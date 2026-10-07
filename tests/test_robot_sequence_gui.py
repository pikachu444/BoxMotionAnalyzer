"""Actual PUB07 GUI Preview/Apply, workers, partial capture and source guards."""
from copy import deepcopy
from pathlib import Path
import time
import pytest
from PySide6.QtWidgets import QApplication,QFileDialog,QMessageBox
from src.simulation.ui.main_window import SimulationUI
from src.simulation.ui.marker_export_dialog import MarkerExportWorker
from src.simulation.mode_profiles import ModeProfiles,save_profiles,read_profiles
from src.simulation.robot_validation import fixture as robot_fixture
from src.simulation.engine.robot_sequence import RobotSequenceEngine
from src.analysis.pipeline.data_loader import DataLoader
from src.utils.artifact_metadata import read_identity
from src.utils.simulation_metadata import artifact_simulation


def wait(predicate,timeout=35):
    until=time.monotonic()+timeout
    while not predicate() and time.monotonic()<until:QApplication.processEvents();time.sleep(.005)
    assert predicate()


@pytest.fixture
def window(monkeypatch):
    app=QApplication.instance() or QApplication([]);w=SimulationUI();w.viewer_cb.setChecked(False)
    for name in ('information','warning','critical'):monkeypatch.setattr(QMessageBox,name,lambda *a:None)
    w.show();app.processEvents();yield w
    if w._busy:w.cancel_simulation();wait(lambda:not w._busy)
    if w.marker_dialog:w.marker_dialog.reject();app.processEvents()
    w.close();app.processEvents()


def apply_config(window,config):
    state=ModeProfiles();state.switch('robot_sequence');state.set_config(config);window._apply_profiles(state)


def public(path):return artifact_simulation(read_identity(DataLoader().load_result_csv(str(path))).values)


def test_real_preview_binds_selected_face_and_edited_rows(window):
    window.mode_combo.setCurrentIndex(1);p=window.settings
    p.handling.setCurrentIndex(p.handling.findData('airborne'));p.run_scope.setCurrentIndex(1);p.table.selectRow(7)
    p.attachment_face.setCurrentText('+X');p.table.item(7,2).setText('11');p.table.item(7,3).setText('12');p.table.item(7,4).setText('37')
    p.preview_sequence();text=p.sequence_preview.text()
    assert '+X face' in text and '1 of 17' in p.preview_count.text() and 'drop 8' in p.preview_count.text()
    dialog=p.sequence_details_dialog();tabs=dialog.layout().itemAt(0).widget()
    actions=tabs.widget(1)
    assert actions.item(3,1).text()=='Turn' and actions.item(3,3).text()=='11 / 12 / 37'
    assert tabs.widget(0).item(7,2).text()=='Yes' and tabs.widget(0).item(0,2).text()=='Excluded'
    dialog.deleteLater()
    before=window.profiles.document();p.physics_controls[0].setValue(26);p.apply_settings()
    assert window.profiles.document()==before and 'Preview sequence' in p.status.text()
    p.preview_sequence();p.apply_settings();c=window.profiles.configs['robot_sequence'];plan=c['sequence_profile']['execution_plan']
    assert plan['attachment_face']=='+X' and plan['selected_step_ids']==[c['sequence_profile']['steps'][7]['step_id']]
    assert len(plan['omitted_step_ids'])==16 and window.run_btn.isEnabled() and not window.batch_btn.isEnabled()
    assert isinstance(window._engine(c),RobotSequenceEngine)
    window.mass_input.setValue(27)
    assert not window.run_btn.isEnabled() and 'stale' in window.run_btn.toolTip()


def test_entire_hazard_blocks_and_loaded_custom_plan_is_preserved(window,tmp_path,monkeypatch):
    window.mode_combo.setCurrentIndex(1);p=window.settings;p.handling.setCurrentIndex(1);p.preview_sequence()
    assert 'Hazard' in p.sequence_preview.text() and not window.run_btn.isEnabled()
    c=robot_fixture(two=False);c['sequence_profile']['execution_plan']['phases'][2]['target_origin_mm'][0]=12.
    c['sequence_profile']['execution_plan']['physics']['radius_mm']=6.5
    apply_config(window,c);window.settings.preview_sequence()
    dialog=window.settings.sequence_details_dialog();conditions=dialog.layout().itemAt(0).widget().widget(2).layout()
    assert conditions.itemAt(0).widget().text()=='Grip geometry'
    assert conditions.itemAt(1).widget().text()=='Sphere, radius 6.5 mm';dialog.deleteLater()
    apply_config(window,c);window.settings.preview_sequence();window.settings.apply_settings()
    assert window.profiles.configs['robot_sequence']['sequence_profile']['execution_plan']==c['sequence_profile']['execution_plan']
    path=tmp_path/'settings.json';monkeypatch.setattr(QFileDialog,'getSaveFileName',lambda *a:(str(path),''))
    window.settings.save_settings();loaded=read_profiles(path)
    assert loaded.configs['robot_sequence']['sequence_profile']['execution_plan']==c['sequence_profile']['execution_plan']


def test_actual_gui_two_release_worker_export_and_reload(window,tmp_path,monkeypatch):
    c=robot_fixture();c['duration_s']=120.;apply_config(window,c);path=tmp_path/'two-release.proc'
    monkeypatch.setattr(QFileDialog,'getSaveFileName',lambda *a:(str(path),''))
    window.run_simulation();assert window._busy and not window.mode_combo.isEnabled()
    wait(lambda:not window._busy);assert path.exists() and window.previous_result==str(path)
    assert window.thread.engine.sequence_evidence['engine_builds']==1
    assert sum(t['kind']=='release' for t in window.thread.engine.sequence_evidence['toggles'])==2
    assert public(path)['execution_status']=='completed' and window.run_btn.isEnabled()
    assert public(path)['configuration']['requested_duration_s']==120. and window.duration_input.maximum()==3600.


def test_explicit_full_edited_plan_gets_sufficient_visible_budget(window):
    window.mode_combo.setCurrentIndex(1);p=window.settings;p.handling.setCurrentIndex(1)
    p.table.selectRow(16);p.remove_drop();p.preview_sequence();p.apply_settings()
    config=window.profiles.configs['robot_sequence'];plan=config['sequence_profile']['execution_plan']
    assert len(plan['selected_step_ids'])==16 and len(plan['phases'])>100
    assert config['duration_s']>60 and window.duration_input.value()==config['duration_s']
    assert window.run_btn.isEnabled()
    window.mode_combo.setCurrentIndex(0);assert window.duration_input.maximum()==60.


@pytest.mark.parametrize('reason',['cancelled','time_limit','face'])
def test_actual_gui_partial_retention_and_retry(window,tmp_path,monkeypatch,reason):
    c=robot_fixture(two=False)
    if reason=='time_limit':c['duration_s']=.5
    if reason=='face':c['sequence_profile']['execution_plan']['attachment_face']='-Z'
    apply_config(window,c);path=tmp_path/'previous.proc';path.write_bytes(b'previous complete result');window.previous_result=str(path)
    monkeypatch.setattr(QFileDialog,'getSaveFileName',lambda *a:(str(path),''))
    if reason=='cancelled':
        original=RobotSequenceEngine._step
        def slower(engine,*args):time.sleep(.0005);return original(engine,*args)
        monkeypatch.setattr(RobotSequenceEngine,'_step',slower)
    window.run_simulation()
    if reason=='cancelled':
        wait(lambda:window.thread.engine.data is not None and window.thread.engine.data.time>.05)
        window.cancel_simulation()
    wait(lambda:not window._busy)
    partial=[r for r in window.result_history if r.get('partial')][-1]
    assert Path(partial['path']).exists() and path.read_bytes()==b'previous complete result' and window.previous_result==str(path)
    assert public(partial['path'])['execution_status']==('failure' if reason=='face' else reason)
    assert window.run_btn.isEnabled()
    if reason=='cancelled':
        generation=window._generation;old=window.result_label.text()
        window._worker_progress(window.thread,generation-1,99.,100.,'stale')
        assert window.result_label.text()==old


def test_actual_h_preview_and_partial_marker_worker(window,tmp_path):
    c=robot_fixture(family='floor_supported',two=False);apply_config(window,c);window.settings.preview_sequence()
    text=window.settings.sequence_preview.text()
    assert 'Virtual tip on floor' in text
    dialog=window.settings.sequence_details_dialog();actions=dialog.layout().itemAt(0).widget().widget(1)
    assert actions.item(2,1).text()=='Turn' and actions.item(2,3).text()=='0 / 15 / 0'
    assert '100 / 0 / -40' in actions.item(2,3).toolTip();dialog.deleteLater()
    c=robot_fixture(two=False);c['duration_s']=.5;marker=c['observation_profile']['marker']
    from src.simulation.ui.main_window import SimulationUI
    simulation=SimulationUI._params(c);p=c['physics_profile'];simulation.update(mass=p['mass_kg'],friction=p['friction'],
        elasticity=p['contact_damping_control'],com_offset=p['com_offset_mm'])
    worker=MarkerExportWorker(str(tmp_path/'capture'),marker['profile'],simulation,marker['faults'],marker['seed'])
    worker.start();wait(lambda:not worker.isRunning())
    assert worker.partial_path and public(worker.partial_path)['execution_status']=='time_limit'
    assert not (tmp_path/'capture'/'observed.csv').exists()


def test_stale_applied_plan_blocks_before_picker(window,monkeypatch):
    c=robot_fixture(two=False);apply_config(window,c);window.w_input.setValue(201.)
    monkeypatch.setattr(QFileDialog,'getSaveFileName',lambda *a:pytest.fail('stale plan opened picker'))
    window.run_simulation();assert not window._busy


def preset_config(selected):
    from src.simulation.ui.mode_settings import preset_steps
    from src.simulation.scenarios import Scenarios
    from src.simulation.robot_profiles import with_example
    c=robot_fixture(two=False);c['sequence_profile']['steps']=preset_steps(Scenarios.CATEGORIES[0],c['size_mm'],1.)
    return with_example(c,selected_step_ids=[c['sequence_profile']['steps'][i]['step_id'] for i in selected])


def test_real_selected_drop_marker_dialog_source_and_worker(window,tmp_path,monkeypatch):
    c=preset_config([7]);apply_config(window,c)
    assert window.custom_h_input.value()!=c['sequence_profile']['steps'][0]['clearance_mm']
    window.open_marker_export();dialog=window.marker_dialog
    assert dialog.simulation['height']==c['sequence_profile']['steps'][0]['clearance_mm']
    monkeypatch.setattr(QFileDialog,'getExistingDirectory',lambda *a:str(tmp_path))
    dialog.generate();wait(lambda:not dialog.busy)
    assert dialog.observed_path and Path(dialog.observed_path).exists()
    header,_=DataLoader().load_csv(dialog.observed_path);value=artifact_simulation(header['artifact_metadata'])
    assert value['configuration']['sequence_profile']['execution_plan']['selected_step_ids']==['preset-8']
    dialog.reject()


def test_loaded_multi_drop_subset_is_visible_and_expansion_is_explicit(window,tmp_path,monkeypatch):
    c=preset_config([0,7]);apply_config(window,c);p=window.settings
    assert p.run_scope.currentData()=='captured' and '2 / 17' in p.run_scope.currentText()
    p.table.selectRow(4);p.apply_settings()
    assert window.profiles.configs['robot_sequence']['sequence_profile']['execution_plan']==c['sequence_profile']['execution_plan']
    path=tmp_path/'captured-subset.proc';monkeypatch.setattr(QFileDialog,'getSaveFileName',lambda *a:(str(path),''))
    window.run_simulation();wait(lambda:not window._busy)
    assert public(path)['configuration']['sequence_profile']['execution_plan']['selected_step_ids']==['preset-1','preset-8']
    assert sum(t['kind']=='release' for t in window.thread.engine.sequence_evidence['toggles'])==2
    p.run_scope.setCurrentIndex(0);before=window.profiles.document();p.apply_settings()
    assert window.profiles.document()==before and 'Preview' in p.status.text()
    p.preview_sequence();assert 'Hazard' in p.sequence_preview.text()


@pytest.mark.parametrize('stale',[False,True])
def test_cancelled_partial_write_failure_remains_visible(window,tmp_path,monkeypatch,stale):
    import src.simulation.ui.main_window as ui
    c=robot_fixture(two=False);apply_config(window,c);path=tmp_path/'previous.proc';path.write_bytes(b'keep')
    window.previous_result=str(path);monkeypatch.setattr(QFileDialog,'getSaveFileName',lambda *a:(str(path),''))
    def failed(*args):raise OSError('injected disk full')
    monkeypatch.setattr(ui,'retain_partial',failed)
    original=RobotSequenceEngine._step
    def slower(engine,*args):time.sleep(.0005);return original(engine,*args)
    monkeypatch.setattr(RobotSequenceEngine,'_step',slower)
    window.run_simulation();wait(lambda:window.thread.engine.data is not None and window.thread.engine.data.time>.05)
    if stale:window.mass_input.setValue(2.)
    else:window.cancel_simulation()
    wait(lambda:not window._busy)
    assert path.read_bytes()==b'keep' and window.previous_result==str(path)
    assert 'Partial capture was not saved' in window.result_label.text() and 'injected disk full' in window.result_label.text()


def test_virtual_h_scope_matches_actual_applied_template(window):
    apply_config(window,robot_fixture(family='floor_supported',two=False))
    assert window.settings.table.item(0,5).text()=='Virtual floor tip'
    assert 'ISTA procedure is unverified' in window.settings.table.item(0,5).toolTip()
    window.settings.preview_sequence();assert 'Virtual tip on floor' in window.settings.sequence_preview.text()


def test_viewer_bridge_mocked_cancel_preserves_retention_failure(window,tmp_path,monkeypatch):
    import src.simulation.ui.main_window as ui
    apply_config(window,robot_fixture(two=False));window.viewer_cb.setChecked(True)
    path=tmp_path/'previous.proc';path.write_bytes(b'previous');window.previous_result=str(path)
    monkeypatch.setattr(QFileDialog,'getSaveFileName',lambda *a:(str(path),''))
    def failed(*args):raise OSError('injected viewer disk full')
    monkeypatch.setattr(ui,'retain_partial',failed)
    original=RobotSequenceEngine.run_simulation
    def headless_bridge(engine,**kwargs):
        callback=kwargs['progress']
        def progress(current,limit):
            if current>.05 and window._cancel_message is None:window.cancel_simulation()
            callback(current,limit)
        kwargs.update(show_viewer=False,progress=progress);return original(engine,**kwargs)
    monkeypatch.setattr(RobotSequenceEngine,'run_simulation',headless_bridge)
    window.run_simulation()
    assert not window._busy and path.read_bytes()==b'previous'
    assert 'injected viewer disk full' in window.result_label.text()
