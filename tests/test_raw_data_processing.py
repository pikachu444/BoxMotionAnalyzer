import unittest
from unittest.mock import MagicMock, patch
import pandas as pd
from PySide6.QtWidgets import QApplication
from src.analysis.ui.widget_raw_data_processing import WidgetRawDataProcessing

# QApplication is required for QWidget
app = QApplication.instance() or QApplication([])

class TestWidgetRawDataProcessing(unittest.TestCase):
    def setUp(self):
        self.mock_data_loader = MagicMock()
        self.mock_parser = MagicMock()
        self.widget = WidgetRawDataProcessing(self.mock_data_loader, self.mock_parser)

    def tearDown(self):
        self.widget.close()
        self.widget.deleteLater()
        app.processEvents()

    def test_file_load_emit_signal_handcrafted_fixture(self):
        # Handcrafted schema fixture; not real-capture evidence.
        import os
        real_file_path = os.path.abspath("data/testdata_box_marker.csv")
        self.assertTrue(os.path.isfile(real_file_path), "Required public schema fixture is missing")

        # We need to use the real DataLoader and Parser for this integration test
        from src.analysis.pipeline.data_loader import DataLoader
        from src.analysis.pipeline.parser import Parser
        from src.config.data_columns import FACE_PREFIX_TO_INFO
        
        real_loader = DataLoader()
        real_parser = Parser(face_prefix_map=FACE_PREFIX_TO_INFO)
        
        # Re-initialize widget with real components
        self.widget.close()
        self.widget.deleteLater()
        app.processEvents()
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

    def test_initial_marker_preview_and_retained_explicit_selection(self):
        from src.analysis.pipeline.data_loader import DataLoader
        from src.config.data_columns import DisplayNames, RigidBodyCols
        import numpy as np

        self.widget.data_loader = DataLoader()
        marker_only = pd.DataFrame({'B1_X': [10., 11., 12.], 'B1_Y': [20., 21., 22.],
                                    'B1_Z': [30., 31., 32.]}, index=[0., .01, .02])
        with_center = marker_only.copy()
        with_center[f'{RigidBodyCols.BASE_NAME}_X'] = [100., 101., 102.]

        for frame, selected, expected_target, expected_values in (
                (marker_only, [], 'Marker B1', [10., 11., 12.]),
                (with_center, [], DisplayNames.RB_CENTER, [100., 101., 102.]),
                (with_center, ['Marker B1'], 'Marker B1', [10., 11., 12.])):
            with self.subTest(expected_target=expected_target, selected=selected):
                self.widget.current_selected_targets = selected
                preview = dict(header_info={}, raw_data=frame, parsed_data=frame,
                    source_sha256='a' * 64,
                    marker_state=(None, frame, frame, 'capture.csv', 'a' * 64, [], {}))
                self.widget._apply_csv_preview('capture.csv', preview, emit=False)
                self.assertEqual(self.widget.current_selected_targets, [expected_target])
                self.assertEqual(self.widget.selected_data_label.text(), f'Selected: {expected_target}')
                # SpanSelector also owns two handle lines; count data channels.
                lines = [line for line in self.widget.plot_manager.ax.lines if line.get_label() in frame.columns]
                self.assertEqual(len(lines), 1)
                np.testing.assert_array_equal(lines[0].get_xdata(), frame.index)
                np.testing.assert_array_equal(lines[0].get_ydata(), expected_values)

if __name__ == '__main__':
    unittest.main()
