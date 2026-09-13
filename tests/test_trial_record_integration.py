"""Trial intent stays separate from independently generated observed motion."""
from copy import deepcopy
import hashlib
import json

import numpy as np
import pytest

from src.analysis.pipeline.data_loader import DataLoader
from src.analysis.pipeline.parser import Parser
from src.analysis.pipeline.scene_detection import Registration, detect_scenes
from src.analysis.pipeline.scene_review import SceneReviewSession
from src.analysis.pipeline.scene_workspace import read_workspace, restore_session, save_workspace
from src.config.data_columns import FACE_PREFIX_TO_INFO
from src.simulation.scene_fixtures import write_sequence
from src.simulation.trial_record_fixtures import trial, trial_record, write_analytic_approach
from test_support_cycles import write_support_observations


@pytest.fixture(scope='module')
def recordings(tmp_path_factory):
    """Compute each public capture once; record variants reuse the same observations."""
    root = tmp_path_factory.mktemp('trial_records')
    folders = {kind: write_sequence(root / kind, kind) for kind in ('drops', 'partial', 'handling')}
    folders['support'] = write_support_observations(root / 'support', cycles=2)
    folders['analytic'] = write_analytic_approach(root / 'analytic')
    loaded = {}
    for kind, folder in folders.items():
        source = folder / 'observed.csv'
        header, raw = DataLoader().load_csv(str(source))
        parsed = Parser(FACE_PREFIX_TO_INFO).process(header, raw)
        result = detect_scenes(header, raw, parsed, registration=Registration.load(folder / 'registration.json'))
        loaded[kind] = (source, result, hashlib.sha256(source.read_bytes()).hexdigest())
    return loaded


def reviewed(recording, *, included='free_fall', ista_type='H'):
    source, result, digest = recording
    session = SceneReviewSession(result, digest)
    session.set_context(ista_type, '2018-03')
    for row in session.rows:
        session.set_decision(row['id'], 'include' if row['motion'] == included else 'exclude')
    return session


def included(session):
    return [row for row in session.rows if row['decision'] == 'include']


def test_repeated_postures_use_explicit_anchors_and_survive_workspace(recordings, tmp_path):
    source, result, digest = recordings['drops']
    session = reviewed(recordings['drops'])
    session.identify()
    rows = included(session)
    assert len(rows) == 2
    assert all(row['item_candidates'] == ['H/B04/D06', 'H/B16/D06'] for row in rows)
    assert all(not row['identity']['confirmed'] for row in rows)
    original_signals = result.signals.copy(deep=True)
    record = trial_record(source, [trial('first', 3, 1.6, 'H/B04/D06'),
                                    trial('later', 7, 4.4, 'H/B16/D06')])
    session.set_trial_record(record)
    session.identify()
    for row, expected in zip(rows, ('H/B04/D06', 'H/B16/D06')):
        assert row['item_candidates'] == [expected]
        assert not row['identity']['confirmed']
        session.confirm_item(row['id'], expected)
    path = tmp_path / 'recorded.scene-review.json'
    save_workspace(path, session, source, (300., 180., 90.))
    restored, changed = restore_session(read_workspace(path), result, digest)
    assert not changed
    assert restored.trial_record == session.trial_record
    assert restored.rows == session.rows
    np.testing.assert_array_equal(result.signals.to_numpy(), original_signals.to_numpy())
    assert hashlib.sha256(source.read_bytes()).hexdigest() == digest
    payload = json.loads(restored.payload(rows[0]['id']))
    assert payload['trial_record'] == session.trial_record
    assert payload['identity']['scenario_id'] == 'H/B04/D06'


def test_missing_record_and_retest_never_shift_later_items(recordings):
    source = recordings['drops'][0]
    session = reviewed(recordings['drops'])
    session.set_trial_record(trial_record(source, [trial('uncaptured', 9, 7., 'H/B04/D01'),
        trial('first', 3, 1.6, 'H/B16/D06'),
        trial('repeat', 5, 4.4, 'H/B16/D06', repeat_of='first')]))
    session.identify()
    assert all(row['item_candidates'] == ['H/B16/D06'] for row in included(session))
    assert [row['start'] for row in included(session)] == sorted(row['start'] for row in included(session))


@pytest.mark.parametrize('item,kind', [('H/B03', 'tip_over'), ('H/B05', 'rotational_flat_drop'),
                                    ('H/B06', 'rotational_edge_drop'), ('H/B22', 'full_rotational_flat_drop')])
def test_supported_motion_keeps_recorded_kind_without_claiming_apparatus(recordings, item, kind):
    source, result, digest = recordings['support']
    session = reviewed(recordings['support'], included='tip_or_rotation')
    session.set_trial_record(trial_record(source, [trial('support-1', 1, 1.2, item, anchor_kind='peak'),
                                                trial('support-2', 2, 4., item, anchor_kind='peak')]))
    session.identify()
    rows = included(session)
    assert len(rows) == 2
    for row in rows:
        assert row['item_candidates'] == [item]
        assert row['motion'] == 'tip_or_rotation'
        assert not row['identity']['confirmed']
        session.confirm_item(row['id'], item)
        assert row['identity']['scenario_kind'] == kind
        assert json.loads(session.payload(row['id']))['identity']['scenario_kind'] == kind


def test_bad_source_does_not_replace_confirmed_record_or_original_data(recordings):
    source, _, digest = recordings['drops']
    session = reviewed(recordings['drops'])
    session.set_trial_record(trial_record(source, [trial('first', 1, 1.6, 'H/B04/D06')]))
    session.identify()
    row = included(session)[0]
    session.confirm_item(row['id'], 'H/B04/D06')
    before_rows, before_record = deepcopy(session.rows), deepcopy(session.trial_record)
    other = deepcopy(before_record)
    other['capture']['sha256'] = 'f' * 64
    with pytest.raises(ValueError):
        session.set_trial_record(other)
    assert session.rows == before_rows
    assert session.trial_record == before_record
    assert hashlib.sha256(source.read_bytes()).hexdigest() == digest


def test_analytic_wrong_face_retains_g16_intent_and_different_approach(recordings):
    source, result, digest = recordings['analytic']
    session = reviewed(recordings['analytic'], ista_type='G')
    record = json.loads((source.parent / 'trial_record.json').read_text())
    session.set_trial_record(record)
    session.identify()
    rows = included(session)
    assert len(rows) == 1
    row = rows[0]
    assert row['record_evidence']['association'] == 'linked'
    assert row['record_evidence']['anchor_time_s'] == .32
    assert row['item_candidates'] == ['G16']
    assert row['observed_consistency']['expected_faces'] == ['LEFT']
    assert row['observed_consistency']['observed_faces'] == ['BOTTOM']
    assert row['observed_consistency']['approach'] == 'different'
    assert row['observed_consistency']['motion'] == 'compatible'
    assert not row['identity']['confirmed']
    session.confirm_item(row['id'], 'G16')
    assert row['identity']['scenario_id'] == 'G16'
    assert 'intended_contact' not in row  # Independent operator contact choice stays independent.
    # Direct comparison to the independently specified physical input, after detection.
    assert result.corners_m[39, :, 1].min() * 1000 == pytest.approx(12.24288, abs=1e-9)
    assert result.corners_m[40, :, 1].min() * 1000 == pytest.approx(0., abs=1e-9)
    assert result.corners_m[41, :, 1].min() * 1000 == pytest.approx(0., abs=1e-9)
    assert hashlib.sha256(source.read_bytes()).hexdigest() == digest


def test_partial_capture_can_link_record_but_not_verify_complete_motion(recordings):
    source = recordings['partial'][0]
    session = reviewed(recordings['partial'])
    session.set_trial_record(trial_record(source, [
        trial('uncaptured-release', 1, 1.6, 'H/B04/D01'),
        trial('observed-first-part', 2, 1.7, 'H/B04/D06', anchor_kind='motion'),
        trial('observed-last-part', 3, 4.4, 'H/B16/D06')]))
    session.identify()
    rows = included(session)
    assert len(rows) == 2 and rows[0]['left_censored'] and rows[1]['right_censored']
    for row, expected in zip(rows, ('H/B04/D06', 'H/B16/D06')):
        assert row['item_candidates'] == [expected]
        assert row['record_evidence']['association'] == 'linked'
        assert row['observed_consistency']['approach'] == 'unavailable'
        assert row['observed_consistency']['motion'] == 'unavailable'
        session.confirm_item(row['id'], expected)
        assert row['identity']['confirmed']


@pytest.mark.parametrize('entries,reason', [
    ([trial('a', 1, 1.6, 'H/B04/D06'), trial('b', 2, 1.6, 'H/B16/D06')], 'ambiguous_anchors'),
    ([trial('a', 2, 1.6, 'H/B04/D06'), trial('b', 1, 4.4, 'H/B16/D06')], 'contradictory_order')])
def test_ambiguous_or_contradictory_records_do_not_force_trial_identity(recordings, entries, reason):
    source = recordings['drops'][0]
    session = reviewed(recordings['drops'])
    session.set_trial_record(trial_record(source, entries))
    session.identify()
    row = included(session)[0]
    assert row['record_evidence']['association'] == reason
    assert not row['record_evidence']['confirmation_supported']
    assert not row['identity']['confirmed']
    with pytest.raises(ValueError):
        session.confirm_item(row['id'], 'H/B04/D06')


def test_handling_record_does_not_promote_air_rotation_to_a_trial(recordings):
    source = recordings['handling'][0]
    session = reviewed(recordings['handling'], included='tip_or_rotation')
    session.set_trial_record(trial_record(source, [trial('robot', 1, 4., None, anchor_kind='motion')]))
    session.identify()
    rows = [row for row in included(session) if row['start'] <= 4. <= row['end']]
    assert len(rows) == 1
    row = rows[0]
    assert row['record_evidence']['association'] == 'handling_record'
    assert row['item_candidates'] == []
    assert row['identity']['scenario_id'] is None
    assert not row['identity']['confirmed']


def test_hazard_intent_does_not_invent_a_hazard_observation(recordings):
    source = recordings['analytic'][0]
    session = reviewed(recordings['analytic'], ista_type='G')
    session.set_trial_record(trial_record(source, [trial('hazard', 1, .32, 'G17', anchor_kind='contact',
        conditions={'package_form': 'standard', 'hazard_used': True})], ista_type='G'))
    session.identify()
    row = included(session)[0]
    assert row['item_candidates'] == ['G17']
    assert row['observed_consistency']['hazard_contact'] == 'unverified'
    session.confirm_item(row['id'], 'G17')
    assert row['identity']['scenario_kind'] == 'hazard_drop'
