"""Shared marker conventions. A changed meaning changes its policy identity."""
import numpy as np

FACE_NORMALS = {'FRONT': (0, 0, 1), 'BACK': (0, 0, -1), 'RIGHT': (1, 0, 0),
                'LEFT': (-1, 0, 0), 'TOP': (0, 1, 0), 'BOTTOM': (0, -1, 0)}
HALF_TURNS = {'X': np.diag([1., -1., -1.]), 'Y': np.diag([-1., 1., -1.]),
              'Z': np.diag([-1., -1., 1.])}
FACE_MAPS = {
    'X': {'FRONT': 'BACK', 'BACK': 'FRONT', 'TOP': 'BOTTOM', 'BOTTOM': 'TOP'},
    'Y': {'FRONT': 'BACK', 'BACK': 'FRONT', 'LEFT': 'RIGHT', 'RIGHT': 'LEFT'},
    'Z': {'LEFT': 'RIGHT', 'RIGHT': 'LEFT', 'TOP': 'BOTTOM', 'BOTTOM': 'TOP'},
}
LOCAL_AXIS_INDEX = {'X': 0, 'Y': 1, 'Z': 2}
LOCAL_HALF_TURN_ROTVECS = {axis: np.eye(3)[index]*np.pi for axis,index in LOCAL_AXIS_INDEX.items()}
