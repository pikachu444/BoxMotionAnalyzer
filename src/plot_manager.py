import matplotlib.pyplot as plt
from matplotlib.figure import Figure
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.widgets import SpanSelector
import pandas as pd
from PySide6.QtCore import Signal, QObject

class PlotManager(QObject):
    region_changed_signal = Signal(float, float)

    def __init__(self, canvas: FigureCanvas, fig: Figure):
        super().__init__()
        self.canvas = canvas
        self.fig = fig
        self.ax = self.fig.add_subplot(111)
        self.span_selector = None
        self.annot = None

    def draw_plot(self, data_df: pd.DataFrame, target_names: list, axis: str):
        self.ax.clear()
        if data_df is None or data_df.empty:
            self.ax.set_title("No Data", color="r")
            self.canvas.draw()
            return

        colors = plt.get_cmap('tab10').colors
        for i, target_name in enumerate(target_names):
            clean_target_name = target_name.replace(' (Rigid Body)', '')
            axis_char = axis.split('-')[1]
            col_to_plot = f"{clean_target_name}_{axis_char}"
            if col_to_plot not in data_df.columns:
                print(f"[Warning] Column '{col_to_plot}' not found, skipping.")
                continue
            x_data = data_df.index.values
            y_data = data_df[col_to_plot].values
            color = colors[i % len(colors)]
            self.ax.plot(x_data, y_data, color=color, label=target_name)

        self.ax.set_title(f"Plot of {axis} for: {', '.join(target_names)}")
        self.ax.set_xlabel("Time (s)")
        self.ax.set_ylabel(axis)
        self.ax.grid(True)
        if len(target_names) > 1:
            self.ax.legend()
        self.canvas.draw()

    def enable_interactions(self, data_df: pd.DataFrame):
        if data_df is None or data_df.empty: return

        min_time, max_time = data_df.index.min(), data_df.index.max()
        initial_region = (min_time + (max_time - min_time) * 0.1, min_time + (max_time - min_time) * 0.2)

        self.span_selector = SpanSelector(
            self.ax, self._on_select, 'horizontal', useblit=True,
            props=dict(alpha=0.3, facecolor='green'), interactive=True,
            drag_from_anywhere=True
        )
        # SpanSelector는 초기값을 직접 설정하는 API가 없으므로, 콜백을 통해 전달합니다.
        self._on_select(initial_region[0], initial_region[1])

        self.annot = self.ax.annotate("", xy=(0,0), xytext=(20,20),
                    textcoords="offset points",
                    bbox=dict(boxstyle="round", fc="w"),
                    arrowprops=dict(arrowstyle="->"))
        self.annot.set_visible(False)
        self.canvas.mpl_connect("motion_notify_event", self._on_hover)

    def _on_select(self, xmin: float, xmax: float):
        self.region_changed_signal.emit(xmin, xmax)

    def _on_hover(self, event):
        # TODO: Implement hover logic
        pass
