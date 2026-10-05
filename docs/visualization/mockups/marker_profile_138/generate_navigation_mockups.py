"""Real gesture prototype and fresh Qt evidence, separate from production acceptance."""
from __future__ import annotations

import argparse
import copy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
import subprocess
import sys
from time import perf_counter

import numpy as np
import PySide6
from PySide6.QtCore import QPoint, QPointF, Qt
from PySide6.QtGui import QWheelEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QComboBox, QLabel

from generate_mockups import EXPECTED_HASHES, PLAN_SPEC
from generate_reviewed_mockups import ReviewedPrototype, capture_reviewed
from profile_preview_navigation import ProfilePreviewNavigation, box_at, intersects, leader, segment_boxes
from src.simulation.marker_fixtures import load_profile


class NavigationPrototype(ReviewedPrototype):
    def __init__(self, example='32', size=(1280, 960)):
        self.scene = None
        super().__init__(example, size)
        bar = self.plot_splitter.widget(0).layout().itemAt(0).layout()
        bar.itemAt(0).widget().setText('3D')
        bar.insertWidget(1, QLabel('View'))
        self.mode_combo = QComboBox(); self.mode_combo.addItems(['Box', 'Exploded faces'])
        self.mode_combo.setCurrentText('Exploded faces'); bar.insertWidget(2, self.mode_combo)
        display = QLabel('Display only'); display.setToolTip('View gestures keep table, selected mm values and saved profile unchanged.')
        bar.insertWidget(3, display); bar.insertWidget(4, QLabel('Names'))
        self.names3 = QComboBox(); self.names3.addItems(['All', 'View face', 'Selected']); bar.insertWidget(5, self.names3)
        self.mode_combo.currentTextChanged.connect(self.scene.set_mode)
        self.names3.currentTextChanged.connect(self.scene.set_names)
        self.setWindowTitle('Marker profile #138 — INTERACTIVE MOCKUP — production pending')

    def draw(self):
        super().draw()
        if self.scene is not None and self.plot_scroll is not None and not self.face_title.text().startswith('2D '):
            self.face_title.setText('2D '+self.face_title.text())

    def render3(self, camera):
        if self.scene is None:
            top_layout = self.plot_splitter.widget(0).layout()
            old = self.canvas3
            # Replace this view's event owner; leave the existing2D toolbar untouched.
            for event in ('button_press_event', 'button_release_event', 'motion_notify_event', 'scroll_event'):
                for cid in list(old.callbacks.callbacks.get(event, {})):
                    old.mpl_disconnect(cid)
            top_layout.removeWidget(old); old.hide(); old.setParent(None); old.deleteLater()
            self.scene = ProfilePreviewNavigation(self.valid_preview, self)
            top_layout.addWidget(self.scene, 1); self.canvas3 = self.scene
            self.axes = self.scene.axes; self.figure3 = self.scene.figure
            initial = self.figure
            initial.clear(); initial.canvas.deleteLater(); self.figure = self.scene.figure
            self.scene.markerSelected.connect(self.table.selectRow)
        self.scene.set_profile(self.valid_preview)
        self.scene.set_selected(self.selected_row, self.current_face)

    def fit3(self):
        if self.scene is not None:
            self.scene.fit()

    def restore_view(self):
        if self.scene is not None:
            self.scene.reset_view()


def settle(app, scene, timeout=2.):
    end = perf_counter()+timeout
    while scene.idle_timer.isActive() or scene.layout_timer.isActive() or scene.solver is not None:
        app.processEvents()
        if perf_counter() > end:
            raise AssertionError('Bounded layout did not settle')
    app.processEvents()


def show_window(app, example, size):
    window = NavigationPrototype(example, size)
    window.show(); app.processEvents(); window.resize(*size); app.processEvents()
    window.plot_splitter.setSizes([550, 450]); app.processEvents()
    window.scene.fit(); settle(app, window.scene)
    return window


def display_diagnostics(scene):
    matrix = scene.axes.transData.get_affine().get_matrix()
    scale_delta = float(abs(abs(matrix[0, 0])-abs(matrix[1, 1])))
    assert scale_delta < 1e-9, 'Unequal3D projection scale'
    boxes = list(scene.badge_boxes.values())
    badges = sum(int(np.count_nonzero(intersects(b, np.asarray(boxes[i+1:]).reshape(-1, 4)))) for i, b in enumerate(boxes))
    points = np.array([box_at(p, np.array([13.35, 13.35])) for p in scene.point_pixels])
    hides = sum(int(np.count_nonzero(intersects(b, points))) for b in boxes)
    distances = np.linalg.norm(scene.point_pixels[:, None]-scene.point_pixels[None, :], axis=2)
    pairs = np.argwhere(np.triu(distances < 13.35, 1)).tolist()
    titles = [box_at(p, size) for p, size, _ in scene.title_boxes.values()]
    title_hides = sum(int(np.count_nonzero(intersects(b, points))) for b in titles)
    title_badges = sum(int(np.count_nonzero(intersects(b, np.asarray(boxes).reshape(-1, 4)))) for b in titles)
    return dict(names=len(scene.layout), requested_names=scene.names, limited=scene.limited,
                badge_collisions=badges, badge_marker_occlusions=hides, marker_disk_overlap_pairs=pairs,
                equal_projection_scale_delta=scale_delta,
                title_marker_occlusions=title_hides, title_badge_collisions=title_badges,
                cache_entries=len(scene.cache), stats=copy.deepcopy(scene.stats))


def timing_summary(values):
    values = list(values)
    return dict(samples=len(values), median_ms=float(np.median(values)) if values else None,
                p95_ms=float(np.percentile(values, 95)) if values else None,
                max_ms=max(values) if values else None,
                kind='Qt-widget-event-to-paint-CPU-wall-clock', native=False)


def navigation_checks(app, window):
    scene = window.scene; source = scene.source_xyz.copy()
    snapshots = copy.deepcopy((window.draft, window.valid_preview, window.applied))
    view = scene.snapshot_view(); selected = window.table.currentRow()
    identity = (id(scene), id(scene._display_points), id(scene._world_scene))
    scene.paint_ms.clear(); scene.input_to_paint_ms.clear()
    starts = scene.stats['solve_starts']
    canvas2 = window.face_axes
    start = np.array([20., 20.]); drag(app, scene, start, start+[100, 35], moves=32, release=False)
    assert scene.stats['solve_starts'] == starts and window.face_axes is canvas2
    assert window.table.currentRow() == selected and scene.gesture is not None
    assert identity == (id(scene), id(scene._display_points), id(scene._world_scene))
    moving = dict(paint=timing_summary(scene.paint_ms), input_to_paint=timing_summary(scene.input_to_paint_ms),
                  layout_solver_starts_during_motion=scene.stats['solve_starts']-starts,
                  same_2d_axes=True, retained_widget_and_buffers=True)
    QTest.mouseRelease(scene, Qt.LeftButton, pos=QPoint(120, 55)); app.processEvents(); settle(app, scene)
    assert np.array_equal(scene.source_xyz, source) and (window.draft, window.valid_preview, window.applied) == snapshots
    scene.load_view_state(view); settle(app, scene)
    # Selection-independent All layout; Selected includes selection in its cache key.
    positions = {r:p.copy() for r, p in scene.layout.items()}
    for row in range(len(scene.ids)):
        scene.set_selected(row); app.processEvents(); settle(app, scene)
        assert set(scene.layout) == set(positions)
        assert all(np.array_equal(scene.layout[r], p) for r, p in positions.items())
    scene.set_names('Selected'); scene.set_selected(0); settle(app, scene); assert set(scene.layout) == {0}
    scene.set_selected(len(scene.ids)-1); settle(app, scene); assert set(scene.layout) == {len(scene.ids)-1}
    # Force more settled states than the LRU capacity; no diagnostic list can grow forever.
    scene.cache.clear()
    for angle in range(12):
        state = scene.snapshot_view(); state['camera'][1] = 50+angle*.4
        scene.load_view_state(state); settle(app, scene)
    assert len(scene.cache) == scene.MAX_CACHE
    assert scene.paint_ms.maxlen == scene.input_to_paint_ms.maxlen == 256
    # New mode cancels the current drag and restores the captured view before switching.
    scene.set_names('All'); scene.load_view_state(view); settle(app, scene)
    drag(app, scene, start, start+[70, 20], release=False)
    window.mode_combo.setCurrentText('Box'); app.processEvents(); settle(app, scene)
    assert scene.gesture is None and scene.mode == 'Box'
    window.mode_combo.setCurrentText('Exploded faces'); app.processEvents(); settle(app, scene)
    assert scene.view == view
    QTest.mouseRelease(scene, Qt.LeftButton, pos=QPoint(90, 40))
    # Face-on normal has no projected drag axis; no large ratio or camera change.
    face_on = scene.snapshot_view(); face_on['camera'] = [0., 0., 0.]
    scene.load_view_state(face_on); settle(app, scene); app.processEvents()
    if 'FRONT' in scene.title_boxes:
        center = scene.title_boxes['FRONT'][0]; drag(app, scene, center, center+[40, 20])
        assert scene.view == face_on
    scene.load_view_state(view); settle(app, scene)
    scene.set_selected(selected, window.current_face); app.processEvents()
    return dict(status='pass', kind='Qt-widget-navigation-and-bounds', source_difference=0,
                motion=moving, cache_capacity=scene.MAX_CACHE, eviction_exercised=True,
                diagnostic_sample_capacity=256, selected_cache_key_exercised=True,
                selection_layouts=len(scene.ids), native=False,
                normal_axis_degeneracy='front at0/0/0 unchanged view', view_only=True)


def profile_revision_checks(app, window):
    scene = window.scene; applied = copy.deepcopy(window.applied); view = scene.snapshot_view()
    old_hash = scene.profile_hash; old_token = scene.solve_token
    # Data-only placement pending before a real editor Preview replaces its source.
    scene.cache.clear(); scene._settle(); assert scene.solver is not None
    window.table.item(0, 2).setText('22'); QTest.mouseClick(window.preview_button, Qt.LeftButton)
    app.processEvents(); settle(app, scene)
    assert scene.profile_hash != old_hash and scene.solve_token > old_token
    assert scene.source_xyz[0, 0] == 22 and window.applied == applied
    for field in ('camera', 'pan', 'zoom', 'offsets'):
        assert scene.view[field] == view[field]
    window.table.item(0, 0).setText('F9'); QTest.mouseClick(window.preview_button, Qt.LeftButton)
    app.processEvents(); settle(app, scene)
    assert scene.ids[0] == 'F9' and 'F1' not in scene.ids and window.applied == applied
    row = next(i for i, m in enumerate(window.valid_preview['markers']) if m['id'] == 'B2')
    valid = scene.source_xyz.copy(); window.table.item(row, 3).setText('bad')
    assert not window.preview_button.isEnabled() and not window.apply_button.isEnabled() and not window.save_button.isEnabled()
    assert np.array_equal(scene.source_xyz, valid)
    window.table.item(row, 3).setText('-26'); assert window.preview_button.isEnabled()
    QTest.mouseClick(window.reset_button, Qt.LeftButton); app.processEvents(); settle(app, scene)
    assert scene.ids[0] == 'F1' and scene.source_xyz[0, 0] == 21 and window.applied == applied
    assert np.array_equal(scene.source_xyz, [m['xyz_mm'] for m in load_profile(example='18')['markers']])
    return dict(status='pass', kind='Qt-editor-preview-source-revision',
                expected='F1X21->22 Preview; F1->F9 Preview; previous placement cancelled; view retained; invalidB2Y blocks Preview/Save/Apply; Reset restores canonical18; applied exact unchanged',
                stale_results_applied=scene.stats['stale_results'], native=False)


def edge_checks(app, window):
    scene = window.scene; view = scene.snapshot_view(); selected = window.table.currentRow()
    source = scene.source_xyz.copy(); snapshots = copy.deepcopy((window.draft, window.valid_preview, window.applied))
    # A non-left click must preserve the canonical selected row and view.
    point = QPoint(*np.rint(scene.point_pixels[0]).astype(int))
    QTest.mouseClick(scene, Qt.MiddleButton, pos=point); app.processEvents(); settle(app, scene)
    assert window.table.currentRow() == selected and scene.view == view
    # Unrelated release/press cannot terminate or replace the captured left gesture.
    drag(app, scene, np.array([20., 20.]), np.array([50., 35.]), moves=3, release=False)
    captured = scene.gesture; moved = scene.snapshot_view()
    QTest.mouseRelease(scene, Qt.RightButton, pos=QPoint(50, 35)); app.processEvents()
    assert scene.gesture is captured and scene.view == moved
    QTest.mousePress(scene, Qt.MiddleButton, pos=QPoint(50, 35)); app.processEvents()
    assert scene.gesture is captured
    QTest.mouseRelease(scene, Qt.MiddleButton, pos=QPoint(50, 35)); app.processEvents()
    assert scene.gesture is captured
    QTest.mouseRelease(scene, Qt.LeftButton, pos=QPoint(50, 35)); app.processEvents(); settle(app, scene)
    assert scene.gesture is None and window.table.currentRow() == selected
    # Adversarial zooms can limit All names. Every actually painted fallback badge
    # must avoid other badges and their leaders; absence retains the table/readout.
    limited = 0; fallback = 0
    for zoom in (.3, .5):
        state = copy.deepcopy(view); state['zoom'] = zoom
        scene.load_view_state(state); settle(app, scene)
        limited += int(scene.limited)
        for row in range(len(scene.ids)):
            scene.set_selected(row); scene.grab(); app.processEvents()
            boxes = scene.badge_boxes
            if row not in scene.layout and row in boxes:
                fallback += 1
                center = (boxes[row][:2]+boxes[row][2:])/2
                assert row in scene._hit(QPointF(*center))[1]
            for r, box in boxes.items():
                other = np.asarray([b for j, b in boxes.items() if j != r]).reshape(-1, 4)
                assert not np.any(intersects(box, other))
                for j, center in scene.layout.items():
                    if j != r:
                        a, b = leader(scene.point_pixels[j], center, scene.id_sizes[j])
                        assert not segment_boxes(a, b, np.asarray([box]))
    assert limited == 2 and fallback > 0
    scene.load_view_state(view); scene.set_selected(selected, window.current_face); settle(app, scene)
    assert np.array_equal(scene.source_xyz, source) and (window.draft, window.valid_preview, window.applied) == snapshots
    return dict(status='pass', kind='Qt-QTest-gesture-and-fallback-boundaries', native=False,
                expected='Middle click keeps selected row; unrelated release/press keeps captured left gesture; zoom.3/.5 all32 actual badges avoid each other and other leaders',
                limited_views=limited, fallback_badges=fallback, selected_layouts=64, source_difference=0)


def drag(app, scene, start, finish, button=Qt.LeftButton, moves=16, release=True):
    QTest.mousePress(scene, button, pos=QPoint(*np.rint(start).astype(int))); app.processEvents()
    for p in np.linspace(start, finish, moves+1)[1:]:
        QTest.mouseMove(scene, QPoint(*np.rint(p).astype(int))); app.processEvents()
    if release:
        QTest.mouseRelease(scene, button, pos=QPoint(*np.rint(finish).astype(int))); app.processEvents()
        settle(app, scene)


def gesture_checks(app, window):
    scene = window.scene
    canonical = np.asarray([m['xyz_mm'] for m in load_profile(example='18')['markers']])
    assert np.array_equal(scene.source_xyz, canonical)
    snapshots = copy.deepcopy((window.draft, window.valid_preview, window.applied))
    model = scene.snapshot_view(); camera = list(model['camera'])
    # Independent expectation: original18 M2 source[38,-60,-18], displayed Y=-200.
    assert np.array_equal(scene.display_geometry()[0][17], [38, -200, -18])
    name, (center, size, _) = next((f, t) for f, t in scene.title_boxes.items() if f == 'FRONT')
    direction = scene.project([np.zeros(3), np.asarray([0, 0, 200])])[0]
    axis = direction[1]-direction[0]; finish = center+axis*.2
    before = scene.view['offsets']['FRONT']
    drag(app, scene, center, finish)
    assert abs(scene.view['offsets']['FRONT']-before-.2) < .015  # integer-pointer rounding, dimensionless display ratio
    assert scene.view['camera'] == camera
    assert all(scene.view['offsets'][f] == model['offsets'][f] for f in scene.view['offsets'] if f != 'FRONT')
    assert (window.draft, window.valid_preview, window.applied) == snapshots
    # Escape cancels just the in-progress view gesture.
    scene.reset_view(); settle(app, scene); original = scene.snapshot_view()
    start = np.array([25., 25.]); drag(app, scene, start, start+[60, 25], release=False)
    assert scene.view != original
    QTest.keyClick(scene, Qt.Key_Escape); app.processEvents(); settle(app, scene)
    assert scene.view == original and scene.gesture is None
    QTest.mouseRelease(scene, Qt.LeftButton, pos=QPoint(85, 50))
    # Marker drag rotates; it must not select on press or when released after drag.
    scene.reset_view(); settle(app, scene); row = window.table.currentRow()
    start = scene.point_pixels[0].copy(); drag(app, scene, start, start+[30, 15])
    assert window.table.currentRow() == row and scene.view['camera'] != camera
    # Middle pan and wheel zoom preserve canonical objects and offsets.
    scene.reset_view(); settle(app, scene); original = scene.snapshot_view()
    drag(app, scene, np.array([20., 20.]), np.array([60., 45.]), Qt.MiddleButton)
    assert np.allclose(np.asarray(scene.view['pan'])-original['pan'], [40, 25])
    zoom = scene.view['zoom']
    event = QWheelEvent(QPointF(100, 100), scene.mapToGlobal(QPoint(100, 100)), QPoint(), QPoint(0, 120),
                        Qt.NoButton, Qt.NoModifier, Qt.NoScrollPhase, False)
    QApplication.sendEvent(scene, event); QTest.qWait(90); settle(app, scene)
    assert scene.view['zoom'] > zoom
    assert np.array_equal(scene.source_xyz, canonical) and (window.draft, window.valid_preview, window.applied) == snapshots
    # Direct click resolves canonical row; no pan/rotate occurs.
    scene.reset_view(); settle(app, scene); source = scene.source_xyz.copy(); view = scene.snapshot_view()
    QTest.mouseClick(scene, Qt.LeftButton, pos=QPoint(*np.rint(scene.point_pixels[17]).astype(int)))
    app.processEvents(); settle(app, scene)
    assert window.table.currentRow() == 17 and '(38, -60, -18) mm' in window.selected_readout.text()
    assert scene.view == view and np.array_equal(scene.source_xyz, source)
    # Stale data-only work is cancelled on source replacement and invalid view contracts reject.
    for change in ({'schema_version': 9}, {'schema_version': True}, {'source_profile_hash': 'stale'},
                   {'source_profile_hash': None}, {'zoom': float('nan')}, {'zoom': float('inf')},
                   {'zoom': True}, {'offset_units': 'cm'}, {'time_semantics': 'recorded-seconds'},
                   {'display_rule_version': 9}, {'display_rule_version': True}, {'display_rule_hash': 'stale'}):
        bad = scene.snapshot_view(); bad.update(change)
        try:
            scene.load_view_state(bad)
        except ValueError:
            pass
        else:
            raise AssertionError('Invalid view contract accepted')
    return dict(status='pass',kind='Qt-QTest-widget-gestures',
                expected='M2canonical[38,-60,-18]/display[38,-200,-18]; front-only+.2display ratio; no camera change; deferred canonical click; Escape restores start; pan[40,25]; wheel increases zoom; source/draft/applied unchanged',
                pointer_rounding_tolerance=dict(value=.015,units='dimensionless-display-ratio',reason='QTest integer-pixel rounding; no physical accuracy tolerance'),
                native=False,metrics=display_diagnostics(scene))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--smoke', action='store_true')
    parser.add_argument('--caption-only', action='store_true')
    parser.add_argument('--live', action='store_true')
    args = parser.parse_args(); args.output.mkdir(parents=True, exist_ok=True)
    app = QApplication.instance() or QApplication([])
    if args.live:
        window = show_window(app, '32', (1280, 960)); sys.exit(app.exec())
    source = Path(__file__)
    report = dict(schema_version=1, plan_spec=PLAN_SPEC, object_type='InteractiveProfileMockupEvidence',
                  utc=datetime.now(timezone.utc).isoformat(), command=sys.argv,
                  commit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
                  dirty=bool(subprocess.check_output(['git', 'status', '--porcelain'], text=True).strip()),
                  source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
                  viewport_sha256=hashlib.sha256(source.with_name('profile_preview_navigation.py').read_bytes()).hexdigest(),
                  dependency_sha256={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in
                                     (source.with_name('generate_reviewed_mockups.py'), source.with_name('generate_mockups.py'),
                                      source.with_name('generate_preview_options.py'))},
                  environment=dict(os=platform.platform(), python=platform.python_version(), pyside=PySide6.__version__,
                                   qt_platform=app.platformName(), os_scale_percent=100, qt_process_dpr=app.primaryScreen().devicePixelRatio()),
                  input=dict(kind='public-synthetic-static-geometry', profile_hashes=EXPECTED_HASHES,
                             seed=None, seed_reason='Static public geometry; deterministic gestures', units='mm', time_semantics='static-no-recorded-time'),
                  native_status='not-executed-existing-capture-activation-error', production_changed=False,
                  tolerances=[dict(value=1e-9, units='logical-pixels-per-projected-unit',
                                   reason='Float64 arithmetic comparison of equal affine scales; no physical accuracy tolerance'),
                              dict(value=.015, units='dimensionless-view-offset-ratio',
                                   reason='Integer-pixel QTest pointer rounding; original source equality remains exact')],
                  limitations=['Qt render/QTest only; actual OS125% and external native input/capture unexecuted.',
                               'Public synthetic geometry only; no validated real experimental data or accuracy approval.',
                               'Production semantic compatibility, persistence/export/worker/CI remain unimplemented.',
                               'During gestures ordinary ID names temporarily omitted, requested Names mode retained.',
                               'Placement work cooperatively slices at8ms with one bounded vector step overrun;100ms total target with same caveat.',
                               'Performance samples are bounded Qt event-to-paint/CPU records, not native latency or achievedFPS.'],
                  user_approval='pending-new-interaction', independent_review='pending', states=[])
    report['scope'] = 'narrow-2D-caption-regression-only' if args.caption_only else 'full-interactive-mockup'
    for example in ('32',) if args.smoke else ('32', '18'):
        for size in ((820, 600),) if args.caption_only else ((1920, 1080),) if args.smoke else ((1280, 960), (1920, 1080), (820, 600)):
            window = show_window(app, example, size); scene = window.scene
            if args.caption_only:
                expected = '2D Back / Z=-45 mm (12)' if example == '32' else '2D Back / Z=-40 mm (3)'
                assert window.face_title.text() == expected
            state = capture_reviewed(window, args.output, f'navigation-{example}-{size[0]}x{size[1]}.png', size)
            state.update(diagnostics=display_diagnostics(scene), source_hash=scene.profile_hash,
                         source_geometry_unchanged=bool(np.array_equal(scene.source_xyz, [m['xyz_mm'] for m in load_profile(example=example)['markers']])),
                         fresh=True, production=False)
            report['states'].append(state)
            print(json.dumps(dict(captured=state['screenshot'], diagnostics=state['diagnostics'])), flush=True)
            if not args.smoke:
                if not args.caption_only:
                    state['navigation'] = navigation_checks(app, window)
                else:
                    state['caption'] = dict(status='pass', expected=expected, actual=window.face_title.text(), units='mm')
                if size == (1280, 960) and example == '32':
                    report['edges'] = edge_checks(app, window)
                if size == (820, 600):
                    bar = window.plot_scroll.verticalScrollBar(); bar.setValue(bar.maximum()); app.processEvents()
                    bottom = capture_reviewed(window, args.output, f'navigation-{example}-820x600-bottom.png', size)
                    bottom.update(state='small-bottom', fresh=True, source_hash=scene.profile_hash)
                    report['states'].append(bottom)
                    bar.setValue(0); app.processEvents()
                    bad_row = next(i for i, m in enumerate(window.valid_preview['markers']) if m['id'] == 'B2')
                    before = copy.deepcopy(window.applied); window.table.item(bad_row, 3).setText('bad')
                    assert not window.preview_button.isEnabled() and not window.save_button.isEnabled() and not window.apply_button.isEnabled()
                    invalid = capture_reviewed(window, args.output, f'navigation-{example}-820x600-invalid.png', size)
                    invalid.update(state='small-invalid-B2Y', fresh=True, applied_unchanged=window.applied == before)
                    report['states'].append(invalid)
            if not args.smoke and size == (1280, 960) and example == '18':
                report['gestures'] = gesture_checks(app, window)
                report['profile_changes'] = profile_revision_checks(app, window)
            window.close(); app.processEvents()
            (args.output/'evidence.json').write_text(json.dumps(report, indent=2, allow_nan=False)+'\n', encoding='utf-8')
    (args.output/'evidence.json').write_text(json.dumps(report, indent=2, allow_nan=False)+'\n', encoding='utf-8')
    print(json.dumps(dict(states=len(report['states']), gestures=report.get('gestures', {}).get('status', 'not-run-scoped-caption' if args.caption_only else 'not-run-smoke'))), flush=True)


if __name__ == '__main__':
    main()
