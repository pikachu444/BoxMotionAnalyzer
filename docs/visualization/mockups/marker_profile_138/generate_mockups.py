"""Disposable #138 preapproval prototype; production widgets are unchanged."""
from __future__ import annotations

import argparse
import copy
from datetime import datetime, timezone
import hashlib
import json
import platform
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))

import PySide6
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtTest import QTest
from PySide6.QtWidgets import (QApplication, QComboBox, QDialog, QFormLayout,
    QHBoxLayout, QHeaderView, QLabel, QLineEdit, QPushButton, QSplitter,
    QTableWidget, QTableWidgetItem, QTabWidget, QVBoxLayout, QWidget)
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure

from src.simulation.marker_fixtures import load_profile, draw_profile, validate_profile
from src.simulation.ui.marker_export_dialog import MarkerExportDialog

PLAN_SPEC = 'ISTA6A-PLAN-20261001-v1'
STATES = ('copy', 'edited', 'reset', 'invalid', 'legacy', 'incompatible',
          'unsupported', 'unidentifiable', 'save-error', 'applied', 'example32')
EXPECTED_HASHES = {
    '18': '66ac8c6d2bcd9b531d532a23c2af7b04e72a7ae1ab1ae8aa8c0c8ec7ef77bafb',
    '32': 'd5405f1cf434c924070033748b4ca1e4661f10e190369d8f0bb0aac75fc97ff0',
}


class Prototype(QDialog):
    """Interactive draft, reset and Apply demonstration; no production writes."""

    def __init__(self, state='copy', size=(1100, 700)):
        super().__init__()
        self.state = state
        self.base = load_profile(example='32' if state == 'example32' else '18')
        self.applied = copy.deepcopy(self.base)
        self.draft = copy.deepcopy(self.base)
        self.draft['profile_id'] = 'custom-example-32' if state == 'example32' else 'custom-example-18'
        self.draft['publication'] = 'user-copy-not-experimental-standard'
        self.draft['source'] = 'User copy of ' + self.base['profile_id']
        if state == 'unidentifiable':
            self.draft['markers'] = [dict(id=f'F{i+1}', face='FRONT', xyz_mm=[x, 0., 40.])
                                     for i, x in enumerate((-60., -20., 20.))]
        if state in ('edited', 'incompatible', 'save-error', 'applied'):
            self.draft['markers'][0]['xyz_mm'][0] = 22.
        self.valid_preview = copy.deepcopy(self.draft)
        self.setWindowTitle('Marker profile #138 — PREAPPROVAL MOCKUP — ' + state)
        self.setMinimumSize(820, 600)
        outer = QVBoxLayout(self)
        top = QHBoxLayout()
        top.addWidget(QLabel('Profile ID'))
        self.profile_id = QLineEdit(self.draft['profile_id'])
        top.addWidget(self.profile_id, 1)
        self.copy_button = QPushButton('Copy preset')
        self.copy_button.setToolTip('Make a custom copy. The public preset stays unchanged.')
        top.addWidget(self.copy_button)
        outer.addLayout(top)
        self.lineage = QLabel('Custom copy of ' + self.base['profile_id'])
        self.lineage.setWordWrap(True)
        outer.addWidget(self.lineage)
        dims = ' × '.join(f'{d:g}' for d in self.draft['box_dims_mm'])
        self.applied_label = QLabel(f'Box: {dims} mm    Preset unchanged    Applied: {self.applied["profile_id"]}')
        self.applied_label.setWordWrap(True)
        outer.addWidget(self.applied_label)

        self.table = QTableWidget(len(self.draft['markers']), 5)
        self.table.setHorizontalHeaderLabels(['Name', 'Face', 'X (mm)', 'Y (mm)', 'Z (mm)'])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setMinimumWidth(320)
        self.table.itemChanged.connect(self.changed)
        self.fill_table()

        self.figure = Figure(layout='constrained')
        self.canvas = FigureCanvasQTAgg(self.figure)
        self.axes = self.figure.add_subplot(111, projection='3d')
        self.canvas.setMinimumSize(280, 200)
        self.preview_panel = QWidget()
        pv = QVBoxLayout(self.preview_panel)
        pv.setContentsMargins(0, 0, 0, 0)
        self.preview_title = QLabel('Draft preview — not applied')
        pv.addWidget(self.preview_title)
        pv.addWidget(self.canvas, 1)
        self.preview_button = QPushButton('Preview draft')
        pv.addWidget(self.preview_button)
        self.preview_button.clicked.connect(self.preview)

        self.rules_panel = QWidget()
        form = QFormLayout(self.rules_panel)
        for label, value in (
            ('Origin', 'Box geometric center'), ('Units', 'mm; recorded time in seconds'),
            ('Local X', '+Right / −Left'), ('Local Y', '+Top / −Bottom'),
            ('Local Z', '+Front / −Back'), ('World vertical', '+Y'),
            ('Names', 'F / B / R / L / T / M identify the declared face'),
            ('Local X half-turn', 'Front ↔ Back; Top ↔ Bottom'),
            ('Local Y half-turn', 'Front ↔ Back; Left ↔ Right'),
            ('Local Z half-turn', 'Left ↔ Right; Top ↔ Bottom'),
            ('Correction', 'Analysis face assignment; measured XYZ and IDs preserved'),
            ('Meaning version', 'Current fixed rules — read only'),
        ):
            text = QLabel(value); text.setWordWrap(True)
            form.addRow(label, text)
        if size[0] >= 1100:
            self.tabs = QTabWidget()
            self.tabs.addTab(self.preview_panel, 'Preview')
            self.tabs.addTab(self.rules_panel, 'Rules')
            splitter = QSplitter(Qt.Horizontal)
            splitter.addWidget(self.table); splitter.addWidget(self.tabs)
            splitter.setSizes([size[0] * 45 // 100, size[0] * 55 // 100])
            outer.addWidget(splitter, 1)
        else:
            self.tabs = QTabWidget()
            self.tabs.addTab(self.table, 'Markers')
            self.tabs.addTab(self.preview_panel, 'Preview')
            self.tabs.addTab(self.rules_panel, 'Rules')
            outer.addWidget(self.tabs, 1)

        self.layout_status = QLabel('Whole layout: local pose constraints supported')
        self.layout_status.setToolTip('Public fixture support is not global uniqueness or real-layout approval.')
        outer.addWidget(self.layout_status)
        self.compatibility = QLabel('Previous result: compatible with the applied profile')
        self.compatibility.setWordWrap(True)
        outer.addWidget(self.compatibility)
        self.status = QLabel('Draft ready. Preview and Apply are separate.')
        self.status.setWordWrap(True)
        self.status.setTextFormat(Qt.PlainText)
        outer.addWidget(self.status)
        actions = QHBoxLayout()
        self.reset_button = QPushButton('Reset to source')
        self.reset_button.setToolTip('Restore the copied/imported source into the draft. Keep custom ID; Apply is still required.')
        self.save_button = QPushButton('Save JSON…')
        self.apply_button = QPushButton('Apply')
        self.cancel_button = QPushButton('Cancel')
        for button in (self.reset_button, self.save_button):
            actions.addWidget(button)
        actions.addStretch()
        for button in (self.apply_button, self.cancel_button):
            actions.addWidget(button)
        outer.addLayout(actions)
        self.reset_button.clicked.connect(self.reset)
        self.copy_button.clicked.connect(self.reset)
        self.apply_button.clicked.connect(self.apply)
        self.cancel_button.clicked.connect(self.reject)
        self.save_button.clicked.connect(lambda: self.status.setText('Prototype only: production persistence is pending approval.'))
        self.profile_id.textChanged.connect(self.changed)
        self.draw()
        if state == 'invalid':
            self.table.item(0, 2).setText('not-a-number')
        elif state == 'legacy':
            self.compatibility.setText('Previous result: meaning unknown (legacy). Comparison blocked.')
            self.compatibility.setToolTip('No semantic declaration exists. Apply affects future exports only; it cannot approve this old result.')
        elif state == 'incompatible':
            self.compatibility.setText('Previous result: incompatible. F1 position changed; reprocessing required.')
        elif state == 'unsupported':
            self.status.setText('Unsupported meaning version. Apply and generation blocked.')
            self.apply_button.setEnabled(False); self.save_button.setEnabled(False)
            self.preview_title.setText('Imported positions only — interpretation unsupported')
            self.compatibility.setText('Previous result: unsupported meaning version. Comparison blocked.')
        elif state == 'unidentifiable':
            self.layout_status.setText('Pose unavailable: insufficient whole-layout constraints')
            self.compatibility.setText('Geometry import is allowed. This layout cannot establish a full pose.')
        elif state == 'save-error':
            self.status.setText('Save failed. Draft and applied profile preserved; retry available.')
        elif state == 'applied':
            self.apply()
        elif state == 'reset':
            self.reset()
        self.resize(*size)

    def fill_table(self):
        self.table.blockSignals(True)
        self.table.setRowCount(len(self.draft['markers']))
        for row, marker in enumerate(self.draft['markers']):
            values = [marker['id'], marker['face'], *[f'{n:g}' for n in marker['xyz_mm']]]
            for col, value in enumerate(values):
                self.table.setItem(row, col, QTableWidgetItem(value))
        self.table.blockSignals(False)

    def read_draft(self):
        result = copy.deepcopy(self.draft)
        result['profile_id'] = self.profile_id.text()
        result['markers'] = [dict(id=self.table.item(r, 0).text(), face=self.table.item(r, 1).text(),
            xyz_mm=[float(self.table.item(r, c).text()) for c in (2, 3, 4)])
            for r in range(self.table.rowCount())]
        validate_profile(result)
        return result

    def changed(self, *_args):
        if not hasattr(self, 'status'):
            return
        try:
            self.draft = self.read_draft()
        except (ValueError, TypeError, KeyError) as error:
            self.status.setText('Invalid draft: ' + str(error))
            self.apply_button.setEnabled(False); self.save_button.setEnabled(False)
            self.preview_button.setEnabled(False)
            self.preview_title.setText('Last valid preview — current draft invalid')
            self.table.item(0, 2).setBackground(QColor('#ffe0e0'))
        else:
            self.status.setText('Draft changed. Preview and Apply are required.')
            self.apply_button.setEnabled(True); self.save_button.setEnabled(True)
            self.preview_button.setEnabled(True)
            self.preview_title.setText('Previous preview — draft changed')

    def draw(self):
        self.axes.clear()
        draw_profile(self.valid_preview, self.axes)
        self.axes.set_title('Box-local layout (mm)', fontsize=11)
        self.axes.legend(fontsize=8, loc='upper left')
        self.canvas.draw()

    def preview(self):
        self.draft = self.read_draft()
        self.valid_preview = copy.deepcopy(self.draft)
        self.draw()
        self.preview_title.setText('Draft preview — not applied')
        self.status.setText('Preview updated. Applied profile is unchanged.')

    def reset(self):
        custom_id = self.profile_id.text()
        self.draft = copy.deepcopy(self.base)
        self.draft.update(profile_id=custom_id, publication='user-copy-not-experimental-standard',
                          source='User copy of ' + self.base['profile_id'])
        self.fill_table()
        self.preview_button.setEnabled(True); self.apply_button.setEnabled(True)
        self.save_button.setEnabled(True)
        self.preview()
        self.status.setText('Draft reset to source. Custom ID retained; Apply is required.')

    def apply(self):
        self.draft = self.read_draft()
        self.applied = copy.deepcopy(self.draft)
        dims = ' × '.join(f'{d:g}' for d in self.applied['box_dims_mm'])
        self.applied_label.setText(f'Box: {dims} mm    Preset unchanged    Applied: {self.applied["profile_id"]}')
        self.status.setText('Applied: ' + self.applied['profile_id'] + '. Not saved to JSON yet.')
        self.preview_title.setText('Applied layout')
        self.valid_preview = copy.deepcopy(self.applied)
        self.draw()


def capture(window, out, name, requested):
    window.show()
    QApplication.processEvents()
    window.resize(*requested)
    QApplication.processEvents()
    pixmap = window.grab()
    assert [window.width(), window.height()] == list(requested)
    assert pixmap.save(str(out / name))
    buttons = [b for b in window.findChildren(QPushButton) if b.isVisible()]
    for button in buttons:
        for corner in (button.rect().topLeft(), button.rect().bottomRight()):
            position = button.mapTo(window, corner)
            assert window.rect().contains(position), (name, button.text(), position)
    return dict(screenshot=name, logical_size=list(requested),
        pixel_size=[pixmap.width(), pixmap.height()], dpr=window.devicePixelRatioF(),
        visible_buttons=[b.text() for b in buttons],
        evidence_kind='Qt-widget-render-preapproval', fresh=True)


def interaction_check(app):
    window = Prototype()
    window.show(); app.processEvents()
    original = copy.deepcopy(window.applied)
    window.table.item(0, 2).setText('22')
    QTest.mouseClick(window.preview_button, Qt.LeftButton)
    assert window.draft['markers'][0]['xyz_mm'][0] == 22.
    assert window.applied == original
    QTest.mouseClick(window.reset_button, Qt.LeftButton)
    assert window.draft['markers'][0]['xyz_mm'] == [21, 12, 40]
    assert window.profile_id.text() == 'custom-example-18'
    window.table.item(0, 2).setText('bad')
    assert not window.apply_button.isEnabled() and window.applied == original
    window.reset()
    window.table.item(0, 2).setText('22')
    QTest.mouseClick(window.apply_button, Qt.LeftButton)
    assert window.applied['markers'][0]['xyz_mm'][0] == 22.
    window.close()
    return dict(status='pass', kind='prototype-QTest-only',
        oracle='F1 [21,12,40] -> [22,12,40]; Preview does not Apply; Reset restores 21 and keeps custom ID',
        production_persistence='not-implemented', native_input='not-executed')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--native', action='store_true')
    parser.add_argument('--state', choices=STATES, default='edited')
    parser.add_argument('--size', default='1100x700')
    parser.add_argument('--output', type=Path, default=Path(__file__).resolve().parent)
    args = parser.parse_args()
    app = QApplication.instance() or QApplication([])
    screen = app.primaryScreen()
    target = (screen.availableGeometry().width(), screen.availableGeometry().height())
    if args.native:
        window = Prototype(args.state, tuple(map(int, args.size.split('x'))))
        window.show()
        return app.exec()
    out = args.output
    out.mkdir(parents=True, exist_ok=True)
    for example, expected in EXPECTED_HASHES.items():
        assert validate_profile(load_profile(example=example)) == expected
    evidence = []
    sim = dict(duration=.5, height=250., mass=1., com_offset=[0., 0., 0.])
    # Existing production dialog, untouched, for a before/after comparison.
    before = MarkerExportDialog(sim, (200., 120., 80.))
    evidence.append(capture(before, out, '1920x1080-existing.png', (1920, 1080)))
    before.close()
    # Proposed entry points are inserted into this disposable instance only.
    parent = MarkerExportDialog(sim, (200., 120., 80.))
    row = parent.controls.layout().itemAt(0).layout()
    row.addWidget(QPushButton('Copy…')); row.addWidget(QPushButton('Edit…'))
    parent.status.setText('Applied: Public example 18. Copy or import a draft to edit.')
    evidence.append(capture(parent, out, '1920x1080-entry.png', (1920, 1080)))
    parent.close()
    for state in STATES:
        for size in ((1920, 1080), (820, 600)):
            window = Prototype(state, size)
            info = capture(window, out, f'{size[0]}x{size[1]}-{state}.png', size)
            info.update(state=state, apply_enabled=window.apply_button.isEnabled(),
                        status=window.status.text(), compatibility=window.compatibility.text())
            evidence.append(info)
            if state == 'edited' and size == (820, 600):
                window.tabs.setCurrentWidget(window.preview_panel)
                evidence.append(capture(window, out, '820x600-preview.png', size))
                window.tabs.setCurrentWidget(window.rules_panel)
                evidence.append(capture(window, out, '820x600-rules.png', size))
            window.close()
    window = Prototype('edited', target)
    evidence.append(capture(window, out, 'target-screen-edited.png', target))
    window.close()
    report = dict(schema_version=1, plan_spec=PLAN_SPEC, object_type='ProfileMockupEvidence',
        run_id='profile-mockup-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'),
        utc=datetime.now(timezone.utc).isoformat(),
        generator_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        approval_status='pending', code_commit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
        dirty=bool(subprocess.check_output(['git', 'status', '--porcelain'], text=True).strip()),
        environment=dict(platform=platform.platform(), python=platform.python_version(), pyside=PySide6.__version__,
            qt_platform=app.platformName(), screen_logical=[screen.size().width(), screen.size().height()],
            target_available=list(target), dpr=screen.devicePixelRatio(),
            effective_qt_scale_percent=screen.devicePixelRatio() * 100,
            system_windows_scale_percent=100,
            scale_basis='Native Qt platform at OS 100%; separate process QT_SCALE_FACTOR=1 or 1.25. OS settings unchanged.'),
        input=dict(source_kind='public-handcrafted-synthetic', seed=None,
            seed_reason='Static geometry UI; no random observation generation.', hashes=EXPECTED_HASHES,
            independent_edit=dict(marker='F1', before_xyz_mm=[21,12,40], after_xyz_mm=[22,12,40])),
        command=sys.argv, states=evidence, interaction=interaction_check(app),
        production_changed=False, native_status='not-executed', experimental_status='unavailable',
        limitations=['Compatibility messages are independent UI fixtures, not executed production policy.',
                    'Prototype QTest is not production persistence/worker or external native input acceptance.',
                    'No profile hash migration, numerical baseline or tolerance approval.'])
    (out / 'mockup-evidence.json').write_text(json.dumps(report, indent=2, allow_nan=False)+'\n', encoding='utf-8')
    print(json.dumps(dict(states=len(evidence), dpr=screen.devicePixelRatio(), output=str(out),
                         interaction=report['interaction']['status'])))


if __name__ == '__main__':
    main()
