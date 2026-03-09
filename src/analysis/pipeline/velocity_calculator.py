import pandas as pd
import numpy as np
from scipy.interpolate import UnivariateSpline
from scipy.spatial.transform import Rotation as R
from scipy.signal import butter, filtfilt
from src.config import config_analysis
from src.config import config_app
from src.config.data_columns import PoseCols, VelocityCols, CornerVelocityCols, CornerAccelerationCols

# --- Module-level Helper Functions ---

def _apply_butter_lowpass(series, cutoff, fs, order):
    """주어진 Series에 Butterworth 저대역 통과 필터를 적용합니다."""
    if fs <= 0 or not (0 < cutoff < 0.5 * fs): return series
    b, a = butter(order, cutoff / (0.5 * fs), btype='low', analog=False)
    series_nonan = series.interpolate(method='linear').fillna(method='ffill').fillna(method='bfill')
    if series_nonan.isna().any(): return series
    return filtfilt(b, a, series_nonan)

def _apply_moving_average(series, window):
    """주어진 Series에 이동 평균 필터를 적용합니다."""
    if window <= 1: return series
    return series.rolling(window=window, center=True, min_periods=1).mean()

def _numerical_derivative(y, t):
    """가변 시간 간격을 처리하는 유한 차분법으로 수치 미분을 계산합니다."""
    if len(y) < 2: return np.zeros_like(y)
    return np.gradient(y, t)

def _ensure_quaternion_continuity(quats):
    """쿼터니언 배열의 연속성을 보장하기 위해 부호를 플립합니다."""
    for i in range(1, len(quats)):
        if np.dot(quats[i-1], quats[i]) < 0:
            quats[i] *= -1
    return quats

class VelocityCalculator:
    def __init__(self):
        self.method = config_analysis.VELOCITY_CALCULATION_METHOD
        self.use_pose_lpf = config_analysis.USE_POSE_LOWPASS_FILTER
        self.pose_lpf_cutoff = config_analysis.POSE_LPF_CUTOFF_HZ
        self.pose_lpf_order = config_analysis.POSE_LPF_ORDER
        self.use_pose_ma = config_analysis.USE_POSE_MOVING_AVERAGE
        self.pose_ma_window = config_analysis.POSE_MA_WINDOW
        self.spline_s_pos = config_analysis.SPLINE_S_FACTOR_POSITION
        self.spline_s_rot = config_analysis.SPLINE_S_FACTOR_ROTATION
        self.spline_k = config_analysis.SPLINE_DEGREE
        self.use_vel_lpf = config_analysis.USE_VELOCITY_LOWPASS_FILTER
        self.vel_lpf_cutoff = config_analysis.VELOCITY_LPF_CUTOFF_HZ
        self.vel_lpf_order = config_analysis.VELOCITY_LPF_ORDER
        self.use_acc_lpf = config_analysis.USE_ACCELERATION_LOWPASS_FILTER
        self.acc_lpf_cutoff = config_analysis.ACCELERATION_LPF_CUTOFF_HZ
        self.acc_lpf_order = config_analysis.ACCELERATION_LPF_ORDER
        self.local_box_corners = config_app.LOCAL_BOX_CORNERS

    def _preprocess_pose_data(self, positions, quaternions, fs):
        if self.use_pose_lpf:
            for i in range(3): positions[:, i] = _apply_butter_lowpass(pd.Series(positions[:, i]), self.pose_lpf_cutoff, fs, self.pose_lpf_order)
            for i in range(4): quaternions[:, i] = _apply_butter_lowpass(pd.Series(quaternions[:, i]), self.pose_lpf_cutoff, fs, self.pose_lpf_order)
        if self.use_pose_ma:
            for i in range(3): positions[:, i] = _apply_moving_average(pd.Series(positions[:, i]), self.pose_ma_window)
            for i in range(4): quaternions[:, i] = _apply_moving_average(pd.Series(quaternions[:, i]), self.pose_ma_window)
        return positions, quaternions

    def _calculate_velocities(self, positions, quaternions, time_s):
        v_com = np.zeros_like(positions)
        if self.method == 'spline':
            for i in range(3):
                spl = UnivariateSpline(time_s, positions[:, i], k=self.spline_k, s=self.spline_s_pos)
                v_com[:, i] = spl.derivative(n=1)(time_s)
        else:
            for i in range(3):
                v_com[:, i] = _numerical_derivative(positions[:, i], time_s)

        ang_vel = np.zeros_like(positions)
        if self.method == 'spline':
            dq_dt = np.zeros_like(quaternions)
            for i in range(4):
                spl = UnivariateSpline(time_s, quaternions[:, i], k=self.spline_k, s=self.spline_s_rot)
                dq_dt[:, i] = spl.derivative(n=1)(time_s)
            for i in range(len(time_s)):
                q, dq = quaternions[i], dq_dt[i]
                w, x, y, z = q[3], q[0], q[1], q[2]
                dw, dx, dy, dz = dq[3], dq[0], dq[1], dq[2]
                ang_vel_body = 2 * np.array([-x*dw+w*dx+z*dy-y*dz, -y*dw-z*dx+w*dy+x*dz, -z*dw+y*dx-x*dy+w*dz])
                ang_vel[i] = R.from_quat(q).apply(ang_vel_body)
        else:
            rot_matrices = R.from_quat(quaternions).as_matrix()
            dR_dt = np.zeros_like(rot_matrices)
            for r, c in np.ndindex(3,3):
                dR_dt[:, r, c] = _numerical_derivative(rot_matrices[:, r, c], time_s)
            for i in range(len(time_s)):
                omega_skew = dR_dt[i] @ rot_matrices[i].T
                ang_vel[i] = [omega_skew[2,1], omega_skew[0,2], omega_skew[1,0]]
        return v_com, ang_vel

    def _postprocess_velocities(self, v_com, ang_vel, fs):
        if self.use_vel_lpf:
            for i in range(3):
                v_com[:, i] = _apply_butter_lowpass(pd.Series(v_com[:, i]), self.vel_lpf_cutoff, fs, self.vel_lpf_order)
                ang_vel[:, i] = _apply_butter_lowpass(pd.Series(ang_vel[:, i]), self.vel_lpf_cutoff, fs, self.vel_lpf_order)
        return v_com, ang_vel

    def _calculate_accelerations(self, v_com, ang_vel, time_s):
        a_com = np.zeros_like(v_com)
        ang_acc = np.zeros_like(ang_vel)

        if self.method == 'spline':
            for i in range(3):
                v_spl = UnivariateSpline(time_s, v_com[:, i], k=self.spline_k, s=self.spline_s_pos)
                w_spl = UnivariateSpline(time_s, ang_vel[:, i], k=self.spline_k, s=self.spline_s_rot)
                a_com[:, i] = v_spl.derivative(n=1)(time_s)
                ang_acc[:, i] = w_spl.derivative(n=1)(time_s)
        else:
            for i in range(3):
                a_com[:, i] = _numerical_derivative(v_com[:, i], time_s)
                ang_acc[:, i] = _numerical_derivative(ang_vel[:, i], time_s)

        return a_com, ang_acc

    def _postprocess_accelerations(self, a_com, ang_acc, fs):
        if self.use_acc_lpf:
            for i in range(3):
                a_com[:, i] = _apply_butter_lowpass(
                    pd.Series(a_com[:, i]), self.acc_lpf_cutoff, fs, self.acc_lpf_order
                )
                ang_acc[:, i] = _apply_butter_lowpass(
                    pd.Series(ang_acc[:, i]), self.acc_lpf_cutoff, fs, self.acc_lpf_order
                )
        return a_com, ang_acc

    def _calculate_corner_velocities(self, v_com, ang_vel, quaternions):
        """ legacy 코드와 동일하게, 모든 입력을 numpy 배열로 가정하고 계산합니다. """
        corner_velocities_data = {}
        rotations = R.from_quat(quaternions)
        for c_idx, r_local in enumerate(self.local_box_corners):
            # 브로드캐스팅을 활용한 벡터화 연산
            r_world_from_com = rotations.apply(r_local)
            corner_vel = v_com + np.cross(ang_vel, r_world_from_com)

            corner_velocities_data[f'C{c_idx + 1}{CornerVelocityCols.VX_SUFFIX}'] = corner_vel[:, 0]
            corner_velocities_data[f'C{c_idx + 1}{CornerVelocityCols.VY_SUFFIX}'] = corner_vel[:, 1]
            corner_velocities_data[f'C{c_idx + 1}{CornerVelocityCols.VZ_SUFFIX}'] = corner_vel[:, 2]
            corner_velocities_data[f'C{c_idx + 1}{CornerVelocityCols.NORM_SUFFIX}'] = np.linalg.norm(corner_vel, axis=1)
        return corner_velocities_data

    def _calculate_corner_accelerations(self, a_com, ang_vel, ang_acc, quaternions):
        corner_accelerations_data = {}
        rotations = R.from_quat(quaternions)
        for c_idx, r_local in enumerate(self.local_box_corners):
            r_world_from_com = rotations.apply(r_local)
            corner_acc = (
                a_com
                + np.cross(ang_acc, r_world_from_com)
                + np.cross(ang_vel, np.cross(ang_vel, r_world_from_com))
            )

            corner_accelerations_data[f'C{c_idx + 1}{CornerAccelerationCols.AX_SUFFIX}'] = corner_acc[:, 0]
            corner_accelerations_data[f'C{c_idx + 1}{CornerAccelerationCols.AY_SUFFIX}'] = corner_acc[:, 1]
            corner_accelerations_data[f'C{c_idx + 1}{CornerAccelerationCols.AZ_SUFFIX}'] = corner_acc[:, 2]
            corner_accelerations_data[f'C{c_idx + 1}{CornerAccelerationCols.NORM_SUFFIX}'] = np.linalg.norm(corner_acc, axis=1)
        return corner_accelerations_data

    def process(self, df: pd.DataFrame) -> pd.DataFrame:
        if df.empty or PoseCols.POS_X not in df.columns:
            return df

        print(f"[VelocityCalculator INFO] Starting velocity calculation using '{self.method}' method...")
        result_df = df.copy()
        time_s = result_df.index.values.astype(float)

        fs = 1.0 / np.mean(np.diff(time_s)) if len(time_s) > 1 else 0

        # DataFrame에서 numpy 배열 추출
        positions = result_df[[PoseCols.POS_X, PoseCols.POS_Y, PoseCols.POS_Z]].to_numpy(copy=True)
        rot_vectors = result_df[[PoseCols.ROT_X, PoseCols.ROT_Y, PoseCols.ROT_Z]].to_numpy(copy=True)
        quaternions = R.from_rotvec(rot_vectors).as_quat()
        quaternions = _ensure_quaternion_continuity(quaternions)

        # 파이프라인 실행
        positions, quaternions = self._preprocess_pose_data(positions, quaternions, fs)
        v_com, ang_vel = self._calculate_velocities(positions, quaternions, time_s)
        v_com, ang_vel = self._postprocess_velocities(v_com, ang_vel, fs)

        # 가속도 계산
        a_com, ang_acc = self._calculate_accelerations(v_com, ang_vel, time_s)
        a_com, ang_acc = self._postprocess_accelerations(a_com, ang_acc, fs)

        # Norm 계산
        com_v_norm = np.linalg.norm(v_com, axis=1)
        ang_w_norm = np.linalg.norm(ang_vel, axis=1)
        com_a_norm = np.linalg.norm(a_com, axis=1)
        ang_a_norm = np.linalg.norm(ang_acc, axis=1)

        # 결과를 numpy 배열로 DataFrame에 할당
        result_df[[VelocityCols.T_VX, VelocityCols.T_VY, VelocityCols.T_VZ]] = v_com
        result_df[[VelocityCols.R_VX, VelocityCols.R_VY, VelocityCols.R_VZ]] = ang_vel
        result_df[[VelocityCols.T_AX, VelocityCols.T_AY, VelocityCols.T_AZ]] = a_com
        result_df[[VelocityCols.R_AX, VelocityCols.R_AY, VelocityCols.R_AZ]] = ang_acc
        result_df[VelocityCols.T_V_NORM] = com_v_norm
        result_df[VelocityCols.R_V_NORM] = ang_w_norm
        result_df[VelocityCols.T_A_NORM] = com_a_norm
        result_df[VelocityCols.R_A_NORM] = ang_a_norm

        # numpy 배열을 사용하여 꼭짓점 속도 계산
        corner_velocities = self._calculate_corner_velocities(v_com, ang_vel, quaternions)
        corner_accelerations = self._calculate_corner_accelerations(a_com, ang_vel, ang_acc, quaternions)

        # 계산된 꼭짓점 속도를 DataFrame에 추가
        for col, data in corner_velocities.items():
            result_df[col] = data
        for col, data in corner_accelerations.items():
            result_df[col] = data

        # 컬럼 순서 재배치
        # 기존 컬럼 순서를 유지하되, norm 컬럼들을 각 벡터의 xyz 성분 뒤로 이동
        cols = result_df.columns.tolist()
        # COM_V_NORM 이동
        cols.remove(VelocityCols.T_V_NORM)
        cols.insert(cols.index(VelocityCols.T_VZ) + 1, VelocityCols.T_V_NORM)
        # ANG_W_NORM 이동
        cols.remove(VelocityCols.R_V_NORM)
        cols.insert(cols.index(VelocityCols.R_VZ) + 1, VelocityCols.R_V_NORM)
        # COM_A_NORM 이동
        cols.remove(VelocityCols.T_A_NORM)
        cols.insert(cols.index(VelocityCols.T_AZ) + 1, VelocityCols.T_A_NORM)
        # ANG_A_NORM 이동
        cols.remove(VelocityCols.R_A_NORM)
        cols.insert(cols.index(VelocityCols.R_AZ) + 1, VelocityCols.R_A_NORM)
        result_df = result_df[cols]

        print(f"[VelocityCalculator INFO] Finished processing {len(df)} frames.")
        return result_df
