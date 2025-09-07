import unittest
import os
import sys
import pandas as pd
from unittest.mock import patch, MagicMock
from PySide6.QtWidgets import QApplication
from src.main_app import MainApp
from src.config import config_app

class TestBoxDimsUpdate(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        """Set up the QApplication instance once for all tests."""
        cls.app = QApplication.instance()
        if not cls.app:
            cls.app = QApplication(sys.argv)

    def setUp(self):
        """Set up the MainApp instance for testing."""
        self.window = MainApp()
        # Mock the raw_data to prevent the run_pipeline method from returning early
        self.window.raw_data = pd.DataFrame({'A': [1]})
        # Mock parsed_data as well to prevent AttributeError in the try block
        self.window.parsed_data = pd.DataFrame({'B': [1]}, index=[0])
        # Mock the worker and its start method to prevent the actual pipeline from running
        self.mock_worker = MagicMock()
        self.mock_pipeline_worker_patch = patch('src.main_app.PipelineWorker', return_value=self.mock_worker)
        self.mock_pipeline_worker = self.mock_pipeline_worker_patch.start()

    def tearDown(self):
        self.mock_pipeline_worker_patch.stop()

    def test_box_dims_are_updated_globally(self):
        """
        Test that changing dimensions in the GUI and running the pipeline
        updates the global config_app.BOX_DIMS variable.
        """
        # 1. Store original global value
        original_dims = list(config_app.BOX_DIMS)

        # 2. Set new values in the GUI line edits
        new_l, new_w, new_h = 100.0, 200.0, 300.0
        self.window.le_box_l.setText(str(new_l))
        self.window.le_box_w.setText(str(new_w))
        self.window.le_box_h.setText(str(new_h))

        # 3. Call the run_pipeline method
        self.window.run_pipeline()

        # 4. Assert that the global config_app.BOX_DIMS has changed
        self.assertNotEqual(config_app.BOX_DIMS, original_dims, "config_app.BOX_DIMS should have been updated.")
        self.assertEqual(config_app.BOX_DIMS, [new_l, new_w, new_h], "config_app.BOX_DIMS should match the new GUI values.")

        # 5. Check that the correct config is passed to the worker (optional but good)
        # The worker is called with the config dictionary. We check if it was called.
        self.mock_worker.start.assert_called_once()

        # Restore original value to not affect other tests
        config_app.BOX_DIMS = original_dims


if __name__ == '__main__':
    unittest.main()
