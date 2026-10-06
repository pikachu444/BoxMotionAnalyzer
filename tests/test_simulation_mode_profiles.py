"""Independent settings/serialization contracts; no robot execution or trial approval."""
from copy import deepcopy
import json
import pytest

from src.simulation.mode_profiles import (ModeProfiles, default_config, drop_step,
    validate_config, require_executable, save_profiles, read_profiles, BLOCKED_REASON)
from src.utils.marker_profile_identity import digest


def rehash(document):
    document['content_hash']=digest({k:v for k,v in document.items() if k!='content_hash'})
    return document


def test_single_defaults_literal_and_marker_identity():
    state=ModeProfiles();config=state.configs['single_drop']
    assert state.mode=='single_drop'
    assert config['size_mm']==[1578,930,142]
    assert config['physics_profile']['mass_kg']==25
    assert config['physics_profile']['com_offset_mm']==[0,-200,0]
    step=config['sequence_profile']['steps'][0]
    assert (step['preset_id'],step['clearance_mm'],step['fixed_xyz_deg'])==('01_Edge_3-4',460,[-98.68,0,0])
    observation=config['observation_profile']
    assert observation['corner']==dict(enabled=False,std_mm=1,seed=0)
    assert observation['marker']['identity']['profile_hash']=='66ac8c6d2bcd9b531d532a23c2af7b04e72a7ae1ab1ae8aa8c0c8ec7ef77bafb'
    assert observation['marker']['faults']['kind'] is None
    assert observation['marker']['seed']==74082
    require_executable(config)


def test_modes_isolated_switch_save_reload_and_source_history(tmp_path):
    state=ModeProfiles();single=deepcopy(state.configs['single_drop'])
    single['sequence_profile']['steps'][0]['clearance_mm']=123
    single['sequence_profile']['steps'][0]['fixed_xyz_deg']=[20,35,-15]
    state.set_config(single)
    robot=state.switch('robot_sequence')
    robot['physics_profile']['mass_kg']=12
    robot['sequence_profile']['steps'].append(drop_step(robot['sequence_profile']['steps'][0]['category'],
        '08_Face_3_Screen_High',150,[0,0,17],step_id='drop-2'))
    state.set_config(robot)
    assert state.switch('single_drop')==single
    assert state.switch('robot_sequence')==robot
    previous=deepcopy(state.document());draft=deepcopy(robot);draft['physics_profile']['mass_kg']=99
    # Cancelling an isolated draft has no effect on either mode.
    assert state.document()==previous
    path=tmp_path/'profiles.json';save_profiles(path,state);reopened=read_profiles(path)
    assert reopened.document()==previous
    assert reopened.configs['robot_sequence']['sequence_profile']['steps'][1]['step_id']=='drop-2'
    assert reopened.history[0]['before']['sequence_profile']['steps'][0]['clearance_mm']==460
    assert reopened.history[0]['after']['sequence_profile']['steps'][0]['clearance_mm']==123
    assert reopened.document()['approval_status']=='not_evaluated'
    with pytest.raises(ValueError,match='#140'):require_executable(reopened.configs['robot_sequence'])


@pytest.mark.parametrize('mutation',[
    lambda c:c.update(mode='batch'),
    lambda c:c.update(schema_version=2),
    lambda c:c.update(plan_spec='wrong'),
    lambda c:c.update(size_mm=[200,float('nan'),80]),
    lambda c:c['physics_profile'].update(source=None),
    lambda c:c['physics_profile'].update(units='lb-inch'),
    lambda c:c['physics_profile'].update(mass_kg=float('inf')),
    lambda c:c['physics_profile'].update(mass_kg=True),
    lambda c:c['sequence_profile']['steps'][0].update(attitude_policy='body-local-radians'),
    lambda c:c['sequence_profile']['steps'][0].update(preset_id='unknown'),
    lambda c:c['sequence_profile']['steps'][0].update(fixed_xyz_deg=[0,0,float('nan')]),
    lambda c:c['observation_profile']['corner'].update(seed=True),
    lambda c:c['observation_profile']['marker']['identity'].update(geometry_hash='0'*64),
    lambda c:c['observation_profile']['marker']['faults'].update(kind='unknown'),
    lambda c:c['observation_profile']['marker']['faults'].update(kind='missing',start=.4,end=.3),
])
def test_invalid_configuration_rejected(mutation):
    config=default_config();mutation(config)
    with pytest.raises(ValueError):validate_config(config)


def test_source_and_current_identity_not_promoted_or_rewritten():
    state=ModeProfiles();document=state.document()
    document['configs']['single_drop']['physics_profile']['friction']=.6
    with pytest.raises(ValueError,match='Stale'):ModeProfiles.from_document(document)
    with pytest.raises(ValueError,match='history/current'):ModeProfiles.from_document(rehash(document))
    document=state.document();document.pop('source_configs')
    with pytest.raises(ValueError,match='source snapshots'):ModeProfiles.from_document(rehash(document))
    with pytest.raises(ValueError,match='schema'):ModeProfiles.from_document({'schema_version':0})


@pytest.mark.parametrize('failure',['write','fsync','replace'])
def test_atomic_profiles_failure_retry_preserves_file_and_state(tmp_path,monkeypatch,failure):
    import src.simulation.mode_profiles as module
    state=ModeProfiles();path=tmp_path/'profiles.json';path.write_bytes(b'previous result')
    snapshot=state.document()
    with monkeypatch.context() as patch:
        if failure=='write':patch.setattr(module,'canonical',lambda _:(_ for _ in ()).throw(OSError('write failed')))
        else:patch.setattr(module.os,failure,lambda *args:(_ for _ in ()).throw(OSError('I/O failed')))
        with pytest.raises(OSError):save_profiles(path,state)
    assert path.read_bytes()==b'previous result'
    assert state.document()==snapshot
    assert not list(tmp_path.glob('.bma-modes-*'))
    save_profiles(path,state)
    assert read_profiles(path).document()==snapshot
