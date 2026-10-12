"""Versioned evaluator contracts. This module never processes a truth pose."""
from __future__ import annotations

from dataclasses import asdict
import hashlib
import json
from pathlib import Path

import numpy as np

PLAN_SPEC = 'ISTA6A-PLAN-20261001-v1'
SCHEMA_VERSION = 1
SEMANTIC_VERSION = 'capture-replay-geocenter-v1'
METRIC_STATUSES = {'valid', 'not_detected', 'unavailable', 'out_of_window', 'ambiguous', 'failed'}
REFERENCE_CATEGORY_METRICS = {'reference_face','contact_state','impact_sequence',
                              'observed_first_contact','first_contact','final_face'}
REFERENCE_NUMERIC_METRICS = {'t1','t2','equivalent_height','vertical_velocity','horizontal_speed',
    'angular_speed','final_rotation_deg','maximum_rotation_deg','BetaAtT1MinusDeg','ThetaLongAtT1MinusDeg',
    'ThetaShortAtT1MinusDeg','DeltaHAtT1Minus_mm','MaxBetaDeg','MaxAbsThetaLongDeg',
    'MaxAbsThetaShortDeg','MaxDeltaH_mm','contact_confidence','ContactConfidence'}


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def file_digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def envelope(kind, **fields):
    return dict(schema_version=SCHEMA_VERSION, plan_spec=PLAN_SPEC, object_type=kind, **fields)


def validate_envelope(value, kind):
    if (type(value.get('schema_version')) is not int or value.get('schema_version') != SCHEMA_VERSION or value.get('plan_spec') != PLAN_SPEC
            or value.get('object_type') != kind):
        raise ValueError(f'Unsupported {kind} schema/plan_spec.')
    canonical(value)  # Reject non-JSON and nonfinite values, including nested fields.


def read_json(path, kind):
    value = json.loads(Path(path).read_text(encoding='utf-8-sig'),
                       parse_constant=lambda token: (_ for _ in ()).throw(ValueError(token)))
    validate_envelope(value, kind)
    return value


def write_new_json(path, value):
    # Baselines and prior run evidence are immutable. No update-baseline option.
    with Path(path).open('x', encoding='utf-8') as stream:
        stream.write(json.dumps(value, indent=2, allow_nan=False) + '\n')


def metric(value=None, status='valid', reason=''):
    if status not in METRIC_STATUSES or (status == 'valid' and value is None):
        raise ValueError('Metric requires a value and a supported status.')
    return dict(value=value, status=status, reason=reason)


def marker_semantics():
    # Retain #135's historical partial digest for replay, without promoting it
    # to complete semantics. New files also carry #138's explicit source-bound
    # marker_profile_identity; missing artifact semantics stays unknown.
    from src.config.config_app import FACE_DEFINITIONS
    from src.simulation.marker_fixtures import FACE_NORMALS
    from src.analysis.pipeline.face_assignment import FACE_MAPS
    return dict(version='legacy-face-assignment-v3', sha256=digest(dict(
        faces=FACE_DEFINITIONS, normals=FACE_NORMALS, half_turn_face_maps=FACE_MAPS)))


def boundary(times, index):
    if index < len(times):
        return dict(value=float(times[index]), status='valid', basis='original_record_timestamp')
    # Never invent timestamp[N] or discard record N-1. No extrapolation here.
    return dict(value=None, status='unavailable', basis='EOF exclusive boundary has no timestamp')


def anchor(raw, start, end):
    if not (type(start) is int and type(end) is int and 0 <= start < end <= len(raw)):
        raise ValueError('Record interval must be nonempty [start,end).')
    times = np.asarray(raw.iloc[:, 1], float)
    # Adjacent observed records, not candidate ordinals or Frame values.
    rows = []
    for i in sorted(set(range(max(0, start - 2), min(len(raw), start + 3))) |
                    set(range(max(0, end - 2), min(len(raw), end + 3)))):
        rows.append([i, *[None if str(v).strip() == '' or str(v).lower() == 'nan' else str(v)
                          for v in raw.iloc[i]]])
    return dict(start_record=start, end_record_exclusive=end,
                start_raw_time_s=float(times[start]), end_raw_time_s=boundary(times, end),
                adjacent_sha256=digest(rows))


def candidate_anchor(raw, candidate):
    times = np.asarray(raw.iloc[:, 1], float)
    # Legacy detector candidates include both sampled endpoints.
    start = int(np.searchsorted(times, candidate.start, side='left'))
    end = int(np.searchsorted(times, candidate.end, side='right'))
    return anchor(raw, start, end)


def replay_mapping(raw, decisions, candidates):
    """Bipartite interval mapping; refuse split/merge/missing/ambiguous transfers.

    Manual approvals remain separate identities even if they overlap automatic
    candidates. All automatic candidates must have one reviewed correspondence.
    """
    automatic = [dict(candidate_id=c.id, anchor=candidate_anchor(raw, c), evidence=asdict(c))
                 for c in candidates]
    reviewed = [d for d in decisions if d['origin'] == 'automatic']
    overlaps = lambda a, b: max(a['start_record'], b['start_record']) < min(
        a['end_record_exclusive'], b['end_record_exclusive'])
    edges = [[i for i, c in enumerate(automatic) if overlaps(d['detected_anchor'], c['anchor'])]
             for d in reviewed]
    reverse = [[i for i, e in enumerate(edges) if j in e] for j in range(len(automatic))]
    mappings = []
    for d in decisions:
        saved = d['anchor']
        integrity = anchor(raw, saved['start_record'], saved['end_record_exclusive']) == saved
        status, matched = 'manual_bound', []
        if not integrity:
            status = 'stale_anchor'
        elif d['origin'] == 'automatic':
            i = reviewed.index(d)
            matched = edges[i]
            if not matched:
                status = 'missing'
            elif len(matched) > 1:
                intervals = [automatic[j]['anchor'] for j in matched]
                status = 'split' if len({(a['start_record'], a['end_record_exclusive']) for a in intervals}) > 1 else 'ambiguous'
            elif len(reverse[matched[0]]) > 1:
                status = 'merged'
            elif automatic[matched[0]]['anchor'] != d['detected_anchor']:
                status = 'changed_boundary'
            else:
                status = 'matched'
        mappings.append(dict(review_id=d['review_id'], status=status,
                             candidate_ids=[automatic[j]['candidate_id'] for j in matched]))
    for j, c in enumerate(automatic):
        c['mapping_status'] = 'unreviewed' if not reverse[j] else next(
            m['status'] for m in mappings if c['candidate_id'] in m['candidate_ids'])
    return mappings, automatic


def validate_fixture(fixture):
    validate_envelope(fixture, 'CaptureReviewFixture')
    for key in ('case_id', 'raw_sha256', 'raw_root_kind', 'relative_path', 'capture_time_field',
                'marker_profile_id', 'marker_profile_hash', 'marker_semantics', 'geometry',
                'test_type', 'type_source', 'flip_decisions', 'scene_decisions',
                'effective_processing_config', 'approval', 'reference', 'tolerance',
                'marker_profile', 'marker_correction_default', 'capture_end_raw_time_s'):
        if key not in fixture:
            raise ValueError(f'Missing fixture field: {key}')
    if (fixture['raw_root_kind'] != 'public_synthetic' or fixture['capture_time_field'] != 'Time'
            or fixture['test_type'] not in ('G', 'H', 'Unknown')):
        raise ValueError('Unsupported source/time/Type contract.')
    path = Path(fixture['relative_path'])
    if path.is_absolute() or '..' in path.parts:
        raise ValueError('Raw path must be relative to the explicit asset root.')
    geom = fixture['geometry']
    required_geometry = ('box_dims_mm', 'floor_y_mm', 'vertical_axis', 'position_units',
                         'world_frame', 'local_frame', 'rotation_convention',
                         'origin_to_geocenter_mm', 'origin_to_com_mm', 'world_transform')
    if any(k not in geom for k in required_geometry):
        raise ValueError('Incomplete canonical geometry.')
    def numbers(value):
        if isinstance(value, list):
            return all(numbers(v) for v in value)
        return type(value) in (int, float) and np.isfinite(value)
    for key in ('box_dims_mm', 'floor_y_mm', 'origin_to_geocenter_mm', 'origin_to_com_mm', 'world_transform'):
        if not numbers(geom[key]):
            raise ValueError('Geometry requires finite numeric values, not bool/text: ' + key)
    dims = np.asarray(geom['box_dims_mm'], float)
    if dims.shape != (3,) or not np.isfinite(dims).all() or (dims <= 0).any():
        raise ValueError('Invalid geometry dimensions.')
    if (geom['position_units'] != 'mm' or geom['vertical_axis'] != 'Y' or
            geom['world_frame'] != 'world-y-up' or geom['local_frame'] != 'box-xyz' or
            geom['rotation_convention'] != 'local-to-world-matrix' or
            geom['world_transform'] != np.eye(4).tolist()):
        raise ValueError('Unsupported units/frame/transform; explicit migration required.')
    for key in ('origin_to_geocenter_mm', 'origin_to_com_mm'):
        offset = np.asarray(geom[key], float)
        if offset.shape != (3,) or not np.isfinite(offset).all():
            raise ValueError('Canonical origin offsets must be known finite body-local vectors.')
    if not np.isfinite(geom['floor_y_mm']):
        raise ValueError('Invalid floor height.')
    config = fixture['effective_processing_config']
    if set(config) != {'processing_mode', 'analysis_options', 'enable_result_resampling'}:
        raise ValueError('Only actual processing options may enter the analyzer (no labels/truth).')
    if fixture['marker_correction_default'] != 'OFF':
        raise ValueError('Marker correction must remain default OFF.')
    if config.get('enable_result_resampling') is not False:
        raise ValueError('Record-exact regression forbids result resampling.')
    from src.config.config_analysis_ui import get_raw_mode_options
    defaults = get_raw_mode_options()
    options = config['analysis_options']
    if (config['processing_mode'] not in ('raw', 'smoothing', 'advanced') or set(options) != set(defaults) or
            any(not numbers(options[k]) if type(v) in (int,float) else type(options[k]) is not type(v)
                for k,v in defaults.items())):
        raise ValueError('Unsupported effective processing options; truth/labels are forbidden.')
    ids = []
    for d in fixture['scene_decisions']:
        ids.append(d['review_id'])
        if d['origin'] not in ('manual', 'automatic') or d['decision'] not in ('include', 'exclude'):
            raise ValueError('Invalid scene decision enum.')
        if d['test_type'] not in ('G', 'H', 'Unknown') or d['label_status'] not in ('confirmed', 'unconfirmed'):
            raise ValueError('Invalid scene label status.')
        if d['label_status'] == 'unconfirmed' and d['scenario_id'] is not None:
            raise ValueError('Unconfirmed scenario must remain null.')
        if d['origin'] == 'automatic' and 'detected_anchor' not in d:
            raise ValueError('Automatic approval requires a detected anchor.')
        for k in ('anchor', 'edited', 'evidence', 'slice_mode', 'padding_rows'):
            if k not in d:
                raise ValueError(f'Missing scene field: {k}')
        if d['slice_mode'] != 'record-half-open' or type(d['padding_rows']) is not int or d['padding_rows'] < 0:
            raise ValueError('Unsupported slice contract.')
    if len(ids) != len(set(ids)):
        raise ValueError('Duplicate review identity.')
    previous = -1
    for f in fixture['flip_decisions']:
        row = f['original_record_index']
        if type(row) is not int or row <= previous or f['axis'] not in ('OFF', 'X', 'Y', 'Z'):
            raise ValueError('Flip decisions must retain strict chronological order and explicit OFF/axis.')
        previous = row
    if fixture['marker_semantics'] != marker_semantics():
        raise ValueError('Stale marker semantics; review #138 integration.')
    if 'marker_profile_identity' in fixture:
        from src.utils.marker_profile_identity import validate_identity
        validate_identity(fixture['marker_profile_identity'])
        if fixture['marker_profile_identity']['source_profile'] != fixture['marker_profile']:
            raise ValueError('Stale replay profile semantic identity.')
    from src.simulation.marker_fixtures import validate_profile
    if (validate_profile(fixture['marker_profile']) != fixture['marker_profile_hash'] or
            fixture['marker_profile']['profile_id'] != fixture['marker_profile_id'] or
            fixture['marker_profile']['box_dims_mm'] != geom['box_dims_mm']):
        raise ValueError('Marker profile identity/geometry mismatch.')


def validate_reference(value):
    validate_envelope(value, 'TrajectoryReference')
    for scene in value['scenes'].values():
        trajectory = scene['trajectory']
        records, times, mask = (trajectory[k] for k in ('original_record_index', 'raw_time_s', 'valid_mask'))
        if (not records or any(type(v) is not int for v in records) or
                any(b != a + 1 for a, b in zip(records, records[1:])) or
                len(records) != len(times) or len(times) != len(mask) or
                any(type(v) is not bool for v in mask)):
            raise ValueError('Invalid required reference record/mask population.')
        def numbers(items, nullable=False):
            if isinstance(items, list):
                return all(numbers(v, nullable) for v in items)
            return (nullable and items is None) or (type(items) in (int, float) and np.isfinite(items))
        if not numbers(times) or any(b <= a for a, b in zip(times, times[1:])):
            raise ValueError('Reference raw time must be finite numeric and increasing.')
        for key in ('geocenter_position_mm', 'rotation_matrix', 'corners_mm', 'floor_height_mm'):
            if not numbers(trajectory[key], True):
                raise ValueError('Invalid reference numeric payload: ' + key)
            data = np.asarray(trajectory[key],float)
            suffix={'geocenter_position_mm':(3,),'rotation_matrix':(3,3),'corners_mm':(8,3),'floor_height_mm':(8,)}[key]
            if data.shape!=(len(records),*suffix):
                raise ValueError('Invalid required reference shape: ' + key)
            if (not np.array_equal(np.isfinite(data.reshape(len(records),-1)).all(axis=1),mask) or
                    not np.isnan(data[np.logical_not(mask)]).all()):
                raise ValueError('Invalid reference valid/unavailable mask: ' + key)
        for key,m in scene['metrics'].items():
            if key not in REFERENCE_CATEGORY_METRICS | REFERENCE_NUMERIC_METRICS:
                raise ValueError('Unsupported reference metric contract: ' + key)
            if (m['status'] not in METRIC_STATUSES or (m['status'] == 'valid' and m['value'] is None)
                    or (m['status'] != 'valid' and m['value'] is not None)):
                raise ValueError('Invalid reference metric status/value.')
            if type(m['value']) is bool:
                raise ValueError('Reference metric boolean cannot masquerade as numeric/category value.')
            if m['status']=='valid':
                if key in REFERENCE_NUMERIC_METRICS and (type(m['value']) not in (int,float)
                        or not np.isfinite(m['value']) or not m.get('tolerance')):
                    raise ValueError('Numeric reference metric requires a finite number and explicit tolerance: ' + key)
                if key in REFERENCE_CATEGORY_METRICS and (type(m['value']) is not str or not m['value'] or 'tolerance' in m):
                    raise ValueError('Categorical reference metric requires its declared text type: ' + key)
            if 'tolerance' in m and (type(m['value']) not in (int, float) or not np.isfinite(m['value'])):
                raise ValueError('Reference metric requires finite numeric values.')


def canonical_pose(origin, rotations, velocity, omega_world, origin_to_center, origin_to_com):
    """Body-local offsets; angular term is required even for nonzero COM."""
    arm = np.einsum('nij,j->ni', rotations, origin_to_center)
    center = origin + arm
    com = origin + np.einsum('nij,j->ni', rotations, origin_to_com)
    center_velocity = velocity + np.cross(omega_world, arm)
    return center, com, center_velocity
