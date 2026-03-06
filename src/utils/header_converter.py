import pandas as pd
import re
from src.config.data_columns import (
    HeaderL1,
    HeaderL2,
    HeaderL3,
    RigidBodyCols,
    VelocityCols,
    PoseCols,
    AnalysisCols,
    TimeCols,
    TimelineMetaCols,
)


def get_conversion_rules() -> list:
    reserved_prefixes = [
        PoseCols.T_PREFIX,
        PoseCols.R_PREFIX,
        VelocityCols.T_V_PREFIX,
        VelocityCols.R_V_PREFIX,
        VelocityCols.T_A_PREFIX,
        VelocityCols.R_A_PREFIX,
        VelocityCols.T_V_NORM,
        VelocityCols.R_V_NORM,
        VelocityCols.T_A_NORM,
        VelocityCols.R_A_NORM,
        AnalysisCols.T_VX_ANA.rsplit("_", 1)[0],  # BoxLocal_V
        AnalysisCols.T_AX_ANA.rsplit("_", 1)[0],  # BoxLocal_A
        RigidBodyCols.BASE_NAME,
        r"C\d+_Global_V_T",
    ]
    exclusion_pattern = f"(?!{'|'.join(reserved_prefixes)})"

    axis_to_pt = {"X": HeaderL3.P_TX, "Y": HeaderL3.P_TY, "Z": HeaderL3.P_TZ}
    axis_to_vt = {"X": HeaderL3.V_TX, "Y": HeaderL3.V_TY, "Z": HeaderL3.V_TZ}

    rules = [
        # Timeline context metadata
        (re.compile(f"^{TimelineMetaCols.FULL_START_SEC}$"),
         lambda m: (HeaderL1.INFO, HeaderL2.TIMELINE, HeaderL3.TL_FULL_START_SEC)),
        (re.compile(f"^{TimelineMetaCols.FULL_END_SEC}$"),
         lambda m: (HeaderL1.INFO, HeaderL2.TIMELINE, HeaderL3.TL_FULL_END_SEC)),
        (re.compile(f"^{TimelineMetaCols.SLICE_START_SEC}$"),
         lambda m: (HeaderL1.INFO, HeaderL2.TIMELINE, HeaderL3.TL_SLICE_START_SEC)),
        (re.compile(f"^{TimelineMetaCols.SLICE_END_SEC}$"),
         lambda m: (HeaderL1.INFO, HeaderL2.TIMELINE, HeaderL3.TL_SLICE_END_SEC)),

        # CoM position (optimized pose)
        (re.compile(f"^{PoseCols.POS_X}$"), lambda m: (HeaderL1.POS, HeaderL2.COM, HeaderL3.P_TX)),
        (re.compile(f"^{PoseCols.POS_Y}$"), lambda m: (HeaderL1.POS, HeaderL2.COM, HeaderL3.P_TY)),
        (re.compile(f"^{PoseCols.POS_Z}$"), lambda m: (HeaderL1.POS, HeaderL2.COM, HeaderL3.P_TZ)),
        (re.compile(f"^{PoseCols.ROT_X}$"), lambda m: (HeaderL1.POS, HeaderL2.COM, HeaderL3.P_RX)),
        (re.compile(f"^{PoseCols.ROT_Y}$"), lambda m: (HeaderL1.POS, HeaderL2.COM, HeaderL3.P_RY)),
        (re.compile(f"^{PoseCols.ROT_Z}$"), lambda m: (HeaderL1.POS, HeaderL2.COM, HeaderL3.P_RZ)),

        # CoM velocity (Global)
        (re.compile(f"^{VelocityCols.T_VX}$"), lambda m: (HeaderL1.VEL, HeaderL2.COM, HeaderL3.V_TX)),
        (re.compile(f"^{VelocityCols.T_VY}$"), lambda m: (HeaderL1.VEL, HeaderL2.COM, HeaderL3.V_TY)),
        (re.compile(f"^{VelocityCols.T_VZ}$"), lambda m: (HeaderL1.VEL, HeaderL2.COM, HeaderL3.V_TZ)),
        (re.compile(f"^{VelocityCols.T_V_NORM}$"), lambda m: (HeaderL1.VEL, HeaderL2.COM, HeaderL3.V_TNORM)),
        (re.compile(f"^{VelocityCols.R_VX}$"), lambda m: (HeaderL1.VEL, HeaderL2.COM, HeaderL3.V_RX)),
        (re.compile(f"^{VelocityCols.R_VY}$"), lambda m: (HeaderL1.VEL, HeaderL2.COM, HeaderL3.V_RY)),
        (re.compile(f"^{VelocityCols.R_VZ}$"), lambda m: (HeaderL1.VEL, HeaderL2.COM, HeaderL3.V_RZ)),
        (re.compile(f"^{VelocityCols.R_V_NORM}$"), lambda m: (HeaderL1.VEL, HeaderL2.COM, HeaderL3.V_RNORM)),

        # CoM acceleration (Global)
        (re.compile(f"^{VelocityCols.T_AX}$"), lambda m: (HeaderL1.ACC, HeaderL2.COM, HeaderL3.A_TX)),
        (re.compile(f"^{VelocityCols.T_AY}$"), lambda m: (HeaderL1.ACC, HeaderL2.COM, HeaderL3.A_TY)),
        (re.compile(f"^{VelocityCols.T_AZ}$"), lambda m: (HeaderL1.ACC, HeaderL2.COM, HeaderL3.A_TZ)),
        (re.compile(f"^{VelocityCols.T_A_NORM}$"), lambda m: (HeaderL1.ACC, HeaderL2.COM, HeaderL3.A_TNORM)),
        (re.compile(f"^{VelocityCols.R_AX}$"), lambda m: (HeaderL1.ACC, HeaderL2.COM, HeaderL3.A_RX)),
        (re.compile(f"^{VelocityCols.R_AY}$"), lambda m: (HeaderL1.ACC, HeaderL2.COM, HeaderL3.A_RY)),
        (re.compile(f"^{VelocityCols.R_AZ}$"), lambda m: (HeaderL1.ACC, HeaderL2.COM, HeaderL3.A_RZ)),
        (re.compile(f"^{VelocityCols.R_A_NORM}$"), lambda m: (HeaderL1.ACC, HeaderL2.COM, HeaderL3.A_RNORM)),

        # CoM velocity (BoxLocal)
        (re.compile(f"^{AnalysisCols.T_VX_ANA}$"), lambda m: (HeaderL1.VEL, HeaderL2.COM, HeaderL3.V_TX_ANA)),
        (re.compile(f"^{AnalysisCols.T_VY_ANA}$"), lambda m: (HeaderL1.VEL, HeaderL2.COM, HeaderL3.V_TY_ANA)),
        (re.compile(f"^{AnalysisCols.T_VZ_ANA}$"), lambda m: (HeaderL1.VEL, HeaderL2.COM, HeaderL3.V_TZ_ANA)),
        (re.compile(f"^{AnalysisCols.T_V_NORM_ANA}$"), lambda m: (HeaderL1.VEL, HeaderL2.COM, HeaderL3.V_TNORM_ANA)),
        (re.compile(f"^{AnalysisCols.R_VX_ANA}$"), lambda m: (HeaderL1.VEL, HeaderL2.COM, HeaderL3.V_RX_ANA)),
        (re.compile(f"^{AnalysisCols.R_VY_ANA}$"), lambda m: (HeaderL1.VEL, HeaderL2.COM, HeaderL3.V_RY_ANA)),
        (re.compile(f"^{AnalysisCols.R_VZ_ANA}$"), lambda m: (HeaderL1.VEL, HeaderL2.COM, HeaderL3.V_RZ_ANA)),
        (re.compile(f"^{AnalysisCols.R_V_NORM_ANA}$"), lambda m: (HeaderL1.VEL, HeaderL2.COM, HeaderL3.V_RNORM_ANA)),

        # CoM acceleration (BoxLocal)
        (re.compile(f"^{AnalysisCols.T_AX_ANA}$"), lambda m: (HeaderL1.ACC, HeaderL2.COM, HeaderL3.A_TX_ANA)),
        (re.compile(f"^{AnalysisCols.T_AY_ANA}$"), lambda m: (HeaderL1.ACC, HeaderL2.COM, HeaderL3.A_TY_ANA)),
        (re.compile(f"^{AnalysisCols.T_AZ_ANA}$"), lambda m: (HeaderL1.ACC, HeaderL2.COM, HeaderL3.A_TZ_ANA)),
        (re.compile(f"^{AnalysisCols.T_A_NORM_ANA}$"), lambda m: (HeaderL1.ACC, HeaderL2.COM, HeaderL3.A_TNORM_ANA)),
        (re.compile(f"^{AnalysisCols.R_AX_ANA}$"), lambda m: (HeaderL1.ACC, HeaderL2.COM, HeaderL3.A_RX_ANA)),
        (re.compile(f"^{AnalysisCols.R_AY_ANA}$"), lambda m: (HeaderL1.ACC, HeaderL2.COM, HeaderL3.A_RY_ANA)),
        (re.compile(f"^{AnalysisCols.R_AZ_ANA}$"), lambda m: (HeaderL1.ACC, HeaderL2.COM, HeaderL3.A_RZ_ANA)),
        (re.compile(f"^{AnalysisCols.R_A_NORM_ANA}$"), lambda m: (HeaderL1.ACC, HeaderL2.COM, HeaderL3.A_RNORM_ANA)),

        # Corner velocity
        (re.compile(r"^(?P<corner>C\d+)_Global_V_T(?P<axis>[XYZ])$"),
         lambda m: (HeaderL1.VEL, m.group("corner"), axis_to_vt[m.group("axis")])),
        (re.compile(r"^(?P<corner>C\d+)_Global_V_T_Norm$"),
         lambda m: (HeaderL1.VEL, m.group("corner"), HeaderL3.V_TNORM)),
        # Backward compatibility
        (re.compile(r"^(?P<corner>C\d+)_V(?P<axis>[xyz])$"),
         lambda m: (HeaderL1.VEL, m.group("corner"), axis_to_vt[m.group("axis").upper()])),

        # Position (RigidBody / corners / markers)
        (re.compile(f"^{RigidBodyCols.BASE_NAME}_(?P<axis>[XYZ])$"),
         lambda m: (HeaderL1.POS, HeaderL2.RB, axis_to_pt[m.group("axis")])),
        (re.compile(r"^(?P<marker>C\d+)_(?P<axis>[XYZ])$"),
         lambda m: (HeaderL1.POS, m.group("marker"), axis_to_pt[m.group("axis")])) ,
        (re.compile(f"^{exclusion_pattern}(?P<marker>.*?)_(?P<suffix>FaceInfo|X|Y|Z)$"),
         lambda m: (
             HeaderL1.POS,
             m.group("marker"),
             HeaderL3.FACE if m.group("suffix") == "FaceInfo" else axis_to_pt[m.group("suffix")]
         )),

        # Analysis
        (re.compile(r"^(?P<corner>C\d+)_H_Ana$"),
         lambda m: (HeaderL1.ANALYSIS, m.group("corner"), HeaderL3.REL_H)),
        (re.compile(r"^(?P<corner>C\d+)_AIH_Ana$"),
         lambda m: (HeaderL1.ANALYSIS_SCENARIO, m.group("corner"), HeaderL3.ANALYSIS_INPUT_H)),

        # Etc
        (re.compile(f"^{AnalysisCols.FLOOR_N_X_ANA.split('_')[0]}_N_(?P<axis>[XYZ])_Ana$"),
         lambda m: (HeaderL1.ETC, HeaderL2.FLOOR_N, getattr(HeaderL3, f"N{m.group('axis')}"))),
        (re.compile(f"^{AnalysisCols.FLOOR_P_X_ANA.split('_')[0]}_P_(?P<axis>[XYZ])_Ana$"),
         lambda m: (HeaderL1.ETC, HeaderL2.FLOOR_P, axis_to_pt[m.group("axis")])),

        # Info
        (re.compile(f"^{TimeCols.FRAME}$"),
         lambda m: (HeaderL1.INFO, HeaderL2.FRAME, HeaderL2.FRAME)),
        (re.compile(f"^{TimeCols.TIME}$"),
         lambda m: (HeaderL1.INFO, HeaderL2.TIME, HeaderL3.TIME)),
        (re.compile(r"^Pose_Source$"),
         lambda m: (HeaderL1.INFO, HeaderL2.POSE_SRC, HeaderL3.SRC)),
    ]
    return rules


CONVERSION_RULES = get_conversion_rules()


def parse_column_name(col_name: str) -> tuple[str, str, str]:
    for pattern, converter in CONVERSION_RULES:
        match = pattern.match(col_name)
        if match:
            return converter(match)
    return (HeaderL1.ETC, HeaderL2.UNKNOWN, col_name)


def convert_to_multi_header(df: pd.DataFrame) -> pd.DataFrame:
    df_reset = df.reset_index()
    new_columns = [parse_column_name(col) for col in df_reset.columns]
    df_multi_header = df_reset.copy()
    df_multi_header.columns = pd.MultiIndex.from_tuples(new_columns)
    return df_multi_header
