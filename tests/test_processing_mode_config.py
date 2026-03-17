import unittest

from src.config import config_analysis_ui


class TestProcessingModeConfig(unittest.TestCase):
    def test_default_processing_mode_is_raw(self):
        self.assertEqual(
            config_analysis_ui.DEFAULT_PROCESSING_MODE,
            config_analysis_ui.PROCESSING_MODE_RAW,
        )

    def test_processing_mode_order_is_raw_smoothing_advanced(self):
        self.assertEqual(
            config_analysis_ui.PROCESSING_MODE_ORDER,
            [
                config_analysis_ui.PROCESSING_MODE_RAW,
                config_analysis_ui.PROCESSING_MODE_STANDARD,
                config_analysis_ui.PROCESSING_MODE_ADVANCED,
            ],
        )

    def test_processing_mode_labels_and_descriptions_match_current_ui(self):
        self.assertEqual(
            config_analysis_ui.PROCESSING_MODE_LABELS[config_analysis_ui.PROCESSING_MODE_RAW],
            "Raw",
        )
        self.assertEqual(
            config_analysis_ui.PROCESSING_MODE_LABELS[config_analysis_ui.PROCESSING_MODE_STANDARD],
            "Smoothing",
        )
        self.assertIn(
            "Smoothing uses smoothing and filtering",
            config_analysis_ui.PROCESSING_MODE_DESCRIPTIONS[
                config_analysis_ui.PROCESSING_MODE_STANDARD
            ],
        )

    def test_initial_advanced_options_follow_default_processing_mode(self):
        initial = config_analysis_ui.get_initial_advanced_options()
        raw = config_analysis_ui.get_raw_mode_options()

        self.assertEqual(initial["enable_marker_smoothing"], raw["enable_marker_smoothing"])
        self.assertEqual(initial["marker_smoothing_method_sequence"], raw["marker_smoothing_method_sequence"])
        self.assertEqual(initial["use_pose_lowpass_filter"], raw["use_pose_lowpass_filter"])
        self.assertEqual(initial["use_pose_moving_average"], raw["use_pose_moving_average"])
        self.assertEqual(initial["velocity_method"], raw["velocity_method"])
        self.assertEqual(initial["acceleration_method"], raw["acceleration_method"])
        self.assertEqual(initial["use_velocity_lowpass_filter"], raw["use_velocity_lowpass_filter"])
        self.assertEqual(initial["use_acceleration_lowpass_filter"], raw["use_acceleration_lowpass_filter"])


if __name__ == "__main__":
    unittest.main()
