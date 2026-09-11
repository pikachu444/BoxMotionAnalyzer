"""Configured-object/hash unit contracts; actual execution is checked by collision GUI."""
import copy
import json
import pandas as pd
import pytest

from comparison_fixtures import write_proc, identity
from src.analysis.pipeline.pipeline_controller import PipelineController
from src.analysis.pipeline.processing_provenance import capture_single_pass, capture_postprocess
from src.analysis.pipeline.artifact_io import add_timeline_context_columns, save_proc_file
from src.analysis.pipeline.data_loader import DataLoader
from src.utils.artifact_metadata import read_identity, compatibility_reasons
from src.utils.processing_settings import processing_record, SETTINGS_ATTR


def configured_record(options=None, threshold=1., *, factor=1, trimming='late', padding=15):
    controller = PipelineController()
    controller.smoother.configure(options)
    controller.velocity_calculator.configure(options)
    return {
        'single_pass': capture_single_pass(controller, trimming_strategy=trimming,
                                            padding_frames=padding, filter_by='time'),
        'result_resampling': {'enabled': factor > 1, 'factor': factor} if factor > 1 else {'enabled': False},
        'postprocess': capture_postprocess(controller.drop_posture_post_processor, threshold),
    }


@pytest.mark.parametrize('options,extra', [
    ({'enable_marker_smoothing': False}, {}),
    ({'marker_butterworth_cutoff_hz': 9.}, {}),
    ({'marker_butterworth_order': 3}, {}),
    ({'marker_moving_average_window': 5}, {}),
    ({'velocity_method': 'finite_difference'}, {}),
    ({'acceleration_method': 'finite_difference'}, {}),
    ({'use_pose_lowpass_filter': True}, {}),
    ({'pose_moving_average_window': 5}, {}),
    ({'use_velocity_lowpass_filter': True}, {}),
    ({'use_acceleration_lowpass_filter': True}, {}),
    ({'spline_s_factor_position': .02}, {}),
    ({'spline_s_factor_rotation': .002}, {}),
    ({'spline_degree': 2}, {}),
    ({}, {'threshold':20.}),
    ({}, {'factor':2}),
    ({}, {'trimming':'early'}),
    ({}, {'padding':0}),
])
def test_executed_settings_identity_changes_with_active_policy(tmp_path, options, extra):
    first = write_proc(tmp_path / 'base.proc', settings=configured_record())
    second = write_proc(tmp_path / 'changed.proc', settings=configured_record(options, **extra))
    a = read_identity(DataLoader().load_result_csv(str(first)))
    b = read_identity(DataLoader().load_result_csv(str(second)))
    assert not a.exclusion_reasons() and not b.exclusion_reasons()
    assert any('ProcessingSemanticsVersion' in reason for reason in compatibility_reasons(a,b))


def test_inactive_settings_and_trial_times_do_not_change_signature(tmp_path):
    baseline = configured_record({'use_pose_lowpass_filter':False})
    inactive_change = configured_record({'use_pose_lowpass_filter':False, 'pose_lpf_cutoff_hz':99.})
    assert processing_record(baseline) == processing_record(inactive_change)
    a = read_identity(DataLoader().load_result_csv(str(write_proc(tmp_path/'a.proc', settings=baseline))))
    b = read_identity(DataLoader().load_result_csv(str(write_proc(tmp_path/'b.proc', times=(10,10.007,10.02),t1=10.007,settings=inactive_change))))
    assert compatibility_reasons(a,b) == []


def test_raw_declaration_cannot_replace_missing_execution_record():
    version, settings = processing_record(configured_record())
    raw_claim = identity(ProcessingSemanticsVersion=version, ProcessingSettingsJson=settings)
    result = add_timeline_context_columns(pd.DataFrame({'Frame':[1]}), {'artifact_metadata':raw_claim})
    assert result['Artifact_ProcessingSemanticsVersion'].isna().all()
    assert result['Artifact_ProcessingSettingsJson'].isna().all()


@pytest.mark.parametrize('kind',['missing','hash','nonconstant','noncanonical','incomplete'])
def test_invalid_processing_record_cannot_be_compatible(tmp_path,kind):
    path = write_proc(tmp_path/'bad.proc', settings=configured_record())
    frame = pd.read_csv(path,header=[0,1,2])
    column = ('Info','Artifact','ProcessingSettingsJson')
    if kind == 'missing':
        frame = frame.drop(columns=[column])
    elif kind == 'hash':
        frame[('Info','Artifact','ProcessingSemanticsVersion')] = 'analysis-face-v3-time-v2:sha256:'+'0'*64
    elif kind == 'nonconstant':
        frame.loc[0,column] = '{}'
    elif kind == 'noncanonical':
        frame[column] = json.dumps(json.loads(frame[column].iloc[0]),indent=2)
    else:
        frame[column] = '{}'
    frame.to_csv(path,index=False)
    assert read_identity(DataLoader().load_result_csv(str(path))).exclusion_reasons()


def test_direct_writer_refreshes_changed_execution_record(tmp_path):
    frame = pd.DataFrame({'Frame':[0,1]}, index=pd.Index([0.,.1],name='Time'))
    old = configured_record(threshold=1.)
    changed = configured_record(threshold=20.)
    frame.attrs[SETTINGS_ATTR] = old
    frame = add_timeline_context_columns(frame, {'artifact_metadata':identity()})
    old_version = frame['Artifact_ProcessingSemanticsVersion'].iloc[0]
    frame.attrs[SETTINGS_ATTR] = changed
    path=tmp_path/'changed.proc'
    save_proc_file(str(path),frame)
    loaded=read_identity(DataLoader().load_result_csv(str(path)))
    assert loaded.values['ProcessingSemanticsVersion'] == processing_record(changed)[0]
    assert loaded.values['ProcessingSemanticsVersion'] != old_version


def test_real_resampling_stage_records_actual_policy_not_unused_method(monkeypatch):
    controller = PipelineController()
    frame = pd.DataFrame({'Frame':[0,1,2],'Value':[0.,1.,2.]},index=pd.Index([0.,.1,.2],name='Time'))
    frame.attrs[SETTINGS_ATTR] = configured_record()
    monkeypatch.setattr(controller,'_execute_analysis_single_pass',lambda config,data: frame.copy())
    result = controller._execute_result_resampling({
        'slice_start_val':0.,'slice_end_val':.2,'result_resampling_factor':2,
        'result_resampling_method':'unused-requested-cubic'},frame)
    policy=result.attrs[SETTINGS_ATTR]['result_resampling']
    assert policy['enabled'] and policy['factor']==2
    assert policy['method'].startswith('linear-result-rows')
    assert policy['scope']=='full-slice'
    assert len(result)==5
