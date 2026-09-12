"""Step 1 uses real widgets, worker, parser and files; dialogs select test paths."""
import json
import time
from dataclasses import replace
from unittest.mock import patch

import pytest
import numpy as np
from PySide6.QtWidgets import QApplication

from src.analysis.pipeline.data_loader import DataLoader
from src.analysis.pipeline.parser import Parser
from src.analysis.pipeline.artifact_io import read_slice_metadata
from src.analysis.ui.widget_raw_data_processing import WidgetRawDataProcessing
from src.config.data_columns import FACE_PREFIX_TO_INFO
from src.simulation.scene_fixtures import write_sequence


APP = QApplication.instance() or QApplication([])


def wait_detection(widget):
    deadline = time.monotonic() + 15
    while widget.scene_busy or (widget.scene_worker and widget.scene_worker.isRunning()):
        APP.processEvents()
        # Release the Python GIL so the Python QThread can compute. QTest.qWait
        # services Qt events but can starve this worker while holding the GIL.
        time.sleep(.01)
        assert time.monotonic() < deadline, widget.log_output.toPlainText()
    APP.processEvents()


@pytest.fixture
def loaded(tmp_path):
    folder = write_sequence(tmp_path / 'capture', 'drops')
    widget = WidgetRawDataProcessing(DataLoader(), Parser(FACE_PREFIX_TO_INFO))
    with patch('PySide6.QtWidgets.QFileDialog.getOpenFileName', return_value=(str(folder/'observed.csv'), '')):
        widget.open_csv_file()
    with patch('PySide6.QtWidgets.QFileDialog.getOpenFileName', return_value=(str(folder/'registration.json'), '')):
        widget.load_scene_geometry()
    yield widget, folder
    if widget.scene_worker and widget.scene_worker.isRunning():
        widget.scene_worker.requestInterruption()
        wait_detection(widget)
    widget.close()
    widget.deleteLater()
    APP.processEvents()


def test_detect_select_edit_review_save_and_reopen(loaded, tmp_path):
    widget, folder = loaded
    calls = []
    widget.file_loaded.connect(lambda *args: calls.append(args))
    widget.scene_panel.detect_button.click()
    assert not widget.load_csv_button.isEnabled()
    wait_detection(widget)
    assert widget.scene_session is not None, widget.log_output.toPlainText()
    assert not widget.scene_panel.save_all_button.isEnabled()
    falls = [r for r in widget.scene_session.rows if r['motion'] == 'free_fall']
    assert len(falls) == 2
    widget.scene_panel.refresh(falls[0]['id'])
    assert float(widget.le_slice_start.text()) == falls[0]['start']
    assert float(widget.le_slice_end.text()) == falls[0]['end']
    assert not calls  # selecting intervals must not change MainApp's active source
    original_start = falls[0]['start']
    widget.le_slice_start.setText(repr(original_start - .008))
    widget.update_span_selector_from_inputs()
    assert falls[0]['evidence_status'] == 'range_changed'
    widget.scene_panel.detect_button.click()
    wait_detection(widget)
    assert falls[0]['start'] == original_start - .008
    assert falls[0]['evidence_status'] == 'current'
    for row in widget.scene_session.rows:
        widget.scene_panel.refresh(row['id'])
        (widget.scene_panel.include_button if row['motion'] == 'free_fall' else widget.scene_panel.exclude_button).click()
    assert widget.scene_panel.save_all_button.isEnabled()
    widget.scene_panel.type_combo.setCurrentText('H')
    widget.scene_panel.identify_button.click()
    assert all(not r['identity']['confirmed'] for r in widget.scene_session.rows)
    with patch('PySide6.QtWidgets.QFileDialog.getExistingDirectory', return_value=str(tmp_path)), \
         patch('PySide6.QtWidgets.QMessageBox.warning') as warning:
        widget.scene_panel.save_all_button.click()
    warning.assert_not_called()
    paths = list((tmp_path/'observed_scenes').glob('*.slice'))
    assert len(paths) == 2, widget.log_output.toPlainText()
    for path in paths:
        meta = read_slice_metadata(str(path))
        review = json.loads(meta.scene_review_json)
        assert review['candidate']['decision'] == 'include'
        assert review['identity']['ista_type'] == 'H'
        assert review['identity']['scenario_id'] is None
        assert meta.user_start == review['candidate']['start']
        assert meta.user_end == review['candidate']['end']
        h, raw = DataLoader().load_csv(str(path))
        assert len(raw) > 1 and h['artifact_metadata']['ScenarioId'] is None


def test_cancel_and_changed_source_preserve_existing_review(loaded):
    widget, folder = loaded
    widget.detect_scene_candidates()
    wait_detection(widget)
    session = widget.scene_session
    row_id = session.rows[0]['id']
    session.set_decision(row_id, 'exclude')
    widget.detect_scene_candidates()
    widget.detect_scene_candidates()  # same action becomes cancellation
    wait_detection(widget)
    assert widget.scene_session is session
    assert session.row(row_id)['decision'] == 'exclude'
    with (folder/'observed.csv').open('a') as f:
        f.write('\n')
    widget.detect_scene_candidates()
    assert widget.scene_session is session
    assert 'changed on disk' in widget.log_output.toPlainText()
    assert not widget.scene_busy


def test_dimension_change_invalidates_confirmed_scenes(loaded):
    widget, _ = loaded
    widget.detect_scene_candidates()
    wait_detection(widget)
    session = widget.scene_session
    session.set_context('H', '2018-03')
    for row in session.rows:
        session.set_decision(row['id'], 'include' if row['motion'] == 'free_fall' else 'exclude')
    session.identify()
    row = next(r for r in session.rows if r['decision'] == 'include')
    session.confirm_item(row['id'], 'H/B04/D06')
    widget.le_box_l.setText('310')
    widget.le_box_l.editingFinished.emit()
    assert row['decision'] == 'unreviewed' and not row['identity']['confirmed']
    assert not widget.scene_panel.save_all_button.isEnabled()
    widget.detect_scene_candidates()
    assert 'differ from the registered' in widget.log_output.toPlainText()


def test_marker_busy_blocks_detection_before_thread_starts_and_keeps_declared_type(loaded):
    widget, _ = loaded
    widget.header_info['artifact_metadata']['IstaType'] = 'G'
    widget._reset_scenes()
    assert widget.scene_panel.type_combo.currentText() == 'G'
    assert widget.scene_panel.edition_combo.currentData() is None
    widget._set_review_busy(True)
    assert not widget.scene_panel.detect_button.isEnabled()
    assert not widget.load_csv_button.isEnabled()
    assert not widget.box_dims_group.isEnabled()
    assert not widget.review_marker_flips_button.isEnabled()
    widget._set_review_busy(False)
    assert widget.scene_panel.detect_button.isEnabled()


def test_position_redraw_preserves_manual_csv_slice_range(loaded):
    widget, _ = loaded
    assert widget.scene_session is None
    assert len(widget.plot_manager.ax.patches) == 1
    widget.current_selected_targets = ['Marker B1']
    widget.combo_plot_axis.setCurrentIndex(1)
    widget.slice_group.setChecked(True)
    bounds = (.123456789, .876543219)
    widget.le_slice_start.setText(repr(bounds[0]))
    widget.le_slice_end.setText(repr(bounds[1]))
    widget.update_span_selector_from_inputs()
    widget.update_plot()
    selector = widget.plot_manager.span_selector
    assert selector.active and selector.get_visible()
    assert selector.extents == bounds
    assert all(artist in widget.plot_manager.ax.get_children() and artist.get_visible()
               for artist in selector.artists)
    assert len(widget.plot_manager.ax.patches) == 1
    line = next(line for line in widget.plot_manager.ax.lines if line.get_label() == 'B1_Y')
    np.testing.assert_array_equal(line.get_ydata(), widget.parsed_data['B1_Y'])
    assert len(line.get_xdata()) == len(widget.raw_data)
    widget.slice_group.setChecked(False)
    widget.update_plot()
    assert not widget.plot_manager.span_selector.active
    assert not widget.plot_manager.span_selector.get_visible()
    assert all(not artist.get_visible() for artist in widget.plot_manager.span_selector.artists)
    widget.slice_group.setChecked(True)
    widget.update_plot()
    assert widget.plot_manager.span_selector.extents == bounds


def test_item_tooltip_explains_observed_geometry_limit_without_raw_dict(loaded):
    widget, _ = loaded
    widget.detect_scene_candidates()
    wait_detection(widget)
    session = widget.scene_session
    session.set_context('G', '2018-03')
    session.result = replace(session.result, registration=replace(session.result.registration, floor_y_mm=None))
    for row in session.rows:
        session.set_decision(row['id'], 'include' if row['motion'] == 'free_fall' else 'exclude')
    session.identify()
    row = next(row for row in session.rows if row['motion'] == 'free_fall')
    assert row['geometry'] == {'status': 'registration_required'}
    for geometry, reason in (
        (row['geometry'], 'Box and floor registration required.'),
        ({'status': 'registered', 'floor_crossings': []}, 'Floor approach not established.'),
        ({'status': 'registered', 'floor_crossings': [{'approach_feature': None}]},
         'Approach feature unclear.'),
        ({}, ''),
    ):
        row['geometry'] = geometry
        widget.scene_panel.refresh(row['id'])
        tooltip = widget.scene_panel.table.item(widget.scene_panel.table.currentRow(), 6).toolTip()
        if reason:
            assert reason in tooltip
            assert reason in widget.scene_panel.item_combo.toolTip()
        else:
            assert 'registration required' not in tooltip
            assert 'Floor approach' not in tooltip
            assert 'Approach feature' not in tooltip
        assert row['sequence_evidence'] in tooltip
        assert row.get('eligibility_condition', '') in tooltip
        assert '{' not in tooltip and 'floor_crossings' not in tooltip


def test_remove_all_scenes_disables_range_and_keeps_full_capture_curve(loaded, tmp_path):
    widget, _ = loaded
    folder = write_sequence(tmp_path / 'support_capture', 'handling')
    for action, name in ((widget.open_csv_file, 'observed.csv'),
                         (widget.load_scene_geometry, 'registration.json')):
        with patch('PySide6.QtWidgets.QFileDialog.getOpenFileName', return_value=(str(folder/name), '')):
            action()
    widget.detect_scene_candidates()
    wait_detection(widget)
    row = next(row for row in widget.scene_session.rows
               if row['motion_geometry']['status'] == 'floor_pivot_compatible')
    widget.scene_panel.refresh(row['id'])
    signal = 'Relative rotation (deg)'
    widget.combo_plot_axis.setCurrentIndex(widget.combo_plot_axis.findData(signal))
    APP.processEvents()
    line = next(line for line in widget.plot_manager.ax.lines if line.get_label() == signal)
    before = line.get_ydata().copy()
    assert np.isfinite(before).any()

    widget.scene_panel.table.selectAll()
    widget.scene_panel.remove_button.click()
    APP.processEvents()

    assert not widget.scene_session.rows
    assert widget.scene_panel.selected_row() is None
    line = next(line for line in widget.plot_manager.ax.lines if line.get_label() == signal)
    np.testing.assert_array_equal(line.get_ydata(), before)
    assert len(line.get_xdata()) == len(widget.raw_data)
    assert not widget.plot_manager.span_selector.active
    assert not widget.save_slice_button.isEnabled()
