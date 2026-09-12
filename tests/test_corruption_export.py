"""Generated channels through real file readers; no measured-camera oracle."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

import numpy as np
import pandas as pd
import pytest

from src.analysis.pipeline.data_loader import DataLoader
from src.analysis.pipeline.parser import Parser
from src.config.data_columns import FACE_PREFIX_TO_INFO
from src.simulation.corruption_export import write_observations
from src.simulation.marker_fixtures import example_profile


def trajectory():
    times = np.arange(8) * .008
    return {'schema_version': 1, 'source_kind': 'handcrafted_dummy',
            'coordinate_policy': 'world-y-up-box-local-fixed-center-v1',
            'frame': [100, 101, 104, 105, 106, 109, 110, 111], 'time_s': times.tolist(),
            'body_origin_mm': np.column_stack((100. + 1000. * times,
                np.full(8, 200.), np.full(8, 300.))).tolist(),
            'rotation_matrix': np.repeat(np.eye(3)[None], 8, axis=0).tolist()}


def physical_spec():
    return {'schema_version': 1, 'events': [
        {'kind': 'gaussian_noise', 'channel': 'physical_markers', 'start_index': 0,
         'end_index_exclusive': 8, 'marker_ids': ['F2'], 'std_mm': .02},
        {'kind': 'missing', 'channel': 'physical_markers', 'start_index': 2,
         'end_index_exclusive': 4, 'marker_ids': ['F1']},
        {'kind': 'label_permutation', 'channel': 'physical_markers', 'start_index': 2,
         'end_index_exclusive': 4, 'mapping': {'F1': 'B1', 'B1': 'F1'}},
        {'kind': 'freeze', 'channel': 'physical_markers', 'start_index': 4,
         'end_index_exclusive': 6, 'marker_ids': ['B2']},
        {'kind': 'reconnect_jump', 'channel': 'physical_markers', 'start_index': 6,
         'end_index_exclusive': 8, 'marker_ids': ['B2'], 'offset_mm': [7., -3., 4.]},
    ]}


def hashes(root):
    return {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in root.iterdir() if p.is_file()}


def physical_rows(header, raw, marker):
    indices = [i for i, (kind, mid) in enumerate(zip(header['type'], header['id']))
               if kind == 'Marker' and mid == marker]
    assert len(indices) == 3
    return raw.iloc[:, indices].apply(pd.to_numeric, errors='coerce').to_numpy(float)


def test_physical_visibility_and_id_routing_preserve_solved_analysis_and_truth(tmp_path):
    values, profile = trajectory(), example_profile()
    clean = write_observations(tmp_path / 'clean', values, profile, {'schema_version': 1, 'events': []})
    faulty = write_observations(tmp_path / 'faulty', values, profile, physical_spec())
    originals = {name: (clean / name).read_bytes() for name in ('truth_pose.csv', 'truth_markers.csv')}
    assert all((faulty / name).read_bytes() == data for name, data in originals.items())
    before = hashes(faulty)
    clean_header, clean_raw = DataLoader().load_csv(str(clean / 'observed.csv'))
    header, raw = DataLoader().load_csv(str(faulty / 'observed.csv'))
    parser = Parser(FACE_PREFIX_TO_INFO)
    parsed = parser.process(header, raw)
    pd.testing.assert_frame_equal(parsed, parser.process(clean_header, clean_raw))
    np.testing.assert_array_equal(parsed.index, values['time_s'])
    np.testing.assert_array_equal(pd.to_numeric(parsed['Frame']), values['frame'])
    np.testing.assert_allclose(physical_rows(header, raw, 'F1')[2], [133., 169., 260.], atol=1e-12)
    assert np.isnan(physical_rows(header, raw, 'B1')[2:4]).all()
    np.testing.assert_allclose(parsed.iloc[2][['F1_X', 'F1_Y', 'F1_Z']].to_numpy(float),
                               [137., 212., 340.], atol=1e-12)
    assert hashes(faulty) == before
    manifest = json.loads((faulty / 'observed.synthetic.json').read_text())
    assert manifest['completion'] == 'complete' and manifest['com_available'] is False
    assert manifest['files']['observed.csv'] == before['observed.csv']
    assert all(manifest['files'][name] == before[name] for name in originals)
    assert all(pd.read_csv(faulty / 'truth_pose.csv')[f'com_{a}_mm'].isna().all() for a in 'xyz')
    observed_text = (faulty / 'observed.csv').read_text()
    for forbidden in ('truth_pose', 'truth_markers', '"events"', '"mapping"', '"seed"', 'start_index'):
        assert forbidden not in observed_text


def test_numpy_trajectory_and_explicit_com_round_trip(tmp_path):
    values = trajectory()
    for field in ('time_s', 'body_origin_mm', 'rotation_matrix'):
        values[field] = np.asarray(values[field])
    values['com_mm'] = values['body_origin_mm'] + [1., -2., 3.]
    root = write_observations(tmp_path / 'numpy', values, example_profile(), {'schema_version': 1, 'events': []})
    loaded = pd.read_csv(root / 'truth_pose.csv')
    np.testing.assert_allclose(loaded[['com_x_mm', 'com_y_mm', 'com_z_mm']], values['com_mm'])
    np.testing.assert_array_equal(loaded.frame, values['frame'])


def test_cli_reopens_and_refuses_overwrite_or_invalid_input(tmp_path):
    truth_path, spec_path = tmp_path / 'trajectory.json', tmp_path / 'faults.json'
    truth_path.write_text(json.dumps(trajectory()), encoding='utf-8')
    spec_path.write_text(json.dumps(physical_spec()), encoding='utf-8')
    out = tmp_path / 'run'
    command = [sys.executable, '-m', 'src.simulation.corruption_export', '--trajectory', str(truth_path),
               '--spec', str(spec_path), '--seed', '42', '--output', str(out)]
    repo = Path(__file__).resolve().parents[1]
    run = subprocess.run(command, cwd=repo, capture_output=True, text=True)
    assert run.returncode == 0, run.stderr
    assert str(out / 'observed.csv') in run.stdout
    saved = hashes(out)
    retry = subprocess.run(command, cwd=repo, capture_output=True, text=True)
    assert retry.returncode == 2 and 'Generation failed' in retry.stderr
    assert hashes(out) == saved
    spec_path.write_text('{', encoding='utf-8')
    rejected = tmp_path / 'invalid'
    command[-1] = str(rejected)
    failed = subprocess.run(command, cwd=repo, capture_output=True, text=True)
    assert failed.returncode == 2 and not rejected.exists()
    assert hashes(out) == saved


def test_failed_new_export_has_no_completion_manifest_and_keeps_prior_export(tmp_path, monkeypatch):
    from src.simulation import corruption_export
    values, profile, spec = trajectory(), example_profile(), {'schema_version': 1, 'events': []}
    prior = write_observations(tmp_path / 'prior', values, profile, spec)
    saved = hashes(prior)
    def fail(*args):
        raise OSError('injected write failure')
    monkeypatch.setattr(corruption_export, '_write_truth', fail)
    incomplete = tmp_path / 'incomplete'
    with pytest.raises(OSError, match='injected write failure'):
        write_observations(incomplete, values, profile, spec)
    assert not (incomplete / 'observed.synthetic.json').exists()
    assert hashes(prior) == saved


@pytest.mark.parametrize('fault', ['offset', 'noise'])
def test_arithmetic_overflow_cannot_create_an_undeclared_missing_export(tmp_path, fault):
    values = trajectory()
    if fault == 'offset':
        values['body_origin_mm'] = [[1e308, 200., 300.]] * 8
        event = {'kind': 'reconnect_jump', 'channel': 'physical_markers', 'start_index': 1,
                 'end_index_exclusive': 3, 'offset_mm': [1e308, 0., 0.]}
    else:
        event = {'kind': 'gaussian_noise', 'channel': 'physical_markers', 'start_index': 0,
                 'end_index_exclusive': 8, 'std_mm': 1e308}
    spec = {'schema_version': 1, 'events': [event]}
    target = tmp_path / 'overflow'
    with pytest.raises(ValueError, match='(?i)arithmetic|overflow|finite'):
        write_observations(target, values, example_profile(), spec, seed=1)
    assert not target.exists()
