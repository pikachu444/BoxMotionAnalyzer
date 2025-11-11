import sys
import os
import pandas as pd
from PySide6.QtCore import QThread, QTimer, Qt
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QLineEdit, QComboBox, QTextEdit, QStatusBar, QGridLayout,
    QFileDialog, QListWidget, QScrollArea, QCheckBox, QGroupBox, QTreeWidget, QTreeWidgetItem,
    QFormLayout
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
    DisplayNames, RESULT_TIME_COL, DISPLAY_RESULT_COLUMNS, TimeCols, HeaderL1, HeaderL2, HeaderL3,
    CORNER_NAME_MAP
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
        self.setWindowTitle("Box Motion Analyzer v2.2")
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
        self.last_selected_result_columns = set()
        self.selected_point_info = {'time': None, 'index': None}
        self.result_point_cursor = None

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

        plot_container1 = QWidget()
        plot_layout1 = QVBoxLayout(plot_container1)
        plot_layout1.setContentsMargins(0,0,0,0)
        self.fig1 = Figure(figsize=(5, 4), dpi=100)
        self.fig1.subplots_adjust(left=0.08, right=0.98, bottom=0.1, top=0.95)
        self.canvas1 = FigureCanvas(self.fig1)
        self.toolbar1 = NavigationToolbar(self.canvas1, self)
        plot_layout1.addWidget(self.toolbar1)
        plot_layout1.addWidget(self.canvas1)

        self.plot_manager1 = PlotManager(self.canvas1, self.fig1)
        self.plot_manager1.ax.text(0.5, 0.5, "Load a CSV file to start.", ha='center', va='center')
        self.plot_manager1.canvas.draw()

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

        top_layout.addWidget(plot_container1, 8)
        top_layout.addLayout(right_panel_layout, 2)
        original_layout.addLayout(top_layout)

        # 1b. 하단 원본 컨트롤 (공간 효율적으로 재배치)
        original_controls_widget = QWidget()
        h_controls_layout = QHBoxLayout(original_controls_widget)

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

        run_button_layout = QVBoxLayout()
        self.run_button = QPushButton("Run Analysis")
        self.export_button = QPushButton("Export Results to CSV")
        self.export_button.setEnabled(False)
        run_button_layout.addWidget(self.run_button)
        run_button_layout.addWidget(self.export_button)
        h_controls_layout.addLayout(run_button_layout)

        original_layout.addWidget(original_controls_widget)
        main_layout.addWidget(original_analysis_group)

        # --- 2. 결과 분석 영역 (그래프와 컨트롤을 좌우로 배치) ---
        result_analysis_group = QGroupBox("Result Analyzer")
        result_analysis_layout = QHBoxLayout(result_analysis_group)

        # 2a. 좌측: 결과 그래프
        result_plot_container = QWidget()
        result_plot_layout = QVBoxLayout(result_plot_container)
        self.fig2 = Figure(figsize=(5, 4), dpi=100)
        self.fig2.subplots_adjust(left=0.08, right=0.98, bottom=0.1, top=0.95)
        self.canvas2 = FigureCanvas(self.fig2)
        self.toolbar2 = NavigationToolbar(self.canvas2, self)
        result_plot_layout.addWidget(self.toolbar2)
        result_plot_layout.addWidget(self.canvas2)
        self.plot_manager2 = PlotManager(self.canvas2, self.fig2)
        result_analysis_layout.addWidget(result_plot_container, 6) # 그래프가 6의 비율

        # 2b. 우측: 결과 컨트롤
        result_controls_container = QWidget()
        result_controls_main_layout = QVBoxLayout(result_controls_container)

        file_browser_layout = QVBoxLayout()
        file_browser_controls_layout = QHBoxLayout()
        self.select_result_folder_button = QPushButton("Select Result Folder...")
        self.plot_results_button = QPushButton("Plot Selected Results")
        self.plot_results_button.setEnabled(False)
        file_browser_controls_layout.addWidget(self.select_result_folder_button)
        file_browser_controls_layout.addWidget(self.plot_results_button)
        file_browser_layout.addLayout(file_browser_controls_layout)
        self.result_folder_path_label = QLabel("No folder selected.")
        file_browser_layout.addWidget(self.result_folder_path_label)

        # New horizontal layout for the list and tree
        list_tree_layout = QHBoxLayout()
        self.result_file_list = QListWidget()
        list_tree_layout.addWidget(self.result_file_list)

        self.result_data_tree = QTreeWidget()
        self.result_data_tree.setHeaderLabel("Select Data to Plot")
        self.result_data_tree.setEnabled(False)
        list_tree_layout.addWidget(self.result_data_tree)

        result_controls_main_layout.addLayout(file_browser_layout)
        result_controls_main_layout.addLayout(list_tree_layout)

        # Point Analysis GroupBox
        point_analysis_group = QGroupBox("지점 분석 (Point Analysis)")
        point_analysis_layout = QVBoxLayout(point_analysis_group)

        find_max_layout = QHBoxLayout()
        find_max_layout.addWidget(QLabel("Target:"))
        self.find_max_target_combo = QComboBox()
        find_max_layout.addWidget(self.find_max_target_combo)
        self.find_max_button = QPushButton("Find Abs. Max")
        find_max_layout.addWidget(self.find_max_button)
        point_analysis_layout.addLayout(find_max_layout)

        selected_export_layout = QHBoxLayout()
        self.selected_point_label = QLabel("Selected: None")
        selected_export_layout.addWidget(self.selected_point_label)
        selected_export_layout.addStretch()
        self.export_point_button = QPushButton("Export Point Data...")
        self.export_point_button.setEnabled(False)
        selected_export_layout.addWidget(self.export_point_button)
        point_analysis_layout.addLayout(selected_export_layout)

        result_controls_main_layout.addWidget(point_analysis_group)

        # Analysis Scenario Output GroupBox
        analysis_scenario_group = QGroupBox("해석 시나리오 출력")
        analysis_scenario_layout = QVBoxLayout(analysis_scenario_group)

        self.offset_manual_checkbox = QCheckBox("수동 오프셋 선택")
        analysis_scenario_layout.addWidget(self.offset_manual_checkbox)

        self.offset_combos = []
        for i in range(3):
            offset_layout = QHBoxLayout()
            offset_layout.addWidget(QLabel(f"오프셋{i}:"))
            combo = QComboBox()
            combo.addItems([f"C{j+1}" for j in range(8)])
            combo.setEnabled(False)
            offset_layout.addWidget(combo)
            self.offset_combos.append(combo)
            analysis_scenario_layout.addLayout(offset_layout)

        scenario_form_layout = QFormLayout()
        self.le_run_time = QLineEdit("0.1")
        self.le_time_step = QLineEdit("1e-7")
        self.le_scene_name = QLineEdit("")
        scenario_form_layout.addRow("analysis run time:", self.le_run_time)
        scenario_form_layout.addRow("critical time step:", self.le_time_step)
        scenario_form_layout.addRow("drop scene name:", self.le_scene_name)
        analysis_scenario_layout.addLayout(scenario_form_layout)

        self.export_scenario_button = QPushButton("Export analysis input")
        analysis_scenario_layout.addWidget(self.export_scenario_button)

        result_controls_main_layout.addWidget(analysis_scenario_group)

        result_analysis_layout.addWidget(result_controls_container, 4) # 컨트롤이 4의 비율

        main_layout.addWidget(result_analysis_group)
        main_layout.setStretch(0, 4)
        main_layout.setStretch(1, 6)

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
        self.canvas2.mpl_connect('button_press_event', self.on_result_plot_click)
        self.find_max_button.clicked.connect(self.on_find_max_click)
        self.export_point_button.clicked.connect(self.on_export_point_data_click)

        # Connections for Analysis Scenario Output
        self.offset_manual_checkbox.toggled.connect(self._on_offset_checkbox_toggled)
        for combo in self.offset_combos:
            combo.currentIndexChanged.connect(self._update_offset_choices)
        self.export_scenario_button.clicked.connect(self.export_analysis_scenario)

    def export_analysis_scenario(self):
        """'해석 시나리오 출력' 그룹의 설정값과 분석 데이터를 조합하여 지정된 포맷의 CSV로 저장합니다."""
        # 1. 유효성 검사: 분석 결과 및 선택된 시간 지점이 있는지 확인
        if self.result_data is None or self.selected_point_info.get('time') is None:
            self.log_output.append("[ERROR] No data point selected. Please click on the result graph to select a time point.")
            self.statusBar().showMessage("Error: No data point selected.")
            return

        selected_time = self.selected_point_info['time']
        time_point_data = self.result_data.loc[selected_time]

        # 2. 오프셋 데이터 가져오기 (자동/수동 분기)
        is_manual_offset = self.offset_manual_checkbox.isChecked()
        if is_manual_offset:
            offset_data = self._get_manual_offset_data(time_point_data)
        else:
            offset_data = self._get_automatic_offset_data(time_point_data)

        if not offset_data or len(offset_data) < 3:
            self.log_output.append("[ERROR] Could not determine 3 offset points. Aborting export.")
            return

        # 3. 속도 및 기타 데이터 가져오기
        vel_cols = {
            'ANG_VEL_X': (HeaderL1.VEL, HeaderL2.COM, HeaderL3.WX),
            'ANG_VEL_Y': (HeaderL1.VEL, HeaderL2.COM, HeaderL3.WY),
            'ANG_VEL_Z': (HeaderL1.VEL, HeaderL2.COM, HeaderL3.WZ),
            'TRA_VEL_X': (HeaderL1.VEL, HeaderL2.COM, HeaderL3.VX),
            'TRA_VEL_Y': (HeaderL1.VEL, HeaderL2.COM, HeaderL3.VY),
            'TRA_VEL_Z': (HeaderL1.VEL, HeaderL2.COM, HeaderL3.VZ),
        }
        velocities = {key: time_point_data.get(col, 0.0) for key, col in vel_cols.items()}

        # 4. 최종 CSV 데이터 리스트 구성
        output_data = [
            ('1', 'Left'), ('2', 'Right'), ('3', 'Bottom'),
            ('4', 'Top'), ('5', 'Rear'), ('6', 'Front'),
            ('cat', 'Corner_Drop_2nd'),
            ('drop_name', self.le_scene_name.text()),
        ]

        # 오프셋 데이터 추가
        for i, (corner_name, corner_value) in enumerate(offset_data):
            variable_name = CORNER_NAME_MAP.get(corner_name, "Unknown")
            output_data.append((f'variable_{i+1}', variable_name))
            output_data.append((f'value_{i+1}', f'{corner_value:.6f}'))

        output_data.extend([
            ('variable_4', 'OFFSET'), ('value_4', '0.0'),
            ('variable_5', 'ANG_VEL_X'), ('value_5', f"{velocities['ANG_VEL_X']:.6f}"),
            ('variable_6', 'ANG_VEL_Y'), ('value_6', f"{velocities['ANG_VEL_Y']:.6f}"),
            ('variable_7', 'ANG_VEL_Z'), ('value_7', f"{velocities['ANG_VEL_Z']:.6f}"),
            ('variable_8', 'TRA_VEL_X'), ('value_8', f"{velocities['TRA_VEL_X']:.6f}"),
            ('variable_9', 'TRA_VEL_Y'), ('value_9', f"{velocities['TRA_VEL_Y']:.6f}"),
            ('variable_10', 'TRA_VEL_Z'), ('value_10', f"{velocities['TRA_VEL_Z']:.6f}"),
            ('variable_11', 'POSI_FROM_CENT_X'), ('value_11', '0.0'),
            ('variable_12', 'POSI_FROM_CENT_Y'), ('value_12', '0.0'),
            ('variable_13', 'POSI_FROM_CENT_Z'), ('value_13', '0.0'),
            ('run_time', self.le_run_time.text()),
            ('tmin', self.le_time_step.text()),
        ])

        # 5. 파일 저장
        suggested_filename = f"scenario_{self.le_scene_name.text()}.csv" if self.le_scene_name.text() else "analysis_scenario.csv"
        filepath, _ = QFileDialog.getSaveFileName(self, "Export Analysis Scenario", suggested_filename, "CSV Files (*.csv)")

        if filepath:
            try:
                # 새로운 포맷에 맞게 문자열 생성
                # 첫 6개 아이템은 줄바꿈으로, 나머지는 쉼표로 연결
                lines = [f"{key},{value}" for key, value in output_data[:6]]
                last_line = ",".join([f"{key},{value}" for key, value in output_data[6:]])
                csv_string = "\n".join(lines) + "\n" + last_line

                with open(filepath, 'w') as f:
                    f.write(csv_string)
                self.log_output.append(f"[SUCCESS] Analysis scenario exported to {filepath}")
                self.statusBar().showMessage(f"Scenario exported to {filepath}")
            except Exception as e:
                self.log_output.append(f"[ERROR] Could not export scenario: {e}")
                self.statusBar().showMessage(f"Error exporting scenario: {e}")

    def _get_automatic_offset_data(self, time_point_data):
        """자동 오프셋 계산 로직을 수행합니다."""
        height_cols = [(HeaderL1.ANALYSIS_SCENARIO, f'C{i+1}', HeaderL3.ANALYSIS_INPUT_H) for i in range(8)]

        # 1. 8개 코너의 높이 값 추출
        corner_heights = {}
        for i, col in enumerate(height_cols):
            if col in time_point_data:
                corner_heights[f'C{i+1}'] = time_point_data[col]
            else:
                self.log_output.append(f"[WARNING] Automatic offset calculation: Column {col} not found in data.")
                return []

        if not corner_heights:
            return []

        # 2. 가장 낮은 높이의 코너 찾기
        min_corner = min(corner_heights, key=corner_heights.get)

        # 3. 그룹 식별 및 정렬
        min_corner_num = int(min_corner[1:])
        group1 = {f'C{i}': corner_heights[f'C{i}'] for i in range(1, 5)}
        group2 = {f'C{i}': corner_heights[f'C{i}'] for i in range(5, 9)}

        target_group = group1 if 1 <= min_corner_num <= 4 else group2

        # 4. 동일 그룹 내에서 높이가 낮은 순으로 정렬하여 상위 3개 선택
        sorted_corners = sorted(target_group.items(), key=lambda item: item[1])

        # 5. 결과 반환 (코너 이름, 높이 값)
        return sorted_corners[:3]

    def _get_manual_offset_data(self, time_point_data):
        """수동 오프셋 계산 로직을 수행합니다."""
        selected_corners = [combo.currentText() for combo in self.offset_combos]

        offset_data = []
        for corner_name in selected_corners:
            height_col = (HeaderL1.ANALYSIS_SCENARIO, corner_name, HeaderL3.ANALYSIS_INPUT_H)
            if height_col in time_point_data:
                offset_data.append((corner_name, time_point_data[height_col]))
            else:
                self.log_output.append(f"[WARNING] Manual offset selection: Column {height_col} not found in data.")
                # 데이터를 찾을 수 없는 경우, 값으로 0 또는 None을 사용할 수 있습니다. 여기서는 0.0을 사용합니다.
                offset_data.append((corner_name, 0.0))

        return offset_data

    def _on_offset_checkbox_toggled(self, checked):
        """Enable/disable offset comboboxes based on checkbox state."""
        for combo in self.offset_combos:
            combo.setEnabled(checked)
        if not checked:
            # Optional: Reset to default state when unchecked
            self._update_offset_choices()

    def _update_offset_choices(self):
        """Update dropdown choices to prevent duplicate selections."""
        all_options = [f"C{i+1}" for i in range(8)]
        selected_options = [combo.currentText() for combo in self.offset_combos if combo.isEnabled()]

        for i, combo in enumerate(self.offset_combos):
            if not combo.isEnabled():
                continue

            current_selection = combo.currentText()
            other_selections = [opt for j, opt in enumerate(selected_options) if i != j]

            # Temporarily disconnect signal to prevent recursion
            combo.blockSignals(True)

            combo.clear()

            # Add the currently selected item first
            combo.addItem(current_selection)

            # Add other available options
            for option in all_options:
                if option != current_selection and option not in other_selections:
                    combo.addItem(option)

            combo.setCurrentText(current_selection)

            # Reconnect signal
            combo.blockSignals(False)

    def plot_selected_results(self):
        if self.result_data is None: return
        self.last_selected_result_columns.clear()
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
                        self.last_selected_result_columns.add(column_tuple)

        self.log_output.append(f"[INFO] Plotting {len(checked_columns)} result columns...")
        self.log_output.append(f"[INFO] Stored {len(self.last_selected_result_columns)} selections for next load.")

        # Update the 'Find Max' target combobox
        self.find_max_target_combo.clear()
        for col in checked_columns:
            self.find_max_target_combo.addItem(f"{col[0]}/{col[1]}/{col[2]}", userData=col)

        if not checked_columns:
            self.plot_manager2.clear_plot()
            self.selected_point_info = {'time': None, 'index': None}
            self.update_point_selection_ui()
            # Reset the navigation toolbar's history to set the new "Home" state
            self.toolbar2.update()
            self.toolbar2.push_current()
            return

        # The DataFrame self.result_data should already have the correct index.
        # We no longer need to check for the time column or set the index here.
        plot_df = self.result_data[checked_columns].copy()
        self.plot_manager2.draw_plot(plot_df, checked_columns)

        # Reset the navigation toolbar's history to set the new "Home" state
        self.toolbar2.update()
        self.toolbar2.push_current()

        self.selected_point_info = {'time': None, 'index': None}
        self.update_point_selection_ui()

    def on_result_plot_click(self, event):
        if event.inaxes != self.plot_manager2.ax:
            return
        if self.result_data is None or self.result_data.empty:
            return

        time_val = event.xdata
        # Find the closest index in the dataframe using the modern pandas API
        indexer = self.result_data.index.get_indexer([time_val], method='nearest')
        closest_index = indexer[0]
        self.selected_point_info['index'] = closest_index
        self.selected_point_info['time'] = self.result_data.index[closest_index]

        # Explicitly enable the button here to be certain.
        self.export_point_button.setEnabled(True)
        self.update_point_selection_ui()

    def on_find_max_click(self):
        if self.result_data is None or self.result_data.empty:
            return

        target_column = self.find_max_target_combo.currentData()
        if target_column is None:
            self.log_output.append("[WARNING] No target data selected for 'Find Max'.")
            return

        try:
            max_index = self.result_data[target_column].abs().idxmax()
            max_value = self.result_data.loc[max_index, target_column]

            self.selected_point_info['index'] = self.result_data.index.get_loc(max_index)
            self.selected_point_info['time'] = max_index

            self.update_point_selection_ui(value=max_value)
            self.log_output.append(f"[INFO] Found max value for '{'/'.join(target_column)}': {max_value:.4f} at T={max_index:.3f}s")
        except Exception as e:
            self.log_output.append(f"[ERROR] Could not find max value: {e}")

    def update_point_selection_ui(self, value=None):
        if self.result_point_cursor:
            try:
                self.result_point_cursor.remove()
            except:
                pass
        self.result_point_cursor = None

        if self.selected_point_info.get('time') is not None:
            time = self.selected_point_info['time']
            self.result_point_cursor = self.plot_manager2.ax.axvline(x=time, color='r', linestyle='--', linewidth=1)
            self.plot_manager2.canvas.draw()

            if value is not None:
                self.selected_point_label.setText(f"Selected: T={time:.3f}s, Value={value:.4f}")
            else:
                self.selected_point_label.setText(f"Selected: T={time:.3f}s")
            self.export_point_button.setEnabled(True)
        else:
            self.selected_point_label.setText("Selected: None")
            self.export_point_button.setEnabled(False)
            self.plot_manager2.canvas.draw()

    def on_export_point_data_click(self):
        if self.result_data is None or self.selected_point_info.get('index') is None:
            self.log_output.append("[ERROR] No point selected to export.")
            return

        selected_index = self.selected_point_info['index']
        point_data = self.result_data.iloc[[selected_index]].copy()

        # Suggest a filename
        time_str = f"{self.selected_point_info['time']:.3f}".replace('.', '_')
        current_file = os.path.basename(self.result_file_list.currentItem().text())
        suggested_filename = f"{os.path.splitext(current_file)[0]}_point_at_{time_str}s.csv"

        filepath, _ = QFileDialog.getSaveFileName(self, "Export Point Data to CSV", suggested_filename, "CSV Files (*.csv)")

        if filepath:
            try:
                point_data.to_csv(filepath, index=True)
                self.log_output.append(f"[INFO] Point data successfully exported to {filepath}")
            except Exception as e:
                self.log_output.append(f"[ERROR] Could not export point data: {e}")

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

            # Set the time index on the main dataframe immediately after loading.
            time_col_tuple = RESULT_TIME_COL
            if time_col_tuple in self.result_data.columns:
                self.result_data.set_index(time_col_tuple, inplace=True)
                self.result_data.index.name = TimeCols.TIME
            elif TimeCols.TIME in self.result_data.columns:
                self.result_data.set_index(TimeCols.TIME, inplace=True)
                self.result_data.index.name = TimeCols.TIME

            # 'Time' 컬럼이 인덱스로 설정되었는지 확인하고, 그렇지 않으면 경고를 로깅합니다.
            if self.result_data.index.name != TimeCols.TIME:
                self.log_output.append(f"[WARNING] '{TimeCols.TIME}' column not found in {item.text()}. Using default integer index for plotting.")

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
        """Populates the QTreeWidget with a hierarchy from the DataFrame's multi-level columns."""
        self.result_data_tree.clear()
        top_level_items = {}

        # 표시할 컬럼을 DISPLAY_RESULT_COLUMNS 리스트를 기준으로 필터링합니다.
        # 데이터프레임에 실제로 존재하는 컬럼만 선택합니다.
        columns_to_plot = [col for col in df.columns if col in DISPLAY_RESULT_COLUMNS]

        for l1, l2, l3 in columns_to_plot:
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

            # Re-apply the last selection state
            column_tuple = (l1, l2, l3)
            if column_tuple in self.last_selected_result_columns:
                leaf_item.setCheckState(0, Qt.Checked)
            else:
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
            # Update box dimensions globally before starting the pipeline
            l = float(self.le_box_l.text())
            w = float(self.le_box_w.text())
            h = float(self.le_box_h.text())
            config_app.BOX_DIMS = [l, w, h]

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

