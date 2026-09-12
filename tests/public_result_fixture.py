"""Small literal GUI/schema input; no capture, simulation or physics oracle."""
from contextlib import contextmanager
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np
import pandas as pd


@contextmanager
def public_result_file():
    # Three identity poses of a 100 x 60 x 40 mm box in Y-up millimetres.
    # Explicit canonical headers keep this independent of capture/export code.
    centers = np.array([[100., 200., 300.], [101., 200., 300.], [102., 200., 300.]])
    corners = np.array([[-50, -30, -20], [50, -30, -20], [50, 30, -20], [-50, 30, -20],
                        [-50, -30, 20], [50, -30, 20], [50, 30, 20], [-50, 30, 20]])
    columns = {('Info', 'Frame', 'Frame'): [0, 1, 2], ('Info', 'Time', 'Time'): [0., .01, .02],
               ('Info', 'Artifact', 'SchemaVersion'): ['1'] * 3,
               ('Info', 'Artifact', 'SourceKind'): ['handcrafted_dummy'] * 3}
    for axis, label in enumerate(('P_TX', 'P_TY', 'P_TZ')):
        columns[('Position', 'CoM', label)] = centers[:, axis]
        for index, corner in enumerate(corners, 1):
            columns[('Position', f'C{index}', label)] = centers[:, axis] + corner[axis]
    for label in ('P_RX', 'P_RY', 'P_RZ'):
        columns[('Position', 'CoM', label)] = np.zeros(3)
    with TemporaryDirectory(prefix='bma-public-schema-') as directory:
        path = Path(directory) / 'public.proc'
        frame = pd.DataFrame(columns)
        frame.columns = pd.MultiIndex.from_tuples(frame.columns)
        frame.to_csv(path, index=False)
        yield str(path)
