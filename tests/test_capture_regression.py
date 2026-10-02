"""Independent contract/fault tests; no experimental data or fitted oracle."""
import builtins
import copy
import io
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from scipy.spatial.transform import Rotation

from src.analysis.regression.contracts import (anchor, candidate_anchor, replay_mapping,
    canonical_pose, read_json, validate_fixture, file_digest, metric, envelope)
from src.analysis.regression.signatures import residual_guard, compare_metrics
from src.analysis.regression.runner import run_corpus, production_capture, process_scene, validate_proc_linkage, validate_trial_counts
from src.analysis.pipeline.data_loader import DataLoader
from src.analysis.pipeline.parser import Parser
from src.analysis.pipeline.scene_detection import SceneCandidate
from src.config.data_columns import FACE_PREFIX_TO_INFO
from src.simulation.capture_corpus import build_corpus, TOLERANCE, independent_corners


@pytest.fixture(scope='module')
def assets(tmp_path_factory):
    root = tmp_path_factory.mktemp('capture_assets') / 'assets'
    build_corpus(root)
    return root


def reviewed_copy(root, destination):
    """Test-only authorization for failure injection; never promotes real assets."""
    import shutil
    shutil.copytree(root, destination)
    approval = dict(status='approved', reviewer='test-only-failure-setup', date='2026-10-02', basis='Exercise nonpass branches, not baseline promotion')
    manifest = json.loads((destination / 'corpus.json').read_text())
    manifest['approval'] = approval
    for case in manifest['cases']:
        path = destination / case['fixture']
        fixture = json.loads(path.read_text())
        fixture['approval'] = fixture['tolerance']['approval'] = approval
        path.write_text(json.dumps(fixture))
    (destination / 'corpus.json').write_text(json.dumps(manifest))
    return destination


def raw_table(n=40):
    return pd.DataFrame({'Frame': 900 + np.arange(n) * 3, 'Time': 10 + np.arange(n) * .01,
                         'X': np.arange(n) / 7})


def decision(raw, a, b, rid, *, origin='automatic'):
    result = dict(review_id=rid, origin=origin, anchor=anchor(raw, a, b))
    if origin == 'automatic':
        result['detected_anchor'] = result['anchor'].copy()
    return result


def candidates(raw, intervals):
    return [SceneCandidate(f'current-{i}', float(raw.iloc[a, 1]), float(raw.iloc[b-1, 1]), 'unclear', 'unclear')
            for i, (a,b) in enumerate(intervals)]


@pytest.mark.parametrize('intervals,expected', [([(0,20)],'matched'), ([(0,10),(10,20)],'split'),
    ([], 'missing'), ([(0,20),(0,20)],'ambiguous'), ([(0,21)],'changed_boundary')])
def test_candidate_mapping_never_transfers_by_ordinal_or_nearest(intervals, expected):
    raw = raw_table()
    mapped, _ = replay_mapping(raw, [decision(raw,0,20,'stable-review')], candidates(raw, intervals))
    assert mapped[0]['status'] == expected


def test_merged_and_new_candidates_require_review():
    raw = raw_table()
    ds = [decision(raw,0,20,'a'), decision(raw,20,40,'b')]
    mapped, _ = replay_mapping(raw, ds, candidates(raw,[(0,40)]))
    assert [m['status'] for m in mapped] == ['merged','merged']
    mapped, auto = replay_mapping(raw,[decision(raw,0,20,'manual',origin='manual')],candidates(raw,[(0,40)]))
    assert mapped[0]['status'] == 'manual_bound'
    assert auto[0]['mapping_status'] == 'unreviewed'


def test_neighbor_digest_and_eof_boundary():
    raw = raw_table()
    approved = decision(raw,0,40,'eof',origin='manual')
    assert approved['anchor']['end_raw_time_s']['status'] == 'unavailable'
    changed = raw.copy()
    changed.iloc[-1,2] += 1
    mapped, _ = replay_mapping(changed,[approved],[])
    assert mapped[0]['status'] == 'stale_anchor'
    assert candidate_anchor(raw, candidates(raw, [(0,40)])[0]) == approved['anchor']


def analytic_trajectory():
    n = 41
    times = 10 + np.arange(n)*.01
    center = np.column_stack((10*np.sin(np.arange(n)*2*np.pi/40), np.full(n,280.), np.zeros(n)))
    rotation = np.repeat(np.eye(3)[None], n, axis=0)
    corners = independent_corners(center, rotation)
    return dict(original_record_index=np.arange(n).tolist(), raw_time_s=times.tolist(),
        geocenter_position_mm=center.tolist(), rotation_matrix=rotation.tolist(), corners_mm=corners.tolist(),
        floor_height_mm=corners[:,:,1].tolist(), valid_mask=[True]*n)


@pytest.mark.parametrize('fault', ['spike','corner_exchange','units','time','record','mask','zero_fill','rotation'])
def test_all_time_guard_detects_intentional_errors(fault):
    reference = analytic_trajectory()
    actual = {k: np.asarray(v, bool if k == 'valid_mask' else float).copy() for k,v in reference.items()}
    if fault == 'spike':
        before_extrema = (actual['geocenter_position_mm'][:,0].min(),actual['geocenter_position_mm'][:,0].max())
        before_jump = np.linalg.norm(np.diff(actual['geocenter_position_mm'],axis=0),axis=1).max()
        # Between representative endpoints/midpoint and below original extrema/jump.
        actual['geocenter_position_mm'][14,0] += .15
        assert before_extrema == (actual['geocenter_position_mm'][:,0].min(),actual['geocenter_position_mm'][:,0].max())
        assert np.linalg.norm(np.diff(actual['geocenter_position_mm'],axis=0),axis=1).max() <= before_jump
    elif fault == 'corner_exchange':
        actual['corners_mm'][:,[0,1]] = actual['corners_mm'][:,[1,0]]
    elif fault == 'units':
        actual['geocenter_position_mm'] /= 1000
    elif fault == 'time':
        actual['raw_time_s'] += .001
    elif fault == 'record':
        actual['original_record_index'][10] += 1
    elif fault == 'mask':
        actual['valid_mask'][10] = False
    elif fault == 'zero_fill':
        reference['valid_mask'][10] = False
        for k in ('geocenter_position_mm','rotation_matrix','corners_mm','floor_height_mm'):
            reference[k][10] = np.full(np.asarray(reference[k][10]).shape,None).tolist()
            actual[k][10] = 0
        actual['valid_mask'][10] = False
    elif fault == 'rotation':
        actual['rotation_matrix'][10] = Rotation.from_rotvec([.01,0,0]).as_matrix()
    result = residual_guard(actual, reference, TOLERANCE)
    assert result['status'] == 'fail'
    assert result['failures']


def test_guard_retains_unavailable_and_quaternion_sign():
    reference = analytic_trajectory()
    for k in ('geocenter_position_mm','rotation_matrix','corners_mm','floor_height_mm'):
        reference[k][3] = np.full(np.asarray(reference[k][3]).shape,None).tolist()
    reference['valid_mask'][3] = False
    actual = {k: np.asarray(v,bool if k=='valid_mask' else float) for k,v in reference.items()}
    q = Rotation.from_matrix(actual['rotation_matrix'][0]).as_quat()
    actual['rotation_matrix'][0] = Rotation.from_quat(-q).as_matrix()
    result = residual_guard(actual,reference,TOLERANCE)
    assert result['status'] == 'pass'
    assert result['checked_samples'] == 40
    assert result['approved_unavailable_samples'] == 1


def test_canonical_offsets_include_world_angular_velocity_term():
    r = Rotation.from_euler('z',90,degrees=True).as_matrix()[None]
    center, com, velocity = canonical_pose(np.array([[10.,20.,30.]]),r,
        np.array([[1.,2.,3.]]),np.array([[0.,0.,2.]]),[3.,0.,0.],[0.,4.,0.])
    np.testing.assert_allclose(center,[[10,23,30]],atol=1e-12)
    np.testing.assert_allclose(com,[[6,20,30]],atol=1e-12)
    np.testing.assert_allclose(velocity,[[-5,2,3]],atol=1e-12)


@pytest.mark.parametrize('key', ['t1','t2'])
def test_event_time_shift_and_missing_to_zero_fail(key):
    expected = {key: dict(**metric(10.2),tolerance='time_s')}
    assert compare_metrics(expected,{key:metric(10.21)},TOLERANCE)[key]['status'] == 'fail'
    assert compare_metrics({key:metric(status='not_detected')},{key:metric(0.)},TOLERANCE)[key]['status'] == 'fail'
    assert compare_metrics({key:metric(status='failed')},{key:metric(0.)},TOLERANCE)[key]['status'] == 'fail'


@pytest.mark.parametrize('change', ['schema','spec','field','units','frame','enum','NaN','resampling','truth','OFF','flip_order'])
def test_invalid_contract_is_rejected(assets,change):
    f = read_json(assets/'two_flips/review.json','CaptureReviewFixture')
    if change=='schema': f['schema_version']=999
    elif change=='spec': f['plan_spec']='unsupported'
    elif change=='field': del f['raw_sha256']
    elif change=='units': f['geometry']['position_units']='m'
    elif change=='frame': f['geometry']['world_frame']='world-z-up'
    elif change=='enum': f['scene_decisions'][0]['decision']='automatic_include'
    elif change=='NaN': f['geometry']['floor_y_mm']=float('nan')
    elif change=='resampling': f['effective_processing_config']['enable_result_resampling']=True
    elif change=='truth': f['effective_processing_config']['oracle']='reference.json'
    elif change=='OFF': f['marker_correction_default']='X'
    elif change=='flip_order': f['flip_decisions'].reverse()
    with pytest.raises((ValueError,KeyError)):
        validate_fixture(f)


def test_empty_lines_and_invalid_time_preserve_original_record_mapping(assets,tmp_path):
    source=(assets/'partial/observed.csv').read_text().splitlines()
    rows=source[:8]+source[8:10]+['']+source[10:]
    import csv
    damaged=next(csv.reader([rows[12]]))
    damaged[1]='bad-time'
    rows[12]=','.join(damaged)
    path=tmp_path/'blank_and_bad_time.csv'
    path.write_text('\n'.join(rows)+'\n')
    h,raw=DataLoader().load_csv(str(path))
    assert len(raw)==60
    parsed=Parser(FACE_PREFIX_TO_INFO).process(h,raw)
    assert len(parsed)==59
    assert parsed.attrs['removed_records']==[dict(original_record_index=3,reason='invalid_time')]
    assert parsed['Source_OriginalRecordIndex'].tolist()==[0,1,2,*range(4,60)]
    assert parsed.iloc[0]['Frame']!='0'


def test_proposed_tolerance_never_passes_and_reports_no_fresh(assets,tmp_path):
    root=reviewed_copy(assets,tmp_path/'copy')
    fpath=root/'two_drops/review.json'
    f=json.loads(fpath.read_text());f['tolerance']['approval']['status']='proposed'
    fpath.write_text(json.dumps(f))
    # No processing allowed when the selected required gate is proposed.
    report=run_corpus(root/'corpus.json',root,tmp_path/'run',select=['two_drops-scene-0'])
    assert report['exit_code']!=0
    assert report['coverage']['fresh']==0


@pytest.mark.parametrize('failure', ['raw_missing','source_changed','worker','slice_save','proc_save','reference_missing','scene_deleted'])
def test_required_failures_are_nonpass_with_honest_coverage(assets,tmp_path,monkeypatch,failure):
    root=reviewed_copy(assets,tmp_path/'copy')
    target=root/'two_drops/observed.csv'
    if failure=='raw_missing': target.unlink()
    elif failure=='source_changed': target.write_text(target.read_text()+'\n')
    elif failure=='scene_deleted':
        path=root/'two_drops/review.json'
        f=json.loads(path.read_text());f['scene_decisions']=[d for d in f['scene_decisions'] if d['review_id']!='two_drops-scene-1'];path.write_text(json.dumps(f))
    elif failure=='reference_missing': (root/'two_drops/reference.json').unlink()
    else:
        def fail(*args,**kwargs): raise RuntimeError('Required injected '+failure+' failure')
        name={'worker':'process_scene','slice_save':'save_slice_file','proc_save':'save_proc_file'}[failure]
        monkeypatch.setattr('src.analysis.regression.runner.'+name,fail)
    # Avoid normal optimizer work in failure-path unit tests. Unrelated cases
    # remain outside the selection; failed required scenes stay in the denominator.
    if failure in ('reference_missing','scene_deleted'):
        def complete(*args,**kwargs):
            kwargs['progress']['processing']='fresh'
            return pd.DataFrame(),None,{}
        monkeypatch.setattr('src.analysis.regression.runner.process_scene',complete)
    report=run_corpus(root/'corpus.json',root,tmp_path/'run',select=['two_drops-scene-0'])
    assert report['status']!='pass'
    assert report['exit_code']!=0
    assert report['coverage']['approved']==6
    assert report['coverage']['reused']==0
    assert (tmp_path/'run/run_report.json').exists()


def test_output_and_baseline_cannot_be_overwritten(assets,tmp_path):
    before=file_digest(assets/'corpus.json')
    with pytest.raises(FileExistsError): build_corpus(assets)
    with pytest.raises(FileExistsError): run_corpus(assets/'corpus.json',assets,assets)
    assert file_digest(assets/'corpus.json')==before


def test_invalid_representative_selection_is_nonpass(assets,tmp_path):
    root=reviewed_copy(assets,tmp_path/'copy')
    report=run_corpus(root/'corpus.json',root,tmp_path/'run',select=['not-approved'])
    assert report['status']=='fail'
    assert report['coverage']['fresh']==0
    assert report['coverage']['unexecuted']==6


def test_capture_selection_cannot_report_representative_pass(assets,tmp_path):
    report=run_corpus(assets/'corpus.json',assets,tmp_path/'run',tier='capture',select=['partial-scene-0'])
    assert report['status']=='fail'
    assert report['coverage']['fresh']==0 and report['coverage']['unexecuted']==6


@pytest.mark.parametrize('fault',['stale_run','source','settings','scene','record','time','zero_status'])
def test_stale_proc_cannot_count_as_fresh(fault):
    linkage=envelope('CaptureReplay',run_id='current-run',raw_sha256='a'*64,settings_sha256='b'*64,review_id='scene')
    stored=copy.deepcopy(linkage)
    if fault=='stale_run':stored['run_id']='previous-run'
    elif fault=='source':stored['raw_sha256']='c'*64
    elif fault=='settings':stored['settings_sha256']='d'*64
    elif fault=='scene':stored['review_id']='other-scene'
    frame=pd.DataFrame({('Info','CaptureReplay','Json'):[json.dumps(stored)]*2,
                       ('Info','Source','OriginalRecordIndex'):[3,4]},index=pd.Index([10.3,10.4],name='Time'))
    if fault=='record':frame.iloc[0,1]=30
    elif fault=='time':frame.index=pd.Index([.3,.4],name='Time')
    elif fault=='zero_status':frame.iloc[0,0]='0'
    with pytest.raises((ValueError,TypeError)):
        validate_proc_linkage(frame,linkage,np.array([3,4]),np.array([10.3,10.4]))


def test_source_move_preserves_identity_but_content_change_rejects(assets,tmp_path):
    import shutil
    root=tmp_path/'moved';shutil.copytree(assets,root)
    f=read_json(root/'partial/review.json','CaptureReviewFixture')
    out=tmp_path/'out';out.mkdir()
    vals=production_capture(root/f['relative_path'],f,out)
    assert all(m['status'] in ('matched','manual_bound') for m in vals[5])
    assert file_digest(root/f['relative_path'])==f['raw_sha256']
    (root/f['relative_path']).write_text((root/f['relative_path']).read_text()+'\n')
    with pytest.raises(ValueError,match='SHA256 mismatch'):
        production_capture(root/f['relative_path'],f,out)


def test_excluded_handling_cannot_be_added_to_approved_set(assets,tmp_path,monkeypatch):
    root=reviewed_copy(assets,tmp_path/'copy')
    fpath=root/'handling_only/review.json'
    f=json.loads(fpath.read_text());f['scene_decisions'][1]['decision']='include';fpath.write_text(json.dumps(f))
    report=run_corpus(root/'corpus.json',root,tmp_path/'run',tier='capture')
    assert report['status']=='fail'
    assert 'approved scene set mismatch' in str(report['errors'])


def test_missing_required_signature_metric_blocks(assets,tmp_path,monkeypatch):
    # The normal full test exercises this on actual produced outputs; the
    # comparator unit contract also refuses an omitted required actual value.
    result=compare_metrics({'vertical_velocity':dict(**metric(-2.),tolerance='velocity_m_s')},{},TOLERANCE)
    assert result['vertical_velocity']['status']=='fail'


def test_raw_clock_roundtrips_without_one_ulp_loss(assets,tmp_path):
    from src.analysis.pipeline.artifact_io import save_proc_file
    h,raw=DataLoader().load_csv(str(assets/'two_drops/observed.csv'))
    parsed=Parser(FACE_PREFIX_TO_INFO).process(h,raw)
    expected=np.asarray(raw.iloc[:,1],float)
    assert expected[112] == 11.120000000000001
    np.testing.assert_array_equal(parsed.index.to_numpy(float),expected)
    path=tmp_path/'clock.proc'
    frame=pd.DataFrame({'Time':expected,'Source_OriginalRecordIndex':np.arange(len(expected))})
    save_proc_file(str(path),frame)
    np.testing.assert_array_equal(DataLoader().load_result_csv(str(path)).index.to_numpy(float),expected)


def test_raw_embedded_profile_mismatch_is_rejected(assets,tmp_path):
    from src.simulation.marker_fixtures import validate_profile
    f=read_json(assets/'partial/review.json','CaptureReviewFixture')
    f['marker_profile']['profile_id']=f['marker_profile_id']='different-reviewed-layout'
    f['marker_profile_hash']=validate_profile(f['marker_profile'])
    with pytest.raises(ValueError,match='declaration conflict'):
        production_capture(assets/'partial/observed.csv',f,tmp_path)


@pytest.mark.parametrize('counts',[({'speed':1},{'speed':2}),({'speed':2},{'speed':2})])
def test_inflated_original_trial_n_fails(counts):
    with pytest.raises(ValueError,match='inflated'):
        validate_trial_counts(*counts)


@pytest.mark.parametrize('fault',['OFF_forced','flip_axes_swapped','flip_boundary_moved'])
def test_actual_replay_fault_changes_pose_and_full_guard_fails(assets,tmp_path,fault):
    case='tracking_OFF' if fault=='OFF_forced' else 'two_flips'
    f=read_json(assets/f'{case}/review.json','CaptureReviewFixture')
    if fault=='OFF_forced':
        f['flip_decisions'][0]['axis']='X'
    elif fault=='flip_axes_swapped':
        f['flip_decisions'][0]['axis'],f['flip_decisions'][1]['axis']='Y','X'
    else:
        _,raw=DataLoader().load_csv(str(assets/f'{case}/observed.csv'))
        d=f['flip_decisions'][0];d['original_record_index']+=1
        d['raw_time_s']=float(raw.iloc[d['original_record_index'],1])
        d['anchor']=anchor(raw,d['original_record_index'],d['original_record_index']+1)
    result=production_capture(assets/f'{case}/observed.csv',f,tmp_path)[3]
    reference=read_json(assets/f'{case}/reference.json','TrajectoryReference')['scenes'][f'{case}-scene-0']['trajectory']
    actual={k:np.asarray(v,bool if k=='valid_mask' else float).copy() for k,v in reference.items()}
    # These are the actual registered marker poses after faulty production
    # replay, not a synthetic rotation injected directly into the guard.
    usable=result.valid_pose & np.isfinite(result.rotations).all(axis=(1,2))
    actual['valid_mask']=usable
    actual['geocenter_position_mm']=result.origins_m*1000.
    actual['rotation_matrix']=result.rotations.copy()
    actual['corners_mm']=independent_corners(actual['geocenter_position_mm'],actual['rotation_matrix'])
    actual['floor_height_mm']=actual['corners_mm'][:,:,1]
    for key in ('geocenter_position_mm','rotation_matrix','corners_mm','floor_height_mm'):
        actual[key][~usable]=np.nan
    assert residual_guard(actual,reference,TOLERANCE)['status']=='fail'


@pytest.fixture(scope='module')
def fresh_full():
    """Every approved scene, actual production calls; evidence retained for CI."""
    import uuid
    from src.analysis.regression import runner
    from src.analysis.regression.signatures import pose_trajectory
    root=Path('tmp/issue135')/('pytest_'+uuid.uuid4().hex)
    source=root/'assets';build_corpus(source)
    protected={str(p.resolve()):file_digest(p) for p in source.rglob('*') if p.is_file()}
    forbidden={Path(p) for p in protected if Path(p).name in
        ('reference.json','truth_pose.csv','truth_markers.csv','observed.synthetic.json')}
    original_open,original_io=builtins.open,io.open
    blocked_reads=[]
    def checked(opener):
        def open_checked(file,*args,**kwargs):
            if isinstance(file,(str,bytes,Path)) and Path(file).resolve() in forbidden:
                blocked_reads.append(str(file));raise AssertionError('Production accessed evaluator/truth sidecar')
            return opener(file,*args,**kwargs)
        return open_checked
    def isolated(function):
        def call(*args,**kwargs):
            with pytest.MonkeyPatch.context() as patch:
                patch.setattr(builtins,'open',checked(original_open));patch.setattr(io,'open',checked(original_io))
                return function(*args,**kwargs)
        return call
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(runner,'production_capture',isolated(production_capture))
        patch.setattr(runner,'process_scene',isolated(process_scene))
        report=runner.run_corpus(source/'corpus.json',source,root/'full',command=['pytest','test_fresh_full_capture_pipeline_preserves_every_approved_scene'])
    after={str(p.resolve()):file_digest(p) for p in source.rglob('*') if p.is_file()}
    isolation=dict(blocked_reads=blocked_reads,source_reference_truth_manifest_unchanged=protected==after,
                   before=protected,after=after)
    (root/'isolation.json').write_text(json.dumps(isolation,indent=2))
    return root,source,report,isolation


def test_fresh_full_capture_pipeline_preserves_every_approved_scene(fresh_full):
    root,source,report,isolation=fresh_full
    assert report['status']=='pass',str(root/'full/run_report.json')
    assert report['coverage']==dict(loaded=6,approved=6,fresh=6,reused=0,failed=0,unexecuted=0)
    assert report['optimizer_calls']==449
    assert isolation['source_reference_truth_manifest_unchanged'] and isolation['blocked_reads']==[]
    scenes=[s for c in report['cases'] for s in c['scenes']]
    assert sum(s['signature']['artifacts']['proc_rows'] for s in scenes)==452
    assert sum(s['signature']['guards']['residual']['checked_samples'] for s in scenes)==449
    assert sum(c['signature']['raw_rows'] for c in report['cases'])==552
    for s in scenes:
        assert s['processing']=='fresh' and s['status']=='pass'
        assert all(v['status']=='pass' for v in s['comparisons'].values())
        assert s['signature']['artifacts']['scenario_guard']['status']=='pass'
    assert report['gui']['status']=='pending' and report['calibration_status']=='pending'


def test_deleted_truth_and_changed_labels_leave_actual_processing_equal(fresh_full,tmp_path):
    import shutil
    from src.analysis.regression.signatures import pose_trajectory
    root,source,report,_=fresh_full
    changed=tmp_path/'changed';shutil.copytree(source,changed)
    for p in changed.rglob('truth_*.csv'):p.unlink()
    for p in changed.rglob('observed.synthetic.json'):
        p.write_text('{"scenario_label":"deliberately wrong; forbidden analyzer input"}')
    f=read_json(changed/'partial/review.json','CaptureReviewFixture')
    out=tmp_path/'process';out.mkdir()
    h,raw,original,_,_,_,_,session,path,correction=production_capture(changed/f['relative_path'],f,out)
    d=next(d for d in f['scene_decisions'] if d['decision']=='include')
    df,_,artifact=process_scene(f,d,session,h,raw,original,path,correction,out,'sidecar-isolation-probe')
    before=DataLoader().load_result_csv(str(root/'full/partial/partial-scene-0.proc'))
    for key,values in pose_trajectory(before,f['geometry']).items():
        np.testing.assert_array_equal(pose_trajectory(df,f['geometry'])[key],values)
    pd.testing.assert_frame_equal(df['Analysis'],before['Analysis'])
    assert artifact['optimizer_calls']==60


def test_actual_step2_compare_and_scenario_export_reuse_fresh_results(fresh_full,monkeypatch):
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication,QFileDialog
    from src.analysis.app.main_window import MainApp
    root,_,report,_=fresh_full
    assert report['status']=='pass'
    gui=root/'gui';gui.mkdir()
    app=QApplication.instance() or QApplication([])
    window=MainApp();window.resize(1510,800);window.show();QTest.qWait(100)
    paths=[str(root/'full'/c['case_id']/s['signature']['artifacts']['proc'])
           for c in report['cases'] for s in c['scenes']]
    before={p:file_digest(p) for p in paths}
    try:
        window.view_saved_results(paths)
        widget=window.result_widget
        assert widget.current_result_file and widget.result_data is not None
        artifact=report['cases'][0]['scenes'][0]['signature']['artifacts']
        selected=artifact['scenario_sample_time_s']
        widget._select_time_by_xdata(selected)
        widget.le_scene_name.setText('two_drops-scene-0')
        widget.le_run_time.setText('1.0');widget.le_time_step.setText('0.001')
        out=gui/'scenario.csv'
        monkeypatch.setattr(QFileDialog,'getSaveFileName',lambda *args:(str(out),''))
        QTest.mouseClick(widget.export_scenario_button,Qt.LeftButton);QTest.qWait(100)
        assert out.read_text()==(root/'full/two_drops/two_drops-scene-0.scenario.csv').read_text()
        assert window.grab().save(str(gui/'step2.png'))
        window.open_comparison(paths)
        compare=window.comparison_window;QTest.qWait(500)
        assert len(compare.model.datasets)==6
        assert compare.grab().save(str(gui/'compare.png'))
        screen=app.primaryScreen();dpr=screen.devicePixelRatio()
        evidence=envelope('GuiExecution',status='pass',scope='Native Qt MainApp Step 2 / Compare / actual scenario button',
            physical_screen=[screen.size().width()*dpr,screen.size().height()*dpr],dpr=dpr,
            window_size=[window.width(),window.height()],source_fresh_run_id=report['run_id'],
            fresh_processing_in_gui=0,reused_proc=6,source_unchanged=before=={p:file_digest(p) for p in paths},
            scenario_exact=True,dialog_scope='Save path supplied by test; native chooser interaction not evaluated',
            screenshots=['step2.png','compare.png'],calibration_status='pending')
        evidence['pending']=['New corpus Step 1/1.5 native fresh processing',
            'Native save chooser interaction','Compare 3D visual inspection (local viewport was black; cause unconfirmed)']
        (gui/'execution.json').write_text(json.dumps(evidence,indent=2))
        assert evidence['source_unchanged']
    finally:
        if window.comparison_window is not None:window.comparison_window.close()
        window.close();app.processEvents()
