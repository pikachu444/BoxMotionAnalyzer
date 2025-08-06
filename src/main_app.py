import sys
from PySide6.QtCore import QThread, QTimer
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QLineEdit, QComboBox, QTextEdit, QStatusBar, QGridLayout,
    QFileDialog, QListWidget, QScrollArea, QCheckBox, QGroupBox
)
import matplotlib
matplotlib.use('QtAgg')
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qtagg import NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure
from src.data_loader import DataLoader
from src.plot_manager import PlotManager
from src.pipeline_controller import PipelineController
from src.data_selection_dialog import DataSelectionDialog
from src.config import config_app
from src.analysis.parser import Parser
from src.config.data_columns import (
    PoseCols, RawMarkerCols, VelocityCols, AnalysisCols, RigidBodyCols, FACE_PREFIX_TO_INFO,
    DisplayNames
)
from src.header_converter import convert_to_multi_header

class PipelineWorker(QThread):
    def __init__(self, controller, config, header_info, raw_data, parsed_data):
        super().__init__()
        self.controller = controller
        self.config = config
        self.header_info = header_info
        self.raw_data = raw_data
        self.parsed_data = parsed_data # 파싱된 데이터도 전달
    def run(self):
        self.controller.run_analysis(self.config, self.header_info, self.raw_data, self.parsed_data)

class MainApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Box Motion Analyzer v2.0 (Refactored)")
        self.setGeometry(100, 100, 1200, 800)

        # 모듈 초기화
        self.data_loader = DataLoader()
        # MainApp이 미리보기 파싱을 위해 Parser 인스턴스를 가짐
        self.parser = Parser(face_prefix_map=FACE_PREFIX_TO_INFO)
        self.pipeline_controller = PipelineController()

        # 데이터 저장 변수
        self.raw_data = None
        self.header_info = None
        self.parsed_data = None # 파싱된 데이터를 캐싱할 변수
        self.final_result = None
        self.current_selected_targets = []

        # UI 구성
        self._setup_ui()
        self._connect_signals()

        self.plot_manager.ax.text(0.5, 0.5, "Load a CSV file to start.", ha='center', va='center')
        self.plot_manager.canvas.draw()

    def _setup_ui(self):
        # (UI 구성 코드는 이전과 동일)
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        top_layout = QHBoxLayout()
        self.fig = Figure(figsize=(5, 4), dpi=100)
        self.canvas = FigureCanvas(self.fig)
        self.toolbar = NavigationToolbar(self.canvas, self)
        plot_container = QWidget()
        plot_layout = QVBoxLayout(plot_container)
        plot_layout.setContentsMargins(0,0,0,0)
        plot_layout.addWidget(self.toolbar)
        plot_layout.addWidget(self.canvas)
        top_layout.addWidget(plot_container, 7)
        self.plot_manager = PlotManager(self.canvas, self.fig)
        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setPlaceholderText("[INFO] Load a CSV file to start.")
        top_layout.addWidget(self.log_output, 3)
        main_layout.addLayout(top_layout, 7)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        bottom_widget = QWidget()
        bottom_layout = QGridLayout(bottom_widget)

        self.load_csv_button = QPushButton("Load CSV File...")
        bottom_layout.addWidget(self.load_csv_button, 0, 0, 1, 7)
        self.file_path_label = QLabel("No file selected.")
        bottom_layout.addWidget(self.file_path_label, 1, 0, 1, 7)

        plot_options_group = QGroupBox("Plot Options")
        plot_options_layout = QGridLayout(plot_options_group)
        self.select_data_button = QPushButton("Select Data...")
        plot_options_layout.addWidget(self.select_data_button, 0, 0)
        self.selected_data_label = QLabel("Selected: None")
        self.selected_data_label.setWordWrap(True)
        plot_options_layout.addWidget(self.selected_data_label, 0, 1)
        plot_options_layout.addWidget(QLabel("Axis:"), 1, 0)
        self.combo_plot_axis = QComboBox()
        self.combo_plot_axis.addItem("Position-X", userData=PoseCols.POS_X)
        self.combo_plot_axis.addItem("Position-Y", userData=PoseCols.POS_Y)
        self.combo_plot_axis.addItem("Position-Z", userData=PoseCols.POS_Z)
        plot_options_layout.addWidget(self.combo_plot_axis, 1, 1)
        bottom_layout.addWidget(plot_options_group, 2, 0, 1, 3)

        self.slice_group = QGroupBox("Slice Range")
        self.slice_group.setCheckable(True)
        self.slice_group.setChecked(False)
        slice_group_layout = QGridLayout(self.slice_group)
        slice_group_layout.addWidget(QLabel("Start:"), 0, 0)
        self.le_slice_start = QLineEdit()
        slice_group_layout.addWidget(self.le_slice_start, 0, 1)
        slice_group_layout.addWidget(QLabel("End:"), 1, 0)
        self.le_slice_end = QLineEdit()
        slice_group_layout.addWidget(self.le_slice_end, 1, 1)
        bottom_layout.addWidget(self.slice_group, 2, 3, 1, 2)

        box_dims_group = QGroupBox("Box Dimensions (mm)")
        box_dims_layout = QGridLayout(box_dims_group)
        box_dims_layout.addWidget(QLabel("L:"), 0, 0)
        self.le_box_l = QLineEdit("1820.0")
        box_dims_layout.addWidget(self.le_box_l, 0, 1)
        box_dims_layout.addWidget(QLabel("W:"), 1, 0)
        self.le_box_w = QLineEdit("1110.0")
        box_dims_layout.addWidget(self.le_box_w, 1, 1)
        box_dims_layout.addWidget(QLabel("H:"), 2, 0)
        self.le_box_h = QLineEdit("164.0")
        box_dims_layout.addWidget(self.le_box_h, 2, 1)
        bottom_layout.addWidget(box_dims_group, 2, 5, 1, 2)

        run_button_layout = QHBoxLayout()
        self.run_button = QPushButton("Run Analysis")
        self.export_button = QPushButton("Export Results to CSV")
        self.export_button.setEnabled(False)
        run_button_layout.addStretch()
        run_button_layout.addWidget(self.run_button)
        run_button_layout.addWidget(self.export_button)
        bottom_layout.addLayout(run_button_layout, 3, 0, 1, 7)

        scroll_area.setWidget(bottom_widget)
        main_layout.addWidget(scroll_area, 3)
        self.setStatusBar(QStatusBar())

    def _connect_signals(self):
        # (시그널 연결 코드는 이전과 동일)
        self.load_csv_button.clicked.connect(self.open_csv_file)
        self.select_data_button.clicked.connect(self.open_data_selection_dialog)
        self.run_button.clicked.connect(self.run_pipeline)
        self.export_button.clicked.connect(self.export_results)
        self.combo_plot_axis.currentIndexChanged.connect(self.update_plot)
        self.plot_manager.region_changed_signal.connect(self.on_region_changed)
        self.pipeline_controller.log_message.connect(self.log_output.append)
        self.pipeline_controller.analysis_finished.connect(self.on_analysis_finished)
        self.slice_group.toggled.connect(self.toggle_slicing_widgets)
        self.le_slice_start.editingFinished.connect(self.update_span_selector_from_inputs)
        self.le_slice_end.editingFinished.connect(self.update_span_selector_from_inputs)

    def open_csv_file(self):
        filepath, _ = QFileDialog.getOpenFileName(self, "Select CSV File", "", "CSV Files (*.csv)")
        if filepath:
            try:
                self.header_info, self.raw_data = self.data_loader.load_csv(filepath)
                self.file_path_label.setText(filepath)
                self.statusBar().showMessage("File loaded. Parsing for preview...")
                self.log_output.append(f"[INFO] Loaded {filepath}. Parsing for preview...")

                # 미리보기용으로 즉시 파싱하고 결과를 캐시에 저장
                self.parsed_data = self.parser.process(self.header_info, self.raw_data)
                self.log_output.append("[INFO] Preview parsing complete.")

                # =================================================================
                # UX 개선: CSV 로드 후, 기본값으로 'Rigid Body Center'를 자동 선택하여 플로팅합니다.
                # 이렇게 하면 사용자가 파일을 로드한 직후 빈 그래프를 보지 않게 됩니다.
                # -----------------------------------------------------------------
                # 1. 플로팅 가능한 전체 대상 목록을 가져옵니다.
                all_targets = self.data_loader.get_plottable_targets(self.parsed_data)

                # 2. 방어 코드: 기본 선택 대상(DisplayNames.RB_CENTER)이 목록에 있는지 확인합니다.
                if DisplayNames.RB_CENTER in all_targets:
                    # 3. 기본 대상을 현재 선택된 항목으로 설정하고, UI 라벨도 업데이트합니다.
                    self.current_selected_targets = [DisplayNames.RB_CENTER]
                    self.selected_data_label.setText(f"Selected: {DisplayNames.RB_CENTER}")
                    self.log_output.append(f"[INFO] Default target '{DisplayNames.RB_CENTER}' selected for plotting.")
                # =================================================================

                self.update_plot()
                self.plot_manager.enable_interactions(self.parsed_data)
                # 파일 로드 후 슬라이싱 기능 비활성화 및 selector 숨김
                self.slice_group.setChecked(False)
                self.statusBar().showMessage("File ready for analysis.")
                self.final_result = None
                self.export_button.setEnabled(False)
            except Exception as e:
                # ... (에러 처리)
                pass

    def run_pipeline(self):
        if self.raw_data is None:
            # ... (에러 처리)
            return
        try:
            config = {
                'slice_filter_by': 'time',
                'slice_start_val': float(self.le_slice_start.text()) if self.slice_group.isChecked() else self.parsed_data.index.min(),
                'slice_end_val': float(self.le_slice_end.text()) if self.slice_group.isChecked() else self.parsed_data.index.max(),
                # ... (기타 config)
            }
        except Exception as e:
            # ... (에러 처리)
            return

        self.run_button.setEnabled(False)
        self.export_button.setEnabled(False)
        self.log_output.clear()
        self.statusBar().showMessage("Running analysis...")

        # PipelineWorker에게 캐시된 parsed_data도 함께 전달
        self.worker = PipelineWorker(self.pipeline_controller, config, self.header_info, self.raw_data, self.parsed_data)
        self.worker.start()

    def on_analysis_finished(self, result_df):
        self.run_button.setEnabled(True)
        self.final_result = result_df

        if result_df.empty:
            self.statusBar().showMessage("Analysis failed.")
            self.export_button.setEnabled(False)
        else:
            self.statusBar().showMessage("Analysis complete.")
            self.export_button.setEnabled(True)

    def update_plot(self):
        """현재 선택된 데이터를 기반으로 플롯을 업데이트합니다."""
        df = self.parsed_data
        if df is None or df.empty:
            self.plot_manager.draw_plot(None, [])
            return

        selected_axis_generic = self.combo_plot_axis.currentData()
        columns_to_plot = []

        # 현재 선택된 타겟이 없으면, Rigid Body Position을 기본으로 플로팅
        targets_to_process = self.current_selected_targets
        if not targets_to_process and RigidBodyCols.BASE_NAME in self.data_loader.get_plottable_targets(df):
            targets_to_process = [RigidBodyCols.BASE_NAME]

        # 축 이름과 타겟 이름을 조합하여 실제 컬럼 이름 생성
        axis_map = {
            PoseCols.POS_X: RawMarkerCols.X_SUFFIX,
            PoseCols.POS_Y: RawMarkerCols.Y_SUFFIX,
            PoseCols.POS_Z: RawMarkerCols.Z_SUFFIX,
        }
        axis_suffix = axis_map.get(selected_axis_generic)

        if axis_suffix:
            for target in targets_to_process:
                # 사용자가 선택한 '표시용 이름'을 데이터프레임의 실제 '기본 이름'으로 역변환합니다.
                # 이 로직은 data_loader.get_plottable_targets의 이름 생성 규칙과 반드시 동기화되어야 합니다.
                base_name = None
                if target == DisplayNames.RB_CENTER:
                    # 'Rigid Body Center' -> 'RigidBody_Position'
                    base_name = RigidBodyCols.BASE_NAME
                elif target.startswith(DisplayNames.MARKER_PREFIX):
                    # 'Marker B1' -> 'B1'
                    base_name = target.replace(DisplayNames.MARKER_PREFIX, '')
                else:
                    # 기타 (예: 레거시 이름)는 그대로 사용
                    base_name = target

                # 기본 이름과 축 접미사를 조합하여 최종 컬럼명을 만듭니다.
                # 예: 'B1' + '_X' -> 'B1_X'
                col_name = f"{base_name}{axis_suffix}"

                if col_name in df.columns:
                    columns_to_plot.append(col_name)

        self.plot_manager.draw_plot(df, columns_to_plot)

    def open_data_selection_dialog(self):
        """플로팅할 데이터를 선택하는 다이얼로그를 엽니다."""
        if self.parsed_data is None:
            return

        all_targets = self.data_loader.get_plottable_targets(self.parsed_data)

        dialog = DataSelectionDialog(all_targets, self.current_selected_targets, self)
        if dialog.exec():
            self.current_selected_targets = dialog.get_selected_items()
            self.selected_data_label.setText(f"Selected: {', '.join(self.current_selected_targets)}")
            self.update_plot()

    def on_region_changed(self, xmin: float, xmax: float):
        """SpanSelector의 변경사항을 QLineEdit에 반영합니다."""
        # 무한 루프 방지를 위해 시그널을 잠시 비활성화
        self.le_slice_start.blockSignals(True)
        self.le_slice_end.blockSignals(True)

        self.le_slice_start.setText(f"{xmin:.2f}")
        self.le_slice_end.setText(f"{xmax:.2f}")

        # 다시 활성화
        self.le_slice_start.blockSignals(False)
        self.le_slice_end.blockSignals(False)

    def toggle_slicing_widgets(self, checked: bool):
        """'Enable Slice' 체크박스 상태에 따라 슬라이싱 관련 위젯들을 제어합니다."""
        self.le_slice_start.setEnabled(checked)
        self.le_slice_end.setEnabled(checked)
        self.plot_manager.set_selector_active(checked)

    def update_span_selector_from_inputs(self):
        """QLineEdit의 값을 읽어 SpanSelector의 영역을 업데이트합니다."""
        try:
            start_val = float(self.le_slice_start.text())
            end_val = float(self.le_slice_end.text())

            # start_val이 end_val보다 크지 않도록 보장
            if start_val > end_val:
                # 예를 들어, start_val을 end_val과 같게 설정하거나, 사용자에게 경고를 표시할 수 있습니다.
                # 여기서는 start_val을 end_val과 같게 만듭니다.
                start_val = end_val
                self.le_slice_start.setText(f"{start_val:.2f}")

            self.plot_manager.set_region(start_val, end_val)
        except (ValueError, TypeError):
            # QLineEdit에 유효하지 않은 숫자(예: 문자)가 있을 경우 무시
            pass

    def export_results(self):
        """분석 완료된 데이터를 멀티헤더 CSV 파일로 저장합니다."""
        if self.final_result is None or self.final_result.empty:
            self.statusBar().showMessage("No analysis result to export.")
            return

        filepath, _ = QFileDialog.getSaveFileName(
            self, "Export Results to CSV", "", "CSV Files (*.csv)"
        )

        if filepath:
            try:
                # 데이터프레임을 멀티헤더로 변환
                export_df = convert_to_multi_header(self.final_result)

                # 멀티헤더 DataFrame을 CSV로 저장
                export_df.to_csv(filepath, index=False)

                self.statusBar().showMessage(f"Results successfully exported to {filepath}")
                self.log_output.append(f"[INFO] Results exported to {filepath}")
            except Exception as e:
                self.statusBar().showMessage(f"Error exporting file: {e}")
                self.log_output.append(f"[ERROR] Could not export file: {e}")

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MainApp()
    window.show()
    sys.exit(app.exec())
