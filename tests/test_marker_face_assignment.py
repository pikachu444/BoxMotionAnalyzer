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


def test_face_review_recommends_real_refit_x_conditionally_without_changing_input():
    header, raw, _ = raw_bundle(samples=45, boundary=20)
    parsed = Parser(FACE_PREFIX_TO_INFO).process(header, raw)
    pose = PoseOptimizer(config_app.FACE_DEFINITIONS, config_app.calculate_local_box_corners(DIMS)).process(parsed, DIMS)
    original_parsed, original_pose = parsed.copy(deep=True), pose.copy(deep=True)
    candidates = FaceAssignmentAnalyzer().detect(parsed, pose, DIMS)
    assert candidates
    candidate = next(c for c in candidates if c.boundary_time_sec == .2)
    assert candidate.correction_kind == 'face_assignment'
    assert candidate.recommendation_axis == 'X'
    assert candidate.best_residual_deg < .1
    assert candidate.no_correction_residual_deg > 179.9
    assert candidate.algorithm_version == '3.1'
    assert candidate.gate_version == 'face-continuity-v1'
    assert 'cause unconfirmed' in candidate.reason
    evidence = json.loads(candidate.evidence_json())
    assert evidence['correspondence_ratio'] is None
    assert all(h['layout_correspondence_ratio'] is None and h['observed_correspondence_ratio'] is None
               for h in evidence['hypotheses'].values())
    assert candidate.continuity_evidence['requested_post_sample_indices'] == [20, 21, 22, 23, 24]
    assert candidate.continuity_evidence['common_post_sample_indices'] == [20, 21, 22, 23, 24]
    pd.testing.assert_frame_equal(parsed, original_parsed)
    pd.testing.assert_frame_equal(pose, original_pose)


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


def _continuity_inputs():
    header, raw, _ = raw_bundle(axis=None, samples=12)
    markers = Parser(FACE_PREFIX_TO_INFO).process(header, raw)
    pose = markers.copy(deep=True)
    pose[list(POSE_COLUMNS)] = np.zeros((len(pose), 6))
    pose[SourceCols.POSE] = 'Optimized'
    pose.loc[pose.index[6:], list(POSE_COLUMNS[3:])] = R.from_euler('x', 180, degrees=True).as_rotvec()
    return markers, pose


def _stub_refits(monkeypatch, analyzer, angles=None, invalid=None, failed=None):
    """Only optimizer outputs are substituted; production comparison/gates run."""
    angles = {'NONE': 180., 'X': 0., 'Y': 160., 'Z': 150., **(angles or {})}
    invalid = invalid or {}

    def refit(label, markers, pose, positions, marker_ids, dims):
        if label == failed:
            return None, True, 'Deliberate refit failure.'
        frame = markers.iloc[list(positions)].copy(deep=True)
        frame[list(POSE_COLUMNS)] = np.zeros((len(frame), 6))
        frame[list(POSE_COLUMNS[3:])] = R.from_euler('x', np.broadcast_to(angles[label], len(frame)).reshape(-1, 1), degrees=True).as_rotvec()
        frame[SourceCols.POSE] = 'Optimized'
        for row in invalid.get(label, ()):
            frame.loc[frame.index[row], SourceCols.POSE] = 'OptimizationFailed'
        return frame, True, ''

    monkeypatch.setattr(analyzer, '_refit_hypothesis', refit)


@pytest.mark.parametrize('angles, settings, expected, reason', [
    ({'X': 35.}, {}, 'X', 'cause unconfirmed'),
    ({'X': 35.001}, {}, None, 'too large'),
    ({'Z': 27.}, {}, 'X', 'cause unconfirmed'),
    ({'Z': 26.999}, {}, None, 'score gap'),
    ({'NONE': 20.}, {'minimum_confidence_margin': 0.}, 'X', 'cause unconfirmed'),
    ({'NONE': 19.999}, {'minimum_confidence_margin': 0.}, None, 'NONE refit'),
    ({'NONE': 0., 'X': 180.}, {}, None, 'No correction'),
])
def test_continuity_fixed_gate_boundaries(monkeypatch, angles, settings, expected, reason):
    markers, pose = _continuity_inputs()
    analyzer = FaceAssignmentAnalyzer(**settings)
    _stub_refits(monkeypatch, analyzer, angles)
    candidate = analyzer._review_boundary(markers, pose, DIMS, 5, 6, 'contract boundary')
    assert candidate.recommendation_axis == expected
    assert reason in candidate.reason
    assert candidate.no_correction_residual_deg == pytest.approx(angles.get('NONE', 180.))
    for hypothesis in candidate.hypotheses:
        assert hypothesis.score == pytest.approx(1. - hypothesis.residual_deg / 180.)


@pytest.mark.parametrize('missing, expected', [(1, 'X'), (2, None)])
def test_continuity_marker_coverage_keeps_requested_denominator(monkeypatch, missing, expected):
    markers, pose = _continuity_inputs()
    # Distribute missing marker-samples rather than inserting a whole tracking gap;
    # leave the adjacent boundary pair intact to isolate requested-window coverage.
    marker_ids = FaceAssignmentAnalyzer._marker_ids(markers)
    for number in range(missing * len(marker_ids)):
        mid = marker_ids[number // 4]
        markers.loc[markers.index[7 + number % 4], [f'{mid}_{axis}' for axis in 'XYZ']] = np.nan
    analyzer = FaceAssignmentAnalyzer()
    _stub_refits(monkeypatch, analyzer)
    candidate = analyzer._review_boundary(markers, pose, DIMS, 5, 6, 'missing marker samples')
    assert candidate.recommendation_axis == expected
    assert candidate.continuity_evidence['post_marker_sample_coverage'] == (5 - missing) / 5
    assert candidate.continuity_evidence['requested_post_sample_indices'] == [6, 7, 8, 9, 10]


@pytest.mark.parametrize('invalid, failed, expected_common, expected', [
    ({label: [0] for label in ('NONE', 'X', 'Y', 'Z')}, None, [7, 8, 9, 10], 'X'),
    ({'NONE': [0], 'X': [1], 'Y': [2], 'Z': [3]}, None, [10], None),
    ({}, 'Y', [], None),
])
def test_continuity_refits_use_common_samples_without_survivor_margin(monkeypatch, invalid, failed, expected_common, expected):
    markers, pose = _continuity_inputs()
    analyzer = FaceAssignmentAnalyzer()
    _stub_refits(monkeypatch, analyzer, invalid=invalid, failed=failed)
    candidate = analyzer._review_boundary(markers, pose, DIMS, 5, 6, 'common support')
    assert candidate.recommendation_axis == expected
    assert candidate.continuity_evidence['common_post_sample_indices'] == expected_common
    assert all(len(h.trace_deg) == (len(expected_common) if expected else 0) for h in candidate.hypotheses)
    if expected is None:
        assert candidate.confidence_margin == 0.
        assert all(np.isnan(h.score) for h in candidate.hypotheses)
        assert json.loads(candidate.evidence_json())['hypotheses']['X']['score'] is None


def test_continuity_raw_pose_lag_is_diagnostic_and_refit_stability_is_gated(monkeypatch):
    markers, pose = _continuity_inputs()
    pose.loc[pose.index[6:11], list(POSE_COLUMNS[3:])] = R.from_euler('x', np.array([0, 0, 180, 180, 180]).reshape(-1, 1), degrees=True).as_rotvec()
    analyzer = FaceAssignmentAnalyzer()
    _stub_refits(monkeypatch, analyzer)
    candidate = analyzer._review_boundary(markers, pose, DIMS, 5, 6, 'lagged raw pose')
    assert candidate.recommendation_axis == 'X'
    assert candidate.continuity_evidence['raw_post_stability_deg'] > 30.
    assert candidate.post_stability_deg == 0.
    _stub_refits(monkeypatch, analyzer, {'X': [-32., -16., 0., 32., 64.]})
    unstable = analyzer._review_boundary(markers, pose, DIMS, 5, 6, 'unstable refit')
    assert unstable.recommendation_axis is None
    assert 'not stable' in unstable.reason


@pytest.mark.parametrize('boundary', ['gap', 'face'])
def test_continuity_does_not_cross_gap_or_approved_assignment(monkeypatch, boundary):
    markers, pose = _continuity_inputs()
    if boundary == 'gap':
        times = markers.index.to_numpy(copy=True)
        times[6:] += .2
        markers.index = pose.index = times
    else:
        markers.loc[markers.index[6:], 'F1_FaceInfo'] = 'BACK'
    analyzer = FaceAssignmentAnalyzer()
    _stub_refits(monkeypatch, analyzer)
    candidate = analyzer._review_boundary(markers, pose, DIMS, 5, 6, 'boundary')
    assert candidate.recommendation_axis is None
    assert 'crosses the comparison' in candidate.reason


def test_continuity_retains_genuine_smooth_180_rotation_without_candidates():
    from marker_face_fixtures import LAYOUT
    header, raw, _ = raw_bundle(axis=None, samples=61)
    rotations = R.from_euler('x', np.linspace(0., 180., len(raw)).reshape(-1, 1), degrees=True)
    # Independent prescribed world trajectory, with translating origin to avoid freeze.
    local = np.array(list(LAYOUT.values()))
    origin = np.c_[np.arange(len(raw)) * .2, np.full(len(raw), 200.), np.full(len(raw), 10.)]
    raw.iloc[:, 2:] = np.stack([rotation.apply(local) + p for rotation, p in zip(rotations, origin)]).reshape(len(raw), -1)
    markers = Parser(FACE_PREFIX_TO_INFO).process(header, raw)
    pose = markers.copy(deep=True)
    pose[list(POSE_COLUMNS[:3])] = origin
    pose[list(POSE_COLUMNS[3:])] = rotations.as_rotvec()
    pose[SourceCols.POSE] = 'Optimized'
    assert FaceAssignmentAnalyzer().detect(markers, pose, DIMS) == []


def test_continuity_bounded_refit_retains_rank_guard():
    # Every supplied raw seed looks valid, but one-face constraints cannot identify pose.
    points = [(-40,-25,40), (-25,10,40), (0,20,40), (35,-30,40), (41,15,40), (5,-10,40)]
    row = {}
    for i, point in enumerate(points):
        row[f'F{i}_FaceInfo'] = 'FRONT'
        row.update({f'F{i}_{axis}': value for axis, value in zip('XYZ', point)})
    markers = pd.DataFrame([row] * 10, index=np.arange(10) * .01)
    pose = markers.copy(deep=True)
    pose[list(POSE_COLUMNS)] = np.zeros((len(pose), 6))
    pose[SourceCols.POSE] = 'Optimized'
    candidate = FaceAssignmentAnalyzer()._review_boundary(markers, pose, DIMS, 4, 5, 'rank contract')
    assert candidate.recommendation_axis is None
    assert candidate.continuity_evidence['common_post_sample_indices'] == []
    assert candidate.continuity_evidence['refit_coverage'] == dict.fromkeys(('NONE', 'X', 'Y', 'Z'), 0.)


@pytest.mark.parametrize('increment, expected', [(30., 'X'), (30.001, None)])
def test_continuity_stability_inclusive_boundary(monkeypatch, increment, expected):
    markers, pose = _continuity_inputs()
    analyzer = FaceAssignmentAnalyzer()
    _stub_refits(monkeypatch, analyzer, {'X': [0., increment, 0., increment, 0.]})
    candidate = analyzer._review_boundary(markers, pose, DIMS, 5, 6, 'stability boundary')
    assert candidate.recommendation_axis == expected


def test_continuity_moving_windows_cannot_turn_a_90_degree_boundary_into_a_recommendation(monkeypatch):
    markers, pose = _continuity_inputs()
    pre_angles = np.array([-50., -25., 0., 25., 50.]).reshape(-1, 1)
    post_angles = np.array([140., 165., 190., 215., 240.]).reshape(-1, 1)
    pose.loc[pose.index[1:6], list(POSE_COLUMNS[3:])] = R.from_euler('y', pre_angles, degrees=True).as_rotvec()
    pose.loc[pose.index[6:11], list(POSE_COLUMNS[3:])] = R.from_euler('y', post_angles, degrees=True).as_rotvec()
    matrices = {'NONE': np.eye(3), 'X': np.diag([1., -1., -1.]),
                'Y': np.diag([-1., 1., -1.]), 'Z': np.diag([-1., -1., 1.])}

    def refit(label, marker_df, pose_df, positions, marker_ids, dims):
        frame = pose_df.iloc[list(positions)].copy(deep=True)
        rotations = R.from_rotvec(frame[list(POSE_COLUMNS[3:])].to_numpy())
        frame[list(POSE_COLUMNS[3:])] = (rotations * R.from_matrix(matrices[label])).as_rotvec()
        return frame, True, ''

    analyzer = FaceAssignmentAnalyzer()
    monkeypatch.setattr(analyzer, '_refit_hypothesis', refit)
    candidate = analyzer._review_boundary(markers, pose, DIMS, 5, 6, 'moving-window counterexample')
    # This tests the comparison of prescribed refits; the independent review also
    # exercises the same counterexample through the real bounded optimizer.
    assert candidate.no_correction_residual_deg == pytest.approx(170.)
    assert candidate.best_hypothesis_label == 'Y'
    assert candidate.best_residual_deg == pytest.approx(10.)
    assert candidate.pre_stability_deg == pytest.approx(100.)
    assert candidate.post_stability_deg == pytest.approx(100.)
    assert candidate.recommendation_axis is None
    assert 'not stable' in candidate.reason
    assert 'Maximum pairwise SO(3)' in candidate.continuity_evidence['window_stability_definition']
    # Legacy v2's adjacent-increment statistic is intentionally unchanged.
    assert MarkerFlipAnalyzer()._window_stability(pose, list(range(1, 6))) == pytest.approx(25.)


def test_continuity_stable_ids_locate_jump_despite_one_failed_raw_pose(monkeypatch):
    markers, pose = _continuity_inputs()
    marker_ids = FaceAssignmentAnalyzer._marker_ids(markers)
    columns = [f'{mid}_{axis}' for mid in marker_ids for axis in 'XYZ']
    points = markers.loc[markers.index[6:], columns].to_numpy().reshape(-1, len(marker_ids), 3)
    centers = points.mean(axis=1, keepdims=True)
    # Literal proper half-turn of the observed stable-ID cloud, not a permutation.
    markers.loc[markers.index[6:], columns] = ((points - centers) @ np.diag([1., -1., -1.]) + centers).reshape(len(points), -1)
    pose.loc[pose.index[6], list(POSE_COLUMNS)] = np.nan
    pose.loc[pose.index[6], SourceCols.POSE] = 'OptimizationFailed'
    analyzer = FaceAssignmentAnalyzer()
    _stub_refits(monkeypatch, analyzer)
    # Isolate the new stable-ID signal from the legacy unordered-cloud detector.
    monkeypatch.setattr(analyzer, '_marker_label_discontinuities', lambda *_: [])
    candidates = analyzer.detect(markers, pose, DIMS)
    assert len(candidates) == 1
    candidate = candidates[0]
    assert candidate.boundary_time_sec == .06
    assert 'stable-ID rotation jump' in candidate.trigger
    assert 'tracking gap' not in candidate.trigger
    assert candidate.recommendation_axis == 'X'
    assert candidate.continuity_evidence['crosses_tracking_gap'] is False


def test_continuity_whole_missing_observation_still_prevents_comparison(monkeypatch):
    markers, pose = _continuity_inputs()
    columns = [f'{mid}_{axis}' for mid in FaceAssignmentAnalyzer._marker_ids(markers) for axis in 'XYZ']
    markers.loc[markers.index[7], columns] = np.nan
    analyzer = FaceAssignmentAnalyzer()
    _stub_refits(monkeypatch, analyzer)
    candidate = analyzer._review_boundary(markers, pose, DIMS, 5, 6, 'tracking loss within window')
    assert candidate.continuity_evidence['post_marker_sample_coverage'] == .8
    assert candidate.continuity_evidence['crosses_tracking_gap'] is True
    assert candidate.recommendation_axis is None


@pytest.mark.parametrize('points', [
    [[-1., 0., 0.], [1., 0., 0.]],
    [[-2., 0., 0.], [-1., 0., 0.], [1., 0., 0.], [2., 0., 0.]],
])
def test_continuity_rigid_boundary_rejects_two_points_and_collinear_zero_error(points):
    points = np.asarray(points)
    analyzer = FaceAssignmentAnalyzer()
    evidence = analyzer._rigid_pair_evidence(points, points @ np.diag([-1., -1., 1.]), DIMS)
    assert evidence['status'] in ('insufficient_markers', 'noncollinear_support_required')
    assert evidence['rotation_deg'] is None
    assert analyzer._rigid_rotation_boundaries(np.stack([points, -points]), DIMS) == []


def test_continuity_scale_distortion_cannot_bypass_boundary_guard_via_pose_jump(monkeypatch):
    markers, pose = _continuity_inputs()
    columns = [f'{mid}_{axis}' for mid in FaceAssignmentAnalyzer._marker_ids(markers) for axis in 'XYZ']
    points = markers.loc[markers.index[6:], columns].to_numpy().reshape(6, -1, 3)
    centers = points.mean(axis=1, keepdims=True)
    markers.loc[markers.index[6:], columns] = (1.1 * (points - centers) @ np.diag([1., -1., -1.]) + centers).reshape(6, -1)
    analyzer = FaceAssignmentAnalyzer()
    _stub_refits(monkeypatch, analyzer)
    # The raw pose jump still creates a candidate even though geometry rejects it.
    candidates = analyzer.detect(markers, pose, DIMS)
    candidate = next(c for c in candidates if c.boundary_time_sec == .06)
    evidence = candidate.continuity_evidence['boundary_rigid_fit']
    assert evidence['rotation_deg'] == pytest.approx(180.)
    assert evidence['rmse_mm'] < evidence['rmse_limit_mm']
    assert evidence['maximum_pair_distance_change_mm'] > evidence['pair_distance_change_limit_mm']
    assert evidence['status'] == 'distortion_exceeds_tolerance'
    assert candidate.recommendation_axis is None
    assert 'Stable-ID marker geometry' in candidate.reason
