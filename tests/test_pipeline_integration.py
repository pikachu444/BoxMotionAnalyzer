import sys
import os
import unittest
import pandas as pd
import numpy as np

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import Analysis Modules
from src.analysis.pipeline.data_loader import DataLoader
from src.analysis.pipeline.parser import Parser
from src.analysis.pipeline.pipeline_controller import PipelineController
from src.config.data_columns import FACE_PREFIX_TO_INFO, RigidBodyCols, TimeCols, PoseCols

# Import Visualization Modules
from src.visualization.data_handler import DataHandler
from src.config import config_visualization as config_vis

class TestPipelineIntegration(unittest.TestCase):
    def setUp(self):
        from src.config import config_app
        original_dims = config_app.BOX_DIMS
        original_corners = config_app.LOCAL_BOX_CORNERS
        self.addCleanup(setattr, config_app, 'BOX_DIMS', original_dims)
        self.addCleanup(setattr, config_app, 'LOCAL_BOX_CORNERS', original_corners)
        # Create a temporary output directory
        self.test_result_path = "data/test_integration_result.csv"

        # Ensure data dir exists
        os.makedirs("data", exist_ok=True)

    def tearDown(self):
        # Cleanup
        if os.path.exists(self.test_result_path):
            os.remove(self.test_result_path)

    def create_mock_parsed_data(self, n_frames=50):
        """Parse an explicit healthy layout; do not rely on prefilled stale poses."""
        from marker_face_fixtures import raw_bundle
        header, raw, truth = raw_bundle(samples=n_frames, boundary=n_frames)
        df = Parser(FACE_PREFIX_TO_INFO).process(header, raw)
        # Retain the rigid-body center required by this legacy validator path.
        for i, col in enumerate((RigidBodyCols.POS_X, RigidBodyCols.POS_Y, RigidBodyCols.POS_Z)):
            df[col] = truth[:, i]
        df[TimeCols.TIME] = df.index
        return df

    def test_full_pipeline_flow(self):
        """
        Verifies:
        1. Mock Data Injection (Simulating Parsed Data)
        2. Processing pipeline (Analysis)
        3. Result export (Analysis)
        4. Result loading (Visualization)
        """
        print("\n[Test] Starting Full Pipeline Integration Test...")

        # Step 1: Mock Parsed Data
        # Use the real Parser on an explicit healthy constraint layout.
        parsed_data = self.create_mock_parsed_data(n_frames=60)

        self.assertFalse(parsed_data.empty, "Mock parsed data is empty.")
        print(f"[Pass] Step 1: Mock parsed data created. Shape: {parsed_data.shape}")

        # Step 2: Analysis - Run Pipeline
        controller = PipelineController()

        # Mock config for analysis
        analysis_config = {
            'slice_filter_by': 'time',
            'slice_start_val': 0.0,
            'slice_end_val': 1.0,
            'box_dimensions': (200., 120., 80.)
        }

        results = []
        errors = []
        logs = []

        def on_finished(df):
            results.append(df)

        def on_failed(msg):
            errors.append(msg)

        def on_log(msg):
            logs.append(msg)

        controller.analysis_finished.connect(on_finished)
        controller.analysis_failed.connect(on_failed)
        controller.log_message.connect(on_log)

        # We need an event loop for signals to work
        from PySide6.QtWidgets import QApplication
        app = QApplication.instance() or QApplication([])

        print("\n[Analysis Logs Start]")
        # We pass None for header_info and raw_data because we provide parsed_data
        controller.run_analysis(analysis_config, {}, None, parsed_data)
        print("[Analysis Logs End]\n")

        # Process events to let signal emit
        app.processEvents()

        if logs:
            # Uncomment to debug
            # for log in logs:
            #     print(f"  > {log}")
            pass

        if errors:
            print(f"[Error Captured] {errors}")

        if not results:
            self.fail(f"Analysis did not produce results. Errors: {errors}")

        result_df = results[0]
        self.assertFalse(result_df.empty, "Analysis result is empty.")

        # Check if result has expected columns (e.g., Velocity, Pose)
        # PoseCols.POS_X = 'Box_Tx'
        if PoseCols.POS_X in result_df.columns:
            print(f"  > Result contains {PoseCols.POS_X}")

        print(f"[Pass] Step 2: Analysis complete. Result Shape: {result_df.shape}")

        # Step 3: Export Results
        # We need to convert to Multi-Header CSV format expected by Visualization
        from src.utils.header_converter import convert_to_multi_header

        # Ensure result_df has 'Time' column for export if it's in index
        # But if 'Time' is ALREADY in columns AND in index, reset_index will fail.
        if TimeCols.TIME in result_df.columns and result_df.index.name == TimeCols.TIME:
             result_df = result_df.drop(columns=[TimeCols.TIME])

        export_df = convert_to_multi_header(result_df)
        export_df.to_csv(self.test_result_path, index=False)
        self.assertTrue(os.path.exists(self.test_result_path), "Export failed.")
        print(f"[Pass] Step 3: Results exported to {self.test_result_path}")

        # Step 4: Visualization - Load Data
        data_handler = DataHandler()
        success = data_handler.load_analysis_result(self.test_result_path)

        if not success:
            # Debugging why loading failed
            print("  > DataHandler failed to load. Checking file content...")
            try:
                with open(self.test_result_path, 'r') as f:
                    print(f"  > Header Line 1: {f.readline().strip()}")
                    print(f"  > Header Line 2: {f.readline().strip()}")
                    print(f"  > Header Line 3: {f.readline().strip()}")
            except:
                pass

        self.assertTrue(success, "DataHandler failed to load the exported CSV.")
        self.assertIsNotNone(data_handler.visualization_dataframe, "Visualization DataFrame is None.")
        self.assertGreater(data_handler.n_frames, 0, "No frames loaded.")
        print(f"[Pass] Step 4: Visualization loaded data successfully.")

        print(f"[Success] Integration Test Passed!")

if __name__ == '__main__':
    unittest.main()
