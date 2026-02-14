import os
import pandas as pd
from PySide6.QtCore import Signal, Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, 
    QLineEdit, QComboBox, QTextEdit, QGroupBox, QTreeWidget, QTreeWidgetItem,
    QFileDialog, QListWidget, QFormLayout, QCheckBox, QGridLayout
)
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qtagg import NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure

from src.analysis.core.plot_manager import PlotManager
from src.config.data_columns import (
    DISPLAY_RESULT_COLUMNS, RESULT_TIME_COL, TimeCols, HeaderL1, HeaderL2, HeaderL3,
    AnalysisCols, CORNER_NAME_MAP
)

class WidgetResultsAnalyzer(QWidget):
    # Signals
    log_message = Signal(str)
    
    def __init__(self, data_loader):
        super().__init__()
        self.data_loader = data_loader
        
        self.result_data = None
        self.last_selected_result_columns = set()
        self.selected_point_info = {'time': None, 'index': None}
        self.result_point_cursor = None
        
        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        
        group_box = QGroupBox("Results Analyzer")
        group_layout = QHBoxLayout(group_box)

        # 2a. Left: Result Plot
        plot_container = QWidget()
        plot_layout = QVBoxLayout(plot_container)
        
        self.fig = Figure(figsize=(5, 4), dpi=100)
        self.fig.subplots_adjust(left=0.08, right=0.98, bottom=0.1, top=0.95)
        self.canvas = FigureCanvas(self.fig)
        self.toolbar = NavigationToolbar(self.canvas, self)
        
        plot_layout.addWidget(self.toolbar)
        plot_layout.addWidget(self.canvas)
        self.plot_manager = PlotManager(self.canvas, self.fig)
        
        group_layout.addWidget(plot_container, 6)

        # 2b. Right: Result Controls
        controls_container = QWidget()
        controls_layout = QVBoxLayout(controls_container)

        # File Browser
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
        controls_layout.addLayout(file_browser_layout)

        # List and Tree
        list_tree_layout = QHBoxLayout()
        self.result_file_list = QListWidget()
        list_tree_layout.addWidget(self.result_file_list)

        self.result_data_tree = QTreeWidget()
        self.result_data_tree.setHeaderLabel("Select Data to Plot")
        self.result_data_tree.setEnabled(False)
        list_tree_layout.addWidget(self.result_data_tree)
        controls_layout.addLayout(list_tree_layout)

        # Point Analysis
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

        controls_layout.addWidget(point_analysis_group)

        # Analysis Scenario Output
        analysis_scenario_group = QGroupBox("해석 시나리오 출력")
        analysis_scenario_layout = QVBoxLayout(analysis_scenario_group)

        self.offset_manual_checkbox = QCheckBox("수동 오프셋 선택")
        analysis_scenario_layout.addWidget(self.offset_manual_checkbox)

        self.manual_height_checkbox = QCheckBox("높이 값 직접 지정")
        self.manual_height_checkbox.setEnabled(False)
        analysis_scenario_layout.addWidget(self.manual_height_checkbox)

        self.offset_combos = []
        self.manual_height_inputs = []
        offsets_layout = QGridLayout()
        for i in range(3):
            offsets_layout.addWidget(QLabel(f"오프셋{i}:"), i, 0)

            combo = QComboBox()
            combo.addItems([f"C{j+1}" for j in range(8)])
            combo.setEnabled(False)
            offsets_layout.addWidget(combo, i, 1)
            self.offset_combos.append(combo)

            height_input = QLineEdit()
            height_input.setPlaceholderText("Height Value")
            height_input.setEnabled(False)
            offsets_layout.addWidget(height_input, i, 2)
            self.manual_height_inputs.append(height_input)

        analysis_scenario_layout.addLayout(offsets_layout)

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

        controls_layout.addWidget(analysis_scenario_group)

        group_layout.addWidget(controls_container, 4)
        layout.addWidget(group_box)

    def _connect_signals(self):
        self.select_result_folder_button.clicked.connect(self.select_result_folder)
        self.result_file_list.itemClicked.connect(self.on_result_file_selected)
        self.plot_results_button.clicked.connect(self.plot_selected_results)
        self.canvas.mpl_connect('button_press_event', self.on_result_plot_click)
        self.find_max_button.clicked.connect(self.on_find_max_click)
        self.export_point_button.clicked.connect(self.on_export_point_data_click)
        
        # Scenario Output
        self.offset_manual_checkbox.toggled.connect(self._on_offset_checkbox_toggled)
        self.manual_height_checkbox.toggled.connect(self._on_manual_height_checkbox_toggled)
        for combo in self.offset_combos:
            combo.currentIndexChanged.connect(self._update_offset_choices)
        self.export_scenario_button.clicked.connect(self.export_analysis_scenario)

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
                self.log_message.emit(f"[INFO] Found {len(files)} CSV files in {folder_path}")
            except Exception as e:
                self.log_message.emit(f"[ERROR] Failed to read folder: {e}")

    def on_result_file_selected(self, item):
        folder_path = self.result_folder_path_label.text()
        file_path = os.path.join(folder_path, item.text())
        try:
            self.log_message.emit(f"[INFO] Loading result file: {file_path}")
            self.result_data = self.data_loader.load_result_csv(file_path)
            
            # Set the time index
            time_col_tuple = RESULT_TIME_COL
            if time_col_tuple in self.result_data.columns:
                self.result_data.set_index(time_col_tuple, inplace=True)
                self.result_data.index.name = TimeCols.TIME
            elif TimeCols.TIME in self.result_data.columns:
                self.result_data.set_index(TimeCols.TIME, inplace=True)
                self.result_data.index.name = TimeCols.TIME

            if self.result_data.index.name != TimeCols.TIME:
                self.log_message.emit(f"[WARNING] '{TimeCols.TIME}' column not found in {item.text()}. Using default integer index for plotting.")

            self.populate_result_tree(self.result_data)
            self.result_data_tree.setEnabled(True)
            self.plot_results_button.setEnabled(True)
            self.log_message.emit("[INFO] Result data loaded. Please select data to plot.")
        except Exception as e:
            self.log_message.emit(f"[ERROR] Failed to load result file: {e}")
            self.result_data_tree.clear()
            self.result_data_tree.setEnabled(False)
            self.plot_results_button.setEnabled(False)

    def populate_result_tree(self, df):
        self.result_data_tree.clear()
        top_level_items = {}
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

            column_tuple = (l1, l2, l3)
            if column_tuple in self.last_selected_result_columns:
                leaf_item.setCheckState(0, Qt.Checked)
            else:
                leaf_item.setCheckState(0, Qt.Unchecked)

        self.result_data_tree.expandAll()

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

        self.log_message.emit(f"[INFO] Plotting {len(checked_columns)} result columns...")
        
        # Update 'Find Max' target combo
        self.find_max_target_combo.clear()
        for col in checked_columns:
            self.find_max_target_combo.addItem(f"{col[0]}/{col[1]}/{col[2]}", userData=col)

        if not checked_columns:
            self.plot_manager.clear_plot()
            self.selected_point_info = {'time': None, 'index': None}
            self.update_point_selection_ui()
            self.toolbar.update()
            self.toolbar.push_current()
            return

        plot_df = self.result_data[checked_columns].copy()
        self.plot_manager.draw_plot(plot_df, checked_columns)
        self.toolbar.update()
        self.toolbar.push_current()
        self.selected_point_info = {'time': None, 'index': None}
        self.update_point_selection_ui()

    def on_result_plot_click(self, event):
        if event.inaxes != self.plot_manager.ax: return
        if self.result_data is None or self.result_data.empty: return

        time_val = event.xdata
        indexer = self.result_data.index.get_indexer([time_val], method='nearest')
        closest_index = indexer[0]
        self.selected_point_info['index'] = closest_index
        self.selected_point_info['time'] = self.result_data.index[closest_index]

        self.export_point_button.setEnabled(True)
        self.update_point_selection_ui()

    def update_point_selection_ui(self, value=None):
        if self.result_point_cursor:
            try: self.result_point_cursor.remove()
            except: pass
        self.result_point_cursor = None

        if self.selected_point_info.get('time') is not None:
            time = self.selected_point_info['time']
            self.result_point_cursor = self.plot_manager.ax.axvline(x=time, color='r', linestyle='--', linewidth=1)
            self.plot_manager.canvas.draw()

            if value is not None:
                self.selected_point_label.setText(f"Selected: T={time:.3f}s, Value={value:.4f}")
            else:
                self.selected_point_label.setText(f"Selected: T={time:.3f}s")
            self.export_point_button.setEnabled(True)
        else:
            self.selected_point_label.setText("Selected: None")
            self.export_point_button.setEnabled(False)
            self.plot_manager.canvas.draw()

    def on_find_max_click(self):
        if self.result_data is None or self.result_data.empty: return
        target_column = self.find_max_target_combo.currentData()
        if target_column is None:
            self.log_message.emit("[WARNING] No target data selected for 'Find Max'.")
            return

        # Ensure target_column is a tuple (fix for PySide6 converting tuple to list)
        if isinstance(target_column, list):
            target_column = tuple(target_column)

        try:
            max_index = self.result_data[target_column].abs().idxmax()
            max_value = self.result_data.loc[max_index, target_column]
            self.selected_point_info['index'] = self.result_data.index.get_loc(max_index)
            self.selected_point_info['time'] = max_index
            self.update_point_selection_ui(value=max_value)
            self.log_message.emit(f"[INFO] Found max value for '{'/'.join(target_column)}': {max_value:.4f} at T={max_index:.3f}s")
        except Exception as e:
            self.log_message.emit(f"[ERROR] Could not find max value: {e}")

    def on_export_point_data_click(self):
        if self.result_data is None or self.selected_point_info.get('index') is None:
            self.log_message.emit("[ERROR] No point selected to export.")
            return

        selected_index = self.selected_point_info['index']
        point_data = self.result_data.iloc[[selected_index]].copy()
        time_str = f"{self.selected_point_info['time']:.3f}".replace('.', '_')
        current_file = os.path.basename(self.result_file_list.currentItem().text())
        suggested_filename = f"{os.path.splitext(current_file)[0]}_point_at_{time_str}s.csv"
        
        filepath, _ = QFileDialog.getSaveFileName(self, "Export Point Data to CSV", suggested_filename, "CSV Files (*.csv)")
        if filepath:
            try:
                point_data.to_csv(filepath, index=True)
                self.log_message.emit(f"[INFO] Point data successfully exported to {filepath}")
            except Exception as e:
                self.log_message.emit(f"[ERROR] Could not export point data: {e}")

    # --- Scenario Export Logic ---
    def _on_offset_checkbox_toggled(self, checked):
        self.manual_height_checkbox.setEnabled(checked)
        for combo in self.offset_combos:
            combo.setEnabled(checked)
        if not checked:
            self.manual_height_checkbox.setChecked(False)
            self._update_offset_choices()
        else:
            self._on_manual_height_checkbox_toggled(self.manual_height_checkbox.isChecked())

    def _on_manual_height_checkbox_toggled(self, checked):
        is_manual_offset_enabled = self.offset_manual_checkbox.isChecked()
        for height_input in self.manual_height_inputs:
            height_input.setEnabled(is_manual_offset_enabled and checked)

    def _update_offset_choices(self):
        all_options = [f"C{i+1}" for i in range(8)]
        selected_options = [combo.currentText() for combo in self.offset_combos if combo.isEnabled()]
        for i, combo in enumerate(self.offset_combos):
            if not combo.isEnabled(): continue
            current_selection = combo.currentText()
            other_selections = [opt for j, opt in enumerate(selected_options) if i != j]
            combo.blockSignals(True)
            combo.clear()
            combo.addItem(current_selection)
            for option in all_options:
                if option != current_selection and option not in other_selections:
                    combo.addItem(option)
            combo.setCurrentText(current_selection)
            combo.blockSignals(False)

    def export_analysis_scenario(self):
        if self.result_data is None or self.selected_point_info.get('time') is None:
            self.log_message.emit("[ERROR] No data point selected.")
            return

        selected_time = self.selected_point_info['time']
        time_point_data = None
        if not (self.offset_manual_checkbox.isChecked() and self.manual_height_checkbox.isChecked()):
            time_point_data = self.result_data.loc[selected_time]

        is_manual_offset = self.offset_manual_checkbox.isChecked()
        if is_manual_offset:
            data_for_manual = time_point_data if not self.manual_height_checkbox.isChecked() else None
            offset_data = self._get_manual_offset_data(data_for_manual)
        else:
            offset_data = self._get_automatic_offset_data(time_point_data)

        if not offset_data or len(offset_data) < 3:
            self.log_message.emit("[ERROR] Could not determine 3 offset points.")
            return

        vel_cols = {
            'ANG_VEL_X': (HeaderL1.VEL, HeaderL2.ANG, HeaderL3.WX_ANA),
            'ANG_VEL_Y': (HeaderL1.VEL, HeaderL2.ANG, HeaderL3.WY_ANA),
            'ANG_VEL_Z': (HeaderL1.VEL, HeaderL2.ANG, HeaderL3.WZ_ANA),
            'TRA_VEL_X': (HeaderL1.VEL, HeaderL2.COM, HeaderL3.VX_ANA),
            'TRA_VEL_Y': (HeaderL1.VEL, HeaderL2.COM, HeaderL3.VY_ANA),
            'TRA_VEL_Z': (HeaderL1.VEL, HeaderL2.COM, HeaderL3.VZ_ANA),
        }
        if time_point_data is not None:
            velocities = {key: time_point_data.get(col, 0.0) for key, col in vel_cols.items()}
        else:
            velocities = {key: 0.0 for key in vel_cols.keys()}

        output_data = [
            ('1', 'Left'), ('2', 'Right'), ('3', 'Bottom'),
            ('4', 'Top'), ('5', 'Rear'), ('6', 'Front'),
            ('cat', 'Corner_Drop_2nd'),
            ('drop_name', self.le_scene_name.text()),
        ]

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
            ('variable_14', 'ROT_ANG_VEL_X'), ('value_14', '0.0'),
            ('variable_15', 'ROT_ANG_VEL_Y'), ('value_15', '0.0'),
            ('variable_16', 'ROT_ANG_VEL_Z'), ('value_16', '0.0'),
            ('run_time', self.le_run_time.text()),
            ('tmin', self.le_time_step.text()),
        ])

        suggested_filename = f"scenario_{self.le_scene_name.text()}.csv" if self.le_scene_name.text() else "analysis_scenario.csv"
        filepath, _ = QFileDialog.getSaveFileName(self, "Export Analysis Scenario", suggested_filename, "CSV Files (*.csv)")

        if filepath:
            try:
                lines = [f"{key},{value}" for key, value in output_data[:6]]
                last_line = ",".join([f"{key},{value}" for key, value in output_data[6:]])
                csv_string = "\n".join(lines) + "\n" + last_line

                with open(filepath, 'w') as f:
                    f.write(csv_string)
                self.log_message.emit(f"[SUCCESS] Analysis scenario exported to {filepath}")
            except Exception as e:
                self.log_message.emit(f"[ERROR] Could not export scenario: {e}")

    def _get_automatic_offset_data(self, time_point_data):
        height_cols = [(HeaderL1.ANALYSIS, f'C{i+1}', HeaderL3.REL_H) for i in range(8)]
        corner_heights = {}
        for i, col in enumerate(height_cols):
            if col in time_point_data:
                corner_heights[f'C{i+1}'] = time_point_data[col]
            else:
                self.log_message.emit(f"[WARNING] Column {col} not found in data.")
                return []

        if not corner_heights: return []
        min_corner = min(corner_heights, key=corner_heights.get)
        min_corner_num = int(min_corner[1:])
        group1 = {f'C{i}': corner_heights[f'C{i}'] for i in range(1, 5)}
        group2 = {f'C{i}': corner_heights[f'C{i}'] for i in range(5, 9)}
        target_group = group1 if 1 <= min_corner_num <= 4 else group2
        sorted_corners = sorted(target_group.items(), key=lambda item: item[1])
        return sorted_corners[:3]

    def _get_manual_offset_data(self, time_point_data):
        selected_corners = [combo.currentText() for combo in self.offset_combos]
        offset_data = []
        use_manual_heights = self.manual_height_checkbox.isChecked()

        for i, corner_name in enumerate(selected_corners):
            height_value = 0.0
            if use_manual_heights:
                try:
                    height_value = float(self.manual_height_inputs[i].text())
                except ValueError:
                    self.log_message.emit(f"[WARNING] Invalid manual height input for Offset {i}. Using 0.0.")
            else:
                if time_point_data is not None:
                    height_col = (HeaderL1.ANALYSIS, corner_name, HeaderL3.REL_H)
                    if height_col in time_point_data:
                        height_value = time_point_data[height_col]
                    else:
                        self.log_message.emit(f"[WARNING] Column {height_col} not found. Using 0.0.")
            offset_data.append((corner_name, height_value))
        return offset_data
