"""Two preapproval visibility alternatives. Never modify production widgets."""
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

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))

import numpy as np
import PySide6
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QComboBox, QHBoxLayout, QLabel, QPushButton
from matplotlib.lines import Line2D
from matplotlib.patches import Rectangle
from mpl_toolkits.mplot3d import proj3d

from generate_mockups import Prototype, capture, EXPECTED_HASHES, PLAN_SPEC
from src.simulation.marker_fixtures import load_profile, validate_profile

FACES = ('FRONT', 'BACK', 'RIGHT', 'LEFT', 'TOP', 'BOTTOM')
COLORS = dict(zip(FACES, ('#0072B2', '#D55E00', '#009E73', '#CC79A7', '#6C51A3', '#8C564B')))
# These are face-local coordinate plots, not mirrored outside-camera images.
PLANE_AXES = {'FRONT': (0, 1), 'BACK': (0, 1), 'RIGHT': (2, 1),
              'LEFT': (2, 1), 'TOP': (0, 2), 'BOTTOM': (0, 2)}


class VisibilityPrototype(Prototype):
    def __init__(self, variant, example, size, mode='3D overview', selected='B1', state='copy'):
        self.variant = variant
        self.ready = False
        self.example = example
        self.selected_id = selected
        self.labels = []
        self.label_bounds = []
        super().__init__('example32' if example == '32' else state, size)
        self.setWindowTitle(f'Marker profile #138 — PREAPPROVAL OPTION {variant} — example {example}')
        controls = QHBoxLayout()
        controls.addWidget(QLabel('View' if variant == 'A' else 'Face'))
        self.view_combo = QComboBox()
        if variant == 'A':
            self.view_combo.addItem('3D overview')
        self.view_combo.addItems([f.title() + ' face' for f in FACES])
        controls.addWidget(self.view_combo)
        self.reset_view = QPushButton('Reset view')
        controls.addWidget(self.reset_view)
        controls.addStretch()
        self.preview_panel.layout().insertLayout(1, controls)
        self.selected_readout = QLabel()
        self.selected_readout.setWordWrap(True)
        self.preview_panel.layout().insertWidget(2, self.selected_readout)
        self.face_legend = QLabel()
        self.face_legend.setWordWrap(True)
        self.preview_panel.layout().insertWidget(3, self.face_legend)
        self.view_combo.setCurrentText(mode if mode != '3D overview' or variant == 'A' else 'Back face')
        self.view_combo.currentTextChanged.connect(self.draw)
        self.table.itemSelectionChanged.connect(self.select_row)
        self.reset_view.clicked.connect(self.restore_view)
        self.canvas.mpl_connect('button_release_event', self.refresh_selection_overlay)
        self.ready = True
        self.figure.clear()
        if variant == 'B':
            self.axes = self.figure.add_subplot(121, projection='3d')
            self.face_axes = self.figure.add_subplot(122)
        else:
            self.axes = None
            self.face_axes = None
        self.draw()
        row = next(i for i, marker in enumerate(self.valid_preview['markers']) if marker['id'] == selected)
        self.table.selectRow(row)
        self.tabs.setCurrentWidget(self.preview_panel)

    def draw(self, *_args):
        if not self.ready:
            return super().draw()
        mode = self.view_combo.currentText()
        face = mode.split()[0].upper() if mode != '3D overview' else None
        previous_camera = None
        if self.axes is not None and hasattr(self.axes, 'elev'):
            previous_camera = (self.axes.elev, self.axes.azim, self.axes.roll)
        self.figure.clear()
        self.selection_overlay = None
        self.selection_annotation = None
        self.labels = []
        self.label_bounds = []
        if self.variant == 'B':
            self.axes = self.figure.add_subplot(121, projection='3d')
            self.face_axes = self.figure.add_subplot(122)
        elif face is None:
            self.axes = self.figure.add_subplot(111, projection='3d')
            self.face_axes = None
        else:
            self.axes = None
            self.face_axes = self.figure.add_subplot(111)
        if self.axes is not None:
            self.draw_overview(previous_camera)
        if self.face_axes is not None:
            self.draw_face(face)
        marker = next((m for m in self.valid_preview['markers'] if m['id'] == self.selected_id), None)
        self.selected_readout.setText('Selected: ' + marker['id'] + '  ' + marker['face'].title() +
            '  (' + ', '.join(f'{v:g}' for v in marker['xyz_mm']) + ') mm' if marker else 'No marker selected')
        self.face_legend.setText('   '.join(f'{f.title()} {sum(m["face"] == f for m in self.valid_preview["markers"])}'
                                          for f in FACES) if self.axes is not None else '')
        self.canvas.draw()
        self.place_face_labels()
        self.refresh_selection_overlay()
        self.canvas.draw()

    def draw_overview(self, previous_camera):
        from itertools import product
        ax = self.axes
        dims = np.asarray(self.valid_preview['box_dims_mm'], float)
        corners = np.asarray(list(product((-1, 1), repeat=3))) * dims / 2
        for i, p in enumerate(corners):
            for q in corners[i+1:]:
                if np.count_nonzero(p != q) == 1:
                    ax.plot(*np.stack((p, q)).T, color='#909090', alpha=.35, linewidth=.9)
        markers = self.valid_preview['markers']
        xyz = np.asarray([m['xyz_mm'] for m in markers])
        ax.scatter(*xyz.T, c=[COLORS[m['face']] for m in markers], s=85,
                   edgecolors='#262626', linewidths=.9, depthshade=False)
        for axis in (ax.xaxis, ax.yaxis, ax.zaxis):
            axis.pane.fill = False
        ax.grid(False)
        ax.set_proj_type('ortho')
        ax.set_box_aspect(dims)
        ax.view_init(*(previous_camera or (20, 30, 0)), vertical_axis='y')
        ax.set(xlabel='Local X (mm)', ylabel='Local Y (mm)', zlabel='Local Z (mm)')
        ax.set_title('3D overview', fontsize=11)
        ax.tick_params(labelsize=9)

    def draw_face(self, face):
        ax = self.face_axes
        self.current_face = face
        a, b = PLANE_AXES[face]
        dims = np.asarray(self.valid_preview['box_dims_mm'], float)
        markers = [m for m in self.valid_preview['markers'] if m['face'] == face]
        self.face_markers = markers
        self.face_points = np.asarray([[m['xyz_mm'][a], m['xyz_mm'][b]] for m in markers])
        ax.add_patch(Rectangle((-dims[a]/2, -dims[b]/2), dims[a], dims[b],
                              fill=False, edgecolor='#999999', linewidth=1))
        if markers:
            ax.scatter(*self.face_points.T, s=85, c=COLORS[face], edgecolors='#262626', linewidths=.9)
        chosen = next((m for m in markers if m['id'] == self.selected_id), None)
        if chosen:
            ax.scatter([chosen['xyz_mm'][a]], [chosen['xyz_mm'][b]], s=240,
                       facecolors='none', edgecolors='#111111', linewidths=2.2, zorder=5)
        ax.set(xlim=(-dims[a]*.60, dims[a]*.60), ylim=(-dims[b]*.60, dims[b]*.60),
               xlabel=f'Local {"XYZ"[a]} (mm)', ylabel=f'Local {"XYZ"[b]} (mm)')
        ax.set_aspect('equal', adjustable='box')
        ax.grid(True, alpha=.12)
        ax.tick_params(labelsize=9)
        ax.set_title(face.title() + f' face ({len(markers)})', fontsize=11)

    def place_face_labels(self):
        if self.face_axes is None:
            return
        ax = self.face_axes
        renderer = self.canvas.get_renderer()
        offsets = ((8,8), (8,-15), (-8,8), (-8,-15), (0,22), (0,-28), (25,0), (-25,0), (0,36), (0,-42))
        ids = list(range(len(self.face_markers)))
        ids.sort(key=lambda i: self.face_markers[i]['id'] != self.selected_id)
        occupied = []
        point_pixels = ax.transData.transform(self.face_points) if len(self.face_points) else np.empty((0,2))
        for i in ids:
            marker = self.face_markers[i]
            best = None
            for dx, dy in offsets:
                label = ax.annotate(marker['id'], xy=self.face_points[i], xytext=(dx,dy),
                    textcoords='offset points', ha='right' if dx < 0 else 'left' if dx > 0 else 'center',
                    va='bottom' if dy >= 0 else 'top', fontsize=11,
                    fontweight='bold' if marker['id'] == self.selected_id else 'normal',
                    bbox=dict(boxstyle='round,pad=.15', fc='white', ec='none', alpha=.94),
                    arrowprops=dict(arrowstyle='-', color='#666666', linewidth=.65), zorder=8)
                box = label.get_bbox_patch()
                label.update_positions(renderer)
                label.update_bbox_position_size(renderer)
                bounds = box.get_window_extent(renderer).expanded(1.05, 1.1)
                score = 1000 * sum(bounds.overlaps(old) for old in occupied)
                score += 100 * sum(bounds.contains(*p) for j,p in enumerate(point_pixels) if j != i)
                score += 1000 if not (ax.bbox.contains(bounds.x0,bounds.y0) and ax.bbox.contains(bounds.x1,bounds.y1)) else 0
                if best is None or score < best[0]:
                    if best is not None:
                        best[1].remove()
                    best = (score, label, bounds)
                else:
                    label.remove()
                if score == 0:
                    break
            self.labels.append(best[1]); occupied.append(best[2])
        self.label_bounds = occupied

    def refresh_selection_overlay(self, *_args):
        if not self.ready or self.axes is None:
            return
        for artist in (self.selection_overlay, self.selection_annotation):
            if artist is not None:
                artist.remove()
        marker = next((m for m in self.valid_preview['markers'] if m['id'] == self.selected_id), None)
        if marker:
            x,y,_z = proj3d.proj_transform(*marker['xyz_mm'], self.axes.get_proj())
            self.selection_overlay = Line2D([x], [y], marker='o', markersize=17,
                markerfacecolor='none', markeredgecolor='#111111', markeredgewidth=2,
                linestyle='none', transform=self.axes.transData, zorder=100)
            self.axes.add_artist(self.selection_overlay)
            self.selection_annotation = self.axes.annotate(marker['id'], (x,y), xytext=(16,16),
                textcoords='offset points', fontsize=12, fontweight='bold',
                bbox=dict(boxstyle='round,pad=.25', fc='white', ec='#333333'),
                arrowprops=dict(arrowstyle='-', color='#333333'), zorder=101)
            self.canvas.draw_idle()

    def select_row(self):
        if not self.ready or self.table.currentRow() < 0:
            return
        self.selected_id = self.table.item(self.table.currentRow(),0).text()
        if self.variant == 'B':
            marker = next((m for m in self.valid_preview['markers'] if m['id'] == self.selected_id), None)
            if marker:
                self.view_combo.blockSignals(True)
                self.view_combo.setCurrentText(marker['face'].title() + ' face')
                self.view_combo.blockSignals(False)
        self.draw()

    def restore_view(self):
        if self.axes is not None:
            self.axes.view_init(20,30,0,vertical_axis='y')
        self.draw()


def check_interaction(app):
    results = []
    for variant in ('A','B'):
        window = VisibilityPrototype(variant, '18', (1100,700), selected='B1')
        window.show(); app.processEvents()
        before = copy.deepcopy(window.applied)
        window.table.selectRow(17)  # Independent literal: M2=[38,-60,-18], BOTTOM.
        assert window.selected_id == 'M2'
        assert '38, -60, -18' in window.selected_readout.text()
        if variant == 'B':
            assert window.current_face == 'BOTTOM'
        window.table.item(0,2).setText('22')
        QTest.mouseClick(window.preview_button,Qt.LeftButton)
        assert window.valid_preview['markers'][0]['xyz_mm'] == [22.,12.,40.]
        assert window.applied == before
        QTest.mouseClick(window.reset_button,Qt.LeftButton)
        assert window.valid_preview['markers'][0]['xyz_mm'] == [21,12,40]
        window.table.item(0,2).setText('bad')
        assert not window.apply_button.isEnabled() and not window.preview_button.isEnabled()
        assert window.applied == before
        window.close()
        results.append(dict(variant=variant,status='pass',kind='prototype-QTest-only',
            oracle='M2=[38,-60,-18],BOTTOM; F1 edit 21->22; Preview preserves applied; Reset restores21'))
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=Path(__file__).resolve().parent / 'revised')
    parser.add_argument('--native', action='store_true')
    parser.add_argument('--variant', choices=('A','B'),default='A')
    parser.add_argument('--example', choices=('18','32'),default='32')
    parser.add_argument('--mode',default='Back face')
    parser.add_argument('--size',default='1100x700')
    args = parser.parse_args()
    app = QApplication.instance() or QApplication([])
    if args.native:
        window = VisibilityPrototype(args.variant,args.example,tuple(map(int,args.size.split('x'))),args.mode)
        window.show()
        return app.exec()
    out = args.output; out.mkdir(parents=True,exist_ok=True)
    screen = app.primaryScreen()
    entries = []
    for example in ('18','32'):
        assert validate_profile(load_profile(example=example)) == EXPECTED_HASHES[example]
        for variant in ('A','B'):
            modes = ('3D overview','Back face') if variant == 'A' else ('Back face',)
            for mode in modes:
                for size in ((1920,1080),(820,600)):
                    window = VisibilityPrototype(variant,example,size,mode)
                    filename=f'{variant}-{example}-{size[0]}x{size[1]}-{mode.split()[0].lower()}.png'
                    window.show(); app.processEvents(); window.resize(*size); app.processEvents()
                    window.draw(); app.processEvents()
                    entry=capture(window,out,filename,size)
                    collisions=int(sum(a.overlaps(b) for i,a in enumerate(window.label_bounds) for b in window.label_bounds[i+1:]))
                    entry.update(variant=variant,example=example,mode=mode,selected='B1',
                        face_labels=[t.get_text() for t in window.labels],label_box_collisions=collisions)
                    assert collisions == 0, entry
                    assert window.valid_preview['markers'] == load_profile(example=example)['markers']
                    entries.append(entry)
                    window.close()
    for variant in ('A','B'):
        window=VisibilityPrototype(variant,'18',(820,600),'Back face',state='invalid')
        entries.append(capture(window,out,f'{variant}-820x600-invalid.png',(820,600)))
        assert not window.apply_button.isEnabled()
        window.close()
    report=dict(schema_version=1,plan_spec=PLAN_SPEC,object_type='ProfilePreviewOptionsEvidence',
        run_id='preview-options-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'),
        utc=datetime.now(timezone.utc).isoformat(),approval_status='pending',
        commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
        dirty=bool(subprocess.check_output(['git','status','--porcelain'],text=True).strip()),
        source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),command=sys.argv,
        environment=dict(platform=platform.platform(),python=platform.python_version(),pyside=PySide6.__version__,
            qt_platform=app.platformName(),screen_logical=[screen.size().width(),screen.size().height()],
            dpr=screen.devicePixelRatio(),system_windows_scale_percent=100,qt_process_scale_percent=screen.devicePixelRatio()*100),
        input=dict(profile_hashes=EXPECTED_HASHES,source_kind='public-synthetic-static-geometry',
            seed=None,seed_reason='No random observation generation',
            selected_oracle=dict(B1=[17,-31,-40],M2=[38,-60,-18]),
            numeric_tolerance=None,tolerance_reason='Exact geometry invariance; label collisions are display diagnostics, not physics bounds'),
        states=entries,interaction=check_interaction(app),native_status='not-executed',
        production_changed=False,experimental_status='unavailable',
        limitations=['Selection rings are screen overlays, not evidence of physical visibility.',
            'Face views preserve increasing local axes and do not mirror a back-face camera view.',
            'No persistence/export/worker production verification; this is preapproval UI only.'],
        prior_attempts=[dict(status='failed',boundary='prototype-label-bounds-check',
            diagnostic='Initial annotation bbox measurement preceded patch-position update and incorrectly reported all three BACK labels colliding.',
            correction='Update annotation bbox position/size and measure after actual window layout; no geometry or expected marker coordinates changed.')])
    (out/'evidence.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    print(json.dumps(dict(states=len(entries),dpr=screen.devicePixelRatio(),interactions=report['interaction'])))


if __name__=='__main__':
    main()
