import unittest
from unittest.mock import Mock

import numpy as np
import pandas as pd
from scipy.spatial.transform import Rotation as R

from src.analysis.pipeline.drop_posture_post_processor import DropPosturePostProcessor
from src.analysis.pipeline.pipeline_controller import PipelineController
from src.config import config_app
from src.config.data_columns import (
    CornerCoordCols,
    DropPostureCols,
    DropPostureSummaryCols,
    PoseCols,
)


BOX_DIMS = np.array([1000.0, 500.0, 200.0])
LOCAL_CORNERS = config_app.calculate_local_box_corners(BOX_DIMS)


def _make_result_frame(rotation: R, min_heights: list[float]) -> pd.DataFrame:
    rotated_local = rotation.apply(LOCAL_CORNERS)
    base_min_height = rotated_local[:, config_app.WORLD_VERTICAL_AXIS_INDEX].min()
    rows = []

    for min_height in min_heights:
        center = np.array([0.0, min_height - base_min_height, 0.0])
        corners = rotated_local + center
        row = {
            PoseCols.POS_X: center[0],
            PoseCols.POS_Y: center[1],
            PoseCols.POS_Z: center[2],
            PoseCols.ROT_X: rotation.as_rotvec()[0],
            PoseCols.ROT_Y: rotation.as_rotvec()[1],
            PoseCols.ROT_Z: rotation.as_rotvec()[2],
        }
        for corner_idx, corner in enumerate(corners, start=1):
            row[f"C{corner_idx}{CornerCoordCols.X_SUFFIX}"] = corner[0]
            row[f"C{corner_idx}{CornerCoordCols.Y_SUFFIX}"] = corner[1]
            row[f"C{corner_idx}{CornerCoordCols.Z_SUFFIX}"] = corner[2]
        rows.append(row)

    return pd.DataFrame(rows, index=[i * 0.1 for i in range(len(rows))])


def _make_contact_sequence_frame(contact_sets: list[tuple[int, ...]]) -> pd.DataFrame:
    rows = []
    for contact_set in contact_sets:
        row = {
            PoseCols.POS_X: 0.0,
            PoseCols.POS_Y: 0.0,
            PoseCols.POS_Z: 0.0,
            PoseCols.ROT_X: 0.0,
            PoseCols.ROT_Y: 0.0,
            PoseCols.ROT_Z: 0.0,
        }
        for corner_idx, local_corner in enumerate(LOCAL_CORNERS, start=1):
            row[f"C{corner_idx}{CornerCoordCols.X_SUFFIX}"] = local_corner[0]
            row[f"C{corner_idx}{CornerCoordCols.Y_SUFFIX}"] = 0.0 if corner_idx in contact_set else 10.0 + corner_idx
            row[f"C{corner_idx}{CornerCoordCols.Z_SUFFIX}"] = local_corner[2]
        rows.append(row)
    return pd.DataFrame(rows, index=[i * 0.1 for i in range(len(rows))])


def _processor() -> DropPosturePostProcessor:
    return DropPosturePostProcessor(
        face_definitions=config_app.FACE_DEFINITIONS,
        local_box_corners=LOCAL_CORNERS,
        vertical_axis_idx=config_app.WORLD_VERTICAL_AXIS_INDEX,
        floor_level=config_app.FLOOR_LEVEL,
    )


class TestDropPosturePostProcessor(unittest.TestCase):
    def test_flat_drop_has_zero_angles_and_expected_height_spread(self):
        df = _make_result_frame(R.identity(), [10.0, 2.0, 0.5, -1.0])
        result = _processor().process(df, contact_threshold_mm=1.0)

        self.assertAlmostEqual(result[DropPostureCols.BETA_DEG].iloc[1], 0.0, places=6)
        self.assertAlmostEqual(result[DropPostureCols.THETA_LONG_DEG].iloc[1], 0.0, places=6)
        self.assertAlmostEqual(result[DropPostureCols.THETA_SHORT_DEG].iloc[1], 0.0, places=6)
        self.assertEqual(result[DropPostureSummaryCols.REFERENCE_FACE].iloc[0], "BOTTOM")
        self.assertEqual(result[DropPostureSummaryCols.T1_MINUS_TIME_SEC].iloc[0], 0.1)
        self.assertTrue(result[DropPostureSummaryCols.T1_DETECTED].iloc[0])
        self.assertAlmostEqual(result[DropPostureCols.DELTA_H_MM].iloc[1], BOX_DIMS[1], places=6)

    def test_long_axis_tilt_matches_physical_rotation_and_corner_height_range(self):
        rotation = R.from_euler("z", 10.0, degrees=True)
        df = _make_result_frame(rotation, [10.0, 2.0, 0.5, -1.0])
        result = _processor().process(df, contact_threshold_mm=1.0)

        expected_spread = np.ptp(rotation.apply(LOCAL_CORNERS)[:, config_app.WORLD_VERTICAL_AXIS_INDEX])
        self.assertAlmostEqual(result[DropPostureCols.BETA_DEG].iloc[1], 10.0, places=6)
        self.assertAlmostEqual(result[DropPostureCols.THETA_LONG_DEG].iloc[1], 10.0, places=6)
        self.assertAlmostEqual(result[DropPostureCols.THETA_SHORT_DEG].iloc[1], 0.0, places=6)
        self.assertAlmostEqual(result[DropPostureCols.DELTA_H_MM].iloc[1], expected_spread, places=6)
        self.assertAlmostEqual(result[DropPostureSummaryCols.BETA_AT_T1_MINUS_DEG].iloc[0], 10.0, places=6)
        self.assertAlmostEqual(result[DropPostureSummaryCols.MAX_BETA_DEG].iloc[0], 10.0, places=6)

    def test_short_axis_tilt_keeps_signed_direction(self):
        rotation = R.from_euler("x", 7.0, degrees=True)
        df = _make_result_frame(rotation, [10.0, 2.0, 0.5, -1.0])
        result = _processor().process(df, contact_threshold_mm=1.0)

        self.assertAlmostEqual(result[DropPostureCols.BETA_DEG].iloc[1], 7.0, places=6)
        self.assertAlmostEqual(result[DropPostureCols.THETA_LONG_DEG].iloc[1], 0.0, places=6)
        self.assertAlmostEqual(result[DropPostureCols.THETA_SHORT_DEG].iloc[1], -7.0, places=6)
        self.assertAlmostEqual(result[DropPostureSummaryCols.THETA_SHORT_AT_T1_MINUS_DEG].iloc[0], -7.0, places=6)

    def test_no_threshold_crossing_falls_back_to_lowest_height_frame(self):
        df = _make_result_frame(R.identity(), [10.0, 8.0, 6.0, 4.0])
        result = _processor().process(df, contact_threshold_mm=1.0)

        self.assertAlmostEqual(result[DropPostureSummaryCols.T1_MINUS_TIME_SEC].iloc[0], 0.3, places=12)
        self.assertFalse(result[DropPostureSummaryCols.T1_DETECTED].iloc[0])

    def test_pipeline_runs_drop_posture_after_result_resampling(self):
        baseline = _make_result_frame(R.from_euler("z", 10.0, degrees=True), [10.0, 2.0, -1.0])
        controller = PipelineController()
        controller.drop_posture_post_processor.configure_geometry(LOCAL_CORNERS)
        controller.drop_posture_post_processor.local_box_corners = LOCAL_CORNERS
        controller._execute_analysis_single_pass = Mock(return_value=baseline)

        result = controller._execute_analysis_from_parsed(
            {
                "enable_result_resampling": True,
                "result_resampling_factor": 2,
                "limit_result_resampling_to_range": False,
                "analysis_options": {"drop_posture_contact_threshold_mm": 1.0},
            },
            baseline,
        )

        self.assertGreater(len(result), len(baseline))
        self.assertIn(DropPostureCols.CMIN_INDEX, result.columns)
        cmin_values = pd.to_numeric(result[DropPostureCols.CMIN_INDEX], errors="coerce")
        self.assertTrue(((cmin_values % 1) == 0).all())
        self.assertAlmostEqual(result[DropPostureSummaryCols.BETA_AT_T1_MINUS_DEG].iloc[0], 10.0, places=6)

    def test_impact_sequence_records_single_and_simultaneous_contact_events(self):
        df = _make_contact_sequence_frame(
            [
                tuple(),
                (1, 2),
                (1, 2),
                tuple(),
                (5,),
                (5,),
                tuple(),
            ]
        )
        result = _processor().process(df, contact_threshold_mm=1.0)

        self.assertEqual(result[DropPostureSummaryCols.IMPACT_SEQUENCE].iloc[0], "{C1,C2} -> C5")
        self.assertEqual(result[DropPostureSummaryCols.IMPACT_EVENT_COUNT].iloc[0], 2)
        self.assertAlmostEqual(result[DropPostureSummaryCols.FIRST_IMPACT_TIME_SEC].iloc[0], 0.1, places=12)
        self.assertEqual(result[DropPostureSummaryCols.FIRST_IMPACT_CONTACT].iloc[0], "{C1,C2}")

    def test_impact_sequence_filters_single_frame_contact_noise(self):
        df = _make_contact_sequence_frame(
            [
                tuple(),
                (1,),
                tuple(),
                (2,),
                (2,),
                tuple(),
            ]
        )
        result = _processor().process(df, contact_threshold_mm=1.0)

        self.assertEqual(result[DropPostureSummaryCols.IMPACT_SEQUENCE].iloc[0], "C2")
        self.assertEqual(result[DropPostureSummaryCols.IMPACT_EVENT_COUNT].iloc[0], 1)
        self.assertAlmostEqual(result[DropPostureSummaryCols.FIRST_IMPACT_TIME_SEC].iloc[0], 0.3, places=12)

    def test_impact_sequence_uses_empty_summary_when_no_contact_event_is_valid(self):
        df = _make_contact_sequence_frame([tuple(), (1,), tuple(), tuple()])
        result = _processor().process(df, contact_threshold_mm=1.0)

        self.assertEqual(result[DropPostureSummaryCols.IMPACT_SEQUENCE].iloc[0], "")
        self.assertEqual(result[DropPostureSummaryCols.IMPACT_EVENT_COUNT].iloc[0], 0)
        self.assertTrue(pd.isna(result[DropPostureSummaryCols.FIRST_IMPACT_TIME_SEC].iloc[0]))
        self.assertEqual(result[DropPostureSummaryCols.FIRST_IMPACT_CONTACT].iloc[0], "")


if __name__ == "__main__":
    unittest.main()
