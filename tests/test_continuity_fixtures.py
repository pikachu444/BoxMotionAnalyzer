"""Independent physical identities and observed-only export for the new challenge."""
import hashlib
import json

import numpy as np
import pandas as pd
from scipy.spatial.transform import Rotation

from src.simulation.continuity_fixtures import make_recording, write_recording, read_spec
from src.analysis.pipeline.data_loader import DataLoader


def test_frozen_kinematics_and_moving_freeze_match_independent_conventions():
    data = make_recording('recording_01')
    local = np.asarray([m['xyz_mm'] for m in read_spec()['profile']['markers']])
    # SciPy intrinsic XYZ independently checks the specification's Rx Ry Rz.
    expected_rotation = Rotation.from_euler('XYZ', [11, -17, 8], degrees=True).as_matrix()
    np.testing.assert_allclose(data['rotation_matrix'][0], expected_rotation, atol=1e-14)
    np.testing.assert_allclose(data['truth_markers'][0],
                               local @ expected_rotation.T + [70, 1500, -40], atol=1e-12)
    assert data['manifest']['expected_recommendation'] == [
        {'time_s': .384, 'axis': 'X'}, {'time_s': .896, 'axis': 'Y'}, {'time_s': 1.408, 'axis': 'Z'}]
    held = make_recording('recording_02')
    assert np.linalg.norm(held['truth_markers'][129] - held['truth_markers'][123]) > 1
    np.testing.assert_array_equal(held['rigid_body_markers'][124:130],
                                 np.repeat(held['rigid_body_markers'][123:124], 6, axis=0))
    assert np.isnan(held['rigid_body_markers'][98:104]).all()


def test_one_observed_export_supports_two_incompatible_truths_without_oracle_columns(tmp_path):
    root = write_recording(tmp_path, 'recording_03')
    manifest = json.loads((root / 'observed.synthetic.json').read_text())
    header, raw = DataLoader().load_csv(str(root / 'observed.csv'))
    assert 'Marker' not in header['type']
    assert len(raw) == 241 and raw.shape[1] == 2 + 24 * 3
    assert manifest['files']['observed.csv'] == hashlib.sha256((root / 'observed.csv').read_bytes()).hexdigest()
    assert len(manifest['oracle_interpretations']) == 2
    assert not any(key in header.get('artifact_metadata', {}) for key in ('events', 'expected_recommendation', 'oracle_interpretations'))
    alternate = pd.read_csv(root / 'truth_actual_intersample_turn.csv')
    primary = pd.read_csv(root / 'truth_pose.csv')
    fields = [f'r{i}{j}' for i in range(3) for j in range(3)]
    primary_r = primary[fields].to_numpy().reshape(-1, 3, 3)
    alternate_r = alternate[fields].to_numpy().reshape(-1, 3, 3)
    local = np.asarray([m['xyz_mm'] for m in read_spec()['profile']['markers']])
    origins = primary[[f'body_{a}_mm' for a in 'xyz']].to_numpy()
    np.testing.assert_allclose(raw.iloc[:, 2:].to_numpy(float).reshape(-1, 24, 3),
                               np.einsum('nij,mj->nmi', alternate_r, local) + origins[:, None, :], atol=1e-10)
    separation = np.degrees((Rotation.from_matrix(primary_r[112:]).inv()
                             * Rotation.from_matrix(alternate_r[112:])).magnitude())
    np.testing.assert_allclose(separation, 180., atol=1e-10)
