"""Build immutable public analytic capture assets, without detector/optimizer.

Paths, motions, unavailable rows and approvals are explicit test definitions.
No generated observation is experimental data. All reference poses are derived
from the formula here, never from processing output. Existing files are refused.
"""
from __future__ import annotations

import argparse
import copy
from pathlib import Path

import numpy as np

from src.analysis.regression.contracts import (envelope, anchor, boundary, file_digest,
    write_new_json, marker_semantics, metric)
from src.analysis.pipeline.data_loader import DataLoader
from src.config.config_analysis_ui import get_raw_mode_options
from .corruption_export import write_observations
from .marker_fixtures import example_profile, validate_profile
from src.utils.marker_profile_identity import profile_identity

VERSION = 'public-analytic-corpus-v2'
SEED = 135001
CASES = ('two_drops', 'supported_H', 'handling_only', 'tracking_OFF', 'partial', 'two_flips')
# Frozen, reviewed detector boundaries are preservation expectations only. They
# are not labels of physical truth or automatic include/scenario decisions.
DETECTED_INTERVALS = dict(two_drops=[(0,180)], supported_H=[(0,18),(18,73),(73,80)],
    handling_only=[(0,18),(18,63),(63,80)], tracking_OFF=[(0,30),(30,33),(33,54),(54,56),(56,80)],
    partial=[(0,60)], two_flips=[(0,71),(71,72)])
APPROVAL = dict(status='approved', reviewer='requirements_review', date='2026-10-02',
    basis='Independent read-only formula/geometry/replay review and two frozen proposed-gate '
          'fresh probes with zero numerical variation; public test-only software approval. '
          'v2 observed_first_contact / censored Compare first_contact meaning migration reviewed separately. '
          'No experimental, ISTA, native GUI or full execution approval. See capture_regression.md.')
TOLERANCE = dict(version='public-analytic-corpus-v1', approval=APPROVAL,
    basis='Noiseless analytic software acceptance: 0.1 mm/0.1 deg existing pose bounds; '
          'corner 0.35 mm = center bound + 123.3 mm radius * sin(0.1 deg); '
          'event bracket 0.01 s sampling, bound 1e-8 s preserves a sample, not event uncertainty; '
          'precontact 0.005 m/s is a separate stricter noiseless accuracy gate (the '
          '5-point quadratic endpoint derivative +/-0.1mm worst bound is 0.0228571 m/s); '
          'spin 0.01 rad/s is a separate stricter noiseless software gate (the worst '
          '+/-0.1 deg endpoint propagation over 0.04 s is 0.0873 rad/s); '
          'repeat variation measured in execution report, not used to enlarge bounds.',
    bounds={k: dict(absolute=v, relative=0.) for k, v in dict(center_mm=.1, rotation_deg=.1,
        corner_mm=.35, height_mm=.35, time_s=1e-8, velocity_m_s=.005, angular_rad_s=.01,
        diagnostic_deg=.1, diagnostic_mm=.35).items()})


def specified_case(case):
    n = 180 if case == 'two_drops' else 60 if case == 'partial' else 72 if case == 'two_flips' else 80
    r = np.arange(n)
    t = 10. + .01 * r
    center = np.column_stack((17. + .2 * r, np.full(n, 280.), 11. + .03 * r))
    rotations = np.repeat(np.eye(3)[None], n, axis=0)
    valid = np.ones(n, bool)
    faults, flips = [], []
    ranges = [(0, n)]
    if case == 'two_drops':
        ranges = [(0, 80), (100, 180)]
        for start, end in ranges:
            tau = np.maximum(0, (r[start:end] - start - 8) * .01)
            center[start:end, 1] = np.maximum(60., 280. - .5 * 9806.65 * tau ** 2)
        center[80:100, 1] = np.linspace(60., 280., 20)
    elif case == 'supported_H':
        angle = np.where(r < 20, 0., np.where(r < 50, (r - 20) / 30 * .2,
                         np.where(r < 70, (70 - r) / 20 * .2, 0.)))
        c, s = np.cos(angle), np.sin(angle)
        rotations[:, 0, 0] = rotations[:, 1, 1] = c
        rotations[:, 1, 0], rotations[:, 0, 1] = s, -s
        center[:, 0] = -100 + 100 * c - 60 * s
        center[:, 1] = 100 * s + 60 * c
        center[:, 2] = 11.
    elif case == 'handling_only':
        center[:, 0] = 17 + 100 * np.clip((r - 20) / 40, 0., 1.)
        ranges = []
    elif case == 'tracking_OFF':
        faults = [dict(kind='missing', channel='rigid_body_markers', start_index=30, end_index_exclusive=33),
                  dict(kind='flip_180_local_axis', channel='rigid_body_markers', start_index=55, axis='X')]
        valid[30:33] = False
        # OFF preserves observed half-turn, not lost physical truth. This lane
        # verifies explicit non-correction and unavailable-mask preservation.
        rotations[55:] = np.diag([1., -1., -1.])
        flips = [(55, 'OFF')]
    elif case == 'partial':
        angle = .1 * r * .01
        c, s = np.cos(angle), np.sin(angle)
        rotations[:, 0, 0] = rotations[:, 1, 1] = c
        rotations[:, 1, 0], rotations[:, 0, 1] = s, -s
        # Frozen before production processing: avoid the strict -50 mm/s
        # contact-trend boundary and its floating-point equality ambiguity.
        center[:, 1] = 400. - 60. * r * .01
    elif case == 'two_flips':
        faults = [dict(kind='flip_180_local_axis', channel='rigid_body_markers', start_index=i, axis=a)
                  for i, a in ((20, 'X'), (48, 'Y'))]
        flips = [(20, 'X'), (48, 'Y')]
    return t, center, rotations, valid, faults, flips, ranges


def independent_corners(center, rotations):
    # Explicit historic C1..C8 geometry; no production corner function import.
    local = np.array([[-100,-60,-40], [100,-60,-40], [100,60,-40], [-100,60,-40],
                      [-100,-60,40], [100,-60,40], [100,60,40], [-100,60,40]], float)
    return np.einsum('nij,kj->nki', rotations, local) + center[:, None]


def independent_metrics(case, times, center, rotations, start, end):
    result = dict(t1=metric(status='unavailable' if case == 'tracking_OFF' else 'not_detected'),
                  t2=metric(status='unavailable' if case == 'tracking_OFF' else 'not_detected'),
                  reference_face=metric('BOTTOM'))
    angles = np.degrees(np.arccos(np.clip((np.trace(rotations[start].T @ rotations[start:end], axis1=1, axis2=2) - 1) / 2, -1, 1)))
    result.update(final_rotation_deg=dict(**metric(float(angles[-1])), tolerance='diagnostic_deg'),
                  maximum_rotation_deg=dict(**metric(float(angles.max())), tolerance='diagnostic_deg'))
    beta = np.degrees(np.arccos(np.clip(rotations[start:end,1,1],-1,1)))
    long = np.degrees(np.arcsin(np.clip(rotations[start:end,1,0],-1,1)))
    short = np.degrees(np.arcsin(np.clip(rotations[start:end,1,2],-1,1)))
    dh = 200*np.abs(rotations[start:end,1,0])+80*np.abs(rotations[start:end,1,2])
    for key,value,bound in [('MaxBetaDeg',np.max(beta),'diagnostic_deg'),
        ('MaxAbsThetaLongDeg',np.max(np.abs(long)),'diagnostic_deg'),
        ('MaxAbsThetaShortDeg',np.max(np.abs(short)),'diagnostic_deg'),
        ('MaxDeltaH_mm',np.max(dh),'diagnostic_mm')]:
        result[key]=dict(**metric(float(value)), tolerance=bound)
    # Formula-defined precontact sample, not force-onset truth.
    if case == 'two_drops':
        pre = start + 29
        result['t1'] = dict(**metric(float(times[pre])), tolerance='time_s')
        result['contact_state'] = metric('ImpactEvent')
        result['impact_sequence'] = metric('{C1,C2,C5,C6}')
        result['vertical_velocity'] = dict(**metric(-9.80665 * .21), tolerance='velocity_m_s')
        result['horizontal_speed'] = dict(**metric(float(np.hypot(.02, .003))), tolerance='velocity_m_s')
        result['angular_speed'] = dict(**metric(0.), tolerance='angular_rad_s')
        for key, unit in (('BetaAtT1MinusDeg', 'diagnostic_deg'), ('ThetaLongAtT1MinusDeg', 'diagnostic_deg'),
                          ('ThetaShortAtT1MinusDeg', 'diagnostic_deg'), ('DeltaHAtT1Minus_mm', 'diagnostic_mm')):
            result[key] = dict(**metric(0.), tolerance=unit)
    elif case == 'supported_H':
        result['contact_state'] = metric('SustainedContact')
    elif case == 'tracking_OFF':
        result['contact_state'] = metric('Unavailable')
    elif case == 'partial':
        result['contact_state'] = metric('Approach')
    else:
        result['contact_state'] = metric('NoContact')
    # Unknown/unconfirmed test item and absent COM applicability never become
    # an equivalent-height value. Missing kinematics are not numerical zeros.
    result['equivalent_height'] = metric(status='unavailable')
    result['final_face'] = metric(status='unavailable')
    if case != 'two_drops':
        for key in ('vertical_velocity', 'horizontal_speed', 'angular_speed', 'first_contact', 'contact_confidence'):
            result[key] = metric(status='unavailable')
        for key in ('BetaAtT1MinusDeg', 'ThetaLongAtT1MinusDeg', 'ThetaShortAtT1MinusDeg', 'DeltaHAtT1Minus_mm'):
            result[key] = metric(status='unavailable')
    else:
        # These manually selected intervals subdivide one continuous activity
        # (nonzero horizontal motion starts at the capture boundary). Preserve
        # recorded-first-event-consistency-v1's conservative censor gate.
        result['first_contact'] = metric(status='unavailable', reason='Explicit censored review interval; Compare gate preserved')
    result['observed_first_contact'] = metric('{C1,C2,C5,C6}') if case == 'two_drops' else metric(status='unavailable')
    return result


def build_corpus(output):
    root = Path(output).resolve()
    root.mkdir(parents=True, exist_ok=False)
    profile = example_profile()
    geometry = dict(box_dims_mm=profile['box_dims_mm'], floor_y_mm=0., vertical_axis='Y', position_units='mm',
        world_frame='world-y-up', local_frame='box-xyz', rotation_convention='local-to-world-matrix',
        origin_to_geocenter_mm=[0., 0., 0.], origin_to_com_mm=[0., 0., 0.], world_transform=np.eye(4).tolist())
    entries, approved_ids = [], []
    for case in CASES:
        times, center, rotations, valid, faults, flips, ranges = specified_case(case)
        observed_rotation = rotations.copy()
        if case == 'tracking_OFF':
            observed_rotation[:] = np.eye(3)  # exporter applies the separately specified fault
        trajectory = dict(schema_version=1, source_kind='handcrafted_dummy',
            coordinate_policy='world-y-up-box-local-fixed-center-v1', frame=(1000 + np.arange(len(times)) * 3).tolist(),
            time_s=times.tolist(), body_origin_mm=center.tolist(), rotation_matrix=observed_rotation.tolist())
        directory = write_observations(root / case, trajectory, profile, dict(schema_version=1, events=faults), SEED)
        raw_path = directory / 'observed.csv'
        _, raw = DataLoader().load_csv(str(raw_path))
        scenes = []
        for i, (a, b) in enumerate(DETECTED_INTERVALS[case]):
            bound = anchor(raw, a, b)
            scenes.append(dict(review_id=f'{case}-candidate-{i}', origin='automatic', detected_anchor=bound,
                anchor=bound, edited=False, decision='exclude', test_type='Unknown', scenario_id=None,
                scenario_kind=None, label_status='unconfirmed', evidence='Reviewed detector preservation snapshot, not motion truth',
                slice_mode='record-half-open', padding_rows=5))
        references = {}
        corners = independent_corners(center, rotations)
        for i, (a, b) in enumerate(ranges):
            rid = f'{case}-scene-{i}'
            approved_ids.append(rid)
            scenes.append(dict(review_id=rid, origin='manual', anchor=anchor(raw, a, b), edited=True,
                decision='include', test_type='H' if case == 'supported_H' else 'G' if case == 'two_drops' else 'Unknown',
                scenario_id=None, scenario_kind=None, label_status='unconfirmed',
                evidence='Explicit synthetic interval from analytic test definition; no experimental or ISTA label',
                slice_mode='record-half-open', padding_rows=5))
            def nullable(values):
                v = values[a:b].copy()
                v[~valid[a:b]] = np.nan
                return np.where(np.isfinite(v), v, None).tolist()
            references[rid] = dict(trajectory=dict(original_record_index=list(range(a, b)), raw_time_s=times[a:b].tolist(),
                geocenter_position_mm=nullable(center), rotation_matrix=nullable(rotations), corners_mm=nullable(corners),
                floor_height_mm=nullable(corners[:, :, 1]), valid_mask=valid[a:b].tolist()),
                metrics=independent_metrics(case, times, center, rotations, a, b),
                event_uncertainty_s=.01, event_basis='Independent prescribed geometry; geometric sample contract, not force/physical accuracy')
        raw_hash = file_digest(raw_path)
        ref = envelope('TrajectoryReference', raw_sha256=raw_hash, geometry=geometry, approval=APPROVAL,
            generator=VERSION, seed=SEED, sample_count=len(times), scenes=references,
            basis='Explicit analytic center/rotation and C1..C8 corner formulas; tracking OFF uses specified observed constraints')
        ref_path = directory / 'reference.json'
        write_new_json(ref_path, ref)
        decisions = [dict(review_id=f'{case}-flip-{i}', original_record_index=row, raw_time_s=float(times[row]),
                          anchor=anchor(raw, row, row + 1), axis=axis, mapping_status='source_bound')
                     for i, (row, axis) in enumerate(flips)]
        fixture = envelope('CaptureReviewFixture', case_id=case, raw_sha256=raw_hash, raw_root_kind='public_synthetic',
            relative_path=f'{case}/observed.csv', capture_time_field='Time', capture_end_raw_time_s=boundary(times, len(times)),
            marker_profile_id=profile['profile_id'], marker_profile_hash=validate_profile(profile),
            marker_profile=profile, marker_semantics=marker_semantics(), geometry=geometry,
            marker_profile_identity=profile_identity(profile),
            test_type='H' if case == 'supported_H' else 'G' if case == 'two_drops' else 'Unknown',
            type_source='Explicit test-only motion template, no mass/filename inference',
            flip_decisions=decisions, marker_correction_default='OFF', scene_decisions=scenes,
            effective_processing_config=dict(processing_mode='raw', analysis_options=get_raw_mode_options(), enable_result_resampling=False),
            approval=APPROVAL, reference=dict(relative_path=f'{case}/reference.json', sha256=file_digest(ref_path)),
            tolerance=TOLERANCE)
        write_new_json(directory / 'review.json', fixture)
        entries.append(dict(case_id=case, fixture=f'{case}/review.json'))
    manifest = envelope('CaptureCorpus', version=VERSION, cases=entries, approved_scene_ids=approved_ids,
        baseline_migration=dict(previous_version='public-analytic-corpus-v1',
            old=dict(first_contact='{C1,C2,C5,C6}'),
            new=dict(observed_first_contact='{C1,C2,C5,C6}', first_contact='unavailable'),
            cause='Separate recorded geometric contact from censored Compare first-event eligibility',
            impact='No pose, numeric expectation, tolerance, raw or scene-boundary changes',
            review=dict(reviewer='requirements_review', date='2026-10-02', status='approved'),
            preservation='v1 assets and failed full_01 are retained as immutable local execution evidence'),
        approval=APPROVAL, measured_data_status='unavailable', calibration_status='pending',
        source_kind='public handcrafted analytic synthetic; not experimental data')
    write_new_json(root / 'corpus.json', manifest)
    return root / 'corpus.json'


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, help='New local asset directory, never overwrite baselines.')
    args = parser.parse_args(argv)
    print(build_corpus(args.output))


if __name__ == '__main__':
    main()
