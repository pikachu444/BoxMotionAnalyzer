import pandas as pd

from src.config.data_columns import (
    AnalysisCols,
    DISPLAY_RESULT_COLUMNS,
    HeaderL1,
    HeaderL2,
    HeaderL3,
    PoseCols,
    VelocityCols,
)
from src.utils.header_converter import convert_to_multi_header


def test_convert_to_multi_header_maps_global_and_local_acceleration_columns():
    df = pd.DataFrame(
        {
            VelocityCols.T_AX: [1.0],
            VelocityCols.T_A_NORM: [1.1],
            VelocityCols.R_AX: [2.0],
            VelocityCols.R_A_NORM: [2.2],
            AnalysisCols.T_AX_ANA: [3.0],
            AnalysisCols.T_A_NORM_ANA: [3.3],
            AnalysisCols.R_AX_ANA: [4.0],
            AnalysisCols.R_A_NORM_ANA: [4.4],
        },
        index=[0.0],
    )
    df.index.name = "Time"
    converted = convert_to_multi_header(df)

    assert (HeaderL1.ACC, HeaderL2.COM, HeaderL3.A_TX) in converted.columns
    assert (HeaderL1.ACC, HeaderL2.COM, HeaderL3.A_TNORM) in converted.columns
    assert (HeaderL1.ACC, HeaderL2.COM, HeaderL3.A_RX) in converted.columns
    assert (HeaderL1.ACC, HeaderL2.COM, HeaderL3.A_RNORM) in converted.columns
    assert (HeaderL1.ACC, HeaderL2.COM, HeaderL3.A_TX_ANA) in converted.columns
    assert (HeaderL1.ACC, HeaderL2.COM, HeaderL3.A_TNORM_ANA) in converted.columns
    assert (HeaderL1.ACC, HeaderL2.COM, HeaderL3.A_RX_ANA) in converted.columns
    assert (HeaderL1.ACC, HeaderL2.COM, HeaderL3.A_RNORM_ANA) in converted.columns


def test_convert_to_multi_header_maps_com_position_from_new_pose_columns():
    df = pd.DataFrame(
        {
            PoseCols.POS_X: [1.0],
            PoseCols.POS_Y: [2.0],
            PoseCols.POS_Z: [3.0],
            PoseCols.ROT_X: [0.1],
            PoseCols.ROT_Y: [0.2],
            PoseCols.ROT_Z: [0.3],
        },
        index=[0.0],
    )
    df.index.name = "Time"
    converted = convert_to_multi_header(df)

    assert (HeaderL1.POS, HeaderL2.COM, HeaderL3.P_TX) in converted.columns
    assert (HeaderL1.POS, HeaderL2.COM, HeaderL3.P_TY) in converted.columns
    assert (HeaderL1.POS, HeaderL2.COM, HeaderL3.P_TZ) in converted.columns
    assert (HeaderL1.POS, HeaderL2.COM, HeaderL3.P_RX) in converted.columns
    assert (HeaderL1.POS, HeaderL2.COM, HeaderL3.P_RY) in converted.columns
    assert (HeaderL1.POS, HeaderL2.COM, HeaderL3.P_RZ) in converted.columns


def test_convert_to_multi_header_maps_corner_velocity_norm():
    df = pd.DataFrame({"C1_Global_V_T_Norm": [12.3]}, index=[0.0])
    df.index.name = "Time"
    converted = convert_to_multi_header(df)
    assert (HeaderL1.VEL, "C1", HeaderL3.V_TNORM) in converted.columns


def test_display_result_columns_include_new_com_velocity_acceleration_items():
    assert (HeaderL1.VEL, HeaderL2.COM, HeaderL3.V_TX_ANA) in DISPLAY_RESULT_COLUMNS
    assert (HeaderL1.VEL, HeaderL2.COM, HeaderL3.V_TX) in DISPLAY_RESULT_COLUMNS
    assert (HeaderL1.ACC, HeaderL2.COM, HeaderL3.A_TX_ANA) in DISPLAY_RESULT_COLUMNS
    assert (HeaderL1.ACC, HeaderL2.COM, HeaderL3.A_TX) in DISPLAY_RESULT_COLUMNS
    assert (HeaderL1.ACC, HeaderL2.COM, HeaderL3.A_TNORM_ANA) in DISPLAY_RESULT_COLUMNS
    assert (HeaderL1.ACC, HeaderL2.COM, HeaderL3.A_TNORM) in DISPLAY_RESULT_COLUMNS
