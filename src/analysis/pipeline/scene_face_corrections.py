"""Approved box-local face states for observed scene motion, never inferred from XYZ."""
import json
from copy import deepcopy

import numpy as np

from src.config.config_app import FACE_DEFINITIONS
from .artifact_io import validate_face_context
from .marker_flip import normalize_marker_corrections, serialize_marker_corrections


CORRECTED_VERSION = 'observed-motion-v3-approved-face-states'
HALF_TURNS = {axis: np.diag([1. if name == axis else -1. for name in 'XYZ'])
              for axis in 'XYZ'}


def face_correction_header(header, context, decisions):
    """Attach validated persisted approval data without putting objects in JSON headers."""
    context = validate_face_context(context) if isinstance(context, str) else deepcopy(context)
    result = deepcopy(header)
    result['face_correction'] = {'schema_version': '3', 'context': context,
        'decisions': json.loads(serialize_marker_corrections(decisions))}
    result['export_metadata'] = deepcopy(context.get('export_metadata', {}))
    return result


def version_change_affects_range(result, saved_version, start, end, legacy_version):
    current = getattr(result, 'version', legacy_version)
    if saved_version == current:
        return False
    affected = getattr(result, 'face_correction_affected', None)
    if saved_version == legacy_version and current == CORRECTED_VERSION and affected is not None:
        times = result.signals.index.to_numpy(float)
        return bool(np.any(affected & (times >= start) & (times <= end)))
    return True


def approved_face_states(header, times, ids, registration):
    """Return the full-history cumulative local state at every actual sample.

    The loader validates materialized faces before exposing this primitive record.
    A suffix therefore retains approvals before its first sample. No marker face
    pattern or low fitting residual can create an approval.
    """
    record = header.get('face_correction')
    if record is None:
        if 'Marker Annotation' in header.get('type', []):
            raise ValueError('Scene detection needs validated face correction history.')
        return None, np.zeros(len(times), dtype=bool)
    if record.get('schema_version') != '3':
        raise ValueError('Unsupported scene face correction history.')
    context = validate_face_context(json.dumps(record['context'], allow_nan=False))
    base_faces = context['base_faces']
    if set(base_faces) != set(ids) or any(face not in FACE_DEFINITIONS for face in base_faces.values()):
        raise ValueError('Scene marker identities differ from the face correction context.')
    if registration is not None:
        dims = np.asarray(registration.profile['box_dims_mm'], float)
        if not np.array_equal(dims, np.asarray(context['box_dims_mm'], float)):
            raise ValueError('Registered dimensions differ from the face correction context.')
        for marker in registration.profile['markers']:
            if marker['id'] not in base_faces:
                continue
            face = base_faces[marker['id']]
            definition = FACE_DEFINITIONS[face]
            axis, direction = definition['axis_idx'], definition['direction']
            if (marker.get('face', face) != face or
                    abs(marker['xyz_mm'][axis] - direction * dims[axis] / 2.) > registration.position_tolerance_mm):
                raise ValueError('Registered marker axes/faces differ from the face correction context.')
    decisions = normalize_marker_corrections(record['decisions'], approved_only=True)
    if any(d.correction_kind != 'face_assignment' for d in decisions):
        raise ValueError('Scene face states cannot use legacy marker permutations.')
    states = np.repeat(np.eye(3)[None, :, :], len(times), axis=0)
    for decision in decisions:
        suffix = times >= decision.boundary_time_sec - 1e-12
        states[suffix] = states[suffix] @ HALF_TURNS[decision.axis]
    boundaries = np.r_[False, np.any(states[1:] != states[:-1], axis=(1, 2))]
    return states, boundaries
