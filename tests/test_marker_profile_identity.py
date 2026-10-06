"""Independent contract mutations; public examples are not real standards."""
from copy import deepcopy
import json
import numpy as np
import pytest

from src.simulation.marker_fixtures import example_profile, virtual_profile_32, validate_profile, load_profile
from src.simulation.profile_document import ProfileEditorState, save_document, read_document
from src.utils.marker_profile_identity import (profile_identity, interpretation_policy, validate_identity,
    compatibility, layout_support, artifact_fields, artifact_identity, canonical)
from src.utils.artifact_metadata import normalize_metadata, ArtifactIdentity


def custom():
    value = example_profile(); value['profile_id'] = 'independent-custom'; return value


def metadata(profile=None):
    profile = custom() if profile is None else profile
    result = dict(SchemaVersion='1', SourceKind='handcrafted_dummy', MarkerLayoutId=profile['profile_id'],
        MarkerLayoutHash=validate_profile(profile), BoxLengthMm=profile['box_dims_mm'][0],
        BoxWidthMm=profile['box_dims_mm'][1], BoxHeightMm=profile['box_dims_mm'][2],
        CoordinatePolicy='world-y-up-box-local-fixed-center-v1', UnitsPolicy='bma-mm-s-rotvec-rad-summary-deg-v1')
    result.update(artifact_fields(profile)); return normalize_metadata(result)


@pytest.mark.parametrize('factory,expected', [(example_profile, '66ac8c6d2bcd9b531d532a23c2af7b04e72a7ae1ab1ae8aa8c0c8ec7ef77bafb'),
    (virtual_profile_32, 'd5405f1cf434c924070033748b4ca1e4661f10e190369d8f0bb0aac75fc97ff0')])
def test_existing_hash_and_whole_layout(factory, expected):
    profile = factory(); assert validate_profile(profile) == expected
    support = layout_support(profile)
    assert support['status'] == 'supported' and support['local_pose_constraint_rank'] == 6
    assert support['global_uniqueness_status'] == 'unavailable'
    assert support['rank_tolerance']['units'] == 'dimensionless-relative-singular-value'


def test_position_semantics_and_correspondence_are_distinct():
    original = custom(); before = profile_identity(original)
    moved = deepcopy(original); moved['markers'][0]['xyz_mm'][0] += 2
    after = profile_identity(moved)
    assert before['geometry_hash'] != after['geometry_hash']
    assert before['semantic_hash'] == after['semantic_hash']
    assert before['observation_mapping_hash'] != after['observation_mapping_hash']
    renamed = deepcopy(original); renamed['markers'][0]['id'] = 'F99'
    after = profile_identity(renamed)
    assert before['geometry_hash'] == after['geometry_hash']
    assert before['semantic_hash'] != after['semantic_hash'] and before['semantic_version'] != after['semantic_version']
    swapped = deepcopy(original)
    swapped['markers'][0]['xyz_mm'], swapped['markers'][1]['xyz_mm'] = swapped['markers'][1]['xyz_mm'], swapped['markers'][0]['xyz_mm']
    after = profile_identity(swapped)
    assert before['geometry_hash'] == after['geometry_hash'] and before['semantic_hash'] == after['semantic_hash']
    assert compatibility(before, after)['status'] == 'review_required'
    assert any('correspondence' in reason for reason in compatibility(before, after)['reasons'])
    reordered = deepcopy(original); reordered['markers'].reverse()
    authored = deepcopy(original); authored['profile_version'] = '2'
    for value in (reordered, authored):
        assert compatibility(before, profile_identity(value))['status'] == 'compatible'
        assert validate_profile(value) != before['profile_hash']


def test_same_face_swap_preserves_center_and_pose_objective():
    from src.analysis.pipeline.pose_optimizer import _objective_function, _face_constraint_rank
    from src.config.config_app import FACE_DEFINITIONS
    from scipy.spatial.transform import Rotation
    profile = custom(); local = np.asarray([m['xyz_mm'] for m in profile['markers']], float)
    pose = np.array([17., 200., 11., .12, -.07, .2])
    world = Rotation.from_rotvec(pose[3:]).apply(local)+pose[:3]
    original = [dict(id=m['id'], cam_coords=p, face_key=m['face']) for m,p in zip(profile['markers'], world)]
    swapped = deepcopy(original)
    swapped[0]['cam_coords'], swapped[1]['cam_coords'] = swapped[1]['cam_coords'], swapped[0]['cam_coords']
    np.testing.assert_allclose(np.mean([m['cam_coords'] for m in original], axis=0),
                               np.mean([m['cam_coords'] for m in swapped], axis=0), rtol=0, atol=1e-12)
    # This exercises the actual face-only objective at exact and offset poses,
    # independently of identity production. It does not claim arbitrary ID
    # edits or missing samples preserve time-series correspondence evidence.
    for candidate in (pose, pose+np.array([1.,2.,3.,.01,.02,.03])):
        a = _objective_function(candidate, original, np.array([200.,120.,80.]), FACE_DEFINITIONS)
        b = _objective_function(candidate, swapped, np.array([200.,120.,80.]), FACE_DEFINITIONS)
        assert abs(a-b) <= 1e-10  # mm², floating sum order only; no new physical tolerance.
    assert _face_constraint_rank(original,pose,np.array([200.,120.,80.]),FACE_DEFINITIONS) == _face_constraint_rank(swapped,pose,np.array([200.,120.,80.]),FACE_DEFINITIONS)


def test_existing_static_template_fit_detects_correspondence_without_center_claim():
    from src.analysis.pipeline.scene_detection import _fit_pose, DetectionSettings
    local=np.asarray([m['xyz_mm'] for m in example_profile()['markers']],float)/1000
    observed=local+np.array([.017,.2,.011]); swapped=local.copy(); swapped[[0,1]]=swapped[[1,0]]
    before=_fit_pose(local,observed); after=_fit_pose(swapped,observed)
    # Static geometry is already used by #135's evaluator. This is not
    # integration with the excluded #113 registration user feature.
    np.testing.assert_allclose(before[0],after[0],rtol=0,atol=1e-12)
    assert before[2] < 1e-12 and after[2] > DetectionSettings().marker_residual_m
    expected=np.sqrt(2*((72/1000)**2+(7/1000)**2)/18)
    assert abs(after[2]-expected) < 1e-12  # m, analytical permutation residual; floating arithmetic only.


def test_edge_face_change_keeps_geometry_and_changes_meaning():
    original = custom(); original['markers'][0]['xyz_mm'] = [100, 12, 40]
    after = deepcopy(original); after['markers'][0].update(id='R99', face='RIGHT')
    a, b = profile_identity(original), profile_identity(after)
    assert a['geometry_hash'] == b['geometry_hash'] and a['semantic_hash'] != b['semantic_hash']
    assert compatibility(a, b)['status'] == 'incompatible'


@pytest.mark.parametrize('field', ['normals', 'local_frame', 'world_vertical_axis_index', 'analysis_half_turn_rotvecs',
    'simulation_half_turns', 'half_turn_face_maps', 'label_prefixes', 'corner_basis'])
def test_fixed_meanings_participate_in_identity(field):
    before = profile_identity(custom()); policy = interpretation_policy()
    # A deliberately unsupported historical policy is internally hash-valid,
    # but cannot become the current consumer policy without migration review.
    policy[field] = {'independent-change': field}
    after = profile_identity(custom(), policy=policy)
    validate_identity(after, require_current=False)
    assert before['semantic_hash'] != after['semantic_hash'] and before['semantic_version'] != after['semantic_version']
    with pytest.raises(ValueError, match='migration'): validate_identity(after)
    assert compatibility(before, after)['status'] == 'unsupported'


def test_actual_shared_constant_change_is_detected(monkeypatch):
    from src.config import marker_semantics
    before = profile_identity(custom()); maps = deepcopy(marker_semantics.FACE_MAPS)
    maps['X']['FRONT'] = 'FRONT'; monkeypatch.setattr(marker_semantics, 'FACE_MAPS', maps)
    assert before['policy_hash'] != profile_identity(custom())['policy_hash']
    with pytest.raises(ValueError, match='migration'): validate_identity(before)


def test_literal_coordinate_and_half_turn_contract():
    from src.analysis.pipeline.marker_flip import local_axis_half_turn
    policy=interpretation_policy()
    assert policy['local_frame']['axes']=={'X':'Right','Y':'Top','Z':'Front'}
    assert policy['world_vertical_axis_index']==1 and policy['local_axis_indices']=={'X':0,'Y':1,'Z':2}
    assert policy['normals']==dict(FRONT=[0,0,1],BACK=[0,0,-1],RIGHT=[1,0,0],LEFT=[-1,0,0],TOP=[0,1,0],BOTTOM=[0,-1,0])
    for axis, signs in (('X',[1,-1,-1]),('Y',[-1,1,-1]),('Z',[-1,-1,1])):
        np.testing.assert_allclose(local_axis_half_turn(axis).as_matrix(),np.diag(signs),rtol=0,atol=2e-16)
        assert policy['simulation_half_turns'][axis]==np.diag(signs).tolist()
    assert policy['half_turn_face_maps']['X']==dict(FRONT='BACK',BACK='FRONT',TOP='BOTTOM',BOTTOM='TOP')
    assert policy['half_turn_face_maps']['Y']==dict(FRONT='BACK',BACK='FRONT',LEFT='RIGHT',RIGHT='LEFT')
    assert policy['half_turn_face_maps']['Z']==dict(LEFT='RIGHT',RIGHT='LEFT',TOP='BOTTOM',BOTTOM='TOP')


@pytest.mark.parametrize('mutation', [lambda x:x.update(schema_version=2), lambda x:x.update(plan_spec='other'),
    lambda x:x.pop('source_profile'), lambda x:x.update(semantic_hash='a'*64)])
def test_stale_or_missing_identity_never_succeeds(mutation):
    value = profile_identity(custom()); mutation(value)
    with pytest.raises(ValueError): validate_identity(value)
    assert compatibility(None, value)['status'] == 'invalid'


def test_legacy_unknown_and_compact_artifact_binding():
    assert compatibility(None, profile_identity(custom()))['status'] == 'unknown'
    assert compatibility(None, profile_identity(custom()))['approval_status'] == 'not_evaluated'
    assert artifact_identity(normalize_metadata()) is None
    assert any('unknown legacy' in reason for reason in ArtifactIdentity(normalize_metadata()).exclusion_reasons())
    value = metadata(); record = artifact_identity(value)
    assert record['source_profile'] == custom()
    for field, bad in [('MarkerLayoutHash', 'a'*64), ('UnitsPolicy', 'meters'), ('SourceKind', 'unknown_legacy'), ('BoxLengthMm', 201), ('SchemaVersion', '2')]:
        tampered = deepcopy(value); tampered[field] = bad
        with pytest.raises(ValueError): artifact_identity(tampered)
    for field, bad in [('schema_version', 2), ('policy_version', 'future'), ('time_semantics', 'frame-index'), ('source_profile', None)]:
        tampered = deepcopy(value); declaration = deepcopy(record); declaration[field] = bad
        tampered['MarkerProfileIdentityJson'] = canonical(declaration)
        with pytest.raises(ValueError): artifact_identity(tampered)
    tampered = deepcopy(value); declaration = deepcopy(record)
    declaration['source_profile']['markers'][0]['xyz_mm'][0] += 2
    tampered['MarkerProfileIdentityJson'] = canonical(declaration)
    with pytest.raises(ValueError, match='stale'): artifact_identity(tampered)
    with pytest.raises(ValueError): artifact_identity(dict(MarkerSemanticsHash='a'*64))


def test_actual_comparison_distinguishes_author_mapping_and_legacy():
    from src.utils.artifact_metadata import compatibility_reasons
    before=custom(); after=deepcopy(before); after['profile_version']='2'
    a=ArtifactIdentity(metadata(before)); b=ArtifactIdentity(metadata(after))
    reasons=compatibility_reasons(a,b)
    assert not any('Marker' in reason for reason in reasons)
    after['markers'][0]['xyz_mm'],after['markers'][1]['xyz_mm']=after['markers'][1]['xyz_mm'],after['markers'][0]['xyz_mm']
    reasons=compatibility_reasons(a,ArtifactIdentity(metadata(after)))
    assert any('correspondence' in reason for reason in reasons)
    legacy=metadata(before)
    for field in ('MarkerProfileIdentityJson','MarkerGeometryHash','MarkerSemanticsVersion','MarkerSemanticsHash'): legacy[field]=None
    assert any('unknown legacy' in reason for reason in compatibility_reasons(a,ArtifactIdentity(legacy)))


@pytest.mark.parametrize('count', [3, 4, 5])
def test_collinear_face_allowed_whole_unavailable_distinguished(count):
    profile = custom(); profile['markers'] = [m for m in profile['markers'] if m['face'] != 'FRONT']
    front = [dict(id=f'F{i+1}', face='FRONT', xyz_mm=[float(x), 0., 40.]) for i,x in enumerate(np.linspace(-60,60,count))]
    profile['markers'] += front
    assert layout_support(profile)['status'] == 'supported'
    profile['markers'] = front
    assert layout_support(profile)['status'] == 'unavailable'
    validate_profile(profile)  # Import accepts declared geometry without certifying pose.


def test_full_rank_distinct_orientation_counterexample_is_ambiguous():
    from src.simulation.profile_semantic_fixtures import ambiguous_face_profile
    from src.analysis.pipeline.pose_optimizer import _objective_function, PoseOptimizer
    from src.config.config_app import FACE_DEFINITIONS, calculate_local_box_corners
    import pandas as pd
    profile=ambiguous_face_profile(); support=layout_support(profile)
    markers=[dict(cam_coords=np.asarray(m['xyz_mm'],float),face_key=m['face']) for m in profile['markers']]
    for pose in (np.zeros(6),np.array([0,0,0,0,np.pi/2,0])):
        assert _objective_function(pose,markers,np.array([100.,100.,100.]),FACE_DEFINITIONS)<1e-20
    assert support['local_pose_constraint_rank']==6 and support['status']=='ambiguous'
    assert support['global_uniqueness_status']=='ambiguous' and support['ambiguity_witness_rotation'] is not None
    with pytest.raises(ValueError,match='orientations'): ProfileEditorState(profile).apply()
    row={f"{m['id']}_{axis}":v for m in profile['markers'] for axis,v in zip('XYZ',m['xyz_mm'])}
    row.update({f"{m['id']}_FaceInfo":m['face'] for m in profile['markers']})
    data=pd.DataFrame([row],index=pd.Index([0.],name='Time')); data.attrs['marker_artifact_metadata']=metadata(profile)
    result=PoseOptimizer(FACE_DEFINITIONS,calculate_local_box_corners([100.,100.,100.])).process(data,box_dims=[100.,100.,100.])
    assert result['Pose_Source'].iloc[0]=='AmbiguousGeometry'
    assert result['F1_X'].iloc[0]==50 and result.attrs==data.attrs
    assert result[['P_TX','P_TY','P_TZ','P_RX','P_RY','P_RZ']].isna().all().all()
    assert any('orientation ambiguity' in reason for reason in ArtifactIdentity(metadata(profile)).exclusion_reasons())


@pytest.mark.parametrize('value', [float('nan'), float('inf'), True])
def test_nonfinite_bool_profile_rejected(value):
    profile = custom(); profile['markers'][0]['xyz_mm'][0] = value
    with pytest.raises(ValueError): profile_identity(profile)


def test_copy_edit_preview_apply_reset_roundtrip(tmp_path):
    source = example_profile(); state = ProfileEditorState(source)
    assert state.source == source and state.draft['profile_id'] == 'custom-'+source['profile_id']
    draft = deepcopy(state.draft); draft['markers'][0]['id'] = 'F99'; state.edit(draft)
    with pytest.raises(ValueError, match='Preview'): state.apply()
    assert state.preview['markers'][0]['id'] == 'F1' and state.applied == source
    state.refresh_preview(); state.apply(); applied = deepcopy(state.applied)
    state.reset_to_source(); assert not state.preview_fresh and state.applied == applied
    path = tmp_path/'profile.json'; save_document(path, state); restored = read_document(path)
    assert restored.document() == state.document()
    assert load_profile(path) == applied  # Reopen never silently applies the reset draft.
    restored.refresh_preview(); restored.apply()
    assert restored.applied['markers'][0]['id'] == 'F1' and source == example_profile()
    assert [event['operation'] for event in state.history] == ['edit', 'preview', 'apply', 'reset']


def test_atomic_save_failure_retry_preserves_all_decisions(tmp_path, monkeypatch):
    import src.simulation.profile_document as documents
    state = ProfileEditorState(custom()); path = tmp_path/'profile.json'; save_document(path,state)
    before = path.read_bytes(); draft = deepcopy(state.draft); draft['profile_version']='2'; state.edit(draft)
    snapshot = state.document()
    with monkeypatch.context() as scoped:
        scoped.setattr(documents.os, 'replace', lambda *a: (_ for _ in ()).throw(OSError('independent failure')))
        with pytest.raises(OSError, match='independent failure'): save_document(path,state)
    assert path.read_bytes() == before and state.document() == snapshot and len(list(tmp_path.iterdir())) == 1
    save_document(path,state); assert read_document(path).document() == snapshot


@pytest.mark.parametrize('field,bad', [('schema_version',2), ('units','m'), ('time_semantics','frame-index'),
    ('revision',True), ('approval_status','approved')])
def test_document_invalid_contract_blocked(field, bad):
    value = ProfileEditorState(custom()).document(); value[field]=bad
    with pytest.raises(ValueError): ProfileEditorState.from_document(value)


def test_document_stale_preview_and_history_blocked():
    state = ProfileEditorState(custom()); draft = deepcopy(state.draft); draft['profile_version']='2'; state.edit(draft)
    value=state.document(); value['preview_revision']=value['revision']
    with pytest.raises(ValueError, match='Stale'): ProfileEditorState.from_document(value)
    value=state.document(); value['history'][0]['source_hash']='b'*64
    with pytest.raises(ValueError, match='history'): ProfileEditorState.from_document(value)


def test_unknown_layout_object_cannot_silently_become_legacy():
    profile=custom(); profile['object_type']='FutureMarkerProfile'
    with pytest.raises(ValueError,match='object_type'): profile_identity(profile)


@pytest.mark.parametrize('kind', ['ambiguous','unavailable'])
def test_declared_layout_support_producer_pipeline_and_result_roundtrip(tmp_path,monkeypatch,kind):
    from src.simulation.profile_semantic_fixtures import ambiguous_face_profile, rank_deficient_face_profile
    from src.simulation.corruption_export import write_observations
    from src.analysis.pipeline.data_loader import DataLoader
    from src.analysis.pipeline.parser import Parser
    from src.analysis.pipeline.pipeline_controller import PipelineController
    from src.analysis.pipeline.artifact_io import save_proc_file, add_timeline_context_columns
    from src.config import config_app
    from src.config.config_analysis_ui import get_raw_mode_options
    from src.config.data_columns import FACE_PREFIX_TO_INFO, SourceCols
    from src.utils.artifact_metadata import read_identity
    from test_general_export_recovery import observed_only, file_hashes
    profile=ambiguous_face_profile() if kind=='ambiguous' else rank_deficient_face_profile()
    times=np.arange(50)*.01
    trajectory=dict(schema_version=1,source_kind='handcrafted_dummy',
        coordinate_policy='world-y-up-box-local-fixed-center-v1',frame=list(range(50)),
        time_s=times.tolist(),body_origin_mm=[[17.,200.,11.]]*50,
        rotation_matrix=np.broadcast_to(np.eye(3),(50,3,3)).tolist())
    # Independently specified observation offsets; truth/profile stay unchanged.
    offsets=np.array([[1,2,0],[-2,1,0],[0,2,-1],[0,-1,2],[1,0,2],[-2,0,-1]])*.01
    events=[] if kind=='ambiguous' else [dict(kind='reconnect_jump',channel='rigid_body_markers',
        start_index=0,end_index_exclusive=50,marker_ids=[m['id']],offset_mm=offset.tolist())
        for m,offset in zip(profile['markers'],offsets)]
    root=write_observations(tmp_path/'capture',trajectory,profile,dict(schema_version=1,events=events),74082)
    before=file_hashes(root)
    monkeypatch.setattr(config_app,'BOX_DIMS',config_app.BOX_DIMS.copy())
    monkeypatch.setattr(config_app,'LOCAL_BOX_CORNERS',config_app.LOCAL_BOX_CORNERS.copy())
    with observed_only(monkeypatch,root):
        header,raw=DataLoader().load_csv(str(root/'observed.csv'))
        parsed=Parser(FACE_PREFIX_TO_INFO).process(header,raw)
        if kind=='unavailable':
            from src.analysis.pipeline.pose_optimizer import _face_constraint_rank
            from src.config.config_app import FACE_DEFINITIONS
            markers=[dict(cam_coords=np.asarray(m['xyz_mm'],float)+offset,face_key=m['face'])
                for m,offset in zip(profile['markers'],offsets)]
            assert _face_constraint_rank(markers,np.zeros(6),np.array([200.,120.,80.]),FACE_DEFINITIONS)==6
            assert layout_support(profile)['local_pose_constraint_rank']==3
        result=PipelineController().process_parsed_data(dict(box_dimensions=profile['box_dims_mm'],
            processing_mode='raw',slice_filter_by='time',slice_start_val=0.,slice_end_val=.49,
            analysis_options=get_raw_mode_options(),enable_result_resampling=False),parsed)
    expected_source='AmbiguousGeometry' if kind=='ambiguous' else 'UnidentifiableGeometry'
    assert len(result)==50 and set(result[SourceCols.POSE])=={expected_source}
    assert result[['P_TX','P_TY','P_TZ','P_RX','P_RY','P_RZ']].isna().all().all()
    # Literal observed point with explicit translation/offset, no truth input.
    expected_point=[67.,180.,61.] if kind=='ambiguous' else [17.01,200.02,51.]
    np.testing.assert_array_equal(result[['F1_X','F1_Y','F1_Z']],np.tile(expected_point,(50,1)))
    assert result.attrs['marker_artifact_metadata']==header['artifact_metadata']
    target=tmp_path/'ambiguous.proc'
    save_proc_file(str(target),add_timeline_context_columns(result,dict(artifact_metadata=canonical(header['artifact_metadata']))))
    reloaded=DataLoader().load_result_csv(str(target)); identity=read_identity(reloaded)
    assert artifact_identity(identity.values)['source_profile']==profile
    expected_reason='orientation ambiguity' if kind=='ambiguous' else 'local pose rank guard'
    assert any(expected_reason in reason for reason in identity.exclusion_reasons())
    from src.utils.artifact_metadata import compatibility_reasons
    assert any(expected_reason in reason for reason in compatibility_reasons(identity,identity))
    from src.analysis.compare.data_model import ComparisonModel
    comparison=ComparisonModel(); comparison.load_file(str(target))
    assert any(expected_reason in reason for reason in comparison.exclusion_reasons(target.name))
    assert all(record['n']==0 for record in comparison.get_impact_comparison()['statistics'].values())
    assert file_hashes(root)==before


def test_declared_source_rejects_conflicting_static_geometry():
    import pandas as pd
    from src.analysis.pipeline.scene_detection import detect_scenes, Registration
    from src.config.data_columns import TimeCols
    profile=custom(); times=np.arange(10)*.01
    parsed=pd.DataFrame({f"{m['id']}_{axis}":[v]*10 for m in profile['markers']
        for axis,v in zip('XYZ',m['xyz_mm'])},index=times)
    for marker in profile['markers']: parsed[marker['id']+'_FaceInfo']=marker['face']
    header=dict(export_metadata={'Length Units':'Millimeters','Coordinate Space':'Global'},artifact_metadata=metadata(profile))
    raw=pd.DataFrame({TimeCols.TIME:times,TimeCols.FRAME:range(10)})
    conflict=deepcopy(profile); conflict['markers'][0]['xyz_mm'][0]+=2
    with pytest.raises(ValueError,match='conflicts with declared'):
        detect_scenes(header,raw,parsed,registration=Registration(conflict))
    from src.analysis.pipeline.pose_optimizer import PoseOptimizer
    from src.config.config_app import FACE_DEFINITIONS, calculate_local_box_corners
    parsed.attrs['marker_artifact_metadata']=metadata(profile)
    with pytest.raises(ValueError,match='conflicts with declared'):
        PoseOptimizer(FACE_DEFINITIONS,calculate_local_box_corners([201.,120.,80.])).process(parsed,box_dims=[201.,120.,80.])
