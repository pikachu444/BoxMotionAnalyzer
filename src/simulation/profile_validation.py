"""Production PUB05 renders from public static fixtures; never native acceptance."""
import argparse
from datetime import datetime, timezone, timedelta
from importlib.metadata import version
import hashlib
import json
from pathlib import Path
import platform
import subprocess
import sys
import time

import numpy as np
import PySide6
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from src.simulation.marker_fixtures import example_profile, virtual_profile_32
from src.simulation.profile_semantic_fixtures import ambiguous_face_profile
from src.simulation.ui.marker_profile_dialog import MarkerProfileDialog
from src.simulation.ui.profile_preview import box_at, intersects
from src.utils.marker_profile_identity import PLAN_SPEC, POLICY_VERSION, envelope, profile_identity


def settled(app, scene):
    deadline=time.monotonic()+4
    while time.monotonic()<deadline:
        QTest.qWait(20); app.processEvents()
        if scene.solver is None and not scene.idle_timer.isActive() and not scene.layout_timer.isActive(): break
    if scene.solver is not None: raise RuntimeError('Name placement did not finish.')
    scene.repaint(); app.processEvents()


def display_diagnostics(scene):
    """Inspect actual painted names/points with literal painter stroke extents."""
    badges=list(scene.badge_boxes.values()); points=np.asarray([box_at(p,[13.35,13.35]) for p in scene.point_pixels])
    titles=[box_at(center,size) for center,size,_ in scene.title_boxes.values()]
    return dict(names=len(scene.layout),limited=scene.limited,
        badge_collisions=sum(int(np.count_nonzero(intersects(b,np.asarray(badges[i+1:]).reshape(-1,4)))) for i,b in enumerate(badges)),
        badge_marker_occlusions=sum(int(np.count_nonzero(intersects(b,points))) for b in badges),
        title_marker_occlusions=sum(int(np.count_nonzero(intersects(b,points))) for b in titles),
        title_badge_collisions=sum(int(np.count_nonzero(intersects(b,np.asarray(badges).reshape(-1,4)))) for b in titles))


def main():
    parser=argparse.ArgumentParser(description=__doc__); parser.add_argument('--output',required=True)
    args=parser.parse_args(); root=Path(args.output); root.mkdir(parents=True,exist_ok=True)
    started=time.monotonic(); stamp=datetime.now(timezone.utc)
    app=QApplication.instance() or QApplication([]); screen=app.primaryScreen()
    report=envelope('RunReport', run_id='pub05-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'),
        utc=stamp.isoformat(),kst=stamp.astimezone(timezone(timedelta(hours=9))).isoformat(),
        command=sys.argv,tier='widget-render',schema_versions=dict(profile_identity=1,profile_document=1,artifact=1,
            manifest=None,decision=None,signature=None),tolerance_version=None,
        code=dict(commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
            dirty=bool(subprocess.check_output(['git','status','--porcelain'],text=True).strip()),semantics=POLICY_VERSION),
        environment=dict(os=platform.platform(),python=platform.python_version(),pyside=PySide6.__version__,
            qt_platform=app.platformName(),dpr=screen.devicePixelRatio(),
            available_logical=[screen.availableGeometry().width(),screen.availableGeometry().height()],
            os_scale='not inferred from QT_SCALE_FACTOR; local Windows setting separately recorded',
            dependencies={name:version(name) for name in ('numpy','pandas','scipy','matplotlib','mujoco','PySide6')}),
        input=dict(kind='public-synthetic-static',seed=None,seed_reason='Explicit deterministic static coordinates; no random observation'),
        approval=dict(mockup='Human approved final interactive mockup on 2026-10-06 before production implementation',
            trial='not_evaluated',tolerance='no new physical tolerance',baseline='no promotion'),
        native=dict(status='not_executed',reason='External Windows capture/activation failed in prior attempts; widget rendering is separate'),
        experimental_validation=dict(status='unavailable',reason='#104 separate; no validated measured dataset'),
        registration=dict(status='not_applicable',reason='#113 user feature excluded; existing static #135 adapter retained'),
        statuses=[], tolerances=[dict(value=0,units='canonical-profile-data',basis='Exact source/draft/applied equality'),
            dict(value=0,units='logical-pixels',basis='Requested client size and button containment')],
        performance=dict(status='structural_bounds_checked',reason='No native latency/FPS/RSS certification'),
        independent_review=dict(status='pending_production'),fresh=True,
        oracle='Literal UI states and untouched declared profile coordinates, independent of production output')
    for factory,count in ((example_profile,18),(virtual_profile_32,32)):
        source=factory(); record=profile_identity(source)
        for size in ((1920,1080),(820,600)):
            for state in ('default','invalid','edited','geometry-blocked','ambiguous'):
                window=MarkerProfileDialog(source,previous_result_identity=record)
                window.resize(*size); window.show(); QTest.qWaitForWindowExposed(window,2000)
                window.resize(*size); settled(app,window.scene)
                if state=='invalid': window.table.item(0,2).setText('NaN')
                elif state=='edited': window.table.item(0,0).setText('F99'); window.preview()
                elif state in ('geometry-blocked','ambiguous'):
                    # Real valid single-face import: no fabricated parser face certification.
                    profile=example_profile(); profile['profile_id']='independent-front-only'
                    profile['markers']=[dict(id=f'F{i}',face='FRONT',xyz_mm=[x,0,40]) for i,x in enumerate((-60,-40,-20,0,20,40),1)]
                    if state=='ambiguous': profile=ambiguous_face_profile()
                    window.close(); window.deleteLater()
                    window=MarkerProfileDialog(profile); window.resize(*size); window.show()
                    QTest.qWaitForWindowExposed(window,2000); window.resize(*size)
                settled(app,window.scene)
                expected_apply=state in ('default','edited')
                assert window.apply_button.isEnabled()==expected_apply
                if state=='invalid': assert not window.preview_button.isEnabled() and not window.save_button.isEnabled()
                if state=='edited': assert window.state.applied==source and window.compatibility.text()=='Previous result: incompatible'
                snapshot=window.state.document() if state!='invalid' else None
                states=[('top',0)] if size[0]>820 else [('top',0),('bottom',window.plot_scroll.verticalScrollBar().maximum())]
                for section,scroll in states:
                    if size[0]==820: window.plot_scroll.verticalScrollBar().setValue(scroll); app.processEvents()
                    filename=f'{count}-{size[0]}x{size[1]}-{state}-{section}.png'
                    pixmap=window.grab(); assert pixmap.save(str(root/filename))
                    assert [window.width(),window.height()]==list(size)
                    buttons={}
                    for key in ('preview_button','reset_button','save_button','apply_button','cancel_button'):
                        button=getattr(window,key); point=button.mapTo(window,button.rect().topLeft())
                        inside=window.rect().contains(point) and window.rect().contains(button.mapTo(window,button.rect().bottomRight()))
                        assert inside and button.isVisible() and button.width()>=button.sizeHint().width()
                        buttons[key]=dict(enabled=button.isEnabled(),visible=True,inside=True)
                    assert np.array_equal(window.scene.source_xyz,[m['xyz_mm'] for m in window.state.preview['markers']])
                    diagnostics=display_diagnostics(window.scene)
                    if state=='default':
                        assert diagnostics['names']==count and not diagnostics['limited']
                        assert all(diagnostics[key]==0 for key in ('badge_collisions','badge_marker_occlusions','title_marker_occlusions','title_badge_collisions'))
                    if snapshot is not None: assert window.state.document()==snapshot
                    report['statuses'].append(dict(example=count,state=state,section=section,logical_size=list(size),
                        pixel_size=[pixmap.width(),pixmap.height()],dpr=pixmap.devicePixelRatio(),
                        input_identity=profile_identity(window.state.source),selected=window.selected_readout.text(),
                        compatibility=window.compatibility.text(),buttons=buttons,screenshot=filename,
                        viewport_stats=dict(window.scene.stats),diagnostics=diagnostics,cache_entries=len(window.scene.cache),fresh=True,status='pass'))
                    assert len(window.scene.cache)<=8 and len(window.scene.paint_ms)<=256 and len(window.scene.input_to_paint_ms)<=256
                window.close(); window.deleteLater(); app.processEvents()
    report['status']='pass'; report['differences']=[]
    report.update(reason='All scoped widget assertions passed; native/experimental acceptance remain separate',
        exit_code=0,duration_s=time.monotonic()-started,peak_memory_bytes=None,optimizer_calls=0,
        first_difference_boundary=None,cache_origin='Fresh window per case; internal bounded display cache only',
        coverage=dict(loaded=len(report['statuses']),approved=0,fresh=len(report['statuses']),reused=0,failed=0,unexecuted=0),
        exception=None,traceback=None)
    report['unapplied_runreport_fields']=dict(raw_sha256='Static geometry identity replaces raw input; no observations processed',
        error_accuracy='Static UI contract only; numerical recovery lives in independent pipeline tests',
        peak_memory='Not an acceptance condition; bounded state inspected directly',
        manifest_decision_signature='Static widget fixtures use declared profile identities; no capture/decision/signature files consumed',
        settings_identity='No numerical analysis settings; exact UI producer source hashes and per-case display statistics recorded',
        tolerance_version='Exact UI invariants only; no new physical tolerance approval',
        approved_coverage='No new capture/trial/tolerance/baseline approvals; mockup approval is recorded separately',
        first_difference_exception='None because scoped assertions passed; failed runs surface a Python traceback/exit in command diagnostics')
    report['source_sha256']={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in
        (Path(__file__),Path('src/simulation/ui/profile_preview.py'),Path('src/simulation/ui/marker_profile_dialog.py'))}
    (root/'execution.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    print(json.dumps(dict(status='pass',states=len(report['statuses']),dpr=screen.devicePixelRatio())))
    return 0


if __name__=='__main__': raise SystemExit(main())
