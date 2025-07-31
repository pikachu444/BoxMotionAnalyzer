import pandas as pd
import re

def parse_column_name(col_name):
    """
    단일 컬럼 이름을 3단계 멀티헤더 튜플로 변환합니다.
    정의된 규칙에 따라 파싱하고, 일치하는 규칙이 없으면 기본값을 반환합니다.
    """
    # Position 규칙
    if col_name.startswith('RigidBody_Position_'):
        axis = col_name[-1]
        return ('Position', 'RigidBody', f'P{axis}')
    if re.match(r'^C\d+_[XYZ]$', col_name):
        parts = col_name.split('_')
        return ('Position', parts[0], f'P{parts[1]}')
    if col_name.endswith(('_X', '_Y', '_Z', '_FaceInfo')):
        parts = col_name.split('_')
        if len(parts) > 1:
            marker_id = '_'.join(parts[:-1])
            suffix = parts[-1]
            if suffix == 'FaceInfo':
                return ('Position', marker_id, 'FaceInfo')
            else:
                return ('Position', marker_id, f'P{suffix[-1]}')

    # Velocity 규칙
    if col_name.startswith('CoM_V'):
        axis = col_name[-1]
        return ('Velocity', 'CoM', f'V{axis.upper()}')
    if col_name.startswith('AngVel_W'):
        axis = col_name[-1]
        return ('Velocity', 'Angular', f'W{axis.upper()}')
    if re.match(r'^C\d+_V[xyz]$', col_name):
        parts = col_name.split('_')
        return ('Velocity', parts[0], parts[1].upper())

    # Pose 규칙
    if col_name.startswith('Box_T'):
        axis = col_name[-1]
        return ('Pose', 'BoxTranslation', f'T{axis.upper()}')
    if col_name.startswith('Box_R'):
        axis = col_name[-1]
        return ('Pose', 'BoxRotation', f'R{axis.upper()}')

    # Etc 규칙
    if 'Floor_N' in col_name:
        axis = col_name.split('_')[2]
        return ('Etc', 'FloorNormal', f'N{axis}')
    if 'Floor_P' in col_name:
        axis = col_name.split('_')[2]
        return ('Etc', 'FloorPoint', f'P{axis}')

    # Info 규칙
    if col_name == 'FrameNumber':
        return ('Info', 'Frame', 'Number')
    if col_name == 'Pose_Source':
        return ('Info', 'Pose', 'Source')

    # 일치하는 규칙이 없는 경우
    return ('Etc', 'Unknown', col_name)

def convert_to_multi_header(df: pd.DataFrame) -> pd.DataFrame:
    """
    DataFrame의 컬럼을 3단계 멀티헤더로 변환합니다.
    """
    # 인덱스도 컬럼으로 변환하여 처리
    df_reset = df.reset_index()

    # 'Time' 인덱스에 대한 멀티헤더 튜플 생성
    time_tuple = ('Info', 'Time', 's')

    new_columns = [parse_column_name(col) for col in df_reset.columns]

    # 'Time' 컬럼의 위치를 찾아 멀티헤더 튜플 교체
    try:
        time_index_pos = list(df_reset.columns).index('Time')
        new_columns[time_index_pos] = time_tuple
    except ValueError:
        # Time 컬럼이 없는 경우, 맨 앞에 추가
        df_reset = df.reset_index(drop=False) # Time을 컬럼으로 가져옴
        new_columns.insert(0, time_tuple)

    df_multi_header = df_reset.copy()
    df_multi_header.columns = pd.MultiIndex.from_tuples(new_columns)

    return df_multi_header
