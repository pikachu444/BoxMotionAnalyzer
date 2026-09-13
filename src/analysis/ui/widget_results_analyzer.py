import os
import numpy as np
import pandas as pd
from PySide6.QtCore import Signal, Qt, QItemSelectionModel
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QScrollArea,
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QLineEdit, QComboBox, QGroupBox, QTreeWidget, QTreeWidgetItem,
    QFileDialog, QListWidget, QFormLayout, QCheckBox, QGridLayout, QSplitter, QFrame,
    QSizePolicy, QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
    QListWidgetItem, QMenu, QToolButton
)
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qtagg import NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure

from src.analysis.ui.plot_manager import PlotManager
from src.analysis.pipeline.artifact_io import list_result_files
from src.analysis.ui.dialog_metric_guide import DropPostureMetricGuideDialog
from src.analysis.ui.plot_popup_dialog import PlotPopupDialog
from src.utils.qt_sections import CollapsibleSection, find_result_column_index, set_path_label
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
    get_result_column_display_path,
    get_result_metric_display_name,
    normalize_result_column,
    RESULT_LEVEL1_DISPLAY, RESULT_LEVEL2_DISPLAY,
    is_corner_id_column, format_result_value, get_result_metric_tooltip,
)
from src.config.result_metric_descriptors import (
    DROP_POSTURE_SUMMARY_GROUP_ORDER,
    get_drop_posture_summary_descriptors,
    get_result_metric_descriptor,
)

class WidgetResultsAnalyzer(QWidget):
    # Signals
    log_message = Signal(str)
    compare_requested = Signal(list)
    
    def __init__(self, data_loader):
        super().__init__()
        self.data_loader = data_loader
        
        self.result_data = None
        self.current_result_file = None
        self.explicit_result_files = None
        self.available_result_columns = []
        self.checked_result_columns = set()
        self.last_selected_result_columns = set()
        self.selected_point_info = {'time': None, 'index': None}
        self.result_point_cursor = None
        self.popup_windows = {}
        self.popup_counter = 0
        
        self._setup_ui()
        self._connect_signals()
        self._reset_context_labels()
        self.update_point_selection_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        main_splitter = QSplitter(Qt.Orientation.Horizontal)
        main_splitter.setChildrenCollapsible(False)

        context_group = QWidget()
        context_layout = QVBoxLayout(context_group)

        context_row_1 = QHBoxLayout()
        context_row_1.addWidget(QLabel("Result:"))
        self.context_active_file_label = QLabel("N/A")
        self.context_active_file_label.setWordWrap(True)
        self.context_active_file_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.context_active_file_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        context_row_1.addWidget(self.context_active_file_label, 1)
        context_row_1.addWidget(QLabel("Samples:"))
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
        context_group.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)
        layout.addWidget(context_group)

        sidebar = QWidget()
        sidebar.setMinimumWidth(260)
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(0, 0, 0, 0)

        files_group = QWidget()
        files_layout = QVBoxLayout(files_group)
        files_layout.setContentsMargins(0, 0, 0, 0)
        button_row = QHBoxLayout()
        self.open_result_button = QPushButton("Open")
        self.select_result_folder_button = QPushButton("Folder")
        self.compare_button = QPushButton("Compare")
        self.compare_button.setEnabled(False)
        button_row.addWidget(self.open_result_button)
        button_row.addWidget(self.select_result_folder_button)
        button_row.addWidget(self.compare_button)
        sidebar_layout.addLayout(button_row)

        path_row = QHBoxLayout()
        self.result_folder_path_label = QLineEdit()
        self.result_folder_path_label.setReadOnly(True)
        self.result_folder_path_label.setPlaceholderText("No folder selected.")
        path_row.addWidget(self.result_folder_path_label)
        files_layout.addLayout(path_row)

        self.result_file_list = QListWidget()
        self.result_file_list.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.result_file_list.setMaximumHeight(115)
        files_layout.addWidget(self.result_file_list)
        self.files_section = CollapsibleSection("Files", files_group)
        sidebar_layout.addWidget(self.files_section)

        selection_group = QGroupBox("Data")
        selection_layout = QVBoxLayout(selection_group)

        selection_controls_row = QHBoxLayout()
        selection_controls_row.addWidget(QLabel("Group By:"))
        self.selection_group_by_combo = QComboBox()
        self.selection_group_by_combo.addItem("Metric", userData="metric")
        self.selection_group_by_combo.addItem("Object", userData="object")
        self.selection_group_by_combo.setEnabled(False)
        selection_controls_row.addWidget(self.selection_group_by_combo)
        selection_controls_row.addStretch()
        selection_layout.addLayout(selection_controls_row)

        selection_search_row = QHBoxLayout()
        selection_search_row.addWidget(QLabel("Search:"))
        self.selection_search_input = QLineEdit()
        self.selection_search_input.setPlaceholderText("Search")
        self.selection_search_input.setToolTip("Space: match all words. Comma: match either term.")
        self.selection_search_input.setEnabled(False)
        selection_search_row.addWidget(self.selection_search_input)
        selection_layout.addLayout(selection_search_row)

        self.result_data_tree = QTreeWidget()
        self.result_data_tree.setHeaderHidden(True)
        self.result_data_tree.setMinimumHeight(200)
        self.result_data_tree.setEnabled(False)
        selection_layout.addWidget(self.result_data_tree, 1)

        selection_buttons_row = QHBoxLayout()
        self.clear_selection_button = QPushButton("Clear")
        self.plot_results_button = QPushButton("Plot")
        self.plot_results_button.setEnabled(False)
        self.open_popup_current_button = QToolButton()
        self.open_popup_current_button.setText("Popup")
        self.open_popup_current_button.setPopupMode(QToolButton.ToolButtonPopupMode.MenuButtonPopup)
        popup_menu = QMenu(self.open_popup_current_button)
        self.close_all_popups_action = popup_menu.addAction("Close all popups")
        self.open_popup_current_button.setMenu(popup_menu)
        selection_buttons_row.addWidget(self.clear_selection_button)
        selection_buttons_row.addWidget(self.plot_results_button)
        selection_buttons_row.addWidget(self.open_popup_current_button)
        selection_layout.addLayout(selection_buttons_row)

        sidebar_layout.addWidget(selection_group, 1)

        experiment_summary_group = QWidget()
        experiment_summary_layout = QVBoxLayout(experiment_summary_group)
        self.experiment_summary_status_label = QLabel("N/A")
        self.experiment_summary_status_label.setStyleSheet("color: #4a5568;")
        context_row_1.addWidget(self.experiment_summary_status_label)

        self.experiment_summary_table = QTableWidget(0, 2)
        self.experiment_summary_table.setHorizontalHeaderLabels(["Metric", "Value"])
        self.experiment_summary_table.verticalHeader().setVisible(False)
        self.experiment_summary_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.experiment_summary_table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.experiment_summary_table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.experiment_summary_table.setAlternatingRowColors(True)
        self.experiment_summary_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.experiment_summary_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        experiment_summary_layout.addWidget(self.experiment_summary_table)

        experiment_summary_footer = QHBoxLayout()
        experiment_summary_footer.addStretch()
        self.metric_guide_button = QPushButton("Metric guide")
        experiment_summary_footer.addWidget(self.metric_guide_button)
        experiment_summary_layout.addLayout(experiment_summary_footer)

        point_analysis_group = QGroupBox("Point")
        point_analysis_layout = QVBoxLayout(point_analysis_group)

        target_layout = QHBoxLayout()
        target_layout.addWidget(QLabel("Metric:"))
        self.find_max_target_combo = QComboBox()
        target_layout.addWidget(self.find_max_target_combo)
        point_analysis_layout.addLayout(target_layout)
        self.find_abs_max_button = QPushButton("Abs Max")
        self.find_max_button = QPushButton("Max")
        self.find_min_button = QPushButton("Min")
        for button in (self.find_abs_max_button, self.find_max_button, self.find_min_button):
            button.setEnabled(False)
        target_layout.addWidget(self.find_abs_max_button)
        target_layout.addWidget(self.find_max_button)
        target_layout.addWidget(self.find_min_button)
        self.find_max_target_combo.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)

        selected_export_layout = QHBoxLayout()
        self.selected_point_label = QLabel("Selected Point: None")
        selected_export_layout.addWidget(self.selected_point_label)
        selected_export_layout.addStretch()
        point_analysis_layout.addLayout(selected_export_layout)

        self.export_point_button = QPushButton("Save point CSV")
        self.export_point_button.setEnabled(False)
        selected_export_layout.addWidget(self.export_point_button)

        analysis_scenario_group = QWidget()
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
        main_plot_group = QWidget()
        main_plot_layout = QVBoxLayout(main_plot_group)
        main_plot_layout.setContentsMargins(4, 4, 4, 4)
        main_plot_layout.setSpacing(2)

        self.fig = Figure(figsize=(5, 4), dpi=100)
        self.canvas = FigureCanvas(self.fig)
        self.toolbar = NavigationToolbar(self.canvas, self)
        main_plot_layout.addWidget(self.toolbar)
        main_plot_layout.addWidget(self.canvas)
        main_plot_group.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.plot_manager = PlotManager(self.canvas, self.fig)

        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.addWidget(main_plot_group, 1)
        right_layout.addWidget(point_analysis_group)
        for name, content, attr in (("Summary", experiment_summary_group, "summary_section"),
                                    ("Export input", analysis_scenario_group, "export_section")):
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setFrameShape(QFrame.Shape.NoFrame)
            scroll.setMaximumHeight(220)
            scroll.setWidget(content)
            section = CollapsibleSection(name, scroll)
            setattr(self, attr, section)
            right_layout.addWidget(section)
        main_splitter.addWidget(sidebar)
        main_splitter.addWidget(right_panel)
        main_splitter.setStretchFactor(0, 0)
        main_splitter.setStretchFactor(1, 1)
        main_splitter.setSizes([300, 900])
        layout.addWidget(main_splitter, 1)

    def _connect_signals(self):
        self.open_result_button.clicked.connect(self.open_result_file)
        self.compare_button.clicked.connect(self.compare_selected_results)
        self.select_result_folder_button.clicked.connect(self.select_result_folder)
        self.result_file_list.itemClicked.connect(self.on_result_file_selected)
        self.selection_group_by_combo.currentIndexChanged.connect(self.refresh_result_tree)
        self.selection_search_input.textChanged.connect(self.refresh_result_tree)
        self.result_data_tree.itemChanged.connect(self.on_tree_item_changed)
        self.clear_selection_button.clicked.connect(self.clear_selection)
        self.plot_results_button.clicked.connect(self.plot_selected_results)
        self.open_popup_current_button.clicked.connect(self.open_popup_current_selection)
        self.close_all_popups_action.triggered.connect(self.close_all_popups)
        self.metric_guide_button.clicked.connect(self.open_metric_guide)
        self.canvas.mpl_connect('button_press_event', self.on_result_plot_click)
        self.find_abs_max_button.clicked.connect(self.on_find_abs_max_click)
        self.find_max_button.clicked.connect(self.on_find_max_click)
        self.find_min_button.clicked.connect(self.on_find_min_click)
        self.find_max_target_combo.currentIndexChanged.connect(self._on_point_target_changed)
        self.export_point_button.clicked.connect(self.on_export_point_data_click)
        
        # Scenario Output
        self.offset_manual_checkbox.toggled.connect(self._on_offset_checkbox_toggled)
        self.manual_height_checkbox.toggled.connect(self._on_manual_height_checkbox_toggled)
        for combo in self.offset_combos:
            combo.currentIndexChanged.connect(self._update_offset_choices)
        self.export_scenario_button.clicked.connect(self.export_analysis_scenario)

    def _reset_context_labels(self):
        set_path_label(self.context_active_file_label, None)
        self.compare_button.setEnabled(False)
        self.context_rows_label.setText("N/A")
        self.timeline_bar_info_label.setText("Full/Slice Range: unknown")
        self._set_selected_columns_context(0)
        self._clear_experiment_summary()
        self._set_timeline_bar_unknown()

    def _set_selected_columns_context(self, count):
        self.plot_results_button.setToolTip(f"Plot {count} selected quantities")

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

        set_path_label(self.context_active_file_label, self.current_result_file or file_name)
        self.compare_button.setEnabled(bool(self.current_result_file))
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
        self._update_drop_posture_summary()

    def _first_value(self, column_tuple):
        if self.result_data is None or column_tuple not in self.result_data.columns:
            return None
        values = self.result_data[column_tuple]
        if isinstance(values, pd.DataFrame):
            values = values.iloc[:, 0]
        values = values.dropna()
        if values.empty:
            return None
        return values.iloc[0]

    @staticmethod
    def _is_missing_value(value):
        if value is None:
            return True
        if isinstance(value, str) and value.strip() == "":
            return True
        try:
            return bool(pd.isna(value))
        except (TypeError, ValueError):
            return False

    def _format_summary_value(self, value, descriptor=None):
        if self._is_missing_value(value):
            return "N/A"
        column = descriptor.column if descriptor is not None else None
        formatted = format_result_value(column, value)
        if descriptor is not None and descriptor.unit:
            return f"{formatted} {descriptor.unit}"
        return formatted

    def _clear_experiment_summary(self, status_text="N/A"):
        self.experiment_summary_status_label.setText(status_text)
        self.experiment_summary_table.setRowCount(0)

    def _is_t1_summary_available(self):
        t1_detected_column = (
            HeaderL1.ANALYSIS,
            HeaderL2.DROP_POSTURE_SUMMARY,
            HeaderL3.DROP_T1_DETECTED,
        )
        value = self._first_value(t1_detected_column)
        if self._is_missing_value(value):
            return True
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.strip().lower() in {"true", "1", "yes"}
        try:
            return bool(float(value))
        except (TypeError, ValueError):
            return bool(value)

    def _add_experiment_summary_group_row(self, group_label):
        row = self.experiment_summary_table.rowCount()
        self.experiment_summary_table.insertRow(row)
        item = QTableWidgetItem(group_label)
        item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        item.setBackground(QColor("#edf2f7"))
        self.experiment_summary_table.setItem(row, 0, item)
        self.experiment_summary_table.setSpan(row, 0, 1, 2)

    def _add_experiment_summary_value_row(self, descriptor, value):
        row = self.experiment_summary_table.rowCount()
        self.experiment_summary_table.insertRow(row)

        metric_item = QTableWidgetItem(descriptor.display_name)
        value_item = QTableWidgetItem(self._format_summary_value(value, descriptor))
        for item in (metric_item, value_item):
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            item.setToolTip(descriptor.short_description)

        self.experiment_summary_table.setItem(row, 0, metric_item)
        self.experiment_summary_table.setItem(row, 1, value_item)

    def _update_drop_posture_summary(self):
        if self.result_data is None or self.result_data.empty:
            self._clear_experiment_summary("Drop Posture data unavailable")
            return

        descriptors = get_drop_posture_summary_descriptors()
        available_columns = {descriptor.column for descriptor in descriptors if descriptor.column in self.result_data.columns}
        if not available_columns:
            self._clear_experiment_summary("Drop Posture data unavailable")
            return

        self.experiment_summary_table.setRowCount(0)
        t1_available = self._is_t1_summary_available()
        populated_count = 0

        for group in DROP_POSTURE_SUMMARY_GROUP_ORDER:
            group_descriptors = [descriptor for descriptor in descriptors if descriptor.group == group]
            present_descriptors = [
                descriptor for descriptor in group_descriptors if descriptor.column in available_columns
            ]
            if not present_descriptors:
                continue

            self._add_experiment_summary_group_row(group.value)
            for descriptor in present_descriptors:
                value = None if descriptor.t1_based and not t1_available else self._first_value(descriptor.column)
                self._add_experiment_summary_value_row(descriptor, value)
                populated_count += 1

        if t1_available:
            self.experiment_summary_status_label.setText("Impact detected")
        else:
            self.experiment_summary_status_label.setText("No impact detected")
        self.experiment_summary_table.resizeRowsToContents()

    def open_metric_guide(self):
        dialog = DropPostureMetricGuideDialog(get_drop_posture_summary_descriptors(), self)
        dialog.exec()

    def _refresh_result_file_list(self, folder_path, selected_file=None, files=None):
        self.result_file_list.clear()
        try:
            files = list_result_files(folder_path) if files is None else list(files)
            # Direct opens also support legacy result CSV files. Include only
            # the validated active CSV, not every unrelated CSV in the folder.
            if selected_file and selected_file not in files:
                files = sorted([*files, selected_file])
            self._set_result_paths([os.path.join(folder_path, name) for name in files])
            self.log_message.emit(f"[INFO] Found {len(files)} result files in {folder_path}")
            if selected_file:
                for i in range(self.result_file_list.count()):
                    if self.result_file_list.item(i).text() == selected_file:
                        self.result_file_list.setCurrentRow(i)
                        break
        except Exception as e:
            self.log_message.emit(f"[ERROR] Failed to read folder: {e}")

    def _item_path(self, item):
        return item.data(Qt.ItemDataRole.UserRole) or os.path.join(
            self.result_folder_path_label.text(), item.text())

    def _set_result_paths(self, paths):
        self.result_file_list.clear()
        names = [os.path.basename(path) for path in paths]
        for path, name in zip(paths, names):
            text = name
            if names.count(name) > 1:
                text += f" ({os.path.dirname(path)})"
            item = QListWidgetItem(text)
            item.setData(Qt.ItemDataRole.UserRole, os.path.abspath(path))
            item.setToolTip(os.path.abspath(path))
            self.result_file_list.addItem(item)

    def open_result_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, 'Open result', '', 'Results (*.proc *.proc.csv *.csv)')
        if path:
            self.open_result_files([path])

    def open_result_files(self, paths):
        """Open the exact saved output list passed by the processing stage."""
        unique = {}
        for path in paths:
            path = os.path.abspath(path)
            unique.setdefault(os.path.normcase(os.path.realpath(path)), path)
        paths = list(unique.values())
        if not paths or not self.load_result_file(paths[0]):
            return False
        self.explicit_result_files = paths
        self._set_result_paths(paths)
        self._restore_active_file_selection()
        self.files_section.setExpanded(len(paths) > 1)
        return True

    def compare_selected_results(self):
        paths = [self._item_path(item) for item in self.result_file_list.selectedItems()]
        if not paths and self.current_result_file:
            paths = [self.current_result_file]
        if paths:
            self.compare_requested.emit(paths)

    def select_result_folder(self):
        folder_path = QFileDialog.getExistingDirectory(self, "Select Result Folder")
        if not folder_path:
            return
        try:
            files = list_result_files(folder_path)
        except OSError as error:
            self.log_message.emit(f'[ERROR] Could not read folder: {error}')
            return

        self.explicit_result_files = None
        self.selection_search_input.blockSignals(True)
        self.selection_search_input.clear()
        self.selection_search_input.blockSignals(False)
        self.result_folder_path_label.setText(folder_path)
        self.result_data_tree.clear()
        self.result_data_tree.setEnabled(False)
        self.selection_group_by_combo.setEnabled(False)
        self.selection_search_input.setEnabled(False)
        self.plot_results_button.setEnabled(False)
        self.find_max_target_combo.clear()
        self.result_data = None
        self.available_result_columns = []
        self.current_result_file = None
        self.checked_result_columns.clear()
        self.last_selected_result_columns.clear()
        self.plot_manager.draw_plot(None, [])
        self.toolbar.update()
        self.selected_point_info = {'time': None, 'index': None}
        self.update_point_selection_ui()
        self.close_all_popups()
        self._reset_context_labels()
        self._refresh_result_file_list(folder_path, files=files)
        self.files_section.setExpanded(True)

    def on_result_file_selected(self, item):
        self.load_result_file(self._item_path(item), preserve_selection=True)

    def _restore_active_file_selection(self):
        self.result_file_list.setCurrentRow(-1)
        for index in range(self.result_file_list.count()):
            if self._item_path(self.result_file_list.item(index)) == self.current_result_file:
                self.result_file_list.setCurrentRow(index)
                break

    @staticmethod
    def _prepare_result_data(data):
        """Validate a candidate without changing the result currently on screen."""
        if not isinstance(data, pd.DataFrame) or data.empty:
            raise ValueError('The file has no result samples.')
        if data.attrs.get('time_error'):
            raise ValueError('The file needs valid, increasing Time values in seconds.')
        if not data.columns.is_unique:
            raise ValueError('The file has conflicting result columns. Choose another result file.')
        data = data.copy()
        if data.index.name != TimeCols.TIME:
            if RESULT_TIME_COL in data.columns:
                data = data.set_index(RESULT_TIME_COL)
            elif TimeCols.TIME in data.columns:
                data = data.set_index(TimeCols.TIME)
            else:
                raise ValueError('The file needs a Time column in seconds.')
        times = pd.to_numeric(data.index, errors='coerce').to_numpy(dtype=float)
        if not np.isfinite(times).all() or (np.diff(times) <= 0).any():
            raise ValueError('Time must contain increasing, unique seconds without missing values.')
        data.index = pd.Index(times, name=TimeCols.TIME)
        for column in data.columns:
            if column not in DISPLAY_RESULT_COLUMNS:
                continue
            values = pd.to_numeric(data[column], errors='coerce')
            if (data[column].notna() & values.isna()).any():
                name = get_result_metric_display_name(*column)
                raise ValueError(f'{name} contains nonnumeric samples. Choose another result.')
            # Numeric strings are supported, while genuine missing samples stay
            # NaN so the graph continues to show the data gap.
            data[column] = values
        return data

    def _capture_result_context(self):
        return {
            'data': self.result_data,
            'file': self.current_result_file,
            'folder': self.result_folder_path_label.text(),
            'files': [self._item_path(self.result_file_list.item(i)) for i in range(self.result_file_list.count())],
            'explicit': self.explicit_result_files,
            'available': self.available_result_columns.copy(),
            'checked': self.checked_result_columns.copy(),
            'plotted': self.last_selected_result_columns.copy(),
            'point': self.selected_point_info.copy(),
            'target': self.find_max_target_combo.currentData(),
            'limits': self.plot_manager.capture_limits(),
            'popups': {name: (popup.selected_columns.copy(), popup.plot_manager.capture_limits())
                       for name, popup in self.popup_windows.items()},
        }

    def _restore_result_context(self, previous):
        """Recover the last good file if a candidate fails during UI rendering."""
        self.result_data = previous['data']
        self.current_result_file = previous['file']
        self.result_folder_path_label.setText(previous['folder'])
        self.explicit_result_files = previous['explicit']
        self._set_result_paths(previous['files'])
        self._restore_active_file_selection()
        self.available_result_columns = previous['available']
        self.checked_result_columns = previous['checked']
        self.last_selected_result_columns = previous['plotted']
        self.refresh_result_tree()
        for control in (self.result_data_tree, self.selection_group_by_combo,
                        self.selection_search_input, self.plot_results_button):
            control.setEnabled(self.result_data is not None)
        target_index = find_result_column_index(self.find_max_target_combo, previous['target'])
        if target_index >= 0:
            self.find_max_target_combo.setCurrentIndex(target_index)
        self._draw_result_columns([col for col in self.available_result_columns
                                   if col in self.last_selected_result_columns])
        self.selected_point_info = previous['point']
        self.update_point_selection_ui()
        self.plot_manager.restore_limits(previous['limits'])
        self.plot_manager.canvas.draw_idle()
        if self.current_result_file:
            self._update_context_from_dataframe(os.path.basename(self.current_result_file))
        else:
            self._reset_context_labels()
        for name, (columns, limits) in previous['popups'].items():
            popup = self.popup_windows[name]
            popup.set_plot_data(self.result_data, columns)
            popup.set_selected_time_cursor(self.selected_point_info.get('time'))
            popup.plot_manager.restore_limits(limits)
            popup.plot_manager.canvas.draw_idle()

    def load_result_file(self, file_path, *, preserve_selection=False):
        if not file_path:
            self._restore_active_file_selection()
            return False
        if not os.path.isfile(file_path):
            self._restore_active_file_selection()
            self.log_message.emit('[ERROR] Result file not found. Choose an existing result file.')
            return False

        file_path = os.path.abspath(file_path)
        folder_path = os.path.dirname(file_path)
        file_name = os.path.basename(file_path)
        try:
            candidate = self.data_loader.load_result_csv(file_path)
        except Exception:
            self._restore_active_file_selection()
            self.log_message.emit('[ERROR] Could not read this result. Choose a saved .proc or result CSV file.')
            return False
        try:
            candidate = self._prepare_result_data(candidate)
        except ValueError as error:
            self._restore_active_file_selection()
            self.log_message.emit(f'[ERROR] {error}')
            return False

        previous = self._capture_result_context()
        try:
            self._activate_result_data(candidate, file_path, preserve_selection=preserve_selection)
        except Exception:
            self._restore_result_context(previous)
            self.log_message.emit('[ERROR] Could not display this result. The previous result is still open.')
            return False
        self.log_message.emit(f'[INFO] Loaded {file_name}.')
        return True

    def _activate_result_data(self, candidate, file_path, *, preserve_selection=False):
        first_result = self.result_data is None
        folder_path = os.path.dirname(file_path)
        file_name = os.path.basename(file_path)
        self.result_data = candidate
        self.current_result_file = file_path
        self.result_folder_path_label.setText(folder_path)
        listed_paths = [self._item_path(self.result_file_list.item(i)) for i in range(self.result_file_list.count())]
        if file_path not in listed_paths:
            self.explicit_result_files = None
            self._refresh_result_file_list(folder_path, selected_file=file_name)
        elif not preserve_selection:
            self._restore_active_file_selection()
        else:
            item = self.result_file_list.item(listed_paths.index(file_path))
            self.result_file_list.setCurrentItem(item, QItemSelectionModel.SelectionFlag.NoUpdate)
        if first_result and not self.checked_result_columns:
            for default in (
                (HeaderL1.ANALYSIS, HeaderL2.DROP_POSTURE, HeaderL3.DROP_BETA_DEG),
                (HeaderL1.POS, HeaderL2.COM, HeaderL3.P_TY),
            ):
                if default in candidate.columns:
                    self.checked_result_columns = {default}
                    break
            self.last_selected_result_columns = self.checked_result_columns.copy()
        self.populate_result_tree(candidate)
        self.last_selected_result_columns.intersection_update(self.available_result_columns)
        self.result_data_tree.setEnabled(True)
        self.selection_group_by_combo.setEnabled(True)
        self.selection_search_input.setEnabled(True)
        self.plot_results_button.setEnabled(True)
        self._draw_result_columns([
            col for col in self.available_result_columns if col in self.last_selected_result_columns
        ])
        self._update_context_from_dataframe(file_name)
        self._refresh_popup_plots()
        self._update_popup_status_label()

    def populate_result_tree(self, df):
        self.available_result_columns = [
            normalize_result_column(col) for col in df.columns if col in DISPLAY_RESULT_COLUMNS
        ]
        self.available_result_columns.sort(
            key=lambda column: self._result_tree_sort_key(column, self._get_group_by_mode())
        )
        self.checked_result_columns.intersection_update(self.available_result_columns)
        self.refresh_result_tree()

    def refresh_result_tree(self):
        self.result_data_tree.blockSignals(True)
        self.result_data_tree.clear()
        top_level_items = {}
        search_terms = self._get_search_terms()

        for entry in self._build_result_tree_entries():
            if not self._entry_matches_search(entry, search_terms):
                continue

            top_label = entry["top_label"]
            mid_label = entry["mid_label"]
            column_tuple = entry["column"]

            if top_label not in top_level_items:
                top_item = QTreeWidgetItem(self.result_data_tree, [top_label])
                top_level_items[top_label] = {'item': top_item, 'children': {}}
            top_level_node = top_level_items[top_label]

            if mid_label not in top_level_node['children']:
                mid_item = QTreeWidgetItem(top_level_node['item'], [mid_label])
                top_level_node['children'][mid_label] = mid_item
            mid_item = top_level_node['children'][mid_label]

            leaf_item = QTreeWidgetItem(mid_item, [entry["leaf_label"]])
            leaf_item.setFlags(leaf_item.flags() | Qt.ItemIsUserCheckable)
            leaf_item.setData(0, Qt.ItemDataRole.UserRole, column_tuple)
            descriptor = get_result_metric_descriptor(column_tuple)
            if descriptor is not None:
                leaf_item.setToolTip(0, descriptor.short_description)
            else:
                leaf_item.setToolTip(0, get_result_metric_tooltip(column_tuple))

            if column_tuple in self.checked_result_columns:
                leaf_item.setCheckState(0, Qt.Checked)
            else:
                leaf_item.setCheckState(0, Qt.Unchecked)

        if self.selection_search_input.text().strip():
            self.result_data_tree.expandAll()
        else:
            for _top, _mid, leaf in self._iter_leaf_items():
                if leaf.checkState(0) == Qt.Checked:
                    _top.setExpanded(True)
                    _mid.setExpanded(True)
            first_checked = next((leaf for _top, _mid, leaf in self._iter_leaf_items()
                                  if leaf.checkState(0) == Qt.Checked), None)
            if first_checked:
                self.result_data_tree.scrollToItem(first_checked, QAbstractItemView.ScrollHint.PositionAtTop)
        self.result_data_tree.blockSignals(False)
        checked_columns = self._get_checked_columns()
        self._set_selected_columns_context(len(checked_columns))
        self._update_find_max_targets(checked_columns)

    @staticmethod
    def _result_metric_rank(l1):
        return {
            HeaderL1.POS: 0,
            HeaderL1.VEL: 1,
            HeaderL1.ACC: 2,
            HeaderL1.ANALYSIS: 3,
            HeaderL1.ANALYSIS_SCENARIO: 4
        }.get(l1, 99)

    @staticmethod
    def _result_object_rank(l2):
        if l2 == HeaderL2.COM:
            return 0
        if isinstance(l2, str) and l2.startswith("C") and l2[1:].isdigit():
            return int(l2[1:])
        return 99

    @classmethod
    def _result_component_rank(cls, l1, l2, l3):
        del cls
        l3_str = str(l3)
        if l1 == HeaderL1.POS and l2 == HeaderL2.COM:
            pos_order = ["P_TX", "P_TY", "P_TZ", "P_RX", "P_RY", "P_RZ"]
            if l3_str in pos_order:
                return pos_order.index(l3_str)
            return 999
        if l1 in {HeaderL1.VEL, HeaderL1.ACC} and l2 == HeaderL2.COM:
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
            return stacked.index(l3_str) if l3_str in stacked else 999
        if l1 in {HeaderL1.VEL, HeaderL1.ACC} and isinstance(l2, str) and l2.startswith("C") and l2[1:].isdigit():
            corner_order = [
                f"Global_{'V' if l1 == HeaderL1.VEL else 'A'}_TX",
                f"Global_{'V' if l1 == HeaderL1.VEL else 'A'}_TY",
                f"Global_{'V' if l1 == HeaderL1.VEL else 'A'}_TZ",
                f"Global_{'V' if l1 == HeaderL1.VEL else 'A'}_T_Norm",
            ]
            return corner_order.index(l3_str) if l3_str in corner_order else 999
        return 999

    @classmethod
    def _result_tree_sort_key(cls, column_tuple, group_by="metric"):
        l1, l2, l3 = column_tuple
        metric_rank = cls._result_metric_rank(l1)
        object_rank = cls._result_object_rank(l2)
        component_rank = cls._result_component_rank(l1, l2, l3)
        l3_str = str(l3)
        if group_by == "object":
            return (object_rank, metric_rank, component_rank, l3_str)
        return (metric_rank, object_rank, component_rank, l3_str)

    def _get_group_by_mode(self):
        return self.selection_group_by_combo.currentData() or "metric"

    def _get_search_terms(self):
        raw_text = self.selection_search_input.text().lower()
        groups = []
        for part in raw_text.split():
            options = [token.strip() for token in part.split(",") if token.strip()]
            if options:
                groups.append(options)
        return groups

    def _build_result_tree_entries(self):
        group_by = self._get_group_by_mode()
        entries = []
        sorted_columns = sorted(
            self.available_result_columns,
            key=lambda column: self._result_tree_sort_key(column, group_by),
        )

        for column in sorted_columns:
            l1, l2, l3 = column
            leaf_label = get_result_metric_display_name(l1, l2, l3)
            path_label = get_result_column_display_path(column)
            search_text = " ".join([
                str(l1),
                str(l2),
                str(l3),
                leaf_label,
                path_label,
                get_result_metric_tooltip(column),
            ]).lower()

            if group_by == "object":
                top_label = RESULT_LEVEL2_DISPLAY.get(l2, str(l2))
                mid_label = RESULT_LEVEL1_DISPLAY.get(l1, str(l1))
            else:
                top_label = RESULT_LEVEL1_DISPLAY.get(l1, str(l1))
                mid_label = RESULT_LEVEL2_DISPLAY.get(l2, str(l2))

            entries.append({
                "column": column,
                "top_label": top_label,
                "mid_label": mid_label,
                "leaf_label": leaf_label,
                "search_text": search_text,
            })

        return entries

    @staticmethod
    def _entry_matches_search(entry, search_terms):
        if not search_terms:
            return True
        search_text = entry["search_text"]
        return all(any(option in search_text for option in group) for group in search_terms)

    def _iter_leaf_items(self):
        root = self.result_data_tree.invisibleRootItem()
        for i in range(root.childCount()):
            top_item = root.child(i)
            for j in range(top_item.childCount()):
                mid_item = top_item.child(j)
                for k in range(mid_item.childCount()):
                    yield top_item, mid_item, mid_item.child(k)

    def _get_checked_columns(self):
        return [
            entry["column"]
            for entry in self._build_result_tree_entries()
            if entry["column"] in self.checked_result_columns
        ]

    def on_tree_item_changed(self, item, _column):
        column_tuple = item.data(0, Qt.ItemDataRole.UserRole)
        if column_tuple is None:
            return

        normalized_column = normalize_result_column(column_tuple)
        if item.checkState(0) == Qt.Checked:
            self.checked_result_columns.add(normalized_column)
        else:
            self.checked_result_columns.discard(normalized_column)

        checked_columns = self._get_checked_columns()
        self._set_selected_columns_context(len(checked_columns))
        self._update_find_max_targets(checked_columns)

    def clear_selection(self):
        self.checked_result_columns.clear()
        self.refresh_result_tree()

    def _update_find_max_targets(self, checked_columns):
        current_target = self.find_max_target_combo.currentData()
        self.find_max_target_combo.clear()
        for col in checked_columns:
            self.find_max_target_combo.addItem(get_result_column_display_path(col), userData=col)

        index = find_result_column_index(self.find_max_target_combo, current_target)
        if index >= 0:
            self.find_max_target_combo.setCurrentIndex(index)

    def _on_point_target_changed(self, *_):
        column = self.find_max_target_combo.currentData()
        quantitative = column is not None and not is_corner_id_column(column)
        for button in (self.find_abs_max_button, self.find_max_button, self.find_min_button):
            button.setEnabled(quantitative)
        self.find_max_target_combo.setToolTip(get_result_metric_tooltip(column))
        self.update_point_selection_ui()

    def plot_selected_results(self):
        if self.result_data is None:
            return

        checked_columns = self._get_checked_columns()
        self.last_selected_result_columns = set(checked_columns)
        self._set_selected_columns_context(len(checked_columns))
        self._update_find_max_targets(checked_columns)
        self.log_message.emit(f"[INFO] Plotting {len(checked_columns)} result columns...")
        self._draw_result_columns(checked_columns)

    def _draw_result_columns(self, columns):
        plot_df = self.result_data[columns].copy() if columns else None
        self.plot_manager.draw_plot(plot_df, columns)
        if columns:
            self.plot_manager.ax.set_title("")
        self.plot_manager.canvas.draw_idle()
        self.toolbar.update()
        self.toolbar.push_current()
        self.selected_point_info = {'time': None, 'index': None}
        self.update_point_selection_ui()
        self._sync_popup_cursors()

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
        if event.inaxes not in self.plot_manager.axes:
            return
        if self.result_data is None or self.result_data.empty:
            return
        if event.xdata is None:
            return

        self._select_time_by_xdata(event.xdata)

    def _get_selected_target_value(self):
        if self.result_data is None:
            return None

        selected_index = self.selected_point_info.get('index')
        if selected_index is None:
            return None

        target_column = self.find_max_target_combo.currentData()
        if target_column is None:
            return None
        target_column = normalize_result_column(target_column)

        try:
            value = self.result_data.iloc[selected_index][target_column]
            return float(value)
        except Exception:
            return None

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

            if value is None:
                value = self._get_selected_target_value()

            if value is not None:
                self.selected_point_label.setText(
                    f"{time_text} s: {format_result_value(self.find_max_target_combo.currentData(), value)}"
                )
            else:
                self.selected_point_label.setText(f"{time_text} s")
            self.export_point_button.setEnabled(True)
            self.export_scenario_button.setEnabled(True)
        else:
            self.selected_point_label.setText("No point selected")
            self.export_point_button.setEnabled(False)
            self.export_scenario_button.setEnabled(False)
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
            columns = [col for col in popup.selected_columns if col in self.result_data.columns]
            popup.set_plot_data(self.result_data, columns)
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
        self.open_popup_current_button.setToolTip(f"{len(self.popup_windows)} open popups")
        self.close_all_popups_action.setEnabled(bool(self.popup_windows))

    def on_popup_point_selected(self, selected_time):
        self._select_time_by_xdata(selected_time)

    def _find_extreme_point(self, mode):
        if self.result_data is None or self.result_data.empty:
            return
        target_column = self.find_max_target_combo.currentData()
        if target_column is None:
            self.log_message.emit("[WARNING] No target data selected for peak search.")
            return
        target_column = normalize_result_column(target_column)
        if is_corner_id_column(target_column):
            return

        try:
            series = pd.to_numeric(self.result_data[target_column], errors='coerce')
            if mode == "abs_max":
                extreme_index = series.abs().idxmax()
                extreme_value = self.result_data.loc[extreme_index, target_column]
                action_label = "abs max"
            elif mode == "max":
                extreme_index = series.idxmax()
                extreme_value = self.result_data.loc[extreme_index, target_column]
                action_label = "max"
            elif mode == "min":
                extreme_index = series.idxmin()
                extreme_value = self.result_data.loc[extreme_index, target_column]
                action_label = "min"
            else:
                raise ValueError(f"Unknown extreme mode: {mode}")

            self._select_time_by_xdata(extreme_index, value=extreme_value)
            selected_time = self.selected_point_info.get('time')
            try:
                selected_time_text = f"{float(selected_time):.3f}s"
            except Exception:
                selected_time_text = str(selected_time)
            self.log_message.emit(
                f"[INFO] Found {action_label} for '{get_result_column_display_path(target_column)}': "
                f"{float(extreme_value):.4f} at T={selected_time_text}"
            )
        except Exception as e:
            self.log_message.emit(f"[ERROR] Could not find extreme value: {e}")

    def on_find_abs_max_click(self):
        self._find_extreme_point("abs_max")

    def on_find_max_click(self):
        self._find_extreme_point("max")

    def on_find_min_click(self):
        self._find_extreme_point("min")

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
