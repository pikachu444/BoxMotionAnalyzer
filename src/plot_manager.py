import pyqtgraph as pg
import pandas as pd
from PySide6.QtCore import Signal, QObject

class PlotManager(QObject):
    """
    GUI의 PyQtGraph 위젯을 관리하고, 데이터 시각화를 처리합니다.
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

        Args:
            data_df (pd.DataFrame): 시각화할 전체 데이터프레임.
            target_name (str): 플롯할 대상의 이름 (예: 'TestBox_85 (강체 중심)').
            axis (str): 플롯할 축 ('X-위치', 'Y-위치', 'Z-위치').
        """
        self.plot_widget.clear()

        if data_df is None or data_df.empty:
            self.plot_widget.getPlotItem().setTitle("데이터 없음", color="r", size="12pt")
            return

        # 컬럼 이름에서 '(강체 중심)' 부분을 제거하여 실제 컬럼을 찾습니다.
        clean_target_name = target_name.replace(' (강체 중심)', '')

        # 'X-위치' -> 'X' 와 같이 축 이름만 추출합니다.
        axis_char = axis.split('-')[0]

        # X, Y, Z에 해당하는 컬럼 이름을 구성합니다.
        try:
            col_to_plot = f"{clean_target_name}_{axis_char}"

            if col_to_plot not in data_df.columns:
                self.plot_widget.getPlotItem().setTitle(f"'{col_to_plot}' 컬럼을 찾을 수 없음", color="r", size="12pt")
                return

            # X축은 시간(인덱스), Y축은 선택된 데이터
            x_data = data_df.index.values
            y_data = data_df[col_to_plot].values

            pen = pg.mkPen(color=(0, 0, 255), width=2)
            self.plot_widget.plot(x_data, y_data, pen=pen)
            self.plot_widget.getPlotItem().setTitle(f"{target_name} - {axis}", color="k", size="12pt")
            self.plot_widget.setLabel('left', f"{axis}")

        except KeyError:
            self.plot_widget.getPlotItem().setTitle(f"데이터 조회 중 오류", color="r", size="12pt")
        except Exception as e:
            self.plot_widget.getPlotItem().setTitle(f"플롯 생성 중 오류: {e}", color="r", size="12pt")
