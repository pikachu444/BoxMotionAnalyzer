"""Analysis-only face interpretation of solved Rigid Body Marker channels.

XYZ values and physical marker identity are never changed by this module.
"""
from __future__ import annotations

from dataclasses import replace
import numpy as np
import pandas as pd
from scipy.spatial.transform import Rotation as R

from src.config import config_app
from src.config.data_columns import FACE_PREFIX_TO_INFO, PoseCols
from .marker_flip import (
    MarkerFlipAnalyzer, MarkerFlipHypothesis, local_axis_half_turn,
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
    """Bounded refits for operator review. Recommendations await validation."""

    def detect(self, marker_df, pose_df, box_dims):
        self.box_dims = tuple(box_dims)
        return super().detect(marker_df, pose_df, box_dims)

    def _evaluate_hypothesis(self, *, label, marker_df, pose_df, pre_positions,
                             post_positions, marker_ids, pre_rotation, pre_medians,
                             pre_sample_coverage, no_correction_residual_deg, tolerance_mm):
        from .pose_optimizer import PoseOptimizer
        post = marker_df.iloc[list(post_positions)].copy()
        face_cols = [f"{mid}_FaceInfo" for mid in marker_ids]
        applicable = bool(face_cols) and all(
            col in post and post[col].str.upper().isin(FACES).all() for col in face_cols
        )
        reason = "" if applicable else "Unknown analysis face; assignment cannot be applied."
        for col in face_cols:
            if col in post:
                post[col] = post[col].str.upper()
                if label != "NONE":
                    post[col] = post[col].map(lambda face: FACE_MAPS[label].get(face, face))
        residual, trace, coverage, rmse = float("inf"), (), 0., None
        if applicable:
            seed = pose_df.iloc[post_positions[0]][list(POSE_COLUMNS)].to_numpy(dtype=float)
            if label != "NONE":
                seed[3:] = (R.from_rotvec(seed[3:]) * local_axis_half_turn(label)).as_rotvec()
            fitted = PoseOptimizer(config_app.FACE_DEFINITIONS,
                config_app.calculate_local_box_corners(self.box_dims)).process(
                    post, box_dims=self.box_dims, initial_pose=seed)
            valid = self._valid_pose_positions(fitted)
            coverage = min(pre_sample_coverage, len(valid) / max(1, len(post)))
            if len(valid) >= self.minimum_window_samples:
                rotations = self._rotations_for_positions(fitted, valid)
                residual = float(np.degrees((pre_rotation.inv() * rotations.mean()).magnitude()))
                trace = tuple(float(v) for v in np.degrees((pre_rotation.inv() * rotations).magnitude()))
                # Fit error is not an independent marker correspondence score.
                from .pose_optimizer import _objective_function
                errors = []
                for i in valid:
                    row = fitted.iloc[i]
                    markers = [{"cam_coords": row[[f"{mid}_{c}" for c in "XYZ"]].to_numpy(dtype=float),
                                "face_key": row[f"{mid}_FaceInfo"]} for mid in marker_ids
                               if np.isfinite(row[[f"{mid}_{c}" for c in "XYZ"]].to_numpy(dtype=float)).all()]
                    if markers:
                        errors.append(_objective_function(row[list(POSE_COLUMNS)].to_numpy(dtype=float),
                                      markers, np.asarray(self.box_dims), config_app.FACE_DEFINITIONS) / len(markers))
                rmse = float(np.sqrt(np.mean(errors))) if errors else None
            else:
                reason = "Insufficient successful pose refits; manual face assignment only."
        return MarkerFlipHypothesis(label, residual, no_correction_residual_deg - residual,
            0., float("nan"), float("nan"), coverage, len(marker_ids), rmse,
            mapping_reason=reason, applicable=applicable, trace_deg=trace)

    def _review_boundary(self, *args, **kwargs):
        candidate = super()._review_boundary(*args, **kwargs)
        # No ranking or calibrated confidence claim for the new physical model.
        return replace(candidate, correction_kind="face_assignment", algorithm_version="3.0",
            gate_version="face-validation-pending", recommendation_axis=None,
            reason="Automatic recommendation pending independent validation. Review each axis and approve explicitly.",
            best_hypothesis_label="NONE", confidence_margin=0., correspondence_ratio=float("nan"),
            best_residual_deg=candidate.no_correction_residual_deg,
            discontinuity_reduction_deg=0.)
