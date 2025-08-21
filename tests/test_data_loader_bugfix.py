import unittest
import pandas as pd
import os
from src.data_loader import DataLoader
from src.config.data_columns import TimeCols

class TestDataLoaderFix(unittest.TestCase):

    def setUp(self):
        """Set up a dummy CSV file for testing."""
        self.test_csv_path = "test_no_time_column.csv"
        # Create a dummy multi-header CSV string WITHOUT a time column
        # The header has 3 levels.
        csv_content = (
            "Pose,Pose,Data\n"
            "Box,Box,Value\n"
            "Position-X,Position-Y,Random\n"
            "1.0,2.0,100\n"
            "1.1,2.1,101\n"
        )
        with open(self.test_csv_path, "w") as f:
            f.write(csv_content)

    def tearDown(self):
        """Clean up the dummy CSV file."""
        if os.path.exists(self.test_csv_path):
            os.remove(self.test_csv_path)

    def test_load_result_csv_no_time_column(self):
        """
        Test that load_result_csv handles a missing 'Time' column gracefully
        without raising an AttributeError.
        """
        data_loader = DataLoader()

        # This call should not raise an AttributeError
        try:
            df = data_loader.load_result_csv(self.test_csv_path)
        except AttributeError as e:
            self.fail(f"load_result_csv raised an AttributeError unexpectedly: {e}")

        # Verify that the returned object is a DataFrame
        self.assertIsInstance(df, pd.DataFrame)

        # Verify that the index is a default integer index (RangeIndex)
        # because no 'Time' column was found to set as the index.
        self.assertIsInstance(df.index, pd.RangeIndex)

        # Verify the content of the dataframe
        self.assertEqual(df.shape, (2, 3))
        # Check one of the values to be sure
        # The column name is a tuple: ('Pose', 'Box', 'Position-X')
        self.assertEqual(df[('Pose', 'Box', 'Position-X')].iloc[0], 1.0)

if __name__ == '__main__':
    unittest.main()
