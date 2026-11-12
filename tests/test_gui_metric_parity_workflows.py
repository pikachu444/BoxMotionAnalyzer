"""Real Qt interactions and generated public files; no measured qualification."""
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest
from PySide6.QtCore import Qt, QCoreApplication, QEvent, QPoint
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QFileDialog

from src.analysis.pipeline.data_loader import DataLoader
from src.analysis.pipeline.parser import Parser
from src.analysis.pipeline.scenario_export import scenario_bytes
from src.analysis.ui.widget_results_analyzer import WidgetResultsAnalyzer
from src.analysis.ui.widget_slice_processing import WidgetSliceProcessing
from src.analysis.ui.shared_metric_guide import SharedMetricGuideDialog
from src.analysis.ui.dialog_marker_flip_review import MarkerFlipReviewDialog
from src.analysis.compare.metric_guide import MetricGuideDialog, guide_key_for_summary
from src.analysis.ui.dialog_metric_guide import DropPostureMetricGuideDialog
from src.config.data_columns import FACE_PREFIX_TO_INFO, RESULT_TIME_COL
from src.config.result_metric_descriptors import get_metric_registry, get_drop_posture_summary_descriptors
from src.utils import ui_language
from test_gui_metric_parity_contract import metric_frame
from test_posture_comparison import posture_frame
from test_gui_metric_parity_exports import CAE_GOLDEN as CAE_MEASURED_GOLDEN, REST_GOLDEN as CAE_REST_GOLDEN


@pytest.fixture
def app(monkeypatch):
    from matplotlib import rcParams
    application = QApplication.instance() or QApplication([])
    QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
    previous = application.property('interfaceLanguage')
    previous_translator = getattr(application, 'qt_language_translator', None)
    fonts, minus = rcParams['font.sans-serif'][:], rcParams['axes.unicode_minus']
    monkeypatch.setattr(ui_language, 'preferred_language', lambda: 'en')
    ui_language.configure_language(application)
    yield application
    QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
    translator = getattr(application, 'qt_language_translator', None)
    if translator is not None and translator is not previous_translator:
        application.removeTranslator(translator)
    rcParams['font.sans-serif'], rcParams['axes.unicode_minus'] = fonts, minus
    application.setProperty('interfaceLanguage', previous)


@pytest.fixture
def results(app):
    widget = WidgetResultsAnalyzer(DataLoader())
    widget.resize(820, 600)
    widget.show()
    app.processEvents()
    yield widget
    widget.close_all_popups()
    widget.close()
    widget.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
    app.processEvents()


def activate(widget, frame, path='public.proc'):
    widget._activate_result_data(widget._prepare_result_data(frame), path)


def click_result_canvas(manager, time):
    """Send a Qt click through the installed Matplotlib event connection."""
    canvas, axis = manager.canvas, manager.ax
    axis.set_xlim(-.02, .12)
    canvas.draw()
    QApplication.processEvents()
    x, y = axis.transData.transform((time, sum(axis.get_ylim()) / 2))
    ratio = canvas.device_pixel_ratio
    position = QPoint(round(x / ratio), round((canvas.figure.bbox.height - y) / ratio))
    events = []
    connection = canvas.mpl_connect('button_press_event', events.append)
    try:
        QTest.mouseClick(canvas, Qt.LeftButton, Qt.NoModifier, position)
        QApplication.processEvents()
    finally:
        canvas.mpl_disconnect(connection)
    assert len(events) == 1 and events[0].inaxes in manager.axes
    assert events[0].xdata == pytest.approx(time, abs=.005)


@pytest.mark.parametrize('source', ['main', 'popup'])
@pytest.mark.parametrize('target_present', [False, True])
def test_canvas_click_rejects_entirely_missing_result(results, source, target_present):
    column = ('Velocity', 'CoM', 'Global_V_TX')
    frame = pd.DataFrame({RESULT_TIME_COL: [0., .1], column: [np.nan, np.nan],
                          ('Velocity', 'CoM', 'Global_V_TY'): [np.nan, np.nan]})
    frame.columns = pd.MultiIndex.from_tuples(frame.columns)
    activate(results, frame)
    if target_present:
        results.checked_result_columns = {column}
        results.plot_selected_results()
    if source == 'popup':
        results._open_popup([column])
        manager = next(iter(results.popup_windows.values())).plot_manager
    else:
        manager = results.plot_manager
    assert (results.find_max_target_combo.currentData() is not None) == target_present
    click_result_canvas(manager, .1)
    assert results.selected_point_info == dict(time=None, index=None)
    assert not results.export_point_button.isEnabled()
    assert not results.export_scenario_button.isEnabled()
    assert all(not button.isEnabled() for button in (
        results.find_abs_max_button, results.find_max_button, results.find_min_button))
    assert all(popup.cursor_line is None for popup in results.popup_windows.values())


@pytest.mark.parametrize('column,values,usable', [
    (('Velocity', 'CoM', 'Global_V_TX'), [0., 0.], True),
    (('Velocity', 'CoM', 'Global_V_TX'), [2., 3.], True),
    (('Velocity', 'CoM', 'Global_V_TX'), [0., np.nan], True),
    (('Velocity', 'CoM', 'Global_V_TX'), [np.inf, -np.inf], False),
    (('Analysis', 'DropPosture', 'CminIndex'), [1., 8.], True),
    (('Analysis', 'DropPosture', 'CminIndex'), [0., 9.], False),
    (('Analysis', 'DropPosture', 'CminIndex'), [1.5, np.nan], False),
    (('Analysis', 'DropPosture', 'CminIndex'), [True, False], False),
    (('Analysis', 'Notes', 'Text'), ['observed', 'text'], False),
])
def test_canvas_point_requires_supported_result_observation(results, column, values, usable):
    frame = pd.DataFrame({RESULT_TIME_COL: [0., .1], column: values,
        ('Info', 'Frame', 'Frame'): [1, 2], ('Frame', 'Frame', 'Frame'): [1, 2],
        ('Info', 'Artifact', 'SchemaVersion'): [1, 1],
        ('Artifact', 'Identity', 'Version'): [1, 1],
        ('Info', 'Label', 'Text'): ['capture', 'description']})
    frame.columns = pd.MultiIndex.from_tuples(frame.columns)
    activate(results, frame)
    assert results.find_max_target_combo.currentData() is None
    click_result_canvas(results.plot_manager, .1)
    assert results.selected_point_info == (dict(time=.1, index=1) if usable else dict(time=None, index=None))
    assert results.export_point_button.isEnabled() == usable
    assert results.export_scenario_button.isEnabled() == usable


def test_point_time_survives_nan_target_and_exports_whole_row(results, tmp_path, monkeypatch):
    observed = ('Velocity', 'CoM', 'Global_V_TX')
    missing = ('Velocity', 'CoM', 'Global_V_TY')
    text = ('Info', 'Label', 'Text')
    precise = .123456789012345
    frame = pd.DataFrame({RESULT_TIME_COL: [0., .1], observed: [0., precise],
                          missing: [np.nan, np.nan], text: ['first', '쉼표, "인용"']})
    frame.columns = pd.MultiIndex.from_tuples(frame.columns)
    activate(results, frame)
    # A point and its complete export do not require any plotted series.
    click_result_canvas(results.plot_manager, .1)
    assert results.selected_point_info == dict(time=.1, index=1)
    results.checked_result_columns = {observed, missing}
    results.refresh_result_tree()
    for index in range(results.find_max_target_combo.count()):
        if tuple(results.find_max_target_combo.itemData(index)) == missing:
            results.find_max_target_combo.setCurrentIndex(index)
            break
    assert tuple(results.find_max_target_combo.currentData()) == missing
    assert results.selected_point_info == dict(time=.1, index=1)
    assert results.export_point_button.isEnabled()
    assert not results.find_max_button.isEnabled()
    results._open_popup([missing])
    popup = next(iter(results.popup_windows.values()))
    click_result_canvas(popup.plot_manager, 0.)
    assert results.selected_point_info == dict(time=0., index=0)
    click_result_canvas(results.plot_manager, .1)
    assert results.selected_point_info == dict(time=.1, index=1)
    assert popup.cursor_line is not None
    path = tmp_path / 'whole-point.csv'
    monkeypatch.setattr(QFileDialog, 'getSaveFileName', lambda *_: (str(path), ''))
    results.export_point_button.click()
    saved = pd.read_csv(path, header=[0, 1, 2], index_col=0, encoding='utf-8', float_precision='round_trip')
    assert saved.columns.tolist() == frame.columns.tolist()
    assert saved.index.tolist() == [.1]
    assert saved[observed].iloc[0] == precise
    assert pd.isna(saved[missing].iloc[0])
    assert saved[text].iloc[0] == frame[text].iloc[1]
    assert str(precise).encode('ascii') in path.read_bytes()


def test_point_lifecycle_preserves_good_context_and_rejects_missing_replacement(results, tmp_path, monkeypatch):
    column = ('Velocity', 'CoM', 'Global_V_TX')
    frames = {
        'good': pd.DataFrame({RESULT_TIME_COL: [0., .1], column: [0., 1.]}),
        'missing': pd.DataFrame({RESULT_TIME_COL: [0., .1], column: [np.nan, np.nan]}),
        'bad': pd.DataFrame({RESULT_TIME_COL: [0., .1], column: ['bad', 'bad']}),
    }
    paths = {}
    for name, frame in frames.items():
        frame.columns = pd.MultiIndex.from_tuples(frame.columns)
        paths[name] = tmp_path / (name + '.proc')
        frame.to_csv(paths[name], index=False)
    assert results.load_result_file(str(paths['good']))
    results.checked_result_columns = {column}
    results.plot_selected_results()
    results.open_popup_current_selection()
    popup = next(iter(results.popup_windows.values()))
    click_result_canvas(popup.plot_manager, .1)
    original = results.result_data
    monkeypatch.setattr(QFileDialog, 'getOpenFileName', lambda *_: ('', ''))
    results.open_result_button.click()
    assert not results.load_result_file(str(paths['bad']))
    assert results.result_data is original
    assert results.selected_point_info == dict(time=.1, index=1)
    assert results.export_point_button.isEnabled() and popup.cursor_line is not None
    destination = tmp_path / 'sentinel.csv'
    destination.write_bytes(b'original sentinel')
    monkeypatch.setattr(QFileDialog, 'getSaveFileName', lambda *_: ('', ''))
    results.export_point_button.click()
    assert destination.read_bytes() == b'original sentinel'
    results.clear_selection()
    assert results.selected_point_info == dict(time=None, index=None)
    assert not results.export_point_button.isEnabled() and popup.cursor_line is None
    click_result_canvas(popup.plot_manager, .1)
    assert results.selected_point_info == dict(time=.1, index=1)
    assert results.load_result_file(str(paths['missing']))
    assert popup.result_data is results.result_data
    assert results.selected_point_info == dict(time=None, index=None)
    assert not results.export_point_button.isEnabled() and popup.cursor_line is None
    click_result_canvas(popup.plot_manager, .1)
    assert results.selected_point_info == dict(time=None, index=None)
    # Both direct export entry points reject even a stale programmatic point.
    results.selected_point_info = dict(time=.1, index=1)
    monkeypatch.setattr(QFileDialog, 'getSaveFileName', lambda *_: pytest.fail('No save dialog without observations'))
    with pytest.raises(ValueError, match='No valid recorded point'):
        results._prepare_scenario_payload()
    results.on_export_point_data_click()
    assert results.selected_point_info == dict(time=None, index=None)
    assert not results.export_scenario_button.isEnabled()
    assert destination.read_bytes() == b'original sentinel'
    results.selected_point_info = dict(time=.1, index=1)
    results.update_point_selection_ui()
    assert results.selected_point_info == dict(time=None, index=None)
    with pytest.raises(ValueError, match='no result samples'):
        results._prepare_result_data(frames['good'].iloc[:0])


def export_frame():
    names = ('BoxLocal_V_RX', 'BoxLocal_V_RY', 'BoxLocal_V_RZ',
             'BoxLocal_V_TX', 'BoxLocal_V_TY', 'BoxLocal_V_TZ')
    frame = pd.DataFrame({RESULT_TIME_COL: [0.1], **{
        ('Velocity', 'CoM', key): [value] for key, value in zip(names, (1., -2., 3., 4., -5., 6.))}})
    frame.columns = pd.MultiIndex.from_tuples(frame.columns)
    return frame


def setup_manual(widget):
    widget.selected_point_info = dict(time=.1, index=0)
    widget.offset_manual_checkbox.setChecked(True)
    widget.manual_height_checkbox.setChecked(True)
    for combo, corner in zip(widget.offset_combos, ('C1', 'C2', 'C3')):
        combo.setCurrentText(corner)
    for field, value in zip(widget.manual_height_inputs, ('0', '1.25', '2.5')):
        field.setText(value)
    widget.le_scene_name.setText('Trial_A')
    widget.le_run_time.setText('1.0')
    widget.le_time_step.setText('0.001')


def test_real_cae_ui_rest_selected_and_transitions(results):
    activate(results, export_frame())
    setup_manual(results)
    assert not results.use_selected_velocities_checkbox.isChecked()
    assert results.use_selected_velocities_checkbox.isEnabled()
    assert results._prepare_scenario_payload() == scenario_bytes(CAE_REST_GOLDEN)
    assert 'rest initial conditions' in results.scenario_origin_label.text()
    results.use_selected_velocities_checkbox.setChecked(True)
    assert results._prepare_scenario_payload() == scenario_bytes(CAE_MEASURED_GOLDEN)
    assert 'Mixed initial conditions' in results.scenario_origin_label.text()
    assert '0.1 s' in results.scenario_origin_label.text()
    results.manual_height_checkbox.setChecked(False)
    assert not results.use_selected_velocities_checkbox.isEnabled()
    assert not results.use_selected_velocities_checkbox.isChecked()
    results.manual_height_checkbox.setChecked(True)
    assert not results.use_selected_velocities_checkbox.isChecked()


def test_real_cae_missing_velocity_and_bad_height_preserve_destination(results, tmp_path, monkeypatch):
    activate(results, export_frame())
    setup_manual(results)
    path = tmp_path / 'sentinel.csv'
    path.write_bytes(b'original sentinel')
    monkeypatch.setattr(QFileDialog, 'getSaveFileName', lambda *_: (str(path), ''))
    missing = ('Velocity', 'CoM', 'BoxLocal_V_TX')
    results.result_data = results.result_data.drop(columns=[missing])
    results.use_selected_velocities_checkbox.setChecked(True)
    results.export_analysis_scenario()
    assert path.read_bytes() == b'original sentinel'
    results.use_selected_velocities_checkbox.setChecked(False)
    assert results._prepare_scenario_payload() == scenario_bytes(CAE_REST_GOLDEN)
    for value in ('', 'nan', 'inf', 'bad'):
        results.manual_height_inputs[1].setText(value)
        results.export_analysis_scenario()
        assert path.read_bytes() == b'original sentinel'


def test_actual_peaks_point_popup_selection_and_empty(results):
    column = ('Velocity', 'CoM', 'Global_V_TX')
    frame = pd.DataFrame({RESULT_TIME_COL: [0., .1, .2, .3], column: [-4., 3., -4., 1.]})
    frame.columns = pd.MultiIndex.from_tuples(frame.columns)
    activate(results, frame)
    assert results.selected_point_info == dict(time=None, index=None)
    results.checked_result_columns = {column}
    results.plot_selected_results()
    results.on_find_abs_max_click()
    assert results.selected_point_info == dict(time=0., index=0)
    assert results._get_selected_target_value() == -4.
    results.on_find_max_click()
    assert results.selected_point_info == dict(time=.1, index=1)
    results.on_find_min_click()
    assert results.selected_point_info == dict(time=0., index=0)
    results.open_popup_current_selection()
    popup = next(iter(results.popup_windows.values()))
    results.on_popup_point_selected(.19)
    assert results.selected_point_info == dict(time=.2, index=2)
    assert popup.selected_columns == [column]
    results.close_all_popups()
    assert not results.popup_windows and not results.close_all_popups_action.isEnabled()
    results.clear_selection()
    assert results.find_max_target_combo.count() == 0
    assert not results.export_point_button.isEnabled()
    for values in ([np.nan] * 4, ['bad'] * 4):
        frame[column] = values
        if values[0] == 'bad':
            with pytest.raises(ValueError, match='nonnumeric'):
                results._prepare_result_data(frame)
            assert results.selected_point_info['index'] is None
            continue
        activate(results, frame)
        results.checked_result_columns = {column}
        results.refresh_result_tree()
        assert not results.find_abs_max_button.isEnabled()
        results._select_time_by_xdata(.19)
        assert results.selected_point_info['index'] is None


@pytest.mark.parametrize('language', ['en', 'ko'])
@pytest.mark.parametrize('size,columns', [((1510,800),5), ((1100,720),3), ((820,600),2)])
def test_processing_real_cards_fonts_lock_and_splitter(app, monkeypatch, language, size, columns):
    monkeypatch.setattr(ui_language, 'preferred_language', lambda: language)
    ui_language.configure_language(app)
    page = WidgetSliceProcessing(DataLoader(), Parser(FACE_PREFIX_TO_INFO))
    try:
        page.resize(*size)
        page.show()
        QTest.qWait(20)
        assert (page.width(), page.height()) == size
        assert page.card_columns == columns
        assert page.context_group.isAncestorOf(page.log_output)
        assert not page.settings_scroll.isAncestorOf(page.log_output)
        assert page.settings_scroll.horizontalScrollBar().maximum() == 0
        assert not page.run_batch_button.isEnabled()
        assert page.rb_processing_raw.isChecked() and not page.cb_enable_resampling.isChecked()
        assert not page.processing_settings_button.isVisible()
        page.rb_processing_advanced.setChecked(True)
        assert page.processing_settings_button.isVisible()
        page._set_batch_controls_enabled(False)
        assert all(not field.isEnabled() for field in (page.input_mode_combo, page.select_data_button,
            page.rb_processing_raw, page.overwrite_proc_checkbox, page.processing_settings_button))
        page._set_batch_controls_enabled(True)
        page.workflow_splitter.setSizes([200,300])
        chosen = page.workflow_splitter.sizes()
        page.input_mode_combo.setCurrentIndex(1)
        page.input_mode_combo.setCurrentIndex(0)
        app.processEvents()
        assert page.workflow_splitter.sizes() == chosen
        axis = page.plot_manager.ax
        assert (axis.xaxis.label.get_fontsize(), axis.yaxis.label.get_fontsize()) == (9,9)
        axis.xaxis.label.set_fontsize(13)
        axis.yaxis.label.set_fontsize(14)
        page.update_plot()
        assert (axis.xaxis.label.get_fontsize(), axis.yaxis.label.get_fontsize()) == (13,14)
    finally:
        page.close()
        page.deleteLater()
        app.processEvents()


def test_result_axis_title_customization_survives_changes(results):
    column = ('Velocity', 'CoM', 'Global_V_TX')
    frame = pd.DataFrame({RESULT_TIME_COL:[0.,.1],column:[1.,2.]})
    frame.columns = pd.MultiIndex.from_tuples(frame.columns)
    activate(results,frame)
    results.plot_manager.ax.xaxis.label.set_fontsize(13)
    results.plot_manager.ax.yaxis.label.set_fontsize(14)
    results._draw_result_columns([column])
    activate(results,frame,'replacement.proc')
    assert results.plot_manager.ax.xaxis.label.get_fontsize() == 13
    assert results.plot_manager.ax.yaxis.label.get_fontsize() == 14


def test_resolved_corner_ties_are_visible_as_nonunique_category(results):
    activate(results, posture_frame(-30.))
    table = results.experiment_summary_table
    row = next(i for i in range(table.rowCount()) if table.item(i, 0).data(Qt.UserRole) == 'step2:summary:CminAtT1MinusIndex')
    assert table.item(row, 1).text() == 'Non-unique {C2,C6}'
    assert table.columnViewportPosition(1) + table.columnWidth(1) <= table.viewport().width()


def test_experiment_info_and_explicit_diagnostics_preserve_owner_values(app,tmp_path):
    from src.analysis.compare.main_window import CompareMainWindow
    page = CompareMainWindow()
    try:
        paths = []
        for name in ('a','b'):
            frame = metric_frame()
            path = tmp_path / (name + '.proc')
            frame.to_csv(path,index=False)
            paths.append(path)
        page.load_result_files([str(p) for p in paths])
        page.show()
        app.processEvents()
        before = page.model.get_impact_comparison()['statistics']
        control = page.control_panel
        assert 'Synthetic validation data' in control.details.toPlainText()
        assert not control.diagnostics_dialog
        assert all(str(p) not in control.file_list.item(i).toolTip() for i,p in enumerate(paths))
        assert all(str(p) not in (control.cb_baseline.itemData(i,Qt.ToolTipRole) or '') for i,p in enumerate(paths))
        control._open_diagnostics()
        assert str(paths[0]) in control.diagnostics_text.toPlainText()
        assert control.diagnostics_text.isReadOnly()
        page.table_panel.view_combo.setCurrentIndex(3)
        page.table_panel.table.setCurrentCell(1,0)
        app.processEvents()
        assert control.selected_file == paths[1].name
        assert 'Selected value' in control.details.toPlainText()
        assert 'Metric repeats n' in control.details.toPlainText()
        assert str(paths[1]) not in page.table_panel.table.item(1,0).toolTip()
        page.table_panel.view_combo.setCurrentIndex(4)
        row = list(page.table_panel._posture_data['files'][paths[1].name]['result'].metrics).index('max_height_range')
        page.table_panel.table.setCurrentCell(row,2)
        assert 'Evaluation window' in control.details.toPlainText()
        assert 'Evaluation time:' not in control.details.toPlainText()
        control.gap_limit.setValue(.02)
        assert page.model.max_gap_sec == .02
        assert page.model.get_impact_comparison()['statistics'] == before
    finally:
        page.close()
        page.deleteLater()
        app.processEvents()


def test_actual_raw_widget_transmits_current_recorded_coordinates(app):
    from src.analysis.ui.widget_raw_data_processing import WidgetRawDataProcessing
    from PySide6.QtWidgets import QDialog
    captured = {}
    class RejectedReview(MarkerFlipReviewDialog):
        def set_observation_context(self,*args,**kwargs):
            captured.update(kwargs)
            super().set_observation_context(*args,**kwargs)
        def exec(self):
            return QDialog.Rejected
    page = WidgetRawDataProcessing(DataLoader(),Parser(FACE_PREFIX_TO_INFO))
    try:
        page.marker_flip_dialog_factory = RejectedReview
        page._review_invalidated = True
        page._pending_review_context = '{}'
        page._pending_review_identity = None
        page.review_parsed_data = pd.DataFrame({f'F1_{a}':[0.,1.,2.] for a in 'XYZ'},index=[0.,.01,1.])
        page.header_info = {'export_metadata':{'Coordinate Space':'Global','Length Units':'Millimeters'}}
        page.review_header_info = None
        page._finish_marker_review([])
        assert captured['coordinate_system'] == 'Global' and captured['units'] == 'Millimeters'
        page.header_info = {'export_metadata':{}}
        page._finish_marker_review([])
        assert captured['coordinate_system'] == '' and captured['units'] == ''
    finally:
        page.close()
        page.deleteLater()
        app.processEvents()


def test_actual_customize_dialog_apply_and_redraw_preserves_text_sizes(results, app):
    from PySide6.QtWidgets import QDialog, QLineEdit, QDialogButtonBox
    column = ('Velocity', 'CoM', 'Global_V_TX')
    frame = pd.DataFrame({RESULT_TIME_COL:[0.,.1], column:[1.,2.]})
    frame.columns = pd.MultiIndex.from_tuples(frame.columns)
    activate(results, frame)
    results._draw_result_columns([column])
    axis = results.plot_manager.ax
    axis.xaxis.label.set_fontsize(13)
    axis.yaxis.label.set_fontsize(14)
    action = next(a for a in results.toolbar.actions() if a.text() == 'Customize')
    results.toolbar.widgetForAction(action).click()
    app.processEvents()
    dialog = next(w for w in QApplication.topLevelWidgets() if isinstance(w,QDialog) and w.isVisible() and w.windowTitle() == 'Figure options')
    field = next(w for w in dialog.findChildren(QLineEdit) if w.text() == 'Time (s)')
    field.setText('Recorded time (s)')
    buttons = dialog.findChild(QDialogButtonBox)
    buttons.button(QDialogButtonBox.Apply).click()
    assert axis.get_xlabel() == 'Recorded time (s)'
    buttons.button(QDialogButtonBox.Ok).click()
    results._draw_result_columns([column])
    assert (axis.xaxis.label.get_fontsize(),axis.yaxis.label.get_fontsize()) == (13,14)


@pytest.mark.parametrize('times', [[0.,.01,.02],[0.,.01,1.]])
def test_original_observation_points_never_bridge_unknown_cadence(app,times):
    frame = pd.DataFrame({f'F1_{axis}':[0.,i,100*i] for i,axis in enumerate('XYZ',1)},index=times)
    original = frame.copy(deep=True)
    dialog = MarkerFlipReviewDialog([])
    try:
        dialog.set_observation_context(frame,units='Millimeters',coordinate_system='Global')
        lines = dialog.context_figure.axes[0].lines
        assert len(lines) == 3
        for line in lines:
            assert line.get_linestyle() == 'None'
            assert line.get_marker() == '.'
            assert list(line.get_xdata()) == times
        assert 'Global' in dialog.recorded_context.text() and 'mm' in dialog.recorded_context.text()
        pd.testing.assert_frame_equal(frame,original)
    finally:
        dialog.close()


@pytest.mark.parametrize('language',['en','ko'])
def test_shared_guide_all_context_targets_filters_lifecycle_and_keyboard(app,monkeypatch,language):
    monkeypatch.setattr(ui_language,'preferred_language',lambda:language)
    ui_language.configure_language(app)
    dialog = MetricGuideDialog()
    try:
        assert isinstance(dialog,SharedMetricGuideDialog)
        assert isinstance(DropPostureMetricGuideDialog(get_drop_posture_summary_descriptors()),SharedMetricGuideDialog)
        dialog.resize(1100,760)
        dialog.show()
        QTest.qWait(20)
        identities = [entry.stable_id for entry in get_metric_registry()]
        assert len(identities) == len(set(identities)) == len(dialog.cards)
        for identity in identities:
            dialog.search.setText('hides-everything')
            dialog.classification.setCurrentIndex(3)
            dialog.focus_metric(identity)
            app.processEvents()
            assert dialog.focused_metric == identity
            assert dialog.tabs.currentIndex() == 0
            assert dialog.search.text() == '' and dialog.classification.currentIndex() == 0
            assert not dialog.cards[identity].isHidden()
        for field in ('T1Detected', 'ImpactEventCount'):
            dialog.focus_metric(guide_key_for_summary(field), context='compare')
            assert dialog.focused_metric == 'compare:summary:' + field
        dialog.focus_metric('does-not-exist')
        assert dialog.tabs.currentIndex() == 1
        dialog.search.setText('nothing-matches-this-definition')
        assert not dialog.empty_label.isHidden()
        dialog.focus_metric('step2:summary:TargetPostureError_deg')
        app.processEvents()
        assert dialog.cards[dialog.focused_metric].hasFocus()
        QTest.keyClick(dialog.cards[dialog.focused_metric],Qt.Key_Tab)
        assert dialog.focusWidget() is not None
        QTest.keyClick(dialog,Qt.Key_Escape)
        assert not dialog.isVisible()
        dialog.show()
        assert dialog.isVisible()
        dialog.close()
        assert not dialog.isVisible()
    finally:
        dialog.deleteLater()
        app.processEvents()


def test_real_public_raw_slice_proc_summary_guide_and_comparison_hop(app,tmp_path,monkeypatch):
    """User approved 11 actual fits per input; no optimized output is mocked."""
    import hashlib
    import json
    from scipy.spatial.transform import Rotation
    from gui_metric_parity_fixtures import generate_raw_metric_parity_inputs
    from src.analysis.pipeline.artifact_io import save_slice_file, add_timeline_context_columns
    from src.analysis.pipeline.pipeline_controller import PipelineController
    from src.analysis.pipeline import pose_optimizer as optimizer_module
    from src.analysis.compare.main_window import CompareMainWindow
    from src.config import config_app, config_analysis_ui
    from src.utils.artifact_metadata import read_identity

    packet = generate_raw_metric_parity_inputs(tmp_path / 'inputs')
    manifest_hash = hashlib.sha256(packet['manifest_path'].read_bytes()).hexdigest()
    limits = packet['manifest']['numerical_limits']
    optimizer_calls = []
    actual_minimize = optimizer_module.minimize
    def measured_minimize(*args,**kwargs):
        optimizer_calls.append(dict(method=kwargs.get('method'),maxiter=kwargs['options']['maxiter']))
        return actual_minimize(*args,**kwargs)
    monkeypatch.setattr(optimizer_module,'minimize',measured_minimize)
    old_dims, old_corners = config_app.BOX_DIMS.copy(), config_app.LOCAL_BOX_CORNERS.copy()
    receipt = dict(status='running',fixture_manifest_sha256=manifest_hash,
                   numerical_limits=limits,producer_policy='actual Raw; 11 included frames per input',cases=[])
    proc_paths = []
    comparison = None
    try:
        for case in packet['cases']:
            expected = case['expected']
            source = case['csv_path']
            source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
            loader = DataLoader()
            header, raw = loader.load_csv(str(source))
            assert len(raw) == 61 and header['export_metadata']['Length Units'] == 'Millimeters'
            slice_path = tmp_path / (case['id'] + '.slice')
            save_slice_file(filepath=str(slice_path),header_info=header,raw_data=raw,source_path=str(source),
                full_start=0.,full_end=1.2,user_start=.1,user_end=.3,
                box_dims=(200.,120.,80.),pad_rows=50)
            processing = WidgetSliceProcessing(loader,Parser(FACE_PREFIX_TO_INFO))
            results_page = WidgetResultsAnalyzer(loader)
            try:
                assert processing.load_slice_file(str(slice_path))
                requests = []
                processing.processing_requested.connect(lambda *args:requests.append(args))
                processing.emit_run_processing()
                assert len(requests) == 1
                config, _, _, parsed, context = requests[0]
                assert config['processing_mode'] == 'raw'
                assert config['analysis_options'] == config_analysis_ui.get_raw_mode_options()
                controller = PipelineController()
                assert controller.pose_optimizer.optimizer_options == limits['optimizer_options']
                before = len(optimizer_calls)
                processed = controller.process_parsed_data(config,parsed)
                processed = add_timeline_context_columns(processed,context)
                assert len(processed) == 11 and len(optimizer_calls)-before == 11
                processing.on_processing_finished(processed)
                proc_path = tmp_path / (case['id'] + '.proc')
                monkeypatch.setattr(QFileDialog,'getSaveFileName',lambda *_,path=proc_path:(str(path),''))
                assert processing.save_processed_result() == str(proc_path)
                assert proc_path.is_file()
                proc_paths.append(proc_path)
                assert results_page.load_result_file(str(proc_path))
                data = results_page.result_data
                np.testing.assert_allclose(data.index.to_numpy(float),expected['slice_times_s'],rtol=0,atol=1e-12)
                assert data[('Info','Pose','Source')].eq('Optimized').all()
                pose = data[[('Position','CoM','P_'+c) for c in ('TX','TY','TZ','RX','RY','RZ')]].to_numpy(float)
                actual_velocity = data[[('Velocity','CoM','Global_V_T'+a) for a in 'XYZ']].to_numpy(float)
                position_error = float(np.max(np.abs(pose[:,:3]-expected['slice_positions_mm'])))
                orientation_error = float(np.max((Rotation.from_rotvec(pose[:,3:]) *
                    Rotation.from_matrix(expected['rotation_matrix']).inv()).magnitude()))
                velocity_error = float(np.max(np.abs(actual_velocity[1:-1]-expected['world_velocity_mm_s'])))
                summary = results_page.resolved_summary
                record = dict(id=case['id'],source_sha256=source_hash,optimizer_calls=len(optimizer_calls)-before,
                    processed_rows=len(data),times_s=data.index.tolist(),
                    max_position_component_error_mm=position_error,
                    max_orientation_geodesic_error_rad=orientation_error,
                    max_interior_velocity_component_error_mm_s=velocity_error,
                    max_beta_deg=summary['MaxBetaDeg'].value,max_delta_h_mm=summary['MaxDeltaH_mm'].value,
                    contact_state=summary['ContactState'].value,contact_confidence=summary['ContactConfidence'].value)
                receipt['cases'].append(record)
                assert position_error <= limits['position_max_component_error_mm']
                assert orientation_error <= limits['orientation_geodesic_error_rad']
                assert velocity_error <= limits['interior_velocity_component_error_mm_s']
                for key in ('MaxBetaDeg','MaxAbsThetaLongDeg','MaxAbsThetaShortDeg'):
                    assert summary[key].value == pytest.approx(expected['posture'][key],abs=limits['whole_window_angle_error_deg'])
                assert summary['MaxDeltaH_mm'].value == pytest.approx(expected['posture']['MaxDeltaH_mm'],abs=limits['fixed_face_height_range_error_mm'])
                assert summary['ReferenceFace'].value == 'BOTTOM'
                assert summary['ContactState'].value == 'NoContact'
                assert summary['ImpactEventCount'].value == 0
                assert summary['ContactConfidence'].value == 0.
                assert summary['FinalFace'].value is None and summary['FinalFace'].reason
                for key in ('BetaAtT1MinusDeg','T1MinusTimeSec','VerticalVelAtT1Minus_mm_s',
                            'EquivalentFreeFallHeight_mm','TargetPostureError_deg'):
                    assert summary[key].value is None and summary[key].reason
                artifact = read_identity(data)
                for field,value in expected['artifact'].items():
                    assert artifact.values[field] == value
                invalid_metadata = data.copy()
                invalid_metadata[('Info','Artifact','BoxLengthMm')] = 201.
                from src.analysis.compare.summary_metrics import resolve_summary_metrics
                invalid_summary = resolve_summary_metrics(invalid_metadata)
                assert invalid_summary['MaxDeltaH_mm'].value is None and invalid_summary['MaxDeltaH_mm'].reason
                target = ('Analysis','DropPosture','BetaDeg')
                results_page.checked_result_columns = {target}
                results_page.refresh_result_tree()
                results_page.open_metric_guide()
                app.processEvents()
                assert results_page.metric_guide_dialog.focused_metric == 'step2:series:Analysis:DropPosture:BetaDeg'
                assert hashlib.sha256(source.read_bytes()).hexdigest() == source_hash
            finally:
                processing.close()
                results_page.close()
                processing.deleteLater()
                results_page.deleteLater()
                QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete)
                app.processEvents()
        assert len(optimizer_calls) == 22
        assert hashlib.sha256(packet['manifest_path'].read_bytes()).hexdigest() == manifest_hash
        comparison = CompareMainWindow()
        comparison.load_result_files([str(path) for path in proc_paths])
        assert len(comparison.model.datasets) == 2
        assert all(identity.source_kind == 'handcrafted_dummy' for identity in comparison.model.identities.values())
        posture = comparison.model.get_posture_comparison()
        assert posture['statistics']['max_height_range']['n'] == 0
        assert all(data['result'].metrics['max_height_range'].value is not None for data in posture['files'].values())
        assert any(data['reasons'] for data in posture['files'].values())
        receipt.update(status='passed',optimizer_calls_total=len(optimizer_calls),comparison_files=2,
                       repeat_n=0,experimental_repeat_claim=False)
    except Exception as error:
        receipt.update(status='failed',failure=str(error))
        raise
    finally:
        if comparison is not None:
            comparison.close()
            comparison.deleteLater()
        config_app.BOX_DIMS,config_app.LOCAL_BOX_CORNERS = old_dims,old_corners
        (tmp_path/'pipeline_hop_receipt.json').write_text(json.dumps(receipt,indent=2,default=float,allow_nan=False)+'\n',encoding='utf-8')
        QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete)
        app.processEvents()


@pytest.mark.parametrize('language',['en','ko'])
def test_real_point_combo_series_contexts_reuse_one_explicit_card(app,monkeypatch,language):
    monkeypatch.setattr(ui_language,'preferred_language',lambda:language)
    ui_language.configure_language(app)
    page = WidgetResultsAnalyzer(DataLoader())
    columns = [('Analysis','DropPosture','BetaDeg'),('Velocity','CoM','Global_V_TY'),
        ('Velocity','CoM','BoxLocal_V_TX'),('Position','CoM','P_RX'),
        ('Analysis','DropPosture','CminIndex'),('Analysis','C1','RelativeHeight')]
    frame = pd.DataFrame({RESULT_TIME_COL:[0.,.1],**{column:[np.nan,np.nan] for column in columns}})
    frame.columns = pd.MultiIndex.from_tuples(frame.columns)
    try:
        activate(page,frame)
        page.checked_result_columns = set(columns)
        page.refresh_result_tree()
        original_count = len(get_metric_registry())
        previous_identity = None
        for column in columns:
            index = next(i for i in range(page.find_max_target_combo.count()) if tuple(page.find_max_target_combo.itemData(i)) == column)
            page.find_max_target_combo.setCurrentIndex(index)
            page.open_metric_guide()
            app.processEvents()
            dialog = page.metric_guide_dialog
            identity = 'step2:series:' + ':'.join(column)
            assert dialog.focused_metric == identity
            assert dialog.tabs.currentIndex() == 0
            assert len(dialog.cards) == original_count + 1
            if previous_identity:
                assert previous_identity not in dialog.cards
            descriptor = next(entry for entry in dialog.entries if entry.stable_id == identity)
            assert descriptor.context == 'step2:series' and descriptor.column == column
            if language == 'ko':
                assert any('\uac00' <= char <= '\ud7a3' for char in descriptor.label_ko)
            assert 'precontact snapshot' in descriptor.caution
            previous_identity = identity
        page.find_max_target_combo.addItem('unsupported',('Info','Unknown','Unknown'))
        page.find_max_target_combo.setCurrentIndex(page.find_max_target_combo.count()-1)
        page.open_metric_guide()
        assert page.metric_guide_dialog.focused_metric is None
        assert page.metric_guide_dialog.tabs.currentIndex() == 1
        assert len(page.metric_guide_dialog.cards) == original_count
    finally:
        page.close()
        page.deleteLater()
        QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete)
        app.processEvents()
