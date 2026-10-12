"""Freeze required CI coverage and measure existing public validation entry points."""
from __future__ import annotations

import argparse
from datetime import datetime
from contextlib import redirect_stdout, redirect_stderr
import json
import os
from pathlib import Path
import runpy
import shlex
import subprocess
import sys
import time
import traceback

from src.analysis.regression.contracts import envelope, read_json, write_new_json, file_digest, digest
from src.analysis.regression.evidence import new_report, source_state, write_reports, validate_capture_report
from src.analysis.regression.runner import peak_memory_bytes
from .public_validation_summary import summarize_junit

INVENTORY = Path('tests/public_ci_inventory.json')
WORKFLOW = Path('.github/workflows/public-marker-validation.yml')
COMPONENTS = {
    'pub07': ('src.simulation.robot_validation', [], 4),
    'pub08': ('src.simulation.contact_validation', [], 13),
    'pub09': ('src.simulation.calibration_cli', ['demo'], 29),
    'pub10': ('src.simulation.observation_validation', [], 16),
    'gui': ('src.simulation.release_gui_validation', [], None),
}
REQUIRED_REPORTS = {**{k:f'tmp/issue144/{k}/run_report.json' for k in COMPONENTS},
                    **{k:f'tmp/issue144/{k}/run_report.json' for k in ('fast','capture','representative','full')}}


def pytest_commands():
    """Read the existing explicit workflow run blocks; no YAML dependency required."""
    lines = WORKFLOW.read_text(encoding='utf-8').splitlines()
    runs = []
    for i,line in enumerate(lines):
        if not line.startswith('        run:'):
            continue
        value = line.partition('run:')[2].strip()
        if value in ('|','>-'):
            block=[]
            for following in lines[i+1:]:
                if following.strip() and not following.startswith('          '): break
                block.append(following.strip())
            value=' '.join(block) if value=='>-' else '\n'.join(block)
        for command in value.splitlines():
            if command.startswith('python -m pytest '):
                args=shlex.split(command)[3:]
                junit=next(a.split('=',1)[1] for a in args if a.startswith('--junitxml='))
                runs.append(dict(junit=junit,args=[a for a in args if not a.startswith('--junitxml=')]))
    if not runs or len({r['junit'] for r in runs})!=len(runs):
        raise ValueError('Invalid required workflow JUnit inventory.')
    return runs


def prepare(output):
    output=Path(output);output.mkdir(parents=True,exist_ok=False)
    inventory=read_json(INVENTORY,'PublicCIInventory')
    step_ids=[line.strip().partition('id:')[2].strip() for line in WORKFLOW.read_text().splitlines()
              if line.startswith('        id: check_')]
    if step_ids!=inventory['required_step_ids']:
        raise ValueError('Required workflow step inventory changed.')
    commands=pytest_commands()
    if {r['junit'] for r in commands}!=set(inventory['jobs']):
        raise ValueError('Required workflow test jobs changed; independently review inventory.')
    report=new_report('ci', [sys.executable,*sys.argv])
    report.update(object_type='EvaluationProtocol',version='pub11-public-ci-v1',
                  inventory_sha256=file_digest(INVENTORY),workflow_sha256=file_digest(WORKFLOW),
                  junits=inventory['jobs'],required_reports=REQUIRED_REPORTS,
                  required_step_ids=inventory['required_step_ids'],
                  budgets=dict(required_job_minutes=120,policy='Existing merge gate retained; no numeric promotion'),
                  experimental=dict(status='pending',required=False,reason='No verified measured data/labels; #104'))
    # Save required population BEFORE collecting or running any test/job.
    write_new_json(output/'protocol.json',report)
    for index,job in enumerate(commands):
        path=output/f'collection-{index}.json'
        with (output/f'collection-{index}.log').open('x',encoding='utf-8') as log:
            result=subprocess.run([sys.executable,'-m','pytest',*job['args'],'--collect-only',
                '--pub11-inventory='+str(path)],stdout=log,stderr=subprocess.STDOUT)
        if result.returncode or read_json(path,'RequiredTests')['nodeids']!=inventory['jobs'][job['junit']]:
            raise ValueError('Required collection differs from frozen test inventory: '+job['junit'])
    print('Required CI protocol:',output/'protocol.json')


def component_protocol(component):
    if component=='pub07':
        return dict(cases=['two-release-G','supported-H','geometry-mass-B','held-only'],releases=[2,1,1,0],required_engines=4)
    if component=='pub08':
        from .contact_policy import frozen_protocol
        p=frozen_protocol()
        return dict(protocol=p,cases=[c['case_id'] for c in p['expectations']]+['actual-face','actual-corner','actual-rebound','actual-two-release-production'])
    if component=='pub09':
        from .calibration_cli import public_cases
        from .contact_calibration import freeze_protocol
        return dict(protocol=freeze_protocol(public_cases()),required_engines=29,
                    operation_counts=dict(references=4,convergence=12,fit=6,holdout=2,production=2,analytical=3),
                    observed_required=4,synthetic_holdout_required=4)
    if component=='pub10':
        from .observation_validation import frozen_protocol
        return dict(protocol=frozen_protocol(),physics=8,observations=16,production=18)
    return dict(adapter='release-gui-execution-v1',required='Actual retained-source Qt state/selection/reopen/export checks',
                native='Separate pending evidence; screenshots alone insufficient')


def component_scope(component, raw, root=None):
    """Explicit adapters for existing diagnostics. Proposed numerical acceptance is separate."""
    if component=='gui':
        if raw.get('version')!=1 or raw.get('status')!='pass' or raw.get('new_raw_executions')!=0:
            raise ValueError('GUI legacy replay adapter requires complete successful Qt evidence.')
        return dict(widget='pass',render_buffer='pass',native_window='pending',native_input='not_executed',
                    human_review='pending',reason='QTest/widget grabs and VTK pixels; external native input/3D review separate')
    required=COMPONENTS[component][2]
    if raw.get('exit_code')!=0 or raw.get('completion')!='needs_review':
        raise ValueError('Required existing validation failed/incomplete.')
    coverage=raw['coverage']
    actual=len(raw['cases']) if component in ('pub07','pub08','pub10') else raw['fresh']
    if type(actual) is not int or actual!=required:
        raise ValueError('Required case/engine denominator differs.')
    if component in ('pub07','pub08'):
        if coverage['reused']!=0 or coverage['failed']!=0 or any(c['status'] not in ('pass','diagnostic_pass') for c in raw['cases']):
            raise ValueError('Required case failed or reused.')
        ids=[c['case_id'] for c in raw['cases']]
        if len(ids)!=len(set(ids)):raise ValueError('Duplicate case identity.')
        if component=='pub07' and ids!=['two-release-G','supported-H','geometry-mass-B','held-only']:
            raise ValueError('Required PUB07 population differs.')
        if component=='pub07' and [c['actual']['releases'] for c in raw['cases']]!=[2,1,1,0]:
            raise ValueError('Required release count differs.')
        if component=='pub08' and ids!=component_protocol('pub08')['cases']:
            raise ValueError('Required PUB08 population differs.')
    elif component=='pub09':
        if (any(type(coverage[k]) is not int or coverage[k]!=expected for k,expected in
                (('required',29),('loaded',29),('fresh',29),('reused',0),('failed',0),('unexecuted',0)))
                or raw['source_changed_during_execution'] is not False):
            raise ValueError('Required PUB09 fresh execution incomplete.')
        if root is None:raise ValueError('PUB09 acceptance requires original frozen protocol/fit/holdout artifacts.')
        root=Path(root)
        from .contact_calibration import validate_protocol, validate_holdout_report, aggregate
        from .initial_conditions import load
        protocol=load(root/'protocol.json',validate_protocol)
        fit=load(root/'fit/fit-result.json',lambda v:v)
        held=load(root/'holdout/holdout-report.json',lambda v:v)
        refs=load(root/'holdout-references.json',lambda v:v)
        validate_holdout_report(held,protocol,fit,refs)
        results=raw['results']
        if results['protocol_sha256']!=protocol['content_hash'] or results['profile_sha256']!=fit['selected_profile_sha256']:
            raise ValueError('PUB09 original protocol/selected profile differs.')
        production=results['production']
        if [p['case_id'] for p in production]!=['corner-holdout','rebound-holdout']:
            raise ValueError('Required observed production population missing/duplicated.')
        records=[]
        for p in production:
            saved=read_json(root/'production'/p['case_id']/'production-report.json','SeedProductionReport')
            if digest(saved)!=digest(p) or p['execution_status']!='pass':
                raise ValueError('PUB09 production report changed/incomplete.')
            if [(e['case_id'],e['endpoint']) for e in p['observed_endpoints']]!=[(p['case_id'],k) for k in ('t1','t2')]:
                raise ValueError('Required observed endpoint population differs.')
            comparison=read_json(root/'production'/p['case_id']/'comparison.json','ContactComparison')
            from .contact_evaluation import load_recording, load_evaluation
            from .contact_comparison import compare_events, validate_detector
            from .contact_policy import policy_approval
            folder=root/'production'/p['case_id']
            recording=load_recording(folder/'engine/contacts.json')
            evaluation=load_evaluation(folder/'engine/evaluation.json',protocol['policy'],recording)
            detector=read_json(folder/'detector.json','DetectorEvents');validate_detector(detector)
            pairing=read_json(folder/'pairing.json','ContactObservationPair')
            if file_digest(folder/'observed/observed.csv')!=p['raw_sha256']:
                raise ValueError('Observed PUB09 source changed.')
            recomputed=compare_events(evaluation,detector,protocol['policy'],pairing=pairing,approval=policy_approval(protocol['policy']))
            if any(digest(recomputed[k])!=digest(comparison[k]) for k in recomputed):
                raise ValueError('PUB09 original observed comparison differs from current evaluator.')
            for e in p['observed_endpoints']:
                if e['status']!=comparison[e['endpoint']]['status'] or e['within_proposed_tolerance'] is not None:
                    raise ValueError('Observed endpoint status differs from original comparison.')
            records.extend(p['observed_endpoints'])
        observed=dict(aggregate(records,4,complete=True),modality='production-observed-Raw')
        synthetic=dict(held['summary'],modality='synthetic-self-consistency')
        if digest(observed)!=digest(results['observed_holdout_summary']) or digest(synthetic)!=digest(results['synthetic_holdout_summary']):
            raise ValueError('PUB09 declared required summary differs from reconstructed endpoints.')
        return dict(engines=coverage,production_observed=results['observed_holdout_summary'],
                    synthetic_holdout=results['synthetic_holdout_summary'],independent_experimental_n=0)
    else:
        from .observation_validation import CASE_RULES, aggregate, frozen_protocol
        if [c['case_id'] for c in raw['cases']] != [c[0] for c in CASE_RULES]:
            raise ValueError('Required PUB10 cases differ.')
        for key,expected in (('fresh_physics',8),('fresh_observations',16),('fresh_production',18),('reused_results',0)):
            if type(coverage[key]) is not int or coverage[key]!=expected:
                raise ValueError('Required operation count differs: '+key)
        endpoints=aggregate(frozen_protocol(),raw['cases'])
        if endpoints!=raw['endpoints'] or not endpoints['functional_pass']:
            raise ValueError('Required endpoint status/count differs.')
        return dict(operations=coverage,endpoints=endpoints,independent_experimental_n=0)
    return coverage


def run_component(component, output, trial_report=None):
    output=Path(output);output.mkdir(parents=True,exist_ok=False)
    report=new_report('gui' if component=='gui' else 'representative', [sys.executable,*sys.argv])
    report.update(component=component,pass_scope='Existing '+component+' frozen required software diagnostics; numerical approval separate',
                  coverage_scope='Declared component cases/engines/operations, not PUB02 approved corpus full regression',
                  numerical_acceptance=dict(status='needs_review',required=False,reason='Existing proposed diagnostic tolerances; no baseline promotion'),
                  required=COMPONENTS[component][2],optimizer_calls=0,processing_attempts=[],cache_origin='none')
    protocol=envelope('EvaluationProtocol',version='pub11-component-scope-v1',
        component=component,required=report['required'],numeric_required=False,
        specification=component_protocol(component),
        reason='GUI state scope' if component=='gui' else 'Frozen existing software cases/operations; diagnostics proposed')
    report['protocol']=protocol;report['protocol_sha256']=digest(protocol)
    write_new_json(output/'protocol.json',protocol)
    start=time.perf_counter()
    from src.analysis.pipeline.pose_optimizer import PoseOptimizer
    from src.analysis.pipeline.pipeline_controller import PipelineController
    optimize,process=PoseOptimizer.process,PipelineController.process_parsed_data
    def counted(self,*args,**kwargs):
        previous=kwargs.get('fit_observer')
        def observe(phase,frame,fit):
            if phase=='start': report['optimizer_calls']+=1
            if previous: previous(phase,frame,fit)
        kwargs['fit_observer']=observe
        return optimize(self,*args,**kwargs)
    def processed(self,config,parsed,*args,**kwargs):
        clock='Time' in parsed and len(parsed)>0
        entry=dict(input_rows=len(parsed),status='started',input_time_s=[float(parsed['Time'].iloc[0]),float(parsed['Time'].iloc[-1])] if clock else None,
                   input_time_status='valid' if clock else 'unavailable',input_time_reason='Actual parsed Raw times' if clock else 'No parsed Time column/rows')
        report['processing_attempts'].append(entry)
        try:
            result=process(self,config,parsed,*args,**kwargs)
            entry.update(status='completed',result_rows=len(result));return result
        except BaseException:
            entry.update(status='failed',traceback=traceback.format_exc());raise
    PoseOptimizer.process=counted;PipelineController.process_parsed_data=processed
    argv=sys.argv
    module,arguments,_=COMPONENTS[component]
    sys.argv=[module,*arguments,'--output',str(output/'raw')]
    if component=='gui':sys.argv += ['--trial-report',str(trial_report)]
    try:
        with (output/'execution.log').open('x',encoding='utf-8') as log,redirect_stdout(log),redirect_stderr(log):
            try: runpy.run_module(module,run_name='__main__')
            except SystemExit as error:
                if error.code not in (None,0):raise RuntimeError('Required CLI exit: '+str(error.code)) from error
        path=output/'raw'/('execution.json' if component=='gui' else 'RunReport.json')
        raw=json.loads(path.read_text(encoding='utf-8')) if component=='gui' else read_json(path,'RunReport')
        digest(raw)  # Also reject nested nonfinite legacy GUI evidence.
        scope=component_scope(component,raw,output/'raw')
        report.update(status='pass',exit_code=0,coverage=scope,original_report=dict(path=str(path),sha256=file_digest(path)),
                      original_verdict=raw.get('completion',raw.get('status')))
        if component=='gui':report['gui']=scope
    except BaseException as error:
        report.update(status='fail',reason=str(error),exception_type=type(error).__name__,traceback=traceback.format_exc())
    finally:
        sys.argv=argv;PoseOptimizer.process=optimize;PipelineController.process_parsed_data=process
        report['duration_s']=time.perf_counter()-start;report['peak_memory_bytes']=peak_memory_bytes()
        report['memory_scope']='Process peak working set including imports; existing runner and measurement wrapper share process'
        report['optimizer_scope']='Actual production PoseOptimizer fit-start callbacks; excludes marker-review hypotheses'
        report['source_sha256_at_completion']=source_state()['content_sha256']
        if report['source_sha256_at_completion']!=report['code']['content_sha256']:
            report.update(status='fail',exit_code=1,reason='Source changed during execution')
        write_reports(output,report)
    print(json.dumps(dict(component=component,status=report['status'],exit_code=report['exit_code'],coverage=report.get('coverage'))))
    return report['exit_code']


def verify(protocol_path, output, require_steps=False):
    protocol=read_json(protocol_path,'EvaluationProtocol')
    output=Path(output);output.mkdir(parents=True,exist_ok=False)
    report=new_report('ci',[sys.executable,*sys.argv]);report.update(cases=[],protocol_sha256=file_digest(protocol_path))
    inventory=read_json(INVENTORY,'PublicCIInventory')
    if (protocol['code']['content_sha256']!=report['code']['content_sha256'] or protocol['workflow_sha256']!=file_digest(WORKFLOW)
            or protocol['inventory_sha256']!=file_digest(INVENTORY) or protocol['junits']!=inventory['jobs']
            or protocol['required_step_ids']!=inventory['required_step_ids'] or protocol['required_reports']!=REQUIRED_REPORTS):
        report['reason']='Source/workflow changed after required protocol freeze'
    else:
        if require_steps:
            outcomes=json.loads(os.environ.get('PUB11_STEP_OUTCOMES','{}'))
            for key in protocol['required_step_ids']:
                actual=outcomes.get(key,{})
                report['cases'].append(dict(case_id=key,kind='step',status='pass' if actual.get('outcome')=='success' else 'fail',
                    scenes=[],actual=actual,reason='Required CI step outcome; missing/skipped/cancelled/failure nonpass'))
        report['step_outcome_scope']='Actual hosted outcomes' if require_steps else 'unavailable; local artifact-only verification'
        for path,nodes in protocol['junits'].items():
            summary=summarize_junit(path,public_required=path=='tmp/public-marker-results.xml',required_nodes=nodes)
            # Every required job rejects skips, even pure-widget/unit lanes.
            failed=summary['status']!='pass' or any(level['counts']['skipped'] for level in summary['levels'].values())
            report['cases'].append(dict(case_id=path,kind='test_run',status='fail' if failed else 'pass',scenes=[],summary=summary))
        for key,path in protocol['required_reports'].items():
            entry=dict(case_id=key,kind='report',status='fail',scenes=[]);report['cases'].append(entry)
            try:
                raw=read_json(path,'RunReport')
                if raw['code']['content_sha256']!=report['code']['content_sha256'] or raw['status']!='pass' or raw['exit_code']!=0:
                    raise ValueError('Required report failed/stale.')
                if raw['source_sha256_at_completion']!=raw['code']['content_sha256'] or raw['ci_context']!=protocol['ci_context']:
                    raise ValueError('Required report source/hosted attempt context differs.')
                if datetime.fromisoformat(raw['utc'])<datetime.fromisoformat(protocol['utc']):
                    raise ValueError('Required report predates the frozen CI attempt.')
                if raw['protocol_sha256']!=digest(raw['protocol']):
                    raise ValueError('Required nested protocol changed.')
                if key in COMPONENTS:
                    original=Path(path).parent/'raw'/('execution.json' if key=='gui' else 'RunReport.json')
                    if file_digest(original)!=raw['original_report']['sha256']:
                        raise ValueError('Original validation evidence changed.')
                    data=json.loads(original.read_text(encoding='utf-8')) if key=='gui' else read_json(original,'RunReport')
                    if component_scope(key,data,original.parent)!=raw['coverage']:
                        raise ValueError('Required component coverage no longer agrees with original evidence.')
                if key in ('fast','capture','representative','full') and raw['tier']!=key:
                    raise ValueError('Partial/representative result cannot satisfy different tier.')
                if key in ('fast','capture','representative','full'):
                    validate_capture_report(path,expected_tier=key,selection=['tracking_OFF-scene-0'] if key=='representative' else None)
                if key=='full' and (raw['coverage']['fresh']!=6 or raw['coverage']['reused']!=0 or raw['coverage']['completed']!=6):
                    raise ValueError('Full required production is incomplete or reused.')
                entry.update(status='pass',sha256=file_digest(path),coverage=raw['coverage'],duration_s=raw['duration_s'],
                             optimizer_calls=raw['optimizer_calls'],peak_memory_bytes=raw['peak_memory_bytes'])
            except Exception as error:entry.update(reason=str(error),traceback=traceback.format_exc())
        if report['cases'] and all(c['status']=='pass' for c in report['cases']):report.update(status='pass',exit_code=0)
    report['coverage']={}
    for kind,required in (('step',len(protocol['required_step_ids'])),('test_run',len(protocol['junits'])),('report',len(protocol['required_reports']))):
        entries=[c for c in report['cases'] if c['kind']==kind]
        report['coverage'][kind]=dict(required=required,reported=len(entries),passed=sum(c['status']=='pass' for c in entries),
            status='valid' if entries else 'unavailable',reason='Required evidence population' if entries else 'Not evaluated; see run status/scope')
    write_reports(output,report)
    print(json.dumps(dict(status=report['status'],coverage=report['coverage'])))
    return report['exit_code']


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__);sub=parser.add_subparsers(dest='action',required=True)
    p=sub.add_parser('prepare');p.add_argument('--output',required=True)
    p=sub.add_parser('run');p.add_argument('--component',choices=[*COMPONENTS,'experimental'],required=True);p.add_argument('--output',required=True);p.add_argument('--trial-report')
    p=sub.add_parser('verify');p.add_argument('--protocol',required=True);p.add_argument('--output',required=True);p.add_argument('--require-step-outcomes',action='store_true')
    args=parser.parse_args(argv)
    if args.action=='prepare':prepare(args.output);return 0
    if args.action=='run':
        if args.component=='experimental':
            root=Path(args.output);root.mkdir(parents=True,exist_ok=False)
            report=new_report('experimental',[sys.executable,*sys.argv])
            report.update(status='blocked',exit_code=1,reason='Required verified measured sources and independent labels unavailable; #104',
                          coverage=dict(status='unavailable',reason='No approved experimental evaluation manifest'),
                          duration_s=0.,peak_memory_bytes=peak_memory_bytes(),optimizer_calls=0)
            write_reports(root,report);print(json.dumps(dict(status='blocked',reason=report['reason'])));return 1
        return run_component(args.component,args.output,args.trial_report)
    return verify(args.protocol,args.output,args.require_step_outcomes)


if __name__=='__main__':raise SystemExit(main())
