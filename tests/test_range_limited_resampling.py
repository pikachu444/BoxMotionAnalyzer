import unittest

import numpy as np
import pandas as pd

from src.analysis.pipeline.resampler import UniformResampler
from src.config.data_columns import TimeCols

try:
    from src.analysis.pipeline.pipeline_controller import PipelineController
    HAS_QT = True
except ModuleNotFoundError:
    PipelineController = object
    HAS_QT = False


class _DeterministicRangeController(PipelineController):
    def _execute_analysis_single_pass(self, gui_config: dict, parsed_data: pd.DataFrame) -> pd.DataFrame:
        start = float(gui_config["slice_start_val"])
        end = float(gui_config["slice_end_val"])
        subset = parsed_data.loc[start:end].copy()

        time_values = subset.index.to_numpy(dtype=float)
        return pd.DataFrame(
            {
                TimeCols.FRAME: np.arange(len(subset), dtype=int),
                "Metric": time_values,
            },
            index=pd.Index(time_values, name=TimeCols.TIME),
        )


@unittest.skipUnless(HAS_QT, "PySide6 is required for PipelineController tests.")
class TestRangeLimitedResampling(unittest.TestCase):
    def _parsed_data(self):
        times = np.round(np.arange(0.0, 1.01, 0.1), 10)
        return pd.DataFrame(
            {TimeCols.FRAME: np.arange(len(times), dtype=int), "Raw": times},
            index=pd.Index(times, name=TimeCols.TIME),
        )

    def _config(self):
        return {
            "slice_filter_by": "time",
            "slice_start_val": 0.0,
            "slice_end_val": 1.0,
            "enable_result_resampling": True,
            "result_resampling_factor": 2,
            "limit_result_resampling_to_range": True,
            "result_resampling_range_start": 0.3,
            "result_resampling_range_end": 0.6,
            "analysis_options": {},
        }

    def test_range_limited_resampling_preserves_existing_samples_and_inserts_only_middle_rows(self):
        controller = _DeterministicRangeController()
        parsed_data = self._parsed_data()

        baseline = controller._execute_analysis_single_pass(
            {**self._config(), "enable_result_resampling": False, "result_resampling_factor": 1},
            parsed_data,
        )
        result = controller._execute_analysis_from_parsed(self._config(), parsed_data)

        self.assertEqual(float(result.index.min()), 0.0)
        self.assertEqual(float(result.index.max()), 1.0)
        self.assertGreater(len(result), len(baseline))
        np.testing.assert_array_equal(result[TimeCols.FRAME].to_numpy(), np.arange(len(result)))

        inserted_times = result.index.difference(baseline.index)
        self.assertTrue((inserted_times >= 0.3).all())
        self.assertTrue((inserted_times <= 0.6).all())
        self.assertGreater(len(inserted_times), 0)

        preserved = result.loc[baseline.index, "Metric"]
        pd.testing.assert_series_equal(preserved, baseline["Metric"], check_names=False)
        np.testing.assert_allclose(
            result.loc[inserted_times, "Metric"].to_numpy(dtype=float),
            inserted_times.to_numpy(dtype=float),
        )

    def test_range_limited_resampling_rejects_invalid_range(self):
        controller = _DeterministicRangeController()
        config = self._config()
        config["result_resampling_range_start"] = 0.7
        config["result_resampling_range_end"] = 0.6

        with self.assertRaisesRegex(ValueError, "start must be smaller"):
            controller._execute_analysis_from_parsed(config, self._parsed_data())

    def test_full_result_resampling_preserves_existing_samples_and_inserts_across_slice(self):
        controller = _DeterministicRangeController()
        parsed_data = self._parsed_data()
        config = self._config()
        config["limit_result_resampling_to_range"] = False
        config["result_resampling_range_start"] = None
        config["result_resampling_range_end"] = None

        baseline = controller._execute_analysis_single_pass(
            {**config, "enable_result_resampling": False, "result_resampling_factor": 1},
            parsed_data,
        )
        result = controller._execute_analysis_from_parsed(config, parsed_data)

        self.assertEqual(len(result), 21)
        inserted_times = result.index.difference(baseline.index)
        self.assertGreater(len(inserted_times), 0)
        self.assertEqual(float(inserted_times.min()), 0.05)
        self.assertEqual(float(inserted_times.max()), 0.95)
        pd.testing.assert_series_equal(
            result.loc[baseline.index, "Metric"],
            baseline["Metric"],
            check_names=False,
        )


if __name__ == "__main__":
    unittest.main()
