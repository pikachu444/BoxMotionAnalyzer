import sys
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QLineEdit, QComboBox, QTextEdit, QStatusBar, QGridLayout,
    QFileDialog
)
import pyqtgraph as pg
from data_loader import DataLoader
from plot_manager import PlotManager

class MainApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Box Motion Analyzer v1.0 (PySide6 기반)")
        self.setGeometry(100, 100, 1200, 800)

        # --- 데이터 및 로직 핸들러 ---
        self.data_loader = DataLoader()
        self.raw_data = None

        # --- 메인 위젯 및 레이아웃 ---
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        # --- 상단 영역: 시각화 및 로그 ---
        top_layout = QHBoxLayout()

        # 1. 데이터 시각화
        self.plot_widget = pg.PlotWidget()
        top_layout.addWidget(self.plot_widget, 7) # 70% 너비 차지

        # PlotManager 초기화
        self.plot_manager = PlotManager(self.plot_widget)

        # 2. 로그 출력
        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setPlaceholderText("[정보] 분석 대기 중...")
        top_layout.addWidget(self.log_output, 3) # 30% 너비 차지

        main_layout.addLayout(top_layout, 7) # 70% 높이 차지

        # --- 하단 영역: 설정 및 실행 ---
        bottom_widget = QWidget()
        bottom_layout = QGridLayout(bottom_widget)

        # 3. 설정 및 실행
        # 파일 불러오기
        self.load_csv_button = QPushButton("CSV 파일 불러오기...")
        bottom_layout.addWidget(self.load_csv_button, 0, 0)
        self.file_path_label = QLabel("파일이 선택되지 않았습니다.")
        bottom_layout.addWidget(self.file_path_label, 0, 1, 1, 5)

        # 박스 규격
        bottom_layout.addWidget(QLabel("<b>박스 규격 (mm):</b>"), 1, 0)
        bottom_layout.addWidget(QLabel("길이(L):"), 1, 1)
        self.le_box_l = QLineEdit("1578.0")
        bottom_layout.addWidget(self.le_box_l, 1, 2)
        bottom_layout.addWidget(QLabel("너비(W):"), 1, 3)
        self.le_box_w = QLineEdit("930.0")
        bottom_layout.addWidget(self.le_box_w, 1, 4)
        bottom_layout.addWidget(QLabel("높이(H):"), 1, 5)
        self.le_box_h = QLineEdit("142.0")
        bottom_layout.addWidget(self.le_box_h, 1, 6)

        # 플롯 옵션
        bottom_layout.addWidget(QLabel("<b>플롯 옵션:</b>"), 2, 0)
        bottom_layout.addWidget(QLabel("데이터:"), 2, 1)
        self.combo_plot_data = QComboBox()
        bottom_layout.addWidget(self.combo_plot_data, 2, 2)
        bottom_layout.addWidget(QLabel("축:"), 2, 3)
        self.combo_plot_axis = QComboBox()
        self.combo_plot_axis.addItems(["X-위치", "Y-위치", "Z-위치"])
        bottom_layout.addWidget(self.combo_plot_axis, 2, 4)

        # 분석 구간
        bottom_layout.addWidget(QLabel("<b>분석 구간 (초):</b>"), 3, 0)
        bottom_layout.addWidget(QLabel("시작:"), 3, 1)
        self.le_slice_start = QLineEdit()
        bottom_layout.addWidget(self.le_slice_start, 3, 2)
        bottom_layout.addWidget(QLabel("종료:"), 3, 3)
        self.le_slice_end = QLineEdit()
        bottom_layout.addWidget(self.le_slice_end, 3, 4)

        # 실행 버튼
        run_button_layout = QHBoxLayout()
        self.run_button = QPushButton("분석 실행")
        self.export_button = QPushButton("결과 CSV로 내보내기")
        self.export_button.setEnabled(False) # 초기 비활성화
        run_button_layout.addStretch()
        run_button_layout.addWidget(self.run_button)
        run_button_layout.addWidget(self.export_button)
        bottom_layout.addLayout(run_button_layout, 4, 0, 1, 7)

        main_layout.addWidget(bottom_widget, 3) # 30% 높이 차지

        # --- 상태바 ---
        self.setStatusBar(QStatusBar())
        self.statusBar().showMessage("준비")

        # --- 시그널 연결 ---
        self.load_csv_button.clicked.connect(self.open_csv_file)
        self.combo_plot_data.currentIndexChanged.connect(self.update_plot)
        self.combo_plot_axis.currentIndexChanged.connect(self.update_plot)
        self.plot_manager.region_changed_signal.connect(self.on_region_changed)

    def open_csv_file(self):
        filepath, _ = QFileDialog.getOpenFileName(
            self,
            "CSV 파일 선택",
            "",
            "CSV Files (*.csv)"
        )
        if filepath:
            try:
                self.raw_data = self.data_loader.load_csv(filepath)
                self.file_path_label.setText(filepath)
                self.statusBar().showMessage("파일 로드 성공")
                self.log_output.append(f"[정보] {filepath} 파일을 성공적으로 불러왔습니다.")

                # 플롯 대상 목록 업데이트
                plottable_targets = self.data_loader.get_plottable_targets(self.raw_data)
                self.combo_plot_data.clear()
                self.combo_plot_data.addItems(plottable_targets)

                # 인터랙션 활성화 및 첫 그래프 그리기
                self.plot_manager.enable_interactions()
                self.update_plot()

            except Exception as e:
                self.statusBar().showMessage("파일 로드 실패")
                self.log_output.append(f"[에러] 파일 로드 실패: {e}")

    def on_region_changed(self, min_x, max_x):
        """
        그래프에서 선택된 영역이 변경되면 호출되는 슬롯.
        """
        self.le_slice_start.setText(f"{min_x:.2f}")
        self.le_slice_end.setText(f"{max_x:.2f}")

    def update_plot(self):
        """
        현재 선택된 옵션으로 PlotManager를 통해 그래프를 다시 그립니다.
        """
        if self.raw_data is None or self.raw_data.empty:
            return

        target_name = self.combo_plot_data.currentText()
        axis_text = self.combo_plot_axis.currentText() # 예: "X-위치"

        if not target_name or not axis_text:
            return

        self.plot_manager.draw_plot(self.raw_data, target_name, axis_text)


if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MainApp()
    window.show()
    sys.exit(app.exec())
