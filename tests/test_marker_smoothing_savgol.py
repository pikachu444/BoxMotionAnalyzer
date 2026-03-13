import unittest

import numpy as np
import pandas as pd

from src.analysis.pipeline.resampling_options import build_effective_analysis_options
from src.analysis.pipeline.smoother import MarkerSmoother


class TestMarkerSmoothingSavitzkyGolay(unittest.TestCase):
    @staticmethod
    def _make_impulse_like_signal():
        dt = 0.002
        time = np.arange(0.0, 1.0, dt)
        peak_1 = 0.30
        peak_2 = 0.34
        sigma = 0.006

        signal = (
            1.0 * np.exp(-((time - peak_1) ** 2) / (2 * sigma**2))
            + 0.8 * np.exp(-((time - peak_2) ** 2) / (2 * sigma**2))
        )

        # Add deterministic high-frequency noise to mimic marker jitter.
        noise = 0.05 * np.sin(2 * np.pi * 60.0 * time) + 0.02 * np.cos(2 * np.pi * 85.0 * time)
        df = pd.DataFrame({"Corner1_X": signal + noise}, index=time)
        return df, peak_1, peak_2

    @staticmethod
    def _peak_time_in_window(series: pd.Series, start: float, end: float) -> float:
        window = series[(series.index >= start) & (series.index <= end)]
        if window.empty:
            raise AssertionError("Peak search window is empty.")
        return float(window.idxmax())

    def test_resampling_scales_savgol_window_length(self):
        analysis_options = {
            "marker_savgol_window_length": 7,
            "marker_moving_average_window": 3,
        }

        result = build_effective_analysis_options(analysis_options, 4)

        self.assertEqual(result["marker_savgol_window_length"], 28)
        self.assertEqual(result["marker_moving_average_window"], 12)

    def test_savgol_path_runs_and_preserves_peak_spacing_better_than_low_cutoff_butterworth(self):
        df, peak_1, peak_2 = self._make_impulse_like_signal()
        expected_spacing = peak_2 - peak_1

        smoother = MarkerSmoother()

        butterworth_options = {
            "enable_marker_smoothing": True,
            "marker_smoothing_method_sequence": ["butterworth"],
            "marker_butterworth_cutoff_hz": 3.0,
            "marker_butterworth_order": 4,
        }
        savgol_options = {
            "enable_marker_smoothing": True,
            "marker_smoothing_method_sequence": ["savitzky_golay"],
            "marker_savgol_window_length": 11,
            "marker_savgol_polyorder": 3,
        }

        smoother.configure(butterworth_options)
        butterworth_df = smoother.process(df)

        smoother.configure(savgol_options)
        savgol_df = smoother.process(df)

        self.assertFalse(butterworth_df["Corner1_X"].isna().any())
        self.assertFalse(savgol_df["Corner1_X"].isna().any())

        raw_series = df["Corner1_X"]
        butterworth_series = butterworth_df["Corner1_X"]
        savgol_series = savgol_df["Corner1_X"]

        raw_spacing = self._peak_time_in_window(raw_series, 0.27, 0.32)
        raw_spacing = self._peak_time_in_window(raw_series, 0.32, 0.37) - raw_spacing
        butterworth_spacing = self._peak_time_in_window(butterworth_series, 0.27, 0.32)
        butterworth_spacing = self._peak_time_in_window(butterworth_series, 0.32, 0.37) - butterworth_spacing
        savgol_spacing = self._peak_time_in_window(savgol_series, 0.27, 0.32)
        savgol_spacing = self._peak_time_in_window(savgol_series, 0.32, 0.37) - savgol_spacing

        self.assertAlmostEqual(raw_spacing, expected_spacing, delta=0.004)
        self.assertLess(
            abs(savgol_spacing - expected_spacing),
            abs(butterworth_spacing - expected_spacing),
        )


if __name__ == "__main__":
    unittest.main()
