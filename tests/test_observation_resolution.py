"""Literal independent oracles for canonical-exact-v1; no producer oracle."""
from itertools import permutations

import numpy as np
import pytest

from src.analysis.compare.impact_metrics import MetricValue
from src.analysis.compare.observation_resolution import resolve_observations


def variant(name, value, *, observation='A', reason=''):
    return dict(name=name, sha256=name * 64, path=name + '.proc',
                observation_key=(observation, 0., 1., 'G01'), reasons=[],
                metrics={'value': MetricValue(value, reason)})


@pytest.mark.parametrize('members,expected,status', [
    ([variant('a', -4., reason='missing Y'), variant('b', -4.)], -4., 'contributing'),
    ([variant('a', -4.), variant('b', -4.)], -4., 'equivalent'),
    ([variant('a', -4.), variant('b', -2.)], None, 'conflict'),
    ([variant('a', -4., reason='invalid event'), variant('b', None, reason='missing')], None, 'invalid'),
    ([variant('a', -0.), variant('b', np.float64(0.))], 0., 'equivalent'),
    ([variant('a', 1.), variant('b', np.nextafter(1., 2.))], None, 'conflict'),
])
def test_literal_resolution_under_every_permutation(members, expected, status):
    reference = None
    for order in permutations(members):
        result = resolve_observations(order, {'value': 'numeric'})
        observation = next(iter(result['observations'].values()))['value']
        assert observation['value'] == expected
        assert observation['status'] == status
        assert result['observations'] == reference if reference is not None else True
        reference = result['observations']
        if status == 'conflict':
            assert observation['reason_code'] == 'conflicting_valid_variants'
            assert not observation['sources']
        if members[0]['metrics']['value'].reason:
            assert result['files']['a']['metric_resolution']['value']['status'] == 'invalid'
            assert result['files']['a']['metric_resolution']['value']['reason'] == members[0]['metrics']['value'].reason


@pytest.mark.parametrize('value', [True, np.bool_(True), None, float('nan'), float('inf'), '1'])
def test_invalid_numeric_never_becomes_a_valid_variant(value):
    result = resolve_observations([variant('a', value)], {'value': 'numeric'})
    assert next(iter(result['observations'].values()))['value']['status'] == 'invalid'


def test_categories_and_independent_observations_have_literal_counts():
    members = [variant('a', 'C1'), variant('b', 'C1'), variant('c', 'C3', observation='B')]
    for order in permutations(members):
        result = resolve_observations(order, {'value': 'categorical'})
        values = [v['value']['value'] for v in result['observations'].values()]
        assert values == ['C1', 'C3']
        assert [v['value']['status'] for v in result['observations'].values()] == ['equivalent', 'contributing']


def test_gate_precedes_grouping_and_invalidity_does_not_cross_metrics():
    a, b = variant('a', -4.), variant('b', -2.)
    a['metrics']['category'] = MetricValue(None, 'invalid event')
    b['metrics']['category'] = MetricValue('C1')
    result = resolve_observations([a, b], {'value': 'numeric', 'category': 'categorical'})
    metrics = next(iter(result['observations'].values()))
    assert metrics['value']['status'] == 'conflict'
    assert metrics['category']['value'] == 'C1'
    b['reasons'] = ['SourceKind mismatch']
    result = resolve_observations([a, b], {'value': 'numeric', 'category': 'categorical'})
    assert next(iter(result['observations'].values()))['value']['value'] == -4.
    assert result['files']['b']['metric_resolution']['value']['status'] == 'ineligible'
