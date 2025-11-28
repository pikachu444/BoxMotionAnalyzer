import sys
import os
import pandas as pd
from PySide6.QtCore import QThread, Qt
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QStatusBar, QMessageBox, QFileDialog
)
import matplotlib
matplotlib.use('QtAgg')

from src.data_loader import DataLoader
from src.pipeline_controller import PipelineController
from src.analysis.parser import Parser
from src.config.data_columns import FACE_PREFIX_TO_INFO
from src.header_converter import convert_to_multi_header
from src.ui.widget_raw_data_processing import WidgetRawDataProcessing
from src.ui.widget_results_analyzer import WidgetResultsAnalyzer

class PipelineWorker(QThread):
    def __init__(self, controller, config, header_info, raw_data, parsed_data):
        super().__init__()
        self.controller = controller
        self.config = config
        self.header_info = header_info
        self.raw_data = raw_data
        self.parsed_data = parsed_data
    def run(self):
        self.controller.run_analysis(self.config, self.header_info, self.raw_data, self.parsed_data)

class MainApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Box Motion Analyzer v2.2")
        self.setGeometry(100, 100, 1200, 900)

        self.data_loader = DataLoader()
        self.parser = Parser(face_prefix_map=FACE_PREFIX_TO_INFO)
        self.pipeline_controller = PipelineController()

        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        # 1. Raw Data Processing Widget
        self.original_widget = WidgetRawDataProcessing(self.data_loader, self.parser)
        main_layout.addWidget(self.original_widget)

        # 2. Results Analyzer Widget
        self.result_widget = WidgetResultsAnalyzer(self.data_loader)
        main_layout.addWidget(self.result_widget)

        main_layout.setStretch(0, 4)
        main_layout.setStretch(1, 6)

        self.setStatusBar(QStatusBar())

    def _connect_signals(self):
        # Original Widget Signals
        self.original_widget.file_loaded.connect(self.on_file_loaded)
        self.original_widget.analysis_requested.connect(self.run_pipeline)
        self.original_widget.export_requested.connect(self.export_results)
        self.original_widget.log_message.connect(self.original_widget.append_log) # Self-logging

        # Result Widget Signals
        self.result_widget.log_message.connect(self.original_widget.append_log) # Log to original widget's console

        # Pipeline Signals
        self.pipeline_controller.log_message.connect(self.original_widget.append_log)
        self.pipeline_controller.analysis_finished.connect(self.on_analysis_finished)
        self.pipeline_controller.analysis_failed.connect(self.on_analysis_failed)

    def on_file_loaded(self, header_info, raw_data, parsed_data):
        self.header_info = header_info
        self.raw_data = raw_data
        self.parsed_data = parsed_data
        self.statusBar().showMessage("File loaded and parsed.")

    def run_pipeline(self, config):
        if not hasattr(self, 'raw_data') or self.raw_data is None:
            return
            
        self.statusBar().showMessage("Running analysis...")
        self.worker = PipelineWorker(self.pipeline_controller, config, self.header_info, self.raw_data, self.parsed_data)
        self.worker.start()

    def on_analysis_finished(self, result_df):
        self.original_widget.on_analysis_finished(not result_df.empty)
        
        if result_df.empty:
            self.statusBar().showMessage("Analysis failed.")
        else:
            self.statusBar().showMessage("Analysis complete.")
            self.final_result = result_df
            # Enable result widget interactions if needed, but mostly it loads files independently
            # However, we might want to inform the user or auto-load if that was the original behavior.
            # For now, we follow the pattern that results are exported or loaded from file.
            
    def on_analysis_failed(self, error_message):
        QMessageBox.critical(self, "Analysis Failed", f"An error occurred during analysis:\n{error_message}")
        self.original_widget.on_analysis_finished(False)
        self.statusBar().showMessage("Analysis failed.")

    def export_results(self):
        if not hasattr(self, 'final_result') or self.final_result is None or self.final_result.empty: return
        filepath, _ = QFileDialog.getSaveFileName(self, "Export Results to CSV", "", "CSV Files (*.csv)")
        if filepath:
            try:
                export_df = convert_to_multi_header(self.final_result)
                export_df.to_csv(filepath, index=False)
                self.statusBar().showMessage(f"Results successfully exported to {filepath}")
                self.original_widget.append_log(f"[INFO] Results exported to {filepath}")
            except Exception as e:
                self.statusBar().showMessage(f"Error exporting file: {e}")
                self.original_widget.append_log(f"[ERROR] Could not export file: {e}")

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MainApp()
    window.show()
    sys.exit(app.exec())
