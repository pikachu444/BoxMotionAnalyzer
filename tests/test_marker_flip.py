import json
import unittest

import numpy as np
import pandas as pd
from scipy.spatial.transform import Rotation as R

from src.analysis.pipeline.marker_flip import (
    MarkerCorrectionDecision,
    MarkerFlipAnalyzer,
    apply_approved_marker_permutations,
    marker_triplet_indices,
    undo_approved_marker_permutations,
)
from src.analysis.pipeline.pose_optimizer import PoseOptimizer
from src.config import config_app
from src.config.data_columns import PoseCols, TimeCols


ORACLE_HALF_TURNS = {
    "X": np.diag([1.0, -1.0, -1.0]),
    "Y": np.diag([-1.0, 1.0, -1.0]),
    "Z": np.diag([-1.0, -1.0, 1.0]),
}


def _corner_layout(extents=(70.0, 40.0, 20.0)) -> dict[str, np.ndarray]:
    layout = {}
    marker_index = 1
    for x_sign in (-1.0, 1.0):
        for y_sign in (-1.0, 1.0):
            for z_sign in (-1.0, 1.0):
                layout[f"M{marker_index}"] = np.array(
                    [
                        x_sign * extents[0],
                        y_sign * extents[1],
                        z_sign * extents[2],
                    ],
                    dtype=float,
                )
                marker_index += 1
    return layout


def _oracle_permutation(
    layout: dict[str, np.ndarray],
    matrix: np.ndarray,
) -> dict[str, str]:
    coordinate_to_label = {
        tuple(np.round(position, decimals=9)): label
        for label, position in layout.items()
    }
    permutation = {}
    for destination, position in layout.items():
        source_position = matrix @ position
        permutation[destination] = coordinate_to_label[
            tuple(np.round(source_position, decimals=9))
        ]
    return permutation


def _build_clean_stream(
    layout: dict[str, np.ndarray],
    *,
    frame_count: int = 50,
    truth_matrices: np.ndarray | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    times = np.arange(frame_count, dtype=float) * 0.01
    translations = np.column_stack(
        [
            np.arange(frame_count, dtype=float) * 0.7,
            np.arange(frame_count, dtype=float) * -0.2,
            np.arange(frame_count, dtype=float) * 0.1,
        ]
    )
    if truth_matrices is None:
        truth_matrices = np.repeat(np.eye(3)[None, :, :], frame_count, axis=0)

    marker_data: dict[str, np.ndarray] = {}
    for marker_id, local_position in layout.items():
        world = np.einsum("nij,j->ni", truth_matrices, local_position) + translations
        marker_data[f"{marker_id}_X"] = world[:, 0]
        marker_data[f"{marker_id}_Y"] = world[:, 1]
        marker_data[f"{marker_id}_Z"] = world[:, 2]

    marker_df = pd.DataFrame(marker_data, index=times)
    pose_df = pd.DataFrame(
        {
            PoseCols.POS_X: translations[:, 0],
            PoseCols.POS_Y: translations[:, 1],
            PoseCols.POS_Z: translations[:, 2],
            PoseCols.ROT_X: R.from_matrix(truth_matrices).as_rotvec()[:, 0],
            PoseCols.ROT_Y: R.from_matrix(truth_matrices).as_rotvec()[:, 1],
            PoseCols.ROT_Z: R.from_matrix(truth_matrices).as_rotvec()[:, 2],
        },
        index=times,
    )
    return marker_df, pose_df


def _inject_representation_change(
    marker_df: pd.DataFrame,
    pose_df: pd.DataFrame,
    layout: dict[str, np.ndarray],
    *,
    boundary: int,
    matrix: np.ndarray,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, object]]:
    observed_markers = marker_df.copy(deep=True)
    observed_pose = pose_df.copy(deep=True)
    permutation = _oracle_permutation(layout, matrix)

    marker_snapshot = marker_df.copy(deep=True)
    for destination, source in permutation.items():
        observed_markers.iloc[
            boundary:,
            observed_markers.columns.get_indexer(
                [f"{destination}_X", f"{destination}_Y", f"{destination}_Z"]
            ),
        ] = marker_snapshot.iloc[
            boundary:,
            marker_snapshot.columns.get_indexer(
                [f"{source}_X", f"{source}_Y", f"{source}_Z"]
            ),
        ].to_numpy(copy=True)

    truth_rotvecs = pose_df[
        [PoseCols.ROT_X, PoseCols.ROT_Y, PoseCols.ROT_Z]
    ].to_numpy(dtype=float)
    observed_rotvecs = truth_rotvecs.copy()
    valid_suffix = np.flatnonzero(
        np.isfinite(truth_rotvecs).all(axis=1)
        & (np.arange(len(truth_rotvecs)) >= boundary)
    )
    if valid_suffix.size:
        truth_matrices = R.from_rotvec(truth_rotvecs[valid_suffix]).as_matrix()
        observed_matrices = np.einsum("nij,jk->nik", truth_matrices, matrix)
        observed_rotvecs[valid_suffix] = R.from_matrix(observed_matrices).as_rotvec()
    observed_pose.loc[:, [PoseCols.ROT_X, PoseCols.ROT_Y, PoseCols.ROT_Z]] = (
        observed_rotvecs
    )
    manifest = {
        "kind": "representation_flip",
        "boundary": boundary,
        "boundary_time_sec": float(observed_pose.index[boundary]),
        "permutation": permutation,
    }
    return observed_markers, observed_pose, manifest


def _raw_header_and_data(
    marker_ids: list[str],
    *,
    row_count: int = 7,
) -> tuple[dict[str, list[str]], pd.DataFrame]:
    type_header = ["", ""]
    name_header = ["Frame", "Time"]
    id_header = ["", ""]
    parent_header = ["", ""]
    category_header = ["", ""]
    component_header = [TimeCols.FRAME, TimeCols.TIME]
    for marker_id in marker_ids:
        type_header.extend(["Rigid Body Marker"] * 3)
        name_header.extend([f"Box:{marker_id}"] * 3)
        id_header.extend([marker_id] * 3)
        parent_header.extend(["Box"] * 3)
        category_header.extend(["Position"] * 3)
        component_header.extend(["X", "Y", "Z"])

    header_info = {
        "type": type_header,
        "name": name_header,
        "id": id_header,
        "parent": parent_header,
        "category": category_header,
        "component": component_header,
    }
    rows = []
    for row_index in range(row_count):
        row = [float(row_index), float(row_index)]
        for marker_index, _marker_id in enumerate(marker_ids):
            base = row_index * 10000.0 + marker_index * 100.0
            row.extend([base + 1.0, base + 2.0, base + 3.0])
        rows.append(row)
    raw_df = pd.DataFrame(rows, columns=component_header)
    return header_info, raw_df


def _build_symmetric_face_stream(
    *,
    frame_count: int = 16,
) -> tuple[pd.DataFrame, dict[str, np.ndarray]]:
    layout = {
        "R1": np.array([100.0, 0.0, 0.0]),
        "L1": np.array([-100.0, 0.0, 0.0]),
        "T1": np.array([0.0, 60.0, 0.0]),
        "M1": np.array([0.0, -60.0, 0.0]),
        "F1": np.array([0.0, 0.0, 40.0]),
        "B1": np.array([0.0, 0.0, -40.0]),
    }
    face_info = {
        "R1": "RIGHT",
        "L1": "LEFT",
        "T1": "TOP",
        "M1": "BOTTOM",
        "F1": "FRONT",
        "B1": "BACK",
    }
    # Face centers alone have no first-order rotational constraints. Add
    # off-center sign-paired points, preserving independently defined half-turns.
    for prefix, face, axis, fixed, u, v in [
        ('R','RIGHT',0,100.,22.,13.), ('L','LEFT',0,-100.,22.,13.),
        ('T','TOP',1,60.,37.,17.), ('M','BOTTOM',1,-60.,37.,17.),
        ('F','FRONT',2,40.,31.,19.), ('B','BACK',2,-40.,31.,19.)]:
        other = [i for i in range(3) if i != axis]
        for number, (s,t) in enumerate([(-1,-1),(-1,1),(1,-1),(1,1)], start=2):
            point = np.zeros(3)
            point[axis] = fixed
            point[other] = [s*u,t*v]
            layout[f'{prefix}{number}'] = point
            face_info[f'{prefix}{number}'] = face
    times = np.arange(frame_count, dtype=float) * 0.01
    translations = np.column_stack(
        [
            np.arange(frame_count, dtype=float) * 0.5,
            np.arange(frame_count, dtype=float) * -0.1,
            np.arange(frame_count, dtype=float) * 0.2,
        ]
    )
    columns: dict[str, object] = {}
    for marker_id, local_position in layout.items():
        world = local_position[None, :] + translations
        columns[f"{marker_id}_FaceInfo"] = [face_info[marker_id]] * frame_count
        columns[f"{marker_id}_X"] = world[:, 0]
        columns[f"{marker_id}_Y"] = world[:, 1]
        columns[f"{marker_id}_Z"] = world[:, 2]
    return pd.DataFrame(columns, index=times), layout


def _row_marker_values(
    raw_df: pd.DataFrame,
    header_info: dict[str, list[str]],
    row_index: int,
) -> dict[str, tuple[float, float, float]]:
    triplets = marker_triplet_indices(header_info)
    return {
        marker_id: tuple(
            float(value) for value in raw_df.iloc[row_index, list(indices)].to_numpy()
        )
        for marker_id, indices in triplets.items()
    }


class TestMarkerFlipDetection(unittest.TestCase):
    def setUp(self):
        self.layout = _corner_layout()
        self.box_dims = (200.0, 120.0, 80.0)
        self.analyzer = MarkerFlipAnalyzer()

    def test_clean_no_flip_returns_no_candidates(self):
        marker_df, pose_df = _build_clean_stream(self.layout)

        self.assertEqual(self.analyzer.detect(marker_df, pose_df, self.box_dims), [])

    def test_marker_named_c1_is_not_confused_with_generated_corner_columns(self):
        marker_df = pd.DataFrame(
            {
                "C1_FaceInfo": ["RIGHT"],
                "C1_X": [1.0],
                "C1_Y": [2.0],
                "C1_Z": [3.0],
                "C2_X": [4.0],
                "C2_Y": [5.0],
                "C2_Z": [6.0],
            }
        )

        self.assertEqual(self.analyzer._marker_ids(marker_df), ["C1"])

    def test_insufficient_window_evidence_is_strict_json(self):
        candidate = self.analyzer._insufficient_window_candidate(
            event_id="flip-000001",
            boundary_time=0.01,
            trigger="fixture",
        )

        payload = json.loads(candidate.evidence_json())

        self.assertIsNone(payload["no_correction_residual_deg"])
        self.assertIsNone(payload["best_residual_deg"])

    def test_gap_only_and_freeze_reconnect_return_no_recommendation(self):
        marker_df, pose_df = _build_clean_stream(self.layout)
        gap_markers = marker_df.copy(deep=True)
        gap_pose = pose_df.copy(deep=True)
        gap_markers.iloc[12:16, :] = np.nan
        gap_pose.iloc[12:16, :] = np.nan

        gap_candidates = self.analyzer.detect(gap_markers, gap_pose, self.box_dims)

        self.assertEqual(len(gap_candidates), 1)
        self.assertIsNone(gap_candidates[0].recommendation_axis)
        self.assertIn("gap", gap_candidates[0].trigger.lower())

        frozen_markers = marker_df.copy(deep=True)
        frozen_pose = pose_df.copy(deep=True)
        frozen_markers.iloc[10:16, :] = marker_df.iloc[9].to_numpy()
        frozen_pose.iloc[10:16, :] = pose_df.iloc[9].to_numpy()

        freeze_candidates = self.analyzer.detect(
            frozen_markers,
            frozen_pose,
            self.box_dims,
        )

        self.assertEqual(len(freeze_candidates), 1)
        self.assertIsNone(freeze_candidates[0].recommendation_axis)
        self.assertIn("freeze", freeze_candidates[0].trigger.lower())

    def test_smooth_physical_half_turn_is_not_a_flip_candidate(self):
        angles = np.linspace(0.0, np.pi, 50)
        truth_matrices = R.from_rotvec(
            np.column_stack([angles, np.zeros_like(angles), np.zeros_like(angles)])
        ).as_matrix()
        marker_df, pose_df = _build_clean_stream(
            self.layout,
            truth_matrices=truth_matrices,
        )

        self.assertEqual(self.analyzer.detect(marker_df, pose_df, self.box_dims), [])

    def test_independent_x_y_z_fixtures_recommend_declared_axis(self):
        clean_markers, clean_pose = _build_clean_stream(self.layout)
        boundary = 25

        for axis, matrix in ORACLE_HALF_TURNS.items():
            with self.subTest(axis=axis):
                observed_markers, observed_pose, manifest = _inject_representation_change(
                    clean_markers,
                    clean_pose,
                    self.layout,
                    boundary=boundary,
                    matrix=matrix,
                )

                candidates = self.analyzer.detect(
                    observed_markers,
                    observed_pose,
                    self.box_dims,
                )

                self.assertEqual(len(candidates), 1)
                candidate = candidates[0]
                self.assertEqual(candidate.boundary_time_sec, manifest["boundary_time_sec"])
                self.assertEqual(candidate.recommendation_axis, axis)
                self.assertEqual(
                    dict(candidate.permutation_for_axis(axis)),
                    manifest["permutation"],
                )
                self.assertGreaterEqual(candidate.coverage_ratio, 0.8)
                self.assertGreaterEqual(candidate.correspondence_ratio, 0.8)
                self.assertGreaterEqual(candidate.discontinuity_reduction_deg, 20.0)
                self.assertGreaterEqual(candidate.confidence_margin, 0.15)

    def test_pose_optimizer_to_detector_path_finds_declared_x_flip(self):
        parsed_data, layout = _build_symmetric_face_stream(frame_count=16)
        boundary = 8
        permutation = _oracle_permutation(layout, ORACLE_HALF_TURNS["X"])
        snapshot = parsed_data.copy(deep=True)
        for destination, source in permutation.items():
            destination_columns = [
                f"{destination}_X",
                f"{destination}_Y",
                f"{destination}_Z",
            ]
            source_columns = [f"{source}_X", f"{source}_Y", f"{source}_Z"]
            parsed_data.loc[parsed_data.index[boundary]:, destination_columns] = snapshot.loc[
                snapshot.index[boundary]:,
                source_columns,
            ].to_numpy(copy=True)

        pose_data = PoseOptimizer(
            face_definitions=config_app.FACE_DEFINITIONS,
            local_box_corners=config_app.calculate_local_box_corners(self.box_dims),
        ).process(parsed_data, box_dims=self.box_dims)
        candidates = self.analyzer.detect(parsed_data, pose_data, self.box_dims)

        recommended = [candidate for candidate in candidates if candidate.recommendation_axis]
        self.assertEqual(len(recommended), 1)
        self.assertEqual(recommended[0].recommendation_axis, "X")
        self.assertEqual(recommended[0].boundary_time_sec, parsed_data.index[boundary])

    def test_gap_plus_flip_recommends_only_the_declared_flip(self):
        marker_df, pose_df = _build_clean_stream(self.layout)
        marker_df.iloc[10:13, :] = np.nan
        pose_df.iloc[10:13, :] = np.nan
        observed_markers, observed_pose, manifest = _inject_representation_change(
            marker_df,
            pose_df,
            self.layout,
            boundary=30,
            matrix=ORACLE_HALF_TURNS["Y"],
        )

        candidates = self.analyzer.detect(observed_markers, observed_pose, self.box_dims)
        recommended = [candidate for candidate in candidates if candidate.recommendation_axis]

        self.assertEqual(len(recommended), 1)
        self.assertEqual(recommended[0].recommendation_axis, "Y")
        self.assertEqual(recommended[0].boundary_time_sec, manifest["boundary_time_sec"])

    def test_unsupported_90_degree_and_arbitrary_axis_return_no_recommendation(self):
        clean_markers, clean_pose = _build_clean_stream(self.layout)
        unsupported_matrices = (
            R.from_euler("x", 90.0, degrees=True).as_matrix(),
            R.from_rotvec(np.deg2rad(120.0) * np.array([1.0, 2.0, 3.0]) / np.sqrt(14.0)).as_matrix(),
        )

        for matrix in unsupported_matrices:
            with self.subTest(matrix=matrix):
                observed_markers = clean_markers.copy(deep=True)
                observed_pose = clean_pose.copy(deep=True)
                matrices = np.repeat(np.eye(3)[None, :, :], len(observed_pose), axis=0)
                matrices[25:] = matrix
                observed_pose.loc[
                    :,
                    [PoseCols.ROT_X, PoseCols.ROT_Y, PoseCols.ROT_Z],
                ] = R.from_matrix(matrices).as_rotvec()

                candidates = self.analyzer.detect(
                    observed_markers,
                    observed_pose,
                    self.box_dims,
                )

                self.assertEqual(len(candidates), 1)
                self.assertIsNone(candidates[0].recommendation_axis)

    def test_low_coverage_returns_no_recommendation(self):
        marker_df, pose_df = _build_clean_stream(self.layout)
        observed_markers, observed_pose, _manifest = _inject_representation_change(
            marker_df,
            pose_df,
            self.layout,
            boundary=25,
            matrix=ORACLE_HALF_TURNS["Z"],
        )
        for marker_id in sorted(self.layout)[2:]:
            observed_markers.loc[
                observed_markers.index[25]:,
                [f"{marker_id}_X", f"{marker_id}_Y", f"{marker_id}_Z"],
            ] = np.nan

        candidates = self.analyzer.detect(observed_markers, observed_pose, self.box_dims)

        self.assertEqual(len(candidates), 1)
        self.assertIsNone(candidates[0].recommendation_axis)
        self.assertLess(candidates[0].coverage_ratio, 0.8)

    def test_equal_x_y_evidence_is_reported_as_ambiguous(self):
        cube_layout = _corner_layout((40.0, 40.0, 40.0))
        marker_df, pose_df = _build_clean_stream(cube_layout)
        diagonal_half_turn = np.array(
            [
                [0.0, 1.0, 0.0],
                [1.0, 0.0, 0.0],
                [0.0, 0.0, -1.0],
            ]
        )
        observed_markers, observed_pose, _manifest = _inject_representation_change(
            marker_df,
            pose_df,
            cube_layout,
            boundary=25,
            matrix=diagonal_half_turn,
        )
        analyzer = MarkerFlipAnalyzer(maximum_corrected_residual_deg=100.0)

        candidates = analyzer.detect(
            observed_markers,
            observed_pose,
            (100.0, 100.0, 100.0),
        )

        self.assertEqual(len(candidates), 1)
        self.assertIsNone(candidates[0].recommendation_axis)
        self.assertAlmostEqual(candidates[0].confidence_margin, 0.0, places=8)
        self.assertIn("margin", candidates[0].reason.lower())


class TestMarkerPermutationApplication(unittest.TestCase):
    def setUp(self):
        self.layout = _corner_layout()
        self.marker_ids = sorted(self.layout)
        self.header_info, self.raw_df = _raw_header_and_data(self.marker_ids)
        self.permutations = {
            axis: tuple(sorted(_oracle_permutation(self.layout, matrix).items()))
            for axis, matrix in ORACLE_HALF_TURNS.items()
        }

    def _decision(
        self,
        event_id: str,
        boundary: float,
        axis: str,
        *,
        approved: bool = True,
    ) -> MarkerCorrectionDecision:
        return MarkerCorrectionDecision(
            event_id=event_id,
            boundary_time_sec=boundary,
            approved=approved,
            axis=axis if approved else None,
            recommendation_axis=axis,
            permutation=self.permutations[axis] if approved else (),
        )

    def test_unapproved_event_preserves_raw_values(self):
        decision = self._decision("off", 2.0, "X", approved=False)

        corrected = apply_approved_marker_permutations(
            self.raw_df,
            self.header_info,
            [decision],
        )

        pd.testing.assert_frame_equal(corrected, self.raw_df)

    def test_two_same_axis_events_restore_mapping_after_second_event(self):
        decisions = [
            self._decision("x-1", 2.0, "X"),
            self._decision("x-2", 4.0, "X"),
        ]

        corrected = apply_approved_marker_permutations(
            self.raw_df,
            self.header_info,
            decisions,
        )
        original_mid = _row_marker_values(self.raw_df, self.header_info, 2)
        corrected_mid = _row_marker_values(corrected, self.header_info, 2)
        for destination, source in self.permutations["X"]:
            self.assertEqual(corrected_mid[destination], original_mid[source])

        self.assertEqual(
            _row_marker_values(corrected, self.header_info, 4),
            _row_marker_values(self.raw_df, self.header_info, 4),
        )

    def test_ordered_different_axis_events_follow_cumulative_suffix_semantics(self):
        decisions = [
            self._decision("x", 2.0, "X"),
            self._decision("y", 4.0, "Y"),
        ]

        corrected = apply_approved_marker_permutations(
            self.raw_df,
            self.header_info,
            decisions,
        )
        original_values = _row_marker_values(self.raw_df, self.header_info, 5)
        corrected_values = _row_marker_values(corrected, self.header_info, 5)
        x_mapping = dict(self.permutations["X"])
        y_mapping = dict(self.permutations["Y"])
        for destination in self.marker_ids:
            expected_source = x_mapping[y_mapping[destination]]
            self.assertEqual(corrected_values[destination], original_values[expected_source])

        restored = undo_approved_marker_permutations(
            corrected,
            self.header_info,
            decisions,
        )
        pd.testing.assert_frame_equal(restored, self.raw_df)

    def test_coordinate_triplets_are_reassigned_without_numeric_rotation(self):
        decision = self._decision("z", 2.0, "Z")

        corrected = apply_approved_marker_permutations(
            self.raw_df,
            self.header_info,
            [decision],
        )

        for row_index in range(len(self.raw_df)):
            before = sorted(_row_marker_values(self.raw_df, self.header_info, row_index).values())
            after = sorted(_row_marker_values(corrected, self.header_info, row_index).values())
            self.assertEqual(after, before)


if __name__ == "__main__":
    unittest.main()
