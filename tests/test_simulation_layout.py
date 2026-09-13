"""Simulation input identity, camera semantics and reachable Run actions."""
import numpy as np
from scipy.spatial.transform import Rotation
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from src.simulation.scenarios import Scenarios
from src.simulation.ui.main_window import OrientationPreviewWidget, SimulationUI


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
        assert all(not section.button.isChecked() for section in sections)
        for size in ((500, 600), (760, 780)):
            window.resize(*size)
            for expanded in (False, True):
                for section in sections:
                    if section.button.isChecked() != expanded:
                        window.form_scroll.ensureWidgetVisible(section.button)
                        app.processEvents()
                        assert section.button.visibleRegion().contains(section.button.rect())
                        QTest.mouseClick(section.button, Qt.LeftButton)
                        app.processEvents()
                    assert section.button.isChecked() == expanded
                QTest.qWait(30)
                assert (window.width(), window.height()) == size
                scroll = window.form_scroll.verticalScrollBar()
                assert window.form_scroll.horizontalScrollBar().maximum() == 0
                for value in (0, scroll.maximum()):
                    scroll.setValue(value)
                    app.processEvents()
                    for control in (window.run_btn, window.batch_btn, window.experimental_label):
                        assert control.visibleRegion().contains(control.rect())
                    assert window.run_btn.geometry().top() > window.form_scroll.geometry().bottom()
        window.com_y.setValue(-37)
        window.elasticity_input.setValue(.25)
        window.noise_cb.setChecked(True)
        window.noise_std_input.setValue(2.5)
        window.custom_r_input.setValue(23.)
        for section in sections:
            section.setExpanded(False)
            section.setExpanded(True)
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
