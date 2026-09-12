"""Offline test harness; truth never enters the production candidate detector."""
from __future__ import annotations

import argparse
import json
import hashlib
from copy import deepcopy
from pathlib import Path
import sys

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
from src.config.data_columns import FACE_PREFIX_TO_INFO, SourceCols, TimeCols


REPORT_VERSION = 1
FIXTURE_FILES = ('observed.csv', 'truth_pose.csv', 'truth_markers.csv', 'observed.synthetic.json')
RECOVERY_CASES = ('healthy', 'x', 'y', 'z', 'xx', 'xy', 'gap', 'gap_x', 'genuine_rotation')


def _file_hashes(root):
    return {name: hashlib.sha256((Path(root) / name).read_bytes()).hexdigest()
            if (Path(root) / name).is_file() else None for name in FIXTURE_FILES}


def _write_report(path, report):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, allow_nan=False), encoding='utf-8')


def _read_manifest(root):
    manifest = json.loads((Path(root) / 'observed.synthetic.json').read_text(encoding='utf-8'))
    if not isinstance(manifest, dict):
        raise ValueError('Fixture manifest must be an object.')
    # Check every nested value before copying metadata into a report. This also
    # rejects JSON numeric overflow such as 1e999, not just NaN/Infinity tokens.
    try:
        json.dumps(manifest, allow_nan=False)
    except ValueError as error:
        raise ValueError('Fixture manifest must contain only finite JSON values.') from error
    return manifest


def _base_report(root, invocation=None):
    return {'report_schema_version': REPORT_VERSION, 'fixture_schema_version': None,
            'case_id': None, 'source_kind': None, 'evidence_level': None, 'seed': None,
            'fixture_root': str(Path(root).resolve()), 'generator_version': None,
            'profile': None, 'layout_hash': None, 'input_sha256': None, 'files_sha256': {},
            'observed_range': None, 'events': None, 'expected': None, 'tolerances': None,
            'invocation': invocation or {'kind': 'api', 'call': 'src.simulation.validate_marker_fixtures.validate_case',
                                         'arguments': {'root': str(Path(root).resolve())}},
            'oracle_rationale': {'pose_origin': 'Independent simulator body origin; COM is separate.',
                'position': 'Maximum Euclidean body-origin error in mm across optimized frames.',
                'rotation': 'Maximum relative SO(3) angle in degrees across optimized frames.',
                'manual_approval': 'Fixture event axis/time is test-only approval after production candidate detection.',
                'limit': 'Synthetic numerical integration evidence, not camera accuracy or ISTA compliance.'},
            'checks': {'execution_completed': False}, 'status': 'fail'}


def _preserve_failure(root, report, error, *, filename='validation.json'):
    report['status'] = 'fail'
    report.setdefault('checks', {})['execution_completed'] = False
    report['error'] = {'type': type(error).__name__, 'message': str(error)}
    try:
        _write_report(Path(root) / filename, report)
    except Exception as reporting_error:
        error.add_note(f'Could not preserve validation report: {reporting_error}')


def _observed_range(raw):
    times = pd.to_numeric(raw[TimeCols.TIME], errors='raise').to_numpy(float)
    frames = pd.to_numeric(raw[TimeCols.FRAME], errors='raise').to_numpy(float)
    if not len(times) or not np.isfinite(times).all() or not np.isfinite(frames).all():
        raise ValueError('Validation needs finite observed sample times and frame identifiers.')
    return {'sample_count': len(raw), 'start_time_s': float(times[0]), 'end_time_s': float(times[-1]),
            'start_frame': int(frames[0]), 'end_frame': int(frames[-1])}


def _optimizer(dims):
    return PoseOptimizer(config_app.FACE_DEFINITIONS, config_app.calculate_local_box_corners(dims))


def _manual_pose(context, *, materializer=None):
    if not context['decisions']:
        return context['pose']
    materializer = materialize_face_assignments if materializer is None else materializer
    header, raw = materializer(deepcopy(context['header']), context['raw'].copy(deep=True), context['decisions'])
    parsed = Parser(FACE_PREFIX_TO_INFO).process(header, raw)
    return _optimizer(context['dims']).process(parsed, context['dims'])


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


def _evaluate(context, *, truth=None, fixed=None):
    """Compare a real production run to the offline oracle, without saving it."""
    manifest, candidates = context['manifest'], context['candidates']
    truth = context['truth'] if truth is None else truth
    fixed = context['fixed'] if fixed is None else fixed
    result = deepcopy(context['report'])
    expected_times = [e['time_s'] for e in manifest['events'] if e['kind'] == 'solver_pose_half_turn']
    found = [c.boundary_time_sec for c in candidates]
    checks = {'execution_completed': True,
              'no_automatic_recommendations': all(c.recommendation_axis is None for c in candidates),
              'declared_flip_boundaries_found': all(any(abs(t - f) < 1e-8 for f in found) for t in expected_times)}
    result.update({'expected_flip_times_s': expected_times,
              'candidates': [{'time_s': c.boundary_time_sec, 'trigger': c.trigger,
                              'recommendation': c.recommendation_axis,
                              'refit_residual_deg': {h.label: h.residual_deg if np.isfinite(h.residual_deg) else None for h in c.hypotheses}}
                             for c in candidates],
              'raw_pose_error': pose_error(context['pose'], truth),
              'note': 'Recommendation checks prove abstention policy only; recommendations remain disabled.'})
    case = manifest['case_id']
    if case in RECOVERY_CASES:
        errors = pose_error(fixed, truth)
        result['after_oracle_manual_approval'] = errors
        tolerance = manifest['pose_tolerances']
        expected_valid = len(truth) - (5 if case in ('gap', 'gap_x') else 0)
        checks['pose_recovery'] = bool(errors['valid_frames'] == expected_valid
                                  and errors['max_position_mm'] < tolerance['position_mm']
                                  and errors['max_rotation_deg'] < tolerance['rotation_deg'])
        result['expected']['pose_valid_frames'] = expected_valid
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
    return result


def _validate_run(root, *, profile=None, invocation=None, failure_reports=None):
    root = Path(root)
    report = _base_report(root, invocation)
    try:
        report['files_sha256'] = _file_hashes(root)
        report['input_sha256'] = report['files_sha256']['observed.csv']
        profile = load_profile() if profile is None else deepcopy(profile)
        layout_hash = validate_profile(profile)
        report['analysis_profile'] = {'profile_id': profile['profile_id'], 'layout_hash': layout_hash}
        header, raw = DataLoader().load_csv(str(root / 'observed.csv'))
        report['observed_range'] = _observed_range(raw)
        declared_hash = header.get('artifact_metadata', {}).get('MarkerLayoutHash')
        if declared_hash and declared_hash != layout_hash:
            raise ValueError('Explicit analysis profile does not match the generated input.')
        dims = tuple(profile['box_dims_mm'])
        # Production sees only observations, generic face labels and explicit
        # dimensions. Fixture events and truth are read after candidate creation.
        parsed = Parser(FACE_PREFIX_TO_INFO).process(header, raw)
        pose = _optimizer(dims).process(parsed, dims)
        candidates = FaceAssignmentAnalyzer().detect(parsed, pose, dims)
        manifest = _read_manifest(root)
        for key in ('case_id', 'source_kind', 'evidence_level', 'seed', 'generator_version', 'profile', 'layout_hash', 'events'):
            report[key] = deepcopy(manifest.get(key))
        report['fixture_schema_version'] = manifest.get('schema_version')
        report['generator_provenance'] = {key: manifest.get(key) for key in
            ('code_revision', 'working_tree_dirty', 'generator_source_sha256', 'engine_source_sha256', 'mujoco_version')}
        report['expected'] = {key: deepcopy(manifest.get(key)) for key in
            ('expected_flip_frames', 'expected_axes', 'expected_recommendation', 'expected_approval')}
        report['tolerances'] = deepcopy(manifest['pose_tolerances'])
        report['tolerances']['boundary_time_s'] = 1e-8
        report['scenario'] = manifest['parameters']['scenario']
        if manifest['layout_hash'] != layout_hash:
            raise ValueError('Explicit analysis profile does not match the generated input.')
        for name in FIXTURE_FILES[:-1]:
            if report['files_sha256'][name] != manifest['files'][name]:
                raise ValueError(f'Fixture integrity mismatch: {name}')
        truth = pd.read_csv(root / 'truth_pose.csv')
        decisions = [MarkerCorrectionDecision(f'oracle-{e["frame"]}', e['time_s'], True, e['axis'],
                      correction_kind='face_assignment', algorithm_version='3.0')
                     for e in manifest['events'] if e['kind'] == 'solver_pose_half_turn'] if manifest['case_id'] in RECOVERY_CASES else []
        report['manual_approval'] = [{'time_s': d.boundary_time_sec, 'axis': d.axis,
                                     'approved': d.approved, 'kind': d.correction_kind} for d in decisions]
        context = {'root': root, 'header': header, 'raw': raw, 'dims': dims, 'pose': pose,
                   'candidates': candidates, 'manifest': manifest, 'truth': truth, 'decisions': decisions,
                   'profile': profile, 'report': report}
        context['fixed'] = _manual_pose(context)
        result = _evaluate(context)
        report = result
        report['files_after_sha256'] = _file_hashes(root)
        changed_files = [name for name in FIXTURE_FILES
                         if report['files_after_sha256'][name] != report['files_sha256'][name]]
        report['checks']['fixture_files_unchanged'] = not changed_files
        if changed_files:
            raise ValueError('Fixture files changed during validation: ' + ', '.join(changed_files))
        context['report'] = result
        _write_report(root / 'validation.json', result)
        return result, context
    except Exception as error:
        if report['fixture_schema_version'] is None:
            # Recover readable metadata for this failure report only, after the
            # production operation has already failed. Never feed it to analysis.
            try:
                failed_manifest = _read_manifest(root)
                for key in ('case_id', 'source_kind', 'evidence_level', 'seed', 'generator_version', 'profile', 'layout_hash', 'events'):
                    report[key] = deepcopy(failed_manifest.get(key))
                report['fixture_schema_version'] = failed_manifest.get('schema_version')
                report['expected'] = {key: deepcopy(failed_manifest.get(key)) for key in
                    ('expected_flip_frames', 'expected_axes', 'expected_recommendation', 'expected_approval')}
                report['tolerances'] = deepcopy(failed_manifest.get('pose_tolerances'))
                report['metadata_recovery'] = 'Read from fixture manifest after analysis failure; not supplied to production.'
            except (OSError, ValueError) as recovery_error:
                report['metadata_recovery_error'] = {'type': type(recovery_error).__name__,
                                                     'message': str(recovery_error)}
        _preserve_failure(root, report, error)
        if failure_reports is not None:
            failure_reports.append(report)
        raise


def validate_case(root, *, profile=None):
    """Validate one case and retain failure evidence before re-raising errors."""
    return _validate_run(root, profile=profile)[0]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', default='tmp/mujoco_marker_validation')
    parser.add_argument('--case', choices=(*CASES, 'all'), default='all')
    parser.add_argument('--seed', type=int, default=74082)
    parser.add_argument('--negative-controls', action='store_true', help='Also verify two intentional faults on public 18-marker free-fall fixtures.')
    layouts = parser.add_mutually_exclusive_group()
    layouts.add_argument('--profile', help='Same explicit local JSON layout used for generation.')
    layouts.add_argument('--example', choices=('18','32'), default='18')
    parser.add_argument('--motion', choices=MOTIONS, default='free_fall')
    arguments = sys.argv[1:] if argv is None else argv
    args = parser.parse_args(arguments)
    profile = load_profile(args.profile, example=args.example)
    if args.negative_controls and (profile != load_profile() or args.motion != 'free_fall'):
        parser.error('--negative-controls requires the public 18-marker profile and free_fall motion.')
    invocation = {'kind': 'cli', 'module': 'src.simulation.validate_marker_fixtures',
                  'argv': list(arguments), 'python_executable': sys.executable, 'working_directory': str(Path.cwd())}
    results = []
    baselines = {}
    for case in CASES if args.case == 'all' else [args.case]:
        print(f'Validating {case}...', flush=True)
        root = Path(args.output) / case
        failures = []
        try:
            root = write_case(args.output, case, seed=args.seed, profile=profile, motion=args.motion)
            result, context = _validate_run(root, profile=profile, invocation=invocation, failure_reports=failures)
            if case in ('healthy', 'x'):
                baselines[case] = context
        except Exception as error:
            if failures:
                result = failures[-1]
            else:
                result = _base_report(root, invocation)
                result['requested_case'] = case
                result['requested_seed'] = args.seed
                result['report_file'] = str(root / 'validation_failure.json')
                # A generation failure is a new failed run, not a validation of
                # the older files. Keep any older normal report intact.
                _preserve_failure(root, result, error, filename='validation_failure.json')
        results.append(result)
        print(json.dumps({'case': case, 'status': result['status'], 'checks': result['checks'],
                          'pose': result.get('after_oracle_manual_approval'),
                          'report': result.get('report_file', str(root / 'validation.json')),
                          **({'error': result['error']} if 'error' in result else {})}), flush=True)
    controls = None
    if args.negative_controls:
        from .marker_validation_controls import run_negative_controls
        try:
            controls = run_negative_controls(args.output, seed=args.seed, baselines=baselines, invocation=invocation)
        except Exception as error:
            controls = {'status': 'fail', 'error': {'type': type(error).__name__, 'message': str(error)}}
        print(json.dumps({'negative_controls': controls['status'],
                          'report': str(Path(args.output) / 'negative_controls.json'),
                          **({'error': controls['error']} if 'error' in controls else {})}), flush=True)
    _write_report(Path(args.output) / 'validation_summary.json', results)
    raise SystemExit(0 if all(r['status'] == 'pass' for r in results)
                     and (controls is None or controls['status'] == 'pass') else 1)


if __name__ == '__main__':
    main()
