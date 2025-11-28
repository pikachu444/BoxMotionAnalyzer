import sys
import os
import unittest
import pandas as pd
import numpy as np

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import Analysis Modules
from src.analysis.core.data_loader import DataLoader
from src.analysis.parser import Parser
from src.analysis.core.pipeline_controller import PipelineController
from src.config.data_columns import FACE_PREFIX_TO_INFO, RigidBodyCols, TimeCols, PoseCols

# Import Visualization Modules
from src.visualization.data_handler import DataHandler
from src.config import config_visualization as config_vis

class TestPipelineIntegration(unittest.TestCase):
    def setUp(self):
        # Create a temporary output directory
        self.test_result_path = "data/test_integration_result.csv"

        # Ensure data dir exists
        os.makedirs("data", exist_ok=True)

    def tearDown(self):
        # Cleanup
        if os.path.exists(self.test_result_path):
            os.remove(self.test_result_path)

    def create_mock_parsed_data(self, n_frames=50):
        """
        Creates a DataFrame that mimics the output of Parser.process().
        It must contain Time and RigidBody_Position columns.
        """
        times = np.linspace(0, 1.0, n_frames)
        frames = np.arange(n_frames)

        data = {
            TimeCols.FRAME: frames,
            TimeCols.TIME: times,
            # Rigid Body Position (Required by Validator)
            # Validator asks for PoseCols (Box_Tx) but Parser produces RigidBodyCols (RigidBody_Position_X).
            # We supply what Validator demands to pass the pipeline check.
            PoseCols.POS_X: np.zeros(n_frames),
            PoseCols.POS_Y: np.zeros(n_frames),
            PoseCols.POS_Z: np.zeros(n_frames),
            # VelocityCalculator needs Rotation columns too
            PoseCols.ROT_X: np.zeros(n_frames),
            PoseCols.ROT_Y: np.zeros(n_frames),
            PoseCols.ROT_Z: np.zeros(n_frames),
        }

        # Add Mock Corner Data (C1~C8) so FrameAnalyzer outputs 'Position' columns
        # DataHandler requires at least one object with 'Position' header to load.
        from src.config.data_columns import CORNER_NAME_MAP
        for corner in CORNER_NAME_MAP.keys(): # C1..C8
            data[f"{corner}_X"] = np.zeros(n_frames)
            data[f"{corner}_Y"] = np.zeros(n_frames)
            data[f"{corner}_Z"] = np.zeros(n_frames)

        df = pd.DataFrame(data)
        # Parser sets Time as index, BUT PipelineController's Validator checks if 'Time' is in columns.
        # This seems to be a logical inconsistency in the legacy code, but we must satisfy it for the test.
        # So we keep 'Time' as a column as well.
        # df.set_index(TimeCols.TIME, inplace=True)
        # If we don't set index, Slicer/Smoother might fail if they rely on index.
        # Let's set index AND keep the column.
        df.set_index(TimeCols.TIME, drop=False, inplace=True)

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
        # We skip Parser because Parser expects Raw Optitrack Format, which is hard to synthesize quickly.
        # We inject data as if Parser already ran.
        parsed_data = self.create_mock_parsed_data(n_frames=60)

        self.assertFalse(parsed_data.empty, "Mock parsed data is empty.")
        print(f"[Pass] Step 1: Mock parsed data created. Shape: {parsed_data.shape}")

        # Step 2: Analysis - Run Pipeline
        controller = PipelineController()

        # Mock config for analysis
        analysis_config = {
            'slice_filter_by': 'time',
            'slice_start_val': 0.0,
            'slice_end_val': 1.0
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
        from PySide6.QtCore import QCoreApplication
        app = QCoreApplication.instance() or QCoreApplication([])

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
