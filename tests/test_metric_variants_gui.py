"""Retained real Qt/VTK evidence at the approved logical size and measured DPR."""
import hashlib
import json
from pathlib import Path
import uuid

import numpy as np
from scipy.spatial.transform import Rotation
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from test_contact_comparison import contact_frame
from test_impact_comparison_gui import _load, _events, _metric_row
from src.analysis.compare.main_window import CompareMainWindow


def test_variant_resolution_in_real_comparison_at_125_percent(monkeypatch):
    out = Path('tmp/issue119') / ('qt_' + uuid.uuid4().hex[:8])
    out.mkdir(parents=True)
    frames = {'invalid.proc': contact_frame(), 'valid.proc': contact_frame(), 'copy.proc': contact_frame()}
    frames['invalid.proc'].loc[7, ('Position', 'CoM', 'P_TY')] = np.nan
    frames['invalid.proc'].loc[10, ('Position', 'CoM', 'P_RX')] = np.nan
    paths = []
    for name, frame in frames.items():
        path = out / name
        frame.to_csv(path, index=False)
        paths.append(path)
    app = QApplication.instance() or QApplication([])
    window = CompareMainWindow()
    window.resize(1510, 800)
    window.move(0, 0)
    window.show()
    _events(app)
    report = {'interaction': 'QTest on real Qt/VTK widgets; file-dialog paths injected',
              'oracle': 'One capture/interval: valid + invalid + equal copy = n 1; valid conflicting contact = n 0',
              'seed': None, 'screens': [], 'baseline_checks': []}

    def capture(name):
        _events(app)
        window.grab().save(str(out / name))
        report['screens'].append(name)

    try:
        _load(window, paths, monkeypatch, app)
        report.update(logical_size=[window.width(), window.height()], dpr=window.devicePixelRatioF())
        assert report['logical_size'] == [1510, 800]
        assert report['dpr'] == 1.25
        panel = window.table_panel
        panel.view_combo.setCurrentIndex(1)
        row = _metric_row(panel.table, 'Vertical velocity')
        panel.table.setCurrentCell(row, 0)
        QTest.mouseClick(window.control_panel.details_section.button, Qt.LeftButton)
        for path in paths:
            combo = window.control_panel.cb_baseline
            combo.setFocus()
            QTest.keyClick(combo, Qt.Key_Home)
            for _ in range(combo.findText(path.name)):
                QTest.keyClick(combo, Qt.Key_Down)
            _events(app)
            assert panel.table.item(row, 1).text() == '1 (low)'
            assert panel.resolution_label.text().startswith('Duplicate 1   Invalid 1   Conflict 0')
            assert window.model.get_contact_comparison()['statistics']['n'] == 1
            report['baseline_checks'].append(dict(baseline=window.model.baseline_name,
                numeric_n=1, contact_n=1, details=window.control_panel.details.toPlainText()))
        assert panel.table.rowHeight(row) <= panel.table.viewport().height()
        capture('01_repeats.png')
        panel.view_combo.setCurrentIndex(3)
        assert 'invalid' in panel.table.item(0, 3).text()
        assert 'equivalent' in panel.table.item(1, 3).text()
        capture('02_contact.png')
        conflict = out / 'conflict.proc'
        contact_frame(observed='{C1,C5}', rotation=Rotation.from_euler('z', 30, degrees=True)).to_csv(conflict, index=False)
        paths.append(conflict)
        _load(window, [conflict], monkeypatch, app)
        assert window.model.get_contact_comparison()['statistics']['n'] == 0
        assert window.model.get_contact_comparison()['statistics']['conflicts'] == 1
        assert 'conflict' in panel.table.item(1, 3).text()
        capture('03_contact_conflict.png')
        panel.view_combo.setCurrentIndex(1)
        row = _metric_row(panel.table, 'First contact')
        panel.table.setCurrentCell(row, 0)
        panel.table.scrollToItem(panel.table.item(row, 0))
        assert panel.table.item(row, 1).text() == '0 (low)'
        assert 'Conflict 1' in panel.resolution_label.text()
        assert 'Conflicting valid variants' in window.control_panel.details.toPlainText()
        capture('04_categorical_conflict.png')
        window.control_panel.file_list.setCurrentRow(1)
        _events(app)
        viewer = window.playback_panel.widgets['valid.proc']
        viewer.plotter.render()
        pixels = viewer.plotter.screenshot(str(out / 'vtk.png'))
        assert pixels is not None and pixels.shape[1] > 500 and pixels.shape[0] > 100 and pixels.std() > 1
        report['screens'].append('vtk.png')
        report['inputs'] = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
        report['contact_statistics'] = window.model.get_contact_comparison()['statistics']
        report['result'] = 'passed'
    finally:
        (out / 'execution.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
        window.close()
        _events(app)
