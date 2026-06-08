import os
import tempfile
import unittest
from unittest.mock import MagicMock, patch

import pandas as pd

from src.analysis.pipeline.artifact_io import SliceMetadata

try:
    from PySide6.QtWidgets import QApplication
    from src.analysis.ui.widget_slice_processing import WidgetSliceProcessing
    HAS_QT = True
except ModuleNotFoundError:
    QApplication = None
    WidgetSliceProcessing = None
    HAS_QT = False


class _DummySignal:
    def __init__(self):
        self._callbacks = []

    def connect(self, callback):
        self._callbacks.append(callback)

    def emit(self, value):
        for callback in self._callbacks:
            callback(value)


class _FakePipelineController:
    def __init__(self, result_df):
        self.log_message = _DummySignal()
        self._result_df = result_df
        self.configs = []

    def process_parsed_data(self, config, parsed_data):
        self.configs.append(config)
        self.log_message.emit("[INFO] Fake batch processing run.")
        return self._result_df.copy()


class TestSliceBatchProcessing(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if HAS_QT:
            cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        if not HAS_QT:
            self.skipTest("PySide6 is required for Step 1.5 widget batch tests.")
        self.widget = WidgetSliceProcessing(MagicMock(), MagicMock())

    def tearDown(self):
        self.widget.close()

    def _metadata(self):
        return SliceMetadata(
            source="source.csv",
            created="2026-03-18T00:00:00+00:00",
            scene="scene",
            box_l=1.0,
            box_w=2.0,
            box_h=3.0,
            full_start=0.0,
            full_end=1.0,
            user_start=0.1,
            user_end=0.9,
            padded_start=0.0,
            padded_end=1.0,
            pad_rows=50,
            row_count=100,
        )

    def _metadata_without_box_dimensions(self):
        return SliceMetadata(
            source="source.csv",
            created="2026-03-18T00:00:00+00:00",
            scene="scene",
            box_l=None,
            box_w=None,
            box_h=None,
            full_start=0.0,
            full_end=1.0,
            user_start=0.1,
            user_end=0.9,
            padded_start=0.0,
            padded_end=1.0,
            pad_rows=50,
            row_count=100,
        )

    def test_batch_processing_skips_existing_proc_and_saves_new_results(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            slice_a = os.path.join(temp_dir, "scene_a.slice")
            slice_b = os.path.join(temp_dir, "scene_b.slice")
            existing_proc = os.path.join(temp_dir, "scene_a.proc")

            open(slice_a, "w", encoding="utf-8").close()
            open(slice_b, "w", encoding="utf-8").close()
            open(existing_proc, "w", encoding="utf-8").close()

            self.widget.batch_slice_folder = temp_dir
            self.widget.batch_folder_label.setText(temp_dir)
            self.widget.pipeline_controller_factory = lambda: _FakePipelineController(
                pd.DataFrame({"metric": [1.0, 2.0]})
            )

            with patch.object(
                self.widget,
                "_load_slice_bundle",
                side_effect=[
                    (self._metadata(), {}, pd.DataFrame(), pd.DataFrame(index=[0.0, 0.1])),
                ],
            ) as mock_load_bundle, patch(
                "src.analysis.ui.widget_slice_processing.save_proc_file",
            ) as mock_save_proc:
                self.widget.run_batch_processing()

            mock_load_bundle.assert_called_once_with(slice_b)
            mock_save_proc.assert_called_once_with(
                os.path.join(temp_dir, "scene_b.proc"),
                unittest.mock.ANY,
            )
            self.assertIn("processed=1", self.widget.batch_summary_label.text())
            self.assertIn("skipped=1", self.widget.batch_summary_label.text())
            self.assertIn("failed=0", self.widget.batch_summary_label.text())

    def test_processing_config_includes_range_limited_resampling_settings(self):
        self.widget.slice_metadata = self._metadata()
        parsed_data = pd.DataFrame(index=pd.Index([0.0, 0.5, 1.0], name="Time"))
        self.widget.cb_enable_resampling.setChecked(True)
        self.widget.cb_limit_resampling_range.setChecked(True)
        self.widget.le_resampling_range_start.setText("0.2")
        self.widget.le_resampling_range_end.setText("0.8")

        config = self.widget._build_processing_config(parsed_data, self.widget.slice_metadata)

        self.assertTrue(config["enable_result_resampling"])
        self.assertTrue(config["limit_result_resampling_to_range"])
        self.assertEqual(config["result_resampling_range_start"], 0.2)
        self.assertEqual(config["result_resampling_range_end"], 0.8)
        self.assertEqual(config["box_dimensions"], (1.0, 2.0, 3.0))

    def test_slice_summary_sets_default_resampling_range_from_metadata(self):
        self.widget.slice_metadata = self._metadata()

        self.widget._set_slice_summary()

        self.assertEqual(self.widget.le_resampling_range_start.text(), "0.100")
        self.assertEqual(self.widget.le_resampling_range_end.text(), "0.900")

    def test_missing_slice_box_dimensions_enable_manual_apply_until_valid(self):
        self.widget.data_loader.get_plottable_targets.return_value = []

        with patch.object(
            self.widget,
            "_load_slice_bundle",
            return_value=(self._metadata_without_box_dimensions(), {}, pd.DataFrame(), pd.DataFrame(index=[0.0, 0.1])),
        ), patch("src.analysis.ui.widget_slice_processing.QMessageBox.warning") as mock_warning:
            self.widget.load_slice_file("missing.slice")

        mock_warning.assert_called_once()
        self.assertTrue(self.widget.le_box_l.isEnabled())
        self.assertFalse(self.widget.apply_box_dims_button.isHidden())
        self.assertFalse(self.widget.run_button.isEnabled())

        self.widget.le_box_l.setText("10")
        self.widget.le_box_w.setText("20")
        self.widget.le_box_h.setText("30")
        self.widget.apply_manual_box_dimensions()

        self.assertEqual(self.widget.manual_box_dimensions, (10.0, 20.0, 30.0))
        self.assertFalse(self.widget.le_box_l.isEnabled())
        self.assertTrue(self.widget.apply_box_dims_button.isHidden())
        self.assertTrue(self.widget.run_button.isEnabled())

    def test_manual_box_dimensions_can_be_saved_to_slice_metadata(self):
        self.widget.data_loader.get_plottable_targets.return_value = []
        updated_metadata = self._metadata()

        with patch.object(
            self.widget,
            "_load_slice_bundle",
            return_value=(self._metadata_without_box_dimensions(), {}, pd.DataFrame(), pd.DataFrame(index=[0.0, 0.1])),
        ), patch("src.analysis.ui.widget_slice_processing.QMessageBox.warning"):
            self.widget.load_slice_file("missing.slice")

        self.widget.le_box_l.setText("10")
        self.widget.le_box_w.setText("20")
        self.widget.le_box_h.setText("30")
        self.widget.save_box_dims_to_slice_checkbox.setChecked(True)

        with patch(
            "src.analysis.ui.widget_slice_processing.update_slice_box_dimensions",
            return_value=updated_metadata,
        ) as mock_update:
            self.widget.apply_manual_box_dimensions()

        mock_update.assert_called_once_with("missing.slice", (10.0, 20.0, 30.0))
        self.assertEqual(self.widget.slice_metadata, updated_metadata)
        self.assertIsNone(self.widget.manual_box_dimensions)
        self.assertTrue(self.widget.run_button.isEnabled())

    def test_batch_processing_uses_each_slice_metadata_dimensions(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            slice_a = os.path.join(temp_dir, "scene_a.slice")
            slice_b = os.path.join(temp_dir, "scene_b.slice")
            open(slice_a, "w", encoding="utf-8").close()
            open(slice_b, "w", encoding="utf-8").close()

            self.widget.batch_slice_folder = temp_dir
            fake_controller = _FakePipelineController(pd.DataFrame({"metric": [1.0, 2.0]}))
            metadata_a = self._metadata()
            metadata_b = SliceMetadata(
                source="source.csv",
                created="2026-03-18T00:00:00+00:00",
                scene="scene",
                box_l=4.0,
                box_w=5.0,
                box_h=6.0,
                full_start=0.0,
                full_end=1.0,
                user_start=0.1,
                user_end=0.9,
                padded_start=0.0,
                padded_end=1.0,
                pad_rows=50,
                row_count=100,
            )
            self.widget.pipeline_controller_factory = lambda: fake_controller

            with patch.object(
                self.widget,
                "_load_slice_bundle",
                side_effect=[
                    (metadata_a, {}, pd.DataFrame(), pd.DataFrame(index=[0.0, 0.1])),
                    (metadata_b, {}, pd.DataFrame(), pd.DataFrame(index=[0.0, 0.1])),
                ],
            ), patch("src.analysis.ui.widget_slice_processing.save_proc_file"):
                self.widget.run_batch_processing()

            self.assertEqual(
                [config["box_dimensions"] for config in fake_controller.configs],
                [(1.0, 2.0, 3.0), (4.0, 5.0, 6.0)],
            )
            self.assertIn("processed=2", self.widget.batch_summary_label.text())
            self.assertIn("failed=0", self.widget.batch_summary_label.text())

    def test_batch_processing_fails_missing_dimensions_per_file_and_continues(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            slice_a = os.path.join(temp_dir, "scene_a.slice")
            slice_b = os.path.join(temp_dir, "scene_b.slice")
            open(slice_a, "w", encoding="utf-8").close()
            open(slice_b, "w", encoding="utf-8").close()

            self.widget.batch_slice_folder = temp_dir
            fake_controller = _FakePipelineController(pd.DataFrame({"metric": [1.0, 2.0]}))
            self.widget.pipeline_controller_factory = lambda: fake_controller

            with patch.object(
                self.widget,
                "_load_slice_bundle",
                side_effect=[
                    (self._metadata_without_box_dimensions(), {}, pd.DataFrame(), pd.DataFrame(index=[0.0, 0.1])),
                    (self._metadata(), {}, pd.DataFrame(), pd.DataFrame(index=[0.0, 0.1])),
                ],
            ), patch("src.analysis.ui.widget_slice_processing.save_proc_file") as mock_save_proc:
                self.widget.run_batch_processing()

            self.assertEqual([config["box_dimensions"] for config in fake_controller.configs], [(1.0, 2.0, 3.0)])
            mock_save_proc.assert_called_once()
            self.assertIn("processed=1", self.widget.batch_summary_label.text())
            self.assertIn("failed=1", self.widget.batch_summary_label.text())


if __name__ == "__main__":
    unittest.main()
