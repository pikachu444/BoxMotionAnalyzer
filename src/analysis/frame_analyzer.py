import pandas as pd
import numpy as np
from scipy.spatial.transform import Rotation as R
from typing import Dict, Any

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
            T_box_lab = frame_row[['Box_Tx', 'Box_Ty', 'Box_Tz']].values.astype(float)
            rv_box_lab = frame_row[['Box_Rx', 'Box_Ry', 'Box_Rz']].values.astype(float)
            v_com_lab = frame_row[['CoM_Vx', 'CoM_Vy', 'CoM_Vz']].values.astype(float)
            omega_w_lab = frame_row[['AngVel_Wx', 'AngVel_Wy', 'AngVel_Wz']].values.astype(float)
        except (KeyError, ValueError):
            return pd.Series(dtype=object)

        R_lab_to_ana = R.from_rotvec(rv_box_lab).as_matrix().T

        v_com_ana = R_lab_to_ana @ v_com_lab
        omega_ana = R_lab_to_ana @ omega_w_lab

        n_floor_lab, p_floor_lab = self._get_lab_floor_params()
        n_floor_ana = R_lab_to_ana @ n_floor_lab
        p_floor_ana = R_lab_to_ana @ (p_floor_lab - T_box_lab)

        result_data = {
            'CoM_Vx_Ana': v_com_ana[0], 'CoM_Vy_Ana': v_com_ana[1], 'CoM_Vz_Ana': v_com_ana[2],
            'AngVel_Wx_Ana': omega_ana[0], 'AngVel_Wy_Ana': omega_ana[1], 'AngVel_Wz_Ana': omega_ana[2],
            'Floor_N_X_Ana': n_floor_ana[0], 'Floor_N_Y_Ana': n_floor_ana[1], 'Floor_N_Z_Ana': n_floor_ana[2],
            'Floor_P_X_Ana': p_floor_ana[0], 'Floor_P_Y_Ana': p_floor_ana[1], 'Floor_P_Z_Ana': p_floor_ana[2],
        }
        return pd.Series(result_data)

    def process(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        입력된 DataFrame의 모든 프레임에 대해 좌표계 변환을 수행합니다.
        """
        if df.empty or 'CoM_Vx' not in df.columns:
            return df

        transformed_data = df.apply(self.process_frame, axis=1)

        result_df = df.join(transformed_data)

        print(f"[FrameAnalyzer INFO] Processed {len(df)} frames.")
        return result_df
