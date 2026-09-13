"""Unit-GUI lifecycle contracts; the controller body is held, no Raw analysis runs."""
from threading import Event

import pandas as pd
from PySide6.QtWidgets import QApplication

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


def test_launcher_keeps_processing_window_when_close_is_deferred(monkeypatch):
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
        assert len(replacements) == 1
        assert launcher.data_processing_window is replacements[0]
        assert replacements[0].isVisible()
        assert not original.isVisible()
    finally:
        if release is not None:
            release.set()
        if worker is not None:
            assert worker.wait(5000)
        for window in [original, *replacements, launcher]:
            window.close()
            window.deleteLater()
        app.processEvents()
