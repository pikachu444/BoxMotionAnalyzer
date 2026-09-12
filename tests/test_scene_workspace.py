"""Workspace recovery from public observations; no truth is a detector input."""
from copy import deepcopy
from dataclasses import replace
import hashlib
import json
import math

import numpy as np
import pytest

from src.analysis.pipeline.data_loader import DataLoader
from src.analysis.pipeline.parser import Parser
from src.analysis.pipeline.scene_detection import Registration, detect_scenes
from src.analysis.pipeline.scene_review import SceneReviewSession
from src.analysis.pipeline.scene_workspace import (
    read_workspace, restore_session, save_workspace, workspace_source_path,
)
from src.config.data_columns import FACE_PREFIX_TO_INFO
from src.simulation.scene_fixtures import write_sequence


def _hash(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load(source, registration, settings=None):
    header, raw = DataLoader().load_csv(str(source))
    parsed = Parser(FACE_PREFIX_TO_INFO).process(header, raw)
    return detect_scenes(header, raw, parsed, registration=registration, settings=settings)


@pytest.fixture(scope='module', params=['handling', 'drops', 'partial'])
def recording(request, tmp_path_factory):
    folder = write_sequence(tmp_path_factory.mktemp('workspace') / 'capture', request.param)
    source = folder / 'observed.csv'
    registration = Registration.load(folder / 'registration.json')
    return request.param, source, _load(source, registration)


@pytest.fixture(scope='module')
def handling(tmp_path_factory):
    folder = write_sequence(tmp_path_factory.mktemp('workspace_handling') / 'capture', 'handling')
    source = folder / 'observed.csv'
    return source, _load(source, Registration.load(folder / 'registration.json'))


def _edited_session(source, result):
    session = SceneReviewSession(result, _hash(source))
    selected = next(row['id'] for row in session.rows if row['motion'] == 'tip_or_rotation')
    session.set_range(selected, .4, 2.)
    removed = session.rows[-1]['id']
    manual = session.add_range(3.2, 4.8)
    session.remove(removed)
    session.refresh(result)
    session.set_context('G', '2018-03')
    session.set_decision(selected, 'include')
    session.set_decision(manual, 'exclude')
    # Other rows remain unreviewed. Saving work must not require slice approval.
    return session, selected, manual, removed


def test_real_handling_workspace_restores_edits_measurement_and_partial_review(handling, tmp_path):
    source, result = handling
    source_before = source.read_bytes()
    session, selected, manual, removed = _edited_session(source, result)
    path = tmp_path / 'work.scene.json'
    save_workspace(path, session, source, (300., 180., 90.), selected_id=selected, signal='Opposite edge height')
    data = read_workspace(path)
    assert workspace_source_path(path, data) == source.resolve()
    fresh = _load(workspace_source_path(path, data), Registration(**data['registration']))
    restored, changed = restore_session(data, fresh, _hash(source))
    assert changed == set()
    assert restored.rows == session.rows
    assert restored.deleted_ids == {removed}
    assert restored.manual_serial == 1
    assert restored.row(manual)['decision'] == 'exclude'
    assert not restored.all_reviewed
    assert data['view'] == {'selected_id': selected, 'signal': 'Opposite edge height', 'targets': []}
    # Independent analytic 300 mm edge raised by 15 degrees, not a stored answer.
    expected_height = 300. * np.sin(np.deg2rad(15.))
    height = restored.row(selected)['motion_geometry']['opposite_edge_max_height_mm']
    assert height == pytest.approx(expected_height, abs=1e-6)
    assert height == session.row(selected)['motion_geometry']['opposite_edge_max_height_mm']
    restored.refresh(fresh)
    assert removed not in {row['id'] for row in restored.rows}
    assert restored.rows == session.rows
    assert source.read_bytes() == source_before
    with pytest.raises(ValueError, match='Review every interval'):
        restored.payload(selected)


def test_capture_reopen_preserves_motion_and_conditional_item_choice(recording, tmp_path):
    case, source, result = recording
    session = SceneReviewSession(result, _hash(source))
    session.set_context('H', '2018-03')
    for row in session.rows:
        session.set_decision(row['id'], 'include' if row['motion'] == 'free_fall' else 'exclude')
    session.identify()
    falls = [row for row in session.rows if row['motion'] == 'free_fall']
    if case == 'drops':
        assert len(falls) == 2
        assert all(row['item_candidates'] == ['H/B04/D06', 'H/B16/D06'] for row in falls)
        # Explicit operator choice for persistence testing, not an actual trial record.
        session.confirm_item(falls[0]['id'], 'H/B16/D06')
    elif case == 'partial':
        assert falls[0]['left_censored'] and falls[-1]['right_censored']
        assert all(row['item_candidates'] == [] for row in falls)
    path = tmp_path / 'work.scene.json'
    save_workspace(path, session, source, (300., 180., 90.))
    restored, changed = restore_session(read_workspace(path), result, _hash(source))
    assert changed == set()
    assert restored.rows == session.rows
    if case == 'drops':
        assert restored.row(falls[0]['id'])['identity']['scenario_id'] == 'H/B16/D06'
        assert restored.row(falls[1]['id'])['identity']['confirmed'] is False
        altered = read_workspace(path)
        selected = next(row for row in altered['rows'] if row['id'] == falls[0]['id'])
        selected['identity']['scenario_id'] = 'H/B04/D01'
        checked, changed = restore_session(altered, result, _hash(source))
        assert changed == {falls[0]['id']}
        changed_row = checked.row(falls[0]['id'])
        assert changed_row['decision'] == 'unreviewed'
        assert changed_row['identity']['confirmed'] is False
        assert changed_row['previous_review']['identity']['scenario_id'] == 'H/B04/D01'
    elif case == 'partial':
        altered = read_workspace(path)
        altered['rows'][0]['left_censored'] = False
        checked, changed = restore_session(altered, result, _hash(source))
        assert falls[0]['id'] in changed
        assert checked.row(falls[0]['id'])['left_censored'] is True
        assert checked.row(falls[0]['id'])['decision'] == 'unreviewed'


@pytest.mark.parametrize('field', ['height', 'classification'])
def test_cached_numeric_or_semantic_change_requires_review_without_losing_choice(handling, tmp_path, field):
    source, result = handling
    session, selected, _, _ = _edited_session(source, result)
    path = tmp_path / 'work.scene.json'
    save_workspace(path, session, source, (300., 180., 90.))
    data = read_workspace(path)
    cached = next(row for row in data['rows'] if row['id'] == selected)
    if field == 'height':
        old = cached['motion_geometry']['opposite_edge_max_height_mm']
        cached['motion_geometry']['opposite_edge_max_height_mm'] = math.nextafter(old, math.inf)
    else:
        cached['motion'] = cached['evidence_class'] = 'free_fall'
    restored, changed = restore_session(data, result, _hash(source))
    assert changed == {selected}
    row = restored.row(selected)
    assert row['decision'] == 'unreviewed'
    assert row['identity']['confirmed'] is False
    assert row['previous_review']['decision'] == 'include'
    assert row['previous_review']['identity'] == session.row(selected)['identity']
    assert row['motion_geometry'] == session.row(selected)['motion_geometry']
    assert row['motion'] == 'tip_or_rotation'


@pytest.mark.parametrize('change', ['registration', 'settings', 'algorithm'])
def test_new_computation_context_requires_review_and_keeps_previous_choices(handling, tmp_path, monkeypatch, change):
    source, result = handling
    session, selected, _, removed = _edited_session(source, result)
    path = tmp_path / 'work.scene.json'
    save_workspace(path, session, source, (300., 180., 90.))
    fresh = result
    if change == 'registration':
        fresh = _load(source, replace(result.registration, floor_y_mm=.5))
    elif change == 'settings':
        fresh = _load(source, result.registration, replace(result.settings, window_s=.096))
    else:
        fresh = replace(result, version='observed-motion-next')
    restored, changed = restore_session(read_workspace(path), fresh, _hash(source))
    assert changed == {row['id'] for row in session.rows}
    assert all(row['decision'] == 'unreviewed' for row in restored.rows)
    assert restored.row(selected)['previous_review']['decision'] == 'include'
    assert restored.deleted_ids == {removed}
    assert [(r['id'], r['start'], r['end']) for r in restored.rows] == [
        (r['id'], r['start'], r['end']) for r in session.rows]


@pytest.mark.parametrize('fault', ['duplicate_id', 'range', 'source_hash', 'settings', 'json'])
def test_invalid_workspace_cannot_replace_an_active_review(handling, tmp_path, fault):
    source, result = handling
    session, _, _, _ = _edited_session(source, result)
    original_rows = deepcopy(session.rows)
    path = tmp_path / 'work.scene.json'
    save_workspace(path, session, source, (300., 180., 90.))
    data = read_workspace(path)
    if fault == 'duplicate_id':
        data['rows'][1]['id'] = data['rows'][0]['id']
    elif fault == 'range':
        data['rows'][0]['end'] = 1000.
    elif fault == 'source_hash':
        data['source']['sha256'] = '0' * 64
    elif fault == 'settings':
        data['settings']['minimum_points'] = 5.5
    if fault == 'json':
        path.write_text('{broken', encoding='utf-8')
    else:
        path.write_text(json.dumps(data), encoding='utf-8')
    with pytest.raises(ValueError):
        restore_session(read_workspace(path), result, _hash(source))
    assert session.rows == original_rows


def test_failed_workspace_save_and_source_overwrite_leave_originals_intact(handling, tmp_path, monkeypatch):
    source, result = handling
    session, selected, _, _ = _edited_session(source, result)
    source_before = source.read_bytes()
    with pytest.raises(ValueError, match='separately'):
        save_workspace(source, session, source, (300., 180., 90.))
    path = tmp_path / 'work.scene.json'
    save_workspace(path, session, source, (300., 180., 90.))
    before = path.read_bytes()
    session.set_decision(selected, 'exclude')
    def fail_replace(*args):
        raise PermissionError('Workspace is open')
    monkeypatch.setattr('src.analysis.pipeline.scene_workspace.os.replace', fail_replace)
    with pytest.raises(PermissionError, match='Workspace is open'):
        save_workspace(path, session, source, (300., 180., 90.))
    assert path.read_bytes() == before
    assert list(tmp_path.iterdir()) == [path]
    assert source.read_bytes() == source_before


def test_active_corrected_source_reference_and_changed_source_are_checked(handling, tmp_path):
    source, result = handling
    active = tmp_path / 'observed.corrected.csv'
    active.write_bytes(source.read_bytes())
    session, selected, _, _ = _edited_session(active, result)
    path = tmp_path / 'work.scene.json'
    save_workspace(path, session, active, (300., 180., 90.), selected_id=selected)
    before = path.read_bytes()
    assert workspace_source_path(path, read_workspace(path)) == active.resolve()
    other_original = tmp_path / 'original.csv'
    other_original.write_bytes(source.read_bytes())
    original_before = other_original.read_bytes()
    with pytest.raises(ValueError, match='separately'):
        save_workspace(other_original, session, active, (300., 180., 90.))
    assert other_original.read_bytes() == original_before
    active.write_bytes(active.read_bytes() + b'\n')
    with pytest.raises(ValueError, match='source changed'):
        save_workspace(path, session, active, (300., 180., 90.))
    with pytest.raises(ValueError, match='source differs'):
        restore_session(read_workspace(path), result, _hash(active))
    assert path.read_bytes() == before


def test_changed_test_context_does_not_keep_old_type_in_row_identity(handling, tmp_path):
    source, result = handling
    session, selected, _, _ = _edited_session(source, result)
    path = tmp_path / 'work.scene.json'
    save_workspace(path, session, source, (300., 180., 90.))
    data = read_workspace(path)
    data['context']['ista_type'] = 'H'
    restored, changed = restore_session(data, result, _hash(source))
    assert changed == {row['id'] for row in session.rows}
    assert restored.row(selected)['identity']['ista_type'] == 'H'
    assert restored.row(selected)['previous_review']['identity']['ista_type'] == 'G'


@pytest.mark.parametrize('remove_registration', [False, True])
def test_pending_geometry_is_saved_before_detection_runs_again(handling, tmp_path, remove_registration):
    source, result = handling
    session, selected, _, _ = _edited_session(source, result)
    for row in session.rows:
        row['previous_review'] = {
            'decision': row['decision'], 'identity': deepcopy(row['identity']),
            'reasons': ['geometry_changed'],
        }
        row['decision'] = 'unreviewed'
        row['evidence_status'] = 'geometry_changed'
        row['motion_geometry'] = {'version': 1, 'status': 'geometry_changed'}
        session._reset_identity(row)
    pending_registration = None if remove_registration else replace(result.registration, floor_y_mm=2.)
    pending_dims = (310., 180., 90.) if remove_registration else (300., 180., 90.)
    path = tmp_path / 'pending.scene.json'
    save_workspace(path, session, source, pending_dims, registration=pending_registration)
    data = read_workspace(path)
    assert data['box_dims_mm'] == list(pending_dims)
    if remove_registration:
        assert data['registration'] is None
        loaded_registration = None
    else:
        assert data['registration']['floor_y_mm'] == 2.
        loaded_registration = Registration(**data['registration'])
    assert session.result.registration.floor_y_mm == 0.
    assert all(row['evidence_status'] == 'geometry_changed' for row in data['rows'])
    fresh = _load(source, loaded_registration)
    restored, changed = restore_session(data, fresh, _hash(source))
    assert changed == {row['id'] for row in session.rows}
    assert all(row['decision'] == 'unreviewed' for row in restored.rows)
    row = restored.row(selected)
    assert row['previous_review']['decision'] == 'include'
    assert row['evidence_status'] == 'current'
    assert row['identity']['confirmed'] is False
    if remove_registration:
        assert row['motion_geometry']['status'] == 'registration_required'
    else:
        # The unchanged public trajectory touched y=0; the newly entered floor is y=2 mm.
        assert row['motion_geometry']['minimum_corner_height_mm'] == pytest.approx(-2., abs=1e-6)


def test_unconfirmed_reference_edition_cannot_mix_with_current_drop_candidates(tmp_path):
    folder = write_sequence(tmp_path / 'capture', 'drops')
    source = folder / 'observed.csv'
    result = _load(source, Registration.load(folder / 'registration.json'))
    session = SceneReviewSession(result, _hash(source))
    session.set_context('H', '2018-03')
    for row in session.rows:
        session.set_decision(row['id'], 'include' if row['motion'] == 'free_fall' else 'exclude')
    session.identify()
    selected = next(row['id'] for row in session.rows if row['motion'] == 'free_fall')
    path = tmp_path / 'work.scene.json'
    save_workspace(path, session, source, (300., 180., 90.))
    data = read_workspace(path)
    cached = next(row for row in data['rows'] if row['id'] == selected)
    assert cached['identity']['confirmed'] is False
    cached['identity']['reference_edition'] = '2017-01'
    restored, changed = restore_session(data, result, _hash(source))
    assert changed == {selected}
    row = restored.row(selected)
    assert row['decision'] == 'unreviewed'
    assert row['identity']['reference_edition'] == '2018-03'
    assert row['identity']['confirmed'] is False
    assert row['item_candidates'] == ['H/B04/D06', 'H/B16/D06']
    assert row['previous_review']['decision'] == 'include'
    assert row['previous_review']['identity']['reference_edition'] == '2017-01'
    assert 'reference_edition_changed' in row['previous_review']['reasons']


def test_position_plot_target_names_survive_workspace_save_and_reopen(handling, tmp_path):
    source, result = handling
    session, selected, _, _ = _edited_session(source, result)
    path = tmp_path / 'position.scene.json'
    targets = ['Marker B1', 'Marker B2']
    save_workspace(path, session, source, (300., 180., 90.), selected_id=selected,
                   signal='P_TY', targets=targets)
    data = read_workspace(path)
    assert data['view'] == {'selected_id': selected, 'signal': 'P_TY', 'targets': targets}
    # Workspaces written before target selection was stored remain readable.
    del data['view']['targets']
    path.write_text(json.dumps(data), encoding='utf-8')
    assert read_workspace(path)['view']['targets'] == []
    data['view']['targets'] = 'Marker B1'
    path.write_text(json.dumps(data), encoding='utf-8')
    with pytest.raises(ValueError, match='list of names'):
        read_workspace(path)


def test_filename_colliding_scene_ids_are_rejected_before_export(handling, tmp_path):
    source, result = handling
    session, _, _, _ = _edited_session(source, result)
    path = tmp_path / 'work.scene.json'
    save_workspace(path, session, source, (300., 180., 90.))
    original = read_workspace(path)
    altered = deepcopy(original)
    altered['rows'][0]['id'] = 'part 1'
    altered['rows'][1]['id'] = 'part_1'
    path.write_text(json.dumps(altered), encoding='utf-8')
    with pytest.raises(ValueError, match='scene IDs'):
        read_workspace(path)
    with pytest.raises(ValueError, match='scene IDs'):
        restore_session(altered, result, _hash(source))
    # Invalid deleted IDs cannot return later as new exportable scenes either.
    altered = deepcopy(original)
    altered['deleted_ids'] = ['part 1', 'part_1']
    path.write_text(json.dumps(altered), encoding='utf-8')
    with pytest.raises(ValueError, match='removed scene IDs'):
        read_workspace(path)
