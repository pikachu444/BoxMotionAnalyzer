"""Independent prescribed marker observations for automatic fixed-edge cycles."""
from copy import deepcopy
from dataclasses import asdict, replace
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from src.analysis.pipeline.data_loader import DataLoader
from src.analysis.pipeline.parser import Parser
from src.analysis.pipeline.scene_detection import (
    DetectionResult, DetectionSettings, Registration, SceneCandidate, detect_scenes,
)
from src.analysis.pipeline.support_cycles import analyze_support_cycle, merge_support_cycles
from src.config.data_columns import FACE_PREFIX_TO_INFO
from src.simulation.corruption_export import write_observations
from src.simulation.marker_fixtures import virtual_profile_32
from src.simulation.scene_fixtures import write_sequence


PEAK_MM = 300. * np.sin(np.deg2rad(15.))


def write_support_observations(folder, *, cycles=1, plateau_s=.4, elevation_mm=0.,
                               case='pivot', peak_deg=15., ramp_s=.8, noise_mm=0.,
                               gap=False, partial=False):
    """Write observations and static registration; production never reads truth files.

    A 300 x 180 x 90 mm box rotates about literal local (-150,-90,z).
    The profile fixes marker locations; no analysis helper supplies expected poses.
    """
    dt = .008
    angles = [0.] * 51  # Actual samples 0 through 0.4 seconds, inclusive.
    ramp_count, plateau_count = round(ramp_s / dt), round(plateau_s / dt)
    u = np.arange(1, ramp_count + 1) / ramp_count
    eased = 10 * u ** 3 - 15 * u ** 4 + 6 * u ** 5
    for repetition in range(cycles):
        if case == 'staircase':
            angles.extend((peak_deg * (repetition + eased)).tolist())
            angles.extend([peak_deg * (repetition + 1)] * plateau_count)
            continue
        angles.extend((peak_deg * eased).tolist())
        angles.extend([peak_deg] * plateau_count)
        if case != 'non_return':
            angles.extend((peak_deg * (1 - eased)).tolist())
            angles.extend([0.] * 50)
        else:
            angles.extend([peak_deg] * 50)
    angles = np.deg2rad(angles)
    times = np.arange(len(angles)) * dt
    if case == 'same_height_different_pose':
        angles = np.deg2rad(5. + 170. * np.clip((times - .4) / ramp_s, 0., 1.))
    c, s = np.cos(angles), np.sin(angles)
    rotations = np.zeros((len(times), 3, 3))
    rotations[:, 0, 0], rotations[:, 0, 1] = c, -s
    rotations[:, 1, 0], rotations[:, 1, 1], rotations[:, 2, 2] = s, c, 1.
    # p + R*(-150,-90,0) = (-150,elevation,0), componentwise.
    origins = np.column_stack((-150. + 150. * c - 90. * s,
                               elevation_mm + 150. * s + 90. * c, np.zeros(len(times))))
    if case == 'center_rotation':
        origins[:] = [0., elevation_mm + 90., 0.]
    elif case == 'moving_pivot':
        origins[:, 0] += 100. * np.sin(angles)
    elif case == 'drag':
        rotations[:] = np.eye(3)
        origins[:] = [0., elevation_mm + 90., 0.]
        origins[:, 0] = 300. * np.sin(angles)
    keep = np.ones(len(times), dtype=bool)
    if gap:
        keep &= ~((times > .9) & (times < 1.1))
    if partial:
        keep &= times >= .72
    trajectory = {'schema_version': 1, 'source_kind': 'handcrafted_dummy',
                  'coordinate_policy': 'world-y-up-box-local-fixed-center-v1',
                  'frame': np.flatnonzero(keep).tolist(), 'time_s': times[keep].tolist(),
                  'body_origin_mm': origins[keep].tolist(), 'rotation_matrix': rotations[keep].tolist()}
    profile = virtual_profile_32()
    events = [] if not noise_mm else [{'kind': 'gaussian_noise', 'channel': 'rigid_body_markers',
        'start_index': 0, 'end_index_exclusive': int(keep.sum()), 'std_mm': noise_mm}]
    root = write_observations(folder, trajectory, profile, {'schema_version': 1, 'events': events}, seed=75075)
    registration = {'version': 1, 'profile': profile, 'floor_y_mm': 0.,
                    'position_tolerance_mm': 1., 'com_offset_mm': None, 'com_inside_box_confirmed': True}
    (root / 'registration.json').write_text(json.dumps(registration), encoding='utf-8')
    return root


def load_support_observations(folder):
    header, raw = DataLoader().load_csv(str(Path(folder) / 'observed.csv'))
    parsed = Parser(FACE_PREFIX_TO_INFO).process(header, raw)
    return detect_scenes(header, raw, parsed, registration=Registration.load(Path(folder) / 'registration.json'))


def _row(result, start=None, end=None, **extra):
    times = result.signals.index.to_numpy(float)
    return {'start': float(times[0] if start is None else times[np.argmin(abs(times - start))]),
            'end': float(times[-1] if end is None else times[np.argmin(abs(times - end))]),
            'left_censored': False, 'right_censored': False, **extra}


def _cycles(result):
    return [candidate for candidate in result.candidates if 'support_cycle_return' in candidate.tags]


@pytest.fixture(scope='module')
def plateau(tmp_path_factory):
    folder = write_support_observations(tmp_path_factory.mktemp('cycle') / 'input')
    return folder, load_support_observations(folder)


def test_public_handling_merges_one_rise_and_return_and_preserves_raw_members(tmp_path):
    folder = write_sequence(tmp_path / 'handling', 'handling')
    result = load_support_observations(folder)
    cycles = _cycles(result)
    assert len(cycles) == 1
    cycle = cycles[0]
    assert [member['motion'] for member in cycle.activity_members] == ['tip_or_rotation', 'stationary', 'tip_or_rotation']
    raw = [c for c in result.activity_candidates if c.id in {m['id'] for m in cycle.activity_members}]
    assert cycle.id == raw[0].id
    assert (cycle.start, cycle.end) == (raw[0].start, raw[-1].end)
    assert all(not item.activity_members for item in result.activity_candidates)
    assert len(result.candidates) == len(result.activity_candidates) - 2
    evidence = analyze_support_cycle(result, _row(result, .4, 2.))
    assert evidence['status'] == 'complete_cycle'
    assert evidence['returned'] is True and evidence['cycle_count'] == 1
    assert evidence['peak_height_mm'] == pytest.approx(PEAK_MM, abs=1e-6)
    assert evidence['return_error_mm'] == pytest.approx(0., abs=1e-6)
    assert evidence['max_origin_displacement_mm'] > 40.  # Centre follows an arc.
    assert [p['phase'] for p in evidence['phases'] if p['phase'] in ('rise', 'fall')] == ['rise', 'fall']
    json.dumps(evidence, allow_nan=False)


def test_plateau_has_rise_resolution_limited_hold_and_return_with_actual_sample_bounds(plateau):
    _, result = plateau
    cycle, = _cycles(result)
    evidence = analyze_support_cycle(result, asdict(cycle))
    assert evidence['status'] == 'complete_cycle'
    assert evidence['peak_height_mm'] == pytest.approx(PEAK_MM, abs=1e-6)
    assert evidence['return_error_mm'] <= 1.
    assert evidence['motion_sequence'] == ['rise', 'fall']
    assert any(p['phase'] == 'steady_within_resolution' and p['start_time_s'] < 1.4 < p['end_time_s'] for p in evidence['phases'])
    times = set(result.signals.index)
    assert all(p['start_time_s'] in times and p['end_time_s'] in times for p in evidence['phases'])
    assert evidence['return_time_s'] in times
    assert cycle.displacement_mm < 1.


def test_elevated_pivot_cycle_keeps_height_above_floor_without_claiming_floor_support(tmp_path):
    result = load_support_observations(write_support_observations(tmp_path / 'input', elevation_mm=100.))
    cycle, = _cycles(result)
    evidence = analyze_support_cycle(result, asdict(cycle))
    assert evidence['geometry_status'] == 'support_unknown'
    assert evidence['status'] == 'complete_cycle'
    assert evidence['peak_height_mm'] == pytest.approx(100. + PEAK_MM, abs=1e-6)


def test_two_returns_stay_two_display_cycles_and_full_range_reports_both(tmp_path):
    result = load_support_observations(write_support_observations(tmp_path / 'input', cycles=2))
    first, second = _cycles(result)
    assert first.end < second.start
    evidence = analyze_support_cycle(result, _row(result))
    assert evidence['status'] == 'multiple_cycles'
    assert evidence['cycle_count'] == 2
    assert len(evidence['return_times_s']) == 2
    assert evidence['return_times_s'][0] < second.start


@pytest.mark.parametrize('options', [dict(gap=True), dict(partial=True), dict(case='non_return'),
    dict(case='center_rotation', elevation_mm=200.), dict(case='moving_pivot'), dict(case='drag'),
    dict(peak_deg=-15.)])
def test_gaps_censored_nonreturns_wrong_pivots_and_penetration_are_not_merged(tmp_path, options):
    result = load_support_observations(write_support_observations(tmp_path / 'input', **options))
    assert _cycles(result) == []
    if options.get('gap'):
        assert any('time_gap' in c.tags for c in result.activity_candidates)
        assert analyze_support_cycle(result, _row(result))['status'] == 'insufficient_tracking'
    if options.get('partial'):
        assert any(c.left_censored for c in result.activity_candidates)


def test_equal_final_height_with_different_box_pose_is_not_a_return(tmp_path):
    result = load_support_observations(write_support_observations(
        tmp_path / 'input', case='same_height_different_pose', elevation_mm=300., ramp_s=2.4))
    evidence = analyze_support_cycle(result, _row(result))
    assert evidence['geometry_status'] == 'support_unknown'
    assert evidence['returned'] is False
    assert evidence['cycle_count'] == 0
    assert evidence['return_error_mm'] > 300.
    corners = result.corners_m[[0, -1], :, 1] * 1000.
    np.testing.assert_allclose(corners[:, [1, 5]].min(axis=1), [300. + 300. * np.sin(np.deg2rad(5.))] * 2, atol=1e-6, rtol=0)


def test_slow_coherent_motion_is_not_steady_merely_because_each_window_change_is_small(tmp_path):
    result = load_support_observations(write_support_observations(
        tmp_path / 'input', ramp_s=8., peak_deg=5., plateau_s=.4))
    evidence = analyze_support_cycle(result, _row(result, 1., 7.5))
    assert evidence['geometry_status'] == 'floor_pivot_compatible'
    assert any(p['phase'] == 'rise' for p in evidence['phases'])
    assert all(p['phase'] != 'steady_within_resolution' for p in evidence['phases'])
    # A short piece has neither enough time support nor a claim of steadiness.
    short = analyze_support_cycle(result, _row(result, 3., 3.024))
    assert short['status'] in ('insufficient_rotation', 'insufficient_window_support')
    assert not any(p['phase'] == 'steady_within_resolution' for p in short['phases'])


def test_low_noise_does_not_turn_peak_hold_into_extra_rise_fall_cycles(tmp_path):
    result = load_support_observations(write_support_observations(tmp_path / 'input', noise_mm=.02))
    evidence = analyze_support_cycle(result, _row(result))
    assert evidence['cycle_count'] == 1
    assert evidence['motion_sequence'] == ['rise', 'fall']
    assert any(p['phase'] == 'steady_within_resolution' and p['start_time_s'] < 1.4 < p['end_time_s'] for p in evidence['phases'])


@pytest.mark.parametrize('motion', ['free_fall', 'tracking_jump', 'unclear', 'robot_handling'])
def test_merging_never_consumes_a_forbidden_raw_interval(plateau, motion):
    result = deepcopy(plateau[1])
    members = _cycles(result)[0].activity_members
    middle = next(c for c in result.activity_candidates if c.id == members[1]['id'])
    middle.motion = motion
    assert all('support_cycle_return' not in c.tags for c in merge_support_cycles(result))


def test_merge_cancellation_interrupts_without_mutating_raw_candidates(plateau):
    result = plateau[1]
    before = [asdict(c) for c in result.activity_candidates]
    with pytest.raises(InterruptedError, match='cancelled'):
        merge_support_cycles(result, cancelled=lambda: True)
    assert [asdict(c) for c in result.activity_candidates] == before


def test_missing_registration_floor_or_corners_returns_raw_candidates_without_analysis(plateau, monkeypatch):
    result = plateau[1]
    before = [asdict(candidate) for candidate in result.activity_candidates]
    def unexpected_analysis(*args, **kwargs):
        pytest.fail('Unavailable registered geometry must not enter prefix analysis.')
    monkeypatch.setattr('src.analysis.pipeline.support_cycles._analyze', unexpected_analysis)
    for unavailable in (replace(result, registration=None),
                        replace(result, registration=replace(result.registration, floor_y_mm=None)),
                        replace(result, corners_m=None)):
        returned = merge_support_cycles(unavailable)
        assert returned is result.activity_candidates
        assert [asdict(candidate) for candidate in returned] == before


@pytest.mark.parametrize('repetitions', [1, 2])
def test_first_raw_candidate_already_containing_returns_never_absorbs_later_unresolved_motion(tmp_path, repetitions):
    result = load_support_observations(write_support_observations(tmp_path / 'input', cycles=repetitions))
    cycles = _cycles(result)
    first = replace(cycles[0], end=cycles[-1].end, tags=[], activity_members=[])
    times = result.signals.index.to_numpy(float)
    after = times[times > first.end]
    split = len(after) // 2
    quiet = SceneCandidate('scene_900', float(after[0]), float(after[split - 1]), 'unclear', 'stationary')
    unresolved = SceneCandidate('scene_901', float(after[split]), float(after[-1]), 'tip_or_rotation', 'tip_or_rotation')
    result.activity_candidates = [first, quiet, unresolved]
    assert analyze_support_cycle(result, asdict(first))['cycle_count'] == repetitions
    assert merge_support_cycles(result) == [first, quiet, unresolved]


@pytest.mark.parametrize('repetitions', [1, 2])
def test_slow_complete_cycles_are_visible_motion_despite_stationary_activity_threshold(tmp_path, repetitions):
    result = load_support_observations(write_support_observations(
        tmp_path / 'input', cycles=repetitions, peak_deg=5., ramp_s=4.))
    original, = result.activity_candidates
    assert original.motion == 'stationary'
    displayed, = result.candidates
    assert displayed.motion == displayed.evidence_class == 'tip_or_rotation'
    assert (displayed.id, displayed.start, displayed.end) == (original.id, original.start, original.end)
    assert displayed.activity_members == [{'id': original.id, 'start': original.start,
                                           'end': original.end, 'motion': 'stationary'}]
    evidence = analyze_support_cycle(result, asdict(displayed))
    assert evidence['cycle_count'] == repetitions
    assert evidence['peak_height_mm'] == pytest.approx(300. * np.sin(np.deg2rad(5.)), abs=1e-6)
    if repetitions == 1:
        assert 'support_cycle_return' in displayed.tags
    else:
        assert 'support_cycle_return' not in displayed.tags
        assert 'support_multiple_cycles' in displayed.tags


def test_noisy_slow_rotation_cannot_be_one_long_steady_phase():
    # Independent physics-review counterexample: small local-window alternating
    # deviations hide a 5-degree trend while every corner follows a real arc.
    times = np.arange(2001) * .008
    angles = np.deg2rad(5. * times / 16. + .02 * np.where(np.arange(2001) % 2 == 0, 1., -1.))
    c, s = np.cos(angles), np.sin(angles)
    rotations = np.zeros((len(times), 3, 3))
    rotations[:, 0, 0], rotations[:, 0, 1] = c, -s
    rotations[:, 1, 0], rotations[:, 1, 1], rotations[:, 2, 2] = s, c, 1.
    origins = np.column_stack((-150. + 150. * c - 90. * s, 150. * s + 90. * c, np.zeros(len(times))))
    local = np.array([[-150., -90., -45.], [150., -90., -45.], [150., 90., -45.], [-150., 90., -45.],
                      [-150., -90., 45.], [150., -90., 45.], [150., 90., 45.], [-150., 90., 45.]])
    corners = np.empty((len(times), 8, 3))
    corners[:, :, 0] = origins[:, None, 0] + c[:, None] * local[:, 0] - s[:, None] * local[:, 1]
    corners[:, :, 1] = origins[:, None, 1] + s[:, None] * local[:, 0] + c[:, None] * local[:, 1]
    corners[:, :, 2] = local[:, 2]
    result = DetectionResult([], pd.DataFrame(index=times), origins / 1000., rotations, corners / 1000.,
                             DetectionSettings(), Registration(virtual_profile_32(), floor_y_mm=0.),
                             np.ones(len(times), dtype=bool), np.zeros(len(times), dtype=int))
    evidence = analyze_support_cycle(result, _row(result))
    assert evidence['return_error_mm'] == pytest.approx(30.521105929, abs=1e-9)
    assert evidence['peak_height_mm'] == pytest.approx(300. * np.sin(np.deg2rad(5.02)), abs=1e-9)
    assert all(phase['phase'] != 'steady_within_resolution' for phase in evidence['phases'])
    assert evidence['phases'] == [{'phase': 'unknown', 'start_time_s': 0., 'end_time_s': 16., 'sample_count': 2001}]


@pytest.mark.parametrize('steps', [4, 8])
def test_nonreturning_staircase_skips_full_analysis_of_impossible_prefixes(tmp_path, monkeypatch, steps):
    import src.analysis.pipeline.support_cycles as module
    full_analysis = module._analyze
    calls = []
    def count_analysis(result, row, cancelled):
        calls.append((row['start'], row['end']))
        return full_analysis(result, row, cancelled)
    monkeypatch.setattr(module, '_analyze', count_analysis)
    result = load_support_observations(write_support_observations(
        tmp_path / 'input', case='staircase', cycles=steps, peak_deg=3., ramp_s=.4, plateau_s=.24))
    assert sum(c.motion == 'tip_or_rotation' for c in result.activity_candidates) == steps
    assert _cycles(result) == []
    raw_bounds = {(c.start, c.end) for c in result.activity_candidates}
    # Each single raw interval still receives its required closed-cycle check.
    # A monotonic staircase can never return to an earlier interval's pose.
    assert all(bounds in raw_bounds for bounds in calls)
    assert len(calls) <= len(result.activity_candidates)
    assert result.candidates == result.activity_candidates
