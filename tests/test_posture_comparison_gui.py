"""Actual Qt/VTK interaction with analytic trials and a public raw-pipeline result."""
import hashlib
import json
from pathlib import Path
import platform
import uuid

from PySide6.QtCore import Qt, QPoint
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from test_posture_comparison import posture_frame
from test_impact_comparison_gui import _load, _events, _metric_row
from test_general_export_recovery import specified_input, observed_only, persist_and_process
from src.simulation.corruption_export import write_observations
from src.simulation.marker_fixtures import example_profile
from src.analysis.pipeline.data_loader import DataLoader
from src.analysis.pipeline.artifact_io import save_proc_file
from src.utils.artifact_metadata import add_artifact_columns
from src.analysis.compare.main_window import CompareMainWindow
from src.config import config_app


def _choose(combo, index, app):
    combo.setFocus()
    QTest.keyClick(combo, Qt.Key_Home)
    for _ in range(index):
        QTest.keyClick(combo, Qt.Key_Down)
    _events(app)


def test_posture_repeats_in_real_window_with_observed_only_pipeline(monkeypatch):
    out = Path('tmp/issue117') / ('qt_' + uuid.uuid4().hex[:8])
    out.mkdir(parents=True)
    monkeypatch.setattr(config_app, 'BOX_DIMS', config_app.BOX_DIMS.copy())
    monkeypatch.setattr(config_app, 'LOCAL_BOX_CORNERS', config_app.LOCAL_BOX_CORNERS.copy())
    app = QApplication.instance() or QApplication([])
    window = CompareMainWindow()
    window.resize(1510, 800)
    window.move(0, 0)
    window.show()
    _events(app)
    report = dict(result='failed', interaction='Actual Qt/VTK with QTest; file-dialog paths supplied',
                  python=platform.python_version(), oracle='Declared Rz 10/20/30 degrees; mean20/min10/max30/range20. Three independent captures and one copy.',
                  seed=74082, screenshots=[])
    paths = []
    def capture(name):
        _events(app)
        assert window.grab().save(str(out / name))
        report['screenshots'].append(name)
    try:
        assert [window.width(), window.height()] == [1510, 800]
        assert window.devicePixelRatioF() == 1.25
        report.update(logical_size=[1510,800], dpr=window.devicePixelRatioF())
        for name, angle, source in [('trial-a',10,'a'), ('trial-b',20,'b'), ('trial-c',30,'c'), ('copy-a',10,'a')]:
            path = out / (name + '.proc')
            posture_frame(angle, source*64).to_csv(path, index=False)
            paths.append(path)
        _load(window, paths, monkeypatch, app)
        panel = window.table_panel
        handle = window.right_splitter.handle(1)
        start = handle.rect().center()
        QTest.mousePress(handle, Qt.LeftButton, pos=start)
        QTest.mouseMove(handle, start + QPoint(0, 90))
        QTest.mouseRelease(handle, Qt.LeftButton, pos=start + QPoint(0, 90))
        _events(app)
        assert window.graph_panel.cb_plot_target.count() == 5
        assert window.graph_panel.plot_manager.ax.lines[0].get_ydata()[0] == 10
        _choose(panel.view_combo, 4, app)
        assert panel.validation_badge.text() == 'Diagnostic'
        assert panel.table.item(_metric_row(panel.table, 'Pre-contact Beta'), 1).text() == '10'
        gap = _metric_row(panel.table, 'Lowest-corner uniqueness gap')
        assert '(mm)' in panel.table.item(gap, 0).text()
        assert panel.table.item(gap, 1).text() == '0'
        assert 'not confidence' in panel.table.item(gap, 0).toolTip()
        panel.table.scrollToItem(panel.table.item(gap, 0))
        capture('01_posture.png')
        _choose(panel.view_combo, 5, app)
        row = _metric_row(panel.table, 'Pre-contact Beta')
        assert [panel.table.item(row, col).text() for col in range(1,6)] == ['3','20','10','30','20']
        panel.table.setCurrentCell(row, 0)
        QTest.mouseClick(window.control_panel.details_section.button, Qt.LeftButton)
        assert 'Duplicate 1' in panel.resolution_label.text()
        capture('02_repeats.png')
        corner = _metric_row(panel.table, 'Pre-contact lowest corner')
        panel.table.setCurrentCell(corner, 0)
        panel.table.scrollToItem(panel.table.item(corner, 0))
        assert panel.table.item(corner, 6).text() == 'Non-unique {C1,C5}: 3'
        assert panel.table.item(corner, 2).text() == '—'
        assert panel.table.item(corner, 7).text() == '—'
        capture('03_corner_counts.png')
        window.control_panel.file_list.setCurrentRow(1)
        selected = window.control_panel.selected_file
        _choose(window.control_panel.cb_baseline, 2, app)
        assert window.control_panel.selected_file == selected
        assert panel.view_combo.currentIndex() == 5
        assert window.model.get_posture_comparison()['statistics']['beta']['n'] == 3
        viewer = window.playback_panel.widgets[selected]
        viewer.plotter.render()
        pixels = viewer.plotter.screenshot(str(out / 'vtk.png'))
        assert pixels.std() > 1 and pixels.shape[1] > 500
        report['screenshots'].append('vtk.png')
        # Exercise existing aligned playback and graph metric controls as widgets.
        _choose(window.control_panel.cb_view, 1, app)
        assert len(window.graph_panel.plot_manager.ax.lines) >= 4
        QTest.mouseClick(window.playback_panel.btn_master_play, Qt.LeftButton)
        # The 96 ms interval may finish during a render; test pause synchronously
        # before yielding to that wall-clock-driven playback timer.
        assert window.playback_panel.master_timer.isActive()
        QTest.mouseClick(window.playback_panel.btn_master_play, Qt.LeftButton)
        assert not window.playback_panel.master_timer.isActive()
        for mode in (0,1,2,3,4,5):
            _choose(panel.view_combo, mode, app)
            assert panel.table.rowCount() > 0
        # Public generator -> normal CSV reader -> real optimizer -> normal .proc
        # writer -> actual Compare open. Evaluation files cannot be read.
        trajectory, spec, _ = specified_input('healthy')
        profile = example_profile()
        root = write_observations(out / 'public-input', trajectory, profile, spec, 74082)
        with observed_only(monkeypatch, root):
            header, raw = DataLoader().load_csv(str(root / 'observed.csv'))
            result, _, _, _ = persist_and_process(root, out / 'processed', header, raw, [], profile)
            path = out / 'public-processed.proc'
            save_proc_file(str(path), add_artifact_columns(result, header['artifact_metadata']))
            _load(window, [path], monkeypatch, app)
        paths.append(path)
        numeric = window.model.posture_results[path.name].metrics['max_beta']
        assert numeric.value is not None, numeric.reason
        assert abs(numeric.value) < .1  # Declared fixed orientation; same published synthetic pose bound.
        report['public_pipeline_max_beta_deg'] = numeric.value
        assert window.model.get_posture_comparison()['statistics']['beta']['n'] == 3
        assert panel.view_combo.currentIndex() == 5
        _choose(panel.view_combo, 4, app)
        capture('04_public_pipeline.png')
        report['inputs'] = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
        report['result'] = 'passed'
    finally:
        (out / 'execution.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
        window.close()
        _events(app)
