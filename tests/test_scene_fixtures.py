"""Generator contracts only: no scene detector or detector-derived oracle."""
import hashlib
import json
from itertools import product

import numpy as np
import pandas as pd
import pytest
from scipy.spatial.transform import Rotation

from src.simulation.scene_fixtures import CASES, DT, make_sequence, write_sequence


def _heights(data):
    corners = np.asarray(list(product((-1, 1), repeat=3))) * [150, 90, 45]
    return (np.einsum("nij,mj->nmi", data["rotation_matrix"], corners) + data["origin_mm"][:, None, :])[:, :, 1]


@pytest.mark.parametrize("case", CASES)
def test_sequence_clock_geometry_and_observation_separation(case):
    data = make_sequence(case)
    np.testing.assert_allclose(np.diff(data["time_s"]), DT, rtol=0, atol=1e-12)
    np.testing.assert_array_equal(np.diff(data["frame"]), 1)
    np.testing.assert_array_equal(data["origin_mm"], data["com_mm"])
    r = data["rotation_matrix"]
    np.testing.assert_allclose(r.transpose(0, 2, 1) @ r, np.broadcast_to(np.eye(3), r.shape), atol=1e-12)
    np.testing.assert_allclose(np.linalg.det(r), 1, atol=1e-12)
    local = np.array([m["xyz_mm"] for m in data["registration"]["profile"]["markers"]])
    independently_transformed = np.stack([Rotation.from_matrix(matrix).apply(local) + origin
                                        for origin, matrix in zip(data["origin_mm"], r)])
    np.testing.assert_allclose(data["truth_markers_mm"], independently_transformed, atol=1e-10)
    assert not np.shares_memory(data["truth_markers_mm"], data["observed_markers_mm"])
    assert set(data["registration"]) == {"version", "profile", "floor_y_mm", "position_tolerance_mm", "com_offset_mm"}


def test_two_real_releases_preserve_actual_clock_and_bounce_is_not_another_drop():
    data = make_sequence("drops")
    assert len(data["time_s"]) == 751
    events = data["manifest"]["events"]
    assert len(events) == 2 and all(e["kind"] == "drop" for e in events)
    heights = _heights(data)
    for event, expected_release in zip(events, (1.6, 4.4)):
        assert event["release_time_s"] == pytest.approx(expected_release, abs=1e-12)
        first = event["release_frame"]
        impact = event["first_contact_frame"]
        np.testing.assert_allclose(data["origin_mm"][first], data["origin_mm"][first - 1], atol=1e-12)
        # Four 2 ms semi-implicit gravity steps start from the held pose with
        # zero velocity. The first saved fall is 0.3924 mm, not a teleport.
        first_fall_mm = 9.81 * 1000 * 0.002**2 * sum(range(1, 5))
        np.testing.assert_allclose(data["origin_mm"][first + 1] - data["origin_mm"][first],
                                   [0, -first_fall_mm, 0], atol=1e-10)
        np.testing.assert_allclose(heights[first].min(), 100, atol=1e-10)
        assert np.count_nonzero(np.isclose(heights[first], 100)) == 4
        assert data["manifest"]["contact_force_n"][first] == 0
        assert data["manifest"]["contact_force_n"][impact] > 0
        assert len(event["contact_episode_start_frames"]) >= 2
        assert heights[impact:event["end_frame"]].min() < 0  # Soft penetration is preserved.
        assert heights[impact + 1:event["end_frame"]].min(axis=1).max() > 0  # Actual rebound.
        bracket = event["contact_onset_bracket_s"]
        assert bracket[1] - bracket[0] == pytest.approx(DT, abs=1e-12)
    np.testing.assert_allclose(data["rotation_matrix"][events[0]["release_frame"]],
                               data["rotation_matrix"][events[1]["release_frame"]], atol=1e-12)
    for stage in data["manifest"]["stages"]:
        if stage["source"] == "mujoco_dynamic":
            local = stage["parameters"]["actual_engine_time_s"]
            np.testing.assert_allclose(data["time_s"][stage["start_frame"]:stage["end_frame"] + 1],
                                       stage["start_time_s"] + np.array(local), atol=1e-12)
            assert all(model["margin_m"] == 0 for model in stage["parameters"]["contact_model"])


def test_prescribed_supported_tilt_airborne_rotation_and_floor_drag():
    data = make_sequence("handling")
    heights = _heights(data)
    assert data["manifest"]["source_kind"] == "handcrafted_dummy"
    assert all(s["source"] == "prescribed_kinematic" for s in data["manifest"]["stages"])
    for stage in data["manifest"]["stages"]:
        a, b = stage["start_frame"], stage["end_frame"] + 1
        if stage["label"] == "supported_tilt":
            np.testing.assert_allclose(heights[a:b].min(axis=1), 0, atol=1e-10)
            interior = heights[a + 1:b - 1]
            np.testing.assert_array_equal(np.isclose(interior, 0, atol=1e-10).sum(axis=1), 2)
        if stage["label"].startswith("airborne_reorientation"):
            assert heights[a:b].min() > 250
        if stage["label"] == "floor_horizontal_drag":
            np.testing.assert_allclose(heights[a:b].min(axis=1), 0, atol=1e-10)
            assert data["origin_mm"][b - 1, 0] - data["origin_mm"][a, 0] == pytest.approx(300)
    np.testing.assert_allclose(Rotation.from_matrix(data["rotation_matrix"][150]).magnitude(), np.radians(15), atol=1e-12)
    assert all(e["expected_drop"] is False for e in data["manifest"]["events"])


def test_tracking_corruption_does_not_change_smooth_truth_or_use_subset_centroids():
    data = make_sequence("tracking")
    truth, observed = data["truth_markers_mm"], data["observed_markers_mm"]
    assert np.isfinite(observed[60:140]).all(axis=2).sum(axis=1).tolist() == [16] * 80
    np.testing.assert_array_equal(np.isfinite(observed[99]).all(axis=1), ~np.isfinite(observed[100]).all(axis=1))
    assert np.isnan(observed[160:170]).all()
    local = np.array([m["xyz_mm"] for m in data["registration"]["profile"]["markers"]])
    expected = local @ (data["rotation_matrix"][400] @ np.diag([1, -1, -1])).T + data["origin_mm"][400]
    np.testing.assert_allclose(observed[400], expected, atol=1e-10)
    np.testing.assert_allclose(observed[450], truth[450], atol=1e-10)
    np.testing.assert_allclose(observed[490] - truth[490], np.broadcast_to([120, 0, -60], (32, 3)), atol=1e-10)
    np.testing.assert_allclose(observed[520], truth[520], atol=1e-10)
    r = Rotation.from_matrix(data["rotation_matrix"])
    assert np.degrees((r[200].inv() * r[350]).magnitude()) == pytest.approx(180, abs=1e-10)
    assert np.degrees((r[:-1].inv() * r[1:]).magnitude()).max() < 3
    np.testing.assert_allclose(observed[200:351], truth[200:351], atol=1e-10)


def test_partial_capture_censors_release_and_final_contact_without_retiming():
    full, partial = make_sequence("drops"), make_sequence("partial")
    for key in ("time_s", "frame", "origin_mm", "rotation_matrix", "truth_markers_mm", "observed_markers_mm"):
        np.testing.assert_array_equal(partial[key], full[key][208:563])
    assert partial["frame"][[0, -1]].tolist() == [208, 562]
    first, last = partial["manifest"]["events"]
    assert first["start_censored"] and not first["end_censored"]
    assert not last["start_censored"] and last["end_censored"]
    assert first["release_time_s"] < partial["time_s"][0] < first["first_contact_time_s"]
    assert last["release_time_s"] < partial["time_s"][-1] < last["first_contact_time_s"]


def test_written_detector_inputs_have_no_scene_or_fault_answers_and_truth_hashes_match(tmp_path):
    root = write_sequence(tmp_path / "recording", "tracking")
    import csv
    with (root / "observed.csv").open(newline="", encoding="utf-8") as f:
        rows = list(csv.reader(f))
    artifact = json.loads(rows[0][rows[0].index("Artifact Metadata") + 1])
    assert artifact["ScenarioId"] is None and artifact["ScenarioKind"] is None and artifact["IstaType"] is None
    assert len(rows) - 8 == 601
    registration = json.loads((root / "registration.json").read_text())
    assert set(registration) == {"version", "profile", "floor_y_mm", "position_tolerance_mm", "com_offset_mm"}
    report = json.loads((root / "truth_events.json").read_text())
    assert report["corruptions"] and report["events"]
    for name, digest in report["files"].items():
        assert hashlib.sha256((root / name).read_bytes()).hexdigest() == digest
    truth = pd.read_csv(root / "truth_pose.csv")
    np.testing.assert_allclose(np.diff(truth.time_s), DT, atol=1e-12)
    np.testing.assert_allclose(np.linalg.norm(truth[["q_w", "q_x", "q_y", "q_z"]], axis=1), 1, atol=1e-12)


def test_seed_changes_only_explicit_observation_noise():
    clean = make_sequence("tracking")
    noisy = make_sequence("tracking", seed=1, noise_std_mm=0.02)
    again = make_sequence("tracking", seed=1, noise_std_mm=0.02)
    other = make_sequence("tracking", seed=2, noise_std_mm=0.02)
    np.testing.assert_array_equal(clean["truth_markers_mm"], noisy["truth_markers_mm"])
    np.testing.assert_array_equal(noisy["truth_markers_mm"], other["truth_markers_mm"])
    np.testing.assert_array_equal(noisy["observed_markers_mm"], again["observed_markers_mm"])
    assert not np.allclose(noisy["observed_markers_mm"], other["observed_markers_mm"], equal_nan=True)
    with pytest.raises(ValueError):
        make_sequence("missing")
    with pytest.raises(ValueError):
        make_sequence("drops", noise_std_mm=-1)
