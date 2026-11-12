"""Build public contracts and same-source adoption metadata from a fixed commit."""
import argparse
from dataclasses import asdict
import hashlib
from importlib.metadata import metadata, version
import json
from pathlib import Path
import platform
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.config.result_metric_descriptors import get_metric_registry, get_series_metric_descriptor
from src.config.data_columns import DISPLAY_RESULT_COLUMNS
from src.config.summary_metric_definitions import DEFINITIONS


def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-revision', required=True)
    parser.add_argument('--base', default='20dd4ce53a6d401fd6e219d6086b7600dba35ad7')
    args = parser.parse_args()
    if not re.fullmatch('[0-9a-f]{40}', args.source_revision):
        raise ValueError('A complete fixed public commit is required')
    git('cat-file', '-e', args.source_revision + '^{commit}')
    output = ROOT / 'docs/visualization/gui_metric_parity'
    output.mkdir(parents=True, exist_ok=True)
    def write(name, value):
        (output / name).write_text(json.dumps(value, ensure_ascii=False, indent=2, default=lambda v:v.value) + '\n', encoding='utf-8')
    entries = [asdict(entry) for entry in get_metric_registry()]
    contract_tests = {}
    def link(keys, *tests):
        for key in keys.split():
            contract_tests[key] = ['tests/test_gui_metric_parity_contract.py::' + test for test in tests]
    link('BetaAtT1MinusDeg ThetaLongAtT1MinusDeg ThetaShortAtT1MinusDeg CminAtT1MinusIndex DeltaHAtT1Minus_mm CminMargin_mm MaxDeltaH_mm ReferenceFace',
         'test_existing_posture_owner_values_are_exposed_under_base_keys',
         'test_a03_exact_100mm_face_spacing_has_50mm_range_at_30deg',
         'test_exact_lowest_corner_ties_are_not_unique_agreement')
    link('TargetPostureError_deg', 'test_target_down_direction_literal_oracle',
         'test_target_rejects_unapproved_or_stale_context', 'test_target_preserves_actual_owner_and_geometry_gates')
    link('FinalFace', 'test_final_face_uses_all_six_faces_and_is_quaternion_sign_invariant',
         'test_final_face_load_requires_saved_field_and_works_without_new_impact',
         'test_final_face_invalid_evidence_is_unavailable')
    link('T1MinusTimeSec T1Detected FirstImpactTimeSec FirstImpactContact ImpactSequence ImpactEventCount',
         'test_detector_onset_and_persistent_contact_start_are_distinct',
         'test_empty_contact_interval_splits_same_set_and_one_frame_is_discarded',
         'test_summary_contact_count_needs_complete_observed_geometry')
    link('VerticalVelAtT1Minus_mm_s VxyAtT1Minus_mm_s AngularSpeedAtT1Minus_rad_s PeakDescentSpeed_mm_s',
         'test_snapshot_reads_saved_components_and_preserves_fit_quantities',
         'test_stored_snapshots_require_actual_time_and_contiguous_segment_provenance',
         'test_peak_descent_needs_complete_prefix_and_all_upward_is_valid_zero')
    link('EquivalentFreeFallHeight_mm', 'test_geometric_height_500mm_with_exact_context_is_distinct_from_com_fit',
         'test_geometric_height_requires_explicit_approved_supported_context',
         'test_geometric_height_projects_only_exact_current_review_context')
    link('RotationDirection TotalSweepAngle_deg SweepConsistency',
         'test_contact_sweep_literal_principal_steps_net_and_cancellation',
         'test_contact_sweep_no_travel_halfturn_and_zero_radius_do_not_invent_values')
    link('ContactState ImpactDetected SustainedContactDetected ContactConfidence ContactDetectionMethod',
         'test_summary_diagnostics_reject_malformed_or_inconsistent_saved_values',
         'test_current_review_evidence_is_separate_from_unmeasured_calibration')
    link('IntendedContactMatch', 'test_intended_contact_adapter_preserves_entire_owner',
         'test_intended_contact_adapter_never_promotes_invalid_equality')
    assert set(contract_tests) == {entry['key'] for entry in DEFINITIONS}
    test_source = (ROOT / 'tests/test_gui_metric_parity_contract.py').read_text(encoding='utf-8')
    assert all('def ' + node.split('::')[1] + '(' in test_source
               for nodes in contract_tests.values() for node in nodes)
    write('metric_contract.json', dict(schema_version=1, source_revision=args.source_revision,
        required_base_keys=[entry['key'] for entry in DEFINITIONS], entries=entries,
        base_contracts=[dict(definition, tests=contract_tests[definition['key']],
            guide_identity='step2:summary:' + definition['key'],
            validity_owner='src.analysis.compare.summary_metrics.resolve_summary_metrics',
            reason_policy='ResolvedMetric.status/reason preserve the actual owner and geometry/provenance gates; unavailable never becomes a fabricated zero.')
            for definition in DEFINITIONS],
        series_context_policy='Full-column tuple identities; one selected-series card is rendered on demand, separate from t1/peak/fit values.',
        series_context_definitions=[asdict(get_series_metric_descriptor(column)) for column in DISPLAY_RESULT_COLUMNS],
        ownership='Producers and existing comparison owners validate values; UI does not recompute eligibility.',
        resolved_fields=['metric_key','value','unit','context','status','reason','source_key','sample_time','method',
                         'reference','window','evidence_status','calibration_status'],
        intended_differences=[
            'Stored geometric-centre snapshots remain separate from one-sided endpoint fits.',
            'Ideal geometric-centre height uses9810mm/s²; registered-COM path-fit height uses9.80665m/s² and already returnsmm.',
            'Detector onset and accepted persistent-event times differ; comparison keeps existing bracket checks.',
            'ReferenceFace and stable-tail FinalFace are distinct; all-six-face public selection is preserved.',
            'Net signed contact sweep is not accumulated angular travel.',
            'Stored intended-contact API enums stay Match/Different/Unclear; only summary adapts Mismatch/Unknown.',
        ]))
    paths = git('diff', '--name-only', args.base, args.source_revision).decode().splitlines()
    files = []
    for path in paths:
        if not (path.startswith(('src/','tests/','scripts/','.github/')) or path == 'build.py'):
            continue
        original = git('show', args.source_revision + ':' + path)
        current = (ROOT / path).read_bytes()
        if git('hash-object', path).strip() != git('rev-parse', args.source_revision + ':' + path).strip():
            raise ValueError('Working source differs from fixed revision: ' + path)
        files.append(dict(path=path, sha256=hashlib.sha256(original).hexdigest(),
                          validated_checkout_sha256=hashlib.sha256(current).hexdigest()))
    dependencies = []
    for name in ('numpy','pandas','scipy','PySide6','matplotlib','pyvista','pyvistaqt','pytest','mujoco','pyinstaller'):
        item = metadata(name)
        dependencies.append(dict(name=name, observed_version=version(name),
            license_metadata=(item.get('License-Expression') or item.get('License') or 'See installed distribution license files').splitlines()[0][:160]))
    license_files = [path for path in git('ls-tree','-r','--name-only',args.source_revision).decode().splitlines()
                     if Path(path).name.upper().startswith(('LICENSE','COPYING'))]
    write('adoption_manifest.json', dict(schema_version=1, source_revision=args.source_revision,
        baseline_revision=args.base, files=files, dependencies=dependencies,
        runtime=dict(python=platform.python_version(), platform=platform.platform(),
                     gui_environment='See validation_report.md for the task-local Qt environment and failed runtime controls; no dependency pin added'),
        hash_policy='sha256 covers committed Git blob bytes; validated_checkout_sha256 records actual tested checkout bytes, including local newline conversion',
        repository_license_files=license_files,
        license_scope='Repository owner same-source adoption; no new dependency or license grant is introduced. Dependencies retain upstream terms.',
        entry_points={
            'processing':'src.analysis.ui.widget_slice_processing.WidgetSliceProcessing',
            'results':'src.analysis.ui.widget_results_analyzer.WidgetResultsAnalyzer',
            'comparison':'src.analysis.compare.main_window.CompareMainWindow',
            'guide':'src.analysis.ui.shared_metric_guide.SharedMetricGuideDialog',
            'resolved_summary':'src.analysis.compare.summary_metrics.resolve_summary_metrics',
            'target_context':'src.analysis.compare.summary_metrics.calculate_target_posture_error',
            'cae_serializer':'src.analysis.pipeline.scenario_export.scenario_text',
        }, signals=dict(processing_requested='existing PipelineController binding',
            results_ready='only successfully saved paths', metric_context_changed='typed selected owner result',
            resolution_details_changed='read-only diagnostics text'),
        defaults=dict(input='Single', processing='Raw', resampling=False, factor=2, overwrite=False,
                      manual_offset=False, manual_height=False, selected_time_velocities=False,
                      runtime='0.1', timestep='1e-7', scene_name='', display_playback_max_gap_sec=.1),
        formats=dict(proc='existing three-level headers; additive FinalFace producer',
                     target_context='optional memory argument; no new SceneReview/CSV target schema',
                     point='entire selected recorded row; original columns and UTF-8 pandas behavior',
                     cae='legacy runtime encoding/newline, six analysis-frame components; atomic replace'),
        verification_commands=[
            'python -m pytest tests/test_gui_metric_parity_contract.py tests/test_gui_metric_parity_exports.py tests/test_gui_metric_parity_workflows.py tests/test_gui177_processing.py',
            'python scripts/gui_metric_parity_product_check.py',
            'python scripts/gui_metric_parity_series_check.py',
            'python scripts/generate_metric_guide_diagrams.py',
        ], limitations=['Synthetic analytic fixtures are not measured experiment truth.',
                        'Actual OS125 and human acceptance are separate, not claimed.',
                        'External native-input activation failed; actual Qt Customize interaction was verified separately.',
                        'Raw producer-hop validation uses the user-approved bounded actual 11 fits per case (22 per successful run).',
                        'Private integration, real capture and CAE regression remain consumer work.']))
    print('Wrote public contracts for', args.source_revision)


if __name__ == '__main__':
    main()
