"""Observed fixed-edge rise/return phases; no support force or trial identity.

Phase support uses actual samples, a finite fitting window and registration
resolution. A small height change alone is never evidence of a stationary pose.
"""
from dataclasses import replace

import numpy as np
from scipy.spatial.transform import Rotation

from .support_motion import support_motion_evidence


VERSION = 1
MERGE_TAG = 'support_cycle_return'


def _runs(values):
    limits = np.r_[0, np.flatnonzero(values[1:] != values[:-1]) + 1, len(values)]
    return [(int(a), int(b), values[a]) for a, b in zip(limits[:-1], limits[1:])]


def _check_cancelled(cancelled):
    if cancelled and cancelled():
        raise InterruptedError('Scene detection cancelled.')


def _phases(times, corners, heights, settings, tolerance, cancelled):
    count = len(times)
    labels = np.full(count, 'unknown', dtype=object)
    signs = np.zeros(count, dtype=int)
    supported = np.zeros(count, dtype=bool)
    stable = np.zeros(count, dtype=bool)
    window = settings.window_s
    numeric_mm = 64 * np.finfo(float).eps * max(1., float(np.abs(corners).max()))
    numeric_time = 64 * np.finfo(float).eps * max(1., float(np.abs(times).max()))
    for i, time in enumerate(times):
        if i % 100 == 0:
            _check_cancelled(cancelled)
        # Bracket the desired window with real samples; never interpolate.
        left = max(times[0], min(time - window / 2., times[-1] - window))
        a = max(0, int(np.searchsorted(times, left, side='right')) - 1)
        b = min(count, int(np.searchsorted(times, left + window, side='left')) + 1)
        span = times[b - 1] - times[a]
        if b - a < settings.minimum_points or span + numeric_time < window:
            continue
        supported[i] = True
        tau = times[a:b] - time
        design = np.column_stack((np.ones(len(tau)), tau))
        values = np.column_stack((heights[a:b], corners[a:b].reshape(b - a, 24)))
        coefficients, _, rank, _ = np.linalg.lstsq(design, values, rcond=None)
        if rank != 2:
            supported[i] = False
            continue
        residual = values - design @ coefficients
        delta_height = coefficients[1, 0] * span
        # This is a deterministic fit-consistency check, not a confidence bound.
        if abs(delta_height) > 2. * np.abs(residual[:, 0]).max() + numeric_mm:
            signs[i] = 1 if delta_height > 0 else -1
        pose_delta = np.linalg.norm(coefficients[1, 1:].reshape(8, 3) * span, axis=1)
        pose_residual = np.linalg.norm(residual[:, 1:].reshape(-1, 8, 3), axis=2).max(axis=0)
        coherent_pose_trend = np.any(pose_delta > 2. * pose_residual + numeric_mm)
        observed = corners[a:b]
        diameter = np.linalg.norm(observed[:, None] - observed[None, :], axis=3).max()
        stable[i] = diameter <= tolerance and not coherent_pose_trend
    # Fit direction must persist over enough observations and exceed positional
    # resolution cumulatively. A noiseless slow drift remains unknown until then.
    for a, b, direction in _runs(signs):
        if (direction and b - a >= settings.minimum_points
                and times[b - 1] - times[a] + numeric_time >= window
                and direction * (heights[b - 1] - heights[a]) > 2. * tolerance):
            labels[a:b] = 'rise' if direction > 0 else 'fall'
    labels[(labels == 'unknown') & supported & stable] = 'steady_within_resolution'
    # Local windows can conceal cumulative slow motion beneath alternating
    # residuals. Require stability over each final steady run as well. Per-corner
    # bounding-box diagonals conservatively bound full pairwise travel in O(N).
    for a, b, label in _runs(labels):
        if label == 'steady_within_resolution':
            extent_upper_bound_mm = np.linalg.norm(np.ptp(corners[a:b], axis=0), axis=1).max()
            if extent_upper_bound_mm > tolerance:
                labels[a:b] = 'unknown'
    phases = [{'phase': str(label), 'start_time_s': float(times[a]), 'end_time_s': float(times[b - 1]),
               'sample_count': b - a} for a, b, label in _runs(labels)]
    return labels, phases, bool(supported.any())


def analyze_support_cycle(result, row):
    """Describe phases and all-corner return on the supplied observed interval."""
    return _analyze(result, row, None)


def _analyze(result, row, cancelled):
    evidence = {'version': VERSION, 'status': 'registration_required', 'phases': [],
                'start_time_s': None, 'end_time_s': None, 'peak_height_mm': None,
                'return_error_mm': None, 'returned': None, 'cycle_count': 0,
                'return_time_s': None, 'return_times_s': []}
    _check_cancelled(cancelled)
    geometry = support_motion_evidence(result, row)
    evidence['geometry_status'] = geometry['status']
    times = result.signals.index.to_numpy(float)
    selected = np.flatnonzero((times >= row['start']) & (times <= row['end']))
    if len(selected):
        evidence.update(start_time_s=float(times[selected[0]]), end_time_s=float(times[selected[-1]]))
    if geometry['status'] not in ('floor_pivot_compatible', 'support_unknown'):
        evidence['status'] = geometry['status']
        return evidence
    if geometry.get('opposite_edge') is None:
        evidence['status'] = 'ambiguous_height_reference'
        return evidence
    corners = result.corners_m[selected] * 1000.
    times = times[selected]
    heights = corners[:, geometry['opposite_edge'], 1].min(axis=1) - result.registration.floor_y_mm
    tolerance = result.registration.position_tolerance_mm
    errors = np.linalg.norm(corners - corners[0], axis=2).max(axis=1)
    labels, phases, supported = _phases(times, corners, heights, result.settings, tolerance, cancelled)
    evidence.update(phases=phases, peak_height_mm=float(heights.max()),
                    peak_time_s=float(times[int(np.argmax(heights))]),
                    return_error_mm=float(errors[-1]), pivot_edge=geometry['pivot_edge'],
                    opposite_edge=geometry['opposite_edge'],
                    max_origin_displacement_mm=float(np.linalg.norm(
                        result.origins_m[selected] - result.origins_m[selected[0]], axis=1).max() * 1000.),
                    max_rotation_deg=geometry['max_rotation_deg'],
                    settings={'window_s': float(result.settings.window_s),
                              'minimum_points': int(result.settings.minimum_points),
                              'position_tolerance_mm': float(tolerance),
                              'minimum_phase_change_mm': float(2. * tolerance),
                              'steady_extent_policy': 'whole-phase per-corner bounding-box diagonal within position tolerance'},
                    meaning='Observed geometry and resolution-limited phases; not support force, release or ISTA identity')
    if not supported:
        evidence['status'] = 'insufficient_window_support'
        return evidence
    if row.get('left_censored') or row.get('right_censored'):
        evidence['status'] = 'censored'
        return evidence
    state = 'idle'
    returns = []
    directions = []
    for i, label in enumerate(labels):
        if label in ('rise', 'fall') and (not directions or directions[-1] != label):
            directions.append(str(label))
        if state == 'idle' and label == 'rise':
            state = 'rising'
        elif state == 'rising' and label == 'fall':
            state = 'falling'
        if state == 'falling' and errors[i] <= tolerance:
            returns.append(float(times[i]))
            state = 'idle'
    evidence.update(cycle_count=len(returns), return_times_s=returns,
                    return_time_s=returns[0] if returns else None,
                    motion_sequence=directions,
                    returned=bool(returns and errors[-1] <= tolerance and state == 'idle'))
    if len(returns) > 1:
        evidence['status'] = 'multiple_cycles'
    elif evidence['returned'] and directions == ['rise', 'fall']:
        evidence['status'] = 'complete_cycle'
    elif len(directions) > 2:
        evidence['status'] = 'multiple_excursions'
    elif np.any(labels == 'rise') or np.any(labels == 'fall'):
        evidence['status'] = 'incomplete_cycle'
    else:
        evidence['status'] = 'no_cycle'
    return evidence


def merge_support_cycles(result, *, cancelled=None):
    """Merge the earliest complete raw group, retaining every original activity."""
    raw = result.activity_candidates if result.activity_candidates is not None else result.candidates
    _check_cancelled(cancelled)
    if (result.registration is None or result.registration.floor_y_mm is None
            or result.corners_m is None):
        return raw
    times = result.signals.index.to_numpy(float)
    usable = (result.valid_pose & (result.block_ids >= 0)
              & np.isfinite(result.corners_m).all(axis=(1, 2)))
    unusable_prefix = np.r_[0, np.cumsum(~usable)]
    block_changes = np.r_[0, np.cumsum(result.block_ids[1:] != result.block_ids[:-1])]
    merged = []
    i = 0
    while i < len(raw):
        _check_cancelled(cancelled)
        first = raw[i]
        if first.motion == 'stationary' and not first.left_censored and not first.right_censored:
            cycle = _analyze(result, {'start': first.start, 'end': first.end,
                                      'left_censored': False, 'right_censored': False}, cancelled)
            if cycle['status'] in ('complete_cycle', 'multiple_cycles'):
                # A whole-path cycle is visible motion even below the initial
                # activity-rate thresholds. Preserve that original activity label.
                tag = MERGE_TAG if cycle['status'] == 'complete_cycle' else 'support_multiple_cycles'
                merged.append(replace(first, motion='tip_or_rotation', evidence_class='tip_or_rotation',
                    tags=list(dict.fromkeys([*first.tags, tag])), rotation_deg=cycle['max_rotation_deg'],
                    activity_members=[{'id': first.id, 'start': first.start, 'end': first.end,
                                       'motion': first.motion}]))
                i += 1
                continue
        if first.motion != 'tip_or_rotation' or first.left_censored or first.right_censored:
            merged.append(first)
            i += 1
            continue
        own_cycle = _analyze(result, {'start': first.start, 'end': first.end,
                                     'left_censored': False, 'right_censored': False}, cancelled)
        # A raw interval that already contains a return is closed. Appending a
        # later unresolved motion must not turn it into a larger single cycle.
        if own_cycle['cycle_count']:
            merged.append(first)
            i += 1
            continue
        found = None
        turns = 1
        first_index = int(np.searchsorted(times, first.start, side='left'))
        for j in range(i + 1, len(raw)):
            _check_cancelled(cancelled)
            last = raw[j]
            if last.motion not in ('tip_or_rotation', 'stationary') or last.left_censored or last.right_censored:
                break
            turns += last.motion == 'tip_or_rotation'
            if turns < 2:
                continue
            last_index = int(np.searchsorted(times, last.end, side='right')) - 1
            if not 0 <= first_index <= last_index < len(times):
                continue
            # Necessary conditions are cheap and do not infer any cycle phase.
            # Invalid tracking already inside a prefix cannot be repaired by
            # extending it. Matching endpoints still require full-path analysis.
            if (unusable_prefix[last_index + 1] != unusable_prefix[first_index]
                    or block_changes[last_index] != block_changes[first_index]):
                break
            endpoint_error_mm = np.linalg.norm(result.corners_m[last_index] * 1000.
                                               - result.corners_m[first_index] * 1000., axis=1).max()
            if endpoint_error_mm > result.registration.position_tolerance_mm:
                continue
            row = {'start': first.start, 'end': last.end, 'left_censored': False, 'right_censored': False}
            cycle = _analyze(result, row, cancelled)
            if cycle['cycle_count'] > 1:
                break
            if cycle['status'] == 'complete_cycle':
                selected = np.flatnonzero((times >= first.start) & (times <= last.end))
                rotation = Rotation.from_matrix(result.rotations[selected] @ result.rotations[selected[0]].T).magnitude()
                tags = list(dict.fromkeys(tag for member in raw[i:j + 1] for tag in member.tags)) + [MERGE_TAG]
                found = replace(first, end=last.end, evidence_class='tip_or_rotation', tags=tags,
                                rotation_deg=float(np.rad2deg(rotation.max())),
                                displacement_mm=float(np.linalg.norm(result.origins_m[selected[-1]]
                                    - result.origins_m[selected[0]]) * 1000.),
                                boundary_uncertainty_s=max(member.boundary_uncertainty_s for member in raw[i:j + 1]),
                                activity_members=[{'id': member.id, 'start': member.start, 'end': member.end,
                                                   'motion': member.motion} for member in raw[i:j + 1]])
                i = j + 1
                break
            if cycle['geometry_status'] in ('insufficient_tracking', 'floor_geometry_inconsistent', 'moving_edges'):
                break
            if cycle['status'] == 'ambiguous_height_reference':
                # The first pose and its starting face do not change on extension.
                break
        if found is None:
            merged.append(first)
            i += 1
        else:
            merged.append(found)
    return merged
