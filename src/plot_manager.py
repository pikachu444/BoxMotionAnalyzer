import pyqtgraph as pg
import pandas as pd
from PySide6.QtCore import Signal, QObject

class PlotManager(QObject):
    """
    GUI의 PyQtGraph 위젯을 관리하고, 데이터 시각화 및 인터랙션을 처리합니다.
    QObject를 상속하여 시그널을 사용할 수 있도록 합니다.
    """
    region_changed_signal = Signal(float, float)

    def __init__(self, plot_widget: pg.PlotWidget):
        super().__init__()
        self.plot_widget = plot_widget
        self.plot_widget.setBackground('w')
        self.plot_widget.showGrid(x=True, y=True)
        self.plot_widget.setLabel('left', 'Y-위치')
        self.plot_widget.setLabel('bottom', '시간(초)')
        self.region = None

    def draw_plot(self, data_df: pd.DataFrame, target_name: str, axis: str):
        """
        주어진 데이터로 플롯 위젯에 그래프를 그립니다.
        """
        self.plot_widget.clear()

        if data_df is None or data_df.empty:
            self.plot_widget.getPlotItem().setTitle("데이터 없음", color="r", size="12pt")
            return

        clean_target_name = target_name.replace(' (강체 중심)', '')
        axis_char = axis.split('-')[0]
        col_to_plot = f"{clean_target_name}_{axis_char}"

        if col_to_plot not in data_df.columns:
            self.plot_widget.getPlotItem().setTitle(f"'{col_to_plot}' 컬럼을 찾을 수 없음", color="r", size="12pt")
            return

        try:
            x_data = data_df.index.values
            y_data = data_df[col_to_plot].values

            pen = pg.mkPen(color=(0, 0, 255), width=2)
            self.plot_widget.plot(x_data, y_data, pen=pen)
            self.plot_widget.getPlotItem().setTitle(f"{target_name} - {axis}", color="k", size="12pt")
            self.plot_widget.setLabel('left', f"{axis}")
            self.plot_widget.autoRange()
        except Exception as e:
            self.plot_widget.getPlotItem().setTitle(f"플롯 생성 중 오류: {e}", color="r", size="12pt")

    def enable_interactions(self, data_df: pd.DataFrame):
        """
        그래프에 LinearRegionItem을 추가하고, 데이터프레임의 시간 축을 기반으로 초기 영역을 설정합니다.
        """
        if data_df is None or data_df.empty:
            return

        if self.region is None:
            min_time = data_df.index.min()
            max_time = data_df.index.max()
            initial_region = (min_time + (max_time - min_time) * 0.1, min_time + (max_time - min_time) * 0.2)

            self.region = pg.LinearRegionItem(values=initial_region, movable=True, brush=(0, 255, 0, 30))
            self.region.setZValue(10)
            self.plot_widget.addItem(self.region, ignoreBounds=True)
            self.region.sigRegionChanged.connect(self._on_region_changed)
            # 초기값은 MainApp에서 직접 설정하므로, 여기서는 자동 호출하지 않음

    def _on_region_changed(self):
        """
        LinearRegionItem의 영역이 변경될 때 호출되어 시그널을 발생시킵니다.
        """
        if self.region:
            min_x, max_x = self.region.getRegion()
            self.region_changed_signal.emit(min_x, max_x)
