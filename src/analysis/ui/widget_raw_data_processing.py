import os
from PySide6.QtCore import Signal, Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QLineEdit, QComboBox, QTextEdit, QGroupBox, QGridLayout, QFileDialog, QRadioButton
)
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qtagg import NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure

from src.analysis.ui.plot_manager import PlotManager
from src.analysis.ui.data_selection_dialog import DataSelectionDialog
from src.analysis.ui.dialog_processing_settings import ProcessingSettingsDialog
from src.config import config_app, config_analysis_ui
from src.config.data_columns import (
    PoseCols, RawMarkerCols, DisplayNames, RigidBodyCols
)

class WidgetRawDataProcessing(QWidget):
    # Signals to communicate with MainApp
    file_loaded = Signal(dict, object, object) # header_info, raw_data, parsed_data
    analysis_requested = Signal(dict) # config
    export_requested = Signal()
    log_message = Signal(str)

    def __init__(self, data_loader, parser):
        super().__init__()
        self.data_loader = data_loader
        self.parser = parser
        
        self.raw_data = None
        self.header_info = None
        self.parsed_data = None
        self.current_selected_targets = []
        self.current_processing_mode = config_analysis_ui.PROCESSING_MODE_STANDARD
        self.advanced_processing_options = config_analysis_ui.get_default_advanced_options()

        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        
        group_box = QGroupBox("Raw Data Processing")
        group_layout = QVBoxLayout(group_box)

        # 1a. Top Layout: Plot and Right Panel
        top_layout = QHBoxLayout()

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

        self.plot_manager = PlotManager(self.canvas, self.fig)
        self.plot_manager.ax.text(0.5, 0.5, "Load a CSV file to start.", ha='center', va='center')
        self.plot_manager.canvas.draw()

        # Right Panel
        right_panel_layout = QVBoxLayout()
        self.load_csv_button = QPushButton("Load CSV File...")
        self.file_path_label = QLabel("No file selected.")
        
        right_panel_layout.addWidget(self.load_csv_button)
        right_panel_layout.addWidget(self.file_path_label)

        # Box Dimensions
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

        # Log Output (Local to this widget for immediate feedback, or shared?)
        # The plan says "Encapsulates...". MainApp has a log output. 
        # But OriginalAnalysisWidget needs to show logs too?
        # In the original UI, the log output was in the right panel of Original Analysis.
        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setPlaceholderText("[INFO] Load a CSV file to start.")
        right_panel_layout.addWidget(self.log_output)

        top_layout.addWidget(plot_container, 8)
        top_layout.addLayout(right_panel_layout, 2)
        group_layout.addLayout(top_layout)

        # 1b. Bottom Controls
        controls_widget = QWidget()
        h_controls_layout = QHBoxLayout(controls_widget)

        # Plot Options
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

        # Slice Range
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

        processing_group = QGroupBox(config_analysis_ui.PROCESSING_MODE_GROUP_TITLE)
        processing_layout = QVBoxLayout(processing_group)

        radio_row = QHBoxLayout()
        self.rb_processing_standard = QRadioButton(
            config_analysis_ui.PROCESSING_MODE_LABELS[config_analysis_ui.PROCESSING_MODE_STANDARD]
        )
        self.rb_processing_standard.setChecked(True)
        self.rb_processing_raw = QRadioButton(
            config_analysis_ui.PROCESSING_MODE_LABELS[config_analysis_ui.PROCESSING_MODE_RAW]
        )
        self.rb_processing_advanced = QRadioButton(
            config_analysis_ui.PROCESSING_MODE_LABELS[config_analysis_ui.PROCESSING_MODE_ADVANCED]
        )
        radio_row.addWidget(self.rb_processing_standard)
        radio_row.addWidget(self.rb_processing_raw)
        radio_row.addWidget(self.rb_processing_advanced)
        radio_row.addStretch()

        self.processing_settings_button = QPushButton(config_analysis_ui.ADVANCED_BUTTON_TEXT)
        self.processing_settings_button.setEnabled(False)
        radio_row.addWidget(self.processing_settings_button)
        processing_layout.addLayout(radio_row)

        self.processing_mode_description = QLabel()
        self.processing_mode_description.setWordWrap(True)
        self.processing_mode_description.setStyleSheet("color: #4a5568;")
        processing_layout.addWidget(self.processing_mode_description)
        h_controls_layout.addWidget(processing_group)

        # Run/Export Buttons
        run_button_layout = QVBoxLayout()
        self.run_button = QPushButton("Run Analysis")
        self.export_button = QPushButton("Export Results to CSV")
        self.export_button.setEnabled(False)
        run_button_layout.addWidget(self.run_button)
        run_button_layout.addWidget(self.export_button)
        h_controls_layout.addLayout(run_button_layout)

        group_layout.addWidget(controls_widget)
        layout.addWidget(group_box)

    def _connect_signals(self):
        self.load_csv_button.clicked.connect(self.open_csv_file)
        self.select_data_button.clicked.connect(self.open_data_selection_dialog)
        self.run_button.clicked.connect(self.emit_run_analysis)
        self.export_button.clicked.connect(self.export_requested.emit)
        self.combo_plot_axis.currentIndexChanged.connect(self.update_plot)
        self.plot_manager.region_changed_signal.connect(self.on_region_changed)
        self.slice_group.toggled.connect(self.toggle_slicing_widgets)
        self.le_slice_start.editingFinished.connect(self.update_span_selector_from_inputs)
        self.le_slice_end.editingFinished.connect(self.update_span_selector_from_inputs)
        self.rb_processing_standard.toggled.connect(self._on_processing_mode_changed)
        self.rb_processing_raw.toggled.connect(self._on_processing_mode_changed)
        self.rb_processing_advanced.toggled.connect(self._on_processing_mode_changed)
        self.processing_settings_button.clicked.connect(self.open_processing_settings_dialog)
        self._update_processing_mode_ui()

    def append_log(self, message):
        self.log_output.append(message)

    def open_csv_file(self):
        filepath, _ = QFileDialog.getOpenFileName(self, "Select CSV File", "", "CSV Files (*.csv)")
        if filepath:
            try:
                self.header_info, self.raw_data = self.data_loader.load_csv(filepath)
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
                self.export_button.setEnabled(False)
                
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

    def emit_run_analysis(self):
        if self.raw_data is None: return
        try:
            # Update box dimensions globally
            l = float(self.le_box_l.text())
            w = float(self.le_box_w.text())
            h = float(self.le_box_h.text())
            config_app.BOX_DIMS = [l, w, h]

            config = {
                'slice_filter_by': 'time',
                'slice_start_val': float(self.le_slice_start.text()) if self.slice_group.isChecked() else self.parsed_data.index.min(),
                'slice_end_val': float(self.le_slice_end.text()) if self.slice_group.isChecked() else self.parsed_data.index.max(),
                'processing_mode': self.current_processing_mode,
                'analysis_options': self._build_analysis_overrides(),
            }
            self.analysis_requested.emit(config)
            self.run_button.setEnabled(False)
            self.export_button.setEnabled(False)
            self.log_output.clear()
            self.append_log("[INFO] Starting analysis...")
            
        except Exception as e:
            self.append_log(f"[ERROR] Invalid configuration: {e}")

    def on_analysis_finished(self, success: bool):
        self.run_button.setEnabled(True)
        self.export_button.setEnabled(success)
        if success:
            self.append_log("[INFO] Analysis completed successfully.")
        else:
            self.append_log("[ERROR] Analysis failed.")
