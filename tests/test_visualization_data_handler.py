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
            (HeaderL1.VEL, HeaderL2.COM, HeaderL3.V_TNORM_ANA),
            (HeaderL1.ACC, HeaderL2.COM, HeaderL3.A_TX),
            (HeaderL1.ACC, HeaderL2.COM, HeaderL3.A_TY),
            (HeaderL1.ACC, HeaderL2.COM, HeaderL3.A_TZ),
            (HeaderL1.ACC, HeaderL2.COM, HeaderL3.A_TNORM),
            (HeaderL1.ACC, HeaderL2.COM, HeaderL3.A_TX_ANA),
            (HeaderL1.ACC, HeaderL2.COM, HeaderL3.A_TY_ANA),
            (HeaderL1.ACC, HeaderL2.COM, HeaderL3.A_TZ_ANA),
            (HeaderL1.ACC, HeaderL2.COM, HeaderL3.A_TNORM_ANA),
            (HeaderL1.POS, "C1", HeaderL3.P_TX),
            (HeaderL1.POS, "C1", HeaderL3.P_TY),
            (HeaderL1.POS, "C1", HeaderL3.P_TZ),
            (HeaderL1.VEL, "C1", HeaderL3.V_TX),
            (HeaderL1.VEL, "C1", HeaderL3.V_TY),
            (HeaderL1.VEL, "C1", HeaderL3.V_TZ),
            (HeaderL1.VEL, "C1", HeaderL3.V_TNORM),
            (HeaderL1.ACC, "C1", HeaderL3.A_TX),
            (HeaderL1.ACC, "C1", HeaderL3.A_TY),
            (HeaderL1.ACC, "C1", HeaderL3.A_TZ),
            (HeaderL1.ACC, "C1", HeaderL3.A_TNORM),
            (HeaderL1.POS, "M1", HeaderL3.P_TX),
            (HeaderL1.POS, "M1", HeaderL3.P_TY),
            (HeaderL1.POS, "M1", HeaderL3.P_TZ),
        ])
        data = [
            [10, 0.0, 1.0, 2.0, 3.0, 0.4, 0.5, 0.6, 0.9, 0.1, 0.2, 0.3, 0.4, 1.4, 1.5, 1.6, 2.6, 0.7, 0.8, 0.9, 1.0, 4.0, 5.0, 6.0, 0.7, 0.8, 0.9, 1.4, 2.0, 2.1, 2.2, 3.6, 7.0, 8.0, 9.0],
            [11, 0.1, 1.1, 2.1, 3.1, 0.4, 0.5, 0.6, 0.9, 0.1, 0.2, 0.3, 0.4, 1.4, 1.5, 1.6, 2.6, 0.7, 0.8, 0.9, 1.0, 4.1, 5.1, 6.1, 0.7, 0.8, 0.9, 1.4, 2.0, 2.1, 2.2, 3.6, 7.1, 8.1, 9.1],
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
        self.assertIn(config.DF_ACC_GLOBAL_X, com_df.columns)
        self.assertIn(config.DF_ACC_BOX_LOCAL_X, com_df.columns)
        self.assertEqual(com_df[config.DF_VEL_GLOBAL_NORM].iloc[0], 0.9)
        self.assertEqual(com_df[config.DF_ACC_GLOBAL_NORM].iloc[0], 2.6)
        self.assertTrue(marker_df[config.DF_VEL_X].isna().all())
        self.assertTrue(marker_df[config.DF_VEL_GLOBAL_NORM].isna().all())
        self.assertTrue(marker_df[config.DF_ACC_GLOBAL_NORM].isna().all())

    def test_visualization_metric_constants_follow_export_schema_keys(self):
        expected_metric_keys = {
            config.DF_POS_GLOBAL_X: HeaderL3.P_TX,
            config.DF_POS_GLOBAL_Y: HeaderL3.P_TY,
            config.DF_POS_GLOBAL_Z: HeaderL3.P_TZ,
            config.DF_VEL_GLOBAL_X: HeaderL3.V_TX,
            config.DF_VEL_GLOBAL_Y: HeaderL3.V_TY,
            config.DF_VEL_GLOBAL_Z: HeaderL3.V_TZ,
            config.DF_VEL_GLOBAL_NORM: HeaderL3.V_TNORM,
            config.DF_VEL_BOX_LOCAL_X: HeaderL3.V_TX_ANA,
            config.DF_VEL_BOX_LOCAL_Y: HeaderL3.V_TY_ANA,
            config.DF_VEL_BOX_LOCAL_Z: HeaderL3.V_TZ_ANA,
            config.DF_VEL_BOX_LOCAL_NORM: HeaderL3.V_TNORM_ANA,
            config.DF_ACC_GLOBAL_X: HeaderL3.A_TX,
            config.DF_ACC_GLOBAL_Y: HeaderL3.A_TY,
            config.DF_ACC_GLOBAL_Z: HeaderL3.A_TZ,
            config.DF_ACC_GLOBAL_NORM: HeaderL3.A_TNORM,
            config.DF_ACC_BOX_LOCAL_X: HeaderL3.A_TX_ANA,
            config.DF_ACC_BOX_LOCAL_Y: HeaderL3.A_TY_ANA,
            config.DF_ACC_BOX_LOCAL_Z: HeaderL3.A_TZ_ANA,
            config.DF_ACC_BOX_LOCAL_NORM: HeaderL3.A_TNORM_ANA,
        }

        for metric_key, export_key in expected_metric_keys.items():
            self.assertEqual(metric_key, export_key)

        plot_metric_keys = set(config.PLOT_DATA_DISPLAY_MAP.values())
        for metric_key in expected_metric_keys:
            self.assertIn(metric_key, plot_metric_keys)

    def test_visualization_help_text_covers_default_and_entity_specific_guidance(self):
        default_text = config.get_inspector_help_text(None)
        self.assertIn("mixed-type selection", default_text)
        self.assertIn("one entity type", default_text)

        self.assertIn("Box Local Frame", config.get_inspector_help_text(config.ENTITY_TYPE_COM))
        self.assertIn("Global Frame", config.get_inspector_help_text(config.ENTITY_TYPE_CORNER))
        self.assertIn("position", config.get_inspector_help_text(config.ENTITY_TYPE_MARKER).lower())


if __name__ == "__main__":
    unittest.main()
