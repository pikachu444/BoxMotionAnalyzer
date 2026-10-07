"""PUB08 fresh public contacts -> persisted truth -> production observed Raw."""
import argparse
from copy import deepcopy
from dataclasses import asdict
from datetime import datetime,timezone,timedelta
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

from src.utils.marker_profile_identity import envelope,digest
from .contact_policy import event_policy,frozen_protocol,policy_approval
from .contact_fixtures import public_case
from .contact_evaluation import evaluate_contacts,evaluate_available,save_document,load_recording,load_evaluation
from .contact_comparison import observed_events,compare_events,motion_diagnostics,observation_pair


def _hash(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def analyze_raw(path, size, *, start=None,end=None):
    """Only CSV/header and declared geometry enter the existing production path."""
    from src.analysis.pipeline.data_loader import DataLoader
    from src.analysis.pipeline.parser import Parser
    from src.analysis.pipeline.pipeline_controller import PipelineController
    from src.config.data_columns import FACE_PREFIX_TO_INFO
    from src.config.config_analysis_ui import get_raw_mode_options
    header,raw=DataLoader().load_csv(str(path));parsed=Parser(FACE_PREFIX_TO_INFO).process(header,raw)
    controller=PipelineController()
    if start is not None:parsed=parsed.loc[(parsed.index>=start)&(parsed.index<end)].copy()
    config=dict(box_dimensions=size,processing_mode='raw',enable_result_resampling=False,analysis_options=get_raw_mode_options(),
        slice_filter_by='time',slice_start_val=float(parsed.index[0]),slice_end_val=float(parsed.index[-1]))
    result=controller.process_parsed_data(config,parsed)
    from src.utils.processing_settings import SETTINGS_ATTR
    source=dict(raw_sha256=_hash(path),geometry_mm=list(size),processing_settings=result.attrs.get(SETTINGS_ATTR,{}),
        interval_s=[float(result.index[0]),float(result.index[-1])],source_kind='public_synthetic_observed_csv')
    from src.utils.simulation_metadata import artifact_simulation
    simulation=artifact_simulation(header.get('artifact_metadata'))
    if simulation is not None:source['public_configuration_sha256']=simulation['configuration_hash']
    detector=observed_events(result,controller.drop_posture_post_processor,source,threshold_mm=config['analysis_options'].get('drop_posture_contact_threshold_mm',1.))
    return result,detector,header,raw


def _logic(root,policy):
    results=[]
    for expected in frozen_protocol()['expectations']:
        recording=public_case(expected['case_id']);window=(.08,.16) if expected['case_id']=='out-of-window' else None
        evaluation=evaluate_contacts(recording,policy,window=window)
        actual=dict(kinds=[e['kind'] for e in evaluation['events']],t2_status=evaluation['t2']['status'])
        passed=actual=={k:expected[k] for k in ('kinds','t2_status')}
        save_document(root/(expected['case_id']+'-evaluation.json'),evaluation)
        results.append(dict(case_id=expected['case_id'],expected=expected,actual=actual,input_sha256=digest(recording),
            status='pass' if passed else 'fail',fresh=True,reused=False,scope='hand-specified logic; not physical calibration'))
        if not passed:raise AssertionError(results[-1])
    return results


def _real_single(root,policy,case_id,xyz,elasticity,expected):
    from .engine.mujoco_engine import MuJoCoEngine
    from .marker_fixtures import load_profile
    from .history_trajectory import history_to_trajectory
    from .corruption_export import write_observations
    size=[200.,120.,80.];source=dict(case_id=case_id,kind='actual_mujoco_public_single',geometry_mm=size,
        mass_kg=1.,initial_clearance_mm=100.,xyz_deg=xyz,damping_control=elasticity)
    engine=MuJoCoEngine(size=size,mass=1.,elasticity=elasticity);engine.set_initial_state(100.,Rotation.from_euler('xyz',xyz,degrees=True).as_quat()[[3,0,1,2]])
    engine.enable_contact_recording(source);history=engine.record_samples(251,4)
    recording=engine.contact_recorder.document();save_document(root/'contacts.json',recording)
    retained=load_recording(root/'contacts.json',source);evaluation=evaluate_contacts(retained,policy)
    save_document(root/'evaluation.json',evaluation)
    evaluation=load_evaluation(root/'evaluation.json',policy,retained)
    impacts=[e for e in evaluation['events'] if e['eligible']]
    check=bool(impacts) and impacts[0]['kind']=='first_floor_impact' and any(e['kind']==expected for e in impacts)
    directory=write_observations(root/'observed',history_to_trajectory(history),load_profile(),dict(schema_version=1,events=[]),74082)
    processed,detector,_,_=analyze_raw(directory/'observed.csv',size)
    from src.analysis.pipeline.artifact_io import save_proc_file
    from src.analysis.pipeline.data_loader import DataLoader
    save_proc_file(str(root/'observed.proc'),processed);reopened=DataLoader().load_result_csv(str(root/'observed.proc'))
    if len(reopened)!=len(processed):raise AssertionError('Production result reopen lost records.')
    pair=observation_pair(evaluation,directory/'observed.csv');save_document(root/'pairing.json',pair)
    comparison=compare_events(evaluation,detector,policy,pairing=pair,approval=policy_approval(policy))
    comparison['post_impact_motion']=motion_diagnostics(recording,evaluation,detector,processed,comparison=comparison)
    save_document(root/'detector.json',detector);save_document(root/'comparison.json',comparison)
    return dict(case_id=case_id,expected=dict(first='first_floor_impact',includes=expected),
        actual=dict(kinds=[e['kind'] for e in impacts],t1=evaluation['t1']['status'],t2=evaluation['t2']['status'],coverage=comparison['coverage']),
        status='pass' if check and detector['status']=='valid' else 'fail',raw_sha256=_hash(directory/'observed.csv'),
        recording_sha256=digest(recording),engine_time_s=recording['samples'][-1]['time_s'],fresh=True,reused=False,
        comparison='diagnostic; no measured/numerical accuracy acceptance')


def _robot(root,policy):
    from .robot_validation import fixture
    from .engine.robot_sequence import RobotSequenceEngine
    from .robot_evaluation import evaluate_sequence
    from .corruption_export import write_observations
    from .history_trajectory import history_to_trajectory
    from src.utils.simulation_metadata import build_metadata
    from src.analysis.pipeline.data_loader import DataLoader
    from src.analysis.pipeline.parser import Parser
    from src.analysis.pipeline.scene_detection import detect_scenes,Registration
    from src.analysis.pipeline.artifact_io import save_slice_file,save_proc_file
    from src.config.data_columns import FACE_PREFIX_TO_INFO
    from src.utils.simulation_metadata import public_configuration
    config=fixture();source=dict(kind='actual_pub07_two_release',configuration_sha256=digest(config),
        public_configuration_sha256=digest(public_configuration(config)),geometry_mm=config['size_mm'])
    save_document(root/'config.json',config)
    engine=RobotSequenceEngine(config);engine.enable_contact_recording(source);history=engine.run_simulation()
    continuity=evaluate_sequence(engine.sequence_evidence,engine.plan,history=history,configuration_hash=digest(config))
    if continuity['releases']!=2 or continuity['engine_builds']!=1 or continuity['status']!='valid':raise AssertionError(continuity)
    save_document(root/'sequence-truth.json',engine.sequence_evidence);save_document(root/'contacts.json',engine.contact_recorder.document())
    recording=load_recording(root/'contacts.json',source);evaluation=evaluate_contacts(recording,policy);save_document(root/'evaluation.json',evaluation)
    evaluation=load_evaluation(root/'evaluation.json',policy,recording)
    marker=config['observation_profile']['marker'];metadata=build_metadata(config,engine,history,route='marker_csv',run_id='pub08-two-release')
    directory=write_observations(root/'observed',history_to_trajectory(history),marker['profile'],dict(schema_version=1,events=[]),marker['seed'],simulation_metadata=metadata)
    raw_path=directory/'observed.csv';processed,detector,header,raw=analyze_raw(raw_path,config['size_mm'])
    if detector['status']!='valid':raise AssertionError(('whole detector adapter',detector['status'],detector['reason']))
    save_proc_file(str(root/'whole.proc'),processed);DataLoader().load_result_csv(str(root/'whole.proc'))
    pair=observation_pair(evaluation,raw_path);save_document(root/'pairing.json',pair)
    comparison=compare_events(evaluation,detector,policy,pairing=pair,approval=policy_approval(policy))
    comparison['post_impact_motion']=motion_diagnostics(recording,evaluation,detector,processed,comparison=comparison)
    save_document(root/'whole-detector.json',detector);save_document(root/'whole-comparison.json',comparison)
    parsed=Parser(FACE_PREFIX_TO_INFO).process(header,raw)
    scenes=detect_scenes(header,raw,parsed,registration=Registration(marker['profile'],0.,1.,(0.,0.,0.),True))
    falls=[c for c in scenes.candidates if c.evidence_class=='free_fall']
    if len(falls)!=2:raise AssertionError('Expected exactly two independently observed free-fall candidates.')
    outputs=[]
    groups=sorted(set(e['release_group_id'] for e in evaluation['events'] if e['eligible']))
    if len(groups)!=2:raise AssertionError('Expected two detached release groups with a first floor impact.')
    for i,candidate in enumerate(falls):
        slice_path=root/f'scene-{i}.slice'
        save_slice_file(filepath=str(slice_path),header_info=header,raw_data=raw,source_path=str(raw_path),
            full_start=float(raw['Time'].iloc[0]),full_end=float(raw['Time'].iloc[-1]),user_start=candidate.start,user_end=candidate.end,
            box_dims=config['size_mm'],pad_rows=50,scene_name='public-observed-candidate')
        result,d,_,_=analyze_raw(slice_path,config['size_mm'])
        if d['status']!='valid':raise AssertionError(('scene detector adapter',i,d['status'],d['reason']))
        save_proc_file(str(root/f'scene-{i}.proc'),result);DataLoader().load_result_csv(str(root/f'scene-{i}.proc'))
        dt=float(np.median(np.diff(result.index)))
        t=evaluate_contacts(recording,policy,window=(float(result.index[0]),float(result.index[-1]+dt)),release_group_id=groups[i])
        save_document(root/f'scene-{i}-evaluation.json',t);t=load_evaluation(root/f'scene-{i}-evaluation.json',policy,recording)
        pair=observation_pair(t,slice_path);save_document(root/f'scene-{i}-pairing.json',pair)
        comparison=compare_events(t,d,policy,pairing=pair,approval=policy_approval(policy));comparison['post_impact_motion']=motion_diagnostics(recording,t,d,result,comparison=comparison)
        save_document(root/f'scene-{i}-comparison.json',comparison)
        outputs.append(dict(candidate=asdict(candidate),release_group_id=groups[i],t1=comparison['t1']['status'],t2=comparison['t2']['status'],coverage=comparison['coverage']))
    # Original Raw bytes are the only event input. Changing/deleting truth cannot affect it.
    manifest=directory/'observed.synthetic.json';original=json.loads(manifest.read_text(encoding='utf-8'))
    changed=deepcopy(original)
    for stage in changed['simulation_metadata']['sequence_evidence']['stages']:stage['kind']='arbitrary-truth-label'
    manifest.write_text(json.dumps(changed),encoding='utf-8')
    p2,d2,_,_=analyze_raw(raw_path,config['size_mm']);pd.testing.assert_frame_equal(processed,p2);assert detector==d2
    save_document(root/'truth-label-control.json',dict(original_manifest_sha256=digest(original),changed_manifest_sha256=digest(changed),observed_result='exactly_equal'))
    for path in ('observed.synthetic.json','truth_pose.csv','truth_markers.csv'):(directory/path).unlink()
    p3,d3,_,_=analyze_raw(raw_path,config['size_mm']);pd.testing.assert_frame_equal(processed,p3);assert detector==d3
    save_document(root/'truth-deletion-control.json',dict(deleted=['observed.synthetic.json','truth_pose.csv','truth_markers.csv'],observed_result='exactly_equal'))
    save_document(root/'retained-original-manifest.json',original)
    return dict(case_id='actual-two-release-production',expected=dict(releases=2,engine_builds=1,observed_falls=2,truth_independence='exactly_equal'),
        actual=dict(releases=2,engine_builds=1,observed_falls=len(falls),truth_independence='exactly_equal',scenes=outputs),
        status='pass',raw_sha256=_hash(raw_path),recording_sha256=digest(recording),engine_time_s=history[-1]['time'],
        fresh=True,reused=False,approval='virtual geometry only; no trial approval',measured_accuracy='unavailable')


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',required=True)
    args=parser.parse_args(argv);root=Path(args.output);root.mkdir(parents=True,exist_ok=False)
    start=time.monotonic();stamp=datetime.now(timezone.utc);policy=event_policy();protocol=frozen_protocol()
    # Freeze before the first evaluator/generator/production execution in this run.
    save_document(root/'policy.json',policy);save_document(root/'protocol.json',protocol)
    source_paths=['src/simulation/'+name+'.py' for name in ('contact_policy','contact_recording','contact_evaluation','contact_comparison','contact_fixtures','contact_validation')]
    source_paths+=['src/simulation/engine/mujoco_engine.py','src/simulation/engine/robot_sequence.py','tests/test_contact_evaluation.py']
    report=envelope('RunReport',run_id='pub08-'+stamp.strftime('%Y%m%dT%H%M%SZ'),utc=stamp.isoformat(),kst=stamp.astimezone(timezone(timedelta(hours=9))).isoformat(),
        command=[sys.executable,*sys.argv],tier='fresh-public-logic-and-production',semantic_version=policy['version'],
        code=dict(commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),dirty=subprocess.check_output(['git','status','--porcelain','--untracked-files=all'],text=True).splitlines(),source_sha256={p:_hash(p) for p in source_paths}),
        environment=dict(os=platform.platform(),python=platform.python_version(),dependencies={n:version(n) for n in ('mujoco','numpy','scipy','pandas','PySide6')}),
        schema_versions=dict(recording=1,evaluation=1,comparison=1,protocol=1),policy_sha256=digest(policy),protocol_sha256=digest(protocol),
        tolerance_version='pub08-numerical-proposed-v1',approval=dict(policy=policy_approval(policy),numerical='proposed',baseline='none',trial='not_evaluated'),
        independent_review='pending',cache_origin='none',optimizer_calls='production path; not instrumented',peak_memory=dict(status='unavailable',reason='Not sampled in bounded functional tier'),
        experimental=dict(status='unavailable',reason='No verified measured dataset; #104'),native=dict(status='not_executed',reason='No UI changes; actual viewer/manual acceptance separate'),cases=[],completion='running')
    active_case='logic'
    try:
        controls=root/'logic';controls.mkdir();report['cases'].extend(_logic(controls,policy))
        # These expectations are fixed before running actual dynamics.
        real_cases=[('actual-face',[0.,0.,0.],0.,'first_floor_impact'),('actual-corner',[20.,25.,0.],0.,'new_feature_impact'),('actual-rebound',[0.,0.,0.],.9,'rebound_recontact')]
        for name,xyz,damping,expected in real_cases:
            active_case=name
            directory=root/name;directory.mkdir();case=_real_single(directory,policy,name,xyz,damping,expected);report['cases'].append(case)
            if case['status']!='pass':raise AssertionError(case)
        active_case='actual-two-release-production';directory=root/'actual-robot';directory.mkdir();report['cases'].append(_robot(directory,policy))
        report.update(completion='needs_review',reason='Software functional contracts pass; numerical/physical accuracy approval remains separate.',exit_code=0)
    except BaseException as error:
        if not any(c['case_id']==active_case for c in report['cases']):report['cases'].append(dict(case_id=active_case,status='fail',reason=str(error),fresh=True,reused=False))
        report.update(completion='fail',reason=str(error),exception_type=type(error).__name__,traceback=traceback.format_exc(),exit_code=1)
    finally:
        report['coverage']=dict(required=13,loaded=len(report['cases']),fresh=len(report['cases']),reused=0,approved=0,
            failed=sum(c['status']=='fail' for c in report['cases']),unexecuted=max(0,13-len(report['cases'])),original_experimental_n=0)
        report['duration_s']=time.monotonic()-start;save_document(root/'RunReport.json',report)
    print(json.dumps(dict(status=report['completion'],cases=len(report['cases']),duration_s=report['duration_s'],reason=report['reason'])))
    return report['exit_code']


if __name__=='__main__':sys.exit(main())
