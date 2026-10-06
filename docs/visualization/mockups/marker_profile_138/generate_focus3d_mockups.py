"""Preapproval revision: B's right pane is a face-focused 3D box."""
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
from PySide6.QtWidgets import QApplication, QComboBox, QLabel
from matplotlib.lines import Line2D
from matplotlib.ticker import MaxNLocator
from mpl_toolkits.mplot3d import proj3d
from mpl_toolkits.mplot3d.art3d import Poly3DCollection

from generate_preview_options import VisibilityPrototype, COLORS, PLANE_AXES
from generate_mockups import capture, EXPECTED_HASHES, PLAN_SPEC
from src.simulation.marker_fixtures import load_profile, validate_profile

# With vertical_axis='y', the eye vector is (cos(e)*sin(a),sin(e),cos(e)*cos(a)).
FACE_CAMERAS = {'FRONT': (0,0), 'BACK': (0,180), 'RIGHT': (0,90),
                'LEFT': (0,-90), 'TOP': (90,0), 'BOTTOM': (-90,0)}
NORMALS = {'FRONT': (0,0,1), 'BACK': (0,0,-1), 'RIGHT': (1,0,0),
           'LEFT': (-1,0,0), 'TOP': (0,1,0), 'BOTTOM': (0,-1,0)}


class Focus3DPrototype(VisibilityPrototype):
    def __init__(self, example='32', size=(1920,1080), camera='3D angle', state='copy'):
        self.focus_ready = False
        self.focus_artists = []
        super().__init__('B', example, size, 'Back face', state=state)
        self.setWindowTitle('Marker profile #138 — PREAPPROVAL B / face-focused 3D')
        controls = self.preview_panel.layout().itemAt(1).layout()
        controls.insertWidget(2, QLabel('Camera'))
        self.camera_combo = QComboBox()
        self.camera_combo.addItems(['3D angle', 'Face aligned'])
        self.camera_combo.setCurrentText(camera)
        controls.insertWidget(3, self.camera_combo)
        self.camera_combo.currentTextChanged.connect(self.draw)
        self.focus_ready = True
        self.draw()

    def draw(self, *_args):
        if not self.focus_ready:
            return super().draw()
        self.figure.clear()
        self.focus_artists = []
        self.labels = []
        self.label_bounds = []
        self.selection_overlay = self.selection_annotation = None
        grid = self.figure.add_gridspec(1,2,width_ratios=(1,2.2))
        self.axes = self.figure.add_subplot(grid[0],projection='3d')
        self.face_axes = self.figure.add_subplot(grid[1],projection='3d',computed_zorder=False)
        self.draw_overview(None)
        # Apply aspect after view_init establishes Y as vertical; the order matters.
        self.axes.set_box_aspect(np.asarray(self.valid_preview['box_dims_mm'],float))
        self.axes.set_title('Whole profile',fontsize=10)
        self.axes.set_axis_off()
        face = self.view_combo.currentText().split()[0].upper()
        self.draw_focus(face)
        marker = next((m for m in self.valid_preview['markers'] if m['id']==self.selected_id),None)
        self.selected_readout.setText('Selected: '+marker['id']+'  '+marker['face'].title()+'  ('+
            ', '.join(f'{v:g}' for v in marker['xyz_mm'])+') mm' if marker else 'No marker selected')
        self.face_legend.setText('Colored: selected face    Gray: other faces    Arrow: outward normal')
        self.canvas.draw()
        self.refresh_selection_overlay()
        self.canvas.draw()

    def draw_focus(self, face):
        self.current_face = face
        ax = self.face_axes
        dims = np.asarray(self.valid_preview['box_dims_mm'],float)
        normal = np.asarray(NORMALS[face],float)
        self.focus_normal = normal
        corners = np.asarray(list(product((-1,1),repeat=3)))*dims/2
        for i,p in enumerate(corners):
            for q in corners[i+1:]:
                if np.count_nonzero(p!=q)==1:
                    ax.plot(*np.stack((p,q)).T,color='#b6b6b6',linewidth=.85,zorder=1)
        a,b = PLANE_AXES[face]
        c = next(i for i in range(3) if i not in (a,b))
        plane = np.zeros((4,3)); plane[:,c]=normal[c]*dims[c]/2
        plane[:,a]=np.asarray([-1,1,1,-1])*dims[a]/2
        plane[:,b]=np.asarray([-1,-1,1,1])*dims[b]/2
        ax.add_collection3d(Poly3DCollection([plane],facecolors=COLORS[face],alpha=.10,
                           edgecolors=COLORS[face],linewidths=1.3,zorder=2))
        context = [m for m in self.valid_preview['markers'] if m['face']!=face]
        if context:
            xyz = np.asarray([m['xyz_mm'] for m in context],float)
            ax.scatter(*xyz.T,s=35,facecolors='#c7c7c7',edgecolors='#a5a5a5',
                       linewidths=.6,alpha=.40,depthshade=False,zorder=3)
        self.face_markers = [m for m in self.valid_preview['markers'] if m['face']==face]
        self.focus_xyz = np.asarray([m['xyz_mm'] for m in self.face_markers],float).reshape(-1,3)
        center = normal*dims/2
        ax.quiver(*center,*normal,length=min(dims)*.4,color=COLORS[face],
                  linewidth=1.6,arrow_length_ratio=.22,zorder=4)
        for axis in (ax.xaxis,ax.yaxis,ax.zaxis):
            axis.pane.fill=False
        ax.grid(False); ax.set_proj_type('ortho')
        ax.set_xlim(-dims[0]*.65,dims[0]*.65)
        ax.set_ylim(-dims[1]*.65,dims[1]*.65)
        ax.set_zlim(-dims[2]*.80,dims[2]*.80)
        elev,azim = FACE_CAMERAS[face]
        if self.camera_combo.currentText()=='3D angle':
            elev = elev+12 if abs(elev)<90 else (65 if elev>0 else -65)
            azim -= 22
        ax.view_init(elev,azim,vertical_axis='y')
        # Match actual axis ranges so a mm has the same display scale on all axes.
        ax.set_box_aspect(dims*np.array([1.3,1.3,1.6]),zoom=1.05)
        for axis in (ax.xaxis,ax.yaxis,ax.zaxis):
            axis.set_major_locator(MaxNLocator(3))
        ax.set_xlabel('X (mm)',fontsize=9,labelpad=1)
        ax.set_ylabel('Y (mm)',fontsize=9,labelpad=1)
        ax.set_zlabel('Z (mm)',fontsize=9,labelpad=1)
        ax.tick_params(labelsize=8)
        ax.set_title(face.title()+f' face in 3D ({len(self.face_markers)})',fontsize=11)
        if self.camera_combo.currentText()=='Face aligned':
            # The depth axis collapses to one screen point in a normal view.
            # State its actual plane coordinate instead of overlapping its ticks.
            depth_axis=(ax.xaxis,ax.yaxis,ax.zaxis)[c]
            depth_axis.set_ticks([])
            depth_axis.label.set_visible(False)
            depth_axis.line.set_visible(False)
            ax.set_title(face.title()+f' face in 3D / {"XYZ"[c]}={center[c]:g} mm ({len(self.face_markers)})',fontsize=11)

    def refresh_selection_overlay(self,*_args):
        super().refresh_selection_overlay()
        if not self.focus_ready:
            return
        for artist in self.focus_artists+self.labels:
            artist.remove()
        self.focus_artists=[]; self.labels=[]; self.label_bounds=[]
        ax=self.face_axes
        self.face_points = np.asarray([proj3d.proj_transform(*p,ax.get_proj())[:2]
                                      for p in self.focus_xyz]).reshape(-1,2)
        # Screen overlays keep selected-face points readable. They do not assert occlusion.
        for marker,p in zip(self.face_markers,self.face_points):
            dot=Line2D([p[0]],[p[1]],marker='o',markersize=10,
                markerfacecolor=COLORS[self.current_face],markeredgecolor='#222222',
                markeredgewidth=1,linestyle='none',transform=ax.transData,zorder=100)
            ax.add_artist(dot); self.focus_artists.append(dot)
            if marker['id']==self.selected_id:
                ring=Line2D([p[0]],[p[1]],marker='o',markersize=18,
                    markerfacecolor='none',markeredgecolor='#111111',markeredgewidth=2,
                    linestyle='none',transform=ax.transData,zorder=101)
                ax.add_artist(ring); self.focus_artists.append(ring)
        self.place_face_labels()
        for label in self.labels:
            label.set_zorder(102)
        self.canvas.draw_idle()


def interaction(app):
    window=Focus3DPrototype('18',(1100,700))
    window.show(); app.processEvents()
    applied=copy.deepcopy(window.applied)
    window.table.selectRow(17)
    assert window.selected_id=='M2' and window.current_face=='BOTTOM'
    assert window.selected_readout.text().endswith('(38, -60, -18) mm')
    assert tuple(window.focus_normal)==(0,-1,0)
    for face,normal in NORMALS.items():
        window.view_combo.setCurrentText(face.title()+' face')
        assert tuple(window.focus_normal)==normal
        assert hasattr(window.face_axes,'get_proj')
        ax=window.face_axes
        ranges=np.array([np.ptp(ax.get_xlim()),np.ptp(ax.get_ylim()),np.ptp(ax.get_zlim())])
        scales=ax._roll_to_vertical(ax.get_box_aspect())/ranges
        assert np.allclose(scales/scales[0],np.ones(3),rtol=1e-12,atol=0)
    window.table.item(0,2).setText('22')
    QTest.mouseClick(window.preview_button,Qt.LeftButton)
    assert window.valid_preview['markers'][0]['xyz_mm']==[22.,12.,40.]
    assert window.applied==applied
    QTest.mouseClick(window.reset_button,Qt.LeftButton)
    assert window.valid_preview['markers'][0]['xyz_mm']==[21,12,40]
    window.table.item(0,2).setText('bad')
    assert not window.preview_button.isEnabled() and not window.apply_button.isEnabled()
    assert window.applied==applied
    window.close()
    return dict(status='pass',kind='prototype-QTest-only',
        independent_expectations='M2=[38,-60,-18]/BOTTOM normal [0,-1,0]; six fixed face normals; equal XYZ display scale (relative arithmetic tolerance 1e-12); F1 21->22; Preview preserves applied; Reset restores21; invalid blocks Apply')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=Path(__file__).resolve().parent/'focus3d')
    args=parser.parse_args()
    app=QApplication.instance() or QApplication([])
    args.output.mkdir(parents=True,exist_ok=True)
    entries=[]
    for example in ('18','32'):
        assert validate_profile(load_profile(example=example))==EXPECTED_HASHES[example]
        for camera in ('3D angle','Face aligned'):
            for size in ((1920,1080),(820,600)):
                window=Focus3DPrototype(example,size,camera)
                window.show(); app.processEvents(); window.resize(*size); app.processEvents()
                window.draw(); app.processEvents()
                name=f'B3D-{example}-{size[0]}x{size[1]}-{camera.split()[0].lower()}.png'
                entry=capture(window,args.output,name,size)
                collisions=int(sum(a.overlaps(b) for i,a in enumerate(window.label_bounds)
                                   for b in window.label_bounds[i+1:]))
                entry.update(example=example,camera=camera,face='BACK',selected='B1',
                    face_labels=[label.get_text() for label in window.labels],
                    label_box_collisions=collisions,normal=[0,0,-1])
                assert collisions==0,entry
                assert window.valid_preview['markers']==load_profile(example=example)['markers']
                entries.append(entry); window.close()
    window=Focus3DPrototype('18',(820,600),state='invalid')
    entries.append(capture(window,args.output,'B3D-820x600-invalid.png',(820,600)))
    assert not window.apply_button.isEnabled(); window.close()
    screen=app.primaryScreen()
    report=dict(schema_version=1,plan_spec=PLAN_SPEC,object_type='ProfileFocus3DMockupEvidence',
        utc=datetime.now(timezone.utc).isoformat(),run_id='focus3d-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'),
        commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
        dirty=bool(subprocess.check_output(['git','status','--porcelain'],text=True).strip()),
        source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),command=sys.argv,
        environment=dict(platform=platform.platform(),python=platform.python_version(),pyside=PySide6.__version__,
            qt_platform=app.platformName(),dpr=screen.devicePixelRatio(),
            logical_screen=[screen.size().width(),screen.size().height()],windows_scale_percent=100,
            qt_process_scale_percent=screen.devicePixelRatio()*100),
        input=dict(profile_hashes=EXPECTED_HASHES,source_kind='public-synthetic-static-geometry',
            seed=None,seed_reason='Deterministic static geometry',numeric_tolerance=None,
            tolerance_reason='Exact geometry/hash invariance; display collision count, not pose accuracy'),
        states=entries,interaction=interaction(app),approval_status='pending',production_changed=False,
        native_status='not-executed-existing-capture-activation-failure',experimental_status='unavailable',
        limitations=['Face points/labels are screen overlays, not physical occlusion evidence.',
            'Outside face cameras can reverse a screen axis; all coordinates retain local XYZ.',
            'Prototype only: no production export, persistence or worker acceptance.'],
        prior_attempts=[dict(status='failed',boundary='small-window-label-overlap',actual=2,
            correction='Set box aspect after Y-up camera, match XYZ ranges; rerender without moving marker coordinates.')])
    (args.output/'evidence.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    print(json.dumps(dict(states=len(entries),dpr=screen.devicePixelRatio(),interaction=report['interaction'])))


if __name__=='__main__':
    main()
