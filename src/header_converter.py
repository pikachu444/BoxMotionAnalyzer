import pandas as pd
import re
from typing import Tuple
from src.config.data_columns import (
    HeaderL1, HeaderL2, HeaderL3, RigidBodyCols, VelocityCols, PoseCols, AnalysisCols, TimeCols
)

# --- 멀티헤더 변환 규칙 ---
# 각 규칙은 (정규식 패턴, 변환 함수) 형태의 튜플로 정의됩니다.
#
# 1. 정규식 패턴 (re.compile):
#    - 컬럼 이름이 어떤 형태인지 감지하는 역할을 합니다.
#    - `(?P<name>...)` 구문을 사용하여, 매칭된 부분에 'name'과 같은 이름을 부여할 수 있습니다.
#
# 2. 변환 함수 (lambda m: ...):
#    - 위 정규식에 컬럼 이름이 매칭되었을 때 실행되는 익명 함수입니다.
#    - 파라미터 'm'은 정규식의 매치(match) 객체를 받습니다.
#    - `m.group('name')`과 같이, 정규식에서 이름 붙인 그룹을 가져와 사용할 수 있습니다.
#    - 최종적으로 3단계 멀티헤더를 나타내는 튜플(level1, level2, level3)을 반환합니다.
CONVERSION_RULES = [
    # 예시: 'RigidBody_Position_X' -> ('Position', 'RigidBody', 'PX')
    (re.compile(f"^{RigidBodyCols.BASE_NAME}_(?P<axis>[XYZ])$"),
     lambda m: (HeaderL1.POS, HeaderL2.RB, getattr(HeaderL3, f"P{m.group('axis')}"))),

    # 예시: 'C0_X', 'C7_Z' -> ('Position', 'C0', 'PX'), ('Position', 'C7', 'PZ')
    (re.compile(r"^(?P<marker>C\d+)_(?P<axis>[XYZ])$"),
     lambda m: (HeaderL1.POS, m.group('marker'), getattr(HeaderL3, f"P{m.group('axis')}"))),

    # 예시: 'B2_X', 'F1_FaceInfo' -> ('Position', 'B2', 'PX'), ('Position', 'F1', 'FaceInfo')
    (re.compile(f"^(?P<marker>[A-Z0-9]+)_(?P<suffix>FaceInfo|X|Y|Z)$"),
     lambda m: (HeaderL1.POS, m.group('marker'), HeaderL3.FACE if m.group('suffix') == 'FaceInfo' else getattr(HeaderL3, f"P{m.group('suffix')}"))),

    # 예시: 'CoM_Vx' -> ('Velocity', 'CoM', 'VX')
    (re.compile(f"^{VelocityCols.COM_VX.replace('x', '')}(?P<axis>[xyz])$"),
     lambda m: (HeaderL1.VEL, HeaderL2.COM, getattr(HeaderL3, f"V{m.group('axis').upper()}"))),

    # 예시: 'AngVel_Wx' -> ('Velocity', 'Angular', 'WX')
    (re.compile(f"^{VelocityCols.ANG_WX.replace('x', '')}(?P<axis>[xyz])$"),
     lambda m: (HeaderL1.VEL, HeaderL2.ANG, getattr(HeaderL3, f"W{m.group('axis').upper()}"))),

    # 예시: 'CoM_Vx_Ana' -> ('Velocity', 'CoM', 'VX_Ana')
    (re.compile(f"^{AnalysisCols.COM_VX_ANA.replace('x', '')[:-4]}(?P<axis>[xyz])_Ana$"),
     lambda m: (HeaderL1.VEL, HeaderL2.COM, f"V{m.group('axis').upper()}_Ana")),

    # 예시: 'AngVel_Wx_Ana' -> ('Velocity', 'Angular', 'WX_Ana')
    (re.compile(f"^{AnalysisCols.ANG_WX_ANA.replace('x', '')[:-4]}(?P<axis>[xyz])_Ana$"),
     lambda m: (HeaderL1.VEL, HeaderL2.ANG, f"W{m.group('axis').upper()}_Ana")),

    # 예시: 'C0_Vx' -> ('Velocity', 'C0', 'VX')
    (re.compile(r"^(?P<corner>C\d+)_V(?P<axis>[xyz])$"),
     lambda m: (HeaderL1.VEL, m.group('corner'), getattr(HeaderL3, f"V{m.group('axis').upper()}"))),

    # 예시: 'Box_Tx' -> ('Pose', 'BoxTranslation', 'TX')
    (re.compile(f"^{PoseCols.POS_X.replace('x', '')}(?P<axis>[xyz])$"),
     lambda m: (HeaderL1.POSE, HeaderL2.BOX_T, getattr(HeaderL3, f"T{m.group('axis').upper()}"))),

    # 예시: 'Box_Rx' -> ('Pose', 'BoxRotation', 'RX')
    (re.compile(f"^{PoseCols.ROT_X.replace('x', '')}(?P<axis>[xyz])$"),
     lambda m: (HeaderL1.POSE, HeaderL2.BOX_R, getattr(HeaderL3, f"R{m.group('axis').upper()}"))),

    # 예시: 'Floor_N_X_Ana' -> ('Etc', 'FloorNormal', 'NX')
    (re.compile(f"^{AnalysisCols.FLOOR_N_X_ANA.split('_')[0]}_N_(?P<axis>[XYZ])_Ana$"),
     lambda m: (HeaderL1.ETC, HeaderL2.FLOOR_N, getattr(HeaderL3, f"N{m.group('axis')}"))),

    # 예시: 'Floor_P_X_Ana' -> ('Etc', 'FloorPoint', 'PX')
    (re.compile(f"^{AnalysisCols.FLOOR_P_X_ANA.split('_')[0]}_P_(?P<axis>[XYZ])_Ana$"),
     lambda m: (HeaderL1.ETC, HeaderL2.FLOOR_P, getattr(HeaderL3, f"P{m.group('axis')}"))),

    # 예시: 'FrameNumber' -> ('Info', 'Frame', 'Number')
    (re.compile(f"^{TimeCols.FRAME}$"),
     lambda m: (HeaderL1.INFO, HeaderL2.FRAME, HeaderL3.NUM)),

    # 예시: 'Time' -> ('Info', 'Time', 's')
    (re.compile(f"^{TimeCols.TIME}$"),
     lambda m: (HeaderL1.INFO, HeaderL2.TIME, HeaderL3.SEC)),

    # 예시: 'Pose_Source' -> ('Info', 'Pose', 'Source')
    (re.compile(r"^Pose_Source$"),
     lambda m: (HeaderL1.INFO, HeaderL2.POSE_SRC, HeaderL3.SRC)),
]

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
