"""Saved posture geometry and repeat applicability, not physical calibration."""
from dataclasses import dataclass, field
import json

import numpy as np
import pandas as pd
from scipy.spatial.transform import Rotation

from src.analysis.compare.impact_metrics import (
    SUMMARY, MetricValue, _column, _constant, _number, _observation_context,
    _processing_context,
)
from src.analysis.pipeline.drop_posture_post_processor import DropPosturePostProcessor
from src.config.config_app import FACE_DEFINITIONS, calculate_local_box_corners
from src.config.result_metric_descriptors import METRIC_DESCRIPTORS
from src.utils.first_event_evidence import validate_first_event
from src.utils.result_time import time_values, exceeds_gap_limit


def _descriptor(column, label, unit, *, whole=False, kind='numeric'):
    return dict(column=column, label=label, unit=unit, whole=whole, kind=kind,
                role='diagnostic', tooltip=METRIC_DESCRIPTORS.get(column, {}).get('tooltip', ''))


POSTURE_METRICS = {
    'beta': _descriptor('BetaAtT1MinusDeg', 'Pre-contact Beta', 'deg'),
    'theta_long': _descriptor('ThetaLongAtT1MinusDeg', 'Pre-contact signed long tilt', 'deg'),
    'theta_short': _descriptor('ThetaShortAtT1MinusDeg', 'Pre-contact signed short tilt', 'deg'),
    'height_range': _descriptor('DeltaHAtT1Minus_mm', 'Pre-contact face height range', 'mm'),
    'lowest_corner': _descriptor('CminAtT1MinusIndex', 'Pre-contact lowest corner', '', kind='categorical'),
    'corner_gap': _descriptor(None, 'Lowest-corner uniqueness gap', 'mm'),
    'max_beta': _descriptor('MaxBetaDeg', 'Whole-window max Beta', 'deg', whole=True),
    'max_long': _descriptor('MaxAbsThetaLongDeg', 'Whole-window max absolute long tilt', 'deg', whole=True),
    'max_short': _descriptor('MaxAbsThetaShortDeg', 'Whole-window max absolute short tilt', 'deg', whole=True),
    'max_height_range': _descriptor('MaxDeltaH_mm', 'Whole-window max face height range', 'mm', whole=True),
    'sequence': _descriptor('ImpactSequence', 'Whole-window contact sequence', '', whole=True, kind='categorical'),
}
FACE_METRICS = ('beta', 'theta_long', 'theta_short', 'height_range',
                'max_beta', 'max_long', 'max_short', 'max_height_range')
POSTURE_METRICS['corner_gap']['tooltip'] = (
    'Second-lowest minus lowest of eight world-Y corner heights at the recorded pre-contact sample. '
    'Geometric separation in mm, not confidence or a pass threshold. Edge/face approaches can correctly give zero.')
POSTURE_METRICS['lowest_corner']['tooltip'] += (
    ' Exact tied minima are a non-unique category; no unique-corner agreement is assigned.')
for key in FACE_METRICS:
    POSTURE_METRICS[key]['tooltip'] += (
        ' Depends on the recorded reference face and local axes; repeats require matching maximum-area faces. '
        'The reference face is not FinalFace or a target angle.')
for descriptor in POSTURE_METRICS.values():
    if descriptor['whole']:
        descriptor['tooltip'] += ' Repeats require complete geometry and equivalent reviewed windows.'


@dataclass
class PostureResult:
    metrics: dict = field(default_factory=dict)
    repeat_reasons: dict = field(default_factory=dict)
    reference: tuple | None = None
    reference_reason: str = ''
    window: tuple | None = None
    grid: np.ndarray | None = None
    window_reason: str = ''
    evaluation_time_s: float | None = None


def lowest_corners(heights):
    """Exact ties only. This geometric length does not estimate uncertainty."""
    heights = np.asarray(heights, float)
    if heights.shape != (8,) or not np.isfinite(heights).all():
        raise ValueError('Eight finite corner heights are required')
    ordered = np.sort(heights)
    corners = np.flatnonzero(heights == ordered[0]) + 1
    category = ','.join(f'C{i}' for i in corners)
    return float(ordered[1] - ordered[0]), category if len(corners) == 1 else f'Non-unique {{{category}}}'


def _numeric(df, col):
    return pd.to_numeric(_column(df, col), errors='coerce').to_numpy(float)


def _saved_numeric(df, name, expected):
    value = _number(_constant(df, (*SUMMARY, name)))
    # CSV/float roundoff validity guard, never a duplicate-equivalence policy.
    if not np.isclose(value, expected, rtol=1e-9, atol=1e-7):
        raise ValueError(f'{name}: saved value differs from pose/corner geometry')
    return value


def _window_context(review, times, event, settings):
    if review is None:
        raise ValueError('Reviewed window definition is unavailable')
    row, detection = review['candidate'], review['detection']
    if row['evidence_status'] != 'current' or row.get('left_censored') or row.get('right_censored'):
        raise ValueError('Window evidence changed or is cut by a capture boundary')
    if 'tracking_jump' in (row.get('motion'), row.get('evidence_class')):
        raise ValueError('Window contains a tracking jump')
    if settings['result_resampling']['enabled'] is not False:
        raise ValueError('Resampled windows do not establish complete observed geometry')
    if not detection.get('version') or not detection.get('settings'):
        raise ValueError('Recorded window detection definition is unavailable')
    gap = _number(detection['settings'].get('gap_factor')) * float(np.median(np.diff(times)))
    if any(exceeds_gap_limit(a, b, gap) for a, b in zip(times[:-1], times[1:])):
        raise ValueError('Window crosses a tracking gap')
    if not np.allclose([row['start'], row['end']], [times[0], times[-1]], rtol=0, atol=1e-12):
        raise ValueError('Saved samples do not cover the reviewed window boundaries')
    if event.valid:
        anchor, origin = 'pre-contact', event.times_s[0]
    else:
        if event.status != 'no-impact' or row.get('origin') != 'automatic':
            raise ValueError('Unaligned window needs a current automatic no-impact definition')
        anchor, origin = 'automatic-motion-start', times[0]
    definition = (anchor, detection['version'], json.dumps(detection['settings'], sort_keys=True),
                  row.get('origin'), row.get('evidence_class'), row.get('motion'))
    return definition, times - origin


def calculate_posture_metrics(df):
    result = PostureResult(metrics={key: MetricValue(None, 'Posture evidence unavailable') for key in POSTURE_METRICS})
    try:
        artifact, dims, floor = _processing_context(df, raw_pose=False)
        settings = json.loads(artifact['ProcessingSettingsJson'])
        if any(settings[stage]['face_definitions'] != FACE_DEFINITIONS for stage in ('single_pass', 'postprocess')):
            raise ValueError('Executed face/corner identities are unsupported')
        times, reason = time_values(df)
        if reason:
            raise ValueError(reason)
        review, _ = _observation_context(df)
        event = validate_first_event(df, review)
        pose = np.column_stack([_numeric(df, ('Position', 'CoM', 'P_' + axis))
                                for axis in ('TX', 'TY', 'TZ', 'RX', 'RY', 'RZ')])
        corners = np.stack([np.column_stack([_numeric(df, ('Position', f'C{i}', 'P_T' + a))
                                            for a in 'XYZ']) for i in range(1, 9)], axis=1)
        valid = (np.isfinite(pose).all(axis=1) & np.isfinite(corners).all(axis=(1, 2))
                 & _column(df, ('Info', 'Pose', 'Source')).eq('Optimized').to_numpy())
        if not valid.any():
            raise ValueError('Pose/corner geometry is unavailable')
        local = calculate_local_box_corners(dims)
        for i in np.flatnonzero(valid):
            expected = pose[i, :3] + Rotation.from_rotvec(pose[i, 3:]).apply(local)
            valid[i] = np.allclose(corners[i], expected, rtol=1e-9, atol=1e-7)
        reference_pos = event.indices[0] if event.valid else int(np.flatnonzero(valid)[0]) if valid.any() else None
        if reference_pos is None or not valid[reference_pos]:
            raise ValueError('Reference pose and saved corners disagree or are unavailable')
        processor = DropPosturePostProcessor(face_definitions=FACE_DEFINITIONS, local_box_corners=local, floor_level=floor)
        face = processor._select_reference_face(Rotation.from_rotvec(pose[reference_pos, 3:]))
        axes = processor._reference_axes(face)
        expected_reference = (face, *(f'LocalAxis{i}' for i in axes))
        try:
            saved_reference = tuple(_constant(df, (*SUMMARY, field)) for field in ('ReferenceFace', 'LongAxis', 'ShortAxis'))
            reference_error = '' if saved_reference == expected_reference else 'Recorded reference face/axes differ from the reference pose'
        except ValueError as error:
            reference_error = str(error)
        result.reference = expected_reference
        result.reference_reason = reference_error
        face_spec = FACE_DEFINITIONS[face]
        area = np.prod(dims[face_spec['bound_axes_indices']])
        max_area = max(np.prod(dims[f['bound_axes_indices']]) for f in FACE_DEFINITIONS.values())
        if area != max_area:
            for key in FACE_METRICS:
                result.repeat_reasons[key] = 'Side reference face: broad-face posture repeats are not comparable'
        # Per-row geometry uses no event fitting, truth or saved derivative columns.
        normals = np.zeros(3)
        normals[face_spec['axis_idx']] = face_spec['direction']
        values = np.full((len(df), 4), np.nan)
        face_corners = face_spec['corners']
        for i in np.flatnonzero(valid):
            normal_y = Rotation.from_rotvec(pose[i, 3:]).apply(normals)[1]
            tilts = []
            for axis in axes:
                positive = local[face_corners, axis] > 0
                heights = corners[i, face_corners, 1]
                tilts.append(np.degrees(np.arcsin(np.clip((heights[positive].mean() - heights[~positive].mean()) / dims[axis], -1, 1))))
            values[i] = [np.degrees(np.arccos(np.clip(-normal_y, -1, 1))), *tilts, np.ptp(corners[i, face_corners, 1])]
        pre_keys = ('beta', 'theta_long', 'theta_short', 'height_range')
        for key, descriptor in POSTURE_METRICS.items():
            try:
                if not descriptor['whole'] and not event.valid:
                    raise ValueError(event.reason)
                if key in FACE_METRICS and reference_error:
                    raise ValueError(reference_error)
                if key in pre_keys:
                    expected = values[reference_pos, pre_keys.index(key)]
                    value = _saved_numeric(df, descriptor['column'], expected)
                elif key in ('lowest_corner', 'corner_gap'):
                    gap, category = lowest_corners(corners[reference_pos, :, 1])
                    tied = np.flatnonzero(corners[reference_pos, :, 1] == corners[reference_pos, :, 1].min()) + 1
                    if key == 'lowest_corner':
                        saved = _number(_constant(df, (*SUMMARY, 'CminAtT1MinusIndex')))
                        if saved not in tied:
                            raise ValueError('Saved lowest corner differs from corner heights')
                    value = category if key == 'lowest_corner' else gap
                elif key != 'sequence':
                    index = ('max_beta', 'max_long', 'max_short', 'max_height_range').index(key)
                    expected = np.nanmax(np.abs(values[:, index]))
                    value = _saved_numeric(df, descriptor['column'], expected)
                else:
                    if not valid.all():
                        raise ValueError('Contact sequence needs complete whole-window geometry')
                    heights = corners[:, :, 1]
                    threshold = _number(settings['postprocess']['contact_threshold_mm'])
                    analysis = processor._contact_analysis(min_heights=heights.min(axis=1), index=pd.Index(times), contact_threshold_mm=threshold)
                    sets = processor._contact_sets(heights, threshold, active_mask=analysis['active_mask'], relative_contact_band=analysis['relative_contact_band'])
                    sequence = processor._impact_sequence_summary(contact_sets=sets, index=pd.Index(times))['DropPostureSummary_ImpactSequence']
                    saved = _constant(df, (*SUMMARY, 'ImpactSequence'))
                    saved = '' if pd.isna(saved) else str(saved)
                    if saved != sequence:
                        raise ValueError('Saved contact sequence differs from the whole-window contact policy')
                    value = saved or 'No contact sequence'
                result.metrics[key] = MetricValue(value)
            except (ValueError, TypeError, KeyError, IndexError) as error:
                result.metrics[key] = MetricValue(None, str(error))
        result.evaluation_time_s = event.times_s[0] if event.valid else None
        try:
            result.window, result.grid = _window_context(review, times, event, settings)
            if not valid.all():
                for key, descriptor in POSTURE_METRICS.items():
                    if descriptor['whole']:
                        result.repeat_reasons[key] = '; '.join(filter(None, (result.repeat_reasons.get(key),
                            'Whole window contains unavailable or inconsistent pose/corner geometry')))
        except (ValueError, TypeError, KeyError) as error:
            result.window_reason = str(error)
    except (ValueError, TypeError, KeyError, IndexError, AttributeError, OverflowError) as error:
        result.metrics = {key: MetricValue(None, str(error)) for key in POSTURE_METRICS}
        result.window_reason = str(error)
    return result


def context_difference(result, baseline, key):
    reasons = []
    if key in FACE_METRICS and (result.reference is None or result.reference != baseline.reference):
        reasons.append('Reference face/local axes differ from the baseline or are unavailable')
    if key in FACE_METRICS:
        reasons.extend(filter(None, (result.reference_reason, baseline.reference_reason)))
    if POSTURE_METRICS[key]['whole']:
        if result.window_reason or baseline.window_reason:
            reasons.extend([result.window_reason, 'Baseline: ' + baseline.window_reason if baseline.window_reason else ''])
        elif (result.window != baseline.window or result.grid is None or baseline.grid is None
              or result.grid.shape != baseline.grid.shape or not np.allclose(result.grid, baseline.grid, rtol=0, atol=1e-12)):
            reasons.append('Whole-window definitions or sampled intervals differ from the baseline')
    return '; '.join(reason for reason in reasons if reason)


def repeat_reasons(result, baseline, key):
    return '; '.join(filter(None, (result.repeat_reasons.get(key, ''), context_difference(result, baseline, key))))


def category_reference(value):
    """A tied set can have counts, but cannot establish unique-corner agreement."""
    return None if isinstance(value, str) and value.startswith('Non-unique') else value
