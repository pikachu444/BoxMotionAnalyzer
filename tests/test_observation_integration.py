"""PUB10 opt-in settings, strict public identities, export and report guards."""
from copy import deepcopy
import csv
import json
from pathlib import Path

import numpy as np
import pytest

from src.simulation.marker_fixtures import example_profile
from src.simulation.mode_profiles import ModeProfiles, save_profiles, read_profiles, validate_config
from src.simulation.observation_profile import observation_profile, orthographic_camera
from src.simulation.corruption_export import write_observations
from src.simulation.observation_cli import export_settings
from src.simulation.observation_validation import frozen_protocol,aggregate,ENDPOINTS
from src.utils.marker_profile_identity import digest
from src.utils.simulation_metadata import public_configuration,artifact_simulation
from src.utils.observation_metadata import FIELD,artifact_observation,validate_records
from test_observation_profile import truth,spec,reseal


def configured():
    state=ModeProfiles();c=deepcopy(state.configs['single_drop']);m=c['observation_profile']['marker']
    c.update(size_mm=m['profile']['box_dims_mm'],duration_s=.5,show_viewer=False)
    c['physics_profile'].update(mass_kg=1.,com_offset_mm=[0.,0.,0.])
    c['sequence_profile']['steps'][0].update(clearance_mm=3000.,fixed_xyz_deg=[90.,0.,0.])
    m['use_layout_box']=True
    m['observation_profile']=observation_profile(m['profile'],groups=[dict(group_id='front',marker_ids=['F1','F2','F3','F4'])],
        occlusions=[dict(group_id='front',start_s=.08,end_s=.16)],adapter='visibility-mask-to-solved-v1')
    state.set_config(c)
    return state,c


def test_settings_hash_full_roundtrip_source_and_atomic_save(tmp_path,monkeypatch):
    state,c=configured();path=tmp_path/'settings.json';save_profiles(path,state)
    assert read_profiles(path).document()==state.document()
    old=path.read_bytes()
    import src.simulation.mode_profiles as modes
    monkeypatch.setattr(modes.os,'replace',lambda *a:(_ for _ in ()).throw(OSError('injected')))
    with pytest.raises(OSError):save_profiles(path,state)
    assert path.read_bytes()==old
    public=public_configuration(c);m=public['observation_profile']['marker']
    assert m['observation_model']['details']=='evaluation-only'
    assert 'start_s' not in json.dumps(public) and 'camera_to_world' not in json.dumps(public)
    changed=deepcopy(c);p=changed['observation_profile']['marker']['observation_profile'];p['occlusions'][0]['end_s']=.17;reseal(p)
    assert public_configuration(changed)['observation_profile']['marker']['settings_hash']!=m['settings_hash']
    changed['observation_profile']['marker']['observation_profile']['marker_profile_hash']='a'*64
    reseal(changed['observation_profile']['marker']['observation_profile'])
    with pytest.raises(ValueError):validate_config(changed)


def test_cli_profile_choice_actual_engine_and_metadata_reopen(tmp_path):
    from src.analysis.pipeline.data_loader import DataLoader
    state,c=configured();settings=tmp_path/'settings.json';save_profiles(settings,state)
    profile=tmp_path/'observation.json';profile.write_text(json.dumps(c['observation_profile']['marker']['observation_profile']),encoding='utf-8')
    selected=tmp_path/'selected.json'
    output=Path(export_settings(settings,profile,tmp_path/'capture',saved_settings=selected))
    header,raw=DataLoader().load_csv(str(output));public=artifact_simulation(header['artifact_metadata'])
    declaration=artifact_observation(header['artifact_metadata'])
    assert public['configuration']['observation_profile']['marker']['observation_model']['content_hash']==declaration['profile_hash']
    assert read_profiles(selected).configs['single_drop']==c
    assert len(raw)>=50 and declaration['clock']['samples']==len(raw)
    original=output.read_bytes()
    with pytest.raises(FileExistsError):export_settings(settings,profile,output.parent)
    assert output.read_bytes()==original


def test_new_profile_cancel_io_failure_and_no_overwrite(tmp_path,monkeypatch):
    from src.simulation.marker_export import generate_marker_capture
    from src.simulation.scenarios import Scenarios
    import src.simulation.corruption_export as writer
    _,c=configured();m=c['observation_profile']['marker'];p=c['physics_profile'];step=c['sequence_profile']['steps'][0]
    simulation=dict(mode_config=c,mass=p['mass_kg'],friction=p['friction'],elasticity=p['contact_damping_control'],com_offset=p['com_offset_mm'],
        height=step['clearance_mm'],quat=Scenarios.get_orientation_from_euler(*step['fixed_xyz_deg']),duration=c['duration_s'])
    args=(tmp_path/'capture',m['profile'],simulation,m['faults'],m['seed'])
    keep=tmp_path/'old.csv';keep.write_bytes(b'keep')
    with pytest.raises(InterruptedError):generate_marker_capture(*args,cancelled=lambda:True)
    monkeypatch.setattr(writer,'_write_truth',lambda *a:(_ for _ in ()).throw(OSError('injected I/O')))
    with pytest.raises(OSError,match='injected'):generate_marker_capture(*args)
    assert list(tmp_path.iterdir())==[keep] and keep.read_bytes()==b'keep'


@pytest.mark.parametrize('attack',['schema','plan','fields','truth','source','profile','hash','seed','clock','numeric_bool','numeric_text'])
def test_resealed_public_source_corruption_rejected(tmp_path,attack):
    from src.analysis.pipeline.data_loader import DataLoader
    p=observation_profile(example_profile());root=write_observations(tmp_path/'capture',truth(),example_profile(),spec(p),42)
    header,_=DataLoader().load_csv(str(root/'observed.csv'));artifact=deepcopy(header['artifact_metadata'])
    value=json.loads(artifact[FIELD])
    if attack=='schema':value['schema_version']=2
    if attack=='plan':value['plan_spec']='future'
    if attack=='fields':del value['adapter']
    if attack=='truth':value['occlusions']=[]
    if attack=='source':value['source_kind']='real'
    if attack=='profile':value['marker_profile_hash']='a'*64
    if attack=='hash':value['content_hash']='b'*64
    if attack=='seed':value['seed']=False
    if attack=='clock':value['clock']['last_s']=0.
    if attack=='numeric_bool':value['clock']['first_s']=False
    if attack=='numeric_text':value['clock']['last_s']='.1'
    if attack!='hash':reseal(value)
    artifact[FIELD]=json.dumps(value)
    with pytest.raises(ValueError):artifact_simulation(artifact)


@pytest.mark.parametrize('attack',['time','frame','omit','infinite','coordinate_inf','coordinate_nan','coordinate_text'])
def test_actual_record_mismatch_not_hidden_by_parser(tmp_path,attack):
    from src.analysis.pipeline.data_loader import DataLoader
    p=observation_profile(example_profile());root=write_observations(tmp_path/'capture',truth(),example_profile(),spec(p),42)
    path=root/'observed.csv'
    with path.open(newline='',encoding='utf-8') as stream:rows=list(csv.reader(stream))
    if attack=='time':rows[9][1]='.011'
    if attack=='frame':rows[9][0]='102'
    if attack=='omit':rows.pop(9)
    if attack=='infinite':rows[9][1]='inf'
    coordinate=next(i for i,(kind,component) in enumerate(zip(rows[2],rows[7])) if kind=='Marker' and component=='X')
    if attack=='coordinate_inf':rows[9][coordinate]='inf'
    if attack=='coordinate_nan':rows[9][coordinate]='nan'
    if attack=='coordinate_text':rows[9][coordinate]='invalid'
    with path.open('w',newline='',encoding='utf-8') as stream:csv.writer(stream).writerows(rows)
    with pytest.raises(ValueError):DataLoader().load_csv(str(path))


def complete_cases():
    return [dict(case_id=c['case_id'],motion_group=c['motion_group'],
        endpoints={k:dict(expected=c['expected_pose'] if k=='pose_status' else 'exact',
            actual=c['expected_pose'] if k=='pose_status' else 'exact') for k in ENDPOINTS}) for c in frozen_protocol()['cases']]


@pytest.mark.parametrize('attack',['case','duplicate','endpoint','source','expected','unavailable_to_valid','ambiguous_to_valid','failed_to_valid','protocol'])
def test_report_denominators_and_status_cannot_be_promoted(attack):
    p=frozen_protocol();cases=complete_cases()
    if attack=='case':cases.pop()
    if attack=='duplicate':cases[-1]=deepcopy(cases[0])
    if attack=='endpoint':del cases[0]['endpoints']['record_alignment']
    if attack=='source':cases[0]['motion_group']='holdout'
    if attack=='expected':cases[0]['endpoints']['pose_status']['expected']='unavailable'
    if attack=='unavailable_to_valid':cases[7]['endpoints']['pose_status']['actual']='valid'
    if attack=='ambiguous_to_valid':cases[13]['endpoints']['pose_status']['actual']='valid'
    if attack=='failed_to_valid':cases[0]['endpoints']['pose_status']['actual']='failed'
    if attack=='protocol':p['cases'].pop()
    if attack in ('unavailable_to_valid','ambiguous_to_valid','failed_to_valid'):
        assert not aggregate(p,cases)['functional_pass']
    else:
        with pytest.raises(ValueError):aggregate(p,cases)
    report=aggregate(frozen_protocol(),complete_cases())
    assert report['required']==80 and not report['accuracy_pass']


def test_opt_out_matches_before_implementation_snapshots_when_retained():
    # Public repository suite is self-contained; the session also verifies
    # immutable preimplementation snapshots, never regenerates them as expected.
    from test_general_export_recovery import specified_input,CASES
    from src.simulation.marker_corruption import apply_corruption
    path=Path('tmp/issue143/legacy-before.npz')
    if not path.exists():return
    before=np.load(path)
    for case in CASES:
        t,s,_=specified_input(case);r=apply_corruption(t,example_profile(),s,74082)
        for channel in ('physical_markers','rigid_body_markers'):
            np.testing.assert_array_equal(r[channel],before[case+'-'+channel])


@pytest.mark.parametrize('attack',['time','frame','missing_frame','varying_metadata','io'])
def test_result_save_preflight_preserves_existing_file(tmp_path,monkeypatch,attack):
    import pandas as pd
    from src.analysis.pipeline.data_loader import DataLoader
    from src.analysis.pipeline.artifact_io import add_timeline_context_columns,save_proc_file
    import src.analysis.pipeline.artifact_io as writer
    root=write_observations(tmp_path/'capture',truth(),example_profile(),spec(observation_profile(example_profile())),42)
    header,raw=DataLoader().load_csv(str(root/'observed.csv'))
    frame=pd.DataFrame({'Frame':raw.iloc[:,0].astype(int).to_numpy()},index=pd.Index(raw.iloc[:,1].astype(float),name='Time'))
    frame=add_timeline_context_columns(frame,{'artifact_metadata':json.dumps(header['artifact_metadata'])})
    path=tmp_path/'keep.proc';save_proc_file(str(path),frame);before=path.read_bytes()
    # A subset must retain the original time/frame pair, not merely lie inside the clock.
    frame=frame.iloc[1:3].copy()
    if attack=='time':frame.index=pd.Index([.011,.03],name='Time')
    if attack=='frame':frame.iloc[0,frame.columns.get_loc('Frame')]=999
    if attack=='missing_frame':frame=frame.drop(columns='Frame')
    if attack=='varying_metadata':frame.iloc[0,frame.columns.get_loc('Artifact_'+FIELD)]='{}'
    if attack=='io':monkeypatch.setattr(writer.os,'replace',lambda *a:(_ for _ in ()).throw(OSError('injected')))
    with pytest.raises((ValueError,OSError)):save_proc_file(str(path),frame)
    assert path.read_bytes()==before
    assert not list(tmp_path.glob('.proc-*.tmp'))


@pytest.mark.parametrize('attack',['missing_declaration','seed','clock','profile_id'])
def test_new_export_requires_matching_observation_and_simulation_declarations(tmp_path,attack):
    from src.analysis.pipeline.data_loader import DataLoader
    state,c=configured();settings=tmp_path/'settings.json';save_profiles(settings,state)
    profile=tmp_path/'observation.json';profile.write_text(json.dumps(c['observation_profile']['marker']['observation_profile']))
    raw=export_settings(settings,profile,tmp_path/'capture')
    artifact=deepcopy(DataLoader().load_csv(str(raw))[0]['artifact_metadata'])
    if attack=='missing_declaration':artifact[FIELD]=None
    else:
        value=json.loads(artifact[FIELD])
        if attack=='seed':value['seed']+=1
        if attack=='clock':value['clock']['first_s']+=.001
        if attack=='profile_id':value['profile_id']='wrong-profile-id'
        reseal(value);artifact[FIELD]=json.dumps(value)
    with pytest.raises(ValueError):artifact_simulation(artifact)


def test_absent_optional_model_keeps_legacy_time_unavailable_policy(tmp_path):
    import pandas as pd
    from comparison_fixtures import write_proc
    from src.utils.result_time import read_result_frame,time_values,TIME_COLUMN
    path=write_proc(tmp_path/'legacy.proc')
    frame=pd.read_csv(path,header=[0,1,2]).drop(columns=TIME_COLUMN)
    frame.to_csv(path,index=False)
    loaded=read_result_frame(path)
    assert time_values(loaded)[0] is None


def test_original_int64_frames_are_not_rounded_through_float(tmp_path):
    from src.analysis.pipeline.data_loader import DataLoader
    t=truth();t['frame']=[2**63-4,2**63-3,2**63-2,2**63-1]
    root=write_observations(tmp_path/'capture',t,example_profile(),spec(observation_profile(example_profile())),42)
    _,raw=DataLoader().load_csv(str(root/'observed.csv'))
    assert [int(f) for f in raw.iloc[:,0]]==t['frame']


@pytest.mark.parametrize('corrupt_records',[False,True])
def test_required_proc_declarations_cannot_both_be_removed(tmp_path,corrupt_records):
    import pandas as pd
    from src.analysis.pipeline.data_loader import DataLoader
    from src.analysis.pipeline.artifact_io import add_timeline_context_columns,save_proc_file
    from src.utils.result_time import read_result_frame
    root=write_observations(tmp_path/'capture',truth(),example_profile(),spec(observation_profile(example_profile())),42)
    header,raw=DataLoader().load_csv(str(root/'observed.csv'))
    frame=pd.DataFrame({'Frame':raw.iloc[:,0].astype(int).to_numpy()},index=pd.Index(raw.iloc[:,1].astype(float),name='Time'))
    frame=add_timeline_context_columns(frame,{'artifact_metadata':json.dumps(header['artifact_metadata'])})
    target=tmp_path/'keep.proc';save_proc_file(str(target),frame);before=target.read_bytes()
    broken=frame.drop(columns=['Artifact_'+FIELD,'Artifact_SimulationMetadataJson'])
    if corrupt_records:
        broken.index=pd.Index([0.,.012,.04,.1],name='Time');broken.iloc[1,broken.columns.get_loc('Frame')]=999
    with pytest.raises(ValueError,match='declaration is required'):save_proc_file(str(target),broken)
    assert target.read_bytes()==before
    persisted=pd.read_csv(target,header=[0,1,2]).drop(columns=[('Info','Artifact',FIELD),('Info','Artifact','SimulationMetadataJson')])
    if corrupt_records:
        persisted[('Info','Time','Time')]=[0.,.012,.04,.1];persisted[('Info','Frame','Frame')]=[100,999,102,103]
    path=tmp_path/'broken.proc';persisted.to_csv(path,index=False)
    with pytest.raises(ValueError,match='declaration is required'):read_result_frame(path)


def test_header_only_declared_capture_rejected_at_loader_and_parser(tmp_path):
    import pandas as pd
    from src.analysis.pipeline.data_loader import DataLoader
    from src.analysis.pipeline.parser import Parser
    from src.config.data_columns import FACE_PREFIX_TO_INFO
    root=write_observations(tmp_path/'capture',truth(),example_profile(),spec(observation_profile(example_profile())),42)
    path=root/'observed.csv';header,_=DataLoader().load_csv(str(path))
    with path.open(newline='',encoding='utf-8') as stream:rows=list(csv.reader(stream))
    with path.open('w',newline='',encoding='utf-8') as stream:csv.writer(stream).writerows(rows[:8])
    with pytest.raises(ValueError,match='timestamps'):DataLoader().load_csv(str(path))
    with pytest.raises(ValueError,match='timestamps'):Parser(FACE_PREFIX_TO_INFO).process(header,pd.DataFrame())
    legacy=deepcopy(header);legacy['artifact_metadata']={}
    assert Parser(FACE_PREFIX_TO_INFO).process(legacy,pd.DataFrame()).empty


def test_complete_extrema_match_original_clock_and_subsets_remain_supported(tmp_path):
    from src.analysis.pipeline.data_loader import DataLoader
    root=write_observations(tmp_path/'capture',truth(),example_profile(),spec(observation_profile(example_profile())),42)
    artifact=deepcopy(DataLoader().load_csv(str(root/'observed.csv'))[0]['artifact_metadata'])
    validate_records(artifact,[.01,.04],[101,102])
    value=json.loads(artifact[FIELD]);value['clock'].update(first_s=-1.,last_s=.2);reseal(value);artifact[FIELD]=json.dumps(value)
    for complete in (False,True):
        with pytest.raises(ValueError,match='identity'):validate_records(artifact,truth()['time_s'],truth()['frame'],complete=complete)
