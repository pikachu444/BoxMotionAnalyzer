"""Exploded faces: a display-only translation; canonical profiles stay intact."""
from __future__ import annotations

import copy
from datetime import datetime, timezone
import hashlib
from itertools import product
import json
from pathlib import Path
import subprocess

import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QComboBox, QLabel
from matplotlib.colors import to_rgba
from matplotlib.lines import Line2D
from mpl_toolkits.mplot3d import proj3d
from mpl_toolkits.mplot3d.art3d import Poly3DCollection

from generate_marker_id_options import MarkerIdPrototype
from generate_reviewed_mockups import settled, capture_reviewed, NORMALS
from generate_preview_options import COLORS, FACES
from generate_mockups import EXPECTED_HASHES, PLAN_SPEC
from src.simulation.marker_fixtures import load_profile, validate_profile


class ExplodedPrototype(MarkerIdPrototype):
    def __init__(self,example='32',size=(1280,960),camera='isometric',ratio=.75):
        self.display_mode='Exploded faces'; self.face_radius_ratio=ratio
        self.camera_preset=camera
        self.source_xyz=None; self.display_xyz=None
        self.triad_lines=[]; self.camera_states={}
        super().__init__(example,size,'All')
        bar=self.plot_splitter.widget(0).layout().itemAt(0).layout()
        bar.insertWidget(1,QLabel('View'))
        self.mode_combo=QComboBox(); self.mode_combo.addItems(['Box','Exploded faces'])
        self.mode_combo.setCurrentText(self.display_mode); bar.insertWidget(2,self.mode_combo)
        bar.insertWidget(3,QLabel('Display only'))
        self.mode_combo.currentTextChanged.connect(self.change_display_mode)
        self.plot_splitter.widget(0).layout().itemAt(0).layout().itemAt(0).widget().setText('3D')
        self.setWindowTitle('Marker profile #138 — PREAPPROVAL exploded faces (display only)')
        self.axes.view_init(35.264,45,0,vertical_axis='y') if camera=='isometric' else self.axes.view_init(20,30,0,vertical_axis='y')
        self.camera_states={'Box':(20,30,0,None),
            'Exploded faces':(self.axes.elev,self.axes.azim,self.axes.roll,None)}

    def change_display_mode(self,mode):
        self.camera_states[self.display_mode]=(self.axes.elev,self.axes.azim,self.axes.roll,self.zoom_3d)
        camera=self.camera_states[mode]
        self.display_mode=mode; self.zoom_3d=camera[3]
        self.axes.view_init(*camera[:3],vertical_axis='y'); self.draw()

    def render3(self,camera):
        self.triad_lines=[]
        self.source_xyz=np.asarray([m['xyz_mm'] for m in self.valid_preview['markers']],dtype=float)
        if self.display_mode=='Box':
            super().render3(camera); self.display_xyz=self.source_xyz.copy(); return
        self.selection_ring=None
        self.figure3.clear(); self.axes=self.figure3.add_axes((.01,.01,.98,.98),projection='3d')
        ax=self.axes; dims=np.asarray(self.valid_preview['box_dims_mm'],float)
        box=np.asarray(list(product((-1,1),repeat=3)))*dims/2
        for i,p in enumerate(box):
            for q in box[i+1:]:
                if np.count_nonzero(p!=q)==1: ax.plot(*np.stack((p,q)).T,color='#666666',linewidth=.8,alpha=.6)
        radius=max(dims)*self.face_radius_ratio
        self.face_offsets={}; self.face_vertices={}; displayed_corners=[box]
        for face in FACES:
            normal=np.asarray(NORMALS[face],float); axis=int(np.flatnonzero(normal)[0])
            offset=normal*(radius-dims[axis]/2); self.face_offsets[face]=offset
            center=normal*dims[axis]/2
            free=[i for i in range(3) if i!=axis]
            vertices=[]
            for a,b in ((-1,-1),(-1,1),(1,1),(1,-1)):
                point=center.copy(); point[free[0]]=a*dims[free[0]]/2; point[free[1]]=b*dims[free[1]]/2
                vertices.append(point+offset)
            vertices=np.asarray(vertices); displayed_corners.append(vertices)
            self.face_vertices[face]=vertices
            ax.add_collection3d(Poly3DCollection([vertices],facecolors=[to_rgba(COLORS[face],.045)],
                edgecolors=[to_rgba(COLORS[face],.75)],linewidths=.9))
            ax.plot(*np.stack((center,center+offset)).T,color=COLORS[face],linestyle='--',linewidth=.6,alpha=.55)
        self.display_xyz=np.asarray([p+self.face_offsets[m['face']] for p,m in zip(self.source_xyz,self.valid_preview['markers'])])
        self.xyz=self.display_xyz  # Compatibility alias for display picking/ID callout helper only.
        ax.scatter(*self.display_xyz.T,s=85,
            c=[to_rgba(COLORS[m['face']],.95 if m['face']==self.current_face else .65) for m in self.valid_preview['markers']],
            edgecolors='#333333',linewidths=.75,depthshade=False)
        self.corners=np.vstack(displayed_corners)
        self.ranges=np.max(np.abs(self.corners),axis=0)*2*1.06
        ax.view_init(*camera,vertical_axis='y'); ax.set_proj_type('ortho'); ax.grid(False)
        for setter,dimension in zip((ax.set_xlim,ax.set_ylim,ax.set_zlim),self.ranges): setter(-dimension/2,dimension/2)
        ax.set_box_aspect(self.ranges.copy(),zoom=self.zoom_3d or 1)
        for axis in (ax.xaxis,ax.yaxis,ax.zaxis): axis.pane.fill=False; axis.set_ticks([])
        ax.set_axis_off()
        self.canvas3.draw()
        if self.zoom_3d is None: self.fit3()
        else: self.selection_overlay()

    def fit3(self):
        if self.display_mode=='Box': return super().fit3()
        self.axes.set_box_aspect(self.ranges.copy(),zoom=1); self.canvas3.draw()
        box=self.bounds3(); fw,fh=self.figure3.bbox.width,self.figure3.bbox.height
        margin=16*self.canvas3.devicePixelRatioF()
        self.zoom_3d=.94*min((fw-2*margin)/box.width,(fh-2*margin)/box.height)
        for _ in range(30):
            self.axes.set_box_aspect(self.ranges.copy(),zoom=self.zoom_3d); self.selection_overlay()
            if self.fit_content_inside(): break
            self.zoom_3d*=.94
        assert self.fit_content_inside()

    def extra_label_obstacles(self):
        if self.display_mode=='Box': return []
        renderer=self.canvas3.get_renderer()
        return [text.get_bbox_patch().get_window_extent(renderer) if text.get_bbox_patch() else text.get_window_extent(renderer)
                for text in self.axes.texts[1:]]

    def draw_selected_overlay(self):
        if self.display_mode=='Box': return super().draw_selected_overlay()
        for line in self.triad_lines: line.remove()
        self.triad_lines=[]
        if self.selection_ring is not None: self.selection_ring.remove()
        for artist in list(self.axes.texts): artist.remove()
        x,y,_=proj3d.proj_transform(*self.display_xyz[self.selected_row],self.axes.get_proj())
        self.selection_ring=Line2D([x],[y],marker='o',markersize=17,markerfacecolor='none',
            markeredgecolor='#111111',markeredgewidth=2,linestyle='none',transform=self.axes.transData,zorder=100)
        self.axes.add_artist(self.selection_ring)
        marker=self.valid_preview['markers'][self.selected_row]
        self.axes.annotate(marker['id'],(x,y),xytext=(15,15),textcoords='offset points',
            fontsize=12,fontweight='bold',bbox=dict(boxstyle='round,pad=.2',fc='white',ec='#444444'),
            arrowprops=dict(arrowstyle='-',color='#444444'),zorder=101)
        dpr=self.canvas3.devicePixelRatioF(); fw,fh=self.figure3.bbox.width,self.figure3.bbox.height
        for face,vertices in self.face_vertices.items():
            xy=np.asarray([proj3d.proj_transform(*p,self.axes.get_proj())[:2] for p in vertices])
            pixels=self.axes.transData.transform(xy)
            title=face.title()+f' ({sum(m["face"]==face for m in self.valid_preview["markers"])})'
            px=float(np.mean(pixels[:,0])); py=float(np.max(pixels[:,1])+12*dpr)
            px=max(55*dpr,min(fw-55*dpr,px)); py=max(12*dpr,min(fh-12*dpr,py))
            self.axes.annotate(title,(px,py),xycoords='figure pixels',ha='center',va='center',
                fontsize=9,color=COLORS[face],fontweight='bold',
                bbox=dict(boxstyle='round,pad=.15',fc='white',ec='none',alpha=.94),zorder=103)
        length=max(self.valid_preview['box_dims_mm'])*.12
        for axis,color in enumerate(('#b33','#386b36','#376fa8')):
            endpoint=np.zeros(3); endpoint[axis]=length
            origin=proj3d.proj_transform(0,0,0,self.axes.get_proj())[:2]
            end=proj3d.proj_transform(*endpoint,self.axes.get_proj())[:2]
            self.axes.annotate('XYZ'[axis],end,xycoords=self.axes.transData,
                xytext=(4,4),textcoords='offset points',fontsize=9,color=color,zorder=104)
            line=Line2D([origin[0],end[0]],[origin[1],end[1]],
                color=color,linewidth=1,transform=self.axes.transData,zorder=99)
            self.axes.add_artist(line); self.triad_lines.append(line)
        self.canvas3.draw()


def check_exploded(app):
    window=ExplodedPrototype('18',(1280,960)); settled(window,app,(1280,960))
    original=copy.deepcopy(window.valid_preview)
    window.table.selectRow(17)
    assert window.selected_id=='M2' and 'Normal: (0, -1, 0)' in window.selected_readout.text()
    assert '(38, -60, -18) mm' in window.selected_readout.text()
    assert np.array_equal(window.source_xyz[17],[38,-60,-18])
    assert np.array_equal(window.display_xyz[17],[38,-150,-18])
    for mode in ('Box','Exploded faces'):
        window.mode_combo.setCurrentText(mode); app.processEvents()
        assert window.valid_preview==original
        assert window.selected_id=='M2'
        assert '(38, -60, -18) mm' in window.selected_readout.text()
    window.mode_combo.setCurrentText('Box'); window.axes.view_init(25,40,0,vertical_axis='y')
    window.mode_combo.setCurrentText('Exploded faces')
    assert (window.axes.elev,window.axes.azim)==(35.264,45)
    window.mode_combo.setCurrentText('Box'); assert (window.axes.elev,window.axes.azim)==(25,40)
    window.mode_combo.setCurrentText('Exploded faces'); assert window.valid_preview==original
    window.selection_overlay(); window.selection_overlay(); assert len(window.triad_lines)==3
    row,annotation=next((r,a) for r,a in window.id_annotations if window.valid_preview['markers'][r]['id']=='F1')
    box=annotation.get_bbox_patch().get_window_extent(window.canvas3.get_renderer())
    p=window.canvas3.rect().topLeft(); dpr=window.canvas3.devicePixelRatioF()
    p.setX(round((box.x0+box.x1)/2/dpr)); p.setY(window.canvas3.height()-round((box.y0+box.y1)/2/dpr))
    QTest.mouseClick(window.canvas3,Qt.LeftButton,pos=p)
    assert window.selected_id=='F1' and window.table.currentRow()==row
    assert window.valid_preview==original
    window.close()
    return dict(status='pass',kind='prototype-QTest',independent_expected='M2 source[38,-60,-18], display[38,-150,-18]; modes leave profile exact; original readout/normal; F1 label click resolves source row')


def main():
    import argparse,sys
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=Path(__file__).resolve().parent/'exploded')
    args=parser.parse_args(); args.output.mkdir(parents=True,exist_ok=True)
    app=QApplication.instance() or QApplication([]); states=[]
    for example in ('18','32'):
        assert validate_profile(load_profile(example=example))==EXPECTED_HASHES[example]
        for camera in ('isometric','original'):
            for size in ((1280,960),(1920,1080)):
                window=ExplodedPrototype(example,size,camera); settled(window,app,size)
                window.plot_splitter.setSizes([550,450]); app.processEvents(); window.zoom_3d=None; window.draw(); app.processEvents()
                entry=capture_reviewed(window,args.output,f'{example}-{camera}-{size[0]}x{size[1]}.png',size)
                entry.update(camera=[window.axes.elev,window.axes.azim],radius_ratio=.75,labels=window.label_metrics,
                    source_hash=EXPECTED_HASHES[example],display_offsets={f:o.tolist() for f,o in window.face_offsets.items()})
                assert window.valid_preview['markers']==load_profile(example=example)['markers']
                states.append(entry); window.close()
    report=dict(schema_version=1,plan_spec=PLAN_SPEC,object_type='ExplodedFaceMockupEvidence',
        utc=datetime.now(timezone.utc).isoformat(),command=sys.argv,
        commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
        dirty=bool(subprocess.check_output(['git','status','--porcelain'],text=True).strip()),
        source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        input=dict(kind='public-synthetic-static-geometry',profile_hashes=EXPECTED_HASHES,seed=None,
            seed_reason='Static geometry',tolerance=None,tolerance_reason='Exact source equality; display offset is not a physical tolerance'),
        environment=dict(qt_platform=app.platformName(),dpr=app.primaryScreen().devicePixelRatio(),windows_scale_percent=100,
            qt_process_scale_percent=app.primaryScreen().devicePixelRatio()*100),
        states=states,interaction=check_exploded(app),production_changed=False,user_approval='pending',
        native_status='not-executed-existing-activation-capture-failure',independent_review='not-approved-new-view',
        limitations=['ID bbox checks do not certify leader-line legibility.',
            'Display XYZ is not source XYZ; no analysis/export/persistence implementation changed.',
            'Small-window exploded render is not yet checked.'])
    (args.output/'evidence.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    print(json.dumps(dict(states=len(states),dpr=app.primaryScreen().devicePixelRatio(),interaction=report['interaction'])))


if __name__=='__main__': main()
