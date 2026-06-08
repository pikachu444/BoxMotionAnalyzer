import os
import sys
import unittest

import numpy as np
import pandas as pd
from scipy.spatial.transform import Rotation as R

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.analysis.pipeline.data_loader import DataLoader
from src.analysis.pipeline.parser import Parser
from src.analysis.pipeline.pipeline_controller import PipelineController
from src.config import config_app
from src.config.data_columns import (
    CornerCoordCols,
    DropPostureCols,
    DropPostureSummaryCols,
    FACE_PREFIX_TO_INFO,
    PoseCols,
)


REAL_RAW_CSV = "TestSets/Input/VDTest_S5_001.csv"
TESTBOX_85_ESTIMATED_DIMS = (2082.9, 1046.6, 254.4)


class TestRealDropPosturePhysics(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        loader = DataLoader()
        header_info, raw_data = loader.load_csv(REAL_RAW_CSV)
        cls.parsed = Parser(face_prefix_map=FACE_PREFIX_TO_INFO).process(header_info, raw_data)

    def _process_slice(self, start, end, box_dimensions=None):
        original_box_dims = np.array(config_app.BOX_DIMS, dtype=float).copy()
        original_local_corners = np.array(config_app.LOCAL_BOX_CORNERS, dtype=float).copy()
        try:
            controller = PipelineController()
            config = {
                "slice_filter_by": "time",
                "slice_start_val": start,
                "slice_end_val": end,
                "analysis_options": {
                    "enable_marker_smoothing": False,
                    "drop_posture_contact_threshold_mm": 1.0,
                },
            }
            if box_dimensions is not None:
                config["box_dimensions"] = box_dimensions
            return controller.process_parsed_data(config, self.parsed)
        finally:
            config_app.BOX_DIMS = original_box_dims
            config_app.LOCAL_BOX_CORNERS = original_local_corners

    def _corner_positions(self, df):
        return np.stack(
            [
                df[
                    [
                        f"C{corner}{CornerCoordCols.X_SUFFIX}",
                        f"C{corner}{CornerCoordCols.Y_SUFFIX}",
                        f"C{corner}{CornerCoordCols.Z_SUFFIX}",
                    ]
                ].to_numpy(dtype=float)
                for corner in range(1, 9)
            ],
            axis=1,
        )

    def _face_delta_h(self, df, reference_face):
        corners = self._corner_positions(df)
        face_indices = config_app.FACE_DEFINITIONS[reference_face]["corners"]
        face_heights = corners[:, face_indices, config_app.WORLD_VERTICAL_AXIS_INDEX]
        return np.nanmax(face_heights, axis=1) - np.nanmin(face_heights, axis=1)

    def _beta_at_row(self, row, reference_face):
        rotation = R.from_rotvec(row[[PoseCols.ROT_X, PoseCols.ROT_Y, PoseCols.ROT_Z]].to_numpy(dtype=float))
        face = config_app.FACE_DEFINITIONS[reference_face]
        normal = np.zeros(3, dtype=float)
        normal[int(face["axis_idx"])] = float(face["direction"])
        normal_world = rotation.apply(normal)
        normal_world = normal_world / np.linalg.norm(normal_world)
        downward = np.zeros(3, dtype=float)
        downward[config_app.WORLD_VERTICAL_AXIS_INDEX] = -1.0
        return float(np.degrees(np.arccos(np.clip(np.dot(normal_world, downward), -1.0, 1.0))))

    def test_estimated_testbox_85_dimensions_match_stable_marker_envelope(self):
        records = []
        marker_ids = sorted(
            {
                column[: -len("_FaceInfo")]
                for column in self.parsed.columns
                if column.endswith("_FaceInfo")
            }
        )
        for timestamp in np.arange(0.0, 1.51, 1.0 / 24.0):
            nearest = self.parsed.index[np.abs(self.parsed.index.to_numpy(dtype=float) - timestamp).argmin()]
            row = self.parsed.loc[nearest]
            points = []
            for marker_id in marker_ids:
                columns = [f"{marker_id}_X", f"{marker_id}_Y", f"{marker_id}_Z"]
                if not all(column in row.index for column in columns):
                    continue
                values = row[columns].to_numpy(dtype=float)
                if np.isfinite(values).all():
                    points.append(values)
            if len(points) >= 20:
                records.append(np.ptp(np.asarray(points), axis=0))

        estimated_dims = np.nanmedian(np.asarray(records), axis=0)
        np.testing.assert_allclose(estimated_dims, TESTBOX_85_ESTIMATED_DIMS, atol=0.2)

    def test_no_contact_real_slice_keeps_frame_metrics_without_t1_fallback(self):
        result = self._process_slice(0.48, 0.56)
        first = result.iloc[0]

        self.assertEqual(first[DropPostureSummaryCols.CONTACT_STATE], "NoContact")
        self.assertFalse(first[DropPostureSummaryCols.T1_DETECTED])
        self.assertFalse(first[DropPostureSummaryCols.IMPACT_DETECTED])
        self.assertFalse(first[DropPostureSummaryCols.SUSTAINED_CONTACT_DETECTED])
        self.assertTrue(pd.isna(first[DropPostureSummaryCols.T1_MINUS_TIME_SEC]))
        self.assertTrue(pd.isna(first[DropPostureSummaryCols.BETA_AT_T1_MINUS_DEG]))
        self.assertEqual(first[DropPostureSummaryCols.IMPACT_SEQUENCE], "")

        reference_face = first[DropPostureSummaryCols.REFERENCE_FACE]
        expected_delta_h = self._face_delta_h(result, reference_face)
        np.testing.assert_allclose(result[DropPostureCols.DELTA_H_MM].to_numpy(), expected_delta_h, atol=1e-6)
        self.assertLess(float(first[DropPostureSummaryCols.MAX_DELTA_H_MM]), 20.0)

    def test_real_contact_slice_detects_event_and_matches_independent_physics(self):
        result = self._process_slice(2.45, 3.05, TESTBOX_85_ESTIMATED_DIMS)
        first = result.iloc[0]

        self.assertEqual(first[DropPostureSummaryCols.CONTACT_STATE], "ImpactEvent")
        self.assertTrue(first[DropPostureSummaryCols.T1_DETECTED])
        self.assertTrue(first[DropPostureSummaryCols.IMPACT_DETECTED])
        self.assertGreaterEqual(first[DropPostureSummaryCols.CONTACT_CONFIDENCE], 0.5)
        self.assertAlmostEqual(first[DropPostureSummaryCols.T1_MINUS_TIME_SEC], 2.716667, places=5)
        self.assertAlmostEqual(first[DropPostureSummaryCols.FIRST_IMPACT_TIME_SEC], 2.720833, places=5)
        self.assertEqual(first[DropPostureSummaryCols.FIRST_IMPACT_CONTACT], "C2")

        reference_face = first[DropPostureSummaryCols.REFERENCE_FACE]
        expected_delta_h = self._face_delta_h(result, reference_face)
        np.testing.assert_allclose(result[DropPostureCols.DELTA_H_MM].to_numpy(), expected_delta_h, atol=1e-6)

        t1_time = first[DropPostureSummaryCols.T1_MINUS_TIME_SEC]
        t1_row = result.loc[t1_time]
        self.assertAlmostEqual(
            first[DropPostureSummaryCols.BETA_AT_T1_MINUS_DEG],
            self._beta_at_row(t1_row, reference_face),
            places=6,
        )
        self.assertAlmostEqual(
            first[DropPostureSummaryCols.DELTA_H_AT_T1_MINUS_MM],
            float(expected_delta_h[result.index.get_loc(t1_time)]),
            places=6,
        )

    def test_real_low_plateau_slice_is_contact_evidence_without_new_t1(self):
        result = self._process_slice(3.00, 3.25, TESTBOX_85_ESTIMATED_DIMS)
        first = result.iloc[0]

        self.assertEqual(first[DropPostureSummaryCols.CONTACT_STATE], "SustainedContact")
        self.assertFalse(first[DropPostureSummaryCols.T1_DETECTED])
        self.assertFalse(first[DropPostureSummaryCols.IMPACT_DETECTED])
        self.assertTrue(first[DropPostureSummaryCols.SUSTAINED_CONTACT_DETECTED])
        self.assertTrue(pd.isna(first[DropPostureSummaryCols.T1_MINUS_TIME_SEC]))
        self.assertEqual(first[DropPostureSummaryCols.IMPACT_SEQUENCE], "")

        reference_face = first[DropPostureSummaryCols.REFERENCE_FACE]
        expected_delta_h = self._face_delta_h(result, reference_face)
        np.testing.assert_allclose(result[DropPostureCols.DELTA_H_MM].to_numpy(), expected_delta_h, atol=1e-6)
        self.assertLess(float(first[DropPostureSummaryCols.MAX_DELTA_H_MM]), 10.0)


if __name__ == "__main__":
    unittest.main()
