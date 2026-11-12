"""Deterministic contact-path and stable-tail diagnostics, not qualification."""
from dataclasses import dataclass

import numpy as np
from scipy.spatial.transform import Rotation

from src.config.config_app import FACE_DEFINITIONS, calculate_local_box_corners


@dataclass(frozen=True)
class ReducerValue:
    value: float | str | None
    reason: str = ''


def final_face(times, rotations, corners, dimensions, *, floor, threshold, vertical_axis=1):
    from src.analysis.pipeline.drop_posture_post_processor import DropPosturePostProcessor

    try:
        t, points, dims = np.asarray(times, float), np.asarray(corners, float), np.asarray(dimensions, float)
        if vertical_axis != 1:
            raise ValueError('Only recorded world Y up is supported')
        if (t.ndim != 1 or len(t) < 2 or not np.isfinite(t).all() or np.any(np.diff(t) <= 0)
                or points.shape != (len(t), 8, 3) or not np.isfinite(points).all()):
            raise ValueError('Finite increasing times and complete corner geometry are required')
        if dims.shape != (3,) or not np.isfinite(dims).all() or np.any(dims <= 0):
            raise ValueError('Finite positive box dimensions are required')
        if not np.isfinite(floor) or not np.isfinite(threshold) or threshold <= 0:
            raise ValueError('Finite floor and positive contact threshold are required')
        rot = rotations if isinstance(rotations, Rotation) else Rotation.from_rotvec(rotations)
        if len(rot) != len(t) or not np.isfinite(rot.as_quat()).all():
            raise ValueError('Complete finite tail rotations are required')
        local = calculate_local_box_corners(dims)
        expected = np.stack([r.apply(local) for r in rot])
        if not np.allclose(points - points.mean(axis=1, keepdims=True), expected, rtol=1e-9, atol=1e-7):
            raise ValueError('Saved pose and corner geometry disagree')
        processor = DropPosturePostProcessor(face_definitions=FACE_DEFINITIONS, local_box_corners=local,
                                            floor_level=floor)
        heights = processor._smooth_min_heights(points[:, :, 1].min(axis=1))
        speed = np.gradient(heights, t, edge_order=1)
        start = int(.65 * len(t))
        tail, velocity = heights[start:], speed[start:]
        if len(tail) < 5 or not np.isfinite(velocity).all():
            raise ValueError('At least five usable tail samples are required')
        d = float(dims.min())
        band = max(threshold, .03 * d, 2.)
        if not (np.median(tail) <= floor + max(band, .10 * d)
                and np.std(tail, ddof=0) <= max(3., .025 * d)
                and np.median(np.abs(velocity)) <= 150.):
            return ReducerValue('Unsettled', 'The observed tail does not meet the stable-height gates')
        quats = rot[start:].as_quat()
        eigenvalues = np.linalg.eigvalsh(quats.T @ quats)
        if eigenvalues[-1] == eigenvalues[-2]:
            raise ValueError('Ambiguous tail orientation: non-unique rotation mean')
        return ReducerValue(processor._select_reference_face(rot[start:].mean()))
    except (ValueError, TypeError, IndexError, OverflowError) as error:
        return ReducerValue(None, str(error))


def contact_sweep(corners, events, *, vertical_axis=1):
    keys = ('TotalSweepAngle_deg', 'SweepConsistency', 'RotationDirection')
    try:
        points = np.asarray(corners, float)
        if vertical_axis != 1:
            raise ValueError('Only recorded world Y up is supported')
        if points.ndim != 3 or points.shape[1:] != (8, 3) or not np.isfinite(points).all():
            raise ValueError('Complete finite contact-path geometry is required')
        if len(events) < 2:
            raise ValueError('At least two accepted contact events are required')
        up = np.array([0., 1., 0.])
        radii = []
        for event in events:
            frame = points[event['start_pos']]
            indices = np.asarray(event['contact_set'], int) - 1
            if not len(indices) or np.any(indices < 0) or np.any(indices >= 8):
                raise ValueError('Contact event has invalid corner identities')
            radius = frame[indices].mean(axis=0) - frame.mean(axis=0)
            radius = radius - up * np.dot(radius, up)
            if not np.isfinite(radius).all():
                raise ValueError('Contact radius arithmetic is non-finite')
            radii.append(radius)
        steps = []
        for left, right in zip(radii[:-1], radii[1:]):
            if min(np.linalg.norm(left), np.linalg.norm(right)) < 1e-6:
                continue
            x, y = float(np.dot(left, right)), float(np.dot(up, np.cross(left, right)))
            if not np.isfinite([x, y]).all():
                raise ValueError('Contact angle arithmetic is non-finite')
            if y == 0 and x < 0:
                raise ValueError('Exact half-turn contact path has ambiguous direction')
            steps.append(np.arctan2(y, x))
        travel = float(np.sum(np.abs(steps)))
        if not steps or travel < 1e-6:
            raise ValueError('No nondegenerate angular contact travel; direction is undefined')
        net = float(np.sum(steps))
        if not np.isfinite([travel, net]).all():
            raise ValueError('Contact sweep arithmetic is non-finite')
        consistency = abs(net) / travel
        direction = 'Indeterminate' if consistency < .5 else 'CCW' if net > 0 else 'CW'
        return dict(zip(keys, (ReducerValue(float(np.degrees(abs(net)))),
                              ReducerValue(consistency), ReducerValue(direction))))
    except (ValueError, TypeError, IndexError, OverflowError) as error:
        return {key: ReducerValue(None, str(error)) for key in keys}
