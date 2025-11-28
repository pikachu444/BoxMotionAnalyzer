import unittest
import os
import pandas as pd
import numpy as np

# Import all necessary components
from src.config import config_visualization as config
from src.visualization.data_handler import DataHandler
from src.visualization.plot_widget import PlotWidget
from PySide6.QtWidgets import QApplication

class TestIntegration(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        """Generate test data once for all tests."""
        # Ensure the test data directory exists
        data_dir = os.path.dirname(config.TEST_CSV_PATH)
        if not os.path.exists(data_dir):
            os.makedirs(data_dir)

        # Always regenerate to ensure it matches current code
        try:
            from src.visualization import make_testdata
            make_testdata.main()
        except Exception as e:
            cls.fail(f"Failed to generate test data: {e}")

        # PySide6 needs a QApplication instance
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        """Set up fresh instances for each test."""
        self.data_handler = DataHandler()
        # Use the new method name
        success = self.data_handler.load_analysis_result(config.TEST_CSV_PATH)
        self.assertTrue(success, "Setup failed: Could not load test CSV.")

        self.plot_widget = PlotWidget()

    def test_data_flow_for_vista_rendering(self):
        """
        Tests the logic of VistaWidget._get_points_for_ids without instantiating the widget.
        This avoids OpenGL errors in a headless environment.
        """
        frame_number = 10
        frame_df = self.data_handler.get_frame_data(frame_number)

        self.assertIsNotNone(frame_df, "get_frame_data returned None.")
        self.assertFalse(frame_df.empty, "get_frame_data returned an empty DataFrame.")

        # --- Replicate the logic of _get_points_for_ids directly ---
        # Note: In the new system, corner labels are C1-C8, not C0-C7 or similar legacy names.
        ids = config.BOX_CORNERS_LABELS

        # Filter rows for these IDs
        points_df = frame_df[frame_df[config.DF_OBJECT_ID].isin(ids)].copy()

        # Verify we found the objects
        found_ids = points_df[config.DF_OBJECT_ID].unique()
        self.assertEqual(len(found_ids), len(ids), f"Could not find all box corners in frame data. Found: {found_ids}")

        # Sort to ensure order matches config.BOX_CORNERS_LABELS
        sorter = pd.CategoricalDtype(categories=ids, ordered=True)
        points_df[config.DF_OBJECT_ID] = points_df[config.DF_OBJECT_ID].astype(sorter)
        points_df = points_df.sort_values(config.DF_OBJECT_ID)

        # Extract X, Y, Z
        points = points_df[[config.DF_POS_X, config.DF_POS_Y, config.DF_POS_Z]].values
        # --- End of replicated logic ---

        self.assertIsNotNone(points, "Point extraction logic should return points, not None.")
        self.assertEqual(points.shape, (len(ids), 3), "Points array has incorrect shape.")
        self.assertFalse(pd.isna(points).any(), "Points array contains NaN values.")

        print("\n✓ Data flows correctly for VistaWidget's point extraction logic.")

    def test_data_flow_to_plot_widget(self):
        """
        Tests if the data flow for plotting (pos and vel) is correct.
        This simulates the logic from MainWindow.update_plot_with_multiple_objects.
        """
        # Pick valid IDs from the new test data
        object_ids = ['C1', 'MK_TOP_1']

        # Test for position data
        data_to_plot_pos = config.DF_POS_X
        plot_args_pos = []
        for obj_id in object_ids:
            df = self.data_handler.get_object_timeseries(obj_id)
            self.assertIsNotNone(df, f"Timeseries not found for {obj_id}")
            self.assertIn(data_to_plot_pos, df.columns, f"'{data_to_plot_pos}' not in timeseries df.")

            plot_args_pos.append({
                "x": df[config.DF_FRAME],
                "y": df[data_to_plot_pos],
                "label": obj_id
            })

        self.plot_widget.plot_multiple_data(plot_args_pos, data_to_plot_pos)
        print(f"✓ Position data ('{data_to_plot_pos}') flows correctly for plotting.")

        # Test for velocity data
        data_to_plot_vel = config.DF_VEL_Y
        plot_args_vel = []
        for obj_id in object_ids:
            df = self.data_handler.get_object_timeseries(obj_id)
            self.assertIn(data_to_plot_vel, df.columns, f"'{data_to_plot_vel}' not in timeseries df.")

            # Check if velocity data is actually numeric (not all NaNs)
            # The test data generator should produce valid velocity.
            if df[data_to_plot_vel].isnull().all():
                print(f"[WARN] Velocity data for {obj_id} is all NaN.")

            plot_args_vel.append({
                "x": df[config.DF_FRAME],
                "y": df[data_to_plot_vel],
                "label": obj_id
            })

        self.plot_widget.plot_multiple_data(plot_args_vel, data_to_plot_vel)
        print(f"✓ Velocity data ('{data_to_plot_vel}') flows correctly for plotting.")


if __name__ == '__main__':
    unittest.main()
