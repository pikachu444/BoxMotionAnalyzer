"""Write independently specified synthetic marker faults for analysis input.

The observed CSV contains separate solved-constraint and physical-marker
channels. Only the separate manifest contains the fault specification.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path

import numpy as np
from scipy.spatial.transform import Rotation

from .marker_corruption import apply_corruption
from .marker_fixtures import load_profile
from src.utils.artifact_metadata import RAW_KEY, metadata_json


def _digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _input_digest(value):
    def numeric_json(item):
        if isinstance(item, np.ndarray):
            return item.tolist()
        if isinstance(item, np.generic):
            return item.item()
        raise TypeError(f'Unsupported input value: {type(item).__name__}')
    encoded = json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False, default=numeric_json)
    return hashlib.sha256(encoded.encode('utf-8')).hexdigest()


def _checkpoint(cancelled):
    if cancelled is not None and cancelled():
        raise InterruptedError('Marker export cancelled.')


def _write_observed(path, result, profile, *, include_physical=True, cancelled=None):
    source = result['manifest']['source_kind']
    version = str(result['manifest']['generator_version'])
    artifact = {
        'SourceKind': source,
        'ModelId': profile['profile_id'],
        **dict(zip(('BoxLengthMm', 'BoxWidthMm', 'BoxHeightMm'), profile['box_dims_mm'])),
        'IstaType': 'not_applicable',
        'ScenarioId': 'specified-synthetic-trajectory-v1',
        'ScenarioKind': 'synthetic_trajectory',
        'MarkerLayoutId': profile['profile_id'],
        'MarkerLayoutHash': result['manifest']['layout_hash'],
        'CoordinatePolicy': 'world-y-up-box-local-fixed-center-v1',
        'UnitsPolicy': 'bma-mm-s-rotvec-rad-summary-deg-v1',
        'GeneratorVersion': 'marker-corruption-' + version,
    }
    with path.open('x', newline='', encoding='utf-8') as stream:
        writer = csv.writer(stream)
        writer.writerow(['Format Version', '1.25', 'Length Units', 'Millimeters',
            'Coordinate Space', 'Global', 'Source Kind', source,
            'Generator Version', artifact['GeneratorVersion'], RAW_KEY, metadata_json(artifact)])
        writer.writerow([])
        headers = {name: ['', ''] for name in ('type', 'name', 'id', 'parent', 'category', 'component')}
        headers['component'] = ['Frame', 'Time']
        for kind in (('Rigid Body Marker', 'Marker') if include_physical else ('Rigid Body Marker',)):
            for marker in profile['markers']:
                mid = marker['id']
                name = profile['profile_id'] + ':' + mid if kind == 'Rigid Body Marker' else mid
                for key, value in (('type', kind), ('name', name), ('id', mid),
                        ('parent', profile['profile_id'] if kind == 'Rigid Body Marker' else ''),
                        ('category', 'Position')):
                    headers[key].extend([value] * 3)
                headers['component'].extend(['X', 'Y', 'Z'])
        writer.writerows(headers.values())
        for i, time in enumerate(result['time_s']):
            if i % 128 == 0:
                _checkpoint(cancelled)
            coordinates = result['rigid_body_markers'][i].ravel()
            if include_physical:
                coordinates = np.concatenate((coordinates, result['physical_markers'][i].ravel()))
            if np.isinf(coordinates).any():
                raise ValueError('Infinite observation coordinates cannot be written as missing markers.')
            writer.writerow([int(result['frame'][i]), float(time),
                             *['' if np.isnan(v) else float(v) for v in coordinates]])


def _write_truth(root, result, profile, cancelled=None):
    quaternions = Rotation.from_matrix(result['rotation_matrix']).as_quat()[:, [3, 0, 1, 2]]
    for i in range(1, len(quaternions)):
        if quaternions[i] @ quaternions[i - 1] < 0:
            quaternions[i] *= -1
    with (root / 'truth_pose.csv').open('x', newline='', encoding='utf-8') as stream:
        writer = csv.writer(stream)
        writer.writerow(['frame', 'time_s', *[f'body_{a}_mm' for a in 'xyz'],
                         *[f'com_{a}_mm' for a in 'xyz'], *[f'q_{a}' for a in 'wxyz'],
                         *[f'r{i}{j}' for i in range(3) for j in range(3)]])
        for i, time in enumerate(result['time_s']):
            if i % 128 == 0:
                _checkpoint(cancelled)
            com = ['', '', ''] if result['com_mm'] is None else result['com_mm'][i]
            writer.writerow([int(result['frame'][i]), float(time), *result['body_origin_mm'][i],
                             *com, *quaternions[i], *result['rotation_matrix'][i].ravel()])
    with (root / 'truth_markers.csv').open('x', newline='', encoding='utf-8') as stream:
        writer = csv.writer(stream)
        writer.writerow(['frame', 'time_s', 'marker_id', 'x_mm', 'y_mm', 'z_mm'])
        for i, time in enumerate(result['time_s']):
            if i % 128 == 0:
                _checkpoint(cancelled)
            for marker, point in zip(profile['markers'], result['truth_markers'][i]):
                writer.writerow([int(result['frame'][i]), float(time), marker['id'], *point])


def write_observations(directory, truth_trajectory, marker_profile, corruption_spec, seed=74082, *, cancelled=None):
    """Validate first; create a new output directory without replacing any file.

    A complete export has its manifest written last. An I/O failure may leave a
    partial new directory for inspection, but never replaces a previous export.
    """
    _checkpoint(cancelled)
    result = apply_corruption(truth_trajectory, marker_profile, corruption_spec, seed)
    _checkpoint(cancelled)
    # Hash only validated input values. No input path or event oracle is embedded
    # in the production CSV, and no real-data class is manufactured by this API.
    input_hashes = {'trajectory': _input_digest(truth_trajectory),
                    'profile': _input_digest(marker_profile), 'spec': _input_digest(corruption_spec)}
    root = Path(directory).resolve()
    root.mkdir(parents=True, exist_ok=False)
    _write_observed(root / 'observed.csv', result, marker_profile, cancelled=cancelled)
    _write_truth(root, result, marker_profile, cancelled)
    _checkpoint(cancelled)
    manifest = dict(result['manifest'])
    manifest.update(input_sha256=input_hashes, com_available=result['com_mm'] is not None,
        files={name: _digest(root / name) for name in ('observed.csv', 'truth_pose.csv', 'truth_markers.csv')},
        source_sha256={name: _digest(Path(__file__).parent / name)
                       for name in ('marker_corruption.py', 'corruption_export.py', 'marker_fixtures.py')},
        observed_contract='Separate Marker physical positions and Rigid Body Marker solved constraints. '
                          'Physical faults do not model a Motive solver response.',
        completion='complete')
    with (root / 'observed.synthetic.json').open('x', encoding='utf-8') as stream:
        json.dump(manifest, stream, indent=2, allow_nan=False)
        stream.write('\n')
    return root


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--trajectory', required=True, help='Explicit Y-up mm/s trajectory JSON.')
    parser.add_argument('--spec', required=True, help='Versioned corruption-specification JSON.')
    profiles = parser.add_mutually_exclusive_group()
    profiles.add_argument('--profile', help='Explicit box-local marker profile JSON.')
    profiles.add_argument('--example', choices=('18', '32'), default='18')
    parser.add_argument('--seed', type=int, default=74082)
    parser.add_argument('--output', required=True, help='New output directory; existing paths are refused.')
    args = parser.parse_args()
    try:
        trajectory = json.loads(Path(args.trajectory).read_text(encoding='utf-8-sig'))
        spec = json.loads(Path(args.spec).read_text(encoding='utf-8-sig'))
        profile = load_profile(args.profile, example=args.example)
        root = write_observations(args.output, trajectory, profile, spec, args.seed)
    except (ValueError, TypeError, KeyError, OSError) as error:
        parser.exit(2, f'Generation failed: {error}\n')
    print(root / 'observed.csv')


if __name__ == '__main__':
    main()
