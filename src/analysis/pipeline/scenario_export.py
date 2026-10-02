"""Shared serializer for the existing Step 2 analysis scenario format."""
from src.config.data_columns import CORNER_NAME_MAP


def automatic_offsets(row):
    heights = {f'C{i}': row[('Analysis', f'C{i}', 'RelativeHeight')] for i in range(1, 9)}
    lowest = min(heights, key=heights.get)
    group = range(1, 5) if int(lowest[1:]) <= 4 else range(5, 9)
    return sorted(((f'C{i}', heights[f'C{i}']) for i in group), key=lambda v: v[1])[:3]


def scenario_text(offsets, velocities, scene_name, run_time, time_step):
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
