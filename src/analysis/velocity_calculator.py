import pandas as pd
import numpy as np
from scipy.interpolate import UnivariateSpline
from scipy.spatial.transform import Rotation as R

from src.config.data_columns import PoseCols, VelocityCols


# --- Helper Functions (Module-level) ---

def _ensure_quaternion_continuity(quaternions: np.ndarray) -> np.ndarray:
    """쿼터니언의 연속성을 보장하기 위해 부호를 플립합니다 (SciPy 형식: [x,y,z,w])."""
    q_proc = np.copy(quaternions)
    for i in range(1, len(q_proc)):
        if np.dot(q_proc[i-1], q_proc[i]) < 0:
            q_proc[i] *= -1
    return q_proc

def _numerical_derivative_finite_diff(y_values: np.ndarray, t_values: np.ndarray) -> np.ndarray:
    """가변 dt를 처리하는 유한 차분법을 사용하여 수치 미분을 계산합니다."""
    if len(y_values) != len(t_values): raise ValueError("y/t length mismatch.")
    if len(y_values) < 2: return np.zeros_like(y_values, dtype=float)

    y_np = np.asarray(y_values)
    t_np = t_values.astype(float)
    dy_dt = np.zeros_like(y_np, dtype=float)

    # Forward difference for the first element
    dt_0 = t_np[1] - t_np[0]
    dy_dt[0] = (y_np[1] - y_np[0]) / dt_0 if dt_0 > 1e-9 else 0.0

    # Central difference for interior elements
    for i in range(1, len(y_np) - 1):
        den = t_np[i+1] - t_np[i-1]
        if abs(den) > 1e-9:
            dy_dt[i] = (y_np[i+1] - y_np[i-1]) / den
        else: # Fallback for duplicate time values
            dt_f = t_np[i+1] - t_np[i]
            dy_dt[i] = (y_np[i+1] - y_np[i]) / dt_f if dt_f > 1e-9 else 0.0

    # Backward difference for the last element
    if len(y_np) > 1:
        dt_N = t_np[-1] - t_np[-2]
        dy_dt[-1] = (y_np[-1] - y_np[-2]) / dt_N if dt_N > 1e-9 else 0.0

    return dy_dt

def _calculate_angular_velocity_quaternion_based_fd(rot_vectors_rad: np.ndarray, time_s: np.ndarray) -> np.ndarray:
    """쿼터니언 미분을 사용하여 유한 차분 기반의 각속도(월드 좌표계)를 계산합니다."""
    num_frames = len(rot_vectors_rad)
    angular_velocities_world = np.zeros((num_frames, 3))
    if num_frames < 2: return angular_velocities_world

    quaternions_scipy = R.from_rotvec(rot_vectors_rad).as_quat()
    continuous_quaternions = _ensure_quaternion_continuity(quaternions_scipy)

    dq_dt_scipy = np.zeros_like(continuous_quaternions)
    for k_comp in range(4):
        dq_dt_scipy[:, k_comp] = _numerical_derivative_finite_diff(continuous_quaternions[:, k_comp], time_s)

    for i in range(num_frames):
        q_i = continuous_quaternions[i]
        dq_dt_i = dq_dt_scipy[i]
        w, x, y, z = q_i[3], q_i[0], q_i[1], q_i[2]
        dw, dx, dy, dz = dq_dt_i[3], dq_dt_i[0], dq_dt_i[1], dq_dt_i[2]

        omega_body_x = 2 * (-x*dw + w*dx + z*dy - y*dz)
        omega_body_y = 2 * (-y*dw - z*dx + w*dy + x*dz)
        omega_body_z = 2 * (-z*dw + y*dx - x*dy + w*dz)
        ang_vel_body = np.array([omega_body_x, omega_body_y, omega_body_z])

        try:
            R_i = R.from_quat(q_i)
            angular_velocities_world[i] = R_i.apply(ang_vel_body)
        except ValueError:
            angular_velocities_world[i] = np.zeros(3)

    return angular_velocities_world

# --- Main Class ---

class VelocityCalculator:
    """
    자세 데이터를 기반으로 강체의 병진 및 각속도를 계산합니다.
    'spline' 또는 'finite_difference' 방법을 지원합니다.
    """

    def __init__(self, method: str = 'spline', **kwargs):
        if method not in ['spline', 'finite_difference']:
            raise ValueError("Method must be one of 'spline' or 'finite_difference'")
        self.method = method
        self.params = kwargs

    def _calculate_translational_velocity(self, df: pd.DataFrame, time_s: np.ndarray) -> pd.DataFrame:
        pos_cols = [PoseCols.POS_X, PoseCols.POS_Y, PoseCols.POS_Z]
        vel_cols = [VelocityCols.COM_VX, VelocityCols.COM_VY, VelocityCols.COM_VZ]

        for p_col, v_col in zip(pos_cols, vel_cols):
            series = df[p_col]
            if self.method == 'spline':
                s_factor = self.params.get('s_factor_pos', 0)
                k = self.params.get('spline_degree', 3)
                spl = UnivariateSpline(time_s, series, k=k, s=s_factor)
                df[v_col] = spl.derivative(n=1)(time_s)
            elif self.method == 'finite_difference':
                df[v_col] = _numerical_derivative_finite_diff(series.values, time_s)
        return df

    def _calculate_angular_velocity(self, df: pd.DataFrame, time_s: np.ndarray) -> pd.DataFrame:
        rot_cols = [PoseCols.ROT_X, PoseCols.ROT_Y, PoseCols.ROT_Z]
        ang_vel_cols = [VelocityCols.ANG_WX, VelocityCols.ANG_WY, VelocityCols.ANG_WZ]

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

        elif self.method == 'finite_difference':
            df[ang_vel_cols] = _calculate_angular_velocity_quaternion_based_fd(rot_vectors, time_s)

        return df

    def process(self, df: pd.DataFrame) -> pd.DataFrame:
        if df.empty or PoseCols.POS_X not in df.columns:
            return df

        print(f"[VelocityCalculator INFO] Starting velocity calculation using '{self.method}' method...")

        result_df = df.copy()
        time_s = result_df.index.values.astype(float)

        result_df = self._calculate_translational_velocity(result_df, time_s)
        result_df = self._calculate_angular_velocity(result_df, time_s)

        print(f"[VelocityCalculator INFO] Finished processing {len(df)} frames.")
        return result_df
