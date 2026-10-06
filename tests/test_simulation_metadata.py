"""Independent transform/clock inputs and real PUB06 producer/consumer routes."""
from copy import deepcopy
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from src.simulation.mode_profiles import default_config,require_executable
from src.simulation.engine import MuJoCoEngine
from src.simulation.data_exporter import DataExporter
from src.simulation.marker_export import generate_marker_capture
from src.simulation.history_trajectory import history_to_trajectory
from src.analysis.pipeline.data_loader import DataLoader
from src.analysis.pipeline.parser import Parser
from src.config.data_columns import FACE_PREFIX_TO_INFO
from src.utils.artifact_metadata import read_identity,normalize_metadata
from src.utils.simulation_metadata import (FIELD,build_metadata,validate_public,validate_full,
    artifact_simulation,compatibility_reasons)
from src.utils.marker_profile_identity import digest,canonical
from src.utils.result_time import read_result_frame


def config():
    value=default_config()
    value['size_mm']=[200.,120.,80.]
    value['physics_profile'].update(mass_kg=1.,friction=.4,contact_damping_control=.1,com_offset_mm=[3.,-4.,2.])
    value['sequence_profile']['steps'][0].update(clearance_mm=250.,fixed_xyz_deg=[0.,0.,90.])
    value['duration_s']=.5;value['show_viewer']=False
    return value


def recorded(value):
    p=value['physics_profile']
    engine=MuJoCoEngine(size=value['size_mm'],mass=p['mass_kg'],friction=p['friction'],
        elasticity=p['contact_damping_control'],com_offset=p['com_offset_mm'])
    # Literal +90-degree Z rotation, independent of production Euler conversion.
    engine.set_initial_state(250.,[2**-.5,0.,0.,2**-.5]);engine.build()
    engine.data.qvel[:]=[.1,.2,.3,1.,2.,3.]
    return engine,engine.record_samples(3,4)


def parameters(value):
    p=value['physics_profile'];o=value['observation_profile']['corner'];s=value['sequence_profile']['steps'][0]
    return dict(mass=p['mass_kg'],friction=p['friction'],elasticity=p['contact_damping_control'],
        com_offset=p['com_offset_mm'],height=s['clearance_mm'],quat=[2**-.5,0,0,2**-.5],
        duration=value['duration_s'],add_noise=o['enabled'],noise_std=o['std_mm'],noise_seed=o['seed'],
        mode_config=value,run_id='public-literal-rotation-v1')


def seal(value):
    value['configuration_hash']=digest(value['configuration'])
    value['content_hash']=digest({k:v for k,v in value.items() if k!='content_hash'})
    return value


def artifact(public):
    return normalize_metadata(dict(SourceKind='mujoco_synthetic',
        CoordinatePolicy='world-y-up-box-local-fixed-center-v1',
        UnitsPolicy='bma-mm-s-rotvec-rad-summary-deg-v1' if public['route']=='marker_csv' else 'mm-s-rotvec-rad-global-angular-v1',
        **dict(zip(('BoxLengthMm','BoxWidthMm','BoxHeightMm'),public['configuration']['size_mm'])),
        MarkerLayoutId=public['configuration']['observation_profile']['marker']['profile_id'],
        MarkerLayoutHash=public['configuration']['observation_profile']['marker']['profile_hash'],
        **{FIELD:canonical(public)}),new=True)


def test_literal_release_origin_com_velocity_and_actual_time():
    value=config();engine,history=recorded(value)
    metadata=build_metadata(value,engine,history,route='direct_proc',run_id='literal-v1')
    release=metadata['release_state'];public=metadata['public']
    np.testing.assert_allclose(release['body_origin_mm'],[0,0,290],rtol=0,atol=1e-12)
    np.testing.assert_allclose(release['rotation_matrix'],[[0,-1,0],[1,0,0],[0,0,1]],rtol=0,atol=1e-14)
    np.testing.assert_allclose(release['com_mm'],[4,3,292],rtol=0,atol=1e-12)
    np.testing.assert_allclose(release['origin_linear_velocity_world'],[100,200,300],rtol=0,atol=1e-12)
    np.testing.assert_allclose(release['angular_velocity_body'],[1,2,3],rtol=0,atol=1e-14)
    np.testing.assert_allclose(release['angular_velocity_world'],[-2,1,3],rtol=0,atol=1e-14)
    assert release['status']=='recorded' and release['world_frame']=='mujoco-z-up'
    # The adapter maps WORLD only; the local offset remains [3,-4,2].
    trajectory=history_to_trajectory(history)
    np.testing.assert_allclose(trajectory['body_origin_mm'][0],[0,290,0],rtol=0,atol=1e-12)
    np.testing.assert_allclose(trajectory['com_mm'][0],[4,292,-3],rtol=0,atol=1e-12)
    np.testing.assert_allclose(trajectory['time_s'],[0,.008,.016],rtol=0,atol=1e-15)
    assert public['clock']['samples']==3 and public['clock']['semantics']=='actual-engine-clock'
    assert not any(key in canonical(public) for key in ('release_state"','origin_linear_velocity_world','rotation_matrix','"faults"','"events"'))
    # Initial-only capture avoids per-frame metadata allocations.
    assert 'AngularVelocityBody' not in history[1]


def test_direct_export_reload_preserves_every_existing_numeric_column(tmp_path):
    value=config();engine,history=recorded(value);params=parameters(value)
    old=tmp_path/'old.proc';new=tmp_path/'new.proc'
    legacy=dict(params);legacy.pop('mode_config')
    DataExporter.from_engine(history,engine,legacy).export_proc_csv(old)
    DataExporter.from_engine(history,engine,params).export_proc_csv(new)
    before=read_result_frame(old);after=DataLoader().load_result_csv(str(new))
    for col in before.columns:
        if col[:2] not in [('Info','Artifact'),('Info','Simulation')]:
            np.testing.assert_array_equal(before[col].to_numpy(),after[col].to_numpy())
    public=artifact_simulation(read_identity(after).values)
    assert public['source']['run_id']=='public-literal-rotation-v1'
    assert public['mode']=='single_drop' and public['seed']==0
    assert read_identity(after).values['ModelId'] is None
    assert artifact_simulation(read_identity(before).values) is None  # No invented legacy contract.
    bad=pd.read_csv(new,header=[0,1,2],float_precision='round_trip')
    bad[('Info','Time','Time')]=[0,.008,.02];bad.to_csv(new,index=False)
    with pytest.raises(ValueError,match='clock'):read_result_frame(new)


@pytest.mark.parametrize('example',['18','32'])
def test_marker_observations_reload_and_separate_truth(tmp_path,example):
    from src.simulation.marker_fixtures import load_profile
    from src.utils.marker_profile_identity import profile_identity
    value=config();marker=value['observation_profile']['marker']
    marker['profile']=load_profile(example=example);marker['identity']=profile_identity(marker['profile'])
    marker['use_layout_box']=True;marker['seed']=37
    marker['faults'].update(kind='missing',start=.08,end=.16)
    path=Path(generate_marker_capture(tmp_path/'capture',marker['profile'],parameters(value),marker['faults'],37))
    header,raw=DataLoader().load_csv(str(path));parsed=Parser(FACE_PREFIX_TO_INFO).process(header,raw)
    public=artifact_simulation(header['artifact_metadata'])
    assert public['clock']['samples']==len(parsed)==63
    np.testing.assert_allclose(parsed.index,np.arange(63)*.008,rtol=0,atol=1e-14)
    assert public['configuration']['size_mm']==marker['profile']['box_dims_mm']
    assert public['configuration']['observation_profile']['marker']['profile_hash']==marker['identity']['profile_hash']
    text=path.read_text(encoding='utf-8')
    assert all(key not in text for key in ('release_state"','origin_linear_velocity_world','"faults"','"events"','truth_pose'))
    manifest=json.loads((path.parent/'observed.synthetic.json').read_text())
    full=validate_full(manifest['simulation_metadata'])
    assert full['requested_source_configuration']['size_mm']==[200.,120.,80.]
    assert full['observation_config']['marker']['faults']['start']==.08
    assert full['release_state']['status']=='recorded'
    # Storage/reload uses only the observed declaration after oracle deletion.
    for name in ('truth_pose.csv','truth_markers.csv','observed.synthetic.json'):(path.parent/name).unlink()
    from src.analysis.pipeline.artifact_io import (save_corrected_source_file,save_slice_file,
        read_slice_metadata,add_timeline_context_columns,save_proc_file)
    corrected=path.parent/'reviewed.csv'
    save_corrected_source_file(filepath=str(corrected),header_info=header,raw_data=raw,
        original_source_path=str(path),decisions=[])
    ch,cr=DataLoader().load_csv(str(corrected))
    assert artifact_simulation(ch['artifact_metadata'])==public
    sliced=path.parent/'scene.slice'
    dims=tuple(marker['profile']['box_dims_mm'])
    save_slice_file(filepath=str(sliced),header_info=ch,raw_data=cr,source_path=str(corrected),
        full_start=0,full_end=float(parsed.index[-1]),user_start=.08,user_end=.4,pad_rows=0,box_dims=dims)
    sm=read_slice_metadata(str(sliced));sh,sr=DataLoader().load_csv(str(sliced))
    assert artifact_simulation(sh['artifact_metadata'])==public
    assert artifact_simulation(json.loads(sm.artifact_metadata_json))==public
    # Handcrafted result wrapper is deliberately NOT pipeline approval. It tests
    # the real serializer/loader and excludes absent executed processing identity.
    flat=pd.DataFrame({'Frame':[10,11,12]},index=pd.Index([.08,.088,.096],name='Time'))
    proc=path.parent/'scene.proc'
    save_proc_file(str(proc),add_timeline_context_columns(flat,{'artifact_metadata':sm.artifact_metadata_json}))
    identity=read_identity(DataLoader().load_result_csv(str(proc)))
    assert artifact_simulation(identity.values)==public
    assert any('processing record missing' in reason for reason in identity.exclusion_reasons())


@pytest.mark.parametrize('mutation',[
    lambda p:p.update(schema_version=99),lambda p:p.update(mode='typo'),
    lambda p:p['source'].pop('run_id'),lambda p:p.update(seed=float('inf')),
    lambda p:p['clock'].update(semantics='frame/fps'),lambda p:p['clock'].update(units='ms'),
    lambda p:p['transforms'].update(output_world='z-up'),lambda p:p['transforms']['units'].update(position='m'),
    lambda p:p['configuration']['observation_profile']['corner'].update(enabled='false'),
    lambda p:p['configuration']['observation_profile']['marker'].update(seed=-1),
    lambda p:p['configuration']['observation_profile'].update(faults={'start':.1}),
    lambda p:p.update(release_state={'com':[0,0,0]}),
    lambda p:p['configuration']['physics_profile']['source'].pop('id'),
    lambda p:p['source'].update(release_state=[1,2,3]),
    lambda p:p['generator'].update(truth={'position':[1,2,3]}),
    lambda p:p['clock'].update(events=[.1]),
    lambda p:p['transforms'].update(release_state=[1,2,3]),
    lambda p:p['clock'].update(interval_min_s=.02,interval_max_s=.02),
    lambda p:p['transforms']['engine_to_output_world'][0].__setitem__(0,True),
])
def test_invalid_metadata_cannot_be_resealed_into_success(mutation):
    value=config();engine,history=recorded(value)
    public=build_metadata(value,engine,history,route='direct_proc',run_id='test-v1')['public']
    mutation(public)
    with pytest.raises((ValueError,TypeError,KeyError)):
        seal(public);validate_public(public)


def test_stale_identity_legacy_and_seed_only_compatibility():
    value=config();engine,history=recorded(value)
    public=build_metadata(value,engine,history,route='direct_proc',run_id='first')['public']
    a=artifact(public);other=deepcopy(public);other['source']['run_id']='second'
    other['seed']=3;other['configuration']['observation_profile']['corner']['seed']=3;seal(other)
    b=artifact(other)
    assert compatibility_reasons(a,b)==[]  # IDs/seeds never create n; existing trial resolver counts it.
    assert compatibility_reasons({}, {})==[]
    assert compatibility_reasons(a,{}) and 'unavailable' in compatibility_reasons(a,{})[0]
    other['configuration']['physics_profile']['mass_kg']=2;seal(other)
    assert 'Simulation physics profile differs' in compatibility_reasons(a,artifact(other))
    other['seed']=4
    with pytest.raises(ValueError,match='Stale'):validate_public(other)


def test_robot_marker_producer_blocked_before_engine_or_output(tmp_path,monkeypatch):
    value=default_config('robot_sequence');marker=value['observation_profile']['marker']
    def forbidden(*args,**kwargs):pytest.fail('Blocked mode constructed an engine')
    monkeypatch.setattr('src.simulation.marker_export.MuJoCoEngine',forbidden)
    with pytest.raises(ValueError,match='attach, pickup and release'):
        generate_marker_capture(tmp_path/'blocked',marker['profile'],dict(mode_config=value),marker['faults'],marker['seed'])
    assert not (tmp_path/'blocked').exists()


def test_cancelled_direct_export_preserves_previous_and_retry(tmp_path,monkeypatch):
    from src.simulation import data_exporter
    value=config();engine,history=recorded(value)
    exporter=DataExporter.from_engine(history,engine,parameters(value))
    path=tmp_path/'keep.proc';path.write_text('previous')
    cancelled=False;original=data_exporter.os.fsync
    def cancel_after_write(handle):
        nonlocal cancelled
        original(handle);cancelled=True
    with monkeypatch.context() as patch:
        patch.setattr(data_exporter.os,'fsync',cancel_after_write)
        with pytest.raises(InterruptedError,match='before publication'):
            exporter.export_proc_csv(path,cancelled=lambda:cancelled)
    assert path.read_text()=='previous' and list(tmp_path.iterdir())==[path]
    cancelled=False
    exporter.export_proc_csv(path,cancelled=lambda:cancelled)
    assert artifact_simulation(read_identity(read_result_frame(path)).values)['mode']=='single_drop'


def test_mismatched_initial_release_and_observation_settings_refused():
    value=config();engine,history=recorded(value)
    changed=deepcopy(value);changed['sequence_profile']['steps'][0]['fixed_xyz_deg']=[0,0,0]
    with pytest.raises(ValueError,match='release'):build_metadata(changed,engine,history,route='direct_proc',run_id='bad')
    params=parameters(value);params['noise_std']=2
    with pytest.raises(ValueError,match='Exporter settings'):DataExporter.from_engine(history,engine,params)


def test_direct_timestamp_interior_tampering_rejected(tmp_path):
    value=config();engine,history=recorded(value);path=tmp_path/'times.proc'
    DataExporter.from_engine(history,engine,parameters(value)).export_proc_csv(path)
    frame=pd.read_csv(path,header=[0,1,2],float_precision='round_trip')
    frame[('Info','Time','Time')]=[0,.009,.016];frame.to_csv(path,index=False)
    with pytest.raises(ValueError,match='clock identity'):read_result_frame(path)


@pytest.mark.parametrize('field',['geometry_hash','semantic_hash','observation_mapping_hash'])
def test_marker_public_identity_must_match_artifact(field):
    from src.utils.marker_profile_identity import artifact_fields
    value=config();marker=value['observation_profile']['marker'];marker['use_layout_box']=True
    # Explicit layout size matches this independent geometry fixture.
    engine,history=recorded(value)
    public=build_metadata(value,engine,history,route='marker_csv',run_id='marker-identity')['public']
    declared=artifact(public);declared.update(artifact_fields(marker['profile']))
    public['configuration']['observation_profile']['marker'][field]='1'*64;seal(public)
    declared[FIELD]=canonical(public)
    with pytest.raises(ValueError,match='interpretation identity'):artifact_simulation(declared)


def test_private_fault_settings_have_opaque_compare_identity():
    value=config();engine,history=recorded(value)
    clean=build_metadata(value,engine,history,route='direct_proc',run_id='clean')['public']
    changed=deepcopy(value);changed['observation_profile']['marker']['faults'].update(kind='missing',start=.08,end=.16)
    faults=build_metadata(changed,engine,history,route='direct_proc',run_id='changed-observation')['public']
    assert 'Simulation observation profile differs' in compatibility_reasons(artifact(clean),artifact(faults))
    assert '"faults"' not in canonical(faults) and '"events"' not in canonical(faults)


def test_lower_direct_api_cannot_publish_unrelated_metadata(tmp_path):
    value=config();engine,history=recorded(value)
    full=build_metadata(value,engine,history,route='direct_proc',run_id='lower')
    exporter=DataExporter(history,add_noise=True,noise_std=2,simulation_metadata=full,
        simulation_settings=dict(size_mm=value['size_mm']))
    path=tmp_path/'keep.proc';path.write_text('previous')
    with pytest.raises(ValueError,match='corner export settings'):exporter.export_proc_csv(path)
    assert path.read_text()=='previous'


def test_lower_observations_api_binds_actual_fault_spec(tmp_path):
    from src.simulation.corruption_export import write_observations
    value=config();engine,history=recorded(value);trajectory=history_to_trajectory(history)
    full=build_metadata(value,engine,history,route='marker_csv',run_id='lower-marker')
    marker=value['observation_profile']['marker']
    spec=dict(schema_version=1,events=[dict(kind='missing',channel='rigid_body_markers',start_index=1,end_index_exclusive=2)])
    with pytest.raises(ValueError,match='corruption settings'):
        write_observations(tmp_path/'invalid',trajectory,marker['profile'],spec,marker['seed'],simulation_metadata=full)
    assert not (tmp_path/'invalid').exists()


def test_direct_release_quaternion_binding_and_sign_equivalence(tmp_path):
    value=config();engine,history=recorded(value)
    full=build_metadata(value,engine,history,route='direct_proc',run_id='quaternion-boundary')
    exporter=DataExporter(history,simulation_metadata=full,simulation_settings=dict(size_mm=value['size_mm']))
    history[0]['QuaternionWXYZ']=np.array([1.,0,0,0])
    path=tmp_path/'pose.proc';path.write_text('previous')
    with pytest.raises(ValueError,match='release quaternion'):exporter.export_proc_csv(path)
    assert path.read_text()=='previous'
    history[0]['QuaternionWXYZ']=-np.array([2**-.5,0,0,2**-.5])
    exporter.export_proc_csv(path)
    assert artifact_simulation(read_identity(read_result_frame(path)).values)['mode']=='single_drop'


def test_lower_marker_geometry_preflight_leaves_retry_path_available(tmp_path):
    from src.simulation.corruption_export import write_observations
    value=config();value['size_mm']=[300.,180.,80.]
    engine,history=recorded(value);trajectory=history_to_trajectory(history)
    full=build_metadata(value,engine,history,route='marker_csv',run_id='geometry-preflight')
    marker=value['observation_profile']['marker'];spec=dict(schema_version=1,events=[])
    path=tmp_path/'retry'
    with pytest.raises(ValueError,match='geometry mismatch'):
        write_observations(path,trajectory,marker['profile'],spec,marker['seed'],simulation_metadata=full)
    assert not path.exists()
    # Corrected effective engine size can retry at the same destination.
    fixed=config();engine,history=recorded(fixed);trajectory=history_to_trajectory(history)
    metadata=build_metadata(fixed,engine,history,route='marker_csv',run_id='geometry-retry')
    write_observations(path,trajectory,marker['profile'],spec,marker['seed'],simulation_metadata=metadata)
    assert (path/'observed.csv').exists()
