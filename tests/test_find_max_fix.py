import unittest
import pandas as pd
import os
import sys
from PySide6.QtWidgets import QApplication, QListWidgetItem, QComboBox
from src.main_app import MainApp

class TestFindMaxFix(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        """Set up the QApplication instance once for all tests."""
        cls.app = QApplication.instance()
        if not cls.app:
            cls.app = QApplication(sys.argv)

    def setUp(self):
        """Set up a dummy CSV file and the MainApp instance for testing."""
        self.test_csv_path = "test_find_max_data.csv"
        # The maximum value (999) is at Time=1.2
        csv_content = (
            "Time,Data,Data\n"
            "Time,Value,Value2\n"
            "Time,X,Y\n"
            "1.0,10,100\n"
            "1.1,50,500\n"
            "1.2,999,9990\n"
            "1.3,20,200\n"
        )
        with open(self.test_csv_path, "w") as f:
            f.write(csv_content)

        # We need an instance of MainApp to test its methods
        self.window = MainApp()
        # Mocking necessary UI elements that are accessed
        self.window.result_folder_path_label.setText(".")
        self.window.find_max_target_combo = QComboBox()


    def tearDown(self):
        """Clean up the dummy CSV file."""
        if os.path.exists(self.test_csv_path):
            os.remove(self.test_csv_path)

    def test_find_max_returns_correct_time_index(self):
        """
        Test that on_find_max_click correctly uses the time-based index
        instead of the integer-based row index.
        """
        # 1. Simulate loading the result file
        # This calls the modified on_result_file_selected method
        item = QListWidgetItem(self.test_csv_path)
        self.window.on_result_file_selected(item)

        # 2. Simulate setting up the target for "Find Max"
        target_column = ('Data', 'Value', 'X')
        self.window.find_max_target_combo.addItem("Data/Value/X", userData=target_column)
        self.window.find_max_target_combo.setCurrentIndex(0)

        # 3. Call the function to be tested
        self.window.on_find_max_click()

        # 4. Assert the results
        # The row index of the max value is 2, but the time index is 1.2
        expected_time = 1.2
        actual_time = self.window.selected_point_info['time']

        self.assertIsNotNone(actual_time, "Time should not be None after finding max.")
        self.assertNotEqual(actual_time, 2, "The time should not be the integer row index.")
        self.assertAlmostEqual(expected_time, actual_time, places=5, msg="The found time should be the value from the Time index.")

if __name__ == '__main__':
    # Note: Running this directly might have issues with QApplication.
    # It's better to run with `python -m unittest tests/test_find_max_fix.py`
    unittest.main()
