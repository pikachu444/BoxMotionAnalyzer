"""Independent geometric inputs for intent comparison, not measured impacts."""
from dataclasses import asdict
import json

import numpy as np
import pandas as pd
import pytest
from scipy.spatial.transform import Rotation

from impact_metric_fixtures import make_frame, update_processing, REVIEW, SUMMARY
from src.analysis.compare.contact_metrics import calculate_contact_comparison
from src.analysis.compare.data_model import ComparisonModel
from src.analysis.pipeline.scene_detection import DetectionSettings


def contact_frame(*, target=('BOTTOM',), observed='{C1,C2,C5,C6}', rotation=None, source='a' * 64):
    times = np.arange(13) * .008
    frame = make_frame(times=times, t1=times[9], impact=times[10], source_sha256=source,
                       omega=(0, 0, 0), com_offset=None)
    rotation = Rotation.identity() if rotation is None else rotation
    local = np.array([[-100,-60,-40], [100,-60,-40], [100,60,-40], [-100,60,-40],
                      [-100,-60,40], [100,-60,40], [100,60,40], [-100,60,40]])
    rotated = rotation.apply(local)
    clearance = np.maximum(0., .5 * 9806.65 * (times[10] ** 2 - times ** 2))
    frame[('Position', 'CoM', 'P_TY')] = clearance - rotated[:, 1].min()
    for axis in 'XZ':
        frame[('Position', 'CoM', 'P_T' + axis)] = 0.
    for index, axis in enumerate('XYZ'):
        frame[('Position', 'CoM', 'P_R' + axis)] = rotation.as_rotvec()[index]
    for i, corner in enumerate(rotated, 1):
        for axis, coordinate in zip('XYZ', corner):
            frame[('Position', f'C{i}', 'P_T' + axis)] = (
                coordinate + frame[('Position', 'CoM', 'P_T' + axis)])
    frame[(*SUMMARY, 'FirstImpactContact')] = observed
    review = json.loads(frame[REVIEW].iloc[0])
    review['detection']['settings'] = asdict(DetectionSettings())
    if target is not None:
        review['candidate']['intended_contact'] = {
            'version': 1, 'basis': 'operator', 'faces': sorted(target),
            'registration_sha256': review['detection']['registration_sha256'],
            'ista_type': 'G', 'applied_edition': '2018-03',
        }
    frame[REVIEW] = json.dumps(review)
    return frame


def change_review(frame, edit):
    data = json.loads(frame[REVIEW].iloc[0])
    edit(data)
    frame[REVIEW] = json.dumps(data)


@pytest.mark.parametrize(('target', 'observed', 'rotation', 'expected'), [
    (('BOTTOM',), '{C1,C2,C5,C6}', None, 'Match'),
    (('BOTTOM',), '{C1,C5}', Rotation.from_euler('z', 30, degrees=True), 'Different'),
    (('BOTTOM', 'LEFT'), '{C1,C5}', Rotation.from_euler('z', 30, degrees=True), 'Match'),
    (('BOTTOM', 'LEFT'), 'C5', Rotation.from_euler('zx', [20,20], degrees=True), 'Different'),
    (('BOTTOM', 'LEFT', 'FRONT'), 'C5', Rotation.from_euler('zx', [20,20], degrees=True), 'Match'),
    (('BOTTOM', 'LEFT', 'FRONT'), '{C1,C5}', Rotation.from_euler('z', 30, degrees=True), 'Different'),
    (('TOP',), '{C1,C2,C5,C6}', None, 'Different'),
])
def test_exact_contact_feature_agreement(target, observed, rotation, expected):
    frame = contact_frame(target=target, observed=observed, rotation=rotation)
    original = frame.copy(deep=True)
    result = calculate_contact_comparison(frame)
    assert result.outcome == expected, result.reason
    assert result.time_s == .080
    assert result.intended and result.observed
    assert not result.reason
    pd.testing.assert_frame_equal(frame, original)


@pytest.mark.parametrize('observed', ['', '{C1,C1}', 'C9', '{C1,C6}', '{C1,C2,C5}', '{C1,C2,C3,C4,C5}'])
def test_ambiguous_or_malformed_observed_feature_is_unclear(observed):
    result = calculate_contact_comparison(contact_frame(observed=observed))
    assert result.outcome == 'Unclear' and result.reason


def test_intention_is_not_inferred_from_detected_scenario_or_contact():
    result = calculate_contact_comparison(contact_frame(target=None))
    assert result.outcome == 'Unclear'
    assert result.target_key is None and 'No independent intended contact' in result.reason


@pytest.mark.parametrize('kind', ['H', 'Unknown'])
def test_local_contact_needs_no_type_edition_or_com(kind):
    frame = contact_frame()
    def edit(review):
        review['identity'].update(ista_type=kind, applied_edition=None, confirmed=False,
                                  scenario_id=None, scenario_kind=None)
        review['candidate']['intended_contact'].update(ista_type=kind, applied_edition=None)
    change_review(frame, edit)
    for field, value in [('IstaType', kind if kind != 'Unknown' else None), ('ScenarioId', None), ('ScenarioKind', None)]:
        frame[('Info', 'Artifact', field)] = value
    assert calculate_contact_comparison(frame).outcome == 'Match'


@pytest.mark.parametrize('failure', ['support', 'cut', 'failed_pose', 'nan_pose', 'face_change', 'time', 'no_impact', 'airborne', 'already_supported', 'registration', 'face_schema', 'resampled'])
def test_unavailable_physical_evidence_is_not_a_match(failure):
    frame = contact_frame()
    if failure == 'support':
        change_review(frame, lambda r: r['candidate'].update(motion='tip_or_rotation'))
    elif failure == 'cut':
        change_review(frame, lambda r: r['candidate'].update(left_censored=True))
    elif failure == 'failed_pose':
        frame.loc[10, ('Info', 'Pose', 'Source')] = 'Failed'
    elif failure == 'nan_pose':
        frame.loc[10, ('Position', 'CoM', 'P_RX')] = np.nan
    elif failure == 'face_change':
        frame.loc[11, ('Position', 'M1', 'FaceInfo')] = 'BACK'
    elif failure == 'time':
        frame[(*SUMMARY, 'FirstImpactTimeSec')] = .079
    elif failure == 'no_impact':
        frame[(*SUMMARY, 'ImpactDetected')] = False
    elif failure == 'airborne':
        frame.loc[[10,11], ('Position', 'CoM', 'P_TY')] += 100.
    elif failure == 'already_supported':
        frame.loc[9, ('Position', 'CoM', 'P_TY')] = 60.
    elif failure == 'registration':
        change_review(frame, lambda r: r['candidate']['intended_contact'].update(registration_sha256='f' * 64))
    elif failure == 'face_schema':
        update_processing(frame, lambda s: s['postprocess']['face_definitions']['BOTTOM'].update(corners=[0,1,2,3]))
    elif failure == 'resampled':
        update_processing(frame, lambda s: s['result_resampling'].update(enabled=True))
    result = calculate_contact_comparison(frame)
    assert result.outcome == 'Unclear' and result.reason


def test_contact_does_not_require_a_velocity_fit_window():
    frame = contact_frame().iloc[8:].copy()
    frame[('Info', 'Timeline', 'SliceStartSec')] = .064
    change_review(frame, lambda r: r['candidate'].update(start=.064, auto_start=.064))
    update_processing(frame, lambda s: s['single_pass']['marker_smoothing'].update(enabled=True))
    result = calculate_contact_comparison(frame)
    assert result.outcome == 'Match', result.reason


def test_legacy_tail_missingness_remains_unclear_until_bounded_policy_is_versioned():
    frame = contact_frame()
    assert calculate_contact_comparison(frame).outcome == 'Match'
    frame.loc[12, ('Position', 'C8', 'P_TY')] = np.nan
    result = calculate_contact_comparison(frame)
    assert result.outcome == 'Unclear'
    assert 'recorded contact policy' in result.reason


@pytest.mark.parametrize(('field', 'value'), [('T1Detected', False), ('ImpactDetected', False),
    ('ContactState', 'NoContact'), ('FirstImpactTimeSec', .079)])
def test_contact_comparison_uses_shared_event_exclusion(field, value):
    from src.analysis.compare.impact_metrics import calculate_impact_metrics
    frame = contact_frame()
    frame[(*SUMMARY, field)] = value
    comparison = calculate_contact_comparison(frame)
    diagnostic = calculate_impact_metrics(frame).metrics['first_contact']
    assert comparison.outcome == 'Unclear'
    assert diagnostic.value is None
    assert comparison.reason == diagnostic.reason


@pytest.mark.parametrize('failure', ['wrong_saved_feature', 'changes_after_one_frame', 'deep_penetration'])
def test_independent_review_rejects_inconsistent_contact_geometry(failure):
    frame = contact_frame()
    if failure == 'wrong_saved_feature':
        change_review(frame, lambda r: r['candidate']['intended_contact'].update(faces=['TOP']))
        frame[(*SUMMARY, 'FirstImpactContact')] = '{C3,C4,C7,C8}'
    elif failure == 'changes_after_one_frame':
        frame.loc[11, ('Position','CoM','P_RX')] = np.pi
        for i in range(1,9):
            frame.loc[11, ('Position',f'C{i}','P_TY')] = 120. - frame.loc[11, ('Position',f'C{i}','P_TY')]
    else:
        frame.loc[[10,11], ('Position','CoM','P_TY')] -= 100.
        for i in range(1,9):
            frame.loc[[10,11], ('Position',f'C{i}','P_TY')] -= 100.
    result = calculate_contact_comparison(frame)
    assert result.outcome == 'Unclear' and result.reason


def test_saved_reopened_values_and_statistical_exclusions(tmp_path):
    frames = [contact_frame(source=c * 64) for c in 'abc']
    frames[1] = contact_frame(source='b' * 64, observed='{C1,C5}', rotation=Rotation.from_euler('z',30,degrees=True))
    frames[2][(*SUMMARY, 'FirstImpactContact')] = '{C1,C6}'
    model = ComparisonModel()
    paths = []
    for i, frame in enumerate(frames):
        path = tmp_path / f'contact_{i}.proc'
        frame.to_csv(path, index=False)
        paths.append(path)
        model.load_file(str(path))
    result = model.get_contact_comparison()
    assert result['statistics'] == {'n':2, 'Match':1, 'Different':1, 'Unclear':1, 'excluded':0}
    before = paths[0].read_bytes()
    copied = model.load_file(str(paths[0]))
    assert model.get_contact_comparison()['statistics']['n'] == 2
    assert 'already counted' in ' '.join(model.get_contact_comparison()['files'][copied]['reasons'])
    assert paths[0].read_bytes() == before
    fresh = ComparisonModel()
    for path in paths:
        fresh.load_file(str(path))
    assert fresh.get_contact_comparison() == result
    different_intent = contact_frame(target=('TOP',), source='d' * 64)
    path = tmp_path / 'different_target.proc'
    different_intent.to_csv(path,index=False)
    name = model.load_file(str(path))
    assert 'Intended contact differs' in ' '.join(model.get_contact_comparison()['files'][name]['reasons'])
    conflicted = contact_frame(target=('TOP',), source='a' * 64)
    path = tmp_path / 'conflicting_choice.proc'
    conflicted.to_csv(path,index=False)
    model.load_file(str(path))
    result = model.get_contact_comparison()
    assert result['statistics']['n'] == 1
    assert 'Conflicting intended contacts' in ' '.join(result['files'][paths[0].name]['reasons'])


def test_mixed_source_cannot_enter_contact_statistics(tmp_path):
    model = ComparisonModel()
    for i, source in enumerate(['real', 'mujoco_synthetic', 'unknown_legacy']):
        frame = contact_frame(source=str(i) * 64)
        frame[('Info','Artifact','SourceKind')] = source
        path = tmp_path / f'source_{i}.proc'
        frame.to_csv(path,index=False)
        model.load_file(str(path))
    assert model.get_contact_comparison()['statistics']['n'] == 1
    assert model.get_contact_comparison()['statistics']['excluded'] == 2


def test_local_contact_counts_need_no_trial_identification(tmp_path):
    frame = contact_frame()
    def edit(review):
        review['identity'].update(ista_type='Unknown', applied_edition=None, confirmed=False,
                                  scenario_id=None, scenario_kind=None)
        review['candidate']['intended_contact'].update(ista_type='Unknown', applied_edition=None)
    change_review(frame, edit)
    for field in ('IstaType', 'ScenarioId', 'ScenarioKind'):
        frame[('Info', 'Artifact', field)] = None
    path = tmp_path / 'local_only.proc'
    frame.to_csv(path,index=False)
    model = ComparisonModel()
    name = model.load_file(str(path))
    assert model.get_contact_comparison()['statistics']['n'] == 1
    # Other metrics retain their original trial-comparison compatibility gate.
    assert model.get_impact_comparison()['files'][name]['reasons']
