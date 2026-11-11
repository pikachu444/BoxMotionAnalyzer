"""Unit-GUI path layout checks; no data parsing or Raw analysis runs."""
import pytest
from PySide6.QtCore import Qt, QPoint
from PySide6.QtGui import QRegion
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from src.analysis.app.main_window import MainApp
from src.utils.qt_sections import set_path_label


def _fully_visible(widget, rect=None):
    rect = widget.rect() if rect is None else rect
    return widget.isVisible() and not rect.isEmpty() and QRegion(rect).subtracted(widget.visibleRegion()).isEmpty()


def test_full_visibility_rejects_partial_and_empty_regions():
    from PySide6.QtCore import QRect
    from PySide6.QtWidgets import QWidget

    app = QApplication.instance() or QApplication([])
    parent = QWidget()
    parent.resize(100, 50)
    child = QWidget(parent)
    child.setGeometry(75, 0, 50, 30)
    parent.show()
    app.processEvents()
    try:
        assert not child.visibleRegion().isEmpty()
        assert not _fully_visible(child)
        assert not _fully_visible(child, QRect())
        child.move(25, 0)
        app.processEvents()
        assert _fully_visible(child)
    finally:
        parent.close()


def test_long_paths_preserve_text_and_allow_plot_panel_resizing():
    app = QApplication.instance() or QApplication([])
    window = MainApp()
    path = ('C:\\SourceCodes\\BoxMotionAnalyzer\\tmp\\public_release\\inputs\\'
            + 'capture_' * 20 + '.csv')
    try:
        window.tab_widget.setCurrentIndex(0)
        widget = window.tab_widget.currentWidget()
        widget._set_file_path_display(path)
        labels = [widget.file_path_label, widget.slice_path_label]
        set_path_label(widget.slice_path_label, path + '.slice')
        assert widget.file_path_label.toolTip() == path
        window.show()
        assert QTest.qWaitForWindowExposed(window, 2000)
        # Windows may constrain the initial native window to the desktop.
        # Apply the layout-test size after those first geometry events settle.
        QTest.qWait(100)
        window.resize(1510, 800)
        QTest.qWait(100)
        splitter = widget.capture_splitter
        assert splitter.orientation() == Qt.Orientation.Vertical

        splitter.setSizes([450, 250])
        app.processEvents()
        wide_plot, narrow_panel = splitter.sizes()
        assert window.width() == 1510
        narrow_text = widget.file_path_label.text()
        assert widget.file_path_label.property('fullPath') == path
        assert widget.file_path_label.fontMetrics().horizontalAdvance(narrow_text) <= widget.file_path_label.width()

        splitter.setSizes([300, 400])
        app.processEvents()
        narrow_plot, wide_panel = splitter.sizes()
        assert narrow_plot < wide_plot
        assert wide_panel > narrow_panel
        assert widget.file_path_label.property('fullPath') == path
        assert widget.file_path_label.toolTip() == path
        assert widget.file_path_label.text().endswith('.csv')
        assert widget.file_path_label.fontMetrics().horizontalAdvance(widget.file_path_label.text()) <= widget.file_path_label.width()
        assert widget.slice_path_label.property('fullPath') == path + '.slice'
        assert widget.slice_path_label.toolTip() == path + '.slice'
        for label in labels:
            displayed = label.text()
            label.setSelection(0, len(displayed))
            assert label.selectedText() == displayed
            assert label.textInteractionFlags() & Qt.TextInteractionFlag.TextSelectableByMouse
    finally:
        window.close()
        window.deleteLater()
        app.processEvents()


@pytest.mark.parametrize('size', [(1510, 800), (1100, 720)])
def test_slice_actions_remain_visible_with_fixed_settings_and_modes(size):
    app = QApplication.instance() or QApplication([])
    window = MainApp()
    try:
        window.tab_widget.setCurrentIndex(1)
        widget = window.processing_widget
        path = 'C:/captures/' + 'long_folder/' * 15 + 'tilt.slice'
        set_path_label(widget.slice_path_label, path)
        window.show()
        assert QTest.qWaitForWindowExposed(window, 2000)
        window.resize(*size)
        for group in (widget.box_dims_group, widget.slice_summary_group, widget.resampling_group,
                      widget.method_controls, widget.log_group):
            assert not hasattr(group, 'button')
        app.processEvents()

        assert widget.slice_path_label.text() == 'tilt.slice'
        assert widget.slice_path_label.toolTip() == path
        for index, buttons in ((0, (widget.run_button, widget.save_view_button)),
                               (1, (widget.run_batch_button, widget.view_batch_button))):
            widget.input_mode_combo.setCurrentIndex(index)
            app.processEvents()
            for button in buttons:
                position = button.mapTo(window, QPoint(0, 0))
                assert _fully_visible(button)
                assert 0 <= position.y() and position.y() + button.height() <= window.height()
        assert window.width() == size[0] and window.height() == size[1]
    finally:
        window.close()
        window.deleteLater()
        app.processEvents()


def test_capture_fixed_review_keeps_four_rows_actions_and_toolbar(tmp_path):
    app = QApplication.instance() or QApplication([])
    window = MainApp()
    try:
        window.tab_widget.setCurrentIndex(0)
        capture = window.original_widget
        from src.simulation.scene_review_fixtures import install_ui_fixture, public_raw

        source = public_raw(tmp_path)
        source = source.rename(source.with_name('긴_장면_' * 20 + '.csv'))
        install_ui_fixture(capture, source)
        table = capture.scene_panel.table
        axes = capture.plot_manager.ax
        assert axes.xaxis.label.get_fontsize() == axes.yaxis.label.get_fontsize() == 9
        axes.yaxis.label.set_fontsize(13)
        window.show()
        assert QTest.qWaitForWindowExposed(window, 2000)
        for width, height in ((1510, 800), (1100, 720)):
            window.resize(width, height)
            closed_plot_height = None
            for tab_index in (1, 0, 0):
                window.tab_widget.setCurrentIndex(tab_index)
                window.tab_widget.setCurrentIndex(0)
                QTest.qWait(50)
                assert (window.width(), window.height()) == (width, height)
                assert axes.yaxis.label.get_fontsize() == 13
                plot_height = axes.get_window_extent().height
                if closed_plot_height is not None:
                    assert plot_height == pytest.approx(closed_plot_height, abs=1)
                closed_plot_height = plot_height
                capture.review_scroll.ensureWidgetVisible(table)
                app.processEvents()
                table.scrollToTop()
                for row in range(4):
                    assert _fully_visible(table.viewport(), table.visualItemRect(table.item(row, 0)))
                for control in (capture.load_csv_button, capture.scene_panel.detect_button,
                                capture.scene_panel.include_button, capture.scene_panel.exclude_button,
                                capture.le_slice_start, capture.le_slice_end, capture.save_slice_button,
                                capture.scene_panel.save_all_button, capture.save_process_button):
                    if capture.review_scroll.widget().isAncestorOf(control):
                        capture.review_scroll.ensureWidgetVisible(control)
                        app.processEvents()
                    position = control.mapTo(window, QPoint(0, 0))
                    assert _fully_visible(control), (width, height, control.objectName(), control.rect(), control.visibleRegion(), position)
                    assert 0 <= position.x() and position.x() + control.width() <= window.width()
                    assert 0 <= position.y() and position.y() + control.height() <= window.height()
                for action in capture.toolbar.actions():
                    if action.text():
                        button = capture.toolbar.widgetForAction(action)
                        assert button.isVisible() and button.focusPolicy() & Qt.TabFocus
        actions = {action.text(): action for action in capture.toolbar.actions() if action.text()}
        for label in ('Pan', 'Zoom'):
            button = capture.toolbar.widgetForAction(actions[label])
            button.setFocus()
            QTest.keyClick(button, Qt.Key_Space)
            assert capture.toolbar.mode.name == label.upper()
            QTest.keyClick(button, Qt.Key_Space)
            assert not capture.toolbar.mode
        row = table.item(3, 0)
        capture.review_scroll.ensureWidgetVisible(table)
        app.processEvents()
        QTest.mouseClick(table.viewport(), Qt.LeftButton, pos=table.visualItemRect(row).center())
        assert capture.scene_panel.selected_id() == row.text()
        QTest.mouseClick(capture.scene_panel.include_button, Qt.LeftButton)
        assert capture.scene_panel.selected_row()['decision'] == 'include'
        QTest.mouseClick(capture.scene_panel.exclude_button, Qt.LeftButton)
        assert capture.scene_panel.selected_row()['decision'] == 'exclude'

        window.resize(820, 600)
        QTest.qWait(50)
        assert (window.width(), window.height()) == (820, 600)
        desktop = window.screen().availableGeometry()
        # The offscreen plugin's 800px virtual screen cannot represent the
        # supported 820px client. Actual desktop bounds are a native gate.
        if app.platformName() == 'windows':
            assert window.frameGeometry().width() <= desktop.width()
            assert window.frameGeometry().height() <= desktop.height()
        table.scrollToBottom()
        capture.review_scroll.ensureWidgetVisible(table)
        app.processEvents()
        last = table.item(table.rowCount() - 1, 0)
        assert _fully_visible(table.viewport(), table.visualItemRect(last))
        assert capture.review_scroll.horizontalScrollBar().maximum() > 0
        assert _fully_visible(capture.save_process_button)
    finally:
        window.close()
        window.deleteLater()
        app.processEvents()
