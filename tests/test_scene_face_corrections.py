"""Approved face states through actual serialized observations, without pose-solver fitting."""
from copy import deepcopy
from dataclasses import asdict
import json
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest
from scipy.spatial.transform import Rotation

from marker_face_fixtures import DIMS, LAYOUT, BASE_FACES, raw_bundle, write_raw, context_json
from src.analysis.pipeline.artifact_io import (save_corrected_source_file, save_slice_file,
    read_slice_metadata, _sha256_file)
from src.analysis.pipeline.data_loader import DataLoader
from src.analysis.pipeline.face_assignment import materialize_face_assignments
from src.analysis.pipeline.marker_flip import MarkerCorrectionDecision
from src.analysis.pipeline.parser import Parser
from src.analysis.pipeline.scene_detection import Registration, VERSION, detect_scenes
from src.analysis.pipeline.scene_face_corrections import CORRECTED_VERSION
from src.analysis.pipeline.scene_review import SceneReviewSession
from src.analysis.pipeline.scene_workspace import save_workspace, read_workspace, restore_session
from src.config.data_columns import FACE_PREFIX_TO_INFO


IDENTITY = np.eye(3)
X = np.diag([1., -1., -1.])
Y = np.diag([-1., 1., -1.])
Z = np.diag([-1., -1., 1.])
LOCAL_CORNERS = np.array([[-100, -60, -40], [100, -60, -40], [100, 60, -40], [-100, 60, -40],
                          [-100, -60, 40], [100, -60, 40], [100, 60, 40], [-100, 60, 40]])


def write_corrected_capture(folder, axes=('X',), *, approved=True, genuine=False, gap=False, gravity=False,
                            samples=121, sample_interval=.01):
    """Small explicit observation input shared by headless and GUI wiring checks.

    The literal oracle/state and expected COM path stay here, never in detector
    inputs. Correction decisions are deliberately specified operator inputs.
    """
    folder.mkdir(parents=True)
    header, raw, _ = raw_bundle(axis=None, samples=samples)
    times = np.arange(samples) * sample_interval
    raw.iloc[:, 1] = times
    rate = np.pi / 1.2 if genuine else .4
    theta = times * rate
    rz = np.zeros((len(times), 3, 3))
    rz[:, 0, 0], rz[:, 1, 1], rz[:, 2, 2] = np.cos(theta), np.cos(theta), 1.
    rz[:, 0, 1], rz[:, 1, 0] = -np.sin(theta), np.sin(theta)
    base = Rotation.from_euler('xy', [23., -17.], degrees=True).as_matrix()
    rotations = rz @ base
    origins = np.column_stack((120. + 10. * times, 500. + 20. * times, 230. - 3. * times))
    if gravity:
        origins[:, 1] = 4000. - 1000. * times - 4905. * times ** 2
    states = np.repeat(IDENTITY[None], len(times), axis=0)
    decisions = []
    for index, axis in enumerate(axes):
        boundary = .4 + .4 * index
        states[times >= boundary] = states[times >= boundary] @ {'X': X, 'Y': Y, 'Z': Z}[axis]
        decisions.append(MarkerCorrectionDecision(f'approved-{index}', boundary, approved,
            axis if approved else None, correction_kind='face_assignment', algorithm_version='3.0'))
    points = origins[:, None, :] + np.einsum('nij,kj->nki', rotations @ states, np.array(list(LAYOUT.values())))
    if gap:
        points[38:44] = np.nan
    raw.iloc[:, 2:] = points.reshape(len(times), -1)
    original = folder / 'observed.csv'
    write_raw(original, header, raw)
    materialized_header, materialized = materialize_face_assignments(header, raw, decisions, BASE_FACES)
    corrected = folder / 'observed.corrected.csv'
    metadata = save_corrected_source_file(filepath=str(corrected), header_info=materialized_header,
        raw_data=materialized, original_source_path=str(original), decisions=decisions,
        context_json=context_json(_sha256_file(original)))
    profile = {'units': 'mm', 'origin': 'box-geometric-center', 'box_dims_mm': list(DIMS),
               'markers': [{'id': mid, 'face': BASE_FACES[mid], 'xyz_mm': list(xyz)} for mid, xyz in LAYOUT.items()]}
    registration = Registration(profile, 0., 1., (7., -9., 13.))
    registration_path = folder / 'registration.json'
    registration_path.write_text(json.dumps({'version': 1, **asdict(registration)}), encoding='utf-8')
    return SimpleNamespace(folder=folder, original=original, corrected=corrected, metadata=metadata,
        registration=registration, registration_path=registration_path, times=times, rotations=rotations,
        origins=origins, states=states, base=base, theta=theta, rate=rate,
        materialized_header=materialized_header, materialized=materialized)


def load_scene(path, registration):
    header, raw = DataLoader().load_csv(str(path))
    parsed = Parser(FACE_PREFIX_TO_INFO).process(header, raw)
    return header, raw, parsed, detect_scenes(header, raw, parsed, registration=registration)


@pytest.mark.parametrize('axes, final_state', [(('X',), X), (('X', 'X'), IDENTITY), (('X', 'Y'), Z)])
def test_registered_full_history_restores_arbitrary_box_pose_and_corners(tmp_path, axes, final_state):
    case = write_corrected_capture(tmp_path / 'capture', axes)
    before = case.corrected.read_bytes()
    header, raw, parsed, result = load_scene(case.corrected, case.registration)
    assert result.version == CORRECTED_VERSION
    assert result.valid_pose.all()
    assert np.array_equal(case.states[-1], final_state)
    np.testing.assert_allclose(result.origins_m * 1000., case.origins, atol=1e-10, rtol=0)
    np.testing.assert_allclose(result.rotations, case.rotations, atol=1e-12, rtol=0)
    expected = case.origins[:, None, :] + np.einsum('nij,kj->nki', case.rotations, LOCAL_CORNERS)
    np.testing.assert_allclose(result.corners_m * 1000., expected, atol=1e-10, rtol=0)
    assert not any(row.motion == 'tracking_jump' for row in result.candidates)
    local_com = case.base @ np.array([7., -9., 13.])
    expected_vy = 20. + case.rate * (np.cos(case.theta) * local_com[0] - np.sin(case.theta) * local_com[1])
    np.testing.assert_allclose(result.signals['Vertical speed (mm/s)'], expected_vy, atol=.002, rtol=0)
    assert header['export_metadata']['Length Units'] == 'Millimeters'
    assert len(header['face_correction']['decisions']) == len(axes)
    json.dumps(header, allow_nan=False)  # No dataclass leaks into generic header transport.
    assert case.corrected.read_bytes() == before


def test_suffix_uses_approval_before_first_saved_sample_and_preserves_payload(tmp_path):
    case = write_corrected_capture(tmp_path / 'capture')
    header, raw, _, result = load_scene(case.corrected, case.registration)
    session = SceneReviewSession(result, _sha256_file(case.corrected))
    for row in session.rows:
        session.set_decision(row['id'], 'include')
    chosen = session.rows[0]
    payload = session.payload(chosen['id'])
    suffix = tmp_path / 'suffix.slice'
    save_slice_file(filepath=str(suffix), header_info=header, raw_data=raw,
        source_path=str(case.corrected), full_start=0., full_end=1.2,
        user_start=.6, user_end=1.2, pad_rows=0, box_dims=DIMS, marker_correction_metadata=case.metadata)
    sh, sr, _, restored = load_scene(suffix, case.registration)
    assert float(sr.iloc[0, 1]) == .6
    assert sh['face_correction']['decisions'][0]['boundary_time_sec'] == .4
    np.testing.assert_allclose(restored.rotations, case.rotations[60:], atol=1e-12, rtol=0)
    np.testing.assert_allclose(restored.corners_m[0] * 1000.,
        case.origins[60] + LOCAL_CORNERS @ case.rotations[60].T, atol=1e-10, rtol=0)
    assert read_slice_metadata(str(suffix)).correction_context_json == case.metadata.context_json
    assert json.loads(payload)['detection']['version'] == CORRECTED_VERSION


def test_off_does_not_correct_and_smooth_real_half_turn_remains_motion(tmp_path):
    off = write_corrected_capture(tmp_path / 'off', approved=False)
    _, _, _, result = load_scene(off.corrected, off.registration)
    assert result.version == VERSION
    valid = result.valid_pose
    np.testing.assert_allclose(result.rotations[valid], (off.rotations @ off.states)[valid], atol=1e-12, rtol=0)
    assert any(row.motion == 'tracking_jump' for row in result.candidates)
    real = write_corrected_capture(tmp_path / 'real', axes=(), genuine=True)
    _, _, _, actual = load_scene(real.corrected, real.registration)
    assert actual.version == VERSION
    assert not any(row.motion == 'tracking_jump' for row in actual.candidates)
    assert actual.signals['Relative rotation (deg)'].iloc[-1] == pytest.approx(180., abs=1e-10)


def test_unregistered_relative_references_and_derivatives_do_not_bridge_approval(tmp_path):
    case = write_corrected_capture(tmp_path / 'capture', ('X', 'Y'))
    _, _, _, result = load_scene(case.corrected, None)
    assert result.corners_m is None
    assert not any(row.motion == 'tracking_jump' for row in result.candidates)
    for boundary in (40, 80):
        assert result.block_ids[boundary - 1] != result.block_ids[boundary]
        assert result.signals['Relative rotation (deg)'].iloc[boundary] != result.signals['Relative rotation (deg)'].iloc[boundary]
        assert np.isnan(result.signals['Vertical speed (mm/s)'].iloc[boundary])
        row = next(c for c in result.candidates if c.start <= case.times[boundary] <= c.end)
        assert row.motion == 'unclear' and 'approved_face_boundary_relative_reference' in row.tags
    for first, last in ((0, 40), (40, 80), (80, 121)):
        expected = np.degrees(.4 * (case.times[first:last] - case.times[first]))
        values = result.signals['Relative rotation (deg)'].iloc[first:last].to_numpy()
        np.testing.assert_allclose(values[np.isfinite(values)], expected[np.isfinite(values)], atol=1e-10, rtol=0)
    assert all(c.end < .4 or c.start >= .4 for c in result.candidates)
    assert all(c.end < .8 or c.start >= .8 for c in result.candidates)


def test_gap_preserves_approval_state_without_filling_pose(tmp_path):
    case = write_corrected_capture(tmp_path / 'capture', gap=True)
    _, _, _, result = load_scene(case.corrected, case.registration)
    assert not result.valid_pose[38:44].any()
    assert np.isnan(result.rotations[38:44]).all()
    assert np.isnan(result.corners_m[38:44]).all()
    np.testing.assert_allclose(result.rotations[44:], case.rotations[44:], atol=1e-12, rtol=0)


@pytest.mark.parametrize('mismatch', ['dimensions', 'face', 'axis', 'units', 'space'])
def test_registered_context_mismatch_is_rejected(tmp_path, mismatch):
    case = write_corrected_capture(tmp_path / 'capture')
    header, raw = DataLoader().load_csv(str(case.corrected))
    parsed = Parser(FACE_PREFIX_TO_INFO).process(header, raw)
    registration = deepcopy(case.registration)
    if mismatch == 'dimensions':
        registration.profile['box_dims_mm'][0] += 1.
    elif mismatch == 'face':
        registration.profile['markers'][0]['face'] = 'BACK'
    elif mismatch == 'axis':
        registration.profile['markers'][0]['xyz_mm'][2] *= -1.
    else:
        key = 'Length Units' if mismatch == 'units' else 'Coordinate Space'
        header['face_correction']['context']['export_metadata'][key] = 'unknown'
    with pytest.raises(ValueError):
        detect_scenes(header, raw, parsed, registration=registration)


def test_old_corrected_review_requires_recheck_but_unchanged_raw_review_does_not(tmp_path):
    case = write_corrected_capture(tmp_path / 'capture')
    for source, registration in ((case.corrected, case.registration), (case.original, case.registration)):
        _, _, _, result = load_scene(source, registration)
        session = SceneReviewSession(result, _sha256_file(source))
        for row in session.rows:
            session.set_decision(row['id'], 'include')
        path = tmp_path / (source.name + '.scene-review.json')
        data = save_workspace(path, session, source, DIMS)
        data['detection_version'] = VERSION
        restored, changed = restore_session(data, result, session.source_sha256)
        if source == case.corrected:
            assert changed
            assert all(row['decision'] == 'unreviewed' and row['previous_review']['decision'] == 'include'
                       for row in restored.rows)
        else:
            assert not changed
            assert restored.rows == session.rows


def test_cancel_during_corrected_fit_does_not_mutate_inputs(tmp_path):
    case = write_corrected_capture(tmp_path / 'capture')
    header, raw = DataLoader().load_csv(str(case.corrected))
    parsed = Parser(FACE_PREFIX_TO_INFO).process(header, raw)
    before = parsed.copy(deep=True)
    with pytest.raises(InterruptedError):
        detect_scenes(header, raw, parsed, registration=case.registration, cancelled=lambda: True)
    pd.testing.assert_frame_equal(before, parsed)


def test_only_affected_ranges_need_version_review_and_constant_unregistered_suffix_keeps_meaning(tmp_path):
    case = write_corrected_capture(tmp_path / 'capture')
    header, raw, _, result = load_scene(case.corrected, case.registration)
    session = SceneReviewSession(result, _sha256_file(case.corrected))
    before_id = session.add_range(.05, .25)
    after_id = session.add_range(.65, .95)
    session.refresh(result)
    for row in session.rows:
        session.set_decision(row['id'], 'include')
    data = save_workspace(tmp_path / 'legacy.scene-review.json', session, case.corrected, DIMS)
    data['detection_version'] = VERSION
    restored, changed = restore_session(data, result, session.source_sha256)
    assert before_id not in changed and restored.row(before_id) == session.row(before_id)
    assert after_id in changed and restored.row(after_id)['previous_review']['decision'] == 'include'
    suffix = tmp_path / 'constant.slice'
    save_slice_file(filepath=str(suffix), header_info=header, raw_data=raw,
        source_path=str(case.corrected), full_start=0., full_end=1.2,
        user_start=.6, user_end=1.2, pad_rows=0, box_dims=DIMS, marker_correction_metadata=case.metadata)
    _, _, _, relative = load_scene(suffix, None)
    assert relative.version == VERSION
    assert not relative.face_correction_affected.any()
    assert relative.signals['Relative rotation (deg)'].iloc[-1] == pytest.approx(np.degrees(.4 * .6), abs=1e-10)


def test_unregistered_gravity_unclear_candidates_still_split_at_relative_reference(tmp_path):
    case = write_corrected_capture(tmp_path / 'gravity', gravity=True, samples=100, sample_interval=.008)
    _, _, _, result = load_scene(case.corrected, None)
    assert result.block_ids[49] != result.block_ids[50]
    assert np.isnan(result.signals['Relative rotation (deg)'].iloc[50])
    assert all(candidate.motion == 'unclear' for candidate in result.candidates)
    assert [(candidate.start, candidate.end) for candidate in result.candidates] == [(0., .392), (.4, .792)]
    for candidate, duration in zip(result.candidates, (.392, .392)):
        assert candidate.rotation_deg == pytest.approx(np.degrees(.4 * duration), abs=1e-10)
        assert 'approved_face_boundary_relative_reference' in candidate.tags
    assert result.candidates[0].right_censored and result.candidates[1].left_censored


def test_refresh_recomputes_old_face_blind_evidence_even_after_xx_returns_to_identity(tmp_path):
    case = write_corrected_capture(tmp_path / 'capture', ('X', 'X'))
    header, raw, parsed, current = load_scene(case.corrected, case.registration)
    # The pre-v3 scene detector used this fixed-template raw-fit interpretation
    # for corrected observations too. Retain that actual fit path as the old
    # result input instead of inventing a stale geometry dictionary.
    old = detect_scenes({'export_metadata': header['export_metadata']}, raw, parsed,
                        registration=case.registration)
    assert old.version == VERSION and current.version == CORRECTED_VERSION
    session = SceneReviewSession(old, _sha256_file(case.corrected))
    row_id = session.add_range(.8, .95)
    session.refresh(old)
    session.set_decision(row_id, 'include')
    saved = deepcopy(session.row(row_id))
    assert not current.face_correction_affected[80:96].any()
    assert saved['motion_geometry']['status'] == 'insufficient_tracking'
    fresh = SceneReviewSession(current, session.source_sha256).recompute_saved_row(saved)
    assert fresh['motion_geometry'] != saved['motion_geometry']
    session.refresh(current)
    row = session.row(row_id)
    assert row['decision'] == 'unreviewed'
    assert row['previous_review']['decision'] == 'include'
    assert 'detection_version_changed' in row['previous_review']['reasons']
    assert row['motion_geometry'] == fresh['motion_geometry']
    assert row['activity_members'] == fresh['activity_members']
