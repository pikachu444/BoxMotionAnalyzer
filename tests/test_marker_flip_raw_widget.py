import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pandas as pd
from PySide6.QtWidgets import QApplication, QDialog

from src.analysis.pipeline.artifact_io import read_corrected_source_metadata
from src.analysis.pipeline.marker_flip import MarkerCorrectionDecision, marker_triplet_indices
from src.analysis.ui.widget_raw_data_processing import WidgetRawDataProcessing
from src.config.data_columns import TimeCols


app = QApplication.instance() or QApplication([])


def _raw_bundle() -> tuple[dict[str, list[str]], pd.DataFrame]:
    marker_ids = ["A", "B", "C", "D"]
    headers = {
        "type": ["", ""],
        "name": ["Frame", "Time"],
        "id": ["", ""],
        "parent": ["", ""],
        "category": ["", ""],
        "component": [TimeCols.FRAME, TimeCols.TIME],
    }
    for marker_id in marker_ids:
        headers["type"].extend(["Rigid Body Marker"] * 3)
        headers["name"].extend([f"Box:{marker_id}"] * 3)
        headers["id"].extend([marker_id] * 3)
        headers["parent"].extend(["Box"] * 3)
        headers["category"].extend(["Position"] * 3)
        headers["component"].extend(["X", "Y", "Z"])

    rows = []
    for row_index in range(5):
        row = [float(row_index), float(row_index)]
        for marker_index in range(len(marker_ids)):
            base = row_index * 1000.0 + marker_index * 10.0
            row.extend([base + 1.0, base + 2.0, base + 3.0])
        rows.append(row)
    return headers, pd.DataFrame(rows, columns=headers["component"])


def _approved_decision() -> MarkerCorrectionDecision:
    return MarkerCorrectionDecision(
        event_id="flip-000002",
        boundary_time_sec=2.0,
        approved=True,
        axis="X",
        recommendation_axis="X",
        permutation=(("A", "B"), ("B", "A"), ("C", "D"), ("D", "C")),
        recommendation_reason="Fixture recommendation.",
        evidence_json='{"fixture":true}',
    )


class _FakePoseOptimizer:
    def __init__(self, pose_data):
        self.pose_data = pose_data

    def process(self, _parsed_data, box_dims=None):
        return self.pose_data


class _FakeAnalyzer:
    def __init__(self, candidates):
        self.candidates = candidates

    def detect(self, _marker_data, _pose_data, _box_dims):
        return self.candidates


class TestMarkerFlipRawWidget(unittest.TestCase):
    def setUp(self):
        self.data_loader = MagicMock()
        self.parser = MagicMock()
        self.widget = WidgetRawDataProcessing(self.data_loader, self.parser)
        self.header_info, self.raw_df = _raw_bundle()
        self.parsed_df = pd.DataFrame({"preview": [1.0, 2.0]}, index=[0.0, 1.0])
        self.widget.header_info = self.header_info
        self.widget.raw_data = self.raw_df
        self.widget.review_raw_data = self.raw_df.copy(deep=True)
        self.widget.parsed_data = self.parsed_df
        self.widget.review_parsed_data = self.parsed_df.copy(deep=True)
        self.widget.source_path = "original.csv"
        self.widget.original_source_reference = "original.csv"

    def tearDown(self):
        self.widget.close()
        self.widget.deleteLater()
        app.processEvents()

    def test_review_cancel_preserves_existing_decisions_and_dirty_state(self):
        existing = [_approved_decision()]
        self.widget.marker_correction_decisions = list(existing)
        self.widget.marker_review_dirty = True
        candidate = SimpleNamespace(recommendation_axis="X")
        fake_dialog = MagicMock()
        fake_dialog.exec.return_value = QDialog.DialogCode.Rejected
        self.widget.pose_optimizer_factory = lambda **_kwargs: _FakePoseOptimizer(
            self.review_pose_data
        )
        self.review_pose_data = self.parsed_df
        self.widget.marker_flip_analyzer_factory = lambda: _FakeAnalyzer([candidate])
        self.widget.marker_flip_dialog_factory = lambda *_args, **_kwargs: fake_dialog

        # Exercise dialog acceptance state separately from the real async worker.
        self.widget._pending_review_context = '{}'
        self.widget._finish_marker_review([candidate])

        self.assertEqual(self.widget.marker_correction_decisions, existing)
        self.assertTrue(self.widget.marker_review_dirty)
        fake_dialog.get_decisions.assert_not_called()

    def test_accepting_all_off_decision_requires_saving_review_history(self):
        candidate = SimpleNamespace(recommendation_axis="X")
        off_decision = MarkerCorrectionDecision(
            event_id="flip-000002",
            boundary_time_sec=2.0,
            approved=False,
            recommendation_axis="X",
            recommendation_reason="Operator left event OFF.",
            evidence_json='{"fixture":"off"}',
        )
        fake_dialog = MagicMock()
        fake_dialog.exec.return_value = QDialog.DialogCode.Accepted
        fake_dialog.get_decisions.return_value = [off_decision]
        self.review_pose_data = self.parsed_df
        self.widget.pose_optimizer_factory = lambda **_kwargs: _FakePoseOptimizer(
            self.review_pose_data
        )
        self.widget.marker_flip_analyzer_factory = lambda: _FakeAnalyzer([candidate])
        self.widget.marker_flip_dialog_factory = lambda *_args, **_kwargs: fake_dialog

        self.widget._pending_review_context = '{}'
        self.widget._finish_marker_review([candidate])

        self.assertTrue(self.widget.marker_review_dirty)
        self.assertTrue(self.widget.save_corrected_source_button.isEnabled())
        self.assertFalse(self.widget.save_slice_button.isEnabled())
        self.assertEqual(self.widget.marker_correction_decisions, [off_decision])

    def test_save_failure_leaves_active_source_and_data_unchanged(self):
        decision = _approved_decision()
        self.widget.marker_correction_decisions = [decision]
        self.widget.marker_review_dirty = True
        previous_metadata = object()
        self.widget.correction_source_metadata = previous_metadata
        corrected_parsed = pd.DataFrame({"corrected": [3.0]}, index=[0.0])
        self.parser.process.return_value = corrected_parsed
        emitted = MagicMock()
        self.widget.file_loaded.connect(emitted)

        with patch(
            "src.analysis.ui.widget_raw_data_processing.QFileDialog.getSaveFileName",
            return_value=("failed.corrected.csv", "Corrected CSV Files"),
        ), patch(
            "src.analysis.ui.widget_raw_data_processing.save_corrected_source_file",
            side_effect=OSError("simulated save failure"),
        ), patch(
            "src.analysis.ui.widget_raw_data_processing.QMessageBox.warning"
        ):
            self.widget.save_corrected_source()

        self.assertEqual(self.widget.source_path, "original.csv")
        self.assertIs(self.widget.raw_data, self.raw_df)
        self.assertIs(self.widget.parsed_data, self.parsed_df)
        self.assertIs(self.widget.correction_source_metadata, previous_metadata)
        self.assertTrue(self.widget.marker_review_dirty)
        emitted.assert_not_called()

    def test_successful_save_activates_corrected_data_after_file_exists(self):
        decision = _approved_decision()
        self.widget.marker_correction_decisions = [decision]
        self.widget.marker_review_dirty = True
        corrected_parsed = pd.DataFrame({"corrected": [3.0]}, index=[0.0])
        self.parser.process.return_value = corrected_parsed
        emitted = MagicMock()
        self.widget.file_loaded.connect(emitted)

        with tempfile.TemporaryDirectory() as temp_dir:
            original_path = Path(temp_dir) / "original.csv"
            original_path.write_text("identity", encoding="utf-8")
            corrected_path = Path(temp_dir) / "original.corrected.csv"
            self.widget.source_path = str(original_path)
            self.widget.original_source_reference = str(original_path)

            with patch(
                "src.analysis.ui.widget_raw_data_processing.QFileDialog.getSaveFileName",
                return_value=(str(corrected_path), "Corrected CSV Files"),
            ), patch.object(self.widget, "update_plot"), patch.object(
                self.widget.plot_manager,
                "enable_interactions",
            ):
                self.widget.save_corrected_source()

            self.assertTrue(corrected_path.exists())
            self.assertEqual(self.widget.source_path, str(corrected_path))
            self.assertIs(self.widget.parsed_data, corrected_parsed)
            self.assertFalse(self.widget.marker_review_dirty)
            self.assertEqual(
                self.widget.correction_source_metadata,
                read_corrected_source_metadata(str(corrected_path)),
            )
            triplets = marker_triplet_indices(self.header_info)
            expected = self.raw_df.iloc[2, list(triplets["B"])].to_numpy()
            actual = self.widget.raw_data.iloc[2, list(triplets["A"])].to_numpy()
            self.assertEqual(actual.tolist(), expected.tolist())
            pd.testing.assert_frame_equal(self.widget.review_raw_data, self.raw_df)
            emitted.assert_called_once()

    def test_long_source_filename_is_wrapped_selectable_and_fully_preserved(self):
        long_path = str(
            Path("C:/captures")
            / (("very_long_capture_directory_and_filename_" * 12) + "corrected.csv")
        )
        self.widget.source_path = long_path
        self.widget.correction_source_metadata = SimpleNamespace(
            event_count=0,
            approved_event_count=0,
        )
        self.widget._set_file_path_display(long_path)
        self.widget._update_marker_review_summary()
        self.widget.resize(820, 600)
        self.widget.show()
        app.processEvents()

        self.assertTrue(self.widget.file_path_label.wordWrap())
        self.assertEqual(self.widget.file_path_label.text(), long_path)
        self.assertEqual(self.widget.file_path_label.toolTip(), long_path)
        self.assertTrue(self.widget.marker_review_source_label.wordWrap())
        self.assertIn(long_path, self.widget.marker_review_source_label.text())
        self.assertEqual(
            self.widget.marker_review_source_label.toolTip(),
            self.widget.marker_review_source_label.text(),
        )


if __name__ == "__main__":
    unittest.main()
