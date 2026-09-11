"""Geometric support evidence from observed poses, never support-force evidence."""
import numpy as np
import pandas as pd
from scipy.spatial.transform import Rotation

from src.config.config_app import BOX_EDGES_AS_CORNER_INDICES, FACE_DEFINITIONS


EDGE_TRAVEL_SIGNAL = 'Least-moving edge travel (mm)'
LIFT_SIGNAL = 'Opposite edge height (mm)'
MINIMUM_ROTATION_DEG = 2.0  # Motion evidence setting, not an ISTA limit.


def support_motion_evidence(result, row):
    reg = result.registration
    evidence = {'version': 1, 'status': 'registration_required'}
    if reg is None or reg.floor_y_mm is None or result.corners_m is None:
        return evidence
    t = result.signals.index.to_numpy(float)
    selected = np.flatnonzero((t >= row['start']) & (t <= row['end']))
    if (len(selected) < 3 or not result.valid_pose[selected].all()
            or len(np.unique(result.block_ids[selected])) != 1):
        evidence['status'] = 'insufficient_tracking'
        return evidence
    corners = result.corners_m[selected] * 1000.
    if not np.isfinite(corners).all():
        evidence['status'] = 'insufficient_tracking'
        return evidence
    edges = np.asarray(BOX_EDGES_AS_CORNER_INDICES, dtype=int)
    travel = np.linalg.norm(corners - corners[0], axis=2)
    edge_maxima = travel[:, edges].max(axis=(0, 2))
    least = int(np.argmin(edge_maxima))
    tolerance = reg.position_tolerance_mm
    possible = np.flatnonzero(edge_maxima <= tolerance)
    rotations = result.rotations[selected]
    angles = np.rad2deg(Rotation.from_matrix(rotations @ rotations[0].T).magnitude())
    floor = reg.floor_y_mm
    # Guard against switching the reference face for tiny pose differences.
    # This geometric scale uses two endpoint tolerances across the smallest
    # box edge; it is not a calibrated orientation-error bound.
    face_ambiguity_deg = float(np.rad2deg(np.arctan2(
        2. * tolerance, min(reg.profile['box_dims_mm']))))
    # A downward normal describes orientation, not trial-start contact.
    downward = sorted((float(rotations[0, 1, d['axis_idx']] * d['direction']), name)
                      for name, d in FACE_DEFINITIONS.items())
    face_angles = np.rad2deg(np.arccos(np.clip([-item[0] for item in downward[:2]], -1., 1.)))
    face_gap_deg = float(face_angles[1] - face_angles[0])
    start_face = downward[0][1] if face_gap_deg > face_ambiguity_deg else None
    edge = edges[least].tolist()
    evidence.update(
        reference_time_s=float(t[selected[0]]), floor_y_mm=float(floor),
        position_tolerance_mm=float(tolerance),
        minimum_rotation_deg=MINIMUM_ROTATION_DEG,
        max_rotation_deg=float(angles.max()), final_rotation_deg=float(angles[-1]),
        least_moving_edge=edge, min_edge_max_travel_mm=float(edge_maxima[least]),
        fixed_edge_candidates=edges[possible].tolist(), pivot_edge=None,
        start_face_ambiguity_deg=face_ambiguity_deg,
        start_face_angle_gap_deg=face_gap_deg,
        start_face_status='unambiguous' if start_face else 'ambiguous_downward_faces',
        starting_downward_face=start_face, opposite_edge=None,
        opposite_edge_max_height_mm=None,
        minimum_corner_height_mm=float(corners[:, :, 1].min() - floor),
        censored=bool(row.get('left_censored') or row.get('right_censored')),
    )
    if evidence['minimum_corner_height_mm'] < -tolerance:
        evidence['status'] = 'floor_geometry_inconsistent'
    elif angles.max() < MINIMUM_ROTATION_DEG:
        evidence['status'] = 'insufficient_rotation'
    elif not len(possible):
        evidence['status'] = 'moving_edges'
    elif len(possible) != 1:
        evidence['status'] = 'ambiguous_pivot'
    else:
        pivot = edges[int(possible[0])].tolist()
        heights = corners[:, pivot, 1] - floor
        evidence['pivot_edge'] = pivot
        evidence['pivot_height_mm'] = float(heights[0].mean())
        on_floor = np.abs(heights).max() <= tolerance
        horizontal = np.abs(heights[:, 0] - heights[:, 1]).max() <= tolerance
        evidence['status'] = 'floor_pivot_compatible' if on_floor and horizontal else 'support_unknown'
        face_corners = set(FACE_DEFINITIONS[start_face]['corners']) if start_face else set()
        if set(pivot).issubset(face_corners):
            opposite = sorted(face_corners - set(pivot))
            if len(opposite) == 2 and any(set(e) == set(opposite) for e in edges):
                evidence['opposite_edge'] = opposite
                # Use the lower endpoint: this is the edge's clearance above
                # the registered floor, not the height of its higher endpoint.
                height = corners[:, opposite, 1].min(axis=1) - floor
                evidence['opposite_edge_max_height_mm'] = float(height.max())
    return evidence


def support_motion_signals(result, row):
    """Selected-interval series on the capture clock; no interpolation over gaps."""
    signals = pd.DataFrame(np.nan, index=result.signals.index,
                           columns=[EDGE_TRAVEL_SIGNAL, LIFT_SIGNAL])
    evidence = row.get('motion_geometry', {})
    edge = evidence.get('least_moving_edge')
    if row.get('evidence_status') != 'current' or edge is None:
        return signals
    t = signals.index.to_numpy(float)
    selected = np.flatnonzero((t >= row['start']) & (t <= row['end']))
    if not len(selected) or not result.valid_pose[selected].all():
        return signals
    corners = result.corners_m[selected] * 1000.
    travel = np.linalg.norm(corners[:, edge] - corners[0, edge], axis=2).max(axis=1)
    signals.iloc[selected, 0] = travel
    opposite = evidence.get('opposite_edge')
    if opposite is not None:
        signals.iloc[selected, 1] = corners[:, opposite, 1].min(axis=1) - result.registration.floor_y_mm
    return signals
