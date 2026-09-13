"""Trial-record contracts on literal box trajectories; no detector truth input."""
from copy import deepcopy
from dataclasses import replace
import hashlib
import json

import numpy as np
import pandas as pd
import pytest

from src.analysis.pipeline.scene_detection import DetectionResult, DetectionSettings, Registration, SceneCandidate
from src.analysis.pipeline.scene_review import SceneReviewSession, validate_scene_review_json
from src.analysis.pipeline.scene_trial_record import validate_trial_record, expected_faces, eligibility_suggestion
from src.analysis.pipeline.scene_workspace import save_workspace, read_workspace, restore_session


def entry(attempt='first', order=1, anchor=.3, item='G16', **kwargs):
    return dict(attempt_id=attempt, performed_order=order, anchor_time_s=anchor,
                anchor_kind='contact', activity_kind='trial', item=item, **kwargs)


def record(digest, entries=None, **kwargs):
    return dict(kind='boxmotion-trial-record', version=1, record_id='public-unit-record',
        capture=dict(sha256=digest, basis='active', time_basis='capture_seconds'),
        ista_type='G', applied_edition='2018-03', trials=entries or [entry(conditions={'critical_face_status': 'unknown'})], **kwargs)


@pytest.fixture
def review(tmp_path):
    source = tmp_path / 'source.csv'
    source.write_text('Independent source reference for persistence contract.\n')
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    times = np.arange(11) / 10
    q = np.array([[-100,-60,-40],[100,-60,-40],[100,60,-40],[-100,60,-40],
                  [-100,-60,40],[100,-60,40],[100,60,40],[-100,60,40]]) / 1000
    origin = np.zeros((11, 3))
    origin[:, 1] = .06 + np.array([.03,.02,.01,0,0,.03,.02,.01,0,0,0])
    corners = origin[:, None, :] + q
    profile = {'units':'mm', 'origin':'box-geometric-center', 'box_dims_mm':[200.,120.,80.],
               'markers':[{'id':f'P{i}', 'xyz_mm':(point * 1000).tolist()} for i, point in enumerate(q[:4])]}
    result = DetectionResult([SceneCandidate('scene_001',0.,.4,'free_fall','free_fall'),
                              SceneCandidate('scene_002',.5,1.,'free_fall','free_fall')],
        pd.DataFrame({'Relative rotation (deg)':np.zeros(11)}, index=times), origin,
        np.broadcast_to(np.eye(3),(11,3,3)).copy(), corners, DetectionSettings(),
        Registration(profile,floor_y_mm=0.), np.ones(11,dtype=bool),np.zeros(11,dtype=int))
    session = SceneReviewSession(result,digest)
    session.set_context('G','2018-03')
    for row in session.rows:
        session.set_decision(row['id'],'include')
    return source,result,session


@pytest.mark.parametrize('change', [
    lambda d: d.update(version=True),
    lambda d: d['capture'].update(time_basis='unix_seconds'),
    lambda d: d['trials'][0].update(anchor_time_s=float('inf')),
    lambda d: d['trials'][0].update(item='G18'),
    lambda d: d['trials'][0].update(extra='unsupported'),
    lambda d: d['trials'][0].update(conditions={'pivot_faces':['LEFT','RIGHT']}),
    lambda d: d['trials'][0].update(conditions={'hazard_used':1}),
    lambda d: d['trials'][0].update(repeat_of='absent'),
])
def test_record_rejects_unsupported_or_nonfinite_values(change):
    data = record('a'*64)
    change(data)
    with pytest.raises(ValueError):
        validate_trial_record(data)


def test_independent_recorded_item_survives_different_observed_face_and_intent(review):
    _, _, session = review
    session.set_intended_contact('scene_001',['TOP'])
    intended = deepcopy(session.row('scene_001')['intended_contact'])
    session.set_trial_record(record(session.source_sha256))
    row = session.row('scene_001')
    assert row['item_candidates'] == ['G16']
    assert row['observed_consistency']['approach'] == 'different'
    assert row['observed_consistency']['expected_faces'] == ['LEFT']
    assert row['observed_consistency']['observed_faces'] == ['BOTTOM']
    assert row['intended_contact'] == intended
    session.confirm_item(row['id'],'G16')
    assert row['identity']['scenario_id'] == 'G16'
    assert row['identity']['record_reference']['attempt_id'] == 'first'
    payload = json.loads(session.payload(row['id']))
    payload['identity']['scenario_kind'] = 'tip_over'
    with pytest.raises(ValueError,match='record reference'):
        validate_scene_review_json(payload)


def test_record_import_rejects_source_and_context_before_mutation(review):
    _, _, session = review
    session.set_trial_record(record(session.source_sha256))
    session.confirm_item('scene_001','G16')
    before = deepcopy(session.rows),deepcopy(session.trial_record)
    wrong = record('f'*64)
    with pytest.raises(ValueError,match='hash'):
        session.set_trial_record(wrong)
    wrong = record(session.source_sha256)
    wrong['ista_type'],wrong['trials'][0]['item'] = 'H','H/B05'
    with pytest.raises(ValueError,match='selected Type'):
        session.set_trial_record(wrong)
    assert (session.rows,session.trial_record) == before


def test_anchor_order_is_independent_of_input_order_missing_and_retests(review):
    _, _, session = review
    entries = [entry('repeat',8,.8,'G09',repeat_of='first'), entry('uncaptured',9,3.,'G10'),
               entry('missing',1,None,'G01'),entry('first',5,.3,'G08')]
    session.set_trial_record(record(session.source_sha256,entries))
    assert [r['item_candidates'] for r in session.rows] == [['G08'],['G09']]
    assert all(not r['identity']['confirmed'] for r in session.rows)


@pytest.mark.parametrize('entries,status', [
    ([entry(),entry('second',2,.3,'G08')],'ambiguous_anchors'),
    ([entry(order=2),entry('second',1,.8,'G08')],'contradictory_order'),
    ([entry(order=1),entry('second',1,.8,'G08')],'contradictory_order'),
])
def test_ambiguous_anchor_or_order_never_confirms(review,entries,status):
    _, _, session = review
    session.set_trial_record(record(session.source_sha256,entries))
    assert session.rows[0]['record_evidence']['association'] == status
    assert session.rows[0]['item_candidates'] == []
    with pytest.raises(ValueError):
        session.confirm_item('scene_001','G16')


def test_workspace_recomputes_on_saved_ranges_and_keeps_legacy_absence(review,tmp_path):
    source,result,session = review
    path = tmp_path / 'saved.json'
    legacy = save_workspace(path,session,source,[200.,120.,80.])
    assert 'trial_record' not in legacy
    old,changed = restore_session(legacy,result,session.source_sha256)
    assert not changed and old.rows == session.rows
    session.set_trial_record(record(session.source_sha256))
    session.confirm_item('scene_001','G16')
    save_workspace(path,session,source,[200.,120.,80.])
    loaded = read_workspace(path)
    assert set(loaded['context']) == {'ista_type','applied_edition'}
    restored,changed = restore_session(loaded,result,session.source_sha256)
    assert not changed and restored.rows == session.rows
    manual = session.add_range(.1,.35)
    session.refresh(result)
    session.set_decision(manual,'include')
    assert session.row('scene_001')['record_evidence']['association'] == 'overlapping_included_ranges'
    assert not session.row('scene_001')['identity']['confirmed']
    session.set_decision('scene_002','exclude')
    save_workspace(path,session,source,[200.,120.,80.])
    restored,changed = restore_session(read_workspace(path),result,session.source_sha256)
    assert not changed
    assert restored.row('scene_001')['record_evidence']['association'] == 'overlapping_included_ranges'
    assert restored.row(manual)['decision'] == 'include'


def test_original_binding_requires_verified_reader_argument(review,tmp_path):
    source,result,session = review
    session.original_source_sha256 = 'b'*64
    data = record(session.source_sha256)
    data['capture'].update(basis='original',sha256='b'*64)
    session.set_trial_record(data)
    session.confirm_item('scene_001','G16')
    path = tmp_path / 'original.json'
    saved = save_workspace(path,session,source,[200.,120.,80.])
    saved['original_source_sha256'] = 'b'*64  # Untrusted workspace declaration cannot authorize binding.
    with pytest.raises(ValueError,match='verified capture'):
        restore_session(saved,result,session.source_sha256)
    restored,changed = restore_session(saved,result,session.source_sha256,original_source_sha256='b'*64)
    assert not changed and restored.rows == session.rows


def test_changed_geometry_or_cached_observation_requires_recheck_but_keeps_record(review,tmp_path):
    source,result,session = review
    session.set_trial_record(record(session.source_sha256))
    session.confirm_item('scene_001','G16')
    path = tmp_path / 'evidence.json'
    saved = save_workspace(path,session,source,[200.,120.,80.])
    corrupt = deepcopy(saved)
    corrupt['rows'][0]['observed_consistency']['approach'] = 'match'
    restored,changed = restore_session(corrupt,result,session.source_sha256)
    assert changed == {'scene_001'}
    assert restored.rows[0]['decision'] == 'unreviewed'
    assert restored.rows[0]['observed_consistency']['approach'] == 'different'
    assert restored.rows[0]['previous_review']['identity']['scenario_id'] == 'G16'
    assert restored.trial_record == session.trial_record
    moved = replace(result,registration=replace(result.registration,floor_y_mm=2.))
    restored,changed = restore_session(saved,moved,session.source_sha256)
    assert changed and not restored.rows[0]['identity']['confirmed']
    assert restored.rows[0]['observed_consistency']['motion'] == 'unavailable'
    assert restored.trial_record == session.trial_record


def test_record_context_change_and_clear_keep_previous_selection(review):
    _,_,session = review
    session.set_trial_record(record(session.source_sha256))
    session.confirm_item('scene_001','G16')
    session.set_context('G',None)
    assert session.row('scene_001')['item_candidates'] == []
    assert session.row('scene_001')['previous_review']['identity']['scenario_id'] == 'G16'
    session.set_trial_record(None)
    assert 'record_evidence' not in session.row('scene_001')
    assert session.row('scene_001')['previous_review']['trial_record']['record_id'] == 'public-unit-record'


def test_previous_identity_record_and_reference_remain_one_snapshot(review,tmp_path):
    source,result,session = review
    records = []
    for label,item in [('A','G16'),('B','G08'),('C','G09')]:
        data = record(session.source_sha256,[entry(item=item)])
        data['record_id'] = label
        records.append(data)
    session.set_trial_record(records[0])
    session.confirm_item('scene_001','G16')
    session.set_trial_record(records[1])
    session.confirm_item('scene_001','G08')
    session.set_trial_record(records[2])
    previous = session.rows[0]['previous_review']
    assert previous['identity']['scenario_id'] == 'G08'
    assert previous['trial_record']['record_id'] == 'B'
    assert previous['identity']['record_reference']['record_sha256'] == previous['record_evidence']['record_sha256']
    assert previous['identity']['record_reference']['record_id'] == previous['trial_record']['record_id']
    # A later, unconfirmed C record cannot replace B inside that snapshot.
    path = tmp_path / 'snapshot.json'
    session.set_range('scene_001',0.,.35)
    saved = save_workspace(path,session,source,[200.,120.,80.])
    restored,changed = restore_session(saved,result,session.source_sha256)
    assert changed
    assert restored.rows[0]['previous_review']['trial_record']['record_id'] == 'B'
    assert restored.rows[0]['previous_review']['identity']['scenario_id'] == 'G08'


def test_detection_version_refresh_preserves_confirmed_record_snapshot(review):
    _,result,session = review
    data = record(session.source_sha256)
    session.set_trial_record(data)
    session.confirm_item('scene_001','G16')
    session.refresh(replace(result,version='independent-new-version'))
    previous = session.rows[0]['previous_review']
    assert session.rows[0]['decision'] == 'unreviewed'
    assert previous['identity']['scenario_id'] == 'G16'
    assert previous['trial_record'] == data
    assert 'detection_version_changed' in previous['reasons']


def test_unclear_motion_does_not_claim_a_different_observed_trial(review):
    _,_,session = review
    # Keep the legacy evidence class to exercise the motion-specific guard.
    session.rows[0]['motion'] = 'unclear'
    session.set_trial_record(record(session.source_sha256))
    assert session.rows[0]['item_candidates'] == ['G16']
    assert session.rows[0]['observed_consistency']['motion'] == 'unavailable'
    assert session.rows[0]['observed_consistency']['approach'] == 'unavailable'


def test_unspecified_trial_item_does_not_infer_recorded_free_fall(review):
    _,_,session = review
    session.set_trial_record(record(session.source_sha256,[entry(item=None)]))
    assert session.rows[0]['motion'] == 'free_fall'
    assert session.rows[0]['item_candidates'] == []
    assert session.rows[0]['observed_consistency']['motion'] == 'unavailable'


def test_record_ui_exposes_type_suggestion_and_order_reason_without_selecting_type(review):
    from PySide6.QtWidgets import QApplication
    from src.analysis.ui.widget_scene_review import SceneReviewWidget, _item_tooltip
    app = QApplication.instance() or QApplication([])
    _,_,session = review
    session.set_context('Unknown',None)
    data = record(session.source_sha256,eligibility=dict(product_category='tv_monitor',shipment_method='parcel',
                  handling_method='standard',mass_kg=20.,girth_mm=2000.))
    data['ista_type'] = 'Unknown'
    session.set_trial_record(data)
    widget = SceneReviewWidget()
    try:
        widget.session = session
        widget.refresh('scene_001')
        assert widget.type_combo.currentText() == 'Unknown'
        assert 'suggests Type G' in widget.type_combo.toolTip()
        assert 'remains unconfirmed' in _item_tooltip(session.rows[0])
        data['trials'] = [entry(order=2),entry('second',1,.8,'G08')]
        session.set_trial_record(data)
        widget.refresh('scene_001')
        assert 'Performed order conflicts' in widget.table.item(0,6).toolTip()
        assert not widget.confirm_button.isEnabled()
    finally:
        widget.close()
        widget.deleteLater()
        app.processEvents()


def test_record_ui_distinguishes_candidate_from_explicit_confirmation(review):
    from PySide6.QtWidgets import QApplication
    from src.analysis.ui.widget_scene_review import SceneReviewWidget
    app = QApplication.instance() or QApplication([])
    _,_,session = review
    session.set_trial_record(record(session.source_sha256))
    widget = SceneReviewWidget()
    try:
        widget.session = session
        widget.refresh('scene_001')
        assert widget.table.item(0,6).text() == 'G16 ?'
        assert 'Recorded item unconfirmed' in widget.table.item(0,6).toolTip()
        session.confirm_item('scene_001','G16')
        widget.refresh('scene_001')
        assert widget.table.item(0,6).text() == 'G16'
        assert 'Recorded item confirmed' in widget.table.item(0,6).toolTip()
        assert widget.table.item(0,8).text() == 'Different approach'
    finally:
        widget.close()
        widget.deleteLater()
        app.processEvents()


def test_operator_context_can_complete_unknown_record_without_rewriting_it(review,tmp_path):
    source,result,session = review
    session.set_context('Unknown',None)
    data = record(session.source_sha256,[entry(item='G08')])
    data['ista_type'],data['applied_edition'] = 'Unknown',None
    session.set_trial_record(data)
    assert session.rows[0]['item_candidates'] == []
    session.set_context('G','2018-03')
    row = session.rows[0]
    assert row['item_candidates'] == ['G08']
    assert row['observed_consistency']['expected_faces'] == ['FRONT']
    session.confirm_item('scene_001','G08')
    assert session.trial_record == data
    path = tmp_path / 'operator-context.json'
    saved = save_workspace(path,session,source,[200.,120.,80.])
    restored,changed = restore_session(saved,result,session.source_sha256)
    assert not changed and restored.rows == session.rows
    session.set_context('H','2018-03')
    assert session.rows[0]['item_candidates'] == []
    assert not session.rows[0]['identity']['confirmed']


@pytest.mark.parametrize('item,conditions,expected', [
    ('G16',{},None),('G16',{'critical_face_status':'unknown'},['LEFT']),
    ('G16',{'critical_face_status':'selected'},None),
    ('G16',{'critical_face_status':'selected','target_faces':['TOP']},['TOP']),
    ('G17',{},None),('G17',{'package_form':'standard'},['FRONT']),
    ('G17',{'package_form':'flat'},['BOTTOM']),('G17',{'package_form':'elongated'},['BOTTOM']),
])
def test_special_targets_require_explicit_conditions(item,conditions,expected):
    assert expected_faces(entry(item=item,conditions=conditions),'G','2018-03') == expected


@pytest.mark.parametrize('ista_type,edition', [('G','2024-01'),('G',None),('H','2018-03'),('Unknown','2018-03')])
def test_reference_targets_need_effective_type_and_applied_edition(review,ista_type,edition):
    _,_,session = review
    session.set_trial_record(record(session.source_sha256))
    session.set_context(ista_type,edition)
    evidence = session.rows[0]['observed_consistency']
    assert evidence['expected_faces'] is None
    assert evidence['target_basis'] == 'unavailable'
    assert evidence['approach'] == 'unavailable'
    assert evidence['motion'] == 'unavailable'
    assert session.rows[0]['item_candidates'] == []


@pytest.mark.parametrize('edition', [None,'2024-01'])
def test_explicit_record_target_compares_geometry_without_protocol_inference(review,edition):
    _,_,session = review
    session.set_context('G',edition)
    data = record(session.source_sha256,[entry(conditions={'target_faces':['LEFT']})])
    data['applied_edition'] = edition
    session.set_trial_record(data)
    evidence = session.rows[0]['observed_consistency']
    assert evidence['expected_faces'] == ['LEFT']
    assert evidence['target_basis'] == 'explicit_record'
    assert evidence['approach'] == 'different'
    assert evidence['motion'] == 'unavailable'
    assert not session.rows[0]['identity']['confirmed']


@pytest.mark.parametrize('shipment,mass,girth,expected', [
    ('parcel',67.9,4190.,'G'),('parcel',68.,4190.,None),('parcel',67.,4190.1,None),
    ('ltl',68.,4190.,'H'),('ltl',67.,4190.1,'H'),('ltl',67.,4190.,None),
])
def test_eligibility_suggestion_is_complete_p2_context_only(shipment,mass,girth,expected):
    data = record('a'*64,eligibility=dict(product_category='tv_monitor',shipment_method=shipment,
                handling_method='standard',mass_kg=mass,girth_mm=girth))
    assert eligibility_suggestion(data)['suggested_type'] == expected
    del data['eligibility']['mass_kg']
    assert eligibility_suggestion(data)['suggested_type'] is None
