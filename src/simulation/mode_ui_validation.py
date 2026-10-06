"""Original-size production QWidget evidence; native input remains separate."""
import argparse
from datetime import datetime, timezone
from importlib.metadata import version
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import subprocess
import sys

from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest
from src.simulation.ui.main_window import SimulationUI
from src.utils.marker_profile_identity import envelope, digest


def main():
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('--output', required=True)
    args = parser.parse_args(); root = Path(args.output); root.mkdir(parents=True, exist_ok=False)
    app = QApplication.instance() or QApplication([])
    dpr = app.primaryScreen().devicePixelRatio()
    changed = subprocess.check_output(['git', 'diff', '--name-only'], text=True).splitlines()
    sources = changed + ['src/simulation/ui/mode_settings.py', 'src/simulation/mode_ui_validation.py', 'tests/test_simulation_modes_gui.py']
    report = envelope('RunReport', run_id='pub06-ui-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'),
        utc=datetime.now(timezone.utc).isoformat(), fresh=True, reused=False, tier='production-widget-render',
        command=[sys.executable, *sys.argv], code=dict(commit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
            dirty=bool(changed), changed_paths=sorted(set(sources)),
            source_sha256={path: hashlib.sha256(Path(path).read_bytes()).hexdigest() for path in sorted(set(sources)) if Path(path).is_file()}),
        environment=dict(os=platform.platform(), python=platform.python_version(), dependencies={name: version(name) for name in ('PySide6', 'mujoco', 'numpy', 'scipy')},
            platform=app.platformName(), qt_process_scale=os.environ.get('QT_SCALE_FACTOR'), screen_dpr=dpr,
            available_logical=[app.primaryScreen().availableGeometry().width(), app.primaryScreen().availableGeometry().height()],
            native_os125='not verified; process scale does not establish OS scale'),
        approval=dict(mockup='Human approved latest shared G17/H12 workspace: 이제 좀 낫긴하네 이거로 해봐', trial='not_evaluated', baseline='no promotion', tolerance='no promotion'),
        native=dict(status='not_executed', reason='Separate native input/OS125 tier; previous activation failures preserved'),
        experimental_validation=dict(status='not_executed', reason='#104 separate; public fixtures only'),
        input=dict(source_kind='public_ui_state_fixture', seed=74082, configuration_hashes=[]),
        oracle='Literal G17/H12 row counts, initial edge(3,4), row8 face3, original manual123mm/Z17 roundtrip; widget bounds are inspected independently of PNG',
        signatures=dict(status='not_applicable', reason='No numerical optimizer/regression baseline in widget rendering'),
        optimizer=dict(starts=0, reason='No optimizer invoked'),
        registration=dict(status='not_applicable', reason='#113 excluded'), states=[], completion='running')
    def capture(window, name, small=False, scope='Production widgets with public state fixture'):
        target = (820, 600) if small else (math.ceil(1920/dpr), math.ceil(1080/dpr))
        window.resize(*target)
        window.show(); QTest.qWait(50); app.processEvents()
        # Windows may constrain the initial client size to the work area while
        # showing a decorated window. Reassert the requested widget size, as the
        # existing profile/scene render fixtures do; this is not native capture.
        window.resize(*target); QTest.qWait(50); app.processEvents()
        if small and name.endswith('preview'):
            window.form_scroll.ensureWidgetVisible(window.orientation_preview); app.processEvents()
            rect = window.orientation_preview.rect(); rect.moveTopLeft(window.orientation_preview.mapTo(window.form_scroll.viewport(), rect.topLeft()))
            assert window.form_scroll.viewport().rect().contains(rect), 'Scrolled small preview must be wholly inside the viewport.'
        if small:
            for control in (*window._value_controls(), window.cat_combo, window.drop_combo, window.rotation_section.button):
                if control.isVisible(): assert control.height() >= control.minimumSizeHint().height(), 'Small fields must retain their readable natural height.'
        for control in (window.run_btn, window.batch_btn, window.marker_btn):
            assert control.visibleRegion().contains(control.rect()), 'Primary actions must remain reachable.'
        if not small:
            assert window.right_scroll.isVisible()
            preview_rect = window.preview_group.rect()
            preview_rect.moveTopLeft(window.preview_group.mapTo(window.right_scroll.viewport(), preview_rect.topLeft()))
            unused_bottom = window.right_scroll.viewport().height() - preview_rect.bottom() - 1
            assert unused_bottom <= window.right_layout.contentsMargins().bottom(), 'The preview must consume the remaining workspace, as approved, rather than leave a blank lower panel.'
            if window.settings.tabs.currentIndex() == 0:
                assert window.settings.table.viewport().height() >= 5*window.settings.table.rowHeight(0), 'Five preset rows must actually be visible.'
            for control in (window.orientation_preview, window.settings.apply_button):
                rect = control.rect(); rect.moveTopLeft(control.mapTo(window.right_scroll.viewport(), rect.topLeft()))
                assert window.right_scroll.viewport().rect().contains(rect), 'Preview and Apply must fit without scrolling in the FHD workspace.'
        pixmap = window.grab(); path = root/(name+'.png'); assert pixmap.save(str(path))
        if not small: assert pixmap.width() >= 1920 and pixmap.height() >= 1080, (target, window.size(), pixmap.size(), dpr)
        report['states'].append(dict(name=name, screenshot=path.name, logical=[window.width(), window.height()],
            pixels=[pixmap.width(), pixmap.height()], dpr=pixmap.devicePixelRatio(), mode=window.profiles.mode,
            selected_preset=window.orientation_preview.sequence_spec.id, scope=scope,
            sequence_steps=len(window.profiles.configs[window.profiles.mode]['sequence_profile']['steps']),
            preset_rows=window.settings.table.rowCount(), preview_meaning='Preset target, not a predicted contact',
            preview_logical=[window.orientation_preview.width(), window.orientation_preview.height()],
            unused_bottom_logical=None if small else unused_bottom,
            expected='Actions inside viewport; preview visible; G17 or H12 browser, no phantom robot execution', actual='passed', tolerance=0, fresh=True))
        report['input']['configuration_hashes'].append(digest(window.profiles.configs[window.profiles.mode]))
    window = SimulationUI()
    try:
        capture(window, 'single-default')
        window.custom_h_input.setValue(123); window.custom_y_input.setValue(17)
        window.mode_combo.setCurrentIndex(1)
        assert window.settings.table.rowCount() == 17
        capture(window, 'robot-sequence')
        window.settings.table.selectRow(7)
        assert window.orientation_preview.sequence_spec.faces == (3,)
        capture(window, 'robot-face3')
        for tab, name in [(1, 'robot-physics'), (2, 'robot-observation')]: window.settings.tabs.setCurrentIndex(tab); capture(window, name)
        window.settings.tabs.setCurrentIndex(0)
        window.settings.table.item(1, 1).setText('NaN'); window.settings.apply_settings()
        assert 'not applied' in window.settings.status.text()
        assert window.settings.table.currentRow() == 1
        capture(window, 'robot-invalid'); window.settings.cancel_settings()
        window.mode_combo.setCurrentIndex(0)
        assert window.custom_h_input.value() == 123 and window.custom_y_input.value() == 17
        capture(window, 'single-returned')
        window.result_label.setText('Cancelled. Previous result: public-fixture.proc'); window.result_label.show()
        capture(window, 'cancelled-previous', scope='Production result label; public fixture text, no simulated completion claim')
        for mode in (0, 1):
            window.mode_combo.setCurrentIndex(mode)
            capture(window, f'mode{mode}-820x600', True)
            capture(window, f'mode{mode}-820x600-preview', True)
        report['completion'] = 'passed'
    except BaseException as error:
        report['completion'] = 'failed'; report['failure'] = repr(error); raise
    finally:
        window.close(); (root/'RunReport.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(dict(states=len(report['states']), status=report['completion'], dpr=dpr)))


if __name__ == '__main__': main()
