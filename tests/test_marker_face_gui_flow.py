"""Production MainApp workflow driven by Qt events, without pipeline mocks."""
import time
from pathlib import Path
import numpy as np
import pandas as pd
from PySide6.QtCore import Qt, QTimer
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QFileDialog, QDialogButtonBox, QLineEdit
from marker_face_fixtures import DIMS, raw_bundle, write_raw
from src.analysis.app.main_window import MainApp
from src.analysis.ui.dialog_marker_flip_review import MarkerFlipReviewDialog
from src.analysis.pipeline.data_loader import DataLoader
from src.analysis.pipeline.artifact_io import read_corrected_source_metadata, read_slice_metadata
from src.config import config_app


def test_production_mainapp_face_review_save_and_process(tmp_path, monkeypatch):
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
    for edit, value in zip((raw_widget.le_box_l, raw_widget.le_box_w, raw_widget.le_box_h), DIMS):
        edit.setText(str(value))

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
            rows = [i for i, c in enumerate(dialog.candidates) if abs(c.boundary_time_sec - .3) < 1e-9]
            assert len(rows) == 1, [c.boundary_time_sec for c in dialog.candidates]
            row = rows[0]
            dialog._axis_combos[row].setCurrentIndex(dialog._axis_combos[row].findData('X'))
            QTest.mouseClick(dialog._approval_checkboxes[row], Qt.MouseButton.LeftButton)
            app.processEvents()
            # Local screenshots are opt-in and ignored by Git.
            evidence = Path('tmp/issue74_gui')
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
    assert raw_widget._read_box_dimensions() == tuple(DIMS)
    assert raw_widget.review_context_json == meta.context_json
    assert raw_widget.parsed_data.loc[.4, 'F1_FaceInfo'] == 'BACK'
    choose(sliced)
    QTest.mouseClick(raw_widget.save_slice_button, Qt.MouseButton.LeftButton)
    assert sliced.exists(), raw_widget.log_output.toPlainText()
    assert read_slice_metadata(str(sliced)).correction_context_json == meta.context_json
    window.tab_widget.setCurrentIndex(1)
    processing = window.processing_widget
    choose(sliced)
    QTest.mouseClick(processing.load_slice_button, Qt.MouseButton.LeftButton)
    assert processing.parsed_data.loc[.4, 'F1_FaceInfo'] == 'BACK'
    QTest.mouseClick(processing.run_button, Qt.MouseButton.LeftButton)
    wait_until(lambda: processing.save_proc_button.isEnabled())
    choose(processed)
    QTest.mouseClick(processing.save_proc_button, Qt.MouseButton.LeftButton)
    assert processed.exists()
    output = pd.read_csv(processed, header=[0, 1, 2], index_col=0)
    assert ('Info', 'MarkerCorrection', 'ContextJson') in output.columns
    window.grab().save('tmp/issue74_gui/processed.png')
    if raw_widget.review_worker:
        raw_widget.review_worker.wait()
    window.worker.wait()
    window.close()
