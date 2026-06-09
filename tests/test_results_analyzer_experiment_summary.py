import os
import sys
import unittest

import pandas as pd

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtWidgets import QApplication, QLabel
    HAS_QT = True
except ModuleNotFoundError:
    QApplication = None
    QLabel = None
    HAS_QT = False

from src.analysis.ui.dialog_metric_guide import (
    DropPostureMetricGuideDialog,
)
from src.analysis.ui.widget_results_analyzer import WidgetResultsAnalyzer
from src.config.data_columns import HeaderL1, HeaderL2, HeaderL3
from src.config.result_metric_descriptors import (
    get_drop_posture_summary_descriptors,
    get_result_metric_descriptor,
)


class _DummyDataLoader:
    pass


@unittest.skipUnless(HAS_QT, "PySide6 is required for Results Analyzer UI tests.")
class TestResultsAnalyzerExperimentSummary(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.widget = WidgetResultsAnalyzer(_DummyDataLoader())

    def tearDown(self):
        self.widget.close()

    def _summary_column(self, l3):
        return (HeaderL1.ANALYSIS, HeaderL2.DROP_POSTURE_SUMMARY, l3)

    def test_experiment_summary_uses_descriptor_group_order(self):
        columns = pd.MultiIndex.from_tuples(
            [
                self._summary_column(HeaderL3.DROP_T1_DETECTED),
                self._summary_column(HeaderL3.DROP_BETA_AT_T1_MINUS_DEG),
                self._summary_column(HeaderL3.DROP_REFERENCE_FACE),
                self._summary_column(HeaderL3.DROP_FIRST_IMPACT_TIME_SEC),
                self._summary_column(HeaderL3.DROP_IMPACT_SEQUENCE),
                self._summary_column(HeaderL3.DROP_CONTACT_STATE),
                self._summary_column(HeaderL3.DROP_CONTACT_CONFIDENCE),
            ]
        )
        self.widget.result_data = pd.DataFrame(
            [[True, 12.3456, "BOTTOM", 2.720833, "C2 -> C5", "ImpactEvent", 0.55]],
            columns=columns,
        )

        self.widget._update_drop_posture_summary()

        first_column_texts = [
            self.widget.experiment_summary_table.item(row, 0).text()
            for row in range(self.widget.experiment_summary_table.rowCount())
        ]
        self.assertEqual(first_column_texts[0], "Posture")
        self.assertIn("Beta at t1-", first_column_texts)
        self.assertIn("Reference face", first_column_texts)
        self.assertLess(first_column_texts.index("Posture"), first_column_texts.index("Impact"))
        self.assertLess(first_column_texts.index("Impact"), first_column_texts.index("Contact"))

    def test_t1_based_summary_values_show_na_when_t1_is_not_detected(self):
        columns = pd.MultiIndex.from_tuples(
            [
                self._summary_column(HeaderL3.DROP_T1_DETECTED),
                self._summary_column(HeaderL3.DROP_BETA_AT_T1_MINUS_DEG),
                self._summary_column(HeaderL3.DROP_T1_MINUS_TIME_SEC),
                self._summary_column(HeaderL3.DROP_CONTACT_STATE),
            ]
        )
        self.widget.result_data = pd.DataFrame(
            [[False, 9.0, 1.23, "NoContact"]],
            columns=columns,
        )

        self.widget._update_drop_posture_summary()

        values_by_metric = {}
        for row in range(self.widget.experiment_summary_table.rowCount()):
            metric_item = self.widget.experiment_summary_table.item(row, 0)
            value_item = self.widget.experiment_summary_table.item(row, 1)
            if metric_item is not None and value_item is not None:
                values_by_metric[metric_item.text()] = value_item.text()

        self.assertEqual(values_by_metric["Beta at t1-"], "N/A")
        self.assertEqual(values_by_metric["t1-"], "N/A")
        self.assertEqual(values_by_metric["Contact state"], "NoContact")

    def test_summary_tooltip_comes_from_descriptor(self):
        column = self._summary_column(HeaderL3.DROP_BETA_AT_T1_MINUS_DEG)
        descriptor = get_result_metric_descriptor(column)
        self.widget.result_data = pd.DataFrame(
            [[True, 10.0]],
            columns=pd.MultiIndex.from_tuples(
                [
                    self._summary_column(HeaderL3.DROP_T1_DETECTED),
                    column,
                ]
            ),
        )

        self.widget._update_drop_posture_summary()

        for row in range(self.widget.experiment_summary_table.rowCount()):
            item = self.widget.experiment_summary_table.item(row, 0)
            if item is not None and item.text() == descriptor.display_name:
                self.assertEqual(item.toolTip(), descriptor.short_description)
                return
        self.fail("Descriptor-backed summary row was not found.")

    def test_metric_guide_dialog_uses_descriptors_and_visual_guides(self):
        descriptors = get_drop_posture_summary_descriptors()
        dialog = DropPostureMetricGuideDialog(descriptors, self.widget)
        try:
            labels = [label.text() for label in dialog.findChildren(QLabel)]

            self.assertTrue(any(descriptors[0].display_name in text for text in labels))
            self.assertTrue(any(descriptors[0].long_description in text for text in labels))
        finally:
            dialog.close()


if __name__ == "__main__":
    unittest.main()
