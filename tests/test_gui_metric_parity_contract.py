"""Independent analytic contracts for P01, not experimental qualification."""
from copy import deepcopy
import json
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest
from scipy.spatial.transform import Rotation

from impact_metric_fixtures import REVIEW, SUMMARY, update_processing
from test_contact_comparison import contact_frame
from test_posture_comparison import posture_frame
from src.analysis.compare.contact_metrics import calculate_contact_comparison
from src.analysis.compare.impact_metrics import calculate_impact_metrics
from src.analysis.compare.posture_metrics import lowest_corners
from src.analysis.compare.summary_metrics import (
    calculate_geometric_height,
    calculate_target_posture_error,
    resolve_summary_metrics,
)
from src.analysis.pipeline.contact_reducers import contact_sweep, final_face
from src.analysis.pipeline.drop_posture_post_processor import DropPosturePostProcessor
from src.analysis.pipeline.resampler import UniformResampler
from src.analysis.pipeline.scene_detection import Registration
from src.analysis.pipeline.scene_review import SceneReviewSession
from src.analysis.pipeline.velocity_calculator import VelocityCalculator
from src.config.config_app import FACE_DEFINITIONS
from src.config.data_columns import DropPostureCols, DropPostureSummaryCols, PoseCols, SourceCols, VelocityCols


REQUIRED_KEYS = {
    'BetaAtT1MinusDeg', 'ThetaLongAtT1MinusDeg', 'ThetaShortAtT1MinusDeg',
    'CminAtT1MinusIndex', 'DeltaHAtT1Minus_mm', 'TargetPostureError_deg',
    'CminMargin_mm', 'MaxDeltaH_mm', 'ReferenceFace', 'FinalFace',
    'T1MinusTimeSec', 'T1Detected', 'FirstImpactTimeSec', 'FirstImpactContact',
    'ImpactSequence', 'ImpactEventCount', 'VerticalVelAtT1Minus_mm_s',
    'PeakDescentSpeed_mm_s', 'VxyAtT1Minus_mm_s',
    'AngularSpeedAtT1Minus_rad_s', 'EquivalentFreeFallHeight_mm',
    'RotationDirection', 'TotalSweepAngle_deg', 'SweepConsistency',
    'ContactState', 'ImpactDetected', 'SustainedContactDetected',
    'ContactConfidence', 'ContactDetectionMethod', 'IntendedContactMatch',
}
LOCAL = np.array([
    [-100., -60., -40.], [100., -60., -40.], [100., 60., -40.], [-100., 60., -40.],
    [-100., -60., 40.], [100., -60., 40.], [100., 60., 40.], [-100., 60., 40.],
])
HEIGHT_CONTEXT = dict(user_approved=True, category='Type G', is_free_fall=True, kind='free-fall')


def unavailable(metric):
    assert metric.value is None
    assert metric.reason


def change_review(frame, edit):
    review = json.loads(frame[REVIEW].iloc[0])
    edit(review)
    frame[REVIEW] = json.dumps(review)


def metric_frame(*, target=('BOTTOM',), rotation=None):
    """Reuse the complete public registered fixture, record intent through its setter."""
    frame = contact_frame(target=None, rotation=rotation)
    review = json.loads(frame[REVIEW].iloc[0])
    review['candidate'].update(left_censored=False, right_censored=False)
    if target is not None:
        registration = Registration(**review['detection']['registration'])
        session = SceneReviewSession(SimpleNamespace(candidates=[], registration=registration), review['source_sha256'])
        session.ista_type, session.applied_edition = 'G', '2018-03'
        row = deepcopy(review['candidate'])
        row['identity'] = deepcopy(review['identity'])
        session.rows = [row]
        record = session.set_intended_contact(row['id'], list(target))
        assert record['registration_sha256'] == registration.fingerprint
        review['candidate']['intended_contact'] = record
    frame[REVIEW] = json.dumps(review)
    for axis, value in zip('XYZ', (300., -400., 0.)):
        frame[('Velocity', 'CoM', 'Global_V_T' + axis)] = value
    frame[('Velocity', 'CoM', 'Global_V_R_Norm')] = 2.
    update_processing(frame, lambda s: s['single_pass']['derivatives'].update(
        velocity_method='finite_difference', acceleration_method='finite_difference',
        time_policy='actual-dt;finite-difference-numpy-gradient;finite-angle-matrix',
        segmentation_policy='face-boundaries-and-finite-contiguous-pose-v3',
        pose_lowpass={'enabled': False}, pose_moving_average={'enabled': False},
        velocity_lowpass={'enabled': False}, acceleration_lowpass={'enabled': False}))
    return frame


def target_context(frame, vector=(0., -1., 0.)):
    review = json.loads(frame[REVIEW].iloc[0])
    return dict(version=1, basis='operator', user_approved=True, phase='t1_minus',
                frame='registered_box_local', target_down_local=list(vector),
                registration_sha256=review['detection']['registration_sha256'],
                ista_type=review['identity']['ista_type'],
                applied_edition=review['identity']['applied_edition'])


@pytest.mark.parametrize('quadratic', [False, True])
def test_a01_a02_recorded_derivatives_have_analytic_interior_units(quadratic):
    times = np.array([0., .1, .2, .3, .4])
    x = 10. + 200. * times + (500. * times**2 if quadratic else 0.)
    frame = pd.DataFrame({PoseCols.POS_X: x, PoseCols.POS_Y: 0., PoseCols.POS_Z: 0.,
                          PoseCols.ROT_X: 0., PoseCols.ROT_Y: 0., PoseCols.ROT_Z: 0.,
                          SourceCols.POSE: 'Optimized'}, index=times)
    calculator = VelocityCalculator()
    calculator.configure(dict(velocity_method='finite_difference', acceleration_method='finite_difference',
        use_pose_lowpass_filter=False, use_pose_moving_average=False,
        use_velocity_lowpass_filter=False, use_acceleration_lowpass_filter=False))
    result = calculator.process(frame)
    assert result.loc[.2, PoseCols.POS_X] == pytest.approx(70. if quadratic else 50., abs=1e-9, rel=1e-9)
    assert result.loc[.2, VelocityCols.T_VX] == pytest.approx(400. if quadratic else 200., abs=1e-9, rel=1e-9)
    assert result.loc[.2, VelocityCols.T_AX] == pytest.approx(1000. if quadratic else 0., abs=1e-9, rel=1e-9)


def test_a01r_interpolation_only_when_explicitly_enabled():
    frame = pd.DataFrame({'x': [10., 30., 50., 70., 90.]}, index=[0., .1, .2, .3, .4])
    assert .15 not in UniformResampler(factor=1).process(frame).index
    interpolated = UniformResampler(factor=2).process(frame)
    index = int(np.argmin(abs(interpolated.index.to_numpy() - .15)))
    assert interpolated.iloc[index]['x'] == pytest.approx(40., abs=1e-9, rel=1e-9)


def test_a04_precontact_sample_is_not_whole_window_peak():
    processor = DropPosturePostProcessor(face_definitions=FACE_DEFINITIONS, local_box_corners=LOCAL)
    metrics = pd.DataFrame({DropPostureCols.BETA_DEG: 0., DropPostureCols.THETA_LONG_DEG: 0.,
        DropPostureCols.THETA_SHORT_DEG: 0., DropPostureCols.CMIN_INDEX: 1.,
        DropPostureCols.DELTA_H_MM: [0., 50., 20., 10.]}, index=[0., .1, .2, .3])
    result = processor._summary_data(metrics=metrics, t1_minus_pos=2, t1_detected=True,
        reference_face_label='BOTTOM', long_axis_idx=0, short_axis_idx=2, impact_summary={},
        contact_analysis=dict(contact_state='ImpactEvent', contact_confidence=.35,
            contact_detection_method='threshold', impact_detected=True, sustained_contact_detected=False))
    assert result[DropPostureSummaryCols.DELTA_H_AT_T1_MINUS_MM] == 20.
    assert result[DropPostureSummaryCols.MAX_DELTA_H_MM] == 50.
    assert result[DropPostureSummaryCols.T1_MINUS_TIME_SEC] == .2


def test_required_thirty_are_subset_and_resolution_never_mutates_input():
    frame = metric_frame()
    original = frame.copy(deep=True)
    result = resolve_summary_metrics(frame)
    assert REQUIRED_KEYS <= result.keys()
    pd.testing.assert_frame_equal(frame, original)


def test_existing_posture_owner_values_are_exposed_under_base_keys():
    result = resolve_summary_metrics(posture_frame(-30.))
    for key, expected in [('BetaAtT1MinusDeg', 30.), ('ThetaLongAtT1MinusDeg', -30.),
                          ('ThetaShortAtT1MinusDeg', 0.), ('DeltaHAtT1Minus_mm', 100.),
                          ('MaxDeltaH_mm', 100.), ('CminMargin_mm', 0.)]:
        assert result[key].value == pytest.approx(expected, abs=1e-9, rel=1e-9), result[key].reason
    assert result['CminAtT1MinusIndex'].value == 'Non-unique {C2,C6}'
    assert result['ReferenceFace'].value == 'BOTTOM'


def test_snapshot_reads_saved_components_and_preserves_fit_quantities():
    frame = metric_frame()
    result = resolve_summary_metrics(frame)
    assert result['VerticalVelAtT1Minus_mm_s'].value == -400.
    assert result['VxyAtT1Minus_mm_s'].value == 300.
    assert result['AngularSpeedAtT1Minus_rad_s'].value == 2.
    assert result['PeakDescentSpeed_mm_s'].value == 400.
    fitted = calculate_impact_metrics(frame)
    # Y(t)=constant - 4903.325*t^2 before contact, evaluated at t=.072.
    assert fitted.metrics['vertical_velocity'].value == pytest.approx(-.7060788, rel=1e-9, abs=1e-9)
    assert fitted.metrics['horizontal_speed'].value == pytest.approx(0., rel=1e-9, abs=1e-9)


def test_snapshot_preserves_pose_corner_consistency_gate():
    frame = metric_frame()
    frame.loc[9, ('Position', 'C1', 'P_TY')] += 10.
    result = resolve_summary_metrics(frame)
    unavailable(result['VerticalVelAtT1Minus_mm_s'])
    unavailable(result['EquivalentFreeFallHeight_mm'])


def test_missing_legacy_derivative_provenance_is_reasoned_unavailable():
    frame = metric_frame()
    update_processing(frame, lambda s: s['single_pass']['derivatives'].pop('velocity_method'))
    unavailable(resolve_summary_metrics(frame)['VerticalVelAtT1Minus_mm_s'])


def test_snapshot_time_and_window_use_saved_seconds_not_dataframe_rows():
    frame = metric_frame()
    shift = 100.
    frame[('Info', 'Time', 'Time')] += shift
    for column in (('Info', 'Timeline', 'SliceStartSec'), ('Info', 'Timeline', 'SliceEndSec'),
                   (*SUMMARY, 'T1MinusTimeSec'), (*SUMMARY, 'FirstImpactTimeSec')):
        frame[column] += shift
    change_review(frame, lambda r: r['candidate'].update(
        start=r['candidate']['start'] + shift, end=r['candidate']['end'] + shift,
        auto_start=r['candidate']['auto_start'] + shift, auto_end=r['candidate']['auto_end'] + shift))
    result = resolve_summary_metrics(frame)
    assert result['VerticalVelAtT1Minus_mm_s'].sample_time == pytest.approx(100.072, abs=1e-12)
    assert result['PeakDescentSpeed_mm_s'].window == pytest.approx((100., 100.072), abs=1e-12)


@pytest.mark.parametrize('field,value', [('FirstImpactContact', 'bogus'), ('ContactConfidence', 5.), ('ReferenceFace', 'TOP')])
def test_saved_summary_alias_cannot_bypass_owner_validation(field, value):
    frame = metric_frame()
    # Supply an independently known identity-pose reference before corrupting it.
    for key, known in [('ReferenceFace', 'BOTTOM'), ('LongAxis', 'LocalAxis0'), ('ShortAxis', 'LocalAxis2')]:
        frame[(*SUMMARY, key)] = known
    frame[(*SUMMARY, field)] = value
    unavailable(resolve_summary_metrics(frame)[field])


@pytest.mark.parametrize('component,key,unrelated', [
    ('Global_V_TX', 'VxyAtT1Minus_mm_s', 'VerticalVelAtT1Minus_mm_s'),
    ('Global_V_TY', 'VerticalVelAtT1Minus_mm_s', 'VxyAtT1Minus_mm_s'),
    ('Global_V_R_Norm', 'AngularSpeedAtT1Minus_rad_s', 'VerticalVelAtT1Minus_mm_s'),
])
def test_snapshot_missing_component_preserves_unrelated_values(component, key, unrelated):
    frame = metric_frame()
    frame.loc[9, ('Velocity', 'CoM', component)] = np.nan
    result = resolve_summary_metrics(frame)
    unavailable(result[key])
    assert result[unrelated].value is not None


@pytest.mark.parametrize('fault', ['negative_angular_norm', 'overflow_horizontal_norm'])
def test_snapshot_norms_must_be_finite_nonnegative(fault):
    frame = metric_frame()
    if fault == 'negative_angular_norm':
        frame[('Velocity', 'CoM', 'Global_V_R_Norm')] = -2.
        key = 'AngularSpeedAtT1Minus_rad_s'
    else:
        for axis in 'XZ':
            frame[('Velocity', 'CoM', 'Global_V_T' + axis)] = np.finfo(float).max
        key = 'VxyAtT1Minus_mm_s'
    unavailable(resolve_summary_metrics(frame)[key])
    assert resolve_summary_metrics(frame)['VerticalVelAtT1Minus_mm_s'].value == -400.


def test_peak_descent_needs_complete_prefix_and_all_upward_is_valid_zero():
    frame = metric_frame()
    frame[('Velocity', 'CoM', 'Global_V_TY')] = 20.
    assert resolve_summary_metrics(frame)['PeakDescentSpeed_mm_s'].value == 0.
    frame.loc[2, ('Velocity', 'CoM', 'Global_V_TY')] = np.nan
    result = resolve_summary_metrics(frame)
    unavailable(result['PeakDescentSpeed_mm_s'])
    assert result['VerticalVelAtT1Minus_mm_s'].value == 20.


def test_detector_onset_and_persistent_contact_start_are_distinct():
    processor = DropPosturePostProcessor(face_definitions=FACE_DEFINITIONS, local_box_corners=LOCAL)
    times = pd.Index(np.arange(8) * .01 + 100.)
    analysis = processor._contact_analysis(min_heights=np.array([30., 20., 0., 0., 0., 0., 0., 0.]),
        index=times, contact_threshold_mm=1.)
    assert analysis['t1_minus_pos'] == 1
    summary = processor._impact_sequence_summary(
        contact_sets=[(), (), (1,), (2,), (3,), (3,), (), ()], index=times)
    assert summary[DropPostureSummaryCols.FIRST_IMPACT_TIME_SEC] == 100.04
    assert summary[DropPostureSummaryCols.IMPACT_SEQUENCE] == 'C3'
    assert times[analysis['t1_minus_pos']] == 100.01
    frame = metric_frame()
    frame[(*SUMMARY, 'T1MinusTimeSec')] = .008
    frame[(*SUMMARY, 'FirstImpactTimeSec')] = .032
    unavailable(resolve_summary_metrics(frame)['VerticalVelAtT1Minus_mm_s'])
    assert frame[(*SUMMARY, 'T1MinusTimeSec')].iloc[0] == .008


def test_empty_contact_interval_splits_same_set_and_one_frame_is_discarded():
    processor = DropPosturePostProcessor(face_definitions=FACE_DEFINITIONS, local_box_corners=LOCAL)
    summary = processor._impact_sequence_summary(
        contact_sets=[(1,), (), (2,), (2,), (), (2,), (2,)], index=pd.Index(np.arange(7) * .1))
    assert summary[DropPostureSummaryCols.IMPACT_EVENT_COUNT] == 2
    assert summary[DropPostureSummaryCols.IMPACT_SEQUENCE] == 'C2 -> C2'
    assert summary[DropPostureSummaryCols.FIRST_IMPACT_TIME_SEC] == .2


@pytest.mark.parametrize('vector,expected', [((0., -1., 0.), 0.), ((1., 0., 0.), 90.), ((0., -7., 0.), 0.)])
def test_target_down_direction_literal_oracle(vector, expected):
    frame = metric_frame()
    metric = calculate_target_posture_error(frame, target_context=target_context(frame, vector))
    assert metric.value == pytest.approx(expected, rel=1e-9, abs=1e-9), metric.reason


def test_target_nonidentity_pose_and_yaw_about_down_direction():
    rotation = Rotation.from_euler('z', 30., degrees=True)
    frame = metric_frame(rotation=rotation)
    # Rz(30)^T * (0,-1,0) = (-1/2,-sqrt(3)/2,0).
    context = target_context(frame, (-.5, -np.sqrt(3.) / 2., 0.))
    assert calculate_target_posture_error(frame, target_context=context).value == pytest.approx(0., abs=1e-9)
    yawed = metric_frame(rotation=Rotation.from_euler('y', 71., degrees=True) * rotation)
    assert calculate_target_posture_error(yawed, target_context=target_context(yawed, context['target_down_local'])).value == pytest.approx(0., abs=1e-9)


def test_current_review_evidence_is_separate_from_unmeasured_calibration():
    frame = metric_frame()
    result = resolve_summary_metrics(frame, target_context=target_context(frame))
    for key in ('TargetPostureError_deg', 'VerticalVelAtT1Minus_mm_s', 'EquivalentFreeFallHeight_mm'):
        assert result[key].evidence_status == 'current'
        assert result[key].calibration_status == 'not measured'


@pytest.mark.parametrize('field,value', [
    ('version', True), ('version', 2), ('user_approved', False), ('user_approved', 1),
    ('phase', 'release'), ('frame', 'world'), ('basis', 'automatic'),
    ('registration_sha256', 'f' * 64), ('applied_edition', '2020-01'),
    ('target_down_local', [0., 0., 0.]), ('target_down_local', [0., np.nan, 0.]),
    ('target_down_local', [False, -1., 0.]), ('target_down_local', [0., -1.]),
    ('unexpected', 1),
])
def test_target_rejects_unapproved_or_stale_context(field, value):
    frame = metric_frame()
    context = target_context(frame)
    context[field] = value
    unavailable(calculate_target_posture_error(frame, target_context=context))


def test_missing_target_is_reasoned_unavailable_while_snapshot_remains_available():
    frame = metric_frame()
    metric = calculate_target_posture_error(frame)
    unavailable(metric)
    assert 'No independently approved t1- target posture' in metric.reason
    assert resolve_summary_metrics(frame)['VerticalVelAtT1Minus_mm_s'].value == -400.


@pytest.mark.parametrize('fault', ['event', 'resampled', 'pose', 'corner', 'registration', 'excluded', 'axis'])
def test_target_preserves_actual_owner_and_geometry_gates(fault):
    frame = metric_frame()
    context = target_context(frame)
    if fault == 'event':
        frame[(*SUMMARY, 'T1MinusTimeSec')] = .064
    elif fault == 'resampled':
        update_processing(frame, lambda s: s['result_resampling'].update(enabled=True))
    elif fault == 'pose':
        frame.loc[9, ('Info', 'Pose', 'Source')] = 'Failed'
    elif fault == 'corner':
        frame.loc[9, ('Position', 'C1', 'P_TY')] += 10.
    elif fault == 'registration':
        change_review(frame, lambda r: r['detection'].update(registration_sha256='b' * 64))
    elif fault == 'excluded':
        change_review(frame, lambda r: r['candidate'].update(decision='exclude'))
    else:
        update_processing(frame, lambda s: s['postprocess'].update(vertical_axis=2))
    unavailable(calculate_target_posture_error(frame, target_context=context))


def test_geometric_height_500mm_with_exact_context_is_distinct_from_com_fit():
    speed = -np.sqrt(2. * 9810. * 500.)
    assert calculate_geometric_height(speed, HEIGHT_CONTEXT).value == pytest.approx(500., abs=1e-9, rel=1e-9)
    frame = metric_frame()
    frame[('Velocity', 'CoM', 'Global_V_TY')] = speed
    height = resolve_summary_metrics(frame)['EquivalentFreeFallHeight_mm']
    assert height.value == pytest.approx(500., abs=1e-9, rel=1e-9), height.reason
    unavailable(calculate_impact_metrics(frame).metrics['equivalent_height'])


@pytest.mark.parametrize('field,value', [('user_approved', False), ('user_approved', 1),
    ('is_free_fall', False), ('is_free_fall', 1), ('category', 'Type H'), ('kind', 'tip')])
def test_geometric_height_requires_explicit_approved_supported_context(field, value):
    context = dict(HEIGHT_CONTEXT, **{field: value})
    unavailable(calculate_geometric_height(-1000., context))


@pytest.mark.parametrize('speed,gravity', [(0., 9810.), (1., 9810.), (np.nan, 9810.),
    (-np.inf, 9810.), (-1e308, 9810.), (-1000., 0.), (-1000., -1.), (-1000., np.nan)])
def test_geometric_height_rejects_non_descent_overflow_and_bad_gravity(speed, gravity):
    unavailable(calculate_geometric_height(speed, HEIGHT_CONTEXT, gravity=gravity))


@pytest.mark.parametrize('fault', ['confirmed', 'motion', 'evidence', 'kind', 'scenario', 'left', 'right', 'censor_absent'])
def test_geometric_height_projects_only_exact_current_review_context(fault):
    frame = metric_frame()
    if fault == 'confirmed':
        change_review(frame, lambda r: r['identity'].update(confirmed=False))
    elif fault in ('motion', 'evidence'):
        field = 'motion' if fault == 'motion' else 'evidence_class'
        change_review(frame, lambda r: r['candidate'].update(**{field: 'tip_or_rotation'}))
    elif fault == 'kind':
        change_review(frame, lambda r: r['identity'].update(scenario_kind='other'))
    elif fault == 'scenario':
        frame[('Info', 'Artifact', 'ScenarioId')] = 'different'
    elif fault == 'censor_absent':
        change_review(frame, lambda r: r['candidate'].pop('left_censored'))
    else:
        change_review(frame, lambda r: r['candidate'].update(**{fault + '_censored': True}))
    unavailable(resolve_summary_metrics(frame)['EquivalentFreeFallHeight_mm'])


@pytest.mark.parametrize('target,owner,base', [
    (('BOTTOM',), 'Match', 'Match'), (('TOP',), 'Different', 'Mismatch'),
    (None, 'Unclear', 'Unknown'),
])
def test_intended_contact_adapter_preserves_entire_owner(target, owner, base):
    frame = metric_frame(target=target)
    comparison = calculate_contact_comparison(frame)
    assert comparison.outcome == owner, comparison.reason
    assert resolve_summary_metrics(frame)['IntendedContactMatch'].value == base


@pytest.mark.parametrize('fault', ['resampled', 'stale_intent', 'support', 'no_transition'])
def test_intended_contact_adapter_never_promotes_invalid_equality(fault):
    frame = metric_frame()
    if fault == 'resampled':
        update_processing(frame, lambda s: s['result_resampling'].update(enabled=True))
    elif fault == 'stale_intent':
        change_review(frame, lambda r: r['candidate']['intended_contact'].update(registration_sha256='f' * 64))
    elif fault == 'support':
        change_review(frame, lambda r: r['candidate'].update(motion='tip_or_rotation'))
    else:
        frame.loc[9, ('Position', 'CoM', 'P_TY')] = 60.
        for i, coordinate in enumerate(LOCAL[:, 1], 1):
            frame.loc[9, ('Position', f'C{i}', 'P_TY')] = 60. + coordinate
    owner = calculate_contact_comparison(frame)
    assert owner.outcome == 'Unclear' and owner.reason
    metric = resolve_summary_metrics(frame)['IntendedContactMatch']
    assert metric.value == 'Unknown'
    assert owner.reason in metric.reason


def settled_inputs(*, rotation=None, floor=0., count=16):
    rotations = Rotation.from_quat(np.tile([0., 0., 0., 1.], (count, 1))) if rotation is None else rotation
    corners = np.array([r.apply(LOCAL) for r in rotations])
    corners[:, :, 1] += floor - corners[:, :, 1].min(axis=1)[:, None]
    return np.arange(count) * .01, rotations, corners, np.array([200., 120., 80.])


@pytest.mark.parametrize('floor', [0., -200., 1000.])
def test_final_face_uses_finite_stable_tail_and_allows_negative_floor(floor):
    times, rotations, corners, dims = settled_inputs(floor=floor)
    result = final_face(times, rotations, corners, dims, floor=floor, threshold=1.)
    assert result.value == 'BOTTOM', result.reason


def test_final_face_uses_all_six_faces_and_is_quaternion_sign_invariant():
    quaternions = np.tile([0., 0., 1., 0.], (16, 1))
    times, rotations, corners, dims = settled_inputs(rotation=Rotation.from_quat(quaternions))
    assert final_face(times, rotations, corners, dims, floor=0., threshold=1.).value == 'TOP'
    quaternions[::2] *= -1.
    assert final_face(times, Rotation.from_quat(quaternions), corners, dims, floor=0., threshold=1.).value == 'TOP'


def test_final_face_rotation_mean_crosses_rotvec_branch_without_arithmetic_cancellation():
    angles = np.resize([179., -179.], 16)
    times, rotations, corners, dims = settled_inputs(rotation=Rotation.from_euler('z', angles, degrees=True))
    result = final_face(times, rotations, corners, dims, floor=0., threshold=1.)
    assert result.value == 'TOP', result.reason


@pytest.mark.parametrize('saved,expected', [(None, None), ('BOTTOM', 'BOTTOM'), ('TOP', None)])
def test_final_face_load_requires_saved_field_and_works_without_new_impact(saved, expected):
    frame = metric_frame()
    for axis_index, axis in enumerate('XYZ'):
        frame[('Position', 'CoM', 'P_T' + axis)] = 60. if axis == 'Y' else 0.
        for i, coordinate in enumerate(LOCAL[:, axis_index], 1):
            frame[('Position', f'C{i}', 'P_T' + axis)] = coordinate + (60. if axis == 'Y' else 0.)
    for key, value in dict(ContactState='SustainedContact', T1Detected=False, ImpactDetected=False,
                           T1MinusTimeSec=np.nan, FirstImpactTimeSec=np.nan, FirstImpactContact='',
                           ImpactSequence='', ImpactEventCount=0, SustainedContactDetected=True,
                           ContactConfidence=.35, ContactDetectionMethod='threshold+plateau').items():
        frame[(*SUMMARY, key)] = value
    if saved is not None:
        frame[(*SUMMARY, 'FinalFace')] = saved
    result = resolve_summary_metrics(frame)
    assert result['FinalFace'].value == expected, result['FinalFace'].reason
    if expected is None:
        assert result['FinalFace'].reason
    unavailable(result['VerticalVelAtT1Minus_mm_s'])


def test_final_face_exact_tie_retains_public_insertion_order():
    # q=(1,0,1,2)/sqrt(6): local down has equal LEFT and FRONT components 2/3.
    rotations = Rotation.from_quat(np.tile([1., 0., 1., 2.], (16, 1)))
    times, rotations, corners, dims = settled_inputs(rotation=rotations)
    result = final_face(times, rotations, corners, dims, floor=0., threshold=1.)
    assert result.value == 'LEFT', result.reason


def test_final_face_ambiguous_mean_is_unavailable_not_arbitrary_face():
    quaternions = np.tile([0., 0., 0., 1.], (16, 1))
    quaternions[10::2] = [1., 0., 0., 0.]
    times, rotations, corners, dims = settled_inputs(rotation=Rotation.from_quat(quaternions))
    result = final_face(times, rotations, corners, dims, floor=0., threshold=1.)
    unavailable(result)
    assert 'ambig' in result.reason.lower()


@pytest.mark.parametrize('fault', ['short', 'missing', 'inconsistent', 'time_duplicate', 'time_reverse', 'dimension', 'axis', 'threshold'])
def test_final_face_invalid_evidence_is_unavailable(fault):
    times, rotations, corners, dims = settled_inputs(count=10 if fault == 'short' else 16)
    kwargs = dict(floor=0., threshold=1., vertical_axis=1)
    if fault == 'missing':
        corners[-1, 0, 1] = np.nan
    elif fault == 'inconsistent':
        corners[-1, 0, 1] += 4.
    elif fault == 'time_duplicate':
        times[-1] = times[-2]
    elif fault == 'time_reverse':
        times[-1] = times[-2] - .005
    elif fault == 'dimension':
        dims[0] = 0.
    elif fault == 'axis':
        kwargs['vertical_axis'] = 2
    elif fault == 'threshold':
        kwargs['threshold'] = 0.
    unavailable(final_face(times, rotations, corners, dims, **kwargs))


def test_final_face_usable_negative_plateau_evidence_is_unsettled():
    times, rotations, corners, dims = settled_inputs()
    corners[:, :, 1] += 100.
    metric = final_face(times, rotations, corners, dims, floor=0., threshold=1.)
    assert metric.value == 'Unsettled'


RIGHT, BACK, LEFT, FRONT = (2, 3, 6, 7), (1, 2, 3, 4), (1, 4, 5, 8), (5, 6, 7, 8)


def sweep_inputs(sets):
    corners = np.tile(LOCAL, (2 * len(sets), 1, 1))
    events = [dict(start_pos=2 * i, contact_set=contact, length=2) for i, contact in enumerate(sets)]
    return corners, events


@pytest.mark.parametrize('sets,sweep,consistency,direction', [
    ([RIGHT, BACK, LEFT], 180., 1., 'CCW'),
    ([RIGHT, FRONT, LEFT], 180., 1., 'CW'),
    ([RIGHT, BACK, RIGHT], 0., 0., 'Indeterminate'),
])
def test_contact_sweep_literal_principal_steps_net_and_cancellation(sets, sweep, consistency, direction):
    corners, events = sweep_inputs(sets)
    for translation in ([0., 0., 0.], [1000., -200., 300.]):
        result = contact_sweep(corners + translation, events)
        assert result['TotalSweepAngle_deg'].value == pytest.approx(sweep, rel=1e-9, abs=1e-9)
        assert result['SweepConsistency'].value == pytest.approx(consistency, rel=1e-9, abs=1e-9)
        assert result['RotationDirection'].value == direction


@pytest.mark.parametrize('perturbation,direction', [(.001, 'CW'), (-.001, 'CCW')])
def test_contact_sweep_principal_halfturn_sides_keep_signed_cross(perturbation, direction):
    corners, events = sweep_inputs([RIGHT, LEFT])
    corners[2:] = Rotation.from_rotvec([0., perturbation, 0.]).apply(LOCAL)
    result = contact_sweep(corners, events)
    expected = 180. - .001 * 180. / np.pi
    assert result['TotalSweepAngle_deg'].value == pytest.approx(expected, abs=1e-9, rel=1e-9)
    assert result['SweepConsistency'].value == 1.
    assert result['RotationDirection'].value == direction


@pytest.mark.parametrize('sets', [[RIGHT], [RIGHT, RIGHT], [RIGHT, LEFT], [RIGHT, tuple(range(1, 9)), BACK]])
def test_contact_sweep_no_travel_halfturn_and_zero_radius_do_not_invent_values(sets):
    corners, events = sweep_inputs(sets)
    result = contact_sweep(corners, events)
    for key in ('TotalSweepAngle_deg', 'SweepConsistency'):
        unavailable(result[key])
    assert result['RotationDirection'].reason


def test_contact_sweep_nonfinite_geometry_invalidates_entire_path():
    corners, events = sweep_inputs([RIGHT, BACK, LEFT])
    corners[-1, 0, 2] = np.nan
    for metric in contact_sweep(corners, events).values():
        assert metric.reason
        assert metric.value is None or metric.value == 'Undefined'


def test_contact_sweep_finite_input_overflow_never_publishes_nan_or_direction():
    corners, events = sweep_inputs([RIGHT, BACK, LEFT])
    with np.errstate(over='ignore', invalid='ignore'):
        result = contact_sweep(corners * 1e306, events)
    for metric in result.values():
        unavailable(metric)


def test_exact_lowest_corner_ties_are_not_unique_agreement():
    gap, category = lowest_corners([0., 0., 120., 120., 0., 0., 120., 120.])
    assert gap == 0.
    assert category == 'Non-unique {C1,C2,C5,C6}'


@pytest.mark.parametrize(('key', 'bad_value'), [
    ('T1Detected', 'banana'),
    ('ImpactDetected', 'banana'),
    ('SustainedContactDetected', 'banana'),
    ('ContactDetectionMethod', 'banana'),
    ('ImpactEventCount', 999),
    ('ImpactEventCount', -1),
    ('ImpactEventCount', 1.5),
    ('ImpactEventCount', 'banana'),
])
def test_summary_diagnostics_reject_malformed_or_inconsistent_saved_values(key, bad_value):
    frame = metric_frame()
    # This fixture reaches the floor at .080 s and stays there for three
    # frames: one accepted bottom-face run. Its short tail is not stable.
    expected = dict(T1Detected=True, ImpactDetected=True,
                    SustainedContactDetected=False, ContactDetectionMethod='threshold',
                    ImpactEventCount=1)
    for field, value in expected.items():
        frame[(*SUMMARY, field)] = value
    baseline = resolve_summary_metrics(frame)
    for field, value in expected.items():
        assert baseline[field].status == 'available', baseline[field].reason
        assert baseline[field].value == value
    frame[(*SUMMARY, key)] = bad_value
    original = frame.copy(deep=True)
    unavailable(resolve_summary_metrics(frame)[key])
    pd.testing.assert_frame_equal(frame, original)


def test_summary_contact_count_needs_complete_observed_geometry():
    frame = metric_frame()
    frame[(*SUMMARY, 'ImpactEventCount')] = 1
    assert resolve_summary_metrics(frame)['ImpactEventCount'].value == 1
    frame.loc[frame.index[-1], ('Position', 'C1', 'P_TX')] = np.nan
    unavailable(resolve_summary_metrics(frame)['ImpactEventCount'])


@pytest.mark.parametrize(('policy', 'bad_value'), [
    ('time_policy', None),
    ('time_policy', 'row-number'),
    ('segmentation_policy', None),
    ('segmentation_policy', 'cross-gap'),
])
def test_stored_snapshots_require_actual_time_and_contiguous_segment_provenance(policy, bad_value):
    frame = metric_frame()
    keys = ('VerticalVelAtT1Minus_mm_s', 'VxyAtT1Minus_mm_s',
            'AngularSpeedAtT1Minus_rad_s', 'PeakDescentSpeed_mm_s')
    baseline = resolve_summary_metrics(frame)
    assert [baseline[key].value for key in keys] == [-400., 300., 2., 400.]
    update_processing(frame, lambda settings:
                      settings['single_pass']['derivatives'].update({policy: bad_value}))
    original = frame.copy(deep=True)
    result = resolve_summary_metrics(frame)
    for key in keys:
        unavailable(result[key])
        assert 'policy' in result[key].reason
    pd.testing.assert_frame_equal(frame, original)


@pytest.mark.parametrize('angle,expected_range', [(0., 0.), (30., 50.), (-30., 50.)])
@pytest.mark.parametrize('vertical_offset', [0., 200.])
def test_a03_exact_100mm_face_spacing_has_50mm_range_at_30deg(angle, expected_range, vertical_offset):
    # Explicit 100 x 60 x 80 mm geometry makes local X the long BOTTOM axis.
    local = np.array([
        [-50., -30., -40.], [50., -30., -40.], [50., 30., -40.], [-50., 30., -40.],
        [-50., -30., 40.], [50., -30., 40.], [50., 30., 40.], [-50., 30., 40.],
    ])
    radians = angle * np.pi / 180.
    matrix = np.array([[np.cos(radians), -np.sin(radians), 0.],
                       [np.sin(radians), np.cos(radians), 0.], [0., 0., 1.]])
    points = local @ matrix.T + [0., vertical_offset, 0.]
    frame = pd.DataFrame({PoseCols.ROT_X: [0.], PoseCols.ROT_Y: [0.],
                          PoseCols.ROT_Z: [radians]}, index=[.2])
    processor = DropPosturePostProcessor(face_definitions=FACE_DEFINITIONS, local_box_corners=local)
    assert processor._select_reference_face(Rotation.from_matrix(matrix)) == 'BOTTOM'
    assert processor._reference_axes('BOTTOM') == (0, 2)
    result = processor._compute_frame_metrics(frame, points[None, :, :], 'BOTTOM', 0, 2).iloc[0]
    # Rz(+30) raises the +X side by 50 mm; range is unsigned, theta is signed.
    assert result[DropPostureCols.DELTA_H_MM] == pytest.approx(expected_range, rel=1e-9, abs=1e-9)
    assert result[DropPostureCols.THETA_LONG_DEG] == pytest.approx(angle, rel=1e-9, abs=1e-9)
    assert result[DropPostureCols.THETA_SHORT_DEG] == pytest.approx(0., rel=1e-9, abs=1e-9)
    assert result[DropPostureCols.BETA_DEG] == pytest.approx(abs(angle), rel=1e-9, abs=1e-9)


def test_a05_real_comparison_owner_aggregates_eligible_10_12_14mm_and_excludes_invalid(tmp_path):
    from src.analysis.compare.data_model import ComparisonModel

    model = ComparisonModel()
    for index, height in enumerate((10., 12., 14., 18.)):
        angle = np.degrees(np.arcsin(height / 200.))
        frame = posture_frame(angle, source='abcd'[index] * 64)
        if index == 3:
            frame[(*SUMMARY, 'DeltaHAtT1Minus_mm')] = 999.
        path = tmp_path / f'a05_independent_source_{index}.proc'
        frame.to_csv(path, index=False)
        model.load_file(str(path))
    comparison = model.get_posture_comparison()
    statistics = comparison['statistics']['height_range']
    assert statistics['n'] == 3
    for key, expected in dict(mean=12., min=10., max=14., range=4.).items():
        assert statistics[key] == pytest.approx(expected, rel=1e-9, abs=1e-9)
    invalid = comparison['files']['a05_independent_source_3.proc']
    assert invalid['result'].metrics['height_range'].value is None
    assert invalid['result'].metrics['height_range'].reason


def test_a05_real_comparison_owner_no_eligible_values_has_n0_and_unavailable_summaries(tmp_path):
    from src.analysis.compare.data_model import ComparisonModel

    model = ComparisonModel()
    for index, height in enumerate((10., 12., 14.)):
        frame = posture_frame(np.degrees(np.arcsin(height / 200.)), source='abc'[index] * 64)
        frame[(*SUMMARY, 'DeltaHAtT1Minus_mm')] = 999.
        path = tmp_path / f'a05_invalid_source_{index}.proc'
        frame.to_csv(path, index=False)
        model.load_file(str(path))
    statistics = model.get_posture_comparison()['statistics']['height_range']
    assert statistics == dict(n=0, mean=None, min=None, max=None, range=None)


def test_a06_combined_absolute_time_and_vertical_translation_preserves_only_relative_quantities(tmp_path):
    from src.analysis.pipeline.data_loader import DataLoader

    original = posture_frame(30.)
    shifted = original.copy(deep=True)
    shifted[('Info', 'Time', 'Time')] += 100.
    for column in (('Info', 'Timeline', 'SliceStartSec'), ('Info', 'Timeline', 'SliceEndSec'),
                   (*SUMMARY, 'T1MinusTimeSec'), (*SUMMARY, 'FirstImpactTimeSec')):
        shifted[column] += 100.
    for column in shifted.columns:
        if column[0] == 'Position' and column[2] == 'P_TY':
            shifted[column] += 1000.
    change_review(shifted, lambda review: review['candidate'].update(
        start=review['candidate']['start'] + 100., end=review['candidate']['end'] + 100.,
        auto_start=review['candidate']['auto_start'] + 100., auto_end=review['candidate']['auto_end'] + 100.))
    def translate_floor(settings):
        settings['single_pass']['frame_analysis']['floor_level_mm'] += 1000.
        settings['postprocess']['floor_level_mm'] += 1000.
    update_processing(shifted, translate_floor)

    loaded = []
    for name, frame in [('original', original), ('shifted', shifted)]:
        path = tmp_path / f'a06_{name}.proc'
        frame.to_csv(path, index=False)
        loaded.append(DataLoader().load_result_csv(str(path)))
    before, after = (resolve_summary_metrics(frame) for frame in loaded)
    for key, expected_before, expected_after in [
        ('T1MinusTimeSec', .072, 100.072), ('FirstImpactTimeSec', .080, 100.080),
    ]:
        assert before[key].value == pytest.approx(expected_before, rel=1e-9, abs=1e-9)
        assert after[key].value == pytest.approx(expected_after, rel=1e-9, abs=1e-9)
    for result in (before, after):
        assert result['FirstImpactTimeSec'].value - result['T1MinusTimeSec'].value == pytest.approx(.008, rel=1e-9, abs=1e-9)
        for key, expected in [('BetaAtT1MinusDeg', 30.), ('ThetaLongAtT1MinusDeg', 30.),
                              ('ThetaShortAtT1MinusDeg', 0.), ('DeltaHAtT1Minus_mm', 100.),
                              ('MaxDeltaH_mm', 100.), ('CminMargin_mm', 0.)]:
            assert result[key].value == pytest.approx(expected, rel=1e-9, abs=1e-9), result[key].reason
        assert result['ReferenceFace'].value == 'BOTTOM'
    assert loaded[0].index[0] == 0.
    assert loaded[1].index[0] == 100.
    for frame in loaded:
        assert frame.index[-1] - frame.index[0] == pytest.approx(.096, rel=1e-9, abs=1e-9)
    # Absolute world heights shift; do not apply an all-outputs-invariant assertion.
    expected_corner_height = .5 * 9806.65 * (.080**2 - .072**2)
    assert loaded[0].iloc[9][('Position', 'C1', 'P_TY')] == pytest.approx(expected_corner_height, rel=1e-9, abs=1e-9)
    assert loaded[1].iloc[9][('Position', 'C1', 'P_TY')] == pytest.approx(1000. + expected_corner_height, rel=1e-9, abs=1e-9)


@pytest.mark.parametrize('units,scale,expected_position', [('Millimeters', 1., 70.), ('Meters', .001, .070)])
def test_a02_declared_raw_units_are_preserved_by_parser_and_metres_are_rejected_at_scene_boundary(tmp_path, units, scale, expected_position):
    import csv
    from src.analysis.pipeline.data_loader import DataLoader
    from src.analysis.pipeline.parser import Parser
    from src.analysis.pipeline.scene_detection import detect_scenes
    from src.config.data_columns import FACE_PREFIX_TO_INFO, RigidBodyCols

    path = tmp_path / f'a02_{units}.csv'
    times = [0., .1, .2, .3, .4]
    headers = [
        ['', '', 'Rigid Body', 'Rigid Body', 'Rigid Body'],
        ['Frame', 'Time', 'PublicBox', 'PublicBox', 'PublicBox'],
        ['', '', '1', '1', '1'], ['', '', '', '', ''],
        ['', '', 'Position', 'Position', 'Position'], ['Frame', 'Time', 'X', 'Y', 'Z'],
    ]
    with path.open('w', encoding='utf-8', newline='') as stream:
        writer = csv.writer(stream)
        writer.writerow(['Format Version', '1.25', 'Length Units', units, 'Coordinate Space', 'Global'])
        writer.writerow([])
        writer.writerows(headers)
        for index, time in enumerate(times):
            writer.writerow([index, time, scale * (10. + 200. * time + 500. * time**2), 0., 0.])
    header, raw = DataLoader().load_csv(str(path))
    parsed = Parser(FACE_PREFIX_TO_INFO).process(header, raw)
    assert header['export_metadata']['Length Units'] == units
    assert parsed.loc[.2, RigidBodyCols.POS_X] == pytest.approx(expected_position, rel=1e-9, abs=1e-9)
    # Parser does no physical-unit conversion. The supported scene boundary
    # rejects declared metres before markers or pose fitting are considered.
    if units == 'Meters':
        with pytest.raises(ValueError, match='declared in millimeters'):
            detect_scenes(header, raw, parsed)


def test_a02_unsupported_saved_metres_policy_cannot_be_reported_as_mm_snapshot():
    frame = metric_frame()
    frame[('Info', 'Artifact', 'UnitsPolicy')] = 'bma-m-s-rotvec-rad-summary-deg-v1'
    result = resolve_summary_metrics(frame)
    unavailable(result['VerticalVelAtT1Minus_mm_s'])
    unavailable(result['EquivalentFreeFallHeight_mm'])


def test_selected_series_identity_uses_full_tuple_without_mutating_fixed_registry():
    from src.config.data_columns import DISPLAY_RESULT_COLUMNS
    from src.config.result_metric_descriptors import get_metric_registry, get_series_metric_descriptor

    registry_before = get_metric_registry()
    columns = tuple(dict.fromkeys(DISPLAY_RESULT_COLUMNS))
    descriptors = [get_series_metric_descriptor(column) for column in columns]
    assert all(descriptor is not None for descriptor in descriptors)
    identities = [descriptor.stable_id for descriptor in descriptors]
    assert len(set(identities)) == len(columns)
    assert not set(identities) & {descriptor.stable_id for descriptor in registry_before}
    for column, descriptor in zip(columns, descriptors):
        assert descriptor.column == column
        assert descriptor.context == 'step2:series'
        assert descriptor.stable_id.startswith('step2:series:')
        assert get_series_metric_descriptor(list(column)).stable_id == descriptor.stable_id
        assert descriptor.time_reference == 'selected recorded sample'
    assert get_metric_registry() == registry_before


@pytest.mark.parametrize(('column', 'unit'), [
    (('Analysis', 'DropPosture', 'BetaDeg'), '°'),
    (('Analysis', 'DropPosture', 'DeltaH_mm'), 'mm'),
    (('Analysis', 'DropPosture', 'CminIndex'), ''),
    (('Position', 'CoM', 'P_TX'), 'mm'),
    (('Position', 'CoM', 'P_RX'), 'rad'),
    (('Velocity', 'CoM', 'Global_V_TY'), 'mm/s'),
    (('Velocity', 'CoM', 'Global_V_R_Norm'), 'rad/s'),
    (('Acceleration', 'CoM', 'BoxLocal_A_TX'), 'mm/s²'),
    (('Acceleration', 'CoM', 'Global_A_RY'), 'rad/s²'),
    (('Analysis', 'C1', 'RelativeHeight'), 'mm'),
])
def test_selected_series_units_and_localized_headings_describe_saved_rows(column, unit):
    from src.config.result_metric_descriptors import get_series_metric_descriptor

    descriptor = get_series_metric_descriptor(column)
    assert descriptor is not None
    assert descriptor.unit == unit
    assert descriptor.definition_ko and descriptor.caution_ko
    assert any('\uac00' <= character <= '\ud7a3' for character in descriptor.label_ko)
    if unit:
        # The shared renderer owns the one visible unit suffix.
        assert '(' + unit + ')' not in descriptor.display_name
        assert '(' + unit + ')' not in descriptor.label_ko
    assert 'selected time need not be t1-' in descriptor.caution.lower()


def test_selected_series_object_and_reference_are_visible_without_aliasing_snapshot_or_fit():
    from src.config.result_metric_descriptors import get_series_metric_descriptor

    columns = [('Velocity', object_name, 'Global_V_TX') for object_name in ('CoM', 'C1', 'C2')]
    descriptors = [get_series_metric_descriptor(column) for column in columns]
    assert len({descriptor.display_name for descriptor in descriptors}) == 3
    assert 'C1' in descriptors[1].display_name
    assert 'C2' in descriptors[2].display_name
    position = get_series_metric_descriptor(('Position', 'CoM', 'P_TX'))
    assert 'geometric' in position.reference.lower() and 'world' in position.reference.lower()
    rotation = get_series_metric_descriptor(('Position', 'CoM', 'P_RX'))
    assert 'rotation-vector' in rotation.long_description
    assert 'not an Euler angle' in rotation.long_description
    beta = get_series_metric_descriptor(('Analysis', 'DropPosture', 'BetaDeg'))
    assert 'at this row' in beta.long_description
    assert 'fixed' in beta.reference
    assert beta.stable_id not in ('step2:summary:BetaAtT1MinusDeg', 'compare:beta')
    assert descriptors[0].stable_id not in ('step2:summary:VerticalVelAtT1Minus_mm_s', 'compare:vertical_velocity')


@pytest.mark.parametrize('column', [None, 'BetaDeg', (), ('Analysis', 'DropPosture'),
    ('Analysis', 'DropPosture', 'BetaDeg', 'extra'), ('Analysis', 'DropPosture', 1),
    ('Analysis', 'DropPostureSummary', 'BetaAtT1MinusDeg'),
    ('Velocity', 'UnregisteredObject', 'Global_V_TX'), ('Unknown', 'CoM', 'P_TX')])
def test_selected_series_unknown_columns_do_not_guess_a_related_definition(column):
    from src.config.result_metric_descriptors import get_series_metric_descriptor

    assert get_series_metric_descriptor(column) is None
