"""Observed support cycles in existing Step 1 and saved review artifacts."""
from copy import deepcopy
import hashlib
import json
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest
from PySide6.QtWidgets import QApplication

from src.analysis.pipeline.artifact_io import (add_timeline_context_columns, read_slice_metadata,
    save_proc_file, save_slice_file, update_slice_box_dimensions)
from src.analysis.pipeline.data_loader import DataLoader
from src.analysis.pipeline.parser import Parser
from src.analysis.pipeline.scene_detection import Registration, detect_scenes
from src.analysis.pipeline.scene_review import SceneReviewSession
from src.analysis.pipeline.scene_workspace import read_workspace, restore_session, save_workspace
from src.analysis.pipeline.support_motion import LIFT_SIGNAL
from src.analysis.ui.widget_raw_data_processing import WidgetRawDataProcessing
from src.analysis.ui.widget_slice_processing import WidgetSliceProcessing
from src.config.data_columns import FACE_PREFIX_TO_INFO
from test_scene_review_gui import wait_detection
from test_support_cycles import write_support_observations


APP = QApplication.instance() or QApplication([])
PEAK_MM = 300. * np.sin(np.deg2rad(15.))


@pytest.fixture(scope='module')
def recording(tmp_path_factory):
    folder = write_support_observations(tmp_path_factory.mktemp('cycle_workflow') / 'recording')
    header, raw = DataLoader().load_csv(str(folder / 'observed.csv'))
    parsed = Parser(FACE_PREFIX_TO_INFO).process(header, raw)
    registration = Registration.load(folder / 'registration.json')
    result = detect_scenes(header, raw, parsed, registration=registration)
    digest = hashlib.sha256((folder / 'observed.csv').read_bytes()).hexdigest()
    return folder, header, raw, parsed, registration, result, digest


def test_step1_shows_automatic_cycle_height_and_phases_then_clears_them(recording):
    folder = recording[0]
    widget = WidgetRawDataProcessing(DataLoader(), Parser(FACE_PREFIX_TO_INFO))
    try:
        for action, filename in ((widget.open_csv_file, 'observed.csv'),
                                 (widget.load_scene_geometry, 'registration.json')):
            with patch('PySide6.QtWidgets.QFileDialog.getOpenFileName',
                       return_value=(str(folder / filename), '')):
                action()
        widget.scene_panel.detect_button.click()
        wait_detection(widget)
        cycles = [row for row in widget.scene_session.rows if 'support_cycle_return' in row['tags']]
        assert len(cycles) == 1
        row = cycles[0]
        assert row['decision'] == 'unreviewed' and not row['identity']['confirmed']
        assert [p['motion'] for p in row['activity_members']] == [
            'tip_or_rotation', 'stationary', 'tip_or_rotation']
        widget.scene_panel.refresh(row['id'])
        widget.combo_plot_axis.setCurrentIndex(widget.combo_plot_axis.findData(LIFT_SIGNAL))
        APP.processEvents()
        assert float(widget.le_slice_start.text()) == row['start']
        assert float(widget.le_slice_end.text()) == row['end']
        line = next(line for line in widget.plot_manager.ax.lines if line.get_label() == LIFT_SIGNAL)
        assert np.nanmax(line.get_ydata()) == pytest.approx(PEAK_MM, abs=1e-6)
        labels = widget.plot_manager.ax.get_legend_handles_labels()[1]
        assert 'Rise' in labels and 'Fall' in labels
        assert 'Rise' in widget.scene_panel.motion_summary.text()
        assert 'Fall' in widget.scene_panel.motion_summary.text()
        assert 'Returned' in widget.scene_panel.motion_summary.text()
        assert not widget.scene_panel.save_all_button.isEnabled()
        widget.scene_panel.table.selectAll()
        widget.scene_panel.remove_button.click()
        APP.processEvents()
        assert widget.scene_panel.motion_summary.text() == ''
        assert not {'Rise', 'Fall'} & set(widget.plot_manager.ax.get_legend_handles_labels()[1])
    finally:
        if widget.scene_worker and widget.scene_worker.isRunning():
            widget.scene_worker.requestInterruption()
            wait_detection(widget)
        widget.close()
        widget.deleteLater()
        APP.processEvents()


def test_original_rise_range_and_decisions_survive_new_grouping_and_reopen(recording, tmp_path):
    folder, header, raw, parsed, registration, result, digest = recording
    session = SceneReviewSession(result, digest)
    row = next(r for r in session.rows if 'support_cycle_return' in r['tags'])
    rise = next(c for c in result.activity_candidates if c.motion == 'tip_or_rotation')
    removed = session.rows[-1]['id']
    session.remove(removed)
    session.set_range(row['id'], rise.start, rise.end)
    session.refresh(result)
    assert row['motion'] == 'tip_or_rotation'
    assert (row['left_censored'], row['right_censored']) == (rise.left_censored, rise.right_censored)
    assert row['support_cycle']['returned'] is False
    session.set_decision(row['id'], 'include')
    others = [r for r in session.rows if r['id'] != row['id']]
    session.set_decision(others[0]['id'], 'exclude')
    saved_rows = deepcopy(session.rows)
    session.refresh(result)
    assert session.rows == saved_rows
    path = tmp_path / 'review.scene-review.json'
    save_workspace(path, session, folder / 'observed.csv', registration.profile['box_dims_mm'],
                   selected_id=row['id'], signal=LIFT_SIGNAL)
    fresh = detect_scenes(header, raw, parsed, registration=registration)
    restored, changed = restore_session(read_workspace(path), fresh, digest)
    assert changed == set()
    assert restored.rows == saved_rows
    assert restored.deleted_ids == {removed}
    assert restored.row(row['id'])['support_cycle']['returned'] is False
    altered = read_workspace(path)
    cached = next(r for r in altered['rows'] if r['id'] == row['id'])
    cached['support_cycle']['peak_height_mm'] = 999.
    checked, changed = restore_session(altered, fresh, digest)
    assert changed == {row['id']}
    assert checked.row(row['id'])['decision'] == 'unreviewed'
    assert checked.row(row['id'])['previous_review']['decision'] == 'include'
    assert checked.row(row['id'])['support_cycle'] == row['support_cycle']


def test_cycle_metadata_survives_slice_proc_and_declared_dimensions_are_preserved(recording, tmp_path):
    folder, header, raw, _, registration, result, digest = recording
    session = SceneReviewSession(result, digest)
    cycle = next(r for r in session.rows if 'support_cycle_return' in r['tags'])
    for row in session.rows:
        session.set_decision(row['id'], 'include' if row is cycle else 'exclude')
    payload = session.payload(cycle['id'])
    path = tmp_path / 'cycle.slice'
    save_slice_file(filepath=str(path), header_info=header, raw_data=raw,
        source_path=str(folder / 'observed.csv'), full_start=float(raw.Time.iloc[0]),
        full_end=float(raw.Time.iloc[-1]), user_start=cycle['start'], user_end=cycle['end'],
        box_dims=registration.profile['box_dims_mm'], pad_rows=0, scene_name='observed_cycle',
        scene_review_json=payload)
    meta = read_slice_metadata(str(path))
    saved = json.loads(meta.scene_review_json)
    assert saved['candidate']['support_cycle'] == cycle['support_cycle']
    assert saved['candidate']['activity_members'] == cycle['activity_members']
    assert saved['identity']['scenario_id'] is None
    context = WidgetSliceProcessing._build_timeline_context(SimpleNamespace(slice_metadata=meta))
    # Serialization contract only; actual pose processing is a separate execution.
    frame = pd.DataFrame({'Frame': [0, 1]}, index=pd.Index([cycle['start'], cycle['end']], name='Time'))
    proc = tmp_path / 'cycle.proc'
    save_proc_file(str(proc), add_timeline_context_columns(frame, context))
    reopened = DataLoader().load_result_csv(str(proc))
    assert reopened[('Info', 'SceneReview', 'Json')].tolist() == [meta.scene_review_json] * 2
    before = path.read_bytes()
    with pytest.raises(ValueError, match='conflict with declared artifact'):
        update_slice_box_dimensions(str(path), (301., 180., 90.))
    assert path.read_bytes() == before
