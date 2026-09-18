"""A face-local line does not determine whole-box pose observability."""
import json
from pathlib import Path

import numpy as np
import pytest
from scipy.spatial.transform import Rotation

from src.analysis.pipeline.data_loader import DataLoader
from src.analysis.pipeline.parser import Parser
from src.analysis.pipeline.pipeline_controller import PipelineController
from src.config import config_app
from src.config.config_analysis_ui import get_raw_mode_options
from src.config.data_columns import FACE_PREFIX_TO_INFO, SourceCols
from src.simulation.corruption_export import write_observations
from src.simulation.marker_fixtures import example_profile, load_profile, validate_profile
from test_general_export_recovery import observed_only, file_hashes


def collinear_front_profile(count):
    profile = example_profile()
    profile['profile_id'] = f'public-collinear-front-{count}'
    profile['markers'] = [m for m in profile['markers'] if m['face'] != 'FRONT']
    # Three coordinates match the successful pre-fix F4-missing investigation.
    xs = [-60., -20., 20.] if count == 3 else np.linspace(-60., 60., count)
    profile['markers'] += [dict(id=f'F{i+1}', face='FRONT', xyz_mm=[float(x), 0., 40.])
                           for i, x in enumerate(xs)]
    return profile


@pytest.mark.parametrize('count', [3, 4, 5])
def test_public_collinear_face_export_recovers_whole_pose(tmp_path, monkeypatch, count):
    """Public writer -> normal reader -> real Raw fit, no evaluator input."""
    original = example_profile()
    original_hash = validate_profile(original)
    profile = collinear_front_profile(count)
    profile_path = tmp_path / 'layout.json'
    profile_path.write_text(json.dumps(profile), encoding='utf-8')
    loaded = load_profile(profile_path)
    assert loaded == profile
    # Harmless JSON whitespace/order cannot change an existing profile hash.
    profile_path.write_text(json.dumps(profile, sort_keys=True, indent=2), encoding='utf-8')
    assert validate_profile(load_profile(profile_path)) == validate_profile(profile)
    times = np.arange(50) * .01
    origins = np.column_stack((17 + 20*times, 200 - 5*times, 11 + 3*times))
    theta = np.deg2rad(10 + 20*times)
    rotations = np.zeros((50, 3, 3))
    rotations[:, 0, 0] = rotations[:, 1, 1] = np.cos(theta)
    rotations[:, 1, 0] = np.sin(theta)
    rotations[:, 0, 1] = -np.sin(theta)
    rotations[:, 2, 2] = 1.
    trajectory = dict(schema_version=1, source_kind='handcrafted_dummy',
        coordinate_policy='world-y-up-box-local-fixed-center-v1', frame=list(range(50)),
        time_s=times.tolist(), body_origin_mm=origins.tolist(), rotation_matrix=rotations.tolist())
    root = write_observations(tmp_path / 'capture', trajectory, loaded,
                              dict(schema_version=1, events=[]), 74082)
    before = file_hashes(root)
    monkeypatch.setattr(config_app, 'BOX_DIMS', config_app.BOX_DIMS.copy())
    monkeypatch.setattr(config_app, 'LOCAL_BOX_CORNERS', config_app.LOCAL_BOX_CORNERS.copy())
    with observed_only(monkeypatch, root):
        header, raw = DataLoader().load_csv(str(root / 'observed.csv'))
        parsed = Parser(FACE_PREFIX_TO_INFO).process(header, raw)
        result = PipelineController().process_parsed_data(dict(box_dimensions=profile['box_dims_mm'],
            processing_mode='raw', slice_filter_by='time', slice_start_val=0., slice_end_val=.49,
            analysis_options=get_raw_mode_options(), enable_result_resampling=False), parsed)
    assert len(result) == 50 and set(result[SourceCols.POSE]) == {'Optimized'}
    actual = result[['P_TX', 'P_TY', 'P_TZ', 'P_RX', 'P_RY', 'P_RZ']].to_numpy(float)
    position_error = float(np.max(np.linalg.norm(actual[:, :3] - origins, axis=1)))
    rotation_error = float(np.max((Rotation.from_matrix(rotations).inv() *
        Rotation.from_rotvec(actual[:, 3:])).magnitude() * 180 / np.pi))
    # Existing noise-free public mechanics bounds, not detector tuning or
    # a claim of physical accuracy, global uniqueness or noise stability.
    assert position_error < .1 and rotation_error < .1
    local = np.array([[-100,-60,-40],[100,-60,-40],[100,60,-40],[-100,60,-40],
                      [-100,-60,40],[100,-60,40],[100,60,40],[-100,60,40]])
    expected = np.einsum('nij,kj->nki', rotations, local) + origins[:, None, :]
    corners = result[[f'C{i}_{axis}' for i in range(1,9) for axis in 'XYZ']].to_numpy(float).reshape(-1,8,3)
    # 0.1 mm origin plus 0.1 deg at the 123.3 mm corner radius is <0.316 mm.
    assert np.max(np.linalg.norm(corners - expected, axis=2)) < .4
    assert file_hashes(root) == before
    assert example_profile() == original and validate_profile(example_profile()) == original_hash
    evidence = Path('tmp/issue116'); evidence.mkdir(exist_ok=True, parents=True)
    (evidence / f'recovery-{count}.json').write_text(json.dumps(dict(
        front_markers=count, samples=50, position_error_mm=position_error,
        rotation_error_deg=rotation_error, input_sha256=before,
        oracle='Declared Rz(10+20t deg), translation [17+20t,200-5t,11+3t] mm',
        evidence='Public synthetic mechanics; not independently calibrated real accuracy'), indent=2))


@pytest.mark.parametrize('count', [3, 4, 5])
def test_face_only_profile_stays_unavailable_in_pose_solver(count):
    from src.analysis.pipeline.pose_optimizer import PoseOptimizer
    import pandas as pd
    profile = collinear_front_profile(count)
    profile['markers'] = [m for m in profile['markers'] if m['face'] == 'FRONT']
    validate_profile(profile)  # Importing geometry never certifies observability.
    row = {f"{m['id']}_{axis}": value for m in profile['markers']
           for axis, value in zip('XYZ', m['xyz_mm'])}
    row.update({f"{m['id']}_FaceInfo": 'FRONT' for m in profile['markers']})
    result = PoseOptimizer(config_app.FACE_DEFINITIONS, config_app.LOCAL_BOX_CORNERS).process(
        pd.DataFrame([row], index=pd.Index([0.], name='Time')), box_dims=profile['box_dims_mm'])
    assert result[SourceCols.POSE].iloc[0] == 'UnidentifiableGeometry'
    columns = [f'P_{c}' for c in ('TX','TY','TZ','RX','RY','RZ')]
    columns += [f'C{i}_{axis}' for i in range(1,9) for axis in 'XYZ']
    assert result[columns].isna().all().all()
