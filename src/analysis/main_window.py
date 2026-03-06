import sys
import pandas as pd
from PySide6.QtCore import QThread
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QStatusBar, QMessageBox, QFileDialog, QTabWidget
)
import matplotlib
try:
    matplotlib.use('QtAgg')
except ImportError:
    pass

from src.analysis.core.data_loader import DataLoader
from src.analysis.core.pipeline_controller import PipelineController
from src.analysis.parser import Parser
from src.config.data_columns import FACE_PREFIX_TO_INFO, TimelineMetaCols
from src.utils.header_converter import convert_to_multi_header
from src.analysis.ui.widget_raw_data_processing import WidgetRawDataProcessing
from src.analysis.ui.widget_results_analyzer import WidgetResultsAnalyzer


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

        self.final_result = None
        self.last_analysis_context = {
            'full_start_sec': None,
            'full_end_sec': None,
            'slice_start_sec': None,
            'slice_end_sec': None,
        }

        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        self.tab_widget = QTabWidget()
        main_layout.addWidget(self.tab_widget)

        self.original_widget = WidgetRawDataProcessing(self.data_loader, self.parser)
        self.result_widget = WidgetResultsAnalyzer(self.data_loader)

        self.tab_widget.addTab(self.original_widget, "Step 1: Raw Data Processing")
        self.tab_widget.addTab(self.result_widget, "Step 2: Results Analysis")

        self.setStatusBar(QStatusBar())

    def _connect_signals(self):
        self.original_widget.file_loaded.connect(self.on_file_loaded)
        self.original_widget.analysis_requested.connect(self.run_pipeline)
        self.original_widget.export_requested.connect(self.export_results)
        self.original_widget.log_message.connect(self.original_widget.append_log)

        self.result_widget.log_message.connect(self.original_widget.append_log)

        self.pipeline_controller.log_message.connect(self.original_widget.append_log)
        self.pipeline_controller.analysis_finished.connect(self.on_analysis_finished)
        self.pipeline_controller.analysis_failed.connect(self.on_analysis_failed)

    def on_file_loaded(self, header_info, raw_data, parsed_data):
        self.header_info = header_info
        self.raw_data = raw_data
        self.parsed_data = parsed_data

        if parsed_data is not None and not parsed_data.empty:
            try:
                self.last_analysis_context['full_start_sec'] = float(parsed_data.index.min())
                self.last_analysis_context['full_end_sec'] = float(parsed_data.index.max())
            except Exception:
                self.last_analysis_context['full_start_sec'] = None
                self.last_analysis_context['full_end_sec'] = None

        self.statusBar().showMessage("File loaded and parsed.")

    def run_pipeline(self, config):
        if not hasattr(self, 'raw_data') or self.raw_data is None:
            return

        self.last_analysis_context['slice_start_sec'] = config.get('slice_start_val')
        self.last_analysis_context['slice_end_sec'] = config.get('slice_end_val')

        self.statusBar().showMessage("Running analysis...")
        self.worker = PipelineWorker(self.pipeline_controller, config, self.header_info, self.raw_data, self.parsed_data)
        self.worker.start()

    def on_analysis_finished(self, result_df):
        self.original_widget.on_analysis_finished(not result_df.empty)

        if result_df.empty:
            self.statusBar().showMessage("Analysis failed.")
            return

        self.statusBar().showMessage("Analysis complete.")
        self.final_result = result_df

    def on_analysis_failed(self, error_message):
        QMessageBox.critical(self, "Analysis Failed", f"An error occurred during analysis:\n{error_message}")
        self.original_widget.on_analysis_finished(False)
        self.statusBar().showMessage("Analysis failed.")

    def _add_timeline_context_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        export_df = df.copy()

        full_start = self.last_analysis_context.get('full_start_sec')
        full_end = self.last_analysis_context.get('full_end_sec')
        slice_start = self.last_analysis_context.get('slice_start_sec')
        slice_end = self.last_analysis_context.get('slice_end_sec')

        export_df[TimelineMetaCols.FULL_START_SEC] = full_start
        export_df[TimelineMetaCols.FULL_END_SEC] = full_end
        export_df[TimelineMetaCols.SLICE_START_SEC] = slice_start
        export_df[TimelineMetaCols.SLICE_END_SEC] = slice_end
        return export_df

    def export_results(self):
        if self.final_result is None or self.final_result.empty:
            return

        filepath, _ = QFileDialog.getSaveFileName(self, "Export Results to CSV", "", "CSV Files (*.csv)")
        if not filepath:
            return

        try:
            export_source_df = self._add_timeline_context_columns(self.final_result)
            export_df = convert_to_multi_header(export_source_df)
            export_df.to_csv(filepath, index=False)

            self.statusBar().showMessage(f"Results successfully exported to {filepath}")
            self.original_widget.append_log(f"[INFO] Results exported to {filepath}")

            self.result_widget.load_result_file(filepath)
            self.tab_widget.setCurrentWidget(self.result_widget)

        except Exception as e:
            self.statusBar().showMessage(f"Error exporting file: {e}")
            self.original_widget.append_log(f"[ERROR] Could not export file: {e}")


if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MainApp()
    window.show()
    sys.exit(app.exec())
