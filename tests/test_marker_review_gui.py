"""Actual Qt/Matplotlib review at the release viewport, with real SciPy cancellation."""
import hashlib
import json
import os
from pathlib import Path
import platform
import threading
import time

import pytest
from PySide6.QtCore import Qt, QTimer
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QFileDialog, QDialogButtonBox, QMessageBox

from marker_face_fixtures import raw_bundle, write_raw, DIMS, LAYOUT, BASE_FACES
from src.analysis.app.main_window import MainApp
from src.analysis.ui.dialog_marker_flip_review import MarkerFlipReviewDialog
from src.analysis.pipeline.artifact_io import read_corrected_source_metadata


@pytest.mark.skipif(os.environ.get('QT_SCALE_FACTOR') != '1.25', reason='Run separately with QT_SCALE_FACTOR=1.25')
def test_actual_review_cancel_save_and_close_at_125_percent(monkeypatch):
    import numpy
    import scipy
    import PySide6
    from src.analysis.ui import widget_raw_data_processing as module
    root = (Path('tmp/issue112/gui') / f'run-{time.time_ns()}').resolve()
    root.mkdir(parents=True, exist_ok=True)
    source = root / ('public_observation_' * 5 + '.csv')
    corrected = root / 'review.corrected.csv'
    h, raw, _ = raw_bundle(samples=32, boundary=16)
    write_raw(source, h, raw)
    original = source.read_bytes()
    app = QApplication.instance() or QApplication([])
    window = MainApp()
    window.resize(1510, 800)
    window.show()
    w = window.original_widget
    errors, measurements, timers = [], [], []
    monkeypatch.setattr(QMessageBox, 'warning', lambda *a: errors.append(str(a[-1])))
    monkeypatch.setattr(QMessageBox, 'information', lambda *a: None)

    # Hold only the first real SciPy objective evaluation for each cancellation
    # trial. Otherwise a fast worker can open its modal between the progress
    # check and the Cancel click, turning a timing race into an infinite wait.
    from src.analysis.pipeline import pose_optimizer
    real_objective = pose_optimizer._objective_function
    active_gate, gates, expired = [None], [], []
    def gated_objective(*args, **kwargs):
        value = real_objective(*args, **kwargs)
        gate = active_gate[0]
        if gate is not None:
            active_gate[0] = None
            entered, release = gate
            entered.set()
            if not release.wait(15):
                raise AssertionError('GUI did not release the real objective evaluation')
        return value
    monkeypatch.setattr(pose_optimizer, '_objective_function', gated_objective)
    def hold_real_fit():
        entered, release = threading.Event(), threading.Event()
        gates.append(release)
        active_gate[0] = (entered, release)
        return entered, release

    def expire():
        modal = app.activeModalWidget()
        detail = {'status': 'timeout', 'modal': type(modal).__name__ if modal else None,
                  'review_state': w.marker_review_summary_label.text(),
                  'log': w.log_output.toPlainText()}
        expired.append(detail)
        try:
            (root / 'timeout.json').write_text(json.dumps(detail, indent=2), encoding='utf-8')
            window.grab().save(str(root / 'timeout.png'))
        finally:
            w.cancel_marker_review()
            for release in gates:
                release.set()
            if modal is not None:
                modal.reject()

    # Keep a guard alive outside wait(), too: any processEvents/QTest call may
    # enter a nested modal event loop. A timeout always fails this test.
    whole_test_guard = QTimer(window)
    whole_test_guard.setSingleShot(True)
    whole_test_guard.timeout.connect(expire)
    whole_test_guard.start(90000)

    def wait(predicate, timeout=40):
        deadline = time.monotonic() + timeout
        watchdog = QTimer(window)
        watchdog.setSingleShot(True)
        watchdog.timeout.connect(expire)
        watchdog.start(int(timeout * 1000))
        try:
            while not predicate() and not expired and time.monotonic() < deadline:
                app.processEvents()
                time.sleep(.002)
        finally:
            watchdog.stop()
            watchdog.deleteLater()
        assert not expired, expired
        assert predicate(), w.log_output.toPlainText()

    def reachable(button, host):
        app.processEvents()
        center = button.rect().center()
        pos = button.mapTo(host, center)
        assert button.isVisible() and host.rect().contains(pos)
        found = host.childAt(pos)
        assert found is button or button.isAncestorOf(found), button.text()

    def open_source(path):
        monkeypatch.setattr(QFileDialog, 'getOpenFileName', lambda *a: (str(path), ''))
        QTest.mouseClick(w.load_csv_button, Qt.MouseButton.LeftButton)

    try:
        open_source(source)
        for edit, value in zip((w.le_box_l, w.le_box_w, w.le_box_h), DIMS):
            edit.setText(str(value))
        w.marker_review_section.setExpanded(True)
        QTest.qWait(100)
        assert (window.width(), window.height()) == (1510, 800)
        assert window.devicePixelRatioF() == 1.25
        assert not w.review_marker_flips_button.isEnabled()
        reachable(w.confirm_review_dimensions, window)
        QTest.mouseClick(w.confirm_review_dimensions, Qt.MouseButton.LeftButton)
        reachable(w.review_marker_flips_button, window)
        window.grab().save(str(root / 'dimensions.png'))

        for trial in range(3):
            entered, release = hold_real_fit()
            QTest.mouseClick(w.review_marker_flips_button, Qt.MouseButton.LeftButton)
            wait(entered.is_set)
            assert w.review_worker.isRunning()
            reachable(w.cancel_marker_review_button, window)
            if trial == 0:
                window.grab().save(str(root / 'calculating.png'))
            start = time.perf_counter()
            QTest.mouseClick(w.cancel_marker_review_button, Qt.MouseButton.LeftButton)
            release.set()
            wait(lambda: w.review_worker is None)
            measurements.append(time.perf_counter() - start)
            assert w.review_marker_flips_button.isEnabled()
            assert w.marker_correction_decisions == []
            assert source.read_bytes() == original
        window.grab().save(str(root / 'cancelled.png'))

        approved = []
        timer = QTimer()
        timers.append(timer)
        def approve():
            dialog = app.activeModalWidget()
            if not isinstance(dialog, MarkerFlipReviewDialog):
                return
            timer.stop()
            try:
                assert len(dialog.candidates) == 1
                assert dialog.candidates[0].boundary_time_sec == .16
                assert dialog.candidates[0].recommendation_axis == 'X'
                box = dialog._approval_checkboxes[0]
                axis = dialog._axis_combos[0]
                assert not box.isChecked()
                axis.setCurrentIndex(axis.findData('Y'))
                assert not box.isChecked()
                axis.setCurrentIndex(axis.findData('X'))
                reachable(box, dialog)
                done = dialog.button_box.button(QDialogButtonBox.StandardButton.Ok)
                cancel = dialog.button_box.button(QDialogButtonBox.StandardButton.Cancel)
                reachable(done, dialog)
                reachable(cancel, dialog)
                dialog.grab().save(str(root / 'approval.png'))
                QTest.mouseClick(box, Qt.MouseButton.LeftButton)
                QTest.mouseClick(done, Qt.MouseButton.LeftButton)
                approved.append(True)
            except Exception as error:
                errors.append(str(error))
                dialog.reject()
        timer.timeout.connect(approve)
        timer.start(10)
        QTest.mouseClick(w.review_marker_flips_button, Qt.MouseButton.LeftButton)
        wait(lambda: (bool(approved) and w.review_worker is None) or bool(errors))
        assert not errors
        assert w.marker_review_dirty
        history = list(w.marker_correction_decisions)
        source_path = w.source_path
        reachable(w.save_corrected_source_button, window)
        monkeypatch.setattr(QFileDialog, 'getSaveFileName', lambda *a: ('', ''))
        QTest.mouseClick(w.save_corrected_source_button, Qt.MouseButton.LeftButton)
        assert w.marker_correction_decisions == history and w.source_path == source_path
        monkeypatch.setattr(QFileDialog, 'getSaveFileName', lambda *a: (str(corrected), ''))
        save = module.save_corrected_source_file
        def fail(**kwargs):
            raise OSError('Injected write failure')
        monkeypatch.setattr(module, 'save_corrected_source_file', fail)
        QTest.mouseClick(w.save_corrected_source_button, Qt.MouseButton.LeftButton)
        assert errors == ['Injected write failure']
        errors.clear()
        assert w.marker_correction_decisions == history and w.source_path == source_path
        monkeypatch.setattr(module, 'save_corrected_source_file', save)
        QTest.mouseClick(w.save_corrected_source_button, Qt.MouseButton.LeftButton)
        assert w.source_path == str(corrected) and not w.marker_review_dirty
        assert read_corrected_source_metadata(str(corrected)).approved_event_count == 1
        assert source.read_bytes() == original
        # Same numerical geometry must work directly after save, without reload,
        # even if input formatting changes from integer text to float text.
        assert w.marker_flip_candidates
        for edit, value in zip((w.le_box_l, w.le_box_w, w.le_box_h), DIMS):
            edit.setText(str(int(value)))
        geometry = root / 'public-geometry.json'
        geometry.write_text(json.dumps({'version': 1, 'profile': {'units': 'mm',
            'origin': 'box-geometric-center', 'box_dims_mm': list(DIMS),
            'markers': [{'id': mid, 'xyz_mm': list(point), 'face': BASE_FACES[mid]}
                        for mid, point in LAYOUT.items()]}}), encoding='utf-8')
        monkeypatch.setattr(QFileDialog, 'getOpenFileName', lambda *a: (str(geometry), ''))
        w.load_scene_geometry()
        assert not w._review_invalidated
        assert w.scene_panel.detect_button.isEnabled()
        open_source(corrected)
        assert w._read_box_dimensions() == DIMS
        assert w.parsed_data.loc[.2, 'F1_FaceInfo'] == 'BACK'
        window.grab().save(str(root / 'saved-reopened.png'))

        w.confirm_review_dimensions.setChecked(True)
        entered, release = hold_real_fit()
        QTest.mouseClick(w.review_marker_flips_button, Qt.MouseButton.LeftButton)
        wait(entered.is_set)
        assert not window.close()
        release.set()
        wait(lambda: w.review_worker is None and not window.isVisible())
        assert source.read_bytes() == original
        assert not expired, expired
        report = {'status': 'pass', 'scope': 'actual Qt controls / real SciPy cancellation with a held objective evaluation; synthetic only',
            'logical_size': [1510, 800], 'measured_dpr': 1.25,
            'source_sha256': hashlib.sha256(original).hexdigest(),
            'cancellation_seconds': measurements, 'maximum_cancellation_seconds': max(measurements),
            'configuration': {'python': platform.python_version(), 'os': platform.system(),
                'machine_architecture': platform.machine(), 'numpy': numpy.__version__,
                'scipy': scipy.__version__, 'qt': PySide6.__version__, 'window_samples': 5,
                'max_iterations': 1500, 'markers': 18, 'frames': 32},
            'checks': ['explicit_dimensions', 'reachable_buttons', 'three_real_cancellations',
                'preview_not_approval', 'save_cancel', 'save_failure', 'save_retry', 'reopen', 'close'],
            'review_statistics': w.last_review_statistics}
        (root / 'execution.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    finally:
        for release in gates:
            release.set()
        for timer in timers:
            timer.stop()
        if w.review_worker is not None:
            w.cancel_marker_review()
            wait(lambda: w.review_worker is None)
        window.close()
        whole_test_guard.stop()
        window.deleteLater()
        app.processEvents()
