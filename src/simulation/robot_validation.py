"""Fresh public PUB07 diagnostics; proposed fixtures are not trial acceptance."""
import argparse
from copy import deepcopy
from datetime import datetime, timezone, timedelta
from importlib.metadata import version
import hashlib
import json
from pathlib import Path
import platform
import subprocess
import sys
import time
import traceback
import numpy as np
from .mode_profiles import default_config
from .robot_profiles import with_example
from .robot_evaluation import evaluate_sequence
from .engine.robot_sequence import RobotSequenceEngine
from .history_trajectory import history_to_trajectory
from .data_exporter import DataExporter
from .corruption_export import write_observations
from .marker_export import fault_spec
from src.utils.simulation_metadata import build_metadata
from src.utils.marker_profile_identity import envelope, digest


def fixture(*, family='airborne', size=(200.,120.,80.), mass=1., com=(0.,0.,0.), two=True):
    c=default_config('robot_sequence');c.update(size_mm=list(size),duration_s=30.,show_viewer=False)
    c['physics_profile'].update(mass_kg=mass,friction=.5,contact_damping_control=.15,com_offset_mm=list(com))
    first=c['sequence_profile']['steps'][0];first.update(clearance_mm=100.,fixed_xyz_deg=[0.,0.,0.])
    if family=='floor_supported':
        from .scenarios import Scenarios
        first.update(category=Scenarios.CATEGORIES[1],preset_id=Scenarios.get_drop_sequence_specs(Scenarios.CATEGORIES[1])[0].id)
    if two:
        second=deepcopy(first);second.update(step_id='drop-2',fixed_xyz_deg=[0.,0.,30.]);c['sequence_profile']['steps'].append(second)
    return with_example(c,family=family)


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',required=True)
    root=Path(parser.parse_args().output);root.mkdir(parents=True,exist_ok=False)
    start=time.monotonic();stamp=datetime.now(timezone.utc)
    paths=['src/simulation/robot_profiles.py','src/simulation/robot_evaluation.py','src/simulation/robot_validation.py',
        'src/simulation/engine/robot_sequence.py','src/simulation/robot_partial.py','src/simulation/mode_profiles.py','src/utils/simulation_metadata.py',
        'src/simulation/marker_export.py','tests/test_robot_sequence.py']
    report=envelope('RunReport',run_id='pub07-'+stamp.strftime('%Y%m%dT%H%M%SZ'),utc=stamp.isoformat(),
        kst=stamp.astimezone(timezone(timedelta(hours=9))).isoformat(),command=[sys.executable,*sys.argv],
        tier='fresh-public-dynamic-diagnostics',semantic_version='pub07-dynamic-gripper-v1',
        code=dict(commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
            dirty=subprocess.check_output(['git','status','--porcelain','--untracked-files=no'],text=True).splitlines(),
            source_sha256={p:hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in paths}),
        environment=dict(os=platform.platform(),python=platform.python_version(),dependencies={n:version(n) for n in ('mujoco','numpy','scipy','pandas','PySide6')}),
        schema_versions=dict(plan=1,evidence=1,metadata=1,artifact=1),tolerance_version='pub07-proposed-virtual-v1',
        approval=dict(ui='pending',fixture='proposed',tolerance='proposed',baseline='no promotion',trial='not_evaluated'),
        independent_review=dict(status='pending backend audit'),cases=[],
        cache_origin='none',optimizer_calls=0,peak_memory=dict(status='not_measured',reason='No process memory sampler in this bounded diagnostic tier'),
        native=dict(status='not_executed',reason='Separate native input/viewer/OS125 tier'),
        experimental=dict(status='unavailable',reason='No verified real dataset; #104 separate'),
        completion='running')
    try:
        cases=[('two-release-G',fixture()),('supported-H',fixture(family='floor_supported',two=False)),
            ('geometry-mass-B',fixture(size=(300.,180.,90.),mass=2.,two=False)),('held-only',fixture(family='held_only',two=False))]
        for name,c in cases:
            before=time.monotonic();engine=RobotSequenceEngine(c);history=engine.run_simulation()
            result=evaluate_sequence(engine.sequence_evidence,engine.plan,history=history,configuration_hash=digest(c))
            expected=2 if name=='two-release-G' else 0 if name=='held-only' else 1
            if result['releases']!=expected or result['status']=='failed':raise AssertionError((name,result))
            (root/(name+'-config.json')).write_text(json.dumps(c,indent=2)+'\n',encoding='utf-8')
            (root/(name+'-truth.json')).write_text(json.dumps(engine.sequence_evidence,indent=2)+'\n',encoding='utf-8')
            p=c['physics_profile'];o=c['observation_profile']['corner']
            params=dict(duration=c['duration_s'],add_noise=o['enabled'],noise_std=o['std_mm'],noise_seed=o['seed'],mode_config=c,run_id='public-pub07-'+name)
            path=root/(name+'.proc');DataExporter.from_engine(history,engine,params).export_proc_csv(path)
            if name=='two-release-G':
                marker=c['observation_profile']['marker'];metadata=build_metadata(c,engine,history,route='marker_csv',run_id='public-pub07-'+name)
                trajectory=history_to_trajectory(history)
                write_observations(root/'observed-capture',trajectory,marker['profile'],fault_spec(trajectory['time_s'],marker['faults']),marker['seed'],simulation_metadata=metadata)
            report['cases'].append(dict(case_id=name,source_kind='public_synthetic_fixture',seed=74082,
                configuration_hash=digest(c),geometry_hash=digest(dict(size=c['size_mm'],physics=p)),profile_hash=digest(engine.plan),
                raw_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),expected=dict(releases=expected,engine_builds=1),
                actual=dict(releases=result['releases'],engine_builds=result['engine_builds'],engine_time_s=history[-1]['time'],recorded_samples=len(history)),
                difference=dict(releases=result['releases']-expected,engine_builds=result['engine_builds']-1),
                tolerance=dict(count=0,units='integer',approval='exact software invariant'),status='diagnostic_pass',
                physical_acceptance='not_evaluated',fresh=True,reused=False,duration_s=time.monotonic()-before))
        report['coverage']=dict(loaded=4,approved=0,fresh=4,reused=0,failed=0,unexecuted=['native','experimental'],
            physical_families=2,original_experimental_n=0,reason='Repeated same-model samples do not expand geometry/family coverage')
        report['completion']='needs_review';report['reason']='Diagnostics passed; proposed numeric fixtures/tolerances and UI await human approval and final independent review.'
        report['exit_code']=0
    except BaseException as error:
        report.update(completion='fail',exception_type=type(error).__name__,traceback=traceback.format_exc(),exit_code=1);raise
    finally:
        report['duration_s']=time.monotonic()-start
        (root/'RunReport.json').write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    print(json.dumps(dict(status=report['completion'],cases=len(report['cases']),duration_s=report['duration_s'])))


if __name__=='__main__':main()
