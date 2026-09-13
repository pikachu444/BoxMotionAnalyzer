"""Independently specified kinematic challenge inputs for conditional axis review.

Generation never imports analysis code. The CLI loads its offline oracle only
after the production detector has returned. These are not measured captures.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

import numpy as np

from .corruption_export import _write_observed, _write_truth
from .marker_fixtures import validate_profile


SPEC_PATH = Path(__file__).parent / 'fixtures' / 'continuity_challenge.json'


def read_spec():
    return json.loads(SPEC_PATH.read_text(encoding='utf-8'))


def _axis_rotation(axis, angle):
    axis = np.asarray(axis, dtype=float)
    axis = axis / np.linalg.norm(axis)
    x, y, z = axis
    skew = np.array([[0., -z, y], [z, 0., -x], [-y, x, 0.]])
    return np.eye(3) + np.sin(angle) * skew + (1 - np.cos(angle)) * (skew @ skew)


def _ease(u):
    return 10 * u**3 - 15 * u**4 + 6 * u**5


def make_recording(recording_id):
    spec = read_spec()
    recording = next(row for row in spec['recordings'] if row['id'] == recording_id)
    profile = spec['profile']
    family = spec['families'][recording['family']]
    n, dt = spec['sampling']['sample_count'], spec['sampling']['dt_s']
    frames = np.arange(n)
    times = frames * dt
    origins, angles = np.zeros((n, 3)), np.zeros((n, 3))
    knots = family['knot_frames']
    for j, (start, end) in enumerate(zip(knots, knots[1:])):
        s = _ease((frames[start:end + 1] - start) / (end - start))[:, None]
        for destination, source in ((origins, family['origin_mm']), (angles, family['angles_xyz_deg'])):
            destination[start:end + 1] = (1 - s) * np.asarray(source[j]) + s * np.asarray(source[j + 1])
    rotations = np.array([_axis_rotation([1, 0, 0], a) @ _axis_rotation([0, 1, 0], b)
                         @ _axis_rotation([0, 0, 1], c) for a, b, c in np.radians(angles)])
    if recording.get('true_motion_extra'):
        extra = recording['true_motion_extra']
        start, end = extra['frame_start'], extra['frame_end']
        for i in range(start, n):
            angle = np.pi * _ease(min(1., (i - start) / (end - start)))
            rotations[i] = rotations[i] @ _axis_rotation([0, 1, 0], angle)
    observed_rotations = rotations.copy()
    events = list(recording.get('events', []))
    if recording_id == 'recording_03':
        events = [{'frame': 112, 'time_s': .896, 'axis': 'X'}]
    half_turns = {axis: np.asarray(spec['corruption_algebra']['H_' + axis]) for axis in 'XYZ'}
    for event in events:
        observed_rotations[event['frame']:] = observed_rotations[event['frame']:] @ half_turns[event['axis']]
    for override in recording.get('solved_state_overrides', []):
        if 'frames_half_open' not in override:
            continue
        start, end = override['frames_half_open']
        matrix = (_axis_rotation([1, 0, 0], np.pi / 2) if override['F'] == 'Rx(pi/2)'
                  else _axis_rotation([1, 2, 3], np.pi / 3))
        observed_rotations[start:end] = rotations[start:end] @ matrix
    local = np.asarray([marker['xyz_mm'] for marker in profile['markers']])
    truth_markers = np.einsum('nij,mj->nmi', rotations, local) + origins[:, None, :]
    observed = np.einsum('nij,mj->nmi', observed_rotations, local) + origins[:, None, :]
    observed += np.random.Generator(np.random.PCG64(recording['seed'])).normal(
        0., recording['noise_sigma_mm'], observed.shape)
    for mask in recording.get('masks', []):
        start, end = mask['frames_half_open']
        if mask['kind'] == 'freeze':
            observed[start:end] = observed[mask['source_frame']]
        else:
            indices = (list(range(len(local))) if mask['marker_ids'] == 'all' else
                       [i for i, marker in enumerate(profile['markers']) if marker['id'] not in ('F1', 'B1')])
            observed[start:end, indices] = np.nan
    if recording.get('position_override'):
        override = recording['position_override']
        start, end = override['frames_half_open']
        observed[start:end] += override['observed_origin_offset_mm']
    manifest = {
        'schema_version': 1, 'generator_version': 'continuity-challenge-1',
        'source_kind': 'handcrafted_dummy', 'evidence_level': 'synthetic_integration',
        'case_id': recording_id, 'seed': recording['seed'], 'profile': profile,
        'layout_hash': validate_profile(profile), 'parameters': {'scenario': 'prescribed_kinematics'},
        'events': [dict(kind='solver_pose_half_turn', **event) for event in events],
        'expected_recommendation': [{'time_s': e['time_s'], 'axis': e['axis']} for e in events],
        'recommendation_contract': 'conditional-continuity-v1', 'expected_approval': False,
        'pose_tolerances': {'position_mm': .1, 'rotation_deg': .1},
        'spec_sha256': hashlib.sha256(SPEC_PATH.read_bytes()).hexdigest(),
        'oracle_interpretations': recording.get('oracle_interpretations', []),
        'physical_channels': 'omitted',
        'scope': 'Conditional continuity hypotheses on prescribed kinematics; no dynamics or real accuracy claim.',
    }
    return {'frame': frames, 'time_s': times, 'body_origin_mm': origins,
            'com_mm': origins.copy(), 'rotation_matrix': rotations, 'truth_markers': truth_markers,
            'rigid_body_markers': observed, 'manifest': manifest}


def write_recording(output, recording_id):
    data = make_recording(recording_id)
    root = Path(output) / recording_id
    root.mkdir(parents=True, exist_ok=False)
    _write_observed(root / 'observed.csv', data, data['manifest']['profile'], include_physical=False)
    _write_truth(root, data, data['manifest']['profile'])
    manifest = data['manifest']
    manifest['files'] = {name: hashlib.sha256((root / name).read_bytes()).hexdigest()
                         for name in ('observed.csv', 'truth_pose.csv', 'truth_markers.csv')}
    if manifest['oracle_interpretations']:
        # Independent sampled truth for the second physical interpretation.
        # The continuous interpolation is specified in the frozen oracle.
        alternate = data['rotation_matrix'].copy()
        alternate[112:] = alternate[112:] @ np.diag([1., -1., -1.])
        np.savetxt(root / 'truth_actual_intersample_turn.csv', np.column_stack((
            data['frame'], data['time_s'], data['body_origin_mm'], alternate.reshape(-1, 9))),
            delimiter=',', header='frame,time_s,body_x_mm,body_y_mm,body_z_mm,'
            + ','.join(f'r{i}{j}' for i in range(3) for j in range(3)), comments='')
        manifest['files']['truth_actual_intersample_turn.csv'] = hashlib.sha256(
            (root / 'truth_actual_intersample_turn.csv').read_bytes()).hexdigest()
    manifest['generator_source_sha256'] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    manifest['exporter_source_sha256'] = hashlib.sha256((Path(__file__).parent / 'corruption_export.py').read_bytes()).hexdigest()
    repository = Path(__file__).resolve().parents[2]
    manifest['code_revision'] = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=repository, text=True).strip()
    manifest['working_tree_dirty'] = bool(subprocess.check_output(['git', 'status', '--porcelain'], cwd=repository, text=True).strip())
    (root / 'observed.synthetic.json').write_text(json.dumps(manifest, indent=2, allow_nan=False), encoding='utf-8')
    return root


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True)
    parser.add_argument('--case', default='all', choices=['all', *[r['id'] for r in read_spec()['recordings']]])
    args = parser.parse_args(argv)
    # Keep generation independent of detector imports and output.
    from .validate_marker_fixtures import _validate_run
    from src.analysis.pipeline.marker_flip import candidate_to_decision, serialize_marker_corrections
    results = []
    names = [r['id'] for r in read_spec()['recordings']] if args.case == 'all' else [args.case]
    for name in names:
        root = write_recording(args.output, name)
        result, context = _validate_run(root, profile=read_spec()['profile'], invocation={
            'kind': 'cli', 'module': 'src.simulation.continuity_fixtures',
            'argv': list(sys.argv[1:] if argv is None else argv), 'python_executable': sys.executable})
        initial = [candidate_to_decision(candidate) for candidate in context['candidates']]
        result['initial_review_decisions'] = json.loads(serialize_marker_corrections(initial))
        result['checks']['initial_decisions_off'] = all(not decision.approved and decision.axis is None for decision in initial)
        result['status'] = 'pass' if all(result['checks'].values()) else 'fail'
        (root / 'validation.json').write_text(json.dumps(result, indent=2, allow_nan=False), encoding='utf-8')
        # Persist computed values for independent audit; do not rerun refits.
        context['pose'].to_csv(root / 'computed_pose.csv')
        (root / 'candidate_evidence.json').write_text(json.dumps(
            [json.loads(c.evidence_json()) for c in context['candidates']], indent=2, allow_nan=False), encoding='utf-8')
        results.append(result)
        print(json.dumps({'case': name, 'status': result['status'], 'checks': result['checks'],
                          'recommendations': [c['recommendation'] for c in result['candidates']]}), flush=True)
    (Path(args.output) / 'validation_summary.json').write_text(json.dumps(results, indent=2, allow_nan=False), encoding='utf-8')
    raise SystemExit(0 if all(result['status'] == 'pass' for result in results) else 1)


if __name__ == '__main__':
    main()
