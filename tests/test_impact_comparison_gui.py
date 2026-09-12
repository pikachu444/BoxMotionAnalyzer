"""Real comparison widgets and serialized analytical inputs, not real trials."""
import time

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox

from impact_metric_fixtures import write_proc
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
        assert window.warning_label.text() == ('4 files. Repeat summary: 3 included, '
                                               '1 excluded. Select a file for details.')
        duplicate = window.control_panel.file_list.item(3)
        assert 'Repeat summary exclusion:' in duplicate.toolTip()
        assert 'already counted' in duplicate.toolTip()
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
