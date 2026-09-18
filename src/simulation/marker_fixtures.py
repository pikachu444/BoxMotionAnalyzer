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
import copy
import re
from pathlib import Path

import mujoco
import numpy as np
from scipy.spatial.transform import Rotation

from .engine.mujoco_engine import MuJoCoEngine
from src.utils.artifact_metadata import metadata_json, RAW_KEY

VERSION = '1.4'
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
MOTIONS = ('free_fall', 'face', 'edge', 'corner')


def canonical_json(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)


def example_profile():
    return {'profile_id': 'public-asymmetric-example-18', 'profile_version': '1',
            'units': 'mm', 'origin': 'box-geometric-center', 'dimension_policy': 'absolute-mm',
            'box_dims_mm': list(DIMENSIONS), 'publication': 'public-example-not-production-standard',
            'source': 'explicit handcrafted geometry; no capture-derived coordinates',
            'license': 'same as repository source code',
            'markers': [{'id': mid, 'face': face, 'xyz_mm': list(xyz)} for mid, face, xyz in EXAMPLE_MARKERS]}


def virtual_profile_32():
    """New virtual geometry; counts resemble a workflow, coordinates are not VDTest."""
    front = [(-115,-61),(-78,49),(-35,-20),(12,62),(62,-53),(117,18),
             (82,57),(-105,8),(-12,-67),(39,7),(101,-27)]
    back = [(-118,32),(-86,-48),(-42,65),(3,-39),(48,51),(112,-9),
            (74,-62),(-106,-4),(-21,19),(23,71),(91,30),(-61,-12)]
    markers = [(f'F{i+1}', 'FRONT', (x,y,45)) for i,(x,y) in enumerate(front)]
    markers += [(f'B{i+1}', 'BACK', (x,y,-45)) for i,(x,y) in enumerate(back)]
    markers += [('L1','LEFT',(-150,-51,13)),('L2','LEFT',(-150,38,29)),('L3','LEFT',(-150,17,-31)),
                ('R1','RIGHT',(150,-37,-21)),('R2','RIGHT',(150,53,8)),('R3','RIGHT',(150,4,33)),
                ('T1','TOP',(-93,90,-17)),('T2','TOP',(54,90,31)),('T3','TOP',(113,90,-28))]
    profile = example_profile()
    profile.update(profile_id='public-virtual-box-32', box_dims_mm=[300.,180.,90.],
                   publication='public-virtual-example-not-VDTest-or-standard',
                   source='New explicit virtual geometry; no capture-derived coordinates',
                   markers=[{'id': mid, 'face': face, 'xyz_mm': list(xyz)} for mid,face,xyz in markers])
    return profile


def validate_profile(profile):
    for key in ('profile_id', 'profile_version', 'publication', 'source', 'license'):
        if not isinstance(profile.get(key), str) or not profile[key].strip():
            raise ValueError(f'Profile requires {key}.')
    if not re.fullmatch(r'[A-Za-z0-9_.-]+', profile['profile_id']):
        raise ValueError('Profile ID must use letters, digits, underscore, dot or hyphen.')
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
        # The current production raw reader uses these label prefixes. Reject
        # incompatible custom labels instead of silently analyzing another face.
        label_face = {'F': 'FRONT', 'B': 'BACK', 'R': 'RIGHT', 'L': 'LEFT',
                      'T': 'TOP', 'M': 'BOTTOM'}.get(marker['id'][:1].upper())
        if not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]*', marker['id']) or label_face != marker['face']:
            raise ValueError('Marker ID must follow the production face-prefix convention.')
        normal = np.asarray(FACE_NORMALS[marker['face']])
        if (np.abs(point) > dims / 2 + 1e-8).any() or not np.isclose(point @ normal, dims[np.flatnonzero(normal)[0]] / 2, atol=1e-8, rtol=0):
            raise ValueError('Marker lies outside its assigned face.')
    distances = np.linalg.norm(xyz[:, None] - xyz[None, :], axis=-1)
    np.fill_diagonal(distances, np.inf)
    if (distances < 1.).any():
        raise ValueError('Markers must be separated by at least 1 mm.')
    # One face may be collinear while other observed faces constrain the pose.
    # Geometry import is not pose certification; the analysis solver checks
    # the complete available marker set at each frame.
    for original in (example_profile(), virtual_profile_32()):
        if profile['profile_id'] == original['profile_id'] and profile != original:
            raise ValueError('Modified public geometry requires a new custom profile ID.')
    return hashlib.sha256(canonical_json(profile).encode()).hexdigest()


def load_profile(path=None, *, example='18'):
    """Read an explicit local JSON profile without modifying the public example."""
    if example not in ('18', '32'):
        raise ValueError('Unknown public example.')
    profile = (virtual_profile_32() if example == '32' else example_profile()) if path is None else json.loads(Path(path).read_text(encoding='utf-8-sig'))
    validate_profile(profile)
    return profile


def draw_profile(profile, ax):
    """Draw the same absolute-mm layout in CLI and GUI previews."""
    from itertools import product
    validate_profile(profile)
    dims = np.asarray(profile['box_dims_mm'])
    corners = np.asarray(list(product((-1, 1), repeat=3))) * dims / 2
    for i, p in enumerate(corners):
        for q in corners[i+1:]:
            if np.count_nonzero(p != q) == 1:
                ax.plot(*np.stack((p, q)).T, color='gray', alpha=.6)
    for face in FACE_NORMALS:
        markers = [m for m in profile['markers'] if m['face'] == face]
        if markers:
            xyz = np.asarray([m['xyz_mm'] for m in markers])
            ax.scatter(*xyz.T, label=f'{face}: {len(markers)}', depthshade=False)
            for marker, point in zip(markers, xyz):
                ax.text(*point, marker['id'], fontsize=7)
    scale = float(dims.max()) * .3
    for i, color in enumerate(('red', 'green', 'blue')):
        axis = np.eye(3)[i] * scale
        ax.quiver(0, 0, 0, *axis, color=color)
        ax.text(*axis, '+' + 'XYZ'[i], color=color)
    ax.set(xlabel='Box local X (mm)', ylabel='Box local Y (mm)', zlabel='Box local Z (mm)',
           title=f'{profile["profile_id"]}\n{profile["publication"]}; origin = geometric center')
    ax.set_box_aspect(dims)
    ax.legend(loc='upper left')


def preview_profile(profile, path):
    """Save a local geometry check; this does not attest physical calibration."""
    import matplotlib.pyplot as plt
    fig = plt.figure(figsize=(11, 8))
    ax = fig.add_subplot(111, projection='3d')
    draw_profile(profile, ax)
    fig.tight_layout()
    fig.savefig(path, dpi=140)
    plt.close(fig)


def record_truth(*, samples=100, genuine_rotation=False, box_dims=DIMENSIONS, motion='free_fall'):
    if motion not in MOTIONS:
        raise ValueError('Unknown motion.')
    com_offset = (3., -4., 2.) if motion == 'free_fall' else (0., 0., 0.)
    engine = MuJoCoEngine(size=box_dims, mass=1., com_offset=com_offset)
    initial = Rotation.from_euler('xyz', [15., 20., 10.], degrees=True).as_matrix()
    q_xyzw = Rotation.from_matrix(WORLD_TO_ANALYSIS.T @ initial).as_quat()
    engine.init_quat = q_xyzw[[3, 0, 1, 2]].tolist()
    # Keep the original public example state. Larger boxes need enough clearance
    # for this no-contact lane; this is not an ISTA drop-height specification.
    height = max(4., float(np.linalg.norm(np.asarray(box_dims) / 2000.)) + 3.4)
    engine.init_pos = [0.12, -0.23, height]
    if motion != 'free_fall':
        from .scenarios import Scenarios
        # Reuse existing contact-feature orientation calculation, with an
        # explicitly virtual height rather than any claimed standard schedule.
        sequence = {'face': '08_Face_3_Screen_High', 'edge': '01_Edge_3-4', 'corner': '04_Corner_3-4-6'}[motion]
        euler = Scenarios.get_euler_angles(sequence, tuple(box_dims), 'Type G')
        q = Scenarios.get_orientation_from_euler(*euler)
        engine.set_initial_state(100., q)
        engine.init_pos[:2] = [.12, -.23]
    engine.build()
    engine.data.qvel[:3] = [.025, -.015, 0.]
    if genuine_rotation:
        engine.data.qvel[3:6] = [np.pi / ((samples - 1) * .008), 0., 0.]
    history = engine.record_samples(samples=samples, substeps=4)
    params = {'initial_position_m': engine.init_pos, 'initial_quaternion_wxyz': list(engine.init_quat),
                     'initial_linear_velocity_m_s': [.025, -.015, 0.],
                     'initial_local_angular_velocity_rad_s': [np.pi / ((samples - 1) * .008), 0., 0.] if genuine_rotation else [0., 0., 0.],
                     'mass_kg': 1., 'com_offset_mm': list(com_offset), 'timestep_s': float(engine.model.opt.timestep),
                     'substeps': 4, 'gravity_m_s2': [0., 0., -9.81],
                     'scenario': motion, 'genuine_rotation': genuine_rotation,
                     'lowest_point_height_mm': None if motion == 'free_fall' else 100.,
                     'contact_feature': None if motion == 'free_fall' else sequence,
                     'inertia_assumption': 'homogeneous cuboid moments about specified COM',
                     'body_inertia_kg_m2': engine.model.body_inertia[1].tolist(),
                     'contact_model': [{'name': mujoco.mj_id2name(engine.model,mujoco.mjtObj.mjOBJ_GEOM,i),
                        'friction': engine.model.geom_friction[i].tolist(), 'margin_m': float(engine.model.geom_margin[i]),
                        'condim': int(engine.model.geom_condim[i]), 'solref': engine.model.geom_solref[i].tolist(),
                        'solimp': engine.model.geom_solimp[i].tolist()} for i in range(engine.model.ngeom)],
                     'solver': int(engine.model.opt.solver), 'iterations': int(engine.model.opt.iterations),
                     'integrator': int(engine.model.opt.integrator),
                     'contact_note': 'Uncalibrated rigid contact. Margin is activation distance, solref damping is not restitution.',
                     'recorded_contact_count': [f['ContactCount'] for f in history],
                     'recorded_contact_force_n': [f['ContactNormalForceN'] for f in history],
                     'recorded_min_corner_height_mm': [min(f[f'C{i}'][2] for i in range(1,9)) for f in history]}
    return history, params


def make_case(case_id, *, seed=74082, profile=None, motion='free_fall'):
    if case_id not in CASES:
        raise ValueError(f'Unknown case: {case_id}')
    profile = example_profile() if profile is None else copy.deepcopy(profile)
    layout_hash = validate_profile(profile)
    history, params = record_truth(genuine_rotation=case_id == 'genuine_rotation', box_dims=profile['box_dims_mm'], motion=motion)
    times = np.asarray([f['time'] for f in history])
    origins = np.asarray([WORLD_TO_ANALYSIS @ f['BodyOrigin'] for f in history])
    com = np.asarray([WORLD_TO_ANALYSIS @ f['COM'] for f in history])
    rotations = np.asarray([WORLD_TO_ANALYSIS @ f['RotationMatrix'] for f in history])
    local = np.asarray([m['xyz_mm'] for m in profile['markers']])
    truth_markers = np.einsum('nij,mj->nmi', rotations, local) + origins[:, None, :]
    observed_rotations = rotations.copy()
    events = []
    first, second = (30,65) if motion == 'free_fall' else (65,85)
    flips = {'x': [(first, 'X')], 'y': [(first, 'Y')], 'z': [(first, 'Z')],
             'xx': [(first, 'X'), (second, 'X')], 'xy': [(first, 'X'), (second, 'Y')], 'gap_x': [(first, 'X')]}.get(case_id, [])
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
        events.append({'kind': 'constraint_dropout', 'remaining_ids': [m['id'] for m in profile['markers'][:2]], 'scope': 'all-frames'})
    manifest = {'schema_version': '1', 'generator_version': VERSION, 'source_kind': 'mujoco_synthetic',
                'evidence_level': 'synthetic_integration', 'case_id': case_id, 'seed': seed,
                'mujoco_version': mujoco.__version__, 'parameters': params, 'profile': profile,
                'layout_hash': layout_hash, 'coordinate_policy': 'global-y-up-box-xyz-mm',
                'world_transform': WORLD_TO_ANALYSIS.tolist(), 'local_basis_changed': False,
                'quaternion_order': 'wxyz', 'events': events,
                'expected_flip_frames': [f for f, _ in flips], 'expected_axes': [a for _, a in flips],
                'expected_recommendation': [{'time_s': float(times[f]), 'axis': a} for f, a in flips],
                'recommendation_contract': 'conditional-continuity-v1', 'expected_approval': False,
                'pose_tolerances': {'position_mm': .1, 'rotation_deg': .1},
                'truth_note': 'Body origin is the analysis pose origin. COM remains separate.'}
    return manifest, times, origins, com, rotations, truth_markers, observed


def write_case(directory, case_id, *, seed=74082, profile=None, motion='free_fall'):
    manifest, times, origins, com, rotations, truth, observed = make_case(case_id, seed=seed, profile=profile, motion=motion)
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
        profile = manifest['profile']
        artifact = {
            'SourceKind': 'mujoco_synthetic',
            'ModelId': 'public-virtual-box-' + 'x'.join(f'{d:g}' for d in profile['box_dims_mm']) + '-mm',
            **dict(zip(('BoxLengthMm', 'BoxWidthMm', 'BoxHeightMm'), profile['box_dims_mm'])),
            'IstaType': 'not_applicable',
            'ScenarioId': f'public-{motion}' + ('-genuine-rotation' if case_id == 'genuine_rotation' else '') + '-v1',
            'ScenarioKind': f'synthetic_{motion}',
            'MarkerLayoutId': profile['profile_id'],
            'MarkerLayoutHash': validate_profile(profile),
            'CoordinatePolicy': 'world-y-up-box-local-fixed-center-v1',
            'UnitsPolicy': 'bma-mm-s-rotvec-rad-summary-deg-v1',
            'GeneratorVersion': VERSION,
        }
        writer.writerow(['Format Version', '1.25', 'Length Units', 'Millimeters', 'Coordinate Space', 'Global',
                         'Source Kind', 'mujoco_synthetic', 'Generator Version', VERSION,
                         RAW_KEY, metadata_json(artifact)])
        writer.writerow([])
        header = {k: ['', ''] for k in ('type', 'name', 'id', 'parent', 'category', 'component')}
        header['component'] = ['Frame', 'Time']
        body_name = 'PublicExample' if manifest['profile']['profile_id'] == example_profile()['profile_id'] else manifest['profile']['profile_id']
        for marker in manifest['profile']['markers']:
            for key, value in [('type', 'Rigid Body Marker'), ('name', body_name + ':' + marker['id']),
                               ('id', marker['id']), ('parent', body_name), ('category', 'Position')]:
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
    layouts = parser.add_mutually_exclusive_group()
    layouts.add_argument('--profile', help='Explicit local JSON layout; omit for the public example.')
    layouts.add_argument('--example', choices=('18','32'), default='18')
    parser.add_argument('--motion', choices=MOTIONS, default='free_fall')
    parser.add_argument('--preview', action='store_true', help='Also save a local box/marker layout image.')
    args = parser.parse_args()
    profile = load_profile(args.profile, example=args.example)
    for case in CASES if args.case == 'all' else [args.case]:
        root = write_case(args.output, case, seed=args.seed, profile=profile, motion=args.motion)
        if args.preview:
            preview_profile(profile, root / 'layout.png')
        print(root)


if __name__ == '__main__':
    main()
