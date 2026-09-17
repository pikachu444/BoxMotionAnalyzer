"""One-sided estimates at the recorded precontact sample from saved raw poses.

The historical CoM position columns describe the box geometric centre. Saved
Velocity columns are intentionally unused: their filters can cross contact.
The fit window and rotation limits below are software support rules, not ISTA
thresholds. Contact labels/confidence are algorithm diagnostics, not force data.
"""
from dataclasses import dataclass
import json
import math
import re

import numpy as np
import pandas as pd
from scipy.spatial.transform import Rotation

from src.analysis.pipeline.face_assignment import face_segments
from src.analysis.pipeline.scene_detection import Registration
from src.analysis.pipeline.scene_review import validate_scene_review_json
from src.config.config_app import FACE_DEFINITIONS, calculate_local_box_corners
from src.utils.artifact_metadata import DIMENSIONS, read_identity
from src.utils.processing_settings import validate_processing_record
from src.utils.result_time import exceeds_gap_limit, timeline_from_frame
from src.utils.first_event_evidence import FirstEventEvidence, validate_first_event


METRICS = {
    'vertical_velocity': dict(label='Vertical velocity', unit='m/s', kind='numeric', role='experimental',
        tooltip='Box geometric-centre velocity before contact; positive upward.'),
    'horizontal_speed': dict(label='Horizontal speed', unit='m/s', kind='numeric', role='experimental',
        tooltip='Box geometric-centre speed in the world XZ plane before contact.'),
    'angular_speed': dict(label='Angular speed', unit='rad/s', kind='numeric', role='experimental',
        tooltip='World-frame angular speed from relative rotations before contact.'),
    'equivalent_height': dict(label='Velocity-equivalent height', unit='mm', kind='numeric', role='experimental',
        tooltip='Registered COM downward velocity squared / (2g), g=9.80665 m/s². Not release height.'),
    'first_contact': dict(label='First contact', unit='', kind='categorical', role='diagnostic',
        tooltip='Recorded corner contact set; inferred by the contact algorithm.'),
    'final_face': dict(label='Final face', unit='', kind='categorical', role='diagnostic',
        tooltip='Explicit recorded final face only; reference face is not substituted.'),
    'contact_confidence': dict(label='Contact confidence (ImpactEvent)', unit='', kind='numeric', role='diagnostic',
        tooltip='Recorded algorithm score for a consistent ImpactEvent; may include plateau evidence. Not a first-impact probability.'),
}
FIT_SETTINGS = {
    'window_s': .040, 'minimum_span_s': .020, 'minimum_samples': 5,
    'maximum_gap_s': .020, 'maximum_rotation_step_rad': .25,
    'maximum_endpoint_rotation_rad': .25, 'maximum_translation_rms_mm': 1.,
    'maximum_angular_rms_rad': .01, 'gravity_m_s2': 9.80665,
}
SUMMARY = ('Analysis', 'DropPostureSummary')
REVIEW_COLUMN = ('Info', 'SceneReview', 'Json')


@dataclass(frozen=True)
class MetricValue:
    value: float | str | None
    reason: str = ''


@dataclass(frozen=True)
class ImpactResult:
    metrics: dict[str, MetricValue]
    evidence: dict
    observation_key: tuple | None = None


def _column(df, column):
    positions = [i for i, name in enumerate(df.columns) if name == column]
    if len(positions) != 1:
        raise ValueError(f'{column[-1]}: missing or duplicate column')
    return df.iloc[:, positions[0]]


def _constant(df, column):
    series = _column(df, column)
    if not len(series) or series.nunique(dropna=False) != 1:
        raise ValueError(f'{column[-1]}: must be constant across the result')
    return series.iloc[0]


def _number(value):
    if isinstance(value, (bool, np.bool_)):
        raise ValueError('Expected a finite numeric value')
    result = float(value)
    if not math.isfinite(result):
        raise ValueError('Expected a finite numeric value')
    return result


def _true(value):
    return str(value).strip().lower() in ('true', '1', '1.0')


def _diagnostics(df):
    metrics = {key: MetricValue(None, 'Precontact estimate unavailable') for key in METRICS}
    for key, column in (('first_contact', 'FirstImpactContact'), ('final_face', 'FinalFace'),
                        ('contact_confidence', 'ContactConfidence')):
        try:
            value = _constant(df, (*SUMMARY, column))
            if key == 'contact_confidence':
                value = _number(value)
                if not 0 <= value <= 1:
                    raise ValueError('ContactConfidence: outside 0–1')
            elif key == 'first_contact':
                text = str(value).strip()
                if not re.fullmatch(r'C[1-8]|\{C[1-8](?:\s*,\s*C[1-8])+\}', text):
                    raise ValueError('FirstImpactContact: no valid corner set')
                corners = re.findall(r'C[1-8]', text)
                if len(set(corners)) != len(corners):
                    raise ValueError('FirstImpactContact: repeated corner')
                value = corners[0] if len(corners) == 1 else '{' + ','.join(sorted(corners)) + '}'
            else:
                value = str(value).strip().upper()
                if value not in FACE_DEFINITIONS:
                    raise ValueError('FinalFace: not a known box face')
            metrics[key] = MetricValue(value)
        except (TypeError, ValueError) as error:
            metrics[key] = MetricValue(None, str(error))
    return metrics


def _processing_context(df, *, raw_pose=True):
    identity = read_identity(df)
    if identity.errors:
        raise ValueError('; '.join(identity.errors))
    artifact = identity.values
    if artifact.get('SchemaVersion') != '1':
        raise ValueError('Supported artifact provenance is missing')
    if artifact.get('CoordinatePolicy') != 'world-y-up-box-local-fixed-center-v1':
        raise ValueError('Geometric-centre coordinate policy is unconfirmed')
    if artifact.get('UnitsPolicy') != 'bma-mm-s-rotvec-rad-summary-deg-v1':
        raise ValueError('Pose mm/s/radian units are unconfirmed')
    error = validate_processing_record(artifact.get('ProcessingSemanticsVersion'), artifact.get('ProcessingSettingsJson'))
    if error:
        raise ValueError(error)
    settings = json.loads(artifact['ProcessingSettingsJson'])
    single, post = settings['single_pass'], settings['postprocess']
    if raw_pose and single['marker_smoothing']['enabled'] is not False:
        raise ValueError('Marker smoothing can cross contact; raw-pose estimate unavailable')
    if raw_pose and settings['result_resampling']['enabled'] is not False:
        raise ValueError('Resampled pose is unsupported for this one-sided estimate')
    dims = np.array([_number(artifact[field]) for field in DIMENSIONS])
    if np.any(dims <= 0):
        raise ValueError('Declared box dimensions must be positive')
    corners = calculate_local_box_corners(dims)
    for stage in (single, post):
        recorded = np.asarray(stage['geometry_mm'], float)
        if recorded.shape != (8, 3) or not np.array_equal(recorded, corners):
            raise ValueError('Executed geometry differs from declared box dimensions')
    floors = []
    for stage in (single['frame_analysis'], post):
        if stage['vertical_axis'] != 1 or isinstance(stage['vertical_axis'], bool):
            raise ValueError('Executed vertical axis must be world Y')
        if stage['floor_policy'] != 'explicit-horizontal-plane':
            raise ValueError('An explicit horizontal floor is required')
        floors.append(_number(stage['floor_level_mm']))
    if floors[0] != floors[1]:
        raise ValueError('Executed frame and contact floors differ')
    if post['contact_policy'] != 'drop-posture-evidence-v1':
        raise ValueError('Unsupported recorded contact policy')
    return artifact, dims, floors[1]


def _sha256(value, label):
    if not isinstance(value, str) or not re.fullmatch(r'[0-9a-f]{64}', value.strip().lower()):
        raise ValueError(f'{label}: invalid SHA-256')
    return value.strip().lower()


def _observation_context(df):
    """Capture identity is independent of support for estimating pose derivatives."""
    if REVIEW_COLUMN not in df.columns:
        return None, None
    text = _constant(df, REVIEW_COLUMN)
    start = _number(_constant(df, ('Info', 'Timeline', 'SliceStartSec')))
    end = _number(_constant(df, ('Info', 'Timeline', 'SliceEndSec')))
    if not isinstance(text, str) or not text:
        raise ValueError('Scene review is empty or invalid')
    data = json.loads(text)
    if (not isinstance(data, dict) or not isinstance(data.get('candidate'), dict)
            or not isinstance(data.get('identity'), dict)):
        raise ValueError('Scene review candidate and identity must be objects')
    for field in ('scenario_id', 'scenario_kind', 'reference_edition', 'applied_edition'):
        if data['identity'].get(field) is not None and not isinstance(data['identity'][field], str):
            raise ValueError(f'Scene identity {field} must be a string or null')
    data['source_sha256'] = _sha256(data.get('source_sha256'), 'Scene source')
    review = json.loads(validate_scene_review_json(data, start=start, end=end))
    identity = review['identity']
    for declared, field in (('IstaType', 'ista_type'), ('ScenarioId', 'scenario_id'), ('ScenarioKind', 'scenario_kind')):
        column = ('Info', 'Artifact', declared)
        if column not in df.columns:
            continue
        value = _constant(df, column)
        if value is not None and not pd.isna(value) and str(value).strip():
            if str(value).strip() != identity.get(field):
                raise ValueError(f'Scene identity differs from artifact {declared}')
    source_sha256 = review['source_sha256']
    original_column = ('Info', 'MarkerCorrection', 'OriginalSourceSha256')
    if original_column in df.columns:
        source_sha256 = _sha256(_constant(df, original_column), 'Original capture source')
    return review, (source_sha256, start, end, identity.get('scenario_id'))


def _review_context(review, dims, floor):
    if review is None:
        return None
    if review['candidate']['evidence_status'] != 'current':
        raise ValueError('Scene evidence changed; review it again')
    if 'tracking_jump' in (review['candidate'].get('evidence_class'), review['candidate'].get('motion')):
        raise ValueError('Scene is marked as a tracking jump, not supported physical motion')
    if not isinstance(review.get('detection'), dict):
        raise ValueError('Scene detection registration context is invalid')
    registration = None
    data = review['detection'].get('registration')
    if data is not None:
        if not isinstance(data, dict) or not isinstance(data.get('profile'), dict):
            raise ValueError('Scene marker registration must be an object')
        registration = Registration(**data)
        registration.validate()
        if registration.fingerprint != review['detection'].get('registration_sha256'):
            raise ValueError('Scene registration hash does not match its geometry')
        if not np.array_equal(np.asarray(registration.profile['box_dims_mm'], float), dims):
            raise ValueError('Scene registration dimensions differ from executed geometry')
        if registration.floor_y_mm is None or registration.floor_y_mm != floor:
            raise ValueError('Scene registration floor differs from executed contact floor')
    return registration


def _window(df, review):
    timeline = timeline_from_frame(df)
    if not timeline.aligned:
        raise ValueError(timeline.reason)
    times, time = timeline.times, timeline.t1
    matches = np.flatnonzero(times == time)
    if len(matches) != 1:
        raise ValueError('T1MinusTimeSec must match an actual sample')
    end = int(matches[0])
    impact = _number(_constant(df, (*SUMMARY, 'FirstImpactTimeSec')))
    if end + 1 >= len(times) or impact != times[end + 1]:
        raise ValueError('First impact must be the actual sample immediately after t1−')
    if not _true(_constant(df, (*SUMMARY, 'ImpactDetected'))) or _constant(df, (*SUMMARY, 'ContactState')) != 'ImpactEvent':
        raise ValueError('Recorded contact state is inconsistent with an impact')
    if exceeds_gap_limit(time, impact, FIT_SETTINGS['maximum_gap_s']):
        raise ValueError('Precontact-to-impact sampling gap exceeds 20 ms')
    rows = np.array([i for i in range(end + 1)
                     if not exceeds_gap_limit(times[i], time, FIT_SETTINGS['window_s'])], dtype=int)
    if len(rows) < FIT_SETTINGS['minimum_samples']:
        raise ValueError('Precontact fit needs at least five samples in 40 ms')
    selected = times[rows]
    if exceeds_gap_limit(selected[-1], selected[0] + FIT_SETTINGS['minimum_span_s'], 0.):
        raise ValueError('Precontact fit needs at least 20 ms of observations')
    if any(exceeds_gap_limit(a, b, FIT_SETTINGS['maximum_gap_s']) for a, b in zip(selected[:-1], selected[1:])):
        raise ValueError('Precontact fit cannot cross a sampling gap over 20 ms')
    if review and not (review['candidate']['start'] <= selected[0] <= time <= review['candidate']['end']):
        raise ValueError('Precontact fit extends outside the reviewed scene')
    poses = _column(df, ('Info', 'Pose', 'Source')).iloc[rows]
    if not poses.eq('Optimized').all():
        raise ValueError('Precontact window contains unavailable or failed pose tracking')
    faces = [column for column in df.columns if isinstance(column, tuple)
             and len(column) == 3 and column[0] == 'Position' and column[2] == 'FaceInfo']
    if not faces:
        raise ValueError('Marker face assignments are not recorded')
    face_frame = pd.DataFrame({f'{column[1]}_FaceInfo': _column(df, column).iloc[rows].to_numpy()
                               for column in faces})
    if len(face_segments(face_frame)) != 1:
        raise ValueError('Precontact fit crosses a marker face-assignment change')
    return rows, selected, time, impact


def _fit(values, times):
    if not np.isfinite(values).all():
        raise ValueError('Required pose component is missing in the precontact window')
    x = (times - times[-1]) / FIT_SETTINGS['window_s']
    design = np.column_stack((np.ones(len(x)), x, x * x))
    # Removing the endpoint offset improves conditioning and keeps a constant
    # path exactly at zero speed instead of creating roundoff descent.
    values = values - values[-1]
    coefficients, _, rank, _ = np.linalg.lstsq(design, values, rcond=None)
    if rank != 3:
        raise ValueError('Precontact quadratic fit is singular')
    residual = np.sqrt(np.mean((design @ coefficients - values) ** 2, axis=0))
    derivative = coefficients[1] / FIT_SETTINGS['window_s']
    if not np.isfinite(derivative).all() or not np.isfinite(residual).all():
        raise ValueError('Precontact fit is not finite')
    return derivative, residual


def _pose_component(df, rows, name):
    return pd.to_numeric(_column(df, ('Position', 'CoM', name)).iloc[rows], errors='coerce').to_numpy(dtype=float)


def calculate_impact_metrics(df):
    metrics = _diagnostics(df)
    diagnostic_field_errors = {key: metrics[key].reason for key in
                               ('first_contact', 'contact_confidence', 'final_face')}
    observation_key, review, review_error = None, None, ''
    try:
        review, observation_key = _observation_context(df)
    except (ValueError, TypeError, KeyError, OverflowError) as error:
        review_error = str(error)
    event = (FirstEventEvidence(reasons=(review_error,)) if review_error
             else validate_first_event(df, review))
    if not event.valid:
        for key in ('first_contact', 'contact_confidence'):
            metrics[key] = MetricValue(None, event.reason)
    evidence = {'method': 'one-sided-quadratic-observed-pose-v1', 'settings': dict(FIT_SETTINGS),
                'support_policy': 'uncalibrated software limits; not ISTA limits or measured accuracy',
                'origin': 'box geometric centre; historical CoM column name',
                'vertical_sign': 'world Y upward positive', 'fit_residuals': {},
                'first_event': event.as_dict(), 'diagnostic_field_errors': diagnostic_field_errors}
    try:
        if review_error:
            raise ValueError(review_error)
        artifact, dims, floor = _processing_context(df)
        registration = _review_context(review, dims, floor)
        rows, times, time, impact = _window(df, review)
        evidence.update(evaluation_time_s=time, window_start_s=float(times[0]), window_end_s=float(times[-1]),
                        sample_count=len(rows), first_impact_time_s=impact,
                        impact_bracket_s=[time, impact], floor_y_mm=floor)
    except (ValueError, TypeError, KeyError, OverflowError) as error:
        reason = str(error) if not isinstance(error, KeyError) else f'Processing/review provenance missing: {error}'
        for key in ('vertical_velocity', 'horizontal_speed', 'angular_speed', 'equivalent_height'):
            metrics[key] = MetricValue(None, reason)
        return ImpactResult(metrics, evidence, observation_key)

    positions, velocities, component_errors = {}, {}, {}
    for axis in 'XYZ':
        try:
            positions[axis] = _pose_component(df, rows, 'P_T' + axis)
            velocity, residual = _fit(positions[axis], times)
            evidence['fit_residuals']['position_' + axis + '_mm'] = float(residual)
            if residual > FIT_SETTINGS['maximum_translation_rms_mm']:
                raise ValueError(f'Position {axis} fit RMS exceeds the 1 mm software support limit')
            velocities[axis] = float(velocity / 1000.)
        except (ValueError, TypeError, np.linalg.LinAlgError) as error:
            component_errors[axis] = str(error)
    metrics['vertical_velocity'] = MetricValue(velocities.get('Y'), component_errors.get('Y', ''))
    if 'X' in velocities and 'Z' in velocities:
        metrics['horizontal_speed'] = MetricValue(float(np.hypot(velocities['X'], velocities['Z'])))
    else:
        metrics['horizontal_speed'] = MetricValue(None, component_errors.get('X') or component_errors.get('Z', ''))

    rotations, rotation_error = None, ''
    try:
        vectors = np.column_stack([_pose_component(df, rows, 'P_R' + axis) for axis in 'XYZ'])
        if not np.isfinite(vectors).all():
            raise ValueError('Rotation is missing in the precontact window')
        rotations = Rotation.from_rotvec(vectors)
        relative = (rotations * rotations[-1].inv()).as_rotvec()
        steps = (rotations[1:] * rotations[:-1].inv()).magnitude()
        endpoint_angles = np.linalg.norm(relative, axis=1)
        evidence['observed_rotation_step_max_rad'] = float(np.max(steps))
        evidence['observed_endpoint_rotation_max_rad'] = float(np.max(endpoint_angles))
        if (np.any(steps > FIT_SETTINGS['maximum_rotation_step_rad'])
                or np.any(endpoint_angles > FIT_SETTINGS['maximum_endpoint_rotation_rad'])):
            raise ValueError('Rotation exceeds 0.25 rad software support; larger-window angular fits are ambiguous')
        omega, residual = _fit(relative, times)
        evidence['fit_residuals']['rotation_world_rad'] = residual.tolist()
        evidence['fit_residuals']['rotation_rms_rad'] = float(np.linalg.norm(residual))
        if np.linalg.norm(residual) > FIT_SETTINGS['maximum_angular_rms_rad']:
            raise ValueError('Rotation fit RMS exceeds the 0.01 rad software support limit')
        metrics['angular_speed'] = MetricValue(float(np.linalg.norm(omega)))
        evidence['angular_velocity_world_rad_s'] = omega.tolist()
    except (ValueError, TypeError, np.linalg.LinAlgError) as error:
        rotation_error = str(error)
        metrics['angular_speed'] = MetricValue(None, rotation_error)
        rotations = None

    try:
        if review is None:
            raise ValueError('Reviewed Type G free fall and explicit COM registration are required')
        identity = review['identity']
        if not (identity['confirmed'] is True and identity['ista_type'] == 'G'
                and identity['scenario_kind'] == 'free_fall' and identity.get('scenario_id')
                and review['candidate'].get('evidence_class') == review['candidate'].get('motion') == 'free_fall'
                and identity['applied_edition'] == identity['reference_edition'] == '2018-03'
                and artifact.get('IstaType') == 'G' and artifact.get('ScenarioId') == identity['scenario_id']
                and artifact.get('ScenarioKind') == 'free_fall'):
            raise ValueError('Velocity-equivalent height requires a confirmed 2018-03 Type G free fall')
        if registration is None or registration.com_offset_mm is None:
            raise ValueError('Explicit box-local COM offset is not registered')
        if 'Y' not in velocities:
            raise ValueError(component_errors['Y'])
        offset = np.asarray(registration.com_offset_mm, float)
        if np.any(offset != 0):
            if rotations is None:
                raise ValueError(rotation_error)
            com_y = positions['Y'] + rotations.apply(offset)[:, 1]
        else:
            com_y = positions['Y']
        derivative, residual = _fit(com_y, times)
        evidence['fit_residuals']['com_Y_mm'] = float(residual)
        if residual > FIT_SETTINGS['maximum_translation_rms_mm']:
            raise ValueError('COM Y fit RMS exceeds the 1 mm software support limit')
        com_vy = float(derivative / 1000.)
        if not math.isfinite(com_vy) or com_vy >= 0:
            raise ValueError('Registered COM velocity must be strictly downward')
        height = 1000. * com_vy ** 2 / (2. * FIT_SETTINGS['gravity_m_s2'])
        if not math.isfinite(height):
            raise ValueError('Velocity-equivalent height is not finite')
        metrics['equivalent_height'] = MetricValue(height)
        evidence['com_vertical_velocity_m_s'] = com_vy
        evidence['com_offset_mm'] = list(registration.com_offset_mm)
    except (ValueError, TypeError, KeyError, OverflowError, np.linalg.LinAlgError) as error:
        metrics['equivalent_height'] = MetricValue(None, str(error))
    return ImpactResult(metrics, evidence, observation_key)
