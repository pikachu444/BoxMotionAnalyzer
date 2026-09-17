"""Read-only event context and real modal source/approval boundaries."""
import csv
import builtins
import hashlib
import io
import json
from pathlib import Path
import time

import numpy as np
import pandas as pd
import pytest
from PySide6.QtCore import Qt, QTimer, QPoint
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QDialogButtonBox, QFileDialog, QMessageBox

from src.analysis.app.main_window import MainApp
from src.analysis.ui.dialog_marker_flip_review import MarkerFlipReviewDialog
from src.analysis.pipeline.artifact_io import read_corrected_source_metadata
from src.simulation.corruption_export import write_observations
from src.simulation.marker_fixtures import example_profile
from test_marker_flip_review_dialog import _candidate


def capture(root, offset=0):
    t = np.arange(54) * .01
    origins = np.column_stack((10 + offset + 20 * t, 180 - 12 * t, 7 + 3 * t))
    origins[10:14] = origins[9]  # Declared held samples, not inferred truth.
    trajectory = dict(schema_version=1, source_kind='handcrafted_dummy',
        coordinate_policy='world-y-up-box-local-fixed-center-v1', time_s=t,
        body_origin_mm=origins, rotation_matrix=np.repeat(np.eye(3)[None], len(t), axis=0),
        frame=np.arange(len(t)) * 3 + 200)
    spec = dict(schema_version=1, events=[
        dict(kind='flip_180_local_axis', channel='rigid_body_markers', start_index=24, axis='X'),
        dict(kind='flip_180_local_axis', channel='rigid_body_markers', start_index=42, axis='Z'),
        dict(kind='missing', channel='rigid_body_markers', start_index=15, end_index_exclusive=17, marker_ids=['F1'])])
    exported = write_observations(root, trajectory, example_profile(), spec)
    # Add a separately declared raw Rigid Body position block, as found in
    # normal CSV. The solver still consumes the solved-marker observations.
    path = exported / 'observed.csv'
    with path.open(newline='') as stream:
        rows = list(csv.reader(stream))
    for i, values in enumerate((['Rigid Body'] * 3, ['Example'] * 3, ['body'] * 3,
                               [''] * 3, ['Position'] * 3, list('XYZ')), 2):
        rows[i].extend(values)
    for row, origin in zip(rows[8:], origins):
        row.extend(origin)
    with path.open('w', newline='') as stream:
        csv.writer(stream).writerows(rows)
    return path, t, origins


def wait_until(condition, timeout=40):
    end = time.monotonic() + timeout
    while not condition() and time.monotonic() < end:
        QApplication.processEvents()
        time.sleep(.003)
    assert condition(), 'Qt review did not finish'


def test_context_snapshot_event_recentre_and_independent_pending_choices():
    app = QApplication.instance() or QApplication([])
    times = np.arange(150) * .013
    values = pd.DataFrame({'F1_X': 1 + 2 * times, 'F1_Y': 5 - times, 'F1_Z': times * 0}, index=times)
    values.iloc[10:12] = np.nan
    dialog = MarkerFlipReviewDialog([_candidate(event_id=str(i), boundary_time_sec=.2 + .3 * i) for i in range(5)])
    dialog.set_observation_context(values, units='Millimeters', source_path='long-' * 60 + '.csv')
    dialog.resize(820, 600)
    dialog.details_section.setExpanded(True)
    dialog.show(); app.processEvents()
    try:
        assert (dialog.width(), dialog.height()) == (820, 600)
        assert not dialog.button_box.visibleRegion().isEmpty()
        dialog.context_canvas.draw()
        renderer = dialog.context_canvas.get_renderer()
        for label in (dialog.context_figure.axes[0].xaxis.label, dialog.context_figure.axes[0].yaxis.label):
            extent = label.get_window_extent(renderer)
            assert dialog.context_figure.bbox.contains(extent.x0, extent.y0)
            assert dialog.context_figure.bbox.contains(extent.x1, extent.y1)
        root = Path('tmp/issue121'); root.mkdir(parents=True, exist_ok=True)
        dialog.grab().save(str(root / 'small-expanded.png'))
        raw_axis = dialog.context_figure.axes[0]
        np.testing.assert_array_equal(raw_axis.lines[0].get_xdata(), times)
        np.testing.assert_allclose(raw_axis.lines[0].get_ydata(), values.F1_X, equal_nan=True)
        assert np.isnan(raw_axis.lines[0].get_ydata()[10:12]).all()
        values.iloc[0, 0] = 999
        assert raw_axis.lines[0].get_ydata()[0] == 1  # Detached input snapshot.
        raw_axis.set_xlim(.1, .17)
        dialog.axis_combo(0).setCurrentText('Y')
        dialog.approval_checkbox(0).setChecked(True)
        assert dialog.context_figure.axes[0].get_xlim() == (.1, .17)
        dialog.table.setCurrentCell(4, 0)
        assert dialog.context_figure.axes[0].get_xlim() == pytest.approx((1.15, 1.65))
        dialog.table.setCurrentCell(0, 0)
        assert dialog.approval_checkbox(0).isChecked() and dialog.axis_combo(0).currentText() == 'Y'
        assert not dialog.approval_checkbox(4).isChecked()
        assert dialog.context_source.toolTip().startswith('long-')
    finally:
        dialog.reject()
    assert dialog._evidence_canvas_disposed


@pytest.mark.parametrize('data', [None, pd.DataFrame({'F1_X': [np.nan], 'F1_Y': [np.nan], 'F1_Z': [np.nan]}, index=[.1])])
def test_empty_context_clears_plot_and_never_invents_observations(data):
    app = QApplication.instance() or QApplication([])
    dialog = MarkerFlipReviewDialog([])
    dialog.set_observation_context(data)
    assert not dialog.around_event_button.isEnabled()
    assert any('unavailable' in text.get_text() for text in dialog.context_figure.axes[0].texts)
    assert dialog.get_decisions() == []
    dialog.reject(); app.processEvents()


def test_actual_review_context_pan_cancel_save_reopen_and_source_switch(tmp_path, monkeypatch):
    app = QApplication.instance() or QApplication([])
    source, times, origins = capture(tmp_path / 'public-capture')
    other, _, _ = capture(tmp_path / 'another-capture', offset=50)
    original = source.read_bytes()
    def guard(original_open):
        def checked(file, *args, **kwargs):
            if isinstance(file, (str, Path)):
                assert Path(file).name not in ('truth_pose.csv', 'truth_markers.csv', 'observed.synthetic.json'), \
                    'Production opened evaluator-only output'
            return original_open(file, *args, **kwargs)
        return checked
    monkeypatch.setattr(builtins, 'open', guard(builtins.open))
    monkeypatch.setattr(io, 'open', guard(io.open))
    window = MainApp(); window.resize(1510, 800); window.show()
    w = window.original_widget
    errors, results = [], []
    monkeypatch.setattr(QMessageBox, 'warning', lambda *a: errors.append(a[-1]))
    monkeypatch.setattr(QMessageBox, 'information', lambda *a: None)
    w.load_csv_path(str(source))
    for edit, value in zip((w.le_box_l, w.le_box_w, w.le_box_h), (200, 120, 80)):
        edit.setText(str(value))
    w.marker_review_section.setExpanded(True)
    w.confirm_review_dimensions.setChecked(True)
    root = Path('tmp/issue121'); root.mkdir(parents=True, exist_ok=True)
    timer = QTimer()
    mode = 'cancel'
    expected_f1_x = origins[:, 0] + np.where(np.arange(54) >= 42, -21, 21)
    expected_f1_x[15:17] = np.nan

    def inspect():
        dialog = app.activeModalWidget()
        if not isinstance(dialog, MarkerFlipReviewDialog):
            return
        timer.stop()
        try:
            assert len(dialog.candidates) >= 2
            dialog.context_target.setCurrentIndex(dialog.context_target.findData('F1'))
            axis = dialog.context_figure.axes[0]
            np.testing.assert_allclose(axis.lines[0].get_xdata(), times)
            np.testing.assert_allclose(axis.lines[0].get_ydata(), expected_f1_x, equal_nan=True)
            assert 'mm' in axis.get_ylabel()
            before = axis.get_xlim()
            dialog.context_toolbar.pan()
            start = QPoint(dialog.context_canvas.width() // 2, dialog.context_canvas.height() // 2)
            QTest.mousePress(dialog.context_canvas, Qt.LeftButton, pos=start)
            QTest.mouseMove(dialog.context_canvas, start + QPoint(60, 0), delay=30)
            QTest.mouseRelease(dialog.context_canvas, Qt.LeftButton, pos=start + QPoint(60, 0))
            dialog.context_toolbar.pan()
            assert axis.get_xlim() != before
            moved = axis.get_xlim()
            dialog.axis_combo(0).setCurrentText('Y')
            assert not dialog.approval_checkbox(0).isChecked()
            assert dialog.context_figure.axes[0].get_xlim() == moved
            QTest.mouseClick(dialog.around_event_button, Qt.LeftButton)
            assert dialog.context_figure.axes[0].get_xlim() == pytest.approx(before)
            dialog.context_target.setCurrentIndex(dialog.context_target.findData('RigidBody_Position'))
            np.testing.assert_allclose(dialog.context_figure.axes[0].lines[1].get_ydata(), origins[:, 1])
            dialog.context_target.setCurrentIndex(dialog.context_target.findData('F1'))
            for row, candidate in enumerate(dialog.candidates):
                dialog.axis_combo(row).setCurrentText('X' if candidate.boundary_time_sec < .4 else 'Z')
            if mode == 'cancel':
                dialog.grab().save(str(root / 'raw-and-axis.png'))
                assert window.width() == 1510 and window.height() == 800
                (root / 'gui.json').write_text(json.dumps(dict(window=[1510, 800],
                    dialog=[dialog.width(), dialog.height()], dpr=window.devicePixelRatioF(),
                    samples=54, actual_pan=True, preview_separate=True,
                    source_sha256=hashlib.sha256(original).hexdigest(), evaluator_files_blocked=True), indent=2))
                QTest.mouseClick(dialog.button_box.button(QDialogButtonBox.Cancel), Qt.LeftButton)
            elif mode == 'switch':
                w.load_csv_path(str(other))  # Model an external source replacement during modal processing.
                QTest.mouseClick(dialog.button_box.button(QDialogButtonBox.Ok), Qt.LeftButton)
            else:
                for box in dialog._approval_checkboxes:
                    QTest.mouseClick(box, Qt.LeftButton)
                QTest.mouseClick(dialog.button_box.button(QDialogButtonBox.Ok), Qt.LeftButton)
            results.append(mode)
        except Exception as error:
            errors.append(str(error)); dialog.reject()

    timer.timeout.connect(inspect)
    def review():
        previous = len(results)
        timer.start(20)
        QTest.mouseClick(w.review_marker_flips_button, Qt.LeftButton)
        wait_until(lambda: errors or len(results) > previous and w.review_worker is None)
        assert not errors, errors
    try:
        review()
        assert not w.marker_correction_decisions and source.read_bytes() == original
        mode = 'approve'; review()
        assert w.marker_review_dirty and source.read_bytes() == original
        decisions = list(w.marker_correction_decisions)
        monkeypatch.setattr(QFileDialog, 'getSaveFileName', lambda *a: ('', ''))
        w.save_corrected_source()
        assert w.source_path == str(source) and w.marker_correction_decisions == decisions
        destination = tmp_path / 'review.corrected.csv'
        monkeypatch.setattr(QFileDialog, 'getSaveFileName', lambda *a: (str(destination), ''))
        from src.analysis.ui import widget_raw_data_processing as module
        def fail(**kwargs):
            raise OSError('injected failure')
        with monkeypatch.context() as patch:
            patch.setattr(module, 'save_corrected_source_file', fail)
            w.save_corrected_source()
        assert errors == ['injected failure']; errors.clear()
        assert w.marker_correction_decisions == decisions and not destination.exists()
        w.save_corrected_source()
        assert not w.marker_review_dirty and read_corrected_source_metadata(str(destination)).approved_event_count > 0
        w.load_csv_path(str(destination)); w.confirm_review_dimensions.setChecked(True)
        # Reopening a corrected source still displays the original observations.
        mode = 'switch'
        timer.start(20)
        QTest.mouseClick(w.review_marker_flips_button, Qt.LeftButton)
        wait_until(lambda: errors and w.review_worker is None)
        assert len(errors) == 1 and 'Source or dimensions changed' in errors[0]
        assert w.source_path == str(other) and not w.marker_correction_decisions
        assert source.read_bytes() == original
    finally:
        timer.stop()
        w.cancel_marker_review()
        wait_until(lambda: w.review_worker is None)
        window.close(); app.processEvents()
