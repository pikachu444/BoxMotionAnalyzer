import os
import unittest

import pandas as pd

from src.config import config_visualization as config
from src.config.data_columns import HeaderL1, HeaderL2, HeaderL3
from src.visualization.data_handler import DataHandler


class TestVisualizationDataHandler(unittest.TestCase):
    def setUp(self):
        self.test_csv_path = "data/test_visualization_result.csv"
        os.makedirs("data", exist_ok=True)

    def tearDown(self):
        if os.path.exists(self.test_csv_path):
            os.remove(self.test_csv_path)

    def test_loads_entity_groups_and_supported_metrics_from_exported_result(self):
        columns = pd.MultiIndex.from_tuples([
            (HeaderL1.INFO, HeaderL2.FRAME, HeaderL3.NUM),
            (HeaderL1.INFO, HeaderL2.TIME, HeaderL3.TIME),
            (HeaderL1.POS, HeaderL2.COM, HeaderL3.P_TX),
            (HeaderL1.POS, HeaderL2.COM, HeaderL3.P_TY),
            (HeaderL1.POS, HeaderL2.COM, HeaderL3.P_TZ),
            (HeaderL1.VEL, HeaderL2.COM, HeaderL3.V_TX),
            (HeaderL1.VEL, HeaderL2.COM, HeaderL3.V_TY),
            (HeaderL1.VEL, HeaderL2.COM, HeaderL3.V_TZ),
            (HeaderL1.VEL, HeaderL2.COM, HeaderL3.V_TNORM),
            (HeaderL1.VEL, HeaderL2.COM, HeaderL3.V_TX_ANA),
            (HeaderL1.VEL, HeaderL2.COM, HeaderL3.V_TY_ANA),
            (HeaderL1.VEL, HeaderL2.COM, HeaderL3.V_TZ_ANA),
            (HeaderL1.POS, "C1", HeaderL3.P_TX),
            (HeaderL1.POS, "C1", HeaderL3.P_TY),
            (HeaderL1.POS, "C1", HeaderL3.P_TZ),
            (HeaderL1.VEL, "C1", HeaderL3.V_TX),
            (HeaderL1.VEL, "C1", HeaderL3.V_TY),
            (HeaderL1.VEL, "C1", HeaderL3.V_TZ),
            (HeaderL1.VEL, "C1", HeaderL3.V_TNORM),
            (HeaderL1.POS, "M1", HeaderL3.P_TX),
            (HeaderL1.POS, "M1", HeaderL3.P_TY),
            (HeaderL1.POS, "M1", HeaderL3.P_TZ),
        ])
        data = [
            [10, 0.0, 1.0, 2.0, 3.0, 0.4, 0.5, 0.6, 0.9, 0.1, 0.2, 0.3, 4.0, 5.0, 6.0, 0.7, 0.8, 0.9, 1.4, 7.0, 8.0, 9.0],
            [11, 0.1, 1.1, 2.1, 3.1, 0.4, 0.5, 0.6, 0.9, 0.1, 0.2, 0.3, 4.1, 5.1, 6.1, 0.7, 0.8, 0.9, 1.4, 7.1, 8.1, 9.1],
        ]
        pd.DataFrame(data, columns=columns).to_csv(self.test_csv_path, index=False)

        handler = DataHandler()
        success = handler.load_analysis_result(self.test_csv_path)

        self.assertTrue(success)
        self.assertEqual(handler.get_entities_by_type()[config.ENTITY_TYPE_COM], [config.ENTITY_ID_COM])
        self.assertEqual(handler.get_entities_by_type()[config.ENTITY_TYPE_CORNER], ["C1"])
        self.assertEqual(handler.get_entities_by_type()[config.ENTITY_TYPE_MARKER], ["M1"])

        com_df = handler.get_entity_timeseries(config.ENTITY_ID_COM)
        marker_df = handler.get_entity_timeseries("M1")
        self.assertIn(config.DF_VEL_BOX_LOCAL_X, com_df.columns)
        self.assertTrue(marker_df[config.DF_VEL_X].isna().all())
        self.assertTrue(marker_df[config.DF_SPEED_GLOBAL].isna().all())


if __name__ == "__main__":
    unittest.main()
