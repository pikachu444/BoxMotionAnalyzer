"""GUI-06 generated-data contracts; these fixtures do not validate trial physics."""
import hashlib
from types import SimpleNamespace

import pandas as pd
import pytest
from PySide6.QtCore import Qt, QRect
from PySide6.QtGui import QRegion
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QWidget

from comparison_fixtures import write_proc, identity
from test_comparison_layout import comparison
from src.utils.result_time import T1_DETECTED_COLUMN
from src.utils.qt_sections import unique_path_labels
from src.utils.ui_language import tr


def fully_visible(widget, rect=None):
    rect = widget.rect() if rect is None else rect
    return widget.isVisible() and not rect.isEmpty() and QRegion(rect).subtracted(widget.visibleRegion()).isEmpty()


def generated_paths(tmp_path, count=2):
    paths = []
    for index in range(count):
        parent = tmp_path / f'capture-{index}'
        parent.mkdir()
        paths.append(write_proc(parent / ('same_capture_' + 'long_name_' * 10 + '.proc')))
    return paths


def test_c01_owner_counts_source_identity_and_individual_data(tmp_path, comparison):
    app, window = comparison
    paths = generated_paths(tmp_path)
    hashes = [hashlib.sha256(path.read_bytes()).hexdigest() for path in paths]
    window.load_result_files([str(path) for path in paths])
    names = list(window.model.datasets)
    owner = window.model.get_impact_comparison()
    assert len(owner.get('observations', {})) == 0  # Fabricated copies are not independent observations.
    assert window.warning_label.text() == 'Files: 2 | Comparison observation groups: 0'
    assert window.control_panel.detail_tabs.count() == 2
    assert window.control_panel.detail_tabs.currentIndex() == 0
    assert [window.control_panel.detail_tabs.tabText(index) for index in range(2)] == ['Experiment info', 'Playback settings']
    assert not any(type(widget).__name__ == 'CollapsibleSection' for widget in window.findChildren(QWidget))
    expected = unique_path_labels(paths)
    assert len(set(expected)) == 2 and all('capture-' in label for label in expected)
    for row, name in enumerate(names):
        item = window.control_panel.file_list.item(row)
        assert item.text().splitlines()[0] == expected[row]
        assert item.data(Qt.UserRole) == name
        assert window.control_panel.cb_baseline.itemText(row) == expected[row]
    window.control_panel.file_list.setCurrentRow(1)
    window.table_panel.view_combo.setCurrentIndex(2)
    assert window.table_panel.table.rowCount() > 0
    assert window.table_panel.table.isVisible()
    assert window.table_panel.maximumHeight() > 110
    assert str(paths[1]) not in window.control_panel.details.toPlainText()
    window.control_panel._open_diagnostics()
    assert str(paths[1]) in window.control_panel.diagnostics_text.toPlainText()
    assert 'Model: contract-box' in window.control_panel.details.toPlainText()
    assert 'ModelId: contract-box' in window.control_panel.diagnostics_text.toPlainText()
    viewer = window.playback_panel.widgets[names[1]]
    camera = viewer.plotter.camera
    window.playback_panel.master_slider.setValue(2)
    window.right_splitter.setSizes([175, 245, 310])
    splitter = window.right_splitter.sizes()
    window.control_panel.detail_tabs.setCurrentIndex(1)
    window.control_panel.detail_tabs.setCurrentIndex(0)
    window.control_panel.cb_baseline.setCurrentIndex(1)
    assert window.control_panel.selected_file == names[1]
    assert window.playback_panel.widgets[names[1]] is viewer
    assert viewer.plotter.camera is camera
    assert window.playback_panel.master_slider.value() == 2
    assert window.right_splitter.sizes() == splitter
    window.table_panel.view_combo.setCurrentIndex(1)
    assert str(paths[1]) not in window.table_panel.cohort_label.toolTip()
    assert expected[1] in window.table_panel.cohort_label.toolTip()
    assert str(paths[1]) in window.control_panel.diagnostics_text.toPlainText()
    assert [hashlib.sha256(path.read_bytes()).hexdigest() for path in paths] == hashes


def test_c02_owner_alignment_exclusion_is_visible_and_not_pooled(tmp_path, comparison):
    app, window = comparison
    paths = generated_paths(tmp_path)
    frame = pd.read_csv(paths[1], header=[0, 1, 2])
    frame[T1_DETECTED_COLUMN] = False
    frame.to_csv(paths[1], index=False)
    window.load_result_files([str(path) for path in paths])
    first, second = list(window.model.datasets)
    window.control_panel.file_list.setCurrentRow(1)
    baseline = window.model.baseline_name
    selected = window.control_panel.selected_file
    reason = window.model.timelines[second].reason
    assert reason and not window.model.timelines[second].aligned
    assert reason not in window.alignment_label.text()
    assert 'Open Diagnostics' in window.alignment_label.text()
    assert reason not in window.control_panel.details.toPlainText()
    window.control_panel._open_diagnostics()
    assert reason in window.control_panel.diagnostics_text.toPlainText()
    window.control_panel.cb_view.setCurrentIndex(1)
    assert second not in window.graph_panel.legend_labels
    assert reason not in window.playback_panel.local_controls[second]['label'].toolTip()
    assert 'Open Diagnostics' in window.playback_panel.local_controls[second]['label'].toolTip()
    assert first in window.graph_panel.legend_labels
    assert window.model.playback_row(second, 0.) is None
    assert window.model.baseline_name == baseline
    assert window.control_panel.selected_file == selected
    owner = window.model.get_impact_comparison()
    assert all(value['n'] == 0 for value in owner['statistics'].values())
    window.table_panel.view_combo.setCurrentIndex(1)
    assert str(paths[1]) not in window.control_panel.details.toPlainText()
    window.control_panel._open_diagnostics()
    assert str(paths[1]) in window.control_panel.diagnostics_text.toPlainText()
    assert reason not in window.alignment_label.text()
    window.control_panel.cb_view.setCurrentIndex(0)
    window.playback_panel.master_slider.setValue(1)
    assert window.playback_panel.widgets[second].last_row == 1


def test_owner_observation_groups_differ_from_files_and_metric_n(tmp_path, comparison):
    from impact_metric_fixtures import write_proc as write_reviewed_proc

    app, window = comparison
    # The same seeded reviewed capture in two files remains one owner group.
    # Its three samples do not support the owner's pre-contact fit.
    paths = [write_reviewed_proc(tmp_path / f'variant-{index}.proc',
                                times=(0., .040, .048)) for index in range(2)]
    window.load_result_files([str(path) for path in paths])
    owner = window.model.get_impact_comparison()
    assert len(owner['observations']) == 1
    assert owner['statistics']['vertical_velocity']['n'] == 0
    assert window.warning_label.text() == 'Files: 2 | Comparison observation groups: 1'
    window.table_panel.view_combo.setCurrentIndex(1)
    table = window.table_panel.table
    row = next(row for row in range(table.rowCount())
               if table.item(row, 0).data(Qt.UserRole) == 'vertical_velocity')
    assert table.item(row, 1).text().startswith('0')


def test_c03_empty_selected_mode_restores_user_splitter_and_keeps_warnings(tmp_path, comparison):
    app, window = comparison
    assert window.table_panel.table.rowCount() == 0
    assert window.table_panel.table.isHidden()
    assert window.table_panel.height() <= 110
    assert fully_visible(window.table_panel.view_combo)
    assert fully_visible(window.table_panel.guide_button)
    path = write_proc(tmp_path / 'timeseries-only.proc')
    frame = pd.read_csv(path, header=[0, 1, 2])
    frame = frame.drop(columns=[column for column in frame.columns if column[:2] == ('Analysis', 'DropPostureSummary')])
    frame.to_csv(path, index=False)
    window.load_result_files([str(path)])
    window.resize(1100, 720)
    QTest.qWait(20)
    window.right_splitter.setSizes([175, 220, 270])
    original = window.right_splitter.sizes()
    viewer = window.playback_panel.widgets[path.name]
    window.table_panel.view_combo.setCurrentIndex(2)
    app.processEvents()
    assert window.table_panel.table.rowCount() == 0
    assert window.table_panel.table.isHidden()
    assert window.table_panel.empty_label.isVisible()
    assert window.table_panel.height() <= 110
    assert window.right_splitter.sizes()[1] == original[1]
    assert window.right_splitter.sizes()[2] > original[2]
    assert window.model.timelines[path.name].reason not in window.alignment_label.text()
    window.control_panel._open_diagnostics()
    assert window.model.timelines[path.name].reason in window.control_panel.diagnostics_text.toPlainText()
    assert fully_visible(window.table_panel.view_combo)
    assert fully_visible(window.table_panel.guide_button)
    window.table_panel.view_combo.setCurrentIndex(0)
    app.processEvents()
    assert window.table_panel.table.rowCount() > 0
    assert window.table_panel.table.isVisible()
    assert window.table_panel.empty_label.isHidden()
    assert window.right_splitter.sizes() == original
    assert window.playback_panel.widgets[path.name] is viewer
    # A repeat count of zero alone never hides rows supplied for a mode.
    window.table_panel.view_combo.setCurrentIndex(1)
    assert window.table_panel.table.rowCount() > 0
    assert not window.table_panel.table.isHidden()
    # New owner data in the *same* previously empty mode restores it as well.
    window.table_panel.view_combo.setCurrentIndex(2)
    write_proc(path)
    window.load_result_files([str(path)], deduplicate=True)
    app.processEvents()
    assert window.table_panel.table.rowCount() > 0
    assert window.table_panel.maximumHeight() > 110
    restored = window.right_splitter.sizes()
    assert [value / sum(restored) for value in restored] == pytest.approx(
        [value / sum(original) for value in original], abs=2 / sum(restored))


@pytest.mark.parametrize('language', ['en', 'ko'])
@pytest.mark.parametrize('size', [(1510, 800), (1100, 720), (820, 600)])
def test_fixed_tabs_and_controls_fit_supported_sizes(tmp_path, comparison, monkeypatch, language, size):
    app, window = comparison
    app.setProperty('interfaceLanguage', language)
    if language == 'ko':
        from matplotlib import rcParams
        monkeypatch.setitem(rcParams, 'font.sans-serif', ['Malgun Gothic', *rcParams['font.sans-serif']])
        monkeypatch.setitem(rcParams, 'axes.unicode_minus', False)
    try:
        # Build another actual window so translated labels are constructed in-language.
        from src.analysis.compare.main_window import CompareMainWindow
        translated = CompareMainWindow()
        translated.show()
        paths = generated_paths(tmp_path, 8)
        translated.load_result_files([str(path) for path in paths])
        translated.control_panel.cb_view.setCurrentIndex(1)
        translated.resize(*size)
        QTest.qWait(30)
        assert (translated.width(), translated.height()) == size
        assert translated.control_panel.detail_tabs.tabText(0) == tr('Experiment info')
        for mode, key in ((0, 'vertical_velocity'), (4, 'beta')):
            translated.table_panel.view_combo.setCurrentIndex(mode)
            assert translated.table_panel.table.horizontalHeaderItem(0).text() == tr('Metric')
            assert translated.table_panel.table.item(0, 0).data(Qt.UserRole) == key
        translated.table_panel.view_combo.setCurrentIndex(0)
        for index in range(2):
            translated.control_panel.detail_tabs.setCurrentIndex(index)
            app.processEvents()
            controls = [translated.control_panel.btn_add_files, translated.control_panel.btn_remove_file,
                        translated.control_panel.cb_view, translated.control_panel.cb_baseline,
                        translated.table_panel.view_combo, translated.table_panel.guide_button,
                        translated.playback_panel.btn_master_play, translated.playback_panel.master_slider,
                        translated.graph_panel.cb_plot_target]
            controls += ([translated.control_panel.details.viewport()] if index == 0 else
                         [translated.control_panel.gap_limit, translated.control_panel.labels_check])
            for widget in controls:
                assert fully_visible(widget), (index, type(widget).__name__, widget.objectName(),
                                               widget.geometry(), widget.visibleRegion().boundingRect())
        graph = translated.graph_panel
        graph.canvas.draw()
        renderer = graph.canvas.get_renderer()
        ax = graph.plot_manager.ax
        width, height = graph.fig.bbox.width, graph.fig.bbox.height
        labels = [ax.title, ax.xaxis.label, ax.yaxis.label]
        for axis in (ax.xaxis, ax.yaxis):
            low, high = axis.get_view_interval()
            labels.extend(label for value, label in zip(axis.get_majorticklocs(), axis.get_ticklabels())
                          if low <= value <= high)
        for label in labels:
            if label.get_visible() and label.get_text():
                box = label.get_window_extent(renderer)
                assert 0 <= box.x0 <= box.x1 <= width and 0 <= box.y0 <= box.y1 <= height, (
                    language, size, label.get_text(), box.bounds, (width, height))
        left, right = graph.plot_manager.ax.get_xlim()
        ticks = [label.get_window_extent(renderer) for value, label in
                 zip(graph.plot_manager.ax.get_xticks(), graph.plot_manager.ax.get_xticklabels())
                 if left <= value <= right and label.get_visible()]
        assert all(first.x1 + 2 <= second.x0 for first, second in zip(ticks, ticks[1:]))
        assert len(graph.legend_labels) == 8
        assert graph.plot_manager.ax.get_legend() is None
        assert graph.legend_scroll.geometry().bottom() < graph.canvas.geometry().top()
        for label in graph.legend_labels.values():
            assert 'capture-' in label.text()
            assert str(paths[0].parent.parent) not in label.toolTip()
            assert label.property('fullPath') in translated.model.file_paths.values()
        assert not any(type(widget).__name__ == 'CollapsibleSection' for widget in translated.findChildren(QWidget))
    finally:
        translated.close()
        translated.deleteLater()
        app.setProperty('interfaceLanguage', 'en')
        app.processEvents()


def test_whole_region_visibility_rejects_partial_and_empty(comparison):
    app, _ = comparison
    host = QWidget()
    host.resize(200, 200)
    parent = QWidget(host)
    parent.setFixedSize(40, 40)
    child = QWidget(parent)
    child.setGeometry(20, 0, 40, 40)
    host.show()
    app.processEvents()
    try:
        assert not fully_visible(child)
        assert not fully_visible(child, QRect())
        child.setGeometry(0, 0, 40, 40)
        app.processEvents()
        assert fully_visible(child)
    finally:
        host.close()


def test_individual_end_playback_displays_recorded_sample_time(tmp_path, comparison):
    app, window = comparison
    path = write_proc(tmp_path / 'three-samples.proc')
    window.load_result_files([str(path)])
    panel = window.playback_panel
    panel.clock = SimpleNamespace(restart=lambda: None, elapsed=lambda: 36)
    panel.toggle_master_playback()
    panel._on_master_timer()
    assert panel.master_slider.value() == 2
    assert panel.widgets[path.name].last_row == 2
    assert window.graph_panel.cursor.get_xdata()[0] == 1.020
    assert panel.time_label.text() == '1.020 s'
    assert panel.time_label.toolTip() == 'Recorded time'
    assert not panel.master_timer.isActive()
    assert panel.btn_master_play.text() == 'Play'
    # Aligned playback keeps the owner's elapsed axis and existing end clamp.
    window.control_panel.cb_view.setCurrentIndex(1)
    panel.master_slider.setValue(0)
    panel.toggle_master_playback()
    panel._on_master_timer()
    assert panel.current_elapsed == pytest.approx(panel.bounds[1])
    assert window.graph_panel.cursor.get_xdata()[0] == pytest.approx(panel.bounds[1])
    assert panel.time_label.text() == f'{panel.bounds[1]:+.3f} s'
    assert panel.time_label.toolTip() == 'Time from the last sample before contact'
    assert not panel.master_timer.isActive()


def test_individual_playback_gap_does_not_claim_a_recorded_timestamp(tmp_path, comparison):
    app, window = comparison
    path = write_proc(tmp_path / 'gap-samples.proc', times=(1., 1.01, 1.30))
    window.load_result_files([str(path)])
    panel = window.playback_panel
    panel.clock = SimpleNamespace(restart=lambda: None, elapsed=lambda: 150)
    panel.toggle_master_playback()
    panel._on_master_timer()
    assert panel.widgets[path.name].isHidden()
    assert panel.master_slider.value() == 0
    assert panel.time_label.text() == 'Unavailable here'
    assert panel.time_label.toolTip() == 'Unavailable here'
    assert panel.master_timer.isActive()
    panel.clock = SimpleNamespace(restart=lambda: None, elapsed=lambda: 300)
    panel._on_master_timer()
    assert panel.time_label.text() == '1.300 s'
    assert panel.time_label.toolTip() == 'Recorded time'
    assert panel.master_slider.value() == 2
    assert not panel.master_timer.isActive()
