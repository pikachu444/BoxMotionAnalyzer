"""PUB11 omissions, stale reuse and state/exit consistency at real boundaries."""
from copy import deepcopy
import json
from pathlib import Path
import shutil
import xml.etree.ElementTree as ET

import pytest

from src.analysis.regression.contracts import read_json, file_digest, digest, validate_envelope
from src.analysis.regression.evidence import cache_identity, environment, source_state
from src.analysis.regression.runner import run_corpus
from src.simulation.capture_corpus import build_corpus
from src.simulation.public_validation_summary import summarize_junit
from src.simulation.ci_evidence import component_scope, main as evidence_main


@pytest.fixture(scope='module')
def corpus(tmp_path_factory):
    root=tmp_path_factory.mktemp('pub11')/'assets';build_corpus(root);return root


@pytest.fixture(scope='module')
def actual(corpus,tmp_path_factory):
    root=tmp_path_factory.mktemp('pub11-production')
    report=run_corpus(corpus/'corpus.json',corpus,root/'representative',tier='representative',select=['partial-scene-0'])
    assert report['status']=='pass',report.get('errors')
    return root,report


def copied(corpus,tmp_path):
    root=tmp_path/'assets';shutil.copytree(corpus,root);return root


def modify(path,function):
    value=json.loads(path.read_text(encoding='utf-8'));function(value);path.write_text(json.dumps(value,allow_nan=False))


@pytest.mark.parametrize('tier',['fast','capture'])
def test_required_zero_scene_capture_cannot_disappear(corpus,tmp_path,tier):
    root=copied(corpus,tmp_path)
    modify(root/'corpus.json',lambda v:v.update(cases=[c for c in v['cases'] if c['case_id']!='handling_only']))
    report=run_corpus(root/'corpus.json',root,tmp_path/'run',tier=tier)
    assert report['status']=='fail' and report['exit_code']==1
    assert 'Required capture case population' in str(report['errors'])
    assert ET.parse(tmp_path/'run/junit.xml').findall('.//failure')
    assert 'verdict: fail / exit: 1' in (tmp_path/'run/summary.md').read_text(encoding='utf-8')


@pytest.mark.parametrize('fault',['reference','raw','approval','tolerance','case','endpoint','schema','units','frame','numeric_bool','numeric_text','nested','boundary'])
def test_required_preflight_errors_are_nonzero(corpus,tmp_path,fault):
    root=copied(corpus,tmp_path);path=root/'partial/review.json'
    if fault=='reference':(root/'partial/reference.json').unlink()
    elif fault=='raw':(root/'partial/observed.csv').unlink()
    elif fault=='approval':modify(path,lambda v:v['approval'].update(status='proposed'))
    elif fault=='tolerance':modify(path,lambda v:v.pop('tolerance'))
    elif fault=='case':modify(root/'corpus.json',lambda v:v['cases'].append(v['cases'][0]))
    elif fault=='endpoint':
        ref=root/'partial/reference.json';modify(ref,lambda v:v['scenes']['partial-scene-0']['metrics'].pop('t1'))
        modify(path,lambda v:v['reference'].update(sha256=file_digest(ref)))
    elif fault=='schema':modify(path,lambda v:v.update(schema_version=True))
    elif fault=='units':modify(path,lambda v:v['geometry'].update(position_units='m'))
    elif fault=='frame':modify(path,lambda v:v['geometry'].update(vertical_axis='Z'))
    elif fault=='numeric_bool':modify(path,lambda v:v['geometry']['box_dims_mm'].__setitem__(0,True))
    elif fault=='numeric_text':modify(path,lambda v:v['geometry']['box_dims_mm'].__setitem__(0,'200'))
    elif fault=='nested':modify(path,lambda v:v['effective_processing_config']['analysis_options'].update(truth={'answer':1}))
    elif fault=='boundary':modify(path,lambda v:v['scene_decisions'][-1]['anchor'].update(end_record_exclusive=61))
    report=run_corpus(root/'corpus.json',root,tmp_path/'run',select=['partial-scene-0'])
    assert report['status']!='pass' and report['exit_code']!=0
    assert (tmp_path/'run/run_report.json').is_file()


@pytest.mark.parametrize('fault',['profile_hash','included_end_bool','excluded_start_bool','capture_end_text','metric_bool','numeric_without_tolerance','numeric_string_without_tolerance','reference_time','seed_bool'])
def test_fast_rejects_independent_review_trust_boundary_failures(corpus,tmp_path,fault):
    root=copied(corpus,tmp_path);path=root/'partial/review.json'
    if fault=='profile_hash':modify(path,lambda v:v.update(marker_profile_hash='wrong'))
    elif fault=='included_end_bool':modify(path,lambda v:v['scene_decisions'][-1]['anchor']['end_raw_time_s'].update(value=True))
    elif fault=='excluded_start_bool':modify(root/'handling_only/review.json',lambda v:v['scene_decisions'][0]['anchor'].update(start_record=True))
    elif fault=='capture_end_text':modify(path,lambda v:v.update(capture_end_raw_time_s='bad clock'))
    else:
        ref=root/'partial/reference.json'
        def bad(v):
            if fault=='seed_bool':v['seed']=True;return
            if fault=='reference_time':v['scenes']['partial-scene-0']['trajectory']['raw_time_s'][5]+=.0001;return
            m=v['scenes']['partial-scene-0']['metrics']['MaxAbsThetaShortDeg'];m.pop('tolerance')
            if fault=='metric_bool':m['value']=False
            elif fault=='numeric_string_without_tolerance':m['value']='0.0'
        modify(ref,bad);modify(path,lambda v:v['reference'].update(sha256=file_digest(ref)))
    report=run_corpus(root/'corpus.json',root,tmp_path/'run',tier='fast')
    assert report['status']!='pass' and report['exit_code']==1


def test_fast_counts_actual_preflight_loading_without_claiming_processing(corpus,tmp_path):
    report=run_corpus(corpus/'corpus.json',corpus,tmp_path/'fast',tier='fast')
    assert report['status']=='pass' and report['coverage']['loaded']==6
    assert report['coverage']['fresh']==report['optimizer_calls']==report['coverage']['started']==0
    assert len(report['preflight_loaded_files'])==6 and sum(v['rows'] for v in report['preflight_loaded_files'])==552
    attempt=read_json(tmp_path/'fast/attempt-start.json','RunReport')
    assert attempt['coverage']['loaded']==6 and attempt['coverage']['fresh']==0


def test_partial_preflight_failure_keeps_actual_loaded_scope(corpus,tmp_path):
    root=copied(corpus,tmp_path);(root/'partial/observed.csv').unlink()
    report=run_corpus(root/'corpus.json',root,tmp_path/'fast',tier='fast')
    assert report['exit_code']==1 and report['coverage']['loaded']==4
    assert [v['case_id'] for v in report['preflight_loaded_files']]==['two_drops','supported_H','handling_only','tracking_OFF']
    assert report['coverage']['fresh']==0 and report['coverage']['unexecuted']==6


def test_pub09_claimed_summary_needs_original_artifacts():
    raw=dict(exit_code=0,completion='needs_review',fresh=29,source_changed_during_execution=False,
             coverage=dict(required=29,loaded=29,fresh=29,reused=0,failed=0,unexecuted=0),
             results=dict(production=[],observed_holdout_summary={'required':4},synthetic_holdout_summary={'required':4}))
    with pytest.raises(ValueError,match='original frozen'):component_scope('pub09',raw)
    raw['coverage']['required']=True
    with pytest.raises(ValueError,match='incomplete'):component_scope('pub09',raw)


def test_representative_resume_reopens_and_does_not_claim_fresh(corpus,actual,tmp_path):
    root,old=actual
    report=run_corpus(corpus/'corpus.json',corpus,tmp_path/'resume',tier='representative',select=['partial-scene-0'],resume=root/'representative/run_report.json')
    assert report['status']=='pass',report
    assert report['coverage']['fresh']==0 and report['coverage']['reused']==1
    assert report['coverage']['completed']==1 and report['coverage']['unexecuted']==5
    assert report['optimizer_calls']==0 and report['tier']=='representative'
    repeated=run_corpus(corpus/'corpus.json',corpus,tmp_path/'again',select=['partial-scene-0'],resume=tmp_path/'resume/run_report.json')
    assert repeated['status']=='pass' and repeated['coverage']['reused']==1
    full=run_corpus(corpus/'corpus.json',corpus,tmp_path/'full',resume=root/'representative/run_report.json')
    assert full['status']=='fail' and full['exit_code']==1 and full['coverage']['fresh']==0


@pytest.mark.parametrize('fault',['proc','slice','scenario','signature','failed','approval','settings','tolerance','code','environment'])
def test_cache_corruption_or_stale_identity_is_never_success(corpus,actual,tmp_path,fault,monkeypatch):
    root=copied(corpus,tmp_path);oldroot=tmp_path/'previous';shutil.copytree(actual[0]/'representative',oldroot)
    path=oldroot/'run_report.json'
    if fault in ('proc','slice','scenario','signature'):
        name={'proc':'partial-scene-0.proc','slice':'partial-scene-0.slice','scenario':'partial-scene-0.scenario.csv','signature':'partial-scene-0.signature.json'}[fault]
        with (oldroot/'partial'/name).open('a') as stream:stream.write('corrupt')
    elif fault=='failed':
        modify(path,lambda v:next(s for c in v['cases'] for s in c['scenes'] if s['review_id']=='partial-scene-0').update(status='fail'))
        def fail(*args,**kwargs):raise RuntimeError('Failed artifact must retry fresh, not resurrect success')
        monkeypatch.setattr('src.analysis.regression.runner.process_scene',fail)
    elif fault=='approval':modify(root/'partial/review.json',lambda v:v['approval'].update(date='2026-10-13'))
    elif fault=='settings':modify(root/'partial/review.json',lambda v:v['effective_processing_config']['analysis_options'].update(marker_butterworth_cutoff_hz=11.))
    elif fault=='tolerance':modify(root/'partial/review.json',lambda v:v['tolerance']['bounds']['center_mm'].update(absolute=.2))
    elif fault=='code':modify(path,lambda v:v['code'].update(content_sha256='changed'))
    else:
        modify(path,lambda v:next(c for c in v['cases'] if c['case_id']=='partial')['cache_identity'].update(environment='changed'))
    report=run_corpus(root/'corpus.json',root,tmp_path/'run',select=['partial-scene-0'],resume=path)
    assert report['status']!='pass' and report['exit_code']!=0
    assert report['coverage']['reused']==0


def test_identity_path_move_and_relevant_changes(corpus):
    fixture=read_json(corpus/'partial/review.json','CaptureReviewFixture');manifest=read_json(corpus/'corpus.json','CaptureCorpus')
    code=source_state();env=environment();original=cache_identity(fixture,manifest,code,env)
    moved=deepcopy(fixture);moved['relative_path']='moved/source.csv';moved['reference']['relative_path']='new/baseline.json'
    assert cache_identity(moved,manifest,code,env)==original
    for key in ('raw_sha256','marker_profile_hash'):
        changed=deepcopy(fixture);changed[key]='changed'
        assert cache_identity(changed,manifest,code,env)!=original
    for key in ('code','environment','baseline','tolerance','approval'):
        assert key in original


def test_cancellation_preserves_attempt_and_required_unexecuted(corpus,tmp_path):
    report=run_corpus(corpus/'corpus.json',corpus,tmp_path/'run',select=['partial-scene-0'],cancel=lambda:True)
    assert report['exit_code']==1 and report['coverage']['unexecuted']==6
    assert report['coverage']['fresh']==0
    assert any('Cancelled' in s.get('reason','') for c in report['cases'] for s in c['scenes'])


@pytest.mark.parametrize('error',[KeyboardInterrupt,InterruptedError])
def test_one_shot_worker_interruption_stops_later_production(corpus,tmp_path,monkeypatch,error):
    calls=[]
    def interrupted(self,*args,**kwargs):
        calls.append(True)
        raise error('One-shot worker stop; later required processing must not start')
    monkeypatch.setattr('src.analysis.regression.runner.PipelineController.process_parsed_data',interrupted)
    report=run_corpus(corpus/'corpus.json',corpus,tmp_path/'run')
    assert len(calls)==1 and report['exit_code']==1
    assert report['coverage']['started']==report['coverage']['failed']==1
    assert report['coverage']['loaded']==6 and report['coverage']['unexecuted']==5
    assert report['coverage']['fresh']==report['coverage']['completed']==report['optimizer_calls']==0
    first=report['cases'][0]['scenes'][0]
    assert first['exception_type']==error.__name__ and first['traceback']
    assert (tmp_path/'run/attempt-start.json').is_file() and (tmp_path/'run/junit.xml').is_file()


def test_one_shot_cancel_keeps_successful_checkpoint_and_explicit_resume(corpus,tmp_path):
    selected=['two_drops-scene-0','two_drops-scene-1'];calls=[]
    def cancelled():
        calls.append(True);return len(calls)==2
    first=run_corpus(corpus/'corpus.json',corpus,tmp_path/'interrupted',select=selected,cancel=cancelled)
    assert len(calls)==2 and first['exit_code']==1
    assert first['coverage']['fresh']==first['coverage']['completed']==1
    assert first['coverage']['unexecuted']==5 and first['coverage']['required']==2
    checkpoint=next((tmp_path/'interrupted').glob('checkpoint-*.json'))
    assert any(s['completed'] for c in read_json(checkpoint,'RunReport')['cases'] for s in c['scenes'])
    prior=tmp_path/'interrupted/run_report.json';before=file_digest(prior)
    resumed=run_corpus(corpus/'corpus.json',corpus,tmp_path/'resumed',select=selected,resume=prior)
    assert resumed['status']=='pass' and resumed['coverage']['fresh']==resumed['coverage']['reused']==1
    assert resumed['coverage']['completed']==2 and resumed['coverage']['unexecuted']==4
    assert file_digest(prior)==before and resumed['resume']['run_id']==first['run_id']


def test_fresh_and_failed_overlap_after_real_processing_save_error(corpus,tmp_path,monkeypatch):
    def broken(*args,**kwargs):raise OSError('Injected save failure after actual production processing')
    monkeypatch.setattr('src.analysis.regression.runner.save_proc_file',broken)
    report=run_corpus(corpus/'corpus.json',corpus,tmp_path/'run',select=['partial-scene-0'])
    assert report['status']=='fail' and report['exit_code']==1
    assert report['coverage']['fresh']==report['coverage']['failed']==report['coverage']['started']==1
    assert report['coverage']['completed']==0 and report['coverage']['unexecuted']==5
    assert report['optimizer_calls']==60
    assert list((tmp_path/'run').glob('checkpoint-*.json'))


@pytest.mark.parametrize('fault',['missing','skipped','duplicate','unclassified'])
def test_junit_required_inventory_rejects_omission_or_skip(tmp_path,fault):
    suite=ET.Element('testsuite')
    for node,level in [('tests/test_a.py::unit','unit_contract'),('tests/test_capture_regression.py::test_fresh_full_capture_pipeline_preserves_every_approved_scene','synthetic_integration')]:
        c=ET.SubElement(suite,'testcase',classname=node.split('::')[0],name=node.split('::')[1]);p=ET.SubElement(c,'properties')
        ET.SubElement(p,'property',name='nodeid',value=node);ET.SubElement(p,'property',name='evidence_level',value=level)
    required=[c.find('./properties/property').get('value') for c in suite]
    if fault=='missing':required.append('tests/test_capture_regression.py::required_negative')
    elif fault=='skipped':ET.SubElement(suite[0],'skipped')
    elif fault=='duplicate':suite.append(deepcopy(suite[0]))
    else:suite[0].find('./properties/property[@name="evidence_level"]').set('value','unknown')
    path=tmp_path/'junit.xml';ET.ElementTree(suite).write(path)
    assert summarize_junit(path,public_required=True,required_nodes=required)['status']=='fail'


def test_required_experimental_data_is_blocked(tmp_path):
    assert evidence_main(['run','--component','experimental','--output',str(tmp_path/'run')])==1
    report=read_json(tmp_path/'run/run_report.json','RunReport')
    assert report['status']=='blocked' and report['coverage']['status']=='unavailable'


def test_screenshot_existence_is_not_native_verification():
    scope=component_scope('gui',dict(version=1,status='pass',new_raw_executions=0,screenshots=['exists.png']))
    assert scope['widget']=='pass' and scope['native_window']=='pending' and scope['native_input']=='not_executed'


@pytest.mark.parametrize('value',[True,'1',2,float('nan'),float('inf')])
def test_schema_numbers_do_not_use_python_bool_or_string_equality(value):
    with pytest.raises(ValueError):validate_envelope(dict(schema_version=value,plan_spec='ISTA6A-PLAN-20261001-v1',object_type='RunReport'),'RunReport')
