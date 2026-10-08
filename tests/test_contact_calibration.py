"""Frozen protocol, leakage, missing-denominator and ambiguity controls."""
from copy import deepcopy

import pytest

from src.simulation.calibration_cli import public_cases
from src.simulation.initial_conditions import contact_profile, reseal, initial_condition
from src.simulation.contact_calibration import (freeze_protocol,validate_protocol,run_case,reference_from_result,
    validate_reference,fit,evaluate_holdout,convergence,candidate_profile,aggregate,extract_endpoints)
from src.simulation.contact_policy import event_policy
from src.simulation.contact_evaluation import metric


@pytest.fixture(scope='module')
def fixture():
    # All contact parameters are inactive before the first contact. This is an
    # independent exact counterexample to unique identification from free flight.
    cases=[deepcopy(public_cases()[0]),deepcopy(public_cases()[3])]
    for c in cases:
        c['window_s']=[0.,.04]
        c['eligible_endpoints']=c['required_endpoints']=['final_origin_x_mm']
        c['endpoint_rules']={'final_origin_x_mm':deepcopy(public_cases()[0]['endpoint_rules']['final_origin_x_mm'])}
    base=contact_profile(solref=(.02,.4));known=contact_profile(solref=(.02,.2))
    refs={}
    for c in cases:
        result,*_=run_case(c,known,event_policy());ref=reference_from_result(c,result,'ref-'+c['case_id'])
        c['reference_identity']=dict(reference_id=ref['reference_id'],content_hash=ref['content_hash']);refs[c['case_id']]=ref
    protocol=freeze_protocol(cases)
    reports={cases[0]['case_id']:convergence(cases[0],base,event_policy())}
    fit_refs={cases[0]['case_id']:refs[cases[0]['case_id']]};holdout={cases[1]['case_id']:refs[cases[1]['case_id']]}
    fitted=fit(protocol,base,fit_refs,convergence_reports=reports)
    return protocol,base,fit_refs,holdout,reports,fitted


def test_real_bounded_fit_is_ambiguous_and_holdout_remains_pending(fixture):
    protocol,base,refs,holdout,reports,result=fixture
    assert result['identifiability']=='ambiguous' and len(result['tied_profile_sha256'])==3
    held=evaluate_holdout(protocol,result,holdout)
    assert held['selected_profile_sha256']==result['selected_profile_sha256']
    assert held['summary']['required']==held['summary']['evaluable']==1
    assert held['summary']['pass_count']==0 and not held['summary']['whole_protocol_pass']
    assert held['summary']['numerical_status']=='needs_review' and held['summary']['physical_status']=='pending'
    assert result['calibration_status']=='uncalibrated'


def test_holdout_leakage_partial_input_and_no_convergence_blocked(fixture):
    p,b,f,h,c,result=fixture
    for supplied in ({**f,**h},{},h):
        with pytest.raises(ValueError,match='leakage|exactly'):fit(p,b,supplied,convergence_reports=c)
    with pytest.raises(ValueError,match='convergence'):fit(p,b,f,convergence_reports={})
    with pytest.raises(ValueError,match='leakage|exactly'):evaluate_holdout(p,result,{**f,**h})


def test_holdout_not_in_fit_objective_or_candidate_selection(fixture):
    p,b,f,h,c,result=fixture
    # Repeated fitting has no input or function capable of reading holdout values.
    changed=deepcopy(h);ref=next(iter(changed.values()));ref['endpoints']['final_origin_x_mm']['value']+=10000
    repeated=fit(p,b,f,convergence_reports=c)
    assert repeated['content_hash']==result['content_hash']
    with pytest.raises(ValueError,match='Stale'):evaluate_holdout(p,result,changed)


@pytest.mark.parametrize('mutation',['same-group','renamed-variant','missing-required','wrong-units','wrong-policy','wrong-version','nan','wrong-budget'])
def test_frozen_protocol_errors(fixture,mutation):
    protocol,*_=fixture;p=deepcopy(protocol)
    if mutation=='same-group':p['cases'][1]['motion_group']=p['cases'][0]['motion_group']
    if mutation=='renamed-variant':
        p['cases'][1]['configuration']['initial_condition']['source']=deepcopy(p['cases'][0]['configuration']['initial_condition']['source'])
        p['cases'][1]['configuration']['initial_condition']=reseal(p['cases'][1]['configuration']['initial_condition'])
    if mutation=='missing-required':p['cases'][0]['required_endpoints']=[]
    if mutation=='wrong-units':p['cases'][0]['endpoint_rules']['final_origin_x_mm']['units']='m'
    if mutation=='wrong-policy':p['policy']['designated_t2']='rebound_only'
    if mutation=='wrong-version':p['schema_version']=2
    if mutation=='nan':p['search']['candidates'][0]=float('nan')
    if mutation=='wrong-budget':p['search']['budget']=1
    if mutation in ('same-group','renamed-variant','missing-required','wrong-units'):
        from src.utils.marker_profile_identity import digest
        p['source_identity']['identity']=digest(p['cases'])
    with pytest.raises(ValueError):validate_protocol(reseal(p))


def test_reference_truth_input_favorable_endpoint_and_stale_identity(fixture):
    p,b,refs,_,con,_=fixture
    for field,value in [('true_parameter',[.2]),('profile',contact_profile()),('extra_truth',{})]:
        bad=deepcopy(next(iter(refs.values())));bad[field]=value
        with pytest.raises(ValueError,match='fields'):validate_reference(reseal(bad))
    bad=deepcopy(refs);ref=next(iter(bad.values()));ref['endpoints']['final_origin_x_mm']['value']=0.;bad[ref['case_id']]=reseal(ref)
    with pytest.raises(ValueError,match='Stale reference'):fit(p,b,bad,convergence_reports=con)
    p2=deepcopy(p);p2['cases'][0]['configuration']['initial_condition']['linear_velocity_reference']='com'
    p2['cases'][0]['configuration']['initial_condition']['position_mm'][0]+=1
    p2['cases'][0]['configuration']['initial_condition']=reseal(p2['cases'][0]['configuration']['initial_condition'])
    from src.utils.marker_profile_identity import digest
    p2['source_identity']['identity']=digest(p2['cases']);p2=reseal(p2)
    with pytest.raises(ValueError,match='initial'):fit(p2,b,refs,convergence_reports=con)


def test_missing_reference_never_unique_or_pass(fixture):
    p,b,_,_,_,_=fixture;p=deepcopy(p)
    for case in p['cases']:case['reference_identity']=None
    from src.utils.marker_profile_identity import digest
    p['source_identity']['identity']=digest(p['cases']);p=reseal(p)
    con={p['cases'][0]['case_id']:convergence(p['cases'][0],b,event_policy())}
    result=fit(p,b,{p['cases'][0]['case_id']:None},convergence_reports=con)
    assert result['identifiability']=='unavailable-required-endpoint'
    held=evaluate_holdout(p,result,{p['cases'][1]['case_id']:None})
    assert held['summary']['required']==held['summary']['unavailable']==1 and held['summary']['evaluable']==0
    assert held['summary']['pass_count']==0 and not held['summary']['whole_protocol_pass']


def test_required_statuses_denominators_partial_and_zero_coercion():
    records=[dict(status=s,within_proposed_tolerance=None) for s in ('valid','ambiguous','unavailable','failed','not_detected','out_of_window')]
    report=aggregate(records,8,complete=False)
    assert report['required']==8 and report['reported']==6 and report['evaluable']==1
    assert report['denominators']==dict(required=8,evaluable=1)
    assert report['ambiguous']==report['unavailable']==report['failed']==1
    assert report['coverage']=='partial' and not report['all_required_evaluable'] and report['pass_count']==0
    ref=deepcopy(public_cases()[0]);result,*_=run_case(ref,contact_profile(),event_policy())
    # Explicit extraction on partial evidence cannot use favorable final samples.
    _,_,_,evaluation,recording,_=run_case(ref,contact_profile(),event_policy())
    recording['execution_status']='partial'
    endpoints=extract_endpoints(recording,evaluation,ref['eligible_endpoints'],ref['window_s'])
    assert all(x['value'] is None and x['status']=='unavailable' for x in endpoints.values())


def test_inactive_parameters_and_refsafe_confound_rejected():
    with pytest.raises(ValueError,match='inactive'):candidate_profile(contact_profile(condim=4),'rolling',.01)
    with pytest.raises(ValueError,match='inactive'):candidate_profile(contact_profile(condim=3),'torsional',.01)
    c=public_cases()[0];p=contact_profile(solref=(.002,1.),timestep_s=.001)
    with pytest.raises(ValueError,match='refsafe'):convergence(c,p,event_policy())


def test_changed_protocol_digest_selected_profile_and_partial_convergence(fixture):
    p,b,f,h,c,result=fixture
    changed=deepcopy(result);changed['selected_profile']['solref'][1]=.8
    with pytest.raises(ValueError,match='Stale'):evaluate_holdout(p,changed,h)
    changed=deepcopy(c);r=next(iter(changed.values()));r['runs'][0]['completion']='partial'
    r['runs'][0]=reseal(r['runs'][0])
    changed[next(iter(changed))]=reseal(r)
    with pytest.raises(ValueError,match='partial'):fit(p,b,f,convergence_reports=changed)
    changed=deepcopy(p);changed['version']='pub09-other-version';changed=reseal(changed)
    with pytest.raises(ValueError,match='differs'):evaluate_holdout(changed,result,h)


@pytest.mark.parametrize('mutation',['empty-endpoints','duplicate-results','omit-result','wrong-rule','invent-score',
    'nested-truth','wrong-source','wrong-base','promoted-summary','wrong-tie','convergence-endpoint','convergence-summary'])
def test_resealed_fit_cannot_change_population_rules_or_selected_profile(fixture,mutation):
    p,b,f,h,c,result=fixture;bad=deepcopy(result);candidate=bad['candidates'][0]
    if mutation=='empty-endpoints':
        for r in bad['candidates']:r.update(endpoints=[],score=0.,missing=0)
    if mutation=='duplicate-results':candidate['results'].append(deepcopy(candidate['results'][0]))
    if mutation=='omit-result':candidate['results']=[]
    if mutation=='wrong-rule':candidate['endpoints'][0]['weight']=0.
    if mutation=='invent-score':candidate['score']=0.123
    if mutation in ('nested-truth','wrong-source'):
        r=candidate['results'][0]
        if mutation=='nested-truth':r['endpoints']['final_origin_x_mm']['profile']=contact_profile()
        else:r['source_identity']={}
        candidate['results'][0]=reseal(r)
    if mutation=='wrong-base':bad['base_profile']=contact_profile(solref=(.02,.8));bad['base_profile_sha256']=bad['base_profile']['content_hash']
    if mutation=='promoted-summary':candidate['summary']['whole_protocol_pass']=True
    if mutation=='wrong-tie':bad['tied_profile_sha256']=[]
    if mutation.startswith('convergence-'):
        r=next(iter(bad['convergence_reports'].values()))
        if mutation=='convergence-summary':r['endpoint_stability']={}
        else:
            nested=r['runs'][0];nested['endpoints']={};r['runs'][0]=reseal(nested)
        r=reseal(r);bad['convergence_reports'][p['cases'][0]['case_id']]=r
        bad['convergence_sha256'][p['cases'][0]['case_id']]=r['content_hash']
    with pytest.raises(ValueError):evaluate_holdout(p,reseal(bad),h)


@pytest.mark.parametrize('mutation',['source','source-extra','approach','window','empty-endpoints','nested-profile','nested-truth','bool-value','string-value','missing-to-zero'])
def test_reference_rejects_nested_truth_and_invalid_declared_input(fixture,mutation):
    p,b,refs,*_=fixture;bad=deepcopy(next(iter(refs.values())));m=bad['endpoints']['final_origin_x_mm']
    if mutation=='source':bad['source_identity']={}
    if mutation=='source-extra':bad['source_identity']['true_parameter']=.2
    if mutation=='approach':bad['approach_sha256']='x'*64
    if mutation=='window':bad['window_s']=[1.,0.]
    if mutation=='empty-endpoints':bad['endpoints']={}
    if mutation=='nested-profile':m['profile']=contact_profile()
    if mutation=='nested-truth':m['true_parameter']=.2
    if mutation=='bool-value':m['value']=True
    if mutation=='string-value':m['value']='1'
    if mutation=='missing-to-zero':m.update(value=0.,status='unavailable',reason='absent',sample_time_s=None)
    with pytest.raises(ValueError):validate_reference(reseal(bad))


def test_reopened_holdout_validates_required_population(fixture):
    from src.simulation.contact_calibration import validate_holdout_report
    p,b,f,h,c,result=fixture;held=evaluate_holdout(p,result,h)
    for mutation in ('endpoints','results','summary'):
        bad=deepcopy(held)
        if mutation=='summary':bad['summary']['pass_count']=1
        else:bad[mutation]=[]
        with pytest.raises(ValueError):validate_holdout_report(reseal(bad),p,result,h)


def test_failed_cli_keeps_frozen_required_budget(fixture,tmp_path):
    from src.simulation.calibration_cli import main
    from src.simulation.initial_conditions import save,load
    p,b,f,h,c,result=fixture
    save(tmp_path/'protocol.json',p);save(tmp_path/'base.json',b);save(tmp_path/'refs.json',{});save(tmp_path/'convergence.json',c)
    output=tmp_path/'partial'
    assert main(['fit','--protocol',str(tmp_path/'protocol.json'),'--profile',str(tmp_path/'base.json'),
        '--references',str(tmp_path/'refs.json'),'--convergence',str(tmp_path/'convergence.json'),'--output',str(output)])==1
    report=load(output/'RunReport.json',lambda v:v)
    assert report['coverage']['required']==report['coverage']['unexecuted']==p['search']['budget']
    assert report['coverage']['fresh']==0 and report['coverage']['failed']==1


def test_rebound_height_is_unavailable_for_designated_new_feature():
    case=public_cases()[2]
    # Make rebound-height eligible without choosing a later, more favorable t2.
    case['eligible_endpoints'].append('rebound_height_mm')
    result,_,_,evaluation,recording,_=run_case(case,contact_profile(),event_policy())
    if evaluation['t2']['status']=='valid' and evaluation['t2']['value']['kind']=='new_feature_impact':
        assert result['endpoints']['rebound_height_mm']['status']=='unavailable'
        assert result['endpoints']['rebound_height_mm']['value'] is None
    else:
        # The same original designated event is retained; a literal controlled
        # classification covers the endpoint guard independently of dynamics.
        changed=deepcopy(evaluation);changed['t2']['value']['kind']='new_feature_impact'
        endpoints=extract_endpoints(recording,changed,['rebound_height_mm'],case['window_s'])
        assert endpoints['rebound_height_mm']['status']=='unavailable'


def test_resealed_result_cannot_replace_t2_with_later_impact():
    from src.simulation.contact_calibration import validate_case_result
    case=public_cases()[2];profile=contact_profile(solref=(.02,.2))
    result,*_=run_case(case,profile,event_policy())
    candidates=[e for e in result['event_sequence'] if e['eligible'] and e['release_group_id']==0]
    assert len(candidates)>=3
    later=candidates[2];bad=deepcopy(result)
    bad['designated_events']['t2']={k:later[k] for k in ('time_s','kind','bracket_s')}
    bad['event_brackets']['t2']=later['bracket_s']
    bad['endpoints']['dt12_s']['value']=later['time_s']-bad['designated_events']['t1']['time_s']
    with pytest.raises(ValueError,match='chronological'):validate_case_result(reseal(bad),case,profile)
