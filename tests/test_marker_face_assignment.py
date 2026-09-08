import json
import numpy as np
import pandas as pd
import pytest
from scipy.spatial.transform import Rotation as R

from marker_face_fixtures import DIMS, BASE_FACES, raw_bundle, write_raw, context_json
from src.analysis.pipeline.face_assignment import materialize_face_assignments, face_columns, FaceAssignmentAnalyzer, POSE_COLUMNS
from src.analysis.pipeline.marker_flip import MarkerCorrectionDecision, MarkerFlipAnalyzer
from src.analysis.pipeline.parser import Parser
from src.analysis.pipeline.data_loader import DataLoader
from src.analysis.pipeline.pose_optimizer import PoseOptimizer
from src.analysis.pipeline.artifact_io import (save_corrected_source_file, save_slice_file,
    read_corrected_source_metadata, read_slice_metadata, _sha256_file)
from src.config import config_app
from src.config.data_columns import FACE_PREFIX_TO_INFO, SourceCols


def decision(axis="X", time=.3, event="event-30", approved=True):
    return MarkerCorrectionDecision(event, time, approved, axis if approved else None,
        correction_kind="face_assignment", algorithm_version="3.0", gate_version="face-validation-pending")


@pytest.mark.parametrize("axis", ["X", "Y", "Z"])
def test_unequal_asymmetric_faces_restore_analysis_pose_without_changing_xyz(axis):
    header, raw, truth = raw_bundle(axis)
    fixed_header, fixed = materialize_face_assignments(header, raw, [decision(axis)], BASE_FACES)
    pd.testing.assert_frame_equal(fixed.iloc[:, :raw.shape[1]], raw)
    parsed = Parser(FACE_PREFIX_TO_INFO).process(fixed_header, fixed)
    pose = PoseOptimizer(config_app.FACE_DEFINITIONS, config_app.calculate_local_box_corners(DIMS)).process(parsed, DIMS)
    values = pose[list(POSE_COLUMNS)].to_numpy()
    assert pose[SourceCols.POSE].eq("Optimized").all()
    assert np.max(np.linalg.norm(values[:, :3] - truth[:, :3], axis=1)) < .1
    error = (R.from_rotvec(truth[:, 3:]).inv() * R.from_rotvec(values[:, 3:])).magnitude()
    assert np.max(np.degrees(error)) < .1


def test_cumulative_faces_and_repeated_save():
    header, raw, _ = raw_bundle()
    h, out = materialize_face_assignments(header, raw, [decision(), decision(time=.6, event="second")], BASE_FACES)
    for mid, col in face_columns(h).items():
        assert out.iloc[65, col] == BASE_FACES[mid]
    h2, again = materialize_face_assignments(h, out, [decision(), decision(time=.6, event="second")], BASE_FACES)
    pd.testing.assert_frame_equal(out, again)
    h3, mixed = materialize_face_assignments(header, raw, [decision(), decision("Y", .6, "second")], BASE_FACES)
    # Explicit oracle: X then Y gives Z: front remains front, right becomes left.
    assert mixed.iloc[65, face_columns(h3)["F1"]] == "FRONT"
    assert mixed.iloc[65, face_columns(h3)["R1"]] == "LEFT"


def test_v3_corrected_and_suffix_slice_roundtrip(tmp_path):
    header, raw, _ = raw_bundle()
    original = tmp_path / "input.csv"
    write_raw(original, header, raw)
    h, fixed = materialize_face_assignments(header, raw, [decision()], BASE_FACES)
    target = tmp_path / "input.corrected.csv"
    meta = save_corrected_source_file(filepath=str(target), header_info=h, raw_data=fixed,
        original_source_path=str(original), decisions=[decision()], context_json=context_json(_sha256_file(str(original))))
    assert read_corrected_source_metadata(str(target)) == meta
    loaded_header, loaded_raw = DataLoader().load_csv(str(target))
    parsed = Parser(FACE_PREFIX_TO_INFO).process(loaded_header, loaded_raw)
    assert parsed.loc[.4, "F1_FaceInfo"] == "BACK"
    sliced = tmp_path / "suffix.slice"
    save_slice_file(filepath=str(sliced), header_info=loaded_header, raw_data=loaded_raw,
        source_path=str(target), full_start=0., full_end=.79, user_start=.4, user_end=.7,
        pad_rows=0, box_dims=DIMS, marker_correction_metadata=meta)
    sh, sr = DataLoader().load_csv(str(sliced))
    assert Parser(FACE_PREFIX_TO_INFO).process(sh, sr).iloc[0]["F1_FaceInfo"] == "BACK"
    assert read_slice_metadata(str(sliced)).correction_context_json == meta.context_json


def test_failed_pose_and_duplicate_time_not_valid_evidence():
    header, raw, _ = raw_bundle()
    parsed = Parser(FACE_PREFIX_TO_INFO).process(header, raw)
    pose = parsed.copy()
    for col in POSE_COLUMNS:
        pose[col] = 0.
    pose[SourceCols.POSE] = "OptimizationFailed"
    assert MarkerFlipAnalyzer._valid_pose_positions(pose).size == 0
    parsed.index = pose.index = [0.] * len(pose)
    with pytest.raises(ValueError, match="strictly increasing"):
        MarkerFlipAnalyzer().detect(parsed, pose, DIMS)


def test_face_review_has_no_automatic_recommendation():
    header, raw, _ = raw_bundle(samples=45, boundary=20)
    parsed = Parser(FACE_PREFIX_TO_INFO).process(header, raw)
    pose = PoseOptimizer(config_app.FACE_DEFINITIONS, config_app.calculate_local_box_corners(DIMS)).process(parsed, DIMS)
    candidates = FaceAssignmentAnalyzer().detect(parsed, pose, DIMS)
    assert candidates
    assert all(c.correction_kind == "face_assignment" and c.recommendation_axis is None for c in candidates)
    assert any(c.hypothesis("X") and c.hypothesis("X").applicable for c in candidates)


def test_source_changed_after_load_refuses_save(tmp_path):
    header, raw, _ = raw_bundle()
    original = tmp_path / "raw.csv"
    write_raw(original, header, raw)
    digest = _sha256_file(str(original))
    original.write_text("changed", encoding="utf-8")
    h, fixed = materialize_face_assignments(header, raw, [decision()], BASE_FACES)
    with pytest.raises(ValueError, match="changed"):
        save_corrected_source_file(filepath=str(tmp_path / "out.csv"), header_info=h, raw_data=fixed,
            original_source_path=str(original), original_source_sha256=digest, decisions=[decision()], context_json=context_json())


def test_missing_face_and_mixed_kind_are_not_silently_applied():
    header, raw, _ = raw_bundle()
    with pytest.raises(ValueError, match="known original"):
        materialize_face_assignments(header, raw, [decision()], {**BASE_FACES, "F1": ""})
    legacy = MarkerCorrectionDecision("legacy", .3, True, "X", permutation=(("F1", "B1"), ("B1", "F1")))
    with pytest.raises(ValueError, match="cannot be mixed"):
        materialize_face_assignments(header, raw, [legacy], BASE_FACES)


def test_processing_does_not_filter_or_resample_through_face_boundary():
    from src.analysis.pipeline.smoother import MarkerSmoother
    from src.analysis.pipeline.resampler import UniformResampler
    from src.analysis.pipeline.velocity_calculator import VelocityCalculator
    from src.config.data_columns import VelocityCols
    times = np.arange(20) * .01
    df = pd.DataFrame({'F1_X': [0.] * 10 + [100.] * 10,
                       'F1_FaceInfo': ['FRONT'] * 10 + ['BACK'] * 10}, index=times)
    smoother = MarkerSmoother()
    smoother.configure({'marker_smoothing_method_sequence': ['moving_average']})
    np.testing.assert_allclose(smoother.process(df)['F1_X'], df['F1_X'])
    out = UniformResampler(2).process(df)
    assert not np.any((out.index > .09 + 1e-10) & (out.index < .1 - 1e-10))
    for col in POSE_COLUMNS:
        df[col] = 0.
    df[POSE_COLUMNS[0]] = df.F1_X
    calculator = VelocityCalculator()
    calculator.configure({'velocity_method': 'finite_difference', 'acceleration_method': 'finite_difference',
                          'use_pose_lowpass_filter': False, 'use_pose_moving_average': False,
                          'use_velocity_lowpass_filter': False, 'use_acceleration_lowpass_filter': False})
    calculated = calculator.process(df)
    new = calculated.columns.difference(df.columns)
    assert calculated.loc[times[[9, 10]], new].isna().all().all()
    expanded = UniformResampler(2).process(calculated)
    assert expanded.loc[np.isclose(expanded.index, .105), new].isna().all().all()


def test_unknown_version_or_missing_annotations_are_rejected(tmp_path):
    header, raw, _ = raw_bundle()
    original = tmp_path / 'raw.csv'
    write_raw(original, header, raw)
    h, fixed = materialize_face_assignments(header, raw, [decision()], BASE_FACES)
    target = tmp_path / 'fixed.csv'
    save_corrected_source_file(filepath=str(target), header_info=h, raw_data=fixed,
        original_source_path=str(original), decisions=[decision()], context_json=context_json())
    import csv
    rows = list(csv.reader(target.open(newline='', encoding='utf-8')))
    for row in rows[2:]:
        del row[raw.shape[1]:]
    with target.open('w', newline='', encoding='utf-8') as f:
        csv.writer(f).writerows(rows)
    with pytest.raises(ValueError, match='requires annotation'):
        DataLoader().load_csv(str(target))


def test_one_row_face_segments_leave_derivatives_unavailable():
    from src.analysis.pipeline.velocity_calculator import VelocityCalculator
    df = pd.DataFrame({col: [0., 0.] for col in POSE_COLUMNS}, index=[0., .01])
    df['F1_FaceInfo'] = ['FRONT', 'BACK']
    calculator = VelocityCalculator()
    calculator.configure({'velocity_method': 'spline'})
    result = calculator.process(df)
    assert result[calculator._derivative_columns()].isna().all().all()


def test_missing_xyz_clears_stale_pose_and_keeps_face_identity():
    header, raw, _ = raw_bundle(samples=1)
    raw.iloc[:, 2:] = np.nan
    parsed = Parser(FACE_PREFIX_TO_INFO).process(header, raw)
    assert parsed.iloc[0]['F1_FaceInfo'].upper() == 'FRONT'
    for col in POSE_COLUMNS:
        parsed[col] = 1.
    pose = PoseOptimizer(config_app.FACE_DEFINITIONS, config_app.calculate_local_box_corners(DIMS)).process(parsed, DIMS)
    assert pose[list(POSE_COLUMNS)].isna().all().all()
    assert pose.iloc[0][SourceCols.POSE] == 'InsufficientData'
