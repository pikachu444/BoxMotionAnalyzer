"""Fast motion evidence from observed markers, independent of the pose solver.

All calculations use metres, seconds and world-frame rotations. A fixed marker
template origin is not a box COM. Thresholds are candidate-detection settings,
not ISTA requirements. No truth or event manifest is read here.
"""
from dataclasses import asdict, dataclass, field
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.spatial.transform import Rotation

from src.config.data_columns import TimeCols
from src.config.config_app import calculate_local_box_corners


VERSION = 'observed-motion-v2-support-cycles'


@dataclass(frozen=True)
class DetectionSettings:
    window_s: float = .08
    minimum_points: int = 5
    moving_speed_m_s: float = .02
    moving_angular_speed_deg_s: float = 3.
    join_quiet_s: float = .12
    minimum_fall_s: float = .032
    followup_s: float = .20
    gravity_error_m_s2: float = 2.
    rotation_contamination_m_s2: float = 1.
    quadratic_residual_m: float = .002
    marker_residual_m: float = .005
    jump_angle_deg: float = 45.
    jump_distance_m: float = .1
    gap_factor: float = 4.


@dataclass(frozen=True)
class Registration:
    profile: dict
    floor_y_mm: float | None = None
    position_tolerance_mm: float = 1.
    com_offset_mm: tuple | None = None
    com_inside_box_confirmed: bool = False

    @classmethod
    def load(cls, path):
        data = json.loads(Path(path).read_text(encoding='utf-8-sig'))
        if data.get('version') != 1:
            raise ValueError('Unsupported geometry file version.')
        result = cls(data['profile'], data.get('floor_y_mm'),
                     data.get('position_tolerance_mm', 1.),
                     tuple(data['com_offset_mm']) if data.get('com_offset_mm') is not None else None,
                     data.get('com_inside_box_confirmed', False))
        result.validate()
        return result

    def validate(self):
        if self.profile.get('units') != 'mm' or self.profile.get('origin') != 'box-geometric-center':
            raise ValueError('Geometry must use mm and the box geometric centre.')
        dims = np.asarray(self.profile['box_dims_mm'], float)
        markers = self.profile['markers']
        xyz = np.asarray([m['xyz_mm'] for m in markers], float)
        ids = [m['id'] for m in markers]
        if dims.shape != (3,) or not np.isfinite(dims).all() or (dims <= 0).any():
            raise ValueError('Geometry needs three positive box dimensions.')
        if len(set(ids)) != len(ids) or len(ids) < 3 or xyz.shape != (len(ids), 3) or not np.isfinite(xyz).all():
            raise ValueError('Geometry needs distinct finite marker coordinates.')
        if self.floor_y_mm is not None and not np.isfinite(self.floor_y_mm):
            raise ValueError('Floor height must be finite.')
        if not np.isfinite(self.position_tolerance_mm) or self.position_tolerance_mm <= 0:
            raise ValueError('Geometry tolerance must be positive.')
        if self.com_offset_mm is not None:
            com = np.asarray(self.com_offset_mm, float)
            if com.shape != (3,) or not np.isfinite(com).all():
                raise ValueError('COM offset must contain three finite values.')
        if not isinstance(self.com_inside_box_confirmed, bool):
            raise ValueError('COM inside box confirmation must be boolean.')

    @property
    def fingerprint(self):
        return hashlib.sha256(json.dumps(asdict(self), sort_keys=True, separators=(',', ':'),
                                         allow_nan=False).encode()).hexdigest()


@dataclass
class SceneCandidate:
    id: str
    start: float
    end: float
    evidence_class: str
    motion: str
    tags: list[str] = field(default_factory=list)
    rotation_deg: float | None = None
    displacement_mm: float | None = None
    event_start: float | None = None
    event_end: float | None = None
    boundary_uncertainty_s: float = 0.
    left_censored: bool = False
    right_censored: bool = False
    gravity_episodes: list[dict] = field(default_factory=list)
    activity_members: list[dict] = field(default_factory=list)


@dataclass
class DetectionResult:
    candidates: list[SceneCandidate]
    signals: pd.DataFrame
    origins_m: np.ndarray
    rotations: np.ndarray
    corners_m: np.ndarray | None
    settings: DetectionSettings
    registration: Registration | None
    valid_pose: np.ndarray
    block_ids: np.ndarray
    activity_candidates: list[SceneCandidate] | None = None


def _runs(values):
    values = np.asarray(values)
    if not len(values):
        return []
    limits = np.r_[0, np.flatnonzero(values[1:] != values[:-1]) + 1, len(values)]
    return [(int(a), int(b), values[a]) for a, b in zip(limits[:-1], limits[1:])]


def _fit_pose(template, observed):
    usable = np.isfinite(template).all(axis=1) & np.isfinite(observed).all(axis=1)
    if usable.sum() < 3:
        return None
    q, y = template[usable], observed[usable]
    qc, yc = q - q.mean(axis=0), y - y.mean(axis=0)
    u, singular, vt = np.linalg.svd(qc.T @ yc)
    if singular[0] <= 0 or singular[1] <= singular[0] * 1e-8:
        return None
    reflection = np.eye(3)
    reflection[-1, -1] = np.linalg.det(vt.T @ u.T)
    r = vt.T @ reflection @ u.T
    p = y.mean(axis=0) - r @ q.mean(axis=0)
    rms = np.sqrt(np.mean(np.sum((q @ r.T + p - y) ** 2, axis=1)))
    return p, r, rms


def _quadratic(times, values, block_ids, settings, cancelled=None):
    n, width = values.shape
    velocity, acceleration = np.full((n, width), np.nan), np.full((n, width), np.nan)
    residual = np.full(n, np.nan)
    for i, time in enumerate(times):
        if cancelled and i % 100 == 0 and cancelled():
            raise InterruptedError('Scene detection cancelled.')
        if block_ids[i] < 0:
            continue
        a = np.searchsorted(times, time - settings.window_s / 2)
        b = np.searchsorted(times, time + settings.window_s / 2, side='right')
        indices = np.arange(a, b)
        indices = indices[(block_ids[indices] == block_ids[i]) & np.isfinite(values[indices]).all(axis=1)]
        if len(indices) < settings.minimum_points:
            continue
        if times[indices[-1]] - times[indices[0]] < settings.window_s / 4:
            continue
        tau = (times[indices] - time) / settings.window_s
        design = np.column_stack((np.ones(len(tau)), tau, .5 * tau ** 2))
        coefficients, _, rank, _ = np.linalg.lstsq(design, values[indices], rcond=None)
        if rank != 3 or np.linalg.cond(design) > 1e6:
            continue
        velocity[i] = coefficients[1] / settings.window_s
        acceleration[i] = coefficients[2] / settings.window_s ** 2
        residual[i] = np.sqrt(np.mean(np.sum((design @ coefficients[:, :3] - values[indices, :3]) ** 2, axis=1)))
    return velocity, acceleration, residual


def detect_scenes(header, raw, parsed, *, registration=None, settings=None, cancelled=None):
    settings = settings or DetectionSettings()
    times = pd.to_numeric(raw[TimeCols.TIME], errors='coerce').to_numpy(float)
    if not len(times) or not np.isfinite(times).all() or (np.diff(times) <= 0).any():
        raise ValueError('Capture times must be finite and strictly increasing.')
    if len(parsed) != len(raw) or not np.array_equal(parsed.index.to_numpy(float), times):
        raise ValueError('Raw and parsed capture times do not match.')
    units = str(header.get('export_metadata', {}).get('Length Units', '')).strip().lower()
    if units not in ('millimeters', 'millimetres', 'mm'):
        raise ValueError('Scene detection requires capture coordinates declared in millimeters.')
    space = str(header.get('export_metadata', {}).get('Coordinate Space', '')).strip().lower()
    if space != 'global':
        raise ValueError('Scene detection requires global capture coordinates.')
    ids = sorted(c[:-9] for c in parsed if isinstance(c, str) and c.endswith('_FaceInfo'))
    if len(ids) < 3:
        raise ValueError('Scene detection needs at least three marker IDs.')
    points = np.stack([parsed[[f'{mid}_{a}' for a in 'XYZ']].to_numpy(float) for mid in ids], axis=1) / 1000.
    count = np.isfinite(points).all(axis=2).sum(axis=1)
    if registration:
        registration.validate()
        lookup = {m['id']: np.asarray(m['xyz_mm'], float) / 1000. for m in registration.profile['markers']}
        template = np.asarray([lookup.get(mid, [np.nan] * 3) for mid in ids])
    else:
        if count.max() < 3:
            raise ValueError('No frame contains three usable markers.')
        template = points[int(np.argmax(count))].copy()
        template -= np.nanmean(template, axis=0)
    if _fit_pose(template, template) is None:
        raise ValueError('The capture and geometry need three common noncollinear markers.')
    n = len(times)
    origins, rotations, rms = np.full((n, 3), np.nan), np.full((n, 3, 3), np.nan), np.full(n, np.nan)
    for i, observed in enumerate(points):
        if cancelled and i % 100 == 0 and cancelled():
            raise InterruptedError('Scene detection cancelled.')
        fit = _fit_pose(template, observed)
        if fit is not None:
            origins[i], rotations[i], rms[i] = fit
    valid = np.isfinite(rms) & (rms <= settings.marker_residual_m)
    dt = np.diff(times)
    typical_dt = float(np.median(dt)) if len(dt) else settings.window_s
    breaks = np.r_[False, dt > settings.gap_factor * typical_dt]
    jump = np.zeros(n, bool)
    angular_speed = np.full(n, np.nan)
    for i in range(1, n):
        if not (valid[i - 1] and valid[i]) or breaks[i]:
            continue
        angle = Rotation.from_matrix(rotations[i] @ rotations[i - 1].T).magnitude()
        angular_speed[i] = angle / dt[i - 1]
        distance = np.linalg.norm(origins[i] - origins[i - 1])
        if dt[i - 1] < .1 and (np.degrees(angle) > settings.jump_angle_deg or distance > settings.jump_distance_m):
            jump[max(0, i - 1):i + 1] = True
    block_ids = np.full(n, -1, int)
    block = -1
    for i in range(n):
        if valid[i] and not jump[i]:
            if i == 0 or block_ids[i - 1] < 0 or breaks[i]:
                block += 1
            block_ids[i] = block
    motion_origin = origins.copy()
    if registration and registration.com_offset_mm is not None:
        motion_origin += np.einsum('nij,j->ni', rotations, np.asarray(registration.com_offset_mm) / 1000.)
    values = np.column_stack((motion_origin, rotations.reshape(n, 9)))
    velocity, acceleration, residual = _quadratic(times, values, block_ids, settings, cancelled)
    # Activity uses a finite-window relative rotation; a one-frame norm turns
    # tiny alternating pose noise into persistent apparent angular motion.
    angular_speed[:] = np.nan
    angular_excursion = np.full(n, np.nan)
    for i, time in enumerate(times):
        if cancelled and i % 100 == 0 and cancelled():
            raise InterruptedError('Scene detection cancelled.')
        if block_ids[i] < 0:
            continue
        a = np.searchsorted(times, time - settings.window_s / 2)
        b = np.searchsorted(times, time + settings.window_s / 2, side='right')
        indices = np.arange(a, b)
        indices = indices[block_ids[indices] == block_ids[i]]
        if len(indices) >= settings.minimum_points:
            first, last = indices[0], indices[-1]
            angular_speed[i] = Rotation.from_matrix(rotations[last] @ rotations[first].T).magnitude() / (times[last] - times[first])
            angular_excursion[i] = Rotation.from_matrix(rotations[indices] @ rotations[first].T).magnitude().max()
    speed = np.linalg.norm(velocity[:, :3], axis=1)
    gravity_error = np.linalg.norm(acceleration[:, :3] - [0., -9.81, 0.], axis=1)
    contamination = np.full(n, np.nan)
    if registration and registration.com_offset_mm is not None:
        contamination[:] = 0.
    elif registration and registration.com_inside_box_confirmed:
        dims = np.asarray(registration.profile['box_dims_mm']) / 1000.
        within = np.all(np.abs(template[np.isfinite(template).all(axis=1)]) <= dims / 2 + 1e-9)
        if within:
            for i in np.flatnonzero(np.isfinite(acceleration[:, 3:]).all(axis=1)):
                contamination[i] = np.linalg.norm(dims) * np.linalg.norm(acceleration[i, 3:].reshape(3, 3), ord=2)
    gravity_like = (gravity_error <= settings.gravity_error_m_s2) & (residual <= settings.quadratic_residual_m) & (velocity[:, 1] < -.1)
    falling = gravity_like & (contamination <= settings.rotation_contamination_m_s2) & (gravity_error + contamination <= settings.gravity_error_m_s2)
    moving = valid & ~jump & ((speed > settings.moving_speed_m_s)
        | (np.degrees(angular_speed) > settings.moving_angular_speed_deg_s)
        | (np.degrees(angular_excursion) > settings.moving_angular_speed_deg_s * settings.window_s))
    for a, b, state in _runs(moving):
        if not state and a > 0 and b < n and times[b] - times[a - 1] <= settings.join_quiet_s:
            if valid[a:b].all() and not jump[a:b].any() and not breaks[a:b + 1].any():
                moving[a:b] = True
    labels = np.full(n, 'stationary', dtype=object)
    labels[~valid] = 'unclear'
    labels[jump] = 'tracking_jump'
    events = []
    active_runs = []
    for a, b, block_id in _runs(block_ids):
        if block_id >= 0:
            active_runs.extend((a + c, a + d) for c, d, active in _runs(moving[a:b]) if active)
    for a, b in active_runs:
        relative = Rotation.from_matrix(rotations[a:b] @ rotations[a].T).magnitude()
        labels[a:b] = 'tip_or_rotation' if np.degrees(np.max(relative)) >= 2. else 'robot_handling'
        if gravity_like[a:b].any() and not np.isfinite(contamination[a:b]).all():
            labels[a:b] = 'unclear'
        for c, d, gravity in _runs(falling[a:b]):
            c, d = a + c, a + d
            if not gravity or times[d - 1] - times[c] + typical_dt < settings.minimum_fall_s:
                continue
            start = max(a, int(np.searchsorted(times, times[c] - settings.window_s / 2)))
            end = min(b, int(np.searchsorted(times, times[d - 1] + settings.window_s / 2 + settings.followup_s, side='right')))
            labels[start:end] = 'free_fall'
            events.append((start, end, float(times[c]), float(times[d - 1])))
    # Keep missing-time intervals separate from observed stationary motion.
    labels[breaks] = 'unclear'
    candidates = []
    for a, b, kind in _runs(labels):
        usable = np.flatnonzero(valid[a:b]) + a
        tags = []
        if kind == 'unclear':
            if breaks[a:b].any():
                tags.append('time_gap')
            if not valid[a:b].all():
                tags.append('tracking_unavailable')
        if kind == 'tracking_jump':
            tags.append('abrupt_rigid_motion_not_confirmed_error')
        if kind != 'free_fall' and gravity_like[a:b].any() and not np.isfinite(contamination[a:b]).all():
            tags.append('gravity_like_translation_rotation_unverified')
        angle, displacement = None, None
        if len(usable) >= 2:
            first, last = usable[0], usable[-1]
            angle = float(np.degrees(np.max(Rotation.from_matrix(rotations[usable] @ rotations[first].T).magnitude())))
            displacement = float(np.linalg.norm(origins[last] - origins[first]) * 1000.)
        matching = [e for e in events if e[0] < b and e[1] > a] if kind == 'free_fall' else []
        if len(matching) > 1:
            tags.append('multiple_gravity_episodes')
        if registration and registration.com_offset_mm is None and registration.com_inside_box_confirmed:
            tags.append('com_inside_box_confirmed_bound')
        if kind == 'robot_handling':
            tags.append('translation_without_trial_evidence')
        candidates.append(SceneCandidate(
            f'scene_{len(candidates) + 1:03d}', float(times[a]), float(times[b - 1]),
            'unclear' if kind == 'stationary' else str(kind), str(kind), tags, angle, displacement,
            min(e[2] for e in matching) if matching else None,
            max(e[3] for e in matching) if matching else None,
            settings.window_s / 2 + typical_dt,
            bool((times[a] - times[0] <= settings.window_s / 2 or (a > 0 and block_ids[a - 1] < 0) or breaks[a]) and kind != 'stationary'),
            bool((times[-1] - times[b - 1] <= settings.window_s / 2 or (b < n and (block_ids[b] < 0 or breaks[b]))) and kind != 'stationary'),
            [{'gravity_evidence_start': e[2], 'gravity_evidence_end': e[3]} for e in matching]))
    # Unusable and discontinuous solutions are never geometry/contact evidence.
    origins[~valid | jump] = np.nan
    rotations[~valid | jump] = np.nan
    corners = None
    if registration:
        local_corners = calculate_local_box_corners(registration.profile['box_dims_mm']) / 1000.
        corners = origins[:, None, :] + np.einsum('nij,kj->nki', rotations, local_corners)
    angle_signal = np.full(n, np.nan)
    pose_valid = valid & ~jump
    if pose_valid.any():
        first = np.flatnonzero(pose_valid)[0]
        angle_signal[pose_valid] = np.degrees(Rotation.from_matrix(rotations[pose_valid] @ rotations[first].T).magnitude())
    signals = pd.DataFrame({'Relative rotation (deg)': angle_signal,
                            'Vertical speed (mm/s)': velocity[:, 1] * 1000.,
                            'Speed (mm/s)': speed * 1000., 'Solved markers': count,
                            'Window rotation rate (deg/s)': np.degrees(angular_speed),
                            'Window rotation span (deg)': np.degrees(angular_excursion),
                            'Marker fit RMS (mm)': rms * 1000.,
                            'Gravity residual (m/s2)': gravity_error,
                            'Rotation bound (m/s2)': contamination}, index=times)
    result = DetectionResult(candidates, signals, origins, rotations, corners, settings, registration,
                             pose_valid, block_ids, activity_candidates=candidates)
    from .support_cycles import merge_support_cycles
    result.candidates = merge_support_cycles(result, cancelled=cancelled)
    return result
