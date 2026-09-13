"""Scene-save handoff contracts; the writer is substituted, not capture accuracy."""
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest
from PySide6.QtWidgets import QApplication, QLabel, QFileDialog, QMessageBox

from src.analysis.ui import scene_review_flow as flow
from src.analysis.ui.widget_raw_data_processing import WidgetRawDataProcessing


@pytest.fixture
def reviewed(tmp_path, monkeypatch):
    app = QApplication.instance() or QApplication([])
    rows = [dict(id=name, start=start, end=end, decision=decision)
            for name, start, end, decision in [('first', .1, .3, 'include'), ('second', .4, .6, 'include'),
                                              ('handling', .7, .9, 'exclude')]]
    session = SimpleNamespace(rows=rows, all_reviewed=True)

    class Panel:
        current = 'first'

        def selected_row(self):
            return next(row for row in rows if row['id'] == self.current)

        def refresh(self, selected):
            self.current = selected

    panel = Panel()
    label = QLabel('Previous saved path')
    signals, logs = [], []
    host = SimpleNamespace(scene_session=session, scene_panel=panel,
        source_path=str(tmp_path / 'capture.csv'), parsed_data=pd.DataFrame(index=[0., 1.]),
        raw_data=pd.DataFrame(), correction_source_metadata=None, marker_review_dirty=False,
        marker_review_busy=False, scene_busy=False, slice_path_label=label,
        slice_saved=SimpleNamespace(emit=signals.append), append_log=logs.append,
        _validate_scene_source=lambda: None, _read_box_dimensions=lambda: (200., 120., 80.),
        _scene_slice_context=lambda: ({}, panel.current))
    monkeypatch.setattr(QFileDialog, 'getExistingDirectory', lambda *_args: str(tmp_path))
    monkeypatch.setattr(QMessageBox, 'warning', lambda *_args: None)
    yield host, signals, tmp_path
    label.deleteLater()
    app.processEvents()


def test_reviewed_scene_save_returns_exact_included_files_and_restores_selection(reviewed, monkeypatch):
    host, signals, _tmp_path = reviewed
    requests = []

    def save(**request):
        requests.append(request)
        Path(request['filepath']).write_text(request['scene_review_json'], encoding='utf-8')

    monkeypatch.setattr(flow, 'save_slice_file', save)
    result = flow.SceneReviewFlow.save_included_scenes(host)
    assert result == signals and len(result) == 2
    assert [request['scene_name'] for request in requests] == ['first', 'second']
    assert [(request['user_start'], request['user_end']) for request in requests] == [(.1, .3), (.4, .6)]
    assert [Path(path).read_text(encoding='utf-8') for path in result] == ['first', 'second']
    assert host.scene_panel.current == 'first'


def test_partial_scene_save_returns_no_handoff_and_keeps_written_file(reviewed, monkeypatch):
    host, signals, _tmp_path = reviewed

    def save(**request):
        if request['scene_name'] == 'second':
            raise OSError('injected second save failure')
        Path(request['filepath']).write_text('first saved', encoding='utf-8')

    monkeypatch.setattr(flow, 'save_slice_file', save)
    assert flow.SceneReviewFlow.save_included_scenes(host) == []
    assert len(signals) == 1 and Path(signals[0]).read_text(encoding='utf-8') == 'first saved'
    assert host.slice_path_label.text() == 'Previous saved path'
    assert host.scene_panel.current == 'first'


def test_manual_scene_processing_handoff_and_cancel_keep_save_only_separate():
    path = 'C:/saved/manual.slice'
    host = SimpleNamespace(scene_session=None, _save_slice=lambda: True, last_saved_slice_path=path)
    assert WidgetRawDataProcessing.save_for_processing(host) == [path]
    host._save_slice = lambda: False
    assert WidgetRawDataProcessing.save_for_processing(host) == []
    host.scene_session = object()
    host.save_included_scenes = lambda: ['C:/saved/first.slice', 'C:/saved/second.slice']
    assert WidgetRawDataProcessing.save_for_processing(host) == host.save_included_scenes()


def test_explicit_restored_scene_scrolls_into_view_without_resetting_manual_scroll():
    """Widget-only viewport check; no detector, solver, or workspace file writes."""
    from src.analysis.ui.widget_scene_review import SceneReviewWidget
    app = QApplication.instance() or QApplication([])
    panel = SceneReviewWidget()
    rows = [dict(id=f'scene_{i + 1:03}', start=i * .2, end=i * .2 + .1,
        motion='stationary', rotation_deg=0., decision='include',
        identity={'scenario_id': None, 'confirmed': False}, item_candidates=[], tags=[],
        left_censored=False, right_censored=False, evidence_status='current') for i in range(9)]
    rows[3].update(start=1.584, end=1.848)
    panel.session = SimpleNamespace(rows=rows, all_reviewed=True, trial_record=None,
        applied_edition=None, result=SimpleNamespace(registration=None),
        row=lambda row_id: next(row for row in rows if row['id'] == row_id))
    selected = []
    panel.row_selected.connect(selected.append)
    try:
        panel.table.setFixedHeight(110)
        panel.resize(900, 240)
        panel.show()
        app.processEvents()
        panel.refresh('scene_004')
        app.processEvents()
        item = panel.table.item(3, 0)
        assert panel.selected_id() == 'scene_004'
        assert selected[-1]['start'] == 1.584 and selected[-1]['end'] == 1.848
        assert panel.table.viewport().rect().contains(panel.table.visualItemRect(item))
        # A user can inspect earlier rows while retaining the active range.
        panel.table.verticalScrollBar().setValue(0)
        app.processEvents()
        panel.refresh()
        app.processEvents()
        assert panel.selected_id() == 'scene_004'
        assert panel.table.verticalScrollBar().value() == 0
        panel.refresh('scene_009')
        app.processEvents()
        assert panel.table.viewport().rect().contains(panel.table.visualItemRect(panel.table.item(8, 0)))
    finally:
        panel.close()
        panel.deleteLater()
        app.processEvents()
