"""Production MainApp workflow driven by Qt events, without pipeline mocks."""
import time
import hashlib
import json
import tempfile
from dataclasses import asdict, replace
from pathlib import Path
import numpy as np
import pandas as pd
import pytest
from scipy.spatial.transform import Rotation
from PySide6.QtCore import Qt, QTimer
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QFileDialog, QDialogButtonBox, QLineEdit
from marker_face_fixtures import DIMS, raw_bundle, write_raw, custom_public_profile
from src.analysis.app.main_window import MainApp
from src.analysis.ui.dialog_marker_flip_review import MarkerFlipReviewDialog
from src.analysis.pipeline.data_loader import DataLoader
from src.analysis.pipeline.artifact_io import read_corrected_source_metadata, read_slice_metadata
from src.config import config_app


def _input_hashes(protected):
    hashes = {}
    for path in protected:
        try:
            hashes[path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
        except FileNotFoundError:
            hashes[path.name] = None
    return hashes


def _preserve_scalar_evidence(report, evidence, protected, errors, logs):
    report['input_sha256_after'] = _input_hashes(protected)
    report['missing_input_files'] = [name for name, value in report['input_sha256_after'].items()
                                     if value is None]
    unchanged = (not report['missing_input_files']
                 and report['input_sha256_before'] == report['input_sha256_after'])
    report['checks']['source_truth_manifest_unchanged'] = unchanged
    if not unchanged:
        report['status'] = 'fail'
    report['workflow_errors'] = errors
    report_path = evidence / 'public_impact_metrics.json'
    report_path.write_text(json.dumps(report, indent=2, allow_nan=False), encoding='utf-8')
    (evidence / 'workflow.log').write_text('\n'.join(logs), encoding='utf-8')
    print(f'Public scalar evidence: {report_path}')
    assert unchanged, f'Protected input changed or disappeared; failure evidence: {report_path}'


@pytest.mark.parametrize('damage', ['changed', 'missing'])
def test_public_scalar_finalizer_preserves_evidence_and_fails_on_input_damage(tmp_path, damage):
    protected = [tmp_path / name for name in
                 ('observed.csv', 'truth_pose.csv', 'truth_markers.csv', 'observed.synthetic.json')]
    for path in protected:
        path.write_text('original ' + path.name, encoding='utf-8')
    before = _input_hashes(protected)
    report = {'status': 'pass', 'checks': {}, 'input_sha256_before': before}
    damaged = protected[0]
    if damage == 'changed':
        damaged.write_text('changed after successful processing', encoding='utf-8')
    else:
        damaged.unlink()
    with pytest.raises(AssertionError, match='Protected input changed or disappeared'):
        _preserve_scalar_evidence(report, tmp_path, protected, [], ['finished processing'])
    saved = json.loads((tmp_path / 'public_impact_metrics.json').read_text(encoding='utf-8'))
    assert saved['status'] == 'fail'
    assert saved['checks']['source_truth_manifest_unchanged'] is False
    assert saved['input_sha256_before'] == before
    assert saved['missing_input_files'] == (['observed.csv'] if damage == 'missing' else [])
    assert saved['input_sha256_after']['observed.csv'] == (
        None if damage == 'missing' else hashlib.sha256(damaged.read_bytes()).hexdigest())
    for path in protected[1:]:
        assert saved['input_sha256_after'][path.name] == before[path.name]


def _record_public_impact_metrics(reopened, truth, report):
    """Independent six-sample derivative oracle; never pass truth to production."""
    from src.analysis.compare.impact_metrics import calculate_impact_metrics
    from src.utils.artifact_metadata import read_identity

    result = calculate_impact_metrics(reopened)
    identity = read_identity(reopened)
    settings = json.loads(identity.values['ProcessingSettingsJson'])
    impact = report['impact'] = {
        'actual': asdict(result), 'processing_settings': settings,
        'expected': {'evaluation_time_s': .136, 'first_impact_time_s': .144,
                     'sample_times_s': [.096, .104, .112, .120, .128, .136],
                     'velocity_xyz_m_s': [.025, -1.34397, .015],
                     'horizontal_speed_m_s': .0291547594742, 'angular_speed_rad_s': 0.,
                     'equivalent_height_mm': None, 'first_contact': '{C5,C6,C7,C8}'},
        'tolerances': {'position_mm': .1, 'rotation_deg': .1,
                       'velocity_m_s': .0223214285714, 'angular_speed_rad_s': .522040445909,
                       'time_representation_s': 1e-10, 'same_pose_arithmetic': 1e-9},
        'oracle_rationale': (
            'Six equally spaced 8 ms samples use endpoint quadratic derivative weights '
            '(85,-49,-108,-92,-1,165)/2.24 per second. Their L1 norm is '
            '223.214285714/s. The existing 0.1 mm pose bound gives 0.0223214285714 m/s; '
            'the existing 0.1 degree constant-orientation bound gives a conservative '
            '0.522040445909 rad/s. Same saved pose is also independently differentiated. '
            'The 2 ms semi-implicit generator gives vy=-1.34397 m/s, not -g*t; '
            'saved central-difference Velocity columns are not an oracle.'),
    }
    checks = report['checks']
    checks['source_and_type_preserved'] = (
        identity.source_kind == 'mujoco_synthetic' and identity.values['IstaType'] == 'not_applicable')
    checks['raw_pose_processing'] = (
        settings['single_pass']['marker_smoothing']['enabled'] is False
        and settings['result_resampling']['enabled'] is False)
    checks['no_trial_identity_added'] = ('Info', 'SceneReview', 'Json') not in reopened.columns
    checks['six_sample_evaluation'] = bool(
        result.evidence.get('sample_count') == 6
        and all(np.isclose(result.evidence.get(key, np.nan), expected, rtol=0, atol=1e-10)
                for key, expected in (('evaluation_time_s', .136), ('first_impact_time_s', .144),
                                      ('window_start_s', .096), ('window_end_s', .136))))
    actual_times = reopened[('Info', 'Time', 'Time')].iloc[12:18].to_numpy(float)
    impact['actual_sample_times_s'] = actual_times.tolist()
    np.testing.assert_allclose(actual_times, impact['expected']['sample_times_s'], rtol=0, atol=1e-10)
    np.testing.assert_allclose(truth.time_s.iloc[12:18], actual_times, rtol=0, atol=1e-10)
    weights = np.array([85., -49., -108., -92., -1., 165.]) / 2.24
    truth_velocity = weights @ truth[[f'body_{axis}_mm' for axis in 'xyz']].iloc[12:18].to_numpy() / 1000.
    saved_velocity = weights @ reopened[[('Position', 'CoM', 'P_T' + axis)
                                         for axis in 'XYZ']].iloc[12:18].to_numpy(float) / 1000.
    matrices = Rotation.from_rotvec(reopened[[('Position', 'CoM', 'P_R' + axis)
                                               for axis in 'XYZ']].iloc[12:18].to_numpy(float)).as_matrix()
    world_logs = Rotation.from_matrix(matrices @ matrices[-1].T).as_rotvec()
    saved_omega = weights @ world_logs
    impact['independent_truth_velocity_xyz_m_s'] = truth_velocity.tolist()
    impact['independent_saved_pose_velocity_xyz_m_s'] = saved_velocity.tolist()
    impact['independent_saved_pose_omega_world_rad_s'] = saved_omega.tolist()
    checks['truth_derivative_matches_prescribed_oracle'] = bool(np.allclose(
        truth_velocity, impact['expected']['velocity_xyz_m_s'], rtol=0, atol=1e-9))
    expected = {'vertical_velocity': -1.34397, 'horizontal_speed': .0291547594742,
                'angular_speed': 0.}
    independent = {'vertical_velocity': saved_velocity[1],
                   'horizontal_speed': np.hypot(saved_velocity[0], saved_velocity[2]),
                   'angular_speed': np.linalg.norm(saved_omega)}
    for key in expected:
        actual = result.metrics[key]
        bound = .522040445909 if key == 'angular_speed' else .0223214285714
        checks[key + '_truth_bound'] = bool(
            actual.value is not None and np.isfinite(actual.value)
            and abs(actual.value - expected[key]) <= bound and actual.reason == '')
        checks[key + '_saved_pose_time_units'] = bool(
            actual.value is not None and np.isclose(actual.value, independent[key], rtol=0, atol=1e-9))
    checks['height_requires_reviewed_type_g_and_com'] = (
        result.metrics['equivalent_height'].value is None
        and result.metrics['equivalent_height'].reason ==
        'Reviewed Type G free fall and explicit COM registration are required')
    checks['first_contact_diagnostic'] = result.metrics['first_contact'].value == '{C5,C6,C7,C8}'


@pytest.mark.parametrize('source_kind', ['handcrafted', 'mujoco', 'custom_mujoco', 'collision_face', 'continuity_layout'])
def test_production_mainapp_face_review_save_and_process(tmp_path, monkeypatch, source_kind, request):
    # Production UI changes runtime geometry; isolate it from following tests.
    monkeypatch.setattr(config_app, 'BOX_DIMS', np.array(config_app.BOX_DIMS, copy=True))
    monkeypatch.setattr(config_app, 'LOCAL_BOX_CORNERS', np.array(config_app.LOCAL_BOX_CORNERS, copy=True))
    app = QApplication.instance() or QApplication([])
    app.setAttribute(Qt.ApplicationAttribute.AA_DontUseNativeDialogs, True)
    window = MainApp()
    window.show()
    QTest.qWait(100)
    raw_widget = window.original_widget
    h, raw, truth = raw_bundle(samples=100, boundary=30)
    source = tmp_path / 'asymmetric.csv'
    corrected = tmp_path / 'asymmetric.corrected.csv'
    sliced = tmp_path / 'scene.slice'
    processed = tmp_path / 'scene.proc'
    write_raw(source, h, raw)
    boundary_time = .3
    mujoco_truth = None
    dims = DIMS
    if source_kind == 'collision_face':
        parent = Path('tmp/issue84_public_metrics')
        parent.mkdir(parents=True, exist_ok=True)
        evidence = Path(tempfile.mkdtemp(prefix='collision_face-', dir=parent)).resolve()
        corrected, sliced, processed = (evidence / name for name in
                                       ('asymmetric.corrected.csv', 'scene.slice', 'scene.proc'))
    else:
        evidence = Path('tmp/issue74_gui') / source_kind
        evidence.mkdir(parents=True, exist_ok=True)
    if source_kind in ('mujoco', 'custom_mujoco', 'collision_face', 'continuity_layout'):
        from src.simulation.marker_fixtures import write_case, load_profile
        profile = None
        if source_kind == 'custom_mujoco':
            profile_path = tmp_path / 'custom_profile.json'
            profile_path.write_text(json.dumps(custom_public_profile()), encoding='utf-8')
            profile = load_profile(profile_path)
            dims = tuple(profile['box_dims_mm'])
        if source_kind == 'collision_face':
            from src.simulation.marker_fixtures import virtual_profile_32
            profile = virtual_profile_32()
            dims = tuple(profile['box_dims_mm'])
        if source_kind == 'continuity_layout':
            from src.simulation.continuity_fixtures import read_spec
            profile = read_spec()['profile']
            dims = tuple(profile['box_dims_mm'])
        generated = write_case((evidence if source_kind == 'collision_face' else tmp_path) / 'independent', 'x', profile=profile,
                               motion='face' if source_kind == 'collision_face' else 'free_fall')
        source = generated / 'observed.csv'
        h, raw = DataLoader().load_csv(str(source))
        mujoco_truth = pd.read_csv(generated / 'truth_pose.csv')
        boundary_time = float(mujoco_truth.time_s.iloc[65 if source_kind == 'collision_face' else 30])
    original_bytes = source.read_bytes()
    errors = []
    if source_kind == 'collision_face':
        manifest = json.loads((generated / 'observed.synthetic.json').read_text(encoding='utf-8'))
        protected = [generated / name for name in
                     ('observed.csv', 'truth_pose.csv', 'truth_markers.csv', 'observed.synthetic.json')]
        scalar_report = {
            'report_version': 1, 'status': 'fail', 'stage': 'actual_mainapp_face_review_and_raw_processing',
            'source_kind': manifest['source_kind'], 'evidence_level': manifest['evidence_level'],
            'fixture_schema_version': manifest['schema_version'], 'generator_version': manifest['generator_version'],
            'seed': manifest['seed'], 'case_id': manifest['case_id'],
            'profile_id': manifest['profile']['profile_id'], 'layout_hash': manifest['layout_hash'],
            'box_dims_mm': list(dims), 'source_path': str(source),
            'time_range_s': [float(raw.iloc[0, 1]), float(raw.iloc[-1, 1])],
            'frame_range': [int(raw.iloc[0, 0]), int(raw.iloc[-1, 0])], 'events': manifest['events'],
            'invocation': {'kind': 'pytest', 'node_id': request.node.nodeid},
            'operator_decision': {'axis': 'X', 'time_s': .520, 'approved': True,
                                  'basis': 'test-only manual approval; not automatic recommendation'},
            'input_sha256_before': _input_hashes(protected), 'checks': {},
        }
        request.addfinalizer(lambda: _preserve_scalar_evidence(
            scalar_report, evidence, protected, errors,
            [raw_widget.log_output.toPlainText(), window.processing_widget.log_output.toPlainText()]))

    def choose(path):
        def accept_file():
            dialog = app.activeModalWidget()
            if not isinstance(dialog, QFileDialog):
                errors.append('Expected actual QFileDialog')
                return
            dialog.selectFile(str(path))
            dialog.findChild(QLineEdit, 'fileNameEdit').setText(str(path))
            # Directory loading can reset the filename during the first event.
            def finish():
                dialog.findChild(QLineEdit, 'fileNameEdit').setText(str(path))
                dialog.accept()
            QTimer.singleShot(250, finish)
        QTimer.singleShot(250, accept_file)

    def wait_until(predicate, timeout=120):
        deadline = time.monotonic() + timeout
        while not predicate() and time.monotonic() < deadline:
            app.processEvents()
            # Release the Python GIL so the actual QThread optimizer can run.
            time.sleep(.01)
        assert predicate(), 'Timed out waiting for actual production workflow'
        assert not errors, errors

    choose(source)
    QTest.mouseClick(raw_widget.load_csv_button, Qt.MouseButton.LeftButton)
    assert raw_widget.raw_data is not None
    for edit, value in zip((raw_widget.le_box_l, raw_widget.le_box_w, raw_widget.le_box_h), dims):
        edit.setText(str(value))
    raw_widget.marker_review_section.setExpanded(True)
    QTest.mouseClick(raw_widget.confirm_review_dimensions, Qt.MouseButton.LeftButton)
    window.grab().save(str(evidence / 'before.png'))

    # Timer operates the real modal when the real background review completes.
    reviewed = []
    timer = QTimer()
    def approve():
        dialog = app.activeModalWidget()
        if not isinstance(dialog, MarkerFlipReviewDialog):
            return
        timer.stop()
        try:
            assert all(not c.isChecked() for c in dialog._approval_checkboxes)
            rows = [i for i, c in enumerate(dialog.candidates) if abs(c.boundary_time_sec - boundary_time) < 1e-9]
            assert len(rows) == 1, [c.boundary_time_sec for c in dialog.candidates]
            row = rows[0]
            assert dialog.candidates[row].recommendation_axis == 'X'
            dialog._axis_combos[row].setCurrentIndex(dialog._axis_combos[row].findData('X'))
            QTest.mouseClick(dialog._approval_checkboxes[row], Qt.MouseButton.LeftButton)
            app.processEvents()
            # Local screenshots are opt-in and ignored by Git.
            dialog.grab().save(str(evidence / 'review.png'))
            reviewed.append(True)
            QTest.mouseClick(dialog.findChild(QDialogButtonBox).button(QDialogButtonBox.StandardButton.Ok), Qt.MouseButton.LeftButton)
        except Exception as exc:
            errors.append(str(exc))
            dialog.reject()
    timer.timeout.connect(approve)
    timer.start(100)
    QTest.mouseClick(raw_widget.review_marker_flips_button, Qt.MouseButton.LeftButton)
    assert not raw_widget.load_csv_button.isEnabled()
    wait_until(lambda: (bool(reviewed) and raw_widget.review_worker is None) or bool(errors))
    assert raw_widget.marker_review_dirty
    assert not raw_widget.save_slice_button.isEnabled()
    choose(corrected)
    QTest.mouseClick(raw_widget.save_corrected_source_button, Qt.MouseButton.LeftButton)
    assert corrected.exists()
    assert not raw_widget.marker_review_dirty
    meta = read_corrected_source_metadata(str(corrected))
    assert meta.schema_version == '3' and meta.approved_event_count == 1
    assert meta.algorithm_version == '3.1'
    assert any(d.recommendation_axis == 'X' and d.approved for d in meta.decisions)
    assert source.read_bytes() == original_bytes
    _, loaded = DataLoader().load_csv(str(corrected))
    np.testing.assert_allclose(loaded.iloc[:, :raw.shape[1]].to_numpy(dtype=float), raw.to_numpy(dtype=float))
    # Reload must restore the approved geometry and context, not apply twice.
    raw_widget.le_box_l.setText('999')
    choose(corrected)
    QTest.mouseClick(raw_widget.load_csv_button, Qt.MouseButton.LeftButton)
    assert raw_widget._read_box_dimensions() == tuple(dims)
    assert raw_widget.review_context_json == meta.context_json
    assert raw_widget.parsed_data['F1_FaceInfo'].iloc[80] == 'BACK'
    window.grab().save(str(evidence / 'reloaded.png'))
    choose(sliced)
    QTest.mouseClick(raw_widget.save_slice_button, Qt.MouseButton.LeftButton)
    assert sliced.exists(), raw_widget.log_output.toPlainText()
    assert read_slice_metadata(str(sliced)).correction_context_json == meta.context_json
    window.tab_widget.setCurrentIndex(1)
    processing = window.processing_widget
    choose(sliced)
    QTest.mouseClick(processing.load_slice_button, Qt.MouseButton.LeftButton)
    assert processing.parsed_data['F1_FaceInfo'].iloc[80] == 'BACK'
    QTest.mouseClick(processing.run_button, Qt.MouseButton.LeftButton)
    wait_until(lambda: processing.save_proc_button.isEnabled())
    choose(processed)
    QTest.mouseClick(processing.save_proc_button, Qt.MouseButton.LeftButton)
    assert processed.exists()
    if source_kind == 'collision_face':
        scalar_report['stage'] = 'official_proc_reopen_and_pose_oracle'
        reopened = DataLoader().load_result_csv(str(processed))
    output = pd.read_csv(processed, header=[0, 1, 2], index_col=0)
    assert ('Info', 'MarkerCorrection', 'ContextJson') in output.columns
    from src.utils.artifact_metadata import read_identity
    exported_identity = read_identity(output)
    if mujoco_truth is not None:
        assert exported_identity.source_kind == 'mujoco_synthetic'
        assert exported_identity.exclusion_reasons() == []
        assert exported_identity.values['IstaType'] == 'not_applicable'
    else:
        assert exported_identity.source_kind == 'unknown_legacy'
    if mujoco_truth is not None:
        pose_output = reopened if source_kind == 'collision_face' else output
        np.testing.assert_allclose(pose_output.index.to_numpy(dtype=float), mujoco_truth.time_s, atol=1e-10)
        positions = pose_output[[('Position', 'CoM', 'P_T' + a) for a in 'XYZ']].to_numpy()
        rotvecs = pose_output[[('Position', 'CoM', 'P_R' + a) for a in 'XYZ']].to_numpy()
        expected_positions = mujoco_truth[[f'body_{a}_mm' for a in 'xyz']].to_numpy()
        expected_rotations = mujoco_truth[[f'r{i}{j}' for i in range(3) for j in range(3)]].to_numpy().reshape(-1, 3, 3)
        position_error = np.linalg.norm(positions - expected_positions, axis=1).max()
        rotation_error = np.degrees((Rotation.from_matrix(expected_rotations).inv() * Rotation.from_rotvec(rotvecs)).magnitude()).max()
        assert position_error < .1
        assert rotation_error < .1
        if source_kind == 'collision_face':
            scalar_report['pose_errors'] = {'max_position_mm': float(position_error),
                                             'max_rotation_deg': float(rotation_error)}
        print(f'MuJoCo GUI proc max error: {position_error} mm, {rotation_error} deg')
    window.grab().save(str(evidence / 'processed.png'))
    if source_kind == 'collision_face':
        import shutil
        from src.analysis.pipeline.artifact_io import add_timeline_context_columns, save_proc_file
        from src.analysis.compare.data_model import ComparisonModel
        from src.analysis.compare.impact_metrics import calculate_impact_metrics
        from src.config.data_columns import DropPostureSummaryCols
        # Independent-review reproduction: same GUI-produced pose, actually
        # executed contact policies 1/20 mm. Only postprocessing is rerun.
        contact_model = ComparisonModel()
        t1_values = []
        contact_records = []
        pose_input = processing.current_processed_result.drop(columns=[
            column for column in processing.current_processed_result.columns
            if str(column).startswith('DropPosture')])
        scalar_report['stage'] = 'public_precontact_scalar_metrics'
        _record_public_impact_metrics(reopened, mujoco_truth, scalar_report)

        # Keep actual binary sample times: source frames 60..71 are twelve
        # already-computed poses. No second Raw/optimizer execution is needed.
        scalar_report['stage'] = 'sustained_contact_postprocess_only'
        sustained_input = pose_input.iloc[60:72].copy()
        sustained_metadata = replace(processing.slice_metadata,
            user_start=float(sustained_input.index[0]), user_end=float(sustained_input.index[-1]))
        sustained = window.pipeline_controller._execute_post_processing(
            {'analysis_options': {'drop_posture_contact_threshold_mm': 1.}}, sustained_input)
        sustained_context = processing._build_timeline_context(sustained_metadata)
        sustained_path = evidence / 'sustained_contact.proc'
        save_proc_file(str(sustained_path), add_timeline_context_columns(sustained, sustained_context))
        sustained_reopened = DataLoader().load_result_csv(str(sustained_path))
        sustained_metrics = calculate_impact_metrics(sustained_reopened)
        summary = ('Analysis', 'DropPostureSummary')
        state = str(sustained_reopened[(*summary, 'ContactState')].iloc[0])
        t1_detected = str(sustained_reopened[(*summary, 'T1Detected')].iloc[0]).lower()
        impact_detected = str(sustained_reopened[(*summary, 'ImpactDetected')].iloc[0]).lower()
        scalar_report['sustained_contact'] = {
            'expected': {'source_frames': [60, 71], 'sample_count': 12,
                         'nominal_time_range_s': [.480, .568], 'contact_state': 'SustainedContact',
                         't1_detected': False, 'impact_detected': False,
                         'numeric_metrics': 'all four unavailable'},
            'actual': {'sample_count': len(sustained_reopened),
                       'time_range_s': [float(sustained_reopened.index[0]), float(sustained_reopened.index[-1])],
                       'contact_state': state, 't1_detected': t1_detected, 'impact_detected': impact_detected,
                       'metrics': asdict(sustained_metrics)},
        }
        checks = scalar_report['checks']
        checks['sustained_contact_has_no_impact'] = (
            len(sustained_reopened) == 12 and state == 'SustainedContact'
            and t1_detected in ('false', '0', '0.0') and impact_detected in ('false', '0', '0.0'))
        checks['sustained_contact_metrics_unavailable'] = all(
            sustained_metrics.metrics[key].value is None and bool(sustained_metrics.metrics[key].reason)
            for key in ('vertical_velocity', 'horizontal_speed', 'angular_speed', 'equivalent_height'))
        checks['sustained_selected_timeline_preserved'] = all(
            sustained_reopened[('Info', 'Timeline', field)].eq(value).all()
            for field, value in (('SliceStartSec', sustained_metadata.user_start),
                                 ('SliceEndSec', sustained_metadata.user_end),
                                 ('FullStartSec', processing.slice_metadata.full_start),
                                 ('FullEndSec', processing.slice_metadata.full_end)))
        scalar_report['stage'] = 'existing_contact_policy_compatibility'
        for threshold in (1., 20.):
            reprocessed = window.pipeline_controller._execute_post_processing(
                {'analysis_options': {'drop_posture_contact_threshold_mm': threshold}},
                pose_input)
            t1_values.append(float(reprocessed[DropPostureSummaryCols.T1_MINUS_TIME_SEC].iloc[0]))
            with_context = add_timeline_context_columns(reprocessed, processing._build_timeline_context())
            contact_path = evidence / f'contact_{threshold:g}mm.proc'
            save_proc_file(str(contact_path), with_context)
            name = contact_model.load_file(str(contact_path))
            contact_records.append(contact_model.identities[name].values['ProcessingSemanticsVersion'])
        np.testing.assert_allclose(t1_values, [.136, .120], atol=1e-10)
        assert contact_records[0] != contact_records[1]
        assert any('ProcessingSemanticsVersion' in reason for reason in contact_model.exclusion_reasons(name))
        (evidence / 'contact_settings_regression.json').write_text(json.dumps({
            'thresholds_mm': [1,20], 't1_sec': t1_values, 'processing_versions': contact_records,
            'excluded_reasons': contact_model.exclusion_reasons(name)}, indent=2), encoding='utf-8')
        for path in [source, corrected, sliced, processed, generated / 'truth_pose.csv',
                     generated / 'truth_markers.csv', generated / 'observed.synthetic.json']:
            if path.resolve() != (evidence / path.name).resolve():
                shutil.copy2(path, evidence / path.name)
        (evidence / 'result.json').write_text(json.dumps({
            'input': str(source), 'expected': '100 samples, unchanged XYZ, manual X at 0.520 s, pose <0.1 mm/deg',
            'actual_samples': len(output), 'max_position_mm': float(position_error),
            'max_rotation_deg': float(rotation_error)}, indent=2), encoding='utf-8')
        checks['source_truth_manifest_unchanged'] = scalar_report['input_sha256_before'] == _input_hashes(protected)
        scalar_report['stage'] = 'scalar_assertions'
        assert all(checks.values()), {key: value for key, value in checks.items() if not value}
    if raw_widget.review_worker:
        raw_widget.review_worker.wait()
    window.worker.wait()
    window.close()
    if source_kind == 'collision_face':
        scalar_report['stage'], scalar_report['status'] = 'complete', 'pass'


def test_reordered_annotations_rereview_off_on_and_suffix_pose(tmp_path, monkeypatch):
    import csv
    import json
    import shutil
    from src.simulation.marker_fixtures import write_case, virtual_profile_32
    from src.analysis.pipeline.face_assignment import materialize_face_assignments, face_columns
    from src.analysis.pipeline.marker_flip import MarkerCorrectionDecision
    from src.analysis.pipeline.artifact_io import save_corrected_source_file, save_slice_file, _sha256_file
    from src.analysis.pipeline.parser import Parser
    from src.config.data_columns import FACE_PREFIX_TO_INFO, SourceCols
    from PySide6.QtWidgets import QMessageBox

    started = time.monotonic()
    monkeypatch.setattr(config_app, 'BOX_DIMS', np.array(config_app.BOX_DIMS, copy=True))
    monkeypatch.setattr(config_app, 'LOCAL_BOX_CORNERS', np.array(config_app.LOCAL_BOX_CORNERS, copy=True))
    profile = virtual_profile_32()
    dims = tuple(profile['box_dims_mm'])
    generated = write_case(tmp_path / 'input', 'x', profile=profile, motion='face')
    original = generated / 'observed.csv'
    header, raw = DataLoader().load_csv(str(original))
    baseline = Parser(FACE_PREFIX_TO_INFO).process(header, raw)
    for column in baseline:
        if column.endswith('_FaceInfo'):
            baseline[column] = baseline[column].str.upper()
    base = {m['id']: m['face'] for m in profile['markers']}
    event = MarkerCorrectionDecision('independent-x', .520, True, 'X',
        correction_kind='face_assignment', algorithm_version='3.0', gate_version='face-validation-pending')
    context = json.dumps({'box_dims_mm': dims, 'base_faces': base,
        'coordinate_policy': 'global-y-up-box-xyz-mm', 'source_sha256': _sha256_file(str(original)),
        'export_metadata': header['export_metadata']})
    h, fixed = materialize_face_assignments(header, raw, [event], base)
    source = tmp_path / 'reordered.corrected.csv'
    save_corrected_source_file(filepath=str(source), header_info=h, raw_data=fixed,
        original_source_path=str(original), decisions=[event], context_json=context)
    # Valid schema: swap whole F1/R1 annotation columns, then interleave one
    # before the XYZ triplets. Header identity travels with each data column.
    annotations = face_columns(h)
    order = list(range(fixed.shape[1]))
    a, b = annotations['F1'], annotations['R1']
    order[a], order[b] = order[b], order[a]
    moved = order.pop(a)
    order.insert(2, moved)
    with source.open(newline='', encoding='utf-8') as stream:
        rows = list(csv.reader(stream))
    rows[2:] = [[row[i] for i in order] for row in rows[2:]]
    with source.open('w', newline='', encoding='utf-8') as stream:
        csv.writer(stream).writerows(rows)
    loaded_header, loaded_raw = DataLoader().load_csv(str(source))
    expected_active = Parser(FACE_PREFIX_TO_INFO).process(h, fixed)
    pd.testing.assert_frame_equal(Parser(FACE_PREFIX_TO_INFO).process(loaded_header, loaded_raw), expected_active)
    source_bytes, original_bytes = source.read_bytes(), original.read_bytes()
    evidence = Path('tmp/issue74_gui/reordered_annotations')
    evidence.mkdir(parents=True, exist_ok=True)
    app = QApplication.instance() or QApplication([])
    app.setAttribute(Qt.ApplicationAttribute.AA_DontUseNativeDialogs, True)
    window = MainApp()
    window.show()
    widget = window.original_widget
    errors = []
    error_watcher = QTimer()
    def capture_error_dialog():
        dialog = app.activeModalWidget()
        if isinstance(dialog, QMessageBox):
            errors.append(dialog.text())
            dialog.reject()
    error_watcher.timeout.connect(capture_error_dialog)
    error_watcher.start(100)
    def choose(path):
        def select():
            dialog = app.activeModalWidget()
            if not isinstance(dialog, QFileDialog):
                errors.append('Expected real file dialog')
                return
            dialog.selectFile(str(path))
            def accept():
                dialog.findChild(QLineEdit, 'fileNameEdit').setText(str(path))
                dialog.accept()
            QTimer.singleShot(250, accept)
        QTimer.singleShot(250, select)
    def wait_until(predicate):
        deadline = time.monotonic() + 150
        while not predicate() and not errors and time.monotonic() < deadline:
            app.processEvents()
            time.sleep(.01)
        assert not errors, errors
        assert predicate(), 'Actual re-review workflow did not finish'
    def reload(path):
        choose(path)
        QTest.mouseClick(widget.load_csv_button, Qt.MouseButton.LeftButton)
        assert Path(widget.source_path) == path
        pd.testing.assert_frame_equal(widget.review_parsed_data, baseline)
        # Review raw data and its own header remain a valid pair after load/save.
        pd.testing.assert_frame_equal(widget.parser.process(widget.review_header_info, widget.review_raw_data), baseline)
    def review(approved):
        finished = []
        timer = QTimer()
        def handle():
            dialog = app.activeModalWidget()
            if not isinstance(dialog, MarkerFlipReviewDialog):
                return
            timer.stop()
            try:
                rows = [i for i,c in enumerate(dialog.candidates) if abs(c.boundary_time_sec - .520) < 1e-9]
                assert len(rows) == 1
                i = rows[0]
                assert dialog.candidates[i].recommendation_axis == 'X'
                assert dialog.candidates[i].hypothesis('X').residual_deg < .1
                dialog._axis_combos[i].setCurrentIndex(dialog._axis_combos[i].findData('X'))
                if dialog._approval_checkboxes[i].isChecked() != approved:
                    QTest.mouseClick(dialog._approval_checkboxes[i], Qt.MouseButton.LeftButton)
                assert dialog._approval_checkboxes[i].isChecked() == approved
                dialog.grab().save(str(evidence / ('review_on.png' if approved else 'review_off.png')))
                QTest.mouseClick(dialog.findChild(QDialogButtonBox).button(QDialogButtonBox.StandardButton.Ok), Qt.MouseButton.LeftButton)
                finished.append(True)
            except Exception as exc:
                errors.append(str(exc))
                dialog.reject()
        timer.timeout.connect(handle)
        timer.start(100)
        widget.marker_review_section.setExpanded(True)
        if not widget.confirm_review_dimensions.isChecked():
            QTest.mouseClick(widget.confirm_review_dimensions, Qt.MouseButton.LeftButton)
        QTest.mouseClick(widget.review_marker_flips_button, Qt.MouseButton.LeftButton)
        wait_until(lambda: bool(finished) and widget.review_worker is None)
        timer.stop()
    try:
        reload(source)
        pd.testing.assert_frame_equal(widget.parsed_data, expected_active)
        outputs = []
        for approved in (False, True):
            review(approved)
            assert widget.marker_review_dirty
            target = tmp_path / ('on.csv' if approved else 'off.csv')
            choose(target)
            QTest.mouseClick(widget.save_corrected_source_button, Qt.MouseButton.LeftButton)
            assert target.exists(), widget.log_output.toPlainText()
            reload(target)
            pd.testing.assert_frame_equal(widget.parsed_data, expected_active if approved else baseline)
            assert read_corrected_source_metadata(str(target)).approved_event_count == int(approved)
            outputs.append(target)
        suffix = tmp_path / 'suffix.slice'
        final_time = float(baseline.index[-1])
        save_slice_file(filepath=str(suffix), header_info=widget.header_info, raw_data=widget.raw_data,
            source_path=widget.source_path, full_start=0., full_end=final_time, user_start=.56, user_end=final_time,
            pad_rows=0, box_dims=dims, marker_correction_metadata=widget.correction_source_metadata)
        window.tab_widget.setCurrentIndex(1)
        processing = window.processing_widget
        choose(suffix)
        QTest.mouseClick(processing.load_slice_button, Qt.MouseButton.LeftButton)
        expected_suffix = expected_active.loc[expected_active.index >= .56-1e-12]
        pd.testing.assert_frame_equal(processing.parsed_data, expected_suffix)
        assert processing.parsed_data.index.min() > .520
        # A 30-row suffix is readable but below the full pipeline's 50-row
        # minimum. Keep that gate; verify its actual parsed pose separately.
        from src.analysis.pipeline.pose_optimizer import PoseOptimizer
        from src.analysis.pipeline.face_assignment import POSE_COLUMNS
        output = PoseOptimizer(config_app.FACE_DEFINITIONS,
            config_app.calculate_local_box_corners(dims)).process(processing.parsed_data, dims)
        assert len(output) == 30
        assert output[SourceCols.POSE].eq('Optimized').all()
        target = tmp_path / 'suffix_pose.csv'
        output.to_csv(target)
        truth = pd.read_csv(generated / 'truth_pose.csv')
        truth = truth.loc[truth.time_s >= .56-1e-12]
        np.testing.assert_allclose(output.index.to_numpy(dtype=float),truth.time_s,atol=1e-10)
        positions = output[list(POSE_COLUMNS[:3])].to_numpy()
        rotvecs = output[list(POSE_COLUMNS[3:])].to_numpy()
        expected_positions = truth[[f'body_{a}_mm' for a in 'xyz']].to_numpy()
        rotations = truth[[f'r{i}{j}' for i in range(3) for j in range(3)]].to_numpy().reshape(-1,3,3)
        pe = np.linalg.norm(positions-expected_positions,axis=1).max()
        re = np.degrees((Rotation.from_matrix(rotations).inv()*Rotation.from_rotvec(rotvecs)).magnitude()).max()
        assert pe < .1 and re < .1
        assert source.read_bytes() == source_bytes and original.read_bytes() == original_bytes
        window.grab().save(str(evidence / 'suffix_loaded.png'))
        for path in [source, original, *outputs, suffix, target, generated/'truth_pose.csv']:
            shutil.copy2(path, evidence/path.name)
        result = {'samples':len(output),'valid_pose_samples':int(output[SourceCols.POSE].eq('Optimized').sum()),
                  'max_position_mm':float(pe),'max_rotation_deg':float(re),
                  'seconds':time.monotonic()-started,'original_bytes_preserved':True,
                  'expected':'ID-based faces/XYZ preserved through reordered load, real OFF/ON re-review, resave, suffix load and direct pose fit; errors <0.1 mm/deg'}
        (evidence/'result.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
        print(result)
    finally:
        error_watcher.stop()
        if widget.review_worker:
            widget.review_worker.wait()
        if getattr(window, "worker", None):
            window.worker.wait()
        window.close()
