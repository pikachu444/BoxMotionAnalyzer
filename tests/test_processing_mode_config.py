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


if __name__ == "__main__":
    unittest.main()
