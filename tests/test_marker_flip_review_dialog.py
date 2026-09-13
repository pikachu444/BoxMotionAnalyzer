import unittest
from dataclasses import replace
import json
import numpy as np

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QDialogButtonBox, QDialog

from src.analysis.pipeline.marker_flip import (
    MarkerCorrectionDecision,
    MarkerFlipCandidate,
    MarkerFlipHypothesis,
)
from src.analysis.ui.dialog_marker_flip_review import MarkerFlipReviewDialog


app = QApplication.instance() or QApplication([])


PERMUTATIONS = {
    "X": (("A", "B"), ("B", "A"), ("C", "D"), ("D", "C")),
    "Y": (("A", "C"), ("C", "A"), ("B", "D"), ("D", "B")),
    "Z": (("A", "D"), ("D", "A"), ("B", "C"), ("C", "B")),
}


def _hypothesis(label: str) -> MarkerFlipHypothesis:
    return MarkerFlipHypothesis(
        label=label,
        residual_deg=0.0 if label != "NONE" else 180.0,
        discontinuity_reduction_deg=180.0 if label != "NONE" else 0.0,
        score=1.0 if label == "X" else 0.2,
        layout_correspondence_ratio=1.0,
        observed_correspondence_ratio=1.0,
        coverage_ratio=1.0,
        common_marker_count=4,
        marker_rmse_mm=0.0,
        permutation=PERMUTATIONS.get(label, ()),
    )


def _candidate(
    recommendation_axis: str | None = "X",
    *,
    event_id: str = "flip-000010",
    boundary_time_sec: float = 0.1,
    trigger: str = "rotation jump 180.0°",
    reason: str = "Synthetic review fixture.",
) -> MarkerFlipCandidate:
    return MarkerFlipCandidate(
        event_id=event_id,
        boundary_time_sec=boundary_time_sec,
        trigger=trigger,
        recommendation_axis=recommendation_axis,
        best_hypothesis_label=recommendation_axis or "NONE",
        no_correction_residual_deg=180.0,
        best_residual_deg=0.0,
        discontinuity_reduction_deg=180.0,
        confidence_margin=0.8,
        correspondence_ratio=1.0,
        marker_rmse_mm=0.0,
        coverage_ratio=1.0,
        common_marker_count=4,
        pre_stability_deg=0.0,
        post_stability_deg=0.0,
        reason=reason,
        hypotheses=tuple(_hypothesis(label) for label in ("NONE", "X", "Y", "Z")),
    )


class TestMarkerFlipReviewDialog(unittest.TestCase):
    def tearDown(self):
        for widget in QApplication.topLevelWidgets():
            if isinstance(widget, MarkerFlipReviewDialog):
                widget.close()
                widget.deleteLater()
        app.processEvents()

    def test_recommendation_is_preselected_but_event_remains_off(self):
        dialog = MarkerFlipReviewDialog([_candidate("X")])

        self.assertFalse(dialog.approval_checkbox(0).isChecked())
        self.assertEqual(dialog.axis_combo(0).currentData(), "X")
        decision = dialog.get_decisions()[0]
        self.assertFalse(decision.approved)
        self.assertIsNone(decision.axis)
        self.assertEqual(decision.recommendation_axis, "X")
        self.assertEqual(decision.permutation, ())

    def test_approving_recommendation_records_selected_axis_and_permutation(self):
        dialog = MarkerFlipReviewDialog([_candidate("X")])
        dialog.approval_checkbox(0).setChecked(True)

        decision = dialog.get_decisions()[0]

        self.assertTrue(decision.approved)
        self.assertEqual(decision.axis, "X")
        self.assertEqual(decision.recommendation_axis, "X")
        self.assertEqual(decision.permutation, PERMUTATIONS["X"])

    def test_operator_override_keeps_recommendation_and_selected_axis_separate(self):
        dialog = MarkerFlipReviewDialog([_candidate("X")])
        dialog.approval_checkbox(0).setChecked(True)
        dialog.axis_combo(0).setCurrentIndex(dialog.axis_combo(0).findData("Y"))

        decision = dialog.get_decisions()[0]

        self.assertEqual(decision.recommendation_axis, "X")
        self.assertEqual(decision.axis, "Y")
        self.assertEqual(decision.permutation, PERMUTATIONS["Y"])

    def test_operator_can_apply_supported_axis_without_recommendation(self):
        dialog = MarkerFlipReviewDialog([_candidate(None)])
        dialog.approval_checkbox(0).setChecked(True)
        dialog.axis_combo(0).setCurrentIndex(dialog.axis_combo(0).findData("Z"))

        decision = dialog.get_decisions()[0]

        self.assertIsNone(decision.recommendation_axis)
        self.assertEqual(decision.axis, "Z")
        self.assertEqual(decision.permutation, PERMUTATIONS["Z"])

    def test_existing_approved_override_is_restored(self):
        existing = MarkerCorrectionDecision(
            event_id="flip-000010",
            boundary_time_sec=0.1,
            approved=True,
            axis="Y",
            recommendation_axis="X",
            permutation=PERMUTATIONS["Y"],
        )

        dialog = MarkerFlipReviewDialog(
            [_candidate("X")],
            existing_decisions=[existing],
        )

        self.assertTrue(dialog.approval_checkbox(0).isChecked())
        self.assertEqual(dialog.axis_combo(0).currentData(), "Y")

    def test_compact_layout_keeps_multiple_event_controls_visible_at_target_size(self):
        long_trigger = "rotation jump after reconnect " * 12
        long_reason = "Recommendation withheld until every conservative gate passes. " * 8
        candidates = [
            _candidate("X", event_id="flip-000010", boundary_time_sec=0.1),
            _candidate(None, event_id="flip-000020", boundary_time_sec=0.2),
            _candidate(
                "Z",
                event_id="flip-000030",
                boundary_time_sec=0.3,
                trigger=long_trigger,
                reason=long_reason,
            ),
        ]
        dialog = MarkerFlipReviewDialog(candidates)
        dialog.resize(820, 600)
        dialog.show()
        app.processEvents()

        self.assertEqual(dialog.table.columnCount(), 4)
        self.assertEqual(dialog.table.horizontalScrollBar().maximum(), 0)
        for row in range(len(candidates)):
            self.assertFalse(dialog.approval_checkbox(row).visibleRegion().isEmpty())
            self.assertFalse(dialog.axis_combo(row).visibleRegion().isEmpty())
        self.assertFalse(dialog.button_box.visibleRegion().isEmpty())

        dialog.table.setCurrentCell(2, 0)
        QTest.mouseClick(dialog.details_section.button, Qt.LeftButton)
        app.processEvents()
        detail_text = dialog.candidate_details.toPlainText()
        self.assertIn(long_trigger.strip(), detail_text)
        self.assertIn(long_reason.strip(), detail_text)
        self.assertEqual(dialog.candidate_details.horizontalScrollBar().maximum(), 0)

    def test_face_continuity_recommendation_is_conditional_off_and_override_preserved(self):
        candidate = replace(_candidate('X'), correction_kind='face_assignment',
            algorithm_version='3.1', gate_version='face-continuity-v1',
            reason='If corrected, local X best restores continuity; cause unconfirmed.',
            correspondence_ratio=float('nan'), confidence_margin=.8,
            pre_window_time_offsets_sec=(-.03, -.02, -.01),
            pre_window_residual_deg=(0., 0., 0.),
            post_window_time_offsets_sec=(0., .01, .02),
            post_window_raw_residual_deg=(180., 180., 180.),
            hypotheses=tuple(replace(_hypothesis(label), permutation=(),
                layout_correspondence_ratio=float('nan'), observed_correspondence_ratio=float('nan'),
                trace_deg=(0., 0., 0.)) for label in ('NONE', 'X', 'Y', 'Z')))
        dialog = MarkerFlipReviewDialog([candidate])
        dialog.resize(820, 600)
        dialog.show()
        app.processEvents()
        details = dialog.candidate_details.toPlainText()
        self.assertIn('Recommendation: X', details)
        self.assertIn('cause unconfirmed', details)
        self.assertIn('Refit none: 180°', details)
        self.assertIn('Selected X: 0°', details)
        self.assertNotIn('score gap', details)
        self.assertNotIn('algorithm=', details)
        self.assertNotIn('validation pending', details)
        self.assertNotIn('match=', details)
        self.assertFalse(dialog.approval_checkbox(0).isChecked())
        self.assertEqual(dialog.axis_combo(0).currentData(), 'X')
        self.assertFalse(dialog.button_box.visibleRegion().isEmpty())
        self.assertEqual(dialog.table.horizontalScrollBar().maximum(), 0)
        off = dialog.get_decisions()[0]
        self.assertFalse(off.approved)
        self.assertIsNone(off.axis)
        dialog.axis_combo(0).setCurrentIndex(dialog.axis_combo(0).findData('Y'))
        dialog.approval_checkbox(0).setChecked(True)
        override = dialog.get_decisions()[0]
        self.assertEqual((override.axis, override.recommendation_axis, override.permutation), ('Y', 'X', ()))
        self.assertEqual(override.algorithm_version, '3.1')
        self.assertIsNone(json.loads(override.evidence_json)['correspondence_ratio'])
        reopened = MarkerFlipReviewDialog([candidate], existing_decisions=[override])
        self.assertTrue(reopened.approval_checkbox(0).isChecked())
        self.assertEqual(reopened.axis_combo(0).currentData(), 'Y')
        reopened.axis_combo(0).setCurrentIndex(reopened.axis_combo(0).findData('Z'))
        reopened.reject()
        self.assertEqual(override.axis, 'Y')
        self.assertEqual(reopened.result(), 0)

    def test_selected_event_axis_actual_trace_and_explicit_done(self):
        def event(index):
            return replace(_candidate('X', event_id=f'event-{index}', boundary_time_sec=index * .1),
                correction_kind='face_assignment', pre_window_time_offsets_sec=(-.03, -.02, -.01),
                pre_window_residual_deg=(.1, .2, .3), post_window_time_offsets_sec=(0., .01, .02),
                post_window_raw_residual_deg=(179., 178., 177.),
                hypotheses=tuple(replace(_hypothesis(axis), trace_deg=(index + .1, np.nan, index + .3))
                                 for axis in ('NONE', 'X', 'Y', 'Z')))
        dialog = MarkerFlipReviewDialog([event(index) for index in range(7)])
        dialog.resize(820, 600)
        dialog.show()
        app.processEvents()
        self.assertFalse(dialog.details_section.button.isChecked())
        self.assertLess(dialog.table.height(), dialog.evidence_canvas.height())
        dialog.axis_combo(6).setCurrentIndex(dialog.axis_combo(6).findData('Y'))
        app.processEvents()
        self.assertEqual(dialog.table.currentRow(), 6)
        self.assertTrue(dialog.axis_combo(6).visibleRegion().contains(dialog.axis_combo(6).rect()))
        self.assertFalse(dialog.approval_checkbox(6).isChecked())
        axis = dialog.evidence_figure.axes[0]
        curves = {line.get_label(): line for line in axis.lines}
        np.testing.assert_array_equal(curves['Original'].get_ydata(), [179., 178., 177.])
        np.testing.assert_array_equal(curves['Preview Y'].get_ydata(), [6.1, np.nan, 6.3])
        self.assertEqual(set(axis.get_legend_handles_labels()[1]), {'Before', 'Original', 'Preview Y'})
        self.assertEqual(axis.get_xlabel(), 'Time from event (s)')
        dialog.approval_checkbox(6).setChecked(True)
        done = dialog.button_box.button(QDialogButtonBox.Ok)
        self.assertEqual(done.text(), 'Done')
        QTest.mouseClick(done, Qt.LeftButton)
        self.assertEqual(dialog.result(), QDialog.DialogCode.Accepted)
        decision = dialog.get_decisions()[6]
        self.assertEqual((decision.axis, decision.recommendation_axis, decision.approved), ('Y', 'X', True))

    def test_unavailable_comparison_keeps_original_and_does_not_display_sentinels(self):
        candidate = replace(_candidate(None), correction_kind='face_assignment',
            reason='Insufficient comparison samples.',
            no_correction_residual_deg=float('inf'), best_residual_deg=float('inf'),
            discontinuity_reduction_deg=0., confidence_margin=0.,
            pre_window_time_offsets_sec=(-.1,), pre_window_residual_deg=(0.,),
            post_window_time_offsets_sec=(0., .01, .02), post_window_raw_residual_deg=(.0015, .061, .1683),
            hypotheses=tuple(replace(_hypothesis(axis), residual_deg=float('inf'),
                marker_rmse_mm=None, trace_deg=()) for axis in ('NONE', 'X', 'Y', 'Z')))
        dialog = MarkerFlipReviewDialog([candidate])
        dialog.resize(820, 600)
        dialog.show()
        app.processEvents()
        dialog.axis_combo(0).setCurrentIndex(dialog.axis_combo(0).findData('X'))
        self.assertEqual(dialog.preview_status.text(), 'Preview unavailable')
        self.assertIn('Insufficient comparison samples', dialog.preview_status.toolTip())
        self.assertTrue(dialog.preview_status.visibleRegion().contains(dialog.preview_status.rect()))
        details = dialog.candidate_details.toPlainText()
        self.assertIn('Comparison: unavailable', details)
        self.assertIn('Selected X: unavailable', details)
        for misleading in ('inf°', 'nan', 'gain 0', 'score gap', 'post fit failed'):
            self.assertNotIn(misleading, details)
        axis = dialog.evidence_figure.axes[0]
        curves = {line.get_label(): line for line in axis.lines}
        np.testing.assert_array_equal(curves['Original'].get_ydata(), candidate.post_window_raw_residual_deg)
        self.assertEqual(set(axis.get_legend_handles_labels()[1]), {'Before', 'Original'})
        low, high = axis.get_ylim()
        self.assertGreaterEqual(high - low, 1.)

    def test_legacy_prediction_is_named_once_and_does_not_replace_original(self):
        candidate = replace(_candidate('X'), pre_window_time_offsets_sec=(-.02, -.01),
            pre_window_residual_deg=(0., .2), post_window_time_offsets_sec=(0., .01),
            post_window_raw_residual_deg=(179., 178.), post_window_best_residual_deg=(1., 2.))
        dialog = MarkerFlipReviewDialog([candidate])
        curves = {line.get_label(): line for line in dialog.evidence_figure.axes[0].lines}
        self.assertEqual([name for name in curves if name.startswith('Predicted')], ['Predicted X'])
        np.testing.assert_array_equal(curves['Original'].get_ydata(), [179., 178.])
        np.testing.assert_array_equal(curves['Predicted X'].get_ydata(), [1., 2.])
        dialog.axis_combo(0).setCurrentIndex(dialog.axis_combo(0).findData('Y'))
        names = dialog.evidence_figure.axes[0].get_legend_handles_labels()[1]
        self.assertEqual([name for name in names if name.startswith('Predicted')], ['Predicted Y mean'])


if __name__ == "__main__":
    unittest.main()
