"""GUI-07 contracts with synthetic samples, not CAE physical validation."""
from types import SimpleNamespace

import pandas as pd
import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QFileDialog, QScrollArea

from src.analysis.pipeline.data_loader import DataLoader
from src.analysis.pipeline.scenario_export import scenario_text
from src.analysis.ui.widget_results_analyzer import WidgetResultsAnalyzer
from src.config.data_columns import HeaderL1, HeaderL2, HeaderL3, RESULT_TIME_COL
from src.config.result_metric_descriptors import get_drop_posture_summary_descriptors


BETA = (HeaderL1.ANALYSIS, HeaderL2.DROP_POSTURE, HeaderL3.DROP_BETA_DEG)
HEIGHT = (HeaderL1.POS, HeaderL2.COM, HeaderL3.P_TY)


@pytest.fixture
def page():
    app = QApplication.instance() or QApplication([])
    widget = WidgetResultsAnalyzer(DataLoader())
    widget.resize(820, 600)
    widget.show()
    app.processEvents()
    yield widget
    widget.close_all_popups()
    widget.close()
    widget.deleteLater()
    app.processEvents()


def write_result(path, columns):
    frame = pd.DataFrame({RESULT_TIME_COL: [0.0, 0.1, 0.2], **columns})
    frame.columns = pd.MultiIndex.from_tuples(frame.columns)
    frame.to_csv(path, index=False)


def test_r01_cancel_failure_and_missing_columns(page, tmp_path, monkeypatch):
    source, reduced, bad = (tmp_path / name for name in ('source.proc', 'reduced.proc', 'bad.proc'))
    write_result(source, {BETA: [1., 2., 3.], HEIGHT: [5., 4., 3.]})
    write_result(reduced, {HEIGHT: [3., 2., 1.]})
    bad.write_text('invalid', encoding='utf8')
    assert page.open_result_files([str(source)])
    page.open_popup_current_selection()
    popup = next(iter(page.popup_windows.values()))
    page.on_result_plot_click(SimpleNamespace(inaxes=page.plot_manager.ax, xdata=.1))
    previous_data, previous_cursor = page.result_data, page.result_point_cursor
    previous_lines = list(page.plot_manager.ax.lines)
    monkeypatch.setattr(QFileDialog, 'getOpenFileName', lambda *_: ('', ''))
    page.open_result_file()
    assert not page.load_result_file(str(bad))
    assert page.result_data is previous_data and page.result_point_cursor is previous_cursor
    assert page.selected_point_info == {'time': .1, 'index': 1}
    assert page.checked_result_columns == {BETA}
    assert list(page.plot_manager.ax.lines) == previous_lines
    assert next(iter(page.popup_windows.values())) is popup

    assert page.load_result_file(str(reduced), preserve_selection=True)
    assert page.checked_result_columns == set()
    assert page.last_selected_result_columns == set()
    assert popup.selected_columns == []


def test_r02_fixed_buttons_and_real_export(page, tmp_path, monkeypatch):
    source = tmp_path / 'source.proc'
    write_result(source, {BETA: [1., 2., 3.]})
    assert page.load_result_file(str(source))
    page.on_result_plot_click(SimpleNamespace(inaxes=page.plot_manager.ax, xdata=.1))
    page.tool_tabs.setCurrentIndex(1)
    QApplication.processEvents()
    scroll = page.tool_tabs.currentWidget().findChild(QScrollArea)
    assert scroll is not None
    assert not scroll.isAncestorOf(page.export_scenario_button)
    assert page.export_scenario_button.isVisible()
    assert page.rect().contains(page.export_scenario_button.mapTo(page, page.export_scenario_button.rect().bottomRight()))
    for field in (*page.offset_combos, *page.manual_height_inputs,
                  page.le_run_time, page.le_time_step, page.le_scene_name):
        scroll.ensureWidgetVisible(field)
        QApplication.processEvents()
        top_left = field.mapTo(scroll.viewport(), field.rect().topLeft())
        bottom_right = field.mapTo(scroll.viewport(), field.rect().bottomRight())
        assert scroll.viewport().rect().contains(top_left)
        assert scroll.viewport().rect().contains(bottom_right)
    page.offset_manual_checkbox.setChecked(True)
    page.manual_height_checkbox.setChecked(True)
    for widget, value in zip(page.manual_height_inputs, ('1.25', '2.5', '3.75')):
        widget.setText(value)
    page.le_scene_name.setText('synthetic')
    page.le_run_time.setText('0.2')
    page.le_time_step.setText('1e-6')
    destination = tmp_path / 'scenario.csv'
    monkeypatch.setattr(QFileDialog, 'getSaveFileName', lambda *_: (str(destination), ''))
    page.export_analysis_scenario()
    offsets = [(combo.currentText(), float(value.text()))
               for combo, value in zip(page.offset_combos, page.manual_height_inputs)]
    velocities = {key: 0.0 for key in ('ANG_VEL_X', 'ANG_VEL_Y', 'ANG_VEL_Z',
                                        'TRA_VEL_X', 'TRA_VEL_Y', 'TRA_VEL_Z')}
    assert destination.read_text() == scenario_text(offsets, velocities, 'synthetic', '0.2', '1e-6')


def test_layout_and_guide_reuse(page):
    assert page.size().width() == 820
    assert page.results_splitter.count() == 3
    assert page.plot_splitter.count() == 2
    assert page.tool_tabs.currentIndex() == 0
    assert page.toolbar.orientation() == Qt.Orientation.Vertical
    page.open_metric_guide()
    dialog = page.metric_guide_dialog
    target = get_drop_posture_summary_descriptors()[-1]
    page.find_max_target_combo.addItem('metric', target.column)
    page.open_metric_guide()
    QApplication.processEvents()
    assert page.metric_guide_dialog is dialog
    scroll = dialog.findChild(QScrollArea)
    assert scroll.verticalScrollBar().value() > 0
    page.find_max_target_combo.clear()
    page.open_metric_guide()
    assert scroll.verticalScrollBar().value() == 0
    dialog.close()
