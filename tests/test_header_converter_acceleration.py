import pandas as pd

from src.config.data_columns import (
    AnalysisCols,
    DISPLAY_RESULT_COLUMNS,
    DropPostureCols,
    DropPostureSummaryCols,
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


def test_convert_to_multi_header_maps_drop_posture_metrics_and_summary():
    df = pd.DataFrame(
        {
            DropPostureCols.BETA_DEG: [10.0],
            DropPostureCols.CMIN_INDEX: [1],
            DropPostureSummaryCols.BETA_AT_T1_MINUS_DEG: [10.0],
            DropPostureSummaryCols.REFERENCE_FACE: ["BOTTOM"],
            DropPostureSummaryCols.CONTACT_STATE: ["ImpactEvent"],
            DropPostureSummaryCols.CONTACT_CONFIDENCE: [0.75],
            DropPostureSummaryCols.CONTACT_DETECTION_METHOD: ["threshold+motion"],
            DropPostureSummaryCols.IMPACT_DETECTED: [True],
            DropPostureSummaryCols.SUSTAINED_CONTACT_DETECTED: [False],
            DropPostureSummaryCols.IMPACT_SEQUENCE: ["{C1,C2} -> C5"],
            DropPostureSummaryCols.IMPACT_EVENT_COUNT: [2],
            DropPostureSummaryCols.FIRST_IMPACT_TIME_SEC: [0.2],
            DropPostureSummaryCols.FIRST_IMPACT_CONTACT: ["{C1,C2}"],
        },
        index=[0.0],
    )
    df.index.name = "Time"
    converted = convert_to_multi_header(df)

    assert (HeaderL1.ANALYSIS, HeaderL2.DROP_POSTURE, HeaderL3.DROP_BETA_DEG) in converted.columns
    assert (HeaderL1.ANALYSIS, HeaderL2.DROP_POSTURE, HeaderL3.DROP_CMIN_INDEX) in converted.columns
    assert (
        HeaderL1.ANALYSIS,
        HeaderL2.DROP_POSTURE_SUMMARY,
        HeaderL3.DROP_BETA_AT_T1_MINUS_DEG,
    ) in converted.columns
    assert (
        HeaderL1.ANALYSIS,
        HeaderL2.DROP_POSTURE_SUMMARY,
        HeaderL3.DROP_REFERENCE_FACE,
    ) in converted.columns
    assert (
        HeaderL1.ANALYSIS,
        HeaderL2.DROP_POSTURE_SUMMARY,
        HeaderL3.DROP_CONTACT_STATE,
    ) in converted.columns
    assert (
        HeaderL1.ANALYSIS,
        HeaderL2.DROP_POSTURE_SUMMARY,
        HeaderL3.DROP_CONTACT_CONFIDENCE,
    ) in converted.columns
    assert (
        HeaderL1.ANALYSIS,
        HeaderL2.DROP_POSTURE_SUMMARY,
        HeaderL3.DROP_CONTACT_DETECTION_METHOD,
    ) in converted.columns
    assert (
        HeaderL1.ANALYSIS,
        HeaderL2.DROP_POSTURE_SUMMARY,
        HeaderL3.DROP_IMPACT_DETECTED,
    ) in converted.columns
    assert (
        HeaderL1.ANALYSIS,
        HeaderL2.DROP_POSTURE_SUMMARY,
        HeaderL3.DROP_SUSTAINED_CONTACT_DETECTED,
    ) in converted.columns
    assert (
        HeaderL1.ANALYSIS,
        HeaderL2.DROP_POSTURE_SUMMARY,
        HeaderL3.DROP_IMPACT_SEQUENCE,
    ) in converted.columns
    assert (
        HeaderL1.ANALYSIS,
        HeaderL2.DROP_POSTURE_SUMMARY,
        HeaderL3.DROP_IMPACT_EVENT_COUNT,
    ) in converted.columns
    assert (
        HeaderL1.ANALYSIS,
        HeaderL2.DROP_POSTURE_SUMMARY,
        HeaderL3.DROP_FIRST_IMPACT_TIME_SEC,
    ) in converted.columns
    assert (
        HeaderL1.ANALYSIS,
        HeaderL2.DROP_POSTURE_SUMMARY,
        HeaderL3.DROP_FIRST_IMPACT_CONTACT,
    ) in converted.columns


def test_display_result_columns_include_new_com_velocity_acceleration_items():
    assert (HeaderL1.VEL, HeaderL2.COM, HeaderL3.V_TX_ANA) in DISPLAY_RESULT_COLUMNS
    assert (HeaderL1.VEL, HeaderL2.COM, HeaderL3.V_TX) in DISPLAY_RESULT_COLUMNS
    assert (HeaderL1.ACC, HeaderL2.COM, HeaderL3.A_TX_ANA) in DISPLAY_RESULT_COLUMNS
    assert (HeaderL1.ACC, HeaderL2.COM, HeaderL3.A_TX) in DISPLAY_RESULT_COLUMNS
    assert (HeaderL1.ACC, HeaderL2.COM, HeaderL3.A_TNORM_ANA) in DISPLAY_RESULT_COLUMNS
    assert (HeaderL1.ACC, HeaderL2.COM, HeaderL3.A_TNORM) in DISPLAY_RESULT_COLUMNS
    assert (HeaderL1.ANALYSIS, HeaderL2.DROP_POSTURE, HeaderL3.DROP_BETA_DEG) in DISPLAY_RESULT_COLUMNS
    assert (HeaderL1.ANALYSIS, HeaderL2.DROP_POSTURE, HeaderL3.DROP_DELTA_H_MM) in DISPLAY_RESULT_COLUMNS
