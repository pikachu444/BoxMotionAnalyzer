"""Unit-GUI lifecycle contracts; the controller body is held, no Raw analysis runs."""
from threading import Event

import pandas as pd
import pytest
from PySide6.QtCore import QCoreApplication, QEvent, QObject, Signal, QTimer
from PySide6.QtWidgets import QApplication, QMainWindow, QFileDialog, QMessageBox
from shiboken6 import isValid

from src.analysis.app.main_window import MainApp, PipelineWorker


def _running_processing(window, monkeypatch):
    started, release = Event(), Event()

    def held_analysis(config, parsed):
        started.set()
        release.wait(5.)

    monkeypatch.setattr(window.pipeline_controller, 'run_analysis_from_parsed', held_analysis)
    window.run_processing_pipeline({}, None, None, pd.DataFrame({'value': [1.]}, index=[0.]), {})
    worker = window.worker
    try:
        assert isinstance(worker, PipelineWorker)
        assert started.wait(2.)
        assert worker.isRunning()
    except BaseException:
        release.set()
        worker.wait(5000)
        raise
    return worker, release


def test_processing_worker_defers_close_until_finished(monkeypatch):
    app = QApplication.instance() or QApplication([])
    window = MainApp()
    worker = release = None
    try:
        window.show()
        app.processEvents()
        worker, release = _running_processing(window, monkeypatch)
        assert window.close() is False
        assert window.isVisible()
        assert worker.isRunning()
        assert window.worker is worker
        assert window.statusBar().currentMessage() == 'Wait for processing to finish before closing.'
        release.set()
        assert worker.wait(5000)
        app.processEvents()
        assert window.close() is True
        assert not window.isVisible()
    finally:
        if release is not None:
            release.set()
        if worker is not None:
            assert worker.wait(5000)
        window.close()
        window.deleteLater()
        app.processEvents()


def test_launcher_keeps_open_processing_window_during_and_after_processing(monkeypatch):
    from src import launcher as launcher_module
    app = QApplication.instance() or QApplication([])
    launcher = launcher_module.LauncherWindow()
    original = MainApp()
    replacements = []
    worker = release = None

    def new_processing_window():
        window = MainApp()
        replacements.append(window)
        return window

    monkeypatch.setattr(launcher_module, 'MainApp', new_processing_window)
    launcher.data_processing_window = original
    try:
        original.show()
        app.processEvents()
        worker, release = _running_processing(original, monkeypatch)
        launcher.open_data_processing()
        assert launcher.data_processing_window is original
        assert replacements == []
        assert original.isVisible() and worker.isRunning()
        release.set()
        assert worker.wait(5000)
        app.processEvents()
        launcher.open_data_processing()
        # Reopening is navigation, not permission to discard the completed work.
        assert replacements == []
        assert launcher.data_processing_window is original
        assert original.isVisible()
    finally:
        if release is not None:
            release.set()
        if worker is not None:
            assert worker.wait(5000)
        for window in [original, *replacements, launcher]:
            window.close()
            window.deleteLater()
        app.processEvents()


@pytest.mark.parametrize('attribute,factory_name,open_method', [
    ('data_processing_window', 'MainApp', 'open_data_processing'),
    ('comparison_window', 'CompareMainWindow', 'open_comparison'),
    ('simulation_window', 'SimulationUI', 'open_simulation'),
])
def test_launcher_restores_minimized_and_recreates_closed_windows(
        monkeypatch, attribute, factory_name, open_method):
    """The test window records destructive close like the comparison VTK owner."""
    from src import launcher as launcher_module
    app = QApplication.instance() or QApplication([])
    created = []

    class WorkWindow(QMainWindow):
        def __init__(self):
            super().__init__()
            self.work = object()
            self.cleaned = False
            created.append(self)

        def closeEvent(self, event):
            self.cleaned = True
            super().closeEvent(event)

    monkeypatch.setattr(launcher_module, factory_name, WorkWindow)
    launcher = launcher_module.LauncherWindow()
    open_window = getattr(launcher, open_method)
    try:
        open_window()
        original = getattr(launcher, attribute)
        work = original.work
        original.showMinimized()
        app.processEvents()
        open_window()
        assert getattr(launcher, attribute) is original
        assert original.work is work and not original.cleaned
        assert original.isVisible() and not original.isMinimized()
        # Reopen immediately, before deferred destruction, must not revive a
        # comparison window whose viewers were cleaned in closeEvent.
        original.close()
        assert original.cleaned
        open_window()
        replacement = getattr(launcher, attribute)
        assert replacement is not original and replacement.isVisible()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        assert not isValid(original)
        assert getattr(launcher, attribute) is replacement
        replacement.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        assert getattr(launcher, attribute) is None
        open_window()
        assert len(created) == 3
    finally:
        for window in created:
            if isValid(window):
                window.close()
        launcher.close()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)


def test_simulation_keeps_window_and_worker_until_completion_callback(monkeypatch, tmp_path):
    """Hold the real UI worker; no physics simulation or output file is produced."""
    from src import launcher as launcher_module
    from src.simulation.ui import main_window as simulation_module
    app = QApplication.instance() or QApplication([])
    started, release = Event(), Event()

    def held_simulation(worker):
        started.set()
        release.wait(5.)
        worker.finished_signal.emit(worker.filepath)

    monkeypatch.setattr(simulation_module.SimulationThread, 'run', held_simulation)
    monkeypatch.setattr(simulation_module, 'MuJoCoEngine', lambda **_kwargs: object())
    monkeypatch.setattr(QFileDialog, 'getSaveFileName', lambda *_args: (str(tmp_path / 'held.proc'), ''))
    monkeypatch.setattr(QMessageBox, 'information', lambda *_args: None)
    launcher = launcher_module.LauncherWindow()
    launcher.open_simulation()
    window = launcher.simulation_window
    worker = None
    try:
        window.viewer_cb.setChecked(False)
        window.run_simulation()
        worker = window.thread
        assert started.wait(2.) and worker.isRunning()
        assert window.close() is False
        assert isValid(window) and window.isVisible()
        launcher.open_simulation()
        assert launcher.simulation_window is window and window.thread is worker
        release.set()
        assert worker.wait(5000)
        # The worker ended, but a queued completion may still start the next
        # batch job. Closing must wait for that callback too.
        assert window.close() is False
        app.processEvents()
        assert window.run_btn.isEnabled() and window.batch_btn.isEnabled()
        assert window.close() is True
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        assert not isValid(window) and launcher.simulation_window is None
    finally:
        release.set()
        if worker is not None:
            assert worker.wait(5000)
        if isValid(window):
            window.close()
        launcher.close()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)


def test_processing_batch_defers_close_and_keeps_both_jobs(monkeypatch, tmp_path):
    """Lifecycle only: two named inputs, a held controller, and captured saves."""
    from src import launcher as launcher_module
    from src.analysis.pipeline.artifact_io import SliceMetadata
    from src.analysis.ui import widget_slice_processing as slice_module
    app = QApplication.instance() or QApplication([])
    launcher = launcher_module.LauncherWindow()
    launcher.open_data_processing()
    window = launcher.data_processing_window
    processing = window.processing_widget
    inputs = [tmp_path / name for name in ('first.slice', 'second.slice')]
    for path in inputs:
        path.touch()
    metadata = SliceMetadata(
        source='fixture.csv', created='2026-09-14T00:00:00+00:00', scene='fixture',
        box_l=200., box_w=120., box_h=80., full_start=0., full_end=.1,
        user_start=0., user_end=.1, padded_start=0., padded_end=.1,
        pad_rows=0, row_count=2,
    )
    processed, saved = [], []

    class HeldController(QObject):
        log_message = Signal(str)

        def process_parsed_data(self, config, parsed):
            processed.append(parsed)
            assert processing.batch_running
            assert window.close() is False
            QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
            assert isValid(window) and window.isVisible()
            launcher.open_data_processing()
            assert launcher.data_processing_window is window
            return pd.DataFrame({'metric': [1., 2.]}, index=[0., .1])

    controller = HeldController()
    processing.batch_slice_folder = str(tmp_path)
    processing.pipeline_controller_factory = lambda: controller
    monkeypatch.setattr(processing, '_load_slice_bundle', lambda _path: (
        metadata, {}, pd.DataFrame(), pd.DataFrame(index=[0., .1])))
    monkeypatch.setattr(slice_module, 'save_proc_file', lambda path, _data: saved.append(path))
    completed, errors = [], []

    def run_from_event_loop():
        try:
            processing.run_batch_processing()
        except BaseException as error:
            errors.append(error)
        finally:
            completed.append(True)

    try:
        assert not processing.batch_running
        QTimer.singleShot(0, run_from_event_loop)
        app.processEvents()
        assert completed and not errors
        assert len(processed) == 2
        assert saved == [str(path.with_suffix('.proc')) for path in inputs]
        assert not processing.batch_running
        assert processing.run_batch_button.isEnabled()
        assert 'processed=2' in processing.batch_summary_label.text()
        assert 'failed=0' in processing.batch_summary_label.text()
        assert window.close() is True
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        assert not isValid(window) and launcher.data_processing_window is None
    finally:
        if isValid(window):
            window.close()
        launcher.close()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
