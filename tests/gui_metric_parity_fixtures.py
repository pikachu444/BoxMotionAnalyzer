"""Public analytic observations and predeclared numerical limits for P07.

Generation writes no fitted output and invokes no analysis optimizer. The two
files are synthetic integration cases, not independent experimental repeats.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np

from src.simulation.corruption_export import write_observations
from src.simulation.marker_fixtures import example_profile


GENERATOR_VERSION = 'gui-metric-parity-raw-1'
GENERATOR_SEED = 74082
RAW_SAMPLE_COUNT = 61
SAMPLE_INTERVAL_S = .02
SLICE_START_S, SLICE_END_S = .1, .3
SLICE_PADDING_ROWS = 50
POSITION_ATOL_MM = .05
ORIENTATION_ATOL_RAD = .001
INTERIOR_VELOCITY_ATOL_MM_S = 2.5
ANGLE_ATOL_DEG = .1
FACE_RANGE_ATOL_MM = .25


def generate_raw_metric_parity_inputs(root):
    """Create two new public CSV inputs and a manifest fixed before fitting.

    Consumers receive only ``csv_path`` as production input; the expectation
    and truth files belong to the test oracle and must not enter pose solving.
    ``root`` must be new, so reruns cannot overwrite prior evidence.
    """
    root = Path(root).resolve()
    root.mkdir(parents=True, exist_ok=False)
    profile = example_profile()
    times = np.arange(RAW_SAMPLE_COUNT, dtype=float) * SAMPLE_INTERVAL_S
    frames = np.arange(RAW_SAMPLE_COUNT, dtype=np.int64)
    selected = np.arange(5, 16, dtype=int)
    limits = dict(
        position_max_component_error_mm=POSITION_ATOL_MM,
        orientation_geodesic_error_rad=ORIENTATION_ATOL_RAD,
        interior_velocity_component_error_mm_s=INTERIOR_VELOCITY_ATOL_MM_S,
        whole_window_angle_error_deg=ANGLE_ATOL_DEG,
        fixed_face_height_range_error_mm=FACE_RANGE_ATOL_MM,
        arithmetic_rtol=1e-9,
        arithmetic_atol=1e-9,
        optimizer_options=dict(maxiter=1500, xatol=1e-4, fatol=1e-4),
        basis=(
            'Predeclared numerical regression limits, not optimizer stopping guarantees or physical accuracy. '
            'For central differences at dt=0.02 s, |position error|<=0.05 mm contributes at most '
            '0.05/0.02=2.5 mm/s to each interior velocity component. Boundary samples are excluded. '
            'Orientation error<=0.001 rad bounds a 200-by-80 mm face separation error by '
            'sqrt(200^2+80^2)*0.001<0.216 mm; the frozen range limit is 0.25 mm. '
            'The frozen 0.1 degree angle limit exceeds 0.001*180/pi degrees. '
            'Pure arithmetic/geometry cases retain rtol=atol=1e-9. '
            'No angular-velocity or acceleration error limit is inferred from these values.'
        ),
        failure_policy='Investigate a failed fixed limit; never relax it after observing optimizer output.',
    )
    manifest = dict(
        schema_version=1,
        generator_version=GENERATOR_VERSION,
        generator_source='tests/gui_metric_parity_fixtures.py',
        seed=GENERATOR_SEED,
        provenance='Deterministic analytic public inputs; no capture or processed output used as truth.',
        evidence_level='synthetic_integration',
        experimental_repeat_status='not experimental repeats',
        calibration_status='not measured',
        format=dict(raw_schema='existing public Format Version 1.25 marker CSV',
                    header_levels=['type', 'name', 'id', 'parent', 'category', 'component'],
                    header_length_units='Millimeters', header_coordinate_space='Global',
                    coordinate_policy='world-y-up-box-local-fixed-center-v1',
                    units=dict(position='mm', time='s', velocity='mm/s', rotation='rad'),
                    channels=['Rigid Body Marker solved constraints', 'Marker physical positions'],
                    solved_marker_count=18, physical_marker_count=18,
                    marker_profile=profile),
        input_clock=dict(count=RAW_SAMPLE_COUNT, first_s=0., last_s=1.2,
                         interval_s=SAMPLE_INTERVAL_S, frame_first=0, frame_last=60),
        processing_packet=dict(
            requested_mode='Raw', raw_options_owner='src.config.config_analysis_ui.get_raw_mode_options',
            slice_start_s=SLICE_START_S, slice_end_s=SLICE_END_S,
            inclusive_slice_frame_indices=selected.tolist(), slice_frame_count=11,
            slice_padding_rows=SLICE_PADDING_ROWS, padded_saved_frame_count=61,
            padding_reason='Keep at least 50 parsed rows before the existing early trim; only 11 selected rows are fitted.',
            optimizer_calls_per_case=11, optimizer_calls_total=22,
            actual_optimizer_required=True, optimizer_result_mocking=False,
            accepted_scope='User-approved bounded optimization of the 11 included frames per case; no full-capture campaign.',
        ),
        numerical_limits=limits,
        comparison_notes=[
            'Each generated CSV is loaded and compared through existing public owners.',
            'No reviewed scene window or actual first-impact event is supplied.',
            'BOTTOM is not the maximum-area face of dimensions [200,120,80]; keep broad-face repeat restrictions.',
            'Whole-window individual values remain distinct from eligibility for repeat statistics.',
        ],
        cases=[],
    )
    cases = []
    for case_id, height_offset, angle_deg in [
        ('affine_identity', 0., 0.),
        ('affine_offset_tilt', 1000., 30.),
    ]:
        # The second rotation is a literal analytic matrix, not fitted output.
        c, s = (1., 0.) if angle_deg == 0. else (np.sqrt(3.) / 2., .5)
        matrix = np.array([[c, -s, 0.], [s, c, 0.], [0., 0., 1.]])
        positions = np.column_stack((10. + 200. * times,
                                     1000. + height_offset + 100. * times,
                                     np.zeros(RAW_SAMPLE_COUNT)))
        rotations = np.repeat(matrix[None, :, :], RAW_SAMPLE_COUNT, axis=0)
        trajectory = dict(schema_version=1, source_kind='handcrafted_dummy',
                          coordinate_policy='world-y-up-box-local-fixed-center-v1',
                          time_s=times, frame=frames, body_origin_mm=positions,
                          rotation_matrix=rotations)
        folder = write_observations(root / case_id, trajectory, profile,
                                    dict(schema_version=1, events=[]), seed=GENERATOR_SEED)
        source = folder / 'observed.csv'
        expected = dict(
            raw_sample_count=RAW_SAMPLE_COUNT,
            raw_times_s=times.tolist(),
            slice_times_s=times[selected].tolist(),
            slice_frames=frames[selected].tolist(),
            slice_positions_mm=positions[selected].tolist(),
            rotation_matrix=matrix.tolist(),
            rotation_vector_rad=[0., 0., angle_deg * np.pi / 180.],
            world_velocity_mm_s=[200., 100., 0.],
            angular_speed_rad_s=0.,
            position_at_0_2_s_mm=[50., 1020. + height_offset, 0.],
            posture=dict(ReferenceFace='BOTTOM', MaxBetaDeg=angle_deg,
                         MaxAbsThetaLongDeg=angle_deg, MaxAbsThetaShortDeg=0.,
                         MaxDeltaH_mm=0. if angle_deg == 0. else 100.),
            contact=dict(ContactState='NoContact', ImpactDetected=False, T1Detected=False,
                         SustainedContactDetected=False, ImpactEventCount=0,
                         ContactConfidence=0., ContactDetectionMethod='none',
                         ImpactSequence='', FirstImpactTimeSec=None, FirstImpactContact=''),
            t1_metric_availability='unavailable: no actual first-impact event',
            final_face_availability='unavailable: only four tail samples after int(0.65*11)',
            repeat_eligibility='not inferred: missing reviewed window and non-maximum-area reference face',
            artifact=dict(SourceKind='handcrafted_dummy', ModelId=profile['profile_id'],
                          ScenarioKind='synthetic_trajectory', IstaType='not_applicable',
                          CoordinatePolicy='world-y-up-box-local-fixed-center-v1',
                          UnitsPolicy='bma-mm-s-rotvec-rad-summary-deg-v1'),
        )
        record = dict(id=case_id, csv_path=source, expected=expected)
        cases.append(record)
        manifest['cases'].append(dict(
            id=case_id,
            observed_csv=source.relative_to(root).as_posix(),
            observed_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
            producer_manifest=(folder / 'observed.synthetic.json').relative_to(root).as_posix(),
            analytic_input=dict(x_mm='10+200*t', y_mm=f'{1000. + height_offset:g}+100*t',
                                z_mm='0', fixed_world_rotation='Rz', fixed_rotation_deg=angle_deg,
                                added_y_offset_mm=height_offset, noise='none', faults=[]),
            expected=expected,
        ))
    manifest_path = root / 'fixture_manifest.json'
    with manifest_path.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(manifest, stream, ensure_ascii=True, indent=2, allow_nan=False)
        stream.write('\n')
    return dict(root=root, manifest_path=manifest_path, cases=cases, manifest=manifest)
