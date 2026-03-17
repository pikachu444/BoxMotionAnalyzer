import os
from PySide6.QtCore import Signal, Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QLineEdit, QComboBox, QTextEdit, QGroupBox, QGridLayout, QFileDialog, QCheckBox,
    QSizePolicy, QSplitter
)
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qtagg import NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure

from src.analysis.ui.plot_manager import PlotManager
from src.analysis.ui.data_selection_dialog import DataSelectionDialog
from src.config import config_app, config_analysis_ui
from src.config.data_columns import (
    PoseCols, RawMarkerCols, DisplayNames, RigidBodyCols
)
from src.analysis.pipeline.artifact_io import (
    DEFAULT_SLICE_PADDING_ROWS,
    build_slice_default_name,
    save_slice_file,
)

class WidgetRawDataProcessing(QWidget):
    # Signals to communicate with MainApp
    file_loaded = Signal(dict, object, object) # header_info, raw_data, parsed_data
    log_message = Signal(str)
    slice_saved = Signal(str)
    open_processing_requested = Signal(str)

    def __init__(self, data_loader, parser):
        super().__init__()
        self.data_loader = data_loader
        self.parser = parser
        
        self.raw_data = None
        self.header_info = None
        self.parsed_data = None
        self.source_path = None
        self.latest_slice_path = None
        self.current_selected_targets = []

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
        self.fig.subplots_adjust(left=0.08, right=0.98, bottom=0.1, top=0.95)
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

        # 1b. Bottom Controls
        controls_widget = QWidget()
        h_controls_layout = QHBoxLayout(controls_widget)
        controls_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        controls_widget.setMinimumHeight(180)

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
        plot_options_bottom_row.addWidget(QLabel("Axis:"))
        self.combo_plot_axis = QComboBox()
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

        next_step_group = QGroupBox("Next Step")
        next_step_layout = QVBoxLayout(next_step_group)
        next_step_group.setMinimumWidth(
            config_analysis_ui.RAW_DATA_PROCESSING_LAYOUT["processing_group_min_width"]
        )
        self.next_step_description = QLabel(
            "Processing settings moved to Step 1.5. Save a scene slice first, then continue with processing."
        )
        self.next_step_description.setWordWrap(True)
        self.next_step_description.setStyleSheet("color: #4a5568;")
        self.next_step_description.setFixedHeight(
            config_analysis_ui.RAW_DATA_PROCESSING_LAYOUT["processing_mode_description_fixed_height"]
        )
        self.next_step_description.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        next_step_layout.addWidget(self.next_step_description)
        self.open_processing_button = QPushButton("Open in Step 1.5")
        self.open_processing_button.setEnabled(False)
        next_step_layout.addWidget(self.open_processing_button)
        next_step_layout.addStretch()
        h_controls_layout.addWidget(next_step_group)

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
        self.save_and_open_button = QPushButton("Save and Open Step 1.5")
        self.save_and_open_button.setEnabled(False)
        run_button_layout.addWidget(self.save_slice_button)
        run_button_layout.addWidget(self.save_and_open_button)
        h_controls_layout.addLayout(run_button_layout)

        # Stretch mapping order:
        #   0: plot_options_group, 1: slice_group, 2: resampling_group, 3: processing_group, 4: run_button_layout
        for index, stretch in enumerate(config_analysis_ui.RAW_DATA_PROCESSING_LAYOUT["bottom_controls_stretch"]):
            h_controls_layout.setStretch(index, stretch)

        main_splitter.addWidget(controls_widget)
        main_splitter.setStretchFactor(0, 6)
        main_splitter.setStretchFactor(1, 1)
        main_splitter.setSizes([700, 220])

        group_layout.addWidget(main_splitter)
        layout.addWidget(group_box)

    def _connect_signals(self):
        self.load_csv_button.clicked.connect(self.open_csv_file)
        self.select_data_button.clicked.connect(self.open_data_selection_dialog)
        self.save_slice_button.clicked.connect(self.save_scene_slice)
        self.save_and_open_button.clicked.connect(self.save_scene_slice_and_open_processing)
        self.open_processing_button.clicked.connect(self.emit_open_processing)
        self.combo_plot_axis.currentIndexChanged.connect(self.update_plot)
        self.plot_manager.region_changed_signal.connect(self.on_region_changed)
        self.slice_group.toggled.connect(self.toggle_slicing_widgets)
        self.le_slice_start.editingFinished.connect(self.update_span_selector_from_inputs)
        self.le_slice_end.editingFinished.connect(self.update_span_selector_from_inputs)

    def append_log(self, message):
        self.log_output.append(message)

    def open_csv_file(self):
        filepath, _ = QFileDialog.getOpenFileName(self, "Select CSV File", "", "CSV Files (*.csv)")
        if filepath:
            try:
                self.header_info, self.raw_data = self.data_loader.load_csv(filepath)
                self.source_path = filepath
                self.latest_slice_path = None
                self.file_path_label.setText(filepath)
                self.log_message.emit(f"[INFO] Loaded {filepath}. Parsing for preview...")
                self.append_log(f"[INFO] Loaded {filepath}. Parsing for preview...")
                
                self.parsed_data = self.parser.process(self.header_info, self.raw_data)
                self.append_log("[INFO] Preview parsing complete.")
                
                # Default selection logic
                all_targets = self.data_loader.get_plottable_targets(self.parsed_data)
                if DisplayNames.RB_CENTER in all_targets:
                    self.current_selected_targets = [DisplayNames.RB_CENTER]
                    self.selected_data_label.setText(f"Selected: {DisplayNames.RB_CENTER}")
                    self.append_log(f"[INFO] Default target '{DisplayNames.RB_CENTER}' selected for plotting.")
                
                self.update_plot()
                self.plot_manager.enable_interactions(self.parsed_data)
                self.slice_group.setChecked(False)
                self.save_slice_button.setEnabled(True)
                self.save_and_open_button.setEnabled(True)
                self.open_processing_button.setEnabled(False)
                self.slice_path_label.setText("Not saved yet.")
                
                # Emit signal to MainApp
                self.file_loaded.emit(self.header_info, self.raw_data, self.parsed_data)
                
            except Exception as e:
                self.append_log(f"[ERROR] Failed to load or parse file: {e}")
                self.log_message.emit(f"[ERROR] Failed to load or parse file: {e}")

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
                    
        self.plot_manager.draw_plot(df, columns_to_plot)

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
        self.plot_manager.set_selector_active(checked)

    def update_span_selector_from_inputs(self):
        try:
            start_val = float(self.le_slice_start.text())
            end_val = float(self.le_slice_end.text())
            if start_val > end_val:
                start_val = end_val
                self.le_slice_start.setText(f"{start_val:.2f}")
            self.plot_manager.set_region(start_val, end_val)
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
        l = float(self.le_box_l.text())
        w = float(self.le_box_w.text())
        h = float(self.le_box_h.text())
        config_app.BOX_DIMS = [l, w, h]

    def _save_slice(self, open_after_save: bool) -> bool:
        if self.raw_data is None or self.parsed_data is None:
            return False

        try:
            self._update_box_dimensions()
            start_val, end_val = self._get_slice_bounds()
            scene_name = self.le_scene_name.text().strip() or "scene"
            default_name = build_slice_default_name(self.source_path or "", scene_name=scene_name)
            filepath, _ = QFileDialog.getSaveFileName(
                self,
                "Save Scene Slice",
                os.path.join(os.path.dirname(self.source_path or ""), default_name),
                "Slice Files (*.slice)",
            )
            if not filepath:
                return False

            metadata = save_slice_file(
                filepath=filepath,
                header_info=self.header_info,
                raw_data=self.raw_data,
                source_path=self.source_path or "",
                box_dims=tuple(config_app.BOX_DIMS),
                full_start=float(self.parsed_data.index.min()),
                full_end=float(self.parsed_data.index.max()),
                user_start=start_val,
                user_end=end_val,
                pad_rows=DEFAULT_SLICE_PADDING_ROWS,
                scene_name=scene_name,
            )
            self.latest_slice_path = filepath
            self.slice_path_label.setText(filepath)
            self.open_processing_button.setEnabled(True)
            self.append_log(
                "[INFO] Scene slice saved: "
                f"{filepath} "
                f"(user={metadata.user_start:.3f}s~{metadata.user_end:.3f}s, "
                f"padded={metadata.padded_start:.3f}s~{metadata.padded_end:.3f}s)"
            )
            self.slice_saved.emit(filepath)
            if open_after_save:
                self.open_processing_requested.emit(filepath)
            return True
        except Exception as e:
            self.append_log(f"[ERROR] Failed to save scene slice: {e}")
            return False

    def save_scene_slice(self):
        self._save_slice(open_after_save=False)

    def save_scene_slice_and_open_processing(self):
        self._save_slice(open_after_save=True)

    def emit_open_processing(self):
        if self.latest_slice_path:
            self.open_processing_requested.emit(self.latest_slice_path)
