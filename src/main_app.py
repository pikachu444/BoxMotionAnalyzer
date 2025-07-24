import sys
from PySide6.QtCore import QThread
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QLineEdit, QComboBox, QTextEdit, QStatusBar, QGridLayout,
    QFileDialog
)
import pyqtgraph as pg
from data_loader import DataLoader
from plot_manager import PlotManager
from pipeline_controller import PipelineController

class PipelineWorker(QThread):
    """별도의 스레드에서 파이프라인을 실행하기 위한 Worker"""
    def __init__(self, controller, config, raw_data):
        super().__init__()
        self.controller = controller
        self.config = config
        self.raw_data = raw_data

    def run(self):
        self.controller.run_analysis(self.config, self.raw_data)

class MainApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Box Motion Analyzer v1.0 (PySide6 기반)")
        self.setGeometry(100, 100, 1200, 800)

        # --- 데이터 및 로직 핸들러 ---
        self.data_loader = DataLoader()
        self.pipeline_controller = PipelineController()
        self.raw_data = None
        self.final_result = None

        # --- 메인 위젯 및 레이아웃 ---
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        # --- 상단 영역: 시각화 및 로그 ---
        top_layout = QHBoxLayout()

        self.plot_widget = pg.PlotWidget()
        top_layout.addWidget(self.plot_widget, 7)

        self.plot_manager = PlotManager(self.plot_widget)

        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setPlaceholderText("[정보] 분석 대기 중...")
        top_layout.addWidget(self.log_output, 3)

        main_layout.addLayout(top_layout, 7)

        # --- 하단 영역: 설정 및 실행 ---
        bottom_widget = QWidget()
        bottom_layout = QGridLayout(bottom_widget)

        self.load_csv_button = QPushButton("CSV 파일 불러오기...")
        bottom_layout.addWidget(self.load_csv_button, 0, 0)
        self.file_path_label = QLabel("파일이 선택되지 않았습니다.")
        bottom_layout.addWidget(self.file_path_label, 0, 1, 1, 5)

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

        bottom_layout.addWidget(QLabel("<b>플롯 옵션:</b>"), 2, 0)
        bottom_layout.addWidget(QLabel("데이터:"), 2, 1)
        self.combo_plot_data = QComboBox()
        bottom_layout.addWidget(self.combo_plot_data, 2, 2)
        bottom_layout.addWidget(QLabel("축:"), 2, 3)
        self.combo_plot_axis = QComboBox()
        self.combo_plot_axis.addItems(["X-위치", "Y-위치", "Z-위치"])
        bottom_layout.addWidget(self.combo_plot_axis, 2, 4)

        bottom_layout.addWidget(QLabel("<b>분석 구간 (초):</b>"), 3, 0)
        bottom_layout.addWidget(QLabel("시작:"), 3, 1)
        self.le_slice_start = QLineEdit()
        bottom_layout.addWidget(self.le_slice_start, 3, 2)
        bottom_layout.addWidget(QLabel("종료:"), 3, 3)
        self.le_slice_end = QLineEdit()
        bottom_layout.addWidget(self.le_slice_end, 3, 4)

        run_button_layout = QHBoxLayout()
        self.run_button = QPushButton("분석 실행")
        self.export_button = QPushButton("결과 CSV로 내보내기")
        self.export_button.setEnabled(False)
        run_button_layout.addStretch()
        run_button_layout.addWidget(self.run_button)
        run_button_layout.addWidget(self.export_button)
        bottom_layout.addLayout(run_button_layout, 4, 0, 1, 7)

        main_layout.addWidget(bottom_widget, 3)

        self.setStatusBar(QStatusBar())
        self.statusBar().showMessage("준비")

        # --- 시그널 연결 ---
        self.load_csv_button.clicked.connect(self.open_csv_file)
        self.run_button.clicked.connect(self.run_pipeline)
        self.export_button.clicked.connect(self.export_results)
        self.combo_plot_data.currentIndexChanged.connect(self.update_plot)
        self.combo_plot_axis.currentIndexChanged.connect(self.update_plot)
        self.plot_manager.region_changed_signal.connect(self.on_region_changed)
        self.pipeline_controller.log_message.connect(self.log_output.append)
        self.pipeline_controller.analysis_finished.connect(self.on_analysis_finished)

    def open_csv_file(self):
        filepath, _ = QFileDialog.getOpenFileName(self, "CSV 파일 선택", "", "CSV Files (*.csv)")
        if filepath:
            try:
                self.raw_data = self.data_loader.load_csv(filepath)
                self.file_path_label.setText(filepath)
                self.statusBar().showMessage("파일 로드 성공")
                self.log_output.append(f"[정보] {filepath} 파일을 성공적으로 불러왔습니다.")

                plottable_targets = self.data_loader.get_plottable_targets(self.raw_data)
                self.combo_plot_data.clear()
                self.combo_plot_data.addItems(plottable_targets)

                # [버그 수정] 로드 직후 첫 그래프를 그리기 위해 update_plot()을 명시적으로 호출합니다.
                self.update_plot()
                self.plot_manager.enable_interactions(self.raw_data)

                # 분석 구간에 초기값을 직접 설정합니다.
                if not self.raw_data.empty:
                    min_time, max_time = self.raw_data.index.min(), self.raw_data.index.max()
                    # LinearRegionItem의 초기값과 동일하게 설정
                    initial_start = min_time + (max_time - min_time) * 0.1
                    initial_end = min_time + (max_time - min_time) * 0.2
                    self.le_slice_start.setText(f"{initial_start:.2f}")
                    self.le_slice_end.setText(f"{initial_end:.2f}")

            except Exception as e:
                self.statusBar().showMessage("파일 로드 실패")
                self.log_output.append(f"[에러] 파일 로드 실패: {e}")

    def on_region_changed(self, min_x, max_x):
        self.le_slice_start.setText(f"{min_x:.2f}")
        self.le_slice_end.setText(f"{max_x:.2f}")

    def update_plot(self):
        if self.raw_data is None or self.raw_data.empty: return
        target_name = self.combo_plot_data.currentText()
        axis_text = self.combo_plot_axis.currentText()
        if not target_name or not axis_text: return
        self.plot_manager.draw_plot(self.raw_data, target_name, axis_text)

    def run_pipeline(self):
        if self.raw_data is None or self.raw_data.empty:
            self.log_output.append("[에러] 데이터가 로드되지 않았습니다. 먼저 CSV 파일을 불러오세요.")
            return
        try:
            config = {
                'slice_time_start': float(self.le_slice_start.text()),
                'slice_time_end': float(self.le_slice_end.text()),
                'box_dimensions': (
                    float(self.le_box_l.text()),
                    float(self.le_box_w.text()),
                    float(self.le_box_h.text())
                )
            }
        except ValueError:
            self.log_output.append("[에러] 분석 구간 또는 박스 규격에 유효하지 않은 숫자 값이 있습니다.")
            return

        self.run_button.setEnabled(False)
        self.export_button.setEnabled(False)
        self.statusBar().showMessage("분석 실행 중...")

        self.worker = PipelineWorker(self.pipeline_controller, config, self.raw_data)
        self.worker.start()

    def on_analysis_finished(self, result_df):
        self.final_result = result_df
        if not result_df.empty:
            self.statusBar().showMessage("분석 완료.")
            self.export_button.setEnabled(True)
        else:
            self.statusBar().showMessage("분석 실패.")
        self.run_button.setEnabled(True)

    def export_results(self):
        if self.final_result is None or self.final_result.empty:
            self.log_output.append("[에러] 내보낼 분석 결과가 없습니다.")
            return
        filepath, _ = QFileDialog.getSaveFileName(self, "결과 저장", "analysis_results.csv", "CSV Files (*.csv)")
        if filepath:
            try:
                self.final_result.to_csv(filepath, index=True, float_format='%.8f')
                self.statusBar().showMessage("결과 저장 완료")
                self.log_output.append(f"[정보] 분석 결과를 {filepath} 에 성공적으로 저장했습니다.")
            except Exception as e:
                self.statusBar().showMessage("결과 저장 실패")
                self.log_output.append(f"[에러] 파일 저장 중 오류 발생: {e}")

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MainApp()
    window.show()
    sys.exit(app.exec())
