"""Whole-path geometry from public observations, independent of trial identity.

These prescribed motions establish numerical geometry, not support forces or
ISTA compliance. Truth/event files are never supplied to the production path.
"""
import csv
import hashlib
import json
from copy import deepcopy
from dataclasses import replace

import numpy as np
import pytest
from scipy.spatial.transform import Rotation

from src.analysis.pipeline.artifact_io import read_slice_metadata, save_slice_file, update_slice_box_dimensions
from src.analysis.pipeline.data_loader import DataLoader
from src.analysis.pipeline.parser import Parser
from src.analysis.pipeline.scene_detection import Registration, detect_scenes
from src.analysis.pipeline.scene_review import SceneReviewSession
from src.analysis.pipeline.support_motion import (
    EDGE_TRAVEL_SIGNAL,
    LIFT_SIGNAL,
    support_motion_evidence,
    support_motion_signals,
)
from src.config.data_columns import FACE_PREFIX_TO_INFO
from src.simulation.scene_fixtures import write_sequence


# Analytic geometry of the public 300 x 180 x 90 mm box. Tolerances concern
# floating-point pose fitting of noise-free inputs, not experimental accuracy.
TOL_MM = 1e-6
TOL_DEG = 1e-7
TILT_HEIGHT_MM = 300.0 * np.sin(np.deg2rad(15.0))
CENTER_TURN_TRAVEL_MM = np.sqrt(2.0) * np.hypot(90.0, 45.0)


def load_observations(path, registration_path):
    header, raw = DataLoader().load_csv(str(path))
    parsed = Parser(FACE_PREFIX_TO_INFO).process(header, raw)
    registration = Registration.load(registration_path)
    result = detect_scenes(header, raw, parsed, registration=registration)
    return header, raw, result


@pytest.fixture(scope='module')
def handling(tmp_path_factory):
    folder = write_sequence(tmp_path_factory.mktemp('support') / 'recording', 'handling')
    path = folder / 'observed.csv'
    header, raw, result = load_observations(path, folder / 'registration.json')
    return folder, header, raw, result


def selected_row(result, start, end):
    # Use actual capture-clock samples; decimal stage boundaries may have a
    # different last floating-point bit after concatenating the fixture stages.
    times = result.signals.index.to_numpy(float)
    return {'start': float(times[np.argmin(abs(times - start))]),
            'end': float(times[np.argmin(abs(times - end))]),
            'evidence_status': 'current', 'left_censored': False,
            'right_censored': False}


def measure(result, start, end):
    row = selected_row(result, start, end)
    row['motion_geometry'] = support_motion_evidence(result, row)
    return row, support_motion_signals(result, row)


def test_floor_tilt_return_measures_peak_not_identical_endpoints(handling):
    result = handling[3]
    row, signals = measure(result, .4, 2.0)
    evidence = row['motion_geometry']
    assert evidence['status'] == 'floor_pivot_compatible'
    assert evidence['pivot_edge'] == [0, 4]
    assert evidence['opposite_edge'] == [1, 5]
    assert evidence['fixed_edge_candidates'] == [[0, 4]]
    assert evidence['min_edge_max_travel_mm'] == pytest.approx(0., abs=TOL_MM)
    assert evidence['max_rotation_deg'] == pytest.approx(15., abs=TOL_DEG)
    assert evidence['final_rotation_deg'] == pytest.approx(0., abs=TOL_DEG)
    assert evidence['opposite_edge_max_height_mm'] == pytest.approx(TILT_HEIGHT_MM, abs=TOL_MM)
    height = signals[LIFT_SIGNAL].dropna()
    assert height.iloc[0] == pytest.approx(0., abs=TOL_MM)
    assert height.iloc[-1] == pytest.approx(0., abs=TOL_MM)
    assert height.max() == pytest.approx(TILT_HEIGHT_MM, abs=TOL_MM)
    assert height.idxmax() == pytest.approx(1.2)
    assert signals[EDGE_TRAVEL_SIGNAL].dropna().max() == pytest.approx(0., abs=TOL_MM)
    outside = (signals.index < row['start']) | (signals.index > row['end'])
    assert signals.loc[outside].isna().all().all()


def test_airborne_center_turn_has_no_fixed_edge_despite_return(handling):
    row, signals = measure(handling[3], 3.2, 4.8)
    evidence = row['motion_geometry']
    assert evidence['status'] == 'moving_edges'
    assert evidence['fixed_edge_candidates'] == []
    assert evidence['pivot_edge'] is None
    assert evidence['max_rotation_deg'] == pytest.approx(90., abs=TOL_DEG)
    assert evidence['final_rotation_deg'] == pytest.approx(0., abs=TOL_DEG)
    assert evidence['min_edge_max_travel_mm'] == pytest.approx(CENTER_TURN_TRAVEL_MM, abs=TOL_MM)
    travel = signals[EDGE_TRAVEL_SIGNAL].dropna()
    assert travel.iloc[-1] == pytest.approx(0., abs=TOL_MM)
    assert travel.max() == pytest.approx(CENTER_TURN_TRAVEL_MM, abs=TOL_MM)
    assert signals[LIFT_SIGNAL].isna().all()


def test_floor_drag_moves_every_edge_without_rotation(handling):
    row, signals = measure(handling[3], 6.0, 6.8)
    evidence = row['motion_geometry']
    assert evidence['status'] == 'insufficient_rotation'
    assert evidence['max_rotation_deg'] == pytest.approx(0., abs=TOL_DEG)
    assert evidence['minimum_corner_height_mm'] == pytest.approx(0., abs=TOL_MM)
    assert evidence['min_edge_max_travel_mm'] == pytest.approx(300., abs=TOL_MM)
    assert evidence['pivot_edge'] is None
    assert signals[EDGE_TRAVEL_SIGNAL].dropna().iloc[-1] == pytest.approx(300., abs=TOL_MM)
    assert signals[LIFT_SIGNAL].isna().all()


def variant_csv(handling, tmp_path, *, fault, start_angle_deg=0.):
    """Change observations only; keep the public static registration unchanged."""
    folder = handling[0]
    with (folder / 'observed.csv').open(newline='', encoding='utf-8') as stream:
        rows = list(csv.reader(stream))
    body = rows[8:]
    if fault in ('negative_tilt', 'elevated_edge', 'near_tied_face'):
        # Independent prescribed trajectory about local (-150,-90,z), from
        # zero to +/-15 degrees and back; all markers remain rigidly attached.
        local = np.array([m['xyz_mm'] for m in handling[3].registration.profile['markers']])
        times = np.arange(201) * .008
        angles = 15. * np.sin(np.pi * times / 1.6) ** 2
        if fault == 'negative_tilt':
            angles *= -1
        elif fault == 'near_tied_face':
            angles = start_angle_deg + angles / 3.
        rotations = Rotation.from_euler('z', angles[:, None], degrees=True).as_matrix()
        edge_point = np.array([-150., -90., 0.])
        fixed_world = np.array([-150., 100. if fault == 'elevated_edge' else 0., 0.])
        points = np.einsum('nij,mj->nmi', rotations, local - edge_point) + fixed_world
        body = [[i, t, *markers.ravel()] for i, (t, markers) in enumerate(zip(times, points))]
    elif fault == 'pose_gap':
        for row in body:
            if .9 < float(row[1]) < 1.1:
                row[2:] = [''] * (len(row) - 2)
    elif fault == 'time_gap':
        body = [row for row in body if not .9 < float(row[1]) < 1.1]
    elif fault == 'partial':
        body = [row for row in body if .72 <= float(row[1]) <= 1.68]
    else:
        raise ValueError(fault)
    path = tmp_path / 'observed.csv'
    with path.open('w', newline='', encoding='utf-8') as stream:
        csv.writer(stream).writerows(rows[:8] + body)
    return load_observations(path, folder / 'registration.json')[2]


def test_fixed_edge_does_not_justify_floor_penetration(handling, tmp_path):
    result = variant_csv(handling, tmp_path, fault='negative_tilt')
    row, signals = measure(result, 0., 1.6)
    evidence = row['motion_geometry']
    assert evidence['fixed_edge_candidates'] == [[0, 4]]
    assert evidence['min_edge_max_travel_mm'] == pytest.approx(0., abs=TOL_MM)
    assert evidence['minimum_corner_height_mm'] == pytest.approx(-TILT_HEIGHT_MM, abs=TOL_MM)
    assert evidence['status'] == 'floor_geometry_inconsistent'
    assert evidence['pivot_edge'] is None
    assert signals[LIFT_SIGNAL].isna().all()


def test_elevated_fixed_edge_cannot_establish_floor_support(handling, tmp_path):
    result = variant_csv(handling, tmp_path, fault='elevated_edge')
    row, _ = measure(result, 0., 1.6)
    evidence = row['motion_geometry']
    assert evidence['status'] == 'support_unknown'
    assert evidence['pivot_edge'] == [0, 4]
    assert evidence['pivot_height_mm'] == pytest.approx(100., abs=TOL_MM)
    assert evidence['minimum_corner_height_mm'] == pytest.approx(100., abs=TOL_MM)
    assert evidence['opposite_edge_max_height_mm'] == pytest.approx(100. + TILT_HEIGHT_MM, abs=TOL_MM)


@pytest.mark.parametrize('start_angle_deg', [44.99, 45., 45.01])
def test_nearly_tied_starting_faces_keep_pivot_but_abstain_on_opposite_height(handling, tmp_path, start_angle_deg):
    result = variant_csv(handling, tmp_path, fault='near_tied_face', start_angle_deg=start_angle_deg)
    row, signals = measure(result, 0., 1.6)
    evidence = row['motion_geometry']
    assert evidence['status'] == 'floor_pivot_compatible'
    assert evidence['pivot_edge'] == [0, 4]
    assert evidence['min_edge_max_travel_mm'] == pytest.approx(0., abs=TOL_MM)
    assert evidence['max_rotation_deg'] == pytest.approx(5., abs=TOL_DEG)
    assert evidence['start_face_status'] == 'ambiguous_downward_faces'
    assert evidence['start_face_angle_gap_deg'] < evidence['start_face_ambiguity_deg']
    assert evidence['starting_downward_face'] is None
    assert evidence['opposite_edge'] is None
    assert evidence['opposite_edge_max_height_mm'] is None
    assert signals[LIFT_SIGNAL].isna().all()
    assert signals[EDGE_TRAVEL_SIGNAL].dropna().max() == pytest.approx(0., abs=TOL_MM)


@pytest.mark.parametrize('fault', ['pose_gap', 'time_gap'])
def test_missing_path_cannot_supply_support_evidence(handling, tmp_path, fault):
    result = variant_csv(handling, tmp_path, fault=fault)
    if fault == 'pose_gap':
        assert not result.valid_pose.all()
    else:
        assert np.diff(result.signals.index).max() > .1
    row, signals = measure(result, .4, 2.)
    assert row['motion_geometry']['status'] == 'insufficient_tracking'
    assert 'pivot_edge' not in row['motion_geometry']
    assert signals.isna().all().all()


def test_partial_rotation_retains_censoring_without_trial_identity(handling, tmp_path):
    result = variant_csv(handling, tmp_path, fault='partial')
    session = SceneReviewSession(result, 'a' * 64)
    turning = [row for row in session.rows if row['motion'] == 'tip_or_rotation']
    assert turning
    assert any(row['left_censored'] for row in turning)
    assert any(row['right_censored'] for row in turning)
    for row in turning:
        assert row['motion_geometry']['censored']
        assert not row['identity']['confirmed']
        assert row['item_candidates'] == []


@pytest.mark.parametrize('missing', ['registration', 'floor'])
def test_missing_static_reference_abstains(handling, missing):
    result = handling[3]
    registration = None if missing == 'registration' else replace(result.registration, floor_y_mm=None)
    result = replace(result, registration=registration)
    row, signals = measure(result, .4, 2.)
    assert row['motion_geometry']['status'] == 'registration_required'
    assert signals.isna().all().all()


def test_range_change_invalidates_measurements_and_saved_json_is_preserved(handling, tmp_path):
    folder, header, raw, result = handling
    source = folder / 'observed.csv'
    session = SceneReviewSession(result, hashlib.sha256(source.read_bytes()).hexdigest())
    bounds = selected_row(result, .4, 2.)
    row_id = session.add_range(bounds['start'], bounds['end'])
    session.refresh(result)
    row = session.row(row_id)
    # The whole round trip contains separate automatic motion intervals. New
    # fixed-edge geometry can describe rotation without inventing trial identity.
    assert row['motion'] == 'tip_or_rotation'
    assert row['identity']['scenario_id'] is None
    assert not row['identity']['confirmed']
    assert row['motion_geometry']['opposite_edge_max_height_mm'] == pytest.approx(TILT_HEIGHT_MM, abs=TOL_MM)
    for other in session.rows:
        session.set_decision(other['id'], 'include' if other['id'] == row_id else 'exclude')
    payload = session.payload(row_id)
    path = tmp_path / 'reviewed.slice'
    save_slice_file(filepath=str(path), header_info=header, raw_data=raw,
                    source_path=str(source), full_start=float(result.signals.index[0]),
                    full_end=float(result.signals.index[-1]), user_start=row['start'], user_end=row['end'],
                    box_dims=[300., 180., 90.], pad_rows=0, scene_review_json=payload)
    reopened = json.loads(read_slice_metadata(str(path)).scene_review_json)
    assert reopened == json.loads(payload)
    assert reopened['candidate']['motion_geometry']['pivot_edge'] == [0, 4]
    assert reopened['identity']['scenario_id'] is None
    assert not reopened['identity']['confirmed']

    shorter = selected_row(result, .4, .8)
    session.set_range(row_id, shorter['start'], shorter['end'])
    assert row['motion_geometry']['status'] == 'range_changed'
    assert 'opposite_edge_max_height_mm' not in row['motion_geometry']
    assert support_motion_signals(result, row).isna().all().all()
    with pytest.raises(ValueError, match='Review every'):
        session.payload(row_id)
    session.refresh(result)
    assert row['motion_geometry']['opposite_edge_max_height_mm'] == pytest.approx(
        300. * np.sin(np.deg2rad(7.5)), abs=TOL_MM)
    assert row['motion_geometry']['censored']
    # A later range edit cannot mutate the already saved measurement record.
    assert json.loads(read_slice_metadata(str(path)).scene_review_json) == reopened

    # Declared source dimensions cannot be silently rewritten.
    before = path.read_bytes()
    with pytest.raises(ValueError, match='conflict with declared artifact'):
        update_slice_box_dimensions(str(path), (310., 180., 90.))
    assert path.read_bytes() == before
    # Older sources without declared dimensions allow operator correction;
    # their saved support measurements must then become invalid.
    legacy_header = deepcopy(header)
    for name in ('BoxLengthMm', 'BoxWidthMm', 'BoxHeightMm'):
        legacy_header['artifact_metadata'][name] = None
    legacy_path = tmp_path / 'undeclared_dimensions.slice'
    save_slice_file(filepath=str(legacy_path), header_info=legacy_header, raw_data=raw,
                    source_path=str(source), full_start=float(result.signals.index[0]),
                    full_end=float(result.signals.index[-1]), user_start=bounds['start'], user_end=bounds['end'],
                    box_dims=[300., 180., 90.], pad_rows=0, scene_review_json=payload)
    update_slice_box_dimensions(str(legacy_path), (310., 180., 90.))
    changed = json.loads(read_slice_metadata(str(legacy_path)).scene_review_json)
    assert changed['candidate']['motion_geometry'] == {'version': 1, 'status': 'geometry_changed'}
    assert changed['candidate']['evidence_status'] == 'geometry_changed'
    assert not changed['identity']['confirmed']
