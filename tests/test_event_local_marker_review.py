"""Public observation-only expectations and bounded work; no production-derived oracle."""
import threading

import numpy as np
import pandas as pd
import pytest

from marker_face_fixtures import DIMS, LAYOUT, BASE_FACES
from src.analysis.pipeline.face_assignment import FaceAssignmentAnalyzer, POSE_COLUMNS
from src.analysis.pipeline.marker_review import review_observations, scan_observations
from src.analysis.pipeline.pose_optimizer import PoseOptimizer
from src.analysis.ui.widget_raw_data_processing import MarkerReviewWorker
from src.config import config_app
from src.config.data_columns import SourceCols


def observations(n=24, events=((12, 'X'),), *, stationary=True):
    points = np.asarray(list(LAYOUT.values()), float)
    values = np.repeat(points[None], n, axis=0)
    matrices = {'X': np.diag([1., -1., -1.]), 'Y': np.diag([-1., 1., -1.]),
                'Z': np.diag([-1., -1., 1.])}
    for row, axis in events:
        values[row:] = values[row:] @ matrices[axis]
    # Fixed origin, declared independently of the fitter.
    values += [17., 200., 11.]
    if not stationary:
        values[:, :, 0] += np.arange(n)[:, None] * .2
    frame = pd.DataFrame(values.reshape(n, -1),
        columns=[f'{mid}_{a}' for mid in LAYOUT for a in 'XYZ'], index=np.arange(n) * .01)
    for mid, face in BASE_FACES.items():
        frame[mid + '_FaceInfo'] = face
    return frame


class RecordingOptimizer:
    calls = []

    def __init__(self, **kwargs):
        pass

    def process(self, frame, **kwargs):
        self.calls.append((len(frame), kwargs))
        result = frame.copy()
        for col in POSE_COLUMNS:
            result[col] = 0.
        result[SourceCols.POSE] = 'Optimized'
        return result


@pytest.mark.parametrize('n', [1000, 10000, 100000])
def test_no_event_worker_never_calls_pose_optimizer(n):
    RecordingOptimizer.calls = []
    worker = MarkerReviewWorker(observations(n, ()), DIMS, RecordingOptimizer, FaceAssignmentAnalyzer)
    worker.run()
    assert worker.error is None
    assert worker.result['candidates'] == []
    assert RecordingOptimizer.calls == []


@pytest.mark.parametrize('n', [100, 1000, 10000])
def test_fixed_events_have_bounded_baseline_and_actual_refit_calls(n):
    RecordingOptimizer.calls = []
    # Add stationary padding only after the independently fixed two boundaries.
    result = review_observations(observations(n, ((12, 'X'), (32, 'X'))), DIMS,
                                 optimizer_factory=RecordingOptimizer)
    assert [c.boundary_time_sec for c in result['candidates']] == [.12, .32]
    calls = result['statistics']['process_calls']
    assert len(calls) == 12
    assert sum(c['frames'] for c in calls) == 60
    assert all(c['frames'] == 5 for c in calls)
    assert len(RecordingOptimizer.calls) == 12
    assert all(kwargs['max_iterations'] == 1500 for _, kwargs in RecordingOptimizer.calls)
    assert [c['role'] for c in calls] == ['baseline pre', 'baseline post', 'NONE', 'X', 'Y', 'Z'] * 2


@pytest.mark.parametrize('axis', ['X', 'Y', 'Z'])
def test_real_local_refit_retains_independent_axis_and_event_time(axis):
    frame = observations(events=((12, axis),), stationary=False)
    original = frame.copy(deep=True)
    result = review_observations(frame, DIMS)
    assert len(result['candidates']) == 1
    candidate = result['candidates'][0]
    assert candidate.boundary_time_sec == .12
    assert candidate.recommendation_axis == axis
    assert candidate.best_residual_deg < .1
    assert result['statistics']['nonlinear_fits'] == 30
    assert candidate.continuity_evidence['requested_post_sample_indices'] == [12, 13, 14, 15, 16]
    pd.testing.assert_frame_equal(original, frame)


def test_pose_jump_only_distortion_public_parity_with_real_optimizer():
    frame = observations(stationary=False)
    xyz = [f'{mid}_{a}' for mid in LAYOUT for a in 'XYZ']
    points = frame.loc[frame.index[12:], xyz].to_numpy().reshape(-1, len(LAYOUT), 3)
    center = points.mean(axis=1, keepdims=True)
    frame.loc[frame.index[12:], xyz] = (center + 1.1 * (points - center)).reshape(len(points), -1)
    analyzer = FaceAssignmentAnalyzer()
    assert analyzer._marker_label_discontinuities(frame, DIMS) == []
    assert analyzer._rigid_rotation_boundaries(analyzer._marker_points(frame, analyzer._marker_ids(frame)), DIMS) == []
    old_pose = PoseOptimizer(config_app.FACE_DEFINITIONS, config_app.calculate_local_box_corners(DIMS)).process(frame, DIMS)
    legacy = analyzer.detect(frame, old_pose, DIMS)
    assert any(c.boundary_time_sec == .12 and 'rotation jump' in c.trigger for c in legacy)
    result = review_observations(frame, DIMS)
    candidate = next(c for c in result['candidates'] if c.boundary_time_sec == .12)
    assert candidate.recommendation_axis is None
    assert candidate.continuity_evidence['boundary_rigid_fit']['status'] == 'distortion_exceeds_tolerance'


def test_missing_held_and_time_gap_boundaries_need_no_pose_truth():
    frame = observations(60, (), stationary=False)
    xyz = [f'{mid}_{a}' for mid in LAYOUT for a in 'XYZ']
    frame.iloc[10:13, :len(xyz)] = np.nan
    frame.iloc[25:29, :len(xyz)] = frame.iloc[24, :len(xyz)].to_numpy()
    times = frame.index.to_numpy(copy=True)
    times[40:] += .2
    frame.index = times
    events, _ = scan_observations(frame, DIMS, FaceAssignmentAnalyzer())
    assert [b.post for b in events] == [10, 13, 29, 40]
    assert 'tracking gap' in events[1].triggers
    assert 'held observations / reconnect' in events[2].triggers


@pytest.mark.parametrize('phase', ['scan', 'baseline pre', 'baseline post', 'NONE', 'X', 'Y', 'Z', 'after'])
def test_cooperative_cancellation_discards_partial_worker_results(phase):
    cancelled = threading.Event()
    class CancelOptimizer(RecordingOptimizer):
        def process(self, frame, **kwargs):
            if kwargs['cancelled']():
                raise InterruptedError()
            result = super().process(frame, **kwargs)
            return result
    worker = MarkerReviewWorker(observations(stationary=False), DIMS, CancelOptimizer, FaceAssignmentAnalyzer)
    if phase == 'scan':
        worker.requestInterruption()  # QThread ignores interruption before start; use explicit predicate.
        worker.isInterruptionRequested = lambda: True
    else:
        original = FaceAssignmentAnalyzer.fit_frames
        def fit(self, frame, dims, **kwargs):
            result = original(self, frame, dims, **kwargs)
            if kwargs.get('role') == phase or (phase == 'after' and kwargs.get('role') == 'Z'):
                cancelled.set()
            return result
        from unittest.mock import patch
        worker.isInterruptionRequested = cancelled.is_set
        with patch.object(FaceAssignmentAnalyzer, 'fit_frames', fit):
            worker.run()
        assert worker.result is None and worker.error is None
        return
    worker.run()
    assert worker.result is None and worker.error is None


def test_cancel_inside_real_scipy_objective(monkeypatch):
    from src.analysis.pipeline import pose_optimizer as module
    original = module._objective_function
    count = 0
    def objective(*args):
        nonlocal count
        count += 1
        return original(*args)
    monkeypatch.setattr(module, '_objective_function', objective)
    with pytest.raises(InterruptedError):
        PoseOptimizer(config_app.FACE_DEFINITIONS, config_app.calculate_local_box_corners(DIMS)).process(
            observations(1, ()), DIMS, cancelled=lambda: count >= 3)
    assert count == 3


def test_low_coverage_pose_jump_parity_keeps_candidate_but_abstains():
    frame = observations(stationary=False)
    for mid in ('F1', 'B1', 'R1', 'L1'):
        frame[[mid + '_' + a for a in 'XYZ']] = np.nan
    analyzer = FaceAssignmentAnalyzer()
    pose = PoseOptimizer(config_app.FACE_DEFINITIONS, config_app.calculate_local_box_corners(DIMS)).process(frame, DIMS)
    legacy = analyzer.detect(frame, pose, DIMS)
    assert any(c.boundary_time_sec == .12 and 'rotation jump' in c.trigger for c in legacy)
    result = review_observations(frame, DIMS)
    candidate = next(c for c in result['candidates'] if c.boundary_time_sec == .12)
    assert candidate.recommendation_axis is None
    assert candidate.continuity_evidence['boundary_rigid_fit']['coverage'] == pytest.approx(14 / 18)


def test_held_reconnect_remains_conditional_abstention():
    result = review_observations(observations(), DIMS)
    candidate = next(c for c in result['candidates'] if c.boundary_time_sec == .12)
    assert candidate.recommendation_axis is None
    assert candidate.continuity_evidence['crosses_held_boundary']
    assert not candidate.continuity_evidence['crosses_tracking_gap']
    assert 'physical motion is unconfirmed' in candidate.reason


def test_cache_identity_includes_actual_analyzer_settings():
    data = observations(20, ())
    first = MarkerReviewWorker(data, DIMS, PoseOptimizer, FaceAssignmentAnalyzer)
    first.run()
    cache = {'key': first.result['cache_key'], 'result': first.result}
    same = MarkerReviewWorker(data, DIMS, PoseOptimizer, FaceAssignmentAnalyzer)
    same.cache = cache
    same.run()
    assert same.result['statistics']['cache_hit']
    changed = MarkerReviewWorker(data, DIMS, PoseOptimizer,
                                 lambda: FaceAssignmentAnalyzer(candidate_angle_deg=70))
    changed.cache = cache
    changed.run()
    assert changed.result['cache_key'] != cache['key']
    assert not changed.result['statistics'].get('cache_hit', False)


def test_local_seed_is_reset_at_timestamp_gap_without_increasing_frame_budget():
    frame = observations(5, ())
    frame.index = [0., .01, .02, .2, .21]
    analyzer = FaceAssignmentAnalyzer(optimizer_factory=RecordingOptimizer)
    analyzer.gap_limit = .03
    RecordingOptimizer.calls = []
    analyzer.fit_frames(frame, DIMS, initial_pose=np.zeros(6))
    assert [n for n, _ in RecordingOptimizer.calls] == [3, 2]
    assert RecordingOptimizer.calls[0][1]['initial_pose'] is not None
    assert RecordingOptimizer.calls[1][1]['initial_pose'] is None


@pytest.mark.parametrize('kind', ['repeat', 'gap', 'genuine', 'unsupported'])
def test_actual_event_local_control_meanings(kind):
    from scipy.spatial.transform import Rotation
    frame = observations(40, ((12, 'X'), (28, 'X')) if kind == 'repeat' else (), stationary=False)
    xyz = [f'{mid}_{a}' for mid in LAYOUT for a in 'XYZ']
    if kind == 'gap':
        frame.iloc[12:15, :len(xyz)] = np.nan
    elif kind in ('genuine', 'unsupported'):
        points = frame[xyz].to_numpy().reshape(-1, len(LAYOUT), 3)
        centers = points.mean(axis=1, keepdims=True)
        angles = np.linspace(0, 180, 40) if kind == 'genuine' else np.r_[np.zeros(12), np.full(28, 90)]
        rotations = Rotation.from_euler('x', angles, degrees=True).as_matrix()
        frame[xyz] = (np.einsum('nij,nmj->nmi', rotations, points - centers) + centers).reshape(40, -1)
    result = review_observations(frame, DIMS)
    recommended = [(c.boundary_time_sec, c.recommendation_axis) for c in result['candidates'] if c.recommendation_axis]
    if kind == 'repeat':
        assert recommended == [(.12, 'X'), (.28, 'X')]
    else:
        assert recommended == []
    if kind == 'gap':
        assert [c.boundary_time_sec for c in result['candidates']] == [.12, .15]
    elif kind == 'genuine':
        assert result['candidates'] == []
    elif kind == 'unsupported':
        assert any(c.boundary_time_sec == .12 for c in result['candidates'])
