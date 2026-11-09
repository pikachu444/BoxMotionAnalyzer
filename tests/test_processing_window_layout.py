"""Unit-GUI path layout checks; no data parsing or Raw analysis runs."""
import pytest
from PySide6.QtCore import Qt, QPoint
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QSplitter

from src.analysis.app.main_window import MainApp
from src.utils.qt_sections import set_path_label


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
        widget.slice_path_label.setText(path + '.slice')
        assert widget.file_path_label.toolTip() == path
        window.show()
        assert QTest.qWaitForWindowExposed(window, 2000)
        # Windows may constrain the initial native window to the desktop.
        # Apply the layout-test size after those first geometry events settle.
        QTest.qWait(100)
        window.resize(1510, 800)
        QTest.qWait(100)
        splitter, = [item for item in widget.findChildren(QSplitter)
                     if item.orientation() == Qt.Orientation.Horizontal]

        splitter.setSizes([1000, 400])
        app.processEvents()
        wide_plot, narrow_panel = splitter.sizes()
        assert wide_plot > 1.5 * narrow_panel
        assert window.width() == 1510
        narrow_text = widget.file_path_label.text()
        assert widget.file_path_label.property('fullPath') == path
        assert widget.file_path_label.fontMetrics().horizontalAdvance(narrow_text) <= widget.file_path_label.width()

        splitter.setSizes([650, 750])
        app.processEvents()
        narrow_plot, wide_panel = splitter.sizes()
        assert narrow_plot < wide_plot
        assert wide_panel > narrow_panel
        assert widget.file_path_label.property('fullPath') == path
        assert widget.file_path_label.toolTip() == path
        assert widget.file_path_label.text().endswith('.csv')
        assert widget.file_path_label.fontMetrics().horizontalAdvance(widget.file_path_label.text()) <= widget.file_path_label.width()
        assert widget.slice_path_label.text() == path + '.slice'
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
def test_slice_actions_remain_visible_when_optional_settings_expand(size):
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
        for section in (widget.box_section, widget.details_section, widget.resampling_section,
                        widget.advanced_section, widget.log_section):
            section.button.click()
        app.processEvents()

        assert widget.slice_path_label.text() == 'tilt.slice'
        assert widget.slice_path_label.toolTip() == path
        for index, buttons in ((0, (widget.run_button, widget.save_view_button)),
                               (1, (widget.run_batch_button, widget.view_batch_button))):
            widget.input_mode_combo.setCurrentIndex(index)
            app.processEvents()
            for button in buttons:
                position = button.mapTo(window, QPoint(0, 0))
                assert button.isVisible() and not button.visibleRegion().isEmpty()
                assert 0 <= position.y() and position.y() + button.height() <= window.height()
        assert window.width() == size[0] and window.height() == size[1]
    finally:
        window.close()
        window.deleteLater()
        app.processEvents()


def test_capture_allows_1100_width_with_details_open_and_closed(tmp_path):
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
            for expanded in (False, True, False):
                capture.scene_panel.details_section.setExpanded(expanded)
                QTest.qWait(50)
                assert (window.width(), window.height()) == (width, height)
                assert axes.yaxis.label.get_fontsize() == 13
                if not expanded:
                    plot_height = axes.get_window_extent().height
                    if closed_plot_height is not None:
                        assert plot_height == pytest.approx(closed_plot_height, abs=1)
                    closed_plot_height = plot_height
                table.scrollToTop()
                for row in range(4):
                    assert table.viewport().rect().contains(table.visualItemRect(table.item(row, 0)))
                for control in (capture.load_csv_button, capture.scene_panel.detect_button,
                                capture.scene_panel.include_button, capture.scene_panel.exclude_button,
                                capture.le_slice_start, capture.le_slice_end, capture.save_slice_button,
                                capture.scene_panel.save_all_button, capture.save_process_button):
                    position = control.mapTo(window, QPoint(0, 0))
                    assert control.isVisible() and control.visibleRegion().contains(control.rect())
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
        QTest.mouseClick(table.viewport(), Qt.LeftButton, pos=table.visualItemRect(row).center())
        assert capture.scene_panel.selected_id() == row.text()
        QTest.mouseClick(capture.scene_panel.include_button, Qt.LeftButton)
        assert capture.scene_panel.selected_row()['decision'] == 'include'
        QTest.mouseClick(capture.scene_panel.exclude_button, Qt.LeftButton)
        assert capture.scene_panel.selected_row()['decision'] == 'exclude'

        window.resize(820, 600)
        capture.scene_panel.details_section.setExpanded(True)
        QTest.qWait(50)
        assert window.width() < 1100 or window.height() < 720
        desktop = window.screen().availableGeometry()
        assert window.frameGeometry().width() <= desktop.width()
        assert window.frameGeometry().height() <= desktop.height()
        table.scrollToBottom()
        last = table.item(table.rowCount() - 1, 0)
        assert table.viewport().rect().contains(table.visualItemRect(last))
        assert capture.scene_panel.details_scroll.verticalScrollBar().maximum() > 0
        assert capture.save_process_button.visibleRegion().contains(capture.save_process_button.rect())
    finally:
        window.close()
        window.deleteLater()
        app.processEvents()
