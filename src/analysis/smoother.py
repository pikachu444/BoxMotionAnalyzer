import pandas as pd
import numpy as np
from scipy.signal import butter, filtfilt
from ..config import config_analysis
from ..config.data_columns import RawMarkerCols

class MarkerSmoother:
    """
    DataFrame에 포함된 마커 데이터에 스무딩 필터를 적용합니다.
    src/legacy/SmoothMarkerData.py의 핵심 로직을 이식한 것입니다.
    """

    def __init__(self):
        """
        MarkerSmoother를 초기화합니다.
        설정값은 config/config_analysis.py에서 가져옵니다.
        """
        self.method_sequence = config_analysis.SMOOTHING_METHOD_SEQUENCE
        self.cutoff_freq = config_analysis.BUTTERWORTH_CUTOFF_FREQ_HZ
        self.order = config_analysis.BUTTERWORTH_ORDER
        self.ma_window = config_analysis.MA_WINDOW_SIZE

    def _calculate_fs(self, time_series: pd.Series) -> float:
        """시간 Series로부터 평균 샘플링 주파수를 계산합니다."""
        if len(time_series) < 2: return 0.0
        time_diffs = time_series.diff().dropna()
        if time_diffs.empty or (time_diffs <= 0).any(): return 0.0
        mean_delta_t = time_diffs.mean()
        if mean_delta_t <= 1e-9: return 0.0
        return 1.0 / mean_delta_t

    def _apply_smoothing(self, series: pd.Series, fs: float) -> pd.Series:
        """단일 데이터 Series에 설정된 스무딩 필터들을 순차적으로 적용합니다."""
        smoothed = series.copy()

        if smoothed.isna().any():
            smoothed = smoothed.interpolate(method='linear').fillna(method='ffill').fillna(method='bfill')
            if smoothed.isna().any(): return series

        for method in self.method_sequence:
            if method == 'butterworth':
                if fs <= 0 or not (0 < self.cutoff_freq < 0.5 * fs): continue
                if len(smoothed) <= 3 * (self.order + 1): continue

                nyquist_freq = 0.5 * fs
                wn = self.cutoff_freq / nyquist_freq
                try:
                    b, a = butter(self.order, wn, btype='low', analog=False)
                    filtered_values = filtfilt(b, a, smoothed.astype(np.float64).values)
                    smoothed = pd.Series(filtered_values, index=series.index, name=series.name)
                except ValueError:
                    continue # 오류 발생 시 원본 데이터 유지

            elif method == 'moving_average':
                if self.ma_window <= 1 or len(smoothed) < self.ma_window: continue
                smoothed = smoothed.rolling(window=self.ma_window, center=True, min_periods=1).mean()

        return smoothed

    def process(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        입력된 DataFrame의 모든 마커 데이터에 스무딩을 적용합니다.
        """
        if df.empty:
            return df

        smoothed_df = df.copy()

        # 'Time' 인덱스로부터 샘플링 주파수 계산
        fs = self._calculate_fs(pd.Series(smoothed_df.index))
        if fs <= 0:
            print("[MarkerSmoother WARNING] 유효한 샘플링 주파수를 계산할 수 없어 스무딩을 건너뜁니다.")
            return df

        marker_cols = [col for col in df.columns if col.endswith((RawMarkerCols.X_SUFFIX, RawMarkerCols.Y_SUFFIX, RawMarkerCols.Z_SUFFIX))]

        for col_name in marker_cols:
            series_to_smooth = pd.to_numeric(df[col_name], errors='coerce')
            if series_to_smooth.isna().all():
                continue

            smoothed_series = self._apply_smoothing(series_to_smooth, fs)
            smoothed_df[col_name] = smoothed_series

        print(f"[MarkerSmoother INFO] Smoothed {len(marker_cols)} marker columns using {self.method_sequence}.")
        return smoothed_df
