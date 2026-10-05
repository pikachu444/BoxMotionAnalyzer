"""Preapproval compact upper-3D/lower-2D preview with useful face/meaning context."""
from __future__ import annotations

import argparse
import copy
from datetime import datetime, timezone
import hashlib
from itertools import product
import json
from pathlib import Path
import platform
import subprocess
import sys

import numpy as np
import PySide6
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QSplitter
from matplotlib.transforms import Bbox
from matplotlib.ticker import MaxNLocator
from mpl_toolkits.mplot3d import proj3d

from generate_stacked_mockups import StackedPrototype
from generate_preview_options import FACES, COLORS, PLANE_AXES
from generate_mockups import capture, EXPECTED_HASHES, PLAN_SPEC
from src.simulation.marker_fixtures import load_profile, validate_profile

NORMALS={'FRONT':(0,0,1),'BACK':(0,0,-1),'RIGHT':(1,0,0),
         'LEFT':(-1,0,0),'TOP':(0,1,0),'BOTTOM':(0,-1,0)}


class CompactPrototype(StackedPrototype):
    def __init__(self,example='32',size=(1920,1080),state='copy'):
        self.compact_ready=False
        self.compact_drawn=False
        super().__init__(example,size,state)
        self.setWindowTitle('Marker profile #138 — PREAPPROVAL compact 3D / 2D')
        splitters=self.findChildren(QSplitter)
        if splitters:
            splitters[0].setSizes([520,size[0]-540])
        self.figure.set_layout_engine(None)
        self.canvas.setMinimumHeight(520)
        self.face_legend.hide()  # Counts move beside their face diagrams.
        self.compact_ready=True
        self.draw()

    def draw(self,*_args):
        if not self.compact_ready:
            return super().draw()
        camera=(self.axes.elev,self.axes.azim,self.axes.roll) if self.compact_drawn else (12,18,0)
        self.figure.clear(); self.labels=[]; self.label_bounds=[]
        self.selection_overlay=self.selection_annotation=None
        # Keep main plots aligned; reserve the right strip for face/meaning context.
        self.top_rect=(.035,.545,.515,.425)
        self.axes=self.figure.add_axes(self.top_rect,projection='3d')
        narrow=self.canvas.width()<1000
        self.face_axes=self.figure.add_axes((.11 if narrow else .075,.075,.405 if narrow else .44,.40))
        self.draw_overview(camera)
        ranges=np.array([np.ptp(self.axes.get_xlim()),np.ptp(self.axes.get_ylim()),
                         np.ptp(self.axes.get_zlim())])
        self.axes.set_box_aspect(ranges)
        self.axes.set_title('')
        self.axes.set_xlabel('X (mm)',fontsize=9,labelpad=0)
        self.axes.set_ylabel('Y (mm)',fontsize=9,labelpad=0)
        self.axes.set_zlabel('Z (mm)',fontsize=9,labelpad=0)
        self.axes.tick_params(labelsize=8)
        for axis in (self.axes.xaxis,self.axes.yaxis,self.axes.zaxis):
            axis.set_major_locator(MaxNLocator(3))
        self.figure.text(.29,.99,'3D overview',ha='center',va='top',fontsize=11)
        face=self.view_combo.currentText().split()[0].upper()
        self.draw_face(face)
        self.face_axes.set_title(face.title()+f' face / 2D ({len(self.face_markers)})',fontsize=11,pad=8)
        self.draw_face_cards(face)
        marker=next((m for m in self.valid_preview['markers'] if m['id']==self.selected_id),None)
        self.selected_readout.setText('Selected: '+marker['id']+'  '+marker['face'].title()+'  ('+
            ', '.join(f'{v:g}' for v in marker['xyz_mm'])+') mm' if marker else 'No marker selected')
        self.draw_meanings(marker,face)
        self.canvas.draw()
        dims=np.asarray(self.valid_preview['box_dims_mm'],float)
        corners=np.asarray(list(product((-1,1),repeat=3)))*dims/2
        original=self.projected_bounds(corners)
        width,height=self.figure.bbox.width,self.figure.bbox.height
        x,y,w,h=self.top_rect
        target=Bbox.from_extents(x*width+25,y*height+45,(x+w)*width-25,(y+h)*height-18)
        zoom=.96*min(target.width/original.width,target.height/original.height)
        self.axes.set_box_aspect(ranges,zoom=zoom)
        # Projection can extend outside Axes3D's square, within the rectangular row.
        # Only screen clipping changes; XYZ and their common scale are preserved.
        for artist in self.axes.get_children():
            artist.set_clip_on(False)
        self.canvas.draw()
        fitted=self.projected_bounds(corners)
        dx=(target.x0+target.x1-fitted.x0-fitted.x1)/2/width
        dy=(target.y0+target.y1-fitted.y0-fitted.y1)/2/height
        position=self.axes.get_position()
        self.axes.set_position((position.x0+dx,position.y0+dy,position.width,position.height))
        self.canvas.draw()
        self.fit_bounds=self.projected_bounds(corners)
        self.fit_target=target
        self.fit_zoom=float(zoom)
        assert target.contains(self.fit_bounds.x0,self.fit_bounds.y0)
        assert target.contains(self.fit_bounds.x1,self.fit_bounds.y1)
        self.place_face_labels(); self.refresh_selection_overlay(); self.canvas.draw()
        self.stack_drawn=True
        self.compact_drawn=True

    def projected_bounds(self,xyz):
        projected=np.asarray([proj3d.proj_transform(*p,self.axes.get_proj())[:2] for p in xyz])
        pixels=self.axes.transData.transform(projected)
        return Bbox.from_extents(*pixels.min(axis=0),*pixels.max(axis=0))

    def draw_face_cards(self,selected_face):
        dims=np.asarray(self.valid_preview['box_dims_mm'],float)
        self.card_axes={}
        for i,face in enumerate(FACES):
            row,col=divmod(i,2)
            ax=self.figure.add_axes((.595+col*.20,.845-row*.145,.175,.11))
            a,b=PLANE_AXES[face]
            markers=[m for m in self.valid_preview['markers'] if m['face']==face]
            if markers:
                xy=np.asarray([[m['xyz_mm'][a],m['xyz_mm'][b]] for m in markers])
                ax.scatter(*xy.T,s=19,c=COLORS[face],edgecolors='#333333',linewidths=.45)
                for marker in markers:
                    if marker['id']==self.selected_id:
                        ax.scatter(marker['xyz_mm'][a],marker['xyz_mm'][b],s=75,
                                   facecolors='none',edgecolors='#111111',linewidths=1.2)
            ax.set(xlim=(-dims[a]/2,dims[a]/2),ylim=(-dims[b]/2,dims[b]/2))
            ax.set_aspect('equal',adjustable='box'); ax.set_xticks([]); ax.set_yticks([])
            ax.set_title(face.title()+f' {len(markers)}',fontsize=9,pad=4,
                         fontweight='bold' if face==selected_face else 'normal')
            for spine in ax.spines.values():
                spine.set_color(COLORS[face] if face==selected_face else '#bbbbbb')
                spine.set_linewidth(1.5 if face==selected_face else .6)
            self.card_axes[face]=ax

    def draw_meanings(self,marker,face):
        ax=self.figure.add_axes((.595,.075,.375,.40)); ax.set_axis_off()
        label=marker['id'] if marker else 'None'
        meaning_face=marker['face'] if marker else face
        normal=', '.join(str(v) for v in NORMALS[meaning_face])
        rows=[('Selected',label),('Face',meaning_face.title()),('Normal',f'({normal})'),
              ('Origin','Box center'),('Units','mm'),
              ('Local X','Right / Left'),('Local Y','Top / Bottom'),('Local Z','Front / Back'),
              ('World up','+Y'),('Half-turn X','Front/Back; Top/Bottom'),
              ('Half-turn Y','Front/Back; Left/Right'),('Half-turn Z','Left/Right; Top/Bottom'),
              ('Meaning','Current fixed rules')]
        for i,(name,value) in enumerate(rows):
            y=1-i*.077
            ax.text(0,y,name,fontsize=9,color='#555555',va='top')
            ax.text(.39,y,value,fontsize=9,va='top',fontweight='bold' if i<3 else 'normal')
        self.meaning_face=meaning_face
        self.meaning_normal=NORMALS[meaning_face]

    def restore_view(self):
        if self.axes is not None:
            self.axes.view_init(12,18,0,vertical_axis='y')
        self.draw()


def interaction(app):
    window=CompactPrototype('18',(1100,700))
    window.show(); app.processEvents(); window.draw(); app.processEvents()
    before=copy.deepcopy(window.applied)
    window.table.selectRow(17)
    assert window.selected_id=='M2' and window.current_face=='BOTTOM'
    assert window.meaning_normal==(0,-1,0)
    assert window.selected_readout.text().endswith('(38, -60, -18) mm')
    window.view_combo.setCurrentText('Front face')
    assert window.current_face=='FRONT' and window.meaning_face=='BOTTOM'
    assert window.meaning_normal==(0,-1,0)  # View selection cannot redefine M2.
    window.table.item(0,2).setText('22'); QTest.mouseClick(window.preview_button,Qt.LeftButton)
    assert window.valid_preview['markers'][0]['xyz_mm']==[22.,12.,40.]
    assert window.applied==before
    QTest.mouseClick(window.reset_button,Qt.LeftButton)
    assert window.valid_preview['markers'][0]['xyz_mm']==[21,12,40]
    window.table.item(0,2).setText('bad')
    assert not window.preview_button.isEnabled() and not window.apply_button.isEnabled()
    window.close()
    return dict(status='pass',kind='prototype-QTest-only',
        independent_expectations='M2=[38,-60,-18]/BOTTOM normal [0,-1,0] stays unchanged when viewing FRONT; F1 21->22; Preview retains applied; Reset restores21; invalid blocks Apply')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=Path(__file__).resolve().parent/'compact')
    args=parser.parse_args(); app=QApplication.instance() or QApplication([])
    args.output.mkdir(parents=True,exist_ok=True); entries=[]
    for example in ('18','32'):
        assert validate_profile(load_profile(example=example))==EXPECTED_HASHES[example]
        for size in ((1920,1080),(820,600)):
            window=CompactPrototype(example,size)
            window.show(); app.processEvents(); window.resize(*size); app.processEvents()
            window.draw(); app.processEvents()
            assert window.valid_preview['markers']==load_profile(example=example)['markers']
            positions=('both',) if size[0]>1000 else ('top','bottom')
            for position in positions:
                bar=window.plot_scroll.verticalScrollBar()
                bar.setValue(bar.maximum() if position=='bottom' else 0); app.processEvents()
                name=f'compact-{example}-{size[0]}x{size[1]}-{position}.png'
                entry=capture(window,args.output,name,size)
                collisions=int(sum(a.overlaps(b) for i,a in enumerate(window.label_bounds) for b in window.label_bounds[i+1:]))
                assert collisions==0
                entry.update(example=example,scroll_position=position,face='BACK',selected='B1',
                    label_box_collisions=collisions,fit_zoom=window.fit_zoom,
                    projected_box_size_pixels=[window.fit_bounds.width,window.fit_bounds.height],
                    fit_target_pixels=list(window.fit_target.bounds),normal=list(window.meaning_normal))
                entries.append(entry)
            window.close()
    window=CompactPrototype('18',(1920,1080),'legacy')
    window.show(); app.processEvents(); window.draw(); app.processEvents()
    entries.append(capture(window,args.output,'compact-legacy-1920x1080.png',(1920,1080)))
    window.close()
    screen=app.primaryScreen(); script=Path(__file__)
    report=dict(schema_version=1,plan_spec=PLAN_SPEC,object_type='ProfileCompactMockupEvidence',
        run_id='compact-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'),utc=datetime.now(timezone.utc).isoformat(),
        commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
        dirty=bool(subprocess.check_output(['git','status','--porcelain'],text=True).strip()),command=sys.argv,
        source_sha256=hashlib.sha256(script.read_bytes()).hexdigest(),
        environment=dict(platform=platform.platform(),python=platform.python_version(),pyside=PySide6.__version__,
            qt_platform=app.platformName(),dpr=screen.devicePixelRatio(),windows_scale_percent=100,
            qt_process_scale_percent=screen.devicePixelRatio()*100),
        input=dict(profile_hashes=EXPECTED_HASHES,kind='public-synthetic-static-geometry',seed=None,
            seed_reason='Static layout',numeric_tolerance=None,tolerance_reason='Exact geometry/hash invariance; display fit is not physical accuracy'),
        states=entries,interaction=interaction(app),approval_status='pending',production_changed=False,
        native_status='not-executed-existing-capture-activation-failure',experimental_status='unavailable',
        limitations=['Face cards and meaning inspector are mockup-only read-only fixture displays.',
            'The 3D fit changes display zoom/clipping only, not local coordinates or proportions.',
            'Small window scrolls; production persistence/export/worker/native acceptance remains pending.'],
        prior_attempts=[dict(status='failed',boundary='display-fit-bounds',
            diagnostic='Size-only fit did not center the projected box within its rectangular target.',
            correction='Center the projected box and retain a display margin; no geometry change.')])
    (args.output/'evidence.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    print(json.dumps(dict(states=len(entries),dpr=screen.devicePixelRatio(),interaction=report['interaction'])))


if __name__=='__main__':
    main()
