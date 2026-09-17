"""One MuJoCo Z-up history to analysis Y-up adapter; local axes are unchanged."""
import numpy as np
from scipy.spatial.transform import Rotation

WORLD_TRANSFORM = np.array([[1., 0., 0.], [0., 0., 1.], [0., -1., 0.]])


def world_vectors(history, key):
    value = np.asarray([frame[key] for frame in history], dtype=float)
    if value.shape != (len(history), 3) or not np.isfinite(value).all():
        raise ValueError(f'Simulation {key} must contain finite XYZ vectors.')
    return value @ WORLD_TRANSFORM.T


def history_to_trajectory(history):
    """Copy actual timestamps, body origin, COM and world-basis-only rotations."""
    if not history:
        raise ValueError('Simulation history is empty.')
    times = np.asarray([frame['time'] for frame in history], dtype=float)
    with np.errstate(over='ignore', invalid='ignore'):
        intervals = np.diff(times)
    if not np.isfinite(times).all() or not np.isfinite(intervals).all() or np.any(intervals <= 0):
        raise ValueError('Simulation times must be finite and strictly increasing.')
    quaternion = np.asarray([frame['QuaternionWXYZ'] for frame in history], dtype=float)
    if quaternion.shape != (len(times), 4) or not np.isfinite(quaternion).all():
        raise ValueError('Simulation quaternion must contain finite WXYZ values.')
    norms = np.linalg.norm(quaternion, axis=1)
    if np.any(norms == 0) or not np.isfinite(norms).all():
        raise ValueError('Simulation quaternion must have a finite nonzero norm.')
    quaternion = quaternion / norms[:, None]
    rotation = Rotation.from_matrix(WORLD_TRANSFORM) * Rotation.from_quat(quaternion[:, [1, 2, 3, 0]])
    return dict(schema_version=1, source_kind='mujoco_synthetic',
        coordinate_policy='world-y-up-box-local-fixed-center-v1',
        time_s=times, frame=np.arange(len(times)), body_origin_mm=world_vectors(history, 'BodyOrigin'),
        com_mm=world_vectors(history, 'COM'), rotation_matrix=rotation.as_matrix())
