import pandas as pd
import re
from typing import Tuple
from src.config.data_columns import (
    HeaderL1, HeaderL2, HeaderL3, RigidBodyCols, VelocityCols, PoseCols, AnalysisCols, TimeCols,
    ANA_COORDINATE_SUFFIX
)

# --- 멀티헤더 변환 규칙 ---

def get_conversion_rules() -> list:
    """
    멀티헤더 변환 규칙을 생성하여 반환합니다.
    이 함수는 순서가 매우 중요합니다: 가장 구체적인 규칙이 먼저, 가장 일반적인 규칙이 나중에 와야 합니다.
    """
    # 1. 시스템 예약 접두사 목록 동적 생성 (마커 규칙의 예외 처리를 위해)
    # data_columns.py의 변수 값이 바뀌어도 자동으로 반영됨
    reserved_prefixes = [
        PoseCols.T_PREFIX,
        PoseCols.R_PREFIX,
        VelocityCols.COM_V_PREFIX,
        VelocityCols.ANG_W_PREFIX,
        VelocityCols.COM_V_NORM,
        VelocityCols.ANG_W_NORM,
        RigidBodyCols.BASE_NAME,
        'C\\d+_V'  # Corner velocity
    ]
    # 정규식의 negative lookahead 패턴 생성: (?!Box_T|Box_R|...)
    exclusion_pattern = f"(?!{'|'.join(reserved_prefixes)})"

    # 2. 변환 규칙 정의 (가장 구체적인 순서 -> 가장 일반적인 순서)
    rules = [
        # --- Level 1: Pose ---
        # 예시: 'Box_Tx' -> ('Pose', 'BoxTranslation', 'TX')
        (re.compile(f"^{PoseCols.T_PREFIX}(?P<axis>[xyz])$"),
         lambda m: (HeaderL1.POSE, HeaderL2.BOX_T, getattr(HeaderL3, f"T{m.group('axis').upper()}"))),
        # 예시: 'Box_Tx_Ana' -> ('Pose', 'BoxTranslation', 'TX_Ana')
        (re.compile(f"^{PoseCols.T_PREFIX}(?P<axis>[xyz]){ANA_COORDINATE_SUFFIX}$"),
         lambda m: (HeaderL1.POSE, HeaderL2.BOX_T, f"T{m.group('axis').upper()}{ANA_COORDINATE_SUFFIX}")),
        # 예시: 'Box_Rx' -> ('Pose', 'BoxRotation', 'RX')
        (re.compile(f"^{PoseCols.R_PREFIX}(?P<axis>[xyz])$"),
         lambda m: (HeaderL1.POSE, HeaderL2.BOX_R, getattr(HeaderL3, f"R{m.group('axis').upper()}"))),
        # 예시: 'Box_Rx_Ana' -> ('Pose', 'BoxRotation', 'RX_Ana')
        (re.compile(f"^{PoseCols.R_PREFIX}(?P<axis>[xyz]){ANA_COORDINATE_SUFFIX}$"),
         lambda m: (HeaderL1.POSE, HeaderL2.BOX_R, f"R{m.group('axis').upper()}{ANA_COORDINATE_SUFFIX}")),

        # --- Level 1: Velocity ---
        # 예시: 'CoM_Vx' -> ('Velocity', 'CoM', 'VX')
        (re.compile(f"^{VelocityCols.COM_V_PREFIX}(?P<axis>[xyz])$"),
         lambda m: (HeaderL1.VEL, HeaderL2.COM, getattr(HeaderL3, f"V{m.group('axis').upper()}"))),
        # 예시: 'AngVel_Wx' -> ('Velocity', 'CoM', 'WX')
        (re.compile(f"^{VelocityCols.ANG_W_PREFIX}(?P<axis>[xyz])$"),
         lambda m: (HeaderL1.VEL, HeaderL2.COM, getattr(HeaderL3, f"W{m.group('axis').upper()}"))),
        # 예시: 'CoM_V_Norm' -> ('Velocity', 'CoM', 'Norm_V')
        (re.compile(f"^{VelocityCols.COM_V_NORM}$"),
         lambda m: (HeaderL1.VEL, HeaderL2.COM, HeaderL3.NORM_V)),
        # 예시: 'AngVel_W_Norm' -> ('Velocity', 'CoM', 'Norm_W')
        (re.compile(f"^{VelocityCols.ANG_W_NORM}$"),
         lambda m: (HeaderL1.VEL, HeaderL2.COM, HeaderL3.NORM_W)),
        # 예시: 'CoM_Vx_Ana' -> ('Velocity', 'CoM', 'VX_Ana')
        (re.compile(f"^{VelocityCols.COM_V_PREFIX}(?P<axis>[xyz])_Ana$"),
         lambda m: (HeaderL1.VEL, HeaderL2.COM, f"V{m.group('axis').upper()}_Ana")),
        # 예시: 'AngVel_Wx_Ana' -> ('Velocity', 'CoM', 'WX_Ana')
        (re.compile(f"^{VelocityCols.ANG_W_PREFIX}(?P<axis>[xyz])_Ana$"),
         lambda m: (HeaderL1.VEL, HeaderL2.COM, f"W{m.group('axis').upper()}_Ana")),
        # 예시: 'CoM_V_Norm_Ana' -> ('Velocity', 'CoM', 'Norm_V_Ana')
        (re.compile(f"^{AnalysisCols.COM_V_NORM_ANA}$"),
         lambda m: (HeaderL1.VEL, HeaderL2.COM, f"{HeaderL3.NORM_V}_Ana")),
        # 예시: 'AngVel_W_Norm_Ana' -> ('Velocity', 'CoM', 'Norm_W_Ana')
        (re.compile(f"^{AnalysisCols.ANG_W_NORM_ANA}$"),
         lambda m: (HeaderL1.VEL, HeaderL2.COM, f"{HeaderL3.NORM_W}_Ana")),
        # 예시: 'C0_Vx' -> ('Velocity', 'C0', 'VX')
        (re.compile(r"^(?P<corner>C\d+)_V(?P<axis>[xyz])$"),
         lambda m: (HeaderL1.VEL, m.group('corner'), getattr(HeaderL3, f"V{m.group('axis').upper()}"))),

        # --- Level 1: Position (Specific) ---
        # 예시: 'RigidBody_Position_X' -> ('Position', 'RigidBody', 'PX')
        (re.compile(f"^{RigidBodyCols.BASE_NAME}_(?P<axis>[XYZ])$"),
         lambda m: (HeaderL1.POS, HeaderL2.RB, getattr(HeaderL3, f"P{m.group('axis')}"))),

        # --- Level 1: Position (General Markers - with Safeguard) ---
        # 예시: 'C0_X', 'C7_Z' -> ('Position', 'C0', 'PX'), ('Position', 'C7', 'PZ')
        (re.compile(r"^(?P<marker>C\d+)_(?P<axis>[XYZ])$"),
         lambda m: (HeaderL1.POS, m.group('marker'), getattr(HeaderL3, f"P{m.group('axis')}"))),
        # 예시: 'B2_X', 'F1_FaceInfo', 'F_Marker_3_Y'
        # 안전장치: 시스템 예약어(Box_T 등)와 충돌하지 않도록 exclusion_pattern 사용
        # 수정: 마커 이름에 '_'가 포함될 수 있도록 허용하고, non-greedy '.*?' 수량자를 사용하여 마지막 suffix만 구분
        (re.compile(f"^{exclusion_pattern}(?P<marker>.*?)_(?P<suffix>FaceInfo|X|Y|Z)$"),
         lambda m: (HeaderL1.POS, m.group('marker'), HeaderL3.FACE if m.group('suffix') == 'FaceInfo' else getattr(HeaderL3, f"P{m.group('suffix')}"))),

        # --- Level 1: Analysis ---
        # 예시: 'C1_H_Ana' -> ('Analysis', 'C1', 'RelativeHeight')
        (re.compile(r"^(?P<corner>C\d+)_H_Ana$"),
         lambda m: (HeaderL1.ANALYSIS, m.group('corner'), HeaderL3.REL_H)),
        # 예시: 'C1_AIH_Ana' -> ('Analysis Scenario', 'C1', 'AnalysisInputHeight')
        (re.compile(r"^(?P<corner>C\d+)_AIH_Ana$"),
         lambda m: (HeaderL1.ANALYSIS_SCENARIO, m.group('corner'), HeaderL3.ANALYSIS_INPUT_H)),

        # --- Level 1: Etc ---
        # 예시: 'Floor_N_X_Ana' -> ('Etc', 'FloorNormal', 'NX')
        (re.compile(f"^{AnalysisCols.FLOOR_N_X_ANA.split('_')[0]}_N_(?P<axis>[XYZ])_Ana$"),
         lambda m: (HeaderL1.ETC, HeaderL2.FLOOR_N, getattr(HeaderL3, f"N{m.group('axis')}"))),
        # 예시: 'Floor_P_X_Ana' -> ('Etc', 'FloorPoint', 'PX')
        (re.compile(f"^{AnalysisCols.FLOOR_P_X_ANA.split('_')[0]}_P_(?P<axis>[XYZ])_Ana$"),
         lambda m: (HeaderL1.ETC, HeaderL2.FLOOR_P, getattr(HeaderL3, f"P{m.group('axis')}"))),

        # --- Level 1: Info ---
        # 예시: 'Frame' -> ('Info', 'Frame', 'Frame')
        (re.compile(f"^{TimeCols.FRAME}$"),
         lambda m: (HeaderL1.INFO, HeaderL2.FRAME, HeaderL2.FRAME)),
        # 예시: 'Time' -> ('Info', 'Time', 'Time')
        (re.compile(f"^{TimeCols.TIME}$"),
         lambda m: (HeaderL1.INFO, HeaderL2.TIME, HeaderL3.TIME)),
        # 예시: 'Pose_Source' -> ('Info', 'Pose', 'Source')
        (re.compile(r"^Pose_Source$"),
         lambda m: (HeaderL1.INFO, HeaderL2.POSE_SRC, HeaderL3.SRC)),
    ]
    return rules

# 모듈 로드 시점에 변환 규칙을 한 번만 생성
CONVERSION_RULES = get_conversion_rules()

def parse_column_name(col_name: str) -> tuple[str, str, str]:
    """
    단일 컬럼 이름을 정의된 규칙에 따라 3단계 멀티헤더 튜플로 변환합니다.
    """
    for pattern, converter in CONVERSION_RULES:
        match = pattern.match(col_name)
        if match:
            return converter(match)
    # 일치하는 규칙이 없는 경우
    return (HeaderL1.ETC, HeaderL2.UNKNOWN, col_name)

def convert_to_multi_header(df: pd.DataFrame) -> pd.DataFrame:
    """
    DataFrame의 컬럼을 3단계 멀티헤더로 변환합니다.
    """
    df_reset = df.reset_index()

    new_columns = [parse_column_name(col) for col in df_reset.columns]

    df_multi_header = df_reset.copy()
    df_multi_header.columns = pd.MultiIndex.from_tuples(new_columns)

    return df_multi_header
