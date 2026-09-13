"""Actual SimulationUI/worker/file dialogs and production comparison renderer."""
import json
import time
from pathlib import Path
import numpy as np
import pytest
from pandas.io.formats.csvs import CSVFormatter
from scipy.spatial.transform import Rotation as R
from PySide6.QtWidgets import QApplication, QFileDialog, QLineEdit, QMessageBox
from PySide6.QtCore import Qt, QTimer
from PySide6.QtTest import QTest
from src.simulation.ui.main_window import SimulationUI, SimulationThread
from src.analysis.compare.main_window import CompareMainWindow
from src.analysis.pipeline.data_loader import DataLoader
from src.config import config_visualization as k
from test_simulation_export import CORNERS, vector


@pytest.fixture
def saving_window():
    app = QApplication.instance() or QApplication([])
    app.setAttribute(Qt.ApplicationAttribute.AA_DontUseNativeDialogs, True)
    window = SimulationUI()
    for widget, value in [(window.w_input, 200), (window.d_input, 120),
                          (window.h_input, 80), (window.mass_input, 1),
                          (window.com_x, 3), (window.com_y, -4), (window.com_z, 2),
                          (window.duration_input, .5)]:
        widget.setValue(value)
    assert window.duration_input.value() == .5
    window.viewer_cb.setChecked(False)
    window.noise_cb.setChecked(False)
    window.show()
    yield app, window
    if isinstance(window.thread, SimulationThread):
        assert window.thread.wait(10000)
    window.close()
    app.processEvents()


def wait_for_message(messages):
    deadline = time.monotonic() + 15
    while not messages and time.monotonic() < deadline:
        QApplication.processEvents()
        # Let the Python CSV writer in the QThread acquire the GIL as well.
        time.sleep(.01)
    assert messages, 'Simulation did not report completion or failure'


@pytest.mark.parametrize('batch', [False, True])
def test_cancel_actual_save_dialog_does_not_start_worker(saving_window, batch):
    app, window = saving_window
    dialogs = []

    def cancel():
        dialog = app.activeModalWidget()
        dialogs.append(dialog)
        if isinstance(dialog, QFileDialog):
            dialog.reject()

    QTimer.singleShot(100, cancel)
    QTest.mouseClick(window.batch_btn if batch else window.run_btn, Qt.LeftButton)
    assert dialogs and isinstance(dialogs[0], QFileDialog)
    # QWidget already has QObject.thread(); only an assigned SimulationThread
    # would mean that the simulation worker was created.
    assert not isinstance(window.thread, SimulationThread)
    assert not hasattr(window, '_batch_success_paths')
    assert window.run_btn.isEnabled() and window.batch_btn.isEnabled()
    assert not window.progress_bar.isVisible()


def test_worker_write_failure_restores_controls_and_retry(saving_window, tmp_path, monkeypatch):
    _, window = saving_window
    path = tmp_path / 'keep.proc'
    path.write_bytes(b'previous result')
    messages = []
    monkeypatch.setattr(QFileDialog, 'getSaveFileName', lambda *args: (str(path), ''))
    monkeypatch.setattr(QMessageBox, 'critical', lambda *args: messages.append(('error', args[2])))
    monkeypatch.setattr(QMessageBox, 'information', lambda *args: messages.append(('success', args[2])))

    def fail_body(*args):
        error = OSError('injected partial CSV write')
        error.add_note('Additional cleanup failure details')
        raise error

    with monkeypatch.context() as patch:
        patch.setattr(CSVFormatter, '_save_body', fail_body)
        QTest.mouseClick(window.run_btn, Qt.LeftButton)
        assert not window.run_btn.isEnabled() and not window.batch_btn.isEnabled()
        assert window.progress_bar.isVisible()
        wait_for_message(messages)
        assert window.thread.wait(5000)
    assert messages == [('error', 'Simulation Failed: injected partial CSV write\nAdditional cleanup failure details')]
    assert path.read_bytes() == b'previous result'
    assert set(tmp_path.iterdir()) == {path}
    assert window.run_btn.isEnabled() and window.batch_btn.isEnabled()
    assert not window.progress_bar.isVisible()
    messages.clear()
    QTest.mouseClick(window.run_btn, Qt.LeftButton)
    wait_for_message(messages)
    assert window.thread.wait(5000)
    assert len(messages) == 1 and messages[0][0] == 'success'
    assert len(DataLoader().load_result_csv(str(path))) == 63
    assert window.run_btn.isEnabled() and window.batch_btn.isEnabled()
    assert not window.progress_bar.isVisible()


def test_batch_stops_at_failed_file_and_keeps_completed_outputs(saving_window, tmp_path, monkeypatch):
    from src.simulation.scenarios import Scenarios
    from src.simulation import data_exporter
    _, window = saving_window
    sequences = Scenarios.get_drop_sequence_specs(window.cat_combo.currentText())
    # Use the real batch list; failure at its second export must stop the list.
    first = tmp_path / f'TypeG_{sequences[0].id}.proc'
    second = tmp_path / f'TypeG_{sequences[1].id}.proc'
    second.write_bytes(b'previous second result')
    messages = []
    monkeypatch.setattr(QFileDialog, 'getExistingDirectory', lambda *args: str(tmp_path))
    monkeypatch.setattr(QMessageBox, 'critical', lambda *args: messages.append(('error', args[2])))
    monkeypatch.setattr(QMessageBox, 'information', lambda *args: messages.append(('success', args[2])))
    replace = data_exporter.os.replace
    completed = []

    def fail_second(source, destination):
        if Path(destination) == second:
            raise PermissionError('injected second destination lock')
        replace(source, destination)
        completed.append((Path(destination), Path(destination).read_bytes()))

    monkeypatch.setattr(data_exporter.os, 'replace', fail_second)
    QTest.mouseClick(window.batch_btn, Qt.LeftButton)
    wait_for_message(messages)
    assert window.thread.wait(5000)
    QTest.qWait(50)
    assert messages == [('error', 'Simulation Failed: injected second destination lock')]
    assert len(completed) == 1 and completed[0] == (first, first.read_bytes())
    assert len(DataLoader().load_result_csv(str(first))) == 63
    assert second.read_bytes() == b'previous second result'
    assert set(tmp_path.iterdir()) == {first, second}
    assert window._batch_success_paths == [str(first)]
    assert window._batch_current_idx == 1
    assert window.run_btn.isEnabled() and window.batch_btn.isEnabled()
    assert not window.progress_bar.isVisible()


def test_simulation_run_save_reopen_actual_gui(monkeypatch):
    app=QApplication.instance() or QApplication([])
    app.setAttribute(Qt.ApplicationAttribute.AA_DontUseNativeDialogs,True)
    evidence=Path('tmp/issue81_gui').resolve()
    evidence.mkdir(parents=True,exist_ok=True)
    path=evidence/'public_box.proc'
    # A new unique output avoids a modal overwrite question on repeated runs.
    path=evidence/f'public_box_{time.time_ns()}.proc'
    window=SimulationUI()
    compare=None
    errors=[]; messages=[]
    import sys
    monkeypatch.setattr(sys,'excepthook',lambda kind,value,tb:errors.append(str(value)))
    watcher=QTimer()
    def acknowledge():
        dialog=app.activeModalWidget()
        if isinstance(dialog,QMessageBox):
            messages.append(dialog.text())
            dialog.grab().save(str(evidence/'save_result.png'))
            dialog.accept()
    watcher.timeout.connect(acknowledge)
    watcher.start(100)
    def pick_file():
        dialog=app.activeModalWidget()
        if not isinstance(dialog,QFileDialog):
            errors.append('Expected actual file dialog')
            return
        editor=dialog.findChild(QLineEdit,'fileNameEdit')
        editor.setText(str(path))
        def accept():
            editor.setText(str(path)); dialog.accept()
        QTimer.singleShot(150,accept)
    try:
        window.show()
        for widget,value in [(window.w_input,200),(window.d_input,120),(window.h_input,80),
                              (window.mass_input,1),(window.com_x,3),(window.com_y,-4),(window.com_z,2),
                              (window.custom_h_input,100),(window.custom_r_input,20),
                              (window.custom_p_input,35),(window.custom_y_input,-15),(window.duration_input,.5)]:
            widget.setValue(value)
        window.viewer_cb.setChecked(False)
        window.noise_cb.setChecked(False)
        QTest.qWait(200)
        window.grab().save(str(evidence/'simulation_inputs.png'))
        QTimer.singleShot(100,pick_file)
        QTest.mouseClick(window.run_btn,Qt.LeftButton)
        deadline=time.monotonic()+30
        while not messages and not errors and time.monotonic()<deadline:
            app.processEvents()
            time.sleep(.01)
        assert not errors and messages and 'completed and saved' in messages[-1]
        assert window.thread.wait(5000)
        frame=DataLoader().load_result_csv(str(path))
        times=frame[('Info','Time','Time')].to_numpy()
        assert len(frame)==63
        np.testing.assert_allclose(np.diff(times),.008,atol=1e-14)
        rot=R.from_rotvec(vector(frame,'Position','CoM',['P_RX','P_RY','P_RZ']))
        assert np.linalg.norm((rot[-1]*rot[0].inv()).as_rotvec())>0.01
        center=vector(frame,'Position','CoM',['P_TX','P_TY','P_TZ'])
        max_error=0.
        for j,c in enumerate(CORNERS,1):
            actual=vector(frame,'Position',f'C{j}',['P_TX','P_TY','P_TZ'])
            max_error=max(max_error,float(np.max(np.abs(actual-center-rot.apply(c)))))
        assert max_error<1e-10
        np.testing.assert_allclose(vector(frame,'Simulation','InertialCOM',['X_mm','Y_mm','Z_mm']),
                                   center+rot.apply([3,-4,2]),atol=1e-10)
        window.hide()
        compare=CompareMainWindow()
        compare.show()
        QTest.qWait(150)
        QTimer.singleShot(100,pick_file)
        QTest.mouseClick(compare.control_panel.btn_add_files,Qt.LeftButton)
        assert not errors and path.name in compare.model.datasets
        panel=compare.playback_panel
        assert compare.control_panel.cb_view.currentData() == 'individual'
        panel.master_slider.setValue(30)
        QTest.qWait(250)
        viewer=panel.widgets[path.name]
        assert viewer.isVisible()
        np.testing.assert_allclose(viewer.polydata[k.SK_ACTOR_BOX].points,
                                   np.array([vector(frame,'Position',f'C{j}',['P_TX','P_TY','P_TZ'])[30] for j in range(1,9)]),atol=1e-10)
        assert compare.model.identities[path.name].source_kind=='mujoco_synthetic'
        assert not compare.model.timelines[path.name].aligned
        assert compare.model.identities[path.name].exclusion_reasons()
        compare.grab().save(str(evidence/'reopened.png'))
        viewer.plotter.screenshot(str(evidence/'renderer.png'))
        report=dict(evidence='synthetic_integration',input=str(path),rows=len(frame),
                    dt=float(np.median(np.diff(times))),max_corner_error_mm=max_error,
                    rotation_change_rad=float(np.linalg.norm((rot[-1]*rot[0].inv()).as_rotvec())),
                    source='mujoco_synthetic',comparison='individual only; t1/Analysis identity absent',
                    errors=errors,messages=messages)
        (evidence/'result.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    finally:
        watcher.stop()
        if hasattr(window,'thread'): window.thread.wait(10000)
        if compare is not None: compare.close()
        window.close(); app.processEvents()
