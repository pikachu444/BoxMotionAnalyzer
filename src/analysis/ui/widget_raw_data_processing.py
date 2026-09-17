import os
import json
import math
from dataclasses import asdict
from copy import deepcopy
from pathlib import Path
from PySide6.QtCore import Signal, Qt, QThread, QTimer
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QLineEdit, QComboBox, QTextEdit, QGroupBox, QGridLayout, QFileDialog,
    QDialog, QMessageBox, QSizePolicy, QSplitter, QScrollArea, QCheckBox, QProgressBar
)
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qtagg import NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure

from src.analysis.ui.plot_manager import PlotManager
from src.utils.qt_sections import CollapsibleSection, set_path_label
from src.analysis.ui.widget_scene_review import SceneReviewWidget
from src.analysis.ui.scene_review_flow import SceneReviewFlow
from src.analysis.ui.data_selection_dialog import DataSelectionDialog
from src.analysis.ui.dialog_marker_flip_review import MarkerFlipReviewDialog
from src.config import config_app, config_analysis_ui
from src.config.data_columns import (
    PoseCols, RawMarkerCols, DisplayNames, RigidBodyCols
)
from src.analysis.pipeline.artifact_io import (
    DEFAULT_SLICE_PADDING_ROWS,
    build_corrected_source_default_name,
    build_slice_default_name,
    corrected_source_file_filter,
    raw_csv_file_filter,
    save_corrected_source_file,
    save_slice_file,
    slice_file_filter,
    try_read_corrected_source_metadata,
    _sha256_file,
)
from src.analysis.pipeline.marker_flip import (
    MarkerCorrectionDecision,
    MarkerFlipAnalyzer,
    apply_approved_marker_permutations,
    normalize_marker_corrections,
    undo_approved_marker_permutations,
)
from src.analysis.pipeline.pose_optimizer import PoseOptimizer
from src.analysis.pipeline.face_assignment import (
    FaceAssignmentAnalyzer, materialize_face_assignments, marker_face, FACE_ASSIGNMENT_ALGORITHM_VERSION,
)
from src.analysis.pipeline.marker_review import (
    REVIEW_VERSION, canonical_key, copy_observations, file_digest, review_observations, analyzer_configuration,
)


class MarkerReviewWorker(QThread):
    completed = Signal(object)
    failed = Signal(str)
    progress = Signal(str, int, int)
    cancelled = Signal()

    def __init__(self, data, dims, optimizer_factory, analyzer_factory, parent=None, *, identity=None,
                 source_path=None, source_sha256=None):
        super().__init__(parent)
        # Pin the loaded stream; UI mutations replace it and invalidate the run.
        # The cancellable owned copy is prepared off the GUI thread in run().
        self.data, self.dims = data, tuple(dims)
        self.optimizer_factory, self.analyzer_factory = optimizer_factory, analyzer_factory
        self.identity = identity
        self.source_path, self.source_sha256 = source_path, source_sha256
        self.result, self.error = None, None
        self.cache = None
        self.cancel_requested = False
        self.pending_confirmation = None
        self.verified_signature = None

    @staticmethod
    def source_signature(path):
        stat = os.stat(path)
        return stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns, stat.st_ino

    def verify_source(self):
        if not self.source_path:
            return
        self.progress.emit('Validating source', 0, 0)
        before = self.source_signature(self.source_path)
        digest = file_digest(self.source_path, self.isInterruptionRequested)
        after = self.source_signature(self.source_path)
        if digest != self.source_sha256 or before != after:
            raise ValueError('Capture changed since loading. Reload it before review.')
        self.verified_signature = after

    def run(self):
        try:
            check = self.isInterruptionRequested
            self.verify_source()
            if self.pending_confirmation is not None:
                if check():
                    raise InterruptedError('Marker review cancelled.')
                self.result = self.pending_confirmation
                return
            data, digest = copy_observations(self.data, check, self.progress.emit)
            analyzer = self.analyzer_factory()
            cache_key = canonical_key({'identity': self.identity, 'observations': digest,
                                       'dims': self.dims, 'configuration': analyzer_configuration(analyzer)})
            if self.optimizer_factory is PoseOptimizer and self.cache and self.cache.get('key') == cache_key:
                result = deepcopy(self.cache['result'])
                result['statistics'] = {'cache_hit': True, 'whole_input_pose_passes': 0,
                    'process_calls': [], 'nonlinear_fits': 0, 'iterations': 0, 'evaluations': 0,
                    'frame_fit_budget': 0}
            else:
                result = review_observations(data, self.dims, optimizer_factory=self.optimizer_factory,
                    analyzer_factory=lambda: analyzer, cancelled=check, progress=self.progress.emit,
                    identity={'request': self.identity, 'observations': digest})
            result['cache_key'] = cache_key
            self.verify_source()
            if check():
                raise InterruptedError('Marker review cancelled.')
            self.result = result
            self.completed.emit(result)
        except InterruptedError:
            self.cancelled.emit()
        except Exception as exc:
            self.error = str(exc)
            self.failed.emit(str(exc))


class WidgetRawDataProcessing(SceneReviewFlow, QWidget):
    # Signals to communicate with MainApp
    file_loaded = Signal(dict, object, object) # header_info, raw_data, parsed_data
    log_message = Signal(str)
    slice_saved = Signal(str)
    process_requested = Signal()

    def __init__(self, data_loader, parser):
        super().__init__()
        self.data_loader = data_loader
        self.parser = parser
        
        self.raw_data = None
        self.header_info = None
        self.parsed_data = None
        self.source_path = None
        self.last_saved_slice_path = None
        self.original_source_reference = None
        self.original_source_sha256 = ""
        self.review_raw_data = None
        self.review_header_info = None
        self.review_parsed_data = None
        self.current_selected_targets = []
        self.marker_flip_candidates = []
        self.marker_correction_decisions: list[MarkerCorrectionDecision] = []
        self.correction_source_metadata = None
        self.marker_review_dirty = False
        self.marker_flip_analyzer_factory = FaceAssignmentAnalyzer
        self.review_context_json = ""
        self.active_source_sha256 = ""
        self.review_worker = None
        self.marker_review_busy = False
        self._source_revision = 0
        self._review_invalidated = False
        self._confirmed_dimensions = None
        self._last_review_dimensions = None
        self._close_after_review = False
        self.last_review_statistics = None
        self._review_cache = None
        self.marker_flip_dialog_factory = MarkerFlipReviewDialog
        self.pose_optimizer_factory = PoseOptimizer
        self._init_scene_state()

        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        group_box = QGroupBox("Capture")
        group_layout = QVBoxLayout(group_box)

        main_splitter = QSplitter(Qt.Orientation.Vertical)
        main_splitter.setChildrenCollapsible(False)

        # 1a. Top Layout: Plot and Right Panel
        top_splitter = QSplitter(Qt.Orientation.Horizontal)
        top_splitter.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        # Plot Container
        plot_container = QWidget()
        plot_layout = QVBoxLayout(plot_container)
        plot_layout.setContentsMargins(0, 0, 0, 0)
        
        self.fig = Figure(figsize=(5, 4), dpi=100)
        self.canvas = FigureCanvas(self.fig)
        self.toolbar = NavigationToolbar(self.canvas, self)

        plot_layout.addWidget(self.toolbar)
        plot_layout.addWidget(self.canvas)
        plot_container.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        self.plot_manager = PlotManager(self.canvas, self.fig)
        self.plot_manager.ax.text(0.5, 0.5, "Load a CSV file to start.", ha='center', va='center')
        self.plot_manager.canvas.draw()
        top_splitter.addWidget(plot_container)

        # Right Panel
        right_panel = QWidget()
        right_panel_layout = QVBoxLayout()
        right_panel.setLayout(right_panel_layout)
        self.load_csv_button = QPushButton("Open capture...")
        self.file_path_label = QLabel("No file selected.")
        self.file_path_label.setWordWrap(True)
        self.file_path_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        
        right_panel_layout.addWidget(self.load_csv_button)
        right_panel_layout.addWidget(self.file_path_label)

        # Box Dimensions
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
        self.box_section = CollapsibleSection('Box dimensions', self.box_dims_group)

        self.marker_review_group = QGroupBox()
        marker_review_layout = QVBoxLayout(self.marker_review_group)
        self.marker_review_summary_label = QLabel("Not reviewed")
        self.marker_review_summary_label.setWordWrap(True)
        marker_review_layout.addWidget(self.marker_review_summary_label)
        self.marker_review_source_label = QLabel("Source: original")
        self.marker_review_source_label.setWordWrap(True)
        self.marker_review_source_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        marker_review_layout.addWidget(self.marker_review_source_label)
        self.confirm_review_dimensions = QCheckBox('Confirm dimensions for this capture')
        marker_review_layout.addWidget(self.confirm_review_dimensions)
        marker_review_button_row = QHBoxLayout()
        self.review_marker_flips_button = QPushButton("Review")
        self.review_marker_flips_button.setEnabled(False)
        self.save_corrected_source_button = QPushButton("Save corrected")
        self.save_corrected_source_button.setEnabled(False)
        marker_review_button_row.addWidget(self.review_marker_flips_button)
        marker_review_button_row.addWidget(self.save_corrected_source_button)
        marker_review_layout.addLayout(marker_review_button_row)
        progress_row = QHBoxLayout()
        self.marker_review_progress = QProgressBar()
        self.cancel_marker_review_button = QPushButton('Cancel')
        progress_row.addWidget(self.marker_review_progress, 1)
        progress_row.addWidget(self.cancel_marker_review_button)
        marker_review_layout.addLayout(progress_row)
        self.marker_review_progress.hide()
        self.cancel_marker_review_button.hide()
        self.marker_review_section = CollapsibleSection('Marker correction', self.marker_review_group)

        # Log Output (Local to this widget for immediate feedback, or shared?)
        # The plan says "Encapsulates...". MainApp has a log output. 
        # But OriginalAnalysisWidget needs to show logs too?
        # In the original UI, the log output was in the right panel of Original Analysis.
        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setPlaceholderText("[INFO] Load a CSV file to start.")
        self.log_output.setMinimumHeight(100)
        self.log_section = CollapsibleSection('Log', self.log_output)
        details = QWidget()
        details_layout = QVBoxLayout(details)
        details_layout.setContentsMargins(0, 0, 0, 0)
        for section in (self.box_section, self.marker_review_section, self.log_section):
            details_layout.addWidget(section)
        details_layout.addStretch()
        details_scroll = QScrollArea()
        details_scroll.setWidgetResizable(True)
        details_scroll.setFrameShape(QScrollArea.NoFrame)
        details_scroll.setWidget(details)
        right_panel_layout.addWidget(details_scroll)
        right_panel.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)

        top_splitter.addWidget(right_panel)
        top_splitter.setChildrenCollapsible(False)
        top_splitter.setStretchFactor(0, 5)
        top_splitter.setStretchFactor(1, 2)
        top_splitter.setSizes([900, 280])
        main_splitter.addWidget(top_splitter)
        self.scene_panel = SceneReviewWidget(self)
        main_splitter.addWidget(self.scene_panel)

        # 1b. Bottom Controls
        controls_widget = QWidget()
        h_controls_layout = QHBoxLayout(controls_widget)
        controls_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        controls_widget.setMinimumHeight(110)

        # Plot Options
        plot_options_group = QGroupBox("Plot Options")
        plot_options_layout = QVBoxLayout(plot_options_group)
        plot_options_top_row = QHBoxLayout()
        self.select_data_button = QPushButton("Markers...")
        self.selected_data_label = QLabel("Selected: None")
        self.selected_data_label.setWordWrap(True)

        plot_options_top_row.addWidget(self.select_data_button)
        plot_options_top_row.addWidget(self.selected_data_label)
        plot_options_layout.addLayout(plot_options_top_row)

        plot_options_bottom_row = QHBoxLayout()
        plot_options_bottom_row.addWidget(QLabel("Signal:"))
        self.combo_plot_axis = QComboBox()
        self.combo_plot_axis.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
        self.combo_plot_axis.setMinimumContentsLength(12)
        self.combo_plot_axis.addItem("Position-X", userData=PoseCols.POS_X)
        self.combo_plot_axis.addItem("Position-Y", userData=PoseCols.POS_Y)
        self.combo_plot_axis.addItem("Position-Z", userData=PoseCols.POS_Z)
        plot_options_bottom_row.addWidget(self.combo_plot_axis)
        plot_options_bottom_row.addStretch()
        plot_options_layout.addLayout(plot_options_bottom_row)

        h_controls_layout.addWidget(plot_options_group)

        # Slice Range
        self.slice_group = QGroupBox("Range (s)")
        self.slice_group.setCheckable(True)
        self.slice_group.setChecked(False)
        slice_layout = QVBoxLayout(self.slice_group)

        slice_start_row = QHBoxLayout()
        slice_start_row.addWidget(QLabel("Start:"))
        self.le_slice_start = QLineEdit()
        slice_start_row.addWidget(self.le_slice_start)
        slice_layout.addLayout(slice_start_row)

        slice_end_row = QHBoxLayout()
        slice_end_row.addWidget(QLabel("End:"))
        self.le_slice_end = QLineEdit()
        slice_end_row.addWidget(self.le_slice_end)
        slice_layout.addLayout(slice_end_row)
        h_controls_layout.addWidget(self.slice_group)

        self.slice_output_group = QGroupBox("Scene")
        slice_output_layout = QGridLayout(self.slice_output_group)
        slice_output_layout.addWidget(QLabel("Name:"), 0, 0)
        self.le_scene_name = QLineEdit("scene")
        slice_output_layout.addWidget(self.le_scene_name, 0, 1)
        slice_output_layout.addWidget(QLabel("Padding:"), 1, 0)
        self.slice_padding_label = QLabel(f"{DEFAULT_SLICE_PADDING_ROWS} rows per side")
        self.slice_padding_label.setWordWrap(True)
        slice_output_layout.addWidget(self.slice_padding_label, 1, 1)
        slice_output_layout.addWidget(QLabel("Saved:"), 2, 0)
        self.slice_path_label = QLabel("Not saved yet.")
        self.slice_path_label.setWordWrap(True)
        slice_output_layout.addWidget(self.slice_path_label, 2, 1)
        h_controls_layout.addWidget(self.slice_output_group)

        # Paths remain selectable content, without imposing a panel/window width.
        for label in (self.file_path_label, self.slice_path_label):
            label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
            label.setTextInteractionFlags(
                Qt.TextInteractionFlag.TextSelectableByMouse
                | Qt.TextInteractionFlag.TextSelectableByKeyboard
            )

        # Run/Export Buttons
        run_button_layout = QVBoxLayout()
        self.save_slice_button = QPushButton("Save slice...")
        self.save_slice_button.setEnabled(False)
        run_button_layout.addWidget(self.save_slice_button)
        self.save_process_button = QPushButton('Save and Process')
        self.save_process_button.setEnabled(False)
        run_button_layout.addWidget(self.save_process_button)
        self.save_status_label = QLabel('')
        self.save_status_label.setWordWrap(True)
        run_button_layout.addWidget(self.save_status_label)
        h_controls_layout.addLayout(run_button_layout)

        stretch_values = config_analysis_ui.RAW_DATA_PROCESSING_LAYOUT["bottom_controls_stretch"]
        # Reuse the existing layout tuning while Step 1 now only keeps slice-related controls.
        h_controls_layout.setStretch(0, stretch_values[0])
        h_controls_layout.setStretch(1, stretch_values[1])
        h_controls_layout.setStretch(2, stretch_values[2])
        h_controls_layout.setStretch(3, stretch_values[4])

        main_splitter.addWidget(controls_widget)
        main_splitter.setStretchFactor(0, 6)
        main_splitter.setStretchFactor(1, 2)
        main_splitter.setStretchFactor(2, 1)
        main_splitter.setSizes([440, 190, 120])

        group_layout.addWidget(main_splitter)
        layout.addWidget(group_box)

    def _connect_signals(self):
        self.load_csv_button.clicked.connect(self.open_csv_file)
        self.select_data_button.clicked.connect(self.open_data_selection_dialog)
        self.save_slice_button.clicked.connect(self.save_scene_slice)
        self.save_process_button.clicked.connect(self.process_requested)
        self.review_marker_flips_button.clicked.connect(self.open_marker_flip_review)
        self.cancel_marker_review_button.clicked.connect(self.cancel_marker_review)
        self.confirm_review_dimensions.toggled.connect(self._confirm_dimensions)
        for edit in (self.le_box_l, self.le_box_w, self.le_box_h):
            edit.textChanged.connect(self._review_dimensions_changed)
        self.save_corrected_source_button.clicked.connect(self.save_corrected_source)
        self.combo_plot_axis.currentIndexChanged.connect(self.update_plot)
        self.plot_manager.region_changed_signal.connect(self.on_region_changed)
        self.slice_group.toggled.connect(self.toggle_slicing_widgets)
        self.le_slice_start.editingFinished.connect(self.update_span_selector_from_inputs)
        self.le_slice_end.editingFinished.connect(self.update_span_selector_from_inputs)
        self._connect_scene_signals()
        self._review_dimensions_changed()

    def append_log(self, message):
        self.log_output.append(message)

    def _approved_marker_corrections(self) -> list[MarkerCorrectionDecision]:
        return normalize_marker_corrections(
            self.marker_correction_decisions,
            approved_only=True,
        )

    def _build_marker_review_state(
        self,
        filepath: str,
        header_info: dict[str, list[str]],
        raw_data,
        parsed_data,
    ):
        metadata = try_read_corrected_source_metadata(filepath)
        review_header_info = header_info
        if metadata is None:
            review_raw_data = raw_data.copy(deep=True)
            review_parsed_data = parsed_data.copy(deep=True)
            original_source_reference = filepath
            original_source_sha256 = _sha256_file(filepath)
            decisions = []
        else:
            if metadata.schema_version == "3":
                context = json.loads(metadata.context_json)
                header_info["export_metadata"] = context.get("export_metadata", {})
                review_header_info, review_raw_data = materialize_face_assignments(
                    header_info, raw_data, [], context["base_faces"])
            else:
                review_raw_data = undo_approved_marker_permutations(
                    raw_data, header_info, metadata.decisions)
            review_parsed_data = self.parser.process(review_header_info, review_raw_data)
            original_source_reference = metadata.source
            original_source_sha256 = metadata.source_sha256
            decisions = list(metadata.decisions)
        return (
            metadata,
            review_raw_data,
            review_parsed_data,
            original_source_reference,
            original_source_sha256,
            decisions,
            review_header_info,
        )

    def _update_marker_review_summary(self) -> None:
        reviewed_count = len(normalize_marker_corrections(self.marker_correction_decisions))
        approved_count = len(self._approved_marker_corrections())
        if self._review_invalidated:
            self.marker_review_summary_label.setText('Source or geometry changed; review again')
        elif self.marker_review_dirty:
            self.marker_review_section.setExpanded(True)
            self.marker_review_summary_label.setText(
                f"{reviewed_count} reviewed, {approved_count} approved; unsaved"
            )
        elif self.correction_source_metadata is not None:
            self.marker_review_summary_label.setText(
                f"{self.correction_source_metadata.event_count} reviewed, "
                f"{self.correction_source_metadata.approved_event_count} approved"
            )
        elif self.marker_flip_candidates:
            recommended_count = sum(
                candidate.recommendation_axis is not None
                for candidate in self.marker_flip_candidates
            )
            self.marker_review_summary_label.setText(
                f"{len(self.marker_flip_candidates)} events, {recommended_count} recommended"
            )
        else:
            self.marker_review_summary_label.setText(
                "Not reviewed"
            )

        if self.correction_source_metadata is not None and self.source_path:
            source_text = "Source: corrected"
        else:
            source_text = "Source: original"
        self.marker_review_source_label.setText(source_text)
        self.marker_review_source_label.setToolTip(self.source_path or source_text)
        self.save_corrected_source_button.setEnabled(
            self.raw_data is not None
            and self.header_info is not None
            and self.marker_review_dirty
        )
        self.save_slice_button.setEnabled(
            self.raw_data is not None and self.parsed_data is not None and not self.marker_review_dirty
        )
        self._update_scene_gates()

    def open_csv_file(self):
        if self.scene_busy or self.marker_review_busy:
            return
        filepath, _ = QFileDialog.getOpenFileName(self, "Select CSV File", "", raw_csv_file_filter())
        if filepath:
            try:
                self.load_csv_path(filepath)
            except Exception as exc:
                self.append_log(f"[ERROR] Failed to load or parse file: {exc}")
                self.log_message.emit(f"[ERROR] Failed to load or parse file: {exc}")

    def load_csv_path(self, filepath):
        """Load a selected observation file through the normal preview path."""
        if self.scene_busy or self.marker_review_busy:
            raise RuntimeError('Wait for the current review before opening another capture.')
        preview = self._prepare_csv_preview(filepath)
        self._apply_csv_preview(filepath, preview)

    def _prepare_csv_preview(self, filepath):
        """Read without replacing the active source or its operator review."""
        signature = MarkerReviewWorker.source_signature(filepath)
        header_info, raw_data = self.data_loader.load_csv(filepath)
        parsed_data = self.parser.process(header_info, raw_data)
        (
            correction_source_metadata,
            review_raw_data,
            review_parsed_data,
            original_source_reference,
            original_source_sha256,
            marker_correction_decisions,
            review_header_info,
        ) = self._build_marker_review_state(
            filepath,
            header_info,
            raw_data,
            parsed_data,
        )
        source_sha256 = _sha256_file(filepath)
        if signature != MarkerReviewWorker.source_signature(filepath):
            raise ValueError('Capture changed while loading. Reload it before review.')
        return dict(header_info=header_info, raw_data=raw_data, parsed_data=parsed_data,
                    source_sha256=source_sha256, marker_state=(
                        correction_source_metadata, review_raw_data, review_parsed_data,
                        original_source_reference, original_source_sha256,
                        marker_correction_decisions, review_header_info))

    def _apply_csv_preview(self, filepath, preview, *, emit=True):
        self._source_revision += 1
        self.cancel_marker_review()
        self.confirm_review_dimensions.setChecked(False)
        header_info, raw_data, parsed_data = (preview[key] for key in
                                              ('header_info', 'raw_data', 'parsed_data'))
        (correction_source_metadata, review_raw_data, review_parsed_data,
         original_source_reference, original_source_sha256,
         marker_correction_decisions, review_header_info) = preview['marker_state']
        self.header_info = header_info
        self.raw_data = raw_data
        self.parsed_data = parsed_data
        self.source_path = filepath
        self.active_source_sha256 = preview['source_sha256']
        self.review_context_json = ""
        self.correction_source_metadata = correction_source_metadata
        if correction_source_metadata is not None and correction_source_metadata.schema_version == '3':
            self.review_context_json = correction_source_metadata.context_json
            dims = json.loads(self.review_context_json)['box_dims_mm']
            for edit, value in zip((self.le_box_l, self.le_box_w, self.le_box_h), dims):
                edit.setText(str(value))
        self.review_raw_data = review_raw_data
        self.review_header_info = review_header_info
        self.review_parsed_data = review_parsed_data
        self.original_source_reference = original_source_reference
        self.original_source_sha256 = original_source_sha256
        self.marker_flip_candidates = []
        self.marker_correction_decisions = marker_correction_decisions
        self.marker_review_dirty = False
        self._review_invalidated = False
        self._reset_scenes()
        self._set_file_path_display(filepath)
        self.append_log("[INFO] Preview parsing complete.")

        # Keep an explicit selection when the new capture has those markers.
        # A marker-only capture still needs an initial visible trajectory.
        all_targets = self.data_loader.get_plottable_targets(self.parsed_data)
        retained_targets = [target for target in self.current_selected_targets if target in all_targets]
        if retained_targets:
            self.current_selected_targets = retained_targets
        elif DisplayNames.RB_CENTER in all_targets:
            self.current_selected_targets = [DisplayNames.RB_CENTER]
        else:
            self.current_selected_targets = all_targets[:1]
        self.selected_data_label.setText('Selected: ' + (', '.join(self.current_selected_targets) or 'None'))

        self.update_plot()
        self.slice_group.setChecked(False)
        self.save_slice_button.setEnabled(True)
        self.review_marker_flips_button.setEnabled(True)
        self.slice_path_label.setText("Not saved yet.")
        self._update_marker_review_summary()

        if emit:
            self.file_loaded.emit(self.header_info, self.raw_data, self.parsed_data)


    def _read_box_dimensions(self) -> tuple[float, float, float]:
        box_dims = (
            float(self.le_box_l.text()),
            float(self.le_box_w.text()),
            float(self.le_box_h.text()),
        )
        if any(not math.isfinite(value) or value <= 0 for value in box_dims):
            raise ValueError("Box dimensions must be positive values.")
        return box_dims

    def _face_context(self):
        old = self.correction_source_metadata
        original = json.loads(old.context_json) if old is not None and old.schema_version == "3" else {}
        base = original.get("base_faces") or {
            mid: marker_face(mid) for mid in MarkerFlipAnalyzer._marker_ids(self.review_parsed_data)
        }
        return json.dumps({
            "box_dims_mm": self._read_box_dimensions(), "base_faces": base,
            "coordinate_policy": "global-y-up-box-xyz-mm",
            "export_metadata": self.header_info.get("export_metadata", {}),
            "original_source_rows": original.get("original_source_rows", self.header_info.get("source_rows", [])),
            "source_sha256": self.original_source_sha256, "algorithm_version": FACE_ASSIGNMENT_ALGORITHM_VERSION,
            "review_policy": REVIEW_VERSION,
            "geometry": config_app.FACE_DEFINITIONS,
            "optimizer": {"method": "Nelder-Mead", "maxiter": 1500,
                          "xatol": self._optimizer_settings()['xatol'],
                          "fatol": self._optimizer_settings()['fatol']},
        }, sort_keys=True, separators=(",", ":"))

    @staticmethod
    def _optimizer_settings():
        from src.config import config_analysis
        return {'xatol': config_analysis.OPTIMIZER_XTOL, 'fatol': config_analysis.OPTIMIZER_FATOL}

    def _review_identity(self):
        return canonical_key({'revision': self._source_revision, 'active_source': self.active_source_sha256,
            'context': self._face_context(), 'history': [asdict(d) for d in self.marker_correction_decisions],
            'configuration': analyzer_configuration(self.marker_flip_analyzer_factory()),
            'registration': self.scene_registration.profile if self.scene_registration else None})

    def _confirm_dimensions(self, checked):
        try:
            self._confirmed_dimensions = self._read_box_dimensions() if checked else None
            if checked:
                self._last_review_dimensions = self._confirmed_dimensions
        except ValueError:
            self._confirmed_dimensions = None
            self.confirm_review_dimensions.setChecked(False)
        self._update_scene_gates()

    def _review_dimensions_changed(self):
        try:
            dimensions = self._read_box_dimensions()
        except ValueError:
            dimensions = None
        if dimensions is not None and dimensions == self._last_review_dimensions:
            return
        self._last_review_dimensions = dimensions
        self._review_cache = None
        self.confirm_review_dimensions.setChecked(False)
        self._confirmed_dimensions = None
        try:
            label = ' × '.join(f'{v:g}' for v in self._read_box_dimensions())
            self.confirm_review_dimensions.setText(f'Use {label} mm for review')
        except ValueError:
            self.confirm_review_dimensions.setText('Enter valid dimensions for review')
        self.cancel_marker_review()
        if self.marker_correction_decisions or self.marker_flip_candidates:
            self._review_invalidated = True
            self.marker_review_summary_label.setText('Dimensions changed; review again')
        self._update_scene_gates()

    def cancel_marker_review(self):
        worker = self.review_worker
        if worker is not None:
            worker.cancel_requested = True
            worker.requestInterruption()
            self.cancel_marker_review_button.setEnabled(False)
            self.marker_review_summary_label.setText('Cancelling review...')

    def _review_progress(self, worker, phase, done, total):
        if worker is not self.review_worker or worker.cancel_requested or worker.isInterruptionRequested():
            return
        self.marker_review_summary_label.setText(phase)
        self.marker_review_progress.setRange(0, total if total else 0)
        self.marker_review_progress.setValue(done)

    def _review_finished(self, worker):
        if worker is not self.review_worker:
            worker.deleteLater()
            return
        self.review_worker = None
        self._set_review_busy(False)
        interrupted = worker.cancel_requested or worker.isInterruptionRequested()
        identity_matches = False
        try:
            identity_matches = worker.identity == self._review_identity()
            current = (identity_matches
                       and worker.verified_signature == worker.source_signature(self.source_path))
        except (ValueError, TypeError, OSError):
            current = False
        if identity_matches and not current and not interrupted:
            self._review_invalidated = True
            self._review_cache = None
            self._update_marker_review_summary()
        if interrupted or not identity_matches or self._close_after_review:
            self.append_log('[INFO] Review cancelled or source changed; existing decisions were kept.')
        elif worker.error:
            self._marker_review_failed(worker.error)
        elif not current:
            self._marker_review_failed('Capture changed after validation. Reload before review.')
        elif worker.pending_confirmation is not None and worker.result is not None:
            result = worker.result
            self._commit_marker_review(result['candidates'], result['decisions'], result['context'])
        elif worker.result is not None:
            self._review_cache = {'key': worker.result['cache_key'], 'result': deepcopy(worker.result)}
            self.last_review_statistics = worker.result['statistics']
            self._pending_review_identity = worker.identity
            self._finish_marker_review(worker.result['candidates'])
        worker.deleteLater()
        if self._close_after_review:
            self._close_after_review = False
            QTimer.singleShot(0, self.window().close)

    def _set_review_busy(self, busy):
        self.marker_review_busy = bool(busy)
        self.load_csv_button.setEnabled(not busy)
        self.review_marker_flips_button.setEnabled(not busy)
        self.review_marker_flips_button.setText('Reviewing...' if busy else 'Review')
        self.box_dims_group.setEnabled(not busy)
        self.confirm_review_dimensions.setEnabled(not busy)
        self.marker_review_progress.setVisible(busy)
        self.cancel_marker_review_button.setVisible(busy)
        self.cancel_marker_review_button.setEnabled(busy)
        if busy:
            self.marker_review_section.setExpanded(True)
            self.marker_review_summary_label.setText('Preparing review')
            self.save_slice_button.setEnabled(False)
            self.save_corrected_source_button.setEnabled(False)
        else:
            self._update_marker_review_summary()
        self._update_scene_gates()

    def open_marker_flip_review(self):
        if self.scene_busy:
            return
        if self.review_parsed_data is None or self.review_parsed_data.empty:
            return
        if self.review_worker is not None and self.review_worker.isRunning():
            return
        try:
            if self._confirmed_dimensions != self._read_box_dimensions():
                raise ValueError('Confirm the box dimensions for this capture before Review.')
            if self.correction_source_metadata is not None and self.correction_source_metadata.schema_version == "2":
                raise ValueError("Legacy XYZ-corrected files remain readable. Load the original CSV for a new face review.")
            metadata = self.header_info.get("export_metadata", {})
            if metadata.get("Length Units") != "Millimeters" or metadata.get("Coordinate Space") != "Global":
                raise ValueError("Face review requires documented Global / Millimeters input.")
            context = self._face_context()
            base = json.loads(context)['base_faces']
            from src.analysis.pipeline.face_assignment import FACES
            if not base or any(face not in FACES for face in base.values()):
                raise ValueError('Every marker requires a known original analysis face.')
            self._pending_review_context = context
            self.append_log('[INFO] Scanning observations before bounded local-axis review...')
            self._set_review_busy(True)
            self.review_worker = MarkerReviewWorker(self.review_parsed_data, self._read_box_dimensions(),
                self.pose_optimizer_factory, self.marker_flip_analyzer_factory, self,
                identity=self._review_identity(), source_path=self.source_path, source_sha256=self.active_source_sha256)
            worker = self.review_worker
            worker.cache = self._review_cache
            worker.progress.connect(lambda phase, done, total: self._review_progress(worker, phase, done, total))
            worker.finished.connect(lambda: self._review_finished(worker))
            self.review_worker.start()
        except Exception as exc:
            self._marker_review_failed(str(exc))

    def _marker_review_failed(self, message):
        self._set_review_busy(False)
        self.append_log(f"[ERROR] Marker flip review failed: {message}")
        QMessageBox.warning(self, "Marker Flip Review Failed", message)

    def _finish_marker_review(self, candidates):
        self._set_review_busy(False)
        if not candidates and not (self._review_invalidated or self.marker_correction_decisions or self.marker_flip_candidates):
            self.marker_review_summary_label.setText('No review candidates')
            QMessageBox.information(self, "Marker Flip Review", "No reviewable candidate discontinuities were found.")
            return
        context = self._pending_review_context
        identity = getattr(self, '_pending_review_identity', None)
        existing = self.marker_correction_decisions if context == self.review_context_json and not self._review_invalidated else []
        # Only retain approvals for unchanged evidence, kind, and operator action.
        existing = [d for d in existing if any(c.event_id == d.event_id
            and c.evidence_json() == d.evidence_json and c.correction_kind == d.correction_kind
            and c.boundary_time_sec == d.boundary_time_sec for c in candidates)]
        dialog = self.marker_flip_dialog_factory(candidates, existing_decisions=existing, parent=self)
        if identity is not None:
            dialog.setWindowTitle('Marker Review — ' + Path(self.source_path).name + ' — '
                                  + ' × '.join(map(str, self._read_box_dimensions())) + ' mm')
        if dialog.exec() != QDialog.DialogCode.Accepted:
            self.append_log("[INFO] Marker flip review cancelled; no decisions changed.")
            return
        try:
            valid_identity = identity is None or identity == self._review_identity()
        except (ValueError, TypeError, OSError):
            valid_identity = False
        if not valid_identity:
            self._review_invalidated = True
            self._marker_review_failed('Source or dimensions changed; review again. No decisions were applied.')
            return
        decisions = normalize_marker_corrections(dialog.get_decisions())
        if identity is not None:
            # Validate the bytes asynchronously before committing operator choices.
            # The old approvals remain active until this cancellable phase finishes.
            self._set_review_busy(True)
            worker = MarkerReviewWorker(None, self._read_box_dimensions(), self.pose_optimizer_factory,
                self.marker_flip_analyzer_factory, self, identity=identity,
                source_path=self.source_path, source_sha256=self.active_source_sha256)
            worker.pending_confirmation = {'candidates': candidates, 'decisions': decisions, 'context': context}
            self.review_worker = worker
            worker.progress.connect(lambda phase, done, total: self._review_progress(worker, phase, done, total))
            worker.finished.connect(lambda: self._review_finished(worker))
            worker.start()
            return
        self._commit_marker_review(candidates, decisions, context)

    def _commit_marker_review(self, candidates, decisions, context):
        self.marker_flip_candidates = candidates
        self.marker_correction_decisions = decisions
        self.review_context_json = context
        self._review_invalidated = False
        active = list(self.correction_source_metadata.decisions) if self.correction_source_metadata else []
        self.marker_review_dirty = self.marker_correction_decisions != active or (
            self.correction_source_metadata is None or self.correction_source_metadata.context_json != context)
        if self.marker_review_dirty:
            self._invalidate_scene_evidence('geometry_changed')
        self._update_marker_review_summary()

    def closeEvent(self, event):
        if self.scene_worker is not None and self.scene_worker.isRunning():
            self.scene_worker.requestInterruption()
            event.ignore()
            return
        if self.review_worker is not None:
            self._close_after_review = True
            self.cancel_marker_review()
            event.ignore()
            return
        super().closeEvent(event)

    def save_corrected_source(self):
        if self.marker_review_busy or self._review_invalidated:
            return
        if (
            self.raw_data is None
            or self.review_raw_data is None
            or self.header_info is None
            or not self.source_path
        ):
            return

        default_name = build_corrected_source_default_name(self.source_path)
        filepath, _ = QFileDialog.getSaveFileName(
            self,
            "Save Corrected Source",
            os.path.join(os.path.dirname(self.source_path), default_name),
            corrected_source_file_filter(),
        )
        if not filepath:
            return

        original_source = self.original_source_reference or self.source_path
        try:
            if self.active_source_sha256 and _sha256_file(self.source_path) != self.active_source_sha256:
                raise ValueError("Active source changed since loading; reload before saving.")
            is_face = bool(self.review_context_json) or any(d.correction_kind == "face_assignment" for d in self.marker_correction_decisions)
            corrected_header = self.header_info
            if is_face:
                if not self.review_context_json or self._face_context() != self.review_context_json:
                    raise ValueError("Review context changed; review and approve again before saving.")
                corrected_header, corrected_raw_data = materialize_face_assignments(
                    self.review_header_info or self.header_info, self.review_raw_data, self.marker_correction_decisions,
                    json.loads(self.review_context_json)["base_faces"])
            else:
                corrected_raw_data = apply_approved_marker_permutations(
                    self.review_raw_data, self.header_info, self.marker_correction_decisions)
            corrected_parsed_data = self.parser.process(
                corrected_header,
                corrected_raw_data,
            )
            metadata = save_corrected_source_file(
                filepath=filepath,
                header_info=corrected_header,
                raw_data=corrected_raw_data,
                original_source_path=original_source,
                original_source_sha256=self.original_source_sha256,
                decisions=self.marker_correction_decisions,
                context_json=self.review_context_json if is_face else "",
            )
        except Exception as e:
            self.append_log(f"[ERROR] Failed to save corrected source: {e}")
            QMessageBox.warning(self, "Corrected Source Save Failed", str(e))
            return

        self.source_path = filepath
        self.active_source_sha256 = _sha256_file(filepath)
        self.header_info = corrected_header
        # Keep a full-width baseline so another save cannot apply the assignment twice.
        if is_face:
            self.review_header_info, self.review_raw_data = materialize_face_assignments(corrected_header, corrected_raw_data, [],
                json.loads(self.review_context_json)["base_faces"])
        self.raw_data = corrected_raw_data
        self.parsed_data = corrected_parsed_data
        self._set_file_path_display(filepath)
        self.correction_source_metadata = metadata
        self.original_source_reference = metadata.source
        self.original_source_sha256 = metadata.source_sha256
        self.marker_correction_decisions = list(metadata.decisions)
        self.marker_review_dirty = False
        self._reset_scenes()
        self.slice_path_label.setText("Not saved yet.")
        self.update_plot()
        self._update_marker_review_summary()
        self.file_loaded.emit(self.header_info, self.raw_data, self.parsed_data)
        self.append_log(f"[INFO] Corrected source saved and activated: {filepath}")

    def _set_file_path_display(self, filepath: str) -> None:
        set_path_label(self.file_path_label, filepath)

    def update_plot(self):
        df = self.parsed_data
        if df is None or df.empty:
            self.plot_manager.draw_plot(None, [])
            return
            
        selected_axis_generic = self.combo_plot_axis.currentData()
        if self.scene_session and selected_axis_generic in self.scene_session.result.signals:
            row = self.scene_panel.selected_row()
            plot_data = self.scene_session.result.signals
            self.plot_manager.draw_plot(plot_data, [selected_axis_generic])
            self.plot_manager.enable_interactions(df)
            if row:
                self.plot_manager.set_selector_active(True)
                self.plot_manager.set_region(row['start'], row['end'])
            else:
                self.plot_manager.set_selector_active(False)
            self.canvas.draw_idle()
            return
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
                    
        previous_region = (self.plot_manager.span_selector.extents
                           if self.plot_manager.span_selector is not None else None)
        self.plot_manager.draw_plot(df, columns_to_plot)
        if columns_to_plot and axis_suffix:
            declared_unit = (self.header_info or {}).get("export_metadata", {}).get("Length Units", "")
            unit = {"millimeters": "mm", "centimeters": "cm", "meters": "m"}.get(
                str(declared_unit).strip().lower(), "unit unknown")
            self.plot_manager.ax.set_ylabel(f"Position ({unit})")
        # Clearing the axes also removes the selector's artists. Reattach them
        # before restoring the selected scene or the manual CSV slice range.
        self.plot_manager.enable_interactions(df)
        if self.scene_session:
            row = self.scene_panel.selected_row()
            if row:
                self.plot_manager.set_selector_active(True)
                self.plot_manager.set_region(row['start'], row['end'])
        else:
            try:
                region = (float(self.le_slice_start.text()), float(self.le_slice_end.text()))
            except (ValueError, TypeError):
                region = previous_region
            if region is not None:
                self.plot_manager.set_region(*region)
            self.plot_manager.set_selector_active(self.slice_group.isChecked())
        self.canvas.draw_idle()

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
        self.le_slice_start.setText(repr(float(xmin)))
        self.le_slice_end.setText(repr(float(xmax)))
        self.le_slice_start.blockSignals(False)
        self.le_slice_end.blockSignals(False)
        self._scene_range_edited(xmin, xmax)

    def toggle_slicing_widgets(self, checked: bool):
        self.le_slice_start.setEnabled(checked)
        self.le_slice_end.setEnabled(checked)
        self.plot_manager.set_selector_active(checked)

    def update_span_selector_from_inputs(self):
        try:
            start_val = float(self.le_slice_start.text())
            end_val = float(self.le_slice_end.text())
            if start_val > end_val:
                start_val = end_val
                self.le_slice_start.setText(f"{start_val:.2f}")
            self.plot_manager.set_region(start_val, end_val)
            self._scene_range_edited(start_val, end_val)
        except (ValueError, TypeError):
            pass

    def _get_slice_bounds(self):
        if self.parsed_data is None or self.parsed_data.empty:
            raise ValueError("No parsed data is available.")

        if self.slice_group.isChecked():
            start_val = float(self.le_slice_start.text())
            end_val = float(self.le_slice_end.text())
        else:
            start_val = float(self.parsed_data.index.min())
            end_val = float(self.parsed_data.index.max())

        if start_val > end_val:
            start_val, end_val = end_val, start_val
        return start_val, end_val

    def _update_box_dimensions(self):
        length, width, height = self._read_box_dimensions()
        config_app.BOX_DIMS = [length, width, height]

    def _save_slice(self) -> bool:
        if self.marker_review_busy or self._review_invalidated:
            return False
        if self.raw_data is None or self.parsed_data is None:
            return False

        try:
            self._update_box_dimensions()
            if self.marker_review_dirty:
                raise ValueError('Save the reviewed corrected source before slicing.')
            if self.correction_source_metadata and self.correction_source_metadata.schema_version == '3':
                context = json.loads(self.correction_source_metadata.context_json)
                if tuple(context['box_dims_mm']) != tuple(config_app.BOX_DIMS):
                    raise ValueError('Box dimensions changed; review the original source again.')
            start_val, end_val = self._get_slice_bounds()
            scene_header, scene_review_json = self._scene_slice_context()
            scene_name = self.le_scene_name.text().strip() or "scene"
            default_name = build_slice_default_name(self.source_path or "", scene_name=scene_name)
            filepath, _ = QFileDialog.getSaveFileName(
                self,
                "Save Scene Slice",
                os.path.join(os.path.dirname(self.source_path or ""), default_name),
                slice_file_filter(),
            )
            if not filepath:
                return False

            metadata = save_slice_file(
                filepath=filepath,
                header_info=scene_header,
                raw_data=self.raw_data,
                source_path=self.source_path or "",
                box_dims=tuple(config_app.BOX_DIMS),
                full_start=float(self.parsed_data.index.min()),
                full_end=float(self.parsed_data.index.max()),
                user_start=start_val,
                user_end=end_val,
                pad_rows=DEFAULT_SLICE_PADDING_ROWS,
                scene_name=scene_name,
                marker_correction_metadata=self.correction_source_metadata,
                scene_review_json=scene_review_json,
            )
            self.last_saved_slice_path = os.path.abspath(filepath)
            set_path_label(self.slice_path_label, self.last_saved_slice_path)
            self.append_log(
                "[INFO] Scene slice saved: "
                f"{filepath} "
                f"(user={metadata.user_start:.3f}s~{metadata.user_end:.3f}s, "
                f"padded={metadata.padded_start:.3f}s~{metadata.padded_end:.3f}s)"
            )
            self.slice_saved.emit(filepath)
            return True
        except Exception as e:
            self.append_log(f"[ERROR] Failed to save scene slice: {e}")
            return False

    def save_scene_slice(self):
        self._save_slice()

    def save_for_processing(self):
        if self.scene_session is not None:
            return self.save_included_scenes()
        return [self.last_saved_slice_path] if self._save_slice() else []
