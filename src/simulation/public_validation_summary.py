"""Summarize one existing JUnit run without rerunning analysis or claiming real accuracy."""
import argparse
import json
from pathlib import Path
import xml.etree.ElementTree as ET


# Explicitly inspected engine/observation-to-consumer paths. Pure array, schema,
# policy and GUI-only checks remain Level 1 even when their fixture is public.
SYNTHETIC_TESTS = {
    'test_posture_comparison_gui': {'test_posture_repeats_in_real_window_with_observed_only_pipeline'},
    'test_scene_signal_gui': {'test_actual_vertical_and_rotation_selection_edit_save_reopen'},
    'test_marker_review_context': {'test_actual_review_context_pan_cancel_save_reopen_and_source_switch'},
    'test_simulation_marker_export': {'test_actual_engine_capture_uses_public_api_and_reopens'},
    'test_simulation_marker_export_gui': {'test_generate_preview_and_open_observations_only'},
    'test_general_export_recovery': {
        'test_general_export_review_roundtrip_and_actual_reprocessing',
        'test_identical_solved_observations_do_not_identify_the_physical_cause',
    },
    'test_mujoco_marker_fixtures': {
        'test_actual_time_and_fresh_origin_com_rotation_sites',
        'test_public_32_collision_truth_is_independent_of_injected_flip',
        'test_existing_simulation_loop_uses_actual_clock',
        'test_two_constraints_cannot_produce_usable_pose_or_flip_candidate',
    },
    'test_marker_face_gui_flow': {
        'test_production_mainapp_face_review_save_and_process',
        'test_reordered_annotations_rereview_off_on_and_suffix_pose',
    },
    'test_simulation_export': {'test_actual_mujoco_nonzero_com_pose_roundtrip'},
    'test_corruption_export': {
        'test_physical_visibility_and_id_routing_preserve_solved_analysis_and_truth',
        'test_exported_solved_half_turn_has_a_scene_tracking_jump_without_truth_input',
    },
    'test_scene_detection': {
        'test_two_releases_remain_two_candidates_including_recontacts',
        'test_similar_handling_has_no_free_fall_or_automatic_trial_identity',
        'test_subset_changes_and_smooth_half_turn_are_not_tracking_jumps',
        'test_partial_record_keeps_both_events_and_censored_boundaries',
        'test_unregistered_gravity_translation_abstains',
    },
    'test_scene_face_corrections': {
        'test_registered_full_history_restores_arbitrary_box_pose_and_corners',
        'test_suffix_uses_approval_before_first_saved_sample_and_preserves_payload',
    },
    'test_scene_face_corrections_gui': {
        'test_current_corrected_memory_detect_and_old_review_reopen_preserve_operator_work',
        'test_workspace_preview_uses_its_own_history_not_previous_active_source',
    },
    'test_support_cycles': {'test_public_handling_merges_one_rise_and_return_and_preserves_raw_members'},
    'test_support_cycle_workflow': {
        'test_step1_selects_automatic_cycle_on_relative_motion_and_keeps_evidence',
        'test_original_rise_range_and_decisions_survive_new_grouping_and_reopen',
        'test_cycle_metadata_survives_slice_proc_and_declared_dimensions_are_preserved',
    },
    'test_scene_review_gui': {'test_detect_select_edit_review_save_and_reopen'},
    'test_scene_workspace_gui': {'test_reopen_unfinished_review_and_continue_without_reviving_deleted_rows'},
    'test_trial_record_integration': {
        'test_repeated_postures_use_explicit_anchors_and_survive_workspace',
        'test_analytic_wrong_face_retains_g16_intent_and_different_approach',
        'test_partial_capture_can_link_record_but_not_verify_complete_motion',
        'test_handling_record_does_not_promote_air_rotation_to_a_trial',
        'test_hazard_intent_does_not_invent_a_hazard_observation',
    },
    'test_trial_record_gui': {'test_mainapp_record_import_reopen_and_raw_process'},
}
INTERNAL_MODULES = {'test_real_data_flow', 'test_real_drop_posture_physics'}
INTERNAL_POSTURE_METHOD = 'test_real_contact_slice_theta_angles_are_physically_consistent_around_t1'


def evidence_level(module, test_name):
    parts = str(module).replace('\\', '/').replace('/', '.').split('.')
    module = next((part for part in parts if part.startswith('test_')), '')
    name = test_name.split('::')[-1].split('[')[0]
    if module in INTERNAL_MODULES or (module == 'test_drop_posture_post_processor' and name == INTERNAL_POSTURE_METHOD):
        return 'internal_real'
    return 'synthetic_integration' if name in SYNTHETIC_TESTS.get(module, ()) else 'unit_contract'


def summarize_junit(path, *, public_required=False):
    levels = {name: {'level': number, 'testcases': [], 'counts': {state: 0 for state in
              ('passed', 'failed', 'error', 'skipped')}} for number, name in
              ((1, 'unit_contract'), (2, 'synthetic_integration'), (3, 'public_external'), (4, 'internal_real'))}
    levels['public_external'].update(status='optional-manual', release_gate_satisfied=False,
                                    meaning='Public external data requires separate source and scope review.')
    levels['internal_real'].update(status='pending', issue='#104', release_gate_satisfied=False,
                                  meaning='Internal consistency observations; independently calibrated accuracy is pending.')
    report = {'report_version': 1, 'source_junit': str(Path(path).resolve()),
              'public_required': public_required, 'levels': levels, 'unclassified': [], 'errors': []}
    try:
        cases = ET.parse(path).getroot().findall('.//testcase')
    except (OSError, ET.ParseError) as error:
        report['errors'].append(f'JUnit cannot be read: {error}')
        cases = []
    if not cases:
        report['errors'].append('JUnit contains no testcases.')
    for case in cases:
        labels = [prop.get('value') for prop in case.findall('./properties/property')
                  if prop.get('name') == 'evidence_level']
        level = labels[0] if len(labels) == 1 else None
        classname, name = case.get('classname', ''), case.get('name', '')
        identity = f'{classname}::{name}'
        status = next((state for tag, state in (('error', 'error'), ('failure', 'failed'), ('skipped', 'skipped'))
                       if case.find(tag) is not None), 'passed')
        entry = {'name': identity, 'status': status, 'evidence_level': level}
        if level not in levels:
            report['unclassified'].append(entry)
            report['errors'].append(f'{identity}: missing, duplicate or unsupported evidence_level {level!r}.')
        else:
            levels[level]['testcases'].append(entry)
            levels[level]['counts'][status] += 1
            if level != evidence_level(classname, name):
                report['errors'].append(f'{identity}: evidence_level does not match its declared test scope.')
            if public_required and level in ('public_external', 'internal_real'):
                report['errors'].append(f'{identity}: {level} cannot satisfy the required public software gate.')
        if status in ('failed', 'error') or (public_required and status == 'skipped'):
            report['errors'].append(f'{identity}: {status}.')
    if public_required:
        for level in ('unit_contract', 'synthetic_integration'):
            if not levels[level]['testcases']:
                report['errors'].append(f'Required level {level} has no testcases.')
    report['status'] = 'fail' if report['errors'] else 'pass'
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--junit', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--public-required', action='store_true')
    args = parser.parse_args(argv)
    source, target = Path(args.junit), Path(args.output)
    if source.resolve() == target.resolve() or (source.exists() and target.exists() and source.samefile(target)):
        parser.error('Summary output must not overwrite the source JUnit (including file aliases).')
    report = summarize_junit(args.junit, public_required=args.public_required)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, indent=2, allow_nan=False), encoding='utf-8')
    for level in ('unit_contract', 'synthetic_integration'):
        data = report['levels'][level]
        print(f"Level {data['level']} {level}: {data['counts']}")
    print(f"Public evidence summary: {report['status']} ({target}); Level 3 public_external optional-manual; "
          'Level 4 internal_real pending independent calibration #104.')
    raise SystemExit(0 if report['status'] == 'pass' else 1)


if __name__ == '__main__':
    main()
