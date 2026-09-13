"""Saved-result identity regressions; synthetic traces are not ISTA accuracy evidence."""
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QFileDialog

from src.analysis.pipeline.data_loader import DataLoader
from src.analysis.ui.widget_results_analyzer import WidgetResultsAnalyzer
from src.config.data_columns import HeaderL1, HeaderL2, HeaderL3, RESULT_TIME_COL


BETA = (HeaderL1.ANALYSIS, HeaderL2.DROP_POSTURE, HeaderL3.DROP_BETA_DEG)
THETA = (HeaderL1.ANALYSIS, HeaderL2.DROP_POSTURE, HeaderL3.DROP_THETA_LONG_DEG)
HEIGHT = (HeaderL1.POS, HeaderL2.COM, HeaderL3.P_TY)


def _save_result(path, times, beta=None, height=None, theta=None):
    values = {RESULT_TIME_COL: np.asarray(times)}
    for column, data in ((BETA, beta), (HEIGHT, height), (THETA, theta)):
        if data is not None:
            values[column] = data
    frame = pd.DataFrame(values)
    frame.columns = pd.MultiIndex.from_tuples(frame.columns)
    frame.to_csv(path, index=False)
    return frame


@pytest.fixture
def results(tmp_path):
    times_a = np.arange(243) / 100
    angles_a = np.interp(times_a, [0., 1.21, 2.42], [0., 15., 0.])
    times_b = 1. + np.arange(27) / 100
    angles_b = np.linspace(0., 1.e-5, 27)
    a, b = tmp_path / 'tilt.proc', tmp_path / 'fall.proc'
    _save_result(a, times_a, angles_a, 100. + angles_a, angles_a)
    _save_result(b, times_b, angles_b, 250. - (times_b - 1.) ** 2, angles_b)
    return SimpleNamespace(a=a, b=b, times_a=times_a, times_b=times_b,
                           angles_a=angles_a, angles_b=angles_b)


@pytest.fixture
def widget():
    app = QApplication.instance() or QApplication([])
    window = WidgetResultsAnalyzer(DataLoader())
    yield window
    window.close_all_popups()
    window.close()
    window.deleteLater()
    app.processEvents()


def _select_point(widget, time):
    widget.on_result_plot_click(SimpleNamespace(inaxes=widget.plot_manager.ax, xdata=time))


def _assert_curve(manager, times, values):
    assert len(manager.ax.lines) == 1
    np.testing.assert_allclose(manager.ax.lines[0].get_xdata(), times)
    np.testing.assert_allclose(manager.ax.lines[0].get_ydata(), values)


def test_switch_redraws_new_file_resets_cursor_and_exports_new_sample(widget, results, tmp_path, monkeypatch):
    assert widget.load_result_file(str(results.a))
    assert widget.checked_result_columns == {BETA}
    _assert_curve(widget.plot_manager, results.times_a, results.angles_a)
    widget.open_popup_current_selection()
    popup = next(iter(widget.popup_windows.values()))
    _select_point(widget, 1.21)
    assert widget.export_point_button.isEnabled() and widget.export_scenario_button.isEnabled()
    assert popup.cursor_line is not None

    assert widget.load_result_file(str(results.b))
    assert widget.context_rows_label.text() == '27'
    assert widget.result_file_list.currentItem().text() == 'fall.proc'
    assert widget.context_active_file_label.text() == 'fall.proc'
    _assert_curve(widget.plot_manager, results.times_b, results.angles_b)
    _assert_curve(popup.plot_manager, results.times_b, results.angles_b)
    assert popup.result_data is widget.result_data
    assert widget.selected_point_info == {'time': None, 'index': None}
    assert widget.result_point_cursor is None and popup.cursor_line is None
    assert not widget.export_point_button.isEnabled() and not widget.export_scenario_button.isEnabled()

    _select_point(widget, results.times_b[13])
    exported = tmp_path / 'selected.csv'
    suggestions = []

    def choose_output(_parent, _caption, suggested, _filter):
        suggestions.append(suggested)
        return str(exported), ''

    monkeypatch.setattr(QFileDialog, 'getSaveFileName', choose_output)
    widget.on_export_point_data_click()
    saved = pd.read_csv(exported, header=[0, 1, 2], index_col=0)
    assert suggestions == ['fall_point_at_1_130s.csv']
    np.testing.assert_allclose(saved.index, [results.times_b[13]])
    np.testing.assert_allclose(saved[BETA], [results.angles_b[13]])


def test_checked_and_plotted_metrics_survive_search_and_switch_separately(widget, results):
    assert widget.load_result_file(str(results.a))
    widget.clear_selection()
    for _top, _mid, leaf in widget._iter_leaf_items():
        if tuple(leaf.data(0, Qt.ItemDataRole.UserRole)) == THETA:
            leaf.setCheckState(0, Qt.Checked)
    widget.plot_selected_results()
    for _top, _mid, leaf in widget._iter_leaf_items():
        if tuple(leaf.data(0, Qt.ItemDataRole.UserRole)) == HEIGHT:
            leaf.setCheckState(0, Qt.Checked)
    widget.selection_search_input.setText('no matching metric')
    assert widget.result_data_tree.topLevelItemCount() == 0
    assert widget.load_result_file(str(results.b))
    assert widget.checked_result_columns == {THETA, HEIGHT}
    assert widget.last_selected_result_columns == {THETA}
    _assert_curve(widget.plot_manager, results.times_b, results.angles_b)
    widget.selection_search_input.clear()
    checked_leaves = {tuple(leaf.data(0, Qt.ItemDataRole.UserRole))
                      for _top, _mid, leaf in widget._iter_leaf_items()
                      if leaf.checkState(0) == Qt.Checked}
    assert checked_leaves == {THETA, HEIGHT}


def test_absent_selected_metric_clears_main_and_popup_without_unrequested_fallback(widget, results, tmp_path):
    assert widget.load_result_file(str(results.a))
    widget.open_popup_current_selection()
    popup = next(iter(widget.popup_windows.values()))
    only_height = tmp_path / 'height.proc'
    _save_result(only_height, [4., 4.1], height=[300., 290.])
    assert widget.load_result_file(str(only_height))
    assert not widget.checked_result_columns and not widget.last_selected_result_columns
    assert not widget.plot_manager.ax.lines and not popup.plot_manager.ax.lines
    assert popup.selected_columns == [] and popup.result_data is widget.result_data


@pytest.mark.parametrize('height,expected', [([300., 290.], {HEIGHT}), (None, set())])
def test_initial_default_uses_height_only_when_beta_unavailable(widget, tmp_path, height, expected):
    path = tmp_path / 'no_angle.proc'
    _save_result(path, [4., 4.1], height=height)
    assert widget.load_result_file(str(path))
    assert widget.checked_result_columns == expected
    if height is None:
        assert not widget.plot_manager.ax.lines
    else:
        _assert_curve(widget.plot_manager, [4., 4.1], height)


def test_failed_load_missing_file_and_cancel_preserve_active_result(widget, results, tmp_path, monkeypatch):
    malformed = tmp_path / 'bad.proc'
    malformed.write_text('not a saved result\n', encoding='utf-8')
    assert widget.load_result_file(str(results.a))
    widget.open_popup_current_selection()
    popup = next(iter(widget.popup_windows.values()))
    _select_point(widget, 1.21)
    previous_data = widget.result_data
    previous_lines = list(widget.plot_manager.ax.lines)
    previous_popup_lines = list(popup.plot_manager.ax.lines)
    previous_cursor = widget.result_point_cursor
    # Item selection moves before itemClicked dispatch; failed loading must
    # restore that selection as well as retaining the original plotted values.
    failed_item = next(widget.result_file_list.item(i) for i in range(widget.result_file_list.count())
                       if widget.result_file_list.item(i).text() == 'bad.proc')
    widget.result_file_list.setCurrentItem(failed_item)
    widget.on_result_file_selected(failed_item)
    assert not widget.load_result_file(str(tmp_path / 'missing.proc'))
    assert not widget.load_result_file('')
    monkeypatch.setattr(QFileDialog, 'getExistingDirectory', lambda *_args: '')
    widget.select_result_folder()
    assert widget.result_data is previous_data
    assert widget.current_result_file == str(results.a)
    assert widget.result_file_list.currentItem().text() == 'tilt.proc'
    assert widget.context_active_file_label.text() == 'tilt.proc'
    assert widget.context_rows_label.text() == '243'
    assert list(widget.plot_manager.ax.lines) == previous_lines
    assert list(popup.plot_manager.ax.lines) == previous_popup_lines
    assert widget.result_point_cursor is previous_cursor
    assert widget.selected_point_info == {'time': 1.21, 'index': 121}
    assert widget.export_point_button.isEnabled() and widget.export_scenario_button.isEnabled()


def test_invalid_time_does_not_replace_active_physical_time_axis(widget, results, tmp_path):
    assert widget.load_result_file(str(results.a))
    duplicate_time = tmp_path / 'duplicate_time.proc'
    _save_result(duplicate_time, [1., 1.], beta=[3., 4.])
    assert not widget.load_result_file(str(duplicate_time))
    assert widget.current_result_file == str(results.a)
    _assert_curve(widget.plot_manager, results.times_a, results.angles_a)


def test_direct_result_csv_open_selects_only_the_validated_csv(widget, tmp_path):
    result_csv = tmp_path / 'saved_result.csv'
    _save_result(result_csv, [1., 1.1], beta=[0., 5.])
    (tmp_path / 'unrelated.csv').write_text('not a result', encoding='utf-8')
    assert widget.load_result_file(str(result_csv))
    assert widget.result_file_list.currentItem().text() == 'saved_result.csv'
    assert widget.result_file_list.count() == 1
    assert widget.current_result_file == str(result_csv)
    _assert_curve(widget.plot_manager, [1., 1.1], [0., 5.])


def test_nonnumeric_metric_rejected_before_replacing_selected_result(widget, tmp_path):
    old, bad, gap = (tmp_path / name for name in ('old.proc', 'bad.proc', 'gap.proc'))
    _save_result(old, [0., .1, .2, .3, .4], beta=[0., 5., 15., 5., 0.])
    _save_result(bad, [0., .1, .2], beta=['15', 'bad', np.nan])
    _save_result(gap, [0., .1, .2], beta=[15., np.nan, 0.])
    assert widget.load_result_file(str(old))
    widget.open_popup_current_selection()
    popup = next(iter(widget.popup_windows.values()))
    _select_point(widget, .4)
    previous_data = widget.result_data
    lines = list(widget.plot_manager.ax.lines)
    popup_lines = list(popup.plot_manager.ax.lines)
    assert not widget.load_result_file(str(bad))
    assert widget.result_data is previous_data and widget.current_result_file == str(old)
    assert widget.result_file_list.currentItem().text() == 'old.proc'
    assert widget.selected_point_info == {'time': .4, 'index': 4}
    assert widget.export_point_button.isEnabled() and widget.export_scenario_button.isEnabled()
    assert list(widget.plot_manager.ax.lines) == lines
    assert list(popup.plot_manager.ax.lines) == popup_lines
    # Genuine tracking gaps remain missing samples, not invalid text or zeros.
    assert widget.load_result_file(str(gap))
    _assert_curve(widget.plot_manager, [0., .1, .2], [15., np.nan, 0.])


def test_display_failure_restores_main_popup_and_selected_point(widget, results, monkeypatch):
    assert widget.load_result_file(str(results.a))
    widget.open_popup_current_selection()
    popup = next(iter(widget.popup_windows.values()))
    _select_point(widget, 1.21)
    widget.plot_manager.ax.set_xlim(.5, 1.5)
    previous_data = widget.result_data
    original_draw = popup.set_plot_data

    def fail_candidate_once(data, columns):
        if len(data) == 27:
            raise RuntimeError('injected popup rendering failure after main plot changed')
        original_draw(data, columns)

    monkeypatch.setattr(popup, 'set_plot_data', fail_candidate_once)
    assert not widget.load_result_file(str(results.b))
    assert widget.result_data is previous_data and widget.current_result_file == str(results.a)
    assert widget.context_rows_label.text() == '243'
    assert widget.result_file_list.currentItem().text() == 'tilt.proc'
    assert widget.checked_result_columns == {BETA} and popup.selected_columns == [BETA]
    assert widget.selected_point_info == {'time': 1.21, 'index': 121}
    assert widget.export_point_button.isEnabled() and widget.export_scenario_button.isEnabled()
    np.testing.assert_allclose(widget.plot_manager.ax.lines[0].get_ydata(), results.angles_a)
    np.testing.assert_allclose(popup.plot_manager.ax.lines[0].get_ydata(), results.angles_a)
    np.testing.assert_allclose(widget.plot_manager.ax.get_xlim(), [.5, 1.5])
    assert popup.result_data is previous_data
    assert widget.result_point_cursor is not None and popup.cursor_line is not None


def test_selecting_empty_folder_clears_every_active_result_context(widget, results, tmp_path, monkeypatch):
    assert widget.load_result_file(str(results.a))
    widget.open_popup_current_selection()
    _select_point(widget, 1.21)
    empty_folder = tmp_path / 'empty'
    empty_folder.mkdir()
    monkeypatch.setattr(QFileDialog, 'getExistingDirectory', lambda *_args: str(empty_folder))
    widget.select_result_folder()
    assert widget.current_result_file is None and widget.result_data is None
    assert widget.result_file_list.count() == 0
    assert widget.result_folder_path_label.text() == str(empty_folder)
    assert not widget.popup_windows and not widget.plot_manager.ax.lines
    assert widget.result_point_cursor is None
    assert widget.selected_point_info == {'time': None, 'index': None}
    assert not widget.checked_result_columns and not widget.last_selected_result_columns
    assert not widget.export_point_button.isEnabled() and not widget.export_scenario_button.isEnabled()
    assert widget.context_rows_label.text() == 'N/A'
