import unittest

from src.analysis.pipeline.resampling_options import build_effective_analysis_options


class TestPipelineResamplingOptions(unittest.TestCase):
    def test_resampling_scales_sample_based_options_and_spline_factors(self):
        analysis_options = {
            "marker_moving_average_window": 3,
            "pose_moving_average_window": 5,
            "spline_s_factor_position": 1e-2,
            "spline_s_factor_rotation": 1e-3,
            "marker_butterworth_cutoff_hz": 10.0,
        }

        result = build_effective_analysis_options(analysis_options, 4)

        self.assertEqual(result["marker_moving_average_window"], 12)
        self.assertEqual(result["pose_moving_average_window"], 20)
        self.assertAlmostEqual(result["spline_s_factor_position"], 4e-2)
        self.assertAlmostEqual(result["spline_s_factor_rotation"], 4e-3)
        self.assertEqual(result["marker_butterworth_cutoff_hz"], 10.0)


if __name__ == "__main__":
    unittest.main()
