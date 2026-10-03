"""Preapproval Qt prototype only; does not modify production classes (#137)."""
from __future__ import annotations

import argparse
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import platform
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))

import matplotlib
import numpy as np
import pandas as pd
import PySide6
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QLabel, QPushButton, QScrollArea, QSplitter

from src.analysis.app.main_window import MainApp
from src.analysis.pipeline.scene_detection import DetectionResult, DetectionSettings, SceneCandidate
from src.analysis.pipeline.scene_review import SceneReviewSession
from src.simulation.corruption_export import write_observations
from src.simulation.marker_fixtures import example_profile

PLAN_SPEC = 'ISTA6A-PLAN-20261001-v1'
VERTICAL = 'Vertical speed (mm/s)'
ROTATION = 'Relative rotation (deg)'
STATES = ('empty', 'one', 'many', 'edited', 'manual', 'blocked', 'loading', 'error', 'details')


def public_input(root):
    """Declared analytic observations, independent of production detection."""
    t = np.arange(601) * .02
    origins = np.column_stack((20 + 30*t, 1000 + 100*np.sin(.8*t), t*0))
    angle = np.deg2rad(15*np.sin(t))
    rotations = np.repeat(np.eye(3)[None], len(t), axis=0)
    rotations[:, 0, 0] = rotations[:, 1, 1] = np.cos(angle)
    rotations[:, 0, 1], rotations[:, 1, 0] = -np.sin(angle), np.sin(angle)
    folder = root / ('observations-' + str(time.time_ns()))
    trajectory = dict(schema_version=1, source_kind='handcrafted_dummy',
        coordinate_policy='world-y-up-box-local-fixed-center-v1', time_s=t,
        body_origin_mm=origins, rotation_matrix=rotations, frame=np.arange(len(t)))
    write_observations(folder, trajectory, example_profile(), dict(schema_version=1, events=[]))
    source = folder / ('public_synthetic_scene_review_long_capture_filename_' * 3 + '.csv')
    (folder / 'observed.csv').rename(source)
    return source, t, origins, rotations


def prototype(source, t, origins, rotations, state, size):
    window = MainApp()
    window.setWindowTitle('Scene review #137 — PREAPPROVAL MOCKUP — ' + state)
    w = window.original_widget
    if hasattr(w.scene_panel, 'revert_button'):
        window.close()
        raise SystemExit('Historical preapproval prototype: use source base 3a38b49 in an isolated checkout. '
                         'For current production evidence use python -m src.simulation.scene_review_validation.')
    w.load_csv_path(str(source))
    count = 0 if state == 'empty' else 1 if state in ('one', 'manual') else 24
    # Test-only UI topology; no detector output is copied into an expectation.
    candidates = [SceneCandidate(f'scene_{i+1:03d}', .1+i*.5, .35+i*.5,
                  'tip_or_rotation' if i % 2 else 'robot_handling',
                  'tip_or_rotation' if i % 2 else 'robot_handling') for i in range(count)]
    signals = pd.DataFrame({VERTICAL: 80*np.cos(.8*t), ROTATION: 15*np.abs(np.sin(t))}, index=t)
    result = DetectionResult(candidates, signals, origins/1000, rotations, None,
        DetectionSettings(), None, np.ones(len(t), dtype=bool), np.zeros(len(t), dtype=int))
    w.scene_session = SceneReviewSession(result, hashlib.sha256(source.read_bytes()).hexdigest())
    panel = w.scene_panel
    panel.session = w.scene_session
    for i, row in enumerate(w.scene_session.rows):
        row['decision'] = 'include' if i < 2 else 'exclude'
    if state in ('edited', 'blocked'):
        row = w.scene_session.rows[0]
        row.update(start=.14, end=.30, decision='unreviewed', evidence_status='range_changed')
        if state == 'blocked':
            for row in w.scene_session.rows[1:4]:
                row['decision'] = 'unreviewed'
    if state == 'manual':
        row = w.scene_session.rows[0]
        row.update(id='manual_001', origin='manual', auto_start=None, auto_end=None,
                   start=.14, end=.30, decision='unreviewed', evidence_status='range_changed')
    w._populate_scene_signals(result, VERTICAL)
    panel.refresh(w.scene_session.rows[0]['id'] if count else None)
    if state == 'details':
        panel.type_combo.setCurrentText('G')
        panel.edition_combo.setCurrentText('2018-03')
    w._update_scene_gates()

    # All proposed widgets/layout changes are local to this disposable instance.
    tools = panel.layout().itemAt(0).layout()
    revert = QPushButton('Revert detected range')
    revert.setToolTip('Restore detected bounds; review Include/Exclude again.')
    tools.insertWidget(5, revert)
    row = panel.selected_row()
    edited = bool(row and (row['start'], row['end']) != (row['auto_start'], row['auto_end']))
    revert.setEnabled(bool(edited and row['origin'] == 'automatic'))
    if not row:
        text = 'No scene selected'
    elif row['origin'] == 'manual':
        text = f"Manual: {row['start']:.2f}–{row['end']:.2f} s    No detected range"
        revert.setToolTip('Manual scenes have no detected range to restore.')
    elif edited:
        text = f"Edited: {row['start']:.2f}–{row['end']:.2f} s    Detected: {row['auto_start']:.2f}–{row['auto_end']:.2f} s"
    else:
        text = f"Detected: {row['start']:.2f}–{row['end']:.2f} s"
    range_label = QLabel(text)
    panel.layout().insertWidget(1, range_label)
    type_label = QLabel('Type basis: Operator selection (G)' if state == 'details' else 'Type basis: Unconfirmed')
    panel.details_section.content.layout().insertWidget(1, type_label)
    panel.type_combo.setToolTip('Choose Type from the test record; filename, mass and row order cannot confirm it.')

    # Bring existing batch action out of optional Details beside current saving.
    old_grid = panel.details_section.content.layout().itemAt(2).layout()
    old_grid.removeWidget(panel.save_all_button)
    save_layout = w.save_slice_button.parentWidget().layout()
    # Existing controls_widget -> horizontal layout -> final vertical save layout.
    save_layout = save_layout.itemAt(save_layout.count()-1).layout()
    save_layout.insertWidget(1, panel.save_all_button)
    included = sum(r['decision'] == 'include' for r in w.scene_session.rows)
    current = int(bool(row and row['decision'] == 'include'))
    pending = sum(r['decision'] == 'unreviewed' for r in w.scene_session.rows)
    w.save_slice_button.setText(f'Save current ({current})...')
    panel.save_all_button.setText(f'Save included ({included})...')
    reason = f'Review {pending} remaining' if pending else 'No scenes' if not count else ''
    w.save_status_label.setText(reason)
    w.save_status_label.setVisible(bool(reason))
    if state == 'loading':
        panel.detect_button.setText('Cancel detection')
        panel.detect_button.setEnabled(True)
        reason = 'Detection running'
    if state == 'error':
        reason = 'Save failed; retry available'
        w.slice_path_label.setText('Not saved yet.')
    if state == 'loading':
        for button in (w.save_slice_button, panel.save_all_button, w.save_process_button,
                       panel.add_button, panel.remove_button, panel.include_button,
                       panel.exclude_button, revert):
            button.setEnabled(False)
        panel.table.setEnabled(False)
    if state in ('loading', 'error'):
        w.save_status_label.setText(reason)
        w.save_status_label.show()
    details_scroll = QScrollArea()
    details_scroll.setWidgetResizable(True)
    details_scroll.setFrameShape(QScrollArea.NoFrame)
    details_scroll.setMaximumHeight(68 if size[0] < 1100 else 150)
    details_scroll.setMinimumHeight(0)
    panel.details_section.layout().removeWidget(panel.details_section.content)
    details_scroll.setWidget(panel.details_section.content)
    panel.details_section.content = details_scroll
    panel.details_section.layout().addWidget(details_scroll)
    # Keep long name concise; existing fullPath/tooltip/Copy path stay attached.
    w.file_path_label.setWordWrap(False)
    w.file_path_label.setText(w.file_path_label.fontMetrics().elidedText(source.name, Qt.ElideMiddle, 175))
    panel.details_section.setExpanded(state == 'details')
    if state == 'details' and size[0] < 1100:
        panel.table.setMinimumHeight(94)
    width, height = size
    window.resize(width, height)
    window.show()
    QApplication.processEvents()
    splitters = w.findChildren(QSplitter)
    main_splitter = next(s for s in splitters if s.orientation() == Qt.Vertical)
    scene_height = max(panel.minimumSizeHint().height(),
                       (300 if state == 'details' else 225) if width >= 1100 else 190)
    bottom_height = 130 if width >= 1100 else 120
    main_splitter.setSizes([max(126, main_splitter.height()-scene_height-bottom_height),
                            scene_height, bottom_height])
    QApplication.processEvents()
    w.file_path_label.setText(w.file_path_label.fontMetrics().elidedText(source.name, Qt.ElideMiddle,
                              max(40, w.file_path_label.width()-4)))
    # Show edited selection inside a declared zoom/pan viewport.
    w.plot_manager.ax.set_xlim(0, 3)
    w.plot_manager.ax.set_ylim(-100, 100)
    w.plot_manager.ax.set_ylabel('Speed\n(mm/s)' if state == 'details' and width < 1100
                                 else 'Vertical speed\n(mm/s)')
    w.fig.set_layout_engine('constrained')
    w.canvas.draw()
    QApplication.processEvents()
    return window, dict(rows=count, selected_id=panel.selected_id(), signal=VERTICAL,
        range_text=text, revert_enabled=revert.isEnabled(), current_targets=current,
        included_targets=included, pending=pending, reason=reason,
        xlim=list(w.plot_manager.ax.get_xlim()), ylim=list(w.plot_manager.ax.get_ylim()),
        logical_size=[window.width(), window.height()], requested_size=list(size),
        dpr=window.devicePixelRatioF(), details=state == 'details')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--state', choices=STATES)
    parser.add_argument('--size', default='820x600')
    parser.add_argument('--native', action='store_true', help='Keep disposable prototype open for external inspection')
    args = parser.parse_args()
    app = QApplication.instance() or QApplication([])
    screen = app.primaryScreen()
    target = (screen.availableGeometry().width(), screen.availableGeometry().height())
    out = Path(__file__).resolve().parent
    runtime = ROOT / 'tmp/issue137/mockup'
    runtime.mkdir(parents=True, exist_ok=True)
    source, t, origins, rotations = public_input(runtime)
    width, height = map(int, args.size.split('x'))
    states = [(args.state, (width, height))] if args.state else [(state, (820, 600)) for state in STATES]
    if not args.state:
        states += [('edited', (1510, 800)), ('edited', (1920, 1080)),
                   ('details', (1920, 1080)), ('details', target)]
    evidence = []
    for state, size in states:
        window, info = prototype(source, t, origins, rotations, state, size)
        if args.native:
            return app.exec()
        filename = f'{size[0]}x{size[1]}-{state}.png'
        assert info['logical_size'] == list(size), info
        window.grab().save(str(out / filename))
        info.update(state=state, screenshot=filename, evidence_kind='widget-render-mockup')
        evidence.append(info)
        window.close()
        window.deleteLater()
        app.processEvents()
    report = dict(schema_version=1, plan_spec=PLAN_SPEC, kind='scene-review-preapproval-mockup',
        approval_status='pending', code_head=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
        environment=dict(platform=platform.platform(), python=platform.python_version(),
            qt_platform=app.platformName(), pyside=PySide6.__version__, matplotlib=matplotlib.__version__,
            target_available=list(target), target_dpr=screen.devicePixelRatio()),
        input=dict(source_kind='public-handcrafted-synthetic', raw_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
            relative_runtime_path=str(source.relative_to(ROOT)).replace('\\', '/'), rows=len(t),
            units='mm', time_basis='capture_seconds', capture_interval_s=[float(t[0]), float(t[-1])],
            ui_fixture_basis='Independent SceneCandidate ranges at 0.10+0.5i to 0.35+0.5i seconds; no production detector labels.'),
        states=evidence, production_changed=False, native_status='not-executed',
        limitations=['Mockup count/reason text is illustrative; shared production gate is pending approval.',
                    'Widget renders are not native capture or external input acceptance.',
                    'No measured accuracy or #104 calibration claim.'])
    (out / 'mockup-evidence.json').write_text(json.dumps(report, indent=2, allow_nan=False)+'\n', encoding='utf-8')
    print(json.dumps(dict(states=len(evidence), sizes=[i['logical_size'] for i in evidence],
                          source_sha256=report['input']['raw_sha256']), allow_nan=False))


if __name__ == '__main__':
    main()
