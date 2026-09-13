"""Optional operator test records, bound by capture hashes and explicit time anchors.

Association is independent of observed agreement and never establishes ISTA conformity.
"""
from copy import deepcopy
import hashlib
import json
import math
from pathlib import Path
import re

import numpy as np

from .intended_contact import feature_corners
from src.config.config_app import FACE_DEFINITIONS

KIND = 'boxmotion-trial-record'
VERSION = 1
ITEM_KINDS = {**{f'G{i:02d}': 'free_fall' for i in range(1, 17)}, 'G17': 'hazard_drop',
              **{f'H/{block}/D{i:02d}': 'free_fall' for block in ('B04', 'B16') for i in range(1, 7)},
              'H/B03': 'tip_over', 'H/B05': 'rotational_flat_drop',
              'H/B06': 'rotational_edge_drop', 'H/B22': 'full_rotational_flat_drop'}
CONDITIONS = {'target_faces', 'critical_face_status', 'package_form', 'hazard_used',
              'transportation_start_face', 'pivot_faces', 'lifted_edge_faces',
              'support_height_mm', 'release_recorded', 'screen_face'}


def _object(value, allowed, required, name):
    if not isinstance(value, dict) or set(value) - allowed or required - set(value):
        raise ValueError(f'Invalid {name} fields.')


def _text(value):
    return isinstance(value, str) and bool(value.strip()) and '\x00' not in value


def _number(value):
    return type(value) in (int, float) and math.isfinite(value)


def _validate_trial_record(value):
    data = json.loads(value) if isinstance(value, str) else deepcopy(value)
    _object(data, {'kind', 'version', 'record_id', 'capture', 'ista_type', 'applied_edition', 'eligibility', 'trials'},
            {'kind', 'version', 'record_id', 'capture', 'ista_type', 'applied_edition', 'trials'}, 'test record')
    if data['kind'] != KIND or type(data['version']) is not int or data['version'] != VERSION or not _text(data['record_id']):
        raise ValueError('Unsupported test record.')
    capture = data['capture']
    _object(capture, {'sha256', 'basis', 'time_basis'}, {'sha256', 'basis', 'time_basis'}, 'capture')
    if not isinstance(capture['sha256'], str) or not re.fullmatch('[0-9a-fA-F]{64}', capture['sha256']):
        raise ValueError('Test record needs a capture SHA-256.')
    capture['sha256'] = capture['sha256'].lower()
    if capture['basis'] not in ('active', 'original') or capture['time_basis'] != 'capture_seconds':
        raise ValueError('Test record anchors must use capture seconds and a declared hash basis.')
    if data['ista_type'] not in ('Unknown', 'G', 'H') or (data['applied_edition'] is not None and not _text(data['applied_edition'])):
        raise ValueError('Invalid test record Type or applied edition.')
    if 'eligibility' in data:
        eligibility = data['eligibility']
        _object(eligibility, {'product_category', 'shipment_method', 'handling_method', 'mass_kg', 'girth_mm'}, set(), 'eligibility')
        for key, choices in [('product_category', ('tv_monitor',)), ('shipment_method', ('parcel', 'ltl')),
                             ('handling_method', ('standard', 'pallet'))]:
            if key in eligibility and eligibility[key] not in choices:
                raise ValueError(f'Invalid eligibility {key}.')
        for key in ('mass_kg', 'girth_mm'):
            if key in eligibility and (not _number(eligibility[key]) or eligibility[key] <= 0):
                raise ValueError(f'Eligibility {key} must be finite and positive.')
    if not isinstance(data['trials'], list):
        raise ValueError('Trials must be a list.')
    ids = set()
    for trial in data['trials']:
        required = {'attempt_id', 'performed_order', 'anchor_time_s', 'anchor_kind', 'activity_kind', 'item'}
        _object(trial, required | {'repeat_of', 'conditions'}, required, 'trial')
        if not _text(trial['attempt_id']) or trial['attempt_id'] in ids:
            raise ValueError('Trial attempt IDs must be unique nonempty strings.')
        ids.add(trial['attempt_id'])
        if type(trial['performed_order']) is not int or trial['performed_order'] < 1:
            raise ValueError('Performed order must be a positive integer.')
        if trial['anchor_time_s'] is not None and not _number(trial['anchor_time_s']):
            raise ValueError('Trial anchor must be finite capture seconds or null.')
        if trial['anchor_kind'] not in ('release', 'contact', 'motion', 'peak') or trial['activity_kind'] not in ('trial', 'handling'):
            raise ValueError('Invalid trial anchor or activity kind.')
        if trial['item'] is not None and trial['item'] not in ITEM_KINDS:
            raise ValueError('Unsupported trial item.')
        if trial['item'] and data['ista_type'] != 'Unknown' and not trial['item'].startswith(data['ista_type']):
            raise ValueError('Trial item conflicts with the recorded Type.')
        if trial['activity_kind'] == 'handling' and trial['item'] is not None:
            raise ValueError('Handling entries cannot declare a protocol trial item.')
        if 'repeat_of' in trial and not _text(trial['repeat_of']):
            raise ValueError('repeat_of must identify an attempt.')
        conditions = trial.get('conditions', {})
        _object(conditions, CONDITIONS, set(), 'trial conditions')
        for key, choices in [('critical_face_status', ('selected', 'unknown')),
                             ('package_form', ('standard', 'flat', 'elongated'))]:
            if key in conditions and conditions[key] not in choices:
                raise ValueError(f'Invalid trial condition {key}.')
        for key in ('target_faces', 'pivot_faces', 'lifted_edge_faces'):
            if key in conditions:
                faces = conditions[key]
                if not isinstance(faces, list) or (key != 'target_faces' and len(faces) != 2):
                    raise ValueError(f'Invalid local feature {key}.')
                feature_corners(faces)
                conditions[key] = sorted(faces)
        for key in ('transportation_start_face', 'screen_face'):
            if key in conditions and conditions[key] not in FACE_DEFINITIONS:
                raise ValueError(f'Invalid local face {key}.')
        for key in ('hazard_used', 'release_recorded'):
            if key in conditions and type(conditions[key]) is not bool:
                raise ValueError(f'Trial condition {key} must be boolean.')
        if 'support_height_mm' in conditions and (not _number(conditions['support_height_mm']) or conditions['support_height_mm'] < 0):
            raise ValueError('Support height must be finite nonnegative millimeters.')
    for trial in data['trials']:
        if 'repeat_of' in trial and (trial['repeat_of'] not in ids or trial['repeat_of'] == trial['attempt_id']):
            raise ValueError('repeat_of must reference another recorded attempt.')
    json.dumps(data, allow_nan=False)
    return data


def validate_trial_record(value):
    try:
        return _validate_trial_record(value)
    except (TypeError, KeyError, AttributeError, OverflowError) as error:
        raise ValueError('Invalid test record values.') from error


def load_trial_record(path):
    return validate_trial_record(Path(path).read_text(encoding='utf-8-sig'))


def record_digest(record):
    return hashlib.sha256(json.dumps(record, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def validate_binding(record, source_sha256, original_source_sha256=None):
    expected = source_sha256 if record['capture']['basis'] == 'active' else original_source_sha256
    if expected is None or record['capture']['sha256'] != str(expected).lower():
        raise ValueError('Test record capture hash does not match the verified capture.')


def eligibility_suggestion(record, *, applied_edition=None):
    evidence = {'suggested_type': None, 'status': 'unverified', 'reference': '2018-03 p.2; not conformity or applied-edition proof'}
    values = record.get('eligibility', {})
    edition = applied_edition or record['applied_edition']
    if (edition != '2018-03' or record['applied_edition'] not in (None, edition)
            or set(values) != {'product_category', 'shipment_method', 'handling_method', 'mass_kg', 'girth_mm'}):
        return evidence
    if values['product_category'] != 'tv_monitor' or values['handling_method'] != 'standard':
        return evidence
    if values['shipment_method'] == 'parcel' and values['mass_kg'] < 68 and values['girth_mm'] <= 4190:
        evidence.update(suggested_type='G', status='conditional_suggestion')
    elif values['shipment_method'] == 'ltl' and (values['mass_kg'] >= 68 or values['girth_mm'] > 4190):
        evidence.update(suggested_type='H', status='conditional_suggestion')
    return evidence


def associate(record, rows, row, ista_type, applied_edition):
    """Use explicit anchors and current reviewed ranges, never sequence filling."""
    evidence = {'version': 1, 'record_id': record['record_id'], 'record_sha256': record_digest(record),
                'association': 'no_anchor', 'attempt_id': None, 'item': None, 'scenario_kind': None,
                'anchor_time_s': None, 'confirmation_supported': False,
                'capture': deepcopy(record['capture']), 'eligibility': eligibility_suggestion(record, applied_edition=applied_edition)}
    if row['decision'] != 'include':
        evidence['association'] = 'not_included'
        return evidence
    matching = [trial for trial in record['trials'] if trial['anchor_time_s'] is not None
                and row['start'] <= trial['anchor_time_s'] <= row['end']]
    if not matching:
        return evidence
    if len(matching) != 1:
        evidence['association'] = 'ambiguous_anchors'
        return evidence
    trial = matching[0]
    anchor = trial['anchor_time_s']
    evidence.update(attempt_id=trial['attempt_id'], item=trial['item'], scenario_kind=ITEM_KINDS.get(trial['item']),
                    anchor_time_s=anchor, anchor_kind=trial['anchor_kind'], performed_order=trial['performed_order'])
    if sum(r['decision'] == 'include' and r['start'] <= anchor <= r['end'] for r in rows) != 1:
        evidence['association'] = 'overlapping_included_ranges'
        return evidence
    for other in record['trials']:
        if other is trial:
            continue
        if (other['performed_order'] == trial['performed_order']
                or (other['anchor_time_s'] is not None
                    and (other['performed_order'] - trial['performed_order']) * (other['anchor_time_s'] - anchor) <= 0)):
            evidence['association'] = 'contradictory_order'
            return evidence
    evidence['association'] = 'linked' if trial['activity_kind'] == 'trial' else 'handling_record'
    evidence['confirmation_supported'] = bool(trial['item'] and evidence['association'] == 'linked'
        and ista_type in ('G', 'H') and trial['item'].startswith(ista_type)
        and record['ista_type'] in ('Unknown', ista_type)
        and applied_edition == '2018-03' and record['applied_edition'] in (None, applied_edition)
        and row['evidence_status'] == 'current')
    return evidence


def expected_target(trial, ista_type, applied_edition=None):
    item, conditions = trial['item'], trial.get('conditions', {})
    explicit = conditions.get('target_faces')
    if explicit:
        return explicit, 'explicit_record'
    if (applied_edition != '2018-03' or ista_type not in ('G', 'H')
            or not item or not item.startswith(ista_type)):
        return None, 'unavailable'
    if item == 'G16':
        if conditions.get('critical_face_status') == 'unknown':
            return ['LEFT'], '2018_reference'
        return None, 'unavailable'
    if item == 'G17':
        form = conditions.get('package_form')
        target = ['FRONT'] if form == 'standard' else ['BOTTOM'] if form in ('flat', 'elongated') else None
        return target, '2018_reference' if target else 'unavailable'
    from .scene_review import G_POSTURES, H_POSTURES, FACE_NUMBERS
    numbers = None
    if item and re.fullmatch(r'G(0[1-9]|1[0-5])', item):
        numbers = G_POSTURES[int(item[1:]) - 1]
    elif item and re.fullmatch(r'H/B(04|16)/D0[1-6]', item):
        numbers = H_POSTURES[item.split('/')[1]][int(item[-2:]) - 1]
    if numbers is None or ista_type not in FACE_NUMBERS:
        return None, 'unavailable'
    reverse = {number: face for face, number in FACE_NUMBERS[ista_type].items()}
    return sorted(reverse[number] for number in numbers), '2018_reference'


def expected_faces(trial, ista_type, applied_edition=None):
    return expected_target(trial, ista_type, applied_edition)[0]


def observe_trial(result, row, trial, ista_type, applied_edition=None):
    expected, target_basis = expected_target(trial, ista_type, applied_edition)
    evidence = {'version': 1, 'motion': 'unavailable', 'approach': 'unavailable',
                'expected_faces': expected, 'target_basis': target_basis, 'observed_faces': None, 'reason': 'Observation unavailable.',
                'hazard_contact': 'unverified', 'support_condition': 'unverified', 'release_condition': 'unverified'}
    times = result.signals.index.to_numpy(float)
    selected = np.flatnonzero((times >= row['start']) & (times <= row['end']))
    if (row['evidence_status'] != 'current' or row.get('left_censored') or row.get('right_censored')
            or row['evidence_class'] in ('tracking_jump', 'unclear') or not len(selected)
            or row['motion'] not in ('free_fall', 'tip_or_rotation', 'stationary', 'robot_handling')
            or not result.valid_pose[selected].all() or np.any(result.block_ids[selected] < 0)
            or len(np.unique(result.block_ids[selected])) != 1):
        evidence['reason'] = 'Incomplete motion or tracking support.'
        return evidence
    reg = result.registration
    if reg and reg.floor_y_mm is not None and result.corners_m is not None:
        height = result.corners_m[selected, :, 1] * 1000 - reg.floor_y_mm
        if not np.isfinite(height).all() or height.min() < -reg.position_tolerance_mm:
            evidence['reason'] = 'Floor geometry inconsistent.'
            return evidence
    supported_context = (applied_edition == '2018-03' and ista_type in ('G', 'H')
                         and trial['item'] and trial['item'].startswith(ista_type))
    kind = ITEM_KINDS.get(trial['item']) if supported_context else None
    rotation_kind = kind in ('tip_over', 'rotational_flat_drop', 'rotational_edge_drop', 'full_rotational_flat_drop')
    expected_motion = 'tip_or_rotation' if rotation_kind else 'free_fall'
    if kind is not None:
        evidence['motion'] = 'compatible' if row['motion'] == expected_motion else 'different'
    if rotation_kind:
        evidence['reason'] = 'Rotation observed; contact unverified.' if evidence['motion'] == 'compatible' else 'Recorded motion not established.'
        return evidence
    crossings = row.get('geometry', {}).get('floor_crossings', [])
    feature = crossings[0].get('approach_feature') if crossings else None
    if feature:
        evidence['observed_faces'] = sorted(feature['faces'])
    if expected and feature:
        evidence['approach'] = 'match' if expected == evidence['observed_faces'] else 'different'
        evidence['reason'] = 'Geometric floor approach; contact force unverified.'
    else:
        evidence['reason'] = ('Target or floor approach unavailable.' if kind is not None
                              else 'Type, applied edition or recorded item unavailable for interpretation.')
    return evidence


def record_reference(evidence):
    return {key: deepcopy(evidence[key]) for key in ('record_id', 'record_sha256', 'attempt_id', 'anchor_time_s')}


def validate_record_confirmation(record, row, identity, rows):
    if not identity.get('confirmed'):
        return
    evidence = associate(record, rows, row, identity['ista_type'], identity.get('applied_edition'))
    if (not evidence['confirmation_supported'] or identity.get('scenario_id') != evidence['item']
            or identity.get('scenario_kind') != evidence['scenario_kind']
            or identity.get('record_reference') != record_reference(evidence)):
        raise ValueError('Confirmed item does not match a unique validated trial record reference.')
