"""Production MainApp workflow driven by Qt events, without pipeline mocks."""
import time
from pathlib import Path
import numpy as np
import pandas as pd
import pytest
from scipy.spatial.transform import Rotation
from PySide6.QtCore import Qt, QTimer
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QFileDialog, QDialogButtonBox, QLineEdit
from marker_face_fixtures import DIMS, raw_bundle, write_raw, custom_public_profile
from src.analysis.app.main_window import MainApp
from src.analysis.ui.dialog_marker_flip_review import MarkerFlipReviewDialog
from src.analysis.pipeline.data_loader import DataLoader
from src.analysis.pipeline.artifact_io import read_corrected_source_metadata, read_slice_metadata
from src.config import config_app


@pytest.mark.parametrize('source_kind', ['handcrafted', 'mujoco', 'custom_mujoco', 'collision_face'])
def test_production_mainapp_face_review_save_and_process(tmp_path, monkeypatch, source_kind):
    # Production UI changes runtime geometry; isolate it from following tests.
    monkeypatch.setattr(config_app, 'BOX_DIMS', np.array(config_app.BOX_DIMS, copy=True))
    monkeypatch.setattr(config_app, 'LOCAL_BOX_CORNERS', np.array(config_app.LOCAL_BOX_CORNERS, copy=True))
    app = QApplication.instance() or QApplication([])
    app.setAttribute(Qt.ApplicationAttribute.AA_DontUseNativeDialogs, True)
    window = MainApp()
    window.show()
    QTest.qWait(100)
    raw_widget = window.original_widget
    h, raw, truth = raw_bundle(samples=100, boundary=30)
    source = tmp_path / 'asymmetric.csv'
    corrected = tmp_path / 'asymmetric.corrected.csv'
    sliced = tmp_path / 'scene.slice'
    processed = tmp_path / 'scene.proc'
    write_raw(source, h, raw)
    boundary_time = .3
    mujoco_truth = None
    dims = DIMS
    evidence = Path('tmp/issue74_gui') / source_kind
    evidence.mkdir(parents=True, exist_ok=True)
    if source_kind in ('mujoco', 'custom_mujoco', 'collision_face'):
        import json
        from src.simulation.marker_fixtures import write_case, load_profile
        profile = None
        if source_kind == 'custom_mujoco':
            profile_path = tmp_path / 'custom_profile.json'
            profile_path.write_text(json.dumps(custom_public_profile()), encoding='utf-8')
            profile = load_profile(profile_path)
            dims = tuple(profile['box_dims_mm'])
        if source_kind == 'collision_face':
            from src.simulation.marker_fixtures import virtual_profile_32
            profile = virtual_profile_32()
            dims = tuple(profile['box_dims_mm'])
        generated = write_case(tmp_path / 'independent', 'x', profile=profile,
                               motion='face' if source_kind == 'collision_face' else 'free_fall')
        source = generated / 'observed.csv'
        h, raw = DataLoader().load_csv(str(source))
        mujoco_truth = pd.read_csv(generated / 'truth_pose.csv')
        boundary_time = float(mujoco_truth.time_s.iloc[65 if source_kind == 'collision_face' else 30])
    original_bytes = source.read_bytes()
    errors = []

    def choose(path):
        def accept_file():
            dialog = app.activeModalWidget()
            if not isinstance(dialog, QFileDialog):
                errors.append('Expected actual QFileDialog')
                return
            dialog.selectFile(str(path))
            dialog.findChild(QLineEdit, 'fileNameEdit').setText(str(path))
            # Directory loading can reset the filename during the first event.
            def finish():
                dialog.findChild(QLineEdit, 'fileNameEdit').setText(str(path))
                dialog.accept()
            QTimer.singleShot(250, finish)
        QTimer.singleShot(250, accept_file)

    def wait_until(predicate, timeout=120):
        deadline = time.monotonic() + timeout
        while not predicate() and time.monotonic() < deadline:
            app.processEvents()
            # Release the Python GIL so the actual QThread optimizer can run.
            time.sleep(.01)
        assert predicate(), 'Timed out waiting for actual production workflow'
        assert not errors, errors

    choose(source)
    QTest.mouseClick(raw_widget.load_csv_button, Qt.MouseButton.LeftButton)
    assert raw_widget.raw_data is not None
    for edit, value in zip((raw_widget.le_box_l, raw_widget.le_box_w, raw_widget.le_box_h), dims):
        edit.setText(str(value))
    window.grab().save(str(evidence / 'before.png'))

    # Timer operates the real modal when the real background review completes.
    reviewed = []
    timer = QTimer()
    def approve():
        dialog = app.activeModalWidget()
        if not isinstance(dialog, MarkerFlipReviewDialog):
            return
        timer.stop()
        try:
            assert all(not c.isChecked() for c in dialog._approval_checkboxes)
            assert all(c.recommendation_axis is None for c in dialog.candidates)
            rows = [i for i, c in enumerate(dialog.candidates) if abs(c.boundary_time_sec - boundary_time) < 1e-9]
            assert len(rows) == 1, [c.boundary_time_sec for c in dialog.candidates]
            row = rows[0]
            dialog._axis_combos[row].setCurrentIndex(dialog._axis_combos[row].findData('X'))
            QTest.mouseClick(dialog._approval_checkboxes[row], Qt.MouseButton.LeftButton)
            app.processEvents()
            # Local screenshots are opt-in and ignored by Git.
            evidence = Path('tmp/issue74_gui') / source_kind
            evidence.mkdir(parents=True, exist_ok=True)
            dialog.grab().save(str(evidence / 'review.png'))
            reviewed.append(True)
            QTest.mouseClick(dialog.findChild(QDialogButtonBox).button(QDialogButtonBox.StandardButton.Ok), Qt.MouseButton.LeftButton)
        except Exception as exc:
            errors.append(str(exc))
            dialog.reject()
    timer.timeout.connect(approve)
    timer.start(100)
    QTest.mouseClick(raw_widget.review_marker_flips_button, Qt.MouseButton.LeftButton)
    assert not raw_widget.load_csv_button.isEnabled()
    wait_until(lambda: bool(reviewed) or bool(errors))
    assert raw_widget.marker_review_dirty
    assert not raw_widget.save_slice_button.isEnabled()
    choose(corrected)
    QTest.mouseClick(raw_widget.save_corrected_source_button, Qt.MouseButton.LeftButton)
    assert corrected.exists()
    assert not raw_widget.marker_review_dirty
    meta = read_corrected_source_metadata(str(corrected))
    assert meta.schema_version == '3' and meta.approved_event_count == 1
    assert source.read_bytes() == original_bytes
    _, loaded = DataLoader().load_csv(str(corrected))
    np.testing.assert_allclose(loaded.iloc[:, :raw.shape[1]].to_numpy(dtype=float), raw.to_numpy(dtype=float))
    # Reload must restore the approved geometry and context, not apply twice.
    raw_widget.le_box_l.setText('999')
    choose(corrected)
    QTest.mouseClick(raw_widget.load_csv_button, Qt.MouseButton.LeftButton)
    assert raw_widget._read_box_dimensions() == tuple(dims)
    assert raw_widget.review_context_json == meta.context_json
    assert raw_widget.parsed_data['F1_FaceInfo'].iloc[80] == 'BACK'
    window.grab().save(str(evidence / 'reloaded.png'))
    choose(sliced)
    QTest.mouseClick(raw_widget.save_slice_button, Qt.MouseButton.LeftButton)
    assert sliced.exists(), raw_widget.log_output.toPlainText()
    assert read_slice_metadata(str(sliced)).correction_context_json == meta.context_json
    window.tab_widget.setCurrentIndex(1)
    processing = window.processing_widget
    choose(sliced)
    QTest.mouseClick(processing.load_slice_button, Qt.MouseButton.LeftButton)
    assert processing.parsed_data['F1_FaceInfo'].iloc[80] == 'BACK'
    QTest.mouseClick(processing.run_button, Qt.MouseButton.LeftButton)
    wait_until(lambda: processing.save_proc_button.isEnabled())
    choose(processed)
    QTest.mouseClick(processing.save_proc_button, Qt.MouseButton.LeftButton)
    assert processed.exists()
    output = pd.read_csv(processed, header=[0, 1, 2], index_col=0)
    assert ('Info', 'MarkerCorrection', 'ContextJson') in output.columns
    if mujoco_truth is not None:
        np.testing.assert_allclose(output.index.to_numpy(dtype=float), mujoco_truth.time_s, atol=1e-10)
        positions = output[[('Position', 'CoM', 'P_T' + a) for a in 'XYZ']].to_numpy()
        rotvecs = output[[('Position', 'CoM', 'P_R' + a) for a in 'XYZ']].to_numpy()
        expected_positions = mujoco_truth[[f'body_{a}_mm' for a in 'xyz']].to_numpy()
        expected_rotations = mujoco_truth[[f'r{i}{j}' for i in range(3) for j in range(3)]].to_numpy().reshape(-1, 3, 3)
        position_error = np.linalg.norm(positions - expected_positions, axis=1).max()
        rotation_error = np.degrees((Rotation.from_matrix(expected_rotations).inv() * Rotation.from_rotvec(rotvecs)).magnitude()).max()
        assert position_error < .1
        assert rotation_error < .1
        print(f'MuJoCo GUI proc max error: {position_error} mm, {rotation_error} deg')
    window.grab().save(str(evidence / 'processed.png'))
    if source_kind == 'collision_face':
        import shutil
        for path in [source, corrected, sliced, processed, generated / 'truth_pose.csv',
                     generated / 'truth_markers.csv', generated / 'observed.synthetic.json']:
            shutil.copy2(path, evidence / path.name)
        (evidence / 'result.json').write_text(json.dumps({
            'input': str(source), 'expected': '100 samples, unchanged XYZ, manual X at 0.520 s, pose <0.1 mm/deg',
            'actual_samples': len(output), 'max_position_mm': float(position_error),
            'max_rotation_deg': float(rotation_error)}, indent=2), encoding='utf-8')
    if raw_widget.review_worker:
        raw_widget.review_worker.wait()
    window.worker.wait()
    window.close()


def test_reordered_annotations_rereview_off_on_and_suffix_pose(tmp_path, monkeypatch):
    import csv
    import json
    import shutil
    from src.simulation.marker_fixtures import write_case, virtual_profile_32
    from src.analysis.pipeline.face_assignment import materialize_face_assignments, face_columns
    from src.analysis.pipeline.marker_flip import MarkerCorrectionDecision
    from src.analysis.pipeline.artifact_io import save_corrected_source_file, save_slice_file, _sha256_file
    from src.analysis.pipeline.parser import Parser
    from src.config.data_columns import FACE_PREFIX_TO_INFO, SourceCols
    from PySide6.QtWidgets import QMessageBox

    started = time.monotonic()
    monkeypatch.setattr(config_app, 'BOX_DIMS', np.array(config_app.BOX_DIMS, copy=True))
    monkeypatch.setattr(config_app, 'LOCAL_BOX_CORNERS', np.array(config_app.LOCAL_BOX_CORNERS, copy=True))
    profile = virtual_profile_32()
    dims = tuple(profile['box_dims_mm'])
    generated = write_case(tmp_path / 'input', 'x', profile=profile, motion='face')
    original = generated / 'observed.csv'
    header, raw = DataLoader().load_csv(str(original))
    baseline = Parser(FACE_PREFIX_TO_INFO).process(header, raw)
    for column in baseline:
        if column.endswith('_FaceInfo'):
            baseline[column] = baseline[column].str.upper()
    base = {m['id']: m['face'] for m in profile['markers']}
    event = MarkerCorrectionDecision('independent-x', .520, True, 'X',
        correction_kind='face_assignment', algorithm_version='3.0', gate_version='face-validation-pending')
    context = json.dumps({'box_dims_mm': dims, 'base_faces': base,
        'coordinate_policy': 'global-y-up-box-xyz-mm', 'source_sha256': _sha256_file(str(original)),
        'export_metadata': header['export_metadata']})
    h, fixed = materialize_face_assignments(header, raw, [event], base)
    source = tmp_path / 'reordered.corrected.csv'
    save_corrected_source_file(filepath=str(source), header_info=h, raw_data=fixed,
        original_source_path=str(original), decisions=[event], context_json=context)
    # Valid schema: swap whole F1/R1 annotation columns, then interleave one
    # before the XYZ triplets. Header identity travels with each data column.
    annotations = face_columns(h)
    order = list(range(fixed.shape[1]))
    a, b = annotations['F1'], annotations['R1']
    order[a], order[b] = order[b], order[a]
    moved = order.pop(a)
    order.insert(2, moved)
    with source.open(newline='', encoding='utf-8') as stream:
        rows = list(csv.reader(stream))
    rows[2:] = [[row[i] for i in order] for row in rows[2:]]
    with source.open('w', newline='', encoding='utf-8') as stream:
        csv.writer(stream).writerows(rows)
    loaded_header, loaded_raw = DataLoader().load_csv(str(source))
    expected_active = Parser(FACE_PREFIX_TO_INFO).process(h, fixed)
    pd.testing.assert_frame_equal(Parser(FACE_PREFIX_TO_INFO).process(loaded_header, loaded_raw), expected_active)
    source_bytes, original_bytes = source.read_bytes(), original.read_bytes()
    evidence = Path('tmp/issue74_gui/reordered_annotations')
    evidence.mkdir(parents=True, exist_ok=True)
    app = QApplication.instance() or QApplication([])
    app.setAttribute(Qt.ApplicationAttribute.AA_DontUseNativeDialogs, True)
    window = MainApp()
    window.show()
    widget = window.original_widget
    errors = []
    error_watcher = QTimer()
    def capture_error_dialog():
        dialog = app.activeModalWidget()
        if isinstance(dialog, QMessageBox):
            errors.append(dialog.text())
            dialog.reject()
    error_watcher.timeout.connect(capture_error_dialog)
    error_watcher.start(100)
    def choose(path):
        def select():
            dialog = app.activeModalWidget()
            if not isinstance(dialog, QFileDialog):
                errors.append('Expected real file dialog')
                return
            dialog.selectFile(str(path))
            def accept():
                dialog.findChild(QLineEdit, 'fileNameEdit').setText(str(path))
                dialog.accept()
            QTimer.singleShot(250, accept)
        QTimer.singleShot(250, select)
    def wait_until(predicate):
        deadline = time.monotonic() + 150
        while not predicate() and not errors and time.monotonic() < deadline:
            app.processEvents()
            time.sleep(.01)
        assert not errors, errors
        assert predicate(), 'Actual re-review workflow did not finish'
    def reload(path):
        choose(path)
        QTest.mouseClick(widget.load_csv_button, Qt.MouseButton.LeftButton)
        assert Path(widget.source_path) == path
        pd.testing.assert_frame_equal(widget.review_parsed_data, baseline)
        # Review raw data and its own header remain a valid pair after load/save.
        pd.testing.assert_frame_equal(widget.parser.process(widget.review_header_info, widget.review_raw_data), baseline)
    def review(approved):
        finished = []
        timer = QTimer()
        def handle():
            dialog = app.activeModalWidget()
            if not isinstance(dialog, MarkerFlipReviewDialog):
                return
            timer.stop()
            try:
                rows = [i for i,c in enumerate(dialog.candidates) if abs(c.boundary_time_sec - .520) < 1e-9]
                assert len(rows) == 1
                i = rows[0]
                assert all(c.recommendation_axis is None for c in dialog.candidates)
                assert dialog.candidates[i].hypothesis('X').residual_deg < .1
                dialog._axis_combos[i].setCurrentIndex(dialog._axis_combos[i].findData('X'))
                if dialog._approval_checkboxes[i].isChecked() != approved:
                    QTest.mouseClick(dialog._approval_checkboxes[i], Qt.MouseButton.LeftButton)
                assert dialog._approval_checkboxes[i].isChecked() == approved
                dialog.grab().save(str(evidence / ('review_on.png' if approved else 'review_off.png')))
                QTest.mouseClick(dialog.findChild(QDialogButtonBox).button(QDialogButtonBox.StandardButton.Ok), Qt.MouseButton.LeftButton)
                finished.append(True)
            except Exception as exc:
                errors.append(str(exc))
                dialog.reject()
        timer.timeout.connect(handle)
        timer.start(100)
        QTest.mouseClick(widget.review_marker_flips_button, Qt.MouseButton.LeftButton)
        wait_until(lambda: bool(finished))
        timer.stop()
    try:
        reload(source)
        pd.testing.assert_frame_equal(widget.parsed_data, expected_active)
        outputs = []
        for approved in (False, True):
            review(approved)
            assert widget.marker_review_dirty
            target = tmp_path / ('on.csv' if approved else 'off.csv')
            choose(target)
            QTest.mouseClick(widget.save_corrected_source_button, Qt.MouseButton.LeftButton)
            assert target.exists(), widget.log_output.toPlainText()
            reload(target)
            pd.testing.assert_frame_equal(widget.parsed_data, expected_active if approved else baseline)
            assert read_corrected_source_metadata(str(target)).approved_event_count == int(approved)
            outputs.append(target)
        suffix = tmp_path / 'suffix.slice'
        final_time = float(baseline.index[-1])
        save_slice_file(filepath=str(suffix), header_info=widget.header_info, raw_data=widget.raw_data,
            source_path=widget.source_path, full_start=0., full_end=final_time, user_start=.56, user_end=final_time,
            pad_rows=0, box_dims=dims, marker_correction_metadata=widget.correction_source_metadata)
        window.tab_widget.setCurrentIndex(1)
        processing = window.processing_widget
        choose(suffix)
        QTest.mouseClick(processing.load_slice_button, Qt.MouseButton.LeftButton)
        expected_suffix = expected_active.loc[expected_active.index >= .56-1e-12]
        pd.testing.assert_frame_equal(processing.parsed_data, expected_suffix)
        assert processing.parsed_data.index.min() > .520
        # A 30-row suffix is readable but below the full pipeline's 50-row
        # minimum. Keep that gate; verify its actual parsed pose separately.
        from src.analysis.pipeline.pose_optimizer import PoseOptimizer
        from src.analysis.pipeline.face_assignment import POSE_COLUMNS
        output = PoseOptimizer(config_app.FACE_DEFINITIONS,
            config_app.calculate_local_box_corners(dims)).process(processing.parsed_data, dims)
        assert len(output) == 30
        assert output[SourceCols.POSE].eq('Optimized').all()
        target = tmp_path / 'suffix_pose.csv'
        output.to_csv(target)
        truth = pd.read_csv(generated / 'truth_pose.csv')
        truth = truth.loc[truth.time_s >= .56-1e-12]
        np.testing.assert_allclose(output.index.to_numpy(dtype=float),truth.time_s,atol=1e-10)
        positions = output[list(POSE_COLUMNS[:3])].to_numpy()
        rotvecs = output[list(POSE_COLUMNS[3:])].to_numpy()
        expected_positions = truth[[f'body_{a}_mm' for a in 'xyz']].to_numpy()
        rotations = truth[[f'r{i}{j}' for i in range(3) for j in range(3)]].to_numpy().reshape(-1,3,3)
        pe = np.linalg.norm(positions-expected_positions,axis=1).max()
        re = np.degrees((Rotation.from_matrix(rotations).inv()*Rotation.from_rotvec(rotvecs)).magnitude()).max()
        assert pe < .1 and re < .1
        assert source.read_bytes() == source_bytes and original.read_bytes() == original_bytes
        window.grab().save(str(evidence / 'suffix_loaded.png'))
        for path in [source, original, *outputs, suffix, target, generated/'truth_pose.csv']:
            shutil.copy2(path, evidence/path.name)
        result = {'samples':len(output),'valid_pose_samples':int(output[SourceCols.POSE].eq('Optimized').sum()),
                  'max_position_mm':float(pe),'max_rotation_deg':float(re),
                  'seconds':time.monotonic()-started,'original_bytes_preserved':True,
                  'expected':'ID-based faces/XYZ preserved through reordered load, real OFF/ON re-review, resave, suffix load and direct pose fit; errors <0.1 mm/deg'}
        (evidence/'result.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
        print(result)
    finally:
        error_watcher.stop()
        if widget.review_worker:
            widget.review_worker.wait()
        if getattr(window, "worker", None):
            window.worker.wait()
        window.close()
