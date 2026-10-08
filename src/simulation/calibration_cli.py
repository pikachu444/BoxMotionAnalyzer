"""PUB09 reproducible opt-in initial conditions, convergence, fitting and holdout."""
import argparse
from copy import deepcopy
from datetime import datetime, timezone, timedelta
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

from src.utils.marker_profile_identity import envelope, digest
from .initial_conditions import (initial_condition, contact_profile, configured, load, save,
    validate_profile, reseal, canonical_state)
from .contact_calibration import (ENDPOINT_UNITS, freeze_protocol, validate_protocol, run_case,
    reference_from_result, fit, evaluate_holdout, convergence, aggregate)
from .contact_policy import event_policy, policy_approval


def public_cases():
    """Authored protocol inputs/rules precede every synthetic reference execution."""
    from .mode_profiles import default_config
    from .marker_fixtures import load_profile
    from src.utils.marker_profile_identity import profile_identity
    inputs=[('face-fit','fit',[0.,0.,0.],[150.,0.,0.],[0.,0.,0.],['final_origin_x_mm','final_rotation_deg']),
            ('rebound-fit','fit',[0.,0.,0.],[0.,0.,0.],[0.,0.,0.],['dt12_s','rebound_height_mm']),
            ('corner-holdout','holdout',[20.,25.,0.],[30.,0.,-50.],[.2,.1,.3],['dt12_s','final_rotation_deg']),
            ('rebound-holdout','holdout',[0.,0.,0.],[0.,0.,-100.],[0.,0.,0.],['dt12_s','rebound_height_mm'])]
    cases=[]
    for name,split,xyz,v,w,endpoints in inputs:
        c=default_config();c['size_mm']=[200.,120.,80.];c['duration_s']=1.2;c['show_viewer']=False
        marker=load_profile();c['observation_profile']['marker'].update(profile=marker,identity=profile_identity(marker))
        r=Rotation.from_euler('xyz',xyz,degrees=True);q=r.as_quat()[[3,0,1,2]].tolist()
        # Geometric origin; 100 mm initial lowest-corner clearance independent of COM.
        signs=np.array([[-1,-1,-1],[1,-1,-1],[1,1,-1],[-1,1,-1],[-1,-1,1],[1,-1,1],[1,1,1],[-1,1,1]])
        p=[0.,0.,100.-(r.apply(signs*np.array(c['size_mm'])/2))[:,2].min()]
        seed=initial_condition(p,q,linear_velocity=v,angular_velocity=w,seed_id=name)
        c=configured(c,seed,contact_profile(solref=(.02,.4)))
        cases.append(dict(case_id=name,motion_group=name,split=split,configuration=c,window_s=[0.,1.2],
            eligible_endpoints=endpoints,required_endpoints=endpoints,reference_identity=None,
            endpoint_rules={k:dict(units=ENDPOINT_UNITS[k],scale={'s':.01,'mm':10.,'deg':5.}[ENDPOINT_UNITS[k]],
                weight=1.,tolerance={'s':.004,'mm':.5,'deg':.5}[ENDPOINT_UNITS[k]],
                label_uncertainty=0.,modality='actual-contact-recording') for k in endpoints}))
    return cases


def production_roundtrip(root, case, profile):
    """Fresh seeded engine -> both exports -> real observed-only processing -> reopen."""
    from .data_exporter import DataExporter
    from .history_trajectory import history_to_trajectory
    from .corruption_export import write_observations
    from .contact_validation import analyze_raw
    from .contact_comparison import observation_pair, compare_events, motion_diagnostics
    from .contact_evaluation import save_document
    from src.utils.simulation_metadata import build_metadata, validate_full
    from src.analysis.pipeline.artifact_io import save_proc_file
    from src.analysis.pipeline.data_loader import DataLoader
    result,engine,history,evaluation,recording,config=run_case(case,profile,event_policy(),output=root/'engine')
    # Select existing actual samples for observation cadence, never resample/alter clocks.
    stride=4;observed_history=history[::stride]
    corner=config['observation_profile']['corner']
    exporter=DataExporter.from_engine(observed_history,engine,dict(mode_config=config,duration=config['duration_s'],
        add_noise=corner['enabled'],noise_std=corner['std_mm'],noise_seed=corner['seed'],run_id=case['case_id']))
    exporter.export_proc_csv(str(root/'direct.proc'))
    direct=DataLoader().load_result_csv(str(root/'direct.proc'))
    if len(direct)!=len(observed_history):raise AssertionError('Direct export lost actual records.')
    metadata=build_metadata(config,engine,observed_history,route='marker_csv',run_id=case['case_id'])
    save(root/'metadata.json',metadata);validate_full(json.loads((root/'metadata.json').read_text(encoding='utf-8')))
    marker=config['observation_profile']['marker']
    directory=write_observations(root/'observed',history_to_trajectory(observed_history),marker['profile'],
        dict(schema_version=1,events=[]),marker['seed'],simulation_metadata=metadata)
    raw=directory/'observed.csv';processed,detector,_,_=analyze_raw(raw,config['size_mm'])
    if detector['status']!='valid':raise AssertionError(('Production detector adapter failed',detector['status'],detector['reason']))
    save_proc_file(str(root/'observed.proc'),processed)
    reopened=DataLoader().load_result_csv(str(root/'observed.proc'))
    if len(reopened)!=len(processed):raise AssertionError('Production result reopen lost records.')
    pairing=observation_pair(evaluation,raw);save_document(root/'pairing.json',pairing)
    comparison=compare_events(evaluation,detector,event_policy(),pairing=pairing,approval=policy_approval(event_policy()))
    comparison['post_impact_motion']=motion_diagnostics(recording,evaluation,detector,processed,comparison=comparison)
    save_document(root/'detector.json',detector);save_document(root/'comparison.json',comparison)
    manifest=directory/'observed.synthetic.json';original=json.loads(manifest.read_text(encoding='utf-8'))
    save(root/'retained-original-manifest.json',original)
    changed=deepcopy(original);changed['simulation_metadata']['release_state']['body_origin_mm']=[999.,999.,999.]
    manifest.write_text(json.dumps(changed,allow_nan=False),encoding='utf-8')
    changed_processed,changed_detector,_,_=analyze_raw(raw,config['size_mm'])
    pd.testing.assert_frame_equal(processed,changed_processed);assert detector==changed_detector
    for name in ('observed.synthetic.json','truth_pose.csv','truth_markers.csv'):(directory/name).unlink()
    deleted_processed,deleted_detector,_,_=analyze_raw(raw,config['size_mm'])
    pd.testing.assert_frame_equal(processed,deleted_processed);assert detector==deleted_detector
    report=envelope('SeedProductionReport',source_identity=result['source_identity'],case_id=case['case_id'],
        seed_sha256=config['initial_condition']['content_hash'],profile_sha256=profile['content_hash'],
        raw_sha256=pairing['raw_sha256'],actual_times=[observed_history[0]['time'],observed_history[-1]['time']],
        native_sample_selection_stride=stride,rows=len(processed),truth_controls='label-change-and-deletion-exactly-equal',
        event_status={k:comparison[k]['status'] for k in ('t1','t2')},coverage=comparison['coverage'],
        observed_endpoints=[dict(case_id=case['case_id'],endpoint=k,status=comparison[k]['status'],
            within_proposed_tolerance=None) for k in ('t1','t2')],
        execution_status='pass',endpoint_acceptance='needs_review',numeric_accuracy='needs_review',measured_accuracy='pending')
    report['observed_summary']=aggregate(report['observed_endpoints'],2,complete=True)
    report['observed_summary']['modality']='production-observed-Raw'
    save(root/'production-report.json',report)
    return report


def analytical(root):
    """Literal independent ballistic/spin expectations, actual clocks and Jacobians."""
    from .engine.mujoco_engine import MuJoCoEngine
    from .history_trajectory import history_to_trajectory, WORLD_TRANSFORM
    import mujoco
    r=Rotation.from_euler('xyz',[23.,-31.,47.],degrees=True).as_matrix()
    q=Rotation.from_matrix(r).as_quat()[[3,0,1,2]].tolist();offset=np.array([70.,-30.,50.])
    p0=np.array([200.,-100.,3000.]);v0=np.array([400.,-200.,700.]);wb=np.array([.3,-.4,1.2]);w=r@wb
    vcom=v0+np.cross(w,r@offset);pcom=p0+r@offset
    inertia=dict(kind='principal-about-COM',principal_kg_m2=[.02,.02,.02],quaternion_wxyz=[1.,0.,0.,0.])
    results=[];histories=[]
    for dt in (.002,.001,.0005):
        profile=contact_profile(com_offset_mm=offset,inertia=inertia,timestep_s=dt)
        seed=initial_condition(p0,q,linear_velocity=v0,angular_velocity=wb,angular_velocity_frame='body',reference_time_s=12.5)
        e=MuJoCoEngine(size=[200.,120.,80.],contact_profile=profile);e.set_initial_condition(seed);e.build()
        jp=np.zeros((3,e.model.nv));jr=jp.copy();mujoco.mj_jac(e.model,e.data,jp,jr,e.data.xipos[1],1)
        actual_vcom=jp@e.data.qvel*1000
        if not np.allclose(actual_vcom,vcom,rtol=0,atol=1e-9):raise AssertionError('Independent seed COM Jacobian mismatch.')
        h=e.record_samples(round(.2/dt)+1,1);times=np.array([row['time'] for row in h])
        expected_p=pcom+times[:,None]*vcom+np.array([0.,0.,-4905.])*times[:,None]**2
        actual_p=np.array([row['COM'] for row in h]);error=float(np.max(np.linalg.norm(actual_p-expected_p,axis=1)))
        expected_r=Rotation.from_rotvec(times[:,None]*w).as_matrix()@r
        rotation_error=float(np.max(Rotation.from_matrix(np.array([row['RotationMatrix'] for row in h])@expected_r.transpose(0,2,1)).magnitude()))
        trajectory=history_to_trajectory(h)
        if not np.allclose(trajectory['com_mm'],actual_p@WORLD_TRANSFORM.T,rtol=0,atol=1e-9):raise AssertionError('Output transform differs.')
        results.append(dict(timestep_s=dt,time_s=times[-1],expected_com_mm=expected_p[-1].tolist(),actual_com_mm=actual_p[-1].tolist(),
            difference_mm=error,rotation_error_rad=rotation_error,seed_com_velocity_expected_mm_s=vcom.tolist(),
            seed_com_velocity_actual_mm_s=actual_vcom.tolist(),tolerance_status='proposed',scope='Euler truncation;not physical accuracy'))
        native=root/'analytical-runs'/str(dt);native.mkdir(parents=True,exist_ok=False);save(native/'result.json',results[-1])
        histories.append(h)
    if not results[2]['difference_mm']<results[1]['difference_mm']<results[0]['difference_mm']:raise AssertionError('Bounded smooth ballistic refinement contract failed.')
    report=envelope('AnalyticalSeedReport',source_identity=dict(kind='public_literal_ballistic-spherical-inertia'),
        expectations='COM ballistic; spherical inertia constant world spin; origin and corners rotate around COM',
        reference_clock='t_reference=t_engine+12.5;engine-times-unchanged',runs=results,status='pass',numerical_approval='proposed')
    save(root/'analytical.json',report);return report


def demo(root):
    cases=public_cases();base=contact_profile(solref=(.02,.4))
    # Rules/search are authored before reference generation. Reference parameters stay here.
    draft=freeze_protocol(cases);save(root/'pre-reference-protocol.json',draft)
    known=contact_profile(profile_id='synthetic-reference-generator',solref=(.02,.2))
    save(root/'reference-generator-profile.json',known)
    references={}
    for case in cases:
        result,*_=run_case(case,known,event_policy(),output=root/'reference-generation'/case['case_id'])
        ref=reference_from_result(case,result,'reference-'+case['case_id']);references[case['case_id']]=ref
        case['reference_identity']=dict(reference_id=ref['reference_id'],content_hash=ref['content_hash'])
    protocol=freeze_protocol(cases);save(root/'protocol.json',protocol);save(root/'base-profile.json',base)
    fit_refs={c['case_id']:references[c['case_id']] for c in cases if c['split']=='fit'}
    holdout_refs={c['case_id']:references[c['case_id']] for c in cases if c['split']=='holdout'}
    save(root/'fit-references.json',fit_refs);save(root/'holdout-references.json',holdout_refs)
    reports={}
    for case in cases:
        if case['split']=='fit':reports[case['case_id']]=convergence(case,base,protocol['policy'],output=root/'convergence'/case['case_id'])
    save(root/'convergence-input.json',reports)
    fitted=fit(protocol,base,fit_refs,convergence_reports=reports,output=root/'fit')
    # Persist selected profile before any holdout endpoint is evaluated.
    save(root/'selected-profile.json',fitted['selected_profile'])
    held=evaluate_holdout(protocol,fitted,holdout_refs,output=root/'holdout')
    if fitted['identifiability']!='unique-on-grid-only' or fitted['selected_profile']['solref'][1]!=.2:
        raise AssertionError('Synthetic known-on-grid diagnostic recovery failed; no calibrated claim.')
    diagnostics=[]
    for case in cases:
        if case['split']=='holdout':diagnostics.append(production_roundtrip(root/'production'/case['case_id'],case,fitted['selected_profile']))
    observed_records=[r for report in diagnostics for r in report['observed_endpoints']]
    expected=[(c,k) for c in protocol['observed_evaluation']['case_ids'] for k in protocol['observed_evaluation']['required_endpoints']]
    if [(r['case_id'],r['endpoint']) for r in observed_records]!=expected:raise AssertionError('Frozen observed required population differs.')
    observed_summary=aggregate(observed_records,len(expected),complete=True)
    observed_summary['modality']='production-observed-Raw'
    save(root/'observed-holdout-report.json',envelope('ObservedHoldoutReport',protocol_sha256=protocol['content_hash'],
        selected_profile_sha256=fitted['selected_profile_sha256'],candidate_selection='already-frozen;observations-not-used',
        endpoints=observed_records,summary=observed_summary))
    return dict(protocol_sha256=protocol['content_hash'],profile_sha256=fitted['selected_profile_sha256'],
        fit_identifiability=fitted['identifiability'],fit_summary=fitted['candidates'][1]['summary'],
        synthetic_holdout_summary=dict(**held['summary'],modality='synthetic-self-consistency'),observed_holdout_summary=observed_summary,
        production=diagnostics,analytical=analytical(root))


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__);sub=parser.add_subparsers(dest='command',required=True)
    for name in ('demo','run','convergence','fit','holdout'):
        p=sub.add_parser(name);p.add_argument('--output',required=True)
        if name=='run':p.add_argument('--configuration',required=True)
        if name in ('convergence','fit','holdout'):p.add_argument('--protocol',required=True)
        if name in ('convergence','fit'):p.add_argument('--profile',required=True)
        if name in ('fit','holdout'):p.add_argument('--references',required=True)
        if name=='fit':p.add_argument('--convergence',required=True)
        if name=='holdout':p.add_argument('--fit-result',required=True)
    args=parser.parse_args(argv);root=Path(args.output);root.mkdir(parents=True,exist_ok=False)
    start=time.monotonic();stamp=datetime.now(timezone.utc)
    from hashlib import sha256
    source_paths=[Path(p) for p in ('src/simulation/initial_conditions.py','src/simulation/contact_calibration.py',
        'src/simulation/calibration_cli.py','src/simulation/contact_evaluation.py','src/simulation/contact_recording.py',
        'src/simulation/engine/mujoco_engine.py','src/simulation/marker_export.py','src/simulation/mode_profiles.py',
        'src/utils/simulation_metadata.py','src/simulation/contact_comparison.py')]
    source_hashes={str(p):sha256(p.read_bytes()).hexdigest() for p in source_paths}
    report=envelope('RunReport',run_id='pub09-'+stamp.strftime('%Y%m%dT%H%M%SZ'),utc=stamp.isoformat(),kst=stamp.astimezone(timezone(timedelta(hours=9))).isoformat(),
        command=[sys.executable,'-m','src.simulation.calibration_cli',*(sys.argv[1:] if argv is None else argv)],tier=args.command,code=dict(commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
            dirty=subprocess.check_output(['git','status','--porcelain'],text=True).splitlines()),
        environment=dict(os=platform.platform(),python=platform.python_version(),dependencies={k:version(k) for k in ('mujoco','numpy','scipy','pandas','PySide6')}),
        approval=dict(numerical='proposed',range='proposed',label_uncertainty='proposed',physical='pending',baseline='none'),
        calibration_status='uncalibrated',completion='running',independent_review='pending',fresh=0,reused=0,
        native=dict(status='not_executed',reason='API/CLI only; no new GUI'),experimental=dict(status='unavailable',reason='No verified measured reference; #104'),
        peak_memory=dict(status='unavailable',reason='Not instrumented'),optimizer_calls='production path; not instrumented')
    report['source_sha256']=source_hashes
    report['schema_versions']=dict(seed=1,profile=1,protocol=1,reference=1,fit=1,holdout=1,recording=1,metadata=1)
    report['tolerance_version']='pub09-diagnostic-proposed-v1'
    report['input_files']={k:dict(path=v,sha256=sha256(Path(v).read_bytes()).hexdigest() if Path(v).is_file() else None)
        for k,v in vars(args).items() if k not in ('command','output')}
    expected=29 if args.command=='demo' else 1 if args.command=='run' else None
    try:
        if args.command=='demo':report['results']=demo(root)
        elif args.command=='run':
            from .mode_profiles import validate_config
            c=load(args.configuration,validate_config);p=c['contact_profile']
            case=dict(case_id=c['initial_condition']['seed_id'],motion_group=c['initial_condition']['source']['motion_id'],
                configuration=c,window_s=[0.,c['duration_s']],eligible_endpoints=list(ENDPOINT_UNITS))
            report['results']=production_roundtrip(root,case,p)
        else:
            protocol=load(args.protocol,validate_protocol);save(root/'protocol.json',protocol)
            expected=(protocol['search']['budget'] if args.command=='fit' else
                len(protocol['convergence_plan']['case_ids'])*len(protocol['convergence_plan']['timesteps_s'])*len(protocol['convergence_plan']['iterations'])
                if args.command=='convergence' else sum(c['split']=='holdout' for c in protocol['cases']))
            if args.command in ('fit','convergence'):profile=load(args.profile,validate_profile)
            if args.command in ('fit','holdout'):references=load(args.references,lambda v:v)
            if args.command=='convergence':
                reports={c['case_id']:convergence(c,profile,protocol['policy'],output=root/c['case_id']) for c in protocol['cases'] if c['split']=='fit'}
                save(root/'convergence-input.json',reports);report['results']={k:v['content_hash'] for k,v in reports.items()}
            elif args.command=='fit':report['results']=fit(protocol,profile,references,convergence_reports=load(args.convergence,lambda v:v),output=root)
            else:report['results']=evaluate_holdout(protocol,load(args.fit_result,lambda v:v),references,output=root)
        report.update(completion='needs_review',exit_code=0,reason='Software execution completed; diagnostic numbers proposed and measured calibration pending.')
    except BaseException as error:
        report.update(completion='fail',exit_code=1,reason=str(error),exception_type=type(error).__name__,traceback=traceback.format_exc())
    finally:
        report['source_sha256_at_completion']={str(p):sha256(p.read_bytes()).hexdigest() for p in source_paths}
        report['source_changed_during_execution']=report['source_sha256']!=report['source_sha256_at_completion']
        report['fresh']=len(list(root.rglob('contacts.json')))
        if args.command=='demo':report['fresh']+=len(list((root/'analytical-runs').rglob('result.json')))
        report['coverage']=dict(required=expected,loaded=report['fresh'],fresh=report['fresh'],reused=0,approved=0,
            failed=int(report['exit_code']!=0),unexecuted=max(0,expected-report['fresh']) if expected is not None else None,
            required_reason='frozen execution budget' if expected is not None else 'Protocol could not be validated; expected population unavailable',cache_origin='none',
            scope='actual-engine runs; production controls run separately within case; no reused results')
        report['duration_s']=time.monotonic()-start
        save(root/'RunReport.json',report)
    print(json.dumps(dict(output=str(root),completion=report['completion'],exit_code=report['exit_code'])))
    return report['exit_code']


if __name__=='__main__':raise SystemExit(main())
