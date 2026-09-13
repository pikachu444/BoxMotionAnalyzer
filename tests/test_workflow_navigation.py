"""Stage handoffs preserve exact file identity; no physical solver substitutes here."""
from types import SimpleNamespace
from threading import Event

import pandas as pd
import pytest
from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QApplication, QFileDialog

from src.analysis.app.main_window import MainApp
from src.analysis.pipeline.artifact_io import save_proc_file
from src.analysis.pipeline.data_loader import DataLoader
from src.analysis.ui.widget_results_analyzer import WidgetResultsAnalyzer
from src.config.data_columns import DropPostureCols


@pytest.fixture
def app():
    return QApplication.instance() or QApplication([])


def result(path, values):
    path.parent.mkdir(parents=True, exist_ok=True)
    frame = pd.DataFrame({('Meta', 'Time', 'Time'): [1., 1.1, 1.2],
                          ('Analysis', 'DropPosture', 'BetaDeg'): values})
    # Use the canonical saved-result time tuple.
    from src.config.data_columns import RESULT_TIME_COL
    frame.columns = pd.MultiIndex.from_tuples([RESULT_TIME_COL, ('Analysis', 'DropPosture', 'BetaDeg')])
    frame.to_csv(path, index=False)
    return str(path)


def test_handed_results_keep_exact_paths_and_multi_selection(app, tmp_path):
    paths = [result(tmp_path / 'first' / 'same.proc', [0., 1., 2.]),
             result(tmp_path / 'second' / 'same.proc', [5., 6., 7.])]
    result(tmp_path / 'second' / 'unrelated.proc', [8., 9., 10.])
    widget = WidgetResultsAnalyzer(DataLoader())
    try:
        assert widget.open_result_files(paths + [paths[0]])
        assert widget.result_file_list.count() == 2
        assert widget.result_file_list.item(0).text() != widget.result_file_list.item(1).text()
        second = widget.result_file_list.item(1)
        second.setSelected(True)
        widget.on_result_file_selected(second)
        assert widget.current_result_file == paths[1]
        assert widget.explicit_result_files == paths
        assert widget.result_file_list.count() == 2
        assert widget.plot_manager.ax.lines[0].get_ydata().tolist() == [5., 6., 7.]
        sent = []
        widget.compare_requested.connect(sent.append)
        widget.compare_selected_results()
        assert sent == [paths]
    finally:
        widget.close()
        widget.deleteLater()
        app.processEvents()


def test_cancelled_direct_open_preserves_result_list_and_cursor(app, tmp_path, monkeypatch):
    paths = [result(tmp_path / 'a.proc', [0., 1., 2.]), result(tmp_path / 'b.proc', [3., 4., 5.])]
    widget = WidgetResultsAnalyzer(DataLoader())
    try:
        assert widget.open_result_files(paths)
        widget._select_time_by_xdata(1.1)
        previous = widget.result_data
        monkeypatch.setattr(QFileDialog, 'getOpenFileName', lambda *_: ('', ''))
        widget.open_result_button.click()
        assert widget.result_data is previous
        assert widget.explicit_result_files == paths
        assert widget.selected_point_info['time'] == 1.1
    finally:
        widget.close()
        widget.deleteLater()
        app.processEvents()


def test_main_handoff_moves_only_after_save_and_input_acceptance(app, monkeypatch):
    window = MainApp()
    raw, processing = window.original_widget, window.processing_widget
    calls = []
    try:
        raw.scene_session = SimpleNamespace(rows=[{'decision': 'include'}, {'decision': 'include'}])
        monkeypatch.setattr(processing, 'prepare_for_input_change',
                            lambda **kw: calls.append(('prepare', kw)) or True)
        monkeypatch.setattr(raw, 'save_for_processing', lambda: calls.append(('save',)) or ['a.slice', 'b.slice'])
        monkeypatch.setattr(processing, 'load_processing_inputs',
                            lambda paths, **kw: calls.append(('load', paths, kw)) or True)
        raw.process_requested.emit()
        assert calls == [('prepare', {'replace_single': False}), ('save',),
                         ('load', ['a.slice', 'b.slice'], {'confirm': False})]
        assert window.tab_widget.currentWidget() is processing
        assert not processing.single_running and not processing.batch_running
        window.tab_widget.setCurrentWidget(raw)
        calls.clear()
        monkeypatch.setattr(processing, 'prepare_for_input_change', lambda **_: False)
        raw.process_requested.emit()
        assert not calls and window.tab_widget.currentWidget() is raw
        monkeypatch.setattr(processing, 'prepare_for_input_change', lambda **_: True)
        monkeypatch.setattr(raw, 'save_for_processing', lambda: [])
        raw.process_requested.emit()
        assert not calls and window.tab_widget.currentWidget() is raw
    finally:
        window.close()
        window.deleteLater()
        app.processEvents()


def test_saved_outputs_open_in_step_two_and_compare_reuses_their_paths(app, tmp_path):
    path = result(tmp_path / 'saved.proc', [0., 1., 2.])
    window = MainApp()
    compared = []
    window.comparison_opener = compared.append
    try:
        window.processing_widget.results_ready.emit([path])
        assert window.tab_widget.currentWidget() is window.result_widget
        assert window.result_widget.current_result_file == path
        window.result_widget.compare_button.click()
        assert compared == [[path]]
        window.tab_widget.setCurrentWidget(window.processing_widget)
        window.processing_widget.results_ready.emit([str(tmp_path / 'missing.proc')])
        assert window.tab_widget.currentWidget() is window.processing_widget
        assert window.result_widget.current_result_file == path
    finally:
        window.close()
        window.deleteLater()
        app.processEvents()


def test_failed_proc_write_preserves_existing_bytes_and_cleans_partial_file(tmp_path, monkeypatch):
    path = tmp_path / 'saved.proc'
    save_proc_file(str(path), pd.DataFrame({'Time': [0., .1], DropPostureCols.BETA_DEG: [1., 2.]}))
    original = path.read_bytes()
    def fail_write(frame, destination, **kwargs):
        destination.write('partial new result')
        raise OSError('injected write failure')
    monkeypatch.setattr(pd.DataFrame, 'to_csv', fail_write)
    with pytest.raises(OSError, match='injected write failure'):
        save_proc_file(str(path), pd.DataFrame({'Time': [0., .1], DropPostureCols.BETA_DEG: [1., 2.]}))
    assert path.read_bytes() == original
    restored = DataLoader().load_result_csv(str(path))
    assert restored[('Analysis', 'DropPosture', 'BetaDeg')].tolist() == [1., 2.]
    assert list(tmp_path.iterdir()) == [path]


def test_long_result_filename_saves_and_reopens_without_temp_name_overflow(tmp_path):
    path = tmp_path / ('a' * 245 + '.proc')
    save_proc_file(str(path), pd.DataFrame({'Time': [0., .1], DropPostureCols.BETA_DEG: [1., 2.]}))
    restored = DataLoader().load_result_csv(str(path))
    assert restored[('Analysis', 'DropPosture', 'BetaDeg')].tolist() == [1., 2.]
    assert list(tmp_path.iterdir()) == [path]


def test_main_waits_for_queued_single_completion_before_closing(app, monkeypatch):
    import src.analysis.app.main_window as module
    class QuickController(QObject):
        log_message = Signal(str)
        analysis_finished = Signal(object)
        analysis_failed = Signal(str)
        def run_analysis_from_parsed(self, config, parsed):
            self.analysis_finished.emit(pd.DataFrame({'Time': [0., .1], 'BetaDeg': [1., 2.]}))
    monkeypatch.setattr(module, 'PipelineController', QuickController)
    window = MainApp()
    processing = window.processing_widget
    processing.parsed_data = pd.DataFrame({'B1_X': [0., 1.]}, index=[0., .1])
    monkeypatch.setattr(processing, '_build_processing_config', lambda *_: {})
    window.show()
    app.processEvents()
    try:
        processing.emit_run_processing()
        assert window.worker.wait(2000)
        assert not window.worker.isRunning() and processing.single_running
        assert not window.close()
        app.processEvents()
        assert not processing.single_running
        assert processing.current_processed_result is not None
        assert window.close()
    finally:
        window.close()
        window.deleteLater()
        app.processEvents()


def test_result_signal_does_not_release_run_before_worker_return(app, monkeypatch):
    import src.analysis.app.main_window as module
    release, emitted = Event(), Event()
    calls = []
    class HeldController(QObject):
        log_message = Signal(str)
        analysis_finished = Signal(object)
        analysis_failed = Signal(str)
        def run_analysis_from_parsed(self, config, parsed):
            calls.append(True)
            self.analysis_finished.emit(pd.DataFrame({'Time': [0., .1], DropPostureCols.BETA_DEG: [1., 2.]}))
            emitted.set()
            release.wait(5)
    monkeypatch.setattr(module, 'PipelineController', HeldController)
    window = MainApp()
    processing = window.processing_widget
    processing.parsed_data = pd.DataFrame({'B1_X': [0., 1.]}, index=[0., .1])
    monkeypatch.setattr(processing, '_build_processing_config', lambda *_: {})
    try:
        processing.emit_run_processing()
        assert emitted.wait(2)
        app.processEvents()
        assert window.worker.isRunning() and processing.single_running
        assert not processing.run_button.isEnabled()
        processing.emit_run_processing()
        assert len(calls) == 1
        release.set()
        assert window.worker.wait(2000)
        app.processEvents()
        assert not processing.single_running and processing.run_button.isEnabled()
        processing.emit_run_processing()
        assert window.worker.wait(2000)
        app.processEvents()
        assert len(calls) == 2 and not processing.single_running
    finally:
        release.set()
        window.worker.wait(2000)
        app.processEvents()
        window.close()
        window.deleteLater()
        app.processEvents()


def test_compare_handoff_deduplicates_paths_and_retains_baseline(app, tmp_path, monkeypatch):
    from src.analysis.compare.main_window import CompareMainWindow
    paths = [result(tmp_path / 'one' / 'saved.proc', [0., 1., 2.]),
             result(tmp_path / 'two' / 'saved.proc', [3., 4., 5.])]
    window = CompareMainWindow()
    try:
        window.load_result_files(paths, deduplicate=True)
        assert list(window.model.file_paths.values()) == paths
        names = list(window.model.datasets)
        window.model.set_baseline(names[1])
        stops = []
        monkeypatch.setattr(window.playback_panel, 'stop', lambda: stops.append(True))
        window.load_result_files(paths + [paths[0]], deduplicate=True)
        assert len(window.model.datasets) == 2
        assert window.model.baseline_name == names[1]
        assert not stops
    finally:
        window.close()
        window.deleteLater()
        app.processEvents()


def test_compare_reloads_overwritten_path_and_keeps_previous_result_on_bad_reload(app, tmp_path, monkeypatch):
    from src.analysis.compare.main_window import CompareMainWindow
    from PySide6.QtWidgets import QMessageBox
    path = result(tmp_path / 'saved.proc', [15., 15., 15.])
    window = CompareMainWindow()
    errors = []
    monkeypatch.setattr(QMessageBox, 'warning', lambda *args: errors.append(args[-1]))
    try:
        window.load_result_files([path], deduplicate=True)
        name = window.model.baseline_name
        result(tmp_path / 'saved.proc', [0., 0., 0.])
        window.load_result_files([path], deduplicate=True)
        assert len(window.model.datasets) == 1 and window.model.baseline_name == name
        assert window.model.datasets[name][('Analysis', 'DropPosture', 'BetaDeg')].tolist() == [0., 0., 0.]
        previous = window.model.datasets[name]
        (tmp_path / 'saved.proc').write_text('broken', encoding='utf-8')
        window.load_result_files([path], deduplicate=True)
        assert errors and window.model.datasets[name] is previous
        assert len(window.model.datasets) == 1 and window.model.baseline_name == name
    finally:
        window.close()
        window.deleteLater()
        app.processEvents()
