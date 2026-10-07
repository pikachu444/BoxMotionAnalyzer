"""Frozen public synthetic semantics; approval is separate from policy identity."""
from copy import deepcopy
import json
from pathlib import Path

from src.utils.marker_profile_identity import envelope, digest, validate_envelope


def event_policy(designated_t2='next_floor_impact'):
    if designated_t2 not in ('next_floor_impact', 'rebound_recontact'):
        raise ValueError('Unsupported designated t2 kind.')
    return envelope('ContactEventPolicy', version='pub08-synthetic-v1', designated_t2=designated_t2,
        eligibility='detached-floor-box; same release ending at next attachment or window end',
        force_on_n=.05, force_off_n=.01, approach_mm_s=50., feature_tolerance_mm=.5,
        rearm_clearance_mm=.5, rearm_dwell_s=.020, merge_s=.004, matching_window_s=.020,
        timing='force-on bracket; approach from immediately preceding material-point state',
        merge='unresolved onset cluster; independently separated onsets retained ambiguous',
        matching='single t1 shift; chronological; multiple possible counterparts ambiguous',
        detector_t2='second eligible legacy contact-set run; physical kind unverified',
        numerical_acceptance='proposed; no physical accuracy or baseline promotion')


def validate_policy(policy):
    validate_envelope(policy, 'ContactEventPolicy')
    if policy != event_policy(policy.get('designated_t2')):
        raise ValueError('Unsupported or changed frozen contact policy; create a new reviewed version.')
    return digest(policy)


def policy_approval(policy):
    """Recorded user scope, separate from immutable semantics and accuracy."""
    ph=validate_policy(policy)
    path=Path(__file__).resolve().parents[2]/'docs/analysis/reference/contact_event_141_confirmation.json'
    if not path.exists():return dict(event_scope='proposed',thresholds='proposed',numerical_accuracy='proposed',baseline='none')
    value=json.loads(path.read_text(encoding='utf-8'));validate_envelope(value,'ContactEventApproval')
    if value['policy_sha256']!=ph:return dict(event_scope='proposed',thresholds='proposed',numerical_accuracy='proposed',baseline='none')
    states={key:value[key]['status'] for key in ('event_scope','thresholds','numerical_accuracy')}
    if any(s not in ('approved','proposed') for s in states.values()) or value['baseline']!='none':
        raise ValueError('Unsupported contact approval scope; baseline promotion requires separate review.')
    return dict(**states,baseline='none',approval_sha256=digest(value))


def frozen_protocol():
    """Authored independently of evaluator outputs, before any event execution."""
    expectations = [
        dict(case_id='face-single', kinds=['first_floor_impact'], t2_status='not_detected'),
        dict(case_id='corner-edge', kinds=['first_floor_impact', 'new_feature_impact'], t2_status='valid'),
        dict(case_id='corner-face', kinds=['first_floor_impact', 'new_feature_impact'], t2_status='valid'),
        dict(case_id='rebound', kinds=['first_floor_impact', 'rebound_recontact'], t2_status='valid'),
        dict(case_id='rocking', kinds=['first_floor_impact', 'support_transition'], t2_status='not_detected'),
        dict(case_id='chatter', kinds=['first_floor_impact', 'contact_chatter'], t2_status='not_detected'),
        dict(case_id='gripper-only', kinds=['gripper_contact'], t2_status='not_detected'),
        dict(case_id='conflict', kinds=['first_floor_impact', 'ambiguous_contact'], t2_status='ambiguous'),
        dict(case_id='out-of-window', kinds=['first_floor_impact', 'new_feature_impact'], t2_status='out_of_window'),
    ]
    return envelope('EvaluationProtocol', version='pub08-public-functional-v1', frozen_date='2026-10-08',
        source_kind='public_hand_specified_contact_controls', policy=event_policy(), policy_sha256=digest(event_policy()),
        expectations=deepcopy(expectations), tolerance_approval='proposed', baseline='none',
        experimental_accuracy='unavailable', label_uncertainty='bracketed at declared sample interval')
