"""Replay retained public results through the production Qt release workflow.

Run in a fresh process with QT_SCALE_FACTOR=1.25. No pose optimization is run.
"""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time
import traceback

import numpy as np
from PySide6.QtCore import Qt, QTimer
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QFileDialog, QLineEdit, QMessageBox, QToolTip, QTreeWidgetItemIterator

from src.analysis.app.main_window import MainApp
from src.analysis.compare.main_window import CompareMainWindow
from src.config.data_columns import normalize_result_column
from src.config import config_visualization as visual


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run(trial_report, output):
    output.mkdir(parents=True, exist_ok=False)
    producer = json.loads(trial_report.read_text(encoding='utf-8'))
    assert producer['status'] == 'pass'
    source_dir = trial_report.parent
    # Relative siblings make downloaded CI evidence portable across machines.
    observed = source_dir / 'analytic'
    protected = [observed / name for name in producer['source_sha256_after']]
    protected += [source_dir / name for name in ('recorded.scene-review.json', 'recorded.slice', 'recorded.proc')]
    before = {str(path): sha(path) for path in protected}
    for name, digest in producer['source_sha256_after'].items():
        assert sha(observed / name) == digest
    inputs = output / 'inputs'
    inputs.mkdir()
    csv = inputs / ('capture_' * 11 + '.csv')
    shutil.copyfile(observed / 'observed.csv', csv)
    workspace = json.loads((source_dir / 'recorded.scene-review.json').read_text(encoding='utf-8'))
    workspace['source']['path'] = csv.name
    review_path = inputs / 'retained.scene-review.json'
    review_path.write_text(json.dumps(workspace), encoding='utf-8')
    slice_path = inputs / ('selected_trial_' * 6 + '.slice')
    shutil.copyfile(source_dir / 'recorded.slice', slice_path)
    results = inputs / 'results'
    results.mkdir()
    paths = []
    for index in range(9):
        path = results / (f'{index:02d}_' + 'same_observation_' * 5 + '.proc')
        shutil.copyfile(source_dir / 'recorded.proc', path)
        paths.append(path)
    malformed = inputs / 'invalid.proc'
    malformed.write_text('not a processed result', encoding='utf-8')
    copied_before = {str(path.relative_to(inputs)): sha(path) for path in inputs.rglob('*') if path.is_file()}
    report = {'version': 1, 'status': 'running', 'evidence_level': 'synthetic_integration',
              'source_kind': 'handcrafted_dummy', 'producer_report_sha256': sha(trial_report),
              'commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
              'processing_reused': True, 'new_raw_executions': 0, 'checks': {}, 'screenshots': [],
              'findings': [], 'dialogs': [], 'protected_sha256_before': before,
              'scope': 'Actual Qt input and saved-result replay; no real calibration or native external mouse claim.'}
    report['copied_input_sha256_before'] = copied_before
    implementation = [Path(name) for name in (
        'src/simulation/release_gui_validation.py', 'src/analysis/ui/plot_manager.py',
        'src/analysis/ui/widget_raw_data_processing.py', 'src/analysis/ui/widget_slice_processing.py',
        'src/analysis/app/main_window.py', 'src/launcher.py',
        'src/analysis/compare/main_window.py', 'src/analysis/compare/playback_panel.py',
        'src/analysis/compare/ui_panels.py')]
    report['implementation_sha256'] = {str(path): sha(path) for path in implementation}
    app = QApplication.instance() or QApplication([])
    app.setAttribute(Qt.ApplicationAttribute.AA_DontUseNativeDialogs, True)
    windows, errors, expected_dialogs = [], [], []
    current = None
    previous_exception_hook = sys.excepthook
    sys.excepthook = lambda kind, value, tb: errors.append(''.join(traceback.format_exception(kind, value, tb)))

    def flush():
        (output / 'execution.json').write_text(json.dumps(report, indent=2, allow_nan=False), encoding='utf-8')

    def events(ms=60):
        QTest.qWait(ms)
        app.processEvents()

    def stage(name):
        report['stage'] = name
        flush()

    def wait_until(predicate, timeout=30):
        deadline = time.monotonic() + timeout
        while not predicate() and time.monotonic() < deadline:
            events(15)
        assert predicate(), f'Timed out: {report["stage"]}'
        assert not errors, errors

    def show(window):
        nonlocal current
        current = window
        windows.append(window)
        window.show()
        assert QTest.qWaitForWindowExposed(window, 5000)
        events(100)
        # Apply the requested viewport after native show/geometry events.
        window.resize(1510, 800)
        window.move(5, 5)
        events(200)
        assert window.width() == 1510
        return window

    def capture(name, description, buttons=()):
        events()
        pixmap = current.grab()
        assert pixmap.save(str(output / (name + '.png')))
        dpr, frame = current.devicePixelRatioF(), current.frameGeometry()
        screen = current.screen()
        details = {'file': name + '.png', 'description': description, 'dpr': dpr,
                   'logical_window': [current.width(), current.height()],
                   'frame_physical': [frame.width() * dpr, frame.height() * dpr],
                   'monitor_logical': [screen.size().width(), screen.size().height()],
                   'available_logical': [screen.availableGeometry().width(), screen.availableGeometry().height()],
                   'monitor_resolution_changed_by_validator': False, 'buttons': {}}
        if isinstance(current, CompareMainWindow):
            graph = current.graph_panel
            details['vertical_panel_heights'] = current.right_splitter.sizes()
            details['plot_physical_size'] = list(graph.plot_manager.ax.get_window_extent().size)
            details['vtk_logical_sizes'] = {name: [viewer.width(), viewer.height()]
                                           for name, viewer in current.playback_panel.widgets.items()}
        assert dpr == 1.25, f'Expected fresh Qt process at 125%, got {dpr}'
        if frame.width() * dpr > 1920 or frame.height() * dpr > 1080:
            report['findings'].append(f'{name}: window does not fit the 1920x1080 physical viewport')
        for button in buttons:
            accessible = button.isVisible() and button.visibleRegion().contains(button.rect())
            details['buttons'][button.text()] = {'visible': accessible, 'enabled': button.isEnabled()}
            if not accessible:
                report['findings'].append(f'{name}: clipped action {button.text()}')
        report['screenshots'].append(details)
        flush()

    def choose(path=None, multiple=False):
        handled = []
        def pick():
            dialog = app.activeModalWidget()
            if not isinstance(dialog, QFileDialog):
                errors.append('Expected actual QFileDialog')
                return
            if path is None:
                QTest.keyClick(dialog, Qt.Key_Escape)
                handled.append('cancelled')
            else:
                text = ' '.join('"' + str(p.resolve()) + '"' for p in path) if multiple else str(path.resolve())
                line = dialog.findChild(QLineEdit, 'fileNameEdit')
                line.setText(text)
                QTimer.singleShot(100, dialog.accept)
        QTimer.singleShot(100, pick)
        return handled

    def click(button):
        assert button.isEnabled(), button.text()
        QTest.mouseClick(button, Qt.LeftButton)
        events()
        assert not errors, errors

    def watch():
        dialog = app.activeModalWidget()
        if isinstance(dialog, QMessageBox):
            report['dialogs'].append(dialog.text())
            if not expected_dialogs:
                errors.append(dialog.text())
            else:
                expected_dialogs.pop()
            dialog.grab().save(str(output / 'expected_load_error.png'))
            dialog.accept()

    watcher = QTimer()
    watcher.timeout.connect(watch)
    watcher.start(50)
    flush()
    try:
        stage('MainApp empty and saved review')
        main = show(MainApp())
        raw = main.original_widget
        capture('01_empty', 'Actual empty Step 1 at 125%; initial controls.', [raw.load_csv_button, raw.scene_panel.open_review_button])
        choose(review_path)
        click(raw.scene_panel.open_review_button)
        wait_until(lambda: raw.scene_session is not None and not raw.scene_busy)
        session, panel = raw.scene_session, raw.scene_panel
        selected = next(row for row in session.rows if row['identity']['confirmed'])
        assert selected['identity']['scenario_id'] == 'G16'
        assert selected['observed_consistency']['approach'] == 'different'
        panel.refresh(selected['id'])
        curve = raw.plot_manager.ax.lines[0]
        np.testing.assert_equal(curve.get_ydata(), session.result.signals['Relative rotation (deg)'])
        assert raw.plot_manager.ax.get_ylim() == (0., 1.)
        raw.plot_manager.ax.set_ylim(0., 1e-13)
        panel.refresh(selected['id'])
        assert raw.plot_manager.ax.get_ylim() == (0., 1e-13)
        raw.plot_manager.ax.set_ylim(0., 1.)
        report['checks']['rotation_display_preserves_samples_and_zoom_limits'] = True
        capture('02_recorded', 'Reopened retained public capture with long filename; G16 and Different approach remain separate.',
                [panel.trial_record_button, panel.confirm_button, panel.save_review_button, panel.save_all_button])
        snapshot = deepcopy(session.rows)
        panel.trial_record_button.setFocus()
        QTest.keyClick(panel.trial_record_button, Qt.Key_Tab)
        forward = app.focusWidget()
        assert forward is not None and forward is not panel.trial_record_button
        QTest.keyClick(forward, Qt.Key_Backtab)
        assert app.focusWidget() is panel.trial_record_button
        pressed = []
        panel.include_button.clicked.connect(lambda: pressed.append(True))
        panel.include_button.setFocus()
        QTest.keyClick(panel.include_button, Qt.Key_Space)
        assert pressed == [True]
        cancelled = choose(None)
        def select_load():
            menu = panel.trial_record_button.menu()
            QTest.mouseClick(menu, Qt.LeftButton, pos=menu.actionGeometry(panel.load_trial_record_action).center())
        QTimer.singleShot(50, select_load)
        QTest.mouseClick(panel.trial_record_button, Qt.LeftButton)
        wait_until(lambda: cancelled == ['cancelled'])
        assert session.rows == snapshot
        report['checks']['tab_backtab_space_escape_preserve_review'] = True
        stage('Many reviewed ranges')
        for _ in range(24):
            click(panel.add_button)
        assert len(session.rows) == len(snapshot) + 24
        table = panel.table
        table.setFocus()
        QTest.keyClick(table, Qt.Key_End, Qt.ControlModifier)
        assert table.currentRow() == table.rowCount() - 1
        assert table.verticalScrollBar().maximum() > 0
        capture('03_many_ranges', '24 additional manual ranges are a UI stress condition, not new physical trials; last row reached by keyboard.',
                [panel.include_button, panel.exclude_button, panel.save_review_button])
        QTest.keyClick(table, Qt.Key_Home, Qt.ControlModifier)
        assert table.currentRow() == 0
        report['checks']['many_ranges_keyboard_and_scroll'] = True
        assert not panel.save_all_button.isEnabled()
        stage('Step 1.5 retained slice')
        main.tab_widget.setCurrentIndex(1)
        processing = main.processing_widget
        choose(slice_path)
        click(processing.load_slice_button)
        assert processing.parsed_data is not None
        capture('04_slice', 'Existing padded slice reopened; original selected range and correction summary are shown. No Raw rerun.',
                [processing.load_slice_button, processing.run_button, processing.save_proc_button])
        stage('Step 2 saved result')
        main.tab_widget.setCurrentIndex(2)
        result = main.result_widget
        choose(results)
        click(result.select_result_folder_button)
        item = result.result_file_list.findItems(paths[0].name, Qt.MatchExactly)[0]
        QTest.mouseClick(result.result_file_list.viewport(), Qt.LeftButton, pos=result.result_file_list.visualItemRect(item).center())
        events()
        assert len(result.result_data) == 27
        # Opening a result now plots its default quantity. Select only centre Y
        # for this saved-position check, using the same visible user action.
        click(result.clear_selection_button)
        tree = result.result_data_tree
        iterator = QTreeWidgetItemIterator(tree)
        leaf = None
        while iterator.value():
            candidate = iterator.value()
            data = candidate.data(0, Qt.UserRole)
            if data is not None and normalize_result_column(data) == ('Position', 'CoM', 'P_TY'):
                leaf = candidate
                break
            iterator += 1
        assert leaf is not None
        tree.setCurrentItem(leaf)
        tree.scrollToItem(leaf)
        tree.setFocus()
        QTest.keyClick(tree, Qt.Key_Space)
        assert leaf.checkState(0) == Qt.Checked
        click(result.plot_results_button)
        line = result.plot_manager.ax.lines[0]
        np.testing.assert_allclose(line.get_xdata(), result.result_data.index.to_numpy(float), atol=1e-10, rtol=0)
        np.testing.assert_allclose(line.get_ydata(), result.result_data[('Position', 'CoM', 'P_TY')], atol=0, rtol=0)
        capture('05_results', 'Step 2 selected geometric-centre Y through the real result tree; plotted all 27 saved timestamps and positions.',
                [result.select_result_folder_button, result.plot_results_button, result.metric_guide_button])
        report['checks']['step2_saved_times_and_positions'] = True
        main.close()
        stage('Comparison loading and duplicated observations')
        comparison = show(CompareMainWindow())
        control = comparison.control_panel
        capture('06_comparison_empty', 'Existing Comparison before result import.', [control.btn_add_files])
        loads = []
        def loading(message):
            if message.startswith('Loading ') and message.endswith('…'):
                loads.append(not control.isEnabled())
                if len(loads) == 1:
                    comparison.grab().save(str(output / 'comparison_loading.png'))
        comparison.statusBar().messageChanged.connect(loading)
        choose(paths, multiple=True)
        click(control.btn_add_files)
        assert len(comparison.model.datasets) == 9 and all(loads) and len(loads) == 9
        QToolTip.hideText()
        first_rect = control.file_list.visualItemRect(control.file_list.item(0))
        QTest.mouseMove(control.file_list.viewport(), first_rect.center())
        tips = lambda: [w for w in app.topLevelWidgets() if w.isVisible() and w.windowType() == Qt.ToolTip]
        wait_until(lambda: bool(tips()) and paths[0].name in QToolTip.text(), timeout=5)
        report['checks']['hover_tooltip_text'] = QToolTip.text()
        # QToolTip.text() reads the visible Qt tooltip. Its transient native
        # surface does not reliably support QWidget.grab() on Windows.
        report['checks']['long_filename_hover_tooltip'] = True
        QTest.mouseMove(comparison.graph_panel, comparison.graph_panel.rect().center())
        metrics = comparison.model.impact_results[paths[0].name]
        expected = {'vertical_velocity': -1.49112, 'horizontal_speed': 0., 'angular_speed': 0.}
        bounds = {'vertical_velocity': .0223214285714, 'horizontal_speed': .0223214285714, 'angular_speed': .522040445909}
        for key, value in expected.items():
            assert abs(metrics.metrics[key].value - value) <= bounds[key]
        expected_height = 1.49112 ** 2 / (2 * 9.80665) * 1000
        height_bound = (2 * 1.49112 * bounds['vertical_velocity'] + bounds['vertical_velocity'] ** 2) / (2 * 9.80665) * 1000
        assert abs(metrics.metrics['equivalent_height'].value - expected_height) <= height_bound
        stats = comparison.model.get_impact_comparison()['statistics']
        assert stats['vertical_velocity']['n'] == 1
        contact = comparison.model.contact_results[paths[0].name]
        assert contact.outcome == 'Unclear'
        report['metrics'] = {'actual': {key: metrics.metrics[key].value for key in (*expected, 'equivalent_height')},
                             'expected': {**expected, 'equivalent_height': expected_height},
                             'bounds': {**bounds, 'equivalent_height': height_bound},
                             'distinct_observations': 1, 'contact_intent': 'unspecified', 'contact_outcome': contact.outcome}
        for mode in range(comparison.table_panel.view_combo.count()):
            comparison.table_panel.view_combo.setCurrentIndex(mode)
            events()
            capture(f'07_comparison_mode_{mode}', 'Existing comparison view: ' + comparison.table_panel.view_combo.currentText())
        expected_dialogs.append(True)
        choose(malformed)
        click(control.btn_add_files)
        assert not expected_dialogs and len(comparison.model.datasets) == 9
        choose(None)
        click(control.btn_add_files)
        assert len(comparison.model.datasets) == 9
        report['checks']['loading_error_cancel_preserve_comparison'] = True
        stage('Actual-time graph and 3D')
        combo = comparison.graph_panel.cb_plot_target
        index = combo.findText('Analysis | DropPosture | ThetaLongDeg')
        assert index >= 0
        combo.setCurrentIndex(index)
        playback = comparison.playback_panel
        start, end = playback.bounds
        for elapsed, row in ((0., 21), (.008, 22)):
            playback.master_slider.setValue(round(100000 * (elapsed - start) / (end - start)))
            events()
            assert playback.local_controls[paths[0].name]['slider'].value() == row
            assert comparison.graph_panel.cursor.get_xdata()[0] == playback.current_elapsed
            source_time = comparison.model.timelines[paths[0].name].times[row]
            assert abs(source_time - (.312 + elapsed)) < 1e-10
            frame = comparison.model.visualization_handlers[paths[0].name].get_frame_data(row)
            corner_y = float(frame.loc[frame[visual.DF_ENTITY_ID] == 'C1', visual.DF_POS_Y].iloc[0])
            expected_y = 12.24288 if row == 21 else 0.
            assert abs(corner_y - expected_y) <= .315179
            report.setdefault('synchronized_samples', []).append(
                {'elapsed': playback.current_elapsed, 'row_zero_based': row,
                 'source_time': source_time, 'corner_c1_y_mm': corner_y,
                 'expected_y_mm': expected_y, 'bound_mm': .315179})
        viewer = playback.widgets[paths[0].name]
        playback.scroll.ensureWidgetVisible(viewer)
        events()
        viewer.plotter.render()
        viewer.plotter.render_window.MakeCurrent()
        pixels = viewer.plotter.screenshot(str(output / '08_actual_3d.png'))
        assert pixels is not None and pixels.max() > pixels.min()
        report['checks']['vtk_pixel_shape'] = list(pixels.shape)
        comparison.table_panel.view_combo.setCurrentIndex(0)
        events()
        for bar in (playback.scroll.horizontalScrollBar(), comparison.table_panel.table.horizontalScrollBar()):
            assert bar.maximum() > 0
            bar.setValue(bar.maximum())
            events()
            assert bar.value() == bar.maximum()
            bar.setValue(0)
        capture('09_synchronized', 'At approximately +0.008 s from t1-minus, source sample 22 is 0.320 s; graph cursor and 3D selection agree.')
        comparison.resize(1100, 700)
        events(150)
        summary = comparison.table_panel.table
        assert summary.viewport().rect().contains(summary.visualItemRect(summary.item(0, 0)))
        capture('10_resized', 'Comparison resized to inspect primary actions and scroll access.', [control.btn_add_files])
        summary.setFocus()
        QTest.keyClick(summary, Qt.Key_End, Qt.ControlModifier)
        events()
        assert summary.currentRow() == summary.rowCount() - 1
        summary.horizontalScrollBar().setValue(0)
        assert summary.viewport().rect().contains(summary.visualItemRect(summary.item(summary.rowCount() - 1, 0)))
        capture('11_last_metric', 'Small window: Ctrl+End reaches the last metric through the existing summary table.', [control.btn_add_files])
        report['checks']['small_window_first_and_last_metric_accessible'] = True
        report['checks']['comparison_metrics_duplicate_count_time_and_3d'] = True
        report['checks']['no_pipeline_worker_started'] = not hasattr(main, 'worker')
        assert report['checks']['no_pipeline_worker_started']
        assert not report['findings'], report['findings']
        report['status'] = 'pass'
    except Exception:
        report['status'] = 'fail'
        report['exception'] = traceback.format_exc()
        if current is not None:
            current.grab().save(str(output / 'failure.png'))
        raise
    finally:
        watcher.stop()
        for window in reversed(windows):
            window.close()
        events()
        sys.excepthook = previous_exception_hook
        report['errors'] = errors
        report['protected_sha256_after'] = {str(path): sha(path) if path.exists() else None for path in protected}
        report['copied_input_sha256_after'] = {str(path.relative_to(inputs)): sha(path) for path in inputs.rglob('*') if path.is_file()}
        unchanged = (report['protected_sha256_after'] == before and report['copied_input_sha256_after'] == copied_before)
        report['checks']['producer_inputs_and_results_unchanged'] = unchanged
        stable_implementation = report['implementation_sha256'] == {str(path): sha(path) for path in implementation}
        report['checks']['implementation_unchanged_during_execution'] = stable_implementation
        if not unchanged or errors or not stable_implementation:
            report['status'] = 'fail'
        flush()
        print('Release GUI evidence:', output)
        assert unchanged and not errors and stable_implementation
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--trial-report', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    run(args.trial_report.resolve(), args.output.resolve())


if __name__ == '__main__':
    main()
