"""GUI export orchestration: explicit geometry/time, cancellation, no overwrite."""
from pathlib import Path
import json

import numpy as np
import pandas as pd
import pytest
from scipy.spatial.transform import Rotation

from src.simulation import marker_export, corruption_export
from src.simulation.history_trajectory import history_to_trajectory
from src.simulation.data_exporter import DataExporter
from src.simulation.marker_fixtures import example_profile
from src.analysis.pipeline.data_loader import DataLoader
from src.analysis.pipeline.parser import Parser
from src.config.data_columns import FACE_PREFIX_TO_INFO
from test_simulation_export import history


def simulation():
    return dict(mass=1., friction=.4, elasticity=.1, com_offset=(3., -4., 2.),
                height=250., quat=[1., 0., 0., 0.], duration=.4)


def test_history_adapter_uses_actual_time_world_basis_and_separate_com():
    times = [0., .013, .041, .09]
    rotations = Rotation.from_euler('xyz', [[10, 20, 30], [12, 19, 31], [18, 10, 40], [25, 9, 46]], degrees=True)
    recorded = history(times, rotations)
    trajectory = history_to_trajectory(recorded)
    direct = DataExporter(recorded).calculate_derivatives()
    # Literal independently specified world map, never local-basis conjugation.
    transform = np.array([[1, 0, 0], [0, 0, 1], [0, -1, 0]])
    expected = transform @ rotations.as_matrix()
    np.testing.assert_array_equal(trajectory['time_s'], times)
    np.testing.assert_allclose(trajectory['rotation_matrix'], expected, atol=1e-14)
    np.testing.assert_allclose(Rotation.from_rotvec(direct['rotation']).as_matrix(), expected, atol=1e-14)
    np.testing.assert_allclose(trajectory['body_origin_mm'], direct['Center'][0], atol=1e-12)
    np.testing.assert_allclose(trajectory['com_mm'] - trajectory['body_origin_mm'],
                               np.einsum('nij,j->ni', expected, [3, -4, 2]), atol=1e-12)


@pytest.mark.parametrize('kind', [None, 'missing', 'flip_180_local_axis', 'gaussian_noise'])
def test_actual_engine_capture_uses_public_api_and_reopens(kind, tmp_path):
    profile = example_profile()
    settings = dict(kind=kind, channel='rigid_body_markers', start=.08, end=.16, axis='Y', std_mm=.03)
    path = Path(marker_export.generate_marker_capture(tmp_path / 'capture', profile, simulation(), settings, 42))
    header, raw = DataLoader().load_csv(str(path))
    parsed = Parser(FACE_PREFIX_TO_INFO).process(header, raw)
    assert header['artifact_metadata']['SourceKind'] == 'mujoco_synthetic'
    assert len(parsed) == 50
    np.testing.assert_allclose(parsed.index, np.arange(50) * .008, atol=1e-14)
    # At t=0 identity MuJoCo orientation -> (local x, local z, -local y),
    # with 250-mm clearance + 40-mm half-height. Local COM is not pose origin.
    for marker in profile['markers']:
        x, y, z = marker['xyz_mm']
        np.testing.assert_allclose(parsed.iloc[0][[marker['id'] + '_' + a for a in 'XYZ']].to_numpy(float),
                                   [x, 290 + z, -y], atol=1e-10)
    coords = parsed[[f"{m['id']}_{a}" for m in profile['markers'] for a in 'XYZ']].to_numpy(float)
    if kind == 'missing':
        assert np.isnan(coords[10:20]).all() and np.isfinite(coords[:10]).all() and np.isfinite(coords[20:]).all()
    else:
        assert np.isfinite(coords).all()
    if kind in ('gaussian_noise', 'flip_180_local_axis'):
        clean = marker_export.generate_marker_capture(tmp_path / 'clean', profile, simulation(), dict(kind=None), 42)
        ch, cr = DataLoader().load_csv(clean)
        base = Parser(FACE_PREFIX_TO_INFO).process(ch, cr)
        columns = [f"{m['id']}_{a}" for m in profile['markers'] for a in 'XYZ']
        assert not np.allclose(base[columns].iloc[10:20], coords[10:20])
        pd.testing.assert_frame_equal(base.iloc[:10], parsed.iloc[:10])
    manifest = json.loads((path.parent / 'observed.synthetic.json').read_text())
    assert manifest['completion'] == 'complete'
    assert len(manifest['events']) == int(kind is not None)
    assert all(forbidden not in path.read_text() for forbidden in ('truth_pose', 'truth_markers', '"events"'))
    if kind == 'gaussian_noise':
        repeat = Path(marker_export.generate_marker_capture(tmp_path / 'repeat', profile, simulation(), settings, 42))
        assert path.read_bytes() == repeat.read_bytes()


def test_time_selection_rejects_outside_recorded_data_instead_of_clamping():
    times = [0, .008, .016, .024]
    settings = dict(kind='missing', channel='rigid_body_markers', start=.009, end=.024)
    event = marker_export.fault_spec(times, settings)['events'][0]
    assert (event['start_index'], event['end_index_exclusive']) == (2, 3)
    for changes in (dict(start=.04), dict(end=.5), dict(end=.008)):
        with pytest.raises(ValueError):
            marker_export.fault_spec(times, {**settings, **changes})


def test_existing_destination_and_writer_failure_keep_previous_files(tmp_path, monkeypatch):
    target = tmp_path / 'capture'
    target.mkdir()
    keep = target / 'keep.txt'; keep.write_text('keep')
    args = (target, example_profile(), simulation(), dict(kind=None), 42)
    with pytest.raises(FileExistsError):
        marker_export.generate_marker_capture(*args)
    assert keep.read_text() == 'keep'

    def fail(root, *args):
        (root / 'partial.csv').write_text('partial')
        raise OSError('injected write failure')
    monkeypatch.setattr(corruption_export, '_write_truth', fail)
    with pytest.raises(OSError, match='injected'):
        marker_export.generate_marker_capture(tmp_path / 'new', *args[1:])
    assert list(tmp_path.iterdir()) == [target]


@pytest.mark.parametrize('phase', ['engine', 'observed', 'truth'])
def test_cancellation_cleans_only_new_staging_directory(phase, tmp_path, monkeypatch):
    cancelled = False
    keep = tmp_path / 'existing.csv'; keep.write_text('keep')
    if phase == 'engine':
        def progress(value, text):
            nonlocal cancelled
            if value > 0:
                cancelled = True
    else:
        progress = None
        key = '_write_observed' if phase == 'observed' else '_write_truth'
        original = getattr(corruption_export, key)
        def interrupt(*args, **kwargs):
            nonlocal cancelled
            cancelled = True
            return original(*args, **kwargs)
        monkeypatch.setattr(corruption_export, key, interrupt)
    with pytest.raises(InterruptedError):
        marker_export.generate_marker_capture(tmp_path / 'capture', example_profile(), simulation(),
            dict(kind=None), 42, cancelled=lambda: cancelled, progress=progress)
    assert list(tmp_path.iterdir()) == [keep] and keep.read_text() == 'keep'
