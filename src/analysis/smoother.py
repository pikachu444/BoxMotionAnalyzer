import pandas as pd
import numpy as np
from scipy.signal import butter, filtfilt
from typing import List

from config.data_columns import RawMarkerCols


class MarkerSmoother:
    """
    DataFrame에 포함된 마커 데이터에 스무딩 필터를 적용합니다.
    """

    def __init__(self, method_sequence: List[str] = ['butterworth'],
                 cutoff_freq: float = 10.0, order: int = 4,
                 ma_window: int = 3):
        """
        MarkerSmoother를 초기화합니다.

        Args:
            method_sequence (List[str]): 적용할 스무딩 방법의 순서.
            cutoff_freq (float): Butterworth 필터의 컷오프 주파수 (Hz).
            order (int): Butterworth 필터의 차수.
            ma_window (int): 이동 평균 필터의 윈도우 크기.
        """
        self.method_sequence = method_sequence
        self.cutoff_freq = cutoff_freq
        self.order = order
        self.ma_window = ma_window

    def _calculate_fs(self, time_series: pd.Series) -> float:
        """시간 Series로부터 평균 샘플링 주파수를 계산합니다."""
        if len(time_series) < 2: return 0.0
        time_diffs = time_series.diff().dropna()
        if time_diffs.empty or (time_diffs <= 0).any(): return 0.0
        return 1.0 / time_diffs.mean()

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
                b, a = butter(self.order, self.cutoff_freq / (0.5 * fs), btype='low')
                smoothed = pd.Series(filtfilt(b, a, smoothed.values), index=series.index, name=series.name)
            elif method == 'moving_average':
                if self.ma_window <= 1: continue
                smoothed = smoothed.rolling(window=self.ma_window, center=True, min_periods=1).mean()

        return smoothed

    def process(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        입력된 DataFrame의 모든 마커 데이터에 스무딩을 적용합니다.
        """
        if df.empty:
            return df

        smoothed_df = df.copy()
        fs = self._calculate_fs(smoothed_df.index.to_series())

        marker_cols = [col for col in df.columns if col.endswith((RawMarkerCols.X_SUFFIX, RawMarkerCols.Y_SUFFIX, RawMarkerCols.Z_SUFFIX))]

        for col_name in marker_cols:
            series_to_smooth = pd.to_numeric(df[col_name], errors='coerce')
            if series_to_smooth.isna().all():
                continue

            smoothed_series = self._apply_smoothing(series_to_smooth, fs)
            smoothed_df[col_name] = smoothed_series

        print(f"[MarkerSmoother INFO] Smoothed {len(marker_cols)} marker columns.")
        return smoothed_df
