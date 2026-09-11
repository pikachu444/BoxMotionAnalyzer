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


@pytest.mark.parametrize('artifact', ['corrected', 'slice'])
def test_v3_history_annotation_mismatch_rejected_on_read_and_write(tmp_path, artifact):
    import csv
    header, raw, _ = raw_bundle(boundary=4, samples=10)
    original = tmp_path / 'raw.csv'
    write_raw(original, header, raw)
    event = decision(time=.04)
    h, fixed = materialize_face_assignments(header, raw, [event], BASE_FACES)
    target = tmp_path / 'fixed.csv'
    meta = save_corrected_source_file(filepath=str(target), header_info=h, raw_data=fixed,
        original_source_path=str(original), decisions=[event], context_json=context_json())
    corrupt = fixed.copy()
    corrupt.iloc[4, face_columns(h)['F1']] = 'FRONT'
    with pytest.raises(ValueError, match='disagrees'):
        save_corrected_source_file(filepath=str(tmp_path / 'bad.csv'), header_info=h, raw_data=corrupt,
            original_source_path=str(original), decisions=[event], context_json=context_json())
    if artifact == 'slice':
        target = tmp_path / 'suffix.slice'
        save_slice_file(filepath=str(target), header_info=h, raw_data=fixed, source_path=str(original),
            full_start=0., full_end=.09, user_start=.05, user_end=.09, pad_rows=0,
            box_dims=DIMS, marker_correction_metadata=meta)
    # A syntactically valid face is still corrupt when it contradicts history.
    with target.open(newline='', encoding='utf-8') as f:
        rows = list(csv.reader(f))
    rows[-1][face_columns(h)['F1']] = 'FRONT'
    with target.open('w', newline='', encoding='utf-8') as f:
        csv.writer(f).writerows(rows)
    with pytest.raises(ValueError, match='disagrees'):
        DataLoader().load_csv(str(target))


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


def test_single_face_six_points_rejects_false_pose_and_stale_corners():
    # Before the guard this converged with ~20.88 mm / 6.50 deg arbitrary pose.
    points = [(-40,-25,40),(-25,10,40),(0,20,40),(35,-30,40),(41,15,40),(5,-10,40)]
    row = {'C1_X': 999., 'C1_Y': 999., 'C1_Z': 999.}
    for i, point in enumerate(points):
        row[f'F{i}_FaceInfo'] = 'FRONT'
        row.update({f'F{i}_{axis}': value for axis,value in zip('XYZ',point)})
    parsed = pd.DataFrame([row], index=pd.Index([0.], name='Time'))
    pose = PoseOptimizer(config_app.FACE_DEFINITIONS, config_app.calculate_local_box_corners(DIMS)).process(parsed,DIMS)
    assert pose.iloc[0][SourceCols.POSE] == 'UnidentifiableGeometry'
    assert pose[list(POSE_COLUMNS)].isna().all().all()
    assert pose[['C1_X','C1_Y','C1_Z']].isna().all().all()
    assert FaceAssignmentAnalyzer().detect(parsed,pose,DIMS) == []


def test_face_centers_reject_rank_deficient_rotation_even_with_three_normal_axes():
    row = {}
    for mid, face, point in [('F1','FRONT',(0,0,40)),('B1','BACK',(0,0,-40)),
                            ('R1','RIGHT',(100,0,0)),('L1','LEFT',(-100,0,0)),
                            ('T1','TOP',(0,60,0)),('M1','BOTTOM',(0,-60,0))]:
        row[mid+'_FaceInfo'] = face
        row.update({f'{mid}_{axis}': value for axis,value in zip('XYZ',point)})
    parsed = pd.DataFrame([row], index=pd.Index([0.], name='Time'))
    pose = PoseOptimizer(config_app.FACE_DEFINITIONS, config_app.calculate_local_box_corners(DIMS)).process(parsed,DIMS,initial_pose=np.zeros(6))
    assert pose.iloc[0][SourceCols.POSE] == 'UnidentifiableGeometry'
    assert pose[list(POSE_COLUMNS)].isna().all().all()


def test_three_front_constraints_have_multiple_zero_cost_poses_and_are_rejected():
    from src.analysis.pipeline.pose_optimizer import _objective_function
    markers = [{'cam_coords': np.array(p), 'face_key': 'FRONT'}
               for p in [(-20.,-10.,40.), (20.,-10.,40.), (0.,20.,40.)]]
    for params in [np.zeros(6), np.array([10.,0.,0.,0.,0.,.1])]:
        assert _objective_function(params, markers, np.array(DIMS), config_app.FACE_DEFINITIONS) < 1e-20
    row = {}
    for i, m in enumerate(markers):
        row[f'F{i}_FaceInfo'] = 'FRONT'
        row.update({f'F{i}_{a}': v for a,v in zip('XYZ',m['cam_coords'])})
    pose = PoseOptimizer(config_app.FACE_DEFINITIONS, config_app.calculate_local_box_corners(DIMS)).process(pd.DataFrame([row], index=[0.]),DIMS)
    assert pose.iloc[0][SourceCols.POSE] == 'UnidentifiableGeometry'


def test_unknown_face_is_unavailable_and_interior_surface_distance_is_nonzero():
    from src.analysis.pipeline.pose_optimizer import _distance_point_to_box_surface_overall
    assert _distance_point_to_box_surface_overall(np.zeros(3), np.array(DIMS)/2) == 40.
    assert _distance_point_to_box_surface_overall(np.array([110.,0.,0.]), np.array(DIMS)/2) == 10.
    h, raw, _ = raw_bundle(samples=1)
    parsed = Parser(FACE_PREFIX_TO_INFO).process(h,raw)
    parsed['F1_FaceInfo'] = ''
    pose = PoseOptimizer(config_app.FACE_DEFINITIONS, config_app.calculate_local_box_corners(DIMS)).process(parsed,DIMS)
    assert pose.iloc[0][SourceCols.POSE] == 'UnknownFace'
    assert pose[list(POSE_COLUMNS)].isna().all().all()


def test_offset_solver_pivot_can_leave_translation_error_despite_zero_face_cost():
    from marker_face_fixtures import LAYOUT
    from src.analysis.pipeline.pose_optimizer import _objective_function
    pivot = np.array([0.,20.,0.])
    half_turn = np.diag([1.,-1.,-1.])
    shifted_origin = pivot - half_turn @ pivot
    # Corrected faces describe a box displaced 40 mm; no face-only evidence
    # can recover the independent physical origin without pivot calibration.
    markers = [{'cam_coords': pivot + half_turn @ (np.array(p)-pivot),
                'face_key': {'FRONT':'BACK','BACK':'FRONT','TOP':'BOTTOM','BOTTOM':'TOP'}.get(BASE_FACES[mid],BASE_FACES[mid])}
               for mid,p in LAYOUT.items()]
    assert np.linalg.norm(shifted_origin) == 40.
    assert _objective_function(np.r_[shifted_origin,np.zeros(3)],markers,np.array(DIMS),config_app.FACE_DEFINITIONS) < 1e-20
