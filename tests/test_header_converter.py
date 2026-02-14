import unittest

from src.config.data_columns import (
    DISPLAY_RESULT_COLUMNS,
    HeaderL1,
    HeaderL2,
    HeaderL3,
)
from src.utils.header_converter import parse_column_name


class TestHeaderConverter(unittest.TestCase):
    def test_same_quantity_ana_and_non_ana_map_to_different_headers(self):
        self.assertEqual(
            parse_column_name("CoM_Vx"),
            (HeaderL1.VEL, HeaderL2.COM, HeaderL3.VX),
        )
        self.assertEqual(
            parse_column_name("CoM_Vx_Ana"),
            (HeaderL1.VEL, HeaderL2.COM, HeaderL3.VX_ANA),
        )

    def test_pose_t_r_ana_pattern_uses_same_rule(self):
        self.assertEqual(
            parse_column_name("Box_Tx"),
            (HeaderL1.POSE, HeaderL2.BOX_T, HeaderL3.TX),
        )
        self.assertEqual(
            parse_column_name("Box_Tx_Ana"),
            (HeaderL1.POSE, HeaderL2.BOX_T, HeaderL3.TX_ANA),
        )

        self.assertEqual(
            parse_column_name("Box_Rz"),
            (HeaderL1.POSE, HeaderL2.BOX_R, HeaderL3.RZ),
        )
        self.assertEqual(
            parse_column_name("Box_Rz_Ana"),
            (HeaderL1.POSE, HeaderL2.BOX_R, HeaderL3.RZ_ANA),
        )

    def test_display_result_columns_separate_ana_and_non_ana_targets(self):
        self.assertIn((HeaderL1.VEL, HeaderL2.COM, HeaderL3.VX), DISPLAY_RESULT_COLUMNS)
        self.assertIn((HeaderL1.VEL, HeaderL2.COM, HeaderL3.VX_ANA), DISPLAY_RESULT_COLUMNS)
        self.assertIn((HeaderL1.POSE, HeaderL2.BOX_T, HeaderL3.TX), DISPLAY_RESULT_COLUMNS)
        self.assertIn((HeaderL1.POSE, HeaderL2.BOX_T, HeaderL3.TX_ANA), DISPLAY_RESULT_COLUMNS)

        self.assertEqual(
            len(DISPLAY_RESULT_COLUMNS),
            len(set(DISPLAY_RESULT_COLUMNS)),
            "DISPLAY_RESULT_COLUMNS contains duplicated entries.",
        )


if __name__ == "__main__":
    unittest.main()
