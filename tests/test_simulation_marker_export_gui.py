"""Real Qt controls, MuJoCo worker, publication and Step 1 handoff."""
import builtins
import copy
import io
import json
from pathlib import Path
import threading
import time

import numpy as np
import pytest
from PySide6.QtCore import Qt, QTimer
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox

from src.simulation.ui.main_window import SimulationUI
from src.simulation.ui import marker_export_dialog
from src.simulation.marker_fixtures import example_profile


def wait_until(condition):
    deadline = time.monotonic() + 25
    while not condition() and time.monotonic() < deadline:
        QApplication.processEvents()
        time.sleep(.01)
    assert condition(), 'Qt operation did not complete'


@pytest.fixture
def gui():
    app = QApplication.instance() or QApplication([])
    app.setAttribute(Qt.AA_DontUseNativeDialogs, True)
    window = SimulationUI()
    window.duration_input.setValue(.5)
    assert window.duration_input.value() == .5
    window.custom_h_input.setValue(250)
    window.show()
    QTest.mouseClick(window.marker_btn, Qt.LeftButton)
    dialog = window.marker_dialog
    assert dialog is not None and dialog.isVisible()
    yield app, window, dialog
    if window.marker_dialog is not None:
        window.marker_dialog.cancel()
        wait_until(lambda: not dialog.busy)
        dialog.close()
    for analysis in list(window.analysis_windows):
        analysis.close()
    window.close()
    app.processEvents()


@pytest.mark.parametrize('kind', [None, 'missing', 'flip_180_local_axis'])
def test_generate_preview_and_open_observations_only(gui, monkeypatch, tmp_path, kind):
    app, window, dialog = gui
    assert not dialog.dimensions.isChecked() and not dialog.generate_button.isEnabled()
    # Preview reads the declared local marker coordinates without rescaling.
    plotted = np.concatenate([np.array(collection._offsets3d).T for collection in dialog.axes.collections
                              if hasattr(collection, '_offsets3d')])
    expected = np.array([m['xyz_mm'] for m in example_profile()['markers']])
    assert sorted(map(tuple, plotted)) == sorted(map(tuple, expected))
    QTest.mouseClick(dialog.dimensions, Qt.LeftButton)
    assert dialog.generate_button.isEnabled()
    dialog.fault_section.setExpanded(True)
    dialog.kind.setCurrentIndex(dialog.kind.findData(kind))
    dialog.start.setValue(.08); dialog.end.setValue(.16)
    dialog.axis.setCurrentText('Z')
    monkeypatch.setattr(QFileDialog, 'getExistingDirectory', lambda *a: str(tmp_path))
    errors = []
    monkeypatch.setattr(QMessageBox, 'warning', lambda *a: errors.append(a[2]))
    QTest.mouseClick(dialog.generate_button, Qt.LeftButton)
    assert dialog.busy and not dialog.open_button.isEnabled() and not dialog.controls.isEnabled()
    wait_until(lambda: not dialog.busy)
    assert not errors and dialog.observed_path and dialog.open_button.isEnabled(), dialog.status.text()
    path = Path(dialog.observed_path)
    before = {p.name: p.read_bytes() for p in path.parent.iterdir()}
    # Subsequent layout selection must not alter the dimensions of the already
    # generated file when the operator opens it.
    dialog.profile_combo.setCurrentIndex(1)
    forbidden = {'truth_pose.csv', 'truth_markers.csv', 'observed.synthetic.json'}
    def guarded(original):
        def opening(file, *args, **kwargs):
            if isinstance(file, (str, Path)):
                assert Path(file).name not in forbidden, 'Analysis accessed evaluation truth'
            return original(file, *args, **kwargs)
        return opening
    with monkeypatch.context() as guard:
        guard.setattr(builtins, 'open', guarded(builtins.open))
        guard.setattr(io, 'open', guarded(io.open))
        QTest.mouseClick(dialog.open_button, Qt.LeftButton)
    assert not errors and len(window.analysis_windows) == 1
    analysis = window.analysis_windows[0]
    analysis.resize(1510, 800)
    app.processEvents()
    raw = analysis.original_widget
    assert Path(raw.source_path) == path
    assert raw._read_box_dimensions() == (200, 120, 80)
    assert not raw.confirm_review_dimensions.isChecked()
    assert not raw.marker_correction_decisions
    assert len(raw.parsed_data) == 63 and np.isfinite(raw.parsed_data.F1_X.iloc[0])
    if kind == 'missing':
        assert raw.parsed_data.F1_X.iloc[10:20].isna().all()
    assert (window.w_input.value(), window.d_input.value(), window.h_input.value()) == (1578, 930, 142)
    assert before == {p.name: p.read_bytes() for p in path.parent.iterdir()}
    # A second open is a fresh window; existing Step 1 source/selection survives.
    raw.le_box_l.setText('201')
    QTest.mouseClick(dialog.open_button, Qt.LeftButton)
    assert len(window.analysis_windows) == 2 and raw.le_box_l.text() == '201'
    raw.le_box_l.setText('200')
    evidence = Path('tmp/issue114'); evidence.mkdir(parents=True, exist_ok=True)
    if kind is None:
        dialog.profile_combo.setCurrentIndex(0)
        dialog.grab().save(str(evidence / 'marker_export.png'))
        analysis.grab().save(str(evidence / 'step1.png'))
        report = dict(dialog_size=[dialog.width(), dialog.height()], step1_size=[analysis.width(), analysis.height()],
                      dpr=analysis.devicePixelRatioF(), samples=len(raw.parsed_data), observations_only=True)
        (evidence / 'gui.json').write_text(json.dumps(report, indent=2))
        assert report['step1_size'] == [1510, 800]
        assert dialog.rect().contains(dialog.open_button.geometry())


def test_import_validation_cancel_overwrite_and_retained_success(gui, tmp_path, monkeypatch):
    app, window, dialog = gui
    errors = []
    monkeypatch.setattr(QMessageBox, 'warning', lambda *a: errors.append(a[2]))
    profile = copy.deepcopy(example_profile())
    profile_id = 'custom-example-' + 'long-layout-name-' * 6
    profile.update(profile_id=profile_id, publication='user-supplied', source='test-declared-coordinates')
    profile['markers'] = [m for m in profile['markers'] if m['id'] != 'F4']
    for marker, x in zip([m for m in profile['markers'] if m['face'] == 'FRONT'], (-60., -20., 20.)):
        marker['xyz_mm'] = [x, 0., 40.]
    file = tmp_path / 'layout.json'; file.write_text(json.dumps(profile))
    monkeypatch.setattr(QFileDialog, 'getOpenFileName', lambda *a: (str(file), ''))
    QTest.mouseClick(dialog.import_button, Qt.LeftButton)
    assert dialog.profile == profile and dialog.profile_combo.currentText() == 'Imported: ' + profile_id
    plotted = np.concatenate([np.array(c._offsets3d).T for c in dialog.axes.collections
                              if hasattr(c, '_offsets3d')])
    assert sorted(map(tuple, plotted)) == sorted(tuple(m['xyz_mm']) for m in profile['markers'])
    file.write_text('[]')
    QTest.mouseClick(dialog.import_button, Qt.LeftButton)
    assert errors and dialog.profile == profile
    monkeypatch.setattr(QFileDialog, 'getOpenFileName', lambda *a: ('', ''))
    QTest.mouseClick(dialog.import_button, Qt.LeftButton)
    assert dialog.profile == profile
    QTest.mouseClick(dialog.dimensions, Qt.LeftButton)
    # Cancel the actual folder picker, without creating a worker or output.
    QTimer.singleShot(150, lambda: QApplication.activeModalWidget().reject())
    QTest.mouseClick(dialog.generate_button, Qt.LeftButton)
    assert not dialog.busy and not dialog.observed_path
    monkeypatch.setattr(QFileDialog, 'getExistingDirectory', lambda *a: str(tmp_path))
    existing = tmp_path / 'synthetic_markers'; existing.mkdir()
    (existing / 'keep.csv').write_text('old')
    QTest.mouseClick(dialog.generate_button, Qt.LeftButton)
    assert not dialog.busy and errors[-1].startswith('Choose a new')
    assert (existing / 'keep.csv').read_text() == 'old'
    dialog.output_name.setText('new-' + 'long-output-name-' * 6)
    QTest.mouseClick(dialog.generate_button, Qt.LeftButton)
    wait_until(lambda: not dialog.busy)
    success = dialog.observed_path
    assert success and dialog.open_button.isEnabled()
    QApplication.processEvents()
    assert dialog.width() == 1000 and dialog.height() == 700
    assert dialog.rect().contains(dialog.open_button.geometry())
    QTest.mouseClick(dialog.open_button, Qt.LeftButton)
    analysis = window.analysis_windows[-1]
    analysis.resize(1510, 800)
    app.processEvents()
    assert Path(analysis.original_widget.source_path) == Path(success)
    assert analysis.original_widget._read_box_dimensions() == (200, 120, 80)
    assert len(analysis.original_widget.parsed_data) == 63
    assert all(f'F{i}_X' in analysis.original_widget.parsed_data for i in (1, 2, 3))
    assert 'F4_X' not in analysis.original_widget.parsed_data
    assert not analysis.original_widget.confirm_review_dimensions.isChecked()
    evidence = Path('tmp/issue116'); evidence.mkdir(parents=True, exist_ok=True)
    assert analysis.devicePixelRatioF() == 1.25
    assert dialog.grab().save(str(evidence / 'imported-three.png'))
    assert analysis.grab().save(str(evidence / 'three-step1.png'))
    (evidence / 'gui.json').write_text(json.dumps(dict(logical_size=[analysis.width(), analysis.height()],
        dpr=analysis.devicePixelRatioF(), samples=63, imported_markers=17,
        note='Actual widget import, preview, export and Step 1 open; numeric Raw recovery has its own test.')))
    dialog.output_name.setText('failure')
    def fail(*args, **kwargs):
        raise OSError('injected export error')
    monkeypatch.setattr(marker_export_dialog, 'generate_marker_capture', fail)
    QTest.mouseClick(dialog.generate_button, Qt.LeftButton)
    wait_until(lambda: not dialog.busy)
    assert 'injected export error' in dialog.status.text()
    assert dialog.observed_path == success and dialog.open_button.isEnabled()
    assert dialog.generate_button.isEnabled() and not dialog.cancel_button.isEnabled()


def test_cancel_and_close_wait_for_running_worker(gui, monkeypatch, tmp_path):
    app, window, dialog = gui
    started = threading.Event()
    def cooperative(*args, cancelled, progress):
        started.set()
        while not cancelled():
            time.sleep(.01)
        raise InterruptedError()
    monkeypatch.setattr(marker_export_dialog, 'generate_marker_capture', cooperative)
    monkeypatch.setattr(QFileDialog, 'getExistingDirectory', lambda *a: str(tmp_path))
    QTest.mouseClick(dialog.dimensions, Qt.LeftButton)
    QTest.mouseClick(dialog.generate_button, Qt.LeftButton)
    wait_until(started.is_set)
    QTest.mouseClick(dialog.cancel_button, Qt.LeftButton)
    wait_until(lambda: not dialog.busy)
    assert 'Cancelled' in dialog.status.text() and not dialog.observed_path
    assert dialog.generate_button.isEnabled()
    started.clear()
    QTest.mouseClick(dialog.generate_button, Qt.LeftButton)
    wait_until(started.is_set)
    assert dialog.close() is False
    wait_until(lambda: window.marker_dialog is None)
    assert window.run_btn.isEnabled() and list(tmp_path.iterdir()) == []
