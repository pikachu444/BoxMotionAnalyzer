import pandas as pd
import numpy as np
from scipy.interpolate import UnivariateSpline
from scipy.spatial.transform import Rotation as R
from typing import List, Dict, Any

def _ensure_quaternion_continuity(quaternions: np.ndarray) -> np.ndarray:
    q_proc = np.copy(quaternions)
    for i in range(1, len(q_proc)):
        if np.dot(q_proc[i-1], q_proc[i]) < 0:
            q_proc[i] *= -1
    return q_proc

class VelocityCalculator:
    """
    자세 데이터를 기반으로 강체의 병진 및 각속도를 계산합니다.
    """

    def __init__(self, method: str = 'spline', **kwargs):
        self.method = method
        self.params = kwargs

    def _calculate_translational_velocity(self, df: pd.DataFrame, time_s: np.ndarray) -> pd.DataFrame:
        pos_cols = ['Box_Tx', 'Box_Ty', 'Box_Tz']
        vel_cols = ['CoM_Vx', 'CoM_Vy', 'CoM_Vz']

        for p_col, v_col in zip(pos_cols, vel_cols):
            series = df[p_col]
            if self.method == 'spline':
                s_factor = self.params.get('s_factor_pos', 0)
                k = self.params.get('spline_degree', 3)
                spl = UnivariateSpline(time_s, series, k=k, s=s_factor)
                df[v_col] = spl.derivative(n=1)(time_s)
            else:
                df[v_col] = np.gradient(series, time_s)
        return df

    def _calculate_angular_velocity(self, df: pd.DataFrame, time_s: np.ndarray) -> pd.DataFrame:
        rot_cols = ['Box_Rx', 'Box_Ry', 'Box_Rz']
        ang_vel_cols = ['AngVel_Wx', 'AngVel_Wy', 'AngVel_Wz']

        if not all(col in df.columns for col in rot_cols):
            for col in ang_vel_cols: df[col] = 0.0
            return df

        rot_vectors = df[rot_cols].values

        if self.method == 'spline':
            quats = R.from_rotvec(rot_vectors).as_quat()
            quats_continuous = _ensure_quaternion_continuity(quats)

            q_spline_t = np.zeros_like(quats_continuous)
            dq_dt_spline_t = np.zeros_like(quats_continuous)

            s_factor_rot = self.params.get('s_factor_rot', 0)
            k = self.params.get('spline_degree', 3)

            for i in range(4):
                spl = UnivariateSpline(time_s, quats_continuous[:, i], k=k, s=s_factor_rot)
                q_spline_t[:, i] = spl(time_s)
                dq_dt_spline_t[:, i] = spl.derivative(n=1)(time_s)

            angular_velocities_world = np.zeros((len(df), 3))
            for i in range(len(df)):
                q = q_spline_t[i]
                dq_dt = dq_dt_spline_t[i]
                w, x, y, z = q[3], q[0], q[1], q[2]
                dw, dx, dy, dz = dq_dt[3], dq_dt[0], dq_dt[1], dq_dt[2]

                omega_body_x = 2 * (-x*dw + w*dx + z*dy - y*dz)
                omega_body_y = 2 * (-y*dw - z*dx + w*dy + x*dz)
                omega_body_z = 2 * (-z*dw + y*dx - x*dy + w*dz)
                ang_vel_body = np.array([omega_body_x, omega_body_y, omega_body_z])

                angular_velocities_world[i] = R.from_quat(q).apply(ang_vel_body)

            df[ang_vel_cols] = angular_velocities_world
        else:
            for col in ang_vel_cols: df[col] = 0.0

        return df

    def process(self, df: pd.DataFrame) -> pd.DataFrame:
        if df.empty or 'Box_Tx' not in df.columns:
            return df

        result_df = df.copy()
        time_s = result_df.index.values.astype(float)

        result_df = self._calculate_translational_velocity(result_df, time_s)
        result_df = self._calculate_angular_velocity(result_df, time_s)

        print(f"[VelocityCalculator INFO] Processed {len(df)} frames.")
        return result_df
