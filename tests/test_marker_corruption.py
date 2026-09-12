"""Literal independent geometry and fault-composition checks for synthetic arrays."""
from copy import deepcopy
import json

import numpy as np
import pytest

from src.simulation.marker_corruption import apply_corruption


PHYSICAL = 'physical_markers'
SOLVED = 'rigid_body_markers'
POLICY = 'world-y-up-box-local-fixed-center-v1'


@pytest.fixture
def inputs():
    profile = {
        'profile_id': 'literal-test-3', 'profile_version': '1', 'units': 'mm',
        'origin': 'box-geometric-center', 'dimension_policy': 'absolute-mm',
        'box_dims_mm': [20., 20., 20.], 'publication': 'synthetic test geometry',
        'source': 'independent literal points', 'license': 'same as repository',
        'markers': [{'id': 'F1', 'face': 'FRONT', 'xyz_mm': [1., 2., 10.]},
                    {'id': 'B1', 'face': 'BACK', 'xyz_mm': [-3., 4., -10.]},
                    {'id': 'R1', 'face': 'RIGHT', 'xyz_mm': [10., -2., 3.]}],
    }
    trajectory = {
        'schema_version': 1, 'source_kind': 'handcrafted_dummy', 'coordinate_policy': POLICY,
        'time_s': [0., .01, .021, .041, .2, .201, .45, .5],
        'frame': [2, 4, 10, 13, 14, 30, 31, 80],
        'body_origin_mm': [[100. + 5 * i, 200. + 2 * i, 300. - 3 * i] for i in range(8)],
        'rotation_matrix': [[[0., -1., 0.], [1., 0., 0.], [0., 0., 1.]]] * 8,
        'com_mm': [[101. + 5 * i, 203. + 2 * i, 302. - 3 * i] for i in range(8)],
    }
    return trajectory, profile


def _clean_expected():
    # Rz(+90) maps (x,y,z) to (-y,x,z), independently of generator code.
    initial = np.array([[98., 201., 310.], [96., 197., 290.], [102., 210., 303.]])
    return initial[None] + np.arange(8)[:, None, None] * np.array([5., 2., -3.])


def _window(kind, start, end, channel=PHYSICAL, **parameters):
    return {'kind': kind, 'channel': channel, 'start_index': start,
            'end_index_exclusive': end, **parameters}


def _flip(start, axis):
    return {'kind': 'flip_180_local_axis', 'channel': SOLVED, 'start_index': start, 'axis': axis}


def _run(inputs, events=(), seed=82):
    return apply_corruption(*inputs, {'schema_version': 1, 'events': list(events)}, seed)


def test_literal_nonidentity_pose_is_exact_and_every_return_is_detached(inputs):
    original = deepcopy(inputs)
    result = _run(inputs)
    for key in ('truth_markers', PHYSICAL, SOLVED):
        np.testing.assert_array_equal(result[key], _clean_expected())
    for key in ('frame', 'time_s', 'body_origin_mm', 'rotation_matrix', 'com_mm'):
        np.testing.assert_array_equal(result[key], inputs[0][key])
    assert result['frame'].dtype.kind == 'i'
    assert result['manifest']['source_kind'] == 'handcrafted_dummy'
    assert result['manifest']['expected_approval'] is False
    assert result['manifest']['expected_recommendation'] is None
    assert result['manifest']['evidence_level'] == 'synthetic_integration'
    assert result['manifest']['profile'] == inputs[1]
    assert len(result['manifest']['layout_hash']) == 64
    json.dumps(result['manifest'], allow_nan=False)
    for key, value in result.items():
        if isinstance(value, np.ndarray):
            for other in result.values():
                if isinstance(other, np.ndarray) and other is not value:
                    assert not np.shares_memory(value, other)
            value.flat[0] = 999
    result['manifest']['profile']['markers'][0]['xyz_mm'][0] = 999
    assert inputs == original


def test_optional_frame_and_com_do_not_infer_unprovided_truth(inputs):
    del inputs[0]['frame']
    del inputs[0]['com_mm']
    inputs[0]['source_kind'] = 'mujoco_synthetic'
    result = _run(inputs)
    np.testing.assert_array_equal(result['frame'], np.arange(8))
    assert result['com_mm'] is None
    assert result['manifest']['source_kind'] == 'mujoco_synthetic'


def test_noise_seed_changes_only_noise_and_freeze_derived_values(inputs):
    events = [_window('gaussian_noise', 1, 3, marker_ids=['F1'], std_mm=.25),
              _window('freeze', 3, 5, marker_ids=['F1']),
              _window('reconnect_jump', 5, 7, marker_ids=['B1'], offset_mm=[7., -3., 4.]),
              _window('missing', 6, 8, marker_ids=['R1'])]
    spec_before = deepcopy(events)
    first, repeat, changed = _run(inputs, events), _run(inputs, events), _run(inputs, events, seed=83)
    for key in ('truth_markers', 'frame', 'time_s', 'body_origin_mm', 'rotation_matrix', 'com_mm', SOLVED):
        np.testing.assert_array_equal(first[key], changed[key])
    np.testing.assert_array_equal(first[PHYSICAL], repeat[PHYSICAL])
    assert not np.array_equal(first[PHYSICAL][1:5, 0], changed[PHYSICAL][1:5, 0])
    np.testing.assert_array_equal(first[PHYSICAL][:, 1:], changed[PHYSICAL][:, 1:])
    np.testing.assert_array_equal(first[PHYSICAL][[0, 5, 6, 7], 0], changed[PHYSICAL][[0, 5, 6, 7], 0])
    np.testing.assert_array_equal(first[PHYSICAL][3:5, 0], np.repeat(first[PHYSICAL][2:3, 0], 2, axis=0))
    assert events == spec_before
    # Seed is irrelevant when no stochastic fault exists.
    clean_a, clean_b = _run(inputs, events[2:], seed=1), _run(inputs, events[2:], seed=2)
    np.testing.assert_array_equal(clean_a[PHYSICAL], clean_b[PHYSICAL])


def test_channel_rng_isolation_and_zero_noise(inputs):
    physical_noise = _window('gaussian_noise', 0, 8, std_mm=.1)
    first = _run(inputs, [physical_noise])
    both = _run(inputs, [_window('gaussian_noise', 0, 8, SOLVED, std_mm=.2), physical_noise])
    np.testing.assert_array_equal(first[PHYSICAL], both[PHYSICAL])
    np.testing.assert_array_equal(first[SOLVED], _clean_expected())
    zero = _run(inputs, [_window('gaussian_noise', 0, 8, std_mm=0)])
    np.testing.assert_array_equal(zero[PHYSICAL], _clean_expected())


def test_noise_and_world_offset_are_applied_before_freeze_and_missing(inputs):
    events = [_window('freeze', 2, 5, marker_ids=['F1']),
              _window('reconnect_jump', 1, 7, marker_ids=['F1'], offset_mm=[7., -3., 4.]),
              _window('missing', 3, 4, marker_ids=['F1']),
              _window('gaussian_noise', 1, 8, marker_ids=['F1'], std_mm=.5)]
    result = _run(inputs, events)
    np.testing.assert_array_equal(result[PHYSICAL][2, 0], result[PHYSICAL][1, 0])
    np.testing.assert_array_equal(result[PHYSICAL][4, 0], result[PHYSICAL][1, 0])
    assert np.isnan(result[PHYSICAL][3, 0]).all()
    np.testing.assert_array_equal(result[PHYSICAL][:, 1:], _clean_expected()[:, 1:])
    assert [event['ordinal'] for event in result['manifest']['events']] == [1, 3, 0, 2]


def test_later_freeze_uses_missing_prior_sample_and_overrides_active_earlier_freeze(inputs):
    events = [_window('freeze', 2, 6, marker_ids=['F1']),
              _window('missing', 3, 4, marker_ids=['F1']),
              _window('freeze', 4, 7, marker_ids=['F1'])]
    result = _run(inputs, events)
    np.testing.assert_array_equal(result[PHYSICAL][2, 0], _clean_expected()[1, 0])
    assert np.isnan(result[PHYSICAL][3:7, 0]).all()
    np.testing.assert_array_equal(result[PHYSICAL][7, 0], _clean_expected()[7, 0])


def test_freeze_snapshots_stable_identity_before_prior_label_routing(inputs):
    events = [_window('gaussian_noise', 1, 2, marker_ids=['F1'], std_mm=.5),
              _window('label_permutation', 1, 2, mapping={'F1': 'B1', 'B1': 'F1'}),
              _window('freeze', 2, 4, marker_ids=['F1'])]
    result = _run(inputs, events)
    np.testing.assert_array_equal(result[PHYSICAL][1, 0], _clean_expected()[1, 1])
    np.testing.assert_array_equal(result[PHYSICAL][2:4, 0], np.repeat(result[PHYSICAL][1:2, 1], 2, axis=0))


@pytest.mark.parametrize('channel', [PHYSICAL, SOLVED])
def test_reconnect_jump_is_a_world_mm_offset_in_one_channel(inputs, channel):
    result = _run(inputs, [_window('reconnect_jump', 2, 5, channel, marker_ids=['B1'], offset_mm=[7., -3., 4.])])
    expected = _clean_expected()
    expected[2:5, 1] += [7., -3., 4.]
    np.testing.assert_array_equal(result[channel], expected)
    np.testing.assert_array_equal(result[SOLVED if channel == PHYSICAL else PHYSICAL], _clean_expected())
    np.testing.assert_array_equal(result['truth_markers'], _clean_expected())


def test_finite_offset_overflow_is_rejected_instead_of_becoming_an_undeclared_gap(inputs):
    for origin in inputs[0]['body_origin_mm']:
        origin[0] = 1e308
    before = deepcopy(inputs)
    event = _window('reconnect_jump', 1, 3, marker_ids=['F1'], offset_mm=[1e308, 0., 0.])
    with pytest.raises(ValueError, match='arithmetic.*finite'):
        _run(inputs, [event])
    assert inputs == before


@pytest.mark.parametrize('mask_afterwards', [False, True])
def test_overflowed_gaussian_draw_is_rejected_before_a_missing_mask_can_hide_it(mask_afterwards):
    from src.simulation.marker_fixtures import example_profile
    trajectory = {
        'schema_version': 1, 'source_kind': 'handcrafted_dummy', 'coordinate_policy': POLICY,
        'time_s': [0., .008, .016], 'body_origin_mm': [[0., 0., 0.]] * 3,
        'rotation_matrix': [[[1., 0., 0.], [0., 1., 0.], [0., 0., 1.]]] * 3,
    }
    events = [_window('gaussian_noise', 0, 3, std_mm=1e308)]
    if mask_afterwards:
        events.append(_window('missing', 0, 3))
    with pytest.raises(ValueError, match='finite'):
        _run((trajectory, example_profile()), events, seed=1)


def test_missing_physical_identity_routes_with_the_label_and_cannot_be_refilled(inputs):
    events = [_window('missing', 2, 5, marker_ids=['F1']),
              _window('label_permutation', 1, 6, mapping={'F1': 'B1', 'B1': 'F1'}),
              _window('gaussian_noise', 0, 8, marker_ids=['F1'], std_mm=.1),
              _flip(3, 'X')]
    result = _run(inputs, events)
    assert np.isnan(result[PHYSICAL][2:5, 1]).all()
    np.testing.assert_array_equal(result[PHYSICAL][1:6, 0], _clean_expected()[1:6, 1])
    assert np.isfinite(result[SOLVED]).all()
    missing_solved = _run(inputs, [_window('missing', 2, 5, SOLVED), _flip(3, 'Y'),
                                  _window('gaussian_noise', 0, 8, SOLVED, std_mm=.1)])
    assert np.isnan(missing_solved[SOLVED][2:5]).all()
    np.testing.assert_array_equal(missing_solved[PHYSICAL], _clean_expected())


def _half_turn_expected(axis):
    # Rz(90) @ H local points, written independently as literal coordinates.
    local_world = {
        'X': [[2., 1., -10.], [4., -3., 10.], [-2., 10., -3.]],
        'Y': [[-2., -1., -10.], [-4., 3., 10.], [2., -10., -3.]],
        'Z': [[2., -1., 10.], [4., 3., -10.], [-2., -10., 3.]],
    }[axis]
    origins = np.array([[100. + 5 * i, 200. + 2 * i, 300. - 3 * i] for i in range(8)])
    return np.asarray(local_world)[None] + origins[:, None]


def test_half_turns_accumulate_locally_xx_restores_and_xy_yx_end_at_z(inputs):
    xx = _run(inputs, [_flip(2, 'X'), _flip(5, 'X')])
    xy = _run(inputs, [_flip(2, 'X'), _flip(5, 'Y')])
    yx = _run(inputs, [_flip(2, 'Y'), _flip(5, 'X')])
    for result in (xx, xy, yx):
        np.testing.assert_array_equal(result[PHYSICAL], _clean_expected())
        np.testing.assert_array_equal(result['truth_markers'], _clean_expected())
        np.testing.assert_array_equal(result['rotation_matrix'], inputs[0]['rotation_matrix'])
        np.testing.assert_array_equal(result[SOLVED][:2], _clean_expected()[:2])
    np.testing.assert_array_equal(xx[SOLVED][2:5], _half_turn_expected('X')[2:5])
    np.testing.assert_array_equal(xx[SOLVED][5:], _clean_expected()[5:])
    np.testing.assert_array_equal(xy[SOLVED][2:5], _half_turn_expected('X')[2:5])
    np.testing.assert_array_equal(yx[SOLVED][2:5], _half_turn_expected('Y')[2:5])
    np.testing.assert_array_equal(xy[SOLVED][5:], _half_turn_expected('Z')[5:])
    np.testing.assert_array_equal(yx[SOLVED][5:], xy[SOLVED][5:])


def test_genuine_truth_rotation_remains_physical_motion_when_solver_flips(inputs):
    rotations = [
        [[1., 0., 0.], [0., 1., 0.], [0., 0., 1.]],
        [[0., -1., 0.], [1., 0., 0.], [0., 0., 1.]],
        [[-1., 0., 0.], [0., -1., 0.], [0., 0., 1.]],
        [[0., 1., 0.], [-1., 0., 0.], [0., 0., 1.]],
    ] * 2
    inputs[0]['rotation_matrix'] = rotations
    expected_offsets = [
        [[1., 2., 10.], [-3., 4., -10.], [10., -2., 3.]],
        [[-2., 1., 10.], [-4., -3., -10.], [2., 10., 3.]],
        [[-1., -2., 10.], [3., -4., -10.], [-10., 2., 3.]],
        [[2., -1., 10.], [4., 3., -10.], [-2., -10., 3.]],
    ] * 2
    result = _run(inputs, [_flip(2, 'X')])
    expected = np.asarray(expected_offsets) + np.asarray(inputs[0]['body_origin_mm'])[:, None]
    np.testing.assert_array_equal(result['truth_markers'], expected)
    np.testing.assert_array_equal(result[PHYSICAL], expected)
    np.testing.assert_array_equal(result['rotation_matrix'], rotations)
    assert not np.array_equal(result[SOLVED][2:], expected[2:])


def test_noncommutative_label_cycles_use_time_then_input_order_and_simultaneous_copies(inputs):
    cycle = _window('label_permutation', 1, 6, mapping={'F1': 'B1', 'B1': 'R1', 'R1': 'F1'})
    swap = _window('label_permutation', 1, 6, mapping={'F1': 'B1', 'B1': 'F1'})
    cycle_swap, swap_cycle = _run(inputs, [cycle, swap]), _run(inputs, [swap, cycle])
    clean = _clean_expected()
    np.testing.assert_array_equal(cycle_swap[PHYSICAL][1:6], clean[1:6][:, [2, 1, 0]])
    np.testing.assert_array_equal(swap_cycle[PHYSICAL][1:6], clean[1:6][:, [0, 2, 1]])
    assert not np.array_equal(cycle_swap[PHYSICAL], swap_cycle[PHYSICAL])
    # Earlier start wins ordering even if later-start event occurs first in JSON.
    swap.update(start_index=3, end_index_exclusive=7)
    timed = _run(inputs, [swap, cycle])
    np.testing.assert_array_equal(timed[PHYSICAL][1:3], clean[1:3][:, [1, 2, 0]])
    np.testing.assert_array_equal(timed[PHYSICAL][3:6], clean[3:6][:, [2, 1, 0]])
    np.testing.assert_array_equal(timed[PHYSICAL][6:7], clean[6:7][:, [1, 0, 2]])
    np.testing.assert_array_equal(timed[PHYSICAL][7:], clean[7:])


def test_manifest_distinguishes_sample_positions_actual_frame_ids_and_exclusive_end(inputs):
    events = [_window('missing', 3, 5, marker_ids=['B1', 'F1']), _flip(6, 'Z')]
    result = _run(inputs, events)
    np.testing.assert_array_equal(result['time_s'], inputs[0]['time_s'])
    np.testing.assert_array_equal(result['frame'], inputs[0]['frame'])
    first, suffix = result['manifest']['events']
    assert first['marker_ids'] == ['F1', 'B1']  # Stable profile order.
    assert (first['start_index'], first['end_index_exclusive']) == (3, 5)
    assert (first['start_frame'], first['last_frame'], first['end_frame_exclusive']) == (13, 14, 30)
    assert (first['start_time_s'], first['last_time_s'], first['end_time_s_exclusive']) == (.041, .2, .201)
    assert (suffix['start_index'], suffix['end_index_exclusive']) == (6, 8)
    assert (suffix['start_frame'], suffix['last_frame'], suffix['end_frame_exclusive']) == (31, 80, None)
    assert (suffix['start_time_s'], suffix['last_time_s'], suffix['end_time_s_exclusive']) == (.45, .5, None)
    json.dumps(result['manifest'], allow_nan=False)
    empty_routing = _run(inputs, [_window('label_permutation', 0, 8, mapping={})])
    np.testing.assert_array_equal(empty_routing[PHYSICAL], _clean_expected())


@pytest.mark.parametrize('fault', ['time_duplicate', 'time_nan', 'time_one', 'time_string',
    'origin_shape', 'origin_inf', 'rotation_scaled', 'rotation_reflection', 'rotation_nan',
    'frame_float', 'frame_duplicate', 'frame_negative', 'frame_bool', 'com_shape',
    'source_real', 'coordinates', 'schema_bool', 'unknown_field'])
def test_invalid_truth_is_rejected_without_mutating_input(inputs, fault):
    trajectory = inputs[0]
    if fault == 'time_duplicate':
        trajectory['time_s'][2] = trajectory['time_s'][1]
    elif fault == 'time_nan':
        trajectory['time_s'][2] = float('nan')
    elif fault == 'time_one':
        trajectory['time_s'] = [0.]
    elif fault == 'time_string':
        trajectory['time_s'][2] = '.021'
    elif fault == 'origin_shape':
        trajectory['body_origin_mm'][2] = [1., 2.]
    elif fault == 'origin_inf':
        trajectory['body_origin_mm'][2][1] = float('inf')
    elif fault == 'rotation_scaled':
        trajectory['rotation_matrix'] = np.asarray(trajectory['rotation_matrix']).tolist()
        trajectory['rotation_matrix'][2][0][1] = -1.000001
    elif fault == 'rotation_reflection':
        trajectory['rotation_matrix'][2] = [[1., 0., 0.], [0., 1., 0.], [0., 0., -1.]]
    elif fault == 'rotation_nan':
        trajectory['rotation_matrix'][2] = [[float('nan'), 0., 0.], [0., 1., 0.], [0., 0., 1.]]
    elif fault == 'frame_float':
        trajectory['frame'] = [float(value) for value in trajectory['frame']]
    elif fault == 'frame_duplicate':
        trajectory['frame'][2] = trajectory['frame'][1]
    elif fault == 'frame_negative':
        trajectory['frame'][0] = -1
    elif fault == 'frame_bool':
        trajectory['frame'] = [False, True] * 4
    elif fault == 'com_shape':
        trajectory['com_mm'] = [[1., 2., 3.]]
    elif fault == 'source_real':
        trajectory['source_kind'] = 'real'
    elif fault == 'coordinates':
        trajectory['coordinate_policy'] = 'world-z-up'
    elif fault == 'schema_bool':
        trajectory['schema_version'] = True
    else:
        trajectory['velocity_mm_s'] = []
    before = deepcopy(inputs)
    with pytest.raises(ValueError):
        _run(inputs)
    assert json.dumps(inputs, sort_keys=True) == json.dumps(before, sort_keys=True)


@pytest.mark.parametrize('event', [
    {'kind': 'unknown'}, {'kind': None},
    _window('missing', 0, 1, channel='both'),
    _window('missing', True, 1), _window('missing', 0., 1),
    _window('missing', -1, 1), _window('missing', 8, 8),
    _window('missing', 1, 1), _window('missing', 0, 9),
    _window('missing', 0, 1, marker_ids=[]), _window('missing', 0, 1, marker_ids=['F1', 'F1']),
    _window('missing', 0, 1, marker_ids=['T2']), _window('missing', 0, 1, unexpected=1),
    _window('freeze', 0, 1),
    _window('gaussian_noise', 0, 1, std_mm=-.1),
    _window('gaussian_noise', 0, 1, std_mm=float('nan')),
    _window('gaussian_noise', 0, 1, std_mm=True),
    _window('reconnect_jump', 0, 1, offset_mm=[1., 2.]),
    _window('reconnect_jump', 0, 1, offset_mm=[1., 2., float('inf')]),
    {**_flip(2, 'X'), 'channel': PHYSICAL}, _flip(2, 'Q'),
    {**_flip(2, 'X'), 'marker_ids': ['F1']}, {**_flip(2, 'X'), 'end_index_exclusive': 3},
    _window('label_permutation', 0, 1, mapping={'F1': 'B1'}),
    _window('label_permutation', 0, 1, mapping={'F1': 'B1', 'B1': 'B1'}),
    _window('label_permutation', 0, 1, mapping={'F1': 'T2', 'T2': 'F1'}),
    _window('label_permutation', 0, 1, mapping=[]),
    _window('label_permutation', 0, 1, channel=SOLVED, mapping={'F1': 'F1'}),
    _window('label_permutation', 0, 1, marker_ids=['F1'], mapping={'F1': 'F1'}),
])
def test_malformed_or_unsupported_events_are_rejected(inputs, event):
    with pytest.raises(ValueError):
        _run(inputs, [event])


@pytest.mark.parametrize('seed', [True, -1, 1., '1', None])
def test_seed_requires_nonnegative_integer(inputs, seed):
    with pytest.raises(ValueError, match='seed'):
        _run(inputs, seed=seed)


@pytest.mark.parametrize('spec', [{'schema_version': True, 'events': []},
    {'schema_version': 1, 'events': {}}, {'schema_version': 1, 'events': [], 'unused': 1}, {}])
def test_specification_requires_exact_supported_schema(inputs, spec):
    with pytest.raises(ValueError):
        apply_corruption(*inputs, spec, 1)


def test_profile_geometry_validation_is_reused_without_modifying_profile(inputs):
    inputs[1]['markers'][0]['xyz_mm'] = [1., 2., 11.]
    before = deepcopy(inputs[1])
    with pytest.raises(ValueError, match='assigned face'):
        _run(inputs)
    assert inputs[1] == before
