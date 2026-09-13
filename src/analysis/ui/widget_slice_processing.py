import os

from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QDoubleValidator
from PySide6.QtWidgets import (
    QApplication,
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QLineEdit, QComboBox, QTextEdit, QGroupBox, QGridLayout, QFileDialog, QRadioButton, QCheckBox,
    QMessageBox, QSizePolicy, QStackedWidget, QScrollArea,
    QTableWidget, QTableWidgetItem, QHeaderView
)
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qtagg import NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure

from src.analysis.pipeline.artifact_io import (
    add_timeline_context_columns,
    build_batch_proc_path,
    build_proc_default_name,
    list_slice_files,
    proc_file_filter,
    read_slice_metadata,
    slice_file_filter,
    save_proc_file,
    update_slice_box_dimensions,
)
from src.analysis.pipeline.pipeline_controller import PipelineController
from src.analysis.ui.data_selection_dialog import DataSelectionDialog
from src.analysis.ui.dialog_processing_settings import ProcessingSettingsDialog
from src.analysis.ui.plot_manager import PlotManager
from src.config import config_app, config_analysis_ui
from src.config.data_columns import DisplayNames, PoseCols, RawMarkerCols, RigidBodyCols
from src.utils.qt_sections import CollapsibleSection, set_path_label


class WidgetSliceProcessing(QWidget):
    processing_requested = Signal(dict, object, object, object, dict)
    log_message = Signal(str)
    results_ready = Signal(list)

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
        self.batch_running = False
        self.single_running = False
        self.batch_input_paths = []
        self.batch_success_paths = []
        self.completed_processing_mode = None
        self._running_processing_mode = None
        self.manual_box_dimensions = None
        self.pipeline_controller_factory = PipelineController

        self._setup_ui()
        self._arrange_workflow()
        self._connect_signals()

    def _arrange_workflow(self):
        """Keep the next action visible; scroll only the optional settings."""
        outer = self.layout()
        row = QHBoxLayout()
        outer.addLayout(row)
        left = QWidget()
        left.setFixedWidth(296)
        controls = QVBoxLayout(left)
        controls.setContentsMargins(0, 0, 8, 0)
        self.input_mode_combo = QComboBox()
        self.input_mode_combo.addItems(['Single', 'Batch'])
        controls.addWidget(self.input_mode_combo)
        self.input_stack = QStackedWidget()
        single_input, batch_input = QWidget(), QWidget()
        single_layout, batch_layout = QVBoxLayout(single_input), QVBoxLayout(batch_input)
        for layout in (single_layout, batch_layout):
            layout.setContentsMargins(0, 0, 0, 0)
        self.load_slice_button.setText('Open slice...')
        self.select_slice_folder_button.setText('Open folder...')
        for widget in (self.load_slice_button, self.slice_path_label):
            single_layout.addWidget(widget)
        for widget in (self.select_slice_folder_button, self.batch_folder_label, self.overwrite_proc_checkbox):
            batch_layout.addWidget(widget)
        self.input_stack.addWidget(single_input)
        self.input_stack.addWidget(batch_input)
        self.input_stack.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)
        controls.addWidget(self.input_stack)

        method = QWidget()
        method_layout = QVBoxLayout(method)
        method_layout.setContentsMargins(0, 0, 0, 0)
        method_layout.addWidget(QLabel('Method'))
        choices = QHBoxLayout()
        for widget in (self.rb_processing_raw, self.rb_processing_standard, self.rb_processing_advanced):
            choices.addWidget(widget)
        method_layout.addLayout(choices)
        self.method_controls = method
        controls.addWidget(method)
        self.processing_mode_description.setFixedHeight(24)
        self.processing_mode_description.setWordWrap(False)
        controls.addWidget(self.processing_mode_description)

        settings = QWidget()
        settings_layout = QVBoxLayout(settings)
        settings_layout.setContentsMargins(0, 0, 4, 0)
        self.box_section = CollapsibleSection('Box dimensions', self.box_dims_group)
        self.details_section = CollapsibleSection('Input details', self.slice_summary_group)
        self.resampling_group.setMinimumWidth(0)
        self.resampling_group.setTitle('')
        self.resampling_section = CollapsibleSection('Resampling', self.resampling_group)
        self.processing_settings_button.setMinimumWidth(0)
        self.processing_settings_button.setText('Processing settings...')
        advanced = QWidget()
        advanced_layout = QVBoxLayout(advanced)
        advanced_layout.setContentsMargins(0, 0, 0, 0)
        advanced_layout.addWidget(self.processing_settings_button)
        self.advanced_section = CollapsibleSection('Advanced', advanced)
        self.log_output.setMinimumHeight(100)
        self.log_section = CollapsibleSection('Log', self.log_output)
        for section in (self.box_section, self.details_section, self.resampling_section,
                        self.advanced_section, self.log_section):
            settings_layout.addWidget(section)
        settings_layout.addStretch()
        self.settings_scroll = QScrollArea()
        self.settings_scroll.setWidgetResizable(True)
        self.settings_scroll.setFrameShape(QScrollArea.NoFrame)
        self.settings_scroll.setWidget(settings)
        controls.addWidget(self.settings_scroll, 1)

        self.action_stack = QStackedWidget()
        single_actions, batch_actions = QWidget(), QWidget()
        action_layout, batch_action_layout = QVBoxLayout(single_actions), QVBoxLayout(batch_actions)
        for layout in (action_layout, batch_action_layout):
            layout.setContentsMargins(0, 0, 0, 0)
        self.run_button.setText('Run')
        self.save_proc_button.setText('Save...')
        self.save_view_button = QPushButton('Save and View')
        self.save_view_button.setEnabled(False)
        action_layout.addWidget(self.result_status_label)
        action_layout.addWidget(self.proc_path_label)
        action_layout.addWidget(self.run_button)
        save_row = QHBoxLayout()
        save_row.addWidget(self.save_proc_button)
        save_row.addWidget(self.save_view_button)
        action_layout.addLayout(save_row)
        self.run_batch_button.setText('Run batch')
        self.view_batch_button = QPushButton('View Results')
        self.view_batch_button.setEnabled(False)
        for widget in (self.batch_summary_label, self.run_batch_button, self.view_batch_button):
            batch_action_layout.addWidget(widget)
        self.action_stack.addWidget(single_actions)
        self.action_stack.addWidget(batch_actions)
        self.action_stack.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)
        controls.addWidget(self.action_stack)
        row.addWidget(left)

        self.preview_stack = QStackedWidget()
        preview = QWidget()
        preview_layout = QVBoxLayout(preview)
        preview_layout.setContentsMargins(0, 0, 0, 0)
        plot_controls = QHBoxLayout()
        self.select_data_button.setText('Markers...')
        for widget in (self.select_data_button, self.combo_plot_axis, self.selected_data_label):
            plot_controls.addWidget(widget)
        preview_layout.addLayout(plot_controls)
        preview_layout.addWidget(self.toolbar)
        preview_layout.addWidget(self.canvas, 1)
        self.batch_table = QTableWidget(0, 2)
        self.batch_table.setHorizontalHeaderLabels(['Slice', 'Result'])
        self.batch_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.batch_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.batch_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.preview_stack.addWidget(preview)
        self.preview_stack.addWidget(self.batch_table)
        row.addWidget(self.preview_stack, 1)
        for label in (self.slice_path_label, self.slice_source_label, self.proc_path_label, self.batch_folder_label):
            set_path_label(label, '')
        for field in (self.le_box_l, self.le_box_w, self.le_box_h):
            field.clear()
        self.box_dims_warning.setText('No slice loaded.')
        self.input_mode_combo.currentIndexChanged.connect(self._set_input_mode)
        self.save_view_button.clicked.connect(self.save_and_view)
        self.view_batch_button.clicked.connect(lambda: self.results_ready.emit(self.batch_success_paths.copy()))
        self._update_processing_mode_ui()

    def _set_input_mode(self, index):
        self.input_stack.setCurrentIndex(index)
        self.action_stack.setCurrentIndex(index)
        self.preview_stack.setCurrentIndex(index)
        # These describe the retained single slice, never the whole batch.
        self.box_section.setVisible(index == 0)
        self.details_section.setVisible(index == 0)

    def _setup_ui(self):
        QVBoxLayout(self)
        self.fig = Figure(figsize=(5, 4), dpi=100)
        self.canvas = FigureCanvas(self.fig)
        self.toolbar = NavigationToolbar(self.canvas, self)
        self.plot_manager = PlotManager(self.canvas, self.fig)
        self.plot_manager.draw_plot(None, [])

        self.load_slice_button = QPushButton('Open slice...')
        self.slice_path_label = QLabel()
        self.slice_summary_group = QGroupBox()
        summary = QGridLayout(self.slice_summary_group)
        self.slice_source_label = QLabel()
        self.slice_user_range_label = QLabel('N/A')
        self.slice_padded_range_label = QLabel('N/A')
        self.slice_marker_correction_label = QLabel('None')
        for row, (title, label) in enumerate((('Source', self.slice_source_label),
                ('Range (s)', self.slice_user_range_label), ('Padded (s)', self.slice_padded_range_label),
                ('Corrections', self.slice_marker_correction_label))):
            label.setWordWrap(True)
            summary.addWidget(QLabel(title), row, 0)
            summary.addWidget(label, row, 1)

        self.box_dims_group = QGroupBox('mm')
        dimensions = QGridLayout(self.box_dims_group)
        self.le_box_l, self.le_box_w, self.le_box_h = QLineEdit(), QLineEdit(), QLineEdit()
        for row, (title, edit) in enumerate(zip(('L', 'W', 'H'), (self.le_box_l, self.le_box_w, self.le_box_h))):
            edit.setEnabled(False)
            dimensions.addWidget(QLabel(title), row, 0)
            dimensions.addWidget(edit, row, 1)
        self.box_dims_warning = QLabel('No slice loaded.')
        self.box_dims_warning.setWordWrap(True)
        dimensions.addWidget(self.box_dims_warning, 3, 0, 1, 2)
        self.save_box_dims_to_slice_checkbox = QCheckBox('Save dimensions to slice')
        self.save_box_dims_to_slice_checkbox.hide()
        dimensions.addWidget(self.save_box_dims_to_slice_checkbox, 4, 0, 1, 2)
        self.apply_box_dims_button = QPushButton('Apply dimensions')
        self.apply_box_dims_button.setEnabled(False)
        self.apply_box_dims_button.hide()
        dimensions.addWidget(self.apply_box_dims_button, 5, 0, 1, 2)

        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        self.select_data_button = QPushButton('Markers...')
        self.selected_data_label = QLabel('Selected: None')
        self.selected_data_label.setWordWrap(True)
        self.combo_plot_axis = QComboBox()
        for label, column in (('Position X', PoseCols.POS_X), ('Position Y', PoseCols.POS_Y), ('Position Z', PoseCols.POS_Z)):
            self.combo_plot_axis.addItem(label, column)

        self.resampling_group = QGroupBox()
        resampling = QGridLayout(self.resampling_group)
        self.cb_enable_resampling = QCheckBox('Resample results')
        self.cb_enable_resampling.setToolTip(config_analysis_ui.RESAMPLING_DESCRIPTION)
        resampling.addWidget(self.cb_enable_resampling, 0, 0, 1, 2)
        self.combo_resampling_factor = QComboBox()
        for label, factor in config_analysis_ui.RESAMPLING_FACTOR_CHOICES:
            self.combo_resampling_factor.addItem(label, factor)
        self.combo_resampling_factor.setEnabled(False)
        resampling.addWidget(QLabel('Factor'), 1, 0)
        resampling.addWidget(self.combo_resampling_factor, 1, 1)
        self.cb_limit_resampling_range = QCheckBox('Limit time range')
        self.cb_limit_resampling_range.setEnabled(False)
        resampling.addWidget(self.cb_limit_resampling_range, 2, 0, 1, 2)
        self.le_resampling_range_start, self.le_resampling_range_end = QLineEdit(), QLineEdit()
        for row, (title, edit) in enumerate((('Start (s)', self.le_resampling_range_start),
                                            ('End (s)', self.le_resampling_range_end)), 3):
            edit.setValidator(QDoubleValidator(self))
            edit.setEnabled(False)
            resampling.addWidget(QLabel(title), row, 0)
            resampling.addWidget(edit, row, 1)
        self.rb_processing_raw = QRadioButton(config_analysis_ui.PROCESSING_MODE_LABELS[config_analysis_ui.PROCESSING_MODE_RAW])
        self.rb_processing_standard = QRadioButton(config_analysis_ui.PROCESSING_MODE_LABELS[config_analysis_ui.PROCESSING_MODE_STANDARD])
        self.rb_processing_advanced = QRadioButton(config_analysis_ui.PROCESSING_MODE_LABELS[config_analysis_ui.PROCESSING_MODE_ADVANCED])
        self.rb_processing_raw.setChecked(self.current_processing_mode == config_analysis_ui.PROCESSING_MODE_RAW)
        self.rb_processing_standard.setChecked(self.current_processing_mode == config_analysis_ui.PROCESSING_MODE_STANDARD)
        self.rb_processing_advanced.setChecked(self.current_processing_mode == config_analysis_ui.PROCESSING_MODE_ADVANCED)
        self.processing_settings_button = QPushButton('Processing settings...')
        self.processing_mode_description = QLabel()
        self.result_status_label = QLabel('Not processed')
        self.result_status_label.setWordWrap(True)
        self.proc_path_label = QLabel()
        self.select_slice_folder_button = QPushButton('Open folder...')
        self.batch_folder_label = QLabel()
        self.overwrite_proc_checkbox = QCheckBox('Overwrite existing results')
        self.batch_summary_label = QLabel('No slices')
        self.batch_summary_label.setWordWrap(True)
        self.run_batch_button = QPushButton('Run batch')
        self.run_button = QPushButton('Run')
        self.run_button.setEnabled(False)
        self.save_proc_button = QPushButton('Save...')
        self.save_proc_button.setEnabled(False)

    def _connect_signals(self):
        self.load_slice_button.clicked.connect(self.open_slice_file)
        self.select_data_button.clicked.connect(self.open_data_selection_dialog)
        self.combo_plot_axis.currentIndexChanged.connect(self.update_plot)
        self.cb_enable_resampling.toggled.connect(self._update_resampling_controls_enabled)
        self.cb_enable_resampling.toggled.connect(self._update_processing_mode_ui)
        self.cb_limit_resampling_range.toggled.connect(self._update_resampling_controls_enabled)
        self.rb_processing_standard.toggled.connect(self._on_processing_mode_changed)
        self.rb_processing_raw.toggled.connect(self._on_processing_mode_changed)
        self.rb_processing_advanced.toggled.connect(self._on_processing_mode_changed)
        self.processing_settings_button.clicked.connect(self.open_processing_settings_dialog)
        self.apply_box_dims_button.clicked.connect(self.apply_manual_box_dimensions)
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
            self.slice_marker_correction_label.setText("None")
            return

        set_path_label(self.slice_source_label, self.slice_metadata.source)
        self.slice_user_range_label.setText(
            f"{self.slice_metadata.user_start:.3f}s ~ {self.slice_metadata.user_end:.3f}s"
        )
        self.slice_padded_range_label.setText(
            f"{self.slice_metadata.padded_start:.3f}s ~ {self.slice_metadata.padded_end:.3f}s"
        )
        reviewed_count = int(self.slice_metadata.correction_event_count or 0)
        approved_count = int(self.slice_metadata.correction_approved_event_count or 0)
        self.slice_marker_correction_label.setText(
            f"{reviewed_count} reviewed event(s), {approved_count} approved"
            if self.slice_metadata.correction_schema_version
            else "None"
        )
        self._set_default_resampling_range()

    def _set_default_resampling_range(self, metadata=None):
        metadata = self.slice_metadata if metadata is None else metadata
        if metadata is not None:
            start = metadata.user_start
            end = metadata.user_end
        elif self.parsed_data is not None and not self.parsed_data.empty:
            start = float(self.parsed_data.index.min())
            end = float(self.parsed_data.index.max())
        else:
            start = None
            end = None

        if start is not None and end is not None:
            self.le_resampling_range_start.setText(f"{float(start):.3f}")
            self.le_resampling_range_end.setText(f"{float(end):.3f}")

    def _update_resampling_controls_enabled(self):
        resampling_enabled = self.cb_enable_resampling.isChecked()
        range_enabled = resampling_enabled and self.cb_limit_resampling_range.isChecked()
        self.combo_resampling_factor.setEnabled(resampling_enabled)
        self.cb_limit_resampling_range.setEnabled(resampling_enabled)
        self.le_resampling_range_start.setEnabled(range_enabled)
        self.le_resampling_range_end.setEnabled(range_enabled)

    def _get_resampling_range_values(self, parsed_data, metadata=None) -> tuple[float | None, float | None]:
        if not (self.cb_enable_resampling.isChecked() and self.cb_limit_resampling_range.isChecked()):
            return None, None

        try:
            range_start = float(self.le_resampling_range_start.text())
            range_end = float(self.le_resampling_range_end.text())
        except ValueError:
            raise ValueError("Enter numeric resampling range start/end times.")

        metadata = self.slice_metadata if metadata is None else metadata
        slice_start = metadata.user_start if metadata else float(parsed_data.index.min())
        slice_end = metadata.user_end if metadata else float(parsed_data.index.max())
        if range_start >= range_end:
            raise ValueError("Result resampling range start must be smaller than end.")
        if range_start < float(slice_start) or range_end > float(slice_end):
            raise ValueError("Result resampling range must stay inside the slice user range.")
        return range_start, range_end

    def _metadata_has_box_dimensions(self, metadata) -> bool:
        return (
            metadata is not None
            and metadata.box_l is not None
            and metadata.box_w is not None
            and metadata.box_h is not None
        )

    def _box_dimensions_from_metadata(self, metadata) -> tuple[float, float, float]:
        if not self._metadata_has_box_dimensions(metadata):
            raise ValueError("Missing box dimensions in slice metadata.")
        box_dims = (float(metadata.box_l), float(metadata.box_w), float(metadata.box_h))
        if any(value <= 0 for value in box_dims):
            raise ValueError("Box dimensions in slice metadata must be positive values.")
        return box_dims

    def _set_box_dimension_inputs_enabled(self, enabled: bool):
        self.le_box_l.setEnabled(enabled)
        self.le_box_w.setEnabled(enabled)
        self.le_box_h.setEnabled(enabled)

    def _reset_box_dimension_state(self):
        self.manual_box_dimensions = None
        self._set_box_dimension_inputs_enabled(False)
        self.apply_box_dims_button.setEnabled(False)
        self.apply_box_dims_button.setVisible(False)
        self.save_box_dims_to_slice_checkbox.setChecked(False)
        self.save_box_dims_to_slice_checkbox.setVisible(False)
        self.box_dims_warning.setText(
            "From slice."
        )
        self.box_dims_warning.setStyleSheet("color: #666666;")

    def _enter_missing_box_dimension_mode(self):
        self.manual_box_dimensions = None
        self._set_box_dimension_inputs_enabled(True)
        self.apply_box_dims_button.setEnabled(True)
        self.apply_box_dims_button.setVisible(True)
        self.save_box_dims_to_slice_checkbox.setVisible(True)
        self.box_dims_warning.setText(
            "Enter missing dimensions."
        )
        self.box_dims_warning.setStyleSheet("color: #b45309;")
        self.run_button.setEnabled(False)
        self.box_section.setExpanded(True)

    def _read_box_dimensions_from_inputs(self) -> tuple[float, float, float]:
        try:
            box_dims = (
                float(self.le_box_l.text()),
                float(self.le_box_w.text()),
                float(self.le_box_h.text()),
            )
        except ValueError:
            raise ValueError("Enter numeric box dimensions for L, W, and H.")
        if any(value <= 0 for value in box_dims):
            raise ValueError("Box dimensions must be positive values.")
        return box_dims

    def _apply_box_dims_from_metadata(self, metadata=None):
        metadata = self.slice_metadata if metadata is None else metadata
        if metadata is None:
            return

        if self._metadata_has_box_dimensions(metadata):
            self.le_box_l.setText(f"{metadata.box_l:g}")
            self.le_box_w.setText(f"{metadata.box_w:g}")
            self.le_box_h.setText(f"{metadata.box_h:g}")
            return

        self.le_box_l.setText("" if metadata.box_l is None else f"{metadata.box_l:g}")
        self.le_box_w.setText("" if metadata.box_w is None else f"{metadata.box_w:g}")
        self.le_box_h.setText("" if metadata.box_h is None else f"{metadata.box_h:g}")

    def apply_manual_box_dimensions(self):
        try:
            box_dims = self._read_box_dimensions_from_inputs()
            from src.utils.artifact_metadata import validate_declared_dimensions
            validate_declared_dimensions(self.slice_metadata.artifact_metadata_json if self.slice_metadata else None, box_dims)
            if self.save_box_dims_to_slice_checkbox.isChecked():
                if not self.slice_path:
                    raise ValueError("No slice file is loaded.")
                self.slice_metadata = update_slice_box_dimensions(self.slice_path, box_dims)
                self._apply_box_dims_from_metadata(self.slice_metadata)
                self.append_log(
                    "[INFO] Box dimensions saved to slice metadata: "
                    f"L={box_dims[0]:g}, W={box_dims[1]:g}, H={box_dims[2]:g}"
                )
            else:
                self.manual_box_dimensions = box_dims
                self.append_log(
                    "[INFO] Box dimensions applied for this processing session: "
                    f"L={box_dims[0]:g}, W={box_dims[1]:g}, H={box_dims[2]:g}"
                )

            self._set_box_dimension_inputs_enabled(False)
            self.apply_box_dims_button.setEnabled(False)
            self.apply_box_dims_button.setVisible(False)
            self.save_box_dims_to_slice_checkbox.setVisible(False)
            self.box_dims_warning.setText(
                "Ready."
            )
            self.box_dims_warning.setStyleSheet("color: #666666;")
            self.run_button.setEnabled(self.parsed_data is not None)
        except Exception as e:
            QMessageBox.warning(self, "Box Dimensions Required", str(e))
            self.append_log(f"[ERROR] Invalid box dimensions: {e}")

    def _load_slice_bundle(self, filepath: str):
        metadata = read_slice_metadata(filepath)
        header_info, raw_data = self.data_loader.load_csv(filepath)
        parsed_data = self.parser.process(header_info, raw_data)
        return metadata, header_info, raw_data, parsed_data

    def open_slice_file(self):
        filepath, _ = QFileDialog.getOpenFileName(self, "Select Slice File", "", slice_file_filter())
        if filepath:
            self.load_slice_file(filepath)

    def prepare_for_input_change(self, replace_single=True):
        if self.single_running or self.batch_running:
            self.append_log('[ERROR] Wait for processing to finish.')
            return False
        if (replace_single and self.current_processed_result is not None
                and not self.current_processed_result.empty and not self.current_proc_path):
            choice = QMessageBox.question(self, 'Unsaved result', 'Save the current result?',
                QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel, QMessageBox.Save)
            if choice == QMessageBox.Cancel:
                return False
            if choice == QMessageBox.Save:
                return bool(self.save_processed_result())
        return True

    def load_processing_inputs(self, paths, confirm=True):
        paths = list(dict.fromkeys(os.path.abspath(os.fspath(path)) for path in paths))
        if not paths or any(not os.path.isfile(path) for path in paths):
            self.append_log('[ERROR] Choose existing slice files.')
            return False
        if confirm and not self.prepare_for_input_change(replace_single=len(paths) == 1):
            return False
        if self.single_running or self.batch_running:
            return False
        if len(paths) == 1:
            return self.load_slice_file(paths[0], confirm=False)
        self._activate_batch_inputs(paths)
        return True

    def _activate_batch_inputs(self, paths):
        self.batch_input_paths = paths
        self.batch_slice_folder = os.path.dirname(paths[0]) if paths else self.batch_slice_folder
        self.batch_success_paths = []
        set_path_label(self.batch_folder_label, self.batch_slice_folder)
        self._populate_batch_table()
        self.batch_summary_label.setText(f'{len(paths)} slices ready')
        self.view_batch_button.setEnabled(False)
        self.input_mode_combo.setCurrentIndex(1)

    def _populate_batch_table(self):
        self.batch_table.setRowCount(len(self.batch_input_paths))
        for index, path in enumerate(self.batch_input_paths):
            item = QTableWidgetItem(os.path.basename(path))
            item.setToolTip(path)
            item.setData(Qt.UserRole, path)
            self.batch_table.setItem(index, 0, item)
            self.batch_table.setItem(index, 1, QTableWidgetItem('Ready'))

    def load_slice_file(self, filepath: str, confirm=True):
        if not filepath or (confirm and not self.prepare_for_input_change()):
            return False
        if self.single_running or self.batch_running:
            return False
        try:
            candidate = self._load_slice_bundle(filepath)
            all_targets = self.data_loader.get_plottable_targets(candidate[3])
        except Exception as e:
            self.append_log(f"[ERROR] Failed to load slice file: {e}")
            return False
        previous = self._capture_single_context()
        try:
            self._reset_box_dimension_state()
            self.slice_metadata, self.header_info, self.raw_data, self.parsed_data = candidate
            self.slice_path = os.path.abspath(filepath)
            set_path_label(self.slice_path_label, self.slice_path)
            self._set_slice_summary()
            self._apply_box_dims_from_metadata()
            self.current_proc_path = None
            self.current_processed_result = None
            self.completed_processing_mode = None
            self.proc_path_label.setText("Not saved yet.")
            self.result_status_label.setText("Ready to process.")
            self.save_proc_button.setEnabled(False)
            self.save_view_button.setEnabled(False)
            self.run_button.setEnabled(self._metadata_has_box_dimensions(self.slice_metadata))

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
            if self._metadata_has_box_dimensions(self.slice_metadata):
                self.append_log(
                    "[INFO] Box dimensions restored from slice metadata: "
                    f"L={self.slice_metadata.box_l:g}, "
                    f"W={self.slice_metadata.box_w:g}, "
                    f"H={self.slice_metadata.box_h:g}"
                )
            else:
                self._enter_missing_box_dimension_mode()
                self.append_log("[WARNING] Box dimensions are missing from slice metadata.")
                QMessageBox.warning(
                    self,
                    "Box Dimensions Required",
                    "Enter the missing box dimensions to run.",
                )
            self.append_log("[INFO] Slice parsed and ready for processing.")
            self.input_mode_combo.setCurrentIndex(0)
            return True
        except Exception as e:
            self._restore_single_context(previous)
            self.append_log(f"[ERROR] Failed to load slice file: {e}")
            return False

    def _capture_single_context(self):
        attributes = ('slice_metadata', 'header_info', 'raw_data', 'parsed_data', 'slice_path',
                      'current_selected_targets', 'current_proc_path', 'current_processed_result',
                      'completed_processing_mode', 'manual_box_dimensions')
        labels = (self.slice_path_label, self.slice_source_label, self.slice_user_range_label,
                  self.slice_padded_range_label, self.slice_marker_correction_label, self.proc_path_label,
                  self.result_status_label, self.selected_data_label, self.box_dims_warning)
        edits = (self.le_box_l, self.le_box_w, self.le_box_h,
                 self.le_resampling_range_start, self.le_resampling_range_end)
        controls = (*edits, self.apply_box_dims_button, self.save_box_dims_to_slice_checkbox,
                    self.run_button, self.save_proc_button, self.save_view_button)
        return {
            'attributes': {name: getattr(self, name) for name in attributes},
            'labels': [(label, label.text(), label.toolTip(), label.property('fullPath')) for label in labels],
            'edits': [(edit, edit.text()) for edit in edits],
            'controls': [(control, control.isEnabled(), control.isHidden()) for control in controls],
            'save_dims': self.save_box_dims_to_slice_checkbox.isChecked(),
            'box_expanded': self.box_section.button.isChecked(),
            'limits': (self.plot_manager.ax.get_xlim(), self.plot_manager.ax.get_ylim()),
        }

    def _restore_single_context(self, previous):
        for name, value in previous['attributes'].items():
            setattr(self, name, value)
        for label, text, tooltip, full_path in previous['labels']:
            label.setText(text)
            label.setToolTip(tooltip)
            label.setProperty('fullPath', full_path)
        for edit, text in previous['edits']:
            edit.setText(text)
        self.save_box_dims_to_slice_checkbox.setChecked(previous['save_dims'])
        self.box_section.setExpanded(previous['box_expanded'])
        for control, enabled, hidden in previous['controls']:
            control.setEnabled(enabled)
            control.setHidden(hidden)
        self.update_plot()
        self.plot_manager.ax.set_xlim(previous['limits'][0])
        self.plot_manager.ax.set_ylim(previous['limits'][1])
        self.canvas.draw_idle()

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
            'Resampling on' if self.cb_enable_resampling.isChecked() else 'Original sampling'
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

    def _resolve_box_dimensions(self, metadata=None) -> tuple[float, float, float]:
        metadata = self.slice_metadata if metadata is None else metadata
        if self._metadata_has_box_dimensions(metadata):
            return self._box_dimensions_from_metadata(metadata)
        if self.manual_box_dimensions is not None:
            return self.manual_box_dimensions
        raise ValueError(
            "Box dimensions are missing. Apply manual dimensions or save a new .slice file from Step 1."
        )

    def _build_timeline_context(self, metadata=None) -> dict:
        metadata = self.slice_metadata if metadata is None else metadata
        full_start = None if metadata is None else metadata.full_start
        full_end = None if metadata is None else metadata.full_end
        slice_start = None if metadata is None else metadata.user_start
        slice_end = None if metadata is None else metadata.user_end
        context = {
            "artifact_metadata": None if metadata is None else metadata.artifact_metadata_json,
            "full_start_sec": full_start,
            "full_end_sec": full_end,
            "slice_start_sec": slice_start,
            "slice_end_sec": slice_end,
            "scene_review_json": "" if metadata is None else metadata.scene_review_json,
        }
        if metadata is not None and metadata.correction_schema_version:
            context.update(
                {
                    "marker_correction_schema_version": metadata.correction_schema_version,
                    "marker_correction_context_json": metadata.correction_context_json,
                    "marker_correction_algorithm_version": (
                        metadata.correction_algorithm_version
                    ),
                    "marker_correction_original_source": metadata.correction_original_source,
                    "marker_correction_original_source_sha256": (
                        metadata.correction_original_source_sha256
                    ),
                    "marker_correction_reviewed_source": (
                        metadata.correction_reviewed_source or metadata.source
                    ),
                    "marker_correction_event_count": metadata.correction_event_count,
                    "marker_correction_approved_event_count": (
                        metadata.correction_approved_event_count
                    ),
                    "marker_correction_events_json": metadata.correction_events_json,
                }
            )
        return context

    def _build_processing_config(self, parsed_data, metadata=None, box_dims=None) -> dict:
        metadata = self.slice_metadata if metadata is None else metadata
        range_start, range_end = self._get_resampling_range_values(parsed_data, metadata)
        resolved_box_dims = self._resolve_box_dimensions(metadata) if box_dims is None else box_dims
        from src.utils.artifact_metadata import normalize_metadata, DIMENSIONS
        declared = normalize_metadata(metadata.artifact_metadata_json if metadata else None)
        for field, value in zip(DIMENSIONS, resolved_box_dims):
            if declared[field] is not None and declared[field] != float(value):
                raise ValueError(f'Processing dimensions conflict with declared artifact {field}.')
        return {
            "slice_filter_by": "time",
            "slice_start_val": (
                metadata.user_start if metadata else float(parsed_data.index.min())
            ),
            "slice_end_val": (
                metadata.user_end if metadata else float(parsed_data.index.max())
            ),
            "enable_result_resampling": self.cb_enable_resampling.isChecked(),
            "result_resampling_factor": self.combo_resampling_factor.currentData(),
            "result_resampling_method": "linear",
            "limit_result_resampling_to_range": (
                self.cb_enable_resampling.isChecked()
                and self.cb_limit_resampling_range.isChecked()
            ),
            "result_resampling_range_start": range_start,
            "result_resampling_range_end": range_end,
            "processing_mode": self.current_processing_mode,
            "analysis_options": self._build_analysis_overrides(),
            "box_dimensions": tuple(float(value) for value in resolved_box_dims),
        }

    def emit_run_processing(self):
        if self.parsed_data is None or self.single_running or self.batch_running:
            return
        try:
            config = self._build_processing_config(self.parsed_data, self.slice_metadata)
            self.single_running = True
            self._running_processing_mode = self.current_processing_mode
            self._set_batch_controls_enabled(False)
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
            self.single_running = False
            self._set_batch_controls_enabled(True)
            self.append_log(f"[ERROR] Invalid processing configuration: {e}")

    def on_processing_finished(self, processed_df):
        self.single_running = False
        self._set_batch_controls_enabled(True)
        self.run_button.setEnabled(True)
        self.current_processed_result = processed_df
        self.completed_processing_mode = self._running_processing_mode or self.current_processing_mode
        if processed_df is not None and not processed_df.empty:
            self.result_status_label.setText("Processed result ready.")
            self.save_proc_button.setEnabled(True)
            self.save_view_button.setEnabled(True)
            self.append_log("[INFO] Processing completed successfully.")
            self.append_log("[INFO] Save the processed result as a .proc file for Step 2 analysis.")
        else:
            self.result_status_label.setText("Processing failed.")
            self.save_proc_button.setEnabled(False)
            self.save_view_button.setEnabled(False)
            self.append_log("[ERROR] Processing failed.")

    def on_processing_failed(self):
        self.single_running = False
        self._set_batch_controls_enabled(True)
        self.run_button.setEnabled(True)
        self.result_status_label.setText("Processing failed.")
        self.save_proc_button.setEnabled(False)
        self.save_view_button.setEnabled(False)

    def select_slice_folder(self):
        if not self.prepare_for_input_change(replace_single=False):
            return
        folder_path = QFileDialog.getExistingDirectory(self, "Select Slice Folder")
        if not folder_path:
            return

        try:
            paths = [os.path.join(folder_path, name) for name in list_slice_files(folder_path)]
        except OSError as error:
            self.append_log(f'[ERROR] Could not read folder: {error}')
            return
        self.batch_slice_folder = folder_path
        self._activate_batch_inputs(paths)
        self.append_log(f"[INFO] Selected slice folder for batch processing: {folder_path}")

    def _set_batch_controls_enabled(self, enabled: bool):
        self.select_slice_folder_button.setEnabled(enabled)
        self.run_batch_button.setEnabled(enabled)
        self.load_slice_button.setEnabled(enabled)
        self.run_button.setEnabled(enabled and self.parsed_data is not None
                                   and (self._metadata_has_box_dimensions(self.slice_metadata)
                                        or self.manual_box_dimensions is not None))
        for widget in (self.input_mode_combo, self.method_controls, self.settings_scroll,
                       self.overwrite_proc_checkbox):
            widget.setEnabled(enabled)
        self.save_proc_button.setEnabled(enabled and self.current_processed_result is not None)
        self.save_view_button.setEnabled(enabled and self.current_processed_result is not None)
        self.view_batch_button.setEnabled(enabled and bool(self.batch_success_paths))

    def run_batch_processing(self):
        if self.single_running or self.batch_running:
            return
        folder_path = self.batch_slice_folder
        if not folder_path:
            self.append_log("[ERROR] Select a slice folder before running batch processing.")
            return

        try:
            paths = self.batch_input_paths.copy() if self.batch_input_paths else [
                os.path.join(folder_path, name) for name in list_slice_files(folder_path)]
        except Exception as e:
            self.append_log(f"[ERROR] Failed to read slice folder: {e}")
            return

        if not paths:
            self.batch_summary_label.setText("No .slice files found.")
            self.append_log(f"[ERROR] No .slice files found in {folder_path}")
            return

        controller = self.pipeline_controller_factory()
        controller.log_message.connect(self.append_log)
        overwrite_existing = self.overwrite_proc_checkbox.isChecked()
        total_files = len(paths)
        processed_count = 0
        skipped_count = 0
        failed_count = 0
        original_box_dims = config_app.BOX_DIMS.copy()
        original_local_box_corners = config_app.LOCAL_BOX_CORNERS.copy()

        self.batch_running = True
        try:
            self.batch_input_paths = paths
            self.batch_success_paths = []
            self._populate_batch_table()
            self._set_batch_controls_enabled(False)
            self.batch_summary_label.setText("Running...")
            self.append_log(
                f"[INFO] Starting batch processing in {folder_path} "
                f"(total={total_files}, overwrite={overwrite_existing})"
            )

            for row_index, slice_path in enumerate(paths):
                QApplication.processEvents()
                proc_path = build_batch_proc_path(slice_path)

                if os.path.exists(proc_path) and not overwrite_existing:
                    skipped_count += 1
                    self.append_log(f"[INFO] Skipped existing proc: {proc_path}")
                    self.batch_table.item(row_index, 1).setText('Already exists')
                    continue

                try:
                    metadata, _, _, parsed_data = self._load_slice_bundle(slice_path)
                    box_dims = self._box_dimensions_from_metadata(metadata)
                    processed_df = controller.process_parsed_data(
                        self._build_processing_config(parsed_data, metadata, box_dims=box_dims),
                        parsed_data,
                    )
                    processed_with_context = add_timeline_context_columns(
                        processed_df,
                        self._build_timeline_context(metadata),
                    )
                    save_proc_file(proc_path, processed_with_context)
                    processed_count += 1
                    self.batch_success_paths.append(os.path.abspath(proc_path))
                    self.batch_table.item(row_index, 1).setText('Saved')
                    self.batch_table.item(row_index, 1).setToolTip(proc_path)
                    self.append_log(f"[INFO] Batch saved: {proc_path}")
                except Exception as e:
                    failed_count += 1
                    self.batch_table.item(row_index, 1).setText('Failed')
                    self.batch_table.item(row_index, 1).setToolTip(str(e))
                    self.append_log(f"[ERROR] Batch processing failed for {slice_path}: {e}")

            summary = (
                f"Batch complete: total={total_files}, processed={processed_count}, "
                f"skipped={skipped_count}, failed={failed_count}"
            )
            self.batch_summary_label.setText(f'{processed_count} saved, {failed_count} failed, {skipped_count} skipped')
            self.append_log(f"[INFO] {summary}")
        finally:
            config_app.BOX_DIMS = original_box_dims
            config_app.LOCAL_BOX_CORNERS = original_local_box_corners
            self._set_batch_controls_enabled(True)
            self.batch_running = False

    def save_processed_result(self):
        if self.current_processed_result is None or self.current_processed_result.empty:
            return None

        default_name = build_proc_default_name(self.slice_path or "", self.completed_processing_mode or self.current_processing_mode)
        filepath, _ = QFileDialog.getSaveFileName(
            self,
            "Save Processed Result",
            os.path.join(os.path.dirname(self.slice_path or ""), default_name),
            proc_file_filter(),
        )
        if not filepath:
            return None

        try:
            save_proc_file(filepath, self.current_processed_result)
            self.current_proc_path = os.path.abspath(filepath)
            set_path_label(self.proc_path_label, self.current_proc_path)
            self.append_log(f"[INFO] Processed result saved: {filepath}")
            return self.current_proc_path
        except Exception as e:
            self.append_log(f"[ERROR] Failed to save processed result: {e}")
            return None

    def save_and_view(self):
        path = self.current_proc_path or self.save_processed_result()
        if path:
            self.results_ready.emit([path])
