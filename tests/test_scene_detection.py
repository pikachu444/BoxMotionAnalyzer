"""Observed-motion acceptance with independent synthetic stage/contact truth."""
from copy import deepcopy
import json

import numpy as np
import pandas as pd
import pytest
from scipy.spatial.transform import Rotation

from src.analysis.pipeline.scene_detection import detect_scenes, Registration
from src.analysis.pipeline.scene_review import SceneReviewSession
from src.config.data_columns import TimeCols
from src.simulation.scene_fixtures import make_sequence


def inputs(data):
    times = data['time_s']
    columns = {}
    for j, marker in enumerate(data['registration']['profile']['markers']):
        mid = marker['id']
        for k, axis in enumerate('XYZ'):
            columns[f'{mid}_{axis}'] = data['observed_markers_mm'][:, j, k]
        columns[f'{mid}_FaceInfo'] = 'unused by detector'
    parsed = pd.DataFrame(columns, index=times)
    raw = pd.DataFrame({TimeCols.TIME: times, TimeCols.FRAME: data['frame']})
    header = {'export_metadata': {'Length Units': 'Millimeters', 'Coordinate Space': 'Global'}}
    registration = Registration(data['registration']['profile'], 0., 1., (0, 0, 0))
    return header, raw, parsed, registration


@pytest.fixture(scope='module')
def captures():
    # Generation and analysis have separate data interfaces. The event record is
    # consulted below only after the detector has returned.
    return {case: make_sequence(case) for case in ('drops', 'handling', 'tracking', 'partial')}


@pytest.fixture(scope='module')
def detected(captures):
    results = {}
    for case, data in captures.items():
        header, raw, parsed, registration = inputs(data)
        results[case] = detect_scenes(header, raw, parsed, registration=registration)
    return results


def test_two_releases_remain_two_candidates_including_recontacts(captures, detected):
    falls = [c for c in detected['drops'].candidates if c.evidence_class == 'free_fall']
    assert len(falls) == 2
    # Independent MuJoCo release and force onset lie inside each reported interval.
    for candidate, event in zip(falls, captures['drops']['manifest']['events']):
        assert candidate.start <= event['release_time_s'] <= candidate.end
        assert candidate.start <= event['first_contact_time_s'] <= candidate.end
        assert not candidate.left_censored and not candidate.right_censored
        assert candidate.gravity_episodes
    assert any(c.motion == 'robot_handling' for c in detected['drops'].candidates)


def test_similar_handling_has_no_free_fall_or_automatic_trial_identity(detected):
    result = detected['handling']
    assert not any(c.motion == 'free_fall' for c in result.candidates)
    rotations = [c for c in result.candidates if c.motion == 'tip_or_rotation']
    assert any(14 < c.rotation_deg < 16 for c in rotations)
    assert any(89 < c.rotation_deg < 91 for c in rotations)
    assert any(c.motion == 'robot_handling' and c.start > 6 for c in result.candidates)
    assert not any(c.motion == 'tracking_jump' for c in result.candidates)


def test_subset_changes_and_smooth_half_turn_are_not_tracking_jumps(captures, detected):
    result = detected['tracking']
    jump_times = [(c.start, c.end) for c in result.candidates if c.motion == 'tracking_jump']
    assert len(jump_times) == 4  # entry/exit of two deliberately corrupted intervals
    assert all(start >= 3.19 for start, _ in jump_times)
    assert any(c.motion == 'tip_or_rotation' and c.rotation_deg > 179 for c in result.candidates)
    gap = (result.signals.index >= 1.28) & (result.signals.index < 1.36)
    assert not result.valid_pose[gap].any()
    assert np.isnan(result.corners_m[~result.valid_pose]).all()
    assert np.nanmax(result.signals['Marker fit RMS (mm)'].to_numpy()[:160]) < 1e-8


def test_partial_record_keeps_both_events_and_censored_boundaries(detected):
    falls = [c for c in detected['partial'].candidates if c.motion == 'free_fall']
    assert len(falls) == 2
    assert falls[0].left_censored and not falls[0].right_censored
    assert falls[1].right_censored and not falls[1].left_censored


def test_unregistered_gravity_translation_abstains(captures):
    header, raw, parsed, _ = inputs(captures['drops'])
    result = detect_scenes(header, raw, parsed)
    assert not any(c.motion == 'free_fall' for c in result.candidates)
    falling_candidates = [c for c in result.candidates if 'gravity_like_translation_rotation_unverified' in c.tags]
    assert len(falling_candidates) == 2
    assert all(c.evidence_class == 'unclear' and 'tracking_unavailable' not in c.tags for c in falling_candidates)


def test_time_gap_does_not_supply_rotation_or_gravity_across_blocks(captures):
    header, raw, parsed, reg = inputs(captures['drops'])
    # Two constant-speed translations separated by unobserved reorientation.
    times = np.r_[np.arange(50) * .008, 1 + np.arange(50) * .008]
    local = np.asarray([m['xyz_mm'] for m in reg.profile['markers']])
    positions = np.tile([0., 500., 0.], (100, 1))
    positions[:, 0] = times * 100
    rotations = np.tile(np.eye(3), (100, 1, 1))
    rotations[50:] = Rotation.from_euler('x', 90, degrees=True).as_matrix()
    data = deepcopy(captures['drops'])
    data.update(time_s=times, frame=np.arange(100), observed_markers_mm=np.einsum('nij,mj->nmi', rotations, local) + positions[:, None])
    header, raw, parsed, reg = inputs(data)
    result = detect_scenes(header, raw, parsed, registration=reg)
    assert not any(c.motion in ('tip_or_rotation', 'free_fall', 'tracking_jump') for c in result.candidates)
    assert any('time_gap' in c.tags for c in result.candidates)
    assert np.isnan(result.signals['Vertical speed (mm/s)']).sum() == 0


def test_round_trip_rotation_with_zero_net_turn_is_visible(captures):
    data = deepcopy(captures['drops'])
    t = np.arange(151) * .008
    rotations = Rotation.from_euler('x', 10 * np.sin(2 * np.pi * t / .08), degrees=True).as_matrix()
    local = np.asarray([m['xyz_mm'] for m in data['registration']['profile']['markers']])
    data.update(time_s=t, frame=np.arange(len(t)), observed_markers_mm=np.einsum('nij,mj->nmi', rotations, local) + [0, 500, 0])
    h, raw, parsed, reg = inputs(data)
    result = detect_scenes(h, raw, parsed, registration=reg)
    assert any(c.motion == 'tip_or_rotation' for c in result.candidates)
    assert not any(c.motion == 'free_fall' for c in result.candidates)


@pytest.mark.parametrize('fault', ['all_missing', 'wrong_units', 'reversed_time', 'collinear', 'unmatched_ids'])
def test_unusable_input_is_rejected(captures, fault):
    h, raw, parsed, reg = inputs(captures['drops'])
    if fault == 'all_missing':
        parsed.loc[:, [c for c in parsed if not c.endswith('FaceInfo')]] = np.nan
        reg = None
    elif fault == 'wrong_units':
        h['export_metadata']['Length Units'] = 'Meters'
    elif fault == 'reversed_time':
        raw.loc[20, TimeCols.TIME] = raw.loc[19, TimeCols.TIME]
    else:
        profile = deepcopy(reg.profile)
        for i, marker in enumerate(profile['markers']):
            if fault == 'collinear':
                marker['xyz_mm'] = [i, 0, 0]
            else:
                marker['id'] = 'other_' + marker['id']
        reg = Registration(profile)
    with pytest.raises(ValueError):
        detect_scenes(h, raw, parsed, registration=reg)


def test_truth_content_never_changes_observed_detection(captures, detected):
    data = deepcopy(captures['partial'])
    data['manifest'] = {'case': 'G17', 'events': [{'fake': True}]}
    data['truth_markers_mm'][:] = 999999
    h, raw, parsed, reg = inputs(data)
    again = detect_scenes(h, raw, parsed, registration=reg)
    assert again.candidates == detected['partial'].candidates


def test_review_gate_ambiguous_h_face_and_range_invalidation(detected):
    session = SceneReviewSession(detected['drops'], 'a' * 64)
    with pytest.raises(ValueError, match='Review every'):
        session.identify()
    session.set_context('H', '2018-03')
    for row in session.rows:
        session.set_decision(row['id'], 'include' if row['motion'] == 'free_fall' else 'exclude')
    session.identify()
    row = next(r for r in session.rows if r['decision'] == 'include')
    assert row['item_candidates'] == ['H/B04/D06', 'H/B16/D06']
    assert not row['identity']['confirmed']
    # Confirmation is a distinct operator decision, not a first-candidate default.
    session.confirm_item(row['id'], 'H/B16/D06')
    payload = json.loads(session.payload(row['id']))
    assert payload['identity']['confirmed']
    session.set_range(row['id'], row['start'] + .008, row['end'])
    assert row['decision'] == 'unreviewed'
    assert not row['identity']['confirmed'] and not row['item_candidates']
    with pytest.raises(ValueError):
        session.payload(row['id'])


def test_redetect_keeps_manual_ranges_exclusion_and_deletion(detected):
    session = SceneReviewSession(detected['drops'], 'b' * 64)
    manual = session.add_range(.3, .8)
    session.set_decision(manual, 'exclude')
    removed = session.rows[0]['id']
    session.remove(removed)
    session.refresh(detected['drops'])
    assert session.row(manual)['start'] == .3
    assert session.row(manual)['decision'] == 'exclude'
    assert removed not in [r['id'] for r in session.rows]
    assert removed in session.deleted_ids


def test_partial_scene_cannot_be_confirmed_by_deleting_and_readding_it(detected):
    session = SceneReviewSession(detected['partial'], 'c' * 64)
    first = session.rows[0].copy()
    session.remove(first['id'])
    manual = session.add_range(first['start'], first['end'])
    session.refresh(detected['partial'])
    session.set_context('H', '2018-03')
    for row in session.rows:
        session.set_decision(row['id'], 'include' if row['id'] == manual else 'exclude')
    session.identify()
    row = session.row(manual)
    assert row['left_censored'] and not row['right_censored']
    assert row['gravity_evidence_start'] >= row['start']
    assert row['gravity_evidence_end'] <= row['end']
    assert not row['item_candidates']
    with pytest.raises(ValueError):
        session.confirm_item(manual, 'H/B04/D06')
    session.set_range(manual, 1.70, 1.72)
    session.refresh(detected['partial'])
    assert row['gravity_evidence_start'] is None and row['gravity_evidence_end'] is None
    assert row['gravity_episodes'] == []
