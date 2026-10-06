"""Fresh production capture runner. No baseline creation or cache promotion."""
from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import datetime, timezone, timedelta
import importlib.metadata
import json
from pathlib import Path
import platform
import subprocess
import sys
import time
import traceback
import uuid

import numpy as np
import pandas as pd

from src.analysis.pipeline.artifact_io import (save_slice_file, read_slice_metadata,
    save_proc_file, add_timeline_context_columns, save_corrected_source_file)
from src.analysis.pipeline.data_loader import DataLoader
from src.analysis.pipeline.parser import Parser
from src.analysis.pipeline.pipeline_controller import PipelineController
from src.analysis.pipeline.scene_detection import Registration, detect_scenes
from src.analysis.pipeline.scene_review import SceneReviewSession
from src.analysis.pipeline.face_assignment import materialize_face_assignments
from src.analysis.pipeline.marker_flip import MarkerCorrectionDecision
from src.analysis.pipeline.scenario_export import automatic_offsets, scenario_text
from src.analysis.compare.data_model import ComparisonModel
from src.config.data_columns import FACE_PREFIX_TO_INFO
from src.config import config_app
from src.simulation.marker_fixtures import validate_profile
from src.utils.header_converter import convert_to_multi_header
from .contracts import (envelope, read_json, write_new_json, file_digest, digest, canonical,
    validate_fixture, anchor, replay_mapping, metric, SEMANTIC_VERSION)
from .signatures import (array, pose_trajectory, residual_guard, compare_metrics,
                          scene_signature, runs, scenario_guard)


def peak_memory_bytes():
    if sys.platform == 'win32':
        import ctypes
        from ctypes import wintypes
        class Counters(ctypes.Structure):
            _fields_ = [('cb', wintypes.DWORD), ('PageFaultCount', wintypes.DWORD),
                       *[(n, ctypes.c_size_t) for n in ('PeakWorkingSetSize', 'WorkingSetSize',
                         'QuotaPeakPagedPoolUsage', 'QuotaPagedPoolUsage', 'QuotaPeakNonPagedPoolUsage',
                         'QuotaNonPagedPoolUsage', 'PagefileUsage', 'PeakPagefileUsage')]]
        c = Counters()
        c.cb = ctypes.sizeof(c)
        kernel = ctypes.WinDLL('kernel32')
        kernel.GetCurrentProcess.restype = wintypes.HANDLE
        api = ctypes.WinDLL('psapi').GetProcessMemoryInfo
        api.argtypes = (wintypes.HANDLE, ctypes.POINTER(Counters), wintypes.DWORD)
        if api(kernel.GetCurrentProcess(), ctypes.byref(c), c.cb):
            return int(c.PeakWorkingSetSize)
        return None
    import resource
    return int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * (1 if sys.platform == 'darwin' else 1024))


class ReviewRequired(ValueError):
    pass


class ReferenceMissing(FileNotFoundError):
    pass


def approval_check(value, label):
    if value.get('status') != 'approved' or any(not value.get(k) for k in ('reviewer', 'date', 'basis')):
        raise ReviewRequired(label + ' is missing reviewed approval.')


def validate_tolerance(value):
    approval_check(value['approval'], 'Tolerance')
    if not value.get('version') or not value.get('basis'):
        raise ReviewRequired('Tolerance version/basis unavailable.')
    for key in ('center_mm', 'rotation_deg', 'corner_mm', 'height_mm', 'time_s', 'velocity_m_s', 'angular_rad_s', 'diagnostic_deg', 'diagnostic_mm'):
        spec = value['bounds'][key]
        if any(type(spec[k]) not in (int, float) or not np.isfinite(spec[k]) or spec[k] < 0 for k in ('absolute', 'relative')):
            raise ValueError('Invalid tolerance: ' + key)


def validate_proc_linkage(df, linkage, expected_records, expected_times):
    column = ('Info', 'CaptureReplay', 'Json')
    if column not in df or df[column].nunique(dropna=False) != 1 or json.loads(df[column].iloc[0]) != linkage:
        raise ValueError('Stale proc/source/settings linkage.')
    if (not np.array_equal(array(df,['Source_OriginalRecordIndex'])[:,0],expected_records)
            or not np.array_equal(df.index.to_numpy(float),expected_times)):
        raise ValueError('Proc lost exact original record/raw-time correspondence.')


def validate_trial_counts(first, duplicate):
    if first != duplicate or any(n > 1 for n in first.values()):
        raise ValueError('Compare inflated original-trial n.')


def production_capture(raw_path, fixture, case_output):
    """Only observed Raw, static geometry and reviewed corrections enter here.

    Evaluator TrajectoryReference and expected metrics are read later, outside
    this boundary; scenario labels never enter detector/optimizer configuration.
    """
    loader = DataLoader()
    header, raw = loader.load_csv(str(raw_path))
    if file_digest(raw_path) != fixture['raw_sha256']:
        raise ValueError('Raw SHA256 mismatch; replay forbidden.')
    profile = fixture['marker_profile']
    if profile['profile_id'] != fixture['marker_profile_id'] or validate_profile(profile) != fixture['marker_profile_hash']:
        raise ValueError('Marker profile identity mismatch.')
    if profile['box_dims_mm'] != fixture['geometry']['box_dims_mm']:
        raise ValueError('Geometry/profile dimensions mismatch.')
    from src.utils.artifact_metadata import DIMENSIONS, validate_declared_dimensions
    declared = header['artifact_metadata']
    if 'marker_profile_identity' in fixture:
        from src.utils.marker_profile_identity import artifact_identity
        actual = artifact_identity(declared)
        expected = fixture['marker_profile_identity']
        if actual is None or any(actual[key] != expected[key] for key in ('profile_hash', 'geometry_hash', 'observation_mapping_hash', 'semantic_hash', 'policy_hash')):
            raise ValueError('Raw/replay marker semantic source identity mismatch.')
    validate_declared_dimensions(declared, fixture['geometry']['box_dims_mm'])
    required_identity = dict(SchemaVersion='1', SourceKind='handcrafted_dummy',
        MarkerLayoutId=fixture['marker_profile_id'], MarkerLayoutHash=fixture['marker_profile_hash'],
        CoordinatePolicy='world-y-up-box-local-fixed-center-v1',
        UnitsPolicy='bma-mm-s-rotvec-rad-summary-deg-v1')
    if any(declared.get(k) != v for k, v in required_identity.items()) or any(declared.get(k) is None for k in DIMENSIONS):
        raise ValueError('Raw/profile/source/frame/units declaration conflict or missing identity.')
    parsed = Parser(FACE_PREFIX_TO_INFO).process(header, raw)
    removed = parsed.attrs.get('removed_records', [])
    if removed:
        raise ValueError('Capture detection cannot replay removed Time records: ' + canonical(removed))
    reg = Registration(profile, fixture['geometry']['floor_y_mm'])
    reg.validate()
    initial = detect_scenes(header, raw, parsed, registration=reg)
    corrections = []
    for f in fixture['flip_decisions']:
        i = f['original_record_index']
        if not 0 <= i < len(raw) or float(raw.iloc[i, 1]) != f['raw_time_s']:
            raise ValueError('Stale flip record/time.')
        if anchor(raw, i, min(len(raw), i + 1)) != f['anchor']:
            raise ValueError('Stale flip neighboring data.')
        corrections.append(MarkerCorrectionDecision(event_id=f['review_id'], boundary_time_sec=f['raw_time_s'],
            approved=f['axis'] != 'OFF', axis=None if f['axis'] == 'OFF' else f['axis'],
            correction_kind='face_assignment', algorithm_version='3.1', gate_version='face-continuity-v1'))
    active_path, correction_metadata = raw_path, None
    if corrections:
        base_faces = {m['id']: m['face'] for m in profile['markers']}
        fixed_header, fixed = materialize_face_assignments(header, raw, corrections, base_faces)
        pd.testing.assert_frame_equal(fixed.iloc[:, :raw.shape[1]], raw)
        context = dict(box_dims_mm=profile['box_dims_mm'], base_faces=base_faces,
            coordinate_policy='global-y-up-box-xyz-mm', source_sha256=fixture['raw_sha256'],
            export_metadata=header['export_metadata'])
        active_path = case_output / 'corrected.csv'
        correction_metadata = save_corrected_source_file(filepath=str(active_path), header_info=fixed_header,
            raw_data=fixed, original_source_path=str(raw_path), decisions=corrections, context_json=canonical(context))
        header, active_raw = loader.load_csv(str(active_path))
        header_raw = active_raw
    else:
        header_raw = raw
    parsed = Parser(FACE_PREFIX_TO_INFO).process(header, header_raw)
    result = detect_scenes(header, header_raw, parsed, registration=reg)
    # Mapping digests always use ORIGINAL observations, including corrected runs.
    mapping, candidates = replay_mapping(raw, fixture['scene_decisions'], result.candidates)
    session = SceneReviewSession(result, fixture['raw_sha256'])
    accepted = {m['review_id']: m for m in mapping if m['status'] in ('matched', 'manual_bound')}
    for d in fixture['scene_decisions']:
        if d['review_id'] not in accepted:
            continue
        times = np.asarray(raw.iloc[:, 1], float)
        a = d['anchor']['start_record']
        b = d['anchor']['end_record_exclusive']
        if d['origin'] == 'automatic':
            row_id = accepted[d['review_id']]['candidate_ids'][0]
            session.set_range(row_id, float(times[a]), float(times[b - 1]))
        else:
            row_id = session.add_range(float(times[a]), float(times[b - 1]))
        # The current production review API rebuilds marker evidence for an
        # edited/manual range. Never merely relabel stale evidence as current.
        saved_row = session.row(row_id)
        rebuilt = session.recompute_saved_row(saved_row)
        session.rows[session.rows.index(saved_row)] = rebuilt
        session.set_decision(row_id, d['decision'])
        session.row(row_id)['replay_review_id'] = d['review_id']
    return header, header_raw, raw, result, initial, mapping, candidates, session, active_path, correction_metadata


def process_scene(fixture, decision, session, header, raw, original_raw, source_path,
                  correction_metadata, output, run_id, progress=None):
    """Actual slice -> Parser -> PipelineController -> proc -> Compare -> export."""
    row = next(r for r in session.rows if r.get('replay_review_id') == decision['review_id'])
    a, b = decision['anchor']['start_record'], decision['anchor']['end_record_exclusive']
    times = np.asarray(original_raw.iloc[:, 1], float)
    start, end = float(times[a]), float(times[b - 1])  # explicit legacy inclusive adapter
    pad = decision['padding_rows']
    saved_indices = list(range(max(0, a - pad), min(len(raw), b + pad)))
    payload = json.loads(session.payload(row['id']))
    # Identification runs on marker evidence before applying reviewed identity.
    session.identify()
    observed_items = list(session.row(row['id'])['item_candidates'])
    payload = json.loads(session.payload(row['id']))
    payload['identity'].update(ista_type=decision['test_type'],
        scenario_id=decision['scenario_id'], confirmed=decision['label_status'] == 'confirmed',
        applied_edition='2018-03' if decision['label_status'] == 'confirmed' else None,
        scenario_kind=decision['scenario_kind'])
    linkage = envelope('CaptureReplay', run_id=run_id, review_id=decision['review_id'],
        raw_sha256=fixture['raw_sha256'], decision_sha256=digest(fixture['scene_decisions']),
        fixture_sha256=digest(fixture), marker_profile_hash=fixture['marker_profile_hash'],
        geometry_sha256=digest(fixture['geometry']), settings_sha256=digest(fixture['effective_processing_config']),
        original_interval=decision['anchor'], saved_original_record_indices=saved_indices,
        correction_decisions=fixture['flip_decisions'], observed_item_candidates=observed_items)
    payload['capture_replay'] = linkage
    metadata_header = dict(header)
    artifact_identity = dict(header['artifact_metadata'])
    artifact_identity.update(IstaType=decision['test_type'], ScenarioId=decision['scenario_id'],
                             ScenarioKind=decision['scenario_kind'])
    metadata_header['artifact_metadata'] = artifact_identity
    slice_path = output / (decision['review_id'] + '.slice')
    meta = save_slice_file(filepath=str(slice_path), header_info=metadata_header, raw_data=raw,
        source_path=str(source_path), full_start=float(times[0]), full_end=float(times[-1]),
        user_start=start, user_end=end, box_dims=fixture['geometry']['box_dims_mm'],
        pad_rows=pad, scene_name=decision['review_id'], marker_correction_metadata=correction_metadata,
        scene_review_json=canonical(payload))
    if read_slice_metadata(str(slice_path)) != meta:
        raise ValueError('Slice metadata changed on reload.')
    sh, sr = DataLoader().load_csv(str(slice_path))
    if len(sr) != len(saved_indices):
        raise ValueError('Slice row count mismatch.')
    # Numerical/ID source preservation, including padded rows and missing values.
    np.testing.assert_allclose(sr.iloc[:, :original_raw.shape[1]].apply(pd.to_numeric).to_numpy(),
        original_raw.iloc[saved_indices].apply(pd.to_numeric).to_numpy(), atol=1e-12, rtol=0, equal_nan=True)
    parsed = Parser(FACE_PREFIX_TO_INFO).process(sh, sr)
    cfg = dict(fixture['effective_processing_config'])
    cfg.update(box_dimensions=fixture['geometry']['box_dims_mm'], slice_filter_by='time',
               slice_start_val=start, slice_end_val=end)
    previous_dims, previous_corners = config_app.BOX_DIMS.copy(), config_app.LOCAL_BOX_CORNERS.copy()
    controller = PipelineController()
    controller.frame_analyzer.floor_level = fixture['geometry']['floor_y_mm']
    controller.drop_posture_post_processor.floor_level = fixture['geometry']['floor_y_mm']
    optimizer_calls = []
    solve = controller.pose_optimizer.process
    def counted(data):
        return solve(data, fit_observer=lambda phase, frame, fit: optimizer_calls.append(frame) if phase == 'start' else None)
    controller.pose_optimizer.process = counted
    try:
        if progress is not None:
            progress.update(processing='failed', boundary='production_processing')
        result = controller.process_parsed_data(cfg, parsed)
        if progress is not None:
            progress.update(processing='fresh', boundary='proc_save_compare_export', optimizer_calls=len(optimizer_calls))
    finally:
        if progress is not None:
            progress['optimizer_calls'] = len(optimizer_calls)
        config_app.BOX_DIMS, config_app.LOCAL_BOX_CORNERS = previous_dims, previous_corners
    if result.empty or not np.array_equal(result['Source_OriginalRecordIndex'].to_numpy(), np.arange(a, b)):
        raise ValueError('Fresh result lost required original records.')
    context = dict(full_start_sec=meta.full_start, full_end_sec=meta.full_end,
        slice_start_sec=meta.user_start, slice_end_sec=meta.user_end,
        artifact_metadata=artifact_identity, scene_review_json=meta.scene_review_json,
        marker_correction_schema_version=meta.correction_schema_version,
        marker_correction_algorithm_version=meta.correction_algorithm_version,
        marker_correction_original_source=meta.correction_original_source,
        marker_correction_original_source_sha256=meta.correction_original_source_sha256,
        marker_correction_reviewed_source=meta.correction_reviewed_source,
        marker_correction_event_count=meta.correction_event_count,
        marker_correction_approved_event_count=meta.correction_approved_event_count,
        marker_correction_context_json=meta.correction_context_json,
        marker_correction_events_json=meta.correction_events_json)
    exported = add_timeline_context_columns(result, context)
    exported['CaptureReplay_Json'] = canonical(linkage)
    proc = output / (decision['review_id'] + '.proc')
    save_proc_file(str(proc), exported)
    reloaded = DataLoader().load_result_csv(str(proc))
    expected_export = convert_to_multi_header(exported).set_index(('Info', 'Time', 'Time'))
    expected_export.index.name = 'Time'
    # Text/status/identity exact; numeric roundtrip only permits CSV rounding.
    for col in expected_export:
        before, after = expected_export[col], reloaded[col]
        if pd.api.types.is_numeric_dtype(before):
            np.testing.assert_allclose(after.to_numpy(float), before.to_numpy(float), atol=1e-9, rtol=1e-12, equal_nan=True)
        else:
            if before.fillna('').astype(str).tolist() != after.fillna('').astype(str).tolist():
                raise ValueError('Proc status/text changed on reload: ' + str(col))
    validate_proc_linkage(reloaded,linkage,np.arange(a,b),times[a:b])
    model = ComparisonModel()
    name = model.load_file(str(proc))
    first_n = {k: v['n'] for k, v in model.get_impact_comparison()['statistics'].items()}
    copy_name = model.load_file(str(proc))
    duplicate_n = {k: v['n'] for k, v in model.get_impact_comparison()['statistics'].items()}
    validate_trial_counts(first_n, duplicate_n)
    selection = len(reloaded) // 2
    selected = reloaded.iloc[selection]
    offsets = automatic_offsets(selected)
    velocities = {prefix + axis: selected[('Velocity', 'CoM', f'BoxLocal_V_{short}{axis}')] for prefix, short in
                  (('ANG_VEL_', 'R'), ('TRA_VEL_', 'T')) for axis in 'XYZ'}
    if not np.isfinite([v for _, v in offsets] + list(velocities.values())).all():
        raise ValueError('Required scenario export sample has unavailable geometry/velocity.')
    text = scenario_text(offsets, velocities, decision['review_id'], '1.0', '0.001')
    scenario = output / (decision['review_id'] + '.scenario.csv')
    with scenario.open('x', encoding='utf-8', newline='') as stream:
        stream.write(text)
    if scenario.read_text(encoding='utf-8') != text:
        raise ValueError('Scenario export changed on reload.')
    info = dict(slice= slice_path.name, proc=proc.name, scenario=scenario.name,
        slice_sha256=file_digest(slice_path), proc_sha256=file_digest(proc), scenario_sha256=file_digest(scenario),
        saved_original_record_indices=saved_indices, slice_rows=len(sr), proc_rows=len(reloaded),
        reload_status='pass', source_sha256=fixture['raw_sha256'],
        compare=dict(compatibility_reasons=model.exclusion_reasons(name), original_trial_n=first_n,
                     duplicate_original_trial_n=duplicate_n, source_kind=model.identities[name].source_kind),
        scenario_sample_time_s=float(reloaded.index[selection]), scenario_offsets=[list(v) for v in offsets],
        scenario_velocities=velocities, optimizer_calls=len(optimizer_calls), optimizer_input_rows=len(parsed))
    return reloaded, model.impact_results[name], info


def capture_signature(fixture, raw, result, initial, mapping, candidates, scenes, coverage):
    from src.analysis.pipeline.marker_flip import marker_triplet_indices
    times = np.asarray(raw.iloc[:, 1], float)
    triplets = marker_triplet_indices(scenes['header'])
    coordinates = np.stack([raw.iloc[:, list(columns)].apply(pd.to_numeric, errors='coerce').to_numpy(float)
                            for columns in triplets.values()], axis=1)
    valid = np.isfinite(coordinates).all(axis=2)
    freeze = np.r_[False, np.all(np.diff(coordinates, axis=0) == 0, axis=(1, 2))]
    dt = np.diff(times)
    return envelope('CaptureSignature', case_id=fixture['case_id'], raw_sha256=fixture['raw_sha256'],
        raw_rows=len(raw), raw_time_s=[float(times[0]), float(times[-1])],
        exclusive_end_time=fixture['capture_end_raw_time_s'], time_interval_s=dict(minimum=float(dt.min()), maximum=float(dt.max()), median=float(np.median(dt))),
        marker_schema=list(triplets), position_units='mm', nan_intervals=runs(~valid.all(axis=1), times),
        freeze_intervals=runs(freeze, times), marker_valid_ratio=float(valid.mean()),
        marker_valid_ratio_by_id={k: float(valid[:, i].mean()) for i, k in enumerate(triplets)},
        detected_pose_valid_ratio=float(result.valid_pose.mean()), pose_unavailable_ratio=float((~result.valid_pose).mean()),
        initial_candidates=[asdict(c) for c in initial.candidates], candidates=candidates,
        replay_mapping=mapping, scene_decisions=fixture['scene_decisions'], flip_decisions=fixture['flip_decisions'],
        artifacts=scenes['artifacts'], completed_file_counts=dict(slice=len(scenes['artifacts']), proc=len(scenes['artifacts']), scenario=len(scenes['artifacts'])),
        file_inventory=scenes['inventory'], file_counts={kind:sum(p['kind']==kind for p in scenes['inventory']) for kind in ('slice','proc','scenario')},
        coverage=coverage, comparison_groups=[a['compare'] for a in scenes['artifacts']],
        calibration_status='pending', measured_data_status='unavailable')


def run_corpus(manifest_path, asset_root, output, *, tier='full', select=None, command=None):
    start = time.perf_counter()
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    report = envelope('RunReport', run_id=str(uuid.uuid4()), utc=datetime.now(timezone.utc).isoformat(),
        kst=datetime.now(timezone(timedelta(hours=9))).isoformat(), tier='representative' if select else tier,
        command=command or sys.argv, environment=dict(python=sys.version, platform=platform.platform(),
            dependencies={n: importlib.metadata.version(n) for n in ('numpy', 'scipy', 'pandas', 'PySide6', 'mujoco')}),
        code=dict(commit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
            dirty=bool(subprocess.check_output(['git', 'status', '--porcelain'], text=True)), semantics=SEMANTIC_VERSION),
        schema_versions=dict(manifest=1, decision=1, signature=1), cases=[],
        coverage=dict(loaded=0, approved=0, fresh=0, reused=0, failed=0, unexecuted=0),
        cache_origin='none; all selected scenes freshly processed', independent_review=dict(status='pending'),
        gui=dict(status='pending', reason='CLI execution is not native GUI verification'),
        calibration_status='pending', measured_data_status='unavailable', status='fail', exit_code=1)
    try:
        manifest = read_json(manifest_path, 'CaptureCorpus')
        report['manifest_sha256'] = file_digest(manifest_path)
        declared = manifest['approved_scene_ids']
        if len(declared) != len(set(declared)):
            raise ValueError('Duplicate corpus approved scene identity.')
        report['coverage']['approved'] = len(declared)
        report['coverage']['unexecuted'] = len(declared)
        if tier not in ('capture','representative','full') or (tier == 'capture' and select) or (tier == 'representative' and not select):
            raise ValueError('Invalid tier/selection combination.')
        if tier != 'capture' and not declared:
            raise ValueError('Processing tier requires a nonempty approved scene set.')
        if select and (not set(select).issubset(declared) or len(select) != len(set(select))):
            raise ValueError('Representative selection must name distinct approved scenes.')
        approval_check(manifest['approval'], 'Corpus')
        expected_ids = []
        for entry in manifest['cases']:
            case = dict(case_id=entry['case_id'], status='fail', boundary='fixture', scenes=[], errors=[])
            report['cases'].append(case)
            try:
                fixture = read_json(Path(asset_root) / entry['fixture'], 'CaptureReviewFixture')
                validate_fixture(fixture)
                approval_check(fixture['approval'], 'Replay')
                validate_tolerance(fixture['tolerance'])
                included = [d for d in fixture['scene_decisions'] if d['decision'] == 'include']
                expected_ids += [d['review_id'] for d in included]
                case['identity'] = dict(raw_sha256=fixture['raw_sha256'], decision_sha256=digest(fixture),
                    profile=fixture['marker_profile_hash'], geometry=digest(fixture['geometry']),
                    settings=digest(fixture['effective_processing_config']), tolerance_version=fixture['tolerance']['version'])
                case_output = output / entry['case_id']
                case_output.mkdir()
                case['boundary'] = 'raw_load_detection_replay'
                values = production_capture(Path(asset_root) / fixture['relative_path'], fixture, case_output)
                header, active, original, detection, initial, mapping, candidates, session, source, correction = values
                report['coverage']['loaded'] += 1
                mapping_bad = any(m['status'] not in ('matched', 'manual_bound') for m in mapping) or any(c['mapping_status'] == 'unreviewed' for c in candidates)
                if mapping_bad or not session.all_reviewed:
                    case['status'] = 'needs_review'
                    case['errors'].append('Candidate mapping changed or contains unreviewed candidates.')
                else:
                    case['status'] = 'pass'
                artifacts = []
                for d in included:
                    item = dict(review_id=d['review_id'], status='skipped', processing='unexecuted', boundary='selection')
                    case['scenes'].append(item)
                    if tier == 'capture' or (select and d['review_id'] not in select):
                        item['reason'] = 'Capture tier or outside representative selection'
                        continue
                    if mapping_bad or not session.all_reviewed:
                        item.update(status='needs_review', reason='Source-bound replay cannot be applied')
                        continue
                    try:
                        item['boundary'] = 'slice_processing_proc_compare_export'
                        df, impact, artifact = process_scene(fixture, d, session, header, active, original,
                            source, correction, case_output, report['run_id'], progress=item)
                        item['processing'] = 'fresh'
                        artifacts.append(artifact)
                        item['boundary'] = 'reference_residual_signature'
                        ref_path = Path(asset_root) / fixture['reference']['relative_path']
                        if not ref_path.is_file():
                            raise ReferenceMissing('Required trajectory reference is missing.')
                        if file_digest(ref_path) != fixture['reference']['sha256']:
                            raise ValueError('Trajectory reference SHA256 mismatch.')
                        reference = read_json(ref_path, 'TrajectoryReference')
                        approval_check(reference['approval'], 'Trajectory reference')
                        if reference['raw_sha256'] != fixture['raw_sha256'] or reference['geometry'] != fixture['geometry']:
                            raise ValueError('Reference source/frame/geometry mismatch.')
                        ref = reference['scenes'][d['review_id']]
                        required_metrics = {'t1','t2','reference_face','contact_state','equivalent_height','observed_first_contact',
                            'vertical_velocity','horizontal_speed','angular_speed','final_face',
                            'first_contact','final_rotation_deg','maximum_rotation_deg',
                            'BetaAtT1MinusDeg','ThetaLongAtT1MinusDeg','ThetaShortAtT1MinusDeg','DeltaHAtT1Minus_mm',
                            'MaxBetaDeg','MaxAbsThetaLongDeg','MaxAbsThetaShortDeg','MaxDeltaH_mm'}
                        if not required_metrics.issubset(ref['metrics']):
                            raise ReferenceMissing('Reference is missing required representative metrics.')
                        guard = residual_guard(pose_trajectory(df, fixture['geometry']), ref['trajectory'], fixture['tolerance'])
                        signature = scene_signature(df, fixture, d, impact, artifact, guard)
                        checks = compare_metrics(ref['metrics'], signature['metrics'], fixture['tolerance'])
                        signature['artifacts']['scenario_guard'] = scenario_guard(artifact,ref['trajectory'],fixture['tolerance'])
                        item.update(status='pass' if guard['status'] == 'pass' and signature['artifacts']['scenario_guard']['status']=='pass' and all(v['status'] == 'pass' for v in checks.values()) else 'fail',
                                    comparisons=checks, signature=signature)
                        write_new_json(case_output / (d['review_id'] + '.signature.json'), signature)
                    except Exception as error:
                        item.update(status='blocked' if isinstance(error, ReferenceMissing) else 'needs_review' if isinstance(error, ReviewRequired) else 'fail',
                                    reason=str(error), exception_type=type(error).__name__, traceback=traceback.format_exc())
                    if item['status'] != 'pass':
                        case['status'] = item['status']
                coverage = dict(approved=len(included), fresh=sum(s['processing'] == 'fresh' for s in case['scenes']),
                    reused=0, failed=sum(s['status'] == 'fail' for s in case['scenes']),
                    unexecuted=sum(s['processing'] == 'unexecuted' for s in case['scenes']))
                case['signature'] = capture_signature(fixture, original, detection, initial, mapping, candidates,
                    dict(header=header, artifacts=artifacts, inventory=[dict(path=p.name,
                        kind='scenario' if p.name.endswith('.scenario.csv') else p.suffix[1:],sha256=file_digest(p))
                        for p in case_output.iterdir() if p.suffix in ('.slice','.proc') or p.name.endswith('.scenario.csv')]), coverage)
                write_new_json(case_output / 'capture.signature.json', case['signature'])
                if file_digest(Path(asset_root) / fixture['relative_path']) != fixture['raw_sha256']:
                    raise ValueError('Original Raw changed during run.')
            except Exception as error:
                case.update(status='needs_review' if isinstance(error, ReviewRequired) else 'fail')
                case['errors'].append(dict(exception_type=type(error).__name__, message=str(error), traceback=traceback.format_exc()))
        if sorted(expected_ids) != sorted(declared):
            report['errors'] = ['Corpus/fixture approved scene set mismatch (deletion/addition).']
        all_scenes = [s for c in report['cases'] for s in c['scenes']]
        report['coverage']['fresh'] = sum(s['processing'] == 'fresh' for s in all_scenes)
        report['coverage']['failed'] = sum(s['status'] == 'fail' for s in all_scenes)
        report['coverage']['unexecuted'] = len(declared) - sum(s['processing'] in ('fresh', 'failed') for s in all_scenes)
        statuses = [c['status'] for c in report['cases']]
        report['status'] = 'fail' if report.get('errors') or 'fail' in statuses else 'blocked' if 'blocked' in statuses else 'needs_review' if 'needs_review' in statuses else 'pass'
        if report['tier'] == 'full' and report['coverage']['fresh'] != len(declared):
            report['status'] = 'fail'
        if report['tier'] == 'representative' and report['coverage']['fresh'] != len(select or []):
            report['status'] = 'fail'
        if not manifest['cases']:
            report['status'] = 'fail'
        report['exit_code'] = 0 if report['status'] == 'pass' else 1
    except Exception as error:
        report.update(status='needs_review' if isinstance(error, ReviewRequired) else 'fail',
                      errors=[dict(exception_type=type(error).__name__, message=str(error), traceback=traceback.format_exc())])
    finally:
        all_scenes = [s for c in report['cases'] for s in c['scenes']]
        report['coverage']['fresh'] = sum(s['processing'] == 'fresh' for s in all_scenes)
        report['coverage']['failed'] = sum(s['status'] == 'fail' for s in all_scenes)
        report['coverage']['unexecuted'] = max(0, report['coverage']['approved'] - sum(s['processing'] in ('fresh', 'failed') for s in all_scenes))
        report['duration_s'] = time.perf_counter() - start
        report['peak_memory_bytes'] = peak_memory_bytes()
        report['memory_scope'] = 'Process peak working set, includes imports; not incremental allocations'
        report['optimizer_calls'] = sum(s.get('optimizer_calls', 0) for c in report['cases'] for s in c['scenes'])
        write_new_json(output / 'run_report.json', report)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', required=True)
    parser.add_argument('--asset-root', required=True)
    parser.add_argument('--output', required=True, help='New output directory only; no overwrite or proc reuse.')
    parser.add_argument('--tier', choices=('capture', 'representative', 'full'), default='full')
    parser.add_argument('--scene', action='append', help='Explicit scene selection always reports representative.')
    args = parser.parse_args(argv)
    if args.tier == 'representative' and not args.scene:
        parser.error('representative requires at least one --scene')
    if args.tier == 'capture' and args.scene:
        parser.error('capture cannot be combined with --scene')
    try:
        report = run_corpus(args.manifest, args.asset_root, args.output, tier=args.tier, select=args.scene)
    except Exception as error:
        parser.exit(2, f'Runner failed: {error}\n')
    print(json.dumps(dict(status=report['status'], tier=report['tier'], coverage=report['coverage'],
                          report=str(Path(args.output) / 'run_report.json'))))
    return report['exit_code']


if __name__ == '__main__':
    raise SystemExit(main())
