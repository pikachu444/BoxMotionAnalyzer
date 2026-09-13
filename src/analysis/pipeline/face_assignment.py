"""Analysis-only face interpretation of solved Rigid Body Marker channels.

XYZ values and physical marker identity are never changed by this module.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.spatial.transform import Rotation as R
from scipy.spatial.distance import pdist

from src.config import config_app
from src.config.data_columns import FACE_PREFIX_TO_INFO, PoseCols
from .marker_flip import (
    MarkerFlipAnalyzer, MarkerFlipHypothesis, MarkerFlipCandidate, local_axis_half_turn,
    marker_triplet_indices, normalize_marker_corrections, _raw_time_values,
)

HEADER_KEYS = ("type", "name", "id", "parent", "category", "component")
FACE_MAPS = {
    "X": {"FRONT": "BACK", "BACK": "FRONT", "TOP": "BOTTOM", "BOTTOM": "TOP"},
    "Y": {"FRONT": "BACK", "BACK": "FRONT", "LEFT": "RIGHT", "RIGHT": "LEFT"},
    "Z": {"LEFT": "RIGHT", "RIGHT": "LEFT", "TOP": "BOTTOM", "BOTTOM": "TOP"},
}
FACES = frozenset(("FRONT", "BACK", "TOP", "BOTTOM", "LEFT", "RIGHT"))
POSE_COLUMNS = (PoseCols.POS_X, PoseCols.POS_Y, PoseCols.POS_Z,
                PoseCols.ROT_X, PoseCols.ROT_Y, PoseCols.ROT_Z)
FACE_ASSIGNMENT_ALGORITHM_VERSION = "3.1"
FACE_ASSIGNMENT_GATE_VERSION = "face-continuity-v1"
# SO(3) mean/rotvec conversions can move exact inclusive limits by a few ULPs.
# This is arithmetic roundoff only, not a wider physical support tolerance.
_ANGLE_ROUNDOFF_DEG = 8 * np.finfo(float).eps * 180.
_SCORE_ROUNDOFF = 8 * np.finfo(float).eps


def marker_face(marker_id):
    prefix = marker_id[:2] if marker_id.startswith(("FA", "BA")) else marker_id[:1]
    return FACE_PREFIX_TO_INFO.get(prefix.upper(), "").upper()


def face_columns(header):
    """Return validated annotation positions, indexed by marker identifier."""
    triplets = marker_triplet_indices(header)
    result = {}
    for i, kind in enumerate(header.get("type", [])):
        if kind != "Marker Annotation":
            continue
        if header["category"][i] != "Assignment" or header["component"][i] != "Face":
            raise ValueError("Unsupported marker annotation.")
        marker = header["name"][i].split(":", 1)[-1].replace(" ", "_")
        if marker not in triplets or marker in result:
            raise ValueError("Duplicate or orphan face annotation.")
        source = triplets[marker][0]
        if any(header[key][i] != header[key][source] for key in ("name", "id", "parent")):
            raise ValueError("Face annotation identity does not match its constraint channel.")
        result[marker] = i
    if result and set(result) != set(triplets):
        raise ValueError("Face annotations must cover every Rigid Body Marker.")
    return result


def strip_face_annotations(header, raw):
    annotations = set(face_columns(header).values())
    keep = [i for i in range(raw.shape[1]) if i not in annotations]
    clean_header = dict(header)
    for key in HEADER_KEYS:
        clean_header[key] = [header[key][i] for i in keep]
    return clean_header, raw.iloc[:, keep].copy(deep=True)


def materialize_face_assignments(header, raw, decisions, base_faces=None):
    header, result = strip_face_annotations(header, raw)
    triplets = marker_triplet_indices(header)
    if not triplets:
        raise ValueError("No Rigid Body Marker channels are available.")
    base = dict(base_faces or {mid: marker_face(mid) for mid in triplets})
    if set(base) != set(triplets) or any(face not in FACES for face in base.values()):
        raise ValueError("Every constraint marker needs a known original analysis face.")
    approved = normalize_marker_corrections(decisions, approved_only=True)
    if any(d.correction_kind != "face_assignment" for d in approved):
        raise ValueError("Legacy XYZ permutations and face assignments cannot be mixed.")
    times = _raw_time_values(result)
    if not np.all(np.diff(times) > 0):
        raise ValueError("Face correction requires strictly increasing timestamps.")
    for mid, indices in triplets.items():
        values = np.full(len(result), base[mid], dtype=object)
        for decision in approved:
            suffix = times >= decision.boundary_time_sec - 1e-12
            mapping = FACE_MAPS[decision.axis]
            values[suffix] = [mapping.get(face, face) for face in values[suffix]]
        i = indices[0]
        for key in HEADER_KEYS:
            value = {"type": "Marker Annotation", "category": "Assignment", "component": "Face"}.get(key)
            header[key].append(header[key][i] if value is None else value)
        result.insert(len(result.columns), "Face", values, allow_duplicates=True)
    return header, result


def validate_materialized_faces(header, raw, decisions, base_faces):
    """Check persisted faces against the full history, including pre-slice events."""
    actual_columns = face_columns(header)
    if not actual_columns:
        raise ValueError("Face correction requires materialized assignments.")
    expected_header, expected = materialize_face_assignments(header, raw, decisions, base_faces)
    expected_columns = face_columns(expected_header)
    for mid, column in actual_columns.items():
        actual = raw.iloc[:, column].astype(str).str.strip().str.upper().to_numpy()
        wanted = expected.iloc[:, expected_columns[mid]].to_numpy()
        if not np.array_equal(actual, wanted):
            raise ValueError(f"Face assignment disagrees with approved correction history for {mid}.")


def face_segments(df):
    """Contiguous segments; no smoothing or differentiation across a face change."""
    cols = [c for c in df if str(c).endswith("_FaceInfo")]
    if not cols or df.empty:
        return [df]
    values = df[cols].fillna("").astype(str)
    changed = values.ne(values.shift()).any(axis=1).to_numpy()
    starts = np.flatnonzero(changed)
    return [df.iloc[a:b] for a, b in zip(starts, [*starts[1:], len(df)])]


class FaceAssignmentAnalyzer(MarkerFlipAnalyzer):
    """Conditional continuity ranking; an axis does not diagnose the cause."""

    def _window_stability(self, pose_df, positions):
        """Maximum pairwise SO(3) angle over the entire requested valid window."""
        if len(positions) < 2:
            return float('inf')
        rotations = self._rotations_for_positions(pose_df, positions)
        return max(float(np.max(np.degrees((rotations[i].inv() * rotations[i + 1:]).magnitude())))
                   for i in range(len(positions) - 1))

    def detect(self, marker_df, pose_df, box_dims):
        if marker_df is None or pose_df is None or marker_df.empty or pose_df.empty:
            return []
        if len(marker_df) != len(pose_df) or not marker_df.index.equals(pose_df.index):
            raise ValueError('Marker and pose data must have the same rows and time index.')
        times = pd.to_numeric(pd.Index(pose_df.index), errors='coerce').to_numpy(dtype=float)
        if not np.isfinite(times).all() or not np.all(np.diff(times) > 0):
            raise ValueError('Marker flip review requires finite, strictly increasing timestamps.')
        valid_pose = self._valid_pose_positions(pose_df)
        if len(valid_pose) < 2:
            return []
        marker_ids = self._marker_ids(marker_df)
        points = self._marker_points(marker_df, marker_ids)
        observed_valid = np.isfinite(points).all(axis=2).sum(axis=1) >= self.minimum_common_markers
        gap_limit = self.gap_factor * np.median(np.diff(times))
        events = {}

        def add(pre, post, trigger):
            entry = events.setdefault(int(post), {'pre': int(pre), 'triggers': []})
            entry['pre'] = min(entry['pre'], int(pre))
            if trigger not in entry['triggers']:
                entry['triggers'].append(trigger)

        marker_boundaries = set()
        for post, direct, assigned in self._marker_label_discontinuities(marker_df, box_dims):
            marker_boundaries.add(post)
            add(post - 1, post, f'marker label discontinuity (labeled RMSE {direct:.1f} mm, set RMSE {assigned:.1f} mm)')
        for post, angle, residual in self._rigid_rotation_boundaries(points, box_dims):
            marker_boundaries.add(post)
            add(post - 1, post, f'stable-ID rotation jump {angle:.1f}° (rigid fit RMSE {residual:.3f} mm)')
        for pre, post in zip(valid_pose[:-1], valid_pose[1:]):
            jump = float(np.degrees((self._rotations_for_positions(pose_df, [pre]).inv()
                                     * self._rotations_for_positions(pose_df, [post])).magnitude()[0]))
            if jump >= self.candidate_angle_deg:
                boundary = next((index for index in sorted(marker_boundaries, reverse=True)
                                 if 0 <= post - index <= self.pose_lag_merge_samples), None)
                if boundary is None:
                    add(pre, post, f'rotation jump {jump:.1f}°')
                else:
                    add(boundary - 1, boundary, f'pose rotation jump {jump:.1f}°')
        # A failed optimization with intact observed coordinates is not a tracking gap.
        # True missing observation/time gaps remain explicit candidates and gate abstention.
        usable = np.flatnonzero(observed_valid)
        for pre, post in zip(usable[:-1], usable[1:]):
            if post - pre > 1 or times[post] - times[pre] > gap_limit:
                add(pre, post, 'tracking gap')
        for start, post in self._freeze_reconnect_boundaries(marker_df):
            earlier, later = valid_pose[valid_pose <= start], valid_pose[valid_pose >= post]
            if len(earlier) and len(later):
                add(earlier[-1], later[0], 'freeze/reconnect')
        return [self._review_boundary(marker_df, pose_df, box_dims, events[post]['pre'], post,
                                     ', '.join(events[post]['triggers'])) for post in sorted(events)]

    @staticmethod
    def _marker_points(marker_df, marker_ids):
        columns = [f'{mid}_{axis}' for mid in marker_ids for axis in 'XYZ']
        return marker_df[columns].to_numpy(dtype=float).reshape(len(marker_df), len(marker_ids), 3)

    def _rigid_rotation_boundaries(self, points, box_dims):
        """Stable-ID Kabsch finds the observed boundary, never a physical cause."""
        boundaries = []
        for post in range(1, len(points)):
            evidence = self._rigid_pair_evidence(points[post - 1], points[post], box_dims)
            if (evidence['status'] == 'supported_within_tolerance'
                    and evidence['rotation_deg'] + _ANGLE_ROUNDOFF_DEG >= self.candidate_angle_deg):
                boundaries.append((post, evidence['rotation_deg'], evidence['rmse_mm']))
        return boundaries

    def _rigid_pair_evidence(self, before, after, box_dims):
        common = np.isfinite(before).all(axis=1) & np.isfinite(after).all(axis=1)
        coverage = float(common.sum() / max(1, len(common)))
        evidence = {'method': 'stable-ID Kabsch', 'common_marker_count': int(common.sum()),
                    'coverage': coverage, 'rotation_deg': None, 'rmse_mm': None,
                    'maximum_pair_distance_change_mm': None,
                    'rmse_limit_mm': float(np.linalg.norm(box_dims) * self.marker_set_continuity_fraction),
                    'pair_distance_change_limit_mm': float(np.linalg.norm(box_dims) * self.marker_set_continuity_fraction),
                    'status': 'insufficient_markers',
                    'scope': 'Rigid-fit support within the stated tolerance; not exact rigidity or error diagnosis.'}
        if common.sum() < max(3, self.minimum_common_markers) or coverage < self.minimum_coverage_ratio:
            return evidence
        before, after = before[common], after[common]
        before, after = before - before.mean(axis=0), after - after.mean(axis=0)
        u, singular, vt = np.linalg.svd(before.T @ after)
        # The same numerical non-collinearity guard as scene rigid registration.
        if singular[0] <= 0 or singular[1] <= singular[0] * 1e-8:
            evidence['status'] = 'noncollinear_support_required'
            return evidence
        handedness = np.eye(3)
        handedness[-1, -1] = np.linalg.det(vt.T @ u.T)
        rotation = vt.T @ handedness @ u.T
        residual = float(np.sqrt(np.mean(np.sum((before @ rotation.T - after) ** 2, axis=1))))
        distance_change = float(np.max(np.abs(pdist(before) - pdist(after))))
        evidence.update(rotation_deg=float(np.degrees(R.from_matrix(rotation).magnitude())), rmse_mm=residual,
                        maximum_pair_distance_change_mm=distance_change,
                        status='supported_within_tolerance' if residual <= evidence['rmse_limit_mm']
                        and distance_change <= evidence['pair_distance_change_limit_mm'] else 'distortion_exceeds_tolerance')
        return evidence

    @staticmethod
    def _marker_sample_coverage(marker_df, positions, marker_ids):
        possible = len(positions) * len(marker_ids)
        if not possible:
            return 0.
        count = 0
        for mid in marker_ids:
            rows = marker_df.iloc[list(positions)]
            xyz = rows[[f'{mid}_{axis}' for axis in 'XYZ']].to_numpy(dtype=float)
            faces = rows.get(f'{mid}_FaceInfo')
            if faces is not None:
                count += int(np.count_nonzero(np.isfinite(xyz).all(axis=1)
                    & faces.astype(str).str.upper().isin(FACES).to_numpy()))
        return count / possible

    def _refit_hypothesis(self, label, marker_df, pose_df, post_positions, marker_ids, box_dims):
        from .pose_optimizer import PoseOptimizer
        post = marker_df.iloc[list(post_positions)].copy()
        face_cols = [f"{mid}_FaceInfo" for mid in marker_ids]
        applicable = bool(face_cols) and all(
            col in post and post[col].astype(str).str.upper().isin(FACES).all() for col in face_cols
        )
        if not applicable:
            return None, False, "Unknown analysis face; assignment cannot be applied."
        for col in face_cols:
            post[col] = post[col].astype(str).str.upper()
            if label != "NONE":
                post[col] = post[col].map(lambda face: FACE_MAPS[label].get(face, face))
        valid_seed = self._valid_pose_positions(pose_df.iloc[list(post_positions)])
        if not len(valid_seed):
            return None, True, "No valid pose seed in the requested post window."
        seed = pose_df.iloc[post_positions[int(valid_seed[0])]][list(POSE_COLUMNS)].to_numpy(dtype=float).copy()
        if label != "NONE":
            seed[3:] = (R.from_rotvec(seed[3:]) * local_axis_half_turn(label)).as_rotvec()
        try:
            fitted = PoseOptimizer(config_app.FACE_DEFINITIONS,
                config_app.calculate_local_box_corners(box_dims)).process(post, box_dims=box_dims, initial_pose=seed)
            if not fitted.index.equals(post.index):
                return None, True, "Refit sample times do not match the requested window."
            self._valid_pose_positions(fitted)
            return fitted, True, ""
        except (ValueError, RuntimeError, FloatingPointError, np.linalg.LinAlgError) as error:
            return None, True, f"Pose refit unavailable: {error}"

    def _review_boundary(self, marker_df, pose_df, box_dims, pre_anchor, post_anchor, trigger):
        from .pose_optimizer import _objective_function
        requested_pre = list(range(max(0, pre_anchor - self.window_size + 1), pre_anchor + 1))
        requested_post = list(range(post_anchor, min(len(pose_df), post_anchor + self.window_size)))
        valid = set(self._valid_pose_positions(pose_df))
        pre = [index for index in requested_pre if index in valid]
        raw_post = [index for index in requested_post if index in valid]
        marker_ids = self._marker_ids(marker_df)
        minimum_samples = max(3, self.minimum_window_samples)
        pre_coverage = len(pre) / max(1, len(requested_pre))
        pre_marker_coverage = self._marker_sample_coverage(marker_df, requested_pre, marker_ids)
        post_marker_coverage = self._marker_sample_coverage(marker_df, requested_post, marker_ids)
        pre_rotation = self._representative_rotation(pose_df, pre) if pre else None
        pre_stability = self._window_stability(pose_df, pre)
        raw_post_stability = self._window_stability(pose_df, raw_post)
        raw_residual = (float(np.degrees((pre_rotation.inv()
            * self._representative_rotation(pose_df, raw_post)).magnitude())) if pre and raw_post else float('inf'))
        times = np.asarray(pose_df.index, float)
        boundary_time = float(times[post_anchor])
        requested = requested_pre + requested_post
        gap_limit = self.gap_factor * np.median(np.diff(times)) if len(times) > 1 else 0.
        available_markers = np.isfinite(self._marker_points(marker_df.iloc[requested], marker_ids)).all(axis=2).sum(axis=1)
        crosses_gap = (post_anchor != pre_anchor + 1 or bool(np.any(np.diff(times[requested]) > gap_limit))
                       or bool(np.any(available_markers < self.minimum_common_markers)))
        face_cols = [f'{mid}_FaceInfo' for mid in marker_ids if f'{mid}_FaceInfo' in marker_df]
        crosses_face_boundary = any(marker_df.iloc[requested][col].fillna('').astype(str).str.upper().nunique() > 1
                                    for col in face_cols)
        boundary_points = self._marker_points(marker_df.iloc[[pre_anchor, post_anchor]], marker_ids)
        rigid_fit = self._rigid_pair_evidence(*boundary_points, box_dims)
        fitted, applicable, failures, valid_refits = {}, {}, {}, {}
        for label in ('NONE', 'X', 'Y', 'Z'):
            frame, can_apply, failure = self._refit_hypothesis(
                label, marker_df, pose_df, requested_post, marker_ids, box_dims)
            fitted[label], applicable[label], failures[label] = frame, can_apply, failure
            valid_refits[label] = set(self._valid_pose_positions(frame)) if frame is not None else set()
        common = sorted(set.intersection(*valid_refits.values()))
        refit_coverage = {label: len(indices) / max(1, len(requested_post)) for label, indices in valid_refits.items()}
        common_coverage = len(common) / max(1, len(requested_post))
        coverage = min(pre_coverage, pre_marker_coverage, post_marker_coverage, common_coverage, *refit_coverage.values())
        residuals, traces, rmse, stability = {}, {}, {}, {}
        supported_comparison = len(pre) >= minimum_samples and len(common) >= minimum_samples
        for label in fitted:
            residuals[label], traces[label], rmse[label], stability[label] = float('inf'), (), None, float('inf')
            if not supported_comparison:
                continue
            frame = fitted[label]
            rotations = self._rotations_for_positions(frame, common)
            residuals[label] = float(np.degrees((pre_rotation.inv() * rotations.mean()).magnitude()))
            traces[label] = tuple(float(value) for value in np.degrees((pre_rotation.inv() * rotations).magnitude()))
            stability[label] = self._window_stability(frame, common)
            errors = []
            for index in common:
                row = frame.iloc[index]
                markers = [{'cam_coords': row[[f'{mid}_{axis}' for axis in 'XYZ']].to_numpy(dtype=float),
                            'face_key': row[f'{mid}_FaceInfo']} for mid in marker_ids
                           if np.isfinite(row[[f'{mid}_{axis}' for axis in 'XYZ']].to_numpy(dtype=float)).all()]
                if markers:
                    errors.append(_objective_function(row[list(POSE_COLUMNS)].to_numpy(dtype=float),
                        markers, np.asarray(box_dims), config_app.FACE_DEFINITIONS) / len(markers))
            rmse[label] = float(np.sqrt(np.mean(errors))) if errors else None
        hypotheses = tuple(MarkerFlipHypothesis(label, residuals[label],
            residuals['NONE'] - residuals[label] if supported_comparison else 0.,
            float(np.clip(1. - residuals[label] / 180., 0., 1.)) if supported_comparison else float('nan'),
            float('nan'), float('nan'), coverage, len(marker_ids), rmse[label],
            mapping_reason=failures[label] or ('' if supported_comparison else 'Insufficient common valid refit samples.'),
            applicable=applicable[label], trace_deg=traces[label]) for label in fitted)
        ranked = sorted(hypotheses, key=lambda item: (item.residual_deg, item.label != 'NONE', item.label))
        best, runner_up = ranked[:2]
        margin = float(best.score - runner_up.score) if supported_comparison else 0.
        post_stability = max(stability.values())
        recommendation = None
        if not supported_comparison or len(marker_ids) < self.minimum_common_markers:
            reason = 'Insufficient common valid samples for four-axis comparison.'
        elif crosses_gap or crosses_face_boundary:
            reason = 'A tracking gap or approved face boundary crosses the comparison.'
        elif rigid_fit['status'] != 'supported_within_tolerance':
            reason = 'Stable-ID marker geometry does not support a rigid boundary comparison.'
        elif coverage < self.minimum_coverage_ratio:
            reason = 'Requested-window marker or refit coverage is below the continuity gate.'
        elif max(pre_stability, post_stability) > self.maximum_window_motion_deg + _ANGLE_ROUNDOFF_DEG:
            reason = 'The comparison windows are not stable enough.'
        elif best.label == 'NONE':
            reason = 'No correction gives the strongest continuity.'
        elif best.residual_deg > self.maximum_corrected_residual_deg + _ANGLE_ROUNDOFF_DEG:
            reason = 'The best refit continuity residual is too large.'
        elif best.discontinuity_reduction_deg + _ANGLE_ROUNDOFF_DEG < self.minimum_discontinuity_reduction_deg:
            reason = 'Improvement over the actual NONE refit is too small.'
        elif margin + _SCORE_ROUNDOFF < self.minimum_confidence_margin:
            reason = 'The four-hypothesis continuity score gap is too small.'
        else:
            recommendation = best.label
            reason = f'If corrected, local {best.label} best restores continuity; cause unconfirmed.'
        common_positions = [requested_post[index] for index in common]
        raw_trace = tuple(float(np.degrees((pre_rotation.inv()
            * self._rotations_for_positions(pose_df, [index])).magnitude()[0]))
            if index in valid and pre_rotation is not None else float('nan') for index in common_positions)
        evidence = {
            'scope': 'Conditional half-turn continuity, not error diagnosis or probability.',
            'score_definition': 'clip(1 - common-sample residual_deg / 180, 0, 1)',
            'residual_definition': 'SO(3) angle from pre-window mean to common-sample post-refit mean.',
            'requested_pre_sample_indices': requested_pre, 'requested_post_sample_indices': requested_post,
            'common_post_sample_indices': common_positions,
            'refit_valid_sample_indices': {label: [requested_post[i] for i in sorted(indices)]
                                           for label, indices in valid_refits.items()},
            'coverage_denominator': 'All actual samples in each requested window; marker count for marker-samples.',
            'pre_pose_coverage': pre_coverage, 'pre_marker_sample_coverage': pre_marker_coverage,
            'post_marker_sample_coverage': post_marker_coverage, 'refit_coverage': refit_coverage,
            'common_refit_coverage': common_coverage, 'raw_post_stability_deg': raw_post_stability,
            'refit_post_stability_deg': stability, 'raw_no_correction_residual_deg': raw_residual,
            'window_stability_definition': 'Maximum pairwise SO(3) angle among all valid window samples; not adjacent increments.',
            'crosses_tracking_gap': crosses_gap, 'crosses_face_assignment_boundary': crosses_face_boundary,
            'boundary_rigid_fit': rigid_fit,
            'thresholds': {'minimum_samples': minimum_samples, 'minimum_coverage': self.minimum_coverage_ratio,
                'maximum_window_motion_deg': self.maximum_window_motion_deg,
                'maximum_best_residual_deg': self.maximum_corrected_residual_deg,
                'minimum_none_improvement_deg': self.minimum_discontinuity_reduction_deg,
                'minimum_score_margin': self.minimum_confidence_margin,
                'arithmetic_roundoff_deg': _ANGLE_ROUNDOFF_DEG, 'arithmetic_roundoff_score': _SCORE_ROUNDOFF},
        }
        return MarkerFlipCandidate(f'flip-{post_anchor:06d}', boundary_time, trigger, recommendation,
            best.label, residuals['NONE'], best.residual_deg, best.discontinuity_reduction_deg, margin,
            float('nan'), best.marker_rmse_mm, coverage, len(marker_ids), pre_stability, post_stability, reason,
            hypotheses=hypotheses, algorithm_version=FACE_ASSIGNMENT_ALGORITHM_VERSION,
            gate_version=FACE_ASSIGNMENT_GATE_VERSION, correction_kind='face_assignment', continuity_evidence=evidence,
            pre_window_time_offsets_sec=tuple(float(times[i] - boundary_time) for i in pre),
            post_window_time_offsets_sec=tuple(float(times[i] - boundary_time) for i in common_positions),
            pre_window_residual_deg=tuple(float(value) for value in np.degrees((pre_rotation.inv()
                * self._rotations_for_positions(pose_df, pre)).magnitude())) if pre else (),
            post_window_raw_residual_deg=raw_trace, post_window_best_residual_deg=best.trace_deg)
