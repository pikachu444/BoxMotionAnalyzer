import sys
from PySide6.QtCore import QThread
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QStatusBar, QMessageBox, QTabWidget
)
import matplotlib
try:
    matplotlib.use('QtAgg')
except ImportError:
    pass

from src.analysis.pipeline.data_loader import DataLoader
from src.analysis.pipeline.artifact_io import add_timeline_context_columns
from src.analysis.pipeline.pipeline_controller import PipelineController
from src.analysis.pipeline.parser import Parser
from src.config.data_columns import FACE_PREFIX_TO_INFO
from src.utils.app_identity import configure_qt_application, get_window_icon
from src.analysis.ui.widget_raw_data_processing import WidgetRawDataProcessing
from src.analysis.ui.widget_slice_processing import WidgetSliceProcessing
from src.analysis.ui.widget_results_analyzer import WidgetResultsAnalyzer


class PipelineWorker(QThread):
    def __init__(self, controller, config, header_info, raw_data, parsed_data, use_parsed_only=False):
        super().__init__()
        self.controller = controller
        self.config = config
        self.header_info = header_info
        self.raw_data = raw_data
        self.parsed_data = parsed_data
        self.use_parsed_only = use_parsed_only

    def run(self):
        if self.use_parsed_only:
            self.controller.run_analysis_from_parsed(self.config, self.parsed_data)
        else:
            self.controller.run_analysis(self.config, self.header_info, self.raw_data, self.parsed_data)


class MainApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Box Motion Analyzer v2.2")
        self.setWindowIcon(get_window_icon())
        self.setGeometry(100, 100, 1200, 900)

        self.data_loader = DataLoader()
        self.parser = Parser(face_prefix_map=FACE_PREFIX_TO_INFO)
        self.pipeline_controller = PipelineController()

        self.current_timeline_context = {
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
        self.processing_widget = WidgetSliceProcessing(self.data_loader, self.parser)
        self.result_widget = WidgetResultsAnalyzer(self.data_loader)

        self.tab_widget.addTab(self.original_widget, "Step 1: Raw Data Slice")
        self.tab_widget.addTab(self.processing_widget, "Step 1.5: Slice Processing")
        self.tab_widget.addTab(self.result_widget, "Step 2: Results Analysis")

        self.setStatusBar(QStatusBar())

    def _connect_signals(self):
        self.original_widget.file_loaded.connect(self.on_file_loaded)
        self.original_widget.slice_saved.connect(self.on_slice_saved)
        self.original_widget.open_processing_requested.connect(self.open_slice_in_processing)
        self.original_widget.log_message.connect(self.original_widget.append_log)

        self.result_widget.log_message.connect(self.original_widget.append_log)
        self.result_widget.log_message.connect(self.processing_widget.append_log)
        self.processing_widget.processing_requested.connect(self.run_processing_pipeline)
        self.processing_widget.open_results_requested.connect(self.open_processed_result_in_step2)
        self.processing_widget.log_message.connect(self.processing_widget.append_log)

        self.pipeline_controller.log_message.connect(self.processing_widget.append_log)
        self.pipeline_controller.analysis_finished.connect(self.on_processing_finished)
        self.pipeline_controller.analysis_failed.connect(self.on_processing_failed)

    def on_file_loaded(self, header_info, raw_data, parsed_data):
        self.header_info = header_info
        self.raw_data = raw_data
        self.parsed_data = parsed_data

        if parsed_data is not None and not parsed_data.empty:
            try:
                self.current_timeline_context['full_start_sec'] = float(parsed_data.index.min())
                self.current_timeline_context['full_end_sec'] = float(parsed_data.index.max())
            except Exception:
                self.current_timeline_context['full_start_sec'] = None
                self.current_timeline_context['full_end_sec'] = None

        self.statusBar().showMessage("File loaded and parsed.")

    def on_slice_saved(self, slice_path):
        self.statusBar().showMessage(f"Scene slice saved: {slice_path}")

    def open_slice_in_processing(self, slice_path):
        self.processing_widget.load_slice_file(slice_path)
        self.tab_widget.setCurrentWidget(self.processing_widget)
        self.statusBar().showMessage(f"Slice loaded into Step 1.5: {slice_path}")

    def run_processing_pipeline(self, config, header_info, raw_data, parsed_data, timeline_context):
        if parsed_data is None:
            return

        self.current_timeline_context = dict(timeline_context or {})
        self.statusBar().showMessage("Running processing...")
        self.worker = PipelineWorker(
            self.pipeline_controller,
            config,
            header_info,
            raw_data,
            parsed_data,
            use_parsed_only=True,
        )
        self.worker.start()

    def on_processing_finished(self, result_df):
        if result_df.empty:
            self.processing_widget.on_processing_finished(result_df)
            self.statusBar().showMessage("Processing failed.")
            return

        processed_with_context = add_timeline_context_columns(result_df, self.current_timeline_context)
        self.processing_widget.on_processing_finished(processed_with_context)
        self.statusBar().showMessage("Processing complete.")

    def on_processing_failed(self, error_message):
        QMessageBox.critical(self, "Processing Failed", f"An error occurred during processing:\n{error_message}")
        self.processing_widget.on_processing_failed()
        self.statusBar().showMessage("Processing failed.")

    def open_processed_result_in_step2(self, result_path):
        if self.result_widget.load_result_file(result_path):
            self.tab_widget.setCurrentWidget(self.result_widget)
            self.statusBar().showMessage("Processed result opened in Step 2.")


if __name__ == '__main__':
    app = QApplication(sys.argv)
    configure_qt_application(app)
    window = MainApp()
    window.show()
    sys.exit(app.exec())
