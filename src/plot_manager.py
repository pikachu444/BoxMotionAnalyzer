import matplotlib.pyplot as plt
from matplotlib.figure import Figure
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.widgets import SpanSelector
import pandas as pd
from PySide6.QtCore import Signal, QObject

class PlotManager(QObject):
    """
    GUI의 Matplotlib Canvas 위젯을 관리하고, 데이터 시각화를 처리합니다.
    """
    region_changed_signal = Signal(float, float)

    def __init__(self, canvas: FigureCanvas, fig: Figure):
        super().__init__()
        self.canvas = canvas
        self.fig = fig
        self.ax = self.fig.add_subplot(111)
        self.span_selector = None
        self.annot = None

    def draw_plot(self, data_df: pd.DataFrame, target_names: list, axis: str):
        """
        주어진 데이터로 Matplotlib ax에 그래프를 그립니다.
        """
        self.ax.clear()

        if data_df is None or data_df.empty:
            self.ax.set_title("데이터 없음", color="r")
            self.canvas.draw()
            return

        # 미리 정의된 색상 리스트
        colors = plt.get_cmap('tab10').colors

        for i, target_name in enumerate(target_names):
            clean_target_name = target_name.replace(' (강체 중심)', '')
            axis_char = axis.split('-')[0]
            col_to_plot = f"{clean_target_name}_{axis_char}"

            if col_to_plot not in data_df.columns:
                print(f"[경고] '{col_to_plot}' 컬럼을 찾을 수 없어 건너뜁니다.")
                continue

            x_data = data_df.index.values
            y_data = data_df[col_to_plot].values

            color = colors[i % len(colors)]
            self.ax.plot(x_data, y_data, color=color, label=target_name)

        self.ax.set_title(f"{', '.join(target_names)} - {axis} 그래프")
        self.ax.set_xlabel("시간 (초)")
        self.ax.set_ylabel(axis)
        self.ax.grid(True)
        if len(target_names) > 1:
            self.ax.legend()

        self.canvas.draw()

    def enable_interactions(self, data_df: pd.DataFrame):
        """
        그래프에 SpanSelector와 마우스 호버 이벤트를 추가합니다.
        """
        # 영역 선택 기능 (SpanSelector)
        self.span_selector = SpanSelector(
            self.ax,
            self._on_select,
            'horizontal',
            useblit=True,
            props=dict(alpha=0.3, facecolor='green'),
            interactive=True,
            drag_from_anywhere=True
        )
        # 마우스 호버 기능
        self.annot = self.ax.annotate("", xy=(0,0), xytext=(20,20),
                    textcoords="offset points",
                    bbox=dict(boxstyle="round", fc="w"),
                    arrowprops=dict(arrowstyle="->"))
        self.annot.set_visible(False)
        self.canvas.mpl_connect("motion_notify_event", self._on_hover)

    def _on_select(self, xmin: float, xmax: float):
        """SpanSelector의 영역이 변경될 때 호출됩니다."""
        self.region_changed_signal.emit(xmin, xmax)

    def _on_hover(self, event):
        """마우스가 그래프 위를 움직일 때 호출됩니다."""
        # TODO: 커서 위치의 값을 찾아 툴팁(annotation)으로 보여주는 로직 구현
        pass
