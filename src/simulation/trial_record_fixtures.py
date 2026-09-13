"""Public record-link example with an analytic flight and prescribed floor stop.

The trial record describes test intent; the separate truth describes observations.
No detector output is used to choose record anchors, intent, or expected geometry.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np

from .corruption_export import _write_observed, _write_truth
from .marker_corruption import apply_corruption
from .marker_fixtures import virtual_profile_32


VERSION = '1.0'


def trial_record(source, trials, *, ista_type='H', applied_edition='2018-03', record_id='public-example'):
    """Bind independently authored trial entries to the exact observed CSV."""
    return {'kind': 'boxmotion-trial-record', 'version': 1, 'record_id': record_id,
            'capture': {'sha256': hashlib.sha256(Path(source).read_bytes()).hexdigest(),
                        'basis': 'active', 'time_basis': 'capture_seconds'},
            'ista_type': ista_type, 'applied_edition': applied_edition, 'trials': trials}


def trial(attempt_id, order, anchor, item, *, anchor_kind='release', conditions=None, repeat_of=None):
    entry = {'attempt_id': attempt_id, 'performed_order': order, 'anchor_time_s': anchor,
             'anchor_kind': anchor_kind, 'activity_kind': 'trial' if item else 'handling', 'item': item}
    if conditions is not None:
        entry['conditions'] = conditions
    if repeat_of is not None:
        entry['repeat_of'] = repeat_of
    return entry


def write_analytic_approach(output):
    """61 samples, 125 Hz, a 200 x 120 x 80 mm cuboid; no impact-force model."""
    root = Path(output)
    root.mkdir(parents=True, exist_ok=False)
    profile = virtual_profile_32()
    scale = np.array([200., 120., 80.]) / np.asarray(profile['box_dims_mm'])
    profile['profile_id'] = 'public-analytic-box-200x120x80'
    profile['box_dims_mm'] = [200., 120., 80.]
    profile['source'] = 'Public virtual 32-marker layout scaled by [2/3, 2/3, 8/9]; no measured coordinates.'
    for marker in profile['markers']:
        marker['xyz_mm'] = (np.asarray(marker['xyz_mm']) * scale).tolist()
    times = np.arange(61) * .008
    tau = np.clip(times - .16, 0., .16)
    origins = np.zeros((61, 3))
    origins[:, 1] = 60. + 125.568 - 4905. * tau ** 2
    # The stop is prescribed, with continuous position and discontinuous velocity.
    origins[times >= .32, 1] = 60.
    trajectory = {'schema_version': 1, 'source_kind': 'handcrafted_dummy',
                  'coordinate_policy': 'world-y-up-box-local-fixed-center-v1',
                  'frame': list(range(61)), 'time_s': times.tolist(),
                  'body_origin_mm': origins.tolist(), 'com_mm': origins.tolist(),
                  'rotation_matrix': np.broadcast_to(np.eye(3), (61, 3, 3)).tolist()}
    result = apply_corruption(trajectory, profile, {'schema_version': 1, 'events': []}, seed=75016)
    _write_observed(root / 'observed.csv', result, profile, include_physical=False)
    _write_truth(root, result, profile)
    registration = {'version': 1, 'profile': profile, 'floor_y_mm': 0.,
                    'position_tolerance_mm': 1., 'com_offset_mm': [0., 0., 0.]}
    (root / 'registration.json').write_text(json.dumps(registration, indent=2), encoding='utf-8')
    record = trial_record(root / 'observed.csv', [trial('g16-attempt-1', 1, .32, 'G16',
        anchor_kind='contact', conditions={'critical_face_status': 'selected', 'target_faces': ['LEFT']})],
        ista_type='G', record_id='public-g16-different-approach')
    (root / 'trial_record.json').write_text(json.dumps(record, indent=2), encoding='utf-8')
    truth = {'version': VERSION, 'source_kind': 'handcrafted_dummy', 'evidence_level': 'synthetic_integration',
             'sample_count': 61, 'sample_interval_s': .008, 'box_dims_mm': profile['box_dims_mm'],
             'body_origin': 'geometric centre; prescribed COM at the same point',
             'release_time_s': .16, 'floor_stop_time_s': .32,
             'expected_bottom_clearance_mm': {'0.312': 12.24288, '0.320': 0., '0.328': 0.},
             'observed_approach_faces': ['BOTTOM'], 'recorded_item': 'G16',
             'recorded_target_faces': ['LEFT'], 'expected_approach_agreement': 'different',
             'limitations': 'Analytic gravity flight and prescribed ideal stop. No force, bounce, packaging '
                            'deformation, real capture accuracy, ISTA height or conformity validation.',
             'files_sha256': {name: hashlib.sha256((root / name).read_bytes()).hexdigest()
                              for name in ('observed.csv', 'registration.json', 'trial_record.json',
                                           'truth_pose.csv', 'truth_markers.csv')}}
    (root / 'truth_events.json').write_text(json.dumps(truth, indent=2), encoding='utf-8')
    return root


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, help='A new directory for the public example.')
    args = parser.parse_args()
    print(write_analytic_approach(args.output))


if __name__ == '__main__':
    main()
