"""Two deliberate offline faults that must fail real production-pose validation."""
from copy import deepcopy
import hashlib
from pathlib import Path
import tempfile

from .marker_fixtures import load_profile, validate_profile, write_case
from .validate_marker_fixtures import (
    REPORT_VERSION, _evaluate, _file_hashes, _manual_pose, _validate_run, _write_report,
)


def _uncorrected_copy(header, raw, decisions):
    """Deliberate test fault: accept the same decisions but omit materialization."""
    return deepcopy(header), raw.copy(deep=True)


def _expected_failure(result):
    return (result['status'] == 'fail'
            and [name for name, passed in result['checks'].items() if not passed] == ['pose_recovery'])


def _baseline_report_hash(context):
    return hashlib.sha256((context['root'] / 'validation.json').read_bytes()).hexdigest()


def run_negative_controls(output, *, seed=74082, baselines=None, invocation=None):
    """Use in-memory runs or new public fixtures; never trust saved pass JSON."""
    output = Path(output)
    report = {'report_schema_version': REPORT_VERSION, 'status': 'fail',
              'scope': 'Public 18-marker free_fall fixtures; two intentional offline faults.',
              'requested_seed': seed, 'baselines': {}, 'controls': [],
              'checks': {'all_controls_executed': False},
              'invocation': invocation or {'kind': 'api', 'call': 'src.simulation.marker_validation_controls.run_negative_controls',
                  'arguments': {'output': str(output.resolve()), 'seed': seed}}}
    try:
        profile = load_profile()
        profile_hash = validate_profile(profile)
        contexts = {}
        extra_root = None
        for case in ('healthy', 'x'):
            context = (baselines or {}).get(case)
            if context is None:
                output.mkdir(parents=True, exist_ok=True)
                if extra_root is None:
                    extra_root = Path(tempfile.mkdtemp(prefix='negative_control_inputs-', dir=output))
                root = write_case(extra_root, case, seed=seed, profile=profile, motion='free_fall')
                baseline, context = _validate_run(root, profile=profile, invocation=report['invocation'])
            else:
                baseline = context['report']
            report['baselines'][case] = deepcopy(baseline)
            if (baseline['status'] != 'pass' or baseline['case_id'] != case or baseline['seed'] != seed
                    or baseline['layout_hash'] != profile_hash or context['profile'] != profile
                    or baseline.get('scenario') != 'free_fall'
                    or _file_hashes(context['root']) != baseline['files_sha256']
                    or baseline['tolerances']['position_mm'] != .1
                    or baseline['tolerances']['rotation_deg'] != .1):
                raise ValueError('Negative controls require a passing current run of the same public profile, input, seed and tolerances.')
            contexts[case] = context
        before = {case: _file_hashes(context['root']) for case, context in contexts.items()}
        reports_before = {case: _baseline_report_hash(context) for case, context in contexts.items()}
        report['files_before_sha256'] = before
        report['baseline_reports_before_sha256'] = reports_before

        healthy = contexts['healthy']
        original_truth = healthy['truth'].copy(deep=True)
        offset_truth = original_truth.copy(deep=True)
        offset_truth['body_x_mm'] += 1.
        offset = _evaluate(healthy, truth=offset_truth)
        errors = offset['after_oracle_manual_approval']
        offset_checks = {
            'exact_pose_recovery_failure': _expected_failure(offset),
            'all_100_frames_valid': errors['valid_frames'] == 100,
            'position_error_above_0_9_mm': errors['max_position_mm'] > .9,
            'rotation_stays_below_0_1_deg': errors['max_rotation_deg'] < .1,
            'original_truth_memory_unchanged': healthy['truth'].equals(original_truth),
            'only_oracle_body_x_changed': offset_truth.drop(columns='body_x_mm').equals(original_truth.drop(columns='body_x_mm')),
        }
        report['controls'].append({'name': 'oracle_body_x_plus_1_mm', 'case_id': 'healthy',
            'fault': 'Add 1 mm only to comparison-oracle body_x_mm after production completes; COM and production inputs stay unchanged.',
            'expected_failure': {'failed_checks': ['pose_recovery'], 'valid_frames': 100,
                                 'position_error_lower_bound_mm': .9, 'rotation_upper_bound_deg': .1},
            'mutant': offset, 'checks': offset_checks,
            'status': 'pass' if all(offset_checks.values()) else 'fail'})

        x_case = contexts['x']
        approvals_before = deepcopy(x_case['report']['manual_approval'])
        uncorrected = _manual_pose(x_case, materializer=_uncorrected_copy)
        bypass = _evaluate(x_case, fixed=uncorrected)
        errors = bypass['after_oracle_manual_approval']
        bypass_checks = {
            'exact_pose_recovery_failure': _expected_failure(bypass),
            'all_100_frames_valid': errors['valid_frames'] == 100,
            'rotation_error_matches_half_turn': abs(errors['max_rotation_deg'] - 180.) < .1,
            'same_manual_axis_and_time': bypass['manual_approval'] == approvals_before,
        }
        report['controls'].append({'name': 'bypass_face_assignment_materialization', 'case_id': 'x',
            'fault': 'Keep test manual approval, return uncorrected header/raw copies, then execute production Parser and PoseOptimizer again.',
            'expected_failure': {'failed_checks': ['pose_recovery'], 'valid_frames': 100,
                                 'rotation_error_deg': 180., 'rotation_tolerance_deg': .1},
            'mutant': bypass, 'checks': bypass_checks,
            'status': 'pass' if all(bypass_checks.values()) else 'fail'})
        after = {case: _file_hashes(context['root']) for case, context in contexts.items()}
        reports_after = {case: _baseline_report_hash(context) for case, context in contexts.items()}
        report['files_after_sha256'] = after
        report['baseline_reports_after_sha256'] = reports_after
        report['checks'] = {'all_controls_executed': len(report['controls']) == 2,
                            'both_baselines_pass': all(b['status'] == 'pass' for b in report['baselines'].values()),
                            'both_expected_failures_detected': all(c['status'] == 'pass' for c in report['controls']),
                            'fixture_files_unchanged': before == after,
                            'normal_reports_unchanged': reports_before == reports_after}
        report['status'] = 'pass' if all(report['checks'].values()) else 'fail'
        _write_report(output / 'negative_controls.json', report)
        return report
    except Exception as error:
        report['status'] = 'fail'
        report['checks']['execution_completed'] = False
        report['error'] = {'type': type(error).__name__, 'message': str(error)}
        try:
            _write_report(output / 'negative_controls.json', report)
        except Exception as reporting_error:
            error.add_note(f'Could not preserve negative-control report: {reporting_error}')
        raise
