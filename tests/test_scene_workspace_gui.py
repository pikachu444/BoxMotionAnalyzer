"""Resume Step 1 work through real widgets, CSV parsing and detection workers."""
from copy import deepcopy
import json
from pathlib import Path
import time
from unittest.mock import patch

import numpy as np
import pytest
from PySide6.QtWidgets import QApplication

from src.analysis.pipeline.data_loader import DataLoader
from src.analysis.pipeline.parser import Parser
from src.analysis.pipeline.support_motion import LIFT_SIGNAL
from src.analysis.ui.widget_raw_data_processing import WidgetRawDataProcessing
from src.config.data_columns import FACE_PREFIX_TO_INFO
from src.simulation.scene_fixtures import write_sequence


APP = QApplication.instance() or QApplication([])


def wait(widget):
    deadline = time.monotonic() + 20
    while widget.scene_busy or (widget.scene_worker and widget.scene_worker.isRunning()):
        APP.processEvents()
        time.sleep(.01)
        assert time.monotonic() < deadline, widget.log_output.toPlainText()
    APP.processEvents()


def open_path(action, path):
    with patch('PySide6.QtWidgets.QFileDialog.getOpenFileName', return_value=(str(path), '')):
        action()


@pytest.fixture
def widgets():
    created = []
    def create():
        widget = WidgetRawDataProcessing(DataLoader(), Parser(FACE_PREFIX_TO_INFO))
        created.append(widget)
        return widget
    yield create
    for widget in created:
        if widget.scene_worker and widget.scene_worker.isRunning():
            widget.scene_worker.requestInterruption()
            wait(widget)
        widget.close()
        widget.deleteLater()
    APP.processEvents()


@pytest.fixture
def saved(widgets, tmp_path):
    folder = write_sequence(tmp_path / 'capture', 'handling')
    widget = widgets()
    open_path(widget.open_csv_file, folder / 'observed.csv')
    open_path(widget.load_scene_geometry, folder / 'registration.json')
    widget.scene_panel.detect_button.click()
    wait(widget)
    session = widget.scene_session
    selected = next(row['id'] for row in session.rows if row['motion'] == 'tip_or_rotation')
    widget.scene_panel.refresh(selected)
    widget.le_slice_start.setText('.4')
    widget.le_slice_end.setText('2.0')
    widget.update_span_selector_from_inputs()
    widget.scene_panel.add_button.click()
    manual = widget.scene_panel.selected_id()
    widget.le_slice_start.setText('3.2')
    widget.le_slice_end.setText('4.8')
    widget.update_span_selector_from_inputs()
    removed = next(row['id'] for row in reversed(session.rows) if row['origin'] == 'automatic')
    widget.scene_panel.refresh(removed)
    widget.scene_panel.remove_button.click()
    widget.scene_panel.detect_button.click()
    wait(widget)
    widget.scene_panel.type_combo.setCurrentText('G')
    widget.scene_panel.edition_combo.setCurrentText('2018-03')
    widget.scene_panel.refresh(manual)
    widget.scene_panel.exclude_button.click()
    widget.scene_panel.refresh(selected)
    widget.scene_panel.include_button.click()
    widget.combo_plot_axis.setCurrentIndex(widget.combo_plot_axis.findData(LIFT_SIGNAL))
    path = tmp_path / 'work.scene-review.json'
    with patch('PySide6.QtWidgets.QFileDialog.getSaveFileName', return_value=(str(path), '')):
        widget.scene_panel.save_review_button.click()
    assert path.is_file(), widget.log_output.toPlainText()
    return widget, path, selected, manual, removed


def test_reopen_unfinished_review_and_continue_without_reviving_deleted_rows(saved, widgets):
    original, path, selected, manual, removed = saved
    expected = deepcopy(original.scene_session.rows)
    widget = widgets()
    assert widget.scene_panel.open_review_button.isEnabled()
    open_path(widget.scene_panel.open_review_button.click, path)
    wait(widget)
    assert widget.scene_session is not None, widget.log_output.toPlainText()
    assert widget.scene_session.rows == expected
    assert widget.scene_panel.selected_id() == selected
    assert widget.combo_plot_axis.currentData() == LIFT_SIGNAL
    assert widget._get_slice_bounds() == (.4, 2.)
    assert widget._read_box_dimensions() == (300., 180., 90.)
    assert widget.scene_panel.type_combo.currentText() == 'G'
    assert widget.scene_panel.edition_combo.currentData() == '2018-03'
    assert not widget.scene_panel.save_all_button.isEnabled()
    assert widget.scene_panel.save_review_button.isEnabled()
    height = next(line for line in widget.plot_manager.ax.lines if line.get_label() == LIFT_SIGNAL)
    assert np.nanmax(height.get_ydata()) == pytest.approx(300. * np.sin(np.deg2rad(15.)), abs=1e-6)
    widget.scene_panel.detect_button.click()
    wait(widget)
    assert widget.scene_session.rows == expected
    assert widget.scene_session.row(manual)['decision'] == 'exclude'
    assert removed in widget.scene_session.deleted_ids
    for row in widget.scene_session.rows:
        if row['decision'] == 'unreviewed':
            widget.scene_panel.refresh(row['id'])
            widget.scene_panel.exclude_button.click()
    assert widget.scene_panel.save_all_button.isEnabled()


def test_cached_measurement_is_rebuilt_and_requires_review(saved, widgets):
    original, path, selected, _, _ = saved
    data = json.loads(path.read_text(encoding='utf-8'))
    next(row for row in data['rows'] if row['id'] == selected)['motion_geometry']['opposite_edge_max_height_mm'] = 999.
    path.write_text(json.dumps(data), encoding='utf-8')
    widget = widgets()
    open_path(widget.open_scene_review, path)
    wait(widget)
    row = widget.scene_session.row(selected)
    assert row['motion_geometry'] == original.scene_session.row(selected)['motion_geometry']
    assert row['decision'] == 'unreviewed'
    assert row['previous_review']['decision'] == 'include'
    assert widget.scene_panel.table.item(widget.scene_panel.table.currentRow(), 5).text() == 'Review again'
    assert not widget.scene_panel.save_all_button.isEnabled()
    widget.scene_panel.include_button.click()
    assert row['decision'] == 'include' and 'previous_review' not in row


def test_failed_and_cancelled_open_preserve_active_review(saved):
    widget, path, selected, _, _ = saved
    session, source = widget.scene_session, widget.source_path
    expected = deepcopy(session.rows)
    original = path.read_text(encoding='utf-8')
    for content in ('{}', original.replace(session.source_sha256, '0' * 64)):
        path.write_text(content, encoding='utf-8')
        open_path(widget.open_scene_review, path)
        wait(widget)
        assert widget.scene_session is session and widget.source_path == source
        assert session.rows == expected and widget.scene_panel.selected_id() == selected
    path.write_text(original, encoding='utf-8')
    open_path(widget.open_scene_review, path)
    widget.scene_panel.detect_button.click()  # cancel pending recomputation, including queued completion
    wait(widget)
    assert widget.scene_session is session and widget.source_path == source
    assert session.rows == expected


def test_locate_moved_capture_and_preserve_unsupported_edition(saved, widgets):
    original, path, _, _, _ = saved
    source = Path(original.source_path)
    moved = source.with_name('moved.csv')
    source.rename(moved)
    data = json.loads(path.read_text(encoding='utf-8'))
    data['context']['applied_edition'] = 'Uncatalogued edition'
    for row in data['rows']:
        row['identity']['applied_edition'] = 'Uncatalogued edition'
    path.write_text(json.dumps(data), encoding='utf-8')
    widget = widgets()
    with patch('PySide6.QtWidgets.QFileDialog.getOpenFileName', side_effect=[(str(path), ''), (str(moved), '')]):
        widget.open_scene_review()
    wait(widget)
    assert Path(widget.source_path) == moved
    assert widget.scene_panel.edition_combo.currentData() == 'Uncatalogued edition'
    assert not any(row['identity']['confirmed'] for row in widget.scene_session.rows)
    widget.scene_panel.detect_button.click()
    wait(widget)
    assert widget.scene_session.applied_edition == 'Uncatalogued edition'


def test_save_pending_geometry_uses_current_input_before_redetection(saved, widgets, tmp_path):
    widget, path, selected, _, _ = saved
    data = json.loads(path.read_text(encoding='utf-8'))
    geometry = data['registration']
    geometry['version'] = 1  # Geometry files have their own wrapper version.
    geometry['floor_y_mm'] = 2.
    geometry_path = tmp_path / 'new_geometry.json'
    geometry_path.write_text(json.dumps(geometry), encoding='utf-8')
    open_path(widget.load_scene_geometry, geometry_path)
    assert widget.scene_registration.floor_y_mm == 2.
    assert widget.scene_session.result.registration.floor_y_mm == 0.
    with patch('PySide6.QtWidgets.QFileDialog.getSaveFileName', return_value=(str(path), '')):
        widget.scene_panel.save_review_button.click()
    assert json.loads(path.read_text(encoding='utf-8'))['registration']['floor_y_mm'] == 2.
    reopened = widgets()
    open_path(reopened.open_scene_review, path)
    wait(reopened)
    assert reopened.scene_registration.floor_y_mm == 2.
    assert reopened.scene_session.row(selected)['motion_geometry']['status'] == 'floor_geometry_inconsistent'
    assert reopened.scene_session.row(selected)['decision'] == 'unreviewed'
    assert reopened.scene_session.row(selected)['previous_review']['decision'] == 'include'
    assert not reopened.scene_panel.save_all_button.isEnabled()

    # Conflicting dimensions require matching geometry, and cannot overwrite saved work.
    saved_before = path.read_bytes()
    widget.le_box_l.setText('310')
    widget.le_box_l.editingFinished.emit()
    with patch('PySide6.QtWidgets.QFileDialog.getSaveFileName', return_value=(str(path), '')):
        widget.scene_panel.save_review_button.click()
    assert path.read_bytes() == saved_before
    assert 'dimensions differ from' in widget.log_output.toPlainText()


def test_position_signal_restores_selected_marker_and_curve(saved, widgets):
    widget, path, _, _, _ = saved
    assert 'Marker B1' in widget.data_loader.get_plottable_targets(widget.parsed_data)
    widget.current_selected_targets = ['Marker B1']
    widget.combo_plot_axis.setCurrentIndex(1)  # existing Position-Y plot
    widget.update_plot()
    before = next(line.get_ydata().copy() for line in widget.plot_manager.ax.lines if line.get_label() == 'B1_Y')
    with patch('PySide6.QtWidgets.QFileDialog.getSaveFileName', return_value=(str(path), '')):
        widget.scene_panel.save_review_button.click()
    fresh = widgets()
    open_path(fresh.open_scene_review, path)
    wait(fresh)
    assert fresh.current_selected_targets == ['Marker B1']
    assert fresh.combo_plot_axis.currentIndex() == 1
    after = next(line.get_ydata() for line in fresh.plot_manager.ax.lines if line.get_label() == 'B1_Y')
    np.testing.assert_array_equal(after, before)
