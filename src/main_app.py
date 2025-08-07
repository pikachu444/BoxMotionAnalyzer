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

        self.data_loader = DataLoader()
        self.parser = Parser(face_prefix_map=FACE_PREFIX_TO_INFO)
        self.pipeline_controller = PipelineController()

        self.raw_data = None
        self.header_info = None
        self.parsed_data = None
        self.final_result = None
        self.current_selected_targets = []
        self.result_data = None

        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        # --- 1. 원본 분석 영역 ---
        original_analysis_group = QGroupBox("Original Data Analysis")
        original_layout = QVBoxLayout(original_analysis_group)

        # 1a. 상단 플롯 및 재구성된 우측 패널
        top_layout = QHBoxLayout()

        # 좌측: 그래프
        plot_container1 = QWidget()
        plot_layout1 = QVBoxLayout(plot_container1)
        plot_layout1.setContentsMargins(0,0,0,0)
        self.fig1 = Figure(figsize=(5, 4), dpi=100)
        self.canvas1 = FigureCanvas(self.fig1)
        self.toolbar1 = NavigationToolbar(self.canvas1, self)
        plot_layout1.addWidget(self.toolbar1)
        plot_layout1.addWidget(self.canvas1)
        top_layout.addWidget(plot_container1, 7) # 그래프가 7의 비율 차지

        self.plot_manager1 = PlotManager(self.canvas1, self.fig1)
        self.plot_manager1.ax.text(0.5, 0.5, "Load a CSV file to start.", ha='center', va='center')
        self.plot_manager1.canvas.draw()

        # 우측: 재구성된 컨트롤/로그 패널
        right_panel_layout = QVBoxLayout()

        self.load_csv_button = QPushButton("Load CSV File...")
        right_panel_layout.addWidget(self.load_csv_button)
        self.file_path_label = QLabel("No file selected.")
        right_panel_layout.addWidget(self.file_path_label)

        self.box_dims_group = QGroupBox("Box Dimensions (mm)")
        box_dims_layout = QGridLayout(self.box_dims_group)
        box_dims_layout.addWidget(QLabel("L:"), 0, 0)
        self.le_box_l = QLineEdit("1820.0")
        box_dims_layout.addWidget(self.le_box_l, 0, 1)
        box_dims_layout.addWidget(QLabel("W:"), 1, 0)
        self.le_box_w = QLineEdit("1110.0")
        box_dims_layout.addWidget(self.le_box_w, 1, 1)
        box_dims_layout.addWidget(QLabel("H:"), 2, 0)
        self.le_box_h = QLineEdit("164.0")
        box_dims_layout.addWidget(self.le_box_h, 2, 1)
        right_panel_layout.addWidget(self.box_dims_group)

        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setPlaceholderText("[INFO] Load a CSV file to start.")
        right_panel_layout.addWidget(self.log_output) # 남은 공간을 로그가 채움

        top_layout.addLayout(right_panel_layout, 3) # 우측 패널이 3의 비율 차지
        original_layout.addLayout(top_layout, 5) # 상단 전체가 5의 비율

        # 1b. 하단 원본 컨트롤 (공간 효율적으로 재배치)
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        original_controls_widget = QWidget()

        # 메인 그리드 대신 수평 레이아웃 사용
        h_controls_layout = QHBoxLayout(original_controls_widget)

        # Plot Options (한 줄로 변경)
        plot_options_group = QGroupBox("Plot Options")
        plot_options_h_layout = QHBoxLayout(plot_options_group)
        self.select_data_button = QPushButton("Select Data...")
        self.selected_data_label = QLabel("Selected: None")
        self.selected_data_label.setWordWrap(True)
        plot_options_h_layout.addWidget(self.select_data_button)
        plot_options_h_layout.addWidget(self.selected_data_label)
        plot_options_h_layout.addWidget(QLabel("Axis:"))
        self.combo_plot_axis = QComboBox()
        self.combo_plot_axis.addItem("Position-X", userData=PoseCols.POS_X)
        self.combo_plot_axis.addItem("Position-Y", userData=PoseCols.POS_Y)
        self.combo_plot_axis.addItem("Position-Z", userData=PoseCols.POS_Z)
        plot_options_h_layout.addWidget(self.combo_plot_axis)
        h_controls_layout.addWidget(plot_options_group)

        # Slice Range (한 줄로 변경)
        self.slice_group = QGroupBox("Slice Range")
        self.slice_group.setCheckable(True)
        self.slice_group.setChecked(False)
        slice_h_layout = QHBoxLayout(self.slice_group)
        slice_h_layout.addWidget(QLabel("Start:"))
        self.le_slice_start = QLineEdit()
        slice_h_layout.addWidget(self.le_slice_start)
        slice_h_layout.addWidget(QLabel("End:"))
        self.le_slice_end = QLineEdit()
        slice_h_layout.addWidget(self.le_slice_end)
        h_controls_layout.addWidget(self.slice_group)

        # 실행 버튼
        run_button_layout = QVBoxLayout()
        self.run_button = QPushButton("Run Analysis")
        self.export_button = QPushButton("Export Results to CSV")
        self.export_button.setEnabled(False)
        run_button_layout.addWidget(self.run_button)
        run_button_layout.addWidget(self.export_button)
        h_controls_layout.addLayout(run_button_layout)

        scroll_area.setWidget(original_controls_widget)
        original_layout.addWidget(scroll_area, 1) # 하단 컨트롤이 1의 비율

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
        result_controls_main_layout = QVBoxLayout(self.result_controls_group)
        top_controls_layout = QHBoxLayout()
        self.result_data_tree = QTreeWidget()
        self.result_data_tree.setHeaderLabel("Select Data to Plot")
        self.result_data_tree.setEnabled(False)
        top_controls_layout.addWidget(self.result_data_tree, 1)

        file_browser_layout = QVBoxLayout()
        file_browser_controls_layout = QHBoxLayout()
        self.select_result_folder_button = QPushButton("Select Result Folder...")
        self.recent_files_combo = QComboBox()
        self.recent_files_combo.addItem("Recent Files...")
        file_browser_controls_layout.addWidget(self.select_result_folder_button)
        file_browser_controls_layout.addWidget(self.recent_files_combo)
        file_browser_layout.addLayout(file_browser_controls_layout)
        self.result_folder_path_label = QLabel("No folder selected.")
        file_browser_layout.addWidget(self.result_folder_path_label)
        self.result_file_list = QListWidget()
        file_browser_layout.addWidget(self.result_file_list)
        top_controls_layout.addLayout(file_browser_layout, 1)

        result_controls_main_layout.addLayout(top_controls_layout)
        self.plot_results_button = QPushButton("Plot Selected Results")
        self.plot_results_button.setEnabled(False)
        result_controls_main_layout.addWidget(self.plot_results_button, 0, Qt.AlignRight)
        main_layout.addWidget(self.result_controls_group)

        main_layout.setStretch(0, 5)
        main_layout.setStretch(1, 3)
        main_layout.setStretch(2, 4)

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
        self.select_result_folder_button.clicked.connect(self.select_result_folder)
        self.result_file_list.itemClicked.connect(self.on_result_file_selected)
        self.plot_results_button.clicked.connect(self.plot_selected_results)

    def plot_selected_results(self):
        if self.result_data is None: return
        checked_columns = []
        root = self.result_data_tree.invisibleRootItem()
        for i in range(root.childCount()):
            top_item = root.child(i)
            for j in range(top_item.childCount()):
                mid_item = top_item.child(j)
                for k in range(mid_item.childCount()):
                    leaf_item = mid_item.child(k)
                    if leaf_item.checkState(0) == Qt.Checked:
                        column_tuple = (top_item.text(0), mid_item.text(0), leaf_item.text(0))
                        checked_columns.append(column_tuple)
        self.log_output.append(f"[INFO] Plotting {len(checked_columns)} result columns...")
        time_col_tuple = ('Info', 'Time', 's')
        if time_col_tuple not in self.result_data.columns:
            self.log_output.append("[ERROR] Could not find time column in result data.")
            return
        plot_df = self.result_data[checked_columns + [time_col_tuple]].copy()
        plot_df.set_index(time_col_tuple, inplace=True)
        self.plot_manager2.draw_plot(plot_df, checked_columns)

    def select_result_folder(self):
        folder_path = QFileDialog.getExistingDirectory(self, "Select Result Folder")
        if folder_path:
            self.result_folder_path_label.setText(folder_path)
            self.result_file_list.clear()
            self.result_data_tree.clear()
            self.result_data_tree.setEnabled(False)
            self.plot_results_button.setEnabled(False)
            try:
                files = [f for f in os.listdir(folder_path) if f.endswith('.csv')]
                self.result_file_list.addItems(files)
                self.log_output.append(f"[INFO] Found {len(files)} CSV files in {folder_path}")
            except Exception as e:
                self.log_output.append(f"[ERROR] Failed to read folder: {e}")

    def on_result_file_selected(self, item):
        folder_path = self.result_folder_path_label.text()
        file_path = os.path.join(folder_path, item.text())
        try:
            self.log_output.append(f"[INFO] Loading result file: {file_path}")
            self.result_data = self.data_loader.load_result_csv(file_path)
            self.statusBar().showMessage("Result file loaded.")
            self.populate_result_tree(self.result_data)
            self.result_data_tree.setEnabled(True)
            self.plot_results_button.setEnabled(True)
            self.log_output.append("[INFO] Result data loaded. Please select data to plot.")
        except Exception as e:
            self.log_output.append(f"[ERROR] Failed to load result file: {e}")
            self.statusBar().showMessage(f"Error: {e}")
            self.result_data_tree.clear()
            self.result_data_tree.setEnabled(False)
            self.plot_results_button.setEnabled(False)

    def populate_result_tree(self, df):
        self.result_data_tree.clear()
        top_level_items = {}
        for l1, l2, l3 in df.columns:
            if l1 not in top_level_items:
                top_item = QTreeWidgetItem(self.result_data_tree, [l1])
                top_level_items[l1] = {'item': top_item, 'children': {}}
            top_level_node = top_level_items[l1]
            if l2 not in top_level_node['children']:
                mid_item = QTreeWidgetItem(top_level_node['item'], [l2])
                top_level_node['children'][l2] = mid_item
            mid_item = top_level_node['children'][l2]
            leaf_item = QTreeWidgetItem(mid_item, [l3])
            leaf_item.setFlags(leaf_item.flags() | Qt.ItemIsUserCheckable)
            leaf_item.setCheckState(0, Qt.Unchecked)
        self.result_data_tree.expandAll()

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
        if self.raw_data is None: return
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
        if self.parsed_data is None: return
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
        if self.final_result is None or self.final_result.empty: return
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
