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

    def draw_plot(self, data_df: pd.DataFrame, columns_to_plot: list):
        self.ax.clear()
        if data_df is None or data_df.empty or not columns_to_plot:
            self.ax.set_title("No Data to Plot", color="r")
            self.canvas.draw()
            return

        colors = plt.get_cmap('tab10').colors
        for i, col_name in enumerate(columns_to_plot):
            if col_name not in data_df.columns:
                print(f"[Warning] Column '{col_name}' not found, skipping.")
                continue

            x_data = data_df.index.values
            y_data = data_df[col_name].values
            color = colors[i % len(colors)]
            self.ax.plot(x_data, y_data, color=color, label=col_name)

        self.ax.set_title(f"Plot for: {', '.join(columns_to_plot)}")
        self.ax.set_xlabel("Time (s)")
        self.ax.set_ylabel("Value")
        self.ax.grid(True)
        if len(columns_to_plot) > 1:
            self.ax.legend()

        self._initialize_hover_annotation()
        self.canvas.draw()

    def enable_interactions(self, data_df: pd.DataFrame):
        if data_df is None or data_df.empty: return

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

    def _initialize_hover_annotation(self):
        """호버 기능에 필요한 Annotation 객체를 생성하고 이벤트를 연결합니다."""
        # 기존 Annotation이 있다면 제거
        if self.annot and self.annot.axes:
            self.annot.remove()

        self.annot = self.ax.annotate("", xy=(0,0), xytext=(20,20),
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

    def _on_hover(self, event):
        """마우스가 그래프 위를 움직일 때 호출되어, 가장 가까운 데이터 포인트에 툴팁을 표시합니다."""
        # 마우스가 Axes 안에 있고, 그려진 선이 있을 때만 실행
        visible = self.annot.get_visible()
        if event.inaxes == self.ax:
            lines = self.ax.get_lines()
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
                        dist = (x_data[i] - event.xdata)**2 + (y_data[i] - event.ydata)**2
                        if dist < min_dist:
                            min_dist = dist
                            closest_point = (line, x_data[i], y_data[i])

            if closest_point:
                line, x, y = closest_point
                # 툴팁(Annotation) 업데이트
                self.annot.xy = (x, y)
                self.annot.set_text(f"{line.get_label()}\nTime: {x:.2f}\nValue: {y:.2f}")
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
            self.span_selector.visible = active
            self.canvas.draw_idle()

    def set_region(self, start, end):
        """외부에서 SpanSelector의 영역을 설정합니다."""
        if self.span_selector:
            self.span_selector.extents = (start, end)
