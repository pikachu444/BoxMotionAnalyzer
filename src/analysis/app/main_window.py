import sys
from PySide6.QtCore import QThread, QSize, Qt
from shiboken6 import isValid
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


class AnalysisTabs(QTabWidget):
    """Hidden processing/results pages must not enlarge the Step 1 window."""
    def minimumSizeHint(self):
        page = self.currentWidget()
        if page is None:
            return super().minimumSizeHint()
        return page.minimumSizeHint() + QSize(4, self.tabBar().sizeHint().height() + 4)


class MainApp(QMainWindow):
    def closeEvent(self, event):
        scene_worker = self.original_widget.scene_worker
        if scene_worker is not None and scene_worker.isRunning():
            scene_worker.requestInterruption()
            event.ignore()
            self.statusBar().showMessage('Cancelling scene detection...')
            return
        worker = self.original_widget.review_worker
        if worker is not None and worker.isRunning():
            event.ignore()
            self.statusBar().showMessage('Wait for marker review calculation before closing.')
            return
        processing_worker = getattr(self, 'worker', None)
        if processing_worker is not None and processing_worker.isRunning():
            event.ignore()
            self.statusBar().showMessage('Wait for processing to finish before closing.')
            return
        if self.processing_widget.single_running:
            event.ignore()
            self.statusBar().showMessage('Wait for the processing result before closing.')
            return
        if self.processing_widget.batch_running:
            event.ignore()
            self.statusBar().showMessage('Wait for batch processing to finish before closing.')
            return
        super().closeEvent(event)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Box Motion Analyzer v2.2")
        self.setWindowIcon(get_window_icon())
        self.resize(1200, 760)
        self.comparison_opener = None
        self.comparison_window = None

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

        self.tab_widget = AnalysisTabs()
        self.tab_widget.currentChanged.connect(lambda _: self.tab_widget.updateGeometry())
        main_layout.addWidget(self.tab_widget)

        self.original_widget = WidgetRawDataProcessing(self.data_loader, self.parser)
        self.processing_widget = WidgetSliceProcessing(self.data_loader, self.parser)
        self.result_widget = WidgetResultsAnalyzer(self.data_loader)

        self.tab_widget.addTab(self.original_widget, "Step 1: Scenes")
        self.tab_widget.addTab(self.processing_widget, "Step 1.5: Process")
        self.tab_widget.addTab(self.result_widget, "Step 2: Results")

        self.setStatusBar(QStatusBar())

    def _connect_signals(self):
        self.original_widget.file_loaded.connect(self.on_file_loaded)
        self.original_widget.slice_saved.connect(self.on_slice_saved)
        self.original_widget.process_requested.connect(self.process_saved_scenes)
        self.original_widget.log_message.connect(self.original_widget.append_log)

        self.result_widget.log_message.connect(self.original_widget.append_log)
        self.result_widget.log_message.connect(self.processing_widget.append_log)
        self.result_widget.log_message.connect(
            lambda message: self.statusBar().showMessage(message.split('] ', 1)[-1])
        )
        self.processing_widget.processing_requested.connect(self.run_processing_pipeline)
        self.processing_widget.results_ready.connect(self.view_saved_results)
        self.result_widget.compare_requested.connect(self.open_comparison)
        self.processing_widget.log_message.connect(self.processing_widget.append_log)
        for widget in (self.original_widget, self.processing_widget):
            widget.log_message.connect(
                lambda message: self.statusBar().showMessage(message.split('] ', 1)[-1]))

        self.pipeline_controller.log_message.connect(self.processing_widget.append_log)
        self.pipeline_controller.analysis_finished.connect(self._receive_processing_result)
        self.pipeline_controller.analysis_failed.connect(self._receive_processing_error)

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

    def process_saved_scenes(self):
        worker = getattr(self, 'worker', None)
        if worker is not None and worker.isRunning():
            self.statusBar().showMessage('Processing is still running.')
            return
        session = self.original_widget.scene_session
        included_count = sum(row['decision'] == 'include' for row in session.rows) if session else 1
        if not self.processing_widget.prepare_for_input_change(replace_single=included_count <= 1):
            return
        paths = self.original_widget.save_for_processing()
        if paths and self.processing_widget.load_processing_inputs(paths, confirm=False):
            self.tab_widget.setCurrentWidget(self.processing_widget)
            self.statusBar().showMessage('Ready to process.')

    def view_saved_results(self, paths):
        if self.result_widget.open_result_files(paths):
            self.tab_widget.setCurrentWidget(self.result_widget)

    def open_comparison(self, paths):
        if self.comparison_opener is not None:
            self.comparison_opener(paths)
            return
        from src.analysis.compare.main_window import CompareMainWindow
        window = self.comparison_window
        if window is None or not isValid(window) or not window.isVisible():
            window = CompareMainWindow()
            window.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
            self.comparison_window = window
        if window.isMinimized():
            window.showNormal()
        else:
            window.show()
        window.raise_()
        window.activateWindow()
        window.load_result_files(paths, deduplicate=True)

    def run_processing_pipeline(self, config, header_info, raw_data, parsed_data, timeline_context):
        if parsed_data is None:
            return

        if getattr(self, 'worker', None) is not None and self.worker.isRunning():
            return
        from copy import deepcopy
        self.processing_timeline_context = deepcopy(timeline_context or {})
        self.processing_outcome = None
        self.statusBar().showMessage("Running processing...")
        self.worker = PipelineWorker(
            self.pipeline_controller,
            config,
            header_info,
            raw_data,
            parsed_data,
            use_parsed_only=True,
        )
        self.worker.finished.connect(self._complete_processing)
        self.worker.start()

    def _receive_processing_result(self, result_df):
        self.processing_outcome = ('result', result_df)

    def _receive_processing_error(self, error_message):
        self.processing_outcome = ('error', error_message)

    def _complete_processing(self):
        # A controller result signal can arrive before QThread.run returns.
        # Release inputs and Run only after the worker has actually stopped.
        outcome = self.processing_outcome
        self.processing_outcome = None
        if outcome is None:
            self.on_processing_failed('Processing ended without a result.')
        elif outcome[0] == 'error':
            self.on_processing_failed(outcome[1])
        else:
            self.on_processing_finished(outcome[1])

    def on_processing_finished(self, result_df):
        if result_df.empty:
            self.processing_widget.on_processing_finished(result_df)
            self.statusBar().showMessage("Processing failed.")
            return

        processed_with_context = add_timeline_context_columns(result_df, self.processing_timeline_context)
        self.processing_widget.on_processing_finished(processed_with_context)
        self.statusBar().showMessage("Processing complete.")

    def on_processing_failed(self, error_message):
        QMessageBox.critical(self, "Processing Failed", f"An error occurred during processing:\n{error_message}")
        self.processing_widget.on_processing_failed()
        self.statusBar().showMessage("Processing failed.")


if __name__ == '__main__':
    app = QApplication(sys.argv)
    configure_qt_application(app)
    window = MainApp()
    window.show()
    sys.exit(app.exec())
