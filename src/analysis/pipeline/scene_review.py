"""Operator review of observed intervals; trial identity is a separate decision.

The catalogue is a posture lookup from ISTA 6-Amazon.com-SIOC 2018-03,
pp. 26, 28, 45–46. It cannot establish eligibility, sequence or applied edition.
"""
from copy import deepcopy
from dataclasses import asdict
import json
import math

import numpy as np

from src.analysis.pipeline.scene_detection import VERSION
from src.analysis.pipeline.support_motion import support_motion_evidence
from src.config.config_app import FACE_DEFINITIONS


REFERENCE_EDITION = '2018-03'
REFERENCE_URL = ('https://d39w7f4ix9f5s9.cloudfront.net/32/98/'
                 'c52dd6b841f18bcb8af679b1f1ac/9.TESTING_thumbnail_ISTA%20Project%206-Amazon.com-SIOC%2018-18.pdf')
FACE_NUMBERS = {
    'G': {'BACK': 1, 'BOTTOM': 2, 'FRONT': 3, 'TOP': 4, 'RIGHT': 5, 'LEFT': 6},
    'H': {'TOP': 1, 'BACK': 2, 'BOTTOM': 3, 'FRONT': 4, 'RIGHT': 5, 'LEFT': 6},
}
G_POSTURES = [(3, 4), (3, 6), (4, 6), (3, 4, 6), (2, 3, 5), (2, 3), (1, 2),
              (3,), (3,), (3, 4), (3, 6), (1, 5), (3, 4, 6), (1, 2, 6), (1, 4, 5)]
H_POSTURES = {
    'B04': [(1,), (2,), (6,), (2, 3, 5), (3, 4), (3,)],
    'B16': [(2, 3), (3, 4, 6), (4, 5), (1, 4, 6), (1, 6), (3,)],
}


def empty_identity(ista_type='Unknown', applied_edition=None):
    return {'ista_type': ista_type, 'scenario_id': None, 'scenario_kind': None,
            'confirmed': False, 'reference_edition': REFERENCE_EDITION,
            'applied_edition': applied_edition}


def validate_scene_review_json(value, *, start=None, end=None):
    if value is None or value == '':
        return ''
    data = json.loads(value) if isinstance(value, str) else deepcopy(value)
    if not isinstance(data, dict) or data.get('version') != 1:
        raise ValueError('Unsupported scene review metadata.')
    candidate = data['candidate']
    a, b = float(candidate['start']), float(candidate['end'])
    if not (math.isfinite(a) and math.isfinite(b) and a <= b):
        raise ValueError('Invalid reviewed scene range.')
    if candidate.get('decision') != 'include':
        raise ValueError('Only an included scene can be saved or processed.')
    if candidate.get('evidence_status') not in ('current', 'range_changed', 'geometry_changed'):
        raise ValueError('Unknown scene evidence status.')
    if (start is not None and a != float(start)) or (end is not None and b != float(end)):
        raise ValueError('Scene review and slice ranges do not match.')
    if not isinstance(data.get('source_sha256'), str) or len(data['source_sha256']) != 64:
        raise ValueError('Scene review needs the capture SHA-256.')
    identity = data['identity']
    if identity.get('ista_type') not in ('Unknown', 'G', 'H'):
        raise ValueError('Invalid scene Type.')
    if not isinstance(identity.get('confirmed'), bool):
        raise ValueError('Invalid scene identity confirmation.')
    if identity['confirmed'] and (not identity.get('scenario_id') or not identity.get('scenario_kind')
                                  or identity['ista_type'] == 'Unknown' or not identity.get('applied_edition')):
        raise ValueError('Confirmed identity needs Type, item, kind and applied edition.')
    if candidate['evidence_status'] != 'current' and identity['confirmed']:
        raise ValueError('Changed evidence cannot retain a confirmed identity.')
    return json.dumps(data, sort_keys=True, separators=(',', ':'), allow_nan=False)


def _feature(corners, tolerance_m):
    """Lowest geometric feature, without claiming a measured contact force."""
    heights = corners[:, 1]
    ids = set(np.flatnonzero(heights <= heights.min() + tolerance_m).tolist())
    faces = sorted(name for name, definition in FACE_DEFINITIONS.items()
                   if ids.issubset(set(definition['corners'])))
    if (len(ids), len(faces)) not in ((1, 3), (2, 2), (4, 1)):
        return None
    return {'kind': {1: 'corner', 2: 'edge', 4: 'face'}[len(ids)], 'faces': faces,
            'corners': sorted(ids)}


def geometry_evidence(result, row):
    reg = result.registration
    if not reg or reg.floor_y_mm is None or result.corners_m is None:
        return {'status': 'registration_required'}
    times = result.signals.index.to_numpy(float)
    selected = np.flatnonzero((times >= row['start']) & (times <= row['end']))
    floor, tol = reg.floor_y_mm / 1000., reg.position_tolerance_mm / 1000.
    heights = np.full(len(times), np.nan)
    heights[result.valid_pose] = result.corners_m[result.valid_pose, :, 1].min(axis=1) - floor
    crossings = []
    for i in selected:
        if i == 0 or not (result.valid_pose[i - 1] and result.valid_pose[i]):
            continue
        if result.block_ids[i - 1] != result.block_ids[i] or i - 1 not in selected:
            continue
        if heights[i - 1] > tol and heights[i] <= tol:
            crossings.append({'time_before': float(times[i - 1]), 'time_after': float(times[i]),
                              'approach_feature': _feature(result.corners_m[i - 1], tol),
                              'height_after_mm': float(heights[i] * 1000.)})
    finite = selected[np.isfinite(heights[selected])]
    return {'status': 'registered', 'floor_y_mm': reg.floor_y_mm,
            'position_tolerance_mm': reg.position_tolerance_mm,
            'floor_crossings': crossings,
            'near_floor_fraction': float(np.mean(np.abs(heights[finite]) <= tol)) if len(finite) else None}


class SceneReviewSession:
    def __init__(self, result, source_sha256):
        self.result = result
        self.source_sha256 = source_sha256
        self.ista_type = 'Unknown'
        self.applied_edition = None
        self.rows = [self._row(c) for c in result.candidates]
        self.deleted_ids = set()
        self.manual_serial = 0

    def _row(self, candidate):
        row = asdict(candidate)
        row['left_censored'], row['right_censored'] = bool(row['left_censored']), bool(row['right_censored'])
        row.update(auto_start=row['start'], auto_end=row['end'], origin='automatic',
                   decision='unreviewed', evidence_status='current', identity=empty_identity(),
                   item_candidates=[], geometry={})
        # The event interval denotes accepted gravity-window centres, not release/contact.
        row['gravity_evidence_start'] = row.pop('event_start')
        row['gravity_evidence_end'] = row.pop('event_end')
        row['motion_geometry'] = support_motion_evidence(self.result, row)
        return row

    @property
    def all_reviewed(self):
        return bool(self.rows) and all(r['decision'] in ('include', 'exclude') for r in self.rows)

    def row(self, row_id):
        return next(r for r in self.rows if r['id'] == row_id)

    def _reset_identity(self, row):
        row['identity'] = empty_identity(self.ista_type, self.applied_edition)
        row['item_candidates'], row['geometry'] = [], {}
        row.pop('eligibility_condition', None)
        row.pop('sequence_evidence', None)

    def set_context(self, ista_type, applied_edition):
        applied_edition = applied_edition or None
        if (ista_type, applied_edition) == (self.ista_type, self.applied_edition):
            return
        self.ista_type, self.applied_edition = ista_type, applied_edition
        for row in self.rows:
            self._reset_identity(row)

    def set_decision(self, row_id, decision):
        if decision not in ('unreviewed', 'include', 'exclude'):
            raise ValueError('Invalid scene review decision.')
        row = self.row(row_id)
        if row['decision'] != decision:
            row['decision'] = decision
            self._reset_identity(row)

    def set_range(self, row_id, start, end):
        start, end = float(start), float(end)
        times = self.result.signals.index
        if not (math.isfinite(start) and math.isfinite(end) and times[0] <= start <= end <= times[-1]):
            raise ValueError('Select a finite range inside the capture.')
        row = self.row(row_id)
        if (start, end) == (row['start'], row['end']):
            return
        row.update(start=start, end=end, decision='unreviewed', evidence_status='range_changed')
        row['motion_geometry'] = {'version': 1, 'status': 'range_changed'}
        row.update(gravity_evidence_start=None, gravity_evidence_end=None, gravity_episodes=[],
                   rotation_deg=None, displacement_mm=None, left_censored=False, right_censored=False)
        self._reset_identity(row)

    def add_range(self, start, end):
        self.manual_serial += 1
        row = deepcopy(self.rows[0]) if self.rows else self._row(self.result.candidates[0])
        row.update(id=f'manual_{self.manual_serial:03d}', auto_start=None, auto_end=None,
                   origin='manual', start=float('nan'), end=float('nan'), tags=[],
                   evidence_class='unclear', motion='unclear', rotation_deg=None,
                   displacement_mm=None, gravity_episodes=[])
        self.rows.append(row)
        try:
            self.set_range(row['id'], start, end)
        except Exception:
            self.rows.remove(row)
            raise
        return row['id']

    def remove(self, row_id):
        self.deleted_ids.add(row_id)
        self.rows = [r for r in self.rows if r['id'] != row_id]

    def refresh(self, result):
        """Same source/registration: preserve reviews, edited ranges and removals."""
        old_reg = self.result.registration
        new_reg = result.registration
        same_context = ((old_reg.fingerprint if old_reg else None) == (new_reg.fingerprint if new_reg else None)
                        and result.settings == self.result.settings)
        self.result = result
        for row in self.rows:
            if not same_context:
                row['decision'], row['evidence_status'] = 'unreviewed', 'geometry_changed'
                self._reset_identity(row)
            if row['evidence_status'] != 'current':
                # A changed interval receives new evidence only when it contains
                # a complete detected active interval. No evidence crosses its bounds.
                contained = [c for c in result.candidates if row['start'] <= c.start and c.end <= row['end']
                             and c.motion != 'stationary']
                row['evidence_class'] = contained[0].evidence_class if len(contained) == 1 else 'unclear'
                row['motion'] = contained[0].motion if len(contained) == 1 else 'unclear'
                row['gravity_episodes'] = [e for c in contained for e in c.gravity_episodes]
                row['gravity_evidence_start'] = min((e['gravity_evidence_start'] for e in row['gravity_episodes']), default=None)
                row['gravity_evidence_end'] = max((e['gravity_evidence_end'] for e in row['gravity_episodes']), default=None)
                overlapping = [c for c in result.candidates if c.start <= row['end'] and c.end >= row['start']
                               and c.motion != 'stationary']
                row['left_censored'] = any(c.start < row['start'] < c.end or c.left_censored for c in overlapping)
                row['right_censored'] = any(c.start < row['end'] < c.end or c.right_censored for c in overlapping)
                row['boundary_uncertainty_s'] = max((c.boundary_uncertainty_s for c in overlapping), default=0.)
                row['evidence_status'] = 'current'
                row['rotation_deg'] = None
                row['displacement_mm'] = None
                row['tags'] = ['reviewed_range_recomputed']
                row['motion_geometry'] = support_motion_evidence(result, row)
                if (row['motion'] == 'unclear'
                        and row['motion_geometry']['status'] == 'floor_pivot_compatible'):
                    row['motion'] = row['evidence_class'] = 'tip_or_rotation'
                    row['tags'].append('fixed_edge_rotation')

    def identify(self):
        if not self.all_reviewed:
            raise ValueError('Review every interval before identifying items.')
        for row in self.rows:
            self._reset_identity(row)
            if row['decision'] != 'include' or row['evidence_status'] != 'current':
                continue
            row['geometry'] = geometry_evidence(self.result, row)
            row['sequence_evidence'] = 'Trial sequence and eligibility need the test record.'
            if self.ista_type == 'H':
                row['eligibility_condition'] = ('Conditional posture lookup: 2018-03 H B04/B16 free-fall tables '
                    'apply below 45 kg (below 100 lb when that unit is used). Verify the test record; '
                    'motion does not establish mass or eligibility.')
            if (self.ista_type not in FACE_NUMBERS or row['evidence_class'] != 'free_fall'
                    or row['left_censored'] or row['right_censored']):
                continue
            crossings = row['geometry'].get('floor_crossings', [])
            if not crossings or not crossings[0]['approach_feature']:
                continue
            faces = tuple(sorted(FACE_NUMBERS[self.ista_type][name]
                                 for name in crossings[0]['approach_feature']['faces']))
            if self.ista_type == 'G':
                row['item_candidates'] = [f'G{i:02d}' for i, posture in enumerate(G_POSTURES, 1) if faces == posture]
            else:
                row['item_candidates'] = [f'H/{block}/D{i:02d}' for block, postures in H_POSTURES.items()
                                          for i, posture in enumerate(postures, 1) if faces == posture]

    def confirm_item(self, row_id, item):
        row = self.row(row_id)
        if not self.all_reviewed or row['decision'] != 'include' or item not in row['item_candidates']:
            raise ValueError('Identify an included interval before confirming its item.')
        if self.applied_edition != REFERENCE_EDITION:
            raise ValueError('This catalogue covers the 2018-03 edition. Verify the test record first.')
        row['identity'].update(scenario_id=item, scenario_kind='free_fall', confirmed=True)

    def payload(self, row_id):
        if not self.all_reviewed:
            raise ValueError('Review every interval before saving scenes.')
        row = deepcopy(self.row(row_id))
        identity = row.pop('identity')
        reg = self.result.registration
        return validate_scene_review_json({
            'version': 1, 'source_sha256': self.source_sha256, 'candidate': row, 'identity': identity,
            'detection': {'version': VERSION, 'settings': asdict(self.result.settings),
                          'registration_sha256': reg.fingerprint if reg else None,
                          'registration': asdict(reg) if reg else None,
                          'coordinate_policy': 'world-y-up-box-xyz-mm',
                          'gravity_time_semantics': 'accepted window centres, not release or contact'},
            'review_decisions': [{'id': r['id'], 'start': r['start'], 'end': r['end'], 'decision': r['decision']}
                                 for r in self.rows], 'deleted_ids': sorted(self.deleted_ids)})
