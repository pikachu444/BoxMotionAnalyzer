import pandas as pd
from PySide6.QtCore import Signal
from PySide6.QtWidgets import QDialog, QVBoxLayout
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qtagg import NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure

from src.analysis.core.plot_manager import PlotManager


class PlotPopupDialog(QDialog):
    point_selected = Signal(float)

    def __init__(self, window_name: str, parent=None):
        super().__init__(parent)
        self.window_name = window_name
        self.selected_columns: list[tuple] = []
        self.result_data: pd.DataFrame | None = None
        self.cursor_line = None

        self.setWindowTitle(f"Popup Plot - {window_name}")
        self.resize(1000, 700)

        layout = QVBoxLayout(self)
        self.canvas = FigureCanvas(Figure(figsize=(9, 6), dpi=100))
        self.toolbar = NavigationToolbar(self.canvas, self)
        layout.addWidget(self.toolbar)
        layout.addWidget(self.canvas)

        self.plot_manager = PlotManager(self.canvas, self.canvas.figure)
        self.canvas.mpl_connect('button_press_event', self._on_plot_click)

    def set_plot_data(self, result_data: pd.DataFrame, selected_columns: list[tuple]):
        self.result_data = result_data
        self.selected_columns = selected_columns

        if result_data is None or result_data.empty or not selected_columns:
            self.plot_manager.draw_plot(None, [])
            return

        available_columns = [col for col in selected_columns if col in result_data.columns]
        if not available_columns:
            self.plot_manager.draw_plot(None, [])
            return

        plot_df = result_data[available_columns].copy()
        self.plot_manager.draw_plot(plot_df, available_columns)
        self.plot_manager.ax.set_title(f"Popup Plot - {self.window_name}")
        self.plot_manager.canvas.draw_idle()

    def set_selected_time_cursor(self, selected_time):
        if self.cursor_line is not None:
            try:
                self.cursor_line.remove()
            except Exception:
                pass
            self.cursor_line = None

        if selected_time is None:
            self.plot_manager.canvas.draw_idle()
            return

        self.cursor_line = self.plot_manager.ax.axvline(
            x=selected_time, color='r', linestyle='--', linewidth=1
        )
        self.plot_manager.canvas.draw_idle()

    def _on_plot_click(self, event):
        if self.result_data is None or self.result_data.empty:
            return
        if event.inaxes != self.plot_manager.ax or event.xdata is None:
            return

        nearest_idx = self.result_data.index.get_indexer([event.xdata], method='nearest')
        if nearest_idx.size == 0 or nearest_idx[0] < 0:
            return

        selected_time = self.result_data.index[nearest_idx[0]]
        self.point_selected.emit(float(selected_time))
