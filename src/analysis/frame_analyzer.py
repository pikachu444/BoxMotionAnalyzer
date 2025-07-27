import pandas as pd
import numpy as np
from scipy.spatial.transform import Rotation as R

from config.data_columns import PoseCols, VelocityCols, AnalysisCols


class FrameAnalyzer:
    """
    계산된 운동학 데이터를 분석 좌표계(Analysis Frame)로 변환합니다.
    """

    def __init__(self, vertical_axis_idx: int = 1, floor_level: float = 0.0):
        """
        FrameAnalyzer를 초기화합니다.

        Args:
            vertical_axis_idx (int): 월드 좌표계에서 수직에 해당하는 축 (0:X, 1:Y, 2:Z).
            floor_level (float): 월드 좌표계에서 바닥의 높이.
        """
        self.vertical_axis_idx = vertical_axis_idx
        self.floor_level = floor_level

    def _get_lab_floor_params(self):
        """월드 좌표계의 바닥 평면 파라미터를 반환합니다."""
        n_floor_lab = np.zeros(3)
        n_floor_lab[self.vertical_axis_idx] = 1.0
        p_floor_lab = np.zeros(3)
        p_floor_lab[self.vertical_axis_idx] = self.floor_level
        return n_floor_lab, p_floor_lab

    def process_frame(self, frame_row: pd.Series) -> pd.Series:
        """단일 프레임(DataFrame의 행)을 처리하여 분석 좌표계 값을 계산합니다."""
        try:
            T_box_lab = frame_row[[PoseCols.POS_X, PoseCols.POS_Y, PoseCols.POS_Z]].values.astype(float)
            rv_box_lab = frame_row[[PoseCols.ROT_X, PoseCols.ROT_Y, PoseCols.ROT_Z]].values.astype(float)
            v_com_lab = frame_row[[VelocityCols.COM_VX, VelocityCols.COM_VY, VelocityCols.COM_VZ]].values.astype(float)
            omega_w_lab = frame_row[[VelocityCols.ANG_WX, VelocityCols.ANG_WY, VelocityCols.ANG_WZ]].values.astype(float)
        except (KeyError, ValueError):
            return pd.Series(dtype=object)

        R_lab_to_ana = R.from_rotvec(rv_box_lab).as_matrix().T

        v_com_ana = R_lab_to_ana @ v_com_lab
        omega_ana = R_lab_to_ana @ omega_w_lab

        n_floor_lab, p_floor_lab = self._get_lab_floor_params()
        n_floor_ana = R_lab_to_ana @ n_floor_lab
        p_floor_ana = R_lab_to_ana @ (p_floor_lab - T_box_lab)

        result_data = {
            AnalysisCols.COM_VX_ANA: v_com_ana[0], AnalysisCols.COM_VY_ANA: v_com_ana[1], AnalysisCols.COM_VZ_ANA: v_com_ana[2],
            AnalysisCols.ANG_WX_ANA: omega_ana[0], AnalysisCols.ANG_WY_ANA: omega_ana[1], AnalysisCols.ANG_WZ_ANA: omega_ana[2],
            AnalysisCols.FLOOR_N_X_ANA: n_floor_ana[0], AnalysisCols.FLOOR_N_Y_ANA: n_floor_ana[1], AnalysisCols.FLOOR_N_Z_ANA: n_floor_ana[2],
            AnalysisCols.FLOOR_P_X_ANA: p_floor_ana[0], AnalysisCols.FLOOR_P_Y_ANA: p_floor_ana[1], AnalysisCols.FLOOR_P_Z_ANA: p_floor_ana[2],
        }
        return pd.Series(result_data)

    def process(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        입력된 DataFrame의 모든 프레임에 대해 좌표계 변환을 수행합니다.
        """
        if df.empty or VelocityCols.COM_VX not in df.columns:
            return df

        transformed_data = df.apply(self.process_frame, axis=1)

        result_df = df.join(transformed_data)

        print(f"[FrameAnalyzer INFO] Processed {len(df)} frames.")
        return result_df
