"""Short Qt wiring checks; the separate data audit owns full pose processing."""
from copy import deepcopy
import json
import time
from unittest.mock import patch

import numpy as np
import pytest
from PySide6.QtWidgets import QApplication

from src.analysis.pipeline.artifact_io import _sha256_file
from src.analysis.pipeline.data_loader import DataLoader
from src.analysis.pipeline.parser import Parser
from src.analysis.pipeline.scene_detection import VERSION
from src.analysis.pipeline.scene_review import SceneReviewSession
from src.analysis.pipeline.scene_workspace import save_workspace
from src.analysis.ui.widget_raw_data_processing import WidgetRawDataProcessing
from src.config.data_columns import FACE_PREFIX_TO_INFO
from test_scene_face_corrections import write_corrected_capture, load_scene, DIMS


APP = QApplication.instance() or QApplication([])


def wait(widget):
    deadline = time.monotonic() + 20
    while widget.scene_busy or (widget.scene_worker and widget.scene_worker.isRunning()):
        APP.processEvents()
        time.sleep(.01)
        assert time.monotonic() < deadline, widget.log_output.toPlainText()
    APP.processEvents()


def open_path(action, path):
    with patch('PySide6.QtWidgets.QFileDialog.getOpenFileName', return_value=(str(path), '')):
        action()


@pytest.fixture
def widgets():
    created = []
    def create():
        widget = WidgetRawDataProcessing(DataLoader(), Parser(FACE_PREFIX_TO_INFO))
        created.append(widget)
        return widget
    yield create
    for widget in created:
        if widget.scene_worker and widget.scene_worker.isRunning():
            widget.scene_worker.requestInterruption()
            wait(widget)
        widget.close()
        widget.deleteLater()
    APP.processEvents()


def test_current_corrected_memory_detect_and_old_review_reopen_preserve_operator_work(tmp_path, widgets):
    case = write_corrected_capture(tmp_path / 'capture')
    widget = widgets()
    open_path(widget.open_csv_file, case.corrected)
    open_path(widget.load_scene_geometry, case.registration_path)
    # Save Corrected Source activates materialized arrays before any loader
    # round-trip. Exercise that precise input shape using its validated metadata.
    widget.header_info = deepcopy(case.materialized_header)
    widget.scene_panel.detect_button.click()
    wait(widget)
    assert widget.scene_session is not None, widget.log_output.toPlainText()
    np.testing.assert_allclose(widget.scene_session.result.rotations, case.rotations, atol=1e-12, rtol=0)
    for row in widget.scene_session.rows:
        widget.scene_session.set_decision(row['id'], 'include')
    selected = widget.scene_session.rows[0]['id']
    widget.scene_panel.refresh(selected)
    path = tmp_path / 'work.scene-review.json'
    with patch('PySide6.QtWidgets.QFileDialog.getSaveFileName', return_value=(str(path), '')):
        widget.scene_panel.save_review_button.click()
    data = json.loads(path.read_text(encoding='utf-8'))
    data['detection_version'] = VERSION
    path.write_text(json.dumps(data), encoding='utf-8')
    fresh = widgets()
    open_path(fresh.open_scene_review, path)
    wait(fresh)
    assert fresh.scene_session is not None, fresh.log_output.toPlainText()
    np.testing.assert_allclose(fresh.scene_session.result.rotations, case.rotations, atol=1e-12, rtol=0)
    assert fresh.scene_panel.selected_id() == selected
    assert fresh._get_slice_bounds() == (data['rows'][0]['start'], data['rows'][0]['end'])
    assert all(row['decision'] == 'unreviewed' and row['previous_review']['decision'] == 'include'
               for row in fresh.scene_session.rows)
    session, source, expected = fresh.scene_session, fresh.source_path, deepcopy(fresh.scene_session.rows)
    bad = deepcopy(data)
    bad['registration']['profile']['markers'][0]['xyz_mm'][2] *= -1.
    path.write_text(json.dumps(bad), encoding='utf-8')
    open_path(fresh.open_scene_review, path)
    wait(fresh)
    assert fresh.scene_session is session and fresh.source_path == source
    assert fresh.scene_session.rows == expected
    assert 'face correction context' in fresh.log_output.toPlainText()
    open_path(fresh.open_scene_review, '')  # Dialog cancellation keeps active work.
    assert fresh.scene_session is session and fresh.scene_session.rows == expected


def test_workspace_preview_uses_its_own_history_not_previous_active_source(tmp_path, widgets):
    old = write_corrected_capture(tmp_path / 'old', ('X',))
    new = write_corrected_capture(tmp_path / 'new', ('Y',))
    _, _, _, result = load_scene(new.corrected, new.registration)
    session = SceneReviewSession(result, _sha256_file(new.corrected))
    path = tmp_path / 'new.scene-review.json'
    save_workspace(path, session, new.corrected, DIMS)
    widget = widgets()
    open_path(widget.open_csv_file, old.corrected)
    assert widget.correction_source_metadata.decisions[0].axis == 'X'
    open_path(widget.open_scene_review, path)
    wait(widget)
    assert widget.scene_session is not None, widget.log_output.toPlainText()
    assert widget.correction_source_metadata.decisions[0].axis == 'Y'
    np.testing.assert_allclose(widget.scene_session.result.rotations, new.rotations, atol=1e-12, rtol=0)
