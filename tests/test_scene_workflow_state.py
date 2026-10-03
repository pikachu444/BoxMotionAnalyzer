"""Independent bounds, decisions and invalid transport for PUB04."""
from copy import deepcopy
import json

import pytest

from src.analysis.pipeline.scene_review import validate_scene_review_json
from src.analysis.pipeline.scene_workspace import save_workspace, restore_session, read_workspace
from src.analysis.pipeline.scene_workflow_state import PLAN_SPEC, validate_plot_view, validate_history
from src.simulation.scene_review_fixtures import public_raw, ui_session, VERTICAL


@pytest.fixture(scope='module')
def source(tmp_path_factory):
    return public_raw(tmp_path_factory.mktemp('pub04-state'))


def plot_view(source):
    session = ui_session(source, 1)
    return dict(schema_version=1, plan_spec=PLAN_SPEC, status='valid',
        source_sha256=session.source_sha256, signal=VERTICAL, targets=[],
        units='mm/s', time_basis='capture_seconds', capture_interval_s=[0., 12.],
        xlim=[0., 3.], ylim=[-100., 100.])


def test_revert_and_multiple_edits_keep_prior_decisions_and_clean_manual_rows(source, tmp_path):
    s = ui_session(source, 1)
    s.set_context('G', '2018-03')
    s.set_decision('scene_001', 'include')
    s.set_range('scene_001', .14, .30)
    s.set_decision('scene_001', 'exclude')
    s.set_range('scene_001', .16, .28)
    s.revert_detected_range('scene_001')
    row = s.row('scene_001')
    assert (row['start'], row['end'], row['auto_start'], row['auto_end']) == (.1, .35, .1, .35)
    assert row['decision'] == 'unreviewed' and not row['identity']['confirmed']
    actions = s.history['entries']
    assert [e['snapshot']['decision'] for e in actions if e['action'] == 'range_edit'] == ['include', 'exclude']
    assert actions[-1]['action'] == 'revert_detected_range'
    assert (actions[-1]['snapshot']['start'], actions[-1]['snapshot']['end']) == (.16, .28)
    s.remove('scene_001')
    manual = s.add_range(1., 2.)  # No automatic rows remain.
    assert manual == 'manual_001'
    assert s.row(manual)['auto_start'] is None and s.row(manual)['auto_end'] is None
    assert s.row(manual)['decision'] == 'unreviewed'
    with pytest.raises(ValueError, match='no detected range'):
        s.revert_detected_range(manual)
    s.refresh(s.result)
    path = tmp_path/'work.json'
    save_workspace(path, s, source, (300., 180., 90.), selected_id=manual,
                   signal=VERTICAL, plot_view=plot_view(source))
    data = read_workspace(path)
    restored, _ = restore_session(data, s.result, s.source_sha256)
    assert restored.history == s.history and restored.deleted_ids == {'scene_001'}
    assert restored.manual_serial == 1 and restored.add_range(3., 4.) == 'manual_002'
    assert data['plot_view']['xlim'] == [0., 3.] and data['context']['type_basis'] == 'operator'


@pytest.mark.parametrize('key,value', [('schema_version', 99), ('schema_version', True),
    ('plan_spec', 'wrong'), ('units', 'm/s'), ('time_basis', 'frames'),
    ('source_sha256', 'x'*64), ('xlim', [0., float('nan')]), ('ylim', [1., 1.]),
    ('capture_interval_s', [True, 12.])])
def test_plot_contract_rejects_version_source_clock_units_and_limits(source, key, value):
    packet = plot_view(source)
    packet[key] = value
    with pytest.raises(ValueError):
        validate_plot_view(packet)


def test_workspace_plot_binding_clock_and_legacy_are_explicit(source, tmp_path):
    s = ui_session(source, 1)
    path = tmp_path/'work.json'
    good = save_workspace(path, s, source, (300., 180., 90.), signal=VERTICAL,
                          plot_view=plot_view(source))
    for key, value in [('source_sha256', '0'*64), ('signal', 'Relative rotation (deg)'), ('targets', ['Marker B1'])]:
        bad = deepcopy(good)
        bad['plot_view'][key] = value
        path.write_text(json.dumps(bad), encoding='utf-8')
        with pytest.raises(ValueError):
            read_workspace(path)
    bad = deepcopy(good)
    bad['plot_view']['capture_interval_s'] = [1., 13.]
    with pytest.raises(ValueError, match='clock differs'):
        restore_session(bad, s.result, s.source_sha256)
    legacy = deepcopy(good)
    for key in ('schema_version', 'plan_spec', 'history', 'plot_view'):
        legacy.pop(key)
    legacy['context'].pop('type_basis')
    restored, changed = restore_session(legacy, s.result, s.source_sha256)
    assert not changed and restored.type_basis == 'unconfirmed'
    legacy['plot_view'] = good['plot_view']
    with pytest.raises(ValueError, match='extensions need'):
        restore_session(legacy, s.result, s.source_sha256)


def test_type_change_preserves_inclusion_but_invalidates_identity_and_audits_basis(source):
    s = ui_session(source, 1)
    s.set_context('G', '2018-03', type_basis='source_declaration')
    s.set_decision('scene_001', 'include')
    with pytest.raises(ValueError, match='Confirm Type'):
        s.confirm_item('scene_001', 'G/B04/D06')
    s.set_context('H', '2018-03')
    assert s.type_basis == 'operator'
    assert s.row('scene_001')['decision'] == 'include'
    assert s.row('scene_001')['identity']['ista_type'] == 'H'
    prior = s.history['entries'][-1]
    assert prior['context']['ista_type'] == 'G' and prior['context']['type_basis'] == 'source_declaration'
    s.set_decision('scene_001', 'exclude')
    s.set_decision('scene_001', 'include')
    packet = json.loads(s.payload('scene_001'))
    assert packet['schema_version'] == 2 and packet['plan_spec'] == PLAN_SPEC
    assert packet['type_basis'] == 'operator' and packet['history'] == s.history
    assert validate_scene_review_json(packet)
    packet['history']['entries'][0]['source_sha256'] = '0'*64
    with pytest.raises(ValueError, match='another source'):
        validate_scene_review_json(packet)
    history = deepcopy(s.history)
    history['entries'][0]['snapshot']['boundary_policy'] = 'half-open-frames'
    with pytest.raises(ValueError, match='clock or boundary'):
        validate_history(history)


@pytest.mark.parametrize('value', [False, '.1', float('nan'), float('inf')])
def test_new_review_packet_rejects_non_numeric_or_non_finite_time(source, value):
    s = ui_session(source, 1)
    s.set_decision('scene_001', 'include')
    packet = json.loads(s.payload('scene_001'))
    packet['candidate']['start'] = value
    with pytest.raises(ValueError, match='finite capture seconds'):
        validate_scene_review_json(packet)
