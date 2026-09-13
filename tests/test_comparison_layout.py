"""Qt layout/state contracts. VTK is replaced here; native rendering is reviewed separately."""
from types import SimpleNamespace
from unittest.mock import Mock

import numpy as np
import pandas as pd
import pytest
from PySide6.QtCore import Qt, QPoint
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QWidget, QMessageBox, QComboBox

from comparison_fixtures import write_proc, identity
from src.analysis.compare.main_window import CompareMainWindow
from src.config import config_visualization as k
from src.utils.result_time import TIME_COLUMN, T1_DETECTED_COLUMN
from src.visualization.vista_widget import VistaWidget
from src.utils.qt_sections import find_result_column_index


@pytest.fixture
def comparison(monkeypatch):
    class FrameViewer(QWidget):
        def __init__(self, data_handler):
            super().__init__()
            self.data_handler = data_handler
            self.plotter = SimpleNamespace(camera=Mock(focal_point=(0., 0., 0.), distance=10.),
                                           reset_camera=Mock(), reset_camera_clipping_range=Mock(),
                                           render=Mock(), camera_position=None)
            self.edge_property = Mock()
            self.actors = {k.SK_ACTOR_BOX_EDGES: SimpleNamespace(GetProperty=lambda: self.edge_property)}
            self.cleanup = Mock()
            self.last_row = None
            self.set_actor_visibility = Mock()

        view_isometric = VistaWidget.view_isometric

        def update_view(self, row):
            self.last_row = row

    monkeypatch.setattr('src.analysis.compare.playback_panel.VistaWidget', FrameViewer)
    app = QApplication.instance() or QApplication([])
    window = CompareMainWindow()
    window.show()
    app.processEvents()
    yield app, window
    window.close()
    window.deleteLater()
    app.processEvents()


def _curve(window, name):
    return next(line for line in window.graph_panel.plot_manager.ax.lines if line.get_label() == name)


def test_file_names_colours_selection_and_small_layout(tmp_path, comparison):
    app, window = comparison
    paths = [write_proc(tmp_path / (f'{index:02}_' + 'long_name_' * 10 + '.proc'), offset=index)
             for index in range(9)]
    corner = ('Analysis', 'DropPosture', 'CminIndex')
    slope = ('Analysis', 'DropPosture', 'ThetaLongDeg')
    for index, path in enumerate(paths):
        frame = pd.read_csv(path, header=[0, 1, 2])
        frame[corner] = index % 8 + 1
        frame.to_csv(path, index=False)
    window.load_result_files([str(path) for path in paths])
    target = window.graph_panel.cb_plot_target
    target.setCurrentIndex(find_result_column_index(target, slope))
    names = list(window.model.datasets)
    assert window.control_panel.cb_view.currentData() == 'individual'
    assert not window.control_panel.details_section.button.isChecked()
    assert not window.control_panel.settings_section.button.isChecked()
    assert window.control_panel.gap_limit.value() == .1
    assert window.control_panel.selected_file == names[0]
    assert list(window.graph_panel.legend_labels) == [names[0]]

    window.control_panel.file_list.setCurrentRow(8)
    viewer = window.playback_panel.widgets[names[-1]]
    viewer.plotter.camera_position = 'user camera'
    window.playback_panel.master_slider.setValue(2)
    assert viewer.last_row == 2
    curve = _curve(window, names[-1])
    expected = window.model.get_timeseries_data('Analysis', 'DropPosture', 'ThetaLongDeg', individual=names[-1])[names[-1]]
    np.testing.assert_array_equal(curve.get_xdata(), expected.index)
    np.testing.assert_array_equal(curve.get_ydata(), expected.values)
    color = curve.get_color()
    assert window.control_panel.file_list.currentItem().data(Qt.UserRole + 1) == color
    assert window.graph_panel.legend_labels[names[-1]].property('fileColor') == color
    assert window.graph_panel.legend_labels[names[-1]].toolTip() == str(paths[-1])
    assert window.playback_panel.containers[names[-1]].isVisible()
    assert all(window.playback_panel.containers[name].isHidden() for name in names[:-1])
    edge_rgb = viewer.edge_property.SetColor.call_args.args
    from PySide6.QtGui import QColor
    assert edge_rgb == (QColor(color).redF(), QColor(color).greenF(), QColor(color).blueF())

    window.control_panel.cb_view.setCurrentIndex(1)
    assert set(window.graph_panel.legend_labels) == set(names)
    assert all(not container.isHidden() for container in window.playback_panel.containers.values())
    for expanded in (False, True):
        window.control_panel.details_section.setExpanded(expanded)
        window.control_panel.settings_section.setExpanded(expanded)
        for width, height in ((1510, 800), (1100, 720)):
            window.resize(width, height)
            QTest.qWait(30)
            assert (window.width(), window.height()) == (width, height)
            table = window.table_panel.table
            # Contact uses two-line filename/source rows; returning to a
            # numeric mode must remeasure those rows, including after resize.
            for mode in (0, 1, 2, 3, 0):
                window.table_panel.view_combo.setCurrentIndex(mode)
                QTest.qWait(20)
                table.setFocus()
                QTest.keyClick(table, Qt.Key_Home, Qt.ControlModifier)
                assert table.viewport().rect().contains(table.visualItemRect(table.item(0, 0)))
                QTest.keyClick(table, Qt.Key_End, Qt.ControlModifier)
                table.horizontalScrollBar().setValue(0)
                assert table.currentRow() == table.rowCount() - 1
                assert table.viewport().rect().contains(table.visualItemRect(table.item(table.currentRow(), 0)))
                table.scrollToTop()
            # Horizontal comparison scrolling must not hide the sample text
            # underneath the render surface at either end of the file list.
            playback = window.playback_panel
            for name in (names[0], names[-1]):
                label = playback.local_controls[name]['label']
                playback.scroll.ensureWidgetVisible(playback.containers[name])
                app.processEvents()
                assert label.visibleRegion().contains(label.rect())
            playback.scroll.horizontalScrollBar().setValue(0)
            for button in (window.control_panel.btn_add_files, window.control_panel.btn_remove_file,
                           window.control_panel.cb_view, window.playback_panel.btn_master_play,
                           window.playback_panel.master_slider, window.graph_panel.cb_plot_target):
                assert not button.visibleRegion().isEmpty()
                origin = button.mapTo(window, QPoint(0, 0))
                assert window.rect().contains(origin) and window.rect().contains(origin + button.rect().bottomRight())
            graph = window.graph_panel
            # Rebuild the nine-file legend through real metric and view
            # changes; readable strings must not be squeezed to one glyph.
            target.setCurrentIndex(find_result_column_index(target, corner))
            window.control_panel.cb_view.setCurrentIndex(0)
            window.control_panel.cb_view.setCurrentIndex(1)
            app.processEvents()
            assert graph.legend_scroll.geometry().bottom() < graph.canvas.geometry().top()
            assert graph.plot_manager.ax.get_legend() is None
            assert graph.canvas.height() >= 130
            for name in names:
                assert _curve(window, name).get_color() == window.model.file_colors[name]
                label = graph.legend_labels[name]
                assert not label.text().isdigit() and name[:3] in label.text()
                assert window.model.file_paths[name] == label.toolTip()
                assert label.width() >= label.fontMetrics().horizontalAdvance(label.text())
            assert graph.legend_scroll.horizontalScrollBar().maximum() > 0
            for name in (names[0], names[-1]):
                label = graph.legend_labels[name]
                graph.legend_scroll.ensureWidgetVisible(label)
                app.processEvents()
                assert label.visibleRegion().contains(label.rect())
            graph.legend_scroll.horizontalScrollBar().setValue(0)

    window.control_panel.cb_baseline.setCurrentIndex(1)
    assert window.control_panel.selected_file == names[-1]
    assert window.playback_panel.widgets[names[-1]] is viewer
    assert viewer.plotter.camera_position == 'user camera'
    window._on_remove_file(names[0])
    assert window.control_panel.selected_file == names[-1]
    assert _curve(window, names[-1]).get_color() == color
    assert window.model.baseline_name == names[1]
    window.control_panel.cb_view.setCurrentIndex(0)
    assert window.playback_panel.master_slider.value() == 2
    assert viewer.last_row == 2
    assert list(window.graph_panel.legend_labels) == [names[-1]]


def test_shared_view_no_impact_invalid_time_and_gap(tmp_path, comparison):
    app, window = comparison
    paths = [write_proc(tmp_path / 'normal.proc'),
             write_proc(tmp_path / 'gap.proc', times=(1., 1.01, 1.04, 2., 2.02)),
             write_proc(tmp_path / 'no_impact.proc'),
             write_proc(tmp_path / 'no_time.proc')]
    no_impact = pd.read_csv(paths[2], header=[0, 1, 2])
    no_impact[T1_DETECTED_COLUMN] = False
    no_impact.to_csv(paths[2], index=False)
    no_time = pd.read_csv(paths[3], header=[0, 1, 2]).drop(columns=[TIME_COLUMN])
    no_time.to_csv(paths[3], index=False)
    window.load_result_files([str(path) for path in paths])
    panel = window.playback_panel
    window.control_panel.file_list.setCurrentRow(2)
    panel.master_slider.setValue(2)
    assert panel.widgets[paths[2].name].last_row == 2
    assert panel.btn_master_play.isEnabled()
    assert list(window.graph_panel.legend_labels) == [paths[2].name]
    window.control_panel.file_list.setCurrentRow(3)
    panel.master_slider.setValue(1)
    assert not panel.btn_master_play.isEnabled()
    assert panel.master_slider.isEnabled()
    assert panel.widgets[paths[3].name].last_row == 1
    np.testing.assert_array_equal(_curve(window, paths[3].name).get_xdata(), [1, 2, 3])
    assert window.graph_panel.cursor.get_xdata()[0] == 2
    assert window.graph_panel.plot_manager.ax.get_xlabel() == 'Sample'
    window.control_panel.cb_view.setCurrentIndex(1)
    start, end = panel.bounds
    panel.master_slider.setValue(round(100000 * (.5 - start) / (end - start)))
    assert all(viewer.isHidden() for viewer in panel.widgets.values())
    assert paths[2].name not in window.graph_panel.legend_labels
    assert paths[3].name not in window.graph_panel.legend_labels
    assert np.isnan(_curve(window, paths[1].name).get_ydata()).sum() == 1
    window.control_panel.cb_view.setCurrentIndex(0)
    assert panel.master_slider.value() == 1
    assert not panel.widgets[paths[3].name].isHidden()


def test_reload_only_changed_viewer_and_preserve_context_on_failure(tmp_path, comparison, monkeypatch):
    app, window = comparison
    paths = [write_proc(tmp_path / 'a.proc'), write_proc(tmp_path / 'b.proc')]
    window.load_result_files([str(path) for path in paths], deduplicate=True)
    window.control_panel.file_list.setCurrentRow(1)
    window.control_panel.cb_baseline.setCurrentIndex(1)
    previous = dict(window.playback_panel.widgets)
    colors = dict(window.model.file_colors)
    window.playback_panel.master_slider.setValue(2)
    window.load_result_files([str(paths[0]), str(paths[1])], deduplicate=True)
    assert window.playback_panel.widgets == previous
    write_proc(paths[0], times=(2., 2.01, 2.02, 2.03), t1=2.01, offset=7)
    window.load_result_files([str(paths[0])], deduplicate=True)
    assert window.playback_panel.widgets[paths[0].name] is not previous[paths[0].name]
    previous[paths[0].name].cleanup.assert_called_once()
    assert window.playback_panel.widgets[paths[1].name] is previous[paths[1].name]
    assert window.model.file_colors == colors
    assert window.control_panel.selected_file == paths[1].name
    assert window.model.baseline_name == paths[1].name
    assert window.playback_panel.master_slider.value() == 2
    assert window.model.datasets[paths[0].name].shape[0] == 4
    errors = []
    monkeypatch.setattr(QMessageBox, 'warning', lambda *args: errors.append(args[2]))
    paths[1].write_text('not a result', encoding='utf-8')
    window.load_result_files([str(paths[1])], deduplicate=True)
    assert errors
    assert window.playback_panel.widgets[paths[1].name] is previous[paths[1].name]
    assert window.control_panel.selected_file == paths[1].name
    assert window.playback_panel.master_slider.value() == 2


def test_category_graph_and_summary_preserve_ids_without_numeric_differences(tmp_path, comparison):
    app, window = comparison
    corner = ('Analysis', 'DropPosture', 'CminIndex')
    summary = ('Analysis', 'DropPostureSummary', 'CminAtT1MinusIndex')
    face = ('Analysis', 'DropPostureSummary', 'RefFaceAtT1Minus')
    paths = [write_proc(tmp_path / 'baseline.proc'), write_proc(tmp_path / 'other.proc')]
    for path, ids, lowest, ref_face in zip(paths, [[5., 5., 5.], [6., 1.5, 9.]], [5, 6], ['BOTTOM', 'FRONT']):
        df = pd.read_csv(path, header=[0, 1, 2])
        df[corner], df[summary], df[face] = ids, lowest, ref_face
        df.to_csv(path, index=False)
    window.load_result_files([str(path) for path in paths])
    window.control_panel.file_list.setCurrentRow(1)
    target = window.graph_panel.cb_plot_target
    target.setCurrentIndex(find_result_column_index(target, corner))
    assert tuple(target.currentData()) == corner
    # Rebuilding entries creates different Python tuples for the same column.
    # Selection must survive this refresh as well as the initial lookup.
    window.graph_panel.set_plot_targets([('Analysis', 'DropPosture', 'ThetaLongDeg'), tuple(list(corner))])
    assert tuple(target.currentData()) == corner
    line = _curve(window, paths[1].name)
    assert line.get_linestyle() == 'None'
    np.testing.assert_allclose(line.get_ydata(), [6., np.nan, np.nan], equal_nan=True)
    np.testing.assert_array_equal(window.model.datasets[paths[1].name][corner], [6., 1.5, 9.])
    assert [label.get_text() for label in window.graph_panel.plot_manager.ax.get_yticklabels()] == [f'C{i}' for i in range(1, 9)]
    # C1-C8 must fit at the actual small size, and window growth must reach
    # the graph instead of stretching the one-line status above the views.
    geometries = []
    for width, height in ((1100, 720), (1510, 800)):
        window.resize(width, height)
        QTest.qWait(30)
        graph = window.graph_panel
        graph.canvas.draw()
        renderer = graph.canvas.get_renderer()
        boxes = [label.get_window_extent(renderer) for label in graph.plot_manager.ax.get_yticklabels()]
        assert all(first.y1 < second.y0 for first, second in zip(boxes, boxes[1:]))
        assert (window.width(), window.height()) == (width, height)
        geometries.append((window.warning_label.height(), graph.canvas.height()))
    assert geometries[0][0] == geometries[1][0]
    assert geometries[1][1] > geometries[0][1]
    window.table_panel.view_combo.setCurrentIndex(2)
    data = window.model.get_summary_differences()
    keys = list(dict.fromkeys(key for value in data.values() for key in value['summary']))
    table = window.table_panel.table
    assert table.item(keys.index(summary[2]), 2).text() == 'C6 (vs C5)'
    assert table.item(keys.index(face[2]), 2).text() == 'FRONT (vs BOTTOM)'
    window.model.datasets[paths[1].name][summary] = 1.5
    window._on_baseline_changed(paths[0].name)
    assert table.item(keys.index(summary[2]), 2).text() == 'Unknown'


def test_missing_identity_is_neutral_and_mixed_aligned_sources_stay_visible(tmp_path, comparison):
    app, window = comparison
    paths = [write_proc(tmp_path / 'incomplete.proc', metadata=identity(ModelId='')),
             write_proc(tmp_path / 'other_source.proc', metadata=identity(SourceKind='real'))]
    window.load_result_files([str(path) for path in paths])
    first = window.control_panel.file_list.item(0)
    assert 'Not comparable' in first.text()
    assert 'Different setup' not in first.text()
    assert 'ModelId: missing' in first.toolTip()
    assert 'Mixed sources' not in window.warning_label.text()
    window.control_panel.cb_view.setCurrentIndex(1)
    assert 'Mixed sources' in window.warning_label.text()
    assert set(window.graph_panel.legend_labels) == {path.name for path in paths}
    assert all(window.model.exclusion_reasons(path.name) for path in paths)
    window.control_panel.cb_view.setCurrentIndex(0)
    assert 'Mixed sources' not in window.warning_label.text()


def test_calibration_badge_and_time_tooltip_follow_current_view(tmp_path, comparison):
    app, window = comparison
    paths = [write_proc(tmp_path / 'recorded.proc'), write_proc(tmp_path / 'no_time.proc')]
    frame = pd.read_csv(paths[1], header=[0, 1, 2]).drop(columns=[TIME_COLUMN])
    frame.to_csv(paths[1], index=False)
    window.load_result_files([str(path) for path in paths])
    table = window.table_panel
    for mode, expected in ((0, 'Experimental'), (1, 'Experimental'), (2, 'Diagnostic'), (3, 'Experimental')):
        table.view_combo.setCurrentIndex(mode)
        assert table.validation_badge.text() == expected
        assert not table.validation_badge.isHidden()
        assert 'Not independently calibrated' in table.validation_badge.toolTip()
    window.resize(1100, 720)
    app.processEvents()
    assert (window.width(), window.height()) == (1100, 720)
    for label in (table.validation_badge, table.cohort_label):
        assert not label.visibleRegion().isEmpty()
        assert table.rect().contains(label.geometry())
    time = window.playback_panel.time_label
    window.control_panel.cb_view.setCurrentIndex(1)
    assert 'last sample before contact' in time.toolTip()
    window.control_panel.cb_view.setCurrentIndex(0)
    assert time.text() == '1.000 s'
    assert time.toolTip() == 'Recorded time'
    window.control_panel.file_list.setCurrentRow(1)
    assert time.text() == 'Sample 1'
    assert time.toolTip() == 'Sample row (time unavailable)'
    window._on_remove_file(paths[0].name)
    window._on_remove_file(paths[1].name)
    assert table.validation_badge.isHidden()
    assert time.text() == 'No file' and time.toolTip() == ''


def test_compare_fit_preserves_y_up_and_labels_are_optional(tmp_path, comparison, monkeypatch):
    app, window = comparison
    monkeypatch.setattr('src.config.config_app.WORLD_VERTICAL_AXIS_INDEX', 1)
    path = write_proc(tmp_path / 'box.proc', times=(1., 1.01, 1.02, 1.03))
    source = pd.read_csv(path, header=[0, 1, 2])
    for column in source.columns:
        if column[0] == 'Position' and column[2] == 'P_TY':
            source[column] += [100., 40., 20., 0.]
    source.loc[2, ('Position', 'C8', 'P_TY')] = np.nan
    source.to_csv(path, index=False)
    window.load_result_files([str(path)])
    viewer = window.playback_panel.widgets[path.name]
    assert viewer.plotter.camera.up == (0., 1., 0.)
    viewer.plotter.camera.zoom.assert_not_called()
    viewer.set_actor_visibility.assert_called_with(k.SK_ACTOR_LABELS, False)
    assert not window.control_panel.labels_check.isChecked()
    fit = viewer.plotter.reset_camera.call_args.kwargs['bounds']
    frame = viewer.data_handler.get_frame_data(0)
    corners = frame.loc[frame[k.DF_OBJECT_ID].isin(k.BOX_CORNERS_LABELS),
                        [k.DF_POS_X, k.DF_POS_Y, k.DF_POS_Z]].to_numpy(dtype=float)
    expected = tuple(value for low, high in zip(corners.min(axis=0), corners.max(axis=0))
                     for value in (low - 1, high + 1))
    assert fit == expected
    initial_centre = corners.mean(axis=0)
    camera = viewer.plotter.camera
    camera.position = (50., 250., 350.)
    camera.focal_point = (10., 110., 0.)
    camera.view_angle = 21.
    camera.parallel_scale = 88.
    original_position = np.array(camera.position)
    original_focal = np.array(camera.focal_point)
    original_data = window.model.datasets[path.name].copy(deep=True)
    QTest.mouseClick(window.control_panel.settings_section.button, Qt.LeftButton)
    app.processEvents()
    check = window.control_panel.labels_check
    assert not check.visibleRegion().isEmpty()
    QTest.mouseClick(check, Qt.LeftButton, pos=QPoint(8, check.height() // 2))
    viewer.set_actor_visibility.assert_called_with(k.SK_ACTOR_LABELS, True)
    window.playback_panel.master_slider.setValue(1)
    viewer.set_actor_visibility.assert_called_with(k.SK_ACTOR_LABELS, True)
    moved = viewer.data_handler.get_frame_data(1)
    moved_centre = moved.loc[moved[k.DF_OBJECT_ID].isin(k.BOX_CORNERS_LABELS),
                            [k.DF_POS_X, k.DF_POS_Y, k.DF_POS_Z]].to_numpy(dtype=float).mean(axis=0)
    np.testing.assert_allclose(camera.position, original_position + moved_centre - initial_centre)
    np.testing.assert_allclose(camera.focal_point, original_focal + moved_centre - initial_centre)
    previous_position = camera.position
    # Missing/gap display and invalid geometry retain the last valid centre.
    window.playback_panel._show_row(path.name, None)
    assert viewer.isHidden() and camera.position == previous_position
    window.playback_panel.master_slider.setValue(2)
    assert viewer.isHidden() and camera.position == previous_position
    np.testing.assert_array_equal(window.playback_panel.local_controls[path.name]['last_box_centre'], moved_centre)
    window.playback_panel.master_slider.setValue(3)
    last = viewer.data_handler.get_frame_data(3)
    last_centre = last.loc[last[k.DF_OBJECT_ID].isin(k.BOX_CORNERS_LABELS),
                          [k.DF_POS_X, k.DF_POS_Y, k.DF_POS_Z]].to_numpy(dtype=float).mean(axis=0)
    np.testing.assert_allclose(camera.position, original_position + last_centre - initial_centre)
    np.testing.assert_allclose(camera.focal_point, original_focal + last_centre - initial_centre)
    np.testing.assert_allclose(np.array(camera.position) - camera.focal_point, original_position - original_focal)
    assert camera.up == (0., 1., 0.) and camera.view_angle == 21. and camera.parallel_scale == 88.
    assert not viewer.isHidden()
    pd.testing.assert_frame_equal(window.model.datasets[path.name], original_data)
    viewer.plotter.reset_camera.assert_called_once()


def test_column_lookup_uses_values_for_tuple_and_list_user_data():
    app = QApplication.instance() or QApplication([])
    combo = QComboBox()
    key = ('Analysis', 'DropPosture', 'CminIndex')
    try:
        for stored in (list(key), tuple(list(key))):
            combo.clear()
            combo.addItem('Lowest corner', stored)
            assert find_result_column_index(combo, tuple(list(key))) == 0
            assert find_result_column_index(combo, list(key)) == 0
            assert find_result_column_index(combo, None) == -1
            assert find_result_column_index(combo, ('Analysis', 'DropPosture', 'BetaDeg')) == -1
    finally:
        combo.deleteLater()
        app.processEvents()
