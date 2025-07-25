import sys
from PySide6.QtCore import QThread
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QLineEdit, QComboBox, QTextEdit, QStatusBar, QGridLayout,
    QFileDialog, QListWidget, QScrollArea, QCheckBox, QGroupBox
)
import matplotlib
matplotlib.use('QtAgg')
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qtagg import NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure
from data_loader import DataLoader
from plot_manager import PlotManager
from pipeline_controller import PipelineController

class PipelineWorker(QThread):
    def __init__(self, controller, config, raw_data):
        super().__init__()
        self.controller = controller
        self.config = config
        self.raw_data = raw_data
    def run(self):
        self.controller.run_analysis(self.config, self.raw_data)

class MainApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Box Motion Analyzer v1.0 (Matplotlib)")
        self.setGeometry(100, 100, 1200, 800)
        self.data_loader = DataLoader()
        self.pipeline_controller = PipelineController()
        self.raw_data = None
        self.final_result = None
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        top_layout = QHBoxLayout()
        self.fig = Figure(figsize=(5, 4), dpi=100)
        self.canvas = FigureCanvas(self.fig)
        self.toolbar = NavigationToolbar(self.canvas, self)
        plot_container = QWidget()
        plot_layout = QVBoxLayout(plot_container)
        plot_layout.setContentsMargins(0,0,0,0)
        plot_layout.addWidget(self.toolbar)
        plot_layout.addWidget(self.canvas)
        top_layout.addWidget(plot_container, 7)
        self.plot_manager = PlotManager(self.canvas, self.fig)
        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setPlaceholderText("[INFO] Waiting for analysis...")
        top_layout.addWidget(self.log_output, 3)
        main_layout.addLayout(top_layout, 7)
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        bottom_widget = QWidget()
        bottom_layout = QGridLayout(bottom_widget)

        self.load_csv_button = QPushButton("Load CSV File...")
        bottom_layout.addWidget(self.load_csv_button, 0, 0, 1, 7)
        self.file_path_label = QLabel("No file selected.")
        bottom_layout.addWidget(self.file_path_label, 1, 0, 1, 7)

        plot_options_group = QGroupBox("Plot Options")
        plot_options_layout = QGridLayout(plot_options_group)
        plot_options_layout.addWidget(QLabel("Data:"), 0, 0)
        self.list_plot_data = QListWidget()
        self.list_plot_data.setSelectionMode(QListWidget.SelectionMode.MultiSelection)
        plot_options_layout.addWidget(self.list_plot_data, 1, 0, 1, 2)
        plot_options_layout.addWidget(QLabel("Axis:"), 0, 2)
        self.combo_plot_axis = QComboBox()
        self.combo_plot_axis.addItems(["Position-X", "Position-Y", "Position-Z"])
        plot_options_layout.addWidget(self.combo_plot_axis, 1, 2)
        bottom_layout.addWidget(plot_options_group, 2, 0, 1, 3)

        self.slice_group = QGroupBox("Slice Range")
        self.slice_group.setCheckable(True)
        self.slice_group.setChecked(False)
        slice_group_layout = QGridLayout(self.slice_group)
        slice_group_layout.addWidget(QLabel("Start:"), 0, 0)
        self.le_slice_start = QLineEdit()
        slice_group_layout.addWidget(self.le_slice_start, 0, 1)
        slice_group_layout.addWidget(QLabel("End:"), 1, 0)
        self.le_slice_end = QLineEdit()
        slice_group_layout.addWidget(self.le_slice_end, 1, 1)
        bottom_layout.addWidget(self.slice_group, 2, 3, 1, 2)

        box_dims_group = QGroupBox("Box Dimensions (mm)")
        box_dims_layout = QGridLayout(box_dims_group)
        box_dims_layout.addWidget(QLabel("L:"), 0, 0)
        self.le_box_l = QLineEdit("1578.0")
        box_dims_layout.addWidget(self.le_box_l, 0, 1)
        box_dims_layout.addWidget(QLabel("W:"), 1, 0)
        self.le_box_w = QLineEdit("930.0")
        box_dims_layout.addWidget(self.le_box_w, 1, 1)
        box_dims_layout.addWidget(QLabel("H:"), 2, 0)
        self.le_box_h = QLineEdit("142.0")
        box_dims_layout.addWidget(self.le_box_h, 2, 1)
        bottom_layout.addWidget(box_dims_group, 2, 5, 1, 2)

        run_button_layout = QHBoxLayout()
        self.run_button = QPushButton("Run Analysis")
        self.export_button = QPushButton("Export Results to CSV")
        self.export_button.setEnabled(False)
        run_button_layout.addStretch()
        run_button_layout.addWidget(self.run_button)
        run_button_layout.addWidget(self.export_button)
        bottom_layout.addLayout(run_button_layout, 3, 0, 1, 7)

        scroll_area.setWidget(bottom_widget)
        main_layout.addWidget(scroll_area, 3)
        self.setStatusBar(QStatusBar())
        self.statusBar().showMessage("Ready")

        self.load_csv_button.clicked.connect(self.open_csv_file)
        self.run_button.clicked.connect(self.run_pipeline)
        self.export_button.clicked.connect(self.export_results)
        self.list_plot_data.itemSelectionChanged.connect(self.update_plot)
        self.combo_plot_axis.currentIndexChanged.connect(self.update_plot)
        self.plot_manager.region_changed_signal.connect(self.on_region_changed)
        self.pipeline_controller.log_message.connect(self.log_output.append)
        self.pipeline_controller.analysis_finished.connect(self.on_analysis_finished)
        self.slice_group.toggled.connect(self.toggle_slicing_widgets)

        self.toggle_slicing_widgets(False)

    def toggle_slicing_widgets(self, is_checked):
        self.plot_manager.set_selector_active(is_checked)

    def open_csv_file(self):
        filepath, _ = QFileDialog.getOpenFileName(self, "Select CSV File", "", "CSV Files (*.csv)")
        if filepath:
            try:
                self.raw_data = self.data_loader.load_csv(filepath)
                self.file_path_label.setText(filepath)
                self.statusBar().showMessage("File loaded successfully.")
                self.log_output.append(f"[INFO] Successfully loaded {filepath}")

                plottable_targets = self.data_loader.get_plottable_targets(self.raw_data)
                self.list_plot_data.clear()
                self.list_plot_data.addItems(plottable_targets)

                if self.list_plot_data.count() > 0:
                    self.list_plot_data.item(0).setSelected(True)

                self.update_plot()
                self.plot_manager.enable_interactions(self.raw_data)
            except Exception as e:
                self.statusBar().showMessage("File load failed.")
                self.log_output.append(f"[ERROR] Failed to load file: {e}")

    def on_region_changed(self, min_x, max_x):
        self.le_slice_start.setText(f"{min_x:.2f}")
        self.le_slice_end.setText(f"{max_x:.2f}")

    def update_plot(self):
        if self.raw_data is None or self.raw_data.empty: return
        selected_items = self.list_plot_data.selectedItems()
        target_names = [item.text() for item in selected_items]
        axis_text = self.combo_plot_axis.currentText()
        if not target_names or not axis_text:
            self.plot_manager.ax.clear()
            self.plot_manager.canvas.draw()
            return
        self.plot_manager.draw_plot(self.raw_data, target_names, axis_text)

    def run_pipeline(self):
        if self.raw_data is None or self.raw_data.empty:
            self.log_output.append("[ERROR] No data loaded. Please load a CSV file first.")
            return
        try:
            if self.slice_group.isChecked():
                slice_start = float(self.le_slice_start.text())
                slice_end = float(self.le_slice_end.text())
            else:
                slice_start = self.raw_data.index.min()
                slice_end = self.raw_data.index.max()

            config = {
                'slice_time_start': slice_start,
                'slice_time_end': slice_end,
                'box_dimensions': (
                    float(self.le_box_l.text()),
                    float(self.le_box_w.text()),
                    float(self.le_box_h.text())
                )
            }
        except ValueError:
            self.log_output.append("[ERROR] Invalid number in 'Slice Range' or 'Box Dimensions'.")
            return

        self.run_button.setEnabled(False)
        self.export_button.setEnabled(False)
        self.statusBar().showMessage("Running analysis...")

        self.worker = PipelineWorker(self.pipeline_controller, config, self.raw_data)
        self.worker.start()

    def on_analysis_finished(self, result_df):
        self.final_result = result_df
        if not result_df.empty:
            self.statusBar().showMessage("Analysis complete.")
            self.export_button.setEnabled(True)
        else:
            self.statusBar().showMessage("Analysis failed.")
        self.run_button.setEnabled(True)

    def export_results(self):
        if self.final_result is None or self.final_result.empty:
            self.log_output.append("[ERROR] No analysis results to export.")
            return
        filepath, _ = QFileDialog.getSaveFileName(self, "Save Results", "analysis_results.csv", "CSV Files (*.csv)")
        if filepath:
            try:
                self.final_result.to_csv(filepath, index=True, float_format='%.8f')
                self.statusBar().showMessage("Results saved successfully.")
                self.log_output.append(f"[INFO] Results successfully saved to {filepath}")
            except Exception as e:
                self.statusBar().showMessage("Failed to save results.")
                self.log_output.append(f"[ERROR] Error saving file: {e}")

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MainApp()
    window.show()
    sys.exit(app.exec())
