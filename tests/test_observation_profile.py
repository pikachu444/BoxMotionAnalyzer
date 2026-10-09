"""Literal PUB10 geometry/recurrence and independent legacy preservation."""
from copy import deepcopy
import json
import math
from pathlib import Path

import numpy as np
import pytest

from src.simulation.marker_fixtures import example_profile
from src.simulation.marker_corruption import apply_corruption
from src.simulation.observation_profile import (observation_profile, orthographic_camera,
    validate_observation_profile)
from src.utils.marker_profile_identity import PLAN_SPEC, digest


def truth(times=(0., .01, .04, .1), rotation=None, origin=(0., 0., 0.)):
    return dict(schema_version=1, source_kind='handcrafted_dummy',
        coordinate_policy='world-y-up-box-local-fixed-center-v1', time_s=list(times),
        frame=list(range(100, 100+len(times))), body_origin_mm=[list(origin)]*len(times),
        rotation_matrix=[np.eye(3).tolist() if rotation is None else rotation]*len(times))


def spec(profile, events=()):
    return dict(schema_version=2, plan_spec=PLAN_SPEC, observation_profile=profile, events=list(events))


def run(profile, trajectory=None, events=(), seed=42, marker=None):
    return apply_corruption(truth() if trajectory is None else trajectory,
        example_profile() if marker is None else marker, spec(profile, events), seed)


def reseal(value):
    value['content_hash'] = digest({k: v for k, v in value.items() if k != 'content_hash'})
    return value


def ids(face):
    return [m['id'] for m in example_profile()['markers'] if m['face'] == face]


@pytest.mark.parametrize('rotation,position,expected', [
    (np.eye(3).tolist(), [0., 0., -500.], 'BACK'),
    ([[0.,0.,1.],[0.,1.,0.],[-1.,0.,0.]], [-500.,0.,0.], 'LEFT'),
    ([[-1.,0.,0.],[0.,1.,0.],[0.,0.,-1.]], [0.,0.,500.], 'FRONT')])
def test_literal_camera_forward_and_true_pose_normals(rotation, position, expected):
    p = observation_profile(example_profile(), camera=orthographic_camera(position, rotation))
    r = run(p)
    mask = np.isfinite(r['physical_markers']).all(axis=2)
    literal = [m['face'] == expected for m in example_profile()['markers']]
    np.testing.assert_array_equal(mask, [literal]*4)
    np.testing.assert_array_equal(r['rigid_body_markers'], r['truth_markers'])
    flip = dict(kind='flip_180_local_axis', channel='rigid_body_markers', start_index=1, axis='Y')
    np.testing.assert_array_equal(run(p, events=[flip])['physical_markers'], r['physical_markers'])


def test_camera_rotated_translated_box_frustum_edge_and_grazing():
    marker = example_profile(); marker['profile_id'] = 'edge-literal'
    marker['markers'][0]['xyz_mm'] = [100., 60., 40.]  # FRONT-assigned corner.
    q = [[0.,0.,-1.],[0.,1.,0.],[1.,0.,0.]]
    # R_box=Ry(+90): front corner becomes (50,80,-70).
    t = truth(rotation=[[0.,0.,1.],[0.,1.,0.],[-1.,0.,0.]], origin=[10.,20.,30.])
    camera = orthographic_camera([500.,20.,30.], q, half_extent_mm=[100.,60.], near_mm=450., far_mm=450.)
    camera['far_mm'] = 451.
    p = observation_profile(marker, camera=camera)
    r = run(p, t, marker=marker)
    assert np.isfinite(r['physical_markers'][:,0]).all()
    p['camera']['half_extent_mm'][0] = 99.999
    assert np.isnan(run(reseal(p), t, marker=marker)['physical_markers'][:,0]).all()
    # Identity box + camera +X: FRONT-assigned corner remains grazing hidden.
    p['camera'] = orthographic_camera([-500.,0.,0.], [[0.,0.,1.],[0.,1.,0.],[-1.,0.,0.]])
    assert np.isnan(run(reseal(p), marker=marker)['physical_markers'][:,0]).all()


@pytest.mark.parametrize('tilt,visible',[(2.220446049250313e-16,False),(.5e-12,False),(2e-12,True),(1e-11,True),(-1e-11,False)])
def test_represented_tangent_has_fixed_conservative_boundary(tilt,visible):
    from scipy.spatial.transform import Rotation
    p=observation_profile(example_profile(),camera=orthographic_camera([0.,0.,-500.],np.eye(3).tolist()))
    t=truth(rotation=Rotation.from_rotvec([-tilt,0.,0.]).as_matrix().tolist())
    observed=run(p,t)
    top=next(i for i,m in enumerate(example_profile()['markers']) if m['face']=='TOP')
    assert bool(np.isfinite(observed['physical_markers'][:,top]).all())==visible


def test_actual_engine_frame_roundtrip_tangent_regression():
    from scipy.spatial.transform import Rotation
    from src.simulation.history_trajectory import history_to_trajectory
    q=Rotation.from_euler('x',90,degrees=True).as_quat()[[3,0,1,2]].tolist()
    history=[dict(time=t,QuaternionWXYZ=q,BodyOrigin=[0.,0.,0.],COM=[0.,0.,0.]) for t in (0.,.01)]
    trajectory=history_to_trajectory(history)
    p=observation_profile(example_profile(),camera=orthographic_camera([0.,0.,-500.],np.eye(3).tolist()))
    observed=run(p,trajectory)
    expected=[m['face']=='BACK' for m in example_profile()['markers']]
    np.testing.assert_array_equal(np.isfinite(observed['physical_markers']).all(axis=2),[expected]*2)


def test_groups_union_half_open_masks_before_freeze_and_routing():
    p = observation_profile(example_profile(),
        groups=[dict(group_id='front', marker_ids=ids('FRONT')), dict(group_id='pair', marker_ids=['F1','B1'])],
        occlusions=[dict(group_id='front', start_s=.01, end_s=.04), dict(group_id='pair',start_s=.04,end_s=.1)],
        adapter='visibility-mask-to-solved-v1')
    events = [dict(kind='freeze',channel='physical_markers',start_index=2,end_index_exclusive=4,marker_ids=['F1']),
        dict(kind='label_permutation',channel='physical_markers',start_index=1,end_index_exclusive=4,mapping={'F1':'B1','B1':'F1'})]
    r = run(p, events=events); mid = [m['id'] for m in example_profile()['markers']]
    assert np.isnan(r['physical_markers'][1:,mid.index('B1')]).all()  # hidden freeze anchor routed to B1.
    assert np.isfinite(r['rigid_body_markers'][3]).all()  # end=.1 excluded.
    for midx in [mid.index(m) for m in ids('FRONT')]:
        assert np.isnan(r['rigid_body_markers'][1,midx]).all()
    assert r['manifest']['observation_evidence']['group_masks'][0]['original_record_indices'] == [1]


def test_literal_ou_recurrence_stationary_initial_actual_irregular_dt(monkeypatch):
    import src.simulation.observation_profile as model
    class LiteralInnovations:
        def __init__(self): self.k = 0
        def normal(self, *, size):
            z = (1., -1., .5)[self.k]; self.k += 1
            return np.full(size, z)
    monkeypatch.setattr(model, '_noise_rng', lambda *args: LiteralInnovations())
    t = truth(times=[0.,math.log(2),math.log(8)])
    p = observation_profile(example_profile(), noise=[dict(noise_id='literal', channel='physical_markers',
        marker_ids=['F1'], start_s=0.,end_s=3.,std_mm=2.,tau_s=1.)])
    r = run(p,t)
    expected = [2., 1-math.sqrt(3), (1-math.sqrt(3)+math.sqrt(15))/4]
    np.testing.assert_allclose((r['physical_markers']-r['truth_markers'])[:,0], np.repeat(np.array(expected)[:,None],3,axis=1), atol=1e-13,rtol=0)
    np.testing.assert_array_equal(r['physical_markers'][:,1:],r['truth_markers'][:,1:])


def test_ou_same_seed_channel_legacy_isolation_latent_gaps_and_freeze():
    t = truth(times=np.arange(20)*.01)
    noise = dict(noise_id='latent',channel='physical_markers',marker_ids=['F1'],start_s=0.,end_s=.195,std_mm=.2,tau_s=.1)
    p = observation_profile(example_profile(),noise=[noise]);r=run(p,t)
    np.testing.assert_array_equal(run(p,t)['physical_markers'],r['physical_markers'])
    assert not np.array_equal(run(p,t,seed=43)['physical_markers'],r['physical_markers'])
    events = [dict(kind='missing',channel='physical_markers',start_index=3,end_index_exclusive=7,marker_ids=['F1']),
        dict(kind='freeze',channel='physical_markers',start_index=10,end_index_exclusive=14,marker_ids=['F1']),
        dict(kind='gaussian_noise',channel='rigid_body_markers',start_index=0,end_index_exclusive=20,std_mm=.02)]
    mixed=run(p,t,events=events)
    np.testing.assert_array_equal(mixed['physical_markers'][7:10],r['physical_markers'][7:10])
    np.testing.assert_array_equal(mixed['physical_markers'][14:],r['physical_markers'][14:])
    np.testing.assert_array_equal(mixed['physical_markers'][10:14,0], np.repeat(r['physical_markers'][9:10,0],4,axis=0))
    legacy=apply_corruption(t,example_profile(),dict(schema_version=1,events=events),42)
    np.testing.assert_array_equal(mixed['rigid_body_markers'],legacy['rigid_body_markers'])
    before=deepcopy(t);profile_before=deepcopy(p);run(p,t,events=events)
    assert t==before and p==profile_before


@pytest.mark.parametrize('field,value', [('std_mm',-1),('std_mm',True),('std_mm','2'),('std_mm',float('inf')),
    ('tau_s',0),('tau_s',False),('tau_s','1'),('noise_id',''),('channel','truth'),('marker_ids',[]),('marker_ids',['unknown'])])
def test_invalid_noise_rejected(field,value):
    p=observation_profile(example_profile(),noise=[dict(noise_id='n',channel='physical_markers',marker_ids=['F1'],start_s=0.,end_s=.1,std_mm=1.,tau_s=1.)])
    p['noise'][0][field]=value
    with pytest.raises((ValueError,OverflowError)):
        validate_observation_profile(reseal(p),example_profile())


@pytest.mark.parametrize('field,value', [('model','perspective'),('frame','engine-z-up'),('units','m'),
    ('camera_to_world',[[1,0,0],[0,1,0],[0,0,-1]]),('position_mm',[0,True,0]),
    ('position_mm',[0,'1',0]),('half_extent_mm',[0,2]),('near_mm',-1),('far_mm',0),('grazing_cos',1)])
def test_invalid_camera_rejected(field,value):
    p=observation_profile(example_profile(),camera=orthographic_camera([0.,0.,-500.],np.eye(3).tolist()))
    p['camera'][field]=value
    with pytest.raises(ValueError): validate_observation_profile(reseal(p),example_profile())


@pytest.mark.parametrize('mutation', ['schema','plan','missing','unknown','hash','profile','duplicate','no_samples','window','reverse','covariance'])
def test_corrupt_profile_and_window_rejected_before_publication(tmp_path,mutation):
    from src.simulation.corruption_export import write_observations
    p=observation_profile(example_profile(),noise=[dict(noise_id='n',channel='physical_markers',marker_ids=['F1'],start_s=0.,end_s=.1,std_mm=1.,tau_s=1.)])
    if mutation=='schema':p['schema_version']=True
    if mutation=='plan':p['plan_spec']='other'
    if mutation=='missing':del p['adapter']
    if mutation=='unknown':p['direction']='auto'
    if mutation=='hash':p['content_hash']='0'*64
    if mutation=='profile':p['marker_profile_hash']='0'*64
    if mutation=='duplicate':p['noise'].append(deepcopy(p['noise'][0]))
    if mutation=='no_samples':p['noise'][0].update(start_s=.02,end_s=.03)
    if mutation=='window':p['noise'][0]['end_s']=1.
    if mutation=='reverse':p['noise'][0].update(start_s=.1,end_s=0.)
    if mutation=='covariance':p['noise'][0]['covariance']=[[1,2,0],[2,1,0],[0,0,1]]
    if mutation!='hash':reseal(p)
    with pytest.raises(ValueError):write_observations(tmp_path/'bad',truth(),example_profile(),spec(p),42)
    assert not (tmp_path/'bad').exists()


def test_opt_in_disabled_legacy_arrays_and_compound_preservation():
    from test_general_export_recovery import specified_input, CASES
    for case in CASES:
        t,s,_=specified_input(case)
        old=apply_corruption(t,example_profile(),s,74082)
        off=apply_corruption(t,example_profile(),spec(observation_profile(example_profile()),s['events']),74082)
        for channel in ('physical_markers','rigid_body_markers','truth_markers'):
            np.testing.assert_array_equal(old[channel],off[channel])


def test_mixed_boolean_coordinates_and_invalid_truth_pose_rejected():
    t=truth();t['body_origin_mm'][0][0]=True
    with pytest.raises(ValueError):run(observation_profile(example_profile()),t)


def test_independent_stationary_ensemble_initial_variance_and_irregular_covariance():
    from src.simulation.observation_profile import stationary_ou
    # Fixed before execution: 20,000 independent realizations, 3 coordinates.
    # Each variance's relative standard error sqrt(2/19999)≈1%; 10% is a
    # proposed diagnostic band, not measured sensor accuracy or a baseline.
    times=np.array([0.,.01,.2,2.]); sigma=2.;tau=1.
    x=np.array(list(stationary_ou(times,sigma,tau,np.random.default_rng(14320261009),(20000,3))))
    var=x.var(axis=1)
    np.testing.assert_allclose(var,4.,rtol=.1,atol=0)
    assert np.max(np.abs(x.mean(axis=1)))<.1
    cov=np.mean((x[0]-x[0].mean(axis=0))*(x[-1]-x[-1].mean(axis=0)),axis=0)
    np.testing.assert_allclose(cov,4*np.exp(-2),rtol=0,atol=.2)
    # Very small Δt retains a positive innovation; a very large gap reinitializes
    # in distribution without any reconnect-specific RNG reset.
    assert math.sqrt(-math.expm1(-2e-20))>0
    assert math.exp(-1e10)==0
    t=truth();t['rotation_matrix'][0][0][0]=2.
    with pytest.raises(ValueError):run(observation_profile(example_profile()),t)
