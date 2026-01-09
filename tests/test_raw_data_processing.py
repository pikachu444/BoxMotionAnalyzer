import unittest
from unittest.mock import MagicMock, patch
import pandas as pd
from PySide6.QtWidgets import QApplication
from src.analysis.ui.widget_raw_data_processing import WidgetRawDataProcessing
from src.config.data_columns import PoseCols

# QApplication is required for QWidget
app = QApplication.instance() or QApplication([])

class TestWidgetRawDataProcessing(unittest.TestCase):
    def setUp(self):
        self.mock_data_loader = MagicMock()
        self.mock_parser = MagicMock()
        self.widget = WidgetRawDataProcessing(self.mock_data_loader, self.mock_parser)

    def test_file_load_emit_signal_real_data(self):
        # Use real data from TestSets
        import os
        real_file_path = os.path.abspath("data/testdata_box_marker.csv")
        if not os.path.exists(real_file_path):
            # Fallback to creating it if missing or using another one
            # The prompt memory mentions 'src/utils/make_testdata.py'
             self.skipTest(f"Test file not found: {real_file_path}")

        # We need to use the real DataLoader and Parser for this integration test
        from src.analysis.core.data_loader import DataLoader
        from src.analysis.parser import Parser
        from src.config.data_columns import FACE_PREFIX_TO_INFO
        
        real_loader = DataLoader()
        real_parser = Parser(face_prefix_map=FACE_PREFIX_TO_INFO)
        
        # Re-initialize widget with real components
        self.widget = WidgetRawDataProcessing(real_loader, real_parser)

        # Mock file dialog to return the real path
        with patch('PySide6.QtWidgets.QFileDialog.getOpenFileName', return_value=(real_file_path, 'CSV Files (*.csv)')):
            # Connect signal to a mock slot
            mock_slot = MagicMock()
            self.widget.file_loaded.connect(mock_slot)
            
            # Trigger action
            self.widget.open_csv_file()
            
            # Verify
            # Check if signal was emitted
            mock_slot.assert_called_once()
            args = mock_slot.call_args[0]
            
            # Verify header info (basic check)
            self.assertIsInstance(args[0], dict)
            
            # Verify raw data (basic check)
            self.assertIsInstance(args[1], pd.DataFrame)
            self.assertFalse(args[1].empty)
            
            # Verify parsed data (basic check)
            self.assertIsInstance(args[2], pd.DataFrame)
            self.assertFalse(args[2].empty)
            print(f"Successfully loaded and parsed {real_file_path}")
            print(f"Parsed data shape: {args[2].shape}")

if __name__ == '__main__':
    unittest.main()
