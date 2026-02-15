import pandas as pd
import numpy as np
from scipy.spatial.transform import Rotation as R

from src.config.data_columns import (
    PoseCols, VelocityCols, AnalysisCols, CornerCoordCols, RelativeHeightCols,
    AnalysisInputHeightCols
)


class FrameAnalyzer:
    """
    계산된 운동학 데이터를 분석하고, 추가적인 분석 값(예: 상대 높이)을 계산합니다.
    """

    def __init__(self, vertical_axis_idx: int = 1, floor_level: float = 0.0):
        """
        FrameAnalyzer를 초기화합니다.
        """
        self.vertical_axis_idx = vertical_axis_idx
        self.floor_level = floor_level

        # --- 상대 높이 계산에 필요한 컬럼 이름 리스트를 동적으로 생성 ---
        # 수직축에 해당하는 suffix (_X, _Y, _Z)를 가져옴
        axis_suffix = [CornerCoordCols.X_SUFFIX, CornerCoordCols.Y_SUFFIX, CornerCoordCols.Z_SUFFIX][self.vertical_axis_idx]
        # 8개 코너의 수직 좌표 컬럼 이름 목록 (예: ['C1_Y', 'C2_Y', ...])
        self.corner_vertical_coord_cols = [f'C{i+1}{axis_suffix}' for i in range(8)]
        # 8개 코너의 상대 높이 결과 컬럼 이름 목록 (예: ['C1_H_Ana', 'C2_H_Ana', ...])
        self.relative_height_cols = [f'C{i+1}{RelativeHeightCols.H_ANA_SUFFIX}' for i in range(8)]
        self.analysis_input_height_cols = [f'C{i+1}{AnalysisInputHeightCols.AIH_ANA_SUFFIX}' for i in range(8)]


    def _transform_coordinates(self, frame_row: pd.Series, R_lab_to_ana: R, T_box_lab: np.ndarray) -> dict:
        """기존의 운동학 데이터를 분석 좌표계로 변환합니다."""
        v_com_lab = frame_row[[VelocityCols.T_VX, VelocityCols.T_VY, VelocityCols.T_VZ]].values.astype(float)
        omega_w_lab = frame_row[[VelocityCols.R_VX, VelocityCols.R_VY, VelocityCols.R_VZ]].values.astype(float)
        a_com_lab = frame_row[[VelocityCols.T_AX, VelocityCols.T_AY, VelocityCols.T_AZ]].values.astype(float)
        alpha_lab = frame_row[[VelocityCols.R_AX, VelocityCols.R_AY, VelocityCols.R_AZ]].values.astype(float)

        v_com_ana = R_lab_to_ana @ v_com_lab
        omega_ana = R_lab_to_ana @ omega_w_lab
        a_com_ana = R_lab_to_ana @ a_com_lab
        alpha_ana = R_lab_to_ana @ alpha_lab

        n_floor_lab = np.zeros(3)
        n_floor_lab[self.vertical_axis_idx] = 1.0
        p_floor_lab = np.zeros(3)
        p_floor_lab[self.vertical_axis_idx] = self.floor_level
        n_floor_ana = R_lab_to_ana @ n_floor_lab
        p_floor_ana = R_lab_to_ana @ (p_floor_lab - T_box_lab)

        v_com_norm_ana = np.linalg.norm(v_com_ana)
        omega_norm_ana = np.linalg.norm(omega_ana)
        a_com_norm_ana = np.linalg.norm(a_com_ana)
        alpha_norm_ana = np.linalg.norm(alpha_ana)

        return {
            AnalysisCols.T_VX_ANA: v_com_ana[0], AnalysisCols.T_VY_ANA: v_com_ana[1], AnalysisCols.T_VZ_ANA: v_com_ana[2],
            AnalysisCols.R_VX_ANA: omega_ana[0], AnalysisCols.R_VY_ANA: omega_ana[1], AnalysisCols.R_VZ_ANA: omega_ana[2],
            AnalysisCols.T_V_NORM_ANA: v_com_norm_ana,
            AnalysisCols.R_V_NORM_ANA: omega_norm_ana,
            AnalysisCols.T_AX_ANA: a_com_ana[0], AnalysisCols.T_AY_ANA: a_com_ana[1], AnalysisCols.T_AZ_ANA: a_com_ana[2],
            AnalysisCols.R_AX_ANA: alpha_ana[0], AnalysisCols.R_AY_ANA: alpha_ana[1], AnalysisCols.R_AZ_ANA: alpha_ana[2],
            AnalysisCols.T_A_NORM_ANA: a_com_norm_ana,
            AnalysisCols.R_A_NORM_ANA: alpha_norm_ana,
            AnalysisCols.FLOOR_N_X_ANA: n_floor_ana[0], AnalysisCols.FLOOR_N_Y_ANA: n_floor_ana[1], AnalysisCols.FLOOR_N_Z_ANA: n_floor_ana[2],
            AnalysisCols.FLOOR_P_X_ANA: p_floor_ana[0], AnalysisCols.FLOOR_P_Y_ANA: p_floor_ana[1], AnalysisCols.FLOOR_P_Z_ANA: p_floor_ana[2],
        }

    def _calculate_relative_heights(self, frame_row: pd.Series) -> dict:
        """8개 코너의 상대 높이를 계산합니다."""
        vertical_coords = frame_row[self.corner_vertical_coord_cols].values.astype(float)
        min_corner_height = np.min(vertical_coords)

        if min_corner_height <= self.floor_level:
            relative_heights = vertical_coords - min_corner_height
        else:
            relative_heights = vertical_coords

        return dict(zip(self.relative_height_cols, relative_heights))

    def _calculate_analysis_input_heights(self, frame_row: pd.Series) -> dict:
        """8개 코너의 해석 시나리오 입력 높이를 계산합니다. (현재는 상대 높이와 동일)"""
        vertical_coords = frame_row[self.corner_vertical_coord_cols].values.astype(float)
        min_corner_height = np.min(vertical_coords)

        if min_corner_height <= self.floor_level:
            analysis_input_heights = vertical_coords - min_corner_height
        else:
            analysis_input_heights = vertical_coords

        return dict(zip(self.analysis_input_height_cols, analysis_input_heights))

    def process_frame(self, frame_row: pd.Series) -> pd.Series:
        """단일 프레임(DataFrame의 행)을 처리하여 모든 분석 값을 계산합니다."""
        try:
            T_box_lab = frame_row[[PoseCols.POS_X, PoseCols.POS_Y, PoseCols.POS_Z]].values.astype(float)
            rv_box_lab = frame_row[[PoseCols.ROT_X, PoseCols.ROT_Y, PoseCols.ROT_Z]].values.astype(float)
            R_lab_to_ana = R.from_rotvec(rv_box_lab).as_matrix().T
        except (KeyError, ValueError):
            return pd.Series(dtype=object)

        transformed_data = self._transform_coordinates(frame_row, R_lab_to_ana, T_box_lab)
        relative_height_data = self._calculate_relative_heights(frame_row)
        analysis_input_height_data = self._calculate_analysis_input_heights(frame_row)

        all_results = {**transformed_data, **relative_height_data, **analysis_input_height_data}
        return pd.Series(all_results)

    def process(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        입력된 DataFrame의 모든 프레임에 대해 분석을 수행합니다.
        """
        # --- 입력 데이터 검증 (Guard Clause) ---
        # 이 분석 모듈이 실행되기 위해 필요한 모든 컬럼이 데이터프레임에 있는지 동적으로 확인합니다.
        required_cols = []
        # 1. Pose(위치/회전)와 Velocity 컬럼 추가 (헬퍼 변수는 제외)
        for col_class in [PoseCols, VelocityCols]:
            for attr_name in col_class.__annotations__:
                if not attr_name.endswith(('_PREFIX', '_SUFFIX')):
                    required_cols.append(getattr(col_class, attr_name))

        # 2. 24개의 코너 좌표 컬럼 이름 동적 생성 및 추가
        for i in range(8):
            corner_num = i + 1
            required_cols.append(f'C{corner_num}{CornerCoordCols.X_SUFFIX}')
            required_cols.append(f'C{corner_num}{CornerCoordCols.Y_SUFFIX}')
            required_cols.append(f'C{corner_num}{CornerCoordCols.Z_SUFFIX}')

        # 3. 필수 컬럼 중 실제 데이터프레임에 없는 컬럼들을 찾음
        missing_cols = [col for col in required_cols if col not in df.columns]
        if missing_cols:
            # 누락된 컬럼이 있으면, 명확한 에러 메시지를 출력하고 분석을 중단
            print(f"[FrameAnalyzer ERROR] Missing required input columns: {sorted(missing_cols)}")
            return df

        # `apply`를 사용하여 각 행에 대해 process_frame 함수를 실행
        analysis_data = df.apply(self.process_frame, axis=1)

        # 원본 데이터프레임에 분석 결과 병합
        result_df = df.join(analysis_data)

        # 컬럼 순서 재배치
        cols = result_df.columns.tolist()
        # COM_V_NORM_ANA 이동
        if AnalysisCols.T_V_NORM_ANA in cols:
            cols.remove(AnalysisCols.T_V_NORM_ANA)
            cols.insert(cols.index(AnalysisCols.T_VZ_ANA) + 1, AnalysisCols.T_V_NORM_ANA)
        # ANG_W_NORM_ANA 이동
        if AnalysisCols.R_V_NORM_ANA in cols:
            cols.remove(AnalysisCols.R_V_NORM_ANA)
            cols.insert(cols.index(AnalysisCols.R_VZ_ANA) + 1, AnalysisCols.R_V_NORM_ANA)
        # COM_A_NORM_ANA 이동
        if AnalysisCols.T_A_NORM_ANA in cols:
            cols.remove(AnalysisCols.T_A_NORM_ANA)
            cols.insert(cols.index(AnalysisCols.T_AZ_ANA) + 1, AnalysisCols.T_A_NORM_ANA)
        # ANG_A_NORM_ANA 이동
        if AnalysisCols.R_A_NORM_ANA in cols:
            cols.remove(AnalysisCols.R_A_NORM_ANA)
            cols.insert(cols.index(AnalysisCols.R_AZ_ANA) + 1, AnalysisCols.R_A_NORM_ANA)
        result_df = result_df[cols]

        print(f"[FrameAnalyzer INFO] Processed {len(df)} frames.")
        return result_df
