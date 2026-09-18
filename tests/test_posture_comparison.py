"""Analytic rigid geometry and literal repeat arithmetic, not measured accuracy."""
from dataclasses import asdict
from itertools import permutations
import json

import numpy as np
import pandas as pd
import pytest

from impact_metric_fixtures import make_frame, update_processing, REVIEW, SUMMARY
from src.analysis.pipeline.scene_detection import DetectionSettings
from src.analysis.compare.posture_metrics import calculate_posture_metrics, lowest_corners
from src.analysis.compare.data_model import ComparisonModel


def posture_frame(angle=10., source='a' * 64, *, no_impact=False):
    """Y-up 200×80×120 box with literal Rz(angle), held after ground contact."""
    times = np.arange(13) * .008
    df = make_frame(times=times, t1=times[9], impact=times[10], omega=(0, 0, 0),
                    source_sha256=source, com_offset=None)
    local = np.array([[-100,-40,-60], [100,-40,-60], [100,40,-60], [-100,40,-60],
                      [-100,-40,60], [100,-40,60], [100,40,60], [-100,40,60]])
    theta = np.radians(angle)
    c, s = np.cos(theta), np.sin(theta)
    matrix = np.array([[c,-s,0], [s,c,0], [0,0,1]])
    rotated = local @ matrix.T
    clearance = np.full(len(times), 200.) if no_impact else np.maximum(0., .5 * 9806.65 * (times[10]**2-times**2))
    position = np.column_stack([np.zeros(len(times)), clearance - rotated[:, 1].min(), np.zeros(len(times))])
    for axis_i, axis in enumerate('XYZ'):
        df[('Position', 'CoM', 'P_T' + axis)] = position[:, axis_i]
        df[('Position', 'CoM', 'P_R' + axis)] = theta if axis == 'Z' else 0.
        for i in range(8):
            df[('Position', f'C{i+1}', 'P_T' + axis)] = position[:, axis_i] + rotated[i, axis_i]
    for field, value in {'BoxWidthMm': 80., 'BoxHeightMm': 120.}.items():
        df[('Info', 'Artifact', field)] = value
    def geometry(settings):
        for stage in ('single_pass', 'postprocess'):
            settings[stage]['geometry_mm'] = local.tolist()
    update_processing(df, geometry)
    review = json.loads(df[REVIEW].iloc[0])
    review['detection'].update(settings=asdict(DetectionSettings()), registration=None, registration_sha256=None)
    df[REVIEW] = json.dumps(review)
    # Independent trigonometric oracle, never production output copied to input.
    values = dict(ReferenceFace='BOTTOM', LongAxis='LocalAxis0', ShortAxis='LocalAxis2',
        BetaAtT1MinusDeg=abs(angle), ThetaLongAtT1MinusDeg=angle, ThetaShortAtT1MinusDeg=0.,
        DeltaHAtT1Minus_mm=200 * abs(s), CminAtT1MinusIndex=1 if angle >= 0 else 2,
        MaxBetaDeg=abs(angle), MaxAbsThetaLongDeg=abs(angle), MaxAbsThetaShortDeg=0.,
        MaxDeltaH_mm=200 * abs(s), ImpactSequence='{C1,C5}' if angle > 0 else '{C2,C6}')
    if no_impact:
        values.update(ContactState='NoContact', T1Detected=False, ImpactDetected=False,
            T1MinusTimeSec=np.nan, FirstImpactTimeSec=np.nan, FirstImpactContact='', ImpactSequence='', ContactConfidence=0.)
        for field in ('BetaAtT1MinusDeg', 'ThetaLongAtT1MinusDeg', 'ThetaShortAtT1MinusDeg', 'DeltaHAtT1Minus_mm', 'CminAtT1MinusIndex'):
            values[field] = np.nan
    else:
        values['FirstImpactContact'] = values['ImpactSequence']
    for name, value in values.items():
        df[(*SUMMARY, name)] = value
    for name, value in dict(BetaDeg=abs(angle), ThetaLongDeg=angle, ThetaShortDeg=0.,
                            DeltaH_mm=200*abs(s), CminIndex=1 if angle >= 0 else 2).items():
        df[('Analysis', 'DropPosture', name)] = value
    return df


@pytest.mark.parametrize('heights,gap,category', [
    ([0,2,4,6,8,10,12,14], 2., 'C1'),
    ([0,0,4,6,8,10,12,14], 0., 'Non-unique {C1,C2}'),
    ([0,0,4,6,0,0,12,14], 0., 'Non-unique {C1,C2,C5,C6}'),
    ([4,3,2,1,0,-1,-2,-3], 1., 'C8'),
])
def test_literal_height_gap_and_translation_invariance(heights, gap, category):
    for translation in (0., 100., -200.):
        assert lowest_corners(np.asarray(heights) + translation) == (gap, category)


@pytest.mark.parametrize('heights', [[0]*7, [0]*7+[np.nan], [0]*7+[np.inf]])
def test_incomplete_heights_never_make_a_gap(heights):
    with pytest.raises(ValueError, match='Eight finite'):
        lowest_corners(heights)


def test_saved_values_checked_against_analytic_geometry_without_registration_or_final_face():
    frame = posture_frame(-20)
    original = frame.copy(deep=True)
    result = calculate_posture_metrics(frame)
    assert result.metrics['beta'].value == 20
    assert result.metrics['theta_long'].value == -20
    assert result.metrics['theta_short'].value == 0
    assert result.metrics['height_range'].value == pytest.approx(200*np.sin(np.radians(20)))
    assert result.metrics['corner_gap'].value == 0
    assert result.metrics['lowest_corner'].value == 'Non-unique {C2,C6}'
    assert result.metrics['sequence'].value == '{C2,C6}', result.metrics['sequence'].reason
    assert all(not m.reason for m in result.metrics.values())
    assert not result.window_reason and result.reference == ('BOTTOM', 'LocalAxis0', 'LocalAxis2')
    pd.testing.assert_frame_equal(frame, original)


def load_frames(tmp_path, frames, order=None):
    paths = []
    for i, frame in enumerate(frames):
        path = tmp_path / f'trial_{i}.proc'
        frame.to_csv(path, index=False)
        paths.append(path)
    model = ComparisonModel()
    for i in range(len(paths)) if order is None else order:
        model.load_file(str(paths[i]))
    return model


def test_independent_repeats_numeric_and_category_counts_copies_count_once(tmp_path):
    model = load_frames(tmp_path, [posture_frame(10), posture_frame(20, 'b'*64), posture_frame(30, 'c'*64), posture_frame(10)])
    result = model.get_posture_comparison()
    assert result['statistics']['beta'] == dict(n=3, mean=20., min=10., max=30., range=20.)
    assert result['statistics']['max_long'] == dict(n=3, mean=20., min=10., max=30., range=20.)
    assert result['statistics']['lowest_corner'] == dict(n=3, counts={'Non-unique {C1,C5}': 3}, reference=None, matching=None)
    assert result['statistics']['corner_gap'] == dict(n=3, mean=0., min=0., max=0., range=0.)


@pytest.mark.parametrize('kind', ['invalid', 'equal', 'conflict'])
def test_metric_resolution_is_independent_of_baseline_and_load_order(tmp_path, kind):
    first, second = posture_frame(), posture_frame()
    if kind == 'invalid':
        first[(*SUMMARY, 'BetaAtT1MinusDeg')] = 999.
    elif kind == 'conflict':
        # Both pass only numerical validity; exact duplicate equality still fails.
        first[(*SUMMARY, 'BetaAtT1MinusDeg')] += 1e-8
    for order in permutations(range(2)):
        model = load_frames(tmp_path, [first, second], order)
        for baseline in model.datasets:
            model.set_baseline(baseline)
            result = model.get_posture_comparison()
            assert result['statistics']['beta']['n'] == (0 if kind == 'conflict' else 1)
            assert result['statistics']['theta_long']['n'] == 1
            assert result['statistics']['corner_gap']['n'] == 1


@pytest.mark.parametrize('field,value', [('SourceKind','real'), ('ModelId','another'), ('BoxLengthMm',201.),
    ('MarkerLayoutHash','c'*64), ('ScenarioId','G02'), ('ProcessingSemanticsVersion','unsupported')])
def test_existing_compatibility_excludes_different_conditions(tmp_path, field, value):
    other = posture_frame(20, 'b'*64)
    other[('Info', 'Artifact', field)] = value
    model = load_frames(tmp_path, [posture_frame(), other])
    assert model.get_posture_comparison()['statistics']['beta']['n'] == 1


def test_no_t1_does_not_exclude_supported_whole_windows(tmp_path):
    model = load_frames(tmp_path, [posture_frame(no_impact=True), posture_frame(20, 'b'*64, no_impact=True)])
    result = model.get_posture_comparison()
    assert result['statistics']['beta']['n'] == 0
    assert result['statistics']['max_beta']['n'] == 2
    assert result['statistics']['max_beta']['mean'] == 15


def test_different_windows_remain_individual_and_do_not_poison_precontact(tmp_path):
    a, b = posture_frame(), posture_frame(20, 'b'*64)
    review = json.loads(b[REVIEW].iloc[0])
    review['candidate']['end'] = .104
    b[REVIEW] = json.dumps(review)
    b[('Info', 'Timeline', 'SliceEndSec')] = .104
    model = load_frames(tmp_path, [a, b])
    result = model.get_posture_comparison()
    assert result['statistics']['beta']['n'] == 2
    assert result['statistics']['max_beta']['n'] == 1
    assert result['files']['trial_1.proc']['result'].metrics['max_beta'].value == 20
    assert 'boundaries' in result['files']['trial_1.proc']['metric_resolution']['max_beta']['reason']


@pytest.mark.parametrize('change', ['manual', 'version', 'settings'])
def test_unaligned_window_definition_must_match(tmp_path, change):
    b = posture_frame(20, 'b'*64, no_impact=True)
    review = json.loads(b[REVIEW].iloc[0])
    if change == 'manual':
        review['candidate']['origin'] = 'manual'
    elif change == 'version':
        review['detection']['version'] = 'different-window-definition'
    else:
        review['detection']['settings']['gap_factor'] = 7
    b[REVIEW] = json.dumps(review)
    model = load_frames(tmp_path, [posture_frame(no_impact=True), b])
    assert model.get_posture_comparison()['statistics']['max_beta']['n'] == 1


def test_one_corrupt_field_does_not_hide_unrelated_geometry():
    frame = posture_frame()
    frame[(*SUMMARY, 'CminAtT1MinusIndex')] = 8
    frame[(*SUMMARY, 'ReferenceFace')] = 'TOP'
    result = calculate_posture_metrics(frame)
    assert result.metrics['beta'].reason
    assert result.metrics['lowest_corner'].reason
    assert result.metrics['corner_gap'].value == 0


def test_missing_whole_window_geometry_is_not_silently_cropped(tmp_path):
    b = posture_frame(20, 'b'*64)
    b.loc[0, ('Position', 'C8', 'P_TY')] = np.nan
    model = load_frames(tmp_path, [posture_frame(), b])
    result = model.get_posture_comparison()
    assert result['statistics']['max_beta']['n'] == 1
    assert result['statistics']['beta']['n'] == 2
    assert 'whole-window geometry' in result['files']['trial_1.proc']['result'].metrics['sequence'].reason


def test_invalid_whole_geometry_variant_does_not_poison_valid_copy_on_baseline_change(tmp_path):
    b = posture_frame()
    b.loc[0, ('Position', 'C8', 'P_TY')] = np.nan
    model = load_frames(tmp_path, [posture_frame(), b])
    for name in model.datasets:
        model.set_baseline(name)
        assert model.get_posture_comparison()['statistics']['max_beta']['n'] == 1


def test_side_reference_angles_stay_individual_but_corner_gap_is_not_excluded(tmp_path):
    frame = posture_frame(80)
    fields = dict(ReferenceFace='LEFT', LongAxis='LocalAxis2', ShortAxis='LocalAxis1',
        BetaAtT1MinusDeg=10., ThetaLongAtT1MinusDeg=0., ThetaShortAtT1MinusDeg=10.,
        DeltaHAtT1Minus_mm=80*np.cos(np.radians(80)), MaxBetaDeg=10., MaxAbsThetaLongDeg=0.,
        MaxAbsThetaShortDeg=10., MaxDeltaH_mm=80*np.cos(np.radians(80)))
    for field, value in fields.items():
        frame[(*SUMMARY, field)] = value
    model = load_frames(tmp_path, [frame])
    result = model.get_posture_comparison()
    assert result['files']['trial_0.proc']['result'].metrics['beta'].value == 10.
    assert result['statistics']['beta']['n'] == 0
    assert result['statistics']['corner_gap']['n'] == 1
    assert 'Side reference face' in result['files']['trial_0.proc']['metric_resolution']['beta']['reason']


def test_gap_does_not_require_saved_corner_id_or_reference_label():
    frame = posture_frame().drop(columns=[(*SUMMARY, 'CminAtT1MinusIndex'), (*SUMMARY, 'ReferenceFace')])
    result = calculate_posture_metrics(frame)
    assert result.metrics['corner_gap'].value == 0, result.metrics['corner_gap'].reason


def test_unavailable_precontact_pose_is_not_a_numeric_value():
    frame = posture_frame()
    frame.loc[9, ('Info', 'Pose', 'Source')] = 'Failed'
    result = calculate_posture_metrics(frame)
    assert result.metrics['corner_gap'].value is None
    assert result.metrics['beta'].value is None


@pytest.mark.parametrize('fault', ['pose', 'window'])
def test_bad_baseline_context_cannot_hide_valid_same_observation(tmp_path, fault):
    bad = posture_frame()
    if fault == 'pose':
        bad.loc[9, ('Info', 'Pose', 'Source')] = 'Failed'
    else:
        review = json.loads(bad[REVIEW].iloc[0])
        review['detection']['version'] = ''
        bad[REVIEW] = json.dumps(review)
    for order in permutations(range(2)):
        model = load_frames(tmp_path, [posture_frame(), bad], order)
        for name in model.datasets:
            model.set_baseline(name)
            result = model.get_posture_comparison()
            assert result['statistics']['beta']['n'] == 1
            assert result['statistics']['max_beta']['n'] == 1


def test_valid_context_conflicts_are_resolved_before_cohort_gates(tmp_path):
    b = posture_frame(20)
    review = json.loads(b[REVIEW].iloc[0])
    review['detection']['version'] = 'another-valid-definition'
    b[REVIEW] = json.dumps(review)
    for order in permutations(range(3)):
        model = load_frames(tmp_path, [posture_frame(), b, posture_frame(30, 'b'*64)], order)
        for name in model.datasets:
            model.set_baseline(name)
            result = model.get_posture_comparison()
            assert result['statistics']['beta']['n'] == 1
            assert result['statistics']['max_beta']['n'] == (1 if name == 'trial_2.proc' else 0)
            for source in ('trial_0.proc', 'trial_1.proc'):
                assert result['files'][source]['metric_resolution']['max_beta']['status'] == 'conflict'


def test_bad_baseline_scalar_keeps_independently_valid_context(tmp_path):
    bad = posture_frame()
    bad[(*SUMMARY, 'BetaAtT1MinusDeg')] = 999.
    bad[(*SUMMARY, 'MaxBetaDeg')] = 999.
    for order in permutations(range(2)):
        model = load_frames(tmp_path, [bad, posture_frame(20, 'b'*64)], order)
        for name in model.datasets:
            model.set_baseline(name)
            result = model.get_posture_comparison()
            assert result['statistics']['beta'] == dict(n=1, mean=20., min=20., max=20., range=0.)
            assert result['statistics']['max_beta']['n'] == 1


def test_bad_reference_declaration_is_not_a_fallback_context(tmp_path):
    bad = posture_frame()
    bad[(*SUMMARY, 'ReferenceFace')] = 'TOP'
    model = load_frames(tmp_path, [bad, posture_frame(20, 'b'*64)])
    assert model.get_posture_comparison()['statistics']['beta']['n'] == 0
