import unittest
from unittest.mock import MagicMock, patch
import pandas as pd
import numpy as np
from PySide6.QtWidgets import QApplication
from src.ui.widget_results_analyzer import WidgetResultsAnalyzer
from src.config.data_columns import HeaderL1, HeaderL2, HeaderL3

# QApplication is required for QWidget
app = QApplication([])

class TestWidgetResultsAnalyzer(unittest.TestCase):
    def setUp(self):
        self.mock_data_loader = MagicMock()
        self.widget = WidgetResultsAnalyzer(self.mock_data_loader)
        
        # Mock UI elements that are used in export
        self.widget.le_scene_name = MagicMock()
        self.widget.le_run_time = MagicMock()
        self.widget.le_time_step = MagicMock()
        self.widget.offset_manual_checkbox = MagicMock()
        self.widget.manual_height_checkbox = MagicMock()
        self.widget.offset_combos = [MagicMock(), MagicMock(), MagicMock()]
        self.widget.manual_height_inputs = [MagicMock(), MagicMock(), MagicMock()]
        self.widget.log_message = MagicMock() # Mock signal

    def _create_test_result_data(self, heights, velocities):
        """Helper to create result_data DataFrame"""
        height_cols = [(HeaderL1.ANALYSIS, f'C{i+1}', HeaderL3.REL_H) for i in range(8)]
        vel_cols = [
            (HeaderL1.VEL, HeaderL2.COM, HeaderL3.WX), (HeaderL1.VEL, HeaderL2.COM, HeaderL3.WY),
            (HeaderL1.VEL, HeaderL2.COM, HeaderL3.WZ), (HeaderL1.VEL, HeaderL2.COM, HeaderL3.VX),
            (HeaderL1.VEL, HeaderL2.COM, HeaderL3.VY), (HeaderL1.VEL, HeaderL2.COM, HeaderL3.VZ),
        ]

        all_cols = height_cols + vel_cols
        all_data = heights + velocities

        data_dict = {col: [val] for col, val in zip(all_cols, all_data)}

        df = pd.DataFrame(data_dict, index=[1.0])
        df.index.name = 'Time'
        return df

    @patch('builtins.open')
    @patch('PySide6.QtWidgets.QFileDialog.getSaveFileName')
    def test_export_scenario_auto_mode(self, mock_get_save_file_name, mock_open):
        # Setup
        mock_get_save_file_name.return_value = ('/fake/path/scenario.csv', None)
        mock_file_handle = MagicMock()
        mock_open.return_value.__enter__.return_value = mock_file_handle

        # Test Data
        heights = [10.0, 20.0, 5.0, 30.0, 100.0, 110.0, 120.0, 130.0]
        velocities = [0.1, 0.2, 0.3, 100.0, 200.0, 300.0]
        self.widget.result_data = self._create_test_result_data(heights, velocities)
        self.widget.selected_point_info = {'time': 1.0, 'index': 0}

        # UI Inputs
        self.widget.offset_manual_checkbox.isChecked.return_value = False
        self.widget.le_scene_name.text.return_value = "TestScene1"
        self.widget.le_run_time.text.return_value = "0.25"
        self.widget.le_time_step.text.return_value = "1e-6"

        # Execute
        self.widget.export_analysis_scenario()

        # Verify
        mock_open.assert_called_once_with('/fake/path/scenario.csv', 'w')
        written_string = mock_file_handle.write.call_args[0][0]
        
        # Check key content in the written string
        self.assertIn("drop_name,TestScene1", written_string)
        self.assertIn("variable_1,RightTopRear,value_1,5.000000", written_string) # Min height in group 1
        self.assertIn("run_time,0.25", written_string)

    @patch('builtins.open')
    @patch('PySide6.QtWidgets.QFileDialog.getSaveFileName')
    def test_export_scenario_manual_height_mode(self, mock_get_save_file_name, mock_open):
        # Setup
        mock_get_save_file_name.return_value = ('/fake/path/scenario_manual.csv', None)
        mock_file_handle = MagicMock()
        mock_open.return_value.__enter__.return_value = mock_file_handle

        # Satisfy initial check
        self.widget.result_data = pd.DataFrame() # Dummy
        self.widget.selected_point_info = {'time': 0.0, 'index': 0}

        # UI Inputs for Manual Height
        self.widget.offset_manual_checkbox.isChecked.return_value = True
        self.widget.manual_height_checkbox.isChecked.return_value = True
        
        self.widget.offset_combos[0].currentText.return_value = 'C1'
        self.widget.offset_combos[1].currentText.return_value = 'C2'
        self.widget.offset_combos[2].currentText.return_value = 'C3'
        
        self.widget.manual_height_inputs[0].text.return_value = "50.5"
        self.widget.manual_height_inputs[1].text.return_value = "60.6"
        self.widget.manual_height_inputs[2].text.return_value = "70.7"
        
        self.widget.le_scene_name.text.return_value = "ManualHeightTest"

        # Execute
        self.widget.export_analysis_scenario()

        # Verify
        written_string = mock_file_handle.write.call_args[0][0]
        self.assertIn("drop_name,ManualHeightTest", written_string)
        self.assertIn("variable_1,LeftBottomRear,value_1,50.500000", written_string)
        self.assertIn("variable_2,RightBottomRear,value_2,60.600000", written_string)
        self.assertIn("variable_3,RightTopRear,value_3,70.700000", written_string)

if __name__ == '__main__':
    unittest.main()
