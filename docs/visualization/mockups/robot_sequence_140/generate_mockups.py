"""Review-only PUB07 states, reusing the approved PUB06 production workspace."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QComboBox, QFormLayout, QHBoxLayout, QLabel, QPushButton
from src.simulation.ui.mode_settings import preset_steps
from src.simulation.ui.main_window import SimulationUI


class Proposal(SimulationUI):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('Simulation — #140 review mockup')
        for button in (self.run_btn, self.batch_btn, self.marker_btn):
            button.clicked.disconnect()
        page = self.settings.tabs.widget(0)
        controls = QFormLayout()
        self.handling = QComboBox()
        self.handling.addItems(['Configuration only', 'Public example: G airborne', 'Public example: H floor supported'])
        self.face = QComboBox(); self.face.addItems(['Auto: upward face at pickup', 'Local +Z', 'Local +X'])
        row = QHBoxLayout(); row.addWidget(self.handling, 2); row.addWidget(QLabel('Attach')); row.addWidget(self.face, 1)
        controls.addRow('Handling profile', row)
        self.scope = QComboBox(); self.scope.addItems(['Entire plan', 'Selected drop only'])
        self.preview_plan = QPushButton('Preview sequence')
        row = QHBoxLayout(); row.addWidget(self.scope, 1); row.addWidget(self.preview_plan)
        controls.addRow('Run scope', row)
        page.layout().insertLayout(1, controls)
        self.settings.fit_tab()
        self.sequence_preview = QLabel(); self.sequence_preview.setWordWrap(True)
        self.sequence_preview.setTextFormat(Qt.PlainText); self.sequence_preview.hide()
        page.layout().addWidget(self.sequence_preview)
        self.preview_plan.clicked.connect(self.show_sequence_preview)

    def show_sequence_preview(self):
        self.sequence_preview.setText('Proposed virtual profile: approach / attach / lift / orient / hold / release / contact / settle / pickup.\n'
            'Attach: upward face, sphere endpoint 5 mm; measured distance ≤ 2 mm, normal ≤ 5°, relative speed ≤ 30 mm/s.\n'
            'G: airborne release. H: floor edge support, explicit local pivot and 15° Y rotation. Conditions require review; no trial approval.')
        self.sequence_preview.show(); self.settings.fit_tab()

    def closeEvent(self, event):
        event.accept()  # All states are review-only, with no live worker.


def main():
    parser = argparse.ArgumentParser(); parser.add_argument('--output', required=True)
    root = Path(parser.parse_args().output); root.mkdir(parents=True, exist_ok=False)
    app = QApplication.instance() or QApplication([])
    window = Proposal(); dpr = app.primaryScreen().devicePixelRatio()
    report = dict(schema_version=1, plan_spec='ISTA6A-PLAN-20261001-v1', object_type='RunReport',
        utc=datetime.now(timezone.utc).isoformat(), command=[sys.executable, *sys.argv],
        code_commit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
        script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        tier='review-only-widget-render', fresh=True, reused=False, approval='pending human review',
        qt_process_scale=os.environ.get('QT_SCALE_FACTOR'), platform=app.platformName(),
        native_os125='unexecuted; Qt process scale is separate', states=[])
    def capture(name, small=False):
        size = (820, 600) if small else (math.ceil(1920/dpr), math.ceil(1080/dpr))
        window.resize(*size); window.show(); QTest.qWait(60); window.resize(*size); app.processEvents()
        for button in (window.run_btn, window.batch_btn, window.marker_btn):
            assert button.visibleRegion().contains(button.rect()), 'Primary actions clipped'
        if not small:
            rect = window.orientation_preview.rect(); rect.moveTopLeft(window.orientation_preview.mapTo(window.right_scroll.viewport(), rect.topLeft()))
            assert window.right_scroll.viewport().rect().contains(rect), 'Target preview clipped'
        image = window.grab(); assert image.save(str(root/(name+'.png')))
        report['states'].append(dict(name=name, logical=[window.width(), window.height()], pixels=[image.width(), image.height()],
            dpr=image.devicePixelRatio(), source='public UI state fixture',
            actual=window.result_label.text(), scope='Mockup labels/buttons; no engine or native acceptance',
            expected='Shared layout, original target picture, primary buttons accessible', status='passed'))
    try:
        window.handling.setEnabled(False); window.face.setEnabled(False); window.scope.setEnabled(False); window.preview_plan.setEnabled(False)
        capture('single-default')
        window.mode_combo.setCurrentIndex(1)
        window.duration_input.setValue(60.)
        window.duration_input.parentWidget().layout().labelForField(window.duration_input).setText('Run time limit (s):')
        for control in (window.handling, window.face, window.scope, window.preview_plan): control.setEnabled(True)
        window.handling.setCurrentIndex(1)
        window.settings.sequence_hint.setText('17 planned drops. Public synthetic handling; hazard block unavailable.')
        window.settings.status.setText('Preview the handling profile, then Use in Simulation. Existing saved plans stay configuration-only.')
        capture('robot-draft')
        window.show_sequence_preview(); capture('robot-preview'); window.sequence_preview.hide(); window.settings.fit_tab()
        window.settings.status.setText('Public G example applied. Entire plan: 16 supported / 1 unavailable (hazard block).')
        window.result_label.setText('Entire plan blocked: G17 hazard block unavailable. Choose a supported subset or selected drop.'); window.result_label.show()
        capture('robot-entire-incomplete')
        window.scope.setCurrentIndex(1); window.settings.table.selectRow(7)
        window.settings.status.setText('Public G example applied. Selected drop 8 / 17. Virtual conditions; trial approval pending.')
        window.result_label.setText('Ready: selected face 3. Previous result: public-single.proc')
        window.run_btn.setEnabled(True); window.marker_btn.setEnabled(True)
        window.batch_btn.setToolTip('Single-drop preset batch is available in Single drop mode.')
        capture('robot-selected')
        window.scope.setCurrentIndex(0)
        window.settings.rows=window.settings.rows[:-1]; window.settings._paint_rows(7)
        window.settings.sequence_hint.setText('16 supported drops in this edited plan. Omitted: G17 hazard block.')
        window.settings.status.setText('Public G example applied. Full edited plan; omitted test remains unavailable.')
        window.result_label.setText('Drop 2 / 16 — pickup · 8.640 s. Previous result: public-single.proc')
        window._set_busy(True); window.progress_bar.setValue(38); capture('robot-running')
        window._set_busy(False)
        window.result_label.setText('Drop 2 — attach failed: face is not accessible. Partial capture retained. Previous result: public-single.proc')
        window.run_btn.setEnabled(True); window.marker_btn.setEnabled(True); window.run_btn.setText('Retry Run')
        capture('robot-attach-failed')
        window.result_label.setText('Cancelled at 8.640 s — partial capture retained. Previous result: public-single.proc')
        capture('robot-cancelled')
        window.settings.status.setText('Profile not applicable: box mass changed. Preview and explicitly apply updated conditions.')
        window.result_label.setText('Cannot run with a stale handling profile. Previous result: public-single.proc')
        window.run_btn.setEnabled(False); window.marker_btn.setEnabled(False); capture('robot-inapplicable')
        window.settings.table.item(1, 1).setText('NaN'); window.settings.table.selectRow(1)
        window.settings.status.setText('Drop 2 clearance must be finite. Settings not applied.'); capture('robot-invalid')
        window.settings.cancel_settings()
        config=window.profiles.configs['robot_sequence']
        from src.simulation.scenarios import Scenarios
        config['sequence_profile']['steps']=preset_steps(Scenarios.CATEGORIES[1],config['size_mm'],config['physics_profile']['mass_kg'])
        window.profiles.set_config(config); window._load_config()
        window.handling.setCurrentIndex(2); window.settings.sequence_hint.setText('12 planned drops. Public H supported rotation; requires explicit per-drop support geometry.')
        window.settings.status.setText('H example uses floor support before release. It is not a validated ISTA procedure.')
        window.result_label.setText('Ready for supported template preview. Previous result: public-single.proc'); capture('robot-h-supported')
        capture('robot-820x600', True)
        window._show_settings(); dialog=window.settings_dialog
        dialog.resize(820,600); QTest.qWait(60); dialog.resize(820,600); app.processEvents()
        image=dialog.grab(); assert image.save(str(root/'robot-settings-820x600.png'))
        for control in (window.handling,window.scope,window.preview_plan,window.settings.apply_button,window.settings.cancel_button):
            assert control.visibleRegion().contains(control.rect()), 'Narrow settings actions clipped'
        report['states'].append(dict(name='robot-settings-820x600',logical=[dialog.width(),dialog.height()],pixels=[image.width(),image.height()],dpr=image.devicePixelRatio(),status='passed'))
        dialog.reject()
        report['completion'] = 'passed'
    finally:
        window.close(); (root/'RunReport.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(dict(states=len(report['states']), status=report['completion'], dpr=dpr)))


if __name__ == '__main__': main()
