"""Independent literals, analytic physics and source/metadata failure controls."""
from copy import deepcopy
import json

import mujoco
import numpy as np
import pytest
from scipy.spatial.transform import Rotation

from src.simulation.initial_conditions import (initial_condition, contact_profile, configured,
    engine_from_config, validate_seed, validate_profile, validate_compiled, reseal, load)
from src.simulation.mode_profiles import default_config, validate_config, ModeProfiles
from src.simulation.engine.mujoco_engine import MuJoCoEngine
from src.simulation.contact_evaluation import evaluate_contacts, load_evaluation, save_document, validate_recording
from src.simulation.contact_policy import event_policy
from src.simulation.history_trajectory import history_to_trajectory, WORLD_TRANSFORM
from src.utils.simulation_metadata import build_metadata, validate_full, validate_public, compatibility_reasons
from src.utils.marker_profile_identity import digest


def config(seed=None, profile=None):
    c=default_config();c['size_mm']=[200.,120.,80.];c['show_viewer']=False;c['duration_s']=.5
    return configured(c,seed or initial_condition([200.,-100.,3000.]),profile or contact_profile())


def velocity(e, point):
    jp=np.zeros((3,e.model.nv));jr=jp.copy()
    mujoco.mj_jac(e.model,e.data,jp,jr,point,1)
    return jp@e.data.qvel*1000,jr@e.data.qvel


@pytest.mark.parametrize('linear_frame,angular_frame,point',[('world','world','body_origin'),('body','body','com'),('world','body','com'),('body','world','body_origin')])
def test_literal_nonzero_com_point_and_frames(linear_frame,angular_frame,point):
    q=[2**-.5,0.,0.,2**-.5]
    # +90 Z: R*c=[4,3,2], omega_world=[-2,1,3], w cross R*c=[-7,16,-10].
    v=[93.,216.,290.] if point=='com' else [100.,200.,300.]
    if linear_frame=='body':v=[v[1],-v[0],v[2]]
    w=[1.,2.,3.] if angular_frame=='body' else [-2.,1.,3.]
    seed=initial_condition([204.,-97.,3002.],q,position_reference='com',linear_velocity=v,
        linear_velocity_reference=point,linear_velocity_frame=linear_frame,angular_velocity=w,angular_velocity_frame=angular_frame)
    e=engine_from_config(config(seed,contact_profile(com_offset_mm=[3.,-4.,2.],
        inertia=dict(kind='principal-about-COM',principal_kg_m2=[.02,.03,.04],quaternion_wxyz=[2**-.5,2**-.5,0.,0.]))));e.build()
    np.testing.assert_allclose(e.data.xpos[1]*1000,[200.,-100.,3000.],atol=1e-10,rtol=0)
    vo,wo=velocity(e,e.data.xpos[1]);vc,_=velocity(e,e.data.xipos[1])
    np.testing.assert_allclose(vo,[100.,200.,300.],atol=1e-10,rtol=0)
    np.testing.assert_allclose(wo,[-2.,1.,3.],atol=1e-10,rtol=0)
    np.testing.assert_allclose(vc,[93.,216.,290.],atol=1e-10,rtol=0)
    assert np.linalg.norm(e.data.xpos[1]-e.data.xipos[1])>0


@pytest.mark.parametrize('spin',[0.,2.])
def test_ballistic_spherical_spin_corners_and_actual_output_clock(spin):
    # Spin around Z with spherical inertia; COM independent ballistic solution.
    offset=[30.,0.,0.];p=contact_profile(com_offset_mm=offset,timestep_s=.001,
        inertia=dict(kind='principal-about-COM',principal_kg_m2=[.02,.02,.02],quaternion_wxyz=[1.,0.,0.,0.]))
    s=initial_condition([0.,0.,3000.],linear_velocity=[100.,0.,200.],angular_velocity=[0.,0.,spin],reference_time_s=40.)
    e=engine_from_config(config(s,p));h=e.record_samples(101,1);times=np.array([x['time'] for x in h])
    expected=np.array([30.,0.,3000.])+times[:,None]*[100.,30*spin,200.]+times[:,None]**2*[0.,0.,-4905.]
    # Euler ballistic truncation is +g*dt*t/2 in magnitude; test analytic discretization too.
    expected[:,2]-=4905.*.001*times
    np.testing.assert_allclose(np.array([x['COM'] for x in h]),expected,atol=.01,rtol=0)
    r=Rotation.from_rotvec(times[:,None]*[0.,0.,spin]).as_matrix()
    np.testing.assert_allclose(np.array([x['RotationMatrix'] for x in h]),r,atol=1e-9,rtol=0)
    local=np.array([[-100.,-60.,-40.],[100.,-60.,-40.],[100.,60.,-40.],[-100.,60.,-40.],[-100.,-60.,40.],[100.,-60.,40.],[100.,60.,40.],[-100.,60.,40.]])
    for row in h:
        expected_corners=(local-np.array(offset))@row['RotationMatrix'].T+row['COM']
        np.testing.assert_allclose([row[f'C{i}'] for i in range(1,9)],expected_corners,atol=1e-9,rtol=0)
    out=history_to_trajectory(h)
    assert out['time_s'][-1]==h[-1]['time'] and out['time_s'][0]==0
    np.testing.assert_allclose(out['body_origin_mm'],np.array([x['BodyOrigin'] for x in h])@WORLD_TRANSFORM.T,atol=1e-10)


def test_sign_and_world_body_equivalence_and_running_setter_block():
    r=Rotation.from_euler('xyz',[23.,-31.,47.],degrees=True);q=r.as_quat()[[3,0,1,2]]
    states=[]
    for sign,frame in ((1,'world'),(-1,'world'),(1,'body')):
        v=np.array([120.,230.,340.]);w=np.array([.4,.5,.6])
        if frame=='body':v=r.inv().apply(v);w=r.inv().apply(w)
        e=engine_from_config(config(initial_condition([100.,0.,3000.],sign*q,linear_velocity=v,
            angular_velocity=w,linear_velocity_frame=frame,angular_velocity_frame=frame)))
        h=e.record_samples(11,1);states.append(h)
        with pytest.raises(ValueError):e.set_initial_condition(initial_condition([0,0,4000]))
    for h in states[1:]:
        np.testing.assert_allclose([x['BodyOrigin'] for x in h],[x['BodyOrigin'] for x in states[0]],atol=1e-9)
        np.testing.assert_allclose([x['RotationMatrix'] for x in h],[x['RotationMatrix'] for x in states[0]],atol=1e-10)


@pytest.mark.parametrize('field,value',[('schema_version',2),('plan_spec','wrong'),('linear_velocity_frame','inertial'),('units',{'position':'m'}),
    ('quaternion_wxyz',[0.,0.,0.,0.]),('quaternion_wxyz',[2.,0.,0.,0.]),('reference_time_s',float('inf')),('prehistory','complete'),('position_reference','corner')])
def test_bad_seed_contract(field,value):
    s=initial_condition([0,0,1000]);s[field]=value
    with pytest.raises(ValueError):validate_seed(reseal(s))


@pytest.mark.parametrize('change',[{'condim':5},{'geometry':'rounded-box'},{'solref':[-1000.,-2.]},{'solref':[.001,1.]},
    {'friction':[.5,-.1,0.]},{'solimp':[.9,1.5,.001,.5,2.]},{'mass_kg':0.},
    {'inertia':dict(kind='principal-about-COM',principal_kg_m2=[.1,.01,.01],quaternion_wxyz=[1.,0.,0.,0.])},
    {'inertia':dict(kind='principal-about-COM',principal_kg_m2=[0.,.03,.03],quaternion_wxyz=[1.,0.,0.,0.])},
    {'calibration_status':'calibrated'}])
def test_invalid_contact_parameters(change):
    p=contact_profile();p.update(change)
    with pytest.raises(ValueError):validate_profile(reseal(p))


@pytest.mark.parametrize('condim',[3,4,6])
def test_actual_combined_contact_and_compiled_drift(condim):
    p=contact_profile(condim=condim,margin_mm=dict(box=2.,floor=1.),friction=[.3,.02,.004])
    e=engine_from_config(config(initial_condition([0,0,40.]),p));e.enable_contact_recording({'id':'effective-parameters'})
    e.record_samples(3,1);d=e.contact_recorder.document();validate_recording(d)
    contact=d['samples'][0]['contacts'][0]['effective_parameters']
    assert contact['condim']==condim and contact['inclusion_margin_mm']==3
    assert contact['friction']==[.3,.3,.02,.004,.004]
    e.model.opt.cone=1
    with pytest.raises(ValueError,match='compiled'):validate_compiled(e)


@pytest.mark.parametrize('field,value',[('mass_kg',True),('mass_kg','1'),('gravity_m_s2',[False,0.,-9.81]),
    ('reference_safety_clamp_enabled',1),('cone',False)])
def test_compiled_numeric_and_boolean_declarations_have_strict_types(field,value):
    from src.simulation.initial_conditions import compiled_settings,validate_compiled_values
    profile=contact_profile();e=engine_from_config(config(profile=profile));e.build()
    actual=compiled_settings(e);actual[field]=value
    with pytest.raises(ValueError):validate_compiled_values(profile,actual,[200.,120.,80.])


def test_precontact_unknown_ordinals_and_saved_evaluation(tmp_path):
    s=initial_condition([0,0,140.],mode='precontact',linear_velocity=[0.,0.,-50.],reference_time_s=1.5)
    e=engine_from_config(config(s));e.enable_contact_recording({'id':'precontact'})
    e.record_samples(251,1);d=e.contact_recorder.document();v=evaluate_contacts(d,event_policy())
    assert any(x['kind']=='visible_floor_impact' for x in v['events'])
    assert not any(x['kind']=='first_floor_impact' for x in v['events'])
    assert v['t1']['status']==v['t2']['status']=='unavailable'
    assert 'prehistory' in v['t1']['reason']
    save_document(tmp_path/'evaluation.json',v);assert digest(load_evaluation(tmp_path/'evaluation.json',event_policy(),d))==digest(v)


def test_full_metadata_reopen_source_seed_binding_and_truth_allowlist(tmp_path):
    c=config(initial_condition([150.,0.,3000.],linear_velocity=[100.,200.,300.]),contact_profile(condim=6))
    e=engine_from_config(c);h=e.record_samples(11,4);m=build_metadata(c,e,h,route='direct_proc',run_id='explicit-state')
    path=tmp_path/'metadata.json';save_document(path,m);assert load(path,validate_full)==m
    assert m['public']['generator']['version']=='pub09-explicit-state-v1'
    assert 'linear_velocity' not in json.dumps(m['public']['configuration']['initial_condition'])
    bad=deepcopy(m);bad['release_state']['origin_linear_velocity_world'][0]+=1
    with pytest.raises(ValueError,match='seed state'):validate_full(reseal(bad))
    bad=deepcopy(m['public']);bad['configuration']['initial_condition']['linear_velocity']=[1,2,3]
    bad['configuration_hash']=digest(bad['configuration'])
    with pytest.raises(ValueError,match='truth'):validate_public(reseal(bad))
    changed=deepcopy(c);changed['initial_condition']['reference_time_s']=2.;changed['initial_condition']=reseal(changed['initial_condition'])
    with pytest.raises(ValueError,match='identity'):build_metadata(changed,e,h,route='direct_proc',run_id='stale')
    p=ModeProfiles();p.set_config(c);assert ModeProfiles.from_document(p.document()).configs['single_drop']==c


def test_opt_ins_cannot_be_applied_to_robot_and_default_xml_unchanged():
    c=default_config('robot_sequence');c['initial_condition']=initial_condition([0,0,1000])
    with pytest.raises(ValueError):validate_config(c)
    e=MuJoCoEngine();assert e.initial_condition is None and e.contact_profile is None
    assert 'alignfree' not in e._generate_xml() and 'timestep="0.002"' in e._generate_xml()


def test_json_nonfinite_and_stale_profile(tmp_path):
    path=tmp_path/'invalid.json';path.write_text('{"value":NaN}',encoding='utf-8')
    with pytest.raises(ValueError,match='Nonfinite'):load(path,lambda v:v)
    p=contact_profile();p['friction'][0]=.8
    with pytest.raises(ValueError,match='Stale'):validate_profile(p)


def test_anisotropic_free_spin_uses_conservation_not_constant_omega():
    # Analytical invariants for torque-free motion: world angular momentum and
    # rotational energy. Euler has truncation; these bounds are diagnostic only.
    inertia=dict(kind='principal-about-COM',principal_kg_m2=[.02,.03,.04],quaternion_wxyz=[1.,0.,0.,0.])
    e=engine_from_config(config(initial_condition([0.,0.,3000.],angular_velocity=[.3,-.4,1.2]),
        contact_profile(inertia=inertia,timestep_s=.0005)))
    h=e.record_samples(401,1);omega=e.data.qvel[3:6];r=e.data.xmat[1].reshape(3,3)
    initial=np.array([.3,-.4,1.2]);moments=np.array([.02,.03,.04])
    np.testing.assert_allclose(r@(moments*omega),moments*initial,atol=2e-5,rtol=0)
    assert abs(.5*np.sum(moments*omega**2)-.5*np.sum(moments*initial**2))<2e-5
    assert np.linalg.norm(r@omega-initial)>.02


def test_existing_marker_producer_honors_opt_in_configuration(tmp_path):
    from src.simulation.marker_export import generate_marker_capture
    from src.simulation.marker_fixtures import load_profile
    from src.utils.marker_profile_identity import profile_identity
    from src.analysis.pipeline.data_loader import DataLoader
    c=config(initial_condition([150.,0.,3000.],linear_velocity=[100.,0.,0.]),contact_profile(condim=6))
    marker=load_profile();c['observation_profile']['marker'].update(profile=marker,identity=profile_identity(marker))
    p=c['physics_profile'];step=c['sequence_profile']['steps'][0];obs=c['observation_profile']['marker']
    params=dict(mode_config=c,mass=p['mass_kg'],friction=p['friction'],elasticity=p['contact_damping_control'],
        com_offset=p['com_offset_mm'],duration=c['duration_s'],height=step['clearance_mm'],
        quat=c['initial_condition']['quaternion_wxyz'],run_id='explicit-marker-source')
    csv=generate_marker_capture(tmp_path/'capture',marker,params,obs['faults'],obs['seed'])
    manifest=json.loads((tmp_path/'capture'/'observed.synthetic.json').read_text(encoding='utf-8'))
    m=validate_full(manifest['simulation_metadata'])
    assert m['source_configuration']['initial_condition']==c['initial_condition']
    assert m['compiled_physics']['explicit_profile']['contacts']['box']['condim']==6
    header,raw=DataLoader().load_csv(csv)
    assert len(raw)>50 and header['artifact_metadata']['SourceKind']=='mujoco_synthetic'
@pytest.mark.parametrize('factory',[
    lambda:initial_condition([0.,0.,1000.],input_source={}),
    lambda:contact_profile(inertia={}),lambda:contact_profile(margin_mm={}),
    lambda:initial_condition([True,0.,1000.]),lambda:initial_condition(['1',0.,1000.]),
    lambda:contact_profile(mass_kg='1'),lambda:contact_profile(solref=(.02,True))])
def test_explicit_invalid_declarations_never_invent_defaults(factory):
    with pytest.raises(ValueError):factory()
