"""Real Qt windows and file dialogs; inputs are serialized unit contracts."""
from pathlib import Path
import pandas as pd
import pytest
from PySide6.QtCore import Qt, QTimer
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QFileDialog, QLineEdit, QMessageBox

from comparison_fixtures import write_proc
from src.analysis.compare.main_window import CompareMainWindow
from src.utils.result_time import TIME_COLUMN


def test_actual_comparison_file_loading_and_time_states(tmp_path, monkeypatch):
    app = QApplication.instance() or QApplication([])
    app.setAttribute(Qt.ApplicationAttribute.AA_DontUseNativeDialogs, True)
    evidence = Path('tmp/issue83_gui')
    evidence.mkdir(parents=True, exist_ok=True)
    paths = [write_proc(tmp_path / 'normal.proc'),
             write_proc(tmp_path / ('long_name_' * 12 + '.proc'), times=(1,1.01,1.04,2,2.02)),
             write_proc(tmp_path / 'legacy.proc', metadata={}),
             write_proc(tmp_path / 'source_only_missing.proc', metadata={}),
             write_proc(tmp_path / 'bad_position.proc')]
    legacy = pd.read_csv(paths[2], header=[0,1,2]).drop(columns=[TIME_COLUMN])
    legacy.to_csv(paths[2], index=False)
    source_only_df = pd.read_csv(paths[3], header=[0,1,2])
    source_only_df = source_only_df.loc[:, [col[:2] != ('Info','Artifact') for col in source_only_df.columns]]
    source_only_df.to_csv(paths[3], index=False)
    bad_position = pd.read_csv(paths[4], header=[0,1,2])
    bad_position[('Position','CoM','P_TX')] = [10., 'bad', 10.2]
    bad_position.to_csv(paths[4], index=False)
    malformed = tmp_path / 'malformed.proc'
    malformed.write_text('not a result')
    window = CompareMainWindow()
    errors = []
    import sys
    monkeypatch.setattr(sys, 'excepthook', lambda kind, value, traceback: errors.append(str(value)))
    loading_states = []
    def record_loading(message):
        if message.startswith('Loading ') and message.endswith('…'):
            loading_states.append(not window.control_panel.btn_add_files.isEnabled())
            window.grab().save(str(evidence / 'loading.png'))
    window.statusBar().messageChanged.connect(record_loading)
    window.show()
    QTest.qWait(250)
    assert not window.model.datasets
    window.grab().save(str(evidence / 'empty.png'))

    def load_file(path, expect_error=False):
        def pick():
            dialog = app.activeModalWidget()
            if not isinstance(dialog, QFileDialog):
                errors.append('File dialog did not open')
                return
            dialog.findChild(QLineEdit, 'fileNameEdit').setText(str(path))
            def accept():
                dialog.findChild(QLineEdit, 'fileNameEdit').setText(str(path))
                dialog.accept()
            QTimer.singleShot(200, accept)
        seen_error = []
        watcher = QTimer()
        def handle_error():
            dialog = app.activeModalWidget()
            if isinstance(dialog, QMessageBox):
                seen_error.append(dialog.text())
                dialog.grab().save(str(evidence / 'malformed.png'))
                dialog.accept()
        watcher.timeout.connect(handle_error)
        watcher.start(100)
        QTimer.singleShot(100, pick)
        QTest.mouseClick(window.control_panel.btn_add_files, Qt.LeftButton)
        watcher.stop()
        assert bool(seen_error) == expect_error
        assert not errors
        QTest.qWait(150)

    try:
        load_file(malformed, expect_error=True)
        assert not window.model.datasets
        for path in paths:
            load_file(path)
        assert len(window.model.datasets) == 5
        assert len(loading_states) == 6 and all(loading_states)
        gap_name = paths[1].name
        unknown_name = paths[2].name
        assert window.model.identities[unknown_name].source_kind == 'unknown_legacy'
        assert window.model.playback_row(unknown_name, 0) is None
        # Move the common clock into the long file's internal gap and beyond
        # the normal file end. Neither viewer may clamp to its endpoint.
        panel = window.playback_panel
        start, end = panel.bounds
        source_only = paths[3].name
        assert window.model.timelines[source_only].times is not None
        assert not window.model.timelines[source_only].aligned
        assert source_only not in window.model.get_timeseries_data('Analysis','DropPosture','ThetaLongDeg')
        panel.master_slider.setValue(0)
        QTest.qWait(100)
        assert not panel.widgets[paths[4].name].isHidden()
        panel.master_slider.setValue(round(100000 * -start / (end-start)))
        QTest.qWait(100)
        assert panel.widgets[paths[4].name].isHidden()
        assert not panel.widgets[paths[0].name].isHidden()
        assert panel.widgets[source_only].isHidden()
        assert not errors
        window.grab().save(str(evidence / 'invalid_position.png'))
        panel.master_slider.setValue(round(100000 * (.5 - start) / (end - start)))
        QTest.qWait(200)
        assert panel.widgets[gap_name].isHidden()
        assert panel.widgets[paths[0].name].isHidden()
        assert panel.widgets[unknown_name].isHidden()
        assert window.graph_panel.cursor.get_xdata()[0] == pytest.approx(panel.current_elapsed)
        curves = window.graph_panel.plot_manager.ax.lines
        assert any(pd.isna(line.get_ydata()).any() for line in curves if len(line.get_ydata()) > 2)
        window.grab().save(str(evidence / 'gap_unavailable.png'))
        window.control_panel.file_list.setCurrentRow(2)
        assert 'unknown_legacy' in window.control_panel.details.toPlainText()
        assert 'ModelId: missing' in window.control_panel.details.toPlainText()
        window.control_panel.cb_view.setCurrentIndex(window.control_panel.cb_view.findData(unknown_name))
        assert window.graph_panel.plot_manager.ax.get_xlabel() == 'Sample row (time unavailable)'
        panel.chk_sync.setChecked(False)
        panel.local_controls[unknown_name]['slider'].setValue(1)
        QTest.qWait(150)
        assert not panel.widgets[unknown_name].isHidden()
        assert 'time unavailable' in panel.local_controls[unknown_name]['label'].text()
        assert not panel.local_controls[unknown_name]['play'].isEnabled()
        # Qt widget grabs do not reliably include native VTK surfaces on Windows.
        # Capture the actual rendered viewport separately; do not composite it.
        panel.widgets[unknown_name].plotter.screenshot(str(evidence / 'individual_3d.png'))
        window.grab().save(str(evidence / 'unknown_individual.png'))
        window.control_panel.cb_view.setCurrentIndex(window.control_panel.cb_view.findData(source_only))
        assert window.graph_panel.plot_manager.ax.get_xlabel() == 'Recorded time (s)'
        panel.local_controls[source_only]['slider'].setValue(1)
        assert not panel.widgets[source_only].isHidden()
        assert panel.local_controls[source_only]['play'].isEnabled()
        window.grab().save(str(evidence / 'source_only_individual.png'))
        window.resize(900,650)
        QTest.qWait(150)
        window.grab().save(str(evidence / 'resized.png'))
        window._on_remove_file(unknown_name)
        assert unknown_name not in window.model.datasets
    finally:
        window.close()
        QTest.qWait(100)
