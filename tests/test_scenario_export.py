import unittest
from unittest.mock import MagicMock, patch
import pandas as pd
import numpy as np

# 테스트 대상 모듈 임포트
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.main_app import MainApp
from src.config.data_columns import AnalysisCols, VelocityCols, HeaderL1, HeaderL2, HeaderL3, CORNER_NAME_MAP

class TestScenarioExport(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        """테스트 전체에 걸쳐 한 번만 실행되는 설정"""
        cls.mock_app = MagicMock()
        sys.modules['PySide6.QtWidgets.QApplication'] = cls.mock_app

    def setUp(self):
        """각 테스트 케이스 실행 전에 호출되는 설정"""
        with patch('src.main_app.MainApp.__init__', lambda x: None):
            self.app = MainApp()

        self.app.result_data = None
        self.app.selected_point_info = {'time': None, 'index': None}
        self.app.log_output = MagicMock()
        self.app.statusBar = MagicMock()

        self.app.offset_manual_checkbox = MagicMock()
        self.app.offset_combos = [MagicMock(), MagicMock(), MagicMock()]
        self.app.le_run_time = MagicMock()
        self.app.le_time_step = MagicMock()
        self.app.le_scene_name = MagicMock()

    def _create_test_result_data(self, heights, velocities):
        """테스트용 result_data DataFrame을 생성하는 헬퍼 메서드"""
        height_cols = [(HeaderL1.ANALYSIS_SCENARIO, f'C{i+1}', HeaderL3.ANALYSIS_INPUT_H) for i in range(8)]
        vel_cols = [
            (HeaderL1.VEL, HeaderL2.COM, HeaderL3.WX),
            (HeaderL1.VEL, HeaderL2.COM, HeaderL3.WY),
            (HeaderL1.VEL, HeaderL2.COM, HeaderL3.WZ),
            (HeaderL1.VEL, HeaderL2.COM, HeaderL3.VX),
            (HeaderL1.VEL, HeaderL2.COM, HeaderL3.VY),
            (HeaderL1.VEL, HeaderL2.COM, HeaderL3.VZ),
        ]

        data = np.array([heights + velocities])
        columns = pd.MultiIndex.from_tuples(height_cols + vel_cols)

        df = pd.DataFrame(data, columns=columns, index=[1.0])
        df.index.name = 'Time'
        return df

    @patch('builtins.open')
    @patch('src.main_app.QFileDialog.getSaveFileName')
    def test_export_scenario_auto_mode_group1(self, mock_get_save_file_name, mock_open):
        """자동 모드, 그룹 1(C1-C4)에서 오프셋이 선택될 때의 동작을 테스트합니다."""
        mock_get_save_file_name.return_value = ('/fake/path/scenario.csv', None)
        mock_file_handle = MagicMock()
        mock_open.return_value.__enter__.return_value = mock_file_handle

        heights = [10.0, 20.0, 5.0, 30.0, 100.0, 110.0, 120.0, 130.0]
        velocities = [0.1, 0.2, 0.3, 100.0, 200.0, 300.0]
        self.app.result_data = self._create_test_result_data(heights, velocities)
        self.app.selected_point_info = {'time': 1.0, 'index': 0}

        self.app.offset_manual_checkbox.isChecked.return_value = False
        self.app.le_scene_name.text.return_value = "TestScene1"
        self.app.le_run_time.text.return_value = "0.25"
        self.app.le_time_step.text.return_value = "1e-6"

        self.app.export_analysis_scenario()

        mock_open.assert_called_once_with('/fake/path/scenario.csv', 'w')
        written_string = mock_file_handle.write.call_args[0][0]

        expected_lines = [
            "1,Left",
            "2,Right",
            "3,Bottom",
            "4,Top",
            "5,Rear",
            "6,Front",
            "cat,Corner_Drop_2nd,drop_name,TestScene1,variable_1,RightTopRear,value_1,5.000000,variable_2,LeftBottomRear,value_2,10.000000,variable_3,RightBottomRear,value_3,20.000000,variable_4,OFFSET,value_4,0.0,variable_5,ANG_VEL_X,value_5,0.100000,variable_6,ANG_VEL_Y,value_6,0.200000,variable_7,ANG_VEL_Z,value_7,0.300000,variable_8,TRA_VEL_X,value_8,100.000000,variable_9,TRA_VEL_Y,value_9,200.000000,variable_10,TRA_VEL_Z,value_10,300.000000,variable_11,POSI_FROM_CENT_X,value_11,0.0,variable_12,POSI_FROM_CENT_Y,value_12,0.0,variable_13,POSI_FROM_CENT_Z,value_13,0.0,run_time,0.25,tmin,1e-6"
        ]
        expected_string = "\n".join(expected_lines)

        self.assertEqual(written_string, expected_string)

    @patch('builtins.open')
    @patch('src.main_app.QFileDialog.getSaveFileName')
    def test_export_scenario_auto_mode_group2(self, mock_get_save_file_name, mock_open):
        """자동 모드, 그룹 2(C5-C8)에서 오프셋이 선택될 때의 동작을 테스트합니다."""
        mock_get_save_file_name.return_value = ('/fake/path/scenario2.csv', None)
        mock_file_handle = MagicMock()
        mock_open.return_value.__enter__.return_value = mock_file_handle

        # 테스트 데이터: C6(55.0)가 최소가 되도록 수정
        heights = [110.0, 120.0, 105.0, 130.0, 75.0, 55.0, 85.0, 65.0]
        velocities = [0.4, 0.5, 0.6, 400.0, 500.0, 600.0]
        self.app.result_data = self._create_test_result_data(heights, velocities)
        self.app.selected_point_info = {'time': 1.0, 'index': 0}

        self.app.offset_manual_checkbox.isChecked.return_value = False
        self.app.le_scene_name.text.return_value = "TestScene2"
        self.app.le_run_time.text.return_value = "0.3"
        self.app.le_time_step.text.return_value = "2e-7"

        self.app.export_analysis_scenario()

        written_string = mock_file_handle.write.call_args[0][0]

        expected_lines = [
            "1,Left",
            "2,Right",
            "3,Bottom",
            "4,Top",
            "5,Rear",
            "6,Front",
            "cat,Corner_Drop_2nd,drop_name,TestScene2,variable_1,RightBottomFront,value_1,55.000000,variable_2,LeftTopFront,value_2,65.000000,variable_3,LeftBottomFront,value_3,75.000000,variable_4,OFFSET,value_4,0.0,variable_5,ANG_VEL_X,value_5,0.400000,variable_6,ANG_VEL_Y,value_6,0.500000,variable_7,ANG_VEL_Z,value_7,0.600000,variable_8,TRA_VEL_X,value_8,400.000000,variable_9,TRA_VEL_Y,value_9,500.000000,variable_10,TRA_VEL_Z,value_10,600.000000,variable_11,POSI_FROM_CENT_X,value_11,0.0,variable_12,POSI_FROM_CENT_Y,value_12,0.0,variable_13,POSI_FROM_CENT_Z,value_13,0.0,run_time,0.3,tmin,2e-7"
        ]
        expected_string = "\n".join(expected_lines)

        self.assertEqual(written_string, expected_string)

    @patch('builtins.open')
    @patch('src.main_app.QFileDialog.getSaveFileName')
    def test_export_scenario_manual_mode(self, mock_get_save_file_name, mock_open):
        """수동 모드에서 사용자가 선택한 오프셋이 올바르게 처리되는지 테스트합니다."""
        mock_get_save_file_name.return_value = ('/fake/path/scenario3.csv', None)
        mock_file_handle = MagicMock()
        mock_open.return_value.__enter__.return_value = mock_file_handle

        heights = [10, 20, 30, 40, 50, 60, 70, 80]
        velocities = [0.7, 0.8, 0.9, 700, 800, 900]
        self.app.result_data = self._create_test_result_data(heights, velocities)
        self.app.selected_point_info = {'time': 1.0, 'index': 0}

        self.app.offset_manual_checkbox.isChecked.return_value = True
        self.app.offset_combos[0].currentText.return_value = 'C2'
        self.app.offset_combos[1].currentText.return_value = 'C5'
        self.app.offset_combos[2].currentText.return_value = 'C7'
        self.app.le_scene_name.text.return_value = "ManualTest"
        self.app.le_run_time.text.return_value = "0.99"
        self.app.le_time_step.text.return_value = "3e-8"

        self.app.export_analysis_scenario()

        written_string = mock_file_handle.write.call_args[0][0]

        expected_lines = [
            "1,Left",
            "2,Right",
            "3,Bottom",
            "4,Top",
            "5,Rear",
            "6,Front",
            "cat,Corner_Drop_2nd,drop_name,ManualTest,variable_1,RightBottomRear,value_1,20.000000,variable_2,LeftBottomFront,value_2,50.000000,variable_3,RightTopFront,value_3,70.000000,variable_4,OFFSET,value_4,0.0,variable_5,ANG_VEL_X,value_5,0.700000,variable_6,ANG_VEL_Y,value_6,0.800000,variable_7,ANG_VEL_Z,value_7,0.900000,variable_8,TRA_VEL_X,value_8,700.000000,variable_9,TRA_VEL_Y,value_9,800.000000,variable_10,TRA_VEL_Z,value_10,900.000000,variable_11,POSI_FROM_CENT_X,value_11,0.0,variable_12,POSI_FROM_CENT_Y,value_12,0.0,variable_13,POSI_FROM_CENT_Z,value_13,0.0,run_time,0.99,tmin,3e-8"
        ]
        expected_string = "\n".join(expected_lines)

        self.assertEqual(written_string, expected_string)

if __name__ == '__main__':
    unittest.main()