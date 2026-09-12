"""Operator-selected contact topology in the registered box's local axes.

These features describe intent, independently of observed contact or an ISTA
item lookup. Corner numbers follow the existing C1..C8 box geometry schema.
"""
from itertools import combinations
import re

from src.config.config_app import FACE_DEFINITIONS


def _faces(value):
    if (not isinstance(value, (list, tuple)) or not 1 <= len(value) <= 3
            or any(not isinstance(face, str) or face not in FACE_DEFINITIONS for face in value)
            or len(set(value)) != len(value)):
        raise ValueError('Intended contact needs one to three distinct local box faces.')
    faces = tuple(sorted(value))
    corners = set.intersection(*(set(FACE_DEFINITIONS[face]['corners']) for face in faces))
    if len(corners) != {1: 4, 2: 2, 3: 1}[len(faces)]:
        raise ValueError('Intended contact faces must meet at one face, edge or corner.')
    return faces, tuple(sorted(index + 1 for index in corners))


def feature_options():
    """Return the six faces, twelve edges and eight corners, in stable order."""
    options = []
    for count in (1, 2, 3):
        for faces in combinations(sorted(FACE_DEFINITIONS), count):
            try:
                canonical, _ = _faces(faces)
            except ValueError:  # Opposite faces never form a contact feature.
                continue
            options.append(canonical)
    return options


def feature_corners(faces):
    return _faces(faces)[1]


def feature_label(faces):
    return ' + '.join(face.title() for face in _faces(faces)[0])


def validate_intended_contact(value):
    """Validate a v1 operator record and return a detached canonical record."""
    if value is None:
        return None
    fields = {'version', 'basis', 'faces', 'registration_sha256', 'ista_type', 'applied_edition'}
    if (not isinstance(value, dict) or set(value) != fields
            or type(value.get('version')) is not int or value['version'] != 1
            or value.get('basis') != 'operator'):
        raise ValueError('Invalid intended contact record.')
    faces, _ = _faces(value['faces'])
    fingerprint = value['registration_sha256']
    if not isinstance(fingerprint, str) or not re.fullmatch(r'[0-9a-f]{64}', fingerprint):
        raise ValueError('Intended contact needs its registration SHA-256.')
    if (value['ista_type'] not in ('Unknown', 'G', 'H')
            or (value['applied_edition'] is not None and not isinstance(value['applied_edition'], str))):
        raise ValueError('Invalid intended contact test context.')
    return {'version': 1, 'basis': 'operator', 'faces': list(faces),
            'registration_sha256': fingerprint, 'ista_type': value['ista_type'],
            'applied_edition': value['applied_edition']}


def validate_intended_contact_context(value, registration_sha256, ista_type, applied_edition):
    record = validate_intended_contact(value)
    if record is not None and (
            record['registration_sha256'] != registration_sha256
            or record['ista_type'] != ista_type or record['applied_edition'] != applied_edition):
        raise ValueError('Intended contact differs from the current registration or test context.')
    return record
