"""General public exporter through the real, observed-only correction workflow.

Level 2 synthetic integration, not calibrated tracking accuracy. The evaluator
owns trajectories/events; analysis receives only observations and box geometry.
"""
import builtins
import csv
import hashlib
import io
import json
import os
from contextlib import contextmanager
from dataclasses import asdict
from pathlib import Path
import platform
import subprocess

import numpy as np
import pandas as pd
import pytest
import scipy
from scipy.spatial.transform import Rotation
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from src.analysis.pipeline.artifact_io import (
    read_corrected_source_metadata, read_slice_metadata,
    save_corrected_source_file, save_slice_file,
)
from src.analysis.pipeline.data_loader import DataLoader
from src.analysis.pipeline.face_assignment import face_columns, materialize_face_assignments, POSE_COLUMNS
from src.analysis.pipeline.marker_review import review_observations
from src.analysis.pipeline.parser import Parser
from src.analysis.pipeline.pipeline_controller import PipelineController
from src.analysis.ui.dialog_marker_flip_review import MarkerFlipReviewDialog
from src.config import config_app
from src.config.config_analysis_ui import get_raw_mode_options
from src.config.data_columns import FACE_PREFIX_TO_INFO, SourceCols
from src.simulation.corruption_export import write_observations
from src.simulation.marker_fixtures import example_profile


CASES = ('healthy', 'genuine', 'missing', 'partial_missing', 'held_reconnect', 'X', 'Y', 'Z',
         'XX', 'XY', 'YX', 'gap_X', 'low_coverage', 'physical_only')
SEED = 74082
# Existing noise-free public pose bound; 0.1 mm is 1/800 of the shortest
# dimension, 0.1 degree moves a corner by at most 0.216 mm at this geometry.
# It is an acceptance bound, not a measured camera accuracy or a detector gate.
POSITION_MM = .1
ROTATION_DEG = .1


def specified_input(case):
    count = 72
    times = np.arange(count) * .01
    origins = np.column_stack((17 + 20 * times, 200 - 5 * times, 11 + 3 * times))
    angles = np.linspace(0, np.pi, count) if case == 'genuine' else np.zeros(count)
    # Literal analytic local-Z rotation, independent of the generator/optimizer.
    rotations = np.zeros((count, 3, 3))
    rotations[:, 0, 0] = rotations[:, 1, 1] = np.cos(angles)
    rotations[:, 1, 0] = np.sin(angles)
    rotations[:, 0, 1] = -np.sin(angles)
    rotations[:, 2, 2] = 1
    trajectory = dict(schema_version=1, source_kind='handcrafted_dummy',
        coordinate_policy='world-y-up-box-local-fixed-center-v1',
        frame=(100 + np.arange(count) * 2).tolist(), time_s=times.tolist(),
        body_origin_mm=origins.tolist(), rotation_matrix=rotations.tolist())
    axes = {'X': 'X', 'Y': 'Y', 'Z': 'Z', 'XX': 'XX', 'XY': 'XY',
            'YX': 'YX', 'gap_X': 'X'}.get(case, '')
    events = [dict(kind='flip_180_local_axis', channel='rigid_body_markers',
                   start_index=row, axis=axis) for row, axis in zip((20, 48), axes)]
    if case in ('missing', 'gap_X'):
        events.append(dict(kind='missing', channel='rigid_body_markers',
                           start_index=18, end_index_exclusive=20))
    if case == 'partial_missing':
        events.append(dict(kind='missing', channel='rigid_body_markers', start_index=18,
                           end_index_exclusive=23, marker_ids=['F1']))
    if case == 'held_reconnect':
        events.extend([
            dict(kind='freeze', channel='rigid_body_markers', start_index=18, end_index_exclusive=23),
            dict(kind='reconnect_jump', channel='rigid_body_markers', start_index=23,
                 end_index_exclusive=27, offset_mm=[7., -3., 4.])])
    if case == 'low_coverage':
        missing = [m['id'] for m in example_profile()['markers'] if m['id'] not in ('F1', 'R1')]
        events.append(dict(kind='missing', channel='rigid_body_markers', start_index=0,
                           end_index_exclusive=count, marker_ids=missing))
    if case == 'physical_only':
        events.extend([
            dict(kind='missing', channel='physical_markers', start_index=18, end_index_exclusive=23),
            dict(kind='label_permutation', channel='physical_markers', start_index=23,
                 end_index_exclusive=count, mapping={'F1': 'B1', 'B1': 'F1'})])
    return trajectory, dict(schema_version=1, events=events), axes


@contextmanager
def observed_only(monkeypatch, root):
    """Fail all Python file-open routes for evaluator artifacts during analysis."""
    forbidden = {p.resolve() for p in root.iterdir() if p.name != 'observed.csv'}
    def wrap(original):
        def checked(file, *args, **kwargs):
            if isinstance(file, (str, bytes, os.PathLike)):
                path = Path(os.fsdecode(file)).resolve()
                if path in forbidden:
                    raise AssertionError('Analysis read evaluator artifact: ' + path.name)
            return original(file, *args, **kwargs)
        return checked
    with monkeypatch.context() as guard:
        for module, name in ((builtins, 'open'), (io, 'open'), (os, 'open')):
            guard.setattr(module, name, wrap(getattr(module, name)))
        # Prove that pathlib, pandas and low-level opens cannot bypass the guard.
        for access in (lambda: (root / 'truth_pose.csv').read_bytes(),
                       lambda: pd.read_csv(root / 'truth_pose.csv'),
                       lambda: os.open(root / 'observed.synthetic.json', os.O_RDONLY)):
            with pytest.raises(AssertionError, match='evaluator artifact'):
                access()
        yield


def file_hashes(root):
    return {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in root.iterdir() if p.is_file()}


def operator_choices(candidates, choices):
    """Use production widgets; choices are explicit test/operator actions."""
    app = QApplication.instance() or QApplication([])
    dialog = MarkerFlipReviewDialog(candidates)
    try:
        dialog.show()
        app.processEvents()
        assert all(not d.approved for d in dialog.get_decisions())
        selected = set()
        for row, candidate in enumerate(candidates):
            time = round(candidate.boundary_time_sec, 8)
            if time not in choices:
                continue
            combo = dialog.axis_combo(row)
            combo.setCurrentIndex(combo.findData(choices[time]))
            assert not dialog.approval_checkbox(row).isChecked()
            QTest.mouseClick(dialog.approval_checkbox(row), Qt.MouseButton.LeftButton)
            selected.add(time)
        assert selected == set(choices)
        return dialog.get_decisions()
    finally:
        dialog.close()
        app.processEvents()


def persist_and_process(root, output, header, raw, decisions, profile):
    dims = tuple(profile['box_dims_mm'])
    base_faces = {m['id']: m['face'] for m in profile['markers']}
    fixed_header, fixed = materialize_face_assignments(header, raw, decisions, base_faces)
    pd.testing.assert_frame_equal(fixed.iloc[:, :raw.shape[1]], raw)
    for key in ('id', 'name', 'type', 'parent', 'category', 'component'):
        assert fixed_header[key][:raw.shape[1]] == header[key]
    context = json.dumps(dict(box_dims_mm=dims, base_faces=base_faces,
        coordinate_policy='global-y-up-box-xyz-mm',
        source_sha256=hashlib.sha256((root / 'observed.csv').read_bytes()).hexdigest(),
        export_metadata=header['export_metadata']))
    output.mkdir()
    corrected = output / 'corrected.csv'
    metadata = save_corrected_source_file(filepath=str(corrected), header_info=fixed_header,
        raw_data=fixed, original_source_path=str(root / 'observed.csv'),
        decisions=decisions, context_json=context)
    assert read_corrected_source_metadata(str(corrected)) == metadata
    reopened_header, reopened = DataLoader().load_csv(str(corrected))
    # All physical and solved coordinates, frame/time and IDs survive disk I/O.
    np.testing.assert_allclose(reopened.iloc[:, :raw.shape[1]].apply(pd.to_numeric).to_numpy(),
                               raw.apply(pd.to_numeric).to_numpy(), rtol=0, atol=1e-12, equal_nan=True)
    for mid, column in face_columns(fixed_header).items():
        np.testing.assert_array_equal(reopened.iloc[:, column], fixed.iloc[:, column])
    sliced = output / 'selection.slice'
    save_slice_file(filepath=str(sliced), header_info=reopened_header, raw_data=reopened,
        source_path=str(corrected), full_start=0., full_end=.71, user_start=.12,
        user_end=.55, pad_rows=50, box_dims=dims, marker_correction_metadata=metadata)
    slice_meta = read_slice_metadata(str(sliced))
    assert slice_meta.correction_context_json == metadata.context_json
    sh, sr = DataLoader().load_csv(str(sliced))
    parsed = Parser(FACE_PREFIX_TO_INFO).process(sh, sr)
    result = PipelineController().process_parsed_data(dict(box_dimensions=dims,
        processing_mode='raw', slice_filter_by='time', slice_start_val=slice_meta.user_start,
        slice_end_val=slice_meta.user_end, enable_result_resampling=False,
        analysis_options=get_raw_mode_options()), parsed)
    np.testing.assert_allclose(result.index, np.arange(12, 56) * .01, rtol=0, atol=1e-12)
    np.testing.assert_array_equal(pd.to_numeric(result['Frame']), 100 + 2 * np.arange(12, 56))
    return result, corrected, fixed_header, fixed


@pytest.mark.parametrize('case', CASES)
def test_general_export_review_roundtrip_and_actual_reprocessing(tmp_path, monkeypatch, case, request):
    monkeypatch.setattr(config_app, 'BOX_DIMS', config_app.BOX_DIMS.copy())
    monkeypatch.setattr(config_app, 'LOCAL_BOX_CORNERS', config_app.LOCAL_BOX_CORNERS.copy())
    trajectory, spec, axes = specified_input(case)
    profile = example_profile()
    root = write_observations(tmp_path / 'input', trajectory, profile, spec, SEED)
    before = file_hashes(root)
    # Predetermined operator instruction; never derive approvals from a recommendation.
    choices = {time: axis for time, axis in zip((.20, .48), axes)}
    report = dict(case=case, seed=SEED, evidence='Level 2 synthetic integration',
        revision=subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
        command='python -m pytest -q ' + request.node.nodeid,
        python=platform.python_version(), numpy=np.__version__, scipy=scipy.__version__,
        input_sha256=before, position_bound_mm=POSITION_MM, rotation_bound_deg=ROTATION_DEG,
        status='fail')
    try:
        with observed_only(monkeypatch, root):
            header, raw = DataLoader().load_csv(str(root / 'observed.csv'))
            parsed = Parser(FACE_PREFIX_TO_INFO).process(header, raw)
            review = review_observations(parsed, profile['box_dims_mm'])
            candidates = review['candidates']
            report['recommendations'] = [dict(time=c.boundary_time_sec, axis=c.recommendation_axis,
                                             reason=c.reason) for c in candidates]
            report['fits'] = review['statistics']['nonlinear_fits']
            if case in ('X', 'Y', 'Z', 'XX', 'XY', 'YX'):
                assert [(round(c.boundary_time_sec, 8), c.recommendation_axis) for c in candidates] == list(choices.items())
            else:
                assert all(c.recommendation_axis is None for c in candidates)
            if case in ('healthy', 'genuine', 'physical_only'):
                assert candidates == []
            decisions = operator_choices(candidates, choices)
            report['operator_actions'] = [asdict(d) for d in decisions]
            result, corrected, fh, fixed = persist_and_process(root, tmp_path / 'approved',
                header, raw, decisions, profile)
            report['persistence'] = 'XYZ/IDs, all decisions and cumulative faces preserved'
            # Literal chronological face oracle, independent of production FACE_MAPS.
            if axes:
                front = fixed.iloc[:, face_columns(fh)['F1']]
                right = fixed.iloc[:, face_columns(fh)['R1']]
                assert (front.iloc[19], right.iloc[19]) == ('FRONT', 'RIGHT')
                expected_first = {'X': ('BACK', 'RIGHT'), 'Y': ('BACK', 'LEFT'), 'Z': ('FRONT', 'LEFT')}
                assert (front.iloc[20], right.iloc[20]) == expected_first[axes[0]]
                if len(axes) == 2:
                    assert (front.iloc[48], right.iloc[48]) == (('FRONT', 'RIGHT') if axes == 'XX' else ('FRONT', 'LEFT'))
            if case == 'X':
                assert_tamper_rejected(corrected, fh)
            if case == 'XY':
                # First event only and an intentionally changed axis stay distinct
                # from automatic recommendation, survive I/O and leave wrong poses.
                variants = {}
                for name, selected in (('subset', {.20: 'X'}), ('changed_axis', {.20: 'Y', .48: 'Y'})):
                    chosen = operator_choices(candidates, selected)
                    variants[name] = persist_and_process(root, tmp_path / name, header, raw, chosen, profile)[0]
        # Evaluation begins only after all production review, writes and fits finish.
        truth = pd.read_csv(root / 'truth_pose.csv')
        manifest = json.loads((root / 'observed.synthetic.json').read_text(encoding='utf-8'))
        report['generator_version'] = manifest['generator_version']
        report['generator_source_sha256'] = manifest['source_sha256']
        np.testing.assert_allclose(truth[[f'body_{a}_mm' for a in 'xyz']], trajectory['body_origin_mm'], rtol=0, atol=1e-12)
        np.testing.assert_allclose(truth[[f'r{i}{j}' for i in range(3) for j in range(3)]],
                                   np.asarray(trajectory['rotation_matrix']).reshape(-1, 9), rtol=0, atol=1e-12)
        expected = truth.iloc[12:56]
        actual = result[list(POSE_COLUMNS)].to_numpy(float)
        valid = np.isfinite(actual).all(axis=1)
        if case == 'low_coverage':
            assert not valid.any()
        else:
            expected_valid = np.ones(44, dtype=bool)
            if case in ('missing', 'gap_X'):
                expected_valid[6:8] = False
            np.testing.assert_array_equal(valid, expected_valid)
            assert result.loc[valid, SourceCols.POSE].eq('Optimized').all()
            compare = valid.copy()
            expected_pos = expected[[f'body_{a}_mm' for a in 'xyz']].to_numpy()
            expected_rot = expected[[f'r{i}{j}' for i in range(3) for j in range(3)]].to_numpy().reshape(-1, 3, 3)
            if case == 'held_reconnect':
                # Check the specified observation model, without claiming recovery
                # of the physical movement hidden by the frozen/offset samples.
                expected_pos[6:11] = trajectory['body_origin_mm'][17]
                expected_pos[11:15] += [7., -3., 4.]
                report['recovery_scope'] = 'held and offset observed poses; hidden physical motion unrecovered'
            pos_error = np.linalg.norm(actual[compare, :3] - expected_pos[compare], axis=1)
            rot_error = np.degrees((Rotation.from_matrix(expected_rot[compare]).inv()
                                   * Rotation.from_rotvec(actual[compare, 3:])).magnitude())
            report['recovery'] = dict(evaluated_samples=int(compare.sum()),
                max_position_mm=float(pos_error.max()), max_rotation_deg=float(rot_error.max()),
                unavailable_samples=int((~valid).sum()))
            assert pos_error.max() < POSITION_MM
            assert rot_error.max() < ROTATION_DEG
            if case == 'XY':
                for name, variant in variants.items():
                    errors = np.degrees(Rotation.from_rotvec(variant[list(POSE_COLUMNS)[3:]].to_numpy()).magnitude())
                    # subset leaves the second Y uncorrected; changing X to Y is wrong from .20.
                    start = 36 if name == 'subset' else 8
                    assert np.all(errors[start:] > 179.9)
                    report[name + '_min_error_deg'] = float(errors[start:].min())
        assert file_hashes(root) == before
        report['status'] = 'pass'
    finally:
        report['input_sha256_after'] = file_hashes(root)
        evidence = Path('tmp/issue115')
        evidence.mkdir(parents=True, exist_ok=True)
        (evidence / (case + '.json')).write_text(json.dumps(report, indent=2), encoding='utf-8')


def assert_tamper_rejected(corrected, header):
    with corrected.open(newline='', encoding='utf-8') as stream:
        original = list(csv.reader(stream))
    for damage in ('face', 'coordinate_policy', 'history'):
        rows = [row.copy() for row in original]
        if damage == 'face':
            rows[-1][face_columns(header)['F1']] = 'FRONT'
            message = 'disagrees'
        else:
            key = 'correction_context' if damage == 'coordinate_policy' else 'correction_events'
            index = next(i for i, cell in enumerate(rows[1]) if cell.startswith(key + '='))
            value = json.loads(rows[1][index].split('=', 1)[1])
            if damage == 'coordinate_policy':
                value['coordinate_policy'] = 'world-z-up'
                message = 'Invalid face correction context'
            else:
                value[0]['axis'] = 'Y'
                message = 'disagrees'
            rows[1][index] = key + '=' + json.dumps(value)
        target = corrected.with_name(damage + '.csv')
        with target.open('w', newline='', encoding='utf-8') as stream:
            csv.writer(stream).writerows(rows)
        with pytest.raises(ValueError, match=message):
            DataLoader().load_csv(str(target))


def test_identical_solved_observations_do_not_identify_the_physical_cause(tmp_path, monkeypatch):
    import copy
    trajectory, spec, _ = specified_input('X')
    physical_turn = copy.deepcopy(trajectory)
    physical_turn['rotation_matrix'][20:] = [np.diag([1., -1., -1.]).tolist()] * 52
    profile = example_profile()
    faulty = write_observations(tmp_path / 'solver_fault', trajectory, profile, spec)
    real_turn = write_observations(tmp_path / 'physical_turn', physical_turn, profile,
                                   dict(schema_version=1, events=[]))
    with observed_only(monkeypatch, faulty), observed_only(monkeypatch, real_turn):
        first = Parser(FACE_PREFIX_TO_INFO).process(*DataLoader().load_csv(str(faulty / 'observed.csv')))
        second = Parser(FACE_PREFIX_TO_INFO).process(*DataLoader().load_csv(str(real_turn / 'observed.csv')))
        pd.testing.assert_frame_equal(first, second)
        candidates = review_observations(first, profile['box_dims_mm'])['candidates']
        assert [(c.boundary_time_sec, c.recommendation_axis) for c in candidates] == [(.20, 'X')]
        assert all(not d.approved for d in operator_choices(candidates, {}))
    # A continuity recommendation is identical for these two incompatible
    # physical narratives. Only the evaluator knows which motion was specified.
    assert trajectory['rotation_matrix'][30] != physical_turn['rotation_matrix'][30]
