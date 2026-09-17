"""Actual Qt contact controls; public synthetic/constructed inputs only."""
from copy import deepcopy
import json
import time

import numpy as np
from PySide6.QtCore import Qt, QEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox

from impact_metric_fixtures import make_frame
from src.analysis.compare.main_window import CompareMainWindow
from src.analysis.pipeline.data_loader import DataLoader
from src.analysis.pipeline.parser import Parser
from src.analysis.ui.widget_raw_data_processing import WidgetRawDataProcessing
from src.config.data_columns import FACE_PREFIX_TO_INFO
from src.simulation.scene_fixtures import write_sequence


def _events(app):
    for _ in range(3):
        app.processEvents()
        app.sendPostedEvents(None, QEvent.DeferredDelete)
        time.sleep(.01)


def _wait_detection(widget, app):
    until = time.monotonic() + 20
    while widget.scene_busy or (widget.scene_worker and widget.scene_worker.isRunning()):
        _events(app)
        assert time.monotonic() < until, widget.log_output.toPlainText()
    _events(app)


def _set_contact(widget, faces, app):
    combo = widget.scene_panel.intended_combo
    index = 0 if faces is None else next(i for i in range(1, combo.count())
                                       if tuple(combo.itemData(i)) == tuple(sorted(faces)))
    combo.setCurrentIndex(index)
    QTest.mouseClick(widget.scene_panel.set_intended_button, Qt.LeftButton)
    _events(app)


def test_independent_intent_reopens_and_geometry_change_clears_it(tmp_path, monkeypatch):
    app = QApplication.instance() or QApplication([])
    folder = write_sequence(tmp_path / 'observations', 'drops')
    make_widget = lambda: WidgetRawDataProcessing(DataLoader(), Parser(FACE_PREFIX_TO_INFO))
    widget = make_widget()
    reopened = None
    try:
        widget.show()
        for button, path in [(widget.load_csv_button, folder / 'observed.csv'),
                             (widget.scene_panel.geometry_button, folder / 'registration.json')]:
            monkeypatch.setattr(QFileDialog, 'getOpenFileName', lambda *a, p=path, **kw: (str(p), ''))
            QTest.mouseClick(button, Qt.LeftButton)
            _events(app)
        QTest.mouseClick(widget.scene_panel.detect_button, Qt.LeftButton)
        _wait_detection(widget, app)
        row = next(row for row in widget.scene_session.rows if row['motion'] == 'free_fall')
        widget.scene_panel.refresh(row['id'])
        QTest.mouseClick(widget.scene_panel.include_button, Qt.LeftButton)
        _events(app)
        assert not row['item_candidates'] and not row['identity']['confirmed']
        assert widget.scene_panel.intended_combo.count() == 27
        _set_contact(widget, ('BOTTOM', 'LEFT'), app)
        intended = deepcopy(row['intended_contact'])
        assert intended['faces'] == ['BOTTOM', 'LEFT']
        workspace = tmp_path / 'unfinished.scene-review.json'
        monkeypatch.setattr(QFileDialog, 'getSaveFileName', lambda *a, **kw: (str(workspace), ''))
        QTest.mouseClick(widget.scene_panel.save_review_button, Qt.LeftButton)
        _events(app)
        saved = workspace.read_bytes()
        monkeypatch.setattr(QFileDialog, 'getSaveFileName', lambda *a, **kw: ('', ''))
        QTest.mouseClick(widget.scene_panel.save_review_button, Qt.LeftButton)
        assert workspace.read_bytes() == saved and row['intended_contact'] == intended
        widget.close()
        reopened = make_widget()
        reopened.show()
        monkeypatch.setattr(QFileDialog, 'getOpenFileName', lambda *a, **kw: (str(workspace), ''))
        QTest.mouseClick(reopened.scene_panel.open_review_button, Qt.LeftButton)
        _wait_detection(reopened, app)
        restored = reopened.scene_session.row(row['id'])
        reopened.scene_panel.refresh(row['id'])
        assert restored['intended_contact'] == intended
        assert reopened.scene_panel.intended_combo.currentText() == 'Bottom + Left'
        assert not reopened.scene_panel.save_all_button.isEnabled()  # remaining rows are unreviewed
        _set_contact(reopened, None, app)
        assert restored.get('intended_contact') is None
        _set_contact(reopened, ('BOTTOM', 'LEFT'), app)
        registration = json.loads((folder / 'registration.json').read_text())
        marker = next(m for m in registration['profile']['markers'] if abs(m['xyz_mm'][0]) < 149)
        marker['xyz_mm'][0] += .5
        changed = tmp_path / 'changed_registration.json'
        changed.write_text(json.dumps(registration))
        monkeypatch.setattr(QFileDialog, 'getOpenFileName', lambda *a, **kw: (str(changed), ''))
        QTest.mouseClick(reopened.scene_panel.geometry_button, Qt.LeftButton)
        _events(app)
        assert restored.get('intended_contact') is None
        assert restored['previous_review']['intended_contact'] == intended
        assert not reopened.scene_panel.set_intended_button.isEnabled()
        assert workspace.read_bytes() == saved
    finally:
        for instance in (widget, reopened):
            if instance is not None:
                if instance.scene_worker and instance.scene_worker.isRunning():
                    instance.scene_worker.requestInterruption()
                    _wait_detection(instance, app)
                instance.close()
        _events(app)


def test_contact_view_compares_exact_feature_and_excludes_conflicting_hypotheses(tmp_path, monkeypatch):
    app = QApplication.instance() or QApplication([])
    errors = []
    monkeypatch.setattr(QMessageBox, 'warning', lambda *args: errors.append(str(args[2])))
    # Explicit analytic approach to a horizontal floor followed by two supported
    # samples. This is a serialized GUI contract, not a processed physical trial.
    frame = make_frame(velocity=(0., -4., 0.), omega=(0., 0., 0.))
    frame[('Position', 'CoM', 'P_TY')] = np.maximum(60., frame[('Position', 'CoM', 'P_TY')])
    # Eight saved box corners are part of the contact-policy evidence. For this
    # unrotated 200x120x80 box their offsets are independently specified here.
    offsets = [(-100., -60., -40.), (100., -60., -40.),
               (100., 60., -40.), (-100., 60., -40.),
               (-100., -60., 40.), (100., -60., 40.),
               (100., 60., 40.), (-100., 60., 40.)]
    for i, (x, y, z) in enumerate(offsets, 1):
        frame[('Position', f'C{i}', 'P_TX')] = x
        frame[('Position', f'C{i}', 'P_TY')] = frame[('Position', 'CoM', 'P_TY')] + y
        frame[('Position', f'C{i}', 'P_TZ')] = z
    frame[('Analysis', 'DropPostureSummary', 'FirstImpactContact')] = '{C1,C2,C5,C6}'
    column = ('Info', 'SceneReview', 'Json')
    review = json.loads(frame[column].iloc[0])
    review['detection']['settings']['gap_factor'] = 2.5
    paths = []
    for name, faces in [('bottom', ['BOTTOM']), ('edge_hypothesis', ['BOTTOM', 'LEFT']), ('unspecified', None)]:
        payload = deepcopy(review)
        if faces:
            payload['candidate']['intended_contact'] = {
                'version': 1, 'basis': 'operator', 'faces': faces,
                'registration_sha256': payload['detection']['registration_sha256'],
                'ista_type': payload['identity']['ista_type'],
                'applied_edition': payload['identity']['applied_edition'],
            }
        copied = frame.copy(deep=True)
        copied[column] = json.dumps(payload)
        path = tmp_path / (name + '.proc')
        copied.to_csv(path, index=False)
        paths.append(path)
    window = CompareMainWindow()
    window.show()
    try:
        monkeypatch.setattr(QFileDialog, 'getOpenFileNames', lambda *a, **kw: ([str(p) for p in paths], ''))
        QTest.mouseClick(window.control_panel.btn_add_files, Qt.LeftButton)
        _events(app)
        window.table_panel.view_combo.setCurrentIndex(3)
        _events(app)
        table = window.table_panel.table
        assert [table.item(i, 3).text().split(' / ')[0] for i in range(3)] == ['Match', 'Different', 'Unclear']
        assert [table.item(i, 2).text() for i in range(2)] == ['Bottom', 'Bottom']
        assert 'No independent intended contact' in table.item(2, 3).toolTip()
        summary = window.model.get_contact_comparison()
        assert summary['statistics'] == {'n': 0, 'Match': 0, 'Different': 0, 'Unclear': 0, 'excluded': 3, 'conflicts': 1}
        assert all('Conflicting intended contacts' in table.item(i, 3).toolTip() for i in range(2))
        assert 'ineligible' in table.item(2, 3).text()
        assert 'No independent intended contact' in table.item(2, 3).toolTip()
        monkeypatch.setattr(QFileDialog, 'getOpenFileNames', lambda *a, **kw: ([], ''))
        QTest.mouseClick(window.control_panel.btn_add_files, Qt.LeftButton)
        assert table.rowCount() == 3
        window.control_panel.cb_baseline.setCurrentText(paths[1].name)
        _events(app)
        assert [table.item(i, 3).text().split(' / ')[0] for i in range(3)] == ['Match', 'Different', 'Unclear']
        assert window.model.get_contact_comparison()['statistics']['n'] == 0
        assert not errors
    finally:
        window.close()
        _events(app)
