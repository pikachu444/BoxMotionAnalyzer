"""Offline test harness; truth never enters the production candidate detector."""
from __future__ import annotations

import argparse
import json
import hashlib
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.spatial.transform import Rotation

from .marker_fixtures import CASES, MOTIONS, write_case, load_profile, validate_profile
from src.analysis.pipeline.data_loader import DataLoader
from src.analysis.pipeline.parser import Parser
from src.analysis.pipeline.pose_optimizer import PoseOptimizer
from src.analysis.pipeline.face_assignment import FaceAssignmentAnalyzer, materialize_face_assignments, POSE_COLUMNS
from src.analysis.pipeline.marker_flip import MarkerCorrectionDecision
from src.config import config_app
from src.config.data_columns import FACE_PREFIX_TO_INFO, SourceCols


def pose_error(pose, truth):
    values = pose[list(POSE_COLUMNS)].to_numpy(dtype=float)
    valid = np.isfinite(values).all(axis=1) & pose[SourceCols.POSE].eq('Optimized').to_numpy()
    if not valid.any():
        return {'valid_frames': 0, 'max_position_mm': None, 'max_rotation_deg': None}
    target = truth[['body_x_mm', 'body_y_mm', 'body_z_mm']].to_numpy()
    matrices = truth[[f'r{i}{j}' for i in range(3) for j in range(3)]].to_numpy().reshape(-1, 3, 3)
    return {'valid_frames': int(valid.sum()),
            'max_position_mm': float(np.linalg.norm(values[valid, :3] - target[valid], axis=1).max()),
            'max_rotation_deg': float(np.degrees((Rotation.from_matrix(matrices[valid]).inv()
                                   * Rotation.from_rotvec(values[valid, 3:])).magnitude()).max())}


def validate_case(root, *, profile=None):
    root = Path(root)
    # Only observed data, explicit box dimensions, and generic label conventions
    # are passed to production. The test oracle is read after candidate creation.
    header, raw = DataLoader().load_csv(str(root / 'observed.csv'))
    profile = load_profile() if profile is None else profile
    expected_layout_hash = validate_profile(profile)
    dims = tuple(profile['box_dims_mm'])
    parsed = Parser(FACE_PREFIX_TO_INFO).process(header, raw)
    optimizer = PoseOptimizer(config_app.FACE_DEFINITIONS, config_app.calculate_local_box_corners(dims))
    pose = optimizer.process(parsed, dims)
    candidates = FaceAssignmentAnalyzer().detect(parsed, pose, dims)
    manifest = json.loads((root / 'observed.synthetic.json').read_text(encoding='utf-8'))
    if manifest['layout_hash'] != expected_layout_hash:
        raise ValueError('Explicit analysis profile does not match the generated input.')
    for name in ('observed.csv', 'truth_pose.csv', 'truth_markers.csv'):
        if hashlib.sha256((root / name).read_bytes()).hexdigest() != manifest['files'][name]:
            raise ValueError(f'Fixture integrity mismatch: {name}')
    truth = pd.read_csv(root / 'truth_pose.csv')
    expected_times = [e['time_s'] for e in manifest['events'] if e['kind'] == 'solver_pose_half_turn']
    found = [c.boundary_time_sec for c in candidates]
    checks = {'no_automatic_recommendations': all(c.recommendation_axis is None for c in candidates),
              'declared_flip_boundaries_found': all(any(abs(t - f) < 1e-8 for f in found) for t in expected_times)}
    result = {'case_id': manifest['case_id'], 'evidence_level': manifest['evidence_level'],
              'input_sha256': manifest['files']['observed.csv'],
              'seed': manifest['seed'], 'expected_flip_times_s': expected_times,
              'candidates': [{'time_s': c.boundary_time_sec, 'trigger': c.trigger,
                              'recommendation': c.recommendation_axis,
                              'refit_residual_deg': {h.label: h.residual_deg if np.isfinite(h.residual_deg) else None for h in c.hypotheses}}
                             for c in candidates],
              'raw_pose_error': pose_error(pose, truth),
              'note': 'Recommendation checks prove abstention policy only; recommendations remain disabled.'}
    case = manifest['case_id']
    if case in ('healthy', 'x', 'y', 'z', 'xx', 'xy', 'gap', 'gap_x', 'genuine_rotation'):
        decisions = [MarkerCorrectionDecision(f'oracle-{e["frame"]}', e['time_s'], True, e['axis'],
                      correction_kind='face_assignment', algorithm_version='3.0')
                     for e in manifest['events'] if e['kind'] == 'solver_pose_half_turn']
        if decisions:
            # Explicit test-only manual approval, never detector-generated truth.
            corrected_header, corrected = materialize_face_assignments(header, raw, decisions)
            fixed = optimizer.process(Parser(FACE_PREFIX_TO_INFO).process(corrected_header, corrected), dims)
        else:
            fixed = pose
        errors = pose_error(fixed, truth)
        result['after_oracle_manual_approval'] = errors
        tolerance = manifest['pose_tolerances']
        expected_valid = len(truth) - (5 if case in ('gap', 'gap_x') else 0)
        checks['pose_recovery'] = (errors['valid_frames'] == expected_valid
                                  and errors['max_position_mm'] < tolerance['position_mm']
                                  and errors['max_rotation_deg'] < tolerance['rotation_deg'])
    if case == 'healthy' and manifest['parameters']['scenario'] in ('free_fall','free-fall-no-contact'):
        checks['healthy_no_candidates'] = not candidates
    if manifest['parameters']['scenario'] in ('face','edge','corner'):
        contact = np.asarray(manifest['parameters']['recorded_contact_force_n'])
        active = np.flatnonzero(contact > 1e-8)
        checks['recorded_floor_contact'] = bool(len(active) and active[0] > 0)
        result['contact'] = {'first_force_time_s': float(truth.time_s.iloc[active[0]]) if len(active) else None,
                             'force_positive_samples': int(len(active)),
                             'note': 'Soft model contact, not physical impact calibration.'}
    if case == 'low_coverage':
        checks['insufficient_pose_unavailable'] = result['raw_pose_error']['valid_frames'] == 0
        checks['no_candidate_from_insufficient_pose'] = not candidates
    result['checks'] = checks
    result['validation_scope'] = ('pose_mechanics' if 'pose_recovery' in checks else
                                  'insufficient_data_rejection' if case == 'low_coverage' else 'abstention_policy_only')
    result['status'] = 'pass' if all(checks.values()) else 'fail'
    (root / 'validation.json').write_text(json.dumps(result, indent=2, allow_nan=False), encoding='utf-8')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', default='tmp/mujoco_marker_validation')
    parser.add_argument('--case', choices=(*CASES, 'all'), default='all')
    layouts = parser.add_mutually_exclusive_group()
    layouts.add_argument('--profile', help='Same explicit local JSON layout used for generation.')
    layouts.add_argument('--example', choices=('18','32'), default='18')
    parser.add_argument('--motion', choices=MOTIONS, default='free_fall')
    args = parser.parse_args()
    profile = load_profile(args.profile, example=args.example)
    results = []
    for case in CASES if args.case == 'all' else [args.case]:
        print(f'Validating {case}...', flush=True)
        root = write_case(args.output, case, profile=profile, motion=args.motion)
        result = validate_case(root, profile=profile)
        results.append(result)
        print(json.dumps({'case': case, 'status': result['status'], 'checks': result['checks'],
                          'pose': result.get('after_oracle_manual_approval')}), flush=True)
    Path(args.output, 'validation_summary.json').write_text(json.dumps(results, indent=2), encoding='utf-8')
    raise SystemExit(0 if all(r['status'] == 'pass' for r in results) else 1)


if __name__ == '__main__':
    main()
