from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from typing import Iterable, Mapping, Sequence

import numpy as np
import pandas as pd
from scipy.optimize import linear_sum_assignment
from scipy.spatial.transform import Rotation as R

from src.config.data_columns import PoseCols, RawMarkerCols, RigidBodyCols, TimeCols, SourceCols


SUPPORTED_LOCAL_AXES = ("X", "Y", "Z")
MARKER_FLIP_ALGORITHM_VERSION = "2.0"
MARKER_FLIP_GATE_VERSION = "2026-09-02.1"

_AXIS_INDEX = {"X": 0, "Y": 1, "Z": 2}
_NO_CORRECTION = "NONE"

MarkerPermutation = tuple[tuple[str, str], ...]


def _json_safe(value: object) -> object:
    if isinstance(value, (float, np.floating)):
        numeric_value = float(value)
        return numeric_value if np.isfinite(numeric_value) else None
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return value


@dataclass(frozen=True)
class MarkerFlipHypothesis:
    label: str
    residual_deg: float
    discontinuity_reduction_deg: float
    score: float
    layout_correspondence_ratio: float
    observed_correspondence_ratio: float
    coverage_ratio: float
    common_marker_count: int
    marker_rmse_mm: float | None
    permutation: MarkerPermutation = ()
    mapping_reason: str = ""
    applicable: bool = True
    trace_deg: tuple[float, ...] = ()


@dataclass(frozen=True)
class MarkerFlipCandidate:
    event_id: str
    boundary_time_sec: float
    trigger: str
    recommendation_axis: str | None
    best_hypothesis_label: str
    no_correction_residual_deg: float
    best_residual_deg: float
    discontinuity_reduction_deg: float
    confidence_margin: float
    correspondence_ratio: float
    marker_rmse_mm: float | None
    coverage_ratio: float
    common_marker_count: int
    pre_stability_deg: float
    post_stability_deg: float
    reason: str
    hypotheses: tuple[MarkerFlipHypothesis, ...] = ()
    algorithm_version: str = MARKER_FLIP_ALGORITHM_VERSION
    gate_version: str = MARKER_FLIP_GATE_VERSION
    pre_window_time_offsets_sec: tuple[float, ...] = ()
    post_window_time_offsets_sec: tuple[float, ...] = ()
    pre_window_residual_deg: tuple[float, ...] = ()
    post_window_raw_residual_deg: tuple[float, ...] = ()
    post_window_best_residual_deg: tuple[float, ...] = ()
    correction_kind: str = "marker_permutation"
    continuity_evidence: dict[str, object] | None = None

    def hypothesis(self, axis: str | None) -> MarkerFlipHypothesis | None:
        label = _NO_CORRECTION if axis is None else str(axis).strip().upper()
        return next((item for item in self.hypotheses if item.label == label), None)

    def permutation_for_axis(self, axis: str | None) -> MarkerPermutation:
        hypothesis = self.hypothesis(axis)
        return () if hypothesis is None else hypothesis.permutation

    def evidence_payload(self) -> dict[str, object]:
        return {
            "algorithm_version": self.algorithm_version,
            "gate_version": self.gate_version,
            "correction_kind": self.correction_kind,
            "trigger": self.trigger,
            "candidate_boundary_sec": self.boundary_time_sec,
            "recommendation_axis": self.recommendation_axis,
            "recommendation_reason": self.reason,
            "no_correction_residual_deg": self.no_correction_residual_deg,
            "best_hypothesis": self.best_hypothesis_label,
            "best_residual_deg": self.best_residual_deg,
            "discontinuity_reduction_deg": self.discontinuity_reduction_deg,
            "confidence_margin": self.confidence_margin,
            "correspondence_ratio": self.correspondence_ratio,
            "coverage_ratio": self.coverage_ratio,
            "common_marker_count": self.common_marker_count,
            "marker_rmse_mm": self.marker_rmse_mm,
            "pre_stability_deg": self.pre_stability_deg,
            "post_stability_deg": self.post_stability_deg,
            **({"continuity_evidence": self.continuity_evidence} if self.continuity_evidence is not None else {}),
            "hypotheses": {
                item.label: {
                    "residual_deg": item.residual_deg,
                    "discontinuity_reduction_deg": item.discontinuity_reduction_deg,
                    "score": item.score,
                    "layout_correspondence_ratio": item.layout_correspondence_ratio,
                    "observed_correspondence_ratio": item.observed_correspondence_ratio,
                    "coverage_ratio": item.coverage_ratio,
                    "common_marker_count": item.common_marker_count,
                    "marker_rmse_mm": item.marker_rmse_mm,
                    "mapping_reason": item.mapping_reason,
                    "applicable": item.applicable,
                }
                for item in self.hypotheses
            },
        }

    def evidence_json(self) -> str:
        return json.dumps(
            _json_safe(self.evidence_payload()),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )

    def evidence_summary(self) -> str:
        marker_rmse = "N/A" if self.marker_rmse_mm is None else f"{self.marker_rmse_mm:.2f} mm"
        if self.correction_kind == "face_assignment":
            return (f"refit NONE {self.no_correction_residual_deg:.1f}° → {self.best_residual_deg:.1f}°; "
                    f"score gap={self.confidence_margin:.2f}; coverage={self.coverage_ratio:.0%}; RMSE={marker_rmse}")
        return (
            f"jump {self.no_correction_residual_deg:.1f}° → {self.best_residual_deg:.1f}°; "
            f"match={self.correspondence_ratio:.0%}; coverage={self.coverage_ratio:.0%}; "
            f"margin={self.confidence_margin:.0%}; RMSE={marker_rmse}"
        )


@dataclass(frozen=True)
class MarkerCorrectionDecision:
    event_id: str
    boundary_time_sec: float
    approved: bool = False
    axis: str | None = None
    recommendation_axis: str | None = None
    permutation: MarkerPermutation = ()
    recommendation_reason: str = ""
    evidence_json: str = ""
    algorithm_version: str = MARKER_FLIP_ALGORITHM_VERSION
    gate_version: str = MARKER_FLIP_GATE_VERSION
    correction_kind: str = "marker_permutation"


def local_axis_half_turn(axis: str) -> R:
    normalized_axis = str(axis).strip().upper()
    if normalized_axis not in SUPPORTED_LOCAL_AXES:
        raise ValueError(f"Unsupported marker correction axis: {axis!r}")
    rotvec = np.zeros(3, dtype=float)
    rotvec[_AXIS_INDEX[normalized_axis]] = np.pi
    return R.from_rotvec(rotvec)


def _normalize_permutation(value: object) -> MarkerPermutation:
    if value in (None, "", (), []):
        return ()
    if isinstance(value, Mapping):
        raw_pairs = list(value.items())
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        raw_pairs = list(value)
    else:
        raise TypeError("Marker permutation must be a mapping or a sequence of pairs.")

    pairs: list[tuple[str, str]] = []
    for pair in raw_pairs:
        if not isinstance(pair, Sequence) or isinstance(pair, (str, bytes)) or len(pair) != 2:
            raise ValueError("Each marker permutation entry must contain destination and source labels.")
        destination = str(pair[0]).strip()
        source = str(pair[1]).strip()
        if not destination or not source:
            raise ValueError("Marker permutation labels cannot be empty.")
        pairs.append((destination, source))

    pairs = sorted(pairs)
    destinations = [destination for destination, _ in pairs]
    sources = [source for _, source in pairs]
    if len(set(destinations)) != len(destinations) or len(set(sources)) != len(sources):
        raise ValueError("Marker permutation must be one-to-one.")
    if set(destinations) != set(sources):
        raise ValueError("Marker permutation must map a closed set of marker labels.")

    mapping = dict(pairs)
    if any(mapping.get(mapping[destination]) != destination for destination in destinations):
        raise ValueError("A local-axis 180-degree marker permutation must be reversible.")
    return tuple(pairs)


def _coerce_decision(value: MarkerCorrectionDecision | Mapping[str, object]) -> MarkerCorrectionDecision:
    if isinstance(value, MarkerCorrectionDecision):
        decision = value
    elif isinstance(value, Mapping):
        axis_value = value.get("axis")
        recommendation_value = value.get("recommendation_axis")
        decision = MarkerCorrectionDecision(
            event_id=str(value.get("event_id", "")),
            boundary_time_sec=float(value.get("boundary_time_sec", 0.0)),
            approved=bool(value.get("approved", False)),
            axis=None if axis_value in (None, "") else str(axis_value).upper(),
            recommendation_axis=(
                None
                if recommendation_value in (None, "")
                else str(recommendation_value).upper()
            ),
            permutation=_normalize_permutation(
                value.get("permutation", value.get("marker_permutation"))
            ),
            recommendation_reason=str(value.get("recommendation_reason", "")),
            evidence_json=str(value.get("evidence_json", value.get("evidence", ""))),
            algorithm_version=str(
                value.get("algorithm_version", MARKER_FLIP_ALGORITHM_VERSION)
            ),
            gate_version=str(value.get("gate_version", MARKER_FLIP_GATE_VERSION)),
            correction_kind=str(value.get("correction_kind", "marker_permutation")),
        )
    else:
        raise TypeError(f"Unsupported marker correction decision: {type(value).__name__}")

    approved = bool(decision.approved)
    axis = None if decision.axis in (None, "") else str(decision.axis).upper()
    recommendation = (
        None
        if decision.recommendation_axis in (None, "")
        else str(decision.recommendation_axis).upper()
    )
    permutation = _normalize_permutation(decision.permutation)

    if axis is not None and axis not in SUPPORTED_LOCAL_AXES:
        raise ValueError(f"Unsupported marker correction axis: {decision.axis!r}")
    if recommendation is not None and recommendation not in SUPPORTED_LOCAL_AXES:
        raise ValueError(
            f"Unsupported marker correction recommendation: {decision.recommendation_axis!r}"
        )
    if not np.isfinite(float(decision.boundary_time_sec)):
        raise ValueError("Marker correction boundary must be finite.")
    if approved and axis is None:
        raise ValueError("An approved marker correction requires an X, Y, or Z local axis.")
    if decision.correction_kind not in ("marker_permutation", "face_assignment"):
        raise ValueError("Unsupported correction kind.")
    if decision.correction_kind == "face_assignment" and permutation:
        raise ValueError("Face assignment must not contain a marker permutation.")
    if approved and decision.correction_kind == "marker_permutation" and not permutation:
        raise ValueError("An approved marker correction requires a marker-column permutation.")
    if not approved:
        axis = None
        permutation = ()

    return MarkerCorrectionDecision(
        event_id=str(decision.event_id),
        boundary_time_sec=float(decision.boundary_time_sec),
        approved=approved,
        axis=axis,
        recommendation_axis=recommendation,
        permutation=permutation,
        recommendation_reason=str(decision.recommendation_reason),
        evidence_json=str(decision.evidence_json),
        algorithm_version=str(decision.algorithm_version or MARKER_FLIP_ALGORITHM_VERSION),
        gate_version=str(decision.gate_version or MARKER_FLIP_GATE_VERSION),
        correction_kind=decision.correction_kind,
    )


def normalize_marker_corrections(
    decisions: Iterable[MarkerCorrectionDecision | Mapping[str, object]] | None,
    *,
    approved_only: bool = False,
) -> list[MarkerCorrectionDecision]:
    normalized = [_coerce_decision(value) for value in (decisions or [])]
    if approved_only:
        normalized = [decision for decision in normalized if decision.approved]
    return sorted(normalized, key=lambda item: (item.boundary_time_sec, item.event_id))


def serialize_marker_corrections(
    decisions: Iterable[MarkerCorrectionDecision | Mapping[str, object]] | None,
    *,
    approved_only: bool = False,
) -> str:
    normalized = normalize_marker_corrections(decisions, approved_only=approved_only)
    payload = [asdict(decision) for decision in normalized]
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def deserialize_marker_corrections(value: str | None) -> list[MarkerCorrectionDecision]:
    if value is None or str(value).strip() == "":
        return []
    try:
        payload = json.loads(value)
    except (TypeError, json.JSONDecodeError) as exc:
        raise ValueError("Invalid marker correction metadata JSON.") from exc
    if not isinstance(payload, list):
        raise ValueError("Marker correction metadata must contain a list of events.")
    return normalize_marker_corrections(payload)


def candidate_to_decision(candidate: MarkerFlipCandidate) -> MarkerCorrectionDecision:
    return MarkerCorrectionDecision(
        event_id=candidate.event_id,
        boundary_time_sec=candidate.boundary_time_sec,
        approved=False,
        axis=None,
        recommendation_axis=candidate.recommendation_axis,
        recommendation_reason=candidate.reason,
        evidence_json=candidate.evidence_json(),
        algorithm_version=candidate.algorithm_version,
        gate_version=candidate.gate_version,
        correction_kind=candidate.correction_kind,
    )


class MarkerFlipAnalyzer:
    """Evaluate independent marker-label half-turn hypotheses at candidate boundaries."""

    def __init__(
        self,
        *,
        window_size: int = 5,
        minimum_window_samples: int = 3,
        candidate_angle_deg: float = 60.0,
        maximum_corrected_residual_deg: float = 35.0,
        maximum_window_motion_deg: float = 30.0,
        minimum_confidence_margin: float = 0.15,
        minimum_discontinuity_reduction_deg: float = 20.0,
        minimum_coverage_ratio: float = 0.80,
        minimum_correspondence_ratio: float = 0.80,
        minimum_common_markers: int = 3,
        correspondence_tolerance_fraction: float = 0.05,
        gap_factor: float = 3.0,
        freeze_min_samples: int = 3,
        freeze_tolerance_mm: float = 1e-9,
        marker_jump_fraction: float = 0.10,
        marker_set_continuity_fraction: float = 0.05,
        marker_jump_reduction_fraction: float = 0.08,
        pose_lag_merge_samples: int = 2,
    ):
        self.window_size = max(2, int(window_size))
        self.minimum_window_samples = max(2, int(minimum_window_samples))
        self.candidate_angle_deg = float(candidate_angle_deg)
        self.maximum_corrected_residual_deg = float(maximum_corrected_residual_deg)
        self.maximum_window_motion_deg = float(maximum_window_motion_deg)
        self.minimum_confidence_margin = float(minimum_confidence_margin)
        self.minimum_discontinuity_reduction_deg = float(
            minimum_discontinuity_reduction_deg
        )
        self.minimum_coverage_ratio = float(minimum_coverage_ratio)
        self.minimum_correspondence_ratio = float(minimum_correspondence_ratio)
        self.minimum_common_markers = int(minimum_common_markers)
        self.correspondence_tolerance_fraction = float(correspondence_tolerance_fraction)
        self.gap_factor = float(gap_factor)
        self.freeze_min_samples = max(2, int(freeze_min_samples))
        self.freeze_tolerance_mm = max(0.0, float(freeze_tolerance_mm))
        self.marker_jump_fraction = max(0.0, float(marker_jump_fraction))
        self.marker_set_continuity_fraction = max(
            0.0,
            float(marker_set_continuity_fraction),
        )
        self.marker_jump_reduction_fraction = max(
            0.0,
            float(marker_jump_reduction_fraction),
        )
        self.pose_lag_merge_samples = max(0, int(pose_lag_merge_samples))

    @staticmethod
    def _valid_pose_positions(pose_df: pd.DataFrame) -> np.ndarray:
        required = [
            PoseCols.POS_X,
            PoseCols.POS_Y,
            PoseCols.POS_Z,
            PoseCols.ROT_X,
            PoseCols.ROT_Y,
            PoseCols.ROT_Z,
        ]
        missing = [column for column in required if column not in pose_df.columns]
        if missing:
            raise ValueError(f"Pose data is missing required columns: {', '.join(missing)}")
        values = pose_df[required].apply(pd.to_numeric, errors="coerce").to_numpy(dtype=float)
        valid = np.isfinite(values).all(axis=1)
        if SourceCols.POSE in pose_df:
            valid &= pose_df[SourceCols.POSE].eq("Optimized").to_numpy()
        return np.flatnonzero(valid)

    @staticmethod
    def _marker_ids(marker_df: pd.DataFrame) -> list[str]:
        columns = {str(column) for column in marker_df.columns}
        has_face_info = any(
            column.endswith(RawMarkerCols.FACEINFO_SUFFIX) for column in columns
        )
        marker_ids = []
        for column in columns:
            if not column.endswith(RawMarkerCols.X_SUFFIX):
                continue
            marker_id = column[: -len(RawMarkerCols.X_SUFFIX)]
            required = {
                f"{marker_id}{RawMarkerCols.X_SUFFIX}",
                f"{marker_id}{RawMarkerCols.Y_SUFFIX}",
                f"{marker_id}{RawMarkerCols.Z_SUFFIX}",
            }
            if not required.issubset(columns):
                continue
            if marker_id == RigidBodyCols.BASE_NAME:
                continue
            if (
                has_face_info
                and f"{marker_id}{RawMarkerCols.FACEINFO_SUFFIX}" not in columns
            ):
                continue
            marker_ids.append(marker_id)
        return sorted(set(marker_ids))

    @staticmethod
    def _rotations_for_positions(pose_df: pd.DataFrame, positions: Sequence[int]) -> R:
        rotvecs = pose_df.iloc[list(positions)][
            [PoseCols.ROT_X, PoseCols.ROT_Y, PoseCols.ROT_Z]
        ].to_numpy(dtype=float)
        return R.from_rotvec(rotvecs)

    def _window_stability(self, pose_df: pd.DataFrame, positions: Sequence[int]) -> float:
        if len(positions) < 2:
            return float("inf")
        rotations = self._rotations_for_positions(pose_df, positions)
        increments = rotations[:-1].inv() * rotations[1:]
        incremental_deg = np.degrees(increments.magnitude())
        if incremental_deg.size == 0:
            return float("inf")
        return float(np.percentile(incremental_deg, 80))

    def _stable_contiguous_positions(
        self,
        pose_df: pd.DataFrame,
        positions: Sequence[int],
        *,
        side: str,
    ) -> list[int]:
        ordered = [int(position) for position in positions]
        if len(ordered) < 2:
            return ordered

        rotations = self._rotations_for_positions(pose_df, ordered)
        times = np.asarray(pose_df.index, dtype=float)
        positive = np.diff(times)
        positive = positive[positive > 0]
        gap_limit = self.gap_factor * np.median(positive) if positive.size else 0
        runs: list[list[int]] = []
        run_start = 0
        for offset in range(1, len(ordered)):
            contiguous = (ordered[offset] == ordered[offset - 1] + 1
                          and times[ordered[offset]] - times[ordered[offset - 1]] <= gap_limit)
            incremental_deg = float(
                np.degrees(
                    (rotations[offset - 1].inv() * rotations[offset]).magnitude()
                )
            )
            if contiguous and incremental_deg <= self.maximum_window_motion_deg:
                continue
            runs.append(ordered[run_start:offset])
            run_start = offset
        runs.append(ordered[run_start:])

        if side == "pre":
            best = max(runs, key=lambda run: (len(run), run[-1]))
            return best[-self.window_size :]
        if side == "post":
            best = max(runs, key=lambda run: (len(run), -run[0]))
            return best[: self.window_size]
        raise ValueError(f"Unsupported stable-window side: {side!r}")

    @staticmethod
    def _representative_rotation(
        pose_df: pd.DataFrame,
        positions: Sequence[int],
        correction: R | None = None,
    ) -> R:
        rotations = MarkerFlipAnalyzer._rotations_for_positions(pose_df, positions)
        if correction is not None:
            rotations = rotations * correction
        return rotations.mean()

    @staticmethod
    def _local_marker_medians(
        marker_df: pd.DataFrame,
        pose_df: pd.DataFrame,
        positions: Sequence[int],
        marker_ids: Sequence[str],
        correction: R | None = None,
    ) -> tuple[dict[str, np.ndarray], float]:
        samples: dict[str, list[np.ndarray]] = {marker_id: [] for marker_id in marker_ids}
        possible_samples = max(1, len(positions) * len(marker_ids))
        valid_samples = 0

        for position in positions:
            pose_row = pose_df.iloc[position]
            translation = np.array(
                [pose_row[PoseCols.POS_X], pose_row[PoseCols.POS_Y], pose_row[PoseCols.POS_Z]],
                dtype=float,
            )
            rotvec = np.array(
                [pose_row[PoseCols.ROT_X], pose_row[PoseCols.ROT_Y], pose_row[PoseCols.ROT_Z]],
                dtype=float,
            )
            if not np.isfinite(translation).all() or not np.isfinite(rotvec).all():
                continue
            rotation = R.from_rotvec(rotvec)
            if correction is not None:
                rotation = rotation * correction

            marker_row = marker_df.iloc[position]
            for marker_id in marker_ids:
                world = np.array(
                    [
                        marker_row.get(f"{marker_id}{RawMarkerCols.X_SUFFIX}"),
                        marker_row.get(f"{marker_id}{RawMarkerCols.Y_SUFFIX}"),
                        marker_row.get(f"{marker_id}{RawMarkerCols.Z_SUFFIX}"),
                    ],
                    dtype=float,
                )
                if not np.isfinite(world).all():
                    continue
                samples[marker_id].append(rotation.inv().apply(world - translation))
                valid_samples += 1

        medians = {
            marker_id: np.median(np.vstack(values), axis=0)
            for marker_id, values in samples.items()
            if values
        }
        return medians, float(valid_samples / possible_samples)

    def _derive_axis_permutation(
        self,
        pre_medians: Mapping[str, np.ndarray],
        axis: str,
        tolerance_mm: float,
    ) -> tuple[MarkerPermutation, float, float | None, str]:
        labels = sorted(pre_medians)
        if len(labels) < self.minimum_common_markers:
            return (), 0.0, None, "Too few markers define a local-axis permutation."

        target_positions = np.vstack([pre_medians[label] for label in labels])
        source_positions = local_axis_half_turn(axis).apply(target_positions)
        costs = np.linalg.norm(
            target_positions[:, None, :] - source_positions[None, :, :],
            axis=2,
        )
        rows, columns = linear_sum_assignment(costs)
        pairs = tuple(
            sorted((labels[int(row)], labels[int(column)]) for row, column in zip(rows, columns))
        )
        distances = np.array([costs[row, column] for row, column in zip(rows, columns)])
        correspondence = float(np.mean(distances <= tolerance_mm))
        rmse = float(np.sqrt(np.mean(distances**2))) if distances.size else None

        try:
            permutation = _normalize_permutation(pairs)
        except ValueError as exc:
            return (), correspondence, rmse, str(exc)
        if not np.all(distances <= tolerance_mm):
            return (), correspondence, rmse, "Some markers have no geometric half-turn counterpart."
        if all(destination == source for destination, source in permutation):
            return (), correspondence, rmse, "Identity mapping does not correct a marker flip."
        return permutation, correspondence, rmse, ""

    def _evaluate_correspondence(
        self,
        pre_medians: Mapping[str, np.ndarray],
        post_medians: Mapping[str, np.ndarray],
        permutation: MarkerPermutation,
        marker_count: int,
        tolerance_mm: float,
        pre_sample_coverage: float,
        post_sample_coverage: float,
    ) -> tuple[float, float, int, float | None]:
        distances = []
        for destination, source in permutation:
            if destination not in pre_medians or source not in post_medians:
                continue
            distances.append(
                float(np.linalg.norm(pre_medians[destination] - post_medians[source]))
            )

        common_count = len(distances)
        if common_count == 0:
            return 0.0, 0.0, 0, None
        distance_array = np.asarray(distances, dtype=float)
        correspondence = float(np.count_nonzero(distance_array <= tolerance_mm) / marker_count)
        coverage = min(
            pre_sample_coverage,
            post_sample_coverage,
            common_count / max(1, marker_count),
        )
        rmse = float(np.sqrt(np.mean(distance_array**2)))
        return correspondence, coverage, common_count, rmse

    def _evaluate_hypothesis(
        self,
        *,
        label: str,
        marker_df: pd.DataFrame,
        pose_df: pd.DataFrame,
        pre_positions: Sequence[int],
        post_positions: Sequence[int],
        marker_ids: Sequence[str],
        pre_rotation: R,
        pre_medians: Mapping[str, np.ndarray],
        pre_sample_coverage: float,
        no_correction_residual_deg: float,
        tolerance_mm: float,
    ) -> MarkerFlipHypothesis:
        correction = None if label == _NO_CORRECTION else local_axis_half_turn(label)
        post_rotation = self._representative_rotation(
            pose_df,
            post_positions,
            correction=correction,
        )
        residual_deg = float(np.degrees((pre_rotation.inv() * post_rotation).magnitude()))

        if label == _NO_CORRECTION:
            permutation = tuple((marker_id, marker_id) for marker_id in marker_ids)
            layout_correspondence = 1.0
            mapping_reason = ""
        else:
            (
                permutation,
                layout_correspondence,
                _layout_rmse,
                mapping_reason,
            ) = self._derive_axis_permutation(pre_medians, label, tolerance_mm)

        post_medians, post_sample_coverage = self._local_marker_medians(
            marker_df,
            pose_df,
            post_positions,
            marker_ids,
            correction=correction,
        )
        if permutation:
            (
                observed_correspondence,
                coverage,
                common_count,
                marker_rmse,
            ) = self._evaluate_correspondence(
                pre_medians,
                post_medians,
                permutation,
                len(marker_ids),
                tolerance_mm,
                pre_sample_coverage,
                post_sample_coverage,
            )
        else:
            observed_correspondence = 0.0
            coverage = 0.0
            common_count = 0
            marker_rmse = None

        orientation_score = max(0.0, 1.0 - min(residual_deg, 180.0) / 180.0)
        geometric_score = min(layout_correspondence, observed_correspondence)
        score = float(orientation_score * geometric_score)
        stored_permutation = () if label == _NO_CORRECTION else permutation
        return MarkerFlipHypothesis(
            label=label,
            residual_deg=residual_deg,
            discontinuity_reduction_deg=float(
                no_correction_residual_deg - residual_deg
            ),
            score=score,
            layout_correspondence_ratio=layout_correspondence,
            observed_correspondence_ratio=observed_correspondence,
            coverage_ratio=coverage,
            common_marker_count=common_count,
            marker_rmse_mm=marker_rmse,
            permutation=stored_permutation,
            mapping_reason=mapping_reason,
        )

    def _insufficient_window_candidate(
        self,
        *,
        event_id: str,
        boundary_time: float,
        trigger: str,
    ) -> MarkerFlipCandidate:
        return MarkerFlipCandidate(
            event_id=event_id,
            boundary_time_sec=boundary_time,
            trigger=trigger,
            recommendation_axis=None,
            best_hypothesis_label=_NO_CORRECTION,
            no_correction_residual_deg=float("inf"),
            best_residual_deg=float("inf"),
            discontinuity_reduction_deg=0.0,
            confidence_margin=0.0,
            correspondence_ratio=0.0,
            marker_rmse_mm=None,
            coverage_ratio=0.0,
            common_marker_count=0,
            pre_stability_deg=float("inf"),
            post_stability_deg=float("inf"),
            reason="Insufficient valid samples in the stable windows.",
        )

    def _review_boundary(
        self,
        marker_df: pd.DataFrame,
        pose_df: pd.DataFrame,
        box_dims: Sequence[float],
        pre_anchor: int,
        post_anchor: int,
        trigger: str,
    ) -> MarkerFlipCandidate:
        valid_positions = set(self._valid_pose_positions(pose_df).tolist())
        pre_positions = [
            position
            for position in range(max(0, pre_anchor - self.window_size + 1), pre_anchor + 1)
            if position in valid_positions
        ]
        post_positions = [
            position
            for position in range(
                post_anchor,
                min(
                    len(pose_df),
                    post_anchor + self.window_size + self.pose_lag_merge_samples,
                ),
            )
            if position in valid_positions
        ]
        pre_positions = self._stable_contiguous_positions(
            pose_df,
            pre_positions,
            side="pre",
        )
        post_positions = self._stable_contiguous_positions(
            pose_df,
            post_positions,
            side="post",
        )
        boundary_time = float(pose_df.index[post_anchor])
        event_id = f"flip-{post_anchor:06d}"

        if (
            len(pre_positions) < self.minimum_window_samples
            or len(post_positions) < self.minimum_window_samples
        ):
            return self._insufficient_window_candidate(
                event_id=event_id,
                boundary_time=boundary_time,
                trigger=trigger,
            )

        marker_ids = self._marker_ids(marker_df)
        if len(marker_ids) < self.minimum_common_markers:
            candidate = self._insufficient_window_candidate(
                event_id=event_id,
                boundary_time=boundary_time,
                trigger=trigger,
            )
            return MarkerFlipCandidate(
                **{
                    **candidate.__dict__,
                    "reason": "Too few labeled markers are available for geometric correspondence.",
                }
            )

        pre_rotation = self._representative_rotation(pose_df, pre_positions)
        post_rotation = self._representative_rotation(pose_df, post_positions)
        no_correction_residual = float(
            np.degrees((pre_rotation.inv() * post_rotation).magnitude())
        )
        pre_stability = self._window_stability(pose_df, pre_positions)
        post_stability = self._window_stability(pose_df, post_positions)
        box_diagonal = max(float(np.linalg.norm(np.asarray(box_dims, dtype=float))), 1.0)
        tolerance_mm = box_diagonal * self.correspondence_tolerance_fraction
        pre_medians, pre_sample_coverage = self._local_marker_medians(
            marker_df,
            pose_df,
            pre_positions,
            marker_ids,
        )

        hypotheses = tuple(
            self._evaluate_hypothesis(
                label=label,
                marker_df=marker_df,
                pose_df=pose_df,
                pre_positions=pre_positions,
                post_positions=post_positions,
                marker_ids=marker_ids,
                pre_rotation=pre_rotation,
                pre_medians=pre_medians,
                pre_sample_coverage=pre_sample_coverage,
                no_correction_residual_deg=no_correction_residual,
                tolerance_mm=tolerance_mm,
            )
            for label in (_NO_CORRECTION, *SUPPORTED_LOCAL_AXES)
        )
        ranked = sorted(
            hypotheses,
            key=lambda item: (
                -item.score,
                item.label != _NO_CORRECTION,
                item.residual_deg,
                item.label,
            ),
        )
        best = ranked[0]
        second = ranked[1]
        confidence_margin = max(0.0, float(best.score - second.score))

        pre_rotations = self._rotations_for_positions(pose_df, pre_positions)
        post_rotations = self._rotations_for_positions(pose_df, post_positions)
        pre_trace = np.degrees((pre_rotation.inv() * pre_rotations).magnitude())
        post_raw_trace = np.degrees((pre_rotation.inv() * post_rotations).magnitude())
        best_correction = (
            None if best.label == _NO_CORRECTION else local_axis_half_turn(best.label)
        )
        corrected_post_rotations = (
            post_rotations
            if best_correction is None
            else post_rotations * best_correction
        )
        post_best_trace = np.degrees(
            (pre_rotation.inv() * corrected_post_rotations).magnitude()
        )
        pre_time_offsets = (
            pd.to_numeric(pd.Index(pose_df.index[pre_positions]), errors="coerce").to_numpy(
                dtype=float
            )
            - boundary_time
        )
        post_time_offsets = (
            pd.to_numeric(pd.Index(pose_df.index[post_positions]), errors="coerce").to_numpy(
                dtype=float
            )
            - boundary_time
        )

        recommendation: str | None = None
        reason = "No supported local-axis correction passes the recommendation gates."
        if best.label == _NO_CORRECTION:
            if "gap" in trigger.lower() or "freeze" in trigger.lower():
                reason = "Gap/freeze evidence does not show a supported marker-label flip."
            else:
                reason = "No correction produced the strongest evidence."
        elif pre_stability > self.maximum_window_motion_deg or post_stability > self.maximum_window_motion_deg:
            reason = "The windows around the event are not stable enough for a recommendation."
        elif not best.permutation:
            reason = best.mapping_reason or "No reversible marker permutation is available."
        elif best.common_marker_count < self.minimum_common_markers:
            reason = "Too few corresponding markers are available for a recommendation."
        elif best.coverage_ratio < self.minimum_coverage_ratio:
            reason = "Marker/data coverage is below the configured recommendation gate."
        elif best.observed_correspondence_ratio < self.minimum_correspondence_ratio:
            reason = "Geometric marker correspondence is below the configured recommendation gate."
        elif best.layout_correspondence_ratio < self.minimum_correspondence_ratio:
            reason = "The local marker layout does not support a unique reversible axis permutation."
        elif best.residual_deg > self.maximum_corrected_residual_deg:
            reason = "The discontinuity is not consistent with a supported 180-degree local-axis flip."
        elif best.discontinuity_reduction_deg < self.minimum_discontinuity_reduction_deg:
            reason = "The orientation discontinuity reduction is below the configured gate."
        elif confidence_margin < self.minimum_confidence_margin:
            reason = "The evidence margin over the second-best alternative is too small."
        else:
            recommendation = best.label
            reason = (
                f"Evidence supports the local {best.label} 180-degree marker-label permutation."
            )

        return MarkerFlipCandidate(
            event_id=event_id,
            boundary_time_sec=boundary_time,
            trigger=trigger,
            recommendation_axis=recommendation,
            best_hypothesis_label=best.label,
            no_correction_residual_deg=no_correction_residual,
            best_residual_deg=best.residual_deg,
            discontinuity_reduction_deg=best.discontinuity_reduction_deg,
            confidence_margin=confidence_margin,
            correspondence_ratio=best.observed_correspondence_ratio,
            marker_rmse_mm=best.marker_rmse_mm,
            coverage_ratio=best.coverage_ratio,
            common_marker_count=best.common_marker_count,
            pre_stability_deg=pre_stability,
            post_stability_deg=post_stability,
            reason=reason,
            hypotheses=hypotheses,
            pre_window_time_offsets_sec=tuple(float(value) for value in pre_time_offsets),
            post_window_time_offsets_sec=tuple(float(value) for value in post_time_offsets),
            pre_window_residual_deg=tuple(float(value) for value in pre_trace),
            post_window_raw_residual_deg=tuple(float(value) for value in post_raw_trace),
            post_window_best_residual_deg=tuple(float(value) for value in post_best_trace),
        )

    def _freeze_reconnect_boundaries(self, marker_df: pd.DataFrame) -> list[tuple[int, int]]:
        marker_ids = self._marker_ids(marker_df)
        coordinate_columns = [
            f"{marker_id}{suffix}"
            for marker_id in marker_ids
            for suffix in (
                RawMarkerCols.X_SUFFIX,
                RawMarkerCols.Y_SUFFIX,
                RawMarkerCols.Z_SUFFIX,
            )
        ]
        if not coordinate_columns:
            return []
        values = marker_df[coordinate_columns].apply(pd.to_numeric, errors="coerce").to_numpy(
            dtype=float
        )

        def rows_match(left: int, right: int) -> bool:
            common = np.isfinite(values[left]) & np.isfinite(values[right])
            if np.count_nonzero(common) < self.minimum_common_markers * 3:
                return False
            return bool(
                np.max(np.abs(values[left, common] - values[right, common]))
                <= self.freeze_tolerance_mm
            )

        boundaries: list[tuple[int, int]] = []
        run_start: int | None = None
        for position in range(1, len(values)):
            if rows_match(position - 1, position):
                if run_start is None:
                    run_start = position - 1
                continue
            if run_start is not None and position - run_start >= self.freeze_min_samples:
                boundaries.append((run_start, position))
            run_start = None
        return boundaries

    def _marker_label_discontinuities(
        self,
        marker_df: pd.DataFrame,
        box_dims: Sequence[float],
    ) -> list[tuple[int, float, float]]:
        marker_ids = self._marker_ids(marker_df)
        if len(marker_ids) < self.minimum_common_markers:
            return []

        box_diagonal = max(float(np.linalg.norm(np.asarray(box_dims, dtype=float))), 1.0)
        jump_threshold = box_diagonal * self.marker_jump_fraction
        continuity_threshold = box_diagonal * self.marker_set_continuity_fraction
        reduction_threshold = box_diagonal * self.marker_jump_reduction_fraction
        boundaries: list[tuple[int, float, float]] = []

        for position in range(1, len(marker_df)):
            pre_row = marker_df.iloc[position - 1]
            post_row = marker_df.iloc[position]
            pre_points = []
            post_points = []
            for marker_id in marker_ids:
                pre_point = np.array(
                    [
                        pre_row.get(f"{marker_id}{RawMarkerCols.X_SUFFIX}"),
                        pre_row.get(f"{marker_id}{RawMarkerCols.Y_SUFFIX}"),
                        pre_row.get(f"{marker_id}{RawMarkerCols.Z_SUFFIX}"),
                    ],
                    dtype=float,
                )
                post_point = np.array(
                    [
                        post_row.get(f"{marker_id}{RawMarkerCols.X_SUFFIX}"),
                        post_row.get(f"{marker_id}{RawMarkerCols.Y_SUFFIX}"),
                        post_row.get(f"{marker_id}{RawMarkerCols.Z_SUFFIX}"),
                    ],
                    dtype=float,
                )
                if not np.isfinite(pre_point).all() or not np.isfinite(post_point).all():
                    continue
                pre_points.append(pre_point)
                post_points.append(post_point)

            if len(pre_points) < self.minimum_common_markers:
                continue

            pre_array = np.vstack(pre_points)
            post_array = np.vstack(post_points)
            pre_centered = pre_array - np.mean(pre_array, axis=0)
            post_centered = post_array - np.mean(post_array, axis=0)
            direct_distances = np.linalg.norm(post_centered - pre_centered, axis=1)
            direct_rmse = float(np.sqrt(np.mean(direct_distances**2)))
            assignment_costs = np.linalg.norm(
                pre_centered[:, None, :] - post_centered[None, :, :],
                axis=2,
            )
            rows, columns = linear_sum_assignment(assignment_costs)
            assigned_distances = assignment_costs[rows, columns]
            assignment_rmse = float(np.sqrt(np.mean(assigned_distances**2)))

            if (
                direct_rmse >= jump_threshold
                and assignment_rmse <= continuity_threshold
                and direct_rmse - assignment_rmse >= reduction_threshold
            ):
                boundaries.append((position, direct_rmse, assignment_rmse))
        return boundaries

    def detect(
        self,
        marker_df: pd.DataFrame,
        pose_df: pd.DataFrame,
        box_dims: Sequence[float],
    ) -> list[MarkerFlipCandidate]:
        if marker_df is None or pose_df is None or marker_df.empty or pose_df.empty:
            return []
        if len(marker_df) != len(pose_df) or not marker_df.index.equals(pose_df.index):
            raise ValueError("Marker and pose data must have the same rows and time index.")

        numeric_time = pd.to_numeric(pd.Index(pose_df.index), errors="coerce").to_numpy(dtype=float)
        if not np.isfinite(numeric_time).all() or not np.all(np.diff(numeric_time) > 0):
            raise ValueError("Marker flip review requires finite, strictly increasing timestamps.")
        valid_positions = self._valid_pose_positions(pose_df)
        if len(valid_positions) < 2:
            return []
        positive_deltas = np.diff(numeric_time)
        positive_deltas = positive_deltas[np.isfinite(positive_deltas) & (positive_deltas > 0)]
        median_delta = float(np.median(positive_deltas)) if positive_deltas.size else 0.0

        events: dict[int, dict[str, object]] = {}

        def add_event(pre_anchor: int, post_anchor: int, trigger: str) -> None:
            entry = events.setdefault(
                int(post_anchor),
                {"pre_anchor": int(pre_anchor), "triggers": []},
            )
            entry["pre_anchor"] = min(int(entry["pre_anchor"]), int(pre_anchor))
            triggers = entry["triggers"]
            if isinstance(triggers, list) and trigger not in triggers:
                triggers.append(trigger)

        marker_event_positions: list[int] = []
        for post_anchor, direct_rmse, assignment_rmse in self._marker_label_discontinuities(
            marker_df,
            box_dims,
        ):
            marker_event_positions.append(post_anchor)
            add_event(
                post_anchor - 1,
                post_anchor,
                (
                    "marker label discontinuity "
                    f"(labeled RMSE {direct_rmse:.1f} mm, set RMSE {assignment_rmse:.1f} mm)"
                ),
            )

        for pre_anchor, post_anchor in zip(valid_positions[:-1], valid_positions[1:]):
            pre_anchor = int(pre_anchor)
            post_anchor = int(post_anchor)
            pre_rotation = self._rotations_for_positions(pose_df, [pre_anchor])
            post_rotation = self._rotations_for_positions(pose_df, [post_anchor])
            jump_deg = float(np.degrees((pre_rotation.inv() * post_rotation).magnitude())[0])
            time_delta = numeric_time[post_anchor] - numeric_time[pre_anchor]
            gap_found = (
                post_anchor - pre_anchor > 1
                or (median_delta > 0 and time_delta > self.gap_factor * median_delta)
            )
            if jump_deg >= self.candidate_angle_deg:
                delayed_marker_event = next(
                    (
                        marker_position
                        for marker_position in reversed(marker_event_positions)
                        if 0 <= post_anchor - marker_position <= self.pose_lag_merge_samples
                    ),
                    None,
                )
                if delayed_marker_event is None:
                    add_event(pre_anchor, post_anchor, f"rotation jump {jump_deg:.1f}°")
                else:
                    add_event(
                        delayed_marker_event - 1,
                        delayed_marker_event,
                        f"delayed rotation jump {jump_deg:.1f}°",
                    )
            if gap_found:
                add_event(pre_anchor, post_anchor, "tracking gap")

        for freeze_start, reconnect_position in self._freeze_reconnect_boundaries(marker_df):
            earlier = valid_positions[valid_positions <= freeze_start]
            later = valid_positions[valid_positions >= reconnect_position]
            if earlier.size == 0 or later.size == 0:
                continue
            add_event(int(earlier[-1]), int(later[0]), "freeze/reconnect")

        candidates = []
        for post_anchor in sorted(events):
            entry = events[post_anchor]
            triggers = entry["triggers"]
            trigger_text = ", ".join(triggers) if isinstance(triggers, list) else str(triggers)
            candidates.append(
                self._review_boundary(
                    marker_df,
                    pose_df,
                    box_dims,
                    int(entry["pre_anchor"]),
                    int(post_anchor),
                    trigger_text,
                )
            )
        return candidates


def marker_triplet_indices(header_info: Mapping[str, Sequence[str]]) -> dict[str, tuple[int, int, int]]:
    type_header = list(header_info.get("type", []))
    name_header = list(header_info.get("name", []))
    parent_header = list(header_info.get("parent", []))
    category_header = list(header_info.get("category", []))
    component_header = list(header_info.get("component", []))
    header_len = min(
        len(type_header),
        len(name_header),
        len(parent_header),
        len(category_header),
        len(component_header),
    )

    marker_columns: dict[str, tuple[int, int, int]] = {}
    for index in range(max(0, header_len - 2)):
        if not (
            type_header[index] == "Rigid Body Marker"
            and parent_header[index]
            and ":" in name_header[index]
            and category_header[index] == "Position"
            and component_header[index].upper() == "X"
            and category_header[index + 1] == "Position"
            and component_header[index + 1].upper() == "Y"
            and category_header[index + 2] == "Position"
            and component_header[index + 2].upper() == "Z"
        ):
            continue
        for key in ("type", "name", "parent", "id"):
            row = header_info.get(key, [])
            if len(row) <= index + 2 or len(set(row[index:index + 3])) != 1:
                raise ValueError("Marker XYZ triplet has inconsistent identity.")
        marker_id = name_header[index].split(":", 1)[1].replace(" ", "_")
        if marker_id in marker_columns:
            raise ValueError(f"Duplicate raw marker label in header: {marker_id}")
        marker_columns[marker_id] = (index, index + 1, index + 2)
    covered = {i for indices in marker_columns.values() for i in indices}
    expected = {i for i, kind in enumerate(type_header)
                if kind == "Rigid Body Marker" and i < len(category_header)
                and category_header[i] == "Position"}
    if covered != expected:
        raise ValueError("Rigid Body Marker positions require complete, identified XYZ triplets.")
    return marker_columns


def _raw_time_values(raw_df: pd.DataFrame) -> np.ndarray:
    matching_positions = [
        index for index, column in enumerate(raw_df.columns) if str(column) == TimeCols.TIME
    ]
    time_position = matching_positions[0] if matching_positions else 1
    if raw_df.shape[1] <= time_position:
        raise ValueError("Raw marker data is missing the time column.")
    values = pd.to_numeric(raw_df.iloc[:, time_position], errors="coerce").to_numpy(dtype=float)
    if not np.isfinite(values).all():
        raise ValueError("Marker correction requires finite numeric time values.")
    return values


def apply_approved_marker_permutations(
    raw_df: pd.DataFrame,
    header_info: Mapping[str, Sequence[str]],
    decisions: Iterable[MarkerCorrectionDecision | Mapping[str, object]] | None,
    *,
    reverse: bool = False,
) -> pd.DataFrame:
    """Reassign marker XYZ columns while preserving every measured coordinate value."""

    result = raw_df.copy(deep=True)
    approved = normalize_marker_corrections(decisions, approved_only=True)
    if any(item.correction_kind != "marker_permutation" for item in approved):
        raise ValueError("Face assignments cannot be applied as XYZ permutations.")
    if reverse:
        approved = list(reversed(approved))
    if result.empty or not approved:
        return result

    marker_columns = marker_triplet_indices(header_info)
    time_values = _raw_time_values(result)
    for decision in approved:
        suffix_positions = np.flatnonzero(
            time_values >= float(decision.boundary_time_sec) - 1e-12
        )
        if suffix_positions.size == 0:
            continue
        missing = sorted(
            {
                marker_id
                for pair in decision.permutation
                for marker_id in pair
                if marker_id not in marker_columns
            }
        )
        if missing:
            raise ValueError(
                "Marker correction references labels missing from the raw header: "
                + ", ".join(missing)
            )

        snapshot = result.iloc[suffix_positions, :].copy(deep=True)
        for destination, source in decision.permutation:
            destination_columns = list(marker_columns[destination])
            source_columns = list(marker_columns[source])
            result.iloc[suffix_positions, destination_columns] = snapshot.iloc[
                :, source_columns
            ].to_numpy(copy=True)
    return result


def undo_approved_marker_permutations(
    raw_df: pd.DataFrame,
    header_info: Mapping[str, Sequence[str]],
    decisions: Iterable[MarkerCorrectionDecision | Mapping[str, object]] | None,
) -> pd.DataFrame:
    return apply_approved_marker_permutations(
        raw_df,
        header_info,
        decisions,
        reverse=True,
    )
