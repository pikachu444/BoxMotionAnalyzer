import unittest
import pandas as pd
from src.analysis.validator import DataValidator

class TestDataValidator(unittest.TestCase):
    def test_validate_data_sufficiency_success(self):
        # Create a dataframe with 50 rows
        df = pd.DataFrame({'A': range(50)})
        try:
            DataValidator.validate_data_sufficiency(df, min_rows=50)
        except ValueError:
            self.fail("validate_data_sufficiency raised ValueError unexpectedly!")

    def test_validate_data_sufficiency_failure(self):
        # Create a dataframe with 49 rows
        df = pd.DataFrame({'A': range(49)})
        with self.assertRaises(ValueError):
            DataValidator.validate_data_sufficiency(df, min_rows=50)

    def test_validate_required_columns_success(self):
        df = pd.DataFrame({
            'Time': [1, 2, 3],
            'RigidBody_Position_X': [1, 2, 3],
            'RigidBody_Position_Y': [1, 2, 3],
            'RigidBody_Position_Z': [1, 2, 3]
        })
        required_cols = ['Time', 'RigidBody_Position_X', 'RigidBody_Position_Y', 'RigidBody_Position_Z']
        try:
            DataValidator.validate_required_columns(df, required_cols)
        except ValueError:
            self.fail("validate_required_columns raised ValueError unexpectedly!")

    def test_validate_required_columns_failure(self):
        df = pd.DataFrame({
            'Time': [1, 2, 3],
            'RigidBody_Position_X': [1, 2, 3]
            # Missing Y and Z
        })
        required_cols = ['Time', 'RigidBody_Position_X', 'RigidBody_Position_Y', 'RigidBody_Position_Z']
        with self.assertRaises(ValueError) as cm:
            DataValidator.validate_required_columns(df, required_cols)
        self.assertIn("Missing required columns", str(cm.exception))

if __name__ == '__main__':
    unittest.main()
