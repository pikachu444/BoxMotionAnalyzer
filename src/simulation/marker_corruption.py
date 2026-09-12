"""Compose explicit synthetic marker faults without consulting analysis code.

Box poses are immutable truth in world Y-up millimetres. A solved local-axis
half turn changes only rigid-body constraints; physical label permutations are
separate routing operations. Noise is an uncalibrated model, not camera accuracy.
"""
from copy import deepcopy
import math

import numpy as np

from .marker_fixtures import HALF_TURNS, validate_profile


VERSION = '1.0'
COORDINATE_POLICY = 'world-y-up-box-local-fixed-center-v1'
ROTATION_TOLERANCE = 1e-9  # Numerical matrix validity, not an ISTA tolerance.
CHANNELS = ('physical_markers', 'rigid_body_markers')
WINDOW_KINDS = ('gaussian_noise', 'missing', 'freeze', 'reconnect_jump')


def _keys(value, required, optional, name):
    if not isinstance(value, dict) or not required <= set(value) or set(value) - required - optional:
        raise ValueError(f'{name} has missing or unsupported fields.')


def _array(value, shape, name):
    try:
        raw = np.asarray(value)
        if raw.dtype.kind not in 'iuf':
            raise ValueError(f'{name} must contain finite real numbers.')
        result = np.array(raw, dtype=float, copy=True)
    except (TypeError, OverflowError) as error:
        raise ValueError(f'{name} must contain finite real numbers.') from error
    if result.shape != shape or not np.isfinite(result).all():
        raise ValueError(f'{name} must have shape {shape} and finite real values.')
    return result


def _truth(value):
    _keys(value, {'schema_version', 'source_kind', 'coordinate_policy', 'time_s',
                  'body_origin_mm', 'rotation_matrix'}, {'frame', 'com_mm'}, 'Truth trajectory')
    if type(value['schema_version']) is not int or value['schema_version'] != 1:
        raise ValueError('Unsupported truth trajectory schema_version.')
    if value['source_kind'] not in ('handcrafted_dummy', 'mujoco_synthetic'):
        raise ValueError('Corruption requires explicitly synthetic truth, not a real capture.')
    if value['coordinate_policy'] != COORDINATE_POLICY:
        raise ValueError('Truth trajectory must declare the supported world Y-up coordinate policy.')
    try:
        count = len(value['time_s'])
    except TypeError as error:
        raise ValueError('time_s must contain at least two samples.') from error
    times = _array(value['time_s'], (count,), 'time_s')
    if count < 2 or not np.all(np.diff(times) > 0):
        raise ValueError('time_s must contain at least two strictly increasing samples.')
    origins = _array(value['body_origin_mm'], (count, 3), 'body_origin_mm')
    rotations = _array(value['rotation_matrix'], (count, 3, 3), 'rotation_matrix')
    if (not np.all(np.abs(np.swapaxes(rotations, 1, 2) @ rotations - np.eye(3)) <= ROTATION_TOLERANCE)
            or not np.all(np.abs(np.linalg.det(rotations) - 1.) <= ROTATION_TOLERANCE)):
        raise ValueError('rotation_matrix must contain proper rotations; no normalization is applied.')
    frame = np.asarray(value.get('frame', np.arange(count, dtype=np.int64)))
    if (frame.shape != (count,) or frame.dtype.kind not in 'iu' or np.any(frame < 0)
            or np.any(frame > np.iinfo(np.int64).max)):
        raise ValueError('frame must contain nonnegative integers representable as int64.')
    frame = np.array(frame, dtype=np.int64, copy=True)
    if not np.all(np.diff(frame) > 0):
        raise ValueError('frame must contain unique strictly increasing identifiers.')
    com = None if value.get('com_mm') is None else _array(value['com_mm'], (count, 3), 'com_mm')
    return frame, times, origins, rotations, com


def _index(value, count, name, *, endpoint=False):
    if type(value) is not int or not 0 <= value <= (count if endpoint else count - 1):
        raise ValueError(f'{name} must be a valid zero-based sample index.')
    return value


def _events(spec, marker_ids, frame, times):
    _keys(spec, {'schema_version', 'events'}, set(), 'Corruption specification')
    if type(spec['schema_version']) is not int or spec['schema_version'] != 1:
        raise ValueError('Unsupported corruption schema_version.')
    if not isinstance(spec['events'], list):
        raise ValueError('Corruption events must be a list.')
    count, normalized = len(times), []
    known = set(marker_ids)
    for ordinal, event in enumerate(spec['events']):
        if not isinstance(event, dict) or not isinstance(event.get('kind'), str):
            raise ValueError(f'Event {ordinal} needs a supported kind.')
        kind = event['kind']
        common = {'kind', 'channel', 'start_index'}
        if kind in WINDOW_KINDS:
            required = common | {'end_index_exclusive'}
            required |= {'std_mm'} if kind == 'gaussian_noise' else {'offset_mm'} if kind == 'reconnect_jump' else set()
            _keys(event, required, {'marker_ids'}, f'Event {ordinal}')
        elif kind == 'flip_180_local_axis':
            _keys(event, common | {'axis'}, set(), f'Event {ordinal}')
        elif kind == 'label_permutation':
            _keys(event, common | {'end_index_exclusive', 'mapping'}, set(), f'Event {ordinal}')
        else:
            raise ValueError(f'Event {ordinal} has an unsupported kind: {kind}.')
        if event['channel'] not in CHANNELS:
            raise ValueError(f'Event {ordinal} has an unsupported channel.')
        start = _index(event['start_index'], count, 'start_index')
        end = count if kind == 'flip_180_local_axis' else _index(event['end_index_exclusive'], count, 'end_index_exclusive', endpoint=True)
        if end <= start:
            raise ValueError('Event end_index_exclusive must be greater than start_index.')
        item = {'ordinal': ordinal, 'kind': kind, 'channel': event['channel'],
                'start_index': start, 'end_index_exclusive': end,
                'start_time_s': float(times[start]), 'start_frame': int(frame[start]),
                'last_time_s': float(times[end - 1]), 'last_frame': int(frame[end - 1]),
                'end_time_s_exclusive': float(times[end]) if end < count else None,
                'end_frame_exclusive': int(frame[end]) if end < count else None}
        if kind in WINDOW_KINDS:
            selected = event.get('marker_ids', marker_ids)
            if (not isinstance(selected, list) or not selected
                    or any(not isinstance(mid, str) or mid not in known for mid in selected)
                    or len(set(selected)) != len(selected)):
                raise ValueError('marker_ids must be a nonempty list of distinct known IDs.')
            item['marker_ids'] = [mid for mid in marker_ids if mid in selected]
            if kind == 'freeze' and start == 0:
                raise ValueError('Freeze requires a sample before start_index; start 0 is unsupported.')
            if kind == 'gaussian_noise':
                std = event['std_mm']
                if (not isinstance(std, (int, float)) or isinstance(std, bool)
                        or not math.isfinite(std) or std < 0):
                    raise ValueError('std_mm must be a finite nonnegative number.')
                item['std_mm'] = float(std)
            if kind == 'reconnect_jump':
                item['offset_mm'] = _array(event['offset_mm'], (3,), 'offset_mm').tolist()
        elif kind == 'flip_180_local_axis':
            if event['channel'] != 'rigid_body_markers' or event['axis'] not in ('X', 'Y', 'Z'):
                raise ValueError('Local half turns require rigid_body_markers and axis X, Y or Z.')
            item['axis'] = event['axis']
        else:
            mapping = event['mapping']
            if (event['channel'] != 'physical_markers' or not isinstance(mapping, dict)
                    or any(not isinstance(mid, str) or mid not in known for mid in mapping)
                    or any(not isinstance(mid, str) or mid not in known for mid in mapping.values())
                    or set(mapping) != set(mapping.values()) or len(set(mapping.values())) != len(mapping)):
                raise ValueError('Physical label mapping must be a bijection on the same known IDs.')
            item['mapping'] = {mid: mapping[mid] for mid in marker_ids if mid in mapping}
        normalized.append(item)
    return sorted(normalized, key=lambda event: (event['start_index'], event['ordinal']))


def _channel_observations(clean, events, marker_ids, rng):
    """Apply stable-ID faults; freeze snapshots include prior final missing masks."""
    values = clean.copy()
    indices = {mid: index for index, mid in enumerate(marker_ids)}
    freeze_events, missing = [], np.zeros(values.shape[:2], dtype=bool)
    for event in events:
        kind = event['kind']
        if kind not in WINDOW_KINDS:
            continue
        start, end = event['start_index'], event['end_index_exclusive']
        selected = [indices[mid] for mid in event['marker_ids']]
        if kind == 'gaussian_noise':
            noise = rng.normal(0., event['std_mm'], (end - start, len(selected), 3))
            # Random generation can overflow without raising a NumPy FP error.
            # Reject before freeze or missing could conceal an invalid draw.
            if not np.isfinite(noise).all():
                raise ValueError('Gaussian noise draw exceeded the finite numeric range.')
            values[start:end, selected] += noise
        elif kind == 'reconnect_jump':
            values[start:end, selected] += np.asarray(event['offset_mm'])
        elif kind == 'missing':
            missing[start:end, selected] = True
        else:
            freeze_events.append((event, selected))
    snapshots = {}
    for sample in range(len(values)):
        for event, selected in freeze_events:
            if sample == event['start_index']:
                snapshots[event['ordinal']] = values[sample - 1, selected].copy()
            if event['start_index'] <= sample < event['end_index_exclusive']:
                values[sample, selected] = snapshots[event['ordinal']]
        values[sample, missing[sample]] = np.nan
    return values


def apply_corruption(truth_trajectory: dict, marker_profile: dict, corruption_spec: dict, seed: int) -> dict:
    """Return detached truth and synthetic observations; indices never interpolate time."""
    try:
        with np.errstate(over='raise', invalid='raise'):
            return _apply_corruption(truth_trajectory, marker_profile, corruption_spec, seed)
    except (FloatingPointError, OverflowError) as error:
        raise ValueError('Corruption arithmetic exceeded the finite numeric range.') from error


def _apply_corruption(truth_trajectory, marker_profile, corruption_spec, seed):
    if type(seed) is not int or seed < 0:
        raise ValueError('seed must be a nonnegative integer, not a boolean.')
    frame, times, origins, rotations, com = _truth(truth_trajectory)
    profile = deepcopy(marker_profile)
    try:
        layout_hash = validate_profile(profile)
    except (KeyError, TypeError, AttributeError) as error:
        raise ValueError('Invalid marker profile.') from error
    marker_ids = [marker['id'] for marker in profile['markers']]
    events = _events(corruption_spec, marker_ids, frame, times)
    local = np.asarray([marker['xyz_mm'] for marker in profile['markers']], dtype=float)
    truth_markers = np.einsum('nij,mj->nmi', rotations, local) + origins[:, None, :]
    if not np.isfinite(truth_markers).all():
        raise ValueError('Truth marker geometry exceeded the finite numeric range.')
    solved_rotations = rotations.copy()
    for event in events:
        if event['kind'] == 'flip_180_local_axis':
            solved_rotations[event['start_index']:] = solved_rotations[event['start_index']:] @ HALF_TURNS[event['axis']]
    solved = np.einsum('nij,mj->nmi', solved_rotations, local) + origins[:, None, :]
    if not np.isfinite(solved).all():
        raise ValueError('Solved marker geometry exceeded the finite numeric range.')
    # Independent child streams keep one channel's noise separate from the other.
    streams = [np.random.default_rng(child) for child in np.random.SeedSequence(seed).spawn(2)]
    observations = {}
    for channel, clean, rng in zip(CHANNELS, (truth_markers, solved), streams):
        observations[channel] = _channel_observations(clean, [e for e in events if e['channel'] == channel], marker_ids, rng)
    physical = observations['physical_markers']
    id_indices = {mid: index for index, mid in enumerate(marker_ids)}
    for event in events:
        if event['kind'] != 'label_permutation':
            continue
        window = slice(event['start_index'], event['end_index_exclusive'])
        destination = [id_indices[mid] for mid in event['mapping']]
        source = [id_indices[mid] for mid in event['mapping'].values()]
        physical[window, destination] = physical[window, source].copy()
    manifest = {
        'schema_version': 1, 'generator_version': VERSION,
        'source_kind': truth_trajectory['source_kind'], 'evidence_level': 'synthetic_integration',
        'seed': seed, 'profile': profile, 'layout_hash': layout_hash,
        'coordinate_policy': COORDINATE_POLICY,
        'units': {'length': 'mm', 'time': 's', 'rotation': 'dimensionless rotation matrix'},
        'operation_order': ['truth geometry', 'cumulative solved local half turns',
                            'stable-ID noise and world offsets', 'freeze prior final pre-label sample',
                            'missing mask', 'physical label routing'],
        'event_order': 'start_index then original ordinal within each operation',
        'index_semantics': 'zero-based sample positions; start inclusive, end exclusive; no interpolation',
        'endpoint_semantics': 'last_* is the included final sample; end_*_exclusive is the next actual sample or null at N',
        'marker_identity': 'physical stable IDs precede label routing; output labels may refer to other physical IDs',
        'mapping_composition': 'each mapping copies its source from currently routed output labels, simultaneously, then the next mapping composes on that result',
        'half_turn_semantics': 'R_solved = R_truth @ F; F accumulates local half turns; physical truth is unchanged',
        'noise_model': 'independent zero-mean Gaussian coordinate noise; uncalibrated synthetic model',
        'rotation_matrix_tolerance': ROTATION_TOLERANCE,
        'events': events, 'expected_approval': False, 'expected_recommendation': None,
    }
    return {'frame': frame, 'time_s': times, 'body_origin_mm': origins, 'rotation_matrix': rotations,
            'com_mm': com, 'truth_markers': truth_markers,
            'physical_markers': physical, 'rigid_body_markers': observations['rigid_body_markers'],
            'manifest': manifest}
