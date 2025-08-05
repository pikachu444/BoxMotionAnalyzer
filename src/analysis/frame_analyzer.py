import pandas as pd
import numpy as np
from scipy.spatial.transform import Rotation as R

from src.config.data_columns import PoseCols, VelocityCols, AnalysisCols, CornerCoordCols, RelativeHeightCols


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
        # C1..C8에 대한 수직축 컬럼 이름 리스트를 동적으로 생성
        axis_suffix = [CornerCoordCols.X_SUFFIX, CornerCoordCols.Y_SUFFIX, CornerCoordCols.Z_SUFFIX][self.vertical_axis_idx]
        self.corner_vertical_coord_cols = [f'C{i+1}{axis_suffix}' for i in range(8)]
        self.relative_height_cols = [f'C{i+1}{RelativeHeightCols.H_ANA_SUFFIX}' for i in range(8)]

    def _transform_coordinates(self, frame_row: pd.Series, R_lab_to_ana: R, T_box_lab: np.ndarray) -> dict:
        """기존의 운동학 데이터를 분석 좌표계로 변환합니다."""
        v_com_lab = frame_row[[VelocityCols.COM_VX, VelocityCols.COM_VY, VelocityCols.COM_VZ]].values.astype(float)
        omega_w_lab = frame_row[[VelocityCols.ANG_WX, VelocityCols.ANG_WY, VelocityCols.ANG_WZ]].values.astype(float)

        v_com_ana = R_lab_to_ana @ v_com_lab
        omega_ana = R_lab_to_ana @ omega_w_lab

        n_floor_lab = np.zeros(3)
        n_floor_lab[self.vertical_axis_idx] = 1.0
        p_floor_lab = np.zeros(3)
        p_floor_lab[self.vertical_axis_idx] = self.floor_level
        n_floor_ana = R_lab_to_ana @ n_floor_lab
        p_floor_ana = R_lab_to_ana @ (p_floor_lab - T_box_lab)

        v_com_norm_ana = np.linalg.norm(v_com_ana)
        omega_norm_ana = np.linalg.norm(omega_ana)

        return {
            AnalysisCols.COM_VX_ANA: v_com_ana[0], AnalysisCols.COM_VY_ANA: v_com_ana[1], AnalysisCols.COM_VZ_ANA: v_com_ana[2],
            AnalysisCols.ANG_WX_ANA: omega_ana[0], AnalysisCols.ANG_WY_ANA: omega_ana[1], AnalysisCols.ANG_WZ_ANA: omega_ana[2],
            AnalysisCols.COM_V_NORM_ANA: v_com_norm_ana,
            AnalysisCols.ANG_W_NORM_ANA: omega_norm_ana,
            AnalysisCols.FLOOR_N_X_ANA: n_floor_ana[0], AnalysisCols.FLOOR_N_Y_ANA: n_floor_ana[1], AnalysisCols.FLOOR_N_Z_ANA: n_floor_ana[2],
            AnalysisCols.FLOOR_P_X_ANA: p_floor_ana[0], AnalysisCols.FLOOR_P_Y_ANA: p_floor_ana[1], AnalysisCols.FLOOR_P_Z_ANA: p_floor_ana[2],
        }

    def _calculate_relative_heights(self, frame_row: pd.Series) -> dict:
        """8개 코너의 상대 높이를 계산합니다."""
        vertical_coords = frame_row[self.corner_vertical_coord_cols].values.astype(float)
        min_corner_height = np.min(vertical_coords)

        if min_corner_height <= self.floor_level:
            # 박스가 바닥에 닿거나 파고든 경우: 가장 낮은 지점을 0으로 하는 상대 높이
            relative_heights = vertical_coords - min_corner_height
        else:
            # 박스가 바닥 위에 완전히 떠 있는 경우: 원래의 절대 높이
            relative_heights = vertical_coords

        return dict(zip(self.relative_height_cols, relative_heights))

    def process_frame(self, frame_row: pd.Series) -> pd.Series:
        """단일 프레임(DataFrame의 행)을 처리하여 모든 분석 값을 계산합니다."""
        try:
            T_box_lab = frame_row[[PoseCols.POS_X, PoseCols.POS_Y, PoseCols.POS_Z]].values.astype(float)
            rv_box_lab = frame_row[[PoseCols.ROT_X, PoseCols.ROT_Y, PoseCols.ROT_Z]].values.astype(float)
            R_lab_to_ana = R.from_rotvec(rv_box_lab).as_matrix().T
        except (KeyError, ValueError):
            return pd.Series(dtype=object)

        # 1. 좌표계 변환
        transformed_data = self._transform_coordinates(frame_row, R_lab_to_ana, T_box_lab)
        # 2. 상대 높이 계산
        relative_height_data = self._calculate_relative_heights(frame_row)

        # 3. 결과 병합
        all_results = {**transformed_data, **relative_height_data}
        return pd.Series(all_results)

    def process(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        입력된 DataFrame의 모든 프레임에 대해 분석을 수행합니다.
        """
        if df.empty or VelocityCols.COM_VX not in df.columns or CornerCoordCols.C7_Z not in df.columns:
            return df

        # `apply`를 사용하여 각 행에 대해 process_frame 함수를 실행
        analysis_data = df.apply(self.process_frame, axis=1)

        # 원본 데이터프레임에 분석 결과 병합
        result_df = df.join(analysis_data)

        # 컬럼 순서 재배치
        cols = result_df.columns.tolist()
        # COM_V_NORM_ANA 이동
        if AnalysisCols.COM_V_NORM_ANA in cols:
            cols.remove(AnalysisCols.COM_V_NORM_ANA)
            cols.insert(cols.index(AnalysisCols.COM_VZ_ANA) + 1, AnalysisCols.COM_V_NORM_ANA)
        # ANG_W_NORM_ANA 이동
        if AnalysisCols.ANG_W_NORM_ANA in cols:
            cols.remove(AnalysisCols.ANG_W_NORM_ANA)
            cols.insert(cols.index(AnalysisCols.ANG_WZ_ANA) + 1, AnalysisCols.ANG_W_NORM_ANA)
        result_df = result_df[cols]

        print(f"[FrameAnalyzer INFO] Processed {len(df)} frames.")
        return result_df
