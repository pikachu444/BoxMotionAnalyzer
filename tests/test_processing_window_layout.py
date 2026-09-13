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
        original_texts = [label.text() for label in labels]
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

        splitter.setSizes([650, 750])
        app.processEvents()
        narrow_plot, wide_panel = splitter.sizes()
        assert narrow_plot < wide_plot
        assert wide_panel > narrow_panel
        for label, original in zip(labels, original_texts):
            assert label.text() == original
            label.setSelection(0, len(original))
            assert label.selectedText() == original
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


def test_capture_allows_1100_width_with_details_open_and_closed():
    app = QApplication.instance() or QApplication([])
    window = MainApp()
    try:
        window.tab_widget.setCurrentIndex(0)
        capture = window.original_widget
        window.show()
        assert QTest.qWaitForWindowExposed(window, 2000)
        for expanded in (False, True, False):
            if capture.scene_panel.details_section.button.isChecked() != expanded:
                capture.scene_panel.details_section.button.click()
            app.processEvents()
            window.resize(1100, 720)
            app.processEvents()
            assert (window.width(), window.height()) == (1100, 720)
            for control in (capture.load_csv_button, capture.scene_panel.detect_button,
                            capture.scene_panel.include_button, capture.scene_panel.exclude_button,
                            capture.le_slice_start, capture.le_slice_end, capture.save_process_button):
                position = control.mapTo(window, QPoint(0, 0))
                assert control.isVisible() and not control.visibleRegion().isEmpty()
                assert 0 <= position.x() and position.x() + control.width() <= window.width()
                assert 0 <= position.y() and position.y() + control.height() <= window.height()
    finally:
        window.close()
        window.deleteLater()
        app.processEvents()
