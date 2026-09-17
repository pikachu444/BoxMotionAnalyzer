"""Real comparison widgets and serialized analytical inputs, not real trials."""
import time

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox

from impact_metric_fixtures import write_proc, make_frame, SUMMARY
from src.analysis.compare.main_window import CompareMainWindow


def _events(app):
    for _ in range(3):
        app.processEvents()
        time.sleep(.01)


def _metric_row(table, label):
    return next(row for row in range(table.rowCount())
                if table.item(row, 0).text().startswith(label))


def _load(window, paths, monkeypatch, app):
    monkeypatch.setattr(QFileDialog, 'getOpenFileNames', lambda *args, **kwargs: ([str(p) for p in paths], ''))
    QTest.mouseClick(window.control_panel.btn_add_files, Qt.LeftButton)
    _events(app)


def test_metric_variants_keep_counts_and_expose_reasons_on_baseline_change(tmp_path, monkeypatch):
    import numpy as np
    app = QApplication.instance() or QApplication([])
    frames = [make_frame(), make_frame(), make_frame(), make_frame(source_sha256='b' * 64, velocity=(3., -2., 0.))]
    frames[0].loc[2, ('Position', 'CoM', 'P_TY')] = np.nan
    paths = [tmp_path / name for name in ('invalid.proc', 'valid.proc', 'copy.proc', 'trial_b.proc')]
    for path, frame in zip(paths, frames):
        frame.to_csv(path, index=False)
    window = CompareMainWindow()
    window.resize(1510, 800)
    window.show()
    _events(app)
    try:
        _load(window, paths, monkeypatch, app)
        panel = window.table_panel
        panel.view_combo.setCurrentIndex(1)
        row = _metric_row(panel.table, 'Vertical velocity')
        panel.table.setCurrentCell(row, 0)
        QTest.mouseClick(window.control_panel.details_section.button, Qt.LeftButton)
        window.control_panel.file_list.setCurrentRow(1)
        _events(app)
        assert window.control_panel.details.toPlainText().startswith('Vertical velocity')
        assert 'Vertical velocity' in window.control_panel.file_list.item(1).toolTip()
        QTest.mouseClick(panel.table.viewport(), Qt.LeftButton,
                         pos=panel.table.visualItemRect(panel.table.item(row, 0)).center())
        assert window.control_panel.details.toPlainText().startswith('Vertical velocity')
        for path in paths:
            window.control_panel.cb_baseline.setCurrentText(path.name)
            _events(app)
            assert [panel.table.item(row, col).text() for col in (1, 2, 3, 4, 5)] == ['2 (low)', '-3', '-4', '-2', '2']
            assert panel.resolution_label.text().startswith('Duplicate 1   Invalid 1   Conflict 0')
            details = window.control_panel.details.toPlainText()
            assert 'Sources:' in details and 'valid.proc' in details and 'copy.proc' in details
            assert 'invalid.proc: invalid' in details and 'SHA-256:' in details
            assert panel.table.currentRow() == row
        conflict = tmp_path / 'conflict.proc'
        make_frame(velocity=(3., -3., 0.)).to_csv(conflict, index=False)
        _load(window, [conflict], monkeypatch, app)
        assert panel.table.item(row, 1).text() == '1 (low)'
        assert 'Conflict 1' in panel.resolution_label.text()
        assert 'Conflicting valid variants' in window.control_panel.details.toPlainText()
        assert 'invalid.proc: invalid' in window.control_panel.details.toPlainText()
        panel.view_combo.setCurrentIndex(3)
        _events(app)
        assert window.control_panel.details.toPlainText().startswith('Contact\n')
        panel.view_combo.setCurrentIndex(2)
        _events(app)
        assert window.control_panel.details.toPlainText() == window.control_panel.file_list.currentItem().toolTip()
        _load(window, [], monkeypatch, app)
        assert len(window.model.datasets) == 5
    finally:
        window.close()
        _events(app)


def test_distinct_repeat_count_survives_duplicate_baseline_remove_and_reload(tmp_path, monkeypatch):
    app = QApplication.instance() or QApplication([])
    errors = []
    monkeypatch.setattr(QMessageBox, 'warning', lambda *args: errors.append(str(args[2])))
    paths = [write_proc(tmp_path / f'trial_{i}.proc', velocity=(0., -float(i), 0.),
                        source_sha256=str(i) * 64) for i in (1, 2, 3)]
    window = CompareMainWindow()
    window.show()
    _events(app)
    try:
        _load(window, paths, monkeypatch, app)
        panel = window.table_panel
        panel.view_combo.setCurrentIndex(1)
        _events(app)
        row = _metric_row(panel.table, 'Vertical velocity')
        assert [panel.table.item(row, col).text() for col in (1, 2, 3, 4, 5)] == ['3', '-2', '-3', '-1', '2']
        _load(window, [paths[0]], monkeypatch, app)
        assert len(window.model.datasets) == 4
        assert window.warning_label.text() == '4 files   3 compatible observations'
        duplicate = window.control_panel.file_list.item(3)
        assert 'equivalent' in duplicate.toolTip()
        row = _metric_row(panel.table, 'Vertical velocity')
        assert panel.table.item(row, 1).text() == '3'
        assert panel.table.item(row, 2).text() == '-2'
        window.control_panel.cb_baseline.setCurrentText(paths[1].name)
        _events(app)
        assert window.model.baseline_name == paths[1].name
        assert panel.table.item(_metric_row(panel.table, 'Vertical velocity'), 1).text() == '3'
        files = window.control_panel.file_list
        for index in range(files.count()):
            if files.item(index).data(Qt.UserRole) == paths[1].name:
                files.setCurrentRow(index)
                break
        QTest.mouseClick(window.control_panel.btn_remove_file, Qt.LeftButton)
        _events(app)
        assert paths[1].name not in window.model.datasets
        row = _metric_row(panel.table, 'Vertical velocity')
        assert panel.table.item(row, 1).text() == '2 (low)'
        assert panel.table.item(row, 2).text() == '-2'
        _load(window, [paths[1]], monkeypatch, app)
        assert panel.table.item(_metric_row(panel.table, 'Vertical velocity'), 1).text() == '3'
        before = list(window.model.datasets)
        _load(window, [], monkeypatch, app)
        assert list(window.model.datasets) == before
        while window.control_panel.file_list.count():
            window.control_panel.file_list.setCurrentRow(0)
            QTest.mouseClick(window.control_panel.btn_remove_file, Qt.LeftButton)
            _events(app)
        assert panel.table.rowCount() == 0 and panel.table.columnCount() == 0
        assert window.model.baseline_name is None
        assert not errors
    finally:
        window.close()
        _events(app)


def test_unconfirmed_h_height_has_visible_reason_and_modes_do_not_hide_it(tmp_path, monkeypatch):
    app = QApplication.instance() or QApplication([])
    errors = []
    monkeypatch.setattr(QMessageBox, 'warning', lambda *args: errors.append(str(args[2])))
    path = write_proc(tmp_path / 'unconfirmed_h.proc', ista_type='H', confirmed=False)
    window = CompareMainWindow()
    window.show()
    _events(app)
    try:
        _load(window, [path], monkeypatch, app)
        panel = window.table_panel
        row = _metric_row(panel.table, 'Velocity-equivalent height')
        assert panel.table.item(row, 1).text() == '—'
        assert 'confirmed 2018-03 Type G free fall' in panel.table.item(row, 1).toolTip()
        for index in (1, 2, 0):
            panel.view_combo.setCurrentIndex(index)
            _events(app)
            assert panel.table.rowCount() > 0
        row = _metric_row(panel.table, 'Velocity-equivalent height')
        assert panel.table.item(row, 1).text() == '—'
        assert 'confirmed 2018-03 Type G free fall' in panel.table.item(row, 1).toolTip()
        assert not errors
    finally:
        window.close()
        _events(app)


def test_stale_contact_reasons_and_confidence_state_survive_mode_changes(tmp_path, monkeypatch):
    app = QApplication.instance() or QApplication([])
    frame = make_frame()
    frame[(*SUMMARY, 'ImpactDetected')] = False
    frame[(*SUMMARY, 'ContactState')] = 'NoContact'
    stale = tmp_path / 'stale.proc'
    frame.to_csv(stale, index=False)
    valid = write_proc(tmp_path / 'valid.proc', source_sha256='b' * 64)
    window = CompareMainWindow()
    window.resize(1510, 800)
    window.show()
    _events(app)
    try:
        _load(window, [stale], monkeypatch, app)
        panel = window.table_panel
        panel.view_combo.setCurrentIndex(1)
        _events(app)
        for label in ('First contact', 'Contact confidence'):
            row = _metric_row(panel.table, label)
            assert panel.table.item(row, 1).text() == '0 (low)'
            assert 'conflicts' in panel.table.item(row, 1).toolTip()
            assert panel.table.item(row, 6).text() == 'Unavailable'
        panel.view_combo.setCurrentIndex(2)
        _events(app)
        row = _metric_row(panel.table, 'First impact contact')
        assert panel.table.item(row, 1).text().startswith('Unavailable —')
        assert 'conflicts' in panel.table.item(row, 1).text()
        assert 'Saved value: {C1,C2}' in panel.table.item(row, 1).toolTip()
        _load(window, [valid], monkeypatch, app)
        panel.view_combo.setCurrentIndex(1)
        assert panel.table.item(_metric_row(panel.table, 'First contact'), 1).text() == '1 (low)'
        panel.view_combo.setCurrentIndex(2)
        row = _metric_row(panel.table, 'Contact confidence')
        assert panel.table.item(row, 2).text() == '0.75 (ImpactEvent)'
        assert 'not a calibrated probability' in panel.table.item(row, 2).toolTip()
        for mode in (0, 3, 1, 2):
            panel.view_combo.setCurrentIndex(mode)
            _events(app)
        assert panel.table.item(_metric_row(panel.table, 'First impact contact'), 1).text().startswith('Unavailable')
    finally:
        window.close()
        _events(app)


def test_no_impact_confidence_is_separate_and_malformed_score_is_not_displayed_as_valid(tmp_path, monkeypatch):
    import numpy as np
    app = QApplication.instance() or QApplication([])
    paths = []
    for label, score in [('sustained', .2), ('invalid_score', 1.1)]:
        frame = make_frame(source_sha256=('c' if score == .2 else 'd') * 64)
        for name in ('T1Detected', 'ImpactDetected'):
            frame[(*SUMMARY, name)] = False
        for name in ('T1MinusTimeSec', 'FirstImpactTimeSec', 'FirstImpactContact'):
            frame[(*SUMMARY, name)] = np.nan
        frame[(*SUMMARY, 'ContactState')] = 'SustainedContact'
        frame[(*SUMMARY, 'ContactConfidence')] = score
        path = tmp_path / (label + '.proc')
        frame.to_csv(path, index=False)
        paths.append(path)
    window = CompareMainWindow()
    window.show()
    _events(app)
    try:
        _load(window, paths, monkeypatch, app)
        panel = window.table_panel
        panel.view_combo.setCurrentIndex(2)
        row = _metric_row(panel.table, 'Contact confidence')
        assert panel.table.item(row, 1).text() == '0.2 (SustainedContact; not pooled)'
        assert panel.table.item(row, 2).text() == 'Unavailable — invalid saved value'
        assert 'ContactConfidence: outside' in panel.table.item(row, 2).toolTip()
        assert window.model.get_impact_comparison()['statistics']['contact_confidence']['n'] == 0
    finally:
        window.close()
        _events(app)


def test_public_event_display_retains_real_qt_screens_and_literal_counts(tmp_path, monkeypatch):
    """Actual Qt/VTK widgets; dialog selection is injected, not native OS input."""
    import hashlib
    import json
    from pathlib import Path
    import uuid
    from test_contact_comparison import contact_frame
    app = QApplication.instance() or QApplication([])
    out = Path('tmp/issue118') / ('qt_' + uuid.uuid4().hex[:8])
    out.mkdir(parents=True)
    paths = []
    for name, source in [('valid', 'a'), ('stale', 'b')]:
        frame = contact_frame(source=source * 64)
        if name == 'stale':
            frame[(*SUMMARY, 'ImpactDetected')] = False
            frame[(*SUMMARY, 'ContactState')] = 'NoContact'
        path = out / (name + '.proc')
        frame.to_csv(path, index=False)
        paths.append(path)
    window = CompareMainWindow()
    window.resize(1510, 800)
    window.move(0, 0)
    window.show()
    _events(app)
    evidence = {'interaction': 'QTest on real Qt widgets; file selection injected',
                'inputs': {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},
                'screens': []}
    try:
        _load(window, paths, monkeypatch, app)
        assert window.size().width() == 1510 and window.size().height() == 800
        evidence['logical_size'] = [window.width(), window.height()]
        evidence['dpr'] = window.devicePixelRatioF()
        panel = window.table_panel
        # Keyboard events operate the actual combo and scroll the actual table.
        panel.view_combo.setFocus()
        QTest.keyClick(panel.view_combo, Qt.Key_Home)
        QTest.keyClick(panel.view_combo, Qt.Key_Down)
        _events(app)
        row = _metric_row(panel.table, 'First contact')
        assert panel.table.item(row, 1).text() == '1 (low)'
        assert 'stale.proc' in panel.table.item(row, 1).toolTip()
        panel.table.scrollToItem(panel.table.item(row, 1))
        _events(app)
        window.grab().save(str(out / 'repeats.png'))
        evidence['screens'].append('repeats.png')
        QTest.keyClick(panel.view_combo, Qt.Key_Down)
        _events(app)
        row = _metric_row(panel.table, 'First impact contact')
        assert panel.table.item(row, 1).text() == '{C1,C2,C5,C6}'
        assert panel.table.item(row, 2).text().startswith('Unavailable')
        panel.table.scrollToItem(panel.table.item(row, 2))
        _events(app)
        window.grab().save(str(out / 'details.png'))
        evidence['screens'].append('details.png')
        row_height = panel.table.rowHeight(row)
        evidence['first_contact_row_height'] = row_height
        evidence['table_viewport_height'] = panel.table.viewport().height()
        assert row_height <= panel.table.viewport().height()
        # QWidget grabs do not reliably contain the OpenGL child; retain an
        # actual VTK render separately, never describe a black Qt child as proof.
        viewer = window.playback_panel.widgets[paths[0].name]
        viewer.plotter.render()
        rendered = viewer.plotter.screenshot(str(out / 'vtk.png'))
        assert rendered is not None and rendered.std() > 1
        evidence['screens'].append('vtk.png')
        evidence['statistics'] = window.model.get_impact_comparison()['statistics']
        evidence['first_contact_reason'] = panel.table.item(row, 2).toolTip()
        assert evidence['statistics']['first_contact']['n'] == 1
        assert evidence['statistics']['contact_confidence']['n'] == 1
        assert evidence['statistics']['contact_confidence']['mean'] == .75
        assert window.model.get_contact_comparison()['statistics']['Match'] == 1
        assert window.model.get_contact_comparison()['statistics']['Unclear'] == 1
        # Reopen the same public files in a fresh model, retaining their bytes.
        from src.analysis.compare.data_model import ComparisonModel
        reopened = ComparisonModel()
        for path in paths:
            reopened.load_file(str(path))
            assert hashlib.sha256(path.read_bytes()).hexdigest() == evidence['inputs'][path.name]
        assert reopened.get_impact_comparison()['statistics'] == evidence['statistics']
        (out / 'execution.json').write_text(json.dumps(evidence, indent=2), encoding='utf-8')
    finally:
        window.close()
        _events(app)
