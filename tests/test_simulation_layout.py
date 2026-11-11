"""Simulation input identity, camera semantics and reachable Run actions."""
import os
from pathlib import Path

import numpy as np
import pytest
from scipy.spatial.transform import Rotation
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QFontDatabase, QFontInfo, QRegion
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QScrollArea, QStyleFactory

from src.simulation.scenarios import Scenarios
from src.simulation.ui.main_window import OrientationPreviewWidget, SimulationUI
from src.utils.ui_language import active_language


def _fully_visible(widget):
    return widget.isVisible() and not widget.rect().isEmpty() and QRegion(widget.rect()).subtracted(widget.visibleRegion()).isEmpty()


def _register_offscreen_fonts(app, registered):
    if app.platformName() == 'offscreen':
        directory = Path(os.environ.get('WINDIR', 'C:/Windows')) / 'Fonts'
        for filename, family in (('segoeui.ttf', 'Segoe UI'), ('malgun.ttf', 'Malgun Gothic')):
            path = directory / filename
            if family not in QFontDatabase.families() and path.is_file():
                font_id = QFontDatabase.addApplicationFont(str(path))
                assert font_id >= 0, f'Could not load diagnostic font {filename}'
                registered.append(font_id)


def _fhd_geometry(window):
    settings = window.settings
    preview = window.preview_group
    viewport = window.right_scroll.viewport()
    page = settings.tabs.currentWidget()
    font = QFontInfo(window.font())
    preview_rect = preview.rect()
    preview_rect.moveTopLeft(preview.mapTo(viewport, preview_rect.topLeft()))
    margins = window.right_layout.contentsMargins()
    preview_minimum = max(preview.minimumHeight(), preview.minimumSizeHint().height())
    return dict(language=active_language(), style=window.style().objectName(), font_family=font.family(),
        font_points=font.pointSizeF(), font_pixels=font.pixelSize(), font_height=window.fontMetrics().height(),
        dpr=window.devicePixelRatioF(), dpi=window.logicalDpiY(),
        viewport=viewport.rect().getRect(), preview=preview_rect.getRect(),
        mandatory_minimum=settings.minimumSizeHint().height() + preview_minimum
            + window.right_layout.spacing() + margins.top() + margins.bottom(),
        content_minimum=window.right_scroll.widget().minimumSizeHint().height(),
        content_hfw=window.right_layout.totalHeightForWidth(viewport.width()),
        settings=settings.geometry().getRect(), settings_minimum=settings.minimumSizeHint().height(),
        settings_maximum=settings.maximumHeight(), tabs_height=settings.tabs.height(),
        page=page.geometry().getRect(), page_hint=page.layout().sizeHint().height(),
        page_hfw=page.layout().totalHeightForWidth(page.width()), preview_minimum=preview_minimum,
        preview_hint=preview.sizeHint().height(), orientation_height=window.orientation_preview.height(),
        orientation_minimum=window.orientation_preview.minimumHeight(),
        table_height=settings.table.height(), table_viewport=settings.table.viewport().height(),
        five_rows=5 * settings.table.rowHeight(0), table_header=settings.table.horizontalHeader().height(),
        table_hbar_max=settings.table.horizontalScrollBar().maximum(),
        table_hbar_height=settings.table.horizontalScrollBar().height(),
        scroll_max=window.right_scroll.verticalScrollBar().maximum())


def test_startup_window_fits_screen_and_robot_target_is_reachable():
    app = QApplication.instance() or QApplication([])
    window = SimulationUI()
    window.show(); QTest.qWait(50); app.processEvents()
    try:
        assert window.screen().availableGeometry().contains(window.frameGeometry())
        original_size = window.size()
        window.mode_combo.setCurrentIndex(1)
        window.settings.handling.setCurrentIndex(1)
        window.settings.run_scope.setCurrentIndex(1)
        window.settings.table.selectRow(7)
        window.settings.preview_sequence(); app.processEvents()
        assert window.size() == original_size  # Mode changes respect window size.
        for control in (window.run_btn, window.marker_btn):
            assert _fully_visible(control)
        if window._narrow:
            window.form_scroll.ensureWidgetVisible(window.orientation_preview); app.processEvents()
            assert _fully_visible(window.orientation_preview)
            window._show_settings(); app.processEvents()
            scroll = window.settings_dialog.layout().itemAt(0).widget()
            scroll.ensureWidgetVisible(window.settings.apply_button); app.processEvents()
            assert _fully_visible(window.settings.apply_button)
            window.settings_dialog.reject()
            return
        assert window.settings.table.viewport().height() >= 5 * window.settings.table.rowHeight(0)
        for control in (window.settings.apply_button, window.orientation_preview):
            window.right_scroll.ensureWidgetVisible(control); app.processEvents()
            assert _fully_visible(control)
        # When the content fits, no part of the bottom preview needs scrolling.
        if window.right_scroll.widget().minimumSizeHint().height() <= window.right_scroll.viewport().height():
            assert window.right_scroll.verticalScrollBar().maximum() == 0
    finally:
        window.close(); app.processEvents()


def test_wide_workspace_preserves_approved_preview_and_left_mode_controls():
    app = QApplication.instance() or QApplication([])
    window = SimulationUI()
    original = window.profiles.document()
    window.show()
    try:
        for size in ((1280, 720), (1536, 864)):
            window.resize(*size); QTest.qWait(50); app.processEvents()
            assert window.right_scroll.isVisible()
            # The approved layout puts mode controls above the left form and
            # gives all space below settings to the existing target preview.
            for control in (window.mode_combo, window.settings_button):
                rect = control.rect(); rect.moveTopLeft(control.mapTo(window.left_panel, rect.topLeft()))
                assert window.left_panel.rect().contains(rect)
            rect = window.preview_group.rect()
            rect.moveTopLeft(window.preview_group.mapTo(window.right_scroll.viewport(), rect.topLeft()))
            assert window.right_scroll.viewport().rect().contains(rect)
            gap = window.right_scroll.viewport().height() - rect.bottom() - 1
            assert gap <= window.right_layout.contentsMargins().bottom()
            for control in (window.orientation_preview, window.settings.apply_button):
                mapped = control.rect(); mapped.moveTopLeft(control.mapTo(window.right_scroll.viewport(), mapped.topLeft()))
                assert window.right_scroll.viewport().rect().contains(mapped)
        assert window.orientation_preview.height() > 300
        assert window.profiles.document() == original
    finally:
        window.close(); app.processEvents()


def test_robot_summary_and_whole_target_fit_fhd_without_scrolling():
    app = QApplication.instance() or QApplication([])
    window = SimulationUI();window.show()
    try:
        window.resize(1536,864);QTest.qWait(50)
        window.mode_combo.setCurrentIndex(1)
        window.settings.handling.setCurrentIndex(1)
        window.settings.run_scope.setCurrentIndex(1)
        window.settings.table.selectRow(7)
        window.settings.preview_sequence();QTest.qWait(50);app.processEvents()
        for control in (window.settings.preview_box,window.settings.apply_button,window.preview_group):
            rect=control.rect();rect.moveTopLeft(control.mapTo(window.right_scroll.viewport(),rect.topLeft()))
            assert window.right_scroll.viewport().rect().contains(rect)
        assert window.right_scroll.verticalScrollBar().maximum()==0
        assert window.settings.table.viewport().height()>=5*window.settings.table.rowHeight(0)
        assert window.orientation_preview.height()>=160
    finally:
        window.close();app.processEvents()


@pytest.mark.parametrize('point_size, language', [(9, 'en'), (9, 'ko'), (11, 'en'), (11, 'ko')])
def test_fhd_robot_preview_fits_content_at_current_font_metrics(point_size, language):
    app = QApplication.instance() or QApplication([])
    original_font = app.font()
    original_style = app.style().objectName()
    original_language = app.property('interfaceLanguage')
    registered_fonts = []
    window = None
    try:
        _register_offscreen_fonts(app, registered_fonts)
        family = 'Segoe UI' if 'Segoe UI' in QFontDatabase.families() else QFontInfo(original_font).family()
        assert family, 'A resolved system font is required for font-metric evidence'
        app.setStyle('windows11' if 'windows11' in QStyleFactory.keys() else 'Windows')
        app.setFont(QFont(family, point_size))
        app.setProperty('interfaceLanguage', language)
        window = SimulationUI()
        window.show()
        actual_font = QFontInfo(window.font())
        assert actual_font.family() == family, _fhd_geometry(window)
        assert abs(actual_font.pointSizeF() - point_size) <= .5, _fhd_geometry(window)
        assert actual_font.pixelSize() > 0, _fhd_geometry(window)
        assert active_language() == language
        window.resize(1536, 864)
        QTest.qWait(50)
        window.mode_combo.setCurrentIndex(1)
        window.settings.handling.setCurrentIndex(1)
        window.settings.run_scope.setCurrentIndex(1)
        window.settings.table.selectRow(7)
        configuration = window._capture_config()
        window.settings.preview_sequence()
        QTest.qWait(50)
        app.processEvents()
        assert _fully_visible(window.settings.preview_box), _fhd_geometry(window)
        assert _fully_visible(window.settings.apply_button), _fhd_geometry(window)
        if point_size == 9:
            assert _fully_visible(window.preview_group), _fhd_geometry(window)
            assert window.right_scroll.verticalScrollBar().maximum() == 0, _fhd_geometry(window)
        else:
            # Actual Segoe 11pt needs 874 px of mandatory content in an 848 px viewport.
            window.right_scroll.ensureWidgetVisible(window.preview_group)
            app.processEvents()
            assert _fully_visible(window.preview_group), _fhd_geometry(window)
        assert window.orientation_preview.height() >= 160
        assert window.settings.table.viewport().height() >= 5 * window.settings.table.rowHeight(0)
        assert window._capture_config() == configuration
        assert all(_fully_visible(button) for button in (window.run_btn, window.batch_btn, window.marker_btn)), _fhd_geometry(window)
        assert window.font().pointSize() == point_size
        for size in ((1510, 800), (1100, 720), (820, 600)):
            window.resize(*size)
            QTest.qWait(30)
            if window._narrow:
                window._show_settings()
                app.processEvents()
                scroll = window.settings_dialog.findChild(QScrollArea)
            else:
                scroll = window.right_scroll
            for index, controls in (
                (0, (window.settings.handling, window.settings.run_scope, window.settings.preview_box)),
                (1, (window.friction_input, window.com_z, *window.settings.physics_controls)),
                (2, (window.noise_std_input, window.settings.corner_std, window.settings.corner_seed,
                     window.settings.marker_combo, window.settings.fault_kind, window.settings.marker_seed)),
            ):
                window.settings.tabs.setCurrentIndex(index)
                QTest.qWait(20)
                for control in (*controls, window.settings.apply_button, window.settings.cancel_button):
                    scroll.ensureWidgetVisible(control)
                    app.processEvents()
                    assert _fully_visible(control), (point_size, size, index, control.geometry())
                if index == 0:
                    scroll.ensureWidgetVisible(window.settings.table)
                    app.processEvents()
                    assert _fully_visible(window.settings.table.viewport())
                    assert window.settings.table.viewport().height() >= 5 * window.settings.table.rowHeight(0)
            if window.settings_dialog:
                window.settings_dialog.accept()
            preview_scroll = window.form_scroll if window._narrow else window.right_scroll
            preview_target = window.orientation_preview if window._narrow else window.preview_group
            preview_scroll.ensureWidgetVisible(preview_target)
            app.processEvents()
            assert _fully_visible(preview_target), (point_size, size, _fhd_geometry(window))
            assert window.orientation_preview.height() >= 160, (point_size, size, _fhd_geometry(window))
            assert window._capture_config() == configuration
        window.resize(1536, 864)
        window.settings.tabs.setCurrentIndex(0)
        QTest.qWait(40)
        if point_size == 9:
            assert _fully_visible(window.preview_group), _fhd_geometry(window)
            assert window.right_scroll.verticalScrollBar().maximum() == 0, _fhd_geometry(window)
        else:
            window.right_scroll.ensureWidgetVisible(window.preview_group)
            app.processEvents()
            assert _fully_visible(window.preview_group), _fhd_geometry(window)
        assert window.font().pointSize() == point_size
    finally:
        if window is not None:
            window.close()
        app.setProperty('interfaceLanguage', original_language)
        app.setStyle(original_style)
        app.setFont(original_font)
        app.processEvents()
        for font_id in registered_fonts:
            assert QFontDatabase.removeApplicationFont(font_id)


def test_small_simulation_form_keeps_run_fixed_and_settings_intact():
    app = QApplication.instance() or QApplication([])
    window = SimulationUI()
    window.show()
    assert QTest.qWaitForWindowExposed(window)
    try:
        assert (window.com_x.value(), window.com_y.value(), window.com_z.value()) == (0., -200., 0.)
        assert window.elasticity_input.value() == .15
        assert not window.noise_cb.isChecked() and window.noise_std_input.value() == 1.
        assert window.viewer_cb.isChecked()
        sections = (window.physics_section, window.rotation_section, window.noise_section)
        assert all(not hasattr(section, 'button') for section in sections)
        for size in ((820, 600), (1100, 720)):
            window.resize(*size)
            app.processEvents()
            if window._narrow:
                window._show_settings()
                app.processEvents()
                settings_scroll = window.settings_dialog.layout().itemAt(0).widget()
            else:
                settings_scroll = window.right_scroll
            for tab_index, controls in ((1, (window.com_y, window.elasticity_input)),
                                        (2, (window.noise_cb, window.noise_std_input))):
                window.settings.tabs.setCurrentIndex(tab_index)
                QTest.qWait(30)
                for control in controls:
                    settings_scroll.ensureWidgetVisible(control)
                    QTest.qWait(30)
                    app.processEvents()
                    assert _fully_visible(control), (size, tab_index, control.rect(), control.visibleRegion(), control.mapTo(settings_scroll.viewport(), control.rect().topLeft()))
                QTest.qWait(30)
                assert (window.width(), window.height()) == size
                scroll = window.form_scroll.verticalScrollBar()
                assert window.form_scroll.horizontalScrollBar().maximum() == 0
                for value in (0, scroll.maximum()):
                    scroll.setValue(value)
                    app.processEvents()
                    for control in (window.run_btn, window.batch_btn, window.experimental_label):
                        assert _fully_visible(control)
                    assert window.run_btn.geometry().top() > window.form_scroll.geometry().bottom()
            if window.settings_dialog is not None:
                window.settings_dialog.reject()
                app.processEvents()
        window.com_y.setValue(-37)
        window.elasticity_input.setValue(.25)
        window.noise_cb.setChecked(True)
        window.noise_std_input.setValue(2.5)
        window.custom_r_input.setValue(23.)
        for tab_index in (0, 1, 2, 0):
            window.settings.tabs.setCurrentIndex(tab_index)
            app.processEvents()
        assert (window.com_y.value(), window.elasticity_input.value(), window.noise_std_input.value(), window.custom_r_input.value()) == (-37., .25, 2.5, 23.)
        assert window.noise_cb.isChecked()
        assert window.warning_label.text() == 'Custom'
    finally:
        window.close()
        app.processEvents()


def test_short_preset_labels_keep_canonical_category_spec_and_initial_values():
    app = QApplication.instance() or QApplication([])
    window = SimulationUI()
    try:
        for index, canonical in enumerate(Scenarios.get_categories()):
            window.cat_combo.setCurrentIndex(index)
            assert window.cat_combo.currentData() == canonical
            assert window.cat_combo.currentText() in ('Type G', 'Type H')
            specs = Scenarios.get_drop_sequence_specs(canonical)
            assert window.drop_combo.count() == len(specs)
            labels = []
            for row, spec in enumerate(specs):
                window.drop_combo.setCurrentIndex(row)
                assert window.drop_combo.currentData() == spec
                labels.append(window.drop_combo.currentText())
                assert '_' not in labels[-1] and labels[-1].startswith(spec.id[:2])
                assert window.drop_combo.toolTip() == spec.id
                size = tuple(control.value() for control in (window.w_input, window.d_input, window.h_input))
                assert window.custom_h_input.value() == Scenarios.calculate_drop_height(canonical, spec, window.mass_input.value())
                expected = Scenarios.get_euler_angles(spec, size, category=canonical)
                # Existing spinbox precision is two decimal places.
                assert tuple(control.value() for control in (window.custom_r_input, window.custom_p_input, window.custom_y_input)) == tuple(round(value, 2) for value in expected)
                assert window.orientation_preview.category == canonical
                assert '_' not in window.orientation_preview._contact_text()
            assert len(set(labels)) == len(labels)
            if index == 0:
                assert 'face 6' in labels[15] and 'High' in labels[15] and 'default' in labels[15]
                assert 'Hazard' in labels[16]
            else:
                assert 'bottom long' in labels[4] and 'bottom short' in labels[5]
    finally:
        window.close()
        app.processEvents()


def test_preview_box_and_world_icon_share_orthonormal_z_up_camera():
    app = QApplication.instance() or QApplication([])
    preview = OrientationPreviewWidget()
    try:
        camera = preview._camera_basis()
        np.testing.assert_allclose(camera @ camera.T, np.eye(3), atol=1e-15)
        assert np.linalg.det(camera) > 0
        projected_axes = np.eye(3) @ camera.T
        assert projected_axes[2, 1] > 0  # shared screen inversion makes +Z point up
        preview.euler = (20., 35., -15.)
        vertices = preview._box_vertices()
        xy, depth = preview._project(vertices)
        expected = Rotation.from_euler('xyz', preview.euler, degrees=True).apply(vertices) @ camera.T
        np.testing.assert_allclose(xy, expected[:, :2])
        np.testing.assert_allclose(depth, expected[:, 2])
        # World axes are independent of the manual object rotation.
        np.testing.assert_array_equal(camera, preview._camera_basis())
    finally:
        preview.close()
        app.processEvents()
