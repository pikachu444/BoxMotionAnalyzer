from src.config.data_columns import HeaderL1, HeaderL2, HeaderL3
from src.utils.header_converter import parse_column_name


def test_acceleration_columns_map_to_acc_header_l1():
    assert parse_column_name("CoM_Ax") == (HeaderL1.ACC, HeaderL2.COM, HeaderL3.AX)
    assert parse_column_name("CoM_Ay") == (HeaderL1.ACC, HeaderL2.COM, HeaderL3.AY)
    assert parse_column_name("CoM_Az") == (HeaderL1.ACC, HeaderL2.COM, HeaderL3.AZ)
    assert parse_column_name("CoM_A_Norm") == (HeaderL1.ACC, HeaderL2.COM, HeaderL3.NORM_A)

    assert parse_column_name("AngAcc_Ax") == (HeaderL1.ACC, HeaderL2.ANG, HeaderL3.AX)
    assert parse_column_name("AngAcc_Ay") == (HeaderL1.ACC, HeaderL2.ANG, HeaderL3.AY)
    assert parse_column_name("AngAcc_Az") == (HeaderL1.ACC, HeaderL2.ANG, HeaderL3.AZ)
    assert parse_column_name("AngAcc_A_Norm") == (HeaderL1.ACC, HeaderL2.ANG, HeaderL3.NORM_A)


def test_acceleration_analysis_columns_map_to_acc_header_l1():
    assert parse_column_name("CoM_Ax_Ana") == (HeaderL1.ACC, HeaderL2.COM, HeaderL3.AX_ANA)
    assert parse_column_name("CoM_A_Norm_Ana") == (HeaderL1.ACC, HeaderL2.COM, HeaderL3.NORM_A_ANA)
    assert parse_column_name("AngAcc_Ax_Ana") == (HeaderL1.ACC, HeaderL2.ANG, HeaderL3.AX_ANA)
    assert parse_column_name("AngAcc_A_Norm_Ana") == (HeaderL1.ACC, HeaderL2.ANG, HeaderL3.NORM_A_ANA)


def test_velocity_columns_remain_velocity_header_l1():
    assert parse_column_name("CoM_Vx") == (HeaderL1.VEL, HeaderL2.COM, HeaderL3.VX)
    assert parse_column_name("AngVel_Wx") == (HeaderL1.VEL, HeaderL2.COM, HeaderL3.WX)
