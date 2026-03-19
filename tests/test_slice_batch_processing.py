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

    def process_parsed_data(self, config, parsed_data):
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


if __name__ == "__main__":
    unittest.main()
