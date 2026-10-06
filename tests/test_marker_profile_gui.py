"""Production widgets/QTest, distinct from external native input verification."""
from copy import deepcopy
from pathlib import Path
import json
import threading
import time

import pytest
from PySide6.QtCore import Qt, QPoint, QPointF
from PySide6.QtGui import QWheelEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox

from src.simulation.marker_fixtures import example_profile, virtual_profile_32
from src.simulation.profile_document import read_document, save_document, ProfileEditorState
from src.simulation.ui.marker_profile_dialog import MarkerProfileDialog
from src.simulation.ui.marker_export_dialog import MarkerExportDialog
from src.utils.marker_profile_identity import profile_identity


@pytest.fixture
def app():
    value = QApplication.instance() or QApplication([]); yield value
    value.processEvents()


def settle(app, ms=200):
    QTest.qWait(ms); app.processEvents()


@pytest.mark.parametrize('factory', [example_profile, virtual_profile_32])
def test_draft_preview_reset_save_reopen_and_apply(app, factory, tmp_path, monkeypatch):
    source=factory(); dialog=MarkerProfileDialog(source); dialog.show(); settle(app)
    assert dialog.scene.profile == dialog.state.preview and dialog.state.applied == source
    before = deepcopy(dialog.state.preview)
    dialog.table.item(0,0).setText('F99')
    assert dialog.state.draft['markers'][0]['id']=='F99' and dialog.state.preview==before
    assert not dialog.apply_button.isEnabled() and dialog.preview_button.isEnabled()
    QTest.mouseClick(dialog.preview_button, Qt.LeftButton); settle(app)
    assert dialog.state.preview['markers'][0]['id']=='F99' and dialog.state.applied==source
    assert dialog.apply_button.isEnabled()
    # Invalid input retains the last valid scene, blocks Preview/Apply/Save.
    dialog.table.item(0,2).setText('Infinity')
    assert 'finite' in dialog.status.text() and not dialog.preview_button.isEnabled()
    assert not dialog.apply_button.isEnabled() and not dialog.save_button.isEnabled()
    assert dialog.scene.profile==dialog.state.preview
    QTest.mouseClick(dialog.reset_button,Qt.LeftButton)
    assert dialog.state.draft['markers'][0]['id']=='F1' and dialog.state.preview['markers'][0]['id']=='F99'
    assert not dialog.apply_button.isEnabled()
    path=tmp_path/'draft.json'; assert dialog.save_to(path)
    saved=read_document(path); assert saved.applied==source and not saved.preview_fresh
    assert saved.draft['markers'][0]['id']=='F1' and saved.preview['markers'][0]['id']=='F99'
    snapshot=dialog.state.document()
    import src.simulation.profile_document as documents
    with monkeypatch.context() as scoped:
        scoped.setattr(documents.os,'replace',lambda *a:(_ for _ in ()).throw(OSError('independent injected failure')))
        assert not dialog.save_to(path) and 'Save failed' in dialog.status.text()
    assert dialog.state.document()==snapshot and read_document(path).document()==saved.document()
    assert dialog.save_to(path)
    monkeypatch.setattr(QFileDialog,'getSaveFileName',lambda *a:('', ''))
    old_bytes=path.read_bytes(); QTest.mouseClick(dialog.save_button,Qt.LeftButton)
    assert path.read_bytes()==old_bytes and dialog.state.document()==snapshot
    dialog.reject(); assert source==factory()
    restored=MarkerProfileDialog(source,document=saved.document()); restored.show(); settle(app)
    QTest.mouseClick(restored.preview_button,Qt.LeftButton); QTest.mouseClick(restored.apply_button,Qt.LeftButton)
    assert restored.result()==MarkerProfileDialog.Accepted
    assert restored.state.applied['markers'][0]['id']=='F1' and restored.state.applied!=source
    dialog.deleteLater(); restored.deleteLater(); settle(app)


@pytest.mark.parametrize('size', [(1920,1080), (820,600)])
def test_display_gestures_and_resize_preserve_profile_and_2d(app, size):
    dialog=MarkerProfileDialog(virtual_profile_32()); dialog.resize(*size); dialog.show(); settle(app)
    assert QTest.qWaitForWindowExposed(dialog,2000)
    # Windows can fit the initial decorated window to the desktop. As in the
    # delivered #137 harness, request the exact logical client after exposure.
    dialog.resize(*size); settle(app)
    assert (dialog.width(),dialog.height())==size
    snapshot=dialog.state.document(); axes=dialog.face_axes; labels=tuple(dialog.face_labels)
    scene=dialog.scene; start=scene.rect().center()
    QTest.mousePress(scene,Qt.LeftButton,pos=start); QTest.mouseMove(scene,start+QPoint(25,17),delay=15)
    QTest.mouseRelease(scene,Qt.LeftButton,pos=start+QPoint(25,17)); settle(app)
    assert dialog.state.document()==snapshot and dialog.face_axes is axes and tuple(dialog.face_labels)==labels
    assert dialog.rect().contains(dialog.apply_button.mapTo(dialog,dialog.apply_button.rect().center()))
    assert dialog.rect().contains(dialog.cancel_button.mapTo(dialog,dialog.cancel_button.rect().center()))
    QTest.mouseClick(dialog.reset_view_button,Qt.LeftButton); settle(app)
    assert dialog.state.document()==snapshot
    dialog.resize(1280,960); settle(app); dialog.resize(*size); settle(app)
    assert dialog.state.document()==snapshot
    # Hide/focus loss cancels capture; subsequent queued motion cannot edit a draft.
    QTest.mousePress(scene,Qt.LeftButton,pos=scene.rect().center()); dialog.hide(); settle(app)
    assert dialog.state.document()==snapshot
    dialog.reject(); dialog.deleteLater(); settle(app)


def test_face_drag_pan_zoom_cancel_preserve_canonical_buffers(app):
    import numpy as np
    from src.simulation.profile_validation import settled, display_diagnostics
    dialog=MarkerProfileDialog(example_profile()); dialog.show(); settle(app); scene=dialog.scene
    settled(app,scene); snapshot=dialog.state.document(); buffers=(id(scene._display_points),id(scene._world_scene))
    before=scene.snapshot_view(); center=scene.title_boxes['FRONT'][0]
    assert before['offsets']==dict(FRONT=.8,BACK=.8,RIGHT=.5,LEFT=.5,TOP=.7,BOTTOM=.7)
    normal=np.array([0,0,1])*200; projected=scene.project([np.zeros(3),normal])[0]
    delta=(projected[1]-projected[0])*.2
    start=QPoint(*np.rint(center).astype(int)); end=QPoint(*np.rint(center+delta).astype(int))
    starts=scene.stats['solve_starts']; labels=tuple(dialog.face_labels)
    QTest.mousePress(scene,Qt.LeftButton,pos=start); QTest.mouseMove(scene,end,delay=20); app.processEvents()
    assert scene.gesture['kind']=='face' and scene.stats['solve_starts']==starts
    assert tuple(dialog.face_labels)==labels and buffers==(id(scene._display_points),id(scene._world_scene))
    QTest.mouseRelease(scene,Qt.MiddleButton,pos=end); assert scene.gesture is not None
    QTest.mouseRelease(scene,Qt.LeftButton,pos=end); settled(app,scene)
    assert abs(scene.view['offsets']['FRONT']-1.)<.015  # Initial .8 + .2 display ratio; integer pointer rounding, not physical tolerance.
    assert all(scene.view['offsets'][f]==before['offsets'][f] for f in before['offsets'] if f!='FRONT')
    view=scene.snapshot_view(); QTest.mousePress(scene,Qt.MiddleButton,pos=QPoint(25,25))
    QTest.mouseMove(scene,QPoint(65,50),delay=20); QTest.mouseRelease(scene,Qt.MiddleButton,pos=QPoint(65,50))
    assert scene.view['pan']==[view['pan'][0]+40,view['pan'][1]+25]
    zoom=scene.view['zoom']; pos=QPointF(scene.rect().center())
    app.sendEvent(scene,QWheelEvent(pos,pos,QPoint(),QPoint(0,120),Qt.NoButton,Qt.NoModifier,Qt.ScrollUpdate,False))
    assert scene.view['zoom']>zoom
    view=scene.snapshot_view(); QTest.mousePress(scene,Qt.LeftButton,pos=QPoint(25,25)); QTest.mouseMove(scene,QPoint(80,65),delay=20)
    QTest.keyClick(scene,Qt.Key_Escape); assert scene.view==view and scene.gesture is None
    assert dialog.state.document()==snapshot
    scene.reset_view(); settled(app,scene)
    diagnostics=display_diagnostics(scene)
    assert diagnostics['names']==18 and not diagnostics['limited']
    assert all(diagnostics[key]==0 for key in ('badge_collisions','badge_marker_occlusions','title_marker_occlusions','title_badge_collisions'))
    for row in range(18):
        positions={r:p.copy() for r,p in scene.layout.items()}; scene.set_selected(row); scene.repaint(); app.processEvents()
        assert all(np.array_equal(positions[r],scene.layout[r]) for r in positions)
    assert dialog.state.document()==snapshot and len(scene.cache)<=8
    dialog.reject(); dialog.deleteLater(); settle(app)


def test_import_saved_applied_with_pending_draft_and_cancel(app,tmp_path,monkeypatch):
    simulation=dict(duration=.5,height=250,mass=10,com_offset=[0,0,0],friction=.5,elasticity=.1,quat=[1,0,0,0])
    dialog=MarkerExportDialog(simulation,(200,120,80)); dialog.show(); settle(app)
    state=ProfileEditorState(example_profile()); draft=deepcopy(state.draft); draft['markers'][0]['id']='F99'; state.edit(draft)
    path=tmp_path/'saved.json'; save_document(path,state)
    monkeypatch.setattr(QFileDialog,'getOpenFileName',lambda *a:(str(path),''))
    QTest.mouseClick(dialog.import_button,Qt.LeftButton)
    assert dialog.profile==example_profile() and dialog.imported_document==state.document()
    def cancel_editor():
        modal=QApplication.activeModalWidget()
        assert isinstance(modal,MarkerProfileDialog) and modal.state.draft['markers'][0]['id']=='F99'
        modal.table.item(0,0).setText('F77'); modal.reject()
    from PySide6.QtCore import QTimer
    QTimer.singleShot(100,cancel_editor); QTest.mouseClick(dialog.edit_button,Qt.LeftButton)
    assert dialog.imported_document==state.document() and dialog.profile==example_profile()
    dialog.profile_combo.setCurrentIndex(1)
    source=deepcopy(dialog.profile)
    def apply_copy():
        modal=QApplication.activeModalWidget(); assert modal.state.source==source
        modal.table.item(0,0).setText('F99'); modal.preview(); modal.apply()
    QTimer.singleShot(100,apply_copy); QTest.mouseClick(dialog.copy_button,Qt.LeftButton)
    assert dialog.profile['markers'][0]['id']=='F99' and virtual_profile_32()==source
    assert dialog.imported_document['history'][-1]['operation']=='apply'
    dialog.reject(); dialog.deleteLater(); settle(app)


def test_profile_change_cancel_late_worker_results_and_retry(app,tmp_path,monkeypatch):
    from src.simulation.ui import marker_export_dialog as module
    simulation=dict(duration=.5,height=250,mass=10,com_offset=[0,0,0],friction=.5,elasticity=.1,quat=[1,0,0,0])
    dialog=MarkerExportDialog(simulation,(200,120,80)); dialog.show(); settle(app)
    started=threading.Event(); finish=threading.Event()
    def late(*a,**k):
        started.set(); finish.wait(10); return str(tmp_path/'late.csv')
    monkeypatch.setattr(module,'generate_marker_capture',late)
    monkeypatch.setattr(QFileDialog,'getExistingDirectory',lambda *a:str(tmp_path))
    dialog.observed_path='previous.csv'; dialog.result_identity=profile_identity(example_profile())
    dialog.generate(); settle(app); assert started.is_set()
    old=dialog.worker; generation=dialog._generation
    dialog.profile_combo.setCurrentIndex(1)
    assert old.isInterruptionRequested() and dialog.result_compatibility['status']=='incompatible'
    # Deliver obsolete events directly while a real worker is still in flight.
    dialog._job_event(old,generation,dialog._ready,'late.csv')
    dialog._job_event(old,generation,dialog._failed,'obsolete error')
    assert dialog.observed_path=='previous.csv' and 'obsolete' not in dialog.status.text()
    finish.set()
    deadline=time.monotonic()+10
    while dialog.busy and time.monotonic()<deadline: settle(app,20)
    assert not dialog.busy and dialog.observed_path=='previous.csv'
    # A retry cannot be finished or overwritten by the prior worker.
    dialog.dimensions.setChecked(True); started.clear(); finish.clear(); dialog.output_name.setText('retry'); dialog.generate(); settle(app)
    current=dialog.worker; assert current is not None and current is not old
    dialog._finished(old); dialog._job_event(old,generation,dialog._ready,'late.csv')
    assert dialog.worker is current and dialog.observed_path=='previous.csv'
    dialog.cancel(); finish.set()
    while dialog.busy and time.monotonic()<deadline+10: settle(app,20)
    assert not dialog.busy and dialog.observed_path=='previous.csv'
    dialog.reject(); dialog.deleteLater(); settle(app)


@pytest.mark.parametrize('kind', ['ambiguous','unavailable'])
def test_export_blocked_reason_and_previous_output_preserved(app,kind):
    from src.simulation.profile_semantic_fixtures import ambiguous_face_profile
    simulation=dict(duration=.5,height=250,mass=10,com_offset=[0,0,0],friction=.5,elasticity=.1,quat=[1,0,0,0])
    source=ambiguous_face_profile() if kind=='ambiguous' else example_profile()
    if kind=='unavailable':
        source['profile_id']='independent-front-only'
        source['markers']=[dict(id=f'F{i}',face='FRONT',xyz_mm=[x,0,40]) for i,x in enumerate((-60,-40,-20,0,20,40),1)]
    dialog=MarkerExportDialog(simulation,(200,120,80)); prior=profile_identity(example_profile())
    dialog.observed_path='previous.csv'; dialog.result_identity=deepcopy(prior)
    dialog.resize(820,600); dialog.show(); settle(app)
    dialog._set_custom(source,imported=True); dialog.dimensions.setChecked(True); settle(app)
    expected='distinct box orientations' if kind=='ambiguous' else 'local six-DOF support for the current solver'
    assert expected in dialog.status.text() and expected in dialog.generate_button.toolTip()
    assert not dialog.generate_button.isEnabled() and dialog.open_button.isEnabled()
    assert dialog.observed_path=='previous.csv' and dialog.result_identity==prior and dialog.result_compatibility['status']=='incompatible'
    assert 'Open uses' in dialog.status.toolTip()
    dialog.generate(); assert dialog.worker is None and expected in dialog.status.text()
    for button in (dialog.generate_button,dialog.cancel_button,dialog.open_button):
        assert button.isVisible() and dialog.rect().contains(button.mapTo(dialog,button.rect().bottomRight()))
    assert dialog.rect().contains(dialog.status.mapTo(dialog,dialog.status.rect().bottomRight()))
    output=Path('tmp/issue138')/f'export-blocked-{round(dialog.devicePixelRatioF()*100)}'; output.mkdir(parents=True,exist_ok=True)
    assert dialog.grab().save(str(output/(kind+'-820x600.png')))
    dialog.profile_combo.setCurrentIndex(0); settle(app)
    assert dialog.generate_button.isEnabled() and not dialog.generate_button.toolTip()
    assert dialog.status.text()=='Previous output: compatible with this profile.'
    assert dialog.observed_path=='previous.csv' and dialog.result_identity==prior
    dialog.reject(); dialog.deleteLater(); settle(app)
