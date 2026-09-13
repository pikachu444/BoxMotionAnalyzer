import os
import json
import math
from pathlib import Path
from PySide6.QtCore import Signal, Qt, QThread
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QLineEdit, QComboBox, QTextEdit, QGroupBox, QGridLayout, QFileDialog,
    QDialog, QMessageBox, QSizePolicy, QSplitter
)
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qtagg import NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure

from src.analysis.ui.plot_manager import PlotManager
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


class MarkerReviewWorker(QThread):
    completed = Signal(object)
    failed = Signal(str)

    def __init__(self, data, dims, optimizer_factory, analyzer_factory, parent=None):
        super().__init__(parent)
        self.data, self.dims = data.copy(deep=True), dims
        self.optimizer_factory, self.analyzer_factory = optimizer_factory, analyzer_factory

    def run(self):
        try:
            optimizer = self.optimizer_factory(face_definitions=config_app.FACE_DEFINITIONS,
                local_box_corners=config_app.calculate_local_box_corners(self.dims))
            pose = optimizer.process(self.data, box_dims=self.dims)
            self.completed.emit(self.analyzer_factory().detect(self.data, pose, self.dims))
        except Exception as exc:
            self.failed.emit(str(exc))


class WidgetRawDataProcessing(SceneReviewFlow, QWidget):
    # Signals to communicate with MainApp
    file_loaded = Signal(dict, object, object) # header_info, raw_data, parsed_data
    log_message = Signal(str)
    slice_saved = Signal(str)

    def __init__(self, data_loader, parser):
        super().__init__()
        self.data_loader = data_loader
        self.parser = parser
        
        self.raw_data = None
        self.header_info = None
        self.parsed_data = None
        self.source_path = None
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
        self.marker_flip_dialog_factory = MarkerFlipReviewDialog
        self.pose_optimizer_factory = PoseOptimizer
        self._init_scene_state()

        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        group_box = QGroupBox("Raw Data Slice")
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
        self.load_csv_button = QPushButton("Load CSV File...")
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
        right_panel_layout.addWidget(self.box_dims_group)

        self.marker_review_group = QGroupBox("Marker Flip Review")
        marker_review_layout = QVBoxLayout(self.marker_review_group)
        self.marker_review_summary_label = QLabel("Load a CSV file to review marker flips.")
        self.marker_review_summary_label.setWordWrap(True)
        marker_review_layout.addWidget(self.marker_review_summary_label)
        self.marker_review_source_label = QLabel("Active source: original")
        self.marker_review_source_label.setWordWrap(True)
        self.marker_review_source_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        marker_review_layout.addWidget(self.marker_review_source_label)
        marker_review_button_row = QHBoxLayout()
        self.review_marker_flips_button = QPushButton("Review Candidates...")
        self.review_marker_flips_button.setEnabled(False)
        self.save_corrected_source_button = QPushButton("Save Corrected Source...")
        self.save_corrected_source_button.setEnabled(False)
        marker_review_button_row.addWidget(self.review_marker_flips_button)
        marker_review_button_row.addWidget(self.save_corrected_source_button)
        marker_review_layout.addLayout(marker_review_button_row)
        right_panel_layout.addWidget(self.marker_review_group)

        # Log Output (Local to this widget for immediate feedback, or shared?)
        # The plan says "Encapsulates...". MainApp has a log output. 
        # But OriginalAnalysisWidget needs to show logs too?
        # In the original UI, the log output was in the right panel of Original Analysis.
        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setPlaceholderText("[INFO] Load a CSV file to start.")
        right_panel_layout.addWidget(self.log_output)
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
        controls_widget.setMinimumHeight(150)

        # Plot Options
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
        plot_options_bottom_row.addWidget(QLabel("Signal:"))
        self.combo_plot_axis = QComboBox()
        self.combo_plot_axis.setMinimumWidth(230)
        self.combo_plot_axis.addItem("Position-X", userData=PoseCols.POS_X)
        self.combo_plot_axis.addItem("Position-Y", userData=PoseCols.POS_Y)
        self.combo_plot_axis.addItem("Position-Z", userData=PoseCols.POS_Z)
        plot_options_bottom_row.addWidget(self.combo_plot_axis)
        plot_options_bottom_row.addStretch()
        plot_options_layout.addLayout(plot_options_bottom_row)

        h_controls_layout.addWidget(plot_options_group)

        # Slice Range
        self.slice_group = QGroupBox("Slice Range")
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

        self.slice_output_group = QGroupBox("Slice Output")
        slice_output_layout = QGridLayout(self.slice_output_group)
        slice_output_layout.addWidget(QLabel("Scene Name:"), 0, 0)
        self.le_scene_name = QLineEdit("scene")
        slice_output_layout.addWidget(self.le_scene_name, 0, 1)
        slice_output_layout.addWidget(QLabel("Padding:"), 1, 0)
        self.slice_padding_label = QLabel(f"{DEFAULT_SLICE_PADDING_ROWS} rows on each side")
        slice_output_layout.addWidget(self.slice_padding_label, 1, 1)
        slice_output_layout.addWidget(QLabel("Last Saved:"), 2, 0)
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

        # Keep bottom controls stable across processing mode text changes.
        plot_options_group.setMinimumWidth(
            config_analysis_ui.RAW_DATA_PROCESSING_LAYOUT["plot_options_group_min_width"]
        )
        self.slice_group.setMinimumWidth(
            config_analysis_ui.RAW_DATA_PROCESSING_LAYOUT["slice_group_min_width"]
        )
        self.slice_output_group.setMinimumWidth(
            config_analysis_ui.RAW_DATA_PROCESSING_LAYOUT["resampling_group_min_width"]
        )
        # Run/Export Buttons
        run_button_layout = QVBoxLayout()
        self.save_slice_button = QPushButton("Save Scene Slice")
        self.save_slice_button.setEnabled(False)
        run_button_layout.addWidget(self.save_slice_button)
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
        main_splitter.setSizes([470, 230, 180])

        group_layout.addWidget(main_splitter)
        layout.addWidget(group_box)

    def _connect_signals(self):
        self.load_csv_button.clicked.connect(self.open_csv_file)
        self.select_data_button.clicked.connect(self.open_data_selection_dialog)
        self.save_slice_button.clicked.connect(self.save_scene_slice)
        self.review_marker_flips_button.clicked.connect(self.open_marker_flip_review)
        self.save_corrected_source_button.clicked.connect(self.save_corrected_source)
        self.combo_plot_axis.currentIndexChanged.connect(self.update_plot)
        self.plot_manager.region_changed_signal.connect(self.on_region_changed)
        self.slice_group.toggled.connect(self.toggle_slicing_widgets)
        self.le_slice_start.editingFinished.connect(self.update_span_selector_from_inputs)
        self.le_slice_end.editingFinished.connect(self.update_span_selector_from_inputs)
        self._connect_scene_signals()

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
        if self.marker_review_dirty:
            self.marker_review_summary_label.setText(
                f"{reviewed_count} reviewed event(s), {approved_count} approved. "
                "Save the corrected source before creating a slice."
            )
        elif self.correction_source_metadata is not None:
            self.marker_review_summary_label.setText(
                f"Loaded corrected source with {self.correction_source_metadata.event_count} "
                f"reviewed event(s), {self.correction_source_metadata.approved_event_count} approved."
            )
        elif self.marker_flip_candidates:
            recommended_count = sum(
                candidate.recommendation_axis is not None
                for candidate in self.marker_flip_candidates
            )
            self.marker_review_summary_label.setText(
                f"Reviewed {len(self.marker_flip_candidates)} candidate(s); "
                f"{recommended_count} had a supported-axis recommendation."
            )
        else:
            self.marker_review_summary_label.setText(
                "No marker correction is active. Review is optional."
            )

        if self.correction_source_metadata is not None and self.source_path:
            source_text = "Active source: corrected"
        else:
            source_text = "Active source: original"
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
        if self.scene_busy:
            return
        filepath, _ = QFileDialog.getOpenFileName(self, "Select CSV File", "", raw_csv_file_filter())
        if filepath:
            try:
                preview = self._prepare_csv_preview(filepath)
                self._apply_csv_preview(filepath, preview)
            except Exception as exc:
                self.append_log(f"[ERROR] Failed to load or parse file: {exc}")
                self.log_message.emit(f"[ERROR] Failed to load or parse file: {exc}")

    def _prepare_csv_preview(self, filepath):
        """Read without replacing the active source or its operator review."""
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
        return dict(header_info=header_info, raw_data=raw_data, parsed_data=parsed_data,
                    source_sha256=_sha256_file(filepath), marker_state=(
                        correction_source_metadata, review_raw_data, review_parsed_data,
                        original_source_reference, original_source_sha256,
                        marker_correction_decisions, review_header_info))

    def _apply_csv_preview(self, filepath, preview, *, emit=True):
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
        self._reset_scenes()
        self._set_file_path_display(filepath)
        self.append_log("[INFO] Preview parsing complete.")

        # Default selection logic
        all_targets = self.data_loader.get_plottable_targets(self.parsed_data)
        if DisplayNames.RB_CENTER in all_targets:
            self.current_selected_targets = [DisplayNames.RB_CENTER]
            self.selected_data_label.setText(f"Selected: {DisplayNames.RB_CENTER}")
            self.append_log(f"[INFO] Default target '{DisplayNames.RB_CENTER}' selected for plotting.")

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
        }, sort_keys=True, separators=(",", ":"))

    def _set_review_busy(self, busy):
        self.marker_review_busy = bool(busy)
        self.load_csv_button.setEnabled(not busy)
        self.review_marker_flips_button.setEnabled(not busy)
        self.review_marker_flips_button.setText('Calculating poses...' if busy else 'Review Candidates...')
        self.box_dims_group.setEnabled(not busy)
        if busy:
            self.marker_review_summary_label.setText('Calculating analysis poses and four face hypotheses. Please wait.')
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
            if self.correction_source_metadata is not None and self.correction_source_metadata.schema_version == "2":
                raise ValueError("Legacy XYZ-corrected files remain readable. Load the original CSV for a new face review.")
            metadata = self.header_info.get("export_metadata", {})
            if metadata.get("Length Units") != "Millimeters" or metadata.get("Coordinate Space") != "Global":
                raise ValueError("Face review requires documented Global / Millimeters input.")
            context = self._face_context()
            # Validate all base faces without changing the active stream.
            materialize_face_assignments(self.review_header_info or self.header_info, self.review_raw_data, [], json.loads(context)["base_faces"])
            self._pending_review_context = context
            self.append_log("[INFO] Estimating pose and refitting local-axis face hypotheses...")
            self._set_review_busy(True)
            self.review_worker = MarkerReviewWorker(self.review_parsed_data, self._read_box_dimensions(),
                self.pose_optimizer_factory, self.marker_flip_analyzer_factory, self)
            self.review_worker.completed.connect(self._finish_marker_review)
            self.review_worker.failed.connect(self._marker_review_failed)
            self.review_worker.finished.connect(self._update_scene_gates)
            self.review_worker.start()
        except Exception as exc:
            self._marker_review_failed(str(exc))

    def _marker_review_failed(self, message):
        self._set_review_busy(False)
        self.append_log(f"[ERROR] Marker flip review failed: {message}")
        QMessageBox.warning(self, "Marker Flip Review Failed", message)

    def _finish_marker_review(self, candidates):
        self._set_review_busy(False)
        if not candidates:
            QMessageBox.information(self, "Marker Flip Review", "No reviewable candidate discontinuities were found.")
            return
        context = self._pending_review_context
        existing = self.marker_correction_decisions if context == self.review_context_json else []
        # Only retain approvals for unchanged evidence, kind, and operator action.
        existing = [d for d in existing if any(c.event_id == d.event_id
            and c.evidence_json() == d.evidence_json and c.correction_kind == d.correction_kind
            and c.boundary_time_sec == d.boundary_time_sec for c in candidates)]
        dialog = self.marker_flip_dialog_factory(candidates, existing_decisions=existing, parent=self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            self.append_log("[INFO] Marker flip review cancelled; no decisions changed.")
            return
        self.marker_flip_candidates = candidates
        self.marker_correction_decisions = normalize_marker_corrections(dialog.get_decisions())
        self.review_context_json = context
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
        if self.review_worker is not None and self.review_worker.isRunning():
            event.ignore()
            self.append_log("[INFO] Wait for the active review calculation before closing.")
            return
        super().closeEvent(event)

    def save_corrected_source(self):
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
            is_face = any(d.correction_kind == "face_assignment" for d in self.marker_correction_decisions)
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
        self.file_path_label.setText(filepath)
        self.file_path_label.setToolTip(filepath)

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
            self.slice_path_label.setText(filepath)
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
