from src.config.data_columns import HeaderL1, HeaderL2, HeaderL3
from src.utils.header_converter import parse_column_name


def test_parse_column_name_for_tr_velocity_and_acceleration_columns():
    assert parse_column_name("T_Vx") == (HeaderL1.VEL, HeaderL2.BOX_T, HeaderL3.VX)
    assert parse_column_name("T_Ay") == (HeaderL1.VEL, HeaderL2.BOX_T, HeaderL3.AY)
    assert parse_column_name("R_Vz") == (HeaderL1.VEL, HeaderL2.BOX_R, HeaderL3.VZ)
    assert parse_column_name("R_Ax") == (HeaderL1.VEL, HeaderL2.BOX_R, HeaderL3.AX)


def test_parse_column_name_for_tr_norm_columns():
    assert parse_column_name("T_V_Norm") == (HeaderL1.VEL, HeaderL2.BOX_T, HeaderL3.NORM_V)
    assert parse_column_name("T_A_Norm") == (HeaderL1.VEL, HeaderL2.BOX_T, HeaderL3.NORM_A)
    assert parse_column_name("R_V_Norm") == (HeaderL1.VEL, HeaderL2.BOX_R, HeaderL3.NORM_V)
    assert parse_column_name("R_A_Norm") == (HeaderL1.VEL, HeaderL2.BOX_R, HeaderL3.NORM_A)
