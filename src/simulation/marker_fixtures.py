"""Independent MuJoCo observation fixtures. No analysis/detector imports.

This public example is not an OptiTrack attachment specification. All lengths
are millimetres and box-local axes remain unchanged during world conversion.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import subprocess
from pathlib import Path

import mujoco
import numpy as np
from scipy.spatial.transform import Rotation

from .engine.mujoco_engine import MuJoCoEngine

VERSION = '1.0'
WORLD_TO_ANALYSIS = np.array([[1., 0., 0.], [0., 0., 1.], [0., -1., 0.]])
HALF_TURNS = {'X': np.diag([1., -1., -1.]), 'Y': np.diag([-1., 1., -1.]),
              'Z': np.diag([-1., -1., 1.])}
DIMENSIONS = (200., 120., 80.)
# Declared explicitly before running production analysis; never fitted to it.
EXAMPLE_MARKERS = (
    ('F1', 'FRONT', (21, 12, 40)), ('F2', 'FRONT', (-51, 19, 40)),
    ('F3', 'FRONT', (30, -35, 40)), ('F4', 'FRONT', (-9, -8, 40)),
    ('B1', 'BACK', (17, -31, -40)), ('B2', 'BACK', (-39, 23, -40)), ('B3', 'BACK', (42, 28, -40)),
    ('R1', 'RIGHT', (100, 12, 8)), ('R2', 'RIGHT', (100, -28, 19)), ('R3', 'RIGHT', (100, 31, -18)),
    ('L1', 'LEFT', (-100, -18, 7)), ('L2', 'LEFT', (-100, 25, 21)), ('L3', 'LEFT', (-100, 19, -25)),
    ('T1', 'TOP', (7, 60, -9)), ('T2', 'TOP', (-45, 60, 23)), ('T3', 'TOP', (51, 60, 18)),
    ('M1', 'BOTTOM', (-12, -60, 25)), ('M2', 'BOTTOM', (38, -60, -18)),
)
FACE_NORMALS = {'FRONT': (0, 0, 1), 'BACK': (0, 0, -1), 'RIGHT': (1, 0, 0),
                'LEFT': (-1, 0, 0), 'TOP': (0, 1, 0), 'BOTTOM': (0, -1, 0)}
CASES = ('healthy', 'x', 'y', 'z', 'xx', 'xy', 'gap', 'gap_x', 'freeze_reconnect',
         'genuine_rotation', 'noise', 'unsupported_90', 'unsupported_arbitrary', 'low_coverage')


def canonical_json(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)


def example_profile():
    return {'profile_id': 'public-asymmetric-example-18', 'profile_version': '1',
            'units': 'mm', 'origin': 'box-geometric-center', 'dimension_policy': 'absolute-mm',
            'box_dims_mm': list(DIMENSIONS), 'publication': 'public-example-not-production-standard',
            'source': 'explicit handcrafted geometry; no capture-derived coordinates',
            'license': 'same as repository source code',
            'markers': [{'id': mid, 'face': face, 'xyz_mm': list(xyz)} for mid, face, xyz in EXAMPLE_MARKERS]}


def validate_profile(profile):
    dims = np.asarray(profile['box_dims_mm'], dtype=float)
    markers = profile['markers']
    if profile['units'] != 'mm' or profile['dimension_policy'] != 'absolute-mm' or profile['origin'] != 'box-geometric-center':
        raise ValueError('Only explicit absolute-mm profiles are supported.')
    if dims.shape != (3,) or not np.isfinite(dims).all() or (dims <= 0).any():
        raise ValueError('Invalid box dimensions.')
    ids = [m['id'] for m in markers]
    if not ids or any(not isinstance(mid, str) or not mid.strip() for mid in ids) or len(set(ids)) != len(ids):
        raise ValueError('Marker IDs must be unique.')
    xyz = np.asarray([m['xyz_mm'] for m in markers], dtype=float)
    if xyz.shape != (len(markers), 3) or not np.isfinite(xyz).all():
        raise ValueError('Invalid marker coordinates.')
    for marker, point in zip(markers, xyz):
        if marker['face'] not in FACE_NORMALS:
            raise ValueError('Unknown assigned face.')
        normal = np.asarray(FACE_NORMALS[marker['face']])
        if (np.abs(point) > dims / 2 + 1e-8).any() or not np.isclose(point @ normal, dims[np.flatnonzero(normal)[0]] / 2, atol=1e-8, rtol=0):
            raise ValueError('Marker lies outside its assigned face.')
    distances = np.linalg.norm(xyz[:, None] - xyz[None, :], axis=-1)
    np.fill_diagonal(distances, np.inf)
    if (distances < 1.).any():
        raise ValueError('Markers must be separated by at least 1 mm.')
    for face in FACE_NORMALS:
        points = xyz[[m['face'] == face for m in markers]]
        if len(points) == 3 and np.linalg.norm(np.cross(points[1] - points[0], points[2] - points[0])) < 1e-8:
            raise ValueError('Three-marker face is collinear.')
    return hashlib.sha256(canonical_json(profile).encode()).hexdigest()


def record_truth(*, samples=100, genuine_rotation=False):
    engine = MuJoCoEngine(size=DIMENSIONS, mass=1., com_offset=(3., -4., 2.))
    initial = Rotation.from_euler('xyz', [15., 20., 10.], degrees=True).as_matrix()
    q_xyzw = Rotation.from_matrix(WORLD_TO_ANALYSIS.T @ initial).as_quat()
    engine.init_quat = q_xyzw[[3, 0, 1, 2]].tolist()
    engine.init_pos = [0.12, -0.23, 4.0]  # No contact during this bounded fixture.
    engine.build()
    engine.data.qvel[:3] = [.025, -.015, 0.]
    if genuine_rotation:
        engine.data.qvel[3:6] = [np.pi / ((samples - 1) * .008), 0., 0.]
    history = engine.record_samples(samples=samples, substeps=4)
    return history, {'initial_position_m': engine.init_pos, 'initial_quaternion_wxyz': engine.init_quat,
                     'initial_linear_velocity_m_s': [.025, -.015, 0.],
                     'initial_local_angular_velocity_rad_s': [np.pi / ((samples - 1) * .008), 0., 0.] if genuine_rotation else [0., 0., 0.],
                     'mass_kg': 1., 'com_offset_mm': [3., -4., 2.], 'timestep_s': float(engine.model.opt.timestep),
                     'substeps': 4, 'gravity_m_s2': [0., 0., -9.81],
                     'scenario': 'free-fall-no-contact' if not genuine_rotation else 'free-fall-principal-axis-spin'}


def make_case(case_id, *, seed=74082):
    if case_id not in CASES:
        raise ValueError(f'Unknown case: {case_id}')
    profile = example_profile()
    layout_hash = validate_profile(profile)
    history, params = record_truth(genuine_rotation=case_id == 'genuine_rotation')
    times = np.asarray([f['time'] for f in history])
    origins = np.asarray([WORLD_TO_ANALYSIS @ f['BodyOrigin'] for f in history])
    com = np.asarray([WORLD_TO_ANALYSIS @ f['COM'] for f in history])
    rotations = np.asarray([WORLD_TO_ANALYSIS @ f['RotationMatrix'] for f in history])
    local = np.asarray([m['xyz_mm'] for m in profile['markers']])
    truth_markers = np.einsum('nij,mj->nmi', rotations, local) + origins[:, None, :]
    observed_rotations = rotations.copy()
    events = []
    flips = {'x': [(30, 'X')], 'y': [(30, 'Y')], 'z': [(30, 'Z')],
             'xx': [(30, 'X'), (65, 'X')], 'xy': [(30, 'X'), (65, 'Y')], 'gap_x': [(30, 'X')]}.get(case_id, [])
    for frame, axis in flips:
        observed_rotations[frame:] = observed_rotations[frame:] @ HALF_TURNS[axis]
        events.append({'kind': 'solver_pose_half_turn', 'frame': frame, 'time_s': float(times[frame]),
                       'axis': axis, 'matrix': HALF_TURNS[axis].tolist(), 'scope': 'cumulative-suffix'})
    if case_id.startswith('unsupported_'):
        vector = np.array([0., 1., 0.]) if case_id.endswith('90') else np.array([1., 2., 3.]) / np.sqrt(14.)
        angle = np.pi / 2 if case_id.endswith('90') else np.pi
        fault = Rotation.from_rotvec(vector * angle).as_matrix()
        observed_rotations[30:] = observed_rotations[30:] @ fault
        events.append({'kind': 'unsupported_pose_error', 'frame': 30, 'time_s': float(times[30]), 'matrix': fault.tolist()})
    observed = np.einsum('nij,mj->nmi', observed_rotations, local) + origins[:, None, :]
    if case_id in ('gap', 'gap_x'):
        observed[15:20] = np.nan
        events.append({'kind': 'constraint_dropout', 'start_frame': 15, 'end_frame_exclusive': 20,
                       'note': 'Loss of solved constraints, not physical-marker visibility.'})
    if case_id == 'freeze_reconnect':
        observed[15:20] = observed[14]
        observed[20:22] += np.array([7., -3., 4.])
        events.extend([{'kind': 'constraint_freeze', 'start_frame': 15, 'end_frame_exclusive': 20},
                       {'kind': 'reconnect_offset', 'start_frame': 20, 'end_frame_exclusive': 22, 'xyz_mm': [7., -3., 4.]}])
    if case_id == 'noise':
        observed += np.random.default_rng(seed).normal(0., .02, observed.shape)
        events.append({'kind': 'independent_constraint_noise', 'std_mm': .02,
                       'note': 'Stress input, not a calibrated model of solved Motive constraints.'})
    if case_id == 'low_coverage':
        observed[:, 2:] = np.nan
        events.append({'kind': 'constraint_dropout', 'remaining_ids': ['F1', 'F2'], 'scope': 'all-frames'})
    manifest = {'schema_version': '1', 'generator_version': VERSION, 'source_kind': 'mujoco_synthetic',
                'evidence_level': 'synthetic_integration', 'case_id': case_id, 'seed': seed,
                'mujoco_version': mujoco.__version__, 'parameters': params, 'profile': profile,
                'layout_hash': layout_hash, 'coordinate_policy': 'global-y-up-box-xyz-mm',
                'world_transform': WORLD_TO_ANALYSIS.tolist(), 'local_basis_changed': False,
                'quaternion_order': 'wxyz', 'events': events,
                'expected_flip_frames': [f for f, _ in flips], 'expected_axes': [a for _, a in flips],
                'expected_recommendation': None, 'expected_approval': False,
                'pose_tolerances': {'position_mm': .1, 'rotation_deg': .1},
                'truth_note': 'Body origin is the analysis pose origin. COM remains separate.'}
    return manifest, times, origins, com, rotations, truth_markers, observed


def write_case(directory, case_id, *, seed=74082):
    manifest, times, origins, com, rotations, truth, observed = make_case(case_id, seed=seed)
    root = Path(directory) / case_id
    root.mkdir(parents=True, exist_ok=True)
    q = Rotation.from_matrix(rotations).as_quat()[:, [3, 0, 1, 2]]
    for i in range(1, len(q)):
        if q[i] @ q[i-1] < 0:
            q[i] *= -1
    with (root / 'truth_pose.csv').open('w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['frame', 'time_s', *[f'body_{a}_mm' for a in 'xyz'],
                         *[f'com_{a}_mm' for a in 'xyz'], *[f'q_{a}' for a in 'wxyz'],
                         *[f'r{i}{j}' for i in range(3) for j in range(3)]])
        for i, t in enumerate(times):
            writer.writerow([i, t, *origins[i], *com[i], *q[i], *rotations[i].ravel()])
    with (root / 'truth_markers.csv').open('w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['frame', 'time_s', 'marker_id', 'x_mm', 'y_mm', 'z_mm'])
        for i, t in enumerate(times):
            for m, point in zip(manifest['profile']['markers'], truth[i]):
                writer.writerow([i, t, m['id'], *point])
    with (root / 'observed.csv').open('w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['Format Version', '1.25', 'Length Units', 'Millimeters', 'Coordinate Space', 'Global',
                         'Source Kind', 'mujoco_synthetic', 'Generator Version', VERSION])
        writer.writerow([])
        header = {k: ['', ''] for k in ('type', 'name', 'id', 'parent', 'category', 'component')}
        header['component'] = ['Frame', 'Time']
        for marker in manifest['profile']['markers']:
            for key, value in [('type', 'Rigid Body Marker'), ('name', 'PublicExample:' + marker['id']),
                               ('id', marker['id']), ('parent', 'PublicExample'), ('category', 'Position')]:
                header[key].extend([value] * 3)
            header['component'].extend(['X', 'Y', 'Z'])
        writer.writerows(header.values())
        for i, t in enumerate(times):
            writer.writerow([i, t, *[float(v) if np.isfinite(v) else '' for v in observed[i].ravel()]])
    manifest['files'] = {name: hashlib.sha256((root / name).read_bytes()).hexdigest()
                         for name in ('observed.csv', 'truth_pose.csv', 'truth_markers.csv')}
    repository = Path(__file__).resolve().parents[2]
    try:
        manifest['code_revision'] = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=repository, text=True).strip()
        manifest['working_tree_dirty'] = bool(subprocess.check_output(['git', 'status', '--porcelain'], cwd=repository, text=True).strip())
    except (OSError, subprocess.CalledProcessError):
        manifest['code_revision'] = 'unavailable'
    manifest['generator_source_sha256'] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    manifest['engine_source_sha256'] = hashlib.sha256((Path(__file__).parent / 'engine' / 'mujoco_engine.py').read_bytes()).hexdigest()
    (root / 'observed.synthetic.json').write_text(json.dumps(manifest, indent=2, allow_nan=False), encoding='utf-8')
    return root


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', default='tmp/mujoco_marker_validation')
    parser.add_argument('--case', choices=(*CASES, 'all'), default='all')
    parser.add_argument('--seed', type=int, default=74082)
    args = parser.parse_args()
    for case in CASES if args.case == 'all' else [args.case]:
        print(write_case(args.output, case, seed=args.seed))


if __name__ == '__main__':
    main()
