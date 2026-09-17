"""Observation-only event scan and bounded review, independent of Qt and truth files."""
from dataclasses import dataclass, replace
import hashlib
import json

import numpy as np
import pandas as pd
from scipy.optimize import linear_sum_assignment

from .face_assignment import FaceAssignmentAnalyzer

REVIEW_VERSION = 'event-local-1'
WINDOW_SIZE = 5
MAX_FRAME_FITS_PER_EVENT = 30
MAX_ITERATIONS = 1500


def analyzer_configuration(analyzer):
    return {'settings': {k: v for k, v in vars(analyzer).items()
                         if isinstance(v, (str, int, float, bool))},
            'faces': analyzer.face_definitions, 'optimizer': analyzer.optimizer_options,
            'implementation': type(analyzer).__module__ + '.' + type(analyzer).__qualname__,
            'version': REVIEW_VERSION}


def checkpoint(cancelled):
    if cancelled is not None and cancelled():
        raise InterruptedError('Marker review cancelled.')


def canonical_key(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                    allow_nan=False).encode()).hexdigest()


def file_digest(path, cancelled=None):
    digest = hashlib.sha256()
    with open(path, 'rb') as stream:
        while True:
            checkpoint(cancelled)
            block = stream.read(1024 * 1024)
            if not block:
                return digest.hexdigest()
            digest.update(block)


def copy_observations(data, cancelled=None, progress=None):
    """Own one snapshot; do not freeze the GUI with a whole-frame constructor copy."""
    pieces = []
    digest = hashlib.sha256(repr(tuple(data.columns)).encode())
    for start in range(0, len(data), 2048):
        checkpoint(cancelled)
        part = data.iloc[start:start + 2048].copy(deep=True)
        digest.update(pd.util.hash_pandas_object(part, index=True).to_numpy().tobytes())
        pieces.append(part)
        if progress:
            progress('Preparing observations', min(start + 2048, len(data)), len(data))
    checkpoint(cancelled)
    return (pd.concat(pieces) if pieces else data.copy()), digest.hexdigest()


@dataclass(frozen=True)
class Boundary:
    pre: int
    post: int
    triggers: tuple[str, ...]


def scan_observations(data, dims, analyzer, cancelled=None, progress=None):
    """O(N) in frame count for a fixed marker layout; no nonlinear pose calls.

    Assignment costs depend on marker count (M), not recording length. Expensive
    correspondence is evaluated only when centered labeled displacement is large.
    Distortion is a candidate reason, never permission to bypass the rigid gate.
    """
    times = np.asarray(data.index, dtype=float)
    if not np.isfinite(times).all() or not np.all(np.diff(times) > 0):
        raise ValueError('Marker review requires finite, strictly increasing timestamps.')
    gap_limit = analyzer.gap_factor * float(np.median(np.diff(times))) if len(times) > 1 else 0.
    ids = analyzer._marker_ids(data)
    if not ids or len(times) < 2:
        return [], gap_limit
    points = analyzer._marker_points(data, ids)
    valid = np.isfinite(points).all(axis=2)
    diagonal = float(np.linalg.norm(dims))
    events = []
    held_start = None
    last_usable = 0 if valid[0].sum() >= analyzer.minimum_common_markers else None
    for post in range(1, len(times)):
        checkpoint(cancelled)
        pre, reasons = post - 1, []
        same_mask = np.array_equal(valid[pre], valid[post])
        common = valid[pre] & valid[post]
        enough = common.sum() >= analyzer.minimum_common_markers
        held = (enough and same_mask and
                np.max(np.abs(points[post, common] - points[pre, common])) <= analyzer.freeze_tolerance_mm)
        if held:
            if held_start is None:
                held_start = pre
        elif held_start is not None:
            if post - held_start >= analyzer.freeze_min_samples:
                reasons.append('held observations / reconnect')
            held_start = None
        if not same_mask:
            reasons.append('marker availability changed')
        usable = valid[post].sum() >= analyzer.minimum_common_markers
        if usable:
            if last_usable is not None and (post - last_usable > 1 or times[post] - times[last_usable] > gap_limit):
                pre = min(pre, last_usable)
                reasons.append('tracking gap')
            last_usable = post
        if times[post] - times[post - 1] > gap_limit:
            reasons.append('timestamp gap')
        if enough and not held:
            before, after = points[post - 1, common], points[post, common]
            before, after = before - before.mean(axis=0), after - after.mean(axis=0)
            direct = float(np.sqrt(np.mean(np.sum((after - before) ** 2, axis=1))))
            # Candidate recall must not use the recommendation coverage gate.
            # Common finite points can expose a jump even at low full-layout
            # coverage; _review_boundary still evaluates the original layout.
            rigid = analyzer._rigid_pair_evidence(before, after, dims)
            if rigid['rotation_deg'] is not None and rigid['rotation_deg'] + 1e-12 >= analyzer.candidate_angle_deg:
                reasons.append('stable-ID rotation jump')
            if rigid['status'] == 'distortion_exceeds_tolerance':
                reasons.append('stable-ID shape discontinuity')
            if direct >= diagonal * analyzer.marker_jump_fraction:
                costs = np.linalg.norm(before[:, None] - after[None, :], axis=2)
                rows, cols = linear_sum_assignment(costs)
                assigned = float(np.sqrt(np.mean(costs[rows, cols] ** 2)))
                if (assigned <= diagonal * analyzer.marker_set_continuity_fraction and
                        direct - assigned >= diagonal * analyzer.marker_jump_reduction_fraction):
                    reasons.append('marker label discontinuity')
        if reasons:
            events.append(Boundary(pre, post, tuple(reasons)))
        if progress and (post % 256 == 0 or post == len(times) - 1):
            progress('Scanning observations', post + 1, len(times))
    checkpoint(cancelled)
    return events, gap_limit


def review_observations(data, dims, *, optimizer_factory=None, analyzer_factory=FaceAssignmentAnalyzer,
                        cancelled=None, progress=None, identity=None):
    """At most 10 baseline + 4*5 hypothesis frame fits per observed event."""
    stats = {'whole_input_pose_passes': 0, 'process_calls': [], 'nonlinear_fits': 0,
             'iterations': 0, 'evaluations': 0, 'frame_fit_budget': 0}
    analyzer = analyzer_factory()
    if analyzer.window_size != WINDOW_SIZE:
        raise ValueError('Event-local review requires the versioned five-sample window.')
    analyzer.optimizer_factory = optimizer_factory
    analyzer.cancelled = cancelled
    boundaries, gap_limit = scan_observations(data, dims, analyzer, cancelled, progress)
    analyzer.gap_limit = gap_limit
    stats['frame_fit_budget'] = MAX_FRAME_FITS_PER_EVENT * len(boundaries)
    plans = [([*range(max(0, b.pre - WINDOW_SIZE + 1), b.pre + 1)],
              [*range(b.post, min(len(data), b.post + WINDOW_SIZE))]) for b in boundaries]
    key = canonical_key({'source': identity, 'dimensions': list(dims), 'windows': plans,
                         'configuration': analyzer_configuration(analyzer)})
    candidates = []
    for event_index, (boundary, (pre, post)) in enumerate(zip(boundaries, plans)):
        checkpoint(cancelled)
        def process_observer(role, frame):
            stats['process_calls'].append({'event': event_index, 'role': role, 'frames': len(frame),
                                           'times': list(map(float, frame.index))})

        def fit_observer(stage, time, result):
            if stage == 'start':
                stats['nonlinear_fits'] += 1
            else:
                stats['iterations'] += result['iterations']
                stats['evaluations'] += result['evaluations']
            if progress:
                role = stats['process_calls'][-1]['role']
                progress(f'Event {event_index + 1}/{len(boundaries)}: {role}',
                         stats['nonlinear_fits'], stats['frame_fit_budget'])

        analyzer.process_observer, analyzer.fit_observer = process_observer, fit_observer
        positions = pre + post
        local = data.iloc[positions].copy()
        # Independent seeds on either side: never warm-start across an interruption.
        before = analyzer.fit_frames(local.iloc[:len(pre)], dims, role='baseline pre')
        after = analyzer.fit_frames(local.iloc[len(pre):], dims, role='baseline post')
        pose = pd.concat([before, after])
        candidate = analyzer._review_boundary(local, pose, dims, len(pre) - 1, len(pre),
            ', '.join(boundary.triggers), gap_limit=gap_limit,
            crosses_observation_gap=boundary.post != boundary.pre + 1,
            crosses_held_boundary='held observations / reconnect' in boundary.triggers)
        evidence = candidate.continuity_evidence
        for name in ('requested_pre_sample_indices', 'requested_post_sample_indices', 'common_post_sample_indices'):
            evidence[name] = [positions[i] for i in evidence[name]]
        evidence['refit_valid_sample_indices'] = {
            label: [positions[i] for i in indices] for label, indices in evidence['refit_valid_sample_indices'].items()}
        evidence['review_execution'] = {'version': REVIEW_VERSION, 'snapshot_key': key,
            'frame_fit_budget': MAX_FRAME_FITS_PER_EVENT, 'max_iterations': MAX_ITERATIONS,
            'seed_policy': 'independent-pre-post-face-kabsch', 'gap_limit_sec': gap_limit,
            'configuration': analyzer_configuration(analyzer)}
        candidates.append(replace(candidate, event_id=f'flip-{boundary.post:06d}'))
    checkpoint(cancelled)
    if progress:
        progress('Review complete', stats['frame_fit_budget'], stats['frame_fit_budget'])
    return {'candidates': candidates, 'snapshot_key': key, 'statistics': stats}
