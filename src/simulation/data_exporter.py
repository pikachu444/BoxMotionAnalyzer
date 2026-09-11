"""Non-destructive simulation export; conventions are in docs/simulation.md."""
import copy
import json
import os
from pathlib import Path
import tempfile
import numpy as np
import pandas as pd
from scipy.spatial.transform import Rotation
from src.config.data_columns import HeaderL1 as L1, HeaderL2 as L2, HeaderL3 as L3
from src.utils.artifact_metadata import normalize_metadata

WORLD_TRANSFORM = np.array([[1., 0., 0.], [0., 0., 1.], [0., -1., 0.]])
EXPORT_VERSION = 'simulation-pose-actual-time-v1'


def interval_derivatives(values, times):
    """Backward interval velocity; acceleration between interval midpoints."""
    velocity = np.full_like(values, np.nan, dtype=float)
    acceleration = np.full_like(values, np.nan, dtype=float)
    dt = np.diff(times)
    velocity[1:] = np.diff(values, axis=0) / dt[:, None]
    acceleration[2:] = np.diff(velocity[1:], axis=0) / ((dt[:-1] + dt[1:]) / 2)[:, None]
    return velocity, acceleration


class DataExporter:
    def __init__(self, history: list, add_noise=False, noise_std=1.0, *, seed=0,
                 simulation_settings=None):
        self.history = history
        self.add_noise = bool(add_noise)
        self.noise_std = float(noise_std)
        if not np.isfinite(self.noise_std) or self.noise_std < 0:
            raise ValueError('Noise standard deviation must be finite and nonnegative.')
        if not isinstance(seed, int) or isinstance(seed, bool) or seed < 0:
            raise ValueError('Noise seed must be a nonnegative integer.')
        self.seed = seed
        self.simulation_settings = copy.deepcopy(simulation_settings or {})

    @classmethod
    def from_engine(cls, history, engine, params):
        """Record actual configured simulation values, without experiment identity."""
        import mujoco
        settings = {
            'size_mm': (np.asarray(engine.size_m) * 2000).tolist(),
            'mass_kg': engine.mass, 'friction': engine.friction,
            'contact_damping_control': engine.elasticity,
            'com_offset_mm': (np.asarray(engine.com_offset) * 1000).tolist(),
            'initial_position_m': list(engine.init_pos),
            'initial_quaternion_wxyz': list(engine.init_quat),
            'timestep_s': float(engine.model.opt.timestep),
            'requested_duration_s': params['duration'], 'mujoco_version': mujoco.__version__,
        }
        return cls(history, params['add_noise'], params['noise_std'],
                   seed=params.get('noise_seed', 0), simulation_settings=settings)

    def calculate_derivatives(self):
        """Return new arrays; neither history nor nested arrays are modified."""
        if not self.history:
            raise ValueError('Simulation history is empty.')
        times = np.asarray([frame['time'] for frame in self.history], dtype=float)
        with np.errstate(over='ignore', invalid='ignore'):
            intervals = np.diff(times)
        if not np.isfinite(times).all() or not np.isfinite(intervals).all() or np.any(intervals <= 0):
            raise ValueError('Simulation times must be finite and strictly increasing.')

        def vectors(key):
            value = np.asarray([frame[key] for frame in self.history], dtype=float)
            if value.shape != (len(times), 3) or not np.isfinite(value).all():
                raise ValueError(f'Simulation {key} must contain finite XYZ vectors.')
            return value @ WORLD_TRANSFORM.T

        quaternion = np.asarray([frame['QuaternionWXYZ'] for frame in self.history], dtype=float)
        if quaternion.shape != (len(times), 4) or not np.isfinite(quaternion).all():
            raise ValueError('Simulation quaternion must contain finite WXYZ values.')
        norms = np.linalg.norm(quaternion, axis=1)
        if np.any(norms == 0) or not np.isfinite(norms).all():
            raise ValueError('Simulation quaternion must have a finite nonzero norm.')
        quaternion = quaternion / norms[:, None]
        # Change only the world basis: local box/corner axes remain unchanged.
        rotation = Rotation.from_matrix(WORLD_TRANSFORM) * Rotation.from_quat(quaternion[:, [1, 2, 3, 0]])
        quaternion = rotation.as_quat()[:, [3, 0, 1, 2]]
        for i in range(1, len(quaternion)):
            if np.dot(quaternion[i - 1], quaternion[i]) < 0:
                quaternion[i] *= -1
        omega = np.full((len(times), 3), np.nan)
        alpha = omega.copy()
        if len(times) > 1:
            dt = np.diff(times)
            omega[1:] = (rotation[1:] * rotation[:-1].inv()).as_rotvec() / dt[:, None]
            alpha[2:] = np.diff(omega[1:], axis=0) / ((dt[:-1] + dt[1:]) / 2)[:, None]
        result = {'time': times, 'quaternion': quaternion, 'rotation': rotation.as_rotvec(),
                  'omega': omega, 'alpha': alpha, 'COM': vectors('COM')}
        rng = np.random.default_rng(self.seed)
        for entity in ['Center'] + [f'C{i}' for i in range(1, 9)]:
            position = vectors('BodyOrigin' if entity == 'Center' else entity)
            if self.add_noise and entity != 'Center':
                position = position + rng.normal(0., self.noise_std, position.shape)
            velocity, acceleration = interval_derivatives(position, times)
            result[entity] = (position, velocity, acceleration)
        return result

    def export_proc_csv(self, filepath: str):
        values = self.calculate_derivatives()
        columns = {(L1.INFO, L2.FRAME, L2.FRAME): np.arange(len(self.history)),
                   (L1.INFO, L2.TIME, L3.TIME): values['time']}

        def add_vector(group, entity, keys, vector):
            for axis, key in enumerate(keys):
                columns[(group, entity, key)] = vector[:, axis]

        for entity in ['Center'] + [f'C{i}' for i in range(1, 9)]:
            output_entity = L2.COM if entity == 'Center' else entity
            position, velocity, acceleration = values[entity]
            add_vector(L1.POS, output_entity, [L3.P_TX, L3.P_TY, L3.P_TZ], position)
            add_vector(L1.VEL, output_entity, [L3.V_TX, L3.V_TY, L3.V_TZ], velocity)
            add_vector(L1.ACC, output_entity, [L3.A_TX, L3.A_TY, L3.A_TZ], acceleration)
            columns[(L1.VEL, output_entity, L3.V_TNORM)] = np.linalg.norm(velocity, axis=1)
            columns[(L1.ACC, output_entity, L3.A_TNORM)] = np.linalg.norm(acceleration, axis=1)
            if entity != 'Center':
                columns[(L1.ANALYSIS, entity, L3.REL_H)] = position[:, 1]
        add_vector(L1.POS, L2.COM, [L3.P_RX, L3.P_RY, L3.P_RZ], values['rotation'])
        add_vector(L1.VEL, L2.COM, [L3.V_RX, L3.V_RY, L3.V_RZ], values['omega'])
        add_vector(L1.ACC, L2.COM, [L3.A_RX, L3.A_RY, L3.A_RZ], values['alpha'])
        columns[(L1.VEL, L2.COM, L3.V_RNORM)] = np.linalg.norm(values['omega'], axis=1)
        columns[(L1.ACC, L2.COM, L3.A_RNORM)] = np.linalg.norm(values['alpha'], axis=1)
        add_vector('Simulation', 'InertialCOM', ['X_mm', 'Y_mm', 'Z_mm'], values['COM'])
        for axis, key in enumerate(['QW', 'QX', 'QY', 'QZ']):
            columns[('Simulation', 'BodyPose', key)] = values['quaternion'][:, axis]
        settings = {**self.simulation_settings, 'export_version': EXPORT_VERSION,
                    'derivative_policy': 'backward-interval;acceleration-midpoint-spacing;initial-nan',
                    'pose': 'body-origin;quaternion-wxyz;rotvec-rad;world-A-times-R',
                    'angular_velocity': 'global-relative-quaternion-shortest-arc-rad/s',
                    'corner_noise': {'enabled': self.add_noise, 'std_mm': self.noise_std if self.add_noise else None,
                                     'seed': self.seed if self.add_noise else None,
                                     'generator': 'numpy-default_rng-PCG64',
                                     'derivatives': 'from-exported-corner-observations'}}
        columns[(L1.INFO, 'Simulation', 'ExportVersion')] = EXPORT_VERSION
        columns[(L1.INFO, 'Simulation', 'SettingsJson')] = json.dumps(settings, sort_keys=True, separators=(',', ':'), allow_nan=False)
        columns[(L1.INFO, 'Simulation', 'Representation')] = 'body-pose-truth;noisy-corner-observations' if self.add_noise else 'simulation-truth'
        metadata = normalize_metadata({'SourceKind': 'mujoco_synthetic',
                                       'GeneratorVersion': EXPORT_VERSION,
                                       'CoordinatePolicy': 'world-y-up-box-local-fixed-center-v1',
                                       'UnitsPolicy': 'mm-s-rotvec-rad-global-angular-v1'}, new=True)
        # Missing model/layout/scene/t1/Analysis execution identity stays missing.
        size = self.simulation_settings.get('size_mm')
        if size is not None:
            if len(size) != 3 or not np.isfinite(size).all() or np.any(np.asarray(size) <= 0):
                raise ValueError('Simulation dimensions must be three positive finite values.')
            for field, value in zip(['BoxLengthMm', 'BoxWidthMm', 'BoxHeightMm'], size):
                metadata[field] = float(value)
        for field, value in metadata.items():
            columns[(L1.INFO, 'Artifact', field)] = value
        frame = pd.DataFrame(columns)
        frame.columns = pd.MultiIndex.from_tuples(frame.columns)
        output_path = Path(filepath)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path = None
        try:
            # Stay on the destination filesystem and close the handle before
            # replacing on Windows. Never truncate the last successful export.
            with tempfile.NamedTemporaryFile(
                mode='w', encoding='utf-8', newline='', dir=output_path.parent,
                prefix='.bma-export-', suffix='.tmp', delete=False,
            ) as stream:
                temporary_path = Path(stream.name)
                frame.to_csv(stream, index=False)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary_path, output_path)
        except BaseException as error:
            if temporary_path is not None:
                try:
                    temporary_path.unlink(missing_ok=True)
                except OSError as cleanup_error:
                    error.add_note(f'Could not remove temporary export {temporary_path}: {cleanup_error}')
            raise
        return str(output_path.absolute())
