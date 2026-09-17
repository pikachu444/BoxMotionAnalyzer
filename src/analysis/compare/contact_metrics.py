"""Compare operator intent with a saved, geometrically inferred first contact.

This does not estimate a target angle, contact force or an ISTA pass/fail result.
The accepted event must contain an observed air-to-floor transition; ongoing
support contact cannot stand in for a newly impacting face or edge.
"""
from dataclasses import dataclass
import json
import re

import numpy as np
import pandas as pd
from scipy.spatial.transform import Rotation

from src.analysis.compare.impact_metrics import (
    SUMMARY, _column, _constant, _number, _observation_context,
    _processing_context, _review_context,
)
from src.analysis.pipeline.face_assignment import face_segments
from src.analysis.pipeline.drop_posture_post_processor import DropPosturePostProcessor
from src.analysis.pipeline.intended_contact import (
    feature_options, feature_corners, feature_label, validate_intended_contact_context,
)
from src.config.config_app import FACE_DEFINITIONS, calculate_local_box_corners
from src.utils.result_time import timeline_from_frame, exceeds_gap_limit
from src.utils.first_event_evidence import validate_first_event


@dataclass(frozen=True)
class ContactComparison:
    intended: str = ''
    observed: str = ''
    outcome: str = 'Unclear'
    reason: str = ''
    time_s: float | None = None
    target_key: tuple | None = None
    registration_sha256: str | None = None


def _observed_feature(text):
    text = str(text).strip()
    if not re.fullmatch(r'C[1-8]|\{C[1-8](?:\s*,\s*C[1-8])+\}', text):
        raise ValueError('First contact has no valid corner set')
    numbers = [int(value) for value in re.findall(r'C([1-8])', text)]
    if len(set(numbers)) != len(numbers):
        raise ValueError('First contact repeats a corner')
    corners = tuple(sorted(numbers))
    for faces in feature_options():
        if feature_corners(faces) == corners:
            return faces, corners
    raise ValueError('First contact is not a single box face, edge or corner')


def calculate_contact_comparison(df):
    intended, observed, target, time, fingerprint = '', '', None, None, None
    try:
        review, _ = _observation_context(df)
        if review is None:
            raise ValueError('No independent intended contact was recorded')
        row = review['candidate']
        record = row.get('intended_contact')
        if record is None:
            raise ValueError('No independent intended contact was recorded')
        identity = review['identity']
        record = validate_intended_contact_context(
            record, review['detection'].get('registration_sha256'),
            identity['ista_type'], identity.get('applied_edition'))
        target = tuple(record['faces'])
        fingerprint = record['registration_sha256']
        intended = feature_label(target)
        event = validate_first_event(df, review)
        if not event.valid:
            raise ValueError(event.reason)
        artifact, dims, floor = _processing_context(df, raw_pose=False)
        registration = _review_context(review, dims, floor)
        if registration is None:
            raise ValueError('Registered box geometry and floor are required')
        settings = json.loads(artifact['ProcessingSettingsJson'])
        if settings['result_resampling']['enabled'] is not False:
            raise ValueError('Resampled results cannot establish two independently observed contact samples')
        for stage in ('single_pass', 'postprocess'):
            if settings[stage]['face_definitions'] != FACE_DEFINITIONS:
                raise ValueError('Executed face/corner identities differ from the registered box')
        if row.get('left_censored') or row.get('right_censored'):
            raise ValueError('The reviewed event is cut by a capture boundary or tracking gap')
        if row.get('motion') != 'free_fall' or row.get('evidence_class') != 'free_fall':
            raise ValueError('Existing support or unclear motion does not identify a new free-fall contact')
        timeline = timeline_from_frame(df)
        if not timeline.aligned:
            raise ValueError(timeline.reason)
        time = event.times_s[1]
        index = event.indices[1]
        indices = np.array(event.indices)
        times = timeline.times[indices]
        if not row['start'] <= times[0] < times[-1] <= row['end']:
            raise ValueError('Contact evidence extends outside the reviewed interval')
        gap_factor = _number(review['detection']['settings']['gap_factor'])
        if gap_factor <= 1:
            raise ValueError('Recorded tracking-gap policy is invalid')
        gap_limit = gap_factor * float(np.median(np.diff(timeline.times)))
        if any(exceeds_gap_limit(a, b, gap_limit) for a, b in zip(times[:-1], times[1:])):
            raise ValueError('Contact evidence crosses a tracking gap')
        if not _column(df, ('Info', 'Pose', 'Source')).iloc[indices].eq('Optimized').all():
            raise ValueError('Contact evidence contains unavailable pose tracking')
        face_columns = [c for c in df.columns if c[0] == 'Position' and c[2] == 'FaceInfo']
        if not face_columns:
            raise ValueError('Marker face assignments are unavailable at contact')
        faces = pd.DataFrame({f'{c[1]}_FaceInfo': _column(df, c).iloc[indices].to_numpy() for c in face_columns})
        if len(face_segments(faces)) != 1:
            raise ValueError('Contact crosses a marker face-assignment change')
        pose = np.column_stack([pd.to_numeric(_column(df, ('Position', 'CoM', 'P_' + component)).iloc[indices],
                                             errors='coerce').to_numpy(float)
                                for component in ('TX', 'TY', 'TZ', 'RX', 'RY', 'RZ')])
        if not np.isfinite(pose).all():
            raise ValueError('Contact pose contains missing or non-finite values')
        corners = np.array([p[:3] + Rotation.from_rotvec(p[3:]).apply(calculate_local_box_corners(dims)) for p in pose])
        minimum = corners[:, :, 1].min(axis=1)
        threshold = _number(settings['postprocess']['contact_threshold_mm'])
        if threshold <= 0:
            raise ValueError('Recorded contact-height threshold is invalid')
        if minimum[0] <= floor + threshold or np.any(minimum[1:] > floor + threshold):
            raise ValueError('The saved first event has no observed air-to-floor transition')
        tolerance = registration.position_tolerance_mm
        if np.any(minimum < floor - tolerance):
            raise ValueError('Contact geometry penetrates the registered floor beyond its tolerance')
        heights = np.column_stack([pd.to_numeric(_column(df, ('Position', f'C{i}', 'P_TY')),
                                                  errors='coerce').to_numpy(float) for i in range(1, 9)])
        if not np.isfinite(heights).all():
            raise ValueError('Saved corner heights cannot reproduce the recorded contact policy')
        if np.any(np.abs(heights[indices] - corners[:, :, 1]) > tolerance):
            raise ValueError('Saved contact corners differ from the observed box pose')
        # Reuse the recorded policy instead of inventing a second contact band.
        # This verifies saved summary fields, not independent force measurements.
        processor = DropPosturePostProcessor(face_definitions=FACE_DEFINITIONS,
            local_box_corners=calculate_local_box_corners(dims), floor_level=floor)
        analysis = processor._contact_analysis(min_heights=heights.min(axis=1),
            index=pd.Index(timeline.times), contact_threshold_mm=threshold)
        contact_sets = processor._contact_sets(heights, threshold, active_mask=analysis['active_mask'],
            relative_contact_band=analysis['relative_contact_band'])
        if (analysis['t1_minus_pos'] != index - 1 or not analysis['impact_detected']
                or not contact_sets[index] or contact_sets[index] != contact_sets[index + 1]):
            raise ValueError('The first contact feature does not persist under the recorded contact policy')
        observed_faces, actual = _observed_feature(_constant(df, (*SUMMARY, 'FirstImpactContact')))
        summary = processor._impact_sequence_summary(contact_sets=contact_sets, index=pd.Index(timeline.times))
        if (summary['DropPostureSummary_FirstImpactTimeSec'] != time
                or contact_sets[index] != actual):
            raise ValueError('Saved first contact differs from the recorded geometric contact policy')
        observed = feature_label(observed_faces)
        expected = feature_corners(target)
        return ContactComparison(intended, observed, 'Match' if expected == actual else 'Different', '', time, target, fingerprint)
    except (ValueError, TypeError, KeyError, AttributeError, OverflowError) as error:
        reason = f'Contact evidence missing: {error}' if isinstance(error, KeyError) else str(error)
        return ContactComparison(intended, observed, 'Unclear', reason, time, target, fingerprint)
