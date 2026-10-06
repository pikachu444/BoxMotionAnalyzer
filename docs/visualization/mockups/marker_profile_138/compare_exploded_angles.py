"""Joint angle/spacing diagnostics for the display-only #138 review prototype."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
from itertools import product
import json
from pathlib import Path
import subprocess
import sys

import numpy as np
from matplotlib.figure import Figure
from matplotlib.backends.backend_agg import FigureCanvasAgg
from mpl_toolkits.mplot3d import proj3d
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest

from generate_exploded_mockups import ExplodedPrototype
from generate_reviewed_mockups import settled, capture_reviewed, NORMALS
from generate_preview_options import FACES
from generate_mockups import EXPECTED_HASHES, PLAN_SPEC
from src.simulation.marker_fixtures import load_profile, validate_profile


class ConfiguredExploded(ExplodedPrototype):
    def __init__(self,example,size,camera,ratio):
        self.default_exploded_camera=tuple(camera)
        self.initial_configuring=True
        super().__init__(example,size,ratio=ratio)
        self.initial_configuring=False
        self.axes.view_init(*camera,vertical_axis='y')
        self.camera_states['Exploded faces']=(*camera,None)

    def render3(self,camera):
        if self.initial_configuring and self.display_mode=='Exploded faces': camera=self.default_exploded_camera
        super().render3(camera)

    def restore_view(self):
        camera=self.default_exploded_camera if self.display_mode=='Exploded faces' else (20,30,0)
        self.axes.view_init(*camera,vertical_axis='y'); self.fit3()


def polygon_area(vertices):
    if len(vertices)<3: return 0.0
    p=np.asarray(vertices)
    return float(abs(np.sum(p[:,0]*np.roll(p[:,1],-1)-p[:,1]*np.roll(p[:,0],-1)))/2)


def intersection_area(subject,clip):
    # Convex clipping; epsilon is arithmetic noise in pixel-space diagnostics.
    clip=np.asarray(clip)
    orientation=np.sign(np.sum(clip[:,0]*np.roll(clip[:,1],-1)-clip[:,1]*np.roll(clip[:,0],-1)))
    output=list(subject)
    def signed(p,a,b):
        v=b-a; w=p-a
        return orientation*(v[0]*w[1]-v[1]*w[0])
    for a,b in zip(clip,np.roll(clip,-1,axis=0)):
        incoming=output; output=[]
        if not incoming: break
        previous=incoming[-1]; pd=signed(previous,a,b)
        for current in incoming:
            cd=signed(current,a,b)
            if (cd>=-1e-9)!=(pd>=-1e-9):
                output.append(previous+(current-previous)*(pd/(pd-cd)))
            if cd>=-1e-9: output.append(current)
            previous=current; pd=cd
    return polygon_area(output)


def geometry(profile,ratio):
    dims=np.asarray(profile['box_dims_mm'],float); radius=max(dims)*ratio
    frames={}; offsets={}
    for face in FACES:
        normal=np.asarray(NORMALS[face],float); axis=int(np.flatnonzero(normal)[0])
        offset=normal*(radius-dims[axis]/2); offsets[face]=offset
        free=[i for i in range(3) if i!=axis]; vertices=[]
        for a,b in ((-1,-1),(-1,1),(1,1),(1,-1)):
            p=normal*dims[axis]/2
            p[free[0]]=a*dims[free[0]]/2; p[free[1]]=b*dims[free[1]]/2
            vertices.append(p+offset)
        frames[face]=np.asarray(vertices)
    points=np.asarray([np.asarray(m['xyz_mm'])+offsets[m['face']] for m in profile['markers']])
    center=np.asarray(list(product((-1,1),repeat=3)))*dims/2
    return frames,points,center


def project(ax,points):
    xy=np.asarray([proj3d.proj_transform(*p,ax.get_proj())[:2] for p in points])
    return ax.transData.transform(xy)


def measurements(profile,frames,points,center):
    faces=[m['face'] for m in profile['markers']]
    distances=np.linalg.norm(points[:,None]-points[None,:],axis=2)
    different=np.asarray(faces)[:,None]!=np.asarray(faces)[None,:]
    upper=np.triu(np.ones(distances.shape,dtype=bool),1)
    near_cross=np.argwhere(upper & different & (distances<14))
    near_same=np.argwhere(upper & ~different & (distances<14))
    overlap=sum(intersection_area(frames[a],frames[b]) for i,a in enumerate(FACES) for b in FACES[i+1:])
    area=sum(polygon_area(p) for p in frames.values())
    ids=[m['id'] for m in profile['markers']]
    return dict(cross_face_pairs_under_14px=int(len(near_cross)),
        same_face_pairs_under_14px=int(len(near_same)),
        cross_pairs=[[ids[a],ids[b]] for a,b in near_cross],
        face_overlap_percent=round(100*overlap/area,2),
        minimum_face_area_px2=round(min(polygon_area(p) for p in frames.values()),1),
        central_box_span_px=np.round(np.ptp(center,axis=0),1).tolist())


def scan(out):
    # Approximate actual default viewport. Final Qt captures remeasure actual Fit.
    figure=Figure(figsize=(6.8,3.55),dpi=100); canvas=FigureCanvasAgg(figure)
    ax=figure.add_axes((.01,.01,.98,.98),projection='3d'); ax.set_proj_type('ortho')
    ax.set_axis_off(); canvas.draw(); states=[]
    cameras=[(20,30,0)]+[(e,a,r) for e in (15,25,35,45,55) for a in (20,35,50,65,80) for r in (0,30,60)]
    for example in ('18','32'):
        profile=load_profile(example=example); assert validate_profile(profile)==EXPECTED_HASHES[example]
        for (elev,azim,roll),ratio in product(cameras,(.75,1.,1.25,1.5)):
            frames,points,center=geometry(profile,ratio)
            extent=np.vstack([center,*frames.values()]); ranges=np.max(np.abs(extent),axis=0)*2*1.06
            for setter,dimension in zip((ax.set_xlim,ax.set_ylim,ax.set_zlim),ranges): setter(-dimension/2,dimension/2)
            ax.view_init(elev,azim,roll,vertical_axis='y'); ax.set_box_aspect(ranges.copy(),zoom=1)
            box=project(ax,extent); span=np.ptp(box,axis=0)
            zoom=.94*min((figure.bbox.width-32)/span[0],(figure.bbox.height-32)/span[1])
            ax.set_box_aspect(ranges.copy(),zoom=zoom)
            values=measurements(profile,{f:project(ax,p) for f,p in frames.items()},project(ax,points),project(ax,center))
            states.append(dict(example=example,camera=[elev,azim,roll],radius_ratio=ratio,**values))
    report=base_report('ExplodedAngleSpacingScan')
    report.update(states=states,viewport_logical_px=[680,355],
        metric_contract='Diagnostic only: 14 logical px matches the existing point-obstacle diameter; not a physical tolerance or approval criterion.',
        limitations=['Geometry-only Agg Fit omits ID/title bounds; final Qt Fit can reduce scene further.',
            'Pairwise frame intersection sum is not union area or perceived readability.',
            'No labels, native input or production paths validated by this scan.'])
    (out/'scan.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    best=sorted((s for s in states if s['example']=='32'),key=lambda s:(s['cross_face_pairs_under_14px'],s['face_overlap_percent'],s['same_face_pairs_under_14px']))
    print(json.dumps(dict(states=len(states),best=best[:12])))


def base_report(kind):
    return dict(schema_version=1,plan_spec=PLAN_SPEC,object_type=kind,
        utc=datetime.now(timezone.utc).isoformat(),command=sys.argv,
        commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
        dirty=bool(subprocess.check_output(['git','status','--porcelain'],text=True).strip()),
        source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        dependency_sha256={name:hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest()
            for name in ('generate_exploded_mockups.py','generate_marker_id_options.py','generate_reviewed_mockups.py','generate_preview_options.py','generate_mockups.py')},
        input=dict(kind='public-synthetic-static-geometry',profile_hashes=EXPECTED_HASHES,
            seed=None,seed_reason='Deterministic static geometry',physical_tolerance=None,
            physical_tolerance_reason='Only display projection; source equality is exact'),
        production_changed=False,user_approval='pending',native_status='not-executed-existing-capture-activation-error')


def check_candidate(app):
    window=ConfiguredExploded('18',(1280,960),(25,50,30),1)
    settled(window,app,(1280,960)); source=load_profile(example='18')
    window.table.selectRow(17); app.processEvents()
    assert window.selected_id=='M2'
    assert np.array_equal(window.source_xyz[17],[38,-60,-18])
    assert np.array_equal(window.display_xyz[17],[38,-200,-18])
    assert '(38, -60, -18) mm' in window.selected_readout.text()
    window.axes.view_init(10,15,5,vertical_axis='y')
    QTest.mouseClick(window.reset_view,Qt.LeftButton)
    assert (window.axes.elev,window.axes.azim,window.axes.roll)==(25,50,30)
    for mode in ('Box','Exploded faces'):
        window.mode_combo.setCurrentText(mode); app.processEvents()
        assert window.valid_preview['markers']==source['markers']
        assert '(38, -60, -18) mm' in window.selected_readout.text()
    assert (window.axes.elev,window.axes.azim,window.axes.roll)==(25,50,30)
    row,annotation=next((r,a) for r,a in window.id_annotations if source['markers'][r]['id']=='F1')
    box=annotation.get_bbox_patch().get_window_extent(window.canvas3.get_renderer()); dpr=window.canvas3.devicePixelRatioF()
    p=window.canvas3.rect().topLeft(); p.setX(round((box.x0+box.x1)/2/dpr))
    p.setY(window.canvas3.height()-round((box.y0+box.y1)/2/dpr))
    QTest.mouseClick(window.canvas3,Qt.LeftButton,pos=p)
    assert window.selected_id=='F1' and window.table.currentRow()==row
    assert window.valid_preview['markers']==source['markers']; window.close()
    return dict(status='pass',kind='prototype-QTest',fresh=True,
        independent_expected='Example18 M2 source[38,-60,-18], display[38,-200,-18]; Reset view restores25/50/30; Box switch and F1 badge pick retain canonical geometry.',
        actual='All exact assertions passed',difference='none',tolerance=None,tolerance_reason='Exact source/camera equality; no physical measurement')


def render(out,candidates,small):
    app=QApplication.instance() or QApplication([]); states=[]
    for name,elev,azim,roll,ratio in candidates:
        assert all(np.isfinite(v) for v in (elev,azim,roll,ratio)) and ratio>=.5
        for example in ('32','18'):
            for size in ((1280,960),(1920,1080),(820,600)) if small else ((1280,960),(1920,1080)):
                window=ConfiguredExploded(example,size,(elev,azim,roll),ratio); settled(window,app,size)
                window.axes.view_init(elev,azim,roll,vertical_axis='y'); window.zoom_3d=None; window.draw(); app.processEvents()
                source=load_profile(example=example)
                assert window.valid_preview['markers']==source['markers']
                assert np.array_equal(window.source_xyz,np.asarray([m['xyz_mm'] for m in source['markers']]))
                dpr=window.canvas3.devicePixelRatioF()
                frames={f:project(window.axes,p)/dpr for f,p in window.face_vertices.items()}
                _,_,center=geometry(source,ratio)
                metrics=measurements(source,frames,project(window.axes,window.display_xyz)/dpr,project(window.axes,center)/dpr)
                entry=capture_reviewed(window,out,f'{name}-{example}-{size[0]}x{size[1]}.png',size)
                entry.update(candidate=name,camera=[elev,azim,roll],radius_ratio=ratio,
                    canvas3_logical=[window.canvas3.width(),window.canvas3.height()],
                    metrics=metrics,labels=window.label_metrics,source_hash=EXPECTED_HASHES[example],
                    display_offsets={f:p.tolist() for f,p in window.face_offsets.items()})
                states.append(entry)
                if size==(820,600):
                    bar=window.plot_scroll.verticalScrollBar(); bar.setValue(bar.maximum()); app.processEvents()
                    entry=capture_reviewed(window,out,f'{name}-{example}-820x600-bottom.png',size)
                    entry.update(candidate=name,scroll_position='bottom'); states.append(entry)
                    window.tabs.setCurrentWidget(window.table)
                    row=next(i for i,m in enumerate(source['markers']) if m['id']=='B2')
                    window.table.item(row,3).setText('bad'); app.processEvents()
                    assert window.status.text()=='B2: Y must be a finite number.'
                    assert not any(b.isEnabled() for b in (window.preview_button,window.save_button,window.apply_button))
                    entry=capture_reviewed(window,out,f'{name}-{example}-820x600-invalid.png',size)
                    entry.update(candidate=name,state='invalid-B2-Y'); states.append(entry)
                    window.table.item(row,3).setText(str(source['markers'][row]['xyz_mm'][1]))
                    assert window.preview_button.isEnabled()
                    assert window.valid_preview['markers']==source['markers']
                window.close()
    report=base_report('ExplodedAngleSpacingRenderEvidence')
    report.update(states=states,environment=dict(qt_platform=app.platformName(),dpr=app.primaryScreen().devicePixelRatio(),
        windows_scale_percent=100,qt_process_scale_percent=100*app.primaryScreen().devicePixelRatio()),
        independent_expected='Literal recorded example hashes; exact unchanged canonical marker positions; same source mm readout. Zero ID badge bbox overlaps/clipping.',
        result='pass',fresh=True,interaction=check_candidate(app),
        limitations=['Projected proximity and polygon overlap diagnostics do not certify human label/leader readability.',
            'Qt render only; no native acceptance, production implementation or user approval.'])
    (out/'evidence.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    print(json.dumps(dict(states=len(states),dpr=app.primaryScreen().devicePixelRatio(),summary=[dict(candidate=s['candidate'],size=s['logical_size'],metrics=s['metrics']) for s in states if s.get('source_hash')==EXPECTED_HASHES['32']])))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--scan',action='store_true')
    parser.add_argument('--small',action='store_true',help='Also capture820x600 top/bottom/invalid states')
    parser.add_argument('--candidate',action='append',default=[],help='name:elev:azim:roll:radius-ratio')
    args=parser.parse_args(); args.output.mkdir(parents=True,exist_ok=True)
    if args.scan: scan(args.output)
    if args.candidate:
        candidates=[]
        for item in args.candidate:
            name,elev,azim,roll,ratio=item.split(':'); candidates.append((name,float(elev),float(azim),float(roll),float(ratio)))
        render(args.output,candidates,args.small)


if __name__=='__main__': main()
