"""PUB04 widget/QTest and save round trips; external native input is separate."""
from copy import deepcopy
import json
from pathlib import Path
import threading
import time
from unittest.mock import patch

import numpy as np
import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from src.analysis.pipeline.artifact_io import read_slice_metadata, add_timeline_context_columns, save_proc_file
from src.analysis.pipeline.data_loader import DataLoader
from src.analysis.pipeline.parser import Parser
from src.analysis.ui.widget_raw_data_processing import WidgetRawDataProcessing
from src.analysis.ui import scene_review_flow as flow
from src.config.data_columns import FACE_PREFIX_TO_INFO
from src.simulation.scene_review_fixtures import public_raw, install_ui_fixture, VERTICAL, ROTATION

APP = QApplication.instance() or QApplication([])


def wait(w):
    deadline = time.monotonic() + 20
    while w.scene_busy or (w.scene_worker and w.scene_worker.isRunning()):
        APP.processEvents()
        time.sleep(.01)
        assert time.monotonic() < deadline, w.log_output.toPlainText()
    APP.processEvents()


@pytest.fixture(scope='module')
def source(tmp_path_factory):
    return public_raw(tmp_path_factory.mktemp('pub04-gui'))


@pytest.fixture
def widgets(source):
    created = []
    def create(state='many'):
        w = WidgetRawDataProcessing(DataLoader(), Parser(FACE_PREFIX_TO_INFO))
        install_ui_fixture(w, source, state)
        created.append(w)
        return w
    yield create
    for w in created:
        if w.scene_worker and w.scene_worker.isRunning():
            w.scene_worker.requestInterruption()
            wait(w)
        w.close()
        w.deleteLater()
    APP.processEvents()


def zoom(w):
    w.plot_manager.ax.set_xlim(0., 3.)
    w.plot_manager.ax.set_ylim(-100., 100.)


def assert_zoom(w):
    np.testing.assert_allclose(w.plot_manager.ax.get_xlim(), [0., 3.])
    np.testing.assert_allclose(w.plot_manager.ax.get_ylim(), [-100., 100.])


def test_selection_edit_revert_add_delete_signals_preserve_scoped_view(widgets):
    w = widgets()
    original_targets = list(w.current_selected_targets)
    zoom(w)
    w.scene_panel.refresh('scene_002')
    assert w.plot_manager.span_selector.extents == (.6, .85)
    w.on_region_changed(.64, .80)
    assert w.scene_panel.range_label.text().startswith('Edited:')
    assert w.scene_panel.revert_button.isEnabled()
    w.scene_panel.revert_button.click()
    assert w._get_slice_bounds() == (.6, .85)
    assert w.scene_session.row('scene_002')['decision'] == 'unreviewed'
    assert w.scene_session.row('scene_001')['decision'] == 'include'
    assert w.scene_panel.range_label.text().startswith('Detected:')
    w.scene_panel.add_button.click()
    assert w.scene_panel.selected_id() == 'manual_001'
    assert not w.scene_panel.revert_button.isEnabled()
    assert 'Manual' in w.scene_panel.range_label.text()
    w.scene_panel.remove_button.click()
    w.scene_panel.refresh('scene_001')
    assert_zoom(w)
    w.combo_plot_axis.setCurrentIndex(w.combo_plot_axis.findData(ROTATION))
    assert w.plot_manager.ax.get_xlim() == (0., 3.)
    assert w.plot_manager.ax.get_ylim() != (-100., 100.)  # Different signal units.
    w.plot_manager.ax.set_ylim(2., 10.)
    w.combo_plot_axis.setCurrentIndex(w.combo_plot_axis.findData(VERTICAL))
    assert_zoom(w)
    w.current_selected_targets = ['Marker B1']
    w.combo_plot_axis.setCurrentIndex(1)
    assert w.plot_manager.ax.get_xlim() == (0., 3.)
    assert w.plot_manager.ax.get_ylim() != (-100., 100.)
    w.current_selected_targets = original_targets
    w.combo_plot_axis.setCurrentIndex(w.combo_plot_axis.findData(VERTICAL))
    assert_zoom(w)


def test_shared_save_counts_and_direct_gate_block_pending_busy_dirty_and_bad_dimensions(widgets, tmp_path):
    w = widgets('blocked')
    assert w.save_slice_button.text() == 'Save current (0)...'
    assert w.scene_panel.save_all_button.text() == 'Save included (0)...'
    assert w.save_status_label.text() == 'Review 4 remaining'
    with patch('PySide6.QtWidgets.QFileDialog.getSaveFileName') as current, \
         patch('PySide6.QtWidgets.QFileDialog.getExistingDirectory') as batch:
        assert not w._save_slice() and w.save_included_scenes() == []
        current.assert_not_called()
        batch.assert_not_called()
    for row in w.scene_session.rows[:4]:
        w.scene_session.set_decision(row['id'], 'include' if row['id'] == 'scene_001' else 'exclude')
    w.scene_panel.refresh('scene_001')
    assert w._scene_save_gate() == (1, '') and w._scene_save_gate(batch=True) == (1, '')
    assert w.save_slice_button.isEnabled() and w.scene_panel.save_all_button.isEnabled()
    for attr, reason in [('scene_busy', 'Detection running'), ('marker_review_busy', 'Review running'),
                         ('marker_review_dirty', 'Save correction first'), ('_review_invalidated', 'Review source and dimensions')]:
        setattr(w, attr, True)
        w._update_scene_gates()
        assert w._scene_save_gate() == (1, reason)
        assert not w.save_slice_button.isEnabled() and w.save_slice_button.toolTip() == reason
        with patch('PySide6.QtWidgets.QFileDialog.getSaveFileName') as dialog:
            assert not w._save_slice()
            dialog.assert_not_called()
        setattr(w, attr, False)
    w.le_box_l.setText('nan')
    w._update_scene_gates()
    assert not w.save_slice_button.isEnabled()
    assert w._scene_save_gate()[1] == w.save_slice_button.toolTip() == 'Enter valid dimensions or range'


def test_current_batch_cancel_error_retry_and_slice_reopen_preserve_edit_history(widgets, tmp_path):
    w = widgets()
    zoom(w)
    w.on_region_changed(.14, .30)
    w.scene_panel.include_button.click()
    before = deepcopy(w.scene_session.rows)
    history = deepcopy(w.scene_session.history)
    with patch('PySide6.QtWidgets.QFileDialog.getSaveFileName', return_value=('', '')):
        assert not w._save_slice()
    assert w.scene_session.rows == before and w.scene_session.history == history
    path = tmp_path/'current.slice'
    with patch('PySide6.QtWidgets.QFileDialog.getSaveFileName', return_value=(str(path), '')), \
         patch('src.analysis.ui.widget_raw_data_processing.save_slice_file', side_effect=OSError('injected failure')):
        assert not w._save_slice()
    assert not path.exists() and w.save_status_label.text() == 'Save failed; retry'
    with patch('PySide6.QtWidgets.QFileDialog.getSaveFileName', return_value=(str(path), '')):
        assert w._save_slice(), w.log_output.toPlainText()
    assert_zoom(w)
    meta = read_slice_metadata(str(path))
    packet = json.loads(meta.scene_review_json)
    assert (meta.user_start, meta.user_end) == (.14, .30)
    assert packet['history'] == history and packet['candidate']['decision'] == 'include'
    assert packet['candidate']['auto_start'] == .1 and packet['candidate']['auto_end'] == .35
    fresh = widgets('empty')
    fresh.load_csv_path(str(path))
    assert json.loads(read_slice_metadata(fresh.source_path).scene_review_json)['history'] == history
    # Existing Step 1.5/proc transport retains the new audit envelope too.
    from src.analysis.ui.widget_slice_processing import WidgetSliceProcessing
    from types import SimpleNamespace
    context = WidgetSliceProcessing._build_timeline_context(SimpleNamespace(slice_metadata=meta))
    import pandas as pd
    frame = pd.DataFrame({'Frame': [7, 8]}, index=pd.Index([.14, .30], name='Time'))
    proc = tmp_path/'review.proc'
    save_proc_file(str(proc), add_timeline_context_columns(frame, context))
    loaded_proc = DataLoader().load_result_csv(str(proc))
    assert json.loads(loaded_proc[('Info', 'SceneReview', 'Json')].iloc[0])['history'] == history
    with patch('PySide6.QtWidgets.QFileDialog.getExistingDirectory', return_value=''):
        assert w.save_included_scenes() == []
    with patch('PySide6.QtWidgets.QFileDialog.getExistingDirectory', return_value=str(tmp_path)), \
         patch('src.analysis.ui.scene_review_flow.save_slice_file', side_effect=OSError('injected batch failure')), \
         patch('PySide6.QtWidgets.QMessageBox.warning'):
        assert w.save_included_scenes() == []
    assert w.scene_panel.selected_id() == 'scene_001' and w.scene_session.rows == before
    with patch('PySide6.QtWidgets.QFileDialog.getExistingDirectory', return_value=str(tmp_path)):
        paths = w.save_included_scenes()
    assert len(paths) == 2 and w.scene_panel.selected_id() == 'scene_001'
    assert [(read_slice_metadata(p).user_start, read_slice_metadata(p).user_end) for p in paths] == [(.14, .30), (.6, .85)]
    assert_zoom(w)


def test_workspace_reopen_view_range_history_and_invalid_open_preserve_active_work(widgets, tmp_path, monkeypatch):
    w = widgets('edited')
    zoom(w)
    path = tmp_path/'review.scene-review.json'
    with patch('PySide6.QtWidgets.QFileDialog.getSaveFileName', return_value=(str(path), '')):
        w.save_scene_review()
    assert path.is_file(), w.log_output.toPlainText()
    data = json.loads(path.read_text(encoding='utf-8'))
    assert data['plot_view']['xlim'] == [0., 3.] and data['plot_view']['ylim'] == [-100., 100.]
    assert data['view']['selected_id'] == 'scene_001' and data['rows'][0]['decision'] == 'unreviewed'
    # Independent UI fixture explicitly supplies its candidate topology again.
    monkeypatch.setattr(flow, 'detect_scenes', lambda *a, **k: w.scene_session.result)
    fresh = widgets('empty')
    with patch('PySide6.QtWidgets.QFileDialog.getOpenFileName', return_value=(str(path), '')):
        fresh.open_scene_review()
    wait(fresh)
    assert fresh._get_slice_bounds() == (.14, .30) and fresh.combo_plot_axis.currentData() == VERTICAL
    assert fresh.plot_manager.span_selector.extents == (.14, .30)
    assert fresh.scene_session.history['entries'][:len(data['history']['entries'])] == data['history']['entries']
    assert_zoom(fresh)
    session = fresh.scene_session
    for key, value in [('units', 'm/s'), ('source_sha256', '0'*64), ('capture_interval_s', [1., 13.])]:
        bad = deepcopy(data)
        bad['plot_view'][key] = value
        path.write_text(json.dumps(bad), encoding='utf-8')
        with patch('PySide6.QtWidgets.QFileDialog.getOpenFileName', return_value=(str(path), '')):
            fresh.open_scene_review()
        wait(fresh)
        assert fresh.scene_session is session
        assert_zoom(fresh)


def test_dialog_state_change_and_source_replacement_reset_only_relevant_work(widgets, tmp_path):
    w = widgets()
    zoom(w)
    path = tmp_path/'stale.slice'
    def changed(*a, **k):
        w.scene_panel.type_combo.setCurrentText('H')
        return str(path), ''
    with patch('PySide6.QtWidgets.QFileDialog.getSaveFileName', side_effect=changed):
        assert not w._save_slice()
    assert not path.exists() and w.scene_session.rows[0]['decision'] == 'include'
    assert w.scene_session.type_basis == 'operator'
    assert not w.scene_session.rows[0]['identity']['confirmed']
    assert_zoom(w)
    w.le_box_l.setText('310')
    w.le_box_l.editingFinished.emit()
    assert all(r['decision'] == 'unreviewed' and r['evidence_status'] == 'geometry_changed' for r in w.scene_session.rows)
    assert any(e['action'] == 'geometry_changed' and e['snapshot']['decision'] == 'include'
               for e in w.scene_session.history['entries'])
    assert_zoom(w)
    replacement = public_raw(tmp_path/'replacement')
    w.load_csv_path(str(replacement))
    assert w.scene_session is None and not w._plot_views
    assert w.plot_manager.ax.get_xlim() != (0., 3.)


def test_running_worker_and_stale_geometry_result_cannot_overwrite_review(widgets, monkeypatch):
    w = widgets()
    zoom(w)
    original = w.scene_session
    entered, release = threading.Event(), threading.Event()
    def held(*a, **k):
        entered.set()
        assert release.wait(15)
        return original.result
    monkeypatch.setattr(flow, 'detect_scenes', held)
    w.detect_scene_candidates()
    try:
        assert entered.wait(15)
        w.scene_busy = False  # Queued completion cannot release an actually running worker.
        w._update_scene_gates()
        assert w._scene_save_gate()[1] == 'Detection running' and not w.save_slice_button.isEnabled()
        w.le_box_l.setText('310')
        w.le_box_l.editingFinished.emit()
        history = deepcopy(original.history)
    finally:
        release.set()
    wait(w)
    assert w.scene_session is original and original.history == history
    assert all(r['decision'] == 'unreviewed' and r['evidence_status'] == 'geometry_changed' for r in original.rows)
    assert 'previous detection result discarded' in w.log_output.toPlainText()
    assert_zoom(w)
    w.detect_scene_candidates()
    wait(w)
    assert all(r['decision'] == 'unreviewed' for r in original.rows)
    assert w._scene_save_gate()[1] == 'Match source dimensions'
    w.le_box_l.setText('200')
    w.le_box_l.editingFinished.emit()
    assert w._scene_save_gate()[1].startswith('Review ')


@pytest.mark.parametrize('size', [(820, 600), (1920, 1080)])
@pytest.mark.parametrize('state', ['empty', 'one', 'many', 'edited', 'manual', 'blocked', 'loading', 'error', 'details'])
def test_production_window_size_and_primary_controls_accessible(widgets, size, state):
    w = widgets(state)
    w.resize(*size)
    w.show()
    assert QTest.qWaitForWindowExposed(w, 2000)
    # The first Windows exposure may fit a decorated window to the desktop.
    # Measure the requested logical client size after those events settle.
    QTest.qWait(100)
    w.resize(*size)
    QTest.qWait(100)
    assert (w.width(), w.height()) == size
    w.canvas.draw()
    for button in (w.scene_panel.detect_button, w.scene_panel.details_section.button,
                   w.scene_panel.revert_button, w.save_slice_button, w.scene_panel.save_all_button,
                   w.save_process_button):
        rect = button.rect()
        assert button.isVisible() and rect.width() >= button.sizeHint().width()
        assert w.rect().contains(button.mapTo(w, rect.topLeft()))
        assert w.rect().contains(button.mapTo(w, rect.bottomRight()))
    assert w.canvas.height() >= 90
    assert w.file_path_label.fontMetrics().horizontalAdvance(w.file_path_label.text()) <= w.file_path_label.width()
    if state == 'many':
        item = w.scene_panel.table.item(1, 0)
        QTest.mouseClick(w.scene_panel.table.viewport(), Qt.LeftButton,
                         pos=w.scene_panel.table.visualItemRect(item).center())
        assert w.scene_panel.selected_id() == 'scene_002'
        assert w.plot_manager.span_selector.extents == (.6, .85)
    if state == 'details':
        assert w.scene_panel.details_scroll.isVisible()
        assert w.scene_panel.open_review_button.isVisible()
        assert w.scene_panel.type_basis_label.text() == 'Type basis: Operator selection'
        for button in (w.scene_panel.identify_button, w.scene_panel.confirm_button, w.scene_panel.set_intended_button):
            if size[0] < 1100:
                w.scene_panel.details_scroll.ensureWidgetVisible(button)
                APP.processEvents()
            assert button.visibleRegion().contains(button.rect())


def test_mainapp_details_retains_minimum_window_size(source):
    from src.analysis.app.main_window import MainApp
    window = MainApp()
    try:
        install_ui_fixture(window.original_widget, source, 'details')
        window.resize(820, 600)
        window.show()
        APP.processEvents()
        assert (window.width(), window.height()) == (820, 600)
        assert window.original_widget.scene_panel.details_scroll.isVisible()
        assert window.original_widget.save_slice_button.visibleRegion().contains(
            window.original_widget.save_slice_button.rect())
    finally:
        window.close()
        window.deleteLater()
        APP.processEvents()
