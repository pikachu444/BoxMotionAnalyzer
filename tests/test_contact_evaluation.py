from copy import deepcopy

import numpy as np
import pytest

from src.simulation.contact_policy import event_policy, frozen_protocol
from src.simulation.contact_fixtures import public_case
from src.simulation.contact_evaluation import evaluate_contacts, load_recording, save_document, validate_recording
from src.simulation.contact_comparison import compare_events, DETECTOR_CONTRACT
from src.utils.marker_profile_identity import envelope,digest


@pytest.mark.parametrize('expected',frozen_protocol()['expectations'],ids=lambda c:c['case_id'])
def test_frozen_public_expectations(expected):
    recording=public_case(expected['case_id'])
    window=(.08,.16) if expected['case_id']=='out-of-window' else None
    result=evaluate_contacts(recording,event_policy(),window=window)
    assert [e['kind'] for e in result['events']]==expected['kinds']
    assert result['t2']['status']==expected['t2_status']
    if expected['case_id'] in ('corner-edge','corner-face','rocking'):
        assert len(result['episodes'])==1


def test_recording_roundtrip_and_sidecar_no_overwrite(tmp_path):
    recording=public_case('corner-edge');path=tmp_path/'contacts.json';save_document(path,recording)
    assert load_recording(path)==recording
    with pytest.raises(FileExistsError):save_document(path,recording)
    with pytest.raises(ValueError):load_recording(path,dict(wrong='identity'))


@pytest.mark.parametrize('mutation',['version','plan','frame','time','units','nan','source','sign','local','order','missing','force'])
def test_invalid_contact_contract_rejected(mutation):
    r=public_case('corner-edge')
    if mutation=='version':r['schema_version']=2
    if mutation=='plan':r['plan_spec']='wrong'
    if mutation=='frame':r['contract']['world_frame']='analysis-y-up'
    if mutation=='time':r['contract']['time']='frames'
    if mutation=='units':r['contract']['units']['position']='m'
    if mutation=='nan':r['samples'][2]['origin_mm'][0]=float('nan')
    if mutation=='source':r['source_identity']['case_id']='relabel'
    if mutation=='order':r['samples'][4]['time_s']=0.
    if mutation=='missing':del r['samples'][4]['rotation']
    if mutation=='sign':r['samples'][50]['contacts'][0]['box_side_sign']=-1
    if mutation=='local':r['samples'][50]['contacts'][0]['box_surface_local_mm'][2]+=1
    if mutation=='force':r['samples'][50]['contacts'][0]['force_world_on_box_n'][2]=-5.
    with pytest.raises((ValueError,KeyError)):validate_recording(r)


def detector(times):
    source=dict(kind='test_only_ordered_events',version=1)
    return envelope('DetectorEvents',contract=deepcopy(DETECTOR_CONTRACT),source_identity=source,source_sha256=digest(source),
        status='valid',reason=None,t1_minus=dict(value=None,status='unavailable',reason='test-only'),settings={},failure=None,
        events=[dict(event_id=i,kind='legacy_contact_set_run',status='valid',eligible=True,time_s=t,bracket_s=[t-.002,t],corner_ids=[1]) for i,t in enumerate(times)])


def test_ordered_matching_first_only_vs_subsequent_and_extra_missing():
    truth=evaluate_contacts(public_case('corner-edge'),event_policy())
    both=compare_events(truth,detector([.112,.192]),event_policy())
    assert both['coverage']=='first_and_subsequent';assert abs(both['delta_t12']['value']['error_s'])<1e-12
    first=compare_events(truth,detector([.112]),event_policy())
    assert first['coverage']=='first_only';assert first['t2']['status']=='not_detected';assert len(first['unmatched_truth'])==1
    extra=compare_events(truth,detector([.112,.142,.192]),event_policy())
    assert len(extra['extra_detector'])==1;assert extra['t2']['status']=='ambiguous'
    late=compare_events(truth,detector([.112,.252]),event_policy())
    assert late['t2']['status']=='not_detected';assert len(late['unmatched_truth'])==len(late['extra_detector'])==1


def test_multiple_matches_ambiguous_no_favorable_t2():
    truth=evaluate_contacts(public_case('corner-edge'),event_policy())
    r=compare_events(truth,detector([.112,.182,.192]),event_policy())
    assert r['t2']['status']=='ambiguous';assert len(r['matches'])==1


def test_wrong_event_order_and_policy_cannot_pass():
    truth=evaluate_contacts(public_case('corner-edge'),event_policy());d=detector([.192,.112])
    with pytest.raises(ValueError):compare_events(truth,d,event_policy())
    p=event_policy();p['approach_mm_s']=1.
    with pytest.raises(ValueError):evaluate_contacts(public_case('rocking'),p)


def test_initial_support_and_constrained_floor_not_fabricated_impact():
    r=public_case('face-single');r['samples']=r['samples'][50:]
    result=evaluate_contacts(r,event_policy());assert result['events'][0]['kind']=='initial_support'
    assert result['t1']['status']=='unavailable'
    r=public_case('corner-edge')
    for s in r['samples']:s['box_attached']=True
    result=evaluate_contacts(r,event_policy());assert not any(e['eligible'] for e in result['events'])


def test_recording_does_not_change_live_state_or_default_results():
    from src.simulation.engine.mujoco_engine import MuJoCoEngine
    def execute(record):
        e=MuJoCoEngine(size=(200,120,80),mass=1);e.set_initial_state(100,[1,0,0,0])
        if record:e.enable_contact_recording(dict(case='actual-single',geometry_mm=[200,120,80]))
        h=e.record_samples(80,4)
        return e,h
    base,bh=execute(False);recorded,rh=execute(True)
    for b,r in zip(bh,rh):
        assert b.keys()==r.keys()
        for key in b:np.testing.assert_array_equal(b[key],r[key])
    np.testing.assert_array_equal(base.data.qpos,recorded.data.qpos);np.testing.assert_array_equal(base.data.qvel,recorded.data.qvel)
    assert len(recorded.contact_recorder.samples)==317
    validate_recording(recorded.contact_recorder.document())


def test_missing_failed_incomplete_and_known_outside_are_distinct():
    from src.simulation.contact_evaluation import evaluate_available
    assert evaluate_available(None,event_policy())['status']=='unavailable'
    r=public_case('corner-edge');del r['contract']
    assert evaluate_available(r,event_policy())['status']=='failed'
    r=public_case('corner-edge');r['samples']=r['samples'][:70];r['execution_status']='time_limit'
    assert evaluate_contacts(r,event_policy())['t2']['status']=='unavailable'
    r=public_case('corner-edge')
    assert evaluate_contacts(r,event_policy(),window=(.08,.16))['t2']['status']=='out_of_window'


def test_unmatched_late_interval_error_is_retained_and_not_promoted():
    truth=evaluate_contacts(public_case('corner-edge'),event_policy())
    r=compare_events(truth,detector([.112,.252]),event_policy())
    assert r['delta_t12']['status']=='unavailable'
    assert r['declared_delta_t12']['value']['error_s']==pytest.approx(.060)
    assert r['numerical_acceptance']=='needs_review'


def test_wrong_body_point_velocity_and_unknown_version_fail():
    r=public_case('corner-edge');r['samples'][49]['corners_velocity_mm_s'][1][2]=1.
    with pytest.raises(ValueError):validate_recording(r)
    r=public_case('corner-edge');r['samples'][51]['contacts'][0]['geom_ids'][0]=1
    with pytest.raises(ValueError):validate_recording(r)
    r=public_case('corner-edge');r['mujoco_version']='unknown'
    with pytest.raises(ValueError):validate_recording(r)


def test_t2_does_not_cross_into_a_later_release():
    r=public_case('corner-edge')
    for s in r['samples']:
        if .14<=s['time_s']<.16:s['box_attached']=True
    result=evaluate_contacts(r,event_policy())
    assert result['t2']['status']=='not_detected'
    assert [e['release_group_id'] for e in result['events'] if e['eligible']]==[0,1]


def test_unsupported_detector_frame_and_stale_configuration_cannot_match():
    t=evaluate_contacts(public_case('corner-edge'),event_policy());d=detector([.112,.192])
    d['contract']['world_frame']='mujoco-z-up'
    with pytest.raises(ValueError):compare_events(t,d,event_policy())
    d=detector([.112,.192]);t['source_identity']['public_configuration_sha256']='a'*64
    with pytest.raises(ValueError):compare_events(t,d,event_policy())


def test_split_onset_within_resolution_is_retained_as_ambiguous_cluster():
    r=public_case('corner-edge')
    # Move C2's independently armed onset to 2 ms after C1; retain original data separately.
    for k in range(51,90):
        r['samples'][k]['contacts'].append(deepcopy(r['samples'][90]['contacts'][1]))
    r['samples'][50]['origin_velocity_mm_s']=[0.,0.,-200.]
    r['samples'][50]['corners_velocity_mm_s']=[[0.,0.,-200.]]*8
    t=evaluate_contacts(r,event_policy())
    assert t['t2']['status']=='ambiguous';assert len(t['onset_clusters'])==1
    assert len(t['onset_clusters'][0]['onset_event_ids'])==2


def test_evaluation_and_detector_roundtrip_and_mutant_event_kind(tmp_path):
    import json
    from src.simulation.contact_evaluation import load_evaluation
    from src.simulation.contact_comparison import validate_detector
    r=public_case('corner-edge');t=evaluate_contacts(r,event_policy());p=tmp_path/'evaluation.json';save_document(p,t)
    reopened=load_evaluation(p,event_policy(),r);assert digest(reopened)==digest(t)
    d=detector([.112,.192]);save_document(tmp_path/'detector.json',d)
    d2=json.loads((tmp_path/'detector.json').read_text());validate_detector(d2)
    comp=compare_events(reopened,d2,event_policy());save_document(tmp_path/'comparison.json',comp)
    assert json.loads((tmp_path/'comparison.json').read_text())==comp
    reopened['events'][1]['kind']='unknown-kind'
    with pytest.raises(ValueError):compare_events(reopened,d,event_policy())
    d2['events'][1]['kind']='simulator-truth-injected'
    with pytest.raises(ValueError):compare_events(t,d2,event_policy())


def test_conflicting_legacy_first_event_cannot_be_skipped_for_later_anchor():
    t=evaluate_contacts(public_case('corner-edge'),event_policy());d=detector([0.,.112,.192])
    d['events'][0].update(status='ambiguous',reason='Legacy run begins at support; t1-minus refers to a later drop.')
    r=compare_events(t,d,event_policy())
    assert r['t1']['status']=='ambiguous';assert r['t1_shift_s']['status']=='unavailable'
    assert r['matches']==[];assert len(r['extra_detector'])==3


def test_raw_contact_pair_rejects_stale_observed_input(tmp_path):
    from src.simulation.contact_comparison import observation_pair
    r=public_case('corner-edge');t=evaluate_contacts(r,event_policy());raw=tmp_path/'observed.csv';raw.write_text('neutral observed input')
    pair=observation_pair(t,raw);d=detector([.112,.192]);d['source_identity']['raw_sha256']=pair['raw_sha256'];d['source_sha256']=digest(d['source_identity'])
    assert compare_events(t,d,event_policy(),pairing=pair)['t1']['status']=='valid'
    d['source_identity']['raw_sha256']='f'*64;d['source_sha256']=digest(d['source_identity'])
    with pytest.raises(ValueError):compare_events(t,d,event_policy(),pairing=pair)


def test_user_event_scope_does_not_promote_accuracy_or_baseline():
    from src.simulation.contact_policy import policy_approval
    approval=policy_approval(event_policy())
    assert approval['event_scope']=='approved'
    assert approval['thresholds'] in ('proposed','approved')
    assert approval['numerical_accuracy']=='proposed';assert approval['baseline']=='none'
    t=evaluate_contacts(public_case('corner-edge'),event_policy())
    result=compare_events(t,detector([.112,.192]),event_policy(),approval=approval)
    assert result['numerical_acceptance']=='needs_review'


def test_post_impact_motion_cannot_realign_an_ambiguous_first_event():
    from src.simulation.contact_comparison import motion_diagnostics
    recording=public_case('corner-edge');t=evaluate_contacts(recording,event_policy());d=detector([0.,.112,.192])
    d['events'][0].update(status='ambiguous',reason='First support run conflicts with impact.')
    comparison=compare_events(t,d,event_policy())
    motion=motion_diagnostics(recording,t,d,None,comparison=comparison)
    assert motion['status']=='ambiguous';assert 'single_t1_shift_s' not in motion
    assert 'truth' not in motion;assert 'detector' not in motion
    stale=deepcopy(comparison);stale['truth_sha256']='0'*64
    with pytest.raises(ValueError):motion_diagnostics(recording,t,d,None,comparison=stale)


def test_duplicate_reordered_or_hidden_designated_truth_endpoint_rejected():
    from src.simulation.contact_evaluation import validate_evaluation
    t=evaluate_contacts(public_case('corner-edge'),event_policy())
    for key in ('t1','t2'):
        mutant=deepcopy(t);mutant[key]=deepcopy(t['t2' if key=='t1' else 't1'])
        with pytest.raises(ValueError):validate_evaluation(mutant,event_policy())
    mutant=deepcopy(t);mutant['t2']=dict(value=None,status='not_detected',reason='hidden event')
    with pytest.raises(ValueError):compare_events(mutant,detector([.112,.192]),event_policy())


def test_ambiguous_designated_detector_t2_is_preserved():
    t=evaluate_contacts(public_case('corner-edge'),event_policy());d=detector([.112,.192,.194])
    d['events'][1]['status']='ambiguous'
    c=compare_events(t,d,event_policy())
    assert c['t2']['status']=='ambiguous';assert len(c['matches'])==1
    assert len(c['ambiguous']['detector'])==1;assert len(c['extra_detector'])==2


def test_truth_reserved_by_ambiguous_matching_cannot_be_matched_again():
    r=public_case('corner-face')
    for k in range(90,95):r['samples'][k]['contacts']=r['samples'][k]['contacts'][:2]
    r['samples'][94]['origin_velocity_mm_s']=[0.,0.,-200.]
    r['samples'][94]['corners_velocity_mm_s']=[[0.,0.,-200.]]*8
    t=evaluate_contacts(r,event_policy());c=compare_events(t,detector([.112,.197,.222]),event_policy())
    reserved={i for a in c['ambiguous']['matching'] for i in a['truth_ids']}
    assert reserved=={1,2};assert reserved.isdisjoint(m['truth_id'] for m in c['matches'])
    assert len(c['matches'])==1


def test_partial_contact_capture_does_not_establish_t2_absence():
    r=public_case('corner-edge');r['samples']=r['samples'][:70];r['execution_status']='partial'
    t=evaluate_contacts(r,event_policy())
    assert t['t1']['status']=='valid';assert t['t2']['status']=='unavailable'


@pytest.mark.parametrize('mutation',['wrong_body_pair','missing_efc','inactive_force'])
def test_contact_body_and_force_constraint_evidence_is_required(mutation):
    r=public_case('corner-edge')
    for s in r['samples']:
        for c in s['contacts']:
            if mutation=='wrong_body_pair':c.update(body_ids=[1,0],body_names=['box','world'])
            elif mutation=='missing_efc':del c['efc_address']
            else:c['efc_address']=-1
    with pytest.raises(ValueError):validate_recording(r)


@pytest.mark.parametrize('case_id',['corner-edge','gripper-only'])
def test_known_geom_pair_cannot_be_hidden_as_other_contact(case_id):
    r=public_case(case_id)
    for s in r['samples']:
        for c in s['contacts']:c['role']='other'
    with pytest.raises(ValueError):evaluate_contacts(r,event_policy())
