"""Render production PUB04 controls with independently declared public fixtures."""
import argparse
import hashlib
import json
from pathlib import Path
import platform
import subprocess
import time

import matplotlib
import PySide6
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from src.analysis.app.main_window import MainApp
from src.analysis.pipeline.scene_workflow_state import PLAN_SPEC
from src.simulation.scene_review_fixtures import public_raw, install_ui_fixture

STATES = ('empty', 'one', 'many', 'edited', 'manual', 'blocked', 'loading', 'error', 'details')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', default='tmp/issue137/final')
    parser.add_argument('--native', action='store_true')
    parser.add_argument('--state', default='edited', choices=STATES)
    parser.add_argument('--size', default='1920x1080')
    args = parser.parse_args()
    app = QApplication.instance() or QApplication([])
    root = Path(args.output)
    root.mkdir(parents=True, exist_ok=True)
    source = public_raw(root / ('input-' + str(time.time_ns())))
    screen = app.primaryScreen()
    target = (screen.availableGeometry().width(), screen.availableGeometry().height())
    cases = [(args.state, tuple(map(int, args.size.split('x'))))] if args.native else (
        [(state, size) for size in ((820, 600), (1920, 1080)) for state in STATES]
        + [('details', target)])
    states = []
    for state, size in cases:
        window = MainApp()
        window.setWindowTitle('Scene review #137 — PRODUCTION — ' + state)
        w = window.original_widget
        install_ui_fixture(w, source, state)
        window.resize(*size)
        window.show()
        if not QTest.qWaitForWindowExposed(window, 2000):
            raise RuntimeError('Production validation window was not exposed.')
        QTest.qWait(100)
        # Match layout tests: Windows may constrain only the initial exposure
        # to fit its decorations. Request the logical client size afterwards.
        window.resize(*size)
        QTest.qWait(100)
        w.update_plot()
        w.plot_manager.ax.set_xlim(0., 3.)
        w.plot_manager.ax.set_ylim(-100., 100.)
        w.canvas.draw()
        app.processEvents()
        if args.native:
            return app.exec()
        filename = f'{size[0]}x{size[1]}-{state}.png'
        window.grab().save(str(root/filename))
        buttons = {}
        for key, button in [('detect', w.scene_panel.detect_button), ('open_review', w.scene_panel.open_review_button),
            ('details', w.scene_panel.details_section.button),
            ('revert', w.scene_panel.revert_button), ('save_current', w.save_slice_button),
            ('save_included', w.scene_panel.save_all_button), ('process', w.save_process_button)]:
            p = button.mapTo(window, button.rect().topLeft())
            q = button.mapTo(window, button.rect().bottomRight())
            buttons[key] = dict(text=button.text(), enabled=button.isEnabled(), visible=button.isVisible(),
                rect=[p.x(), p.y(), button.width(), button.height()],
                inside_window=window.rect().contains(p) and window.rect().contains(q),
                sufficient_width=button.width() >= button.sizeHint().width())
        actual_size = [window.width(), window.height()]
        buttons['open_review']['disclosure'] = 'Details'
        passed = (actual_size == list(size) and all(b['inside_window'] and
            (b['visible'] or k == 'open_review' and buttons['details']['visible']) and b['sufficient_width']
            for k, b in buttons.items()))
        states.append(dict(state=state, requested_size=list(size), actual_size=actual_size,
            buttons=buttons, signal=w.combo_plot_axis.currentData(), selected_id=w.scene_panel.selected_id(),
            current_gate=list(w._scene_save_gate()), included_gate=list(w._scene_save_gate(batch=True)),
            range_text=w.scene_panel.range_label.text(), type_basis=w.scene_panel.type_basis_label.text(),
            xlim=[float(v) for v in w.plot_manager.ax.get_xlim()], ylim=[float(v) for v in w.plot_manager.ax.get_ylim()],
            plot_canvas_size=[w.canvas.width(), w.canvas.height()], screenshot=filename,
            result='pass' if passed else 'fail', evidence_kind='production-widget-render'))
        window.close()
        window.deleteLater()
        app.processEvents()
    report = dict(schema_version=1, plan_spec=PLAN_SPEC, kind='scene-review-production-render',
        code_head=subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
        working_tree='modified' if subprocess.check_output(['git', 'status', '--porcelain'], text=True).strip() else 'clean',
        environment=dict(platform=platform.platform(), python=platform.python_version(), pyside=PySide6.__version__,
            matplotlib=matplotlib.__version__, qt_platform=app.platformName(), dpr=screen.devicePixelRatio(),
            target_available=list(target)), input=dict(source_kind='public-handcrafted-synthetic',
            raw_sha256=hashlib.sha256(source.read_bytes()).hexdigest(), path=str(source), rows=601,
            time_basis='capture_seconds', units='mm', expected_capture_interval_s=[0., 12.],
            independent_ui_ranges='0.10+0.5i through 0.35+0.5i inclusive capture seconds'),
        mockup_approval='User approved FHD/minimum mockups on 2026-10-03 before production UI edits.',
        states=states, result='pass' if all(s['result'] == 'pass' for s in states) else 'fail',
        render_size_policy='requested logical client size after initial Windows exposure',
        native_status='not-executed', measured_calibration='#104 separate, not assessed')
    (root/'execution.json').write_text(json.dumps(report, indent=2, allow_nan=False)+'\n', encoding='utf-8')
    print(json.dumps(dict(result=report['result'], states=len(states), code_head=report['code_head'],
                         raw_sha256=report['input']['raw_sha256'])))
    return 0 if report['result'] == 'pass' else 1


if __name__ == '__main__':
    raise SystemExit(main())
