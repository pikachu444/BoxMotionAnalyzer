"""Preapproval layout: marker table left; overall 3D above face 2D on right."""
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

import numpy as np
import PySide6
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QFrame, QScrollArea
from matplotlib.ticker import MaxNLocator

from generate_preview_options import VisibilityPrototype, FACES
from generate_mockups import capture, EXPECTED_HASHES, PLAN_SPEC
from src.simulation.marker_fixtures import load_profile, validate_profile


class StackedPrototype(VisibilityPrototype):
    def __init__(self, example='32', size=(1920,1080), state='copy'):
        self.stacked_ready=False
        self.stack_drawn=False
        super().__init__('B',example,size,'Back face',state=state)
        self.setWindowTitle('Marker profile #138 — PREAPPROVAL stacked 3D / 2D')
        # Preserve legibility in the minimum window; scroll plots, not fixed actions.
        layout=self.preview_panel.layout()
        index=layout.indexOf(self.canvas)
        layout.removeWidget(self.canvas)
        self.plot_scroll=QScrollArea()
        self.plot_scroll.setFrameShape(QFrame.NoFrame)
        self.plot_scroll.setWidgetResizable(True)
        self.canvas.setMinimumHeight(500)
        self.plot_scroll.setWidget(self.canvas)
        layout.insertWidget(index,self.plot_scroll,1)
        self.stacked_ready=True
        self.draw()

    def draw(self,*_args):
        if not self.stacked_ready:
            return super().draw()
        camera=(self.axes.elev,self.axes.azim,self.axes.roll) if self.stack_drawn else (20,30,0)
        self.figure.clear()
        self.labels=[]; self.label_bounds=[]
        self.selection_overlay=self.selection_annotation=None
        grid=self.figure.add_gridspec(2,1,height_ratios=(1,1.05),hspace=.12)
        self.axes=self.figure.add_subplot(grid[0],projection='3d')
        self.face_axes=self.figure.add_subplot(grid[1])
        self.draw_overview(camera)
        # Y-up is set before aspect; equal mm scale follows the actual XYZ ranges.
        ranges=np.array([np.ptp(self.axes.get_xlim()),np.ptp(self.axes.get_ylim()),
                         np.ptp(self.axes.get_zlim())])
        self.axes.set_box_aspect(ranges)
        for axis in (self.axes.xaxis,self.axes.yaxis,self.axes.zaxis):
            axis.set_major_locator(MaxNLocator(3))
        self.axes.set_xlabel('X (mm)',fontsize=9,labelpad=0)
        self.axes.set_ylabel('Y (mm)',fontsize=9,labelpad=0)
        self.axes.set_zlabel('Z (mm)',fontsize=9,labelpad=0)
        self.axes.tick_params(labelsize=8)
        face=self.view_combo.currentText().split()[0].upper()
        self.draw_face(face)
        self.face_axes.set_title(face.title()+f' face / 2D ({len(self.face_markers)})',fontsize=11)
        marker=next((m for m in self.valid_preview['markers'] if m['id']==self.selected_id),None)
        self.selected_readout.setText('Selected: '+marker['id']+'  '+marker['face'].title()+'  ('+
            ', '.join(f'{v:g}' for v in marker['xyz_mm'])+') mm' if marker else 'No marker selected')
        self.face_legend.setText('   '.join(f'{f.title()} {sum(m["face"]==f for m in self.valid_preview["markers"])}'
                                          for f in FACES))
        self.canvas.draw()
        self.stack_drawn=True
        self.place_face_labels()
        self.refresh_selection_overlay()
        self.canvas.draw()


def interaction(app):
    window=StackedPrototype('18',(820,600))
    window.show(); app.processEvents(); window.draw(); app.processEvents()
    before=copy.deepcopy(window.applied)
    window.table.selectRow(17)
    assert window.selected_id=='M2' and window.current_face=='BOTTOM'
    assert window.selected_readout.text().endswith('(38, -60, -18) mm')
    assert hasattr(window.axes,'get_proj') and not hasattr(window.face_axes,'get_proj')
    assert window.axes.bbox.y0>window.face_axes.bbox.y1  # Actual top/bottom order.
    bar=window.plot_scroll.verticalScrollBar()
    assert bar.maximum()>0
    bar.setValue(bar.maximum()); app.processEvents()
    assert bar.value()==bar.maximum()
    window.table.item(0,2).setText('22')
    QTest.mouseClick(window.preview_button,Qt.LeftButton)
    assert window.valid_preview['markers'][0]['xyz_mm']==[22.,12.,40.]
    assert window.applied==before
    QTest.mouseClick(window.reset_button,Qt.LeftButton)
    assert window.valid_preview['markers'][0]['xyz_mm']==[21,12,40]
    window.table.item(0,2).setText('bad')
    assert not window.preview_button.isEnabled() and not window.apply_button.isEnabled()
    assert window.applied==before
    window.close()
    return dict(status='pass',kind='prototype-QTest-only',
        independent_expectations='3D axes above 2D axes; small-window scrollbar reaches bottom; M2=[38,-60,-18]/BOTTOM; F1 21->22; Preview preserves applied; Reset restores21; invalid blocks Apply')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=Path(__file__).resolve().parent/'stacked')
    args=parser.parse_args()
    app=QApplication.instance() or QApplication([])
    args.output.mkdir(parents=True,exist_ok=True)
    entries=[]
    for example in ('18','32'):
        assert validate_profile(load_profile(example=example))==EXPECTED_HASHES[example]
        for size in ((1920,1080),(820,600)):
            window=StackedPrototype(example,size)
            window.show(); app.processEvents(); window.resize(*size); app.processEvents()
            window.draw(); app.processEvents()
            collisions=int(sum(a.overlaps(b) for i,a in enumerate(window.label_bounds)
                               for b in window.label_bounds[i+1:]))
            assert collisions==0
            assert window.valid_preview['markers']==load_profile(example=example)['markers']
            positions=('both',) if size[0]>1000 else ('top','bottom')
            for position in positions:
                bar=window.plot_scroll.verticalScrollBar()
                bar.setValue(bar.maximum() if position=='bottom' else 0); app.processEvents()
                name=f'stacked-{example}-{size[0]}x{size[1]}-{position}.png'
                entry=capture(window,args.output,name,size)
                entry.update(example=example,face='BACK',selected='B1',scroll_position=position,
                    scroll_range=[0,bar.maximum()],label_box_collisions=collisions,
                    face_labels=[label.get_text() for label in window.labels])
                if position=='both':
                    assert bar.maximum()==0
                entries.append(entry)
            window.close()
    for state,size in (('invalid',(820,600)),('legacy',(1920,1080)),('incompatible',(1920,1080))):
        window=StackedPrototype('18',size,state)
        window.show(); app.processEvents(); window.resize(*size); app.processEvents()
        window.draw(); app.processEvents()
        if state=='invalid':
            bar=window.plot_scroll.verticalScrollBar(); bar.setValue(bar.maximum()); app.processEvents()
            assert not window.apply_button.isEnabled()
        entries.append(capture(window,args.output,f'stacked-{state}-{size[0]}x{size[1]}.png',size))
        window.close()
    screen=app.primaryScreen()
    script=Path(__file__)
    report=dict(schema_version=1,plan_spec=PLAN_SPEC,object_type='ProfileStackedMockupEvidence',
        utc=datetime.now(timezone.utc).isoformat(),run_id='stacked-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'),
        commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
        dirty=bool(subprocess.check_output(['git','status','--porcelain'],text=True).strip()),
        source_sha256=hashlib.sha256(script.read_bytes()).hexdigest(),command=sys.argv,
        dependency_sha256={name:hashlib.sha256((script.parent/name).read_bytes()).hexdigest()
                           for name in ('generate_preview_options.py','generate_mockups.py')},
        environment=dict(platform=platform.platform(),python=platform.python_version(),pyside=PySide6.__version__,
            qt_platform=app.platformName(),dpr=screen.devicePixelRatio(),windows_scale_percent=100,
            qt_process_scale_percent=screen.devicePixelRatio()*100),
        input=dict(profile_hashes=EXPECTED_HASHES,source_kind='public-synthetic-static-geometry',
            seed=None,seed_reason='Deterministic static geometry',numeric_tolerance=None,
            tolerance_reason='Exact geometry/hash invariance; display diagnostics, not pose accuracy'),
        states=entries,interaction=interaction(app),approval_status='pending',production_changed=False,
        native_status='not-executed-existing-capture-activation-failure',experimental_status='unavailable',
        limitations=['At 820x600 the preview scrolls vertically; fixed actions remain accessible.',
            'Compatibility/error states are UI fixtures, not implemented production checks.',
            'No production export/persistence/worker or physical validation acceptance.'],
        prior_attempts=[dict(status='render-revised',boundary='small-window-viewport',
            diagnostic='Initial 660px canvas clipped portions of each plot in the small viewport.',
            correction='Use a 500px minimum canvas and interplot spacing; keep scroll and fixed actions.')])
    (args.output/'evidence.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    print(json.dumps(dict(states=len(entries),dpr=screen.devicePixelRatio(),interaction=report['interaction'])))


if __name__=='__main__':
    main()
