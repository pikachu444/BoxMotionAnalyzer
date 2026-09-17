"""Existing vertical/rotation signals through real observations and Qt workers."""
import builtins
from dataclasses import replace
import io
import json
from pathlib import Path
import threading
import time

import numpy as np
import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox

from src.analysis.app.main_window import MainApp
from src.analysis.pipeline.data_loader import DataLoader
from src.analysis.pipeline.scene_detection import Registration
from src.analysis.ui import scene_review_flow as flow
from src.config.data_columns import PoseCols
from src.simulation.corruption_export import write_observations
from src.simulation.marker_fixtures import example_profile


VERTICAL = 'Vertical speed (mm/s)'
ROTATION = 'Relative rotation (deg)'
APP = QApplication.instance() or QApplication([])


def capture(root, *, rotating=False, offset=0):
    t = np.arange(61) * .01
    origins = np.column_stack((np.full(len(t), 20 + offset), 2500 - 4905*t*t, t*0))
    angle = np.deg2rad(45*t if rotating else t*0)
    rotation = np.repeat(np.eye(3)[None], len(t), axis=0)
    rotation[:, 0, 0] = rotation[:, 1, 1] = np.cos(angle)
    rotation[:, 0, 1], rotation[:, 1, 0] = -np.sin(angle), np.sin(angle)
    trajectory = dict(schema_version=1, source_kind='handcrafted_dummy',
        coordinate_policy='world-y-up-box-local-fixed-center-v1', time_s=t,
        body_origin_mm=origins, rotation_matrix=rotation, frame=np.arange(len(t)))
    folder = write_observations(root, trajectory, example_profile(), dict(schema_version=1, events=[]))
    return folder/'observed.csv', t


def wait(widget):
    deadline = time.monotonic() + 25
    while widget.scene_busy or (widget.scene_worker and widget.scene_worker.isRunning()):
        APP.processEvents()
        time.sleep(.005)
        assert time.monotonic() < deadline, widget.log_output.toPlainText()
    APP.processEvents()


@pytest.fixture
def window(monkeypatch):
    def unexpected(*args, **kwargs):
        raise AssertionError(f'Unexpected message: {args}')
    monkeypatch.setattr(QMessageBox, 'warning', unexpected)
    monkeypatch.setattr(QMessageBox, 'critical', unexpected)
    window = MainApp(); window.resize(1510, 800); window.show()
    yield window
    worker = window.original_widget.scene_worker
    if worker and worker.isRunning():
        worker.requestInterruption()
        wait(window.original_widget)
    window.close(); window.deleteLater(); APP.processEvents()


def select(widget, name):
    combo = widget.combo_plot_axis
    # Real key navigation exercises the connected selection signal.
    combo.setFocus()
    QTest.keyClick(combo, Qt.Key_Home)
    for _ in range(combo.findData(name)):
        QTest.keyClick(combo, Qt.Key_Down)
    assert combo.currentData() == name
    APP.processEvents()


@pytest.mark.parametrize('rotating', [False, True])
def test_actual_vertical_and_rotation_selection_edit_save_reopen(window, tmp_path, monkeypatch, rotating):
    source, t = capture(tmp_path/'capture', rotating=rotating)
    def guard(original):
        def checked(file, *args, **kwargs):
            if isinstance(file, (str, Path)):
                assert Path(file).name not in ('truth_pose.csv', 'truth_markers.csv', 'observed.synthetic.json')
            return original(file, *args, **kwargs)
        return checked
    monkeypatch.setattr(builtins, 'open', guard(builtins.open))
    monkeypatch.setattr(io, 'open', guard(io.open))
    w = window.original_widget
    w.load_csv_path(str(source))
    for edit, value in zip((w.le_box_l, w.le_box_w, w.le_box_h), (200, 120, 80)):
        edit.setText(str(value))
    QTest.mouseClick(w.scene_panel.detect_button, Qt.LeftButton); wait(w)
    assert w.scene_session is not None, w.log_output.toPlainText()
    assert w.combo_plot_axis.currentData() == VERTICAL
    assert 'reference point' in w.combo_plot_axis.toolTip()
    assert w.plot_manager.ax.get_ylabel() == VERTICAL
    signals = w.scene_session.result.signals
    np.testing.assert_allclose(signals[ROTATION], 45*t if rotating else t*0, atol=3e-5)
    if not rotating:
        # Independently differentiated declared Y(t), not copied solver output.
        np.testing.assert_allclose(signals[VERTICAL].iloc[5:-5], -9810*t[5:-5], atol=.003)
        assert np.ptp(signals[VERTICAL].dropna()) > 4000
    select(w, ROTATION)
    np.testing.assert_allclose(w.plot_manager.ax.lines[0].get_ydata(), 45*t if rotating else t*0, atol=3e-5)
    assert not w.combo_plot_axis.toolTip()
    row = w.scene_panel.selected_row()
    w.le_slice_start.setText('.10'); w.le_slice_end.setText('.40')
    w.update_span_selector_from_inputs()
    assert row['start'] == .1 and row['end'] == .4
    QTest.mouseClick(w.scene_panel.detect_button, Qt.LeftButton); wait(w)
    assert w.combo_plot_axis.currentData() == ROTATION
    assert w.scene_panel.selected_row()['start'] == .1
    select(w, PoseCols.POS_Y)
    QTest.mouseClick(w.scene_panel.detect_button, Qt.LeftButton); wait(w)
    assert w.combo_plot_axis.currentData() == PoseCols.POS_Y
    select(w, VERTICAL)
    for item in w.scene_session.rows:
        w.scene_panel.refresh(item['id'])
        QTest.mouseClick(w.scene_panel.include_button if item['id'] == row['id'] else
                         w.scene_panel.exclude_button, Qt.LeftButton)
    w.scene_panel.refresh(row['id'])
    assert w.scene_panel.save_all_button.isEnabled()
    saved = tmp_path/'work.scene-review.json'
    monkeypatch.setattr(QFileDialog, 'getSaveFileName', lambda *a, **k: (str(saved), ''))
    w.save_scene_review()
    assert json.loads(saved.read_text())['view']['signal'] == VERTICAL
    monkeypatch.setattr(QFileDialog, 'getExistingDirectory', lambda *a, **k: str(tmp_path))
    w.save_included_scenes()
    slices = list((tmp_path/'observed_scenes').glob('*.slice'))
    assert len(slices) == 1, w.log_output.toPlainText()
    assert len(DataLoader().load_csv(str(slices[0]))[1]) > 1
    select(w, ROTATION)
    monkeypatch.setattr(QFileDialog, 'getOpenFileName', lambda *a, **k: (str(saved), ''))
    w.open_scene_review(); wait(w)
    assert w.combo_plot_axis.currentData() == VERTICAL
    assert w.scene_panel.selected_row()['decision'] == 'include'
    assert w.scene_panel.selected_row()['start'] == .1
    w.scene_panel.details_section.setExpanded(True)
    if rotating:
        select(w, ROTATION)
    APP.processEvents(); w.canvas.draw()
    root = Path('tmp/issue123'); root.mkdir(parents=True, exist_ok=True)
    window.grab().save(str(root / ('rotation.png' if rotating else 'vertical.png')))
    report = dict(logical_size=[window.width(), window.height()], dpr=window.devicePixelRatioF(),
                  samples=len(t), nonrotating=not rotating, selected=w.combo_plot_axis.currentData())
    (root/('rotation.json' if rotating else 'vertical.json')).write_text(json.dumps(report))
    assert report['logical_size'] == [1510, 800]


def test_finite_fallbacks_empty_signal_and_new_source_clear_old_curve(window, tmp_path):
    w = window.original_widget
    source, _ = capture(tmp_path/'capture')
    w.load_csv_path(str(source)); w.detect_scene_candidates(); wait(w)
    result = w.scene_session.result
    # Unit boundary probes intentionally replace signal availability only.
    unavailable = result.signals.copy(); unavailable[VERTICAL] = np.nan
    w.scene_session.result = replace(result, signals=unavailable)
    w._populate_scene_signals(w.scene_session.result, VERTICAL)
    assert w.combo_plot_axis.currentData() == ROTATION  # All-zero rotation is valid.
    select(w, VERTICAL)
    assert w.plot_manager.ax.get_title() == 'Signal unavailable'
    assert np.isnan(w.plot_manager.ax.lines[0].get_ydata()).all()
    unavailable[ROTATION] = np.nan
    w._populate_scene_signals(w.scene_session.result, 'removed signal')
    assert w.combo_plot_axis.currentData() == PoseCols.POS_X
    target_columns = w._raw_plot_columns(PoseCols.POS_Y)
    w.parsed_data.loc[:, target_columns] = np.nan
    assert not w._scene_signal_available(result, PoseCols.POS_Y)
    # Registered meaning follows actual detector inputs, including COM.
    for registration, label in ((Registration(example_profile()), 'box center'),
                                 (Registration(example_profile(), com_offset_mm=(0, 0, 0)), 'center of mass')):
        w.scene_session.result = replace(result, registration=registration)
        w._populate_scene_signals(w.scene_session.result, VERTICAL)
        assert label in w.combo_plot_axis.toolTip()
    other, _ = capture(tmp_path/'other', offset=400)
    w.load_csv_path(str(other))
    assert w.scene_session is None and w.combo_plot_axis.count() == 3
    assert not w.combo_plot_axis.toolTip()
    assert all(line.get_label() not in (VERTICAL, ROTATION) for line in w.plot_manager.ax.lines)


@pytest.mark.parametrize('operation', ['detect', 'workspace'])
def test_stale_worker_cannot_attach_to_another_file(window, tmp_path, monkeypatch, operation):
    w = window.original_widget
    source, _ = capture(tmp_path/'capture'); other, _ = capture(tmp_path/'other', offset=400)
    w.load_csv_path(str(source)); w.detect_scene_candidates(); wait(w)
    saved = tmp_path/'work.scene-review.json'
    monkeypatch.setattr(QFileDialog, 'getSaveFileName', lambda *a, **k: (str(saved), ''))
    w.save_scene_review()
    entered, release = threading.Event(), threading.Event()
    real_detect = flow.detect_scenes
    def held(*args, **kwargs):
        result = real_detect(*args, **kwargs)
        entered.set()
        assert release.wait(15)
        return result
    monkeypatch.setattr(flow, 'detect_scenes', held)
    if operation == 'workspace':
        monkeypatch.setattr(QFileDialog, 'getOpenFileName', lambda *a, **k: (str(saved), ''))
        w.open_scene_review()
    else:
        w.detect_scene_candidates()
    try:
        assert entered.wait(15)
        # Load button is blocked; force a legitimate programmatic preview/source replacement.
        w._apply_csv_preview(str(other), w._prepare_csv_preview(str(other)))
    finally:
        release.set()
    wait(w)
    assert w.source_path == str(other) and w.scene_session is None
    assert w.combo_plot_axis.count() == 3
    assert 'previous detection result discarded' in w.log_output.toPlainText()
    old = w.scene_worker
    w.scene_worker = flow.SceneDetectionWorker(w.header_info, w.raw_data, w.parsed_data, None, w)
    w.scene_busy = True
    old.failed.emit('late error'); old.cancelled.emit(); old.completed.emit(None)
    assert w.scene_busy and w.scene_session is None
    w.scene_busy = False


def test_cancel_after_worker_finishes_before_queued_result_is_delivered(window, tmp_path):
    w = window.original_widget
    source, _ = capture(tmp_path/'capture')
    w.load_csv_path(str(source)); w.detect_scene_candidates(); wait(w)
    session = w.scene_session
    select(w, ROTATION)
    w.detect_scene_candidates()
    # Deliberately do not process the GUI's queued completed signal.
    assert w.scene_worker.wait(15000)
    w.detect_scene_candidates()  # Explicit cancellation must outlive QThread completion.
    wait(w)
    assert w.scene_session is session and w.combo_plot_axis.currentData() == ROTATION
    assert 'Detection cancelled' in w.log_output.toPlainText()
