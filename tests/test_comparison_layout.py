"""Unit-GUI layout/identification contracts; no Raw or optimizer execution."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from comparison_fixtures import write_proc
from src.analysis.compare.main_window import CompareMainWindow


def test_numbered_legend_stays_outside_axes_and_keeps_individual_file_identity(tmp_path):
    app = QApplication.instance() or QApplication([])
    window = CompareMainWindow()
    names = []
    try:
        # Reopen existing-format result contracts; no 3D viewers are constructed
        # for this focused graph/list test. Real VTK layout is checked separately.
        for index in range(9):
            path = write_proc(tmp_path / (f'{index:02}_' + 'long_name_' * 10 + '.proc'))
            names.append(window.model.load_file(str(path)))
        window.control_panel.update_files(names, names[0], window.model)
        window.table_panel.update_table(window.model.get_summary_differences(), names[0],
                                        window.model.get_impact_comparison())
        window.graph_panel.set_plot_targets(['Analysis | DropPosture | ThetaLongDeg'])
        window.show()
        for width, height in ((1510, 800), (1100, 700)):
            window.resize(width, height)
            app.processEvents()
            graph = window.graph_panel
            graph.canvas.draw()
            renderer = graph.canvas.get_renderer()
            axes_box = graph.plot_manager.ax.get_window_extent(renderer)
            legend = graph.plot_manager.ax.get_legend()
            assert [text.get_text() for text in legend.get_texts()] == [str(i) for i in range(1, 10)]
            assert legend.get_window_extent(renderer).y0 >= axes_box.y1
            assert legend.get_window_extent(renderer).x1 <= graph.fig.bbox.x1
            assert not legend.get_window_extent(renderer).overlaps(axes_box)
            table = window.table_panel.table
            # Content may raise the small window's minimum height; a metric
            # must remain readable while the frame still fits the desktop.
            assert table.viewport().rect().contains(table.visualItemRect(table.item(0, 0)))
            assert window.width() == width and window.height() >= height
            assert window.frameGeometry().width() * window.devicePixelRatioF() <= 1920
            assert window.frameGeometry().height() * window.devicePixelRatioF() <= 1080
            for index, name in enumerate(names, 1):
                item = window.control_panel.file_list.item(index - 1)
                assert item.text().startswith(f'{index}. {name}\n')
                assert item.data(Qt.UserRole) == name
                assert name in item.toolTip()

        window.control_panel.cb_view.setCurrentIndex(window.control_panel.cb_view.findData(names[-1]))
        app.processEvents()
        assert [text.get_text() for text in graph.plot_manager.ax.get_legend().get_texts()] == ['9']
        curve, = graph.plot_manager.ax.lines
        expected = window.model.get_timeseries_data('Analysis', 'DropPosture', 'ThetaLongDeg', individual=names[-1])[names[-1]]
        assert list(curve.get_xdata()) == list(expected.index)
        assert list(curve.get_ydata()) == list(expected.values)
    finally:
        window.close()
        window.deleteLater()
        app.processEvents()
