import pandas as pd

from src.config.data_columns import HeaderL1, HeaderL2, HeaderL3, VelocityCols, DISPLAY_RESULT_COLUMNS
from src.utils.header_converter import convert_to_multi_header


def test_convert_to_multi_header_maps_acceleration_columns():
    df = pd.DataFrame(
        {
            VelocityCols.T_AX: [1.0],
            VelocityCols.T_A_NORM: [1.0],
            VelocityCols.R_AX: [0.5],
            VelocityCols.R_A_NORM: [0.5],
        },
        index=[0.0],
    )
    df.index.name = "Time"

    converted = convert_to_multi_header(df)

    assert (HeaderL1.ACC, HeaderL2.TRN, HeaderL3.AX) in converted.columns
    assert (HeaderL1.ACC, HeaderL2.TRN, HeaderL3.NORM_A) in converted.columns
    assert (HeaderL1.ACC, HeaderL2.ROT, HeaderL3.AX) in converted.columns
    assert (HeaderL1.ACC, HeaderL2.ROT, HeaderL3.NORM_A) in converted.columns


def test_display_result_columns_includes_acceleration_items():
    assert (HeaderL1.ACC, HeaderL2.TRN, HeaderL3.AX) in DISPLAY_RESULT_COLUMNS
    assert (HeaderL1.ACC, HeaderL2.TRN, HeaderL3.NORM_A) in DISPLAY_RESULT_COLUMNS
    assert (HeaderL1.ACC, HeaderL2.ROT, HeaderL3.AX) in DISPLAY_RESULT_COLUMNS
    assert (HeaderL1.ACC, HeaderL2.ROT, HeaderL3.NORM_A) in DISPLAY_RESULT_COLUMNS


def test_convert_to_multi_header_distinguishes_ana_suffix_columns():
    df = pd.DataFrame(
        {
            VelocityCols.T_VX: [1.0],
            f"{VelocityCols.T_VX}_Ana": [2.0],
        },
        index=[0.0],
    )
    df.index.name = "Time"

    converted = convert_to_multi_header(df)

    assert (HeaderL1.VEL, HeaderL2.TRN, HeaderL3.VX) in converted.columns
    assert (HeaderL1.VEL, HeaderL2.TRN, HeaderL3.VX_ANA) in converted.columns
