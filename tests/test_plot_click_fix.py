import unittest
import pandas as pd
import os
import sys
from unittest.mock import MagicMock
from PySide6.QtWidgets import QApplication, QListWidgetItem
from src.main_app import MainApp

class TestPlotClickFix(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        """Set up the QApplication instance once for all tests."""
        cls.app = QApplication.instance()
        if not cls.app:
            cls.app = QApplication(sys.argv)

    def setUp(self):
        """Set up a dummy CSV file and the MainApp instance for testing."""
        self.test_csv_path = "test_plot_click_data.csv"
        # Dummy data with a time index
        csv_content = (
            "Time,Data\n"
            "Time,Value\n"
            "Time,X\n"
            "10.0,100\n"
            "10.1,110\n"
            "10.2,120\n"
            "10.3,130\n"
        )
        with open(self.test_csv_path, "w") as f:
            f.write(csv_content)

        self.window = MainApp()
        self.window.result_folder_path_label.setText(".")
        # Load the data into the MainApp instance
        item = QListWidgetItem(self.test_csv_path)
        self.window.on_result_file_selected(item)

    def tearDown(self):
        """Clean up the dummy CSV file."""
        if os.path.exists(self.test_csv_path):
            os.remove(self.test_csv_path)

    def test_on_result_plot_click_with_get_indexer(self):
        """
        Test that on_result_plot_click correctly finds the nearest index
        using the modern get_indexer method without raising a TypeError.
        """
        # Create a mock event object that mimics a Matplotlib mouse event
        # We simulate a click at time 10.16, which is closest to 10.2
        mock_event = MagicMock()
        mock_event.inaxes = self.window.plot_manager2.ax
        mock_event.xdata = 10.16

        # Call the method to be tested
        try:
            self.window.on_result_plot_click(mock_event)
        except TypeError as e:
            self.fail(f"on_result_plot_click raised a TypeError unexpectedly: {e}")

        # Assert that the correct nearest point was selected
        expected_time = 10.2
        actual_time = self.window.selected_point_info['time']
        self.assertAlmostEqual(expected_time, actual_time, places=5,
                               msg="The selected time should be the nearest actual time point.")

        # Simulate another click, this time closer to 10.1
        mock_event.xdata = 10.11
        self.window.on_result_plot_click(mock_event)
        expected_time_2 = 10.1
        actual_time_2 = self.window.selected_point_info['time']
        self.assertAlmostEqual(expected_time_2, actual_time_2, places=5,
                               msg="The selected time should be the nearest actual time point.")


if __name__ == '__main__':
    unittest.main()
