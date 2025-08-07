import sys
import os
from PySide6.QtCore import QThread, QTimer, Qt
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QLineEdit, QComboBox, QTextEdit, QStatusBar, QGridLayout,
    QFileDialog, QListWidget, QScrollArea, QCheckBox, QGroupBox, QTreeWidget, QTreeWidgetItem
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
        self.parsed_data = parsed_data
    def run(self):
        self.controller.run_analysis(self.config, self.header_info, self.raw_data, self.parsed_data)

class MainApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Box Motion Analyzer v2.1")
        self.setGeometry(100, 100, 1200, 900)

        # 모듈 초기화
        self.data_loader = DataLoader()
        self.parser = Parser(face_prefix_map=FACE_PREFIX_TO_INFO)
        self.pipeline_controller = PipelineController()

        # 데이터 저장 변수
        self.raw_data = None
        self.header_info = None
        self.parsed_data = None
        self.final_result = None
        self.current_selected_targets = []
        self.result_data = None

        # UI 구성
        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        # --- 1. 원본 분석 영역 ---
        original_analysis_group = QGroupBox("Original Data Analysis")
        original_layout = QVBoxLayout(original_analysis_group)

        # 1a. 상단 플롯 및 로그
        top_plot_layout = QHBoxLayout()
        self.fig1 = Figure(figsize=(5, 4), dpi=100)
        self.canvas1 = FigureCanvas(self.fig1)
        self.toolbar1 = NavigationToolbar(self.canvas1, self)
        plot_container1 = QWidget()
        plot_layout1 = QVBoxLayout(plot_container1)
        plot_layout1.setContentsMargins(0,0,0,0)
        plot_layout1.addWidget(self.toolbar1)
        plot_layout1.addWidget(self.canvas1)
        top_plot_layout.addWidget(plot_container1, 7)

        self.plot_manager1 = PlotManager(self.canvas1, self.fig1)
        self.plot_manager1.ax.text(0.5, 0.5, "Load a CSV file to start.", ha='center', va='center')
        self.plot_manager1.canvas.draw()

        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setPlaceholderText("[INFO] Load a CSV file to start.")
        top_plot_layout.addWidget(self.log_output, 3)
        original_layout.addLayout(top_plot_layout)

        # 1b. 하단 원본 컨트롤
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        original_controls_widget = QWidget()
        original_controls_layout = QGridLayout(original_controls_widget)

        self.load_csv_button = QPushButton("Load CSV File...")
        original_controls_layout.addWidget(self.load_csv_button, 0, 0, 1, 7)
        self.file_path_label = QLabel("No file selected.")
        original_controls_layout.addWidget(self.file_path_label, 1, 0, 1, 7)

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
        original_controls_layout.addWidget(plot_options_group, 2, 0, 1, 3)

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
        original_controls_layout.addWidget(self.slice_group, 2, 3, 1, 2)

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
        original_controls_layout.addWidget(box_dims_group, 2, 5, 1, 2)

        run_button_layout = QHBoxLayout()
        self.run_button = QPushButton("Run Analysis")
        self.export_button = QPushButton("Export Results to CSV")
        self.export_button.setEnabled(False)
        run_button_layout.addStretch()
        run_button_layout.addWidget(self.run_button)
        run_button_layout.addWidget(self.export_button)
        original_controls_layout.addLayout(run_button_layout, 3, 0, 1, 7)

        scroll_area.setWidget(original_controls_widget)
        original_layout.addWidget(scroll_area)

        main_layout.addWidget(original_analysis_group)

        # --- 2. 결과 분석 그래프 영역 ---
        result_plot_group = QGroupBox("Result Data Plot")
        result_plot_layout = QVBoxLayout(result_plot_group)
        self.fig2 = Figure(figsize=(5, 2), dpi=100)
        self.canvas2 = FigureCanvas(self.fig2)
        self.toolbar2 = NavigationToolbar(self.canvas2, self)
        result_plot_layout.addWidget(self.toolbar2)
        result_plot_layout.addWidget(self.canvas2)
        self.plot_manager2 = PlotManager(self.canvas2, self.fig2)
        main_layout.addWidget(result_plot_group)

        # --- 3. 결과 컨트롤 패널 ---
        self.result_controls_group = QGroupBox("Result Analyzer")
        # 이 부분은 다음 단계에서 채워집니다.
        self.result_controls_group.setLayout(QVBoxLayout())
        main_layout.addWidget(self.result_controls_group)

        # 전체 레이아웃 비율 조정
        main_layout.setStretch(0, 5)
        main_layout.setStretch(1, 4)
        main_layout.setStretch(2, 3)

        self.setStatusBar(QStatusBar())

    def _connect_signals(self):
        self.load_csv_button.clicked.connect(self.open_csv_file)
        self.select_data_button.clicked.connect(self.open_data_selection_dialog)
        self.run_button.clicked.connect(self.run_pipeline)
        self.export_button.clicked.connect(self.export_results)
        self.combo_plot_axis.currentIndexChanged.connect(self.update_plot)
        self.plot_manager1.region_changed_signal.connect(self.on_region_changed)
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
                self.parsed_data = self.parser.process(self.header_info, self.raw_data)
                self.log_output.append("[INFO] Preview parsing complete.")

                all_targets = self.data_loader.get_plottable_targets(self.parsed_data)
                if DisplayNames.RB_CENTER in all_targets:
                    self.current_selected_targets = [DisplayNames.RB_CENTER]
                    self.selected_data_label.setText(f"Selected: {DisplayNames.RB_CENTER}")
                    self.log_output.append(f"[INFO] Default target '{DisplayNames.RB_CENTER}' selected for plotting.")

                self.update_plot()
                self.plot_manager1.enable_interactions(self.parsed_data)
                self.slice_group.setChecked(False)
                self.statusBar().showMessage("File ready for analysis.")
                self.final_result = None
                self.export_button.setEnabled(False)
            except Exception as e:
                self.log_output.append(f"[ERROR] Failed to load or parse file: {e}")
                self.statusBar().showMessage(f"Error: {e}")

    def run_pipeline(self):
        if self.raw_data is None:
            return
        try:
            config = {
                'slice_filter_by': 'time',
                'slice_start_val': float(self.le_slice_start.text()) if self.slice_group.isChecked() else self.parsed_data.index.min(),
                'slice_end_val': float(self.le_slice_end.text()) if self.slice_group.isChecked() else self.parsed_data.index.max(),
            }
        except Exception as e:
            self.statusBar().showMessage(f"Invalid analysis configuration: {e}")
            return

        self.run_button.setEnabled(False)
        self.export_button.setEnabled(False)
        self.log_output.clear()
        self.statusBar().showMessage("Running analysis...")

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
        df = self.parsed_data
        if df is None or df.empty:
            self.plot_manager1.draw_plot(None, [])
            return

        selected_axis_generic = self.combo_plot_axis.currentData()
        columns_to_plot = []
        targets_to_process = self.current_selected_targets

        if not targets_to_process:
             # Check if default can be plotted
            all_targets = self.data_loader.get_plottable_targets(df)
            if DisplayNames.RB_CENTER in all_targets:
                targets_to_process = [DisplayNames.RB_CENTER]

        axis_map = {
            PoseCols.POS_X: RawMarkerCols.X_SUFFIX,
            PoseCols.POS_Y: RawMarkerCols.Y_SUFFIX,
            PoseCols.POS_Z: RawMarkerCols.Z_SUFFIX,
        }
        axis_suffix = axis_map.get(selected_axis_generic)

        if axis_suffix:
            for target in targets_to_process:
                base_name = None
                if target == DisplayNames.RB_CENTER:
                    base_name = RigidBodyCols.BASE_NAME
                elif target.startswith(DisplayNames.MARKER_PREFIX):
                    base_name = target.replace(DisplayNames.MARKER_PREFIX, '')
                else:
                    base_name = target

                col_name = f"{base_name}{axis_suffix}"
                if col_name in df.columns:
                    columns_to_plot.append(col_name)

        self.plot_manager1.draw_plot(df, columns_to_plot)

    def open_data_selection_dialog(self):
        if self.parsed_data is None:
            return
        all_targets = self.data_loader.get_plottable_targets(self.parsed_data)
        dialog = DataSelectionDialog(all_targets, self.current_selected_targets, self)
        if dialog.exec():
            self.current_selected_targets = dialog.get_selected_items()
            self.selected_data_label.setText(f"Selected: {', '.join(self.current_selected_targets)}")
            self.update_plot()

    def on_region_changed(self, xmin: float, xmax: float):
        self.le_slice_start.blockSignals(True)
        self.le_slice_end.blockSignals(True)
        self.le_slice_start.setText(f"{xmin:.2f}")
        self.le_slice_end.setText(f"{xmax:.2f}")
        self.le_slice_start.blockSignals(False)
        self.le_slice_end.blockSignals(False)

    def toggle_slicing_widgets(self, checked: bool):
        self.le_slice_start.setEnabled(checked)
        self.le_slice_end.setEnabled(checked)
        self.plot_manager1.set_selector_active(checked)

    def update_span_selector_from_inputs(self):
        try:
            start_val = float(self.le_slice_start.text())
            end_val = float(self.le_slice_end.text())
            if start_val > end_val:
                start_val = end_val
                self.le_slice_start.setText(f"{start_val:.2f}")
            self.plot_manager1.set_region(start_val, end_val)
        except (ValueError, TypeError):
            pass

    def export_results(self):
        if self.final_result is None or self.final_result.empty:
            return
        filepath, _ = QFileDialog.getSaveFileName(self, "Export Results to CSV", "", "CSV Files (*.csv)")
        if filepath:
            try:
                export_df = convert_to_multi_header(self.final_result)
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
