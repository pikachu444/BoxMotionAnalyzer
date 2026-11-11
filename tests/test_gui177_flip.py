"""GUI-04 approval and evidence contracts; synthetic data is not physical validation."""
from dataclasses import replace
from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QRegion
from PySide6.QtTest import QTest, QSignalSpy
from PySide6.QtWidgets import QApplication, QDialogButtonBox, QPushButton

from src.analysis.ui.dialog_marker_flip_review import MarkerFlipReviewDialog
from test_marker_review_layout import layout_fixture, settle


def fully_visible(widget, rect=None):
    rect = widget.rect() if rect is None else rect
    return widget.isVisible() and not rect.isEmpty() and QRegion(rect).subtracted(widget.visibleRegion()).isEmpty()


@pytest.fixture
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def review(app):
    dialog, data = layout_fixture(6)
    dialog.show()
    settle(app, dialog)
    yield dialog, data
    dialog.close()
    dialog.deleteLater()
    app.processEvents()


def test_f01_counts_responsive_rows_identity_and_fixed_actions(app, review):
    dialog, data = review
    snapshot = data.copy(deep=True)
    boxes = tuple(dialog._approval_checkboxes)
    combos = tuple(dialog._axis_combos)
    canvases = (dialog.context_canvas, dialog.evidence_canvas)
    identities = [candidate.event_id for candidate in dialog.candidates]
    for size, visible_rows in [((1280, 740), 4), ((820, 600), 3), ((1100, 720), 4), ((1280, 740), 4)]:
        dialog.resize(*size)
        settle(app, dialog)
        assert (dialog.width(), dialog.height()) == size
        assert dialog.approval_status.text() == '6 candidates | Correction ON: 0 | Axis missing: 0'
        assert fully_visible(dialog.approval_status)
        assert dialog.table.columnCount() == 5
        assert dialog.table.horizontalScrollBar().maximum() == 0
        visible = sum(fully_visible(dialog.table.viewport(), dialog.table.visualItemRect(dialog.table.item(row, 0)))
                      for row in range(dialog.table.rowCount()))
        assert visible == visible_rows
        for row in range(visible_rows):
            assert fully_visible(boxes[row]) and fully_visible(combos[row])
        for button in (QDialogButtonBox.Ok, QDialogButtonBox.Cancel):
            assert fully_visible(dialog.button_box.button(button))
        assert dialog.button_box.button(QDialogButtonBox.Ok).isEnabled()
        assert tuple(dialog._approval_checkboxes) == boxes
        assert tuple(dialog._axis_combos) == combos
        assert (dialog.context_canvas, dialog.evidence_canvas) == canvases
        assert [dialog.table.item(row, 1).data(Qt.UserRole) for row in range(6)] == identities
        assert all(not decision.approved and decision.axis is None for decision in dialog.get_decisions())
    pd.testing.assert_frame_equal(data, snapshot)
    assert not fully_visible(dialog.table.viewport(), dialog.table.viewport().rect().translated(0, 1000))
    assert not fully_visible(dialog.table.viewport(), dialog.table.viewport().rect().adjusted(0, 0, 0, 10))


def test_f02_on_none_gate_off_and_axis_exploration_emit_real_signals(app, review):
    dialog, _ = review
    checkbox, combo = dialog.approval_checkbox(0), dialog.axis_combo(0)
    others = dialog.get_decisions()[1:]
    toggled, selected = QSignalSpy(checkbox.toggled), QSignalSpy(combo.currentIndexChanged)
    done = dialog.button_box.button(QDialogButtonBox.Ok)
    QTest.mouseClick(checkbox, Qt.LeftButton)
    combo.setFocus()
    QTest.keyClick(combo, Qt.Key_Home)
    assert checkbox.isChecked() and combo.currentData() is None
    assert dialog.approval_status.text() == '6 candidates | Correction ON: 1 | Axis missing: 1'
    assert not done.isEnabled()
    with patch('src.analysis.ui.dialog_marker_flip_review.QMessageBox.warning') as warning:
        dialog.accept()
        warning.assert_called_once()
    assert dialog.isVisible() and not dialog._evidence_canvas_disposed
    QTest.mouseClick(checkbox, Qt.LeftButton)
    assert done.isEnabled()
    for axis in 'XYZ':
        QTest.keyClick(combo, Qt.Key_Down)
        assert combo.currentData() == axis
        assert not checkbox.isChecked()
        assert done.isEnabled()
    assert toggled.count() == 2 and selected.count() == 4
    assert dialog.get_decisions()[1:] == others
    assert dialog.get_decisions()[0].axis is None
    QTest.mouseClick(done, Qt.LeftButton)
    assert dialog.result() == dialog.DialogCode.Accepted


@pytest.mark.parametrize('count', [0, 1, 24])
def test_f03_real_missing_data_and_reused_nonmodal_evidence(app, count):
    dialog, data = layout_fixture(count, unavailable=True)
    original = data.copy(deep=True)
    dialog.resize(820, 600)
    dialog.show()
    try:
        settle(app, dialog)
        assert dialog.table.rowCount() == count
        assert fully_visible(dialog.button_box.button(QDialogButtonBox.Cancel))
        recorded = dialog.context_figure.axes[0].lines[0].get_ydata()
        assert np.isnan(recorded[10:12]).all()
        if count:
            dialog.table.setCurrentCell(count-1, 0)
            QTest.mouseClick(dialog.evidence_button, Qt.LeftButton)
            popup = dialog.evidence_dialog
            assert popup.isVisible() and not popup.isModal()
            assert dialog.evidence_text.isReadOnly()
            assert 'Insufficient comparison samples.' in dialog.evidence_text.toPlainText()
            assert not any(button.text() in ('Done', 'ON', 'Approve') for button in popup.findChildren(QPushButton))
            popup.close()
            QTest.mouseClick(dialog.evidence_button, Qt.LeftButton)
            assert dialog.evidence_dialog is popup
            curves = {line.get_label(): line for line in dialog.evidence_figure.axes[0].lines}
            np.testing.assert_array_equal(curves['Original'].get_ydata(), [179., np.nan, 177.])
            assert not any(name.startswith(('Preview ', 'Predicted ')) for name in curves)
            assert dialog.preview_status.text() == 'Preview evidence unavailable'
            QTest.mouseClick(dialog.copy_diagnostics_button, Qt.LeftButton)
            assert QApplication.clipboard().text() == dialog.evidence_text.toPlainText()
        else:
            assert not dialog.evidence_button.isEnabled()
        pd.testing.assert_frame_equal(data, original)
    finally:
        dialog.reject()
        if count:
            assert not popup.isVisible()
        dialog.deleteLater()
        app.processEvents()


def test_f03_without_evidence_does_not_invent_traces(app):
    fixture, _ = layout_fixture(1)
    candidate = replace(fixture.candidates[0], trigger='Long reconnect event ' * 80,
        reason='Supplied reason only. ' * 100, hypotheses=(), pre_window_time_offsets_sec=(),
        pre_window_residual_deg=(), post_window_time_offsets_sec=(),
        post_window_raw_residual_deg=(), post_window_best_residual_deg=())
    fixture.close()
    dialog = MarkerFlipReviewDialog([candidate])
    dialog.resize(820, 600)
    dialog.show()
    try:
        settle(app, dialog)
        axis = dialog.evidence_figure.axes[0]
        assert not axis.lines and not axis.patches
        assert any(text.get_text() == 'Preview evidence unavailable' for text in axis.texts)
        assert (dialog.width(), dialog.height()) == (820, 600)
        assert fully_visible(dialog.button_box.button(QDialogButtonBox.Ok))
        QTest.mouseClick(dialog.evidence_button, Qt.LeftButton)
        assert candidate.reason in dialog.evidence_text.toPlainText()
    finally:
        dialog.close()
        dialog.deleteLater()
        app.processEvents()


def test_aggregate_only_evidence_uses_actual_bars_without_timestamps(app):
    fixture, _ = layout_fixture(1)
    candidate = replace(fixture.candidates[0], correction_kind='marker_label',
        pre_window_time_offsets_sec=(), pre_window_residual_deg=(),
        post_window_time_offsets_sec=(), post_window_raw_residual_deg=(),
        post_window_best_residual_deg=())
    fixture.close()
    dialog = MarkerFlipReviewDialog([candidate])
    try:
        axis = dialog.evidence_figure.axes[0]
        assert not axis.lines
        np.testing.assert_allclose([bar.get_height() for bar in axis.patches],
                                   [hypothesis.residual_deg for hypothesis in candidate.hypotheses])
        assert axis.get_xlabel() == 'Hypothesis'
        assert not dialog.approval_checkbox(0).isChecked()
    finally:
        dialog.close()
        dialog.deleteLater()
        app.processEvents()
