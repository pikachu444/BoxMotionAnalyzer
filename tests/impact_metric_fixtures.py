"""Analytical public contract inputs, not claims of processing measured trials.

Expected velocities come from the prescribed world translation and rotation.
No production metric function, saved velocity, or simulation truth is used.
"""
from copy import deepcopy
from dataclasses import asdict
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.spatial.transform import Rotation

from src.analysis.pipeline.scene_detection import Registration
from src.config.config_app import FACE_DEFINITIONS
from src.utils.processing_settings import processing_record


SUMMARY = ('Analysis', 'DropPostureSummary')
REVIEW = ('Info', 'SceneReview', 'Json')


def make_frame(*, times=None, t1=.040, impact=.048, velocity=(3., -4., 0.), omega=(0., 0., 2.),
               com_offset=(0., 0., 0.), ista_type='G', confirmed=True, scenario_id='G01',
               review=True, source_sha256='a' * 64, marker_smoothing=False, result_resampling=False,
               floor_y_mm=0., registration_floor_y_mm=0., base_rotvec=(0., 0., 0.)):
    times = np.array([0., .008, .016, .024, .032, .040, .048, .056] if times is None else times, float)
    dims = [200., 120., 80.]
    signs = np.array([[-1,-1,-1], [1,-1,-1], [1,1,-1], [-1,1,-1],
                      [-1,-1,1], [1,-1,1], [1,1,1], [-1,1,1]])
    corners = (signs * [100., 60., 40.]).tolist()
    positions = np.array([0., 92., 0.]) + (times - t1)[:, None] * np.asarray(velocity) * 1000.
    rotations = (Rotation.from_rotvec(times[:, None] * np.asarray(omega))
                 * Rotation.from_rotvec(base_rotvec)).as_rotvec()
    data = {('Info', 'Time', 'Time'): times,
            ('Info', 'Frame', 'Frame'): np.arange(len(times)),
            ('Info', 'Pose', 'Source'): ['Optimized'] * len(times),
            ('Position', 'M1', 'FaceInfo'): ['FRONT'] * len(times),
            (*SUMMARY, 'T1MinusTimeSec'): t1, (*SUMMARY, 'T1Detected'): True,
            (*SUMMARY, 'FirstImpactTimeSec'): impact, (*SUMMARY, 'ImpactDetected'): True,
            (*SUMMARY, 'ContactState'): 'ImpactEvent', (*SUMMARY, 'FirstImpactContact'): '{C1,C2}',
            (*SUMMARY, 'ContactConfidence'): .75,
            ('Info', 'Timeline', 'SliceStartSec'): float(times[0]),
            ('Info', 'Timeline', 'SliceEndSec'): float(times[-1])}
    for i, axis in enumerate('XYZ'):
        data[('Position', 'CoM', 'P_T' + axis)] = positions[:, i]
        data[('Position', 'CoM', 'P_R' + axis)] = rotations[:, i]
        # A deliberately wrong saved velocity demonstrates that it is unused.
        data[('Velocity', 'CoM', 'Global_V_T' + axis)] = 999999.
    settings = {
        'single_pass': {
            'marker_smoothing': {'enabled': marker_smoothing},
            'geometry_mm': corners, 'face_definitions': deepcopy(FACE_DEFINITIONS),
            'derivatives': {'pose_lowpass': {'enabled': True}, 'pose_moving_average': {'enabled': True}},
            'frame_analysis': {'vertical_axis': 1, 'floor_policy': 'explicit-horizontal-plane',
                               'floor_level_mm': floor_y_mm},
        },
        'result_resampling': {'enabled': result_resampling},
        'postprocess': {'vertical_axis': 1, 'floor_policy': 'explicit-horizontal-plane',
                        'floor_level_mm': floor_y_mm, 'geometry_mm': corners,
                        'face_definitions': deepcopy(FACE_DEFINITIONS),
                        'contact_threshold_mm': 1., 'contact_policy': 'drop-posture-evidence-v1'},
    }
    version, settings_text = processing_record(settings)
    effective_id = scenario_id if confirmed else None
    artifact = dict(SchemaVersion='1', SourceKind='handcrafted_dummy', ModelId='analytic-box',
        BoxLengthMm=200., BoxWidthMm=120., BoxHeightMm=80., IstaType=ista_type if ista_type != 'Unknown' else None,
        ScenarioId=effective_id, ScenarioKind='free_fall' if confirmed else None,
        MarkerLayoutId='analytic-layout', MarkerLayoutHash='b' * 64,
        ProcessingSemanticsVersion=version, ProcessingSettingsJson=settings_text,
        CoordinatePolicy='world-y-up-box-local-fixed-center-v1', UnitsPolicy='bma-mm-s-rotvec-rad-summary-deg-v1',
        GeneratorVersion='analytical-contract-1')
    for key, value in artifact.items():
        data[('Info', 'Artifact', key)] = value
    if review:
        profile = {'units': 'mm', 'origin': 'box-geometric-center', 'box_dims_mm': dims,
                   'markers': [{'id': f'M{i+1}', 'xyz_mm': corner} for i, corner in enumerate(corners[:4])]}
        registration = Registration(profile, registration_floor_y_mm, 1., com_offset)
        payload = {
            'version': 1, 'source_sha256': source_sha256,
            'candidate': {'id': 'scene_001', 'start': float(times[0]), 'end': float(times[-1]),
                          'auto_start': float(times[0]), 'auto_end': float(times[-1]),
                          'evidence_class': 'free_fall', 'motion': 'free_fall', 'tags': [],
                          'origin': 'automatic', 'decision': 'include', 'evidence_status': 'current'},
            'identity': {'ista_type': ista_type, 'scenario_id': effective_id,
                         'scenario_kind': 'free_fall' if confirmed else None, 'confirmed': confirmed,
                         'reference_edition': '2018-03', 'applied_edition': '2018-03' if confirmed else None},
            'detection': {'version': 'observed-motion-v1', 'settings': {},
                          'registration': asdict(registration), 'registration_sha256': registration.fingerprint},
        }
        data[REVIEW] = json.dumps(payload, sort_keys=True, separators=(',', ':'))
    frame = pd.DataFrame(data)
    frame.columns = pd.MultiIndex.from_tuples(frame.columns)
    return frame


def write_proc(path, **kwargs):
    path = Path(path)
    make_frame(**kwargs).to_csv(path, index=False)
    return path


def update_processing(frame, edit):
    """Change explicitly fabricated execution declarations and their integrity hash."""
    settings = json.loads(frame[('Info', 'Artifact', 'ProcessingSettingsJson')].iloc[0])
    edit(settings)
    version, text = processing_record(settings)
    frame[('Info', 'Artifact', 'ProcessingSemanticsVersion')] = version
    frame[('Info', 'Artifact', 'ProcessingSettingsJson')] = text
