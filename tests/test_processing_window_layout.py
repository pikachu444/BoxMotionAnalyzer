"""Unit-GUI path layout checks; no data parsing or Raw analysis runs."""
import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QSplitter

from src.analysis.app.main_window import MainApp


@pytest.mark.parametrize('tab_index', [0, 1], ids=['source', 'slice'])
def test_long_paths_preserve_text_and_allow_plot_panel_resizing(tab_index):
    app = QApplication.instance() or QApplication([])
    window = MainApp()
    path = ('C:\\SourceCodes\\BoxMotionAnalyzer\\tmp\\public_release\\inputs\\'
            + 'capture_' * 20 + '.csv')
    try:
        window.tab_widget.setCurrentIndex(tab_index)
        widget = window.tab_widget.currentWidget()
        if tab_index == 0:
            widget._set_file_path_display(path)
            labels = [widget.file_path_label, widget.slice_path_label]
            widget.slice_path_label.setText(path + '.slice')
            assert widget.file_path_label.toolTip() == path
        else:
            labels = [widget.slice_path_label, widget.slice_source_label,
                      widget.proc_path_label, widget.batch_folder_label]
            for label in labels:
                label.setText(path)
        original_texts = [label.text() for label in labels]
        window.resize(1510, 800)
        window.show()
        app.processEvents()
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
