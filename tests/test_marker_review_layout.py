"""PUB03 widget/render evidence; this never claims native Windows inspection."""
from dataclasses import replace
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys

import numpy as np
import pandas as pd
import pytest
from PySide6.QtCore import Qt, QPoint
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QDialogButtonBox

from src.analysis.ui.dialog_marker_flip_review import MarkerFlipReviewDialog
from test_marker_flip_review_dialog import _candidate, _hypothesis


LONG_SOURCE = 'public_synthetic_observations_' * 6 + '.csv'


def layout_fixture(count, unavailable=False):
    """Literal UI curves; no solver output or measured physical expectations."""
    candidates = [replace(_candidate(None if unavailable else 'X', event_id=f'ui-{i}',
        boundary_time_sec=10.2 + .3 * i,
        reason='Insufficient comparison samples.' if unavailable else 'Public UI fixture.'),
        correction_kind='face_assignment',
        pre_window_time_offsets_sec=(-.02, -.01), pre_window_residual_deg=(0., .2),
        post_window_time_offsets_sec=(0., .01, .02),
        post_window_raw_residual_deg=(179., np.nan, 177.),
        hypotheses=tuple(replace(_hypothesis(axis), residual_deg=178. if axis == 'NONE' else 1.5,
            trace_deg=() if unavailable else (179., np.nan, 177.) if axis == 'NONE' else (1., np.nan, 2.))
                         for axis in ('NONE', 'X', 'Y', 'Z'))) for i in range(count)]
    times = 10 + np.arange(800) * .01
    data = pd.DataFrame({'F1_X': 10 + (times - 10) * 20,
        'F1_Y': 180 - (times - 10) * 12, 'F1_Z': 7 + (times - 10) * 3}, index=times)
    data.iloc[10:12] = np.nan
    dialog = MarkerFlipReviewDialog(candidates)
    dialog.set_observation_context(data, units='Millimeters', source_path=LONG_SOURCE)
    return dialog, data


def settle(app, dialog):
    app.processEvents()
    # Activate queued canvas resizes/layout before measuring the renderer.
    for canvas in (dialog.context_canvas, dialog.evidence_canvas):
        canvas.draw()
    app.processEvents()


def reachable(widget, host):
    assert widget.isVisible()
    assert widget.visibleRegion().contains(widget.rect())
    point = widget.mapTo(host, widget.rect().center())
    child = host.childAt(point)
    assert child is widget or widget.isAncestorOf(child)


def assert_plot_labels(canvas):
    figure = canvas.figure
    renderer = canvas.get_renderer()
    axis = figure.axes[0]
    if not axis.axison:
        return
    labels = [axis.title, axis.xaxis.label, axis.yaxis.label,
              axis.xaxis.get_offset_text(), axis.yaxis.get_offset_text()]
    # Matplotlib's locators also return ticks outside the view interval;
    # those labels are never drawn and are not clipping failures.
    for locations, tick_labels, limits in ((axis.get_xticks(), axis.get_xticklabels(), axis.get_xlim()),
                                          (axis.get_yticks(), axis.get_yticklabels(), axis.get_ylim())):
        labels.extend(label for location, label in zip(locations, tick_labels)
                      if min(limits) <= location <= max(limits))
    for label in labels:
        if not label.get_visible() or not label.get_text():
            continue
        bounds = label.get_window_extent(renderer)
        assert bounds.x0 >= 0 and bounds.y0 >= 0, (label.get_text(), bounds)
        assert bounds.x1 <= figure.bbox.width and bounds.y1 <= figure.bbox.height, (label.get_text(), bounds)


@pytest.mark.parametrize('size', [(820, 600), (1280, 740)])
@pytest.mark.parametrize('count,expanded,unavailable', [
    (1, False, False), (24, False, False), (24, True, False),
    (1, True, True), (24, True, True), (0, True, False)])
def test_graphs_labels_units_and_controls_at_important_states(size, count, expanded, unavailable):
    app = QApplication.instance() or QApplication([])
    dialog, data = layout_fixture(count, unavailable)
    dialog.resize(*size)
    dialog.details_section.setExpanded(expanded)
    dialog.show()
    scale = os.environ.get('QT_SCALE_FACTOR', 'target')
    root = Path('tmp/issue136') / f'widget-{scale}'
    root.mkdir(parents=True, exist_ok=True)
    case = f'{size[0]}x{size[1]}-{count}-details-{expanded}-unavailable-{unavailable}'
    try:
        settle(app, dialog)
        assert (dialog.width(), dialog.height()) == size
        assert dialog._tabbed_plots == (size[0] < 1100)
        for index, canvas in enumerate((dialog.context_canvas, dialog.evidence_canvas)):
            if dialog._tabbed_plots:
                dialog.plot_tabs.setCurrentIndex(index)
            settle(app, dialog)
            reachable(canvas, dialog)
            assert_plot_labels(canvas)
            for button in (QDialogButtonBox.Ok, QDialogButtonBox.Cancel):
                reachable(dialog.button_box.button(button), dialog)
            if index == 0:
                reachable(dialog.around_event_button, dialog)
                reachable(dialog.context_toolbar, dialog)
                assert dialog.context_source.property('fullPath') == LONG_SOURCE
                assert dialog.context_source.toolTip().startswith(LONG_SOURCE)
                assert '…' in dialog.context_source.text()
                assert dialog.context_source.text().endswith('.csv')
                axis = canvas.figure.axes[0]
                assert axis.get_xlabel() == 'Time (s)' and axis.get_ylabel() == 'Position (mm)'
                np.testing.assert_array_equal(axis.lines[0].get_xdata(), data.index)
                np.testing.assert_allclose(axis.lines[0].get_ydata(), data.F1_X, equal_nan=True)
            elif count:
                axis = canvas.figure.axes[0]
                assert axis.get_xlabel() == 'Time from event (s)'
                assert axis.get_ylabel() == 'Relative rotation (°)'
                curves = {line.get_label(): line for line in axis.lines}
                np.testing.assert_allclose(curves['Original'].get_ydata(), (179., np.nan, 177.), equal_nan=True)
                if unavailable:
                    assert dialog.preview_status.text() == 'Preview unavailable'
                    reachable(dialog.preview_status, dialog)
                    assert dialog.table.item(0, 1).text() == 'No recommendation'
                else:
                    np.testing.assert_allclose(curves['Preview X'].get_ydata(), (1., np.nan, 2.), equal_nan=True)
            dialog.grab().save(str(root / f'{case}-view-{index}.png'))
        if count:
            dialog.axis_combo(count - 1).setCurrentText('Y')
            settle(app, dialog)
            reachable(dialog.axis_combo(count - 1), dialog)
            reachable(dialog.approval_checkbox(count - 1), dialog)
            assert dialog.table.currentRow() == count - 1
            assert all(not d.approved and d.axis is None for d in dialog.get_decisions())
        screen = app.primaryScreen()
        report = dict(schema_version=1, plan_spec='ISTA6A-PLAN-20261001-v1',
            case_id=case, status='pass', evidence_level='widget_render_and_qtest',
            native_windows={'status': 'pending', 'reason': 'Separate external capture/input required'},
            calibration_status='pending', input_kind='public_ui_fixture', seed=None,
            raw_sha256=None, raw_status='not_applicable_literal_ui_curves',
            input_digest=hashlib.sha256(data.to_csv().encode()).hexdigest(),
            code_commit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
            code_dirty=bool(subprocess.check_output(['git', 'status', '--porcelain'], text=True)),
            command=sys.argv, environment=dict(platform=platform.platform(), python=sys.version,
                qt_platform=app.platformName(), dpr=dialog.devicePixelRatioF(),
                screen=[screen.size().width(), screen.size().height()]),
            expected=dict(size=size, clipped_labels=0, automatic_approvals=0),
            actual=dict(size=[dialog.width(), dialog.height()], clipped_labels=0, automatic_approvals=0),
            difference=0, tolerance='exact_widget_size_and_data; rendered_labels_within_canvas',
            processing='not_applicable_no_pipeline_execution', independent_review='pending')
        (root / f'{case}.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    finally:
        dialog.reject()
        dialog.deleteLater()
        app.processEvents()


def test_resize_tabs_and_preview_preserve_pan_zoom_choices_and_explicit_apply():
    app = QApplication.instance() or QApplication([])
    dialog, _ = layout_fixture(24)
    dialog.resize(820, 600)
    dialog.show()
    try:
        settle(app, dialog)
        axis = dialog.context_figure.axes[0]
        before = axis.get_xlim()
        dialog.context_toolbar.pan()
        start = QPoint(dialog.context_canvas.width() // 2, dialog.context_canvas.height() // 2)
        QTest.mousePress(dialog.context_canvas, Qt.LeftButton, pos=start)
        QTest.mouseMove(dialog.context_canvas, start + QPoint(55, 0), delay=30)
        QTest.mouseRelease(dialog.context_canvas, Qt.LeftButton, pos=start + QPoint(55, 0))
        dialog.context_toolbar.pan()
        assert axis.get_xlim() != before
        dialog.context_toolbar.zoom()
        QTest.mousePress(dialog.context_canvas, Qt.LeftButton, pos=start - QPoint(60, 20))
        QTest.mouseMove(dialog.context_canvas, start + QPoint(60, 20), delay=30)
        QTest.mouseRelease(dialog.context_canvas, Qt.LeftButton, pos=start + QPoint(60, 20))
        dialog.context_toolbar.zoom()
        limits = (axis.get_xlim(), axis.get_ylim())
        assert limits[0][1] - limits[0][0] < before[1] - before[0]
        dialog.axis_combo(0).setCurrentText('Y')
        dialog.plot_tabs.setCurrentIndex(1)
        for width in (1100, 1099, 1280, 820):
            dialog.resize(width, 600)
            settle(app, dialog)
            assert dialog.context_figure.axes[0] is axis  # Layout never refits/recreates.
            assert (axis.get_xlim(), axis.get_ylim()) == limits
            assert not dialog.approval_checkbox(0).isChecked()
        assert dialog.plot_tabs.currentIndex() == 1
        QTest.mouseClick(dialog.approval_checkbox(0), Qt.LeftButton)
        assert dialog.get_decisions()[0].approved and dialog.get_decisions()[0].axis == 'Y'
        dialog.table.setCurrentCell(23, 0)
        assert dialog.context_figure.axes[0].get_xlim() == pytest.approx((16.85, 17.35))
        marker = dialog.context_figure.axes[0].lines[-1]
        np.testing.assert_allclose(marker.get_xdata(), (17.1, 17.1))
        dialog.table.setCurrentCell(0, 0)
        assert dialog.approval_checkbox(0).isChecked()
        dialog.plot_tabs.setCurrentIndex(0)
        settle(app, dialog)
        QTest.mouseClick(dialog.around_event_button, Qt.LeftButton)
        assert dialog.context_figure.axes[0].get_xlim() == pytest.approx(before)
        QTest.mouseClick(dialog.button_box.button(QDialogButtonBox.Cancel), Qt.LeftButton)
        assert dialog.result() == dialog.DialogCode.Rejected
        assert dialog._evidence_canvas_disposed and dialog._context_data is None
    finally:
        dialog.close()
        dialog.deleteLater()
        app.processEvents()
