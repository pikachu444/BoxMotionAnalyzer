"""Frozen PUB10 functional cases through fresh physics and production analysis.

Numerical/stochastic diagnostics remain proposed. Variants share motion groups;
they are neither independent trials nor fit/holdout populations.
"""
import argparse
from contextlib import contextmanager, redirect_stdout
from copy import deepcopy
from dataclasses import asdict
from datetime import datetime, timezone, timedelta
import hashlib
from importlib.metadata import version
import json
from pathlib import Path
import platform
import subprocess
import sys
import time
import traceback

import numpy as np
import pandas as pd
from scipy.spatial.transform import Rotation

from src.utils.marker_profile_identity import envelope, digest, profile_identity
from .observation_profile import observation_profile, orthographic_camera
from .marker_fixtures import example_profile
from .marker_corruption import apply_corruption
from .corruption_export import write_observations
from .marker_export import fault_spec

SEED = 74082
CASE_RULES = (
    ('off', 'single', 'valid'), ('physical-reference', 'single', 'valid'),
    ('camera-recoverable', 'single', 'valid'), ('face-loss', 'single', 'valid'),
    ('single-flip', 'single', 'valid'), ('multiple-flips', 'single', 'mixed'),
    ('all-gap', 'single', 'mixed'), ('all-unavailable', 'single', 'unavailable'),
    ('one-face-rank', 'single', 'unavailable'), ('ou-irregular', 'single', 'valid'),
    ('compound', 'single', 'valid'), ('pub09-seed', 'seeded', 'valid'),
    ('genuine-rotation', 'spinning', 'valid'), ('ambiguous', 'ambiguous', 'ambiguous'),
    ('declared-rank', 'single', 'unavailable'), ('robot-sequence', 'robot', 'valid'))
ENDPOINTS = ('pose_status', 'record_alignment', 'truth_invariance', 'save_reopen', 'correction_policy')


def frozen_protocol():
    return envelope('EvaluationProtocol', protocol_version='pub10-functional-v1',
        cases=[dict(case_id=name, motion_group=source, source_kind='mujoco_synthetic',
            seed=SEED, expected_pose=status, required_endpoints=list(ENDPOINTS),
            evaluation_window='all actual records; irregular is a declared original-record subset')
            for name, source, status in CASE_RULES],
        rules=dict(fault_intervals='[start,end); original records retained',
            single_flips=[dict(time_s=.32, axis='X')], multiple_flips=[dict(time_s=.32,axis='X'),dict(time_s=.56,axis='Y')],
            group_window_s=[.16,.24], freeze_window_s=[.24,.28], jump_window_s=[.28,.32],
            noise=dict(std_mm=.02,tau_s=.08,initialization='stationary',seed=SEED),
            irregular='keep indices not congruent 1 modulo 3; preserve original frames/timestamps',
            physics_runs=8, fresh_observation_variants=16, numerical_tolerance=dict(position_mm=.1,rotation_deg=.1,approval='proposed'),
            stochastic_diagnostic=dict(samples=12000,seed=143,variance_relative=.2,lag_absolute=.2,approval='proposed'),
            original_experimental_n=0, fit_holdout='none; variants share motion_group'),
        approval=dict(software='exact contract and fixed functional checks', numerical='proposed',
            baseline='no promotion', camera_noise='uncalibrated', measured='pending #104'))


def aggregate(protocol, cases):
    if digest(protocol) != digest(frozen_protocol()):
        raise ValueError('Unsupported or changed frozen observation protocol.')
    expected = {c['case_id']: c for c in protocol['cases']}
    if len(cases) != len(expected) or {c['case_id'] for c in cases} != set(expected):
        raise ValueError('Required observation cases missing or duplicated; partial execution cannot pass.')
    counts = dict(required=len(expected)*len(ENDPOINTS), evaluable=0, passed=0,
        ambiguous=0, unavailable=0, failed=0)
    for case in cases:
        if case['motion_group'] != expected[case['case_id']]['motion_group']:
            raise ValueError('Observation motion_group/source mismatch.')
        endpoints = case['endpoints']
        if set(endpoints) != set(ENDPOINTS):
            raise ValueError('Required observation endpoint missing.')
        if endpoints['pose_status']['expected'] != expected[case['case_id']]['expected_pose']:
            raise ValueError('Expected observation pose status changed.')
        for name, item in endpoints.items():
            if set(item) != {'expected','actual'} or item['expected'] not in ('valid','mixed','unavailable','ambiguous','exact'):
                raise ValueError('Unsupported observation endpoint expectation.')
            if name != 'pose_status' and item['expected'] != 'exact':
                raise ValueError('Observation integrity expectation changed.')
            if item['actual'] not in ('valid','mixed','unavailable','ambiguous','exact','failed'):
                raise ValueError('Unsupported observation endpoint status.')
            counts['evaluable'] += item['actual'] not in ('unavailable','ambiguous','failed')
            counts['ambiguous'] += item['actual'] == 'ambiguous'
            counts['unavailable'] += item['actual'] == 'unavailable'
            counts['passed'] += (item['actual'] == item['expected'] and item['actual'] not in ('unavailable','ambiguous','failed'))
            counts['failed'] += item['actual'] != item['expected']
    # Expected unavailable is a functional match, never an available pose/accuracy pass.
    return dict(counts, functional_pass=counts['failed']==0, accuracy_pass=False)


def _save(path, value):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False)+'\n', encoding='utf-8')


def _hash(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _review_record(value):
    """Existing reviewer unavailable scalars become explicit finite JSON evidence."""
    if isinstance(value,dict):return {k:_review_record(v) for k,v in value.items()}
    if isinstance(value,(list,tuple)):return [_review_record(v) for v in value]
    if isinstance(value,float) and not np.isfinite(value):
        return dict(value=None,status='unavailable',reason='Existing reviewer uses a nonfinite sentinel for an unevaluable candidate scalar.',
            original_sentinel='NaN' if np.isnan(value) else 'Infinity' if value>0 else '-Infinity')
    return value


def _serial(trajectory):
    return {k: v.tolist() if isinstance(v, np.ndarray) else v for k, v in trajectory.items()}


def _config(source, marker=None):
    from .mode_profiles import default_config, validate_config
    from .initial_conditions import configured, initial_condition, contact_profile
    marker = example_profile() if marker is None else marker
    if source == 'robot':
        from .robot_validation import fixture
        return fixture()
    c = default_config(); c.update(size_mm=marker['box_dims_mm'], duration_s=.8, show_viewer=False)
    c['physics_profile'].update(mass_kg=1.,com_offset_mm=[0.,0.,0.])
    c['sequence_profile']['steps'][0].update(fixed_xyz_deg=[90.,0.,0.],clearance_mm=3000.)
    c['observation_profile']['marker'].update(profile=marker,identity=profile_identity(marker),use_layout_box=True)
    if source in ('seeded','spinning'):
        q=Rotation.from_euler('x',90,degrees=True).as_quat()[[3,0,1,2]].tolist()
        s=initial_condition([100.,200.,3060.],q,linear_velocity=[25.,-15.,0.],
            angular_velocity=[0.,0.,np.pi/.8] if source=='spinning' else [.1,.2,.3],
            seed_id='pub10-'+source)
        c=configured(c,s,contact_profile())
    return validate_config(c)


def _physics(root, source, config, repeated=False, observation=None):
    from .initial_conditions import engine_from_config
    from .engine.robot_sequence import RobotSequenceEngine
    from .history_trajectory import history_to_trajectory
    from src.utils.simulation_metadata import build_metadata
    if repeated:
        config=deepcopy(config)
        marker=config['observation_profile']['marker']
        marker['observation_profile']=deepcopy(observation) if observation is not None else observation_profile(marker['profile'],
            groups=[dict(group_id='all',marker_ids=[m['id'] for m in marker['profile']['markers']])],
            occlusions=[dict(group_id='all',start_s=.16,end_s=.24)],adapter='visibility-mask-to-solved-v1')
    engine=RobotSequenceEngine(config) if source=='robot' else engine_from_config(config)
    history=engine.run_simulation(show_viewer=False,stop_condition_time=config['duration_s'])
    trajectory=history_to_trajectory(history)
    name=source+('-on' if repeated else '-off')
    _save(root/(name+'-configuration.json'),config)
    _save(root/(name+'-trajectory.json'),_serial(trajectory))
    metadata=build_metadata(config,engine,history,route='marker_csv',run_id='pub10-'+name)
    _save(root/(name+'-metadata.json'),metadata)
    if source=='robot':
        from .robot_evaluation import evaluate_sequence
        result=evaluate_sequence(engine.sequence_evidence,engine.plan,history=history,configuration_hash=digest(config))
        if result['releases']!=2 or result['engine_builds']!=1 or result['status']!='valid':
            raise AssertionError(result)
    return trajectory, metadata, config


def _variant(case, trajectory, marker):
    ids=[m['id'] for m in marker['markers']]
    group=[dict(group_id='front',marker_ids=[m['id'] for m in marker['markers'] if m['face']=='FRONT']),dict(group_id='all',marker_ids=ids)]
    kwargs={}; events=[]; t=deepcopy(trajectory)
    if case in ('physical-reference','camera-recoverable'):
        s2,s3,s6=np.sqrt(2),np.sqrt(3),np.sqrt(6)
        q=np.array([[1/s2,1/s6,-1/s3],[0.,-2/s6,-1/s3],[-1/s2,1/s6,-1/s3]]).tolist()
        kwargs['camera']=orthographic_camera([5000.,5000.,5000.],q)
        if case=='camera-recoverable':kwargs['adapter']='visibility-mask-to-solved-v1'
    if case=='one-face-rank':
        kwargs.update(camera=orthographic_camera([0.,3000.,5000.],[[-1.,0.,0.],[0.,1.,0.],[0.,0.,-1.]]),adapter='visibility-mask-to-solved-v1')
    if case in ('face-loss','single-flip','compound'):
        kwargs.update(groups=group,occlusions=[dict(group_id='front',start_s=.16,end_s=.24)],adapter='visibility-mask-to-solved-v1')
    if case in ('all-gap','multiple-flips','all-unavailable'):
        kwargs.update(groups=group,occlusions=[dict(group_id='all',start_s=0. if case=='all-unavailable' else .16,
            end_s=.8 if case=='all-unavailable' else .24)],adapter='visibility-mask-to-solved-v1')
    if case in ('single-flip','multiple-flips'):
        axes='X' if case=='single-flip' else 'XY'
        events=[dict(kind='flip_180_local_axis',channel='rigid_body_markers',start_index=int(np.searchsorted(t['time_s'],at)),axis=axis)
            for at,axis in zip((.32,.56),axes)]
    if case in ('ou-irregular','compound','pub09-seed','robot-sequence'):
        kwargs['noise']=[dict(noise_id='pub10-ou',channel='rigid_body_markers',marker_ids=ids,
            start_s=float(t['time_s'][0]),end_s=float(t['time_s'][-1]+.001),std_mm=.02,tau_s=.08)]
    if case=='ou-irregular':
        keep=np.arange(len(t['time_s']))%3!=1
        for key in ('time_s','frame','body_origin_mm','com_mm','rotation_matrix'):t[key]=t[key][keep]
    if case=='compound':
        kwargs['noise'].append(dict(kwargs['noise'][0],noise_id='physical-ou',channel='physical_markers'))
        for kind,start,end,extra in [('freeze',.24,.28,{}),('reconnect_jump',.28,.32,dict(offset_mm=[7.,-3.,4.])),
                ('missing',.08,.12,dict(marker_ids=['F1']))]:
            events.append(dict(kind=kind,channel='rigid_body_markers',start_index=int(np.searchsorted(t['time_s'],start)),
                end_index_exclusive=int(np.searchsorted(t['time_s'],end)),**extra))
        events.append(dict(kind='label_permutation',channel='physical_markers',start_index=40,end_index_exclusive=len(t['time_s']),mapping={'F1':'B1','B1':'F1'}))
    if case=='off':return t,dict(schema_version=1,events=[]),None
    p=observation_profile(marker,profile_id='pub10-'+case,**kwargs)
    from src.utils.marker_profile_identity import PLAN_SPEC
    return t,dict(schema_version=2,plan_spec=PLAN_SPEC,events=events,observation_profile=p),p


@contextmanager
def _observed_only():
    import builtins
    import io
    forbidden={'truth_pose.csv','truth_markers.csv','observed.synthetic.json'}
    def guard(original):
        def opening(file,*args,**kwargs):
            if isinstance(file,(str,Path)) and Path(file).name in forbidden:
                raise AssertionError('Production attempted to read evaluation truth.')
            return original(file,*args,**kwargs)
        return opening
    original,io_original=builtins.open,io.open
    builtins.open,io.open=guard(original),guard(io_original)
    try:yield
    finally:builtins.open,io.open=original,io_original


def _process(path,marker,output,choices):
    with _observed_only():return _process_impl(path,marker,output,choices)


def _process_impl(path, marker, output, choices):
    from src.analysis.pipeline.data_loader import DataLoader
    from src.analysis.pipeline.parser import Parser
    from src.analysis.pipeline.pipeline_controller import PipelineController
    from src.analysis.pipeline.marker_review import review_observations
    from src.analysis.pipeline.marker_flip import MarkerCorrectionDecision
    from src.analysis.pipeline.face_assignment import materialize_face_assignments, POSE_COLUMNS
    from src.analysis.pipeline.artifact_io import (save_corrected_source_file, save_slice_file,
        save_proc_file, add_timeline_context_columns, read_slice_metadata)
    from src.config.data_columns import FACE_PREFIX_TO_INFO, SourceCols
    from src.config.config_analysis_ui import get_raw_mode_options
    header,raw=DataLoader().load_csv(str(path))
    parsed=Parser(FACE_PREFIX_TO_INFO).process(header,raw)
    review=review_observations(parsed,marker['box_dims_mm'])
    decisions=[];selected=set()
    for candidate in review['candidates']:
        at=round(candidate.boundary_time_sec,8);axis=choices.get(at)
        if axis: selected.add(at)
        decisions.append(MarkerCorrectionDecision(candidate.event_id,candidate.boundary_time_sec,
            approved=axis is not None,axis=axis,recommendation_axis=candidate.recommendation_axis,
            recommendation_reason=candidate.reason,evidence_json=candidate.evidence_json(),
            algorithm_version=candidate.algorithm_version,gate_version=candidate.gate_version,correction_kind=candidate.correction_kind))
    if selected!=set(choices):raise AssertionError('Required independently chosen flip boundary not observed.')
    # Approval is an authored operator action after candidate creation, never a detector input.
    _save(output/'review.json',_review_record(dict(candidates=[asdict(c) for c in review['candidates']],decisions=[asdict(d) for d in decisions],statistics=review['statistics'])))
    active=path;correction_metadata=None
    if choices:
        h,r=materialize_face_assignments(header,raw,decisions,{m['id']:m['face'] for m in marker['markers']})
        context=json.dumps(dict(box_dims_mm=marker['box_dims_mm'],base_faces={m['id']:m['face'] for m in marker['markers']},
            coordinate_policy='global-y-up-box-xyz-mm',source_sha256=_hash(path),export_metadata=header['export_metadata']))
        active=output/'corrected.csv'
        correction_metadata=save_corrected_source_file(filepath=str(active),header_info=h,raw_data=r,original_source_path=str(path),decisions=decisions,context_json=context)
        header,raw=DataLoader().load_csv(str(active))
    slice_path=output/'observed.slice'
    save_slice_file(filepath=str(slice_path),header_info=header,raw_data=raw,source_path=str(active),
        full_start=float(raw['Time'].iloc[0]),full_end=float(raw['Time'].iloc[-1]),user_start=float(raw['Time'].iloc[0]),
        user_end=float(raw['Time'].iloc[-1]),box_dims=marker['box_dims_mm'],pad_rows=50,
        marker_correction_metadata=correction_metadata)
    sh,sr=DataLoader().load_csv(str(slice_path));sp=Parser(FACE_PREFIX_TO_INFO).process(sh,sr)
    options=dict(box_dimensions=marker['box_dims_mm'],processing_mode='raw',enable_result_resampling=False,
        analysis_options=get_raw_mode_options(),slice_filter_by='time',slice_start_val=float(sp.index[0]),slice_end_val=float(sp.index[-1]))
    result=PipelineController().process_parsed_data(options,sp)
    metadata=read_slice_metadata(str(slice_path))
    context=dict(artifact_metadata=metadata.artifact_metadata_json,
        full_start_sec=metadata.full_start,full_end_sec=metadata.full_end,
        slice_start_sec=metadata.user_start,slice_end_sec=metadata.user_end)
    if metadata.correction_schema_version:
        context.update(marker_correction_schema_version=metadata.correction_schema_version,
            marker_correction_context_json=metadata.correction_context_json,
            marker_correction_algorithm_version=metadata.correction_algorithm_version,
            marker_correction_original_source=metadata.correction_original_source,
            marker_correction_original_source_sha256=metadata.correction_original_source_sha256,
            marker_correction_reviewed_source=metadata.correction_reviewed_source or metadata.source,
            marker_correction_event_count=metadata.correction_event_count,
            marker_correction_approved_event_count=metadata.correction_approved_event_count,
            marker_correction_events_json=metadata.correction_events_json)
    save_proc_file(str(output/'observed.proc'),add_timeline_context_columns(result,context))
    reopened=DataLoader().load_result_csv(str(output/'observed.proc'))
    from src.utils.result_time import read_result_frame
    normalized=read_result_frame(output/'observed.proc')
    # Result reader flattens saved multi-header columns; compare pose/time/status below.
    from src.config.data_columns import PoseCols
    from src.utils.result_time import TIME_COLUMN
    columns=[('Position','CoM',a) for a in ('P_TX','P_TY','P_TZ','P_RX','P_RY','P_RZ')]
    np.testing.assert_allclose(normalized[TIME_COLUMN],result.index,rtol=0,atol=1e-14)
    np.testing.assert_allclose(normalized[columns].to_numpy(float),result[list(POSE_COLUMNS)].to_numpy(float),rtol=0,atol=1e-12,equal_nan=True)
    np.testing.assert_array_equal(normalized[('Info','Pose','Source')],result[SourceCols.POSE])
    np.testing.assert_array_equal(normalized[('Info','Frame','Frame')],pd.to_numeric(result['Frame']))
    from src.utils.artifact_metadata import read_identity
    saved_identity=read_identity(normalized).values
    if any(saved_identity[k]!=v for k,v in header['artifact_metadata'].items()
            if k not in ('ProcessingSemanticsVersion','ProcessingSettingsJson')):
        raise AssertionError('Saved/reopened result changed observation source metadata.')
    return result,review,header,normalized


def _pose_status(result):
    from src.analysis.pipeline.face_assignment import POSE_COLUMNS
    from src.config.data_columns import SourceCols
    valid=np.isfinite(result[list(POSE_COLUMNS)].to_numpy(float)).all(axis=1)
    ambiguous=result[SourceCols.POSE].eq('AmbiguousGeometry').to_numpy()
    if valid.all():status='valid'
    elif ambiguous.all():status='ambiguous'
    elif not valid.any():status='unavailable'
    else:status='mixed'
    return status,valid,dict(required=len(result),evaluable=int(valid.sum()),valid=int(valid.sum()),
        unavailable=int((~valid & ~ambiguous).sum()),ambiguous=int(ambiguous.sum()),
        pose_source_counts=result[SourceCols.POSE].value_counts().to_dict())


def _diagnostics(result, t):
    from src.analysis.pipeline.face_assignment import POSE_COLUMNS
    pose=result[list(POSE_COLUMNS)].to_numpy(float);valid=np.isfinite(pose).all(axis=1)
    if not valid.any():return dict(status='unavailable',reason='No identifiable production poses.',position_mm=None,rotation_deg=None)
    pos=np.linalg.norm(pose[valid,:3]-t['body_origin_mm'][valid],axis=1)
    rot=np.degrees((Rotation.from_matrix(t['rotation_matrix'][valid]).inv()*Rotation.from_rotvec(pose[valid,3:])).magnitude())
    return dict(status='needs_review',reason='Proposed synthetic diagnostics; no tolerance or baseline promotion.',
        max_position_mm=float(pos.max()),max_rotation_deg=float(rot.max()),
        within_proposed=bool(pos.max()<=.1 and rot.max()<=.1))


def _case(root, rule, sources, counts):
    name,source,expected=rule;trajectory,metadata,config=sources[source]
    marker=deepcopy(config['observation_profile']['marker']['profile'])
    if name=='declared-rank':
        from .profile_semantic_fixtures import rank_deficient_face_profile
        marker=rank_deficient_face_profile()
    t,spec,p=_variant(name,trajectory,marker)
    before=digest(_serial(t));output=root/name;output.mkdir()
    _save(output/'spec.json',spec);_save(output/'truth-input.json',_serial(t))
    # Different Raw clock subset or unsupported declared geometry keeps its own
    # source identity; it cannot reuse complete source metadata for a different capture.
    bind=metadata if name=='off' else None
    if name in ('pub09-seed','robot-sequence'):
        # These sources were actually executed with this captured profile.
        # Never rebind a robot's configuration hash or regenerate state evidence.
        if config['observation_profile']['marker']['observation_profile']!=p:
            raise AssertionError('Captured observation configuration differs from generated variant.')
        bind=metadata
    counts['observation_attempted']+=1
    directory=write_observations(output/'capture',t,marker,spec,SEED,simulation_metadata=bind)
    counts['observation_fresh']+=1
    choices={.32:'X',.56:'Y'} if name=='multiple-flips' else {.32:'X'} if name=='single-flip' else {}
    counts['production_attempted']+=1
    result,review,header,reopened=_process(directory/'observed.csv',marker,output,choices)
    counts['production_fresh']+=1
    status,valid,coverage=_pose_status(result)
    np.testing.assert_array_equal(result.index,t['time_s'])
    np.testing.assert_array_equal(pd.to_numeric(result['Frame']).to_numpy(),t['frame'])
    actual=apply_corruption(t,marker,spec,SEED)
    np.testing.assert_array_equal(actual['body_origin_mm'],t['body_origin_mm'])
    np.testing.assert_array_equal(actual['rotation_matrix'],t['rotation_matrix'])
    if before!=digest(_serial(t)):raise AssertionError('Observation changed truth input.')
    if name in ('all-gap','multiple-flips'):
        np.testing.assert_array_equal(valid,~((t['time_s']>=.16)&(t['time_s']<.24)))
    if name=='physical-reference':np.testing.assert_array_equal(actual['rigid_body_markers'],actual['truth_markers'])
    endpoints={k:dict(expected='exact',actual='exact') for k in ENDPOINTS}
    endpoints['pose_status']=dict(expected=expected,actual=status)
    # Preserve raw truth before label mutation/deletion. Controls are additional
    # fresh production runs on the same motion, not independent physical trials.
    controls=[]
    if name=='pub09-seed':
        manifest=directory/'observed.synthetic.json';original=manifest.read_bytes()
        _save(output/'original-manifest.json',json.loads(original))
        changed=json.loads(original);changed['events']=[dict(kind='arbitrary-oracle-label')]
        changed['observation_evidence']['combined_unavailable']=[];_save(manifest,changed)
        for suffix in ('labels','deleted'):
            if suffix=='deleted':
                for path in ('truth_pose.csv','truth_markers.csv','observed.synthetic.json'):(directory/path).unlink()
            target=output/('oracle-'+suffix);target.mkdir()
            counts['production_attempted']+=1
            r2,_,_,_=_process(directory/'observed.csv',marker,target,{})
            counts['production_fresh']+=1
            pd.testing.assert_frame_equal(result,r2)
            controls.append(dict(kind=suffix,actual='exactly_equal',production_fresh=True))
    report=dict(case_id=name,motion_group=source,source_kind='mujoco_synthetic',seed=SEED,
        truth_hash=before,raw_sha256=_hash(directory/'observed.csv'),profile_hash=digest(marker),
        observation_profile_hash=None if p is None else p['content_hash'],spec_hash=digest(spec),
        metadata_status='source-bound' if bind is not None else 'explicit synthetic trajectory/profile; no complete simulation declaration',
        actual_record_count=len(t['time_s']),evaluation_window=dict(first_s=float(t['time_s'][0]),last_s=float(t['time_s'][-1]),last_included=True),
        endpoints=endpoints,pose_coverage=coverage,diagnostics=_diagnostics(result,t),
        fresh_observations=1,fresh_production=1+len(controls),physics='reused from fresh source '+source,
        controls=controls,review_fits=review['statistics']['nonlinear_fits'])
    _save(output/'case-report.json',report)
    return report


def stochastic_diagnostic():
    """Independent long-path diagnostic; uncertainty accounts for OU effective n."""
    count=12000;dt=.02;tau=.08;sigma=.02;times=np.arange(count)*dt
    t=dict(schema_version=1,source_kind='handcrafted_dummy',coordinate_policy='world-y-up-box-local-fixed-center-v1',
        time_s=times,body_origin_mm=np.zeros((count,3)),rotation_matrix=np.repeat(np.eye(3)[None],count,axis=0))
    p=observation_profile(example_profile(),noise=[dict(noise_id='statistics',channel='physical_markers',marker_ids=['F1'],start_s=0.,end_s=float(times[-1]+.001),std_mm=sigma,tau_s=tau)])
    from src.utils.marker_profile_identity import PLAN_SPEC
    r=apply_corruption(t,example_profile(),dict(schema_version=2,plan_spec=PLAN_SPEC,observation_profile=p,events=[]),143)
    x=(r['physical_markers']-r['truth_markers'])[:,0];a=np.exp(-dt/tau)
    var=x.var(axis=0);lag=np.array([np.corrcoef(x[:-1,k],x[1:,k])[0,1] for k in range(3)])
    return dict(status='needs_review',approval='proposed',samples=count,effective_n_approx=float(count*(1-a)/(1+a)),
        expected=dict(variance_mm2=sigma**2,lag=float(a)),actual=dict(variance_mm2=var.tolist(),lag=lag.tolist()),
        within_proposed=bool(np.max(np.abs(var/sigma**2-1))<=.2 and np.max(np.abs(lag-a))<=.2),
        initial_distribution_check='literal recurrence + separate independent ensemble in tests; no burn-in or normalization')


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',required=True)
    args=parser.parse_args(argv);root=Path(args.output);root.mkdir(parents=True,exist_ok=False)
    start=time.monotonic();stamp=datetime.now(timezone.utc);protocol=frozen_protocol()
    paths=sorted([*Path('src/simulation').rglob('*.py'),*Path('src/utils').glob('*.py'),*Path('src/analysis/pipeline').glob('*.py')])
    hashes={str(p):_hash(p) for p in paths}
    report=envelope('RunReport',run_id='pub10-'+stamp.strftime('%Y%m%dT%H%M%SZ'),utc=stamp.isoformat(),
        kst=stamp.astimezone(timezone(timedelta(hours=9))).isoformat(),
        command=[sys.executable,'-m','src.simulation.observation_validation',*(sys.argv[1:] if argv is None else argv)],
        invocation_source='interpreter-module' if argv is None else 'caller-supplied-main-argv',tier='pub10-fresh-production',
        code=dict(commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
            dirty=subprocess.check_output(['git','status','--porcelain','--untracked-files=no'],text=True).splitlines(),source_sha256=hashes),
        environment=dict(os=platform.platform(),python=platform.python_version(),executable=sys.executable,
            dependencies={n:version(n) for n in ('mujoco','numpy','scipy','pandas','PySide6')}),
        protocol=protocol,protocol_hash=digest(protocol),schema_versions=dict(profile=1,spec=2,evidence=1,simulation=1,artifact=1),
        cases=[],physics_fresh=0,physics_attempted=0,observation_fresh=0,observation_attempted=0,
        production_fresh=0,production_attempted=0,reused_results=0,completion='running',exit_code=1,
        peak_memory=dict(status='unavailable',reason='No process memory instrumentation'),
        optimizer_calls=dict(status='unavailable',reason='Review fit count only; whole production optimizer calls uninstrumented'),
        independent_review=dict(status='pending'),measured=dict(status='pending',reason='#104; no verified measured dataset'))
    _save(root/'protocol.json',protocol)
    try:
        from .profile_semantic_fixtures import ambiguous_face_profile
        sources={}
        for source in ('single','seeded','spinning','ambiguous','robot'):
            marker=ambiguous_face_profile() if source=='ambiguous' else None
            c=_config(source,marker)
            report['physics_attempted']+=1
            sources[source]=_physics(root/'physics',source,c);report['physics_fresh']+=1
            if source in ('single','seeded','robot'):
                report['physics_attempted']+=1
                selected=None
                if source in ('seeded','robot'):
                    selected=_variant('pub09-seed' if source=='seeded' else 'robot-sequence',sources[source][0],
                        c['observation_profile']['marker']['profile'])[2]
                recorded=_physics(root/'physics',source,c,repeated=True,observation=selected)
                on=recorded[0];report['physics_fresh']+=1
                if digest(_serial(on))!=digest(_serial(sources[source][0])):raise AssertionError('Opt-in observations changed actual physics '+source)
                if source in ('seeded','robot'):sources[source]=recorded
        for rule in CASE_RULES:
            before=time.monotonic()
            with (root/(rule[0]+'.log')).open('x',encoding='utf-8') as log,redirect_stdout(log):
                case=_case(root,rule,sources,report)
            case['duration_s']=time.monotonic()-before;report['cases'].append(case)
            _save(root/'RunReport.json',report)
            print(json.dumps(dict(case=rule[0],pose=case['endpoints']['pose_status'],duration_s=case['duration_s'])),flush=True)
        report['endpoints']=aggregate(protocol,report['cases'])
        if not report['endpoints']['functional_pass']:raise AssertionError('Required functional endpoint failed.')
        report['statistics']=stochastic_diagnostic()
        report.update(completion='needs_review',exit_code=0,reason='Required software contracts matched; numeric diagnostics proposed, real calibration pending.')
    except BaseException as error:
        report.update(completion='fail',exit_code=1,reason=str(error),exception_type=type(error).__name__,traceback=traceback.format_exc())
    finally:
        after={str(p):_hash(p) for p in paths};report['source_sha256_at_completion']=after
        report['source_changed_during_execution']=hashes!=after
        if hashes!=after:report.update(completion='fail',exit_code=1,reason='Source changed during required fresh execution.')
        report['coverage']=dict(required_cases=len(CASE_RULES),executed_cases=len(report['cases']),unexecuted_cases=len(CASE_RULES)-len(report['cases']),
            required_physics=8,fresh_physics=report['physics_fresh'],reused_physics_for_variants=len(report['cases']),
            physics_attempted=report['physics_attempted'],physics_failed=report['physics_attempted']-report['physics_fresh'],
            required_observations=16,fresh_observations=report['observation_fresh'],fresh_production=report['production_fresh'],
            production_attempted=report['production_attempted'],production_failed=report['production_attempted']-report['production_fresh'],
            observations_attempted=report['observation_attempted'],observations_failed=report['observation_attempted']-report['observation_fresh'],
            reused_results=0,approved_numerical=0,original_experimental_n=0,
            unexecuted_reason=None if len(report['cases'])==len(CASE_RULES) else report.get('reason','Incomplete run'),cache_origin='none')
        report['duration_s']=time.monotonic()-start;_save(root/'RunReport.json',report)
    print(json.dumps(dict(output=str(root),completion=report['completion'],exit_code=report['exit_code'])))
    return report['exit_code']


if __name__=='__main__':raise SystemExit(main())
