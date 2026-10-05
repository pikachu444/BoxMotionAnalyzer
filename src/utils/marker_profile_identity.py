"""Marker interpretation identities, separate from unchanged author profile hashes.

Only declared geometry enters this contract; no observation or simulator truth.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from itertools import permutations, product

import numpy as np

PLAN_SPEC = 'ISTA6A-PLAN-20261001-v1'
SCHEMA_VERSION = 1
POLICY_VERSION = 'marker-interpretation-v1'
COORDINATE_POLICY = 'world-y-up-box-local-fixed-center-v1'
UNITS_POLICY = 'bma-mm-s-rotvec-rad-summary-deg-v1'
LOCAL_FRAME = dict(origin='box-geometric-center', handedness='right',
                   axes={'X': 'Right', 'Y': 'Top', 'Z': 'Front'},
                   position_units='mm', time_units='s',
                   rotation='local-to-world; p_world = R @ p_local + T')


def _proper_axis_rotations():
    rotations=[]
    for order in permutations(range(3)):
        for signs in product((-1,1),repeat=3):
            matrix=np.eye(3)[:,order]*signs
            if np.linalg.det(matrix)>0 and not np.array_equal(matrix,np.eye(3)): rotations.append(matrix)
    return tuple(rotations)


_AXIS_ROTATIONS = _proper_axis_rotations()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode('utf-8')).hexdigest()


def envelope(kind, **fields):
    return dict(schema_version=SCHEMA_VERSION, plan_spec=PLAN_SPEC, object_type=kind, **fields)


def validate_envelope(value, kind):
    if (not isinstance(value, dict) or type(value.get('schema_version')) is not int
            or value['schema_version'] != SCHEMA_VERSION or value.get('plan_spec') != PLAN_SPEC
            or value.get('object_type') != kind):
        raise ValueError(f'Unsupported {kind} schema/plan_spec.')
    canonical(value)


def interpretation_policy():
    """Bind actual consumer/producer constants, including fixed-code meanings."""
    from src.config.config_app import FACE_DEFINITIONS, WORLD_VERTICAL_AXIS_INDEX, calculate_local_box_corners
    from src.config.data_columns import FACE_PREFIX_TO_INFO
    from src.simulation.marker_fixtures import WORLD_TO_ANALYSIS
    from src.config.marker_semantics import FACE_NORMALS, HALF_TURNS, FACE_MAPS, LOCAL_AXIS_INDEX, LOCAL_HALF_TURN_ROTVECS
    return envelope('MarkerInterpretationPolicy', version=POLICY_VERSION,
        coordinate_policy=COORDINATE_POLICY, units_policy=UNITS_POLICY,
        local_frame=deepcopy(LOCAL_FRAME), world_vertical_axis_index=int(WORLD_VERTICAL_AXIS_INDEX),
        label_prefixes={key: value.upper() for key, value in FACE_PREFIX_TO_INFO.items()},
        faces=deepcopy(FACE_DEFINITIONS), normals={key: list(value) for key, value in FACE_NORMALS.items()},
        corner_basis=calculate_local_box_corners([2., 2., 2.]).tolist(),
        simulation_world_transform=WORLD_TO_ANALYSIS.tolist(),
        simulation_half_turns={key: value.tolist() for key, value in HALF_TURNS.items()},
        analysis_half_turn_rotvecs={axis: vector.tolist() for axis, vector in LOCAL_HALF_TURN_ROTVECS.items()},
        local_axis_indices=deepcopy(LOCAL_AXIS_INDEX),
        half_turn_face_maps=deepcopy(FACE_MAPS),
        half_turn_operation='cumulative local R @ F; assigned face map; observed XYZ and IDs unchanged')


def profile_identity(profile, *, policy=None):
    from src.simulation.marker_fixtures import validate_profile
    profile_hash = validate_profile(profile)
    policy = interpretation_policy() if policy is None else deepcopy(policy)
    validate_envelope(policy, 'MarkerInterpretationPolicy')
    required = {'version', 'coordinate_policy', 'units_policy', 'local_frame', 'world_vertical_axis_index',
        'label_prefixes', 'faces', 'normals', 'corner_basis', 'simulation_world_transform',
        'simulation_half_turns', 'analysis_half_turn_rotvecs', 'local_axis_indices', 'half_turn_face_maps', 'half_turn_operation'}
    if not required.issubset(policy) or not isinstance(policy.get('version'), str) or not policy['version']:
        raise ValueError('Incomplete marker interpretation policy/version.')
    # Geometry ignores labels, faces, author/version/provenance and marker order.
    geometry = dict(box_dims_mm=np.asarray(profile['box_dims_mm'], float).tolist(), units=profile['units'],
                    origin=profile['origin'], dimension_policy=profile['dimension_policy'],
                    points=sorted([np.asarray(m['xyz_mm'], float).tolist() for m in profile['markers']]))
    bindings = sorted([dict(label=m['id'], face=m['face']) for m in profile['markers']], key=lambda m:m['label'])
    semantic_hash = digest(dict(policy=policy, bindings=bindings))
    return envelope('MarkerProfileIdentity', source_profile=deepcopy(profile),
        profile_hash=profile_hash, geometry_hash=digest(geometry),
        observation_mapping_hash=digest(sorted(
            [dict(label=m['id'], xyz_mm=np.asarray(m['xyz_mm'], float).tolist()) for m in profile['markers']],
            key=lambda m: m['label'])), policy=policy,
        policy_hash=digest(policy), semantic_hash=semantic_hash,
        semantic_version=policy['version']+'/'+semantic_hash)


def validate_identity(value, *, require_current=True):
    validate_envelope(value, 'MarkerProfileIdentity')
    if not isinstance(value.get('source_profile'), dict) or not isinstance(value.get('policy'), dict):
        raise ValueError('Marker identity requires its declared source profile and policy.')
    try:
        expected = profile_identity(value['source_profile'], policy=value['policy'])
    except (KeyError, TypeError, AttributeError, IndexError) as error:
        raise ValueError('Incomplete marker source/interpretation.') from error
    if canonical(value) != canonical(expected):
        raise ValueError('Stale or incomplete marker profile identity.')
    if require_current and value['policy_hash'] != digest(interpretation_policy()):
        raise ValueError('Unsupported marker interpretation; explicit migration review required.')
    return value


def compatibility(previous, current):
    """Compatibility never supplies missing evidence or approves a result."""
    reasons = []
    try:
        validate_identity(current)
    except ValueError as error:
        status = 'unsupported' if 'Unsupported marker interpretation' in str(error) else 'invalid'
        reasons.append(str(error))
    else:
        return _compatibility_with_valid_current(previous, current)
    return envelope('MarkerProfileCompatibility', status=status, reasons=reasons,
        previous_profile_hash=previous.get('profile_hash') if isinstance(previous, dict) else None,
        current_profile_hash=current.get('profile_hash') if isinstance(current, dict) else None,
        approval_status='not_evaluated', numerical_pose_change='not_inferred')


def _compatibility_with_valid_current(previous, current):
    reasons = []
    if previous is None:
        status = 'unknown'; reasons.append('Previous result has no marker semantic identity.')
    else:
        try:
            validate_identity(previous, require_current=False)
            validate_identity(current, require_current=False)
        except ValueError as error:
            status = 'invalid'; reasons.append(str(error))
        else:
            for key, label in (('geometry_hash', 'Marker positions/dimensions'),
                               ('semantic_hash', 'Labels/faces/normal/frame/axes/half-turn interpretation')):
                if previous[key] != current[key]:
                    reasons.append(label+' changed.')
            if current['policy_hash'] != digest(interpretation_policy()):
                reasons.append('Current semantic policy is unsupported.')
                status = 'unsupported'
            else:
                status = 'incompatible' if reasons else 'compatible'
                if previous['observation_mapping_hash'] != current['observation_mapping_hash']:
                    if not reasons: status = 'review_required'
                    reasons.append('Label-to-position correspondence changed; same-face pose may remain invariant. Reuse needs scoped review.')
                if not reasons:
                    reasons.append('Geometry and interpretation match; author metadata may differ.')
    return envelope('MarkerProfileCompatibility', status=status, reasons=reasons,
        previous_profile_hash=previous.get('profile_hash') if isinstance(previous, dict) else None,
        current_profile_hash=current.get('profile_hash') if isinstance(current, dict) else None,
        approval_status='not_evaluated', numerical_pose_change='not_inferred')


def layout_support(profile):
    """Whole assigned-face rank at declared geometry; never face-local rejection.

    The existing optimizer tolerance is a dimensionless numerical rank guard,
    not a new physical accuracy tolerance. Full local rank is not global proof.
    """
    from src.simulation.marker_fixtures import validate_profile
    from src.analysis.pipeline.pose_optimizer import _face_constraint_rank, FACE_RANK_RELATIVE_TOLERANCE
    from src.config.config_app import FACE_DEFINITIONS
    validate_profile(profile)
    markers = [dict(cam_coords=np.asarray(m['xyz_mm'], float), face_key=m['face']) for m in profile['markers']]
    rank = _face_constraint_rank(markers, np.zeros(6), np.asarray(profile['box_dims_mm'], float), FACE_DEFINITIONS)
    supported = len(markers) >= 6 and rank == 6
    witness = None
    if supported:
        from src.config.marker_semantics import FACE_NORMALS
        xyz=np.asarray([m['xyz_mm'] for m in profile['markers']],float)
        dims=np.asarray(profile['box_dims_mm'],float); normals=np.asarray([FACE_NORMALS[m['face']] for m in profile['markers']])
        half=dims[np.argmax(np.abs(normals),axis=1)]/2
        # An exact bounded counterexample is enough to disprove uniqueness.
        # Absence of these 23 witnesses does not prove arbitrary global uniqueness.
        for rotation in _AXIS_ROTATIONS:
            local=xyz@rotation
            if np.all(np.abs(np.sum(local*normals,axis=1)-half)<=1e-8) and np.all(np.abs(local)<=dims/2+1e-8):
                witness=rotation.tolist(); break
    status='ambiguous' if witness is not None else 'supported' if supported else 'unavailable'
    return envelope('MarkerLayoutSupport', status=status,
        local_pose_constraint_rank=rank, required_rank=6, complete_marker_count=len(markers),
        reason='Complete assigned-face constraints admit distinct box orientations.' if witness is not None else
            'Complete assigned-face constraints have local six-DOF support.' if supported else
            'This layout lacks local six-DOF support for the current solver.',
        global_uniqueness_status='ambiguous' if witness is not None else 'unavailable',
        ambiguity_witness_rotation=witness, ambiguity_check='23 proper signed-axis rotations at the declared centre; not exhaustive',
        ambiguity_tolerance=dict(value=1e-8,units='mm',basis='Existing declared face-plane import arithmetic tolerance; not physical accuracy'),
        scope='Declared complete observations; frame coverage and global ambiguity remain runtime checks.',
        rank_tolerance=dict(value=FACE_RANK_RELATIVE_TOLERANCE, units='dimensionless-relative-singular-value',
                            basis='Existing production optimizer numerical degeneracy guard; not physical accuracy.'))


def artifact_fields(profile):
    record = profile_identity(profile)
    # Constant .proc columns repeat on disk: retain a compact declaration, not
    # all fixed policy constants on every observation row. Source coordinates
    # remain necessary to recompute the declared hashes rather than trust them.
    artifact = envelope('MarkerArtifactIdentity', profile_id=profile['profile_id'],
        source_profile=deepcopy(profile),
        profile_hash=record['profile_hash'], geometry_hash=record['geometry_hash'],
        observation_mapping_hash=record['observation_mapping_hash'],
        semantic_hash=record['semantic_hash'], semantic_version=record['semantic_version'],
        policy_version=POLICY_VERSION, policy_hash=record['policy_hash'],
        box_dims_mm=np.asarray(profile['box_dims_mm'], float).tolist(),
        bindings=sorted([dict(label=m['id'], face=m['face']) for m in profile['markers']], key=lambda m:m['label']),
        units='mm', coordinate_policy=COORDINATE_POLICY, time_semantics='static-profile; observations in seconds')
    return dict(MarkerProfileIdentityJson=canonical(artifact), MarkerGeometryHash=record['geometry_hash'],
                MarkerSemanticsHash=record['semantic_hash'], MarkerSemanticsVersion=record['semantic_version'])


def artifact_identity(metadata):
    text = metadata.get('MarkerProfileIdentityJson')
    if text is None or text == '':
        if any(metadata.get(key) for key in ('MarkerGeometryHash', 'MarkerSemanticsHash', 'MarkerSemanticsVersion')):
            raise ValueError('Marker semantic declaration requires its source identity.')
        return None
    try:
        record = json.loads(text, parse_constant=lambda token: (_ for _ in ()).throw(ValueError(token)))
        validate_envelope(record, 'MarkerArtifactIdentity')
        if not isinstance(record.get('source_profile'), dict):
            raise ValueError('Marker artifact requires its declared source profile.')
        # Resolve fixed meanings by current policy hash; recompute every identity
        # from the declared source, including label-to-position correspondence.
        expected_record = json.loads(artifact_fields(record['source_profile'])['MarkerProfileIdentityJson'])
        if canonical(record) != canonical(expected_record):
            raise ValueError('Unsupported or stale marker artifact source/semantic identity.')
    except (TypeError, KeyError, AttributeError, IndexError, json.JSONDecodeError) as error:
        raise ValueError('Invalid marker semantic declaration.') from error
    expected = dict(MarkerGeometryHash=record['geometry_hash'], MarkerSemanticsHash=record['semantic_hash'],
                    MarkerSemanticsVersion=record['semantic_version'], MarkerLayoutHash=record['profile_hash'],
                    MarkerLayoutId=record['profile_id'])
    if any(metadata.get(key) != value for key, value in expected.items()):
        raise ValueError('Stale artifact marker identity.')
    if metadata.get('SourceKind') not in ('real', 'public_external', 'mujoco_synthetic', 'handcrafted_dummy'):
        raise ValueError('Marker identity requires an explicit artifact source kind.')
    if metadata.get('SchemaVersion') != '1':
        raise ValueError('Unsupported or missing marker artifact host SchemaVersion.')
    if metadata.get('CoordinatePolicy') != COORDINATE_POLICY or metadata.get('UnitsPolicy') != UNITS_POLICY:
        raise ValueError('Unsupported marker artifact coordinates/units/time policy.')
    if any(metadata.get(key) != float(dim) for key, dim in
           zip(('BoxLengthMm', 'BoxWidthMm', 'BoxHeightMm'), record['box_dims_mm'])):
        raise ValueError('Marker identity dimensions conflict with artifact geometry.')
    return record
