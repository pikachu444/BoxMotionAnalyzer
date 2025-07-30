import pandas as pd
import numpy as np
from scipy.interpolate import UnivariateSpline
from scipy.spatial.transform import Rotation as R
from scipy.signal import butter, filtfilt
from src.config import config_analysis, app_config
from src.config.data_columns import PoseCols, VelocityCols, CornerVelocityCols

# --- Module-level Helper Functions ---

def _apply_butter_lowpass(series, cutoff, fs, order):
    """주어진 Series에 Butterworth 저대역 통과 필터를 적용합니다."""
    if fs <= 0 or not (0 < cutoff < 0.5 * fs): return series
    b, a = butter(order, cutoff / (0.5 * fs), btype='low', analog=False)
    # NaN 값 보간 후 필터링
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
    """
    자세 데이터를 기반으로 강체의 병진 및 각속도를 계산합니다.
    Pose 데이터 전처리, 속도 계산, 속도 후처리, 꼭짓점 속도 계산의 전체 파이프라인을 포함합니다.
    """
    def __init__(self):
        """
        설정 파일(config_analysis.py)에서 모든 파라미터를 로드하여 초기화합니다.
        """
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
        self.local_box_corners = app_config.LOCAL_BOX_CORNERS

    def _preprocess_pose_data(self, positions, quaternions, fs):
        """Pose 데이터(위치, 쿼터니언)에 필터와 스무딩을 적용합니다."""
        if self.use_pose_lpf:
            for i in range(3): positions[:, i] = _apply_butter_lowpass(pd.Series(positions[:, i]), self.pose_lpf_cutoff, fs, self.pose_lpf_order)
            for i in range(4): quaternions[:, i] = _apply_butter_lowpass(pd.Series(quaternions[:, i]), self.pose_lpf_cutoff, fs, self.pose_lpf_order)

        if self.use_pose_ma:
            for i in range(3): positions[:, i] = _apply_moving_average(pd.Series(positions[:, i]), self.pose_ma_window)
            for i in range(4): quaternions[:, i] = _apply_moving_average(pd.Series(quaternions[:, i]), self.pose_ma_window)

        return positions, quaternions

    def _calculate_velocities(self, positions, quaternions, time_s):
        """전처리된 Pose 데이터로부터 병진 및 각속도를 계산합니다."""
        # 병진 속도
        v_com = np.zeros_like(positions)
        if self.method == 'spline':
            for i in range(3):
                spl = UnivariateSpline(time_s, positions[:, i], k=self.spline_k, s=self.spline_s_pos)
                v_com[:, i] = spl.derivative(n=1)(time_s)
        else: # finite_difference
            for i in range(3):
                v_com[:, i] = _numerical_derivative(positions[:, i], time_s)

        # 각속도
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
        else: # finite_difference
            rot_matrices = R.from_quat(quaternions).as_matrix()
            dR_dt = np.zeros_like(rot_matrices)
            for r, c in np.ndindex(3,3):
                dR_dt[:, r, c] = _numerical_derivative(rot_matrices[:, r, c], time_s)
            for i in range(len(time_s)):
                omega_skew = dR_dt[i] @ rot_matrices[i].T
                ang_vel[i] = [omega_skew[2,1], omega_skew[0,2], omega_skew[1,0]]

        return v_com, ang_vel

    def _postprocess_velocities(self, v_com, ang_vel, fs):
        """계산된 속도 데이터에 저대역 통과 필터를 적용합니다."""
        if self.use_vel_lpf:
            for i in range(3):
                v_com[:, i] = _apply_butter_lowpass(pd.Series(v_com[:, i]), self.vel_lpf_cutoff, fs, self.vel_lpf_order)
                ang_vel[:, i] = _apply_butter_lowpass(pd.Series(ang_vel[:, i]), self.vel_lpf_cutoff, fs, self.vel_lpf_order)
        return v_com, ang_vel

    def _calculate_corner_velocities(self, v_com, ang_vel, quaternions):
        """최종 속도와 자세를 바탕으로 박스 꼭짓점의 속도를 계산합니다."""
        corner_velocities = {}
        rotations = R.from_quat(quaternions)
        for c_idx, r_local in enumerate(self.local_box_corners):
            r_world = rotations.apply(r_local)
            corner_vel = v_com + np.cross(ang_vel, r_world)
            corner_velocities[f'C{c_idx}{CornerVelocityCols.VX_SUFFIX}'] = corner_vel[:, 0]
            corner_velocities[f'C{c_idx}{CornerVelocityCols.VY_SUFFIX}'] = corner_vel[:, 1]
            corner_velocities[f'C{c_idx}{CornerVelocityCols.VZ_SUFFIX}'] = corner_vel[:, 2]
        return pd.DataFrame(corner_velocities, index=v_com.index)

    def process(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        전체 속도 계산 파이프라인을 실행합니다.

        1. Pose 데이터 전처리
        2. 병진 및 각속도 계산
        3. 계산된 속도 후처리
        4. 꼭짓점 속도 계산 및 DataFrame에 추가
        """
        if df.empty or PoseCols.POS_X not in df.columns:
            return df

        print(f"[VelocityCalculator INFO] Starting velocity calculation using '{self.method}' method...")
        result_df = df.copy()
        time_s = result_df.index.values.astype(float)

        fs = 1.0 / np.mean(np.diff(time_s)) if len(time_s) > 1 else 0

        # 데이터 준비
        positions = result_df[[PoseCols.POS_X, PoseCols.POS_Y, PoseCols.POS_Z]].values
        quaternions = R.from_rotvec(result_df[[PoseCols.ROT_X, PoseCols.ROT_Y, PoseCols.ROT_Z]].values).as_quat()
        quaternions = _ensure_quaternion_continuity(quaternions)

        # 파이프라인 실행
        positions, quaternions = self._preprocess_pose_data(positions, quaternions, fs)
        v_com, ang_vel = self._calculate_velocities(positions, quaternions, time_s)
        v_com, ang_vel = self._postprocess_velocities(v_com, ang_vel, fs)

        # 결과 DataFrame에 추가
        result_df[[VelocityCols.COM_VX, VelocityCols.COM_VY, VelocityCols.COM_VZ]] = v_com
        result_df[[VelocityCols.ANG_WX, VelocityCols.ANG_WY, VelocityCols.ANG_WZ]] = ang_vel

        # DataFrame 인덱스를 사용하여 꼭짓점 속도 계산
        v_com_df = pd.DataFrame(v_com, index=result_df.index)
        ang_vel_df = pd.DataFrame(ang_vel, index=result_df.index)
        quaternions_df = pd.DataFrame(quaternions, index=result_df.index)
        corner_velocities_df = self._calculate_corner_velocities(v_com_df, ang_vel_df, quaternions_df)

        result_df = result_df.join(corner_velocities_df)

        print(f"[VelocityCalculator INFO] Finished processing {len(df)} frames.")
        return result_df
