import pandas as pd
from PySide6.QtCore import QObject, Signal
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from scipy.signal import butter, filtfilt
from scipy.spatial.transform import Rotation
from scipy.interpolate import UnivariateSpline
import numpy as np
import config

class PipelineController(QObject):
    """
    전체 데이터 분석 워크플로우를 제어하고, GUI와 백엔드 로직을 연결합니다.
    """
    log_message = Signal(str)
    analysis_finished = Signal(pd.DataFrame)

    def __init__(self):
        super().__init__()
        # 나중에 AnalysisConfig 객체를 통해 받아오도록 수정
        self.box_dims = config.BOX_DIMS
        self.local_box_corners = config.LOCAL_BOX_CORNERS

    def run_analysis(self, config, raw_data: pd.DataFrame):
        """
        분석 파이프라인을 순차적으로 실행하는 메인 메서드.
        """
        try:
            self.log_message.emit("[1/3] 데이터 슬라이싱 시작...")
            sliced_data = self._slice(raw_data, config['slice_time_start'], config['slice_time_end'])
            self.log_message.emit("...완료.")

            self.log_message.emit("[2/3] 데이터 스무딩 시작...")
            smoothed_data = self._smooth(sliced_data)
            self.log_message.emit("...완료.")

            self.log_message.emit("[3/3] 운동학 계산 시작...")
            final_result = self._calculate_kinematics(smoothed_data)
            self.log_message.emit("...완료.")

            self.log_message.emit("모든 분석이 성공적으로 완료되었습니다.")
            self.analysis_finished.emit(final_result)

        except Exception as e:
            import traceback
            traceback.print_exc()
            self.log_message.emit(f"[에러] 분석 중 오류 발생: {e}")
            self.analysis_finished.emit(pd.DataFrame())

    def _slice(self, data: pd.DataFrame, start_time: float, end_time: float) -> pd.DataFrame:
        """데이터를 주어진 시간 범위로 자릅니다."""
        self.log_message.emit(f"    {start_time:.2f}초 부터 {end_time:.2f}초 까지 슬라이싱...")
        return data.loc[start_time:end_time].copy()

    def _calculate_fs(self, time_series: pd.Series) -> float:
        """시간 데이터로부터 샘플링 주파수를 계산합니다."""
        return 1.0 / time_series.diff().mean()

    def _smooth(self, data: pd.DataFrame) -> pd.DataFrame:
        """데이터에 Butterworth 로우패스 필터를 적용합니다."""
        self.log_message.emit("    Butterworth 필터 적용...")

        smoothed_data = data.copy()
        fs = self._calculate_fs(smoothed_data.index.to_series())

        cutoff_freq = 10.0
        filter_order = 4

        if fs <= 0 or not (0 < cutoff_freq < 0.5 * fs):
            self.log_message.emit(f"    [경고] 유효하지 않은 주파수 설정 (fs={fs:.2f}, cutoff={cutoff_freq:.2f}). 스무딩을 건너뜁니다.")
            return data

        b, a = butter(filter_order, cutoff_freq / (0.5 * fs), btype='low')

        for col in smoothed_data.columns:
            if col.endswith(('_X', '_Y', '_Z')):
                series = smoothed_data[col].interpolate().fillna(method='bfill').fillna(method='ffill')
                if len(series) > 3 * (filter_order + 1):
                    smoothed_data[col] = filtfilt(b, a, series.values)

        return smoothed_data

    def _calculate_kinematics(self, data: pd.DataFrame) -> pd.DataFrame:
        """자세, 속도 등 운동학적 계산을 수행합니다."""
        self.log_message.emit(f"    박스 규격 {self.box_dims} 적용하여 계산...")

        result_df = data.copy()
        time_s = result_df.index.values.astype(float)

        main_body_name = [col.replace('_X', '') for col in data.columns if '_X' in col and ':' not in col]
        if not main_body_name:
            self.log_message.emit("[에러] 주요 강체(Rigid Body) 데이터를 찾을 수 없습니다.")
            return pd.DataFrame()
        main_body_name = main_body_name[0]

        positions = result_df[[f'{main_body_name}_X', f'{main_body_name}_Y', f'{main_body_name}_Z']].values
        rotations = Rotation.from_quat(np.tile([0, 0, 0, 1], (len(result_df), 1)))

        trans_vel = np.zeros_like(positions)
        for i in range(3):
            spl = UnivariateSpline(time_s, positions[:, i], s=0)
            trans_vel[:, i] = spl.derivative(n=1)(time_s)

        result_df['CoM_Vx'] = trans_vel[:, 0]
        result_df['CoM_Vy'] = trans_vel[:, 1]
        result_df['CoM_Vz'] = trans_vel[:, 2]

        angular_vel = np.zeros_like(positions)
        result_df['AngVel_Wx'] = angular_vel[:, 0]
        result_df['AngVel_Wy'] = angular_vel[:, 1]
        result_df['AngVel_Wz'] = angular_vel[:, 2]

        for c_idx, corner_local in enumerate(self.local_box_corners):
            r_world_from_com = rotations.apply(corner_local)
            corner_vel = trans_vel + np.cross(angular_vel, r_world_from_com)
            result_df[f'C{c_idx}_Vx'] = corner_vel[:, 0]
            result_df[f'C{c_idx}_Vy'] = corner_vel[:, 1]
            result_df[f'C{c_idx}_Vz'] = corner_vel[:, 2]

        return result_df
