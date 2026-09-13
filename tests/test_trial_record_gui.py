"""Actual MainApp record import, workspace reopening, slice and Raw/proc path."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import time

import numpy as np
import pandas as pd
from PySide6.QtCore import Qt, QTimer
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QFileDialog, QLineEdit, QMessageBox
from scipy.spatial.transform import Rotation

from src.analysis.app.main_window import MainApp
from src.analysis.pipeline.artifact_io import read_slice_metadata
from src.analysis.pipeline.data_loader import DataLoader
from src.config import config_app
from src.simulation.trial_record_fixtures import write_analytic_approach
from src.utils.artifact_metadata import read_identity


def test_mainapp_record_import_reopen_and_raw_process(monkeypatch):
    monkeypatch.setattr(config_app, 'BOX_DIMS', np.array(config_app.BOX_DIMS, copy=True))
    monkeypatch.setattr(config_app, 'LOCAL_BOX_CORNERS', np.array(config_app.LOCAL_BOX_CORNERS, copy=True))
    app = QApplication.instance() or QApplication([])
    app.setAttribute(Qt.ApplicationAttribute.AA_DontUseNativeDialogs, True)
    evidence = (Path('tmp/issue75_trial_gui') / str(time.time_ns())).resolve()
    evidence.mkdir(parents=True)
    folder = write_analytic_approach(evidence / 'analytic')
    protected = list(folder.iterdir())
    before_hashes = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in protected}
    report = {'status': 'fail', 'input': str(folder.resolve()), 'source_kind': 'handcrafted_dummy',
              'expected': 'G16 recorded intent, LEFT intended face, BOTTOM approach Different; no conformity claim',
              'source_sha256_before': before_hashes, 'screenshots': {}, 'checks': {}}
    errors, windows = [], []
    active = None

    def create():
        window = MainApp()
        window.resize(1400, 880)
        window.show()
        windows.append(window)
        app.processEvents()
        return window

    def wait_until(predicate, timeout=120):
        deadline = time.monotonic() + timeout
        while not predicate() and time.monotonic() < deadline:
            app.processEvents()
            time.sleep(.01)
        assert predicate(), 'Timed out in MainApp workflow'
        assert not errors, errors

    def wait_detection(widget):
        wait_until(lambda: not widget.scene_busy and not (
            widget.scene_worker and widget.scene_worker.isRunning()), timeout=25)

    def choose(path=None):
        def accept_file():
            dialog = app.activeModalWidget()
            if not isinstance(dialog, QFileDialog):
                errors.append('Expected an actual QFileDialog')
                return
            if path is None:
                dialog.reject()
                return
            dialog.selectFile(str(Path(path).resolve()))
            def finish():
                dialog.findChild(QLineEdit, 'fileNameEdit').setText(str(Path(path).resolve()))
                dialog.accept()
            QTimer.singleShot(200, finish)
        QTimer.singleShot(200, accept_file)

    def click(button):
        assert button.isEnabled(), button.text()
        assert button.isVisible() and button.visibleRegion().contains(button.rect()), button.text()
        QTest.mouseClick(button, Qt.MouseButton.LeftButton)
        app.processEvents()

    def load_record(panel, path):
        choose(path)
        menu = panel.trial_record_button.menu()
        QTimer.singleShot(80, lambda: QTest.mouseClick(menu, Qt.MouseButton.LeftButton,
            pos=menu.actionGeometry(panel.load_trial_record_action).center()))
        click(panel.trial_record_button)

    def screenshot(window, name, description):
        app.processEvents()
        assert window.grab().save(str(evidence / name))
        report['screenshots'][name] = description

    def watch_errors():
        dialog = app.activeModalWidget()
        if isinstance(dialog, QMessageBox):
            errors.append(dialog.text())
            dialog.accept()

    watcher = QTimer()
    watcher.timeout.connect(watch_errors)
    watcher.start(100)
    try:
        active = create()
        widget = active.original_widget
        choose(folder / 'observed.csv')
        click(widget.load_csv_button)
        click(widget.scene_panel.details_section.button)
        choose(folder / 'registration.json')
        click(widget.scene_panel.geometry_button)
        click(widget.scene_panel.detect_button)
        wait_detection(widget)
        panel, session = widget.scene_panel, widget.scene_session
        assert session is not None, widget.log_output.toPlainText()
        for row in session.rows:
            panel.refresh(row['id'])
            click(panel.include_button if row['motion'] == 'free_fall' else panel.exclude_button)
        load_record(panel, folder / 'trial_record.json')
        click(panel.identify_button)
        row = next(row for row in session.rows if row['decision'] == 'include')
        panel.refresh(row['id'])
        assert row['item_candidates'] == ['G16']
        assert not row['identity']['confirmed']
        assert row['observed_consistency']['approach'] == 'different'
        assert 'Different' in panel.table.item(panel.table.currentRow(), 8).text()
        panel.item_combo.setCurrentIndex(panel.item_combo.findData('G16'))
        click(panel.confirm_button)
        assert row['identity']['confirmed']
        screenshot(active, '01_recorded_difference.png',
                   'Step 1: loaded analytic CSV, automatic interval reviewed; G16 confirmed from record and observed BOTTOM differs from LEFT intent.')
        snapshot = deepcopy(session.rows)
        load_record(panel, None)
        assert session.rows == snapshot
        assert session.trial_record is not None
        report['checks']['cancel_preserved_record'] = True
        workspace = evidence / 'recorded.scene-review.json'
        choose(workspace)
        click(panel.save_review_button)
        assert workspace.exists(), widget.log_output.toPlainText()
        selected_id = row['id']
        expected_payload = session.payload(selected_id)
        active.close()

        active = create()
        widget = active.original_widget
        click(widget.scene_panel.details_section.button)
        choose(workspace)
        click(widget.scene_panel.open_review_button)
        wait_detection(widget)
        assert widget.scene_session is not None, widget.log_output.toPlainText()
        assert widget.scene_session.rows == snapshot
        assert widget.scene_session.payload(selected_id) == expected_payload
        widget.scene_panel.refresh(selected_id)
        assert widget.scene_panel.table.item(widget.scene_panel.table.currentRow(), 8).text().startswith('Different')
        screenshot(active, '02_workspace_reopened.png',
                   'New MainApp window: workspace read from disk, capture re-detected, confirmed G16 and Different approach restored.')
        sliced, processed = evidence / 'recorded.slice', evidence / 'recorded.proc'
        choose(sliced)
        click(widget.save_slice_button)
        metadata = read_slice_metadata(str(sliced))
        assert metadata.scene_review_json == expected_payload
        active.tab_widget.setCurrentIndex(1)
        processing = active.processing_widget
        choose(sliced)
        click(processing.load_slice_button)
        click(processing.rb_processing_raw)
        assert processing.rb_processing_raw.isChecked()
        click(processing.run_button)
        wait_until(lambda: processing.save_proc_button.isEnabled())
        choose(processed)
        click(processing.save_proc_button)
        assert processed.exists()
        output = DataLoader().load_result_csv(str(processed))
        assert set(output[('Info', 'SceneReview', 'Json')].dropna()) == {expected_payload}
        identity = read_identity(output)
        assert identity.source_kind == 'handcrafted_dummy'
        assert identity.values['ScenarioId'] == 'G16'
        assert identity.values['ScenarioKind'] == 'free_fall'
        # Read separate truth only after the real processing path has finished.
        truth = pd.read_csv(folder / 'truth_pose.csv', float_precision='round_trip')
        selected = truth[(truth.time_s >= metadata.user_start) & (truth.time_s <= metadata.user_end)]
        np.testing.assert_allclose(output.index.to_numpy(float), selected.time_s, atol=1e-10, rtol=0)
        position = output[[('Position', 'CoM', 'P_T' + axis) for axis in 'XYZ']].to_numpy(float)
        expected_position = selected[['body_x_mm', 'body_y_mm', 'body_z_mm']].to_numpy()
        pos_error = float(np.linalg.norm(position - expected_position, axis=1).max())
        rotvec = output[[('Position', 'CoM', 'P_R' + axis) for axis in 'XYZ']].to_numpy(float)
        rot_error = float(np.rad2deg(Rotation.from_rotvec(rotvec).magnitude()).max())
        assert pos_error < .1 and rot_error < .1  # Existing public pose-mechanics bounds.
        screenshot(active, '03_raw_processed.png',
                   'Step 1.5: recorded slice processed with actual Raw optimizer and saved as proc; metadata and selected original times verified by reopening.')
        report.update(status='pass', selected_rows=len(output), selected_range_s=[metadata.user_start, metadata.user_end],
                      max_position_error_mm=pos_error, max_rotation_error_deg=rot_error,
                      workspace=str(workspace), slice=str(sliced), proc=str(processed),
                      device_pixel_ratio=active.devicePixelRatioF(),
                      logical_window_size=[active.width(), active.height()])
        report['checks'].update(recorded_identity_and_observed_difference=True,
                                workspace_slice_proc_meaning_preserved=True, actual_raw_processing=True)
    finally:
        watcher.stop()
        report['errors'] = errors
        report['source_sha256_after'] = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() if p.exists() else None
                                          for p in protected}
        unchanged = report['source_sha256_after'] == before_hashes
        report['checks']['inputs_unchanged'] = unchanged
        if not unchanged or errors:
            report['status'] = 'fail'
        if active is not None:
            (evidence / 'workflow.log').write_text(active.original_widget.log_output.toPlainText() + '\n' +
                active.processing_widget.log_output.toPlainText(), encoding='utf-8')
        (evidence / 'execution.json').write_text(json.dumps(report, indent=2, allow_nan=False), encoding='utf-8')
        for window in windows:
            window.close()
        app.processEvents()
        print('Trial-record MainApp evidence:', evidence)
        assert unchanged and not errors, report
