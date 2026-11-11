"""GUI-08: generated input bindings, draft boundaries and reachable controls."""
from copy import deepcopy

import pytest
from PySide6.QtGui import QRegion
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QFileDialog, QGroupBox, QScrollArea, QWidget

from src.simulation.ui.main_window import SimulationUI
from src.simulation.ui import marker_export_dialog
from src.utils.ui_language import tr


def fully_visible(widget):
    return (widget.isVisible() and not widget.rect().isEmpty()
            and QRegion(widget.rect()).subtracted(widget.visibleRegion()).isEmpty())


@pytest.fixture
def window():
    app = QApplication.instance() or QApplication([])
    original_language = app.property('interfaceLanguage')
    app.setProperty('interfaceLanguage', 'en')
    widget = SimulationUI()
    widget.show()
    app.processEvents()
    yield widget
    if widget.marker_dialog is not None:
        widget.marker_dialog.reject()
    if widget.settings_dialog is not None:
        widget.settings_dialog.reject()
    widget._set_busy(False)
    widget.close()
    app.setProperty('interfaceLanguage', original_language)
    app.processEvents()


@pytest.mark.parametrize('size', [(1510, 800), (1100, 720), (820, 600)])
@pytest.mark.parametrize('language', ['en', 'ko'])
def test_m02_fixed_groups_tabs_and_actions_are_reachable(window, size, language):
    app = QApplication.instance()
    app.setProperty('interfaceLanguage', language)
    # Build with the actual requested language rather than translating a snapshot.
    localized = SimulationUI()
    localized.show()
    localized.resize(*size)
    QTest.qWait(30)
    try:
        assert (localized.width(), localized.height()) == size
        assert localized.profiles.mode == 'single_drop'
        assert not any(type(child).__name__ == 'CollapsibleSection' for child in localized.findChildren(QWidget))
        assert isinstance(localized.rotation_section, QGroupBox)
        for control in (localized.custom_r_input, localized.custom_p_input, localized.custom_y_input):
            localized.form_scroll.ensureWidgetVisible(control)
            app.processEvents()
            assert fully_visible(control), (control.geometry().getRect(), control.visibleRegion().boundingRect().getRect(), control.parentWidget().geometry().getRect())
        for button in (localized.run_btn, localized.batch_btn, localized.marker_btn):
            assert fully_visible(button)
            assert button.height() >= button.sizeHint().height()
        identities = tuple(map(id, localized._value_controls()))
        config = localized._capture_config()
        if localized._narrow:
            localized._show_settings()
            app.processEvents()
            scroll = localized.settings_dialog.findChild(QScrollArea)
        else:
            scroll = localized.right_scroll
        for tab, controls, group in (
            (1, (localized.friction_input, localized.elasticity_input, localized.com_x,
                 localized.com_y, localized.com_z), localized.physics_section),
            (2, (localized.noise_cb, localized.noise_std_input), localized.noise_section),
        ):
            localized.settings.tabs.setCurrentIndex(tab)
            app.processEvents()
            assert group.title() == tr('Current run')
            assert group.parentWidget() is localized.settings.tabs.widget(tab)
            assert any(child.title() == tr('Draft profile') for child in group.parentWidget().findChildren(QGroupBox))
            for control in (*controls, localized.settings.apply_button, localized.settings.cancel_button):
                scroll.ensureWidgetVisible(control)
                app.processEvents()
                assert fully_visible(control), (tab, control, control.geometry().getRect(), control.visibleRegion().boundingRect().getRect(), control.parentWidget().geometry().getRect())
            draft_controls = (localized.settings.physics_controls if tab == 1 else
                (localized.settings.corner_enabled, localized.settings.corner_std,
                 localized.settings.corner_seed, localized.settings.marker_combo,
                 localized.settings.fault_kind, localized.settings.channel,
                 localized.settings.start, localized.settings.end, localized.settings.axis,
                 localized.settings.marker_std, localized.settings.marker_seed))
            for control in draft_controls:
                scroll.ensureWidgetVisible(control)
                app.processEvents()
                assert fully_visible(control), (tab, control, control.visibleRegion().boundingRect().getRect(), control.rect().getRect())
        assert localized._capture_config() == config
        assert tuple(map(id, localized._value_controls())) == identities
        localized.result_label.setText('Previous result: generated/' + 'long-folder/' * 18 + 'simulation.proc')
        localized.result_label.show()
        localized._set_busy(True)
        app.processEvents()
        assert (localized.width(), localized.height()) == size
        assert all(fully_visible(button) for button in (localized.run_btn, localized.batch_btn, localized.marker_btn))
        assert fully_visible(localized.cancel_run) and localized.cancel_run.isEnabled()
        assert not localized.run_btn.isEnabled()
        localized.cancel_simulation()
        assert not localized.cancel_run.isEnabled()
    finally:
        if localized.settings_dialog:
            localized.settings_dialog.reject()
        localized._set_busy(False)
        localized.close()
        app.processEvents()


def test_m01_mode_roundtrip_draft_cancel_apply_and_run_payload(window, monkeypatch, tmp_path):
    window.custom_r_input.setValue(23)
    window.custom_p_input.setValue(-17)
    window.custom_y_input.setValue(11)
    window.com_y.setValue(-37)
    window.friction_input.setValue(.7)
    window.noise_cb.setChecked(True)
    window.noise_std_input.setValue(2.5)
    window.viewer_cb.setChecked(False)
    single = window._capture_config()
    assert window.orientation_preview.euler == (23, -17, 11)
    panel = window.settings
    panel.physics_controls[1].setValue(1.3)
    panel.corner_std.setValue(4)
    assert window._capture_config() == single
    panel.cancel_settings()
    assert window._capture_config() == single
    assert panel.physics_controls[1].value() == .7 and panel.corner_std.value() == 2.5
    panel.physics_controls[1].setValue(1.3)
    panel.corner_std.setValue(4)
    panel.apply_settings()
    assert window.friction_input.value() == 1.3 and window.noise_std_input.value() == 4
    applied = window._capture_config()
    window.mode_combo.setCurrentIndex(1)
    robot = window._capture_config()
    assert not window.batch_btn.isEnabled()
    assert not window.rotation_section.isEnabled()
    window.mode_combo.setCurrentIndex(0)
    assert window._capture_config() == applied
    window.mode_combo.setCurrentIndex(1)
    assert window._capture_config() == robot
    window.mode_combo.setCurrentIndex(0)
    target = tmp_path / 'generated.proc'
    captured = {}
    monkeypatch.setattr(QFileDialog, 'getSaveFileName', lambda *args: (str(target), ''))
    monkeypatch.setattr(window, '_engine', lambda config: captured.update(config=deepcopy(config)) or object())
    monkeypatch.setattr(window, '_start_worker', lambda engine, params, path, **kwargs:
                        captured.update(params=deepcopy(params), path=path))
    window.run_btn.click()
    assert captured['config'] == applied
    assert captured['params']['mode_config'] == applied
    assert captured['params']['noise_std'] == 4 and captured['params']['add_noise']
    assert captured['path'] == str(target)
    generation = window._generation
    window.previous_result = 'generated/previous.proc'
    window.cancel_run.click()
    assert window._generation == generation + 1
    assert window.previous_result == 'generated/previous.proc'
    assert window._capture_config() == applied


def test_m02_marker_fault_group_keeps_defaults_conditions_and_csv_payload(window, monkeypatch, tmp_path):
    before = window._capture_config()
    window.open_marker_export()
    dialog = window.marker_dialog
    dialog.resize(820, 600)
    QApplication.processEvents()
    dialog.canvas.draw()
    renderer = dialog.canvas.get_renderer()
    canvas_box = dialog.figure.bbox
    for axis in (dialog.axes.xaxis, dialog.axes.yaxis, dialog.axes.zaxis):
        label_box = axis.label.get_window_extent(renderer)
        assert canvas_box.contains(*label_box.p0) and canvas_box.contains(*label_box.p1)
        assert axis.label.get_fontsize() == 9
    assert isinstance(dialog.fault_section, QGroupBox)
    assert not any(type(child).__name__ == 'CollapsibleSection' for child in dialog.findChildren(QWidget))
    assert dialog.kind.currentData() is None
    assert not dialog.start.isEnabled() and not dialog.axis.isEnabled()
    assert dialog.seed.value() == before['observation_profile']['marker']['seed']
    dialog.kind.setCurrentIndex(dialog.kind.findData('flip_180_local_axis'))
    assert dialog.axis.isEnabled() and not dialog.channel.isEnabled() and not dialog.end.isEnabled()
    dialog.kind.setCurrentIndex(dialog.kind.findData('gaussian_noise'))
    assert dialog.std.isEnabled() and dialog.seed.isEnabled() and dialog.channel.isEnabled()
    assert not dialog.axis.isEnabled()
    dialog.start.setValue(.08)
    dialog.end.setValue(.16)
    dialog.std.setValue(.3)
    dialog.seed.setValue(1234)
    dialog.dimensions.setChecked(True)
    # Cancelling the folder picker leaves the source and all output untouched.
    monkeypatch.setattr(QFileDialog, 'getExistingDirectory', lambda *args: '')
    dialog.generate()
    assert dialog.worker is None and window._capture_config() == before
    monkeypatch.setattr(QFileDialog, 'getExistingDirectory', lambda *args: str(tmp_path))
    monkeypatch.setattr(marker_export_dialog.MarkerExportWorker, 'start', lambda worker: None)
    dialog.generate()
    worker = dialog.worker
    assert worker is not None
    destination, profile, simulation, faults, seed = worker.arguments
    assert seed == 1234 and faults == dict(kind='gaussian_noise', channel='rigid_body_markers',
        start=.08, end=.16, axis='X', std_mm=.3)
    assert simulation['height'] == dialog.simulation['height']
    assert simulation['com_offset'] == tuple(before['physics_profile']['com_offset_mm'])
    assert simulation['mode_config']['observation_profile']['marker']['faults'] == faults
    assert dialog.simulation['mode_config'] == before
    assert not (tmp_path / 'synthetic_markers').exists()
    dialog.cancel()
    assert dialog._cancel_reason == 'Cancelled. Previous results are preserved.'
    dialog._finished(worker)
