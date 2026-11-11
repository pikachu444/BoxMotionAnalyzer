"""GUI-05 generated-input contracts; no measured experiment or physical oracle."""
import hashlib
from types import SimpleNamespace

import pandas as pd
import pytest
from PySide6.QtCore import Qt, QPoint
from PySide6.QtGui import QRegion
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QFileDialog, QGroupBox, QMessageBox, QWidget, QLineEdit, QScrollArea

from src.analysis.pipeline.artifact_io import save_slice_file, add_timeline_context_columns
from src.analysis.pipeline.data_loader import DataLoader
from src.analysis.pipeline.parser import Parser
from src.analysis.pipeline.pipeline_controller import PipelineController
from src.analysis.ui.widget_slice_processing import WidgetSliceProcessing, _ProcessingScrollArea
from src.config import config_analysis_ui, config_app
from src.config.data_columns import FACE_PREFIX_TO_INFO
from src.simulation.scene_review_fixtures import public_raw
from src.utils.header_converter import convert_to_multi_header
from src.utils.result_time import indexed_result
from src.utils.artifact_metadata import normalize_metadata, read_identity
from src.utils import ui_language



@pytest.fixture
def app(monkeypatch):
    from matplotlib import rcParams
    fonts, minus = rcParams['font.sans-serif'][:], rcParams['axes.unicode_minus']
    application = QApplication.instance() or QApplication([])
    language = application.property('interfaceLanguage')
    translator = getattr(application, 'qt_language_translator', None)
    monkeypatch.setattr(ui_language, 'preferred_language', lambda: 'en')
    ui_language.configure_language(application)
    yield application
    current_translator = getattr(application, 'qt_language_translator', None)
    if current_translator is not None and current_translator is not translator:
        application.removeTranslator(current_translator)
    rcParams['font.sans-serif'], rcParams['axes.unicode_minus'] = fonts, minus
    application.setProperty('interfaceLanguage', language)


@pytest.fixture
def slice_path(tmp_path):
    source = public_raw(tmp_path)
    header, raw = DataLoader().load_csv(str(source))
    path = tmp_path / 'public_long_processing_input.slice'
    save_slice_file(filepath=str(path), header_info=header, raw_data=raw,
                    source_path=str(source), full_start=0., full_end=12.,
                    user_start=0., user_end=1.2, box_dims=(200., 120., 80.), pad_rows=0)
    return path


def fully_visible(widget):
    return (widget.isVisible() and not widget.rect().isEmpty()
            and QRegion(widget.rect()).subtracted(widget.visibleRegion()).isEmpty())


@pytest.mark.parametrize('language', ['en', 'ko'])
@pytest.mark.parametrize('size', [(1510, 800), (1100, 720), (820, 600)])
def test_fixed_groups_action_bars_scroll_and_toolbar(app, slice_path, language, size, monkeypatch):
    monkeypatch.setattr(ui_language, 'preferred_language', lambda: language)
    ui_language.configure_language(app)
    widget = WidgetSliceProcessing(DataLoader(), Parser(FACE_PREFIX_TO_INFO))
    try:
        assert widget.load_slice_file(str(slice_path))
        widget.show()
        widget.resize(*size)
        app.processEvents()
        assert (widget.width(), widget.height()) == size
        assert not any(type(child).__name__ == 'CollapsibleSection' for child in widget.findChildren(QWidget))
        assert all(isinstance(group, QGroupBox) for group in (
            widget.method_controls, widget.resampling_group, widget.log_group,
            widget.box_dims_group, widget.slice_summary_group))
        assert widget.toolbar.orientation() == Qt.Vertical
        assert widget.toolbar.iconSize().width() == 16
        assert widget.toolbar.x() > widget.canvas.x()
        assert widget.plot_manager.ax.xaxis.label.get_fontsize() == 9
        assert widget.plot_manager.ax.yaxis.label.get_fontsize() == 9
        expected_xlim = widget.plot_manager.ax.get_xlim()
        for index, active, inactive in (
            (0, (widget.run_button, widget.save_proc_button, widget.save_view_button),
             (widget.run_batch_button, widget.view_batch_button)),
            (1, (widget.run_batch_button, widget.view_batch_button),
             (widget.run_button, widget.save_proc_button, widget.save_view_button)),
            (0, (widget.run_button, widget.save_proc_button, widget.save_view_button),
             (widget.run_batch_button, widget.view_batch_button))):
            widget.input_mode_combo.setCurrentIndex(index)
            app.processEvents()
            assert fully_visible(widget.input_mode_combo)
            assert widget.input_stack.currentIndex() == widget.preview_stack.currentIndex() == widget.action_stack.currentIndex() == index
            assert all(fully_visible(button) for button in active)
            assert all(not button.isVisible() for button in inactive)
            assert widget.box_dims_group.isHidden() == bool(index)
            assert widget.slice_summary_group.isHidden() == bool(index)
        # A small window reaches settings through their own explicit scroll.
        for field in (widget.le_resampling_range_end, widget.processing_settings_button):
            widget.settings_scroll.ensureWidgetVisible(field)
            app.processEvents()
            assert fully_visible(field)
        widget.context_scroll.ensureWidgetVisible(widget.le_box_h)
        app.processEvents()
        assert fully_visible(widget.le_box_h)
        assert widget.slice_path_label.toolTip() == str(slice_path)
        assert widget.plot_manager.ax.get_xlim() == expected_xlim
        # Neither a mode switch nor a file change resets a user's splitter sizes.
        widget.workflow_splitter.setSizes([300, 200])
        widget.context_splitter.setSizes([500, 260])
        app.processEvents()
        splits = (widget.workflow_splitter.sizes(), widget.context_splitter.sizes())
        widget.input_mode_combo.setCurrentIndex(1)
        widget.input_mode_combo.setCurrentIndex(0)
        assert widget.load_slice_file(str(slice_path))
        app.processEvents()
        assert (widget.workflow_splitter.sizes(), widget.context_splitter.sizes()) == splits
        messages = []
        widget.status_message.connect(messages.append)
        widget.toolbar.set_message('x=0.400 s, y=250 mm')
        assert messages[-1] == 'x=0.400 s, y=250 mm'
    finally:
        widget.close()
        widget.deleteLater()
        app.processEvents()


def test_p01_mode_switch_retains_actual_inputs_and_never_runs(app, slice_path, monkeypatch):
    widget = WidgetSliceProcessing(DataLoader(), Parser(FACE_PREFIX_TO_INFO))
    try:
        assert widget.load_slice_file(str(slice_path))
        requested = []
        widget.processing_requested.connect(lambda *payload: requested.append(payload))
        widget.rb_processing_advanced.setChecked(True)
        widget.advanced_processing_options['marker_ma_window'] = 7
        widget.cb_enable_resampling.setChecked(True)
        widget.combo_resampling_factor.setCurrentIndex(2)
        widget.cb_limit_resampling_range.setChecked(True)
        widget.le_resampling_range_start.setText('0.2')
        widget.le_resampling_range_end.setText('0.8')
        config = widget._build_processing_config(widget.parsed_data)
        context = widget._build_timeline_context()
        data = widget.parsed_data
        widget._activate_batch_inputs([str(slice_path), str(slice_path.parent / 'nested' / slice_path.name)])
        assert widget.batch_table.item(0, 0).text() != widget.batch_table.item(1, 0).text()
        widget.overwrite_proc_checkbox.setChecked(True)
        widget.input_mode_combo.setCurrentIndex(0)
        widget.input_mode_combo.setCurrentIndex(1)
        widget.input_mode_combo.setCurrentIndex(0)
        assert widget.overwrite_proc_checkbox.isChecked()
        assert widget.parsed_data is data
        assert widget._build_processing_config(data) == config
        assert widget._build_timeline_context() == context
        assert tuple(config['box_dimensions']) == (200., 120., 80.)
        assert config['result_resampling_factor'] == 4
        assert config['result_resampling_range_start'] == .2
        assert config['result_resampling_range_end'] == .8
        assert config['analysis_options']['marker_ma_window'] == 7
        assert requested == []
        # Opening/cancelling advanced settings has no processing side effect.
        monkeypatch.setattr('src.analysis.ui.widget_slice_processing.ProcessingSettingsDialog',
                            lambda *_args: SimpleNamespace(exec=lambda: False))
        widget.processing_settings_button.click()
        assert widget._build_processing_config(data) == config and requested == []
    finally:
        widget.close()
        widget.deleteLater()
        app.processEvents()


def test_p02_real_small_run_failure_save_reload_and_cancels(app, slice_path, tmp_path, monkeypatch):
    widget = WidgetSliceProcessing(DataLoader(), Parser(FACE_PREFIX_TO_INFO))
    original = hashlib.sha256(slice_path.read_bytes()).hexdigest()
    old_dims, old_corners = config_app.BOX_DIMS.copy(), config_app.LOCAL_BOX_CORNERS.copy()
    try:
        assert widget.load_slice_file(str(slice_path))
        requested = []
        widget.processing_requested.connect(lambda *payload: requested.append(payload))
        widget.emit_run_processing()
        assert len(requested) == 1 and widget.single_running
        assert not widget.context_scroll.isEnabled() and not widget.settings_scroll.isEnabled()
        assert not widget.le_box_l.isEnabled()
        widget.emit_run_processing()
        assert len(requested) == 1
        config, header, raw, parsed, context = requested[0]
        assert header is widget.header_info and raw is widget.raw_data and parsed is widget.parsed_data
        assert config['processing_mode'] == config_analysis_ui.PROCESSING_MODE_RAW
        assert config['analysis_options'] == config_analysis_ui.get_raw_mode_options()
        assert tuple(config['box_dimensions']) == (200., 120., 80.)
        assert context == widget._build_timeline_context()
        # Failure restores the same run gate; the next click emits exactly once.
        widget.on_processing_failed()
        assert not widget.single_running and widget.run_button.isEnabled()
        assert not widget.save_proc_button.isEnabled()
        widget.run_button.click()
        assert len(requested) == 2
        result = PipelineController().process_parsed_data(config, parsed)
        result = add_timeline_context_columns(result, context)
        assert not result.empty
        widget.on_processing_finished(result)
        monkeypatch.setattr(QFileDialog, 'getSaveFileName', lambda *_args: ('', ''))
        assert widget.save_processed_result() is None
        assert widget.current_processed_result is result and widget.current_proc_path is None
        monkeypatch.setattr(QMessageBox, 'question', lambda *_args: QMessageBox.Cancel)
        assert not widget.prepare_for_input_change()
        assert widget.current_processed_result is result and widget.parsed_data is parsed
        target = tmp_path / 'temporary_output.proc'
        monkeypatch.setattr(QFileDialog, 'getSaveFileName', lambda *_args: (str(target), ''))
        assert widget.save_processed_result() == str(target)
        loaded = DataLoader().load_result_csv(str(target))
        identity = read_identity(loaded).values
        for field, value in normalize_metadata(context['artifact_metadata']).items():
            if field not in {'ProcessingSemanticsVersion', 'ProcessingSettingsJson'}:
                assert identity[field] == value
        expected = indexed_result(convert_to_multi_header(result))
        for column in expected.columns:
            # CSV reload infers numeric Frame strings; compare recorded values.
            try:
                observed, reference = pd.to_numeric(loaded[column]), pd.to_numeric(expected[column])
            except (ValueError, TypeError):
                observed = loaded[column].fillna('').astype(str)
                reference = expected[column].fillna('').astype(str)
            pd.testing.assert_series_equal(observed, reference, check_dtype=False, check_names=False,
                                           check_exact=False, rtol=1e-12, atol=1e-12, check_flags=False)
        assert hashlib.sha256(slice_path.read_bytes()).hexdigest() == original
    finally:
        config_app.BOX_DIMS, config_app.LOCAL_BOX_CORNERS = old_dims, old_corners
        widget.close()
        widget.deleteLater()
        app.processEvents()





@pytest.mark.parametrize('size', [(1510, 800), (1100, 720), (820, 600)])
def test_missing_dimensions_and_action_remain_reachable(app, slice_path, size, monkeypatch):
    from dataclasses import replace
    widget = WidgetSliceProcessing(DataLoader(), Parser(FACE_PREFIX_TO_INFO))
    try:
        metadata, header, raw, parsed = widget._load_slice_bundle(str(slice_path))
        missing = replace(metadata, box_l=None, box_w=None, box_h=None)
        monkeypatch.setattr(widget, '_load_slice_bundle', lambda _path: (missing, header, raw, parsed))
        monkeypatch.setattr(QMessageBox, 'warning', lambda *_args: None)
        widget.resize(*size)
        widget.show()
        assert widget.load_slice_file(str(slice_path))
        app.processEvents()
        widget.context_scroll.ensureWidgetVisible(widget.apply_box_dims_button)
        app.processEvents()
        assert (widget.width(), widget.height()) == size
        assert fully_visible(widget.apply_box_dims_button)
        assert fully_visible(widget.input_mode_combo) and fully_visible(widget.run_button)
        assert widget.le_box_l.isEnabled() and not widget.run_button.isEnabled()
        widget._set_batch_controls_enabled(False)
        assert not widget.le_box_l.isEnabled() and not widget.apply_box_dims_button.isEnabled()
        widget._set_batch_controls_enabled(True)
        assert widget.le_box_l.isEnabled() and widget.apply_box_dims_button.isEnabled()
    finally:
        widget.close()
        widget.deleteLater()
        app.processEvents()


@pytest.mark.parametrize('edge', ['bottom', 'right'])
def test_context_scroll_reveals_whole_field_when_cursor_is_already_visible(app, edge):
    scroll = _ProcessingScrollArea()
    content = QWidget()
    content.setFixedSize(500, 500)
    group = QWidget(content)
    group.setGeometry(7, 9, 450, 450)
    field = QLineEdit('200', group)
    field.resize(120, 80)
    scroll.setWidget(content)
    scroll.resize(220, 160)
    scroll.show()
    app.processEvents()
    try:
        if edge == 'bottom':
            field.move(10, scroll.viewport().height() - field.height() + 3 - group.y())
        else:
            field.move(scroll.viewport().width() - field.width() + 3 - group.x(), 10)
        app.processEvents()
        cursor = field.inputMethodQuery(Qt.ImCursorRectangle)
        cursor_in_viewport = cursor.translated(field.mapTo(scroll.viewport(), QPoint()))
        assert scroll.viewport().rect().contains(cursor_in_viewport)
        assert not fully_visible(field)
        # Negative control: stock Qt returns as soon as the cursor fits.
        QScrollArea.ensureWidgetVisible(scroll, field)
        assert not fully_visible(field)
        scroll.ensureWidgetVisible(field)
        app.processEvents()
        assert fully_visible(field)
    finally:
        scroll.close()
        scroll.deleteLater()
        app.processEvents()


def test_context_keyboard_navigation_reveals_whole_field(app):
    scroll = _ProcessingScrollArea()
    content = QWidget()
    content.setFixedSize(500, 500)
    first = QLineEdit('first', content)
    first.setGeometry(10, 0, 120, 30)
    second = QLineEdit('second', content)
    second.resize(120, 80)
    scroll.setWidget(content)
    scroll.resize(220, 160)
    scroll.show()
    app.processEvents()
    try:
        second.move(10, scroll.viewport().height() - second.height() + 3)
        first.setFocus()
        app.processEvents()
        assert first.hasFocus() and not fully_visible(second)
        QTest.keyClick(first, Qt.Key_Tab)
        app.processEvents()
        assert second.hasFocus() and fully_visible(second)
    finally:
        scroll.close()
        scroll.deleteLater()
        app.processEvents()
