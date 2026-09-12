"""Operator intent stays distinct from observed contact and stale evidence."""
from copy import deepcopy
from dataclasses import replace
import hashlib
import json

import pandas as pd
import pytest

from src.analysis.pipeline.artifact_io import (
    add_timeline_context_columns, read_slice_metadata, save_proc_file,
    save_slice_file, update_slice_box_dimensions,
)
from src.analysis.pipeline.data_loader import DataLoader
from src.analysis.pipeline.intended_contact import (
    feature_corners, feature_label, feature_options,
    validate_intended_contact, validate_intended_contact_context,
)
from src.analysis.pipeline.parser import Parser
from src.analysis.pipeline.scene_detection import Registration, detect_scenes
from src.analysis.pipeline.scene_review import SceneReviewSession, validate_scene_review_json
from src.analysis.pipeline.scene_workspace import read_workspace, restore_session, save_workspace
from src.config.data_columns import FACE_PREFIX_TO_INFO
from src.simulation.scene_fixtures import write_sequence


DIMS = (300., 180., 90.)
INTENDED = ('FRONT', 'TOP', 'RIGHT')


def _load(source, registration, settings=None):
    header, raw = DataLoader().load_csv(str(source))
    parsed = Parser(FACE_PREFIX_TO_INFO).process(header, raw)
    return detect_scenes(header, raw, parsed, registration=registration, settings=settings)


@pytest.fixture(scope='module')
def drops(tmp_path_factory):
    folder = write_sequence(tmp_path_factory.mktemp('intended') / 'capture', 'drops')
    source = folder / 'observed.csv'
    registration = Registration.load(folder / 'registration.json')
    # Only observation CSV and registered geometry enter the production path.
    return source, _load(source, registration)


def _session(drops):
    source, result = drops
    session = SceneReviewSession(result, hashlib.sha256(source.read_bytes()).hexdigest())
    session.set_context('H', '2018-03')
    for row in session.rows:
        session.set_decision(row['id'], 'include' if row['motion'] == 'free_fall' else 'exclude')
    selected = next(row['id'] for row in session.rows if row['motion'] == 'free_fall')
    session.identify()
    return session, selected


def _record():
    return {'version': 1, 'basis': 'operator', 'faces': list(INTENDED),
            'registration_sha256': 'a' * 64, 'ista_type': 'H', 'applied_edition': '2018-03'}


def test_all_26_local_features_have_distinct_valid_topology():
    options = feature_options()
    assert len(options) == len(set(options)) == 26
    assert [sum(len(faces) == count for faces in options) for count in (1, 2, 3)] == [6, 12, 8]
    assert all(faces == tuple(sorted(faces)) for faces in options)
    corners = [feature_corners(faces) for faces in options]
    assert len(set(corners)) == 26
    assert [sum(len(ids) == count for ids in corners) for count in (4, 2, 1)] == [6, 12, 8]
    assert feature_corners(('BOTTOM',)) == (1, 2, 5, 6)
    assert feature_corners(('FRONT', 'TOP')) == (7, 8)
    assert feature_corners(INTENDED) == (7,)
    assert feature_label(('TOP', 'FRONT')) == 'Front + Top'


@pytest.mark.parametrize('faces', [(), ('TOP', 'BOTTOM'), ('LEFT', 'RIGHT'), ('FRONT', 'BACK'),
    ('TOP', 'TOP'), ('TOP', 'BOTTOM', 'FRONT'), ('TOP', 'FRONT', 'RIGHT', 'BACK'),
    ('C7',), (7,), 'TOP', {'TOP'}, None])
def test_invalid_or_opposite_faces_cannot_become_an_intended_feature(faces):
    with pytest.raises(ValueError, match='Intended contact'):
        feature_corners(faces)


def test_record_canonicalization_does_not_mutate_input_and_context_is_exact():
    value = _record()
    canonical = validate_intended_contact(value)
    assert canonical['faces'] == ['FRONT', 'RIGHT', 'TOP']
    assert value['faces'] == list(INTENDED)
    assert validate_intended_contact(None) is None
    assert validate_intended_contact_context(None, None, 'Unknown', None) is None
    assert validate_intended_contact_context(value, 'a' * 64, 'H', '2018-03') == canonical
    for fingerprint, ista_type, edition in [('b' * 64, 'H', '2018-03'),
                                            ('a' * 64, 'G', '2018-03'),
                                            ('a' * 64, 'H', None)]:
        with pytest.raises(ValueError, match='context'):
            validate_intended_contact_context(value, fingerprint, ista_type, edition)


@pytest.mark.parametrize('field,value', [('version', True), ('version', 2), ('basis', 'automatic'),
    ('registration_sha256', 'x' * 64), ('ista_type', 'J'), ('applied_edition', 2018),
    ('faces', ['TOP', 'BOTTOM']), ('corners', [7])])
def test_malformed_intended_record_is_rejected(field, value):
    record = _record()
    record[field] = value
    with pytest.raises(ValueError, match='[Ii]ntended contact'):
        validate_intended_contact(record)


def test_operator_can_intend_a_corner_when_public_drop_approaches_bottom_face(drops):
    session, selected = _session(drops)
    row = session.row(selected)
    observed = deepcopy(row['geometry'])
    assert observed['floor_crossings'][0]['approach_feature']['faces'] == ['BOTTOM']
    assert row['item_candidates'] == ['H/B04/D06', 'H/B16/D06']
    record = session.set_intended_contact(selected, INTENDED)
    assert record['faces'] == ['FRONT', 'RIGHT', 'TOP']
    assert record['registration_sha256'] == session.result.registration.fingerprint
    assert record['basis'] == 'operator'
    # Identify updates observed posture lookup without reinterpreting operator intent.
    session.identify()
    session.refresh(session.result)
    session.set_context('H', '2018-03')
    session.set_range(selected, row['start'], row['end'])
    session.set_decision(selected, 'include')
    assert row['intended_contact'] == record
    assert row['geometry'] == observed
    assert row['identity']['confirmed'] is False
    payload = json.loads(session.payload(selected))
    assert payload['candidate']['intended_contact'] == record
    session.confirm_item(selected, 'H/B16/D06')
    assert row['intended_contact'] == record
    session.set_intended_contact(selected, None)
    assert row.get('intended_contact') is None


@pytest.mark.parametrize('change', ['type', 'edition', 'range', 'exclude', 'unreviewed', 'geometry', 'settings'])
def test_actual_review_context_changes_clear_operator_intent(drops, change):
    session, selected = _session(drops)
    session.set_intended_contact(selected, INTENDED)
    row = session.row(selected)
    if change == 'type':
        session.set_context('G', '2018-03')
    elif change == 'edition':
        session.set_context('H', None)
    elif change == 'range':
        session.set_range(selected, row['start'] + .008, row['end'])
    elif change in ('exclude', 'unreviewed'):
        session.set_decision(selected, change)
    elif change == 'geometry':
        session.refresh(replace(session.result, registration=replace(session.result.registration, floor_y_mm=2.)))
    else:
        session.refresh(replace(session.result, settings=replace(session.result.settings, window_s=.096)))
    assert row.get('intended_contact') is None


@pytest.mark.parametrize('missing', ['include', 'current', 'registration', 'floor'])
def test_intent_requires_current_included_range_and_explicit_registered_floor(drops, missing):
    session, selected = _session(drops)
    if missing == 'include':
        session.set_decision(selected, 'exclude')
    elif missing == 'current':
        session.row(selected)['evidence_status'] = 'range_changed'
    elif missing == 'registration':
        session.result = replace(session.result, registration=None)
    else:
        session.result = replace(session.result, registration=replace(session.result.registration, floor_y_mm=None))
    with pytest.raises(ValueError):
        session.set_intended_contact(selected, INTENDED)
    assert session.row(selected).get('intended_contact') is None


def test_invalid_replacement_leaves_the_previous_intended_feature(drops):
    session, selected = _session(drops)
    record = session.set_intended_contact(selected, INTENDED)
    with pytest.raises(ValueError):
        session.set_intended_contact(selected, ('BOTTOM', 'TOP'))
    assert session.row(selected)['intended_contact'] == record


def test_public_workspace_recompute_preserves_independent_intent_and_legacy_absence(drops, tmp_path):
    source, _ = drops
    session, selected = _session(drops)
    session.set_intended_contact(selected, INTENDED)
    path = tmp_path / 'work.scene.json'
    save_workspace(path, session, source, DIMS)
    data = read_workspace(path)
    fresh = _load(source, Registration(**data['registration']))
    restored, changed = restore_session(data, fresh, session.source_sha256)
    assert changed == set()
    assert restored.rows == session.rows
    for null_record in (False, True):
        legacy = deepcopy(data)
        for row in legacy['rows']:
            row.pop('intended_contact', None)
            if null_record:
                row['intended_contact'] = None
        restored, changed = restore_session(legacy, fresh, session.source_sha256)
        assert changed == set()
        assert restored.rows == legacy['rows']


@pytest.mark.parametrize('change', ['cached_geometry', 'registration', 'settings', 'algorithm'])
def test_workspace_changed_evidence_clears_active_intent_and_keeps_previous_choice(drops, tmp_path, monkeypatch, change):
    source, result = drops
    session, selected = _session(drops)
    record = session.set_intended_contact(selected, INTENDED)
    path = tmp_path / 'work.scene.json'
    save_workspace(path, session, source, DIMS)
    data = read_workspace(path)
    fresh = result
    if change == 'cached_geometry':
        cached = next(row for row in data['rows'] if row['id'] == selected)
        cached['geometry']['floor_crossings'][0]['approach_feature']['faces'] = ['TOP']
    elif change == 'registration':
        fresh = _load(source, replace(result.registration, floor_y_mm=.5))
    elif change == 'settings':
        fresh = _load(source, result.registration, replace(result.settings, window_s=.096))
    else:
        monkeypatch.setattr('src.analysis.pipeline.scene_workspace.VERSION', 'observed-motion-next')
    restored, changed = restore_session(data, fresh, session.source_sha256)
    assert selected in changed
    row = restored.row(selected)
    assert row.get('intended_contact') is None
    assert row['decision'] == 'unreviewed'
    assert row['previous_review']['intended_contact'] == record
    assert row['previous_review']['decision'] == 'include'
    # The previous choice remains historical through a further unfinished save.
    save_workspace(path, restored, source, DIMS)
    assert next(r for r in read_workspace(path)['rows'] if r['id'] == selected)['previous_review']['intended_contact'] == record


@pytest.mark.parametrize('change', ['faces', 'registration', 'type', 'edition', 'decision', 'status'])
def test_damaged_active_intent_is_rejected_on_save_and_read(drops, tmp_path, change):
    source, _ = drops
    session, selected = _session(drops)
    session.set_intended_contact(selected, INTENDED)
    path = tmp_path / 'work.scene.json'
    save_workspace(path, session, source, DIMS)
    before = path.read_bytes()
    row = session.row(selected)
    if change == 'faces':
        row['intended_contact']['faces'] = ['TOP', 'BOTTOM']
    elif change == 'registration':
        row['intended_contact']['registration_sha256'] = 'a' * 64
    elif change == 'type':
        row['intended_contact']['ista_type'] = 'G'
    elif change == 'edition':
        row['intended_contact']['applied_edition'] = None
    elif change == 'decision':
        row['decision'] = 'exclude'
    else:
        row['evidence_status'] = 'geometry_changed'
    with pytest.raises(ValueError, match='[Ii]ntended contact'):
        save_workspace(path, session, source, DIMS)
    assert path.read_bytes() == before
    damaged = json.loads(before)
    damaged['rows'] = session.rows
    path.write_text(json.dumps(damaged), encoding='utf-8')
    with pytest.raises(ValueError, match='[Ii]ntended contact'):
        read_workspace(path)


@pytest.mark.parametrize('change', ['hash', 'type', 'floor', 'stale', 'missing_geometry'])
def test_slice_payload_links_intent_to_its_registered_geometry_and_context(drops, change):
    session, selected = _session(drops)
    session.set_intended_contact(selected, INTENDED)
    payload = json.loads(session.payload(selected))
    if change == 'hash':
        payload['detection']['registration_sha256'] = 'a' * 64
    elif change == 'type':
        payload['identity']['ista_type'] = 'G'
    elif change == 'floor':
        payload['detection']['registration']['floor_y_mm'] = None
    elif change == 'stale':
        payload['candidate']['evidence_status'] = 'geometry_changed'
    else:
        payload['detection'].pop('registration')
    with pytest.raises(ValueError, match='[Ii]ntended contact'):
        validate_scene_review_json(payload)


def test_selected_public_interval_carries_intent_through_slice_and_proc(drops, tmp_path):
    source, result = drops
    session, selected = _session(drops)
    record = session.set_intended_contact(selected, INTENDED)
    row = session.row(selected)
    header, raw = DataLoader().load_csv(str(source))
    path = tmp_path / 'drop.slice'
    save_slice_file(filepath=str(path), header_info=header, raw_data=raw, source_path=str(source),
                    full_start=float(result.signals.index[0]), full_end=float(result.signals.index[-1]),
                    user_start=row['start'], user_end=row['end'], box_dims=DIMS, pad_rows=1,
                    scene_review_json=session.payload(selected))
    metadata = read_slice_metadata(str(path))
    assert json.loads(metadata.scene_review_json)['candidate']['intended_contact'] == record
    frame = pd.DataFrame({'Frame': [1, 2]}, index=pd.Index([row['start'], row['end']], name='Time'))
    proc = tmp_path / 'drop.proc'
    save_proc_file(str(proc), add_timeline_context_columns(frame, {
        'scene_review_json': metadata.scene_review_json,
        'slice_start_sec': row['start'], 'slice_end_sec': row['end'],
    }))
    loaded = DataLoader().load_result_csv(str(proc))
    assert loaded[('Info', 'SceneReview', 'Json')].tolist() == [metadata.scene_review_json] * 2
    before = path.read_bytes()
    with pytest.raises(ValueError, match='conflict with declared artifact'):
        update_slice_box_dimensions(str(path), (310., 180., 90.))
    assert path.read_bytes() == before


def test_legacy_slice_dimension_rewrite_clears_old_local_frame_intent(drops, tmp_path):
    source, result = drops
    session, selected = _session(drops)
    session.set_intended_contact(selected, INTENDED)
    row = session.row(selected)
    header, raw = DataLoader().load_csv(str(source))
    # This separate legacy-format case has no source declaration of dimensions.
    # Current declared captures are protected from conflicting edits above.
    header.pop('artifact_metadata', None)
    path = tmp_path / 'legacy.slice'
    save_slice_file(filepath=str(path), header_info=header, raw_data=raw, source_path=str(source),
                    full_start=float(result.signals.index[0]), full_end=float(result.signals.index[-1]),
                    user_start=row['start'], user_end=row['end'], box_dims=DIMS, pad_rows=1,
                    scene_review_json=session.payload(selected))
    changed = update_slice_box_dimensions(str(path), (310., 180., 90.))
    assert json.loads(changed.scene_review_json)['candidate'].get('intended_contact') is None
