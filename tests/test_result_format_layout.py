import unittest

from src.config.data_columns import (
    DISPLAY_RESULT_COLUMNS,
    HeaderL1,
    HeaderL2,
    HeaderL3,
    get_result_column_display_path,
    get_result_metric_display_name,
)


def _l3_for(l1: str, l2: str) -> list[str]:
    return [l3 for a, b, l3 in DISPLAY_RESULT_COLUMNS if a == l1 and b == l2]


class TestResultFormatLayout(unittest.TestCase):
    def test_position_com_order_is_translation_then_rotation(self):
        expected = [
            HeaderL3.P_TX, HeaderL3.P_TY, HeaderL3.P_TZ,
            HeaderL3.P_RX, HeaderL3.P_RY, HeaderL3.P_RZ,
        ]
        self.assertEqual(_l3_for(HeaderL1.POS, HeaderL2.COM), expected)

    def test_velocity_com_order_is_boxlocal_then_global(self):
        expected = [
            HeaderL3.V_TX_ANA, HeaderL3.V_TY_ANA, HeaderL3.V_TZ_ANA, HeaderL3.V_TNORM_ANA,
            HeaderL3.V_RX_ANA, HeaderL3.V_RY_ANA, HeaderL3.V_RZ_ANA, HeaderL3.V_RNORM_ANA,
            HeaderL3.V_TX, HeaderL3.V_TY, HeaderL3.V_TZ, HeaderL3.V_TNORM,
            HeaderL3.V_RX, HeaderL3.V_RY, HeaderL3.V_RZ, HeaderL3.V_RNORM,
        ]
        self.assertEqual(_l3_for(HeaderL1.VEL, HeaderL2.COM), expected)

    def test_acceleration_com_order_is_boxlocal_then_global(self):
        expected = [
            HeaderL3.A_TX_ANA, HeaderL3.A_TY_ANA, HeaderL3.A_TZ_ANA, HeaderL3.A_TNORM_ANA,
            HeaderL3.A_RX_ANA, HeaderL3.A_RY_ANA, HeaderL3.A_RZ_ANA, HeaderL3.A_RNORM_ANA,
            HeaderL3.A_TX, HeaderL3.A_TY, HeaderL3.A_TZ, HeaderL3.A_TNORM,
            HeaderL3.A_RX, HeaderL3.A_RY, HeaderL3.A_RZ, HeaderL3.A_RNORM,
        ]
        self.assertEqual(_l3_for(HeaderL1.ACC, HeaderL2.COM), expected)

    def test_corner_velocity_includes_norm_for_all_corners(self):
        for i in range(1, 9):
            l2 = f"C{i}"
            cols = set(_l3_for(HeaderL1.VEL, l2))
            self.assertIn(HeaderL3.V_TX, cols)
            self.assertIn(HeaderL3.V_TY, cols)
            self.assertIn(HeaderL3.V_TZ, cols)
            self.assertIn(HeaderL3.V_TNORM, cols)

    def test_result_metric_display_names_follow_schema_meaning(self):
        self.assertEqual(
            get_result_metric_display_name(HeaderL1.POS, HeaderL2.COM, HeaderL3.P_TX),
            "Position X",
        )
        self.assertEqual(
            get_result_metric_display_name(HeaderL1.POS, HeaderL2.COM, HeaderL3.P_RX),
            "Rotation X",
        )
        self.assertEqual(
            get_result_metric_display_name(HeaderL1.VEL, HeaderL2.COM, HeaderL3.V_TX_ANA),
            "Velocity X (Box Local Frame)",
        )
        self.assertEqual(
            get_result_metric_display_name(HeaderL1.VEL, HeaderL2.COM, HeaderL3.V_RNORM),
            "Angular Velocity Norm (Global Frame)",
        )
        self.assertEqual(
            get_result_metric_display_name(HeaderL1.ACC, HeaderL2.COM, HeaderL3.A_TNORM),
            "Acceleration Norm (Global Frame)",
        )
        self.assertEqual(
            get_result_metric_display_name(HeaderL1.ANALYSIS, "C1", HeaderL3.REL_H),
            "Relative Height",
        )

    def test_result_column_display_path_uses_user_facing_labels(self):
        self.assertEqual(
            get_result_column_display_path((HeaderL1.VEL, HeaderL2.COM, HeaderL3.V_TX_ANA)),
            "Velocity / CoM / Velocity X (Box Local Frame)",
        )
        self.assertEqual(
            get_result_column_display_path((HeaderL1.ACC, "C3", HeaderL3.A_TNORM)),
            "Acceleration / C3 / Acceleration Norm (Global Frame)",
        )


if __name__ == "__main__":
    unittest.main()
