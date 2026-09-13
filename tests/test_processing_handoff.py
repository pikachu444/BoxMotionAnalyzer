"""Input/output handoff contracts; parsing and expensive solving are substituted."""
import os
from types import SimpleNamespace

import pandas as pd
import pytest
from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox

from src.analysis.pipeline.artifact_io import SliceMetadata
from src.analysis.ui import widget_slice_processing as module
from src.config import config_analysis_ui


@pytest.fixture
def processing(tmp_path, monkeypatch):
    app = QApplication.instance() or QApplication([])
    loader = SimpleNamespace(get_plottable_targets=lambda _data: [])
    widget = module.WidgetSliceProcessing(loader, object())
    metadata = SliceMetadata(source='capture.csv', created='2026-09-14', scene='scene',
        box_l=200., box_w=120., box_h=80., full_start=0., full_end=.1,
        user_start=0., user_end=.1, padded_start=0., padded_end=.1, pad_rows=0, row_count=2)
    monkeypatch.setattr(widget, '_load_slice_bundle', lambda _path: (
        metadata, {}, pd.DataFrame(), pd.DataFrame(index=pd.Index([0., .1], name='Time'))))
    paths = [tmp_path / name for name in ('a.slice', 'b.slice', 'unrelated.slice')]
    for path in paths:
        path.touch()
    yield widget, paths, metadata
    widget.close()
    widget.deleteLater()
    app.processEvents()


def test_handoff_prepares_exact_inputs_without_running_and_preserves_single(processing, monkeypatch):
    widget, paths, _metadata = processing
    requested = []
    widget.processing_requested.connect(lambda *args: requested.append(args))
    assert widget.load_processing_inputs([str(paths[0])])
    single_data = widget.parsed_data
    single_result = pd.DataFrame({'value': [1., 2.]})
    widget.on_processing_finished(single_result)
    widget.details_section.setExpanded(True)
    widget.box_section.setExpanded(True)
    single_range = widget.slice_user_range_label.text()
    single_dimensions = (widget.le_box_l.text(), widget.le_box_w.text(), widget.le_box_h.text())
    monkeypatch.setattr(QMessageBox, 'question', lambda *_args: pytest.fail('Batch does not replace the single result'))
    assert widget.load_processing_inputs([str(path) for path in paths[:2]])
    assert widget.input_mode_combo.currentText() == 'Batch'
    assert widget.batch_input_paths == [str(path) for path in paths[:2]]
    assert widget.batch_table.rowCount() == 2 and not requested
    assert widget.details_section.isHidden() and widget.box_section.isHidden()
    widget.input_mode_combo.setCurrentIndex(0)
    assert not widget.details_section.isHidden() and not widget.box_section.isHidden()
    assert widget.details_section.button.isChecked() and widget.box_section.button.isChecked()
    assert widget.slice_user_range_label.text() == single_range
    assert (widget.le_box_l.text(), widget.le_box_w.text(), widget.le_box_h.text()) == single_dimensions
    assert widget.parsed_data is single_data and widget.current_processed_result is single_result
    assert widget.slice_path == str(paths[0])


def test_cancel_keeps_previous_result(processing, monkeypatch):
    widget, paths, _metadata = processing
    assert widget.load_processing_inputs([str(paths[0])])
    previous = pd.DataFrame({'value': [1., 2.]})
    widget.on_processing_finished(previous)
    monkeypatch.setattr(QMessageBox, 'question', lambda *_args: QMessageBox.Cancel)
    assert not widget.load_processing_inputs([str(paths[1])])
    assert widget.current_processed_result is previous and widget.slice_path == str(paths[0])


def test_preview_save_and_parse_failures_keep_previous_result(processing, monkeypatch):
    widget, paths, _metadata = processing
    assert widget.load_processing_inputs([str(paths[0])])
    previous = pd.DataFrame({'value': [1., 2.]})
    widget.on_processing_finished(previous)
    old_parsed = widget.parsed_data
    monkeypatch.setattr(QMessageBox, 'question', lambda *_args: QMessageBox.Discard)
    original_plot = widget.update_plot

    def reject_new_preview():
        if widget.slice_path == str(paths[1]):
            raise ValueError('injected new preview failure')
        original_plot()

    monkeypatch.setattr(widget, 'update_plot', reject_new_preview)
    assert not widget.load_processing_inputs([str(paths[1])])
    assert widget.current_processed_result is previous and widget.parsed_data is old_parsed
    assert widget.slice_path == str(paths[0]) and widget.slice_path_label.text() == 'a.slice'
    assert widget.save_view_button.isEnabled()
    monkeypatch.setattr(QMessageBox, 'question', lambda *_args: QMessageBox.Save)
    monkeypatch.setattr(QFileDialog, 'getSaveFileName', lambda *_args: ('', ''))
    assert not widget.load_processing_inputs([str(paths[1])])
    monkeypatch.setattr(QFileDialog, 'getSaveFileName', lambda *_args: (str(paths[0].with_suffix('.proc')), ''))
    monkeypatch.setattr(module, 'save_proc_file', lambda *_args: (_ for _ in ()).throw(OSError('write denied')))
    assert not widget.load_processing_inputs([str(paths[1])])
    assert widget.current_processed_result is previous and widget.current_proc_path is None
    monkeypatch.setattr(QMessageBox, 'question', lambda *_args: QMessageBox.Discard)
    monkeypatch.setattr(widget, '_load_slice_bundle', lambda *_args: (_ for _ in ()).throw(ValueError('bad slice')))
    assert not widget.load_processing_inputs([str(paths[1])])
    assert widget.current_processed_result is previous and widget.slice_path == str(paths[0])


def test_completed_mode_names_saved_result_and_only_view_emits_handoff(processing, monkeypatch, tmp_path):
    widget, paths, _metadata = processing
    assert widget.load_processing_inputs([str(paths[0])])
    configs, ready = [], []
    widget.processing_requested.connect(lambda config, *_args: configs.append(config))
    widget.results_ready.connect(ready.append)
    widget.emit_run_processing()
    assert widget.single_running and not widget.input_mode_combo.isEnabled()
    assert configs[0]['processing_mode'] == config_analysis_ui.PROCESSING_MODE_RAW
    assert not configs[0]['enable_result_resampling']
    widget.on_processing_finished(pd.DataFrame({'value': [1., 2.]}))
    widget.rb_processing_standard.setChecked(True)
    outputs, suggested = [], []

    def choose(_parent, _title, path, _filter):
        suggested.append(os.path.basename(path))
        return str(tmp_path / 'saved.proc'), ''

    monkeypatch.setattr(QFileDialog, 'getSaveFileName', choose)
    monkeypatch.setattr(module, 'save_proc_file', lambda path, data: outputs.append((path, data)))
    path = widget.save_processed_result()
    assert suggested == ['a_raw.proc']
    assert outputs and not ready
    widget.save_and_view()
    assert ready == [[path]] and len(outputs) == 1


def test_batch_only_handed_inputs_and_only_new_successful_outputs(processing, monkeypatch):
    widget, paths, _metadata = processing
    assert widget.load_processing_inputs([str(path) for path in paths[:2]])
    loaded, saved, ready = [], [], []
    original_load = widget._load_slice_bundle
    monkeypatch.setattr(widget, '_load_slice_bundle', lambda path: (loaded.append(path), original_load(path))[1])
    widget.results_ready.connect(ready.append)

    class Controller(QObject):
        log_message = Signal(str)

        def process_parsed_data(self, config, parsed):
            assert widget.batch_running
            assert not widget.input_mode_combo.isEnabled() and not widget.method_controls.isEnabled()
            assert not widget.settings_scroll.isEnabled()
            return pd.DataFrame({'value': [1., 2.]})

    controller = Controller()
    widget.pipeline_controller_factory = lambda: controller

    def save(path, _data):
        if path.endswith('b.proc'):
            raise OSError('injected failure')
        saved.append(path)

    monkeypatch.setattr(module, 'save_proc_file', save)
    widget.run_batch_processing()
    assert loaded == [str(path) for path in paths[:2]]
    assert widget.batch_success_paths == saved == [str(paths[0].with_suffix('.proc'))]
    assert widget.batch_table.item(0, 1).text() == 'Saved'
    assert widget.batch_table.item(1, 1).text() == 'Failed'
    assert not ready
    widget.view_batch_button.click()
    assert ready == [saved]
    # Existing output is not announced as a newly successful processing result.
    paths[0].with_suffix('.proc').touch()
    widget.run_batch_processing()
    assert widget.batch_success_paths == [] and not widget.view_batch_button.isEnabled()


def test_missing_dimensions_open_only_needed_settings(processing, monkeypatch):
    widget, paths, metadata = processing
    assert widget.le_box_l.text() == '' and not widget.box_section.button.isChecked()
    from dataclasses import replace
    missing = replace(metadata, box_l=None, box_w=None, box_h=None)
    monkeypatch.setattr(widget, '_load_slice_bundle', lambda _path: (
        missing, {}, pd.DataFrame(), pd.DataFrame(index=[0., .1])))
    monkeypatch.setattr(QMessageBox, 'warning', lambda *_args: None)
    assert widget.load_processing_inputs([str(paths[0])])
    assert widget.box_section.button.isChecked() and widget.le_box_l.isEnabled()
    assert not widget.run_button.isEnabled()
    assert widget.load_processing_inputs([str(paths[1]), str(paths[2])])
    assert widget.box_section.isHidden() and widget.details_section.isHidden()
    widget.input_mode_combo.setCurrentIndex(0)
    assert not widget.box_section.isHidden() and widget.box_section.button.isChecked()
    assert widget.le_box_l.isEnabled() and not widget.run_button.isEnabled()
    for edit, value in zip((widget.le_box_l, widget.le_box_w, widget.le_box_h), ('200', '120', '80')):
        edit.setText(value)
    widget.apply_manual_box_dimensions()
    assert widget.run_button.isEnabled() and not widget.le_box_l.isEnabled()
