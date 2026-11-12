"""Resolved display values; existing producers retain validity and repeat ownership."""
from dataclasses import dataclass, field
import json
import math

import numpy as np
import pandas as pd
from scipy.spatial.transform import Rotation

from src.analysis.compare.impact_metrics import (
    MetricValue, SUMMARY, _column, _constant, _number, _observation_context,
    _processing_context, _review_context, calculate_impact_metrics, _diagnostics,
)
from src.analysis.compare.posture_metrics import calculate_posture_metrics, _window_context
from src.analysis.compare.contact_metrics import calculate_contact_comparison
from src.analysis.pipeline.contact_reducers import final_face, contact_sweep
from src.analysis.pipeline.drop_posture_post_processor import DropPosturePostProcessor
from src.config.config_app import FACE_DEFINITIONS, calculate_local_box_corners
from src.utils.first_event_evidence import validate_first_event, _boolean
from src.utils.result_time import time_values


@dataclass(frozen=True)
class ResolvedMetric:
    metric_key: str
    value: float | str | bool | None = None
    unit: str = ''
    context: str = 'step2:summary'
    status: str = 'unavailable'
    reason: str = ''
    source_key: str | tuple = ''
    sample_time: float | None = None
    method: str = ''
    reference: str = ''
    window: tuple = ()
    evidence_status: str = 'unknown'
    calibration_status: str = 'not measured'
    evidence: dict = field(default_factory=dict)


def calculate_geometric_height(velocity, context, *, gravity=9810):
    try:
        if not isinstance(context, dict) or context.get('user_approved') is not True:
            raise ValueError('An independently approved free-fall scenario is required')
        if (context.get('category') != 'Type G' or context.get('is_free_fall') is not True
                or context.get('kind') not in ('face', 'edge', 'corner', 'free-fall')):
            raise ValueError('A supported Type G free-fall context is required')
        velocity, gravity = _number(velocity), _number(gravity)
        if velocity >= 0 or gravity <= 0:
            raise ValueError('Strictly downward velocity and positive gravity are required')
        height = velocity * velocity / (2 * gravity)
        if not math.isfinite(height):
            raise ValueError('Speed-equivalent height is not finite')
        return MetricValue(height)
    except (ValueError, TypeError, OverflowError) as error:
        return MetricValue(None, str(error))


def _geometry(df):
    artifact, dims, floor = _processing_context(df, raw_pose=False)
    settings = json.loads(artifact['ProcessingSettingsJson'])
    if any(settings[s]['face_definitions'] != FACE_DEFINITIONS for s in ('single_pass', 'postprocess')):
        raise ValueError('Executed local face and axis identities are unsupported')
    times, reason = time_values(df)
    if reason:
        raise ValueError(reason)
    pose = np.column_stack([np.asarray(_column(df, ('Position', 'CoM', 'P_' + c)), float)
                            for c in ('TX', 'TY', 'TZ', 'RX', 'RY', 'RZ')])
    points = np.stack([np.column_stack([np.asarray(_column(df, ('Position', f'C{i}', 'P_T' + a)), float)
                                       for a in 'XYZ']) for i in range(1, 9)], axis=1)
    valid = (np.isfinite(pose).all(axis=1) & np.isfinite(points).all(axis=(1, 2))
             & _column(df, ('Info', 'Pose', 'Source')).eq('Optimized').to_numpy())
    local = calculate_local_box_corners(dims)
    for i in np.flatnonzero(valid):
        valid[i] = np.allclose(points[i], pose[i, :3] + Rotation.from_rotvec(pose[i, 3:]).apply(local),
                               rtol=1e-9, atol=1e-7)
    return artifact, dims, floor, settings, times, pose, points, valid


def _included_review(df, dims, floor):
    review, _ = _observation_context(df)
    if review is None or review['candidate'].get('decision') != 'include':
        raise ValueError('A current included scene review is required')
    if review['candidate'].get('evidence_status') != 'current':
        raise ValueError('Scene evidence changed; review it again')
    registration = _review_context(review, dims, floor)
    return review, registration



def _contact_replay(geometry):
    _, dimensions, floor, settings, times, _, points, valid = geometry
    if not valid.all():
        raise ValueError('Contact detector requires complete consistent pose/corner observations')
    processor = DropPosturePostProcessor(face_definitions=FACE_DEFINITIONS,
        local_box_corners=calculate_local_box_corners(dimensions), floor_level=floor)
    threshold = _number(settings['postprocess']['contact_threshold_mm'])
    if threshold <= 0:
        raise ValueError('Recorded contact threshold must be positive')
    analysis = processor._contact_analysis(min_heights=points[:, :, 1].min(axis=1),
                                           index=pd.Index(times), contact_threshold_mm=threshold)
    sets = processor._contact_sets(points[:, :, 1], threshold, active_mask=analysis['active_mask'],
                                   relative_contact_band=analysis['relative_contact_band'])
    return analysis, processor._accepted_events(sets)


def _detector_precontact(df, review, geometry):
    times = geometry[4]
    analysis, accepted = _contact_replay(geometry)
    detector_index = analysis['t1_minus_pos']
    if detector_index is None or not analysis['impact_detected']:
        raise ValueError('Contact detector has no precontact sample')
    saved_t1 = _number(_constant(df, (*SUMMARY, 'T1MinusTimeSec')))
    if saved_t1 != times[detector_index]:
        raise ValueError('Saved T1MinusTimeSec differs from the contact detector precontact sample')
    saved_impact = _number(_constant(df, (*SUMMARY, 'FirstImpactTimeSec')))
    if not accepted or saved_impact != times[accepted[0]['start_pos']]:
        raise ValueError('Saved FirstImpactTimeSec differs from the accepted contact detector event')
    impact_index = accepted[0]['start_pos']
    if detector_index >= impact_index:
        raise ValueError('Contact detector precontact sample does not precede the accepted event')
    if review is not None and times[detector_index] < review['candidate']['start']:
        raise ValueError('Contact detector precontact sample is outside the reviewed interval')
    # The legacy declaration validator assumes adjacency; validate its other
    # provenance and gap checks against the accepted event's actual bracket.
    bracket = df.copy()
    bracket[(*SUMMARY, 'T1MinusTimeSec')] = times[impact_index - 1]
    event = validate_first_event(bracket, review)
    if not event.valid:
        raise ValueError(event.reason)
    return detector_index

def calculate_target_posture_error(df, *, target_context=None):
    key = 'TargetPostureError_deg'
    reason = 'No independently approved t1- target posture'
    try:
        if target_context is None:
            raise ValueError(reason)
        record = target_context
        required = {'version', 'basis', 'user_approved', 'phase', 'frame', 'target_down_local',
                    'registration_sha256', 'ista_type', 'applied_edition'}
        if (not isinstance(record, dict) or set(record) != required or type(record['version']) is not int
                or record['version'] != 1 or record['basis'] != 'operator' or record['user_approved'] is not True
                or record['phase'] != 't1_minus' or record['frame'] != 'registered_box_local'):
            raise ValueError('Invalid independently approved target context')
        vector = record['target_down_local']
        if (not isinstance(vector, (list, tuple, np.ndarray)) or len(vector) != 3
                or any(isinstance(v, (bool, np.bool_)) or not isinstance(v, (int, float, np.number)) for v in vector)):
            raise ValueError('Target direction must contain three finite numeric components')
        vector = np.asarray(vector, float)
        norm = np.linalg.norm(vector)
        if vector.shape != (3,) or not np.isfinite(vector).all() or not np.isfinite(norm) or norm <= 1e-12:
            raise ValueError('Target direction must be finite and nonzero')
        artifact, dims, floor, settings, times, pose, points, valid = _geometry(df)
        review, registration = _included_review(df, dims, floor)
        if registration is None:
            raise ValueError('Registered box geometry and floor are required')
        if (record['registration_sha256'] != registration.fingerprint
                or record['ista_type'] != review['identity']['ista_type']
                or record['applied_edition'] != review['identity'].get('applied_edition')):
            raise ValueError('Target registration or scenario edition differs from the current review')
        index = _detector_precontact(df, review,
            (artifact, dims, floor, settings, times, pose, points, valid))
        if not valid[index]:
            raise ValueError('Optimized precontact pose and corner geometry are unavailable or inconsistent')
        observed = Rotation.from_rotvec(pose[index, 3:]).inv().apply([0., -1., 0.])
        value = float(np.degrees(np.arccos(np.clip(np.dot(observed, vector / norm), -1., 1.))))
        return ResolvedMetric(key, value, 'deg', status='available', sample_time=float(times[index]),
                              source_key='approved target / Optimized pose', method='local-down-direction-angle',
                              reference='registered box local; yaw about down unconstrained',
                              evidence_status=review['candidate']['evidence_status'],
                              evidence={'registration_sha256': registration.fingerprint})
    except (ValueError, TypeError, KeyError, IndexError, AttributeError, OverflowError) as error:
        return ResolvedMetric(key, unit='deg', reason=str(error))


POSTURE_ALIASES = {
    'BetaAtT1MinusDeg': 'beta', 'ThetaLongAtT1MinusDeg': 'theta_long',
    'ThetaShortAtT1MinusDeg': 'theta_short', 'CminAtT1MinusIndex': 'lowest_corner',
    'DeltaHAtT1Minus_mm': 'height_range', 'CminMargin_mm': 'corner_gap', 'MaxDeltaH_mm': 'max_height_range',
    'MaxBetaDeg': 'max_beta', 'MaxAbsThetaLongDeg': 'max_long', 'MaxAbsThetaShortDeg': 'max_short',
    'ImpactSequence': 'sequence',
}


def resolve_summary_metrics(df, *, target_context=None):
    from src.config.result_metric_descriptors import get_drop_posture_summary_descriptors

    descriptors = get_drop_posture_summary_descriptors()
    result = {}
    evidence_status = 'unknown'
    def put(key, item, **metadata):
        unit = next((d.unit for d in descriptors if d.column[2] == key), '')
        result[key] = ResolvedMetric(key, item.value, unit, status='available' if item.value is not None else 'unavailable',
                                     reason=item.reason, evidence_status=evidence_status, **metadata)
    try:
        reviewed, _ = _observation_context(df)
        if reviewed is not None:
            evidence_status = reviewed['candidate'].get('evidence_status', 'unknown')
    except (ValueError, TypeError, KeyError):
        pass
    posture = calculate_posture_metrics(df)
    impact = calculate_impact_metrics(df)
    for key, owner in POSTURE_ALIASES.items():
        put(key, posture.metrics[owner], source_key='compare:' + owner, method='saved-geometry-validation',
            sample_time=None if key.startswith('Max') or key == 'ImpactSequence' else posture.evaluation_time_s,
            evidence={'repeat_reason': posture.repeat_reasons.get(owner, ''), 'window_reason': posture.window_reason})
    result['TargetPostureError_deg'] = calculate_target_posture_error(df, target_context=target_context)
    contact = calculate_contact_comparison(df)
    put('IntendedContactMatch', MetricValue({'Match': 'Match', 'Different': 'Mismatch', 'Unclear': 'Unknown'}[contact.outcome], contact.reason),
        source_key='calculate_contact_comparison', sample_time=contact.time_s, method='existing-contact-owner',
        evidence=dict(outcome=contact.outcome, intended=contact.intended, observed=contact.observed,
                      registration_sha256=contact.registration_sha256, target_key=contact.target_key))
    event = None
    review_error = ''
    try:
        review, _ = _observation_context(df)
        event = validate_first_event(df, review)
    except (ValueError, TypeError, KeyError) as error:
        review, event_reason = None, str(error)
        review_error = str(error)
    else:
        event_reason = event.reason
    # Preserve independent diagnostic fields even when an event-dependent field fails.
    contact_usable = False
    try:
        state = _constant(df, (*SUMMARY, 'ContactState'))
        contact_usable = state in ('NoContact', 'Approach', 'SustainedContact', 'ImpactEvent')
    except (ValueError, TypeError):
        pass
    diagnostic_expected, diagnostic_error = {}, ''
    try:
        analysis, accepted = _contact_replay(_geometry(df))
        diagnostic_expected = dict(ContactState=analysis['contact_state'], T1Detected=analysis['t1_detected'],
            ImpactDetected=analysis['impact_detected'], SustainedContactDetected=analysis['sustained_contact_detected'],
            ContactDetectionMethod=analysis['contact_detection_method'],
            ContactConfidence=analysis['contact_confidence'], ImpactEventCount=len(accepted))
    except (ValueError, TypeError, KeyError, AttributeError, IndexError) as error:
        diagnostic_error = str(error)
    for key in ('ReferenceFace', 'T1MinusTimeSec', 'T1Detected', 'FirstImpactTimeSec', 'FirstImpactContact',
                'ImpactEventCount', 'ContactState', 'ImpactDetected', 'SustainedContactDetected',
                'ContactConfidence', 'ContactDetectionMethod'):
        try:
            if not contact_usable and key != 'ReferenceFace':
                raise ValueError('Usable contact analysis is unavailable')
            if key in ('T1MinusTimeSec', 'FirstImpactTimeSec', 'FirstImpactContact') and not (event and event.valid):
                raise ValueError(event_reason)
            value = _constant(df, (*SUMMARY, key))
            if key in ('T1Detected', 'ImpactDetected', 'SustainedContactDetected'):
                value = _boolean(value, key)
            if key in diagnostic_expected:
                matches = (math.isclose(_number(value), diagnostic_expected[key], rel_tol=1e-9, abs_tol=1e-9)
                           if key == 'ContactConfidence' else value == diagnostic_expected[key])
                if not matches:
                    raise ValueError(key + ': recorded diagnostic differs from the public contact analysis')
            elif key in ('ContactState', 'T1Detected', 'ImpactDetected', 'SustainedContactDetected', 'ContactDetectionMethod', 'ImpactEventCount', 'ContactConfidence'):
                raise ValueError(diagnostic_error or 'Contact diagnostic evidence is unavailable')
            if key == 'ReferenceFace':
                if posture.reference_reason or posture.reference is None:
                    raise ValueError(posture.reference_reason or 'Recorded reference geometry is unavailable')
                value = posture.reference[0]
            if key in ('FirstImpactContact', 'ContactConfidence'):
                item = impact.metrics['first_contact'] if key == 'FirstImpactContact' else _diagnostics(df)['contact_confidence']
                if item.value is None:
                    raise ValueError(item.reason)
                value = item.value
            if key == 'ImpactEventCount':
                number = _number(value)
                if number < 0 or not number.is_integer():
                    raise ValueError('Accepted contact count must be a nonnegative integer')
            if value is None or (not isinstance(value, str) and not np.isfinite(value)):
                raise ValueError(f'{key}: recorded value is unavailable')
            put(key, MetricValue(value), source_key=(*SUMMARY, key), method='saved-public-postprocess')
        except (ValueError, TypeError, KeyError) as error:
            put(key, MetricValue(None, str(error)), source_key=(*SUMMARY, key))
    snapshot_keys = ('VerticalVelAtT1Minus_mm_s', 'VxyAtT1Minus_mm_s', 'AngularSpeedAtT1Minus_rad_s',
                     'PeakDescentSpeed_mm_s', 'EquivalentFreeFallHeight_mm')
    path_keys = ('FinalFace', 'TotalSweepAngle_deg', 'SweepConsistency', 'RotationDirection')
    try:
        artifact, dims, floor, settings, times, pose, corners, valid = _geometry(df)
        processor = DropPosturePostProcessor(face_definitions=FACE_DEFINITIONS,
            local_box_corners=calculate_local_box_corners(dims), floor_level=floor)
        threshold = _number(settings['postprocess']['contact_threshold_mm'])
        if not valid.all():
            raise ValueError('Whole-window pose/corner geometry is unavailable or inconsistent')
        tail = final_face(times, Rotation.from_rotvec(pose[:, 3:]), corners, dims, floor=floor, threshold=threshold)
        try:
            saved_face = _constant(df, (*SUMMARY, 'FinalFace'))
            if tail.value is not None and saved_face != tail.value:
                raise ValueError('Recorded FinalFace differs from stable-tail evidence')
        except (ValueError, TypeError) as error:
            tail = MetricValue(None, str(error))
        put('FinalFace', tail, source_key='stable-tail-rotation-mean', method='public-height-plateau/Rotation.mean',
            window=(float(times[int(.65 * len(times))]), float(times[-1])), reference='all six local faces')
        try:
            _window_context(review, times, event, settings)
            if posture.metrics['sequence'].value is None:
                raise ValueError(posture.metrics['sequence'].reason)
            analysis = processor._contact_analysis(min_heights=corners[:, :, 1].min(axis=1), index=pd.Index(times),
                                                   contact_threshold_mm=threshold)
            sets = processor._contact_sets(corners[:, :, 1], threshold, active_mask=analysis['active_mask'],
                                           relative_contact_band=analysis['relative_contact_band'])
            for key, item in contact_sweep(corners, processor._accepted_events(sets)).items():
                put(key, item, source_key='accepted-contact-start-radii', method='principal-signed-steps',
                    reference='geometric centre / world Y up', window=(float(times[0]), float(times[-1])))
        except (ValueError, TypeError, KeyError, AttributeError) as error:
            for key in path_keys[1:]:
                put(key, MetricValue(None, str(error)))
    except (ValueError, TypeError, KeyError, IndexError, AttributeError) as error:
        for key in path_keys:
            put(key, MetricValue(None, str(error)))
    try:
        artifact, dims, floor = _processing_context(df, raw_pose=False)
        if review_error:
            raise ValueError(review_error)
        geometry = _geometry(df)
        index = _detector_precontact(df, review, geometry)
        _, _, _, settings, times, _, _, geometry_valid = geometry
        sample = float(times[index])
        derivative = settings['single_pass'].get('derivatives', {})
        if (derivative.get('time_policy') != 'actual-dt;finite-difference-numpy-gradient;finite-angle-matrix'
                or derivative.get('segmentation_policy') != 'face-boundaries-and-finite-contiguous-pose-v3'):
            raise ValueError('Recorded derivative time or contiguous-segment policy is unavailable or unsupported')
        if derivative.get('velocity_method') not in ('finite_difference', 'spline'):
            raise ValueError('Recorded derivative method is unavailable or unsupported')
        for name in ('pose_lowpass', 'pose_moving_average', 'velocity_lowpass'):
            if type(derivative.get(name, {}).get('enabled')) is not bool:
                raise ValueError('Recorded derivative filter provenance is unavailable')
        if not geometry_valid[index]:
            raise ValueError('Stored derivative evaluation pose/corner geometry is unavailable or inconsistent')
        if _column(df, ('Info', 'Pose', 'Source')).iloc[index] != 'Optimized':
            raise ValueError('Stored derivative requires an Optimized evaluation sample')
        def velocity(name):
            return _number(_column(df, ('Velocity', 'CoM', name)).iloc[index])
        components = {
            'VerticalVelAtT1Minus_mm_s': lambda: velocity('Global_V_TY'),
            'VxyAtT1Minus_mm_s': lambda: float(np.hypot(velocity('Global_V_TX'), velocity('Global_V_TZ'))),
            'AngularSpeedAtT1Minus_rad_s': lambda: velocity('Global_V_R_Norm'),
        }
        for key, compute in components.items():
            try:
                value = _number(compute())
                if key != 'VerticalVelAtT1Minus_mm_s' and value < 0:
                    raise ValueError('Stored speed norm must be nonnegative')
                put(key, MetricValue(value), source_key='VelocityCalculator stored derivative',
                    sample_time=sample, method='saved derivative', reference='box geometric centre / world Y up',
                    evidence={'processing_settings': settings['single_pass']})
            except (ValueError, TypeError, KeyError) as error:
                put(key, MetricValue(None, str(error)))
        try:
            prefix = np.asarray(_column(df, ('Velocity', 'CoM', 'Global_V_TY')).iloc[:index + 1], float)
            if not geometry_valid[:index + 1].all() or not np.isfinite(prefix).all():
                raise ValueError('Peak descent requires the complete finite vertical-velocity interval')
            put('PeakDescentSpeed_mm_s', MetricValue(max(0., -float(prefix.min()))),
                method='saved derivative interval minimum', window=(float(times[0]), sample))
        except (ValueError, TypeError, KeyError) as error:
            put('PeakDescentSpeed_mm_s', MetricValue(None, str(error)))
        try:
            review, _ = _included_review(df, dims, floor)
            identity, candidate = review['identity'], review['candidate']
            if not (identity.get('confirmed') is True and identity.get('ista_type') == 'G'
                    and identity.get('scenario_id') and identity.get('scenario_kind') == 'free_fall'
                    and candidate.get('motion') == candidate.get('evidence_class') == 'free_fall'
                    and candidate.get('left_censored') is False and candidate.get('right_censored') is False
                    and artifact.get('IstaType') == 'G' and artifact.get('ScenarioId') == identity['scenario_id']
                    and artifact.get('ScenarioKind') == 'free_fall'):
                raise ValueError('A current confirmed uncensored Type G free-fall scenario is required')
            height = calculate_geometric_height(result['VerticalVelAtT1Minus_mm_s'].value,
                dict(user_approved=True, category='Type G', is_free_fall=True, kind='free-fall'))
            put('EquivalentFreeFallHeight_mm', height, method='geometric snapshot vY squared / (2*9810)',
                sample_time=sample, reference='geometric centre; ideal free fall')
        except (ValueError, TypeError, KeyError) as error:
            put('EquivalentFreeFallHeight_mm', MetricValue(None, str(error)))
    except (ValueError, TypeError, KeyError, IndexError, AttributeError) as error:
        for key in snapshot_keys:
            put(key, MetricValue(None, str(error)))
    for descriptor in descriptors:
        result.setdefault(descriptor.column[2], ResolvedMetric(descriptor.column[2], unit=descriptor.unit,
                          reason='Recorded source quantity is unavailable'))
    return result
