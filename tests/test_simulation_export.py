"""Analytic and bounded MuJoCo export contracts, not real-impact validation."""
import copy
import json
import numpy as np
import pandas as pd
import pytest
from scipy.spatial.transform import Rotation as R
from src.simulation.data_exporter import DataExporter, WORLD_TRANSFORM as A
from src.simulation.engine.mujoco_engine import MuJoCoEngine
from src.analysis.pipeline.data_loader import DataLoader
from src.utils.artifact_metadata import read_identity
from src.visualization.data_handler import DataHandler
from src.config import config_visualization as visual_config

CORNERS = np.array([[-1,-1,-1],[1,-1,-1],[1,1,-1],[-1,1,-1],
                    [-1,-1,1],[1,-1,1],[1,1,1],[-1,1,1]]) * [100,60,40]


def history(times, rotations=None):
    times = np.asarray(times)
    rotations = rotations if rotations is not None else R.from_euler('z', np.zeros(len(times)))
    result=[]
    for i,t in enumerate(times):
        p = np.array([10 + 3*t + 2*t*t, 20., 500.])
        q = rotations[i].as_quat()[[3,0,1,2]]
        row = dict(time=t, Center=p.copy(), BodyOrigin=p.copy(), COM=p+rotations[i].apply([3,-4,2]),
                   QuaternionWXYZ=q, RotationMatrix=rotations[i].as_matrix())
        row.update({f'C{j+1}':p+rotations[i].apply(c) for j,c in enumerate(CORNERS)})
        result.append(row)
    return result


def vector(df,group,entity,keys):
    return df.loc[:,[(group,entity,k) for k in keys]].to_numpy(dtype=float)


def load(path):
    return DataLoader().load_result_csv(str(path))


@pytest.mark.parametrize('axis',['x','y','z'])
def test_irregular_time_angular_and_linear_motion(axis):
    t=np.array([0.,.03,.08,.2,.35])
    omega=.8
    data=DataExporter(history(t,R.from_euler(axis,omega*t))).calculate_derivatives()
    expected=A @ (np.eye(3)['xyz'.index(axis)]*omega)
    np.testing.assert_allclose(data['omega'][1:],np.tile(expected,(4,1)),atol=1e-13)
    np.testing.assert_allclose(data['alpha'][2:],0,atol=1e-12)
    np.testing.assert_allclose(data['Center'][1][1:,0],3+2*(t[:-1]+t[1:]),atol=1e-10)
    np.testing.assert_allclose(data['Center'][2][2:,0],4,atol=1e-9)
    assert np.isnan(data['omega'][0]).all() and np.isnan(data['alpha'][:2]).all()
    assert np.isnan(data['Center'][1][0]).all() and np.isnan(data['Center'][2][:2]).all()


@pytest.mark.parametrize('angles',[[0,0,0],[90,0,0],[0,180,0],[0,0,90],[23,-47,81]])
def test_known_composite_pose_corners_and_com_roundtrip(tmp_path,angles):
    rotations=R.from_euler('xyz',[angles]*3,degrees=True)
    raw=history([0,.01,.04],rotations)
    path=tmp_path/'pose.proc'
    DataExporter(raw).export_proc_csv(path)
    df=load(path)
    exported=R.from_rotvec(vector(df,'Position','CoM',['P_RX','P_RY','P_RZ']))
    np.testing.assert_allclose(exported.as_matrix(),A @ rotations.as_matrix(),atol=1e-14)
    center=vector(df,'Position','CoM',['P_TX','P_TY','P_TZ'])
    for j,c in enumerate(CORNERS,1):
        saved=vector(df,'Position',f'C{j}',['P_TX','P_TY','P_TZ'])
        np.testing.assert_allclose(saved,center+exported.apply(c),atol=1e-10)
    np.testing.assert_allclose(vector(df,'Simulation','InertialCOM',['X_mm','Y_mm','Z_mm']),
                               center+exported.apply([3,-4,2]),atol=1e-10)
    q=vector(df,'Simulation','BodyPose',['QW','QX','QY','QZ'])
    np.testing.assert_allclose(np.linalg.norm(q,axis=1),1,atol=1e-14)
    np.testing.assert_allclose(R.from_quat(q[:,[1,2,3,0]]).as_matrix(),exported.as_matrix(),atol=1e-14)
    assert read_identity(df).values['SourceKind']=='mujoco_synthetic'
    assert read_identity(df).exclusion_reasons()  # no invented real/Analysis identity
    handler=DataHandler()
    assert handler.load_analysis_result(str(path)) and len(handler.object_ids)==9


def test_quaternion_sign_flip_stationary_and_multiturn():
    t=np.arange(25)*.1
    raw=history(t,R.from_euler('z',np.arange(25)*30,degrees=True))
    for row in raw[::2]:
        row['QuaternionWXYZ'] *= -7
    data=DataExporter(raw).calculate_derivatives()
    np.testing.assert_allclose(data['omega'][1:],np.tile([0,np.deg2rad(300),0],(24,1)),atol=1e-12)
    assert np.all(np.sum(data['quaternion'][1:]*data['quaternion'][:-1],axis=1)>=0)
    stationary=history([0,.01,.2])
    for row in stationary:
        row['BodyOrigin']=stationary[0]['BodyOrigin'].copy()
        for i in range(1,9): row[f'C{i}']=stationary[0][f'C{i}'].copy()
    stationary[1]['QuaternionWXYZ'] *= -1
    output=DataExporter(stationary).calculate_derivatives()
    np.testing.assert_allclose(output['omega'][1:],0,atol=1e-14)
    np.testing.assert_allclose(output['Center'][1][1:],0,atol=1e-14)


@pytest.mark.parametrize('times',[[0,0],[1,0],[0,np.nan],[0,np.inf],[-1e308,1e308]])
def test_invalid_time_rejected_without_touching_existing_file(tmp_path,times):
    raw=history([0,.1])
    for frame,t in zip(raw,times): frame['time']=t
    path=tmp_path/'keep.proc'
    path.write_text('existing')
    with pytest.raises(ValueError,match='strictly increasing'):
        DataExporter(raw).export_proc_csv(path)
    assert path.read_text()=='existing'


def test_empty_and_single_sample_are_explicit(tmp_path):
    with pytest.raises(ValueError, match='empty'):
        DataExporter([]).export_proc_csv(tmp_path/'empty.proc')
    raw=history([0.])
    result=DataExporter(raw).calculate_derivatives()
    assert np.isfinite(result['rotation']).all()
    assert np.isnan(result['omega']).all() and np.isnan(result['alpha']).all()
    assert np.isnan(result['Center'][1]).all()
    raw[0]['QuaternionWXYZ'][:]=0
    with pytest.raises(ValueError, match='nonzero norm'):
        DataExporter(raw).calculate_derivatives()


@pytest.mark.parametrize('count', [1, 2, 63])
def test_exported_unavailable_norms_survive_visualization(tmp_path, count):
    path=tmp_path/'short.proc'
    DataExporter(history(np.arange(count)*.008)).export_proc_csv(path)
    frame=load(path)
    handler=DataHandler()
    assert handler.load_analysis_result(str(path))
    for entity in ['CoM']+[f'C{i}' for i in range(1,9)]:
        series=handler.get_entity_timeseries(visual_config.ENTITY_ID_COM if entity=='CoM' else entity)
        for group,key in [('Velocity','Global_V_T_Norm'),('Acceleration','Global_A_T_Norm')]:
            expected=frame[(group,entity,key)].to_numpy()
            assert np.isnan(expected[:1 if group=='Velocity' else 2]).all()
            np.testing.assert_array_equal(series[key].to_numpy(),expected)


@pytest.mark.parametrize('group,prefix', [('Velocity','V'),('Acceleration','A')])
@pytest.mark.parametrize('frame_prefix', ['Global', 'BoxLocal'])
@pytest.mark.parametrize('declared', [True, False])
def test_legacy_norm_fallback_requires_missing_column_and_finite_xyz(tmp_path, group, prefix, frame_prefix, declared):
    path=tmp_path/'legacy.proc'
    DataExporter(history([0,.1,.2,.3])).export_proc_csv(path)
    frame=load(path)
    norm=f'{frame_prefix}_{prefix}_T_Norm'
    components=[f'{frame_prefix}_{prefix}_T{axis}' for axis in 'XYZ']
    for key,values in zip(components,[[3.,np.nan,3.,3.],[4.,4.,np.inf,'bad'],[0.,0.,0.,0.]]):
        frame[(group,'CoM',key)]=values
    if declared:
        frame[(group,'CoM',norm)]=np.nan
    else:
        frame=frame.drop(columns=[(group,'CoM',norm)],errors='ignore')
    frame.to_csv(path,index=False)
    handler=DataHandler()
    assert handler.load_analysis_result(str(path))
    actual=handler.get_entity_timeseries(visual_config.ENTITY_ID_COM)[norm].to_numpy()
    np.testing.assert_array_equal(actual,[np.nan]*4 if declared else [5.,np.nan,np.nan,np.nan])


def test_repeat_export_no_mutation_and_seeded_observation_derivatives(tmp_path):
    raw=history([0,.01,.03,.06])
    original=copy.deepcopy(raw)
    exporter=DataExporter(raw)
    paths=[tmp_path/f'{i}.proc' for i in range(3)]
    exporter.export_proc_csv(paths[0]); exporter.export_proc_csv(paths[1])
    DataExporter(raw).export_proc_csv(paths[2])
    assert paths[0].read_bytes()==paths[1].read_bytes()==paths[2].read_bytes()
    for expected,actual in zip(original,raw):
        assert expected.keys()==actual.keys()
        for key in expected: np.testing.assert_array_equal(expected[key],actual[key])
    a=DataExporter(raw,True,1.,seed=12).calculate_derivatives()
    b=DataExporter(raw,True,1.,seed=12).calculate_derivatives()
    c=DataExporter(raw,True,1.,seed=13).calculate_derivatives()
    np.testing.assert_array_equal(a['C1'][0],b['C1'][0])
    assert not np.array_equal(a['C1'][0],c['C1'][0])
    np.testing.assert_allclose(a['C1'][1][1:],np.diff(a['C1'][0],axis=0)/np.diff(a['time'])[:,None])
    dt=np.diff(a['time'])
    np.testing.assert_allclose(a['C1'][2][2:],np.diff(a['C1'][1][1:],axis=0)/((dt[:-1]+dt[1:])/2)[:,None])
    np.testing.assert_array_equal(a['Center'][0],exporter.calculate_derivatives()['Center'][0])
    path=tmp_path/'noise.proc'
    noisy=DataExporter(raw,True,1.,seed=12)
    noisy.export_proc_csv(path)
    first=path.read_bytes(); noisy.export_proc_csv(path)
    assert path.read_bytes()==first
    settings=json.loads(load(path)[('Info','Simulation','SettingsJson')].iloc[0])
    assert settings['corner_noise']['seed']==12
    assert 'noisy-corner' in load(path)[('Info','Simulation','Representation')].iloc[0]
    for expected,actual in zip(original,raw):
        for key in expected: np.testing.assert_array_equal(expected[key],actual[key])


def test_actual_mujoco_nonzero_com_pose_roundtrip(tmp_path):
    engine=MuJoCoEngine(size=(200,120,80),mass=1,com_offset=(3,-4,2))
    engine.set_initial_state(300,R.from_euler('xyz',[20,35,-15],degrees=True).as_quat()[[3,0,1,2]])
    engine.build()
    engine.data.qvel[3:6]=[.5,.2,-.3]
    raw=engine.record_samples(samples=15,substeps=4)
    path=tmp_path/'mujoco.proc'
    DataExporter.from_engine(raw,engine,{'duration':.12,'add_noise':False,'noise_std':1.}).export_proc_csv(path)
    df=load(path)
    np.testing.assert_allclose(df[('Info','Time','Time')],[row['time'] for row in raw],atol=1e-15)
    center=vector(df,'Position','CoM',['P_TX','P_TY','P_TZ'])
    rotation=R.from_rotvec(vector(df,'Position','CoM',['P_RX','P_RY','P_RZ']))
    np.testing.assert_allclose(rotation.as_matrix(),A @ np.array([r['RotationMatrix'] for r in raw]),atol=1e-14)
    for j,c in enumerate(CORNERS,1):
        np.testing.assert_allclose(vector(df,'Position',f'C{j}',['P_TX','P_TY','P_TZ']),center+rotation.apply(c),atol=1e-10)
    com=vector(df,'Simulation','InertialCOM',['X_mm','Y_mm','Z_mm'])
    np.testing.assert_allclose(com,center+rotation.apply([3,-4,2]),atol=1e-10)
    assert np.max(np.linalg.norm(com-center,axis=1))>5
    assert read_identity(df).values['BoxLengthMm']==200
    assert np.linalg.norm(vector(df,'Velocity','CoM',['Global_V_RX','Global_V_RY','Global_V_RZ'])[1:])>0
