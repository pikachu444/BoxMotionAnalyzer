import numpy as np
import pandas as pd
from scipy.spatial.transform import Rotation as R

from src.config.data_columns import (
    CornerCoordCols,
    DropPostureCols,
    DropPostureSummaryCols,
    PoseCols,
)


class DropPosturePostProcessor:
    def __init__(
        self,
        *,
        face_definitions: dict,
        local_box_corners,
        vertical_axis_idx: int = 1,
        floor_level: float = 0.0,
    ):
        self.face_definitions = face_definitions
        self.local_box_corners = np.asarray(local_box_corners, dtype=float)
        self.vertical_axis_idx = int(vertical_axis_idx)
        self.floor_level = float(floor_level)
        self.corner_coord_cols = [
            [
                f"C{i + 1}{CornerCoordCols.X_SUFFIX}",
                f"C{i + 1}{CornerCoordCols.Y_SUFFIX}",
                f"C{i + 1}{CornerCoordCols.Z_SUFFIX}",
            ]
            for i in range(8)
        ]

    def configure_geometry(self, local_box_corners) -> None:
        self.local_box_corners = np.asarray(local_box_corners, dtype=float)

    def _required_columns(self) -> list[str]:
        columns = [PoseCols.ROT_X, PoseCols.ROT_Y, PoseCols.ROT_Z]
        for corner_cols in self.corner_coord_cols:
            columns.extend(corner_cols)
        return columns

    def _corner_positions(self, df: pd.DataFrame) -> np.ndarray:
        data = np.empty((len(df), 8, 3), dtype=float)
        for corner_idx, corner_cols in enumerate(self.corner_coord_cols):
            data[:, corner_idx, :] = df[corner_cols].to_numpy(dtype=float)
        return data

    def _detect_t1_minus_index(
        self,
        min_heights: np.ndarray,
        contact_threshold_mm: float,
    ) -> tuple[int | None, bool]:
        threshold = self.floor_level + float(contact_threshold_mm)
        contact_indices = np.flatnonzero(min_heights <= threshold)
        if len(contact_indices) == 0:
            return None, False

        first_contact_idx = int(contact_indices[0])
        if first_contact_idx == 0:
            return 0, True
        return first_contact_idx - 1, True

    def _contiguous_runs(self, mask: np.ndarray) -> list[tuple[int, int]]:
        runs = []
        start = None
        for pos, active in enumerate(mask):
            if active and start is None:
                start = pos
            elif not active and start is not None:
                runs.append((start, pos - start))
                start = None
        if start is not None:
            runs.append((start, len(mask) - start))
        return runs

    def _first_run_start(self, mask: np.ndarray, min_length: int) -> int | None:
        for start, length in self._contiguous_runs(mask):
            if length >= min_length:
                return int(start)
        return None

    def _smooth_min_heights(self, values: np.ndarray) -> np.ndarray:
        if len(values) < 5:
            return values.astype(float, copy=True)

        window = min(11, len(values) if len(values) % 2 == 1 else len(values) - 1)
        if window < 5:
            return values.astype(float, copy=True)

        padded = np.pad(values.astype(float), (window // 2, window // 2), mode="edge")
        kernel = np.ones(window, dtype=float) / float(window)
        return np.convolve(padded, kernel, mode="valid")

    def _contact_analysis(
        self,
        *,
        min_heights: np.ndarray,
        index: pd.Index,
        contact_threshold_mm: float,
    ) -> dict[str, object]:
        threshold = self.floor_level + float(contact_threshold_mm)
        absolute_contact = min_heights <= threshold
        threshold_start = self._first_run_start(absolute_contact, min_length=2)
        threshold_detected = threshold_start is not None
        threshold_impact_detected = threshold_start is not None and threshold_start > 0

        smooth_heights = self._smooth_min_heights(min_heights)
        time_values = index.to_numpy(dtype=float)
        if len(time_values) >= 2 and np.ptp(time_values) > 0:
            velocity = np.gradient(smooth_heights, time_values)
            acceleration = np.gradient(velocity, time_values)
        else:
            velocity = np.zeros_like(smooth_heights)
            acceleration = np.zeros_like(smooth_heights)

        min_pos = int(np.nanargmin(smooth_heights))
        height_range = float(np.nanmax(smooth_heights) - np.nanmin(smooth_heights))
        smallest_dim = float(np.nanmin(np.ptp(self.local_box_corners, axis=0)))
        near_floor_band = max(float(contact_threshold_mm), 0.03 * smallest_dim, 2.0)
        relative_contact_band = max(float(contact_threshold_mm), 0.05 * max(height_range, 1.0), 2.0)
        significant_drop = max(5.0, min(30.0, 0.20 * max(height_range, 1.0)))

        pre_start = max(0, min_pos - 12)
        post_end = min(len(smooth_heights), min_pos + 13)
        pre_segment = smooth_heights[pre_start : min_pos + 1]
        approach_drop = float(np.nanmax(pre_segment) - smooth_heights[min_pos]) if len(pre_segment) else 0.0
        descending_before = bool(min_pos > 1 and np.nanmin(velocity[pre_start : min_pos + 1]) < -50.0)
        rebounds_after = bool(min_pos < len(velocity) - 2 and np.nanmax(velocity[min_pos:post_end]) > 50.0)
        positive_curvature = bool(min_pos < len(acceleration) and acceleration[min_pos] > 1000.0)
        near_floor = bool(smooth_heights[min_pos] <= self.floor_level + near_floor_band)
        motion_detected = bool(
            near_floor
            and approach_drop >= significant_drop
            and descending_before
            and (rebounds_after or positive_curvature)
        )

        motion_start = None
        if motion_detected:
            low_cutoff = smooth_heights[min_pos] + relative_contact_band
            for pos in range(min_pos, -1, -1):
                if smooth_heights[pos] > low_cutoff:
                    motion_start = min(pos + 1, len(smooth_heights) - 1)
                    break
            if motion_start is None:
                motion_start = min_pos

        tail_start = max(0, int(len(smooth_heights) * 0.65))
        tail = smooth_heights[tail_start:]
        tail_velocity = velocity[tail_start:]
        plateau_level = float(np.nanmedian(tail)) if len(tail) else np.nan
        plateau_std = float(np.nanstd(tail)) if len(tail) else np.inf
        plateau_speed = float(np.nanmedian(np.abs(tail_velocity))) if len(tail_velocity) else np.inf
        sustained_detected = bool(
            len(tail) >= 5
            and plateau_level <= self.floor_level + max(near_floor_band, 0.10 * smallest_dim)
            and plateau_std <= max(3.0, 0.025 * smallest_dim)
            and plateau_speed <= 150.0
        )

        impact_start = threshold_start if threshold_impact_detected else motion_start
        impact_detected = impact_start is not None
        if impact_detected:
            contact_state = "ImpactEvent"
        elif sustained_detected:
            contact_state = "SustainedContact"
        elif height_range >= significant_drop and np.nanmin(velocity) < -50.0:
            contact_state = "Approach"
        else:
            contact_state = "NoContact"

        method_parts = []
        confidence = 0.0
        if threshold_detected:
            method_parts.append("threshold")
            confidence += 0.35 if threshold_impact_detected else 0.15
        if motion_detected:
            method_parts.append("motion")
            confidence += 0.40
        if sustained_detected:
            method_parts.append("plateau")
            confidence += 0.20
        if contact_state == "NoContact":
            method = "none"
            confidence = 0.0
        else:
            method = "+".join(method_parts) if method_parts else "trend"
            confidence = min(1.0, confidence if confidence > 0 else 0.25)

        active_mask = np.zeros(len(min_heights), dtype=bool)
        if impact_detected:
            low_cutoff = np.nanmin(smooth_heights) + relative_contact_band
            after_start = np.arange(len(min_heights)) >= int(impact_start)
            active_mask = absolute_contact | (after_start & (smooth_heights <= low_cutoff))

        t1_minus_pos = None
        if impact_detected:
            t1_minus_pos = max(int(impact_start) - 1, 0)

        return {
            "t1_minus_pos": t1_minus_pos,
            "t1_detected": bool(impact_detected),
            "impact_detected": bool(impact_detected),
            "sustained_contact_detected": bool(sustained_detected),
            "contact_state": contact_state,
            "contact_confidence": float(confidence),
            "contact_detection_method": method,
            "active_mask": active_mask,
            "relative_contact_band": float(relative_contact_band),
        }

    def _contact_label(self, contact_set: tuple[int, ...]) -> str:
        labels = [f"C{corner_idx}" for corner_idx in contact_set]
        if len(labels) == 1:
            return labels[0]
        return "{" + ",".join(labels) + "}"

    def _contact_sets(
        self,
        vertical_positions: np.ndarray,
        contact_threshold_mm: float,
        *,
        active_mask: np.ndarray | None = None,
        relative_contact_band: float | None = None,
    ) -> list[tuple[int, ...]]:
        threshold = self.floor_level + float(contact_threshold_mm)
        contact_sets = []
        if active_mask is None:
            active_mask = np.ones(len(vertical_positions), dtype=bool)

        for pos, frame_heights in enumerate(vertical_positions):
            if not active_mask[pos]:
                contact_sets.append(tuple())
                continue

            if relative_contact_band is None:
                contact_indices = np.flatnonzero(frame_heights <= threshold)
            else:
                frame_min = np.nanmin(frame_heights)
                contact_indices = np.flatnonzero(frame_heights <= frame_min + float(relative_contact_band))
            contact_sets.append(tuple(int(index) + 1 for index in contact_indices))
        return contact_sets

    def _impact_sequence_summary(
        self,
        *,
        contact_sets: list[tuple[int, ...]],
        index: pd.Index,
        min_event_frames: int = 2,
    ) -> dict[str, object]:
        events = []
        current_set = tuple()
        current_start = None
        current_length = 0

        def flush_current():
            if current_set and current_start is not None and current_length >= min_event_frames:
                events.append(
                    {
                        "contact_set": current_set,
                        "start_pos": current_start,
                        "length": current_length,
                    }
                )

        for pos, contact_set in enumerate(contact_sets):
            if contact_set == current_set:
                if contact_set:
                    current_length += 1
                continue

            flush_current()
            current_set = contact_set
            current_start = pos if contact_set else None
            current_length = 1 if contact_set else 0

        flush_current()

        if not events:
            return {
                DropPostureSummaryCols.IMPACT_SEQUENCE: "",
                DropPostureSummaryCols.IMPACT_EVENT_COUNT: 0,
                DropPostureSummaryCols.FIRST_IMPACT_TIME_SEC: np.nan,
                DropPostureSummaryCols.FIRST_IMPACT_CONTACT: "",
            }

        sequence = " -> ".join(self._contact_label(event["contact_set"]) for event in events)
        first_event = events[0]
        first_time = index[int(first_event["start_pos"])]
        return {
            DropPostureSummaryCols.IMPACT_SEQUENCE: sequence,
            DropPostureSummaryCols.IMPACT_EVENT_COUNT: len(events),
            DropPostureSummaryCols.FIRST_IMPACT_TIME_SEC: float(first_time),
            DropPostureSummaryCols.FIRST_IMPACT_CONTACT: self._contact_label(first_event["contact_set"]),
        }

    def _face_world_normal(self, face: dict, rotation: R) -> np.ndarray:
        normal = np.zeros(3, dtype=float)
        normal[int(face["axis_idx"])] = float(face["direction"])
        return rotation.apply(normal)

    def _select_reference_face(self, rotation: R) -> str:
        downward = np.zeros(3, dtype=float)
        downward[self.vertical_axis_idx] = -1.0

        best_label = None
        best_score = -np.inf
        for label, face in self.face_definitions.items():
            normal_world = self._face_world_normal(face, rotation)
            normal_world = normal_world / np.linalg.norm(normal_world)
            score = float(np.dot(normal_world, downward))
            if score > best_score:
                best_label = label
                best_score = score

        if best_label is None:
            raise ValueError("No face definitions are available for drop posture analysis.")
        return str(best_label)

    def _reference_axes(self, face_label: str) -> tuple[int, int]:
        face = self.face_definitions[face_label]
        bound_axes = list(face["bound_axes_indices"])
        if len(bound_axes) != 2:
            raise ValueError(f"Face {face_label!r} must define exactly two bound axes.")

        extents = np.ptp(self.local_box_corners[:, bound_axes], axis=0)
        if extents[0] >= extents[1]:
            return int(bound_axes[0]), int(bound_axes[1])
        return int(bound_axes[1]), int(bound_axes[0])

    def _axis_tilt_deg(
        self,
        corner_positions: np.ndarray,
        face_corner_indices: list[int],
        axis_idx: int,
    ) -> float:
        local_axis_values = self.local_box_corners[face_corner_indices, axis_idx]
        positive_mask = local_axis_values > 0
        negative_mask = local_axis_values < 0
        if not positive_mask.any() or not negative_mask.any():
            return np.nan

        face_positions = corner_positions[face_corner_indices]
        pos_height = np.mean(face_positions[positive_mask, self.vertical_axis_idx])
        neg_height = np.mean(face_positions[negative_mask, self.vertical_axis_idx])
        axis_length = float(np.ptp(self.local_box_corners[:, axis_idx]))
        if axis_length <= 0:
            return np.nan

        ratio = np.clip((pos_height - neg_height) / axis_length, -1.0, 1.0)
        return float(np.degrees(np.arcsin(ratio)))

    def _compute_frame_metrics(
        self,
        df: pd.DataFrame,
        corner_positions: np.ndarray,
        reference_face_label: str,
        long_axis_idx: int,
        short_axis_idx: int,
    ) -> pd.DataFrame:
        face = self.face_definitions[reference_face_label]
        face_corner_indices = [int(index) for index in face["corners"]]
        downward = np.zeros(3, dtype=float)
        downward[self.vertical_axis_idx] = -1.0

        rotations = R.from_rotvec(df[[PoseCols.ROT_X, PoseCols.ROT_Y, PoseCols.ROT_Z]].to_numpy(dtype=float))
        beta_values = []
        theta_long_values = []
        theta_short_values = []
        for row_idx, rotation in enumerate(rotations):
            face_normal = self._face_world_normal(face, rotation)
            face_normal = face_normal / np.linalg.norm(face_normal)
            dot_value = np.clip(np.dot(face_normal, downward), -1.0, 1.0)
            beta_values.append(float(np.degrees(np.arccos(dot_value))))
            theta_long_values.append(
                self._axis_tilt_deg(corner_positions[row_idx], face_corner_indices, long_axis_idx)
            )
            theta_short_values.append(
                self._axis_tilt_deg(corner_positions[row_idx], face_corner_indices, short_axis_idx)
            )

        vertical_positions = corner_positions[:, :, self.vertical_axis_idx]
        return pd.DataFrame(
            {
                DropPostureCols.BETA_DEG: beta_values,
                DropPostureCols.THETA_LONG_DEG: theta_long_values,
                DropPostureCols.THETA_SHORT_DEG: theta_short_values,
                DropPostureCols.CMIN_INDEX: np.nanargmin(vertical_positions, axis=1) + 1,
                DropPostureCols.DELTA_H_MM: (
                    np.nanmax(vertical_positions[:, face_corner_indices], axis=1)
                    - np.nanmin(vertical_positions[:, face_corner_indices], axis=1)
                ),
            },
            index=df.index,
        )

    def _summary_data(
        self,
        *,
        metrics: pd.DataFrame,
        t1_minus_pos: int | None,
        t1_detected: bool,
        reference_face_label: str,
        long_axis_idx: int,
        short_axis_idx: int,
        impact_summary: dict[str, object],
        contact_analysis: dict[str, object],
    ) -> dict[str, object]:
        if t1_minus_pos is None:
            beta_at_t1 = np.nan
            theta_long_at_t1 = np.nan
            theta_short_at_t1 = np.nan
            delta_h_at_t1 = np.nan
            cmin_at_t1 = np.nan
            t1_time = np.nan
        else:
            t1_row = metrics.iloc[t1_minus_pos]
            beta_at_t1 = float(t1_row[DropPostureCols.BETA_DEG])
            theta_long_at_t1 = float(t1_row[DropPostureCols.THETA_LONG_DEG])
            theta_short_at_t1 = float(t1_row[DropPostureCols.THETA_SHORT_DEG])
            delta_h_at_t1 = float(t1_row[DropPostureCols.DELTA_H_MM])
            cmin_at_t1 = int(t1_row[DropPostureCols.CMIN_INDEX])
            t1_time = float(metrics.index[t1_minus_pos])

        return {
            DropPostureSummaryCols.BETA_AT_T1_MINUS_DEG: beta_at_t1,
            DropPostureSummaryCols.MAX_BETA_DEG: float(pd.to_numeric(metrics[DropPostureCols.BETA_DEG]).max()),
            DropPostureSummaryCols.THETA_LONG_AT_T1_MINUS_DEG: theta_long_at_t1,
            DropPostureSummaryCols.MAX_ABS_THETA_LONG_DEG: float(pd.to_numeric(metrics[DropPostureCols.THETA_LONG_DEG]).abs().max()),
            DropPostureSummaryCols.THETA_SHORT_AT_T1_MINUS_DEG: theta_short_at_t1,
            DropPostureSummaryCols.MAX_ABS_THETA_SHORT_DEG: float(pd.to_numeric(metrics[DropPostureCols.THETA_SHORT_DEG]).abs().max()),
            DropPostureSummaryCols.DELTA_H_AT_T1_MINUS_MM: delta_h_at_t1,
            DropPostureSummaryCols.MAX_DELTA_H_MM: float(pd.to_numeric(metrics[DropPostureCols.DELTA_H_MM]).max()),
            DropPostureSummaryCols.CMIN_AT_T1_MINUS_INDEX: cmin_at_t1,
            DropPostureSummaryCols.T1_MINUS_TIME_SEC: t1_time,
            DropPostureSummaryCols.REFERENCE_FACE: reference_face_label,
            DropPostureSummaryCols.LONG_AXIS: f"LocalAxis{long_axis_idx}",
            DropPostureSummaryCols.SHORT_AXIS: f"LocalAxis{short_axis_idx}",
            DropPostureSummaryCols.T1_DETECTED: bool(t1_detected),
            DropPostureSummaryCols.CONTACT_STATE: contact_analysis["contact_state"],
            DropPostureSummaryCols.CONTACT_CONFIDENCE: contact_analysis["contact_confidence"],
            DropPostureSummaryCols.CONTACT_DETECTION_METHOD: contact_analysis["contact_detection_method"],
            DropPostureSummaryCols.IMPACT_DETECTED: contact_analysis["impact_detected"],
            DropPostureSummaryCols.SUSTAINED_CONTACT_DETECTED: contact_analysis["sustained_contact_detected"],
            **impact_summary,
        }

    def process(self, df: pd.DataFrame, *, contact_threshold_mm: float = 1.0) -> pd.DataFrame:
        if df is None or df.empty:
            return df

        missing = [column for column in self._required_columns() if column not in df.columns]
        if missing:
            print(f"[DropPosturePostProcessor WARNING] Missing required columns: {sorted(missing)}")
            return df

        result = df.copy()
        corner_positions = self._corner_positions(result)
        vertical_positions = corner_positions[:, :, self.vertical_axis_idx]
        min_heights = np.nanmin(vertical_positions, axis=1)
        contact_analysis = self._contact_analysis(
            min_heights=min_heights,
            index=result.index,
            contact_threshold_mm=contact_threshold_mm,
        )
        t1_minus_pos = contact_analysis["t1_minus_pos"]
        t1_detected = contact_analysis["t1_detected"]
        contact_sets = self._contact_sets(
            vertical_positions,
            contact_threshold_mm,
            active_mask=contact_analysis["active_mask"],
            relative_contact_band=contact_analysis["relative_contact_band"],
        )
        impact_summary = self._impact_sequence_summary(contact_sets=contact_sets, index=result.index)

        reference_pos = t1_minus_pos if t1_minus_pos is not None else 0
        t1_rotation = R.from_rotvec(
            result.iloc[reference_pos][[PoseCols.ROT_X, PoseCols.ROT_Y, PoseCols.ROT_Z]].to_numpy(dtype=float)
        )
        reference_face_label = self._select_reference_face(t1_rotation)
        long_axis_idx, short_axis_idx = self._reference_axes(reference_face_label)

        metrics = self._compute_frame_metrics(
            result,
            corner_positions,
            reference_face_label,
            long_axis_idx,
            short_axis_idx,
        )
        summary = self._summary_data(
            metrics=metrics,
            t1_minus_pos=t1_minus_pos,
            t1_detected=t1_detected,
            reference_face_label=reference_face_label,
            long_axis_idx=long_axis_idx,
            short_axis_idx=short_axis_idx,
            impact_summary=impact_summary,
            contact_analysis=contact_analysis,
        )

        result = result.join(metrics)
        for column, value in summary.items():
            result[column] = value
        return result
