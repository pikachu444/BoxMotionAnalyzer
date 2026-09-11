"""Actual SimulationUI/worker/file dialogs and production comparison renderer."""
import json
import time
from pathlib import Path
import numpy as np
from scipy.spatial.transform import Rotation as R
from PySide6.QtWidgets import QApplication, QFileDialog, QLineEdit, QMessageBox
from PySide6.QtCore import Qt, QTimer
from PySide6.QtTest import QTest
from src.simulation.ui.main_window import SimulationUI
from src.analysis.compare.main_window import CompareMainWindow
from src.analysis.pipeline.data_loader import DataLoader
from src.config import config_visualization as k
from test_simulation_export import CORNERS, vector


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
            QTest.qWait(50)
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
        panel.chk_sync.setChecked(False)
        panel.local_controls[path.name]['slider'].setValue(30)
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
