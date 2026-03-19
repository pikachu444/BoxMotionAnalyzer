import os

from PySide6.QtCore import Signal, Qt
from PySide6.QtWidgets import (
    QApplication,
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QLineEdit, QComboBox, QTextEdit, QGroupBox, QGridLayout, QFileDialog, QRadioButton, QCheckBox,
    QSizePolicy, QSplitter
)
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qtagg import NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure

from src.analysis.pipeline.artifact_io import (
    PROC_FILE_EXTENSION,
    add_timeline_context_columns,
    build_batch_proc_path,
    build_proc_default_name,
    list_slice_files,
    proc_file_filter,
    read_slice_metadata,
    slice_file_filter,
    save_proc_file,
)
from src.analysis.pipeline.pipeline_controller import PipelineController
from src.analysis.ui.data_selection_dialog import DataSelectionDialog
from src.analysis.ui.dialog_processing_settings import ProcessingSettingsDialog
from src.analysis.ui.plot_manager import PlotManager
from src.config import config_app, config_analysis_ui
from src.config.data_columns import DisplayNames, PoseCols, RawMarkerCols, RigidBodyCols


class WidgetSliceProcessing(QWidget):
    processing_requested = Signal(dict, object, object, object, dict)
    log_message = Signal(str)

    def __init__(self, data_loader, parser):
        super().__init__()
        self.data_loader = data_loader
        self.parser = parser

        self.header_info = None
        self.raw_data = None
        self.parsed_data = None
        self.slice_path = None
        self.slice_metadata = None
        self.current_selected_targets = []
        self.current_processing_mode = config_analysis_ui.DEFAULT_PROCESSING_MODE
        self.advanced_processing_options = config_analysis_ui.get_initial_advanced_options()
        self.current_processed_result = None
        self.current_proc_path = None
        self.batch_slice_folder = None
        self.pipeline_controller_factory = PipelineController

        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        group_box = QGroupBox("Slice Processing")
        group_layout = QVBoxLayout(group_box)

        main_splitter = QSplitter(Qt.Orientation.Vertical)
        main_splitter.setChildrenCollapsible(False)

        top_splitter = QSplitter(Qt.Orientation.Horizontal)
        top_splitter.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        plot_container = QWidget()
        plot_layout = QVBoxLayout(plot_container)
        plot_layout.setContentsMargins(0, 0, 0, 0)

        self.fig = Figure(figsize=(5, 4), dpi=100)
        self.fig.subplots_adjust(left=0.08, right=0.98, bottom=0.1, top=0.95)
        self.canvas = FigureCanvas(self.fig)
        self.toolbar = NavigationToolbar(self.canvas, self)
        plot_layout.addWidget(self.toolbar)
        plot_layout.addWidget(self.canvas)
        plot_container.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        self.plot_manager = PlotManager(self.canvas, self.fig)
        self.plot_manager.ax.text(0.5, 0.5, "Load a .slice file to start processing.", ha="center", va="center")
        self.plot_manager.canvas.draw()
        top_splitter.addWidget(plot_container)

        right_panel = QWidget()
        right_panel_layout = QVBoxLayout()
        right_panel.setLayout(right_panel_layout)

        self.load_slice_button = QPushButton("Load Slice File...")
        self.slice_path_label = QLabel("No slice selected.")
        self.slice_path_label.setWordWrap(True)
        right_panel_layout.addWidget(self.load_slice_button)
        right_panel_layout.addWidget(self.slice_path_label)

        self.slice_summary_group = QGroupBox("Slice Summary")
        slice_summary_layout = QGridLayout(self.slice_summary_group)
        slice_summary_layout.addWidget(QLabel("Source:"), 0, 0)
        self.slice_source_label = QLabel("N/A")
        self.slice_source_label.setWordWrap(True)
        slice_summary_layout.addWidget(self.slice_source_label, 0, 1)
        slice_summary_layout.addWidget(QLabel("User Range:"), 1, 0)
        self.slice_user_range_label = QLabel("N/A")
        slice_summary_layout.addWidget(self.slice_user_range_label, 1, 1)
        slice_summary_layout.addWidget(QLabel("Padded Range:"), 2, 0)
        self.slice_padded_range_label = QLabel("N/A")
        slice_summary_layout.addWidget(self.slice_padded_range_label, 2, 1)
        right_panel_layout.addWidget(self.slice_summary_group)

        self.box_dims_group = QGroupBox("Box Dimensions (mm)")
        box_dims_layout = QGridLayout(self.box_dims_group)
        box_dims_layout.addWidget(QLabel("L:"), 0, 0)
        self.le_box_l = QLineEdit(str(config_app.BOX_DIMS[0]))
        box_dims_layout.addWidget(self.le_box_l, 0, 1)
        box_dims_layout.addWidget(QLabel("W:"), 1, 0)
        self.le_box_w = QLineEdit(str(config_app.BOX_DIMS[1]))
        box_dims_layout.addWidget(self.le_box_w, 1, 1)
        box_dims_layout.addWidget(QLabel("H:"), 2, 0)
        self.le_box_h = QLineEdit(str(config_app.BOX_DIMS[2]))
        box_dims_layout.addWidget(self.le_box_h, 2, 1)
        right_panel_layout.addWidget(self.box_dims_group)

        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setPlaceholderText("[INFO] Load a .slice file to start processing.")
        right_panel_layout.addWidget(self.log_output)
        right_panel.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)

        top_splitter.addWidget(right_panel)
        top_splitter.setChildrenCollapsible(False)
        top_splitter.setStretchFactor(0, 5)
        top_splitter.setStretchFactor(1, 2)
        top_splitter.setSizes([900, 280])
        main_splitter.addWidget(top_splitter)

        controls_widget = QWidget()
        h_controls_layout = QHBoxLayout(controls_widget)
        controls_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        controls_widget.setMinimumHeight(180)

        plot_options_group = QGroupBox("Plot Options")
        plot_options_layout = QVBoxLayout(plot_options_group)
        plot_options_top_row = QHBoxLayout()
        self.select_data_button = QPushButton("Select Data...")
        self.selected_data_label = QLabel("Selected: None")
        self.selected_data_label.setWordWrap(True)
        plot_options_top_row.addWidget(self.select_data_button)
        plot_options_top_row.addWidget(self.selected_data_label)
        plot_options_layout.addLayout(plot_options_top_row)

        plot_options_bottom_row = QHBoxLayout()
        plot_options_bottom_row.addWidget(QLabel("Axis:"))
        self.combo_plot_axis = QComboBox()
        self.combo_plot_axis.addItem("Position-X", userData=PoseCols.POS_X)
        self.combo_plot_axis.addItem("Position-Y", userData=PoseCols.POS_Y)
        self.combo_plot_axis.addItem("Position-Z", userData=PoseCols.POS_Z)
        plot_options_bottom_row.addWidget(self.combo_plot_axis)
        plot_options_bottom_row.addStretch()
        plot_options_layout.addLayout(plot_options_bottom_row)
        h_controls_layout.addWidget(plot_options_group)

        self.resampling_group = QGroupBox(config_analysis_ui.RESAMPLING_GROUP_TITLE)
        resampling_layout = QGridLayout(self.resampling_group)
        self.cb_enable_resampling = QCheckBox(config_analysis_ui.RESAMPLING_ENABLE_LABEL)
        resampling_layout.addWidget(self.cb_enable_resampling, 0, 0, 1, 2)
        resampling_layout.addWidget(QLabel(config_analysis_ui.RESAMPLING_FACTOR_LABEL), 1, 0)
        self.combo_resampling_factor = QComboBox()
        for label, factor in config_analysis_ui.RESAMPLING_FACTOR_CHOICES:
            self.combo_resampling_factor.addItem(label, userData=factor)
        self.combo_resampling_factor.setEnabled(False)
        resampling_layout.addWidget(self.combo_resampling_factor, 1, 1)
        self.resampling_description = QLabel(config_analysis_ui.RESAMPLING_DESCRIPTION)
        self.resampling_description.setWordWrap(True)
        self.resampling_description.setStyleSheet("color: #4a5568;")
        self.resampling_description.setFixedHeight(
            config_analysis_ui.RAW_DATA_PROCESSING_LAYOUT["resampling_description_fixed_height"]
        )
        self.resampling_description.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        resampling_layout.addWidget(self.resampling_description, 2, 0, 1, 2)
        h_controls_layout.addWidget(self.resampling_group)

        processing_group = QGroupBox(config_analysis_ui.PROCESSING_MODE_GROUP_TITLE)
        processing_layout = QVBoxLayout(processing_group)
        processing_group.setMinimumWidth(
            config_analysis_ui.RAW_DATA_PROCESSING_LAYOUT["processing_group_min_width"]
        )

        radio_row = QHBoxLayout()
        self.rb_processing_raw = QRadioButton(
            config_analysis_ui.PROCESSING_MODE_LABELS[config_analysis_ui.PROCESSING_MODE_RAW]
        )
        self.rb_processing_raw.setChecked(
            self.current_processing_mode == config_analysis_ui.PROCESSING_MODE_RAW
        )
        self.rb_processing_standard = QRadioButton(
            config_analysis_ui.PROCESSING_MODE_LABELS[config_analysis_ui.PROCESSING_MODE_STANDARD]
        )
        self.rb_processing_standard.setChecked(
            self.current_processing_mode == config_analysis_ui.PROCESSING_MODE_STANDARD
        )
        self.rb_processing_advanced = QRadioButton(
            config_analysis_ui.PROCESSING_MODE_LABELS[config_analysis_ui.PROCESSING_MODE_ADVANCED]
        )
        radio_row.addWidget(self.rb_processing_raw)
        radio_row.addWidget(self.rb_processing_standard)
        radio_row.addWidget(self.rb_processing_advanced)
        radio_row.addStretch()
        processing_layout.addLayout(radio_row)

        settings_row = QHBoxLayout()
        settings_row.addStretch()
        self.processing_settings_button = QPushButton(config_analysis_ui.ADVANCED_BUTTON_TEXT)
        self.processing_settings_button.setEnabled(False)
        self.processing_settings_button.setMinimumWidth(
            config_analysis_ui.RAW_DATA_PROCESSING_LAYOUT["processing_settings_button_min_width"]
        )
        self.processing_settings_button.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        settings_row.addWidget(self.processing_settings_button)
        processing_layout.addLayout(settings_row)

        self.processing_mode_description = QLabel()
        self.processing_mode_description.setWordWrap(True)
        self.processing_mode_description.setStyleSheet("color: #4a5568;")
        self.processing_mode_description.setFixedHeight(
            config_analysis_ui.RAW_DATA_PROCESSING_LAYOUT["processing_mode_description_fixed_height"]
        )
        self.processing_mode_description.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        processing_layout.addWidget(self.processing_mode_description)
        h_controls_layout.addWidget(processing_group)

        result_group = QGroupBox("Processing Output")
        result_layout = QGridLayout(result_group)
        result_layout.addWidget(QLabel("Current Result:"), 0, 0)
        self.result_status_label = QLabel("Not processed yet.")
        self.result_status_label.setWordWrap(True)
        result_layout.addWidget(self.result_status_label, 0, 1)
        result_layout.addWidget(QLabel("Saved File:"), 1, 0)
        self.proc_path_label = QLabel("Not saved yet.")
        self.proc_path_label.setWordWrap(True)
        result_layout.addWidget(self.proc_path_label, 1, 1)
        h_controls_layout.addWidget(result_group)

        batch_group = QGroupBox("Batch Processing")
        batch_layout = QGridLayout(batch_group)
        self.select_slice_folder_button = QPushButton("Select Slice Folder...")
        batch_layout.addWidget(self.select_slice_folder_button, 0, 0, 1, 2)
        batch_layout.addWidget(QLabel("Folder:"), 1, 0)
        self.batch_folder_label = QLabel("No folder selected.")
        self.batch_folder_label.setWordWrap(True)
        batch_layout.addWidget(self.batch_folder_label, 1, 1)
        self.overwrite_proc_checkbox = QCheckBox("Overwrite existing .proc")
        batch_layout.addWidget(self.overwrite_proc_checkbox, 2, 0, 1, 2)
        batch_layout.addWidget(QLabel("Summary:"), 3, 0)
        self.batch_summary_label = QLabel("Not run yet.")
        self.batch_summary_label.setWordWrap(True)
        batch_layout.addWidget(self.batch_summary_label, 3, 1)
        self.run_batch_button = QPushButton("Run Batch Processing")
        batch_layout.addWidget(self.run_batch_button, 4, 0, 1, 2)
        h_controls_layout.addWidget(batch_group)

        plot_options_group.setMinimumWidth(
            config_analysis_ui.RAW_DATA_PROCESSING_LAYOUT["plot_options_group_min_width"]
        )
        self.resampling_group.setMinimumWidth(
            config_analysis_ui.RAW_DATA_PROCESSING_LAYOUT["resampling_group_min_width"]
        )

        action_layout = QVBoxLayout()
        self.run_button = QPushButton("Run Processing")
        self.run_button.setEnabled(False)
        self.save_proc_button = QPushButton("Save Processed Result")
        self.save_proc_button.setEnabled(False)
        action_layout.addWidget(self.run_button)
        action_layout.addWidget(self.save_proc_button)
        h_controls_layout.addLayout(action_layout)

        for index, stretch in enumerate(config_analysis_ui.RAW_DATA_PROCESSING_LAYOUT["bottom_controls_stretch"]):
            if index <= 3:
                h_controls_layout.setStretch(index, stretch)
        h_controls_layout.setStretch(4, 4)
        h_controls_layout.setStretch(5, 4)
        h_controls_layout.setStretch(6, 2)

        main_splitter.addWidget(controls_widget)
        main_splitter.setStretchFactor(0, 6)
        main_splitter.setStretchFactor(1, 1)
        main_splitter.setSizes([700, 220])

        group_layout.addWidget(main_splitter)
        layout.addWidget(group_box)
        self._update_processing_mode_ui()

    def _connect_signals(self):
        self.load_slice_button.clicked.connect(self.open_slice_file)
        self.select_data_button.clicked.connect(self.open_data_selection_dialog)
        self.combo_plot_axis.currentIndexChanged.connect(self.update_plot)
        self.cb_enable_resampling.toggled.connect(self.combo_resampling_factor.setEnabled)
        self.rb_processing_standard.toggled.connect(self._on_processing_mode_changed)
        self.rb_processing_raw.toggled.connect(self._on_processing_mode_changed)
        self.rb_processing_advanced.toggled.connect(self._on_processing_mode_changed)
        self.processing_settings_button.clicked.connect(self.open_processing_settings_dialog)
        self.run_button.clicked.connect(self.emit_run_processing)
        self.save_proc_button.clicked.connect(self.save_processed_result)
        self.select_slice_folder_button.clicked.connect(self.select_slice_folder)
        self.run_batch_button.clicked.connect(self.run_batch_processing)

    def append_log(self, message):
        self.log_output.append(message)

    def _set_slice_summary(self):
        if self.slice_metadata is None:
            self.slice_source_label.setText("N/A")
            self.slice_user_range_label.setText("N/A")
            self.slice_padded_range_label.setText("N/A")
            return

        self.slice_source_label.setText(self.slice_metadata.source or "N/A")
        self.slice_user_range_label.setText(
            f"{self.slice_metadata.user_start:.3f}s ~ {self.slice_metadata.user_end:.3f}s"
        )
        self.slice_padded_range_label.setText(
            f"{self.slice_metadata.padded_start:.3f}s ~ {self.slice_metadata.padded_end:.3f}s"
        )

    def _apply_box_dims_from_metadata(self, metadata=None):
        metadata = self.slice_metadata if metadata is None else metadata
        if metadata is None:
            return

        if metadata.box_l is not None:
            self.le_box_l.setText(f"{metadata.box_l:g}")
        if metadata.box_w is not None:
            self.le_box_w.setText(f"{metadata.box_w:g}")
        if metadata.box_h is not None:
            self.le_box_h.setText(f"{metadata.box_h:g}")

    def _load_slice_bundle(self, filepath: str):
        metadata = read_slice_metadata(filepath)
        header_info, raw_data = self.data_loader.load_csv(filepath)
        parsed_data = self.parser.process(header_info, raw_data)
        return metadata, header_info, raw_data, parsed_data

    def open_slice_file(self):
        filepath, _ = QFileDialog.getOpenFileName(self, "Select Slice File", "", slice_file_filter())
        if filepath:
            self.load_slice_file(filepath)

    def load_slice_file(self, filepath: str):
        try:
            self.slice_metadata, self.header_info, self.raw_data, self.parsed_data = self._load_slice_bundle(filepath)
            self.slice_path = filepath
            self.slice_path_label.setText(filepath)
            self._set_slice_summary()
            self._apply_box_dims_from_metadata()
            self.current_proc_path = None
            self.current_processed_result = None
            self.proc_path_label.setText("Not saved yet.")
            self.result_status_label.setText("Ready to process.")
            self.save_proc_button.setEnabled(False)
            self.run_button.setEnabled(True)

            all_targets = self.data_loader.get_plottable_targets(self.parsed_data)
            if DisplayNames.RB_CENTER in all_targets:
                self.current_selected_targets = [DisplayNames.RB_CENTER]
                self.selected_data_label.setText(f"Selected: {DisplayNames.RB_CENTER}")
            elif all_targets:
                self.current_selected_targets = [all_targets[0]]
                self.selected_data_label.setText(f"Selected: {all_targets[0]}")
            else:
                self.current_selected_targets = []
                self.selected_data_label.setText("Selected: None")

            self.update_plot()
            self.append_log(f"[INFO] Loaded slice file: {filepath}")
            if (
                self.slice_metadata.box_l is not None and
                self.slice_metadata.box_w is not None and
                self.slice_metadata.box_h is not None
            ):
                self.append_log(
                    "[INFO] Box dimensions restored from slice metadata: "
                    f"L={self.slice_metadata.box_l:g}, "
                    f"W={self.slice_metadata.box_w:g}, "
                    f"H={self.slice_metadata.box_h:g}"
                )
            self.append_log("[INFO] Slice parsed and ready for processing.")
        except Exception as e:
            self.append_log(f"[ERROR] Failed to load slice file: {e}")

    def update_plot(self):
        df = self.parsed_data
        if df is None or df.empty:
            self.plot_manager.draw_plot(None, [])
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
                if target == DisplayNames.RB_CENTER:
                    base_name = RigidBodyCols.BASE_NAME
                elif target.startswith(DisplayNames.MARKER_PREFIX):
                    base_name = target.replace(DisplayNames.MARKER_PREFIX, "")
                else:
                    base_name = target

                col_name = f"{base_name}{axis_suffix}"
                if col_name in df.columns:
                    columns_to_plot.append(col_name)

        self.plot_manager.draw_plot(df, columns_to_plot)

    def open_data_selection_dialog(self):
        if self.parsed_data is None:
            return
        all_targets = self.data_loader.get_plottable_targets(self.parsed_data)
        dialog = DataSelectionDialog(all_targets, self.current_selected_targets, self)
        if dialog.exec():
            self.current_selected_targets = dialog.get_selected_items()
            self.selected_data_label.setText(f"Selected: {', '.join(self.current_selected_targets)}")
            self.update_plot()

    def _on_processing_mode_changed(self):
        if self.rb_processing_standard.isChecked():
            self.current_processing_mode = config_analysis_ui.PROCESSING_MODE_STANDARD
        elif self.rb_processing_raw.isChecked():
            self.current_processing_mode = config_analysis_ui.PROCESSING_MODE_RAW
        elif self.rb_processing_advanced.isChecked():
            self.current_processing_mode = config_analysis_ui.PROCESSING_MODE_ADVANCED
        self._update_processing_mode_ui()

    def _update_processing_mode_ui(self):
        self.processing_settings_button.setEnabled(
            self.current_processing_mode == config_analysis_ui.PROCESSING_MODE_ADVANCED
        )
        self.processing_mode_description.setText(
            config_analysis_ui.PROCESSING_MODE_DESCRIPTIONS[self.current_processing_mode]
        )

    def open_processing_settings_dialog(self):
        dialog = ProcessingSettingsDialog(self.advanced_processing_options, self)
        if dialog.exec():
            self.advanced_processing_options = dialog.get_settings()
            self._update_processing_mode_ui()

    def _build_analysis_overrides(self):
        if self.current_processing_mode == config_analysis_ui.PROCESSING_MODE_STANDARD:
            return config_analysis_ui.get_default_advanced_options()
        if self.current_processing_mode == config_analysis_ui.PROCESSING_MODE_RAW:
            return config_analysis_ui.get_raw_mode_options()
        return dict(self.advanced_processing_options)

    def _get_current_box_dimensions(self) -> tuple[float, float, float]:
        return (
            float(self.le_box_l.text()),
            float(self.le_box_w.text()),
            float(self.le_box_h.text()),
        )

    def _set_box_dimensions(self, box_dims: tuple[float, float, float]):
        config_app.BOX_DIMS = [float(box_dims[0]), float(box_dims[1]), float(box_dims[2])]

    def _resolve_box_dimensions(self, metadata=None) -> tuple[float, float, float]:
        metadata = self.slice_metadata if metadata is None else metadata
        if (
            metadata is not None
            and metadata.box_l is not None
            and metadata.box_w is not None
            and metadata.box_h is not None
        ):
            return (float(metadata.box_l), float(metadata.box_w), float(metadata.box_h))
        return self._get_current_box_dimensions()

    def _build_timeline_context(self, metadata=None) -> dict:
        metadata = self.slice_metadata if metadata is None else metadata
        full_start = None if metadata is None else metadata.full_start
        full_end = None if metadata is None else metadata.full_end
        slice_start = None if metadata is None else metadata.user_start
        slice_end = None if metadata is None else metadata.user_end
        return {
            "full_start_sec": full_start,
            "full_end_sec": full_end,
            "slice_start_sec": slice_start,
            "slice_end_sec": slice_end,
        }

    def _build_processing_config(self, parsed_data, metadata=None) -> dict:
        metadata = self.slice_metadata if metadata is None else metadata
        return {
            "slice_filter_by": "time",
            "slice_start_val": (
                metadata.user_start if metadata else float(parsed_data.index.min())
            ),
            "slice_end_val": (
                metadata.user_end if metadata else float(parsed_data.index.max())
            ),
            "enable_resampling": self.cb_enable_resampling.isChecked(),
            "resampling_factor": self.combo_resampling_factor.currentData(),
            "resampling_method": "linear",
            "processing_mode": self.current_processing_mode,
            "analysis_options": self._build_analysis_overrides(),
        }

    def emit_run_processing(self):
        if self.parsed_data is None:
            return
        try:
            self._set_box_dimensions(self._get_current_box_dimensions())
            config = self._build_processing_config(self.parsed_data, self.slice_metadata)
            self.run_button.setEnabled(False)
            self.save_proc_button.setEnabled(False)
            self.current_proc_path = None
            self.proc_path_label.setText("Not saved yet.")
            self.result_status_label.setText("Processing...")
            self.append_log("[INFO] Starting processing...")
            self.processing_requested.emit(
                config,
                self.header_info,
                self.raw_data,
                self.parsed_data,
                self._build_timeline_context(),
            )
        except Exception as e:
            self.append_log(f"[ERROR] Invalid processing configuration: {e}")

    def on_processing_finished(self, processed_df):
        self.run_button.setEnabled(True)
        self.current_processed_result = processed_df
        if processed_df is not None and not processed_df.empty:
            self.result_status_label.setText("Processed result ready.")
            self.save_proc_button.setEnabled(True)
            self.append_log("[INFO] Processing completed successfully.")
            self.append_log("[INFO] Save the processed result as a .proc file for Step 2 analysis.")
        else:
            self.result_status_label.setText("Processing failed.")
            self.save_proc_button.setEnabled(False)
            self.append_log("[ERROR] Processing failed.")

    def on_processing_failed(self):
        self.run_button.setEnabled(True)
        self.result_status_label.setText("Processing failed.")
        self.save_proc_button.setEnabled(False)

    def select_slice_folder(self):
        folder_path = QFileDialog.getExistingDirectory(self, "Select Slice Folder")
        if not folder_path:
            return

        self.batch_slice_folder = folder_path
        self.batch_folder_label.setText(folder_path)
        self.batch_summary_label.setText("Ready to run.")
        self.append_log(f"[INFO] Selected slice folder for batch processing: {folder_path}")

    def _set_batch_controls_enabled(self, enabled: bool):
        self.select_slice_folder_button.setEnabled(enabled)
        self.run_batch_button.setEnabled(enabled)
        self.load_slice_button.setEnabled(enabled)
        self.run_button.setEnabled(enabled and self.parsed_data is not None)

    def run_batch_processing(self):
        folder_path = self.batch_slice_folder
        if not folder_path:
            self.append_log("[ERROR] Select a slice folder before running batch processing.")
            return

        try:
            slice_filenames = list_slice_files(folder_path)
        except Exception as e:
            self.append_log(f"[ERROR] Failed to read slice folder: {e}")
            return

        if not slice_filenames:
            self.batch_summary_label.setText("No .slice files found.")
            self.append_log(f"[ERROR] No .slice files found in {folder_path}")
            return

        controller = self.pipeline_controller_factory()
        controller.log_message.connect(self.append_log)
        overwrite_existing = self.overwrite_proc_checkbox.isChecked()
        total_files = len(slice_filenames)
        processed_count = 0
        skipped_count = 0
        failed_count = 0
        original_box_dims = list(config_app.BOX_DIMS)

        self._set_batch_controls_enabled(False)
        self.save_proc_button.setEnabled(False)
        self.current_processed_result = None
        self.current_proc_path = None
        self.proc_path_label.setText("Not saved yet.")
        self.result_status_label.setText("Batch processing...")
        self.batch_summary_label.setText("Running...")
        self.append_log(
            f"[INFO] Starting batch processing in {folder_path} "
            f"(total={total_files}, overwrite={overwrite_existing})"
        )

        try:
            for filename in slice_filenames:
                QApplication.processEvents()
                slice_path = os.path.join(folder_path, filename)
                proc_path = build_batch_proc_path(slice_path)

                if os.path.exists(proc_path) and not overwrite_existing:
                    skipped_count += 1
                    self.append_log(f"[INFO] Skipped existing proc: {proc_path}")
                    continue

                try:
                    metadata, _, _, parsed_data = self._load_slice_bundle(slice_path)
                    self._set_box_dimensions(self._resolve_box_dimensions(metadata))
                    processed_df = controller.process_parsed_data(
                        self._build_processing_config(parsed_data, metadata),
                        parsed_data,
                    )
                    processed_with_context = add_timeline_context_columns(
                        processed_df,
                        self._build_timeline_context(metadata),
                    )
                    save_proc_file(proc_path, processed_with_context)
                    processed_count += 1
                    self.append_log(f"[INFO] Batch saved: {proc_path}")
                except Exception as e:
                    failed_count += 1
                    self.append_log(f"[ERROR] Batch processing failed for {slice_path}: {e}")
        finally:
            config_app.BOX_DIMS = original_box_dims
            self._set_batch_controls_enabled(True)

        summary = (
            f"Batch complete: total={total_files}, processed={processed_count}, "
            f"skipped={skipped_count}, failed={failed_count}"
        )
        self.batch_summary_label.setText(summary)
        self.result_status_label.setText("Batch complete.")
        self.append_log(f"[INFO] {summary}")

    def save_processed_result(self):
        if self.current_processed_result is None or self.current_processed_result.empty:
            return

        default_name = build_proc_default_name(self.slice_path or "", self.current_processing_mode)
        filepath, _ = QFileDialog.getSaveFileName(
            self,
            "Save Processed Result",
            os.path.join(os.path.dirname(self.slice_path or ""), default_name),
            proc_file_filter(),
        )
        if not filepath:
            return

        try:
            save_proc_file(filepath, self.current_processed_result)
            self.current_proc_path = filepath
            self.proc_path_label.setText(filepath)
            self.append_log(f"[INFO] Processed result saved: {filepath}")
        except Exception as e:
            self.append_log(f"[ERROR] Failed to save processed result: {e}")
