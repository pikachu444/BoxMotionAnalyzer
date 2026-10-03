"""Bounded PUB04 transport: operator history and source-bound plot view."""
from copy import deepcopy
import math
import re

PLAN_SPEC = 'ISTA6A-PLAN-20261001-v1'
SCHEMA_VERSION = 2
TYPE_BASES = {'unconfirmed', 'operator', 'test_record', 'source_declaration', 'legacy_unconfirmed'}
HISTORY_ACTIONS = {'range_edit', 'revert_detected_range', 'decision', 'add', 'remove',
                   'test_context_changed', 'test_record_changed', 'geometry_changed',
                   'detection_context_changed', 'confirm_item', 'intended_contact', 'evidence_changed'}


def finite(value):
    return type(value) in (float, int) and math.isfinite(value)


def contract(data):
    """Version-1 files are explicit legacy; extensions require the new envelope."""
    if 'schema_version' not in data and 'plan_spec' not in data:
        if any(key in data for key in ('history', 'plot_view', 'type_basis')):
            raise ValueError('Scene workflow extensions need schema_version and plan_spec.')
        return False
    if type(data.get('schema_version')) is not int or data['schema_version'] != SCHEMA_VERSION:
        raise ValueError('Unsupported scene workflow schema_version.')
    if data.get('plan_spec') != PLAN_SPEC:
        raise ValueError('Unsupported scene workflow plan_spec.')
    return True


def empty_history():
    return {'schema_version': 1, 'plan_spec': PLAN_SPEC, 'entries': []}


def validate_history(value):
    try:
        if type(value['schema_version']) is not int or value['schema_version'] != 1 or value['plan_spec'] != PLAN_SPEC:
            raise ValueError('Unsupported scene history contract.')
        if not isinstance(value['entries'], list):
            raise ValueError('Invalid scene history entries.')
        for serial, entry in enumerate(value['entries'], 1):
            if type(entry['serial']) is not int or entry['serial'] != serial or entry['action'] not in HISTORY_ACTIONS:
                raise ValueError('Invalid scene history action or order.')
            if not re.fullmatch('[0-9a-f]{64}', entry['source_sha256']):
                raise ValueError('Invalid scene history source.')
            context = entry['context']
            if context['ista_type'] not in ('Unknown', 'G', 'H') or context['type_basis'] not in TYPE_BASES:
                raise ValueError('Invalid scene history Type context.')
            if context['applied_edition'] is not None and not isinstance(context['applied_edition'], str):
                raise ValueError('Invalid scene history edition.')
            state = entry['snapshot']
            if not re.fullmatch('(scene|manual)_[0-9]{3,}', state['id']):
                raise ValueError('Invalid scene history row.')
            if state['time_basis'] != 'capture_seconds' or state['boundary_policy'] != 'inclusive-gui-seconds':
                raise ValueError('Invalid scene history clock or boundary policy.')
            if not (finite(state['start']) and finite(state['end']) and state['start'] <= state['end']):
                raise ValueError('Invalid scene history range.')
            if state['decision'] not in ('unreviewed', 'include', 'exclude'):
                raise ValueError('Invalid scene history decision.')
            identity = state['identity']
            if identity['ista_type'] not in ('Unknown', 'G', 'H') or type(identity['confirmed']) is not bool:
                raise ValueError('Invalid historical identity.')
    except (KeyError, TypeError, AttributeError) as exc:
        raise ValueError('Incomplete scene history.') from exc
    return deepcopy(value)


def unavailable_plot_view():
    return {'schema_version': 1, 'plan_spec': PLAN_SPEC, 'status': 'unavailable', 'reason': 'not_captured'}


def validate_plot_view(value, *, source_sha256=None, signal=None, targets=None):
    try:
        if type(value['schema_version']) is not int or value['schema_version'] != 1 or value['plan_spec'] != PLAN_SPEC:
            raise ValueError('Unsupported scene plot view contract.')
        if value['status'] == 'unavailable' and value.get('reason') == 'not_captured':
            return deepcopy(value)
        if value['status'] != 'valid' or value['time_basis'] != 'capture_seconds':
            raise ValueError('Invalid scene plot view status or clock.')
        if not isinstance(value['source_sha256'], str) or not re.fullmatch('[0-9a-f]{64}', value['source_sha256']):
            raise ValueError('Invalid scene plot source.')
        if source_sha256 is not None and value['source_sha256'] != source_sha256:
            raise ValueError('Scene plot view source differs from workspace.')
        if not isinstance(value['signal'], str) or not value['signal'] or (signal is not None and signal != value['signal']):
            raise ValueError('Scene plot view signal differs from workspace.')
        if not isinstance(value['targets'], list) or any(not isinstance(t, str) for t in value['targets']):
            raise ValueError('Invalid scene plot targets.')
        if targets is not None and value['targets'] != list(targets):
            raise ValueError('Scene plot targets differ from workspace.')
        expected_unit = {'Vertical speed (mm/s)': 'mm/s', 'Relative rotation (deg)': 'deg'}.get(value['signal'])
        if value['units'] not in ('mm', 'cm', 'm', 'mm/s', 'deg', 'unit unknown'):
            raise ValueError('Unsupported scene plot units.')
        if expected_unit is not None and value['units'] != expected_unit:
            raise ValueError('Scene plot units differ from signal.')
        for key in ('capture_interval_s', 'xlim', 'ylim'):
            pair = value[key]
            if not isinstance(pair, list) or len(pair) != 2 or any(not finite(v) for v in pair) or pair[0] >= pair[1]:
                raise ValueError('Invalid scene plot limits or capture interval.')
    except (KeyError, TypeError, AttributeError) as exc:
        raise ValueError('Incomplete scene plot view.') from exc
    return deepcopy(value)
