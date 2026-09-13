"""Report and failure contracts; the CLI integration job runs real controls once."""
import json
import hashlib
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
import xml.etree.ElementTree as ET

import numpy as np
import pandas as pd
import pytest

from src.simulation import validate_marker_fixtures as validation
from src.simulation import marker_validation_controls as controls
from src.simulation.marker_fixtures import load_profile, validate_profile, virtual_profile_32
from src.config.data_columns import TimeCols


def _evaluation_context(case):
    """Literal evaluation inputs only; no extra simulator or optimizer run."""
    frames = np.arange(100)
    angles = frames * (np.pi / 99 if case == 'genuine_rotation' else .001)
    matrices = np.zeros((100, 3, 3))
    matrices[:, 0, 0] = matrices[:, 1, 1] = np.cos(angles)
    matrices[:, 0, 1] = -np.sin(angles)
    matrices[:, 1, 0] = np.sin(angles)
    matrices[:, 2, 2] = 1.
    truth = pd.DataFrame({'time_s': frames * .008,
        'body_x_mm': frames.astype(float), 'body_y_mm': frames * 2., 'body_z_mm': -frames.astype(float)})
    for i in range(3):
        for j in range(3):
            truth[f'r{i}{j}'] = matrices[:, i, j]
    pose = pd.DataFrame(np.column_stack((frames, 2 * frames, -frames,
                         np.zeros(100), np.zeros(100), angles)), columns=validation.POSE_COLUMNS)
    pose[validation.SourceCols.POSE] = 'Optimized'
    if case == 'noise':
        pose[validation.POSE_COLUMNS[0]] += .01
    if case == 'freeze_reconnect':
        pose.loc[15:19, list(validation.POSE_COLUMNS)] = [14., 28., -14., 0., 0., .014]
        pose.loc[20:21, list(validation.POSE_COLUMNS[:3])] = [[27., 37., -16.], [28., 39., -17.]]
    report = validation._base_report(Path('.'))
    report['expected'] = {}
    return {'manifest': {'case_id': case, 'events': [], 'parameters': {'scenario': 'free_fall'},
                        'pose_tolerances': {'position_mm': .1, 'rotation_deg': .1}},
            'candidates': [], 'decisions': [], 'truth': truth, 'pose': pose,
            'fixed': pose.copy(deep=True), 'report': report}


@pytest.mark.parametrize('case, damage, failed_check', [
    ('noise', 'position', 'noisy_raw_pose_within_tolerance'),
    ('noise', 'invalid_frame', 'noisy_raw_pose_within_tolerance'),
    ('genuine_rotation', 'candidate', 'genuine_rotation_no_candidates'),
    ('genuine_rotation', 'approval', 'genuine_rotation_preserved_without_correction'),
    ('freeze_reconnect', 'normal', 'unaffected_pose_matches_observation_model'),
    ('freeze_reconnect', 'frozen', 'frozen_pose_matches_observation_model'),
    ('freeze_reconnect', 'offset', 'reconnect_offset_pose_matches_observation_model'),
    ('freeze_reconnect', 'return', 'return_frame_22_pose_matches_observation_model'),
])
def test_existing_pose_evaluation_rejects_wrong_noise_rotation_or_reconnect_semantics(case, damage, failed_check):
    context = _evaluation_context(case)
    baseline = validation._evaluate(context)
    assert baseline['status'] == 'pass'
    if case == 'freeze_reconnect':
        assert baseline['observed_pose_model']['expected_valid_frames'] == {
            'unaffected': 93, 'frozen': 5, 'reconnect_offset': 2, 'return_frame_22': 1}
    changed = deepcopy(context)
    if damage == 'candidate':
        changed['candidates'] = [SimpleNamespace(boundary_time_sec=.240, trigger='test',
            recommendation_axis=None, hypotheses=[])]
    elif damage == 'approval':
        changed['decisions'] = ['unexpected test-only approval']
    elif damage == 'invalid_frame':
        changed['pose'].loc[0, validation.SourceCols.POSE] = 'OptimizationFailed'
    else:
        row = {'position': 0, 'normal': 0, 'frozen': 17, 'offset': 20, 'return': 22}[damage]
        changed['pose'].loc[row, validation.POSE_COLUMNS[0]] += 1.
    result = validation._evaluate(changed)
    assert result['status'] == 'fail' and result['checks'][failed_check] is False
    _assert_boolean_checks(result)


def test_genuine_collision_does_not_require_zero_candidates():
    context = _evaluation_context('genuine_rotation')
    context['manifest']['parameters'].update(scenario='face', recorded_contact_force_n=[0., 1.] + [0.] * 98)
    context['candidates'] = [SimpleNamespace(boundary_time_sec=.240, trigger='contact',
        recommendation_axis=None, hypotheses=[])]
    result = validation._evaluate(context)
    assert result['status'] == 'pass'
    assert 'genuine_rotation_no_candidates' not in result['checks']


@pytest.mark.parametrize('damage', ['wrong_axis', 'missing', 'extra'])
def test_conditional_recommendation_oracle_rejects_wrong_missing_or_extra_axis(damage):
    context = _evaluation_context('healthy')
    context['manifest']['case_id'] = 'recommendation_contract'
    context['manifest']['events'] = [dict(kind='solver_pose_half_turn', time_s=.24, axis='X')]
    candidate = SimpleNamespace(boundary_time_sec=.24, trigger='pose_jump',
                                recommendation_axis='X', hypotheses=[])
    context['candidates'] = [candidate]
    assert validation._evaluate(context)['checks']['conditional_recommendations_match_oracle']
    if damage == 'wrong_axis':
        candidate.recommendation_axis = 'Y'
    elif damage == 'missing':
        context['candidates'] = []
    else:
        context['candidates'].append(SimpleNamespace(boundary_time_sec=.40, trigger='gap',
                                   recommendation_axis='X', hypotheses=[]))
    result = validation._evaluate(context)
    assert not result['checks']['conditional_recommendations_match_oracle']
    assert result['status'] == 'fail'


def _junit_fixture(path, rows):
    suite = ET.Element('testsuite')
    for module, name, level, status in rows:
        case = ET.SubElement(suite, 'testcase', classname=module, name=name)
        if level is not None:
            properties = ET.SubElement(case, 'properties')
            ET.SubElement(properties, 'property', name='evidence_level', value=level)
        if status != 'passed':
            ET.SubElement(case, {'failed': 'failure', 'error': 'error', 'skipped': 'skipped'}[status])
    ET.ElementTree(suite).write(path, encoding='utf-8', xml_declaration=True)


PUBLIC_JUNIT_CASES = [
    ('tests.test_marker_validation', 'test_report_contract', 'unit_contract', 'passed'),
    ('tests.test_corruption_export', 'test_physical_visibility_and_id_routing_preserve_solved_analysis_and_truth',
     'synthetic_integration', 'passed'),
]


def test_junit_levels_summarize_existing_results_and_keep_real_accuracy_pending(tmp_path, request):
    from src.simulation.public_validation_summary import main
    assert ('evidence_level', 'unit_contract') in request.node.user_properties
    xml, output = tmp_path / 'results.xml', tmp_path / 'summary.json'
    _junit_fixture(xml, PUBLIC_JUNIT_CASES)
    before = xml.read_bytes()
    with pytest.raises(SystemExit) as stopped:
        main(['--junit', str(xml), '--output', str(output), '--public-required'])
    assert stopped.value.code == 0 and xml.read_bytes() == before
    summary = _read(output)
    assert summary['status'] == 'pass'
    assert summary['levels']['unit_contract']['counts']['passed'] == 1
    assert summary['levels']['synthetic_integration']['counts']['passed'] == 1
    assert summary['levels']['synthetic_integration']['testcases'][0]['name'].endswith(PUBLIC_JUNIT_CASES[1][1])
    assert summary['levels']['public_external']['level'] == 3
    assert summary['levels']['public_external']['status'] == 'optional-manual'
    assert summary['levels']['internal_real']['level'] == 4
    assert summary['levels']['internal_real']['status'] == 'pending'
    assert summary['levels']['internal_real']['issue'] == '#104'
    assert summary['levels']['internal_real']['release_gate_satisfied'] is False


@pytest.mark.parametrize('alias', ['same_path', 'hard_link'])
def test_junit_summary_cannot_overwrite_its_input(tmp_path, capsys, alias):
    from src.simulation.public_validation_summary import main
    source = tmp_path / 'results.xml'
    _junit_fixture(source, PUBLIC_JUNIT_CASES)
    before = source.read_bytes()
    target = source
    if alias == 'hard_link':
        target = tmp_path / 'summary.json'
        target.hardlink_to(source)
    with pytest.raises(SystemExit) as stopped:
        main(['--junit', str(source), '--output', str(target), '--public-required'])
    assert stopped.value.code == 2
    assert 'must not overwrite the source JUnit' in capsys.readouterr().err
    assert source.read_bytes() == before and target.read_bytes() == before


@pytest.mark.parametrize('problem', ['unlabeled', 'unknown', 'private', 'external', 'misclassified',
                                    'skipped', 'empty', 'missing_level1', 'missing_level2', 'internal_real', 'public_external'])
def test_public_junit_rejects_missing_or_misclassified_evidence(tmp_path, problem):
    from src.simulation.public_validation_summary import main
    rows = list(PUBLIC_JUNIT_CASES)
    if problem in ('unlabeled', 'unknown', 'private', 'external', 'misclassified'):
        row = rows[0]
        level = None if problem == 'unlabeled' else 'synthetic_integration' if problem == 'misclassified' else problem
        rows[0] = (row[0], row[1], level, row[3])
    elif problem == 'skipped':
        rows[1] = (*rows[1][:3], 'skipped')
    elif problem == 'empty':
        rows = []
    elif problem == 'missing_level1':
        rows = rows[1:]
    elif problem == 'missing_level2':
        rows = rows[:1]
    elif problem == 'internal_real':
        rows.append(('tests.test_real_data_flow.TestRealDataFlow', 'test_capture', 'internal_real', 'passed'))
    else:
        rows.append(('tests.test_external_capture', 'test_capture', 'public_external', 'passed'))
    xml, output = tmp_path / 'results.xml', tmp_path / 'summary.json'
    _junit_fixture(xml, rows)
    with pytest.raises(SystemExit) as stopped:
        main(['--junit', str(xml), '--output', str(output), '--public-required'])
    assert stopped.value.code == 1
    assert _read(output)['status'] == 'fail' and _read(output)['errors']


def test_internal_and_gui_only_test_classification_is_explicit():
    from src.simulation.public_validation_summary import evidence_level
    assert evidence_level('tests/test_real_drop_posture_physics.py', 'test_values') == 'internal_real'
    assert evidence_level('tests/test_real_data_flow.py', 'test_values') == 'internal_real'
    assert evidence_level('tests/test_drop_posture_post_processor.py',
        'test_real_contact_slice_theta_angles_are_physically_consistent_around_t1') == 'internal_real'
    assert evidence_level('tests/test_drop_posture_post_processor.py', 'test_flat_drop_has_zero_angles_and_zero_reference_face_height_spread') == 'unit_contract'
    assert evidence_level('tests/test_simulation_contact_gui.py', 'test_contact_damping_controls_in_production_window') == 'unit_contract'


def _read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def _assert_boolean_checks(value):
    if isinstance(value, dict):
        if 'checks' in value:
            assert isinstance(value['checks'], dict)
            assert all(type(flag) is bool for flag in value['checks'].values())
        for nested in value.values():
            _assert_boolean_checks(nested)
    elif isinstance(value, list):
        for nested in value:
            _assert_boolean_checks(nested)


def test_api_report_keeps_schema_identity_unknown_until_read_and_serializes_dict(tmp_path):
    report = validation._base_report(tmp_path)
    assert report['report_schema_version'] == 1
    assert report['fixture_schema_version'] is None
    assert report['invocation'] == {'kind': 'api',
        'call': 'src.simulation.validate_marker_fixtures.validate_case',
        'arguments': {'root': str(tmp_path.resolve())}}
    assert report['seed'] is None and report['expected'] is None
    assert report['oracle_rationale']['pose_origin'].startswith('Independent simulator body origin')
    validation._write_report(tmp_path / 'validation.json', report)
    validation._write_report(tmp_path / 'validation_summary.json', [report])
    assert _read(tmp_path / 'validation.json') == report
    assert _read(tmp_path / 'validation_summary.json') == [report]
    _assert_boolean_checks(report)


@pytest.mark.parametrize('control_status, exit_code', [('pass', 0), ('fail', 1)])
def test_cli_reports_controls_status_and_path_without_repeating_integration(tmp_path, monkeypatch, capsys,
                                                                          control_status, exit_code):
    # Stub completed runs only to test CLI plumbing. Actual numerical controls
    # run in the separate CLI integration command, not a second time in pytest.
    result = validation._base_report(tmp_path / 'healthy')
    result.update(status='pass', case_id='healthy', checks={'execution_completed': True})
    monkeypatch.setattr(validation, 'write_case', lambda *args, **kwargs: tmp_path / 'healthy')
    monkeypatch.setattr(validation, '_validate_run', lambda *args, **kwargs: (result, {'report': result}))
    monkeypatch.setattr(controls, 'run_negative_controls',
                        lambda *args, **kwargs: {'status': control_status})
    with pytest.raises(SystemExit) as stopped:
        validation.main(['--output', str(tmp_path), '--case', 'healthy', '--negative-controls'])
    assert stopped.value.code == exit_code
    assert _read(tmp_path / 'validation_summary.json') == [result]
    console_rows = [json.loads(line) for line in capsys.readouterr().out.splitlines() if line.startswith('{')]
    assert console_rows[-1] == {'negative_controls': control_status,
                               'report': str(tmp_path / 'negative_controls.json')}


def test_wrong_explicit_profile_still_raises_value_error_with_failure_report(tmp_path, monkeypatch):
    # No pose is fitted: the actual declared header/profile contract must reject
    # the mismatch before production parsing, and retain readable failure data.
    header = {'artifact_metadata': {'MarkerLayoutHash': validate_profile(load_profile())}}
    raw = pd.DataFrame({TimeCols.TIME: [0., .008], TimeCols.FRAME: [0, 1]})
    monkeypatch.setattr(validation.DataLoader, 'load_csv', lambda *args: (header, raw))
    (tmp_path / 'observed.synthetic.json').write_text(json.dumps({
        'schema_version': '1', 'seed': 74082, 'case_id': 'healthy',
        'source_kind': 'mujoco_synthetic', 'evidence_level': 'synthetic_integration',
        'pose_tolerances': {'position_mm': .1, 'rotation_deg': .1}}), encoding='utf-8')
    with pytest.raises(ValueError, match='profile does not match'):
        validation.validate_case(tmp_path, profile=virtual_profile_32())
    report = _read(tmp_path / 'validation.json')
    assert report['status'] == 'fail'
    assert report['error']['type'] == 'ValueError'
    assert report['invocation']['kind'] == 'api'
    assert report['seed'] == 74082  # Recovered from a readable manifest after failure.
    assert report['fixture_schema_version'] == '1'
    assert report['source_kind'] == 'mujoco_synthetic'
    assert report['evidence_level'] == 'synthetic_integration'
    assert report['tolerances'] == {'position_mm': .1, 'rotation_deg': .1}
    assert report['metadata_recovery'].startswith('Read from fixture manifest after analysis failure')


def test_unreadable_manifest_does_not_invent_seed_or_expected_values(tmp_path, monkeypatch):
    error = RuntimeError('Observed input could not be read')
    def fail_load(*args, **kwargs):
        raise error
    monkeypatch.setattr(validation.DataLoader, 'load_csv', fail_load)
    (tmp_path / 'observed.synthetic.json').write_text('{broken', encoding='utf-8')
    with pytest.raises(RuntimeError) as failure:
        validation.validate_case(tmp_path)
    assert failure.value is error
    report = _read(tmp_path / 'validation.json')
    assert report['status'] == 'fail' and report['checks']['execution_completed'] is False
    assert report['seed'] is None and report['expected'] is None and report['fixture_schema_version'] is None
    assert report['invocation']['kind'] == 'api'
    assert report['error'] == {'type': 'RuntimeError', 'message': 'Observed input could not be read'}


def test_generation_error_cannot_reuse_an_old_pass_and_preserves_it(tmp_path, monkeypatch, capsys):
    case_root = tmp_path / 'healthy'
    case_root.mkdir()
    previous = {'case_id': 'healthy', 'seed': 999, 'status': 'pass', 'checks': {'pose_recovery': True}}
    old_path = case_root / 'validation.json'
    old_path.write_text(json.dumps(previous), encoding='utf-8')
    old_bytes = old_path.read_bytes()
    def fail_generation(*args, **kwargs):
        raise RuntimeError('Synthetic input generation failed')
    monkeypatch.setattr(validation, 'write_case', fail_generation)
    with pytest.raises(SystemExit) as stopped:
        validation.main(['--output', str(tmp_path), '--case', 'healthy', '--seed', '123'])
    assert stopped.value.code == 1
    summary = _read(tmp_path / 'validation_summary.json')
    assert isinstance(summary, list) and len(summary) == 1
    assert summary[0]['status'] == 'fail' and summary[0]['seed'] is None
    assert summary[0]['requested_seed'] == 123 and summary[0]['requested_case'] == 'healthy'
    assert summary[0]['expected'] is None
    assert summary[0] == _read(case_root / 'validation_failure.json')
    assert old_path.read_bytes() == old_bytes
    console = capsys.readouterr().out
    assert 'validation_failure.json' in console and 'Synthetic input generation failed' in console


def test_arbitrary_control_exception_is_failure_not_a_successful_negative_control(tmp_path, monkeypatch):
    error = FileNotFoundError('Required fixture is unavailable')
    def fail_generation(*args, **kwargs):
        raise error
    monkeypatch.setattr(controls, 'write_case', fail_generation)
    with pytest.raises(FileNotFoundError) as failure:
        controls.run_negative_controls(tmp_path)
    assert failure.value is error
    report = _read(tmp_path / 'negative_controls.json')
    assert report['status'] == 'fail'
    assert report['controls'] == []
    assert report['checks']['all_controls_executed'] is False
    assert report['checks']['execution_completed'] is False


def test_negative_controls_reject_custom_scope_before_generating_files(tmp_path):
    with pytest.raises(SystemExit) as stopped:
        validation.main(['--output', str(tmp_path), '--case', 'healthy', '--example', '32', '--negative-controls'])
    assert stopped.value.code == 2
    assert list(tmp_path.iterdir()) == []


def test_only_the_exact_expected_failed_check_counts_as_detected_fault():
    assert controls._expected_failure({'status': 'fail', 'checks': {'execution_completed': True, 'pose_recovery': False}})
    assert not controls._expected_failure({'status': 'pass', 'checks': {'pose_recovery': True}})
    assert not controls._expected_failure({'status': 'fail', 'checks': {'execution_completed': False, 'pose_recovery': False}})


def _stub_reporting_case(root, monkeypatch, *, change_file=None):
    """Isolate reporting from numerical analysis with explicit producer doubles."""
    for name in validation.FIXTURE_FILES[:-1]:
        (root / name).write_text('time_s\n0\n0.008\n', encoding='utf-8')
    profile = load_profile()
    manifest = {'schema_version': '1', 'case_id': 'healthy', 'seed': 74082,
        'source_kind': 'mujoco_synthetic', 'evidence_level': 'synthetic_integration',
        'profile': profile, 'layout_hash': validate_profile(profile), 'events': [],
        'parameters': {'scenario': 'free_fall'},
        'pose_tolerances': {'position_mm': .1, 'rotation_deg': .1},
        'files': {name: hashlib.sha256((root / name).read_bytes()).hexdigest()
                  for name in validation.FIXTURE_FILES[:-1]}}
    (root / 'observed.synthetic.json').write_text(json.dumps(manifest), encoding='utf-8')
    raw = pd.DataFrame({TimeCols.TIME: [0., .008], TimeCols.FRAME: [0, 1]})
    monkeypatch.setattr(validation.DataLoader, 'load_csv', lambda *args: ({}, raw))
    monkeypatch.setattr(validation.Parser, 'process', lambda *args: raw)
    def produce(*args):
        if change_file is not None:
            path = root / change_file
            path.write_bytes(path.read_bytes() + b'\n')
        return raw
    monkeypatch.setattr(validation, '_optimizer', lambda *args: SimpleNamespace(process=produce))
    monkeypatch.setattr(validation.FaceAssignmentAnalyzer, 'detect', lambda *args: [])
    def evaluated(context):
        result = dict(context['report'])
        result.update(status='pass', checks={'execution_completed': True, 'pose_recovery': True})
        return result
    monkeypatch.setattr(validation, '_evaluate', evaluated)


@pytest.mark.parametrize('changed_file', validation.FIXTURE_FILES)
def test_file_change_during_production_cannot_leave_a_passing_report(tmp_path, monkeypatch, changed_file):
    _stub_reporting_case(tmp_path, monkeypatch, change_file=changed_file)
    before = {name: hashlib.sha256((tmp_path / name).read_bytes()).hexdigest()
              for name in validation.FIXTURE_FILES}
    with pytest.raises(ValueError, match='changed during validation'):
        validation.validate_case(tmp_path)
    report = _read(tmp_path / 'validation.json')
    assert report['status'] == 'fail'
    assert report['checks']['fixture_files_unchanged'] is False
    assert report['files_sha256'] == before
    assert report['files_after_sha256'] == {
        name: hashlib.sha256((tmp_path / name).read_bytes()).hexdigest()
        for name in validation.FIXTURE_FILES}
    assert report['files_after_sha256'][changed_file] != before[changed_file]


@pytest.mark.parametrize('invalid_number', ['NaN', 'Infinity', '-Infinity', '1e999'])
@pytest.mark.parametrize('fail_production', [False, True])
def test_nonfinite_manifest_preserves_current_failure_and_original_error(tmp_path, monkeypatch,
                                                                       invalid_number, fail_production):
    _stub_reporting_case(tmp_path, monkeypatch)
    error = RuntimeError('Production stopped before metadata was read')
    if fail_production:
        def fail_load(*args):
            raise error
        monkeypatch.setattr(validation.DataLoader, 'load_csv', fail_load)
    (tmp_path / 'observed.synthetic.json').write_text(
        '{"schema_version":"1","seed":' + invalid_number + '}', encoding='utf-8')
    (tmp_path / 'validation.json').write_text('{"status":"pass"}', encoding='utf-8')
    with pytest.raises(RuntimeError if fail_production else ValueError) as failure:
        validation.validate_case(tmp_path)
    if fail_production:
        assert failure.value is error
    report = _read(tmp_path / 'validation.json')
    assert report['status'] == 'fail' and report['checks']['execution_completed'] is False
    assert report['seed'] is None and report['expected'] is None and report['fixture_schema_version'] is None
    assert report['metadata_recovery_error']['type'] == 'ValueError'
    assert report['error']['type'] == ('RuntimeError' if fail_production else 'ValueError')
    assert report['error']['message'] == str(failure.value)
    json.dumps(report, allow_nan=False)
