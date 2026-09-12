"""Report and failure contracts; the CLI integration job runs real controls once."""
import json
import hashlib
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest

from src.simulation import validate_marker_fixtures as validation
from src.simulation import marker_validation_controls as controls
from src.simulation.marker_fixtures import load_profile, validate_profile, virtual_profile_32
from src.config.data_columns import TimeCols


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
