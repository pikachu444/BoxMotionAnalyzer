import sys
import os
import tempfile
import unittest
import numpy as np
import pandas as pd
from scipy.spatial.transform import Rotation as R

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.analysis.pipeline.data_loader import DataLoader
from src.analysis.pipeline.pipeline_controller import PipelineController
from src.config import config_app
from src.config.data_columns import HeaderL1, HeaderL2, HeaderL3, DropPostureSummaryCols
from src.utils.header_converter import convert_to_multi_header
from src.visualization.data_handler import DataHandler
from src.config import config_visualization as config_vis

TESTBOX_85_ESTIMATED_DIMS = (2082.9, 1046.6, 254.4)

class TestRealDataFlow(unittest.TestCase):
    def setUp(self):
        self.raw_csv_path = "TestSets/Input/VDTest_S5_001.csv"
        self.temp_dir = tempfile.TemporaryDirectory()
        self.result_csv_path = os.path.join(self.temp_dir.name, "test_real_data_result.proc")

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_full_flow_with_real_file(self):
        print(f"\n[Test] Running full flow with real file: {self.raw_csv_path}")

        # 1. Load Data
        loader = DataLoader()
        try:
            header_info, raw_data = loader.load_csv(self.raw_csv_path)
        except Exception as e:
            self.fail(f"Failed to load CSV: {e}")

        print(f"  > Loaded. Raw Shape: {raw_data.shape}")

        # 2. Run Analysis Pipeline
        # Only process a small slice to save time, but enough to generate headers
        controller = PipelineController()
        config = {
            'slice_filter_by': 'time',
            'slice_start_val': 0.0,
            'slice_end_val': 1.0 # 1 second slice
        }

        # Capture results using signal spy equivalent
        results = []
        controller.analysis_finished.connect(lambda df: results.append(df))
        controller.analysis_failed.connect(lambda msg: self.fail(f"Analysis failed: {msg}"))

        # We need event loop for signals? Or controller runs synchronously?
        # Based on previous analysis, it runs synchronously.
        controller.run_analysis(config, header_info, raw_data)

        if not results:
            self.fail("No analysis results produced.")

        result_df = results[0]
        print(f"  > Analysis complete. Result Shape: {result_df.shape}")

        # 3. Export to CSV
        try:
            export_df = convert_to_multi_header(result_df)
            export_df.to_csv(self.result_csv_path, index=False) # index=False because convert_to_multi_header might handle index
            print(f"  > Exported to {self.result_csv_path}")
        except Exception as e:
            self.fail(f"Export failed: {e}")

        # 4. Load Back with Visualization DataHandler
        handler = DataHandler()
        success = handler.load_analysis_result(self.result_csv_path)

        if not success:
            # If failed, print error and file content inspection
            print("  [ERROR] DataHandler failed to load result.")
            self.fail("DataHandler.load_analysis_result returned False.")
        else:
            print("  > Visualization loaded successfully.")
            # Verify frame normalization
            frames = handler.visualization_dataframe[config_vis.DF_FRAME]
            self.assertEqual(frames.min(), 0, "Real data frames did not start at 0")
            print(f"  > Frame normalization check passed (Min: {frames.min()}, Max: {frames.max()})")

    def _summary_column(self, l3):
        return (HeaderL1.ANALYSIS, HeaderL2.DROP_POSTURE_SUMMARY, l3)

    def _position_column(self, l2, l3):
        return (HeaderL1.POS, l2, l3)

    def _first_reloaded_value(self, df, l3):
        values = df[self._summary_column(l3)]
        if isinstance(values, pd.DataFrame):
            values = values.iloc[:, 0]
        values = values.dropna()
        self.assertFalse(values.empty, f"Missing reloaded summary value for {l3}")
        return values.iloc[0]

    def _nearest_row(self, df, timestamp):
        time_column = (HeaderL1.INFO, HeaderL2.TIME, HeaderL3.TIME)
        if time_column in df.columns:
            index_values = df[time_column].to_numpy(dtype=float)
        else:
            index_values = df.index.to_numpy(dtype=float)
        nearest_pos = np.abs(index_values - float(timestamp)).argmin()
        return df.iloc[int(nearest_pos)]

    def _corner_positions_from_row(self, row):
        return np.asarray(
            [
                [
                    float(row[self._position_column(f"C{corner}", HeaderL3.P_TX)]),
                    float(row[self._position_column(f"C{corner}", HeaderL3.P_TY)]),
                    float(row[self._position_column(f"C{corner}", HeaderL3.P_TZ)]),
                ]
                for corner in range(1, 9)
            ],
            dtype=float,
        )

    def _beta_from_row(self, row, reference_face):
        rotation = R.from_rotvec(
            [
                float(row[self._position_column(HeaderL2.COM, HeaderL3.P_RX)]),
                float(row[self._position_column(HeaderL2.COM, HeaderL3.P_RY)]),
                float(row[self._position_column(HeaderL2.COM, HeaderL3.P_RZ)]),
            ]
        )
        face = config_app.FACE_DEFINITIONS[reference_face]
        normal = np.zeros(3, dtype=float)
        normal[int(face["axis_idx"])] = float(face["direction"])
        normal_world = rotation.apply(normal)
        normal_world = normal_world / np.linalg.norm(normal_world)
        downward = np.zeros(3, dtype=float)
        downward[config_app.WORLD_VERTICAL_AXIS_INDEX] = -1.0
        return float(np.degrees(np.arccos(np.clip(np.dot(normal_world, downward), -1.0, 1.0))))

    def test_real_testbox_85_contact_slice_flow_preserves_physics_summary(self):
        loader = DataLoader()
        header_info, raw_data = loader.load_csv(self.raw_csv_path)
        self.assertTrue(
            any("TestBox_85" in str(name) for name in header_info.get("name", [])),
            "Expected the real flow fixture to contain TestBox_85 marker headers.",
        )

        original_box_dims = np.array(config_app.BOX_DIMS, dtype=float).copy()
        original_local_corners = np.array(config_app.LOCAL_BOX_CORNERS, dtype=float).copy()
        try:
            controller = PipelineController()
            config = {
                "slice_filter_by": "time",
                "slice_start_val": 2.45,
                "slice_end_val": 3.05,
                "box_dimensions": TESTBOX_85_ESTIMATED_DIMS,
                "analysis_options": {
                    "enable_marker_smoothing": False,
                    "drop_posture_contact_threshold_mm": 1.0,
                },
            }
            results = []
            controller.analysis_finished.connect(lambda df: results.append(df))
            controller.analysis_failed.connect(lambda msg: self.fail(f"Analysis failed: {msg}"))
            controller.run_analysis(config, header_info, raw_data)
        finally:
            config_app.BOX_DIMS = original_box_dims
            config_app.LOCAL_BOX_CORNERS = original_local_corners

        if not results:
            self.fail("No analysis results produced for the TestBox_85 contact slice.")

        result_df = results[0]
        self.assertFalse(result_df.empty)
        first = result_df.iloc[0]
        self.assertEqual(first[DropPostureSummaryCols.CONTACT_STATE], "ImpactEvent")

        with tempfile.TemporaryDirectory() as temp_dir:
            result_path = os.path.join(temp_dir, "testbox_85_contact_slice.proc")
            convert_to_multi_header(result_df).to_csv(result_path, index=False)

            handler = DataHandler()
            self.assertTrue(handler.load_analysis_result(result_path))

            reloaded = loader.load_result_csv(result_path)
            self.assertFalse(reloaded.empty)

        t1_time = float(self._first_reloaded_value(reloaded, HeaderL3.DROP_T1_MINUS_TIME_SEC))
        first_impact_time = float(self._first_reloaded_value(reloaded, HeaderL3.DROP_FIRST_IMPACT_TIME_SEC))
        reference_face = str(self._first_reloaded_value(reloaded, HeaderL3.DROP_REFERENCE_FACE))
        first_impact_contact = str(self._first_reloaded_value(reloaded, HeaderL3.DROP_FIRST_IMPACT_CONTACT))
        impact_sequence = str(self._first_reloaded_value(reloaded, HeaderL3.DROP_IMPACT_SEQUENCE))

        self.assertAlmostEqual(t1_time, 2.716667, places=5)
        self.assertAlmostEqual(first_impact_time, 2.720833, places=5)
        self.assertEqual(first_impact_contact, "C2")
        self.assertIn("C2", impact_sequence)

        t1_row = self._nearest_row(reloaded, t1_time)
        corner_positions = self._corner_positions_from_row(t1_row)
        vertical_heights = corner_positions[:, config_app.WORLD_VERTICAL_AXIS_INDEX]
        expected_cmin = int(np.nanargmin(vertical_heights)) + 1
        face_indices = config_app.FACE_DEFINITIONS[reference_face]["corners"]
        face_heights = vertical_heights[face_indices]
        expected_delta_h = float(np.nanmax(face_heights) - np.nanmin(face_heights))
        expected_beta = self._beta_from_row(t1_row, reference_face)

        self.assertEqual(
            int(float(self._first_reloaded_value(reloaded, HeaderL3.DROP_CMIN_AT_T1_MINUS_INDEX))),
            expected_cmin,
        )
        self.assertAlmostEqual(
            float(self._first_reloaded_value(reloaded, HeaderL3.DROP_DELTA_H_AT_T1_MINUS_MM)),
            expected_delta_h,
            places=6,
        )
        self.assertAlmostEqual(
            float(self._first_reloaded_value(reloaded, HeaderL3.DROP_BETA_AT_T1_MINUS_DEG)),
            expected_beta,
            places=6,
        )

if __name__ == '__main__':
    unittest.main()
