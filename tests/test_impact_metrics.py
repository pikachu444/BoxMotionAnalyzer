"""Analytical and serialized-contract checks, not measured ISTA validation."""
import json
import math

import numpy as np
import pandas as pd
import pytest
from scipy.spatial.transform import Rotation

from impact_metric_fixtures import REVIEW, SUMMARY, make_frame, update_processing, write_proc
from src.analysis.compare.impact_metrics import METRICS, calculate_impact_metrics
from src.analysis.pipeline.data_loader import DataLoader


NUMERIC = ('vertical_velocity', 'horizontal_speed', 'angular_speed', 'equivalent_height')
HEIGHT = 815.7729703823426


def _edit_review(frame, edit):
    data = json.loads(frame[REVIEW].iloc[0])
    edit(data)
    frame[REVIEW] = json.dumps(data, sort_keys=True, separators=(',', ':'))


def _expected(result):
    for key, value in zip(NUMERIC, (-4., 3., 2., HEIGHT)):
        assert result.metrics[key].value == pytest.approx(value, rel=0, abs=1e-9)
        assert result.metrics[key].reason == ''


def test_analytical_world_velocities_and_explicit_com_height_without_input_mutation():
    frame = make_frame(base_rotvec=(.3, .2, .1))
    before = frame.copy(deep=True)
    result = calculate_impact_metrics(frame)
    _expected(result)
    pd.testing.assert_frame_equal(frame, before)
    assert result.evidence['angular_velocity_world_rad_s'] == pytest.approx([0., 0., 2.], abs=1e-10)
    assert result.evidence['evaluation_time_s'] == .040
    assert result.evidence['window_start_s'] == 0.
    assert result.evidence['window_end_s'] == .040
    assert result.evidence['sample_count'] == 6
    assert result.metrics['first_contact'].value == '{C1,C2}'
    assert result.metrics['final_face'].value is None
    assert result.metrics['contact_confidence'].value == .75
    assert METRICS['first_contact']['kind'] == 'categorical'
    assert METRICS['contact_confidence']['role'] == 'diagnostic'


def test_serialized_public_contract_reopens_with_the_same_physical_values(tmp_path):
    path = write_proc(tmp_path / 'analytic.proc')
    frame = DataLoader().load_result_csv(str(path))
    result = calculate_impact_metrics(frame)
    _expected(result)
    assert result.observation_key == ('a' * 64, 0., .056, 'G01')


def test_postcontact_rebound_and_saved_velocity_cannot_change_one_sided_estimate():
    frame = make_frame()
    original = calculate_impact_metrics(frame)
    after = frame[('Info', 'Time', 'Time')] > .040
    for axis in 'XYZ':
        frame.loc[after, ('Position', 'CoM', 'P_T' + axis)] = 1e6
        frame.loc[after, ('Position', 'CoM', 'P_R' + axis)] = np.nan
        frame[('Velocity', 'CoM', 'Global_V_T' + axis)] = -1e20
    frame.loc[after, ('Info', 'Pose', 'Source')] = 'OptimizationFailed'
    changed = calculate_impact_metrics(frame)
    for key in NUMERIC:
        assert changed.metrics[key] == original.metrics[key]
    assert changed.evidence == original.evidence


def test_offset_com_rotates_while_geometric_centre_has_zero_velocity():
    frame = make_frame(velocity=(0., 0., 0.), omega=(0., 0., 0.), com_offset=(100., 0., 0.))
    times = frame[('Info', 'Time', 'Time')].to_numpy()
    # COM y = 100*sin(-asin(2*(t-t*))) = -200*(t-t*) mm exactly.
    frame[('Position', 'CoM', 'P_RZ')] = -np.arcsin(2 * (times - .040))
    result = calculate_impact_metrics(frame)
    assert result.metrics['vertical_velocity'].value == 0.
    assert result.metrics['horizontal_speed'].value == 0.
    assert result.evidence['com_vertical_velocity_m_s'] == pytest.approx(-.2, abs=1e-12)
    assert result.metrics['equivalent_height'].value == pytest.approx(2.0394324259558565, abs=1e-10)


def test_irregular_actual_samples_and_rotvec_branch_crossing_are_supported():
    frame = make_frame(times=[0., .003, .011, .020, .033, .040, .048, .056], base_rotvec=(0., 0., 3.12))
    _expected(calculate_impact_metrics(frame))


@pytest.mark.parametrize('component, missing', [('P_TX', {'horizontal_speed'}),
    ('P_TY', {'vertical_velocity', 'equivalent_height'}), ('P_RZ', {'angular_speed'})])
def test_missing_pose_component_only_blocks_its_dependent_metrics(component, missing):
    frame = make_frame()
    frame.loc[2, ('Position', 'CoM', component)] = np.nan
    result = calculate_impact_metrics(frame)
    for key, expected in zip(NUMERIC, (-4., 3., 2., HEIGHT)):
        if key in missing:
            assert result.metrics[key].value is None
            assert result.metrics[key].reason
        else:
            assert result.metrics[key].value == pytest.approx(expected, abs=1e-9)


def test_nonzero_com_requires_rotation_even_when_geometric_vertical_is_valid():
    frame = make_frame(com_offset=(100., 0., 0.))
    frame.loc[2, ('Position', 'CoM', 'P_RX')] = np.nan
    result = calculate_impact_metrics(frame)
    assert result.metrics['vertical_velocity'].value == pytest.approx(-4.)
    assert result.metrics['equivalent_height'].value is None


def test_ambiguous_large_rotation_blocks_angular_but_zero_com_height_stays_available():
    frame = make_frame(omega=(0., 0., 50.))
    result = calculate_impact_metrics(frame)
    assert result.metrics['angular_speed'].value is None
    assert 'ambiguous' in result.metrics['angular_speed'].reason
    assert result.metrics['equivalent_height'].value == pytest.approx(HEIGHT, abs=1e-9)


@pytest.mark.parametrize('fault', ['gap', 'short_span', 'failed_pose', 'face_change', 'missing_faces',
    'no_t1', 'off_sample_t1', 'wrong_impact', 'no_impact', 'tracking_jump'])
def test_missing_precontact_support_is_not_replaced_with_an_earlier_sample(fault):
    if fault == 'gap':
        frame = make_frame(times=[0., .004, .028, .032, .036, .040, .048, .056])
    elif fault == 'short_span':
        frame = make_frame(times=[0., .004, .008, .012, .016, .024], t1=.016, impact=.024)
    else:
        frame = make_frame()
        if fault == 'failed_pose':
            frame.loc[4, ('Info', 'Pose', 'Source')] = 'OptimizationFailed'
        elif fault == 'face_change':
            frame.loc[3:, ('Position', 'M1', 'FaceInfo')] = 'BACK'
        elif fault == 'missing_faces':
            frame = frame.drop(columns=[('Position', 'M1', 'FaceInfo')])
        elif fault == 'no_t1':
            frame[(*SUMMARY, 'T1Detected')] = False
        elif fault == 'off_sample_t1':
            frame[(*SUMMARY, 'T1MinusTimeSec')] = .039
        elif fault == 'wrong_impact':
            frame[(*SUMMARY, 'FirstImpactTimeSec')] = .056
        elif fault == 'no_impact':
            frame[(*SUMMARY, 'ContactState')] = 'NoContact'
        elif fault == 'tracking_jump':
            _edit_review(frame, lambda r: r['candidate'].update(evidence_class='tracking_jump', motion='tracking_jump'))
    result = calculate_impact_metrics(frame)
    assert all(result.metrics[key].value is None and result.metrics[key].reason for key in NUMERIC)


@pytest.mark.parametrize('fault', ['smoothing', 'resampling', 'floor', 'axis', 'geometry',
    'missing_record', 'reviewed_range', 'outside_review', 'stale_review', 'bad_source_hash'])
def test_processing_and_review_context_must_match_the_observed_pose(fault):
    frame = make_frame()
    if fault == 'smoothing':
        update_processing(frame, lambda s: s['single_pass']['marker_smoothing'].update(enabled=True))
    elif fault == 'resampling':
        update_processing(frame, lambda s: s['result_resampling'].update(enabled=True))
    elif fault == 'floor':
        frame = make_frame(registration_floor_y_mm=2.)
    elif fault == 'axis':
        update_processing(frame, lambda s: s['postprocess'].update(vertical_axis=2))
    elif fault == 'geometry':
        update_processing(frame, lambda s: s['postprocess']['geometry_mm'][0].__setitem__(0, -101.))
    elif fault == 'missing_record':
        frame = frame.drop(columns=[('Info', 'Artifact', 'ProcessingSettingsJson')])
    elif fault in ('reviewed_range', 'outside_review'):
        _edit_review(frame, lambda r: r['candidate'].update(start=.008))
        if fault == 'outside_review':
            frame[('Info', 'Timeline', 'SliceStartSec')] = .008
    elif fault == 'stale_review':
        _edit_review(frame, lambda r: r['candidate'].update(evidence_status='range_changed'))
    else:
        _edit_review(frame, lambda r: r.update(source_sha256='z' * 64))
    result = calculate_impact_metrics(frame)
    assert all(result.metrics[key].value is None and result.metrics[key].reason for key in NUMERIC)


@pytest.mark.parametrize('options', [dict(ista_type='H', scenario_id='H/B04/D06'),
    dict(ista_type='Unknown', confirmed=False), dict(confirmed=False), dict(review=False),
    dict(com_offset=None), dict(velocity=(3., 4., 0.)), dict(velocity=(3., 0., 0.))])
def test_velocity_equivalent_height_is_only_for_supported_downward_registered_g(options):
    frame = make_frame(**options)
    result = calculate_impact_metrics(frame)
    assert result.metrics['equivalent_height'].value is None
    assert result.metrics['equivalent_height'].reason
    assert result.metrics['vertical_velocity'].value is not None
    assert result.metrics['horizontal_speed'].value == pytest.approx(3.)
    assert result.metrics['angular_speed'].value == pytest.approx(2.)


def test_non_free_fall_g_scene_does_not_receive_an_equivalent_height():
    frame = make_frame()
    _edit_review(frame, lambda r: r['candidate'].update(evidence_class='tip_or_rotation', motion='tip_or_rotation'))
    result = calculate_impact_metrics(frame)
    assert result.metrics['vertical_velocity'].value == pytest.approx(-4.)
    assert result.metrics['equivalent_height'].value is None


def test_unconfirmed_review_still_identifies_copied_observations():
    result = calculate_impact_metrics(make_frame(ista_type='H', confirmed=False))
    assert result.observation_key == ('a' * 64, 0., .056, None)
    assert result.metrics['vertical_velocity'].value == pytest.approx(-4.)


def test_diagnostic_categories_and_confidence_do_not_become_experimental_values():
    frame = make_frame()
    frame[(*SUMMARY, 'FinalFace')] = 'BOTTOM'
    assert calculate_impact_metrics(frame).metrics['final_face'].value == 'BOTTOM'
    frame[(*SUMMARY, 'FinalFace')] = '3'
    frame[(*SUMMARY, 'FirstImpactContact')] = '{C1,C9}'
    frame[(*SUMMARY, 'ContactConfidence')] = 1.1
    result = calculate_impact_metrics(frame)
    assert all(result.metrics[key].value is None for key in ('final_face', 'first_contact', 'contact_confidence'))
    _expected(result)


@pytest.mark.parametrize('bad', [np.nan, np.inf, -np.inf])
def test_nonfinite_vertical_pose_never_produces_a_height(bad):
    frame = make_frame()
    frame.loc[2, ('Position', 'CoM', 'P_TY')] = bad
    result = calculate_impact_metrics(frame)
    assert result.metrics['vertical_velocity'].value is None
    assert result.metrics['equivalent_height'].value is None
    assert result.metrics['horizontal_speed'].value == pytest.approx(3.)


def test_original_and_corrected_copy_have_one_original_capture_identity(tmp_path):
    raw = make_frame()
    corrected = make_frame(source_sha256='c' * 64)
    corrected[('Info', 'MarkerCorrection', 'OriginalSourceSha256')] = '  ' + 'A' * 64 + '  '
    path = tmp_path / 'corrected.proc'
    corrected.to_csv(path, index=False)
    restored = DataLoader().load_result_csv(str(path))
    raw_result = calculate_impact_metrics(raw)
    corrected_result = calculate_impact_metrics(restored)
    assert raw_result.observation_key == corrected_result.observation_key == ('a' * 64, 0., .056, 'G01')
    _expected(corrected_result)


@pytest.mark.parametrize('fault', ['smoothing', 'resampling', 'registration', 'settings'])
def test_diagnostic_observation_identity_survives_unsupported_pose_estimation(fault):
    frame = make_frame(marker_smoothing=fault == 'smoothing', result_resampling=fault == 'resampling',
                       registration_floor_y_mm=2. if fault == 'registration' else 0.)
    if fault == 'settings':
        frame[('Info', 'Artifact', 'ProcessingSettingsJson')] = '{invalid'
    result = calculate_impact_metrics(frame)
    assert result.observation_key == ('a' * 64, 0., .056, 'G01')
    # #118: identity survives, but unproven original samples or execution
    # provenance no longer qualify as supported recorded event diagnostics.
    if fault in ('resampling', 'settings'):
        assert result.metrics['first_contact'].value is None
        assert result.metrics['contact_confidence'].value is None
        assert result.metrics['first_contact'].reason
    else:
        assert result.metrics['first_contact'].value == '{C1,C2}'
        assert result.metrics['contact_confidence'].value == .75
    assert all(result.metrics[key].value is None for key in NUMERIC)


@pytest.mark.parametrize('field', ['identity', 'candidate', 'detection'])
def test_malformed_optional_scene_context_returns_unavailable_metrics_not_an_exception(field):
    frame = make_frame()
    _edit_review(frame, lambda r: r.update({field: None}))
    result = calculate_impact_metrics(frame)
    assert all(result.metrics[key].value is None and result.metrics[key].reason for key in NUMERIC)
    assert result.metrics['first_contact'].value is None
    assert result.metrics['contact_confidence'].value is None
    assert result.metrics['first_contact'].reason
    assert (result.observation_key is not None) == (field == 'detection')


def test_invalid_original_capture_identity_cannot_fall_back_to_the_corrected_hash():
    frame = make_frame(source_sha256='c' * 64)
    frame[('Info', 'MarkerCorrection', 'OriginalSourceSha256')] = 'not-a-hash'
    result = calculate_impact_metrics(frame)
    assert result.observation_key is None
    assert 'Original capture source' in result.metrics['vertical_velocity'].reason


@pytest.mark.parametrize('axis, blocked', [('X', {'horizontal_speed'}),
    ('Y', {'vertical_velocity', 'equivalent_height'})])
def test_large_single_position_error_is_not_reported_as_valid_speed(axis, blocked):
    frame = make_frame()
    frame.loc[4, ('Position', 'CoM', 'P_T' + axis)] += 1000.
    result = calculate_impact_metrics(frame)
    assert result.evidence['fit_residuals']['position_' + axis + '_mm'] > 300.
    for key, expected in zip(NUMERIC, (-4., 3., 2., HEIGHT)):
        if key in blocked:
            assert result.metrics[key].value is None
            assert 'support' in result.metrics[key].reason
        else:
            assert result.metrics[key].value == pytest.approx(expected, abs=1e-9)


def test_rotation_fit_residual_has_its_own_software_support_limit():
    frame = make_frame()
    frame.loc[4, ('Position', 'CoM', 'P_RZ')] += .1
    result = calculate_impact_metrics(frame)
    assert result.evidence['observed_endpoint_rotation_max_rad'] < .25
    assert result.evidence['fit_residuals']['rotation_rms_rad'] > .01
    assert result.metrics['angular_speed'].value is None
    assert result.metrics['vertical_velocity'].value == pytest.approx(-4.)
    assert result.metrics['equivalent_height'].value == pytest.approx(HEIGHT, abs=1e-9)


@pytest.mark.parametrize('times', [None, [0., .003, .011, .020, .033, .040, .048, .056]])
def test_variable_world_axis_rotation_has_bounded_local_fit_bias(times):
    frame = make_frame(times=times)
    time = frame[('Info', 'Time', 'Time')].to_numpy()
    rate = 4.4
    matrices = (Rotation.from_rotvec(np.column_stack((time * 0, time * 0, time * rate)))
                * Rotation.from_rotvec(np.column_stack((time * rate, time * 0, time * 0)))).as_rotvec()
    for i, axis in enumerate('XYZ'):
        frame[('Position', 'CoM', 'P_R' + axis)] = matrices[:, i]
    result = calculate_impact_metrics(frame)
    # For Rz(a*t)Rx(b*t), world omega=(b*cos(a*t),b*sin(a*t),a).
    # The quadratic log fit has truncation bias; this synthetic support case
    # permits 0.2%, independently bounded by the two analytical trajectories.
    assert result.evidence['observed_endpoint_rotation_max_rad'] < .25
    assert result.metrics['angular_speed'].value == pytest.approx(math.sqrt(2 * rate**2), rel=.002)


def test_large_variable_axis_rotation_is_outside_the_supported_fit_range():
    frame = make_frame(com_offset=(100., 0., 0.))
    time = frame[('Info', 'Time', 'Time')].to_numpy()
    matrices = (Rotation.from_rotvec(np.column_stack((time * 0, time * 0, time * 25)))
                * Rotation.from_rotvec(np.column_stack((time * 25, time * 0, time * 0)))).as_rotvec()
    for i, axis in enumerate('XYZ'):
        frame[('Position', 'CoM', 'P_R' + axis)] = matrices[:, i]
    result = calculate_impact_metrics(frame)
    assert result.metrics['angular_speed'].value is None
    assert result.metrics['equivalent_height'].value is None
    assert result.metrics['vertical_velocity'].value == pytest.approx(-4.)


@pytest.mark.parametrize(('field', 'value', 'reason'), [
    ('T1Detected', False, 'T1Detected'), ('T1Detected', 'invalid', 'invalid boolean'),
    ('ImpactDetected', False, 'ImpactDetected'), ('ImpactDetected', 'invalid', 'invalid boolean'),
    ('ContactState', 'NoContact', 'conflicts'), ('ContactState', 'SustainedContact', 'conflicts'),
    ('ContactState', 'Approach', 'conflicts'), ('ContactState', 'unknown', 'unknown state'),
    ('FirstImpactTimeSec', np.nan, 'finite time'), ('FirstImpactTimeSec', np.inf, 'finite time'),
    ('FirstImpactTimeSec', .049, 'actual timeline sample'), ('FirstImpactTimeSec', 100., 'actual timeline sample'),
    ('FirstImpactTimeSec', .056, 'following event sample'),
    ('T1MinusTimeSec', .039, 'immediately before'), ('T1MinusTimeSec', True, 'finite time'),
])
def test_stale_contact_is_excluded_for_each_event_contradiction(field, value, reason):
    frame = make_frame()
    frame[(*SUMMARY, field)] = value
    before = frame.copy(deep=True)
    result = calculate_impact_metrics(frame)
    for key in ('first_contact', 'contact_confidence'):
        assert result.metrics[key].value is None
        assert reason in result.metrics[key].reason
    pd.testing.assert_frame_equal(frame, before)


@pytest.mark.parametrize('field', ['T1Detected', 'ImpactDetected', 'ContactState',
                                  'T1MinusTimeSec', 'FirstImpactTimeSec'])
@pytest.mark.parametrize('fault', ['missing', 'duplicate', 'row_conflict'])
def test_event_columns_are_single_constants(field, fault):
    frame = make_frame()
    column = (*SUMMARY, field)
    if fault == 'missing':
        frame = frame.drop(columns=[column])
    elif fault == 'duplicate':
        frame = pd.concat([frame, frame[[column]]], axis=1)
    else:
        frame[column] = frame[column].astype(object)
        frame.loc[2, column] = 'different row'
    result = calculate_impact_metrics(frame)
    assert result.metrics['first_contact'].value is None
    assert result.metrics['contact_confidence'].value is None
    assert field in result.metrics['first_contact'].reason


@pytest.mark.parametrize('fault', ['duplicate', 'decreasing', 'nan', 'conflicting_column'])
def test_event_requires_unambiguous_actual_timeline(fault):
    frame = make_frame()
    column = ('Info', 'Time', 'Time')
    if fault == 'conflicting_column':
        extra = frame[[column]].copy()
        extra[column] += .001
        frame = pd.concat([frame, extra], axis=1)
    else:
        frame.loc[6, column] = {'duplicate': .040, 'decreasing': .039, 'nan': np.nan}[fault]
    result = calculate_impact_metrics(frame)
    assert result.metrics['first_contact'].value is None
    assert 'Time unavailable' in result.metrics['first_contact'].reason


@pytest.mark.parametrize('state', ['NoContact', 'Approach', 'SustainedContact'])
def test_no_impact_state_is_not_a_first_contact_or_zero_confidence_observation(state):
    frame = make_frame()
    for name in ('T1Detected', 'ImpactDetected'):
        frame[(*SUMMARY, name)] = False
    for name in ('T1MinusTimeSec', 'FirstImpactTimeSec', 'FirstImpactContact'):
        frame[(*SUMMARY, name)] = np.nan
    frame[(*SUMMARY, 'ContactState')] = state
    frame[(*SUMMARY, 'ContactConfidence')] = 0. if state == 'NoContact' else .2
    frame[(*SUMMARY, 'FinalFace')] = 'BOTTOM'
    result = calculate_impact_metrics(frame)
    assert result.evidence['first_event']['status'] == 'no-impact'
    assert result.metrics['first_contact'].value is None
    assert result.metrics['contact_confidence'].value is None
    assert result.metrics['final_face'].value == 'BOTTOM'
    assert 'No impact declared' in result.metrics['first_contact'].reason


def test_minimal_recorded_event_survives_absent_pose_and_velocity_fit_support():
    frame = make_frame(times=[.040, .048, .056], marker_smoothing=True)
    frame = frame.drop(columns=[c for c in frame.columns if c[:2] == ('Position', 'CoM')])
    result = calculate_impact_metrics(frame)
    assert all(result.metrics[key].value is None for key in NUMERIC)
    assert result.metrics['first_contact'].value == '{C1,C2}'
    assert result.metrics['contact_confidence'].value == .75
    event = result.evidence['first_event']
    assert event['times_s'] == (.040, .048, .056)
    assert event['indices'] == (0, 1, 2)
    assert event['status'] == 'recorded-consistent'
    assert event['contract_version'] == 'recorded-first-event-consistency-v1'
    assert event['contact_policy'] == 'drop-posture-evidence-v1'
    assert event['geometry_verified'] is False


@pytest.mark.parametrize('gap_index', [2, 6, 7])
def test_recorded_gap_policy_rejects_earlier_or_bracketing_gaps(gap_index):
    times = np.arange(8) * .008
    times[gap_index:] += .1
    frame = make_frame(times=times, t1=times[5], impact=times[6])
    _edit_review(frame, lambda r: r['detection']['settings'].update(gap_factor=3.5))
    result = calculate_impact_metrics(frame)
    assert result.metrics['first_contact'].value is None
    assert 'tracking gap' in result.metrics['first_contact'].reason


@pytest.mark.parametrize('fault', ['legacy_source', 'missing_provenance', 'unknown_policy', 'right_bracket', 'left_censored', 'tracking_jump'])
def test_unsupported_event_provenance_and_review_are_explicit(fault):
    frame = make_frame()
    if fault == 'legacy_source':
        frame[('Info', 'Artifact', 'SourceKind')] = 'unknown_legacy'
    elif fault == 'missing_provenance':
        frame = frame.drop(columns=[('Info', 'Artifact', 'ProcessingSettingsJson')])
    elif fault == 'unknown_policy':
        update_processing(frame, lambda s: s['postprocess'].update(contact_policy='future-policy'))
    elif fault == 'left_censored':
        _edit_review(frame, lambda r: r['candidate'].update(left_censored=True))
    elif fault == 'tracking_jump':
        _edit_review(frame, lambda r: r['candidate'].update(motion='tracking_jump', evidence_class='tracking_jump'))
    else:
        _edit_review(frame, lambda r: r['candidate'].update(end=.048))
    result = calculate_impact_metrics(frame)
    assert result.metrics['first_contact'].value is None
    assert result.metrics['contact_confidence'].value is None
    assert result.metrics['first_contact'].reason


def test_no_contact_with_nonzero_score_is_a_contradiction_not_valid_no_contact():
    frame = make_frame()
    for field in ('T1Detected', 'ImpactDetected'):
        frame[(*SUMMARY, field)] = False
    for field in ('T1MinusTimeSec', 'FirstImpactTimeSec', 'FirstImpactContact'):
        frame[(*SUMMARY, field)] = np.nan
    frame[(*SUMMARY, 'ContactState')] = 'NoContact'
    result = calculate_impact_metrics(frame)
    assert result.evidence['first_event']['status'] == 'unavailable'
    assert 'zero score' in result.metrics['contact_confidence'].reason
