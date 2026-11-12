"""Shared serializer for the existing Step 2 analysis scenario format."""
import locale
import math
import os
from pathlib import Path
import tempfile

from src.config.data_columns import CORNER_NAME_MAP


def automatic_offsets(row):
    heights = {f'C{i}': row[('Analysis', f'C{i}', 'RelativeHeight')] for i in range(1, 9)}
    for corner, value in heights.items():
        _finite(value, corner + ' height')
    lowest = min(heights, key=heights.get)
    group = range(1, 5) if int(lowest[1:]) <= 4 else range(5, 9)
    return sorted(((f'C{i}', heights[f'C{i}']) for i in group), key=lambda v: v[1])[:3]


def scenario_text(offsets, velocities, scene_name, run_time, time_step):
    if not isinstance(scene_name, str) or any(char in scene_name for char in ',"\r\n\0'):
        raise ValueError('Scene name cannot contain comma, double quote, CR, LF or NUL')
    if len(offsets) != 3 or len({corner for corner, _ in offsets}) != 3:
        raise ValueError('Three different C1..C8 offset corners are required')
    for corner, height in offsets:
        if corner not in CORNER_NAME_MAP:
            raise ValueError('Unknown offset corner: ' + str(corner))
        _finite(height, corner + ' height')
    for name in ('ANG_VEL_X', 'ANG_VEL_Y', 'ANG_VEL_Z', 'TRA_VEL_X', 'TRA_VEL_Y', 'TRA_VEL_Z'):
        if name not in velocities:
            raise ValueError(name + ': measured velocity is missing')
        _finite(velocities[name], name)
    for name, value in (('runtime', run_time), ('timestep', time_step)):
        if _finite(value, name) <= 0:
            raise ValueError(name + ' must be positive')
    data = [('1', 'Left'), ('2', 'Right'), ('3', 'Bottom'), ('4', 'Top'),
            ('5', 'Rear'), ('6', 'Front'), ('cat', 'Corner_Drop_2nd'), ('drop_name', scene_name)]
    for i, (corner, height) in enumerate(offsets, 1):
        data.extend([(f'variable_{i}', CORNER_NAME_MAP.get(corner, 'Unknown')),
                     (f'value_{i}', f'{height:.6f}')])
    variables = [('OFFSET', 0.), *[(k, velocities[k]) for k in
        ('ANG_VEL_X', 'ANG_VEL_Y', 'ANG_VEL_Z', 'TRA_VEL_X', 'TRA_VEL_Y', 'TRA_VEL_Z')],
        *[(k, 0.) for k in ('POSI_FROM_CENT_X', 'POSI_FROM_CENT_Y', 'POSI_FROM_CENT_Z',
                           'ROT_ANG_VEL_X', 'ROT_ANG_VEL_Y', 'ROT_ANG_VEL_Z')]]
    for i, (name, value) in enumerate(variables, 4):
        data.extend([(f'variable_{i}', name), (f'value_{i}', '0.0' if name in
            ('OFFSET', 'POSI_FROM_CENT_X', 'POSI_FROM_CENT_Y', 'POSI_FROM_CENT_Z',
             'ROT_ANG_VEL_X', 'ROT_ANG_VEL_Y', 'ROT_ANG_VEL_Z') else f'{value:.6f}')])
    data.extend([('run_time', run_time), ('tmin', time_step)])
    return '\n'.join(f'{k},{v}' for k, v in data[:6]) + '\n' + ','.join(f'{k},{v}' for k, v in data[6:])


def _finite(value, name):
    if isinstance(value, bool):
        raise ValueError(name + ' must be finite numeric data')
    try:
        number = float(value)
    except (ValueError, TypeError):
        raise ValueError(name + ' must be finite numeric data') from None
    if not math.isfinite(number):
        raise ValueError(name + ' must be finite numeric data')
    return number


def scenario_bytes(text):
    """Keep the runtime's legacy text encoding and newline policy, validated first."""
    encoding = locale.getpreferredencoding(False)
    normalized = text.replace('\n', os.linesep)
    payload = normalized.encode(encoding, errors='strict')
    if payload.decode(encoding, errors='strict') != normalized:
        raise ValueError('Scene text cannot round-trip in the runtime encoding')
    return payload


def atomic_write_scenario(destination, payload):
    """Only a fully written same-directory file may replace an existing result."""
    path = Path(destination)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode='wb', dir=path.parent, prefix='.scenario-', suffix='.tmp', delete=False) as stream:
            temporary = Path(stream.name)
            written = stream.write(payload)
            if written != len(payload):
                raise OSError('Incomplete scenario write')
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
