"""PUB06 independent software evidence; no trial/baseline/native approval."""
import argparse
from copy import deepcopy
from datetime import datetime, timezone, timedelta
from importlib.metadata import version
import json
import hashlib
from pathlib import Path
import platform
import subprocess
import sys
import time
import traceback

import numpy as np

from src.simulation.mode_profiles import default_config,ModeProfiles,save_profiles,read_profiles,require_executable
from src.simulation.engine import MuJoCoEngine
from src.simulation.data_exporter import DataExporter
from src.simulation.marker_export import generate_marker_capture
from src.simulation.history_trajectory import history_to_trajectory
from src.analysis.pipeline.data_loader import DataLoader
from src.utils.simulation_metadata import artifact_simulation
from src.utils.artifact_metadata import read_identity
from src.utils.marker_profile_identity import envelope,digest


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',required=True)
    args=parser.parse_args();root=Path(args.output);root.mkdir(parents=True,exist_ok=False)
    start=time.monotonic();stamp=datetime.now(timezone.utc)
    report=envelope('RunReport',run_id='pub06-'+stamp.strftime('%Y%m%dT%H%M%SZ'),
        utc=stamp.isoformat(),kst=stamp.astimezone(timezone(timedelta(hours=9))).isoformat(),
        command=sys.argv,tier='independent-transform-and-storage-fixture',fresh=True,reused=False,
        code=dict(commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
            dirty=bool(subprocess.check_output(['git','status','--porcelain'],text=True).strip()),
            changed_paths=subprocess.check_output(['git','diff','--name-only'],text=True).splitlines(),
            new_contract_paths=['src/simulation/mode_profiles.py','src/utils/simulation_metadata.py','src/simulation/mode_validation.py']),
        environment=dict(os=platform.platform(),python=platform.python_version(),
            dependencies={name:version(name) for name in ('numpy','pandas','scipy','mujoco','PySide6')}),
        schema_versions=dict(mode_profiles=1,simulation_metadata=1,artifact=1),
        approval=dict(mockup='Human approved shared G17/H12 workspace on 2026-10-06',trial='not_evaluated',baseline='no promotion',tolerance='no physical tolerance approval'),
        native=dict(status='not_executed',reason='Windows activation failed; no native input or actual OS125 evidence'),
        experimental_validation=dict(status='not_executed',reason='#104 separate; no verified experimental dataset'),
        registration=dict(status='not_applicable',reason='#113 excluded by user; existing source lineage retained'),
        signatures=dict(status='not_applicable',reason='Bounded PUB06 contract fixtures, not capture optimization regression'),
        optimizer=dict(starts=0,reason='No optimizer invoked in this tier'),
        oracle='Literal 90-degree Z rotation, COM [3,-4,2] mm, qvel [.1,.2,.3,1,2,3]; no copied production baseline',
        input=dict(source_kind='public_synthetic_fixture',seed=37,configuration_hash=None),checks=[],
        independent_review=dict(status='pending production'),completion='running')
    source_paths=set(report['code']['changed_paths']+report['code']['new_contract_paths']+
        ['tests/test_simulation_mode_profiles.py','tests/test_simulation_metadata.py'])
    report['code']['source_sha256']={path:hashlib.sha256(Path(path).read_bytes()).hexdigest()
        for path in sorted(source_paths) if Path(path).is_file() and Path(path).suffix in ('.py','.yml')}
    def check(name,actual,expected,tolerance=0,units='contract-value'):
        a=np.asarray(actual);b=np.asarray(expected)
        difference=float(np.max(np.abs(a.astype(float)-b.astype(float))))
        passed=a.shape==b.shape and difference<=tolerance
        report['checks'].append(dict(name=name,actual=a.tolist(),expected=b.tolist(),
            maximum_difference=difference,tolerance=tolerance,units=units,passed=bool(passed),fresh=True))
        if not passed:raise AssertionError(name)
    try:
        value=default_config();value['size_mm']=[200.,120.,80.];value['duration_s']=.5;value['show_viewer']=False
        value['physics_profile'].update(mass_kg=1.,friction=.4,contact_damping_control=.1,com_offset_mm=[3.,-4.,2.])
        value['sequence_profile']['steps'][0].update(clearance_mm=250.,fixed_xyz_deg=[0.,0.,90.])
        report['input']['configuration_hash']=digest(value)
        engine=MuJoCoEngine(size=[200,120,80],mass=1.,friction=.4,elasticity=.1,com_offset=[3,-4,2])
        engine.set_initial_state(250,[2**-.5,0,0,2**-.5]);engine.build();engine.data.qvel[:]=[.1,.2,.3,1,2,3]
        history=engine.record_samples(3,4);initial=history[0]
        check('release-origin',initial['BodyOrigin'],[0,0,290],1e-12,'mm')
        check('release-COM',initial['COM'],[4,3,292],1e-12,'mm')
        check('release-world-linear-velocity',initial['OriginLinearVelocityWorld'],[100,200,300],1e-12,'mm/s')
        check('release-body-angular-velocity',initial['AngularVelocityBody'],[1,2,3],1e-14,'rad/s')
        check('release-world-angular-velocity',initial['AngularVelocityWorld'],[-2,1,3],1e-14,'rad/s')
        trajectory=history_to_trajectory(history)
        check('actual-engine-time',trajectory['time_s'],[0,.008,.016],1e-15,'s')
        check('output-world-origin',trajectory['body_origin_mm'][0],[0,290,0],1e-12,'mm')
        check('output-world-COM',trajectory['com_mm'][0],[4,292,-3],1e-12,'mm')
        params=dict(height=250.,quat=[2**-.5,0,0,2**-.5],duration=.5,add_noise=False,noise_std=1.,noise_seed=0,
            mass=1.,friction=.4,elasticity=.1,com_offset=[3,-4,2],mode_config=value,run_id='public-pub06-release-v1')
        direct=root/'release.proc';DataExporter.from_engine(history,engine,params).export_proc_csv(direct)
        identity=read_identity(DataLoader().load_result_csv(str(direct)))
        public=artifact_simulation(identity.values)
        check('direct-metadata-clock-count',public['clock']['samples'],3)
        check('direct-mode-preserved',public['mode']=='single_drop',True)
        state=ModeProfiles();state.set_config(value);state.switch('robot_sequence');state.switch('single_drop')
        path=root/'settings.json';save_profiles(path,state)
        check('mode-roundtrip-preserved',read_profiles(path).document()==state.document(),True)
        try:require_executable(state.configs['robot_sequence'])
        except ValueError as error:
            check('robot-execution-blocked','attach, pickup and release' in str(error),True)
        else:raise AssertionError('Robot execution was not blocked.')
        marker=value['observation_profile']['marker'];marker['seed']=37
        marker['faults'].update(kind='missing',start=.08,end=.16);marker['use_layout_box']=True
        params['mode_config']=deepcopy(value)
        observed=generate_marker_capture(root/'capture',marker['profile'],params,marker['faults'],37)
        # Demonstrate that the consumer has no truth/manifests to consult.
        for filename in ('truth_pose.csv','truth_markers.csv','observed.synthetic.json'):
            (Path(observed).parent/filename).unlink()
        header,raw=DataLoader().load_csv(observed);declaration=artifact_simulation(header['artifact_metadata'])
        check('marker-recorded-count',declaration['clock']['samples'],63)
        check('marker-source-profile',declaration['configuration']['observation_profile']['marker']['profile_hash']==marker['identity']['profile_hash'],True)
        check('truth-isolation',all(term not in Path(observed).read_text(encoding='utf-8') for term in ('"faults"','"events"','origin_linear_velocity_world')),True)
        report['completion']='passed'
    except BaseException as error:
        report['completion']='failed';report['failure']=dict(boundary=report['checks'][-1]['name'] if report['checks'] else 'setup',
            message=str(error),traceback=traceback.format_exc())
        raise
    finally:
        report['duration_s']=time.monotonic()-start
        try:
            import psutil
            report['performance']=dict(process_peak_working_set_bytes=psutil.Process().memory_info().peak_wset,
                status='observed single bounded process; not optimization or native latency certification')
        except (ImportError,AttributeError):
            report['performance']=dict(status='unavailable',reason='Windows process peak working set unavailable')
        (root/'RunReport.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    print(root/'RunReport.json')


if __name__=='__main__':main()
