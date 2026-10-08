"""PUB09 opt-in seed and contact settings; no calibrated defaults."""
from copy import deepcopy
import json
from pathlib import Path
import re
from numbers import Real

import numpy as np
from scipy.spatial.transform import Rotation

from src.utils.marker_profile_identity import envelope, validate_envelope, digest


UNITS = dict(position='mm', linear_velocity='mm/s', angular_velocity='rad/s', time='s')
PROFILE_UNITS = dict(mass='kg', position='mm', inertia='kg*m^2', time='s',
                     friction='sliding-dimensionless;torsional-and-rolling-m')


def sealed(kind, **fields):
    value = envelope(kind, **deepcopy(fields))
    value['content_hash'] = digest(value)
    return value


def check(value, kind, fields):
    validate_envelope(value, kind)
    if set(value) != {'schema_version', 'plan_spec', 'object_type', 'content_hash', *fields}:
        raise ValueError(f'Unexpected {kind} fields.')
    if value['content_hash'] != digest({k: v for k, v in value.items() if k != 'content_hash'}):
        raise ValueError(f'Stale {kind} digest.')


def finite(value, shape, label):
    def numeric(x):
        if isinstance(x, (list, tuple, np.ndarray)):
            return all(numeric(item) for item in x)
        return isinstance(x, Real) and not isinstance(x, (bool, np.bool_))
    if not numeric(value):
        raise ValueError(f'Invalid {label}; numeric values required.')
    array = np.asarray(value, dtype=float)
    if array.shape != shape or not np.isfinite(array).all() or np.asarray(value).dtype.kind == 'b':
        raise ValueError(f'Invalid {label}.')
    return array


def quaternion(value):
    q = finite(value, (4,), 'unit WXYZ quaternion')
    if abs(np.linalg.norm(q) - 1) > 1e-10:
        raise ValueError('Quaternion must be a unit WXYZ local-to-world rotation.')
    return Rotation.from_quat(q[[1, 2, 3, 0]]).as_matrix()


def source(value):
    if (not isinstance(value, dict) or set(value) != {'kind', 'motion_id', 'artifact_sha256'}
            or value['kind'] not in ('public_synthetic', 'manual', 'external_reference')
            or not isinstance(value['motion_id'], str) or not value['motion_id'].strip()
            or not isinstance(value['artifact_sha256'], str)
            or re.fullmatch('[0-9a-f]{64}', value['artifact_sha256']) is None):
        raise ValueError('Explicit input source/motion identity is required.')


SEED_FIELDS = {'seed_id', 'source', 'mode', 'position_mm', 'position_reference',
    'quaternion_wxyz', 'quaternion_convention', 'linear_velocity', 'linear_velocity_frame',
    'linear_velocity_reference', 'angular_velocity', 'angular_velocity_frame', 'world_frame',
    'units', 'reference_time_s', 'clock_policy', 'prehistory'}


def initial_condition(position_mm, quaternion_wxyz=(1., 0., 0., 0.), *,
        linear_velocity=(0., 0., 0.), angular_velocity=(0., 0., 0.),
        position_reference='body_origin', linear_velocity_reference='body_origin',
        linear_velocity_frame='world', angular_velocity_frame='world', mode='release',
        reference_time_s=0., seed_id='public-seed', input_source=None):
    value = sealed('InitialCondition', seed_id=seed_id,
        source=dict(kind='public_synthetic', motion_id=seed_id,
                    artifact_sha256=digest(dict(seed_id=seed_id))) if input_source is None else input_source,
        mode=mode, position_mm=list(position_mm), position_reference=position_reference,
        quaternion_wxyz=list(quaternion_wxyz), quaternion_convention='wxyz-active-local-to-world',
        linear_velocity=list(linear_velocity), linear_velocity_frame=linear_velocity_frame,
        linear_velocity_reference=linear_velocity_reference, angular_velocity=list(angular_velocity),
        angular_velocity_frame=angular_velocity_frame, world_frame='mujoco-z-up', units=UNITS,
        reference_time_s=reference_time_s, clock_policy='engine-starts-zero;reference=engine+offset',
        prehistory='release-begins-at-seed' if mode == 'release' else 'unknown-before-seed')
    return validate_seed(value)


def validate_seed(value):
    check(value, 'InitialCondition', SEED_FIELDS)
    source(value['source'])
    if not isinstance(value['seed_id'], str) or not value['seed_id'].strip():
        raise ValueError('Seed identity is required.')
    if (value['mode'] not in ('release', 'precontact') or value['world_frame'] != 'mujoco-z-up'
            or value['units'] != UNITS or value['quaternion_convention'] != 'wxyz-active-local-to-world'
            or value['clock_policy'] != 'engine-starts-zero;reference=engine+offset'
            or value['prehistory'] != ('release-begins-at-seed' if value['mode'] == 'release' else 'unknown-before-seed')):
        raise ValueError('Unsupported seed mode/frame/time/units.')
    for key in ('position_reference', 'linear_velocity_reference'):
        if value[key] not in ('body_origin', 'geocenter', 'com'):
            raise ValueError('Unsupported seed reference point.')
    for key in ('linear_velocity_frame', 'angular_velocity_frame'):
        if value[key] not in ('world', 'body'):
            raise ValueError('Unsupported velocity frame.')
    for key in ('position_mm', 'linear_velocity', 'angular_velocity'):
        finite(value[key], (3,), key)
    finite(value['reference_time_s'], (), 'reference time')
    quaternion(value['quaternion_wxyz'])
    return value


def canonical_state(seed, com_offset_mm):
    validate_seed(seed)
    r = quaternion(seed['quaternion_wxyz'])
    lever = r @ finite(com_offset_mm, (3,), 'COM offset')
    p = np.asarray(seed['position_mm']) - (lever if seed['position_reference'] == 'com' else 0.)
    w = np.asarray(seed['angular_velocity'], dtype=float)
    if seed['angular_velocity_frame'] == 'body': w = r @ w
    v = np.asarray(seed['linear_velocity'], dtype=float)
    if seed['linear_velocity_frame'] == 'body': v = r @ v
    if seed['linear_velocity_reference'] == 'com': v = v - np.cross(w, lever)
    return dict(origin_mm=p, rotation=r, origin_velocity_mm_s=v,
                angular_velocity_world=w, angular_velocity_body=r.T @ w,
                com_mm=p + lever, com_velocity_mm_s=v + np.cross(w, lever))


PROFILE_FIELDS = {'profile_id', 'version', 'source', 'units', 'geometry', 'mass_kg',
    'com_offset_mm', 'inertia', 'solref', 'solimp', 'friction', 'condim', 'margin_mm',
    'solver', 'calibration_status', 'approval'}


def contact_profile(*, profile_id='public-contact', mass_kg=1., com_offset_mm=(0., 0., 0.),
        inertia=None, solref=(.02, 1.), solimp=(.9, .95, .001, .5, 2.),
        friction=(.7, .01, .005), condim=4, margin_mm=None, timestep_s=.002,
        iterations=100, tolerance=1e-8):
    value = sealed('ContactParameterProfile', profile_id=profile_id, version='pub09-contact-v1',
        source=dict(kind='public_synthetic', motion_id=profile_id, artifact_sha256=digest(profile_id)),
        units=PROFILE_UNITS, geometry='cuboid-plane', mass_kg=mass_kg,
        com_offset_mm=list(com_offset_mm), inertia=dict(kind='homogeneous-cuboid-about-offset-COM',
            principal_kg_m2=None, quaternion_wxyz=[1., 0., 0., 0.]) if inertia is None else inertia, solref=list(solref),
        solimp=list(solimp), friction=list(friction), condim=condim,
        margin_mm=dict(box=5., floor=0.) if margin_mm is None else margin_mm,
        solver=dict(timestep_s=timestep_s, integrator='Euler', algorithm='Newton',
                    iterations=iterations, tolerance=tolerance),
        calibration_status='uncalibrated', approval='proposed')
    return validate_profile(value)


def validate_profile(value):
    check(value, 'ContactParameterProfile', PROFILE_FIELDS)
    source(value['source'])
    if (not isinstance(value['profile_id'], str) or not value['profile_id'].strip()
            or value['version'] != 'pub09-contact-v1' or value['units'] != PROFILE_UNITS
            or value['geometry'] != 'cuboid-plane' or value['calibration_status'] != 'uncalibrated'
            or value['approval'] != 'proposed'):
        raise ValueError('Unsupported contact profile or unapproved promotion.')
    mass = finite(value['mass_kg'], (), 'mass')
    if not .1 <= mass <= 10000: raise ValueError('Unsupported mass.')
    finite(value['com_offset_mm'], (3,), 'COM offset')
    inertia = value['inertia']
    if not isinstance(inertia, dict) or set(inertia) != {'kind', 'principal_kg_m2', 'quaternion_wxyz'}:
        raise ValueError('Unsupported inertia fields.')
    quaternion(inertia['quaternion_wxyz'])
    if inertia['kind'] == 'principal-about-COM':
        moments = finite(inertia['principal_kg_m2'], (3,), 'principal inertia')
        if np.any(moments <= 0) or 2 * max(moments) > sum(moments):
            raise ValueError('Inertia must be positive and obey triangle inequalities.')
    elif (inertia['kind'] != 'homogeneous-cuboid-about-offset-COM'
            or inertia['principal_kg_m2'] is not None or inertia['quaternion_wxyz'] != [1., 0., 0., 0.]):
        raise ValueError('Unsupported homogeneous inertia assumption.')
    solver = value['solver']
    if (not isinstance(solver, dict) or set(solver) != {'timestep_s', 'integrator', 'algorithm', 'iterations', 'tolerance'}
            or solver['integrator'] != 'Euler' or solver['algorithm'] != 'Newton'
            or type(solver['iterations']) is not int or not 1 <= solver['iterations'] <= 1000):
        raise ValueError('Unsupported solver configuration.')
    dt = finite(solver['timestep_s'], (), 'timestep')
    tol = finite(solver['tolerance'], (), 'solver tolerance')
    if not 1e-5 <= dt <= .01 or not 0 <= tol <= 1e-3: raise ValueError('Unsupported solver range.')
    ref = finite(value['solref'], (2,), 'positive-format solref')
    if ref[0] < 2 * dt or ref[1] <= 0:
        raise ValueError('Positive solref only; timeconst must be at least twice timestep (no silent clamp).')
    imp = finite(value['solimp'], (5,), 'solimp')
    if not (0 < imp[0] <= imp[1] < 1 and imp[2] > 0 and 0 < imp[3] < 1 and imp[4] >= 1):
        raise ValueError('Unsupported solimp.')
    friction = finite(value['friction'], (3,), 'friction')
    if np.any(friction < 0) or type(value['condim']) is not int or value['condim'] not in (3, 4, 6):
        raise ValueError('Unsupported friction/condim.')
    margin = value['margin_mm']
    if not isinstance(margin, dict) or set(margin) != {'box', 'floor'}:
        raise ValueError('Only contact activation margins are supported.')
    for item in margin.values():
        if not 0 <= finite(item, (), 'margin') <= 10: raise ValueError('Unsupported margin.')
    return value


def moments(profile, size_mm):
    validate_profile(profile)
    if profile['inertia']['kind'] == 'principal-about-COM':
        return profile['inertia']['principal_kg_m2']
    x, y, z = np.asarray(size_mm) / 1000.
    return (profile['mass_kg'] / 12 * np.array([y*y+z*z, x*x+z*z, x*x+y*y])).tolist()


def reseal(value):
    result = deepcopy(value)
    result['content_hash'] = digest({k: v for k, v in result.items() if k != 'content_hash'})
    return result


def save(path, value):
    """Immutable new-file output; retries preserve previous evidence."""
    with Path(path).open('x', encoding='utf-8') as stream:
        json.dump(value, stream, indent=2, allow_nan=False)


def load(path, validator):
    value = json.loads(Path(path).read_text(encoding='utf-8'),
                       parse_constant=lambda s: (_ for _ in ()).throw(ValueError(f'Nonfinite JSON: {s}')))
    return validator(value)


def compiled_settings(engine):
    import mujoco
    m = engine.model
    body = mujoco.mj_name2id(m, mujoco.mjtObj.mjOBJ_BODY, 'box')
    contacts = {}
    for role, name in (('box', 'box_geom'), ('floor', 'floor')):
        geom = mujoco.mj_name2id(m, mujoco.mjtObj.mjOBJ_GEOM, name)
        contacts[role] = dict(condim=int(m.geom_condim[geom]), friction=m.geom_friction[geom].tolist(),
            solref=m.geom_solref[geom].tolist(), solimp=m.geom_solimp[geom].tolist(),
            margin_mm=float(m.geom_margin[geom]*1000), gap_mm=float(m.geom_gap[geom]*1000),
            priority=int(m.geom_priority[geom]), solmix=float(m.geom_solmix[geom]))
    box=mujoco.mj_name2id(m,mujoco.mjtObj.mjOBJ_GEOM,'box_geom')
    floor=mujoco.mj_name2id(m,mujoco.mjtObj.mjOBJ_GEOM,'floor')
    return dict(mass_kg=float(m.body_mass[body]), com_offset_mm=(m.body_ipos[body]*1000).tolist(),
        inertia_kg_m2=m.body_inertia[body].tolist(), inertia_orientation_wxyz=m.body_iquat[body].tolist(),
        size_mm=(m.geom_size[box]*2000).tolist(), contacts=contacts,
        geometry_types=[int(m.geom_type[box]),int(m.geom_type[floor])],
        cone=int(m.opt.cone),enableflags=int(m.opt.enableflags),disableflags=int(m.opt.disableflags),
        solver=dict(timestep_s=float(m.opt.timestep), integrator='Euler' if m.opt.integrator == 0 else 'unsupported',
            algorithm='Newton' if m.opt.solver == 2 else 'unsupported', iterations=int(m.opt.iterations),
            tolerance=float(m.opt.tolerance)), gravity_m_s2=m.opt.gravity.tolist(),
        reference_safety_clamp_enabled=not bool(m.opt.disableflags & int(mujoco.mjtDisableBit.mjDSBL_REFSAFE)))


def validate_compiled_values(profile, actual, size_mm):
    validate_profile(profile)
    expected = dict(mass_kg=profile['mass_kg'], com_offset_mm=profile['com_offset_mm'],
        inertia_kg_m2=moments(profile, size_mm), size_mm=list(size_mm), solver=profile['solver'],
        gravity_m_s2=[0., 0., -9.81], reference_safety_clamp_enabled=True, contacts={},
        geometry_types=[6,0],cone=0,enableflags=0,disableflags=0)
    for role in ('box', 'floor'):
        expected['contacts'][role] = dict(condim=profile['condim'], friction=profile['friction'],
            solref=profile['solref'], solimp=profile['solimp'], margin_mm=profile['margin_mm'][role],
            gap_mm=0., priority=0, solmix=1.)
    if set(actual) != {*expected, 'inertia_orientation_wxyz'}:
        raise ValueError('Unsupported compiled physics fields.')
    def compare(a, b):
        if isinstance(b, dict): return isinstance(a, dict) and set(a) == set(b) and all(compare(a[k], b[k]) for k in b)
        if isinstance(b, (str, bool)): return type(a) is type(b) and a == b
        return np.allclose(finite(a,np.asarray(b).shape,'compiled numeric value'), b, rtol=0, atol=1e-12)
    if not all(compare(actual[k], v) for k, v in expected.items()):
        raise ValueError('Requested profile differs from actual compiled physics.')
    if not np.allclose(quaternion(actual['inertia_orientation_wxyz']),
                       quaternion(profile['inertia']['quaternion_wxyz']), rtol=0, atol=1e-12):
        raise ValueError('Compiled inertial frame differs.')
    return actual


def validate_compiled(engine):
    return validate_compiled_values(engine.contact_profile, compiled_settings(engine),
                                    (np.asarray(engine.size_m)*2000).tolist())


def configured(config, seed, profile):
    """Opt-in adapter preserves legacy fields and their explicit binding."""
    from .mode_profiles import validate_config
    result = deepcopy(config)
    if result['mode'] != 'single_drop': raise ValueError('Explicit seeds cannot reset robot sequences.')
    result['initial_condition'] = deepcopy(validate_seed(seed))
    result['contact_profile'] = deepcopy(validate_profile(profile))
    physics = result['physics_profile']
    physics.update(mass_kg=profile['mass_kg'], friction=profile['friction'][0], com_offset_mm=profile['com_offset_mm'])
    return validate_config(result)


def engine_from_config(config):
    from .mode_profiles import require_executable
    from .engine.mujoco_engine import MuJoCoEngine
    require_executable(config)
    if config['mode'] != 'single_drop': raise ValueError('Use the continuous robot runner for robot mode.')
    p = config['physics_profile']
    engine = MuJoCoEngine(size=config['size_mm'], mass=p['mass_kg'], friction=p['friction'],
        elasticity=p['contact_damping_control'], com_offset=p['com_offset_mm'], contact_profile=config.get('contact_profile'))
    if 'initial_condition' in config:
        engine.set_initial_condition(config['initial_condition'])
    else:
        step = config['sequence_profile']['steps'][0]
        q = Rotation.from_euler('xyz', step['fixed_xyz_deg'], degrees=True).as_quat()[[3, 0, 1, 2]]
        engine.set_initial_state(step['clearance_mm'], q)
    return engine
