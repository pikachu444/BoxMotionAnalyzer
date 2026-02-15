from src.config.data_columns import DISPLAY_RESULT_COLUMNS, HeaderL1, HeaderL2, HeaderL3


def _l3_for(l1: str, l2: str) -> list[str]:
    return [l3 for a, b, l3 in DISPLAY_RESULT_COLUMNS if a == l1 and b == l2]


def test_position_com_order_is_translation_then_rotation():
    expected = [
        HeaderL3.P_TX, HeaderL3.P_TY, HeaderL3.P_TZ,
        HeaderL3.P_RX, HeaderL3.P_RY, HeaderL3.P_RZ,
    ]
    assert _l3_for(HeaderL1.POS, HeaderL2.COM) == expected


def test_velocity_com_order_is_boxlocal_then_global():
    expected = [
        HeaderL3.V_TX_ANA, HeaderL3.V_TY_ANA, HeaderL3.V_TZ_ANA, HeaderL3.V_TNORM_ANA,
        HeaderL3.V_RX_ANA, HeaderL3.V_RY_ANA, HeaderL3.V_RZ_ANA, HeaderL3.V_RNORM_ANA,
        HeaderL3.V_TX, HeaderL3.V_TY, HeaderL3.V_TZ, HeaderL3.V_TNORM,
        HeaderL3.V_RX, HeaderL3.V_RY, HeaderL3.V_RZ, HeaderL3.V_RNORM,
    ]
    assert _l3_for(HeaderL1.VEL, HeaderL2.COM) == expected


def test_acceleration_com_order_is_boxlocal_then_global():
    expected = [
        HeaderL3.A_TX_ANA, HeaderL3.A_TY_ANA, HeaderL3.A_TZ_ANA, HeaderL3.A_TNORM_ANA,
        HeaderL3.A_RX_ANA, HeaderL3.A_RY_ANA, HeaderL3.A_RZ_ANA, HeaderL3.A_RNORM_ANA,
        HeaderL3.A_TX, HeaderL3.A_TY, HeaderL3.A_TZ, HeaderL3.A_TNORM,
        HeaderL3.A_RX, HeaderL3.A_RY, HeaderL3.A_RZ, HeaderL3.A_RNORM,
    ]
    assert _l3_for(HeaderL1.ACC, HeaderL2.COM) == expected


def test_corner_velocity_includes_norm_for_all_corners():
    for i in range(1, 9):
        l2 = f"C{i}"
        cols = set(_l3_for(HeaderL1.VEL, l2))
        assert HeaderL3.V_TX in cols
        assert HeaderL3.V_TY in cols
        assert HeaderL3.V_TZ in cols
        assert HeaderL3.V_TNORM in cols
