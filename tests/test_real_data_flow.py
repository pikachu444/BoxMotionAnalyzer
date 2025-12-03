import sys
import os
import unittest
import pandas as pd

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.analysis.core.data_loader import DataLoader
from src.analysis.core.pipeline_controller import PipelineController
from src.utils.header_converter import convert_to_multi_header
from src.visualization.data_handler import DataHandler
from src.config import config_visualization as config_vis

class TestRealDataFlow(unittest.TestCase):
    def setUp(self):
        self.raw_csv_path = "TestSets/VDTest_S5_001.csv"
        self.result_csv_path = "data/test_real_data_result.csv"
        os.makedirs("data", exist_ok=True)

    def tearDown(self):
        # Keep the result file for inspection if it failed
        pass

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

if __name__ == '__main__':
    unittest.main()
