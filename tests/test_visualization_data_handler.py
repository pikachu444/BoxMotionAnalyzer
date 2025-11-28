import unittest
import os
import pandas as pd
from src.visualization.data_handler import DataHandler
from src.config import config_visualization as config

class TestDataHandlerRefactor(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        """Set up for the test class. Generate the test data once."""
        # Ensure the test data file is up-to-date with the multi-header format
        try:
            from src.visualization import make_testdata
            make_testdata.main()
            print(f"Test data generated at {config.TEST_CSV_PATH}")
        except Exception as e:
            cls.fail(f"Failed to generate test data: {e}")

    def setUp(self):
        """Set up for each test."""
        self.data_handler = DataHandler()
        self.test_csv_path = config.TEST_CSV_PATH
        self.assertTrue(os.path.exists(self.test_csv_path), "Test CSV file should exist.")

    def test_multi_header_loading_and_processing(self):
        """
        Verify that the refactored DataHandler correctly loads and processes
        the new multi-header CSV format.
        """
        # --- 1. Test Successful Loading ---
        # The method name changed to load_analysis_result
        success = self.data_handler.load_analysis_result(self.test_csv_path)
        self.assertTrue(success, "load_analysis_result should return True on success.")

        df = self.data_handler.visualization_dataframe
        self.assertIsNotNone(df, "Visualization dataframe should not be None after loading.")

        # --- 2. Test DataFrame Structure and Columns ---
        expected_columns = [
            config.DF_FRAME, config.DF_TIME, config.DF_OBJECT_ID,
            config.DF_POS_X, config.DF_POS_Y, config.DF_POS_Z,
            config.DF_VEL_X, config.DF_VEL_Y, config.DF_VEL_Z
        ]

        # Check if all expected columns are present
        for col in expected_columns:
            self.assertIn(col, df.columns, f"Column {col} missing from DataFrame")

        print("\n✓ Final DataFrame has the correct columns.")

        # --- 3. Test Data Integrity ---
        # Check for unexpected NaN values
        # Note: Velocity might be NaN if not present, but our test data has it.
        self.assertFalse(df.isnull().values.any(), "There should be no NaN values in the final DataFrame for test data.")

        # Check data types
        self.assertTrue(pd.api.types.is_integer_dtype(df[config.DF_FRAME]))
        self.assertTrue(pd.api.types.is_string_dtype(df[config.DF_OBJECT_ID]))
        self.assertTrue(pd.api.types.is_numeric_dtype(df[config.DF_POS_X]))
        self.assertTrue(pd.api.types.is_numeric_dtype(df[config.DF_VEL_Z]))
        print("✓ Data types are correct.")

        # --- 4. Test Handler State ---
        # Check n_frames
        self.assertEqual(self.data_handler.n_frames, config.N_FRAMES, "n_frames is not set correctly.")

        # Check object_ids
        expected_ids = sorted(config.BOX_CORNERS_LABELS + config.MARKER_LABELS)
        self.assertListEqual(self.data_handler.get_object_ids(), expected_ids,
                             "get_object_ids() does not return the correct list of IDs.")
        print("✓ DataHandler state (n_frames, object_ids) is correct.")

        # --- 5. Test Getter Methods ---
        frame_data = self.data_handler.get_frame_data(10)
        self.assertIsNotNone(frame_data)
        # Should return one row per object for that frame
        self.assertEqual(len(frame_data), len(expected_ids), "get_frame_data should return data for all objects.")

        object_data = self.data_handler.get_object_timeseries('C1')
        self.assertIsNotNone(object_data)
        self.assertEqual(len(object_data), config.N_FRAMES, "get_object_timeseries should return data for all frames.")
        print("✓ Getter methods work as expected.")


if __name__ == '__main__':
    unittest.main()
