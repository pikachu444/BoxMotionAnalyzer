"""PUB07 public dynamic fixtures and independently calculated failure controls."""
from copy import deepcopy
import json
import numpy as np
import pandas as pd
import pytest
from scipy.spatial.transform import Rotation
from src.simulation.mode_profiles import default_config, ModeProfiles, require_executable, save_profiles, read_profiles
from src.simulation.robot_profiles import with_example, example_plan, phase, applicability, validate_plan
from src.simulation.robot_evaluation import evaluate_sequence
from src.simulation.engine.robot_sequence import RobotSequenceEngine, SequenceFailure
from src.simulation.data_exporter import DataExporter
from src.simulation.marker_export import generate_marker_capture
from src.analysis.pipeline.data_loader import DataLoader
from src.analysis.pipeline.parser import Parser
from src.analysis.pipeline.scene_detection import detect_scenes, Registration
from src.config.data_columns import FACE_PREFIX_TO_INFO
from src.utils.marker_profile_identity import digest
from src.utils.simulation_metadata import build_metadata, validate_public, artifact_simulation


def config(*, size=(200.,120.,80.), mass=1., com=(0.,0.,0.), family='airborne', face='upward', two=True):
    c=default_config('robot_sequence');c.update(size_mm=list(size),duration_s=30.,show_viewer=False)
    c['physics_profile'].update(mass_kg=mass,friction=.5,contact_damping_control=.15,com_offset_mm=list(com))
    first=c['sequence_profile']['steps'][0];first.update(clearance_mm=100.,fixed_xyz_deg=[0.,0.,0.])
    if family=='floor_supported':
        from src.simulation.scenarios import Scenarios
        first.update(category=Scenarios.CATEGORIES[1],preset_id=Scenarios.get_drop_sequence_specs(Scenarios.CATEGORIES[1])[0].id)
    if two:
        second=deepcopy(first);second.update(step_id='drop-2',fixed_xyz_deg=[0.,0.,30.]);c['sequence_profile']['steps'].append(second)
    return with_example(c,family=family,attachment_face=face)


def params(c):
    p=c['physics_profile'];s=c['sequence_profile']['steps'][0];o=c['observation_profile']['corner']
    from src.simulation.scenarios import Scenarios
    return dict(mass=p['mass_kg'],friction=p['friction'],elasticity=p['contact_damping_control'],com_offset=p['com_offset_mm'],
        height=s['clearance_mm'],quat=Scenarios.get_orientation_from_euler(*s['fixed_xyz_deg']),
        duration=c['duration_s'],add_noise=o['enabled'],noise_std=o['std_mm'],noise_seed=o['seed'],mode_config=c)


@pytest.fixture(scope='module')
def sequence():
    c=config();engine=RobotSequenceEngine(c);history=engine.run_simulation()
    return c,engine,history


def test_two_releases_one_engine_and_phase_boundary_continuity(sequence):
    c,e,h=sequence;result=evaluate_sequence(e.sequence_evidence,e.plan,history=h,configuration_hash=digest(c))
    assert result['status']=='valid' and result['releases']==2 and result['engine_builds']==1
    kinds=[s['kind'] for s in e.sequence_evidence['stages']]
    assert set(('approach','attach','lift','orient','hold','release','free_motion','contact','settle','pickup'))<=set(kinds)
    assert kinds.index('pickup')>kinds.index('release')
    releases=[t for t in e.sequence_evidence['toggles'] if t['kind']=='release']
    assert releases[0]['after']['time_s']<releases[1]['before']['time_s']
    times=np.array([row['time'] for row in h]);assert times[0]==0 and times[-1]>10
    np.testing.assert_allclose(np.diff(times)[:-1],.008,atol=1e-12,rtol=0)
    for t in e.sequence_evidence['toggles']:
        assert t['before']['qpos']==t['after']['qpos'] and t['before']['qvel']==t['after']['qvel']
        assert t['next_step']['time_s']>t['after']['time_s']
    assert e.sequence_evidence['stages'][-1]['end_time_s']==h[-1]['time']
    with pytest.raises(ValueError,match='resumed'): e.run_simulation()


@pytest.mark.parametrize('mutation',['velocity','clock','transform','hold_exit','settle_exit'])
def test_negative_controls_fail_independent_evaluator(sequence,mutation):
    c,e,h=sequence;truth=deepcopy(e.sequence_evidence)
    if mutation=='velocity':truth['toggles'][0]['after']['qvel'][2]+=1
    elif mutation=='clock':truth['toggles'][0]['after']['time_s']=0
    elif mutation=='transform':truth['toggles'][0]['after']['weld_data'][3]+=.1
    else:
        kind='hold' if mutation=='hold_exit' else 'settle'
        stop=next(i for i,s in enumerate(truth['stages']) if s['kind']==kind)
        truth['stages']=truth['stages'][:stop+1];truth['unfinished_phase_ids']=[]
    result=evaluate_sequence(truth,e.plan,history=h,configuration_hash=digest(c))
    assert result['status']=='failed' and result['errors']


@pytest.mark.parametrize('mutation',['boundary_pose','boundary_velocity','stage_status','toggle_phase','duplicate_toggle',
    'next_velocity','next_nonfinite','next_relative','release_relative','completion','unfinished'])
def test_reviewed_boundary_and_evidence_negative_controls(sequence,mutation):
    c,e,h=sequence;truth=deepcopy(e.sequence_evidence)
    if mutation=='boundary_pose':truth['stages'][1]['start_state']['qpos'][0]+=.01
    elif mutation=='boundary_velocity':truth['stages'][1]['start_state']['qvel'][0]+=1.
    elif mutation=='stage_status':truth['stages'][0]['status']='running'
    elif mutation=='toggle_phase':truth['toggles'][0]['phase_id']=truth['toggles'][1]['phase_id']
    elif mutation=='duplicate_toggle':truth['toggles'][1]=deepcopy(truth['toggles'][0])
    elif mutation=='next_velocity':truth['toggles'][0]['next_step']['qvel'][2]+=1.
    elif mutation=='next_nonfinite':truth['toggles'][0]['next_step']['qpos'][0]=float('nan')
    elif mutation=='next_relative':truth['toggles'][0]['next_step']['relative_transform']['origin_mm'][0]+=10.
    elif mutation=='release_relative':
        release=next(t for t in truth['toggles'] if t['kind']=='release');release['after']['relative_transform']['origin_mm'][0]+=10.
    elif mutation=='completion':truth['completion']='arbitrary'
    else:truth['unfinished_phase_ids']=['missing-phase']
    if mutation=='next_nonfinite':
        with pytest.raises(ValueError):evaluate_sequence(truth,e.plan,history=h,configuration_hash=digest(c))
    else:
        assert evaluate_sequence(truth,e.plan,history=h,configuration_hash=digest(c))['status']=='failed'


@pytest.mark.parametrize('kind',['attach','release'])
@pytest.mark.parametrize('outcome',['cancelled','time_limit'])
def test_interrupt_immediately_after_toggle_retains_unavailable_reaction(sequence,tmp_path,kind,outcome):
    from src.simulation.robot_partial import retain_partial
    c,reference,_=sequence;c=deepcopy(c)
    expected=next(t['before']['time_s'] for t in reference.sequence_evidence['toggles'] if t['kind']==kind)
    if outcome=='time_limit':c['duration_s']=expected
    e=RobotSequenceEngine(c)
    def cancelled():
        return bool(e.sequence_evidence['toggles'] and e.sequence_evidence['toggles'][-1]['kind']==kind
            and e.sequence_evidence['toggles'][-1]['next_step'] is None)
    with pytest.raises(SequenceFailure):e.run_simulation(cancelled=cancelled if outcome=='cancelled' else None)
    assert e.sequence_evidence['completion']==outcome
    transition=e.sequence_evidence['toggles'][-1]
    assert transition['kind']==kind and transition['next_step'] is None and transition['next_step_status']=='unavailable'
    assert evaluate_sequence(e.sequence_evidence,e.plan,history=e.history)['status']=='partial'
    previous=tmp_path/'previous.proc';previous.write_bytes(b'keep previous result')
    partial=retain_partial(previous,e)
    assert previous.read_bytes()==b'keep previous result'
    from src.utils.artifact_metadata import read_identity
    public=artifact_simulation(read_identity(DataLoader().load_result_csv(partial)).values)
    assert public['execution_status']==outcome
    damaged=deepcopy(e.sequence_evidence);damaged['terminal_state']['relative_transform']['origin_mm'][0]+=10.
    assert evaluate_sequence(damaged,e.plan,history=e.history)['status']=='failed'


@pytest.mark.parametrize('kind,settings',[('approach',dict(motion_fraction=.5)),('approach',dict(support_pivot_local_mm=[100.,0.,-40.])),
    ('lift',dict(motion_fraction=.5)),('release',dict(motion_fraction=.5)),('release',dict(target_frame='mujoco-z-up-box-origin'))])
def test_ignored_phase_settings_are_rejected(kind,settings):
    c=config();item=next(p for p in c['sequence_profile']['execution_plan']['phases'] if p['kind']==kind);item.update(settings)
    with pytest.raises(ValueError):require_executable(c)


def test_required_phase_chronology_and_actual_source_plan_are_bound(sequence):
    c,e,h=sequence;changed=deepcopy(c);p=changed['sequence_profile']['execution_plan'];phases=p['phases']
    orient=next(i for i,s in enumerate(phases) if s['step_id']=='drop-2' and s['kind']=='orient')
    phases.insert(3,phases.pop(orient))
    with pytest.raises(ValueError):require_executable(changed)
    runner=RobotSequenceEngine(c);runner.plan['phases'][2]['target_origin_mm'][0]+=20
    with pytest.raises(ValueError,match='captured source'):runner.run_simulation()
    runner=deepcopy(e);runner.plan['phases'][2]['target_origin_mm'][0]+=20
    with pytest.raises(ValueError,match='captured source'):build_metadata(c,runner,h,route='direct_proc',run_id='changed-effective-plan')


def test_rotated_nonzero_com_measured_pickup_and_moving_spinning_release():
    c=config(com=(3.,-4.,2.),two=False)
    plan=c['sequence_profile']['execution_plan'];release=next(p for p in plan['phases'] if p['kind']=='release')
    release.update(duration_s=.8,target_origin_mm=[80.,30.,190.],target_xyz_deg=[15.,10.,60.],target_frame='mujoco-z-up-box-origin',motion_fraction=.5)
    e=RobotSequenceEngine(c);h=e.run_simulation()
    event=next(t for t in e.sequence_evidence['toggles'] if t['kind']=='release');s=event['before']['box']
    assert np.linalg.norm(s['origin_velocity_world_mm_s'])>20 and np.linalg.norm(s['angular_velocity_world_rad_s'])>.2
    assert event['before']['box']==event['after']['box']
    r=np.array(s['rotation']);v=np.array(s['origin_velocity_world_mm_s']);w=np.array(s['angular_velocity_world_rad_s'])
    expected_com_v=v+np.cross(w,r@np.array([3.,-4.,2.]))
    # Independently differentiate inertial COM over the next integration step.
    post=event['next_step']['box'];dt=event['next_step']['time_s']-event['after']['time_s']
    p0=np.array(s['origin_mm'])+r@np.array([3.,-4.,2.]);r1=np.array(post['rotation'])
    p1=np.array(post['origin_mm'])+r1@np.array([3.,-4.,2.])
    np.testing.assert_allclose((p1-p0)/dt,expected_com_v,atol=25,rtol=0)
    assert evaluate_sequence(e.sequence_evidence,e.plan,history=h)['status']=='valid'


@pytest.mark.parametrize('size,mass', [((300.,180.,90.),2.),((120.,100.,60.),.5)])
def test_distinct_virtual_geometry_mass_inertia(size,mass):
    c=config(size=size,mass=mass,two=False);e=RobotSequenceEngine(c);e.run_simulation()
    a,b,d=np.array(size)/1000
    expected=mass/12*np.array([b*b+d*d,a*a+d*d,a*a+b*b])
    np.testing.assert_allclose(e.model.body_inertia[e.ids['box']],expected,atol=1e-15,rtol=0)
    assert e.sequence_evidence['completion']=='completed'


def test_type_h_supported_rotation_and_distinct_floor_gripper_contacts():
    c=config(family='floor_supported',two=False);e=RobotSequenceEngine(c);e.run_simulation()
    release=next(t for t in e.sequence_evidence['toggles'] if t['kind']=='release')
    assert release['before']['contacts']['floor_force_n']>0
    angle=Rotation.from_matrix(release['before']['box']['rotation']).magnitude()
    assert angle>np.radians(10)
    assert e.plan['test_type']=='H' and e.sequence_evidence['completion']=='completed'
    assert 'gripper_force_n' in release['before']['contacts']


def test_held_only_and_partial_not_automatic_freefall_approval():
    c=config(family='held_only',two=False);e=RobotSequenceEngine(c);h=e.run_simulation()
    assert e.sequence_evidence['completion']=='partial'
    assert not any(t['kind']=='release' for t in e.sequence_evidence['toggles'])
    assert evaluate_sequence(e.sequence_evidence,e.plan,history=h)['status']=='partial'


def test_actual_registered_detector_two_releases_and_held_only(sequence,tmp_path):
    from src.simulation.corruption_export import write_observations
    from src.simulation.history_trajectory import history_to_trajectory
    records=[('released',*sequence)]
    c=config(family='held_only',two=False);e=RobotSequenceEngine(c);h=e.run_simulation();records.append(('held',c,e,h))
    for name,c,e,h in records:
        marker=c['observation_profile']['marker'];metadata=build_metadata(c,e,h,route='marker_csv',run_id='public-'+name)
        directory=write_observations(tmp_path/name,history_to_trajectory(h),marker['profile'],dict(schema_version=1,events=[]),marker['seed'],simulation_metadata=metadata)
        header,raw=DataLoader().load_csv(str(directory/'observed.csv'));parsed=Parser(FACE_PREFIX_TO_INFO).process(header,raw)
        registration=Registration(marker['profile'],0.,1.,(0.,0.,0.),True)  # Literal virtual geometry, no event/truth input.
        result=detect_scenes(header,raw,parsed,registration=registration)
        falls=[candidate for candidate in result.candidates if candidate.evidence_class=='free_fall']
        assert len(falls)==(2 if name=='released' else 0)


def test_optional_floor_move_flip_and_explicit_omitted_step():
    c=config();p=c['sequence_profile']['execution_plan'];first=c['sequence_profile']['steps'][0]
    p=example_plan(c,selected_step_ids=[first['step_id']]);c['sequence_profile']['execution_plan']=p
    floor=phase('floor_move',101,first['step_id'],1.,target_origin_mm=[50.,0.,39.9])
    p['phases'].insert(2,floor)
    p['phases'].insert(4,phase('flip',102,first['step_id'],1.5,target_xyz_deg=[0.,0.,180.]))
    e=RobotSequenceEngine(c);e.run_simulation()
    stage=next(s for s in e.sequence_evidence['stages'] if s['kind']=='floor_move')
    assert stage['end_state']['contacts']['floor_force_n']>0
    assert abs(stage['end_state']['box']['origin_mm'][0]-50)<5
    flip=next(s for s in e.sequence_evidence['stages'] if s['kind']=='flip')
    assert Rotation.from_matrix(flip['end_state']['box']['rotation']).magnitude()>3
    assert p['omitted_step_ids']==['drop-2'] and len([t for t in e.sequence_evidence['toggles'] if t['kind']=='release'])==1


@pytest.mark.parametrize('reason',['cancelled','time_limit','face'])
def test_cancel_limit_attach_failure_preserves_partial_history(reason):
    c=config(face='-Z' if reason=='face' else 'upward')
    if reason=='time_limit': c['duration_s']=.5
    e=RobotSequenceEngine(c)
    with pytest.raises(SequenceFailure) as caught:
        e.run_simulation(cancelled=(lambda:e.data is not None and e.data.time>.05) if reason=='cancelled' else None)
    expected='failure' if reason=='face' else reason
    assert e.sequence_evidence['completion']==expected
    assert len(caught.value.history)>1 and caught.value.evidence['unfinished_phase_ids']
    assert not any(t['kind']=='release' for t in e.sequence_evidence['toggles'])
    if reason=='cancelled':assert isinstance(caught.value,InterruptedError)


def test_attach_failure_retry_remeasures_and_never_teleports():
    c=config(two=False);e=RobotSequenceEngine(c);original=e.can_attach;calls=[0]
    def temporarily_unavailable(*args):
        result=original(*args);calls[0]+=1
        if e.current_phase['kind']=='attach' and e.data.time<4.5:result['eligible']=False
        return result
    e.can_attach=temporarily_unavailable;e.run_simulation()
    attempts=e.sequence_evidence['attempts']
    assert attempts[0]['status']=='failed' and attempts[1]['status']=='attached'
    assert e.sequence_evidence['completion']=='completed'


def test_side_attachment_face_and_unknown_type_remain_explicit():
    c=config(face='+X',two=False);c['sequence_profile']['execution_plan']['test_type']='unknown'
    e=RobotSequenceEngine(c);h=e.run_simulation()
    t=next(t for t in e.sequence_evidence['toggles'] if t['kind']=='attach')
    np.testing.assert_allclose(t['after']['weld_data'][:3],[.1,0,0],atol=1e-15,rtol=0)
    public=build_metadata(c,e,h,route='direct_proc',run_id='public-side-unknown')['public']
    assert public['configuration']['sequence_profile']['execution_plan']['test_type']=='unknown'


@pytest.mark.parametrize('layout',['32','custom'])
def test_robot_marker_example32_and_custom_geometry_identity(layout,tmp_path):
    from src.simulation.marker_fixtures import load_profile
    from src.utils.marker_profile_identity import profile_identity
    c=config(two=False);marker=c['observation_profile']['marker']
    profile=load_profile(example='32' if layout=='32' else '18')
    if layout=='custom':
        profile['profile_id']='public-pub07-custom';scale=np.array([.8,.9,1.1])
        profile['box_dims_mm']=(np.array(profile['box_dims_mm'])*scale).tolist()
        for item in profile['markers']:item['xyz_mm']=(np.array(item['xyz_mm'])*scale).tolist()
    c['size_mm']=list(profile['box_dims_mm']);marker.update(profile=profile,identity=profile_identity(profile),document=None)
    c=with_example(c)
    observed=generate_marker_capture(tmp_path/layout,profile,params(c),marker['faults'],marker['seed'])
    header,raw=DataLoader().load_csv(observed);public=artifact_simulation(header['artifact_metadata'])
    declared=public['configuration']['observation_profile']['marker']
    assert declared['profile_hash']==marker['identity']['profile_hash'] and declared['geometry_hash']==marker['identity']['geometry_hash']
    assert public['source']['kind']=='mujoco_synthetic'


@pytest.mark.parametrize('field', ['size','mass','attitude'])
def test_applicability_invalidated_but_document_history_retained(field,tmp_path):
    c=config();state=ModeProfiles();state.set_config(c)
    if field=='size':c['size_mm'][0]+=1
    elif field=='mass':c['physics_profile']['mass_kg']+=1
    else:c['sequence_profile']['steps'][0]['fixed_xyz_deg'][2]+=1
    state.set_config(c);save_profiles(tmp_path/'settings.json',state)
    reopened=read_profiles(tmp_path/'settings.json');assert len(reopened.history)==2
    with pytest.raises(ValueError,match='stale'):require_executable(reopened.configs['robot_sequence'])
    legacy=default_config('robot_sequence');state.set_config(legacy);save_profiles(tmp_path/'legacy.json',state)
    with pytest.raises(ValueError,match='#140'):require_executable(read_profiles(tmp_path/'legacy.json').configs['robot_sequence'])


@pytest.mark.parametrize('change', ['version','type','units','nonfinite','source','missingrelease'])
def test_invalid_execution_contract_rejected(change):
    c=config();p=c['sequence_profile']['execution_plan']
    if change=='version':p['schema_version']=99
    elif change=='type':p['test_type']='television'
    elif change=='units':p['endpoint']='world-mm'
    elif change=='nonfinite':p['transition']['distance_mm']=float('nan')
    elif change=='source':p.pop('source')
    else:p['phases']=[i for i in p['phases'] if i['kind']!='release']
    with pytest.raises((ValueError,TypeError,KeyError)):require_executable(c)


def test_real_direct_export_metadata_reload_and_truth_allowlist(sequence,tmp_path):
    c,e,h=sequence;output=tmp_path/'sequence.proc';DataExporter.from_engine(h,e,params(c)).export_proc_csv(output)
    loaded=DataLoader().load_result_csv(str(output))
    from src.utils.artifact_metadata import read_identity
    public=artifact_simulation(read_identity(loaded).values)
    assert public['mode']=='robot_sequence' and public['execution_status']=='completed'
    assert public['clock']['samples']==len(h)
    assert 'sequence_evidence' not in json.dumps(public) and 'next_step' not in json.dumps(public)
    for mutate in ('units','clock','generator'):
        value=deepcopy(public)
        if mutate=='units':value['transforms']['units']['time']='frame'
        elif mutate=='clock':value['clock']['semantics']='release-relative'
        else:value['generator']['version']='pub06-simulation-contract-v1'
        value['content_hash']=digest({k:v for k,v in value.items() if k!='content_hash'})
        with pytest.raises(ValueError):validate_public(value)


def test_marker_producer_real_detector_truth_isolation(tmp_path):
    c=config(two=False);marker=c['observation_profile']['marker']
    output=generate_marker_capture(tmp_path/'capture',marker['profile'],params(c),marker['faults'],marker['seed'])
    def analyze():
        header,raw=DataLoader().load_csv(output);parsed=Parser(FACE_PREFIX_TO_INFO).process(header,raw)
        result=detect_scenes(header,raw,parsed)
        from src.analysis.pipeline.pipeline_controller import PipelineController
        from src.config.config_analysis_ui import get_raw_mode_options
        processed=PipelineController().process_parsed_data(dict(box_dimensions=c['size_mm'],processing_mode='raw',
            slice_filter_by='time',slice_start_val=2.,slice_end_val=2.08,enable_result_resampling=False,
            analysis_options=get_raw_mode_options()),parsed)
        return result,parsed,processed
    original,parsed,processed=analyze()
    manifest=tmp_path/'capture'/'observed.synthetic.json'
    truth=json.loads(manifest.read_text(encoding='utf-8'))
    for stage in truth['simulation_metadata']['sequence_evidence']['stages']:stage['kind']='relabeled-evaluation-only'
    manifest.write_text(json.dumps(truth),encoding='utf-8')
    altered,p2,r2=analyze();assert altered.candidates==original.candidates;pd.testing.assert_frame_equal(parsed,p2);pd.testing.assert_frame_equal(processed,r2)
    for name in ('observed.synthetic.json','truth_pose.csv','truth_markers.csv'):(tmp_path/'capture'/name).unlink()
    removed,p3,r3=analyze();assert removed.candidates==original.candidates;pd.testing.assert_frame_equal(parsed,p3);pd.testing.assert_frame_equal(processed,r3)
    assert len(removed.candidates)>0


def test_partial_retention_does_not_replace_previous_output(tmp_path):
    from src.simulation.robot_partial import retain_partial
    c=config();e=RobotSequenceEngine(c)
    with pytest.raises(SequenceFailure):e.run_simulation(cancelled=lambda:e.data is not None and e.data.time>.05)
    previous=tmp_path/'previous.proc';previous.write_bytes(b'prior complete result')
    partial=retain_partial(previous,e)
    assert previous.read_bytes()==b'prior complete result' and partial!=str(previous)
    from src.utils.artifact_metadata import read_identity
    public=artifact_simulation(read_identity(DataLoader().load_result_csv(partial)).values)
    assert public['execution_status']=='cancelled' and public['mode']=='robot_sequence'
