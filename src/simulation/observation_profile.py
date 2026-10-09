"""PUB10 virtual observations: ideal cuboid visibility and stationary OU stress.

Camera, masks and noise are evaluation-only. This models neither optics nor a
Motive solver. All selections use actual timestamps and stable pre-routing IDs.
"""
from copy import deepcopy
import hashlib
import math

import numpy as np

from src.config.marker_semantics import FACE_NORMALS
from src.utils.marker_profile_identity import envelope, validate_envelope, digest
from .marker_fixtures import validate_profile

MODEL = 'virtual-box-observation-v1'
ADAPTERS = ('physical_only', 'visibility-mask-to-solved-v1')
FRAME = 'world-y-up-box-local-fixed-center-v1'
FACING_ROUNDOFF = 1e-12  # Conservative dimensionless representation band, not optical calibration.


def _keys(value, keys, label):
    if not isinstance(value, dict) or set(value) != set(keys):
        raise ValueError(label + ' has missing or unsupported fields.')


def _number(value, label, *, minimum=None, positive=False):
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError(label + ' must be a finite real number, not bool or text.')
    if minimum is not None and value < minimum or positive and value <= 0:
        raise ValueError(label + ' is outside the supported range.')


def _text(value, label):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(label + ' must be nonempty text.')


def _vector(value, count, label):
    if not isinstance(value, list) or len(value) != count:
        raise ValueError(label + ' has an invalid shape.')
    for item in value:
        _number(item, label)


def orthographic_camera(position_mm, camera_to_world, *, half_extent_mm=(10000., 10000.),
                        near_mm=0., far_mm=100000., grazing_cos=0.):
    """Camera +Z is forward, +X/+Y span its rectangular view; R is proper."""
    return dict(model='orthographic-assigned-face-v1', frame=FRAME, units='mm',
        position_mm=list(position_mm), camera_to_world=deepcopy(camera_to_world),
        half_extent_mm=list(half_extent_mm), near_mm=near_mm, far_mm=far_mm,
        grazing_cos=grazing_cos)


def observation_profile(marker_profile, *, profile_id='virtual-observations', camera=None,
                        groups=(), occlusions=(), noise=(), adapter='physical_only'):
    value = envelope('VirtualObservationProfile', profile_id=profile_id,
        source=dict(kind='synthetic_configuration', id='pub10-virtual-v1'), model=MODEL,
        marker_profile_hash=validate_profile(marker_profile), calibration_status='uncalibrated',
        frame=FRAME, units='mm-s', adapter=adapter, camera=deepcopy(camera),
        groups=deepcopy(list(groups)), occlusions=deepcopy(list(occlusions)), noise=deepcopy(list(noise)))
    value['content_hash'] = digest(value)
    validate_observation_profile(value, marker_profile)
    return value


def validate_observation_profile(value, marker_profile):
    validate_envelope(value, 'VirtualObservationProfile')
    _keys(value, ('schema_version', 'plan_spec', 'object_type', 'profile_id', 'source',
        'model', 'marker_profile_hash', 'calibration_status', 'frame', 'units', 'adapter',
        'camera', 'groups', 'occlusions', 'noise', 'content_hash'), 'Observation profile')
    if value['content_hash'] != digest({k: v for k, v in value.items() if k != 'content_hash'}):
        raise ValueError('Stale observation profile content hash.')
    _text(value['profile_id'], 'Observation profile ID')
    _keys(value['source'], ('kind', 'id'), 'Observation source')
    _text(value['source']['id'], 'Observation source ID')
    if (value['source']['kind'] != 'synthetic_configuration' or value['model'] != MODEL
            or value['frame'] != FRAME or value['units'] != 'mm-s'
            or value['calibration_status'] != 'uncalibrated' or value['adapter'] not in ADAPTERS):
        raise ValueError('Unsupported observation source/model/frame/units/adapter/calibration.')
    if value['marker_profile_hash'] != validate_profile(marker_profile):
        raise ValueError('Observation profile belongs to a different marker profile.')
    camera = value['camera']
    if camera is not None:
        _keys(camera, ('model', 'frame', 'units', 'position_mm', 'camera_to_world',
            'half_extent_mm', 'near_mm', 'far_mm', 'grazing_cos'), 'Camera')
        if camera['model'] != 'orthographic-assigned-face-v1' or camera['frame'] != FRAME or camera['units'] != 'mm':
            raise ValueError('Unsupported camera model/frame/units.')
        _vector(camera['position_mm'], 3, 'Camera position')
        matrix = camera['camera_to_world']
        if not isinstance(matrix, list) or len(matrix) != 3:
            raise ValueError('Camera rotation must be a proper 3x3 matrix.')
        for row in matrix:
            _vector(row, 3, 'Camera rotation')
        r = np.asarray(matrix)
        with np.errstate(over='raise', invalid='raise'):
            if not np.allclose(r.T @ r, np.eye(3), rtol=0, atol=1e-9) or abs(np.linalg.det(r)-1) > 1e-9:
                raise ValueError('Camera rotation must be proper; no normalization is applied.')
        _vector(camera['half_extent_mm'], 2, 'Camera half extent')
        if min(camera['half_extent_mm']) <= 0:
            raise ValueError('Camera half extents must be positive.')
        _number(camera['near_mm'], 'Camera near', minimum=0)
        _number(camera['far_mm'], 'Camera far', positive=True)
        if camera['far_mm'] <= camera['near_mm']:
            raise ValueError('Camera far must exceed near.')
        _number(camera['grazing_cos'], 'Camera grazing cosine', minimum=0)
        if camera['grazing_cos'] >= 1:
            raise ValueError('Camera grazing cosine must be less than one.')
    ids = [m['id'] for m in marker_profile['markers']]
    def members(selected):
        if (not isinstance(selected, list) or not selected
                or any(not isinstance(mid, str) or mid not in ids for mid in selected)
                or len(set(selected)) != len(selected)):
            raise ValueError('Observation members must be distinct declared stable marker IDs.')
    groups = {}
    if not all(isinstance(value[k], list) for k in ('groups', 'occlusions', 'noise')):
        raise ValueError('Observation groups/occlusions/noise must be lists.')
    for group in value['groups']:
        _keys(group, ('group_id', 'marker_ids'), 'Occlusion group')
        _text(group['group_id'], 'Group ID'); members(group['marker_ids'])
        if group['group_id'] in groups:
            raise ValueError('Duplicate occlusion group ID.')
        groups[group['group_id']] = group['marker_ids']
    def window(item):
        _number(item['start_s'], 'Observation start')
        _number(item['end_s'], 'Observation end')
        if item['start_s'] >= item['end_s']:
            raise ValueError('Observation window must increase: [start_s,end_s).')
    for item in value['occlusions']:
        _keys(item, ('group_id', 'start_s', 'end_s'), 'Group occlusion')
        if not isinstance(item['group_id'], str) or item['group_id'] not in groups:
            raise ValueError('Occlusion must reference a declared group.')
        window(item)
    noise_ids = set()
    for item in value['noise']:
        _keys(item, ('noise_id', 'channel', 'marker_ids', 'start_s', 'end_s', 'std_mm', 'tau_s'), 'OU noise')
        _text(item['noise_id'], 'Noise ID')
        if item['noise_id'] in noise_ids:
            raise ValueError('Noise IDs must be unique.')
        noise_ids.add(item['noise_id'])
        if item['channel'] not in ('physical_markers', 'rigid_body_markers'):
            raise ValueError('Unsupported OU noise channel.')
        members(item['marker_ids']); window(item)
        _number(item['std_mm'], 'OU stationary standard deviation', minimum=0)
        _number(item['tau_s'], 'OU correlation time', positive=True)
    return value


def _samples(times, item):
    # Select actual records; endpoints between records never create new samples.
    indices = np.flatnonzero((times >= item['start_s']) & (times < item['end_s']))
    if not len(indices):
        raise ValueError('Observation window contains no actual samples.')
    if item['start_s'] < times[0] or item['start_s'] > times[-1] or item['end_s'] > times[-1]:
        # End after the last record has no known timestamp. A window may include
        # it using a finite exclusive boundary no farther than the last Δt.
        stop = times[-1] + (times[-1]-times[-2])
        if not math.isfinite(stop) or item['start_s'] < times[0] or item['start_s'] > times[-1] or item['end_s'] > stop:
            raise ValueError('Observation window is outside the recorded clock.')
    return indices


def _noise_rng(seed, channel, noise_id):
    words = np.frombuffer(hashlib.sha256(noise_id.encode('utf-8')).digest(), dtype='<u4').tolist()
    return np.random.default_rng(np.random.SeedSequence(seed,
        spawn_key=(143, ('physical_markers', 'rigid_body_markers').index(channel), *words)))


def stationary_ou(times, sigma, tau, rng, shape):
    """Exact sampled recurrence; all latent records evolve even when unobserved."""
    state = rng.normal(size=shape) * sigma
    for k, at in enumerate(times):
        if k:
            dt = float(at-times[k-1])
            a = math.exp(-dt/tau)
            state = a*state + sigma*math.sqrt(-math.expm1(-2*dt/tau))*rng.normal(size=shape)
        if not np.isfinite(state).all():
            raise ValueError('OU arithmetic exceeded the finite range.')
        yield state


def observation_effects(profile, marker_profile, times, origins, rotations, truth_markers, seed):
    """Return stable-ID masks/additive noise and evaluation evidence only."""
    validate_observation_profile(profile, marker_profile)
    intervals = np.diff(times)
    if not np.isfinite(intervals).all() or np.any(intervals <= 0):
        raise ValueError('Observation timestamps require finite positive actual intervals.')
    ids = [m['id'] for m in marker_profile['markers']]
    missing = np.zeros(truth_markers.shape[:2], dtype=bool)
    camera_visible = None
    camera = profile['camera']
    if camera is not None:
        r = np.asarray(camera['camera_to_world'])
        q = (truth_markers-np.asarray(camera['position_mm'])) @ r
        normals = np.asarray([FACE_NORMALS[m['face']] for m in marker_profile['markers']])
        world_normals = np.einsum('nij,mj->nmi', rotations, normals)
        facing = world_normals @ (-r[:, 2]) > camera['grazing_cos'] + FACING_ROUNDOFF
        inside = ((np.abs(q[:, :, :2]) <= camera['half_extent_mm']).all(axis=2)
            & (q[:, :, 2] >= camera['near_mm']) & (q[:, :, 2] <= camera['far_mm']))
        if not np.isfinite(q).all():
            raise ValueError('Camera arithmetic exceeded the finite range.')
        camera_visible = facing & inside
        missing |= ~camera_visible
    groups = {g['group_id']: g['marker_ids'] for g in profile['groups']}
    group_records = []
    for item in profile['occlusions']:
        samples = _samples(times, item)
        selected = [ids.index(mid) for mid in groups[item['group_id']]]
        missing[np.ix_(samples, selected)] = True
        group_records.append(dict(**item, marker_ids=groups[item['group_id']],
            original_record_indices=samples.tolist(), actual_time_s=times[samples].tolist()))
    noise = {ch: np.zeros_like(truth_markers) for ch in ('physical_markers', 'rigid_body_markers')}
    for item in profile['noise']:
        samples = _samples(times, item)
        # Stream order follows declared marker order, independent of member-list order.
        selected = [i for i, mid in enumerate(ids) if mid in item['marker_ids']]
        rng = _noise_rng(seed, item['channel'], item['noise_id'])
        sigma, tau = item['std_mm'], item['tau_s']
        for sample, state in zip(samples, stationary_ou(times[samples], sigma, tau, rng, (len(selected),3))):
            noise[item['channel']][sample, selected] += state
    evidence = envelope('VirtualObservationEvidence', profile=deepcopy(profile),
        profile_hash=profile['content_hash'], calibration_status='uncalibrated',
        stable_marker_ids=ids, original_record_indices=list(range(len(times))),
        actual_time_s=times.tolist(), camera_visible=None if camera_visible is None else camera_visible.tolist(),
        camera_status='disabled' if camera is None else 'virtual', group_masks=group_records,
        facing_roundoff_guard=FACING_ROUNDOFF,
        combined_unavailable=missing.tolist(), adapter=profile['adapter'],
        noise_semantics='Independent marker/XYZ stationary OU in output-world mm; not rigid pose noise or drift.',
        noise_initialization='stationary at first actual selected sample; reset per window/noise_id',
        noise_gaps='state evolves through visibility/missing/freeze; no reconnect reset',
        rng='PCG64; SeedSequence(seed, spawn_key=(143,channel,sha256(noise_id) little-endian uint32 words)); legacy spawn(2) unchanged')
    return missing, noise, evidence
