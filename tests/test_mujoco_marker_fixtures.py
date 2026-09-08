import copy
import json
import hashlib
import numpy as np
import pytest
from scipy.spatial.transform import Rotation

from src.simulation.marker_fixtures import (example_profile, validate_profile, record_truth,
    make_case, write_case, WORLD_TO_ANALYSIS)
from src.simulation.engine.mujoco_engine import MuJoCoEngine


def test_actual_time_and_fresh_origin_com_rotation_sites():
    engine = MuJoCoEngine(size=(200, 120, 80), mass=1., com_offset=(3, -4, 2))
    engine.init_pos = [.12, -.23, 4.]
    q = Rotation.from_euler('xyz', [.2, -.3, .4]).as_quat()
    engine.init_quat = q[[3, 0, 1, 2]]
    history = engine.record_samples(8, 4)
    np.testing.assert_allclose([f['time'] for f in history], np.arange(8) * .008, atol=1e-14)
    last = history[-1]
    np.testing.assert_allclose(last['BodyOrigin'], engine.data.qpos[:3] * 1000., atol=1e-10)
    np.testing.assert_allclose(last['COM'] - last['BodyOrigin'], last['RotationMatrix'] @ [3., -4., 2.], atol=1e-10)
    np.testing.assert_allclose(last['C1'], last['BodyOrigin'] + last['RotationMatrix'] @ [-100., -60., -40.], atol=1e-10)
    snapshot = last['BodyOrigin'].copy()
    engine.data.qpos[:3] += 1
    np.testing.assert_array_equal(last['BodyOrigin'], snapshot)


def test_existing_simulation_loop_uses_actual_clock():
    engine = MuJoCoEngine(size=(200, 120, 80), mass=1.)
    engine.init_pos = [0, 0, 4]
    frames = engine.run_simulation(target_fps=120, stop_condition_time=.024)
    np.testing.assert_allclose([f['time'] for f in frames], [0., .008, .016], atol=1e-12)


def test_world_change_keeps_local_basis_and_round_trips():
    history, _ = record_truth(samples=4)
    frame = history[2]
    matrix = WORLD_TO_ANALYSIS @ frame['RotationMatrix']
    np.testing.assert_allclose(matrix.T @ matrix, np.eye(3), atol=1e-12)
    assert np.isclose(np.linalg.det(matrix), 1.)
    local = np.array([21., 12., 40.])
    observed = WORLD_TO_ANALYSIS @ (frame['BodyOrigin'] + frame['RotationMatrix'] @ local)
    np.testing.assert_allclose(matrix.T @ (observed - WORLD_TO_ANALYSIS @ frame['BodyOrigin']), local, atol=1e-10)
    assert not np.allclose(matrix, WORLD_TO_ANALYSIS @ frame['RotationMatrix'] @ WORLD_TO_ANALYSIS.T)


def test_profile_validation_hash_and_independent_oracle():
    profile = example_profile()
    assert validate_profile(profile) == validate_profile(json.loads(json.dumps(profile)))
    changed = copy.deepcopy(profile)
    changed['markers'][0]['xyz_mm'][0] += 1
    assert validate_profile(changed) != validate_profile(profile)
    changed['markers'][0]['xyz_mm'][2] += 1
    with pytest.raises(ValueError, match='assigned face'):
        validate_profile(changed)
    clean = make_case('healthy')
    x = make_case('x')
    # Independent expected matrix, not the corruption operator or detector result.
    h = np.diag([1., -1., -1.])
    local = np.array([m['xyz_mm'] for m in profile['markers']])
    expected = local @ (clean[4][30] @ h).T + clean[2][30]
    np.testing.assert_allclose(x[-1][30], expected, atol=1e-10)
    for a, b in zip(clean[1:-1], x[1:-1]):
        np.testing.assert_array_equal(a, b)
    np.testing.assert_array_equal(x[-1][:30], clean[-1][:30])
    xx = make_case('xx')
    np.testing.assert_allclose(xx[-1][65:], clean[-1][65:], atol=1e-10)
    xy = make_case('xy')
    expected_xy = local @ (clean[4][65] @ np.diag([-1., -1., 1.])).T + clean[2][65]
    np.testing.assert_allclose(xy[-1][65], expected_xy, atol=1e-10)


def test_seeded_noise_and_files_do_not_change_truth(tmp_path):
    first = make_case('noise', seed=2)
    again = make_case('noise', seed=2)
    other = make_case('noise', seed=3)
    np.testing.assert_array_equal(first[-1], again[-1])
    assert not np.array_equal(first[-1], other[-1])
    np.testing.assert_array_equal(first[-2], other[-2])
    root = write_case(tmp_path, 'gap_x')
    manifest = json.loads((root / 'observed.synthetic.json').read_text())
    assert set(manifest['files']) == {'observed.csv', 'truth_pose.csv', 'truth_markers.csv'}
    assert all(hashlib.sha256((root / name).read_bytes()).hexdigest() == digest
               for name, digest in manifest['files'].items())
    assert 'solver_pose_half_turn' not in (root / 'observed.csv').read_text()
    assert manifest['expected_flip_frames'] == [30]


def test_pose_error_oracle_rejects_wrong_axis_and_origin(tmp_path):
    import pandas as pd
    from src.simulation.validate_marker_fixtures import pose_error, POSE_COLUMNS, SourceCols
    root = write_case(tmp_path, 'healthy')
    truth = pd.read_csv(root / 'truth_pose.csv')
    matrices = truth[[f'r{i}{j}' for i in range(3) for j in range(3)]].to_numpy().reshape(-1, 3, 3)
    positions = truth[[f'body_{a}_mm' for a in 'xyz']].to_numpy()
    wrong_rotations = matrices @ np.diag([1., -1., -1.])
    wrong = pd.DataFrame(np.column_stack([positions + [1., 0., 0.],
                         Rotation.from_matrix(wrong_rotations).as_rotvec()]), columns=POSE_COLUMNS)
    wrong[SourceCols.POSE] = 'Optimized'
    errors = pose_error(wrong, truth)
    assert np.isclose(errors['max_position_mm'], 1.)
    assert np.isclose(errors['max_rotation_deg'], 180.)


def test_two_constraints_cannot_produce_usable_pose_or_flip_candidate(tmp_path):
    from src.simulation.validate_marker_fixtures import validate_case
    root = write_case(tmp_path, 'low_coverage')
    result = validate_case(root)
    assert result['raw_pose_error']['valid_frames'] == 0
    assert result['candidates'] == []
    assert result['checks']['insufficient_pose_unavailable']
