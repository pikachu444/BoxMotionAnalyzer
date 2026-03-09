import os
import pandas as pd
from PySide6.QtCore import Signal, Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QLineEdit, QComboBox, QGroupBox, QTreeWidget, QTreeWidgetItem,
    QFileDialog, QListWidget, QFormLayout, QCheckBox, QGridLayout, QSplitter, QFrame
)
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qtagg import NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure

from src.analysis.ui.plot_manager import PlotManager
from src.analysis.ui.plot_popup_dialog import PlotPopupDialog
from src.config.data_columns import (
    DISPLAY_RESULT_COLUMNS,
    RESULT_TIME_COL,
    RESULT_TIMELINE_FULL_END_COL,
    RESULT_TIMELINE_FULL_START_COL,
    RESULT_TIMELINE_SLICE_END_COL,
    RESULT_TIMELINE_SLICE_START_COL,
    TimeCols,
    HeaderL1,
    HeaderL2,
    HeaderL3,
    CORNER_NAME_MAP,
)

class WidgetResultsAnalyzer(QWidget):
    # Signals
    log_message = Signal(str)
    
    def __init__(self, data_loader):
        super().__init__()
        self.data_loader = data_loader
        
        self.result_data = None
        self.current_result_file = None
        self.last_selected_result_columns = set()
        self.selected_point_info = {'time': None, 'index': None}
        self.result_point_cursor = None
        self.popup_windows = {}
        self.popup_counter = 0
        
        self._setup_ui()
        self._connect_signals()
        self._reset_context_labels()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        context_group = QGroupBox("Time Window")
        context_layout = QVBoxLayout(context_group)

        context_row_1 = QHBoxLayout()
        context_row_1.addWidget(QLabel("Active File:"))
        self.context_active_file_label = QLabel("N/A")
        context_row_1.addWidget(self.context_active_file_label)
        context_row_1.addStretch()
        context_row_1.addWidget(QLabel("Number of Samples:"))
        self.context_rows_label = QLabel("N/A")
        context_row_1.addWidget(self.context_rows_label)
        context_layout.addLayout(context_row_1)

        timeline_bar_row = QVBoxLayout()
        self.timeline_bar_info_label = QLabel("Full/Slice Range: unknown")
        timeline_bar_row.addWidget(self.timeline_bar_info_label)
        self.timeline_bar_widget = QFrame()
        self.timeline_bar_widget.setFrameShape(QFrame.StyledPanel)
        self.timeline_bar_widget.setMinimumHeight(18)
        timeline_bar_layout = QHBoxLayout(self.timeline_bar_widget)
        timeline_bar_layout.setContentsMargins(0, 0, 0, 0)
        timeline_bar_layout.setSpacing(0)
        self.timeline_bar_left = QFrame()
        self.timeline_bar_left.setStyleSheet("background-color: #d7dbe0;")
        self.timeline_bar_slice = QFrame()
        self.timeline_bar_slice.setStyleSheet("background-color: #89cf8a;")
        self.timeline_bar_right = QFrame()
        self.timeline_bar_right.setStyleSheet("background-color: #d7dbe0;")
        timeline_bar_layout.addWidget(self.timeline_bar_left, 1)
        timeline_bar_layout.addWidget(self.timeline_bar_slice, 1)
        timeline_bar_layout.addWidget(self.timeline_bar_right, 1)
        timeline_bar_row.addWidget(self.timeline_bar_widget)
        context_layout.addLayout(timeline_bar_row)
        layout.addWidget(context_group)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        files_group = QGroupBox("1. Result Files")
        files_layout = QVBoxLayout(files_group)
        button_row = QHBoxLayout()
        self.select_result_folder_button = QPushButton("Select Result Folder...")
        button_row.addWidget(self.select_result_folder_button)
        button_row.addStretch()
        files_layout.addLayout(button_row)

        path_row = QHBoxLayout()
        path_row.addWidget(QLabel("Folder Path:"))
        self.result_folder_path_label = QLineEdit()
        self.result_folder_path_label.setReadOnly(True)
        self.result_folder_path_label.setPlaceholderText("No folder selected.")
        path_row.addWidget(self.result_folder_path_label)
        files_layout.addLayout(path_row)

        self.result_file_list = QListWidget()
        files_layout.addWidget(self.result_file_list)
        splitter.addWidget(files_group)

        selection_group = QGroupBox("2. Data Selection")
        selection_layout = QVBoxLayout(selection_group)
        self.result_data_tree = QTreeWidget()
        self.result_data_tree.setHeaderLabel("Select Data to Plot")
        self.result_data_tree.setEnabled(False)
        selection_layout.addWidget(self.result_data_tree)

        selection_buttons_row = QHBoxLayout()
        self.clear_selection_button = QPushButton("Clear Selection")
        self.plot_results_button = QPushButton("Plot Selected Results")
        self.plot_results_button.setEnabled(False)
        self.open_popup_current_button = QPushButton("Open Popup (Current Selection)")
        selection_buttons_row.addWidget(self.clear_selection_button)
        selection_buttons_row.addWidget(self.plot_results_button)
        selection_buttons_row.addWidget(self.open_popup_current_button)
        selection_layout.addLayout(selection_buttons_row)

        popup_buttons_row = QHBoxLayout()
        self.close_all_popups_button = QPushButton("Close All Popups")
        popup_buttons_row.addStretch()
        popup_buttons_row.addWidget(self.close_all_popups_button)
        selection_layout.addLayout(popup_buttons_row)

        self.popup_status_label = QLabel("Opened Popups: 0")
        selection_layout.addWidget(self.popup_status_label)
        self.selection_checked_columns_label = QLabel("Checked Columns: 0")
        selection_layout.addWidget(self.selection_checked_columns_label)
        splitter.addWidget(selection_group)

        right_group = QGroupBox("3. Point Analysis & Export")
        right_layout = QVBoxLayout(right_group)

        point_analysis_group = QGroupBox("Point Analysis")
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
        right_layout.addWidget(point_analysis_group)

        analysis_scenario_group = QGroupBox("4. Export Analysis Input")
        analysis_scenario_layout = QVBoxLayout(analysis_scenario_group)

        manual_check_row = QHBoxLayout()
        self.offset_manual_checkbox = QCheckBox("Manual Offset")
        self.manual_height_checkbox = QCheckBox("Manual Height")
        self.manual_height_checkbox.setEnabled(False)
        manual_check_row.addWidget(self.offset_manual_checkbox)
        manual_check_row.addWidget(self.manual_height_checkbox)
        manual_check_row.addStretch()
        analysis_scenario_layout.addLayout(manual_check_row)

        self.offset_combos = []
        self.manual_height_inputs = []
        offsets_layout = QGridLayout()
        for i in range(3):
            offsets_layout.addWidget(QLabel(f"Offset{i}:"), i, 0)

            combo = QComboBox()
            combo.addItems([f"C{j + 1}" for j in range(8)])
            combo.setEnabled(False)
            offsets_layout.addWidget(combo, i, 1)
            self.offset_combos.append(combo)

            height_input = QLineEdit()
            height_input.setPlaceholderText("H")
            height_input.setEnabled(False)
            offsets_layout.addWidget(height_input, i, 2)
            self.manual_height_inputs.append(height_input)
        analysis_scenario_layout.addLayout(offsets_layout)

        scenario_form_layout = QFormLayout()
        self.le_run_time = QLineEdit("0.1")
        self.le_time_step = QLineEdit("1e-7")
        self.le_scene_name = QLineEdit("")
        scenario_form_layout.addRow("Run Time:", self.le_run_time)
        scenario_form_layout.addRow("Step:", self.le_time_step)
        scenario_form_layout.addRow("Scene Name:", self.le_scene_name)
        analysis_scenario_layout.addLayout(scenario_form_layout)

        self.export_scenario_button = QPushButton("Export Scenario CSV")
        analysis_scenario_layout.addWidget(self.export_scenario_button)
        right_layout.addWidget(analysis_scenario_group)
        right_layout.addStretch()
        splitter.addWidget(right_group)

        splitter.setSizes([320, 620, 500])
        layout.addWidget(splitter, 3)

        main_plot_group = QGroupBox("Main Plot")
        main_plot_layout = QVBoxLayout(main_plot_group)
        main_plot_layout.setContentsMargins(4, 4, 4, 4)
        main_plot_layout.setSpacing(2)

        self.fig = Figure(figsize=(5, 4), dpi=100)
        self.fig.subplots_adjust(left=0.055, right=0.995, bottom=0.085, top=0.995)
        self.canvas = FigureCanvas(self.fig)
        self.toolbar = NavigationToolbar(self.canvas, self)
        main_plot_layout.addWidget(self.toolbar)
        main_plot_layout.addWidget(self.canvas)
        self.plot_manager = PlotManager(self.canvas, self.fig)
        layout.addWidget(main_plot_group, 5)

    def _connect_signals(self):
        self.select_result_folder_button.clicked.connect(self.select_result_folder)
        self.result_file_list.itemClicked.connect(self.on_result_file_selected)
        self.result_data_tree.itemChanged.connect(self.on_tree_item_changed)
        self.clear_selection_button.clicked.connect(self.clear_selection)
        self.plot_results_button.clicked.connect(self.plot_selected_results)
        self.open_popup_current_button.clicked.connect(self.open_popup_current_selection)
        self.close_all_popups_button.clicked.connect(self.close_all_popups)
        self.canvas.mpl_connect('button_press_event', self.on_result_plot_click)
        self.find_max_button.clicked.connect(self.on_find_max_click)
        self.export_point_button.clicked.connect(self.on_export_point_data_click)
        
        # Scenario Output
        self.offset_manual_checkbox.toggled.connect(self._on_offset_checkbox_toggled)
        self.manual_height_checkbox.toggled.connect(self._on_manual_height_checkbox_toggled)
        for combo in self.offset_combos:
            combo.currentIndexChanged.connect(self._update_offset_choices)
        self.export_scenario_button.clicked.connect(self.export_analysis_scenario)

    def _reset_context_labels(self):
        self.context_active_file_label.setText("N/A")
        self.context_rows_label.setText("N/A")
        self.timeline_bar_info_label.setText("Full/Slice Range: unknown")
        self.selection_checked_columns_label.setText("Checked Columns: 0")
        self._set_timeline_bar_unknown()

    def _set_selected_columns_context(self, count):
        self.selection_checked_columns_label.setText(f"Checked Columns: {count}")

    @staticmethod
    def _first_numeric_value(df, column_tuple):
        if column_tuple not in df.columns:
            return None
        values = df[column_tuple]
        if isinstance(values, pd.DataFrame):
            values = values.iloc[:, 0]
        values = pd.to_numeric(values, errors="coerce").dropna()
        if values.empty:
            return None
        return float(values.iloc[0])

    def _set_timeline_bar_unknown(self):
        bar_layout = self.timeline_bar_widget.layout()
        bar_layout.setStretch(0, 1)
        bar_layout.setStretch(1, 0)
        bar_layout.setStretch(2, 1)

    def _update_timeline_bar(self, full_start, full_end, slice_start, slice_end):
        if any(v is None for v in [full_start, full_end, slice_start, slice_end]):
            self.timeline_bar_info_label.setText("Full/Slice Range: unknown")
            self._set_timeline_bar_unknown()
            return

        full_span = float(full_end) - float(full_start)
        if full_span <= 0:
            self.timeline_bar_info_label.setText("Full/Slice Range: unknown")
            self._set_timeline_bar_unknown()
            return

        clamped_start = min(max(float(slice_start), float(full_start)), float(full_end))
        clamped_end = min(max(float(slice_end), float(full_start)), float(full_end))
        if clamped_end < clamped_start:
            clamped_start, clamped_end = clamped_end, clamped_start

        left_ratio = (clamped_start - float(full_start)) / full_span
        slice_ratio = (clamped_end - clamped_start) / full_span
        right_ratio = max(0.0, 1.0 - left_ratio - slice_ratio)

        scale = 1000
        left_w = max(0, int(round(left_ratio * scale)))
        slice_w = max(1, int(round(slice_ratio * scale)))
        right_w = max(0, scale - left_w - slice_w)

        bar_layout = self.timeline_bar_widget.layout()
        bar_layout.setStretch(0, left_w)
        bar_layout.setStretch(1, slice_w)
        bar_layout.setStretch(2, right_w)
        self.timeline_bar_info_label.setText(
            f"Full: {float(full_start):.3f}s ~ {float(full_end):.3f}s | "
            f"Slice: {clamped_start:.3f}s ~ {clamped_end:.3f}s"
        )

    def _update_context_from_dataframe(self, file_name):
        if self.result_data is None or self.result_data.empty:
            self.context_active_file_label.setText(file_name)
            self.context_rows_label.setText("0")
            self._set_timeline_bar_unknown()
            return

        self.context_active_file_label.setText(file_name)
        self.context_rows_label.setText(str(len(self.result_data)))

        full_start = self._first_numeric_value(self.result_data, RESULT_TIMELINE_FULL_START_COL)
        full_end = self._first_numeric_value(self.result_data, RESULT_TIMELINE_FULL_END_COL)
        slice_start = self._first_numeric_value(self.result_data, RESULT_TIMELINE_SLICE_START_COL)
        slice_end = self._first_numeric_value(self.result_data, RESULT_TIMELINE_SLICE_END_COL)

        try:
            if full_start is None:
                full_start = float(self.result_data.index.min())
            if full_end is None:
                full_end = float(self.result_data.index.max())
        except Exception:
            pass

        try:
            if slice_start is None:
                slice_start = float(self.result_data.index.min())
            if slice_end is None:
                slice_end = float(self.result_data.index.max())
        except Exception:
            pass

        self._update_timeline_bar(full_start, full_end, slice_start, slice_end)

    def _refresh_result_file_list(self, folder_path, selected_file=None):
        self.result_file_list.clear()
        try:
            files = sorted(f for f in os.listdir(folder_path) if f.lower().endswith(".csv"))
            self.result_file_list.addItems(files)
            self.log_message.emit(f"[INFO] Found {len(files)} CSV files in {folder_path}")
            if selected_file:
                for i in range(self.result_file_list.count()):
                    if self.result_file_list.item(i).text() == selected_file:
                        self.result_file_list.setCurrentRow(i)
                        break
        except Exception as e:
            self.log_message.emit(f"[ERROR] Failed to read folder: {e}")

    def select_result_folder(self):
        folder_path = QFileDialog.getExistingDirectory(self, "Select Result Folder")
        if not folder_path:
            return

        self.result_folder_path_label.setText(folder_path)
        self.result_data_tree.clear()
        self.result_data_tree.setEnabled(False)
        self.plot_results_button.setEnabled(False)
        self.find_max_target_combo.clear()
        self.result_data = None
        self.current_result_file = None
        self.last_selected_result_columns.clear()
        self.selected_point_info = {'time': None, 'index': None}
        self.update_point_selection_ui()
        self.close_all_popups()
        self._reset_context_labels()
        self._refresh_result_file_list(folder_path)

    def on_result_file_selected(self, item):
        folder_path = self.result_folder_path_label.text()
        file_path = os.path.join(folder_path, item.text())
        self.load_result_file(file_path)

    def load_result_file(self, file_path):
        if not file_path or not os.path.isfile(file_path):
            self.log_message.emit(f"[ERROR] Result file not found: {file_path}")
            return False

        folder_path = os.path.dirname(file_path)
        file_name = os.path.basename(file_path)
        self.result_folder_path_label.setText(folder_path)
        self._refresh_result_file_list(folder_path, selected_file=file_name)

        try:
            self.log_message.emit(f"[INFO] Loading result file: {file_path}")
            self.result_data = self.data_loader.load_result_csv(file_path)
            self.current_result_file = file_path

            if self.result_data.index.name != TimeCols.TIME:
                if RESULT_TIME_COL in self.result_data.columns:
                    self.result_data.set_index(RESULT_TIME_COL, inplace=True)
                    self.result_data.index.name = TimeCols.TIME
                elif TimeCols.TIME in self.result_data.columns:
                    self.result_data.set_index(TimeCols.TIME, inplace=True)
                    self.result_data.index.name = TimeCols.TIME

            if self.result_data.index.name != TimeCols.TIME:
                self.log_message.emit(
                    f"[WARNING] '{TimeCols.TIME}' column not found in {file_name}. "
                    "Using default integer index for plotting."
                )

            self.populate_result_tree(self.result_data)
            self.result_data_tree.setEnabled(True)
            self.plot_results_button.setEnabled(True)
            self.selected_point_info = {'time': None, 'index': None}
            self.update_point_selection_ui()
            self._update_context_from_dataframe(file_name)
            if self.popup_windows:
                self._refresh_popup_plots()
            self._update_popup_status_label()
            self.log_message.emit("[INFO] Result data loaded. Select columns and plot.")
            return True
        except Exception as e:
            self.log_message.emit(f"[ERROR] Failed to load result file: {e}")
            self.result_data_tree.clear()
            self.result_data_tree.setEnabled(False)
            self.plot_results_button.setEnabled(False)
            self.find_max_target_combo.clear()
            self._reset_context_labels()
            return False

    def populate_result_tree(self, df):
        self.result_data_tree.blockSignals(True)
        self.result_data_tree.clear()
        top_level_items = {}
        columns_to_plot = [col for col in df.columns if col in DISPLAY_RESULT_COLUMNS]
        columns_to_plot.sort(key=self._result_tree_sort_key)

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
        self.result_data_tree.blockSignals(False)
        self._set_selected_columns_context(len(self._get_checked_columns()))

    @staticmethod
    def _result_tree_sort_key(column_tuple):
        l1, l2, l3 = column_tuple
        l1_order = {
            HeaderL1.POS: 0,
            HeaderL1.VEL: 1,
            HeaderL1.ACC: 2,
            HeaderL1.ANALYSIS: 3,
            HeaderL1.ANALYSIS_SCENARIO: 4
        }
        if l2 == HeaderL2.COM:
            l2_rank = 0
        elif isinstance(l2, str) and l2.startswith("C") and l2[1:].isdigit():
            l2_rank = int(l2[1:])
        else:
            l2_rank = 99

        l3_str = str(l3)
        if l1 == HeaderL1.POS and l2 == HeaderL2.COM:
            pos_order = ["P_TX", "P_TY", "P_TZ", "P_RX", "P_RY", "P_RZ"]
            if l3_str in pos_order:
                l3_rank = pos_order.index(l3_str)
            else:
                l3_rank = 999
        elif l1 in {HeaderL1.VEL, HeaderL1.ACC} and l2 == HeaderL2.COM:
            local_order = [
                f"BoxLocal_{'V' if l1 == HeaderL1.VEL else 'A'}_TX",
                f"BoxLocal_{'V' if l1 == HeaderL1.VEL else 'A'}_TY",
                f"BoxLocal_{'V' if l1 == HeaderL1.VEL else 'A'}_TZ",
                f"BoxLocal_{'V' if l1 == HeaderL1.VEL else 'A'}_T_Norm",
                f"BoxLocal_{'V' if l1 == HeaderL1.VEL else 'A'}_RX",
                f"BoxLocal_{'V' if l1 == HeaderL1.VEL else 'A'}_RY",
                f"BoxLocal_{'V' if l1 == HeaderL1.VEL else 'A'}_RZ",
                f"BoxLocal_{'V' if l1 == HeaderL1.VEL else 'A'}_R_Norm",
            ]
            global_order = [
                f"Global_{'V' if l1 == HeaderL1.VEL else 'A'}_TX",
                f"Global_{'V' if l1 == HeaderL1.VEL else 'A'}_TY",
                f"Global_{'V' if l1 == HeaderL1.VEL else 'A'}_TZ",
                f"Global_{'V' if l1 == HeaderL1.VEL else 'A'}_T_Norm",
                f"Global_{'V' if l1 == HeaderL1.VEL else 'A'}_RX",
                f"Global_{'V' if l1 == HeaderL1.VEL else 'A'}_RY",
                f"Global_{'V' if l1 == HeaderL1.VEL else 'A'}_RZ",
                f"Global_{'V' if l1 == HeaderL1.VEL else 'A'}_R_Norm",
            ]
            stacked = local_order + global_order
            l3_rank = stacked.index(l3_str) if l3_str in stacked else 999
        elif l1 in {HeaderL1.VEL, HeaderL1.ACC} and isinstance(l2, str) and l2.startswith("C") and l2[1:].isdigit():
            corner_order = [
                f"Global_{'V' if l1 == HeaderL1.VEL else 'A'}_TX",
                f"Global_{'V' if l1 == HeaderL1.VEL else 'A'}_TY",
                f"Global_{'V' if l1 == HeaderL1.VEL else 'A'}_TZ",
                f"Global_{'V' if l1 == HeaderL1.VEL else 'A'}_T_Norm",
            ]
            l3_rank = corner_order.index(l3_str) if l3_str in corner_order else 999
        else:
            l3_rank = 999
        return (l1_order.get(l1, 99), l2_rank, l3_rank, l3_str)

    def _iter_leaf_items(self):
        root = self.result_data_tree.invisibleRootItem()
        for i in range(root.childCount()):
            top_item = root.child(i)
            for j in range(top_item.childCount()):
                mid_item = top_item.child(j)
                for k in range(mid_item.childCount()):
                    yield top_item, mid_item, mid_item.child(k)

    def _get_checked_columns(self):
        checked_columns = []
        for top_item, mid_item, leaf_item in self._iter_leaf_items():
            if leaf_item.checkState(0) == Qt.Checked:
                checked_columns.append((top_item.text(0), mid_item.text(0), leaf_item.text(0)))
        return checked_columns

    def on_tree_item_changed(self, _item, _column):
        self._set_selected_columns_context(len(self._get_checked_columns()))

    def clear_selection(self):
        self.result_data_tree.blockSignals(True)
        for _, _, leaf_item in self._iter_leaf_items():
            leaf_item.setCheckState(0, Qt.Unchecked)
        self.result_data_tree.blockSignals(False)
        self._set_selected_columns_context(0)

    def _update_find_max_targets(self, checked_columns):
        self.find_max_target_combo.clear()
        for col in checked_columns:
            self.find_max_target_combo.addItem(f"{col[0]}/{col[1]}/{col[2]}", userData=col)

    def plot_selected_results(self):
        if self.result_data is None:
            return

        checked_columns = self._get_checked_columns()
        self.last_selected_result_columns = set(checked_columns)
        self._set_selected_columns_context(len(checked_columns))
        self._update_find_max_targets(checked_columns)
        self.log_message.emit(f"[INFO] Plotting {len(checked_columns)} result columns...")

        if not checked_columns:
            self.plot_manager.clear_plot()
            self.selected_point_info = {'time': None, 'index': None}
            self.update_point_selection_ui()
            self.toolbar.update()
            self.toolbar.push_current()
            return

        plot_df = self.result_data[checked_columns].copy()
        self.plot_manager.draw_plot(plot_df, checked_columns)
        self.plot_manager.ax.set_title("")
        self.plot_manager.canvas.draw_idle()
        self.toolbar.update()
        self.toolbar.push_current()
        self.selected_point_info = {'time': None, 'index': None}
        self.update_point_selection_ui()

    def _get_nearest_row_index(self, time_val):
        if self.result_data is None or self.result_data.empty:
            return None

        try:
            indexer = self.result_data.index.get_indexer([time_val], method='nearest')
            if len(indexer) > 0 and indexer[0] >= 0:
                return int(indexer[0])
        except Exception:
            pass

        try:
            numeric_index = pd.to_numeric(pd.Series(self.result_data.index), errors='coerce')
            if numeric_index.isna().all():
                return None
            distance = (numeric_index - float(time_val)).abs()
            return int(distance.idxmin())
        except Exception:
            return None

    def _sync_popup_cursors(self):
        selected_time = self.selected_point_info.get('time')
        for popup in list(self.popup_windows.values()):
            if popup is None:
                continue
            popup.set_selected_time_cursor(selected_time)

    def _select_time_by_xdata(self, xdata, value=None):
        nearest_index = self._get_nearest_row_index(xdata)
        if nearest_index is None:
            return

        self.selected_point_info['index'] = nearest_index
        self.selected_point_info['time'] = self.result_data.index[nearest_index]
        self.update_point_selection_ui(value=value)
        self._sync_popup_cursors()

    def on_result_plot_click(self, event):
        if event.inaxes != self.plot_manager.ax:
            return
        if self.result_data is None or self.result_data.empty:
            return
        if event.xdata is None:
            return

        self._select_time_by_xdata(event.xdata)

    def update_point_selection_ui(self, value=None):
        if self.result_point_cursor:
            try:
                self.result_point_cursor.remove()
            except Exception:
                pass
        self.result_point_cursor = None

        if self.selected_point_info.get('time') is not None:
            selected_time = self.selected_point_info['time']
            self.result_point_cursor = self.plot_manager.ax.axvline(
                x=selected_time, color='r', linestyle='--', linewidth=1
            )
            self.plot_manager.canvas.draw()

            try:
                time_text = f"{float(selected_time):.3f}"
            except Exception:
                time_text = str(selected_time)

            if value is not None:
                self.selected_point_label.setText(
                    f"Selected: T={time_text}s, Value={float(value):.4f}"
                )
            else:
                self.selected_point_label.setText(f"Selected: T={time_text}s")
            self.export_point_button.setEnabled(True)
        else:
            self.selected_point_label.setText("Selected: None")
            self.export_point_button.setEnabled(False)
            self.plot_manager.canvas.draw()

    def _open_popup(self, selected_columns):
        if self.result_data is None or self.result_data.empty:
            self.log_message.emit("[WARNING] Load a result file first.")
            return
        if not selected_columns:
            self.log_message.emit("[WARNING] Select columns first.")
            return

        self.popup_counter += 1
        window_name = f"Popup_{self.popup_counter}"
        popup = PlotPopupDialog(window_name, self)
        popup.selected_columns = list(selected_columns)
        popup.set_plot_data(self.result_data, popup.selected_columns)
        popup.set_selected_time_cursor(self.selected_point_info.get('time'))
        popup.point_selected.connect(self.on_popup_point_selected)
        popup.finished.connect(lambda _result, name=window_name: self._on_popup_closed(name))
        popup.show()

        self.popup_windows[window_name] = popup
        self._update_popup_status_label()

    def open_popup_current_selection(self):
        self._open_popup(self._get_checked_columns())

    def _refresh_popup_plots(self):
        if not self.popup_windows:
            return
        if self.result_data is None:
            return

        for popup in list(self.popup_windows.values()):
            if popup is None:
                continue
            popup.set_plot_data(self.result_data, popup.selected_columns)
            popup.set_selected_time_cursor(self.selected_point_info.get('time'))

    def close_all_popups(self):
        for popup in list(self.popup_windows.values()):
            try:
                popup.close()
            except Exception:
                pass
        self.popup_windows.clear()
        self._update_popup_status_label()

    def _on_popup_closed(self, window_name):
        self.popup_windows.pop(window_name, None)
        self._update_popup_status_label()

    def _update_popup_status_label(self):
        self.popup_status_label.setText(f"Opened Popups: {len(self.popup_windows)}")

    def on_popup_point_selected(self, selected_time):
        self._select_time_by_xdata(selected_time)

    def on_find_max_click(self):
        if self.result_data is None or self.result_data.empty:
            return
        target_column = self.find_max_target_combo.currentData()
        if target_column is None:
            self.log_message.emit("[WARNING] No target data selected for 'Find Max'.")
            return

        if isinstance(target_column, list):
            target_column = tuple(target_column)

        try:
            max_index = self.result_data[target_column].abs().idxmax()
            max_value = self.result_data.loc[max_index, target_column]
            self._select_time_by_xdata(max_index, value=max_value)
            selected_time = self.selected_point_info.get('time')
            try:
                selected_time_text = f"{float(selected_time):.3f}s"
            except Exception:
                selected_time_text = str(selected_time)
            self.log_message.emit(
                f"[INFO] Found max value for '{'/'.join(target_column)}': "
                f"{float(max_value):.4f} at T={selected_time_text}"
            )
        except Exception as e:
            self.log_message.emit(f"[ERROR] Could not find max value: {e}")

    def on_export_point_data_click(self):
        if self.result_data is None or self.selected_point_info.get('index') is None:
            self.log_message.emit("[ERROR] No point selected to export.")
            return

        selected_index = self.selected_point_info['index']
        point_data = self.result_data.iloc[[selected_index]].copy()
        try:
            time_str = f"{float(self.selected_point_info['time']):.3f}".replace('.', '_')
        except Exception:
            time_str = str(self.selected_point_info['time']).replace('.', '_')

        if self.current_result_file:
            current_file = os.path.basename(self.current_result_file)
        elif self.result_file_list.currentItem():
            current_file = self.result_file_list.currentItem().text()
        else:
            current_file = "result.csv"

        suggested_filename = f"{os.path.splitext(current_file)[0]}_point_at_{time_str}s.csv"
        filepath, _ = QFileDialog.getSaveFileName(
            self, "Export Point Data to CSV", suggested_filename, "CSV Files (*.csv)"
        )
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
            'ANG_VEL_X': (HeaderL1.VEL, HeaderL2.COM, HeaderL3.V_RX_ANA),
            'ANG_VEL_Y': (HeaderL1.VEL, HeaderL2.COM, HeaderL3.V_RY_ANA),
            'ANG_VEL_Z': (HeaderL1.VEL, HeaderL2.COM, HeaderL3.V_RZ_ANA),
            'TRA_VEL_X': (HeaderL1.VEL, HeaderL2.COM, HeaderL3.V_TX_ANA),
            'TRA_VEL_Y': (HeaderL1.VEL, HeaderL2.COM, HeaderL3.V_TY_ANA),
            'TRA_VEL_Z': (HeaderL1.VEL, HeaderL2.COM, HeaderL3.V_TZ_ANA),
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
