import os
import tempfile
import unittest
from unittest.mock import patch

import pandas as pd

from src.analysis.pipeline.artifact_io import result_file_filter
from src.analysis.pipeline.data_loader import DataLoader
from src.config import config_visualization as config
from src.config.data_columns import HeaderL1, HeaderL2, HeaderL3
from src.visualization.data_handler import DataHandler

try:
    from PySide6.QtWidgets import QApplication
    from src.visualization.main_window import MainWindow
    HAS_QT = True
except ModuleNotFoundError:
    QApplication = None
    MainWindow = None
    HAS_QT = False


class TestVisualizationProcSupport(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if HAS_QT:
            cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.proc_path = os.path.join(self.temp_dir.name, "sample_result.proc")
        self.csv_path = os.path.join(self.temp_dir.name, "sample_result.csv")

        columns = pd.MultiIndex.from_tuples([
            (HeaderL1.INFO, HeaderL2.FRAME, HeaderL3.NUM),
            (HeaderL1.INFO, HeaderL2.TIME, HeaderL3.TIME),
            (HeaderL1.POS, HeaderL2.COM, HeaderL3.P_TX),
            (HeaderL1.POS, HeaderL2.COM, HeaderL3.P_TY),
            (HeaderL1.POS, HeaderL2.COM, HeaderL3.P_TZ),
        ])
        data = [
            [10, 0.0, 1.0, 2.0, 3.0],
            [11, 0.1, 1.1, 2.1, 3.1],
        ]
        pd.DataFrame(data, columns=columns).to_csv(self.proc_path, index=False)
        pd.DataFrame(data, columns=columns).to_csv(self.csv_path, index=False)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_data_handler_loads_proc_result_file(self):
        handler = DataHandler()

        success = handler.load_analysis_result(self.proc_path)

        self.assertTrue(success)
        self.assertEqual(handler.get_entities_by_type()[config.ENTITY_TYPE_COM], [config.ENTITY_ID_COM])

    def test_result_loaders_can_still_read_legacy_csv_paths_programmatically(self):
        handler = DataHandler()
        loader = DataLoader()

        self.assertTrue(handler.load_analysis_result(self.csv_path))
        result_df = loader.load_result_csv(self.csv_path)
        self.assertFalse(result_df.empty)

    @unittest.skipUnless(HAS_QT, "PySide6 is required for visualization window tests.")
    def test_main_window_uses_shared_result_filter(self):
        window = MainWindow()
        try:
            with patch(
                "PySide6.QtWidgets.QFileDialog.getOpenFileName",
                return_value=("", ""),
            ) as mock_dialog:
                window.open_result_file()

            mock_dialog.assert_called_once_with(window, "Open Result File", "", result_file_filter())
        finally:
            window.close()


if __name__ == "__main__":
    unittest.main()
