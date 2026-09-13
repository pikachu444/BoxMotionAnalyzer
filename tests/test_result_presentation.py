"""Display real-valued angles and corner identities without changing saved samples."""
from types import SimpleNamespace
import hashlib

import numpy as np
import pandas as pd
import pytest
from matplotlib.backend_bases import MouseEvent
from matplotlib.figure import Figure
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from PySide6.QtWidgets import QApplication, QFileDialog

from src.analysis.pipeline.data_loader import DataLoader
from src.analysis.ui.plot_manager import PlotManager
from src.analysis.ui.widget_results_analyzer import WidgetResultsAnalyzer
from src.config.data_columns import RESULT_TIME_COL, get_result_column_unit


BETA = ('Analysis', 'DropPosture', 'BetaDeg')
CORNER = ('Analysis', 'DropPosture', 'CminIndex')


@pytest.fixture
def app():
    return QApplication.instance() or QApplication([])


def _write(path, values):
    frame = pd.DataFrame(values)
    frame.columns = pd.MultiIndex.from_tuples(frame.columns)
    frame.to_csv(path, index=False)


def test_corner_selection_export_and_failed_switch_preserve_category_context(app, tmp_path, monkeypatch):
    source = tmp_path / 'tilt.proc'
    times = [0., .01, .02, .03]
    _write(source, {RESULT_TIME_COL: times, BETA: [1e-6, 2e-6, np.nan, 3e-6],
                    CORNER: [1., 5., 2.5, np.nan]})
    original_hash = hashlib.sha256(source.read_bytes()).hexdigest()
    window = WidgetResultsAnalyzer(DataLoader())
    try:
        assert window.load_result_file(str(source))
        window.checked_result_columns = {BETA, CORNER}
        window.refresh_result_tree()
        window.plot_selected_results()
        manager = window.plot_manager
        assert len(manager.axes) == 2
        corner_line, = manager.category_ax.lines
        assert corner_line.get_linestyle() == 'None' and corner_line.get_marker() == 'o'
        np.testing.assert_array_equal(corner_line.get_ydata(), [1., 5., np.nan, np.nan])
        assert [tick.get_text() for tick in manager.category_ax.get_yticklabels()] == [f'C{i}' for i in range(1, 9)]
        assert manager.ax.get_ylim() == (0., 1.)
        np.testing.assert_array_equal(manager.ax.lines[0].get_ydata(), [1e-6, 2e-6, np.nan, 3e-6])
        assert window.result_data[CORNER].iloc[2] == 2.5

        window.find_max_target_combo.setCurrentIndex(window.find_max_target_combo.findData(CORNER))
        assert not any(button.isEnabled() for button in
                       (window.find_max_button, window.find_min_button, window.find_abs_max_button))
        window.on_result_plot_click(SimpleNamespace(inaxes=manager.category_ax, xdata=.01))
        assert window.selected_point_label.text() == '0.010 s: C5'
        selected = window.selected_point_info.copy()
        window.on_find_max_click()
        assert window.selected_point_info == selected
        manager.canvas.draw()
        px, py = manager.category_ax.transData.transform((.01, 5.))
        manager._on_hover(MouseEvent('motion_notify_event', manager.canvas, px, py))
        assert manager.annot.get_visible() and manager.annot.get_text().endswith('\nC5')

        exported = tmp_path / 'point.csv'
        monkeypatch.setattr(QFileDialog, 'getSaveFileName', lambda *_: (str(exported), ''))
        window.on_export_point_data_click()
        saved = pd.read_csv(exported, header=[0, 1, 2], index_col=0)
        assert saved[CORNER].iloc[0] == 5. and saved.index[0] == .01
        window.on_result_plot_click(SimpleNamespace(inaxes=manager.category_ax, xdata=.02))
        assert window.selected_point_label.text() == '0.020 s: Unknown'
        window.on_export_point_data_click()
        assert pd.read_csv(exported, header=[0, 1, 2], index_col=0)[CORNER].iloc[0] == 2.5

        window.open_popup_current_selection()
        popup = next(iter(window.popup_windows.values()))
        assert len(popup.plot_manager.axes) == 2
        popup._on_plot_click(SimpleNamespace(inaxes=popup.plot_manager.category_ax, xdata=.01))
        assert window.selected_point_label.text() == '0.010 s: C5'
        manager.category_ax.set_ylim(.8, 5.2)
        popup.plot_manager.category_ax.set_ylim(.6, 6.2)
        old_draw = popup.set_plot_data
        def fail_new_result(data, columns):
            if len(data) == 2:
                raise RuntimeError('New result cannot be rendered')
            old_draw(data, columns)
        monkeypatch.setattr(popup, 'set_plot_data', fail_new_result)
        new_file = tmp_path / 'new.proc'
        _write(new_file, {RESULT_TIME_COL: [1., 1.1], BETA: [10., 15.]})
        assert not window.load_result_file(str(new_file))
        assert window.current_result_file == str(source)
        assert manager.category_ax.get_ylim() == (.8, 5.2)
        assert popup.plot_manager.category_ax.get_ylim() == (.6, 6.2)
        assert window.selected_point_label.text() == '0.010 s: C5'
        monkeypatch.setattr(popup, 'set_plot_data', old_draw)
        assert window.load_result_file(str(new_file))
        assert len(manager.axes) == len(popup.plot_manager.axes) == 1
        assert window.find_max_button.isEnabled()
        assert hashlib.sha256(source.read_bytes()).hexdigest() == original_hash
    finally:
        window.close_all_popups()
        window.close()
        window.deleteLater()
        app.processEvents()


@pytest.mark.parametrize('column,unit,minimum', [
    (('Analysis', 'DropPosture', 'ThetaLongDeg'), '°', 1.),
    (('Position', 'CoM', 'P_RX'), 'rad', np.pi / 180.),
    (('Velocity', 'CoM', 'Global_V_RX'), 'rad/s', None),
    (('Acceleration', 'CoM', 'BoxLocal_A_RX'), 'rad/s²', None),
    (('Position', 'CoM', 'P_TX'), 'mm', None),
])
def test_default_scale_respects_metric_units_and_keeps_samples_and_zoom(app, column, unit, minimum):
    canvas = FigureCanvasQTAgg(Figure())
    manager = PlotManager(canvas, canvas.figure)
    values = np.array([1e-7, 2e-7, 3e-7])
    manager.draw_plot(pd.DataFrame({column: values}, index=[0., .1, .2]), [column])
    assert get_result_column_unit(column) == unit
    assert unit in manager.ax.get_ylabel()
    np.testing.assert_array_equal(manager.ax.lines[0].get_ydata(), values)
    width = np.diff(manager.ax.get_ylim())[0]
    if minimum is None:
        assert width < 1e-5
    else:
        assert width == pytest.approx(minimum)
    manager.ax.set_ylim(1e-7, 2e-7)
    manager._on_resize(None)
    assert manager.ax.get_ylim() == (1e-7, 2e-7)
    manager.draw_plot(None, [])
    manager._on_hover(SimpleNamespace(inaxes=None))
    canvas.close()
