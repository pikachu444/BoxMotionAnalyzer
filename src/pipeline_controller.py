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
        Runs the analysis pipeline sequentially.
        """
        try:
            self.log_message.emit("[1/3] Slicing data...")
            sliced_data = self._slice(raw_data, config['slice_time_start'], config['slice_time_end'])
            self.log_message.emit("...Done.")

            self.log_message.emit("[2/3] Smoothing data...")
            smoothed_data = self._smooth(sliced_data)
            self.log_message.emit("...Done.")

            self.log_message.emit("[3/3] Calculating kinematics...")
            final_result = self._calculate_kinematics(smoothed_data)
            self.log_message.emit("...Done.")

            self.log_message.emit("All analysis steps completed successfully.")
            self.analysis_finished.emit(final_result)

        except Exception as e:
            import traceback
            traceback.print_exc()
            self.log_message.emit(f"[ERROR] An error occurred during analysis: {e}")
            self.analysis_finished.emit(pd.DataFrame())

    def _slice(self, data: pd.DataFrame, start_time: float, end_time: float) -> pd.DataFrame:
        """Slices the data to the given time range."""
        self.log_message.emit(f"    Slicing from {start_time:.2f}s to {end_time:.2f}s...")
        return data.loc[start_time:end_time].copy()

    def _calculate_fs(self, time_series: pd.Series) -> float:
        """Calculates sampling frequency from a time series."""
        return 1.0 / time_series.diff().mean()

    def _smooth(self, data: pd.DataFrame) -> pd.DataFrame:
        """Applies a Butterworth low-pass filter to the data."""
        self.log_message.emit("    Applying Butterworth filter...")

        smoothed_data = data.copy()
        fs = self._calculate_fs(smoothed_data.index.to_series())

        cutoff_freq = 10.0
        filter_order = 4

        if fs <= 0 or not (0 < cutoff_freq < 0.5 * fs):
            self.log_message.emit(f"    [WARNING] Invalid frequency settings (fs={fs:.2f}, cutoff={cutoff_freq:.2f}). Skipping smoothing.")
            return data

        b, a = butter(filter_order, cutoff_freq / (0.5 * fs), btype='low')

        for col in smoothed_data.columns:
            if col.endswith(('_X', '_Y', '_Z')):
                series = smoothed_data[col].interpolate().fillna(method='bfill').fillna(method='ffill')
                if len(series) > 3 * (filter_order + 1):
                    smoothed_data[col] = filtfilt(b, a, series.values)

        return smoothed_data

    def _calculate_kinematics(self, data: pd.DataFrame) -> pd.DataFrame:
        """Calculates kinematics like pose and velocity."""
        self.log_message.emit(f"    Calculating with box dimensions {self.box_dims}...")

        result_df = data.copy()
        time_s = result_df.index.values.astype(float)

        main_body_name = [col.replace('_X', '') for col in data.columns if '_X' in col and ':' not in col]
        if not main_body_name:
            self.log_message.emit("[ERROR] Could not find main Rigid Body data.")
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
