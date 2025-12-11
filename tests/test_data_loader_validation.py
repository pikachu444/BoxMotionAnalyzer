import unittest
import pandas as pd
from src.analysis.core.data_loader import DataLoader

class TestDataLoaderValidation(unittest.TestCase):
    def test_validate_raw_data_valid(self):
        """Tests that validation passes when 'Time' is present."""
        loader = DataLoader()
        # Case 1: Standard 'Time'
        df1 = pd.DataFrame({'Time': [0, 1], 'Val': [1, 2]})
        try:
            loader.validate_raw_data(df1)
        except ValueError:
            self.fail("validate_raw_data raised ValueError unexpectedly for 'Time'.")

        # Case 2: Fuzzy 'Time (Seconds)'
        df2 = pd.DataFrame({'Time (Seconds)': [0, 1], 'Val': [1, 2]})
        try:
            loader.validate_raw_data(df2)
        except ValueError:
            self.fail("validate_raw_data raised ValueError unexpectedly for 'Time (Seconds)'.")

        # Case 3: 'Frame'
        df3 = pd.DataFrame({'Frame': [0, 1], 'Val': [1, 2]})
        try:
            loader.validate_raw_data(df3)
        except ValueError:
            self.fail("validate_raw_data raised ValueError unexpectedly for 'Frame'.")

    def test_validate_raw_data_invalid(self):
        """Tests that validation fails when 'Time' is missing."""
        loader = DataLoader()
        # Case: Missing Time/Frame
        df = pd.DataFrame({'Value': [1, 2], 'Another': [3, 4]})

        with self.assertRaises(ValueError) as context:
            loader.validate_raw_data(df)

        self.assertIn("Invalid CSV format", str(context.exception))
        self.assertIn("Missing 'Time'", str(context.exception))

if __name__ == '__main__':
    unittest.main()
