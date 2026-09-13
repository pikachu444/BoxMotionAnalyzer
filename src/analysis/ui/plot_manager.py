import matplotlib.pyplot as plt
from matplotlib.figure import Figure
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.widgets import SpanSelector
import pandas as pd
import numpy as np
from PySide6.QtCore import Signal, QObject

from src.config.data_columns import (
    get_result_column_display_path, get_result_column_unit,
    get_result_metric_display_name, is_corner_id_column, format_result_value,
)


def plot_result_series(ax, x, y, column, **style):
    """Draw categories as observations, never interpolate between corner IDs."""
    values = np.asarray(y)
    if is_corner_id_column(column):
        values = pd.to_numeric(pd.Series(values), errors='coerce').to_numpy(dtype=float)
        valid = np.isfinite(values) & (values == np.floor(values)) & (values >= 1) & (values <= 8)
        if np.asarray(y).dtype.kind == 'b':
            valid[:] = False
        values = np.where(valid, values, np.nan)
        style.update(linestyle='None', marker='o')
        style.setdefault('markersize', 3.5)
    line, = ax.plot(x, values, **style)
    line._result_column = column
    return line


def configure_result_axis(ax, columns):
    """Set a display scale only; toolbar zoom and original data remain intact."""
    if not columns:
        ax.set_ylabel('Value')
        return
    if all(is_corner_id_column(col) for col in columns):
        ax.set_ylabel('Corner')
        ax.set_yticks(range(1, 9), [f'C{i}' for i in range(1, 9)])
        ax.set_ylim(.5, 8.5)
        return
    units = {get_result_column_unit(col) for col in columns}
    if len(columns) == 1 and isinstance(columns[0], (tuple, list)):
        ax.set_ylabel(get_result_metric_display_name(*columns[0]))
    else:
        ax.set_ylabel(next(iter(units)) if len(units) == 1 and '' not in units else 'Value')
    minimum = None
    if units == {'°'}:
        minimum = 1.
    elif units == {'rad'} and all(isinstance(col, (tuple, list)) and col[2] in {'P_RX', 'P_RY', 'P_RZ'} for col in columns):
        minimum = np.pi / 180.
    if minimum is None:
        return
    finite_values = [np.asarray(line.get_ydata(), dtype=float)
                     for line in ax.lines if hasattr(line, '_result_column')]
    finite_values = np.concatenate(finite_values) if finite_values else np.array([])
    finite_values = finite_values[np.isfinite(finite_values)]
    if not len(finite_values):
        return
    if columns == ['Relative rotation (deg)']:
        ax.set_ylim(0., max(1., ax.get_ylim()[1]))
        return
    low, high = ax.get_ylim()
    if high - low < minimum:
        middle = (low + high) / 2
        low, high = middle - minimum / 2, middle + minimum / 2
        # Face tilt and relative rotation are nonnegative angles. Signed
        # direction angles and rotation-vector components keep signed axes.
        unsigned = all(col == 'Relative rotation (deg)' or
                       (isinstance(col, (tuple, list)) and col[2] == 'BetaDeg')
                       for col in columns)
        if unsigned and finite_values.min() >= 0 and low < 0:
            low, high = 0., minimum
        ax.set_ylim(low, high)

class PlotManager(QObject):
    region_changed_signal = Signal(float, float)

    def __init__(self, canvas: FigureCanvas, fig: Figure):
        super().__init__()
        self.canvas = canvas
        self.fig = fig
        self.ax = self.fig.add_subplot(111)
        self.category_ax = None
        self.span_selector = None
        self.annot = None
        self.canvas.mpl_connect("resize_event", self._on_resize)

    def draw_plot(self, data_df: pd.DataFrame, columns_to_plot: list):
        self.reset_axes()
        if data_df is None or data_df.empty or not columns_to_plot:
            self.ax.set_title("Select data to plot", color="#666666")
            self.canvas.draw()
            return

        colors = plt.get_cmap('tab10').colors
        # 컬럼 이름이 튜플(멀티헤더)일 수도, 문자열일 수도 있으므로, 레이블용 문자열 리스트를 별도로 생성합니다.
        labels_to_plot = []
        numeric_columns = [col for col in columns_to_plot if col in data_df and not is_corner_id_column(col)]
        category_columns = [col for col in columns_to_plot if col in data_df and is_corner_id_column(col)]
        if numeric_columns and category_columns:
            self.category_ax = self.ax.twinx()
            self.category_ax.grid(False)
        lines = []
        for i, col_name in enumerate(columns_to_plot):
            if col_name not in data_df.columns:
                print(f"[Warning] Column '{col_name}' not found, skipping.")
                continue

            # 튜플인 경우, 제목과 범례에 사용할 문자열 레이블을 생성합니다.
            if isinstance(col_name, tuple):
                label = get_result_column_display_path(col_name)
            else:
                label = col_name
            labels_to_plot.append(label)

            x_data = data_df.index.values
            y_data = data_df[col_name].values
            color = colors[i % len(colors)]
            axis = self.category_ax if is_corner_id_column(col_name) and self.category_ax is not None else self.ax
            lines.append(plot_result_series(axis, x_data, y_data, col_name, color=color, label=label))

        self.ax.set_xlabel("Time (s)")
        self.ax.grid(True)
        configure_result_axis(self.ax, numeric_columns or category_columns)
        if self.category_ax is not None:
            configure_result_axis(self.category_ax, category_columns)
        if labels_to_plot:
            self.ax.legend(handles=lines)

        self._initialize_hover_annotation()
        self.fig.tight_layout()
        self.canvas.draw()

    @property
    def axes(self):
        return [self.ax] + ([self.category_ax] if self.category_ax is not None else [])

    def reset_axes(self):
        if self.annot is not None and self.annot.axes is not None:
            self.annot.remove()
        self.annot = None
        if self.category_ax is not None:
            self.category_ax.remove()
            self.category_ax = None
        self.ax.clear()

    def capture_limits(self):
        return [(axis.get_xlim(), axis.get_ylim()) for axis in self.axes]

    def restore_limits(self, limits):
        for axis, (xlim, ylim) in zip(self.axes, limits):
            axis.set_xlim(xlim)
            axis.set_ylim(ylim)

    def clear_plot(self):
        """Clears only the data lines and legend, preserving axis limits."""
        # Iterate over a copy of the list of lines to avoid modification issues
        for axis in self.axes:
            for line in list(axis.lines):
                line.remove()
        if self.annot is not None:
            self.annot.set_visible(False)

        # Remove the legend if it exists
        if hasattr(self.ax, 'legend_') and self.ax.legend_ is not None:
            self.ax.legend_.remove()
            # It's good practice to also nullify the reference
            self.ax.legend_ = None

        self.ax.set_title("")
        self.canvas.draw()

    def enable_interactions(self, data_df: pd.DataFrame):
        if data_df is None or data_df.empty: return
        if self.span_selector is not None:
            self.span_selector.disconnect_events()

        # SpanSelector 초기화
        min_time, max_time = data_df.index.min(), data_df.index.max()
        initial_region = (min_time + (max_time - min_time) * 0.1, min_time + (max_time - min_time) * 0.2)
        self.span_selector = SpanSelector(
            self.ax, self._on_select, 'horizontal', useblit=True,
            props=dict(alpha=0.3, facecolor='green'), interactive=True,
            drag_from_anywhere=True
        )
        self.span_selector.extents = initial_region
        self.set_selector_active(False)

        # 호버 기능 초기화
        self._initialize_hover_annotation()

    def _initialize_hover_annotation(self, axis=None):
        """호버 기능에 필요한 Annotation 객체를 생성하고 이벤트를 연결합니다."""
        # 기존 Annotation이 있다면 제거
        if self.annot and self.annot.axes:
            self.annot.remove()

        self.annot = (axis or self.ax).annotate("", xy=(0,0), xytext=(20,20),
                    textcoords="offset points",
                    bbox=dict(boxstyle="round", fc="w"),
                    arrowprops=dict(arrowstyle="->"))
        self.annot.set_visible(False)

        # 이벤트 리스너가 중복 연결되지 않도록 기존 연결을 먼저 끊을 수 있지만,
        # Matplotlib은 동일한 콜백에 대해 중복 연결을 방지하므로, 여기서는 생략 가능.
        # self.canvas.mpl_disconnect(self.hover_cid)
        self.canvas.mpl_connect("motion_notify_event", self._on_hover)

    def _on_select(self, xmin: float, xmax: float):
        self.region_changed_signal.emit(xmin, xmax)

    def _on_resize(self, _event):
        # Recompute subplot padding when the embedded canvas size changes.
        self.fig.tight_layout()
        self.canvas.draw_idle()

    def _place_hover_annotation(self, x, y):
        # Keep tooltip visible inside the plot area by flipping direction
        # near top/right edges.
        axis = self.annot.axes
        point_px = axis.transData.transform((x, y))
        point_ax = axis.transAxes.inverted().transform(point_px)
        ax_x, ax_y = float(point_ax[0]), float(point_ax[1])

        if ax_x > 0.78:
            x_offset = -20
            ha = "right"
        else:
            x_offset = 20
            ha = "left"

        if ax_y > 0.78:
            y_offset = -20
            va = "top"
        else:
            y_offset = 20
            va = "bottom"

        self.annot.set_position((x_offset, y_offset))
        self.annot.set_ha(ha)
        self.annot.set_va(va)

    def _on_hover(self, event):
        """마우스가 그래프 위를 움직일 때 호출되어, 가장 가까운 데이터 포인트에 툴팁을 표시합니다."""
        # 마우스가 Axes 안에 있고, 그려진 선이 있을 때만 실행
        if self.annot is None:
            return
        visible = self.annot.get_visible()
        if event.inaxes in self.axes:
            lines = [line for axis in self.axes for line in axis.lines
                     if hasattr(line, '_result_column')]
            if not lines:
                return

            # 모든 선을 순회하며 가장 가까운 점을 찾음
            min_dist = float('inf')
            closest_point = None

            for line in lines:
                cont, ind = line.contains(event)
                if cont:
                    # 마우스와 데이터 포인트 사이의 거리를 계산
                    x_data, y_data = line.get_data()
                    for i in ind['ind']:
                        # Both axes share time but have different y units.
                        # Compare screen distances, not degrees against IDs.
                        px, py = line.axes.transData.transform((x_data[i], y_data[i]))
                        dist = (px - event.x)**2 + (py - event.y)**2
                        if dist < min_dist:
                            min_dist = dist
                            closest_point = (line, x_data[i], y_data[i])

            if closest_point:
                line, x, y = closest_point
                if self.annot.axes is not line.axes:
                    self._initialize_hover_annotation(line.axes)
                # 툴팁(Annotation) 업데이트
                self.annot.xy = (x, y)
                self._place_hover_annotation(x, y)
                value = format_result_value(line._result_column, y)
                x_label = 'Sample' if 'sample' in line.axes.get_xlabel().lower() else 'Time'
                suffix = '' if x_label == 'Sample' else ' s'
                self.annot.set_text(f"{line.get_label()}\n{x_label}: {x:.6g}{suffix}\n{value}")
                self.annot.get_bbox_patch().set_facecolor(line.get_color())
                self.annot.get_bbox_patch().set_alpha(0.4)
                self.annot.set_visible(True)
                self.canvas.draw_idle()
            elif visible:
                # 가장 가까운 점이 없으면 툴팁 숨김
                self.annot.set_visible(False)
                self.canvas.draw_idle()
        elif visible:
            self.annot.set_visible(False)
            self.canvas.draw_idle()

    def set_selector_active(self, active):
        """SpanSelector의 활성화 및 가시성을 설정합니다."""
        if self.span_selector:
            self.span_selector.set_active(active)
            self.span_selector.set_visible(active)
            self.canvas.draw_idle()

    def set_region(self, start, end):
        """외부에서 SpanSelector의 영역을 설정합니다."""
        if self.span_selector:
            self.span_selector.extents = (start, end)
