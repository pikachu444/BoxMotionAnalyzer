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
    ) -> tuple[int, bool]:
        threshold = self.floor_level + float(contact_threshold_mm)
        contact_indices = np.flatnonzero(min_heights <= threshold)
        if len(contact_indices) == 0:
            return int(np.nanargmin(min_heights)), False

        first_contact_idx = int(contact_indices[0])
        if first_contact_idx == 0:
            return 0, True
        return first_contact_idx - 1, True

    def _contact_label(self, contact_set: tuple[int, ...]) -> str:
        labels = [f"C{corner_idx}" for corner_idx in contact_set]
        if len(labels) == 1:
            return labels[0]
        return "{" + ",".join(labels) + "}"

    def _contact_sets(self, vertical_positions: np.ndarray, contact_threshold_mm: float) -> list[tuple[int, ...]]:
        threshold = self.floor_level + float(contact_threshold_mm)
        contact_sets = []
        for frame_heights in vertical_positions:
            contact_indices = np.flatnonzero(frame_heights <= threshold)
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
                DropPostureCols.DELTA_H_MM: np.nanmax(vertical_positions, axis=1) - np.nanmin(vertical_positions, axis=1),
            },
            index=df.index,
        )

    def _summary_data(
        self,
        *,
        metrics: pd.DataFrame,
        t1_minus_pos: int,
        t1_detected: bool,
        reference_face_label: str,
        long_axis_idx: int,
        short_axis_idx: int,
        impact_summary: dict[str, object],
    ) -> dict[str, object]:
        t1_row = metrics.iloc[t1_minus_pos]
        t1_time = metrics.index[t1_minus_pos]
        return {
            DropPostureSummaryCols.BETA_AT_T1_MINUS_DEG: float(t1_row[DropPostureCols.BETA_DEG]),
            DropPostureSummaryCols.MAX_BETA_DEG: float(pd.to_numeric(metrics[DropPostureCols.BETA_DEG]).max()),
            DropPostureSummaryCols.THETA_LONG_AT_T1_MINUS_DEG: float(t1_row[DropPostureCols.THETA_LONG_DEG]),
            DropPostureSummaryCols.MAX_ABS_THETA_LONG_DEG: float(pd.to_numeric(metrics[DropPostureCols.THETA_LONG_DEG]).abs().max()),
            DropPostureSummaryCols.THETA_SHORT_AT_T1_MINUS_DEG: float(t1_row[DropPostureCols.THETA_SHORT_DEG]),
            DropPostureSummaryCols.MAX_ABS_THETA_SHORT_DEG: float(pd.to_numeric(metrics[DropPostureCols.THETA_SHORT_DEG]).abs().max()),
            DropPostureSummaryCols.DELTA_H_AT_T1_MINUS_MM: float(t1_row[DropPostureCols.DELTA_H_MM]),
            DropPostureSummaryCols.MAX_DELTA_H_MM: float(pd.to_numeric(metrics[DropPostureCols.DELTA_H_MM]).max()),
            DropPostureSummaryCols.CMIN_AT_T1_MINUS_INDEX: int(t1_row[DropPostureCols.CMIN_INDEX]),
            DropPostureSummaryCols.T1_MINUS_TIME_SEC: float(t1_time),
            DropPostureSummaryCols.REFERENCE_FACE: reference_face_label,
            DropPostureSummaryCols.LONG_AXIS: f"LocalAxis{long_axis_idx}",
            DropPostureSummaryCols.SHORT_AXIS: f"LocalAxis{short_axis_idx}",
            DropPostureSummaryCols.T1_DETECTED: bool(t1_detected),
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
        t1_minus_pos, t1_detected = self._detect_t1_minus_index(min_heights, contact_threshold_mm)
        contact_sets = self._contact_sets(vertical_positions, contact_threshold_mm)
        impact_summary = self._impact_sequence_summary(contact_sets=contact_sets, index=result.index)

        t1_rotation = R.from_rotvec(
            result.iloc[t1_minus_pos][[PoseCols.ROT_X, PoseCols.ROT_Y, PoseCols.ROT_Z]].to_numpy(dtype=float)
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
        )

        result = result.join(metrics)
        for column, value in summary.items():
            result[column] = value
        return result
