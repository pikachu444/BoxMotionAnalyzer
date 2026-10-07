"""PUB06 production bindings, with literal UI/clock/transform expectations."""
from copy import deepcopy
import json
import threading
import time

import numpy as np
import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox
from src.simulation.ui.main_window import SimulationUI
from src.simulation.mode_profiles import read_profiles, save_profiles, BLOCKED_REASON
from src.simulation.data_exporter import DataExporter
from src.analysis.pipeline.data_loader import DataLoader
from src.utils.artifact_metadata import read_identity
from src.utils.simulation_metadata import artifact_simulation
from src.utils.result_time import read_result_frame, TIME_COLUMN
from src.utils.marker_profile_identity import digest


@pytest.fixture
def window(monkeypatch):
    app = QApplication.instance() or QApplication([])
    widget = SimulationUI(); widget.viewer_cb.setChecked(False); widget.duration_input.setValue(.5)
    monkeypatch.setattr(QMessageBox, 'information', lambda *args: None)
    monkeypatch.setattr(QMessageBox, 'critical', lambda *args: None)
    widget.show(); app.processEvents()
    yield widget
    if widget._busy:
        widget.cancel_simulation(); wait(lambda: not widget._busy)
    if widget.marker_dialog:
        widget.marker_dialog.reject(); app.processEvents()
    widget.close(); app.processEvents()


def wait(predicate, timeout=15):
    deadline = time.monotonic()+timeout
    while not predicate() and time.monotonic() < deadline:
        QApplication.processEvents(); time.sleep(.005)
    assert predicate()


def settings(window, callback):
    panel = window.settings; callback(panel); panel.apply_settings()
    return panel


def test_mode_roundtrip_preserves_manual_pose_and_ordered_plan(window):
    window.drop_combo.setCurrentIndex(2); window.custom_h_input.setValue(123); window.custom_y_input.setValue(17)
    original = deepcopy(window.profiles.configs['single_drop'])
    window.mode_combo.setCurrentIndex(1)
    panel = window.settings
    assert panel.table.rowCount() == 17 and panel.table.item(16, 5).text() == '미지원'
    assert 'Hazard block is not implemented' in panel.table.item(16,5).toolTip()
    assert window.orientation_preview.sequence_spec.faces == (3, 4)
    panel.table.selectRow(7)
    assert window.orientation_preview.sequence_spec.faces == (3,) and window.custom_h_input.value() == 910
    panel.move_drop(-1); panel.apply_settings()
    robot = deepcopy(window.profiles.configs['robot_sequence'])
    assert robot['sequence_profile']['steps'][6]['preset_id'] == '08_Face_3_Screen_High'
    window.mode_combo.setCurrentIndex(0)
    assert window.profiles.configs['single_drop'] == original
    assert window.custom_h_input.value() == 123 and window.custom_y_input.value() == 17
    assert window.warning_label.text() == 'Custom'
    window.mode_combo.setCurrentIndex(1)
    assert window.profiles.configs['robot_sequence'] == robot
    window.close()  # A disabled robot Run button does not imply a live worker.
    assert not window.isVisible()


def test_settings_cancel_apply_save_reload_and_unsupported(window, tmp_path, monkeypatch):
    panel = window.settings
    before = deepcopy(window.profiles.configs)
    panel.physics_controls[0].setValue(73); panel.cancel_settings()
    assert window.profiles.configs == before and panel.physics_controls[0].value() == 25
    panel.marker_combo.setCurrentIndex(1); panel.marker_seed.setValue(1234); panel.physics_controls[0].setValue(73)
    path = tmp_path/'profiles.json'
    monkeypatch.setattr(QFileDialog, 'getSaveFileName', lambda *args: (str(path), ''))
    panel.save_settings()
    assert window.profiles.configs == before  # Save is not Apply.
    saved = read_profiles(path)
    assert saved.configs['single_drop']['physics_profile']['mass_kg'] == 73
    assert saved.configs['single_drop']['observation_profile']['marker']['seed'] == 1234
    panel.cancel_settings()
    monkeypatch.setattr(QFileDialog, 'getOpenFileName', lambda *args: (str(path), ''))
    panel.open_settings()
    assert window.profiles.configs == before  # Open is review-only too.
    panel.apply_settings()
    assert window.mass_input.value() == 73
    assert window.profiles.configs['single_drop']['observation_profile']['marker']['profile'] == saved.configs['single_drop']['observation_profile']['marker']['profile']
    applied = window.profiles.document()
    value = json.loads(path.read_text()); value['schema_version'] = 999
    path.write_text(json.dumps(value)); panel.open_settings()
    assert window.profiles.document() == applied and 'unsupported' in panel.status.text().lower()
    save_profiles(path, window.profiles)
    assert read_profiles(path).document() == window.profiles.document()


def test_draft_row_selection_preserves_edits_until_apply_or_cancel(window):
    panel = window.settings; before = deepcopy(window.profiles.configs['single_drop'])
    panel.physics_controls[0].setValue(73); panel.table.item(0, 1).setText('123'); panel.table.selectRow(7)
    assert panel.physics_controls[0].value() == 73 and panel.table.item(0, 1).text() == '123'
    assert window.profiles.configs['single_drop'] == before
    assert window.drop_combo.currentIndex() == 0 and window.orientation_preview.sequence_spec.faces == (3,)
    panel.cancel_settings()
    assert panel.table.currentRow() == 0 and window.orientation_preview.sequence_spec.faces == (3, 4)
    assert window.profiles.configs['single_drop'] == before
    panel.physics_controls[0].setValue(73); panel.table.selectRow(7); panel.apply_settings()
    assert window.mass_input.value() == 73 and window.drop_combo.currentIndex() == 7
    assert panel.table.currentRow() == 7 and window.orientation_preview.sequence_spec.faces == (3,)


@pytest.mark.parametrize('mode', ['single_drop', 'robot_sequence'])
def test_loaded_other_category_previews_its_own_draft(window, tmp_path, monkeypatch, mode):
    from src.simulation.mode_profiles import ModeProfiles
    from src.simulation.scenarios import Scenarios
    from src.simulation.ui.mode_settings import preset_steps
    state = ModeProfiles(); state.switch(mode); config = deepcopy(state.configs[mode])
    steps = preset_steps(Scenarios.CATEGORIES[1], config['size_mm'], 25)
    config['sequence_profile']['steps'] = steps if mode == 'robot_sequence' else [steps[0]]
    state.set_config(config); path = tmp_path/'H.json'; save_profiles(path, state)
    before = window.profiles.document(); panel = window.settings
    monkeypatch.setattr(QFileDialog, 'getOpenFileName', lambda *args: (str(path), ''))
    panel.open_settings(); panel.table.selectRow(1)
    assert window.profiles.document() == before
    assert window.orientation_preview.category == Scenarios.CATEGORIES[1]
    assert window.orientation_preview.sequence_spec.faces == (2,)
    panel.apply_settings()
    assert window.profiles.mode == mode and window.cat_combo.currentData() == Scenarios.CATEGORIES[1]
    assert window.orientation_preview.sequence_spec.faces == (2,) and panel.table.currentRow() == 1


def test_robot_apply_cancel_synchronizes_active_preview(window):
    window.mode_combo.setCurrentIndex(1); panel = window.settings; panel.table.selectRow(7)
    panel.apply_settings()
    assert panel.table.currentRow() == 7 and window.drop_combo.currentIndex() == 7
    assert window.orientation_preview.sequence_spec.faces == (3,)
    panel.table.item(7, 4).setText('37')
    assert window.orientation_preview.euler[2] == 37
    panel.cancel_settings()
    assert panel.table.currentRow() == 7 and window.drop_combo.currentIndex() == 7
    assert window.orientation_preview.euler[2] == 0


def test_loaded_robot_geometry_uses_draft_size_and_edit_event(window, tmp_path, monkeypatch):
    from src.simulation.mode_profiles import ModeProfiles
    state = ModeProfiles(); state.switch('robot_sequence'); config = deepcopy(state.configs['robot_sequence'])
    config['size_mm'] = [200, 120, 80]; state.set_config(config)
    path = tmp_path/'small-robot.json'; save_profiles(path, state)
    window.mode_combo.setCurrentIndex(1); panel = window.settings
    before = window.profiles.document()
    monkeypatch.setattr(QFileDialog, 'getOpenFileName', lambda *args: (str(path), ''))
    panel.open_settings()
    assert window.profiles.document() == before and window.w_input.value() == 1578
    assert window.orientation_preview.box_size == (200, 120, 80)
    assert '200 × 120 × 80' in panel.status.text()
    panel.table.item(0, 4).setText('37')
    assert window.orientation_preview.euler[2] == 37 and window.orientation_preview.box_size == (200, 120, 80)
    assert window.preview_group.title() == 'Settings preview'
    panel.cancel_settings()
    assert window.orientation_preview.box_size == (1578, 930, 142) and window.orientation_preview.euler[2] == 0


@pytest.mark.parametrize('bad', ['NaN', 'Infinity', '-Infinity', 'garbage'])
def test_invalid_draft_does_not_apply_or_save(window, tmp_path, monkeypatch, bad):
    window.mode_combo.setCurrentIndex(1); panel = window.settings
    before = window.profiles.document(); panel.table.item(1, 1).setText(bad)
    panel.apply_settings()
    assert window.profiles.document() == before
    assert 'not applied' in panel.status.text()
    assert panel.table.currentRow() == 1 and 'Drop 2 clearance' in panel.status.text()
    path = tmp_path/'keep.json'; path.write_text('previous document')
    monkeypatch.setattr(QFileDialog, 'getSaveFileName', lambda *args: (str(path), ''))
    panel.save_settings(); assert path.read_text() == 'previous document'


def test_robot_execution_guard_precedes_all_file_pickers(window, monkeypatch):
    warnings = []; calls = []
    monkeypatch.setattr(QMessageBox, 'warning', lambda *args: warnings.append(args[2]))
    monkeypatch.setattr(QFileDialog, 'getSaveFileName', lambda *args: calls.append('save'))
    monkeypatch.setattr(QFileDialog, 'getExistingDirectory', lambda *args: calls.append('directory'))
    window.mode_combo.setCurrentIndex(1)
    assert not any(button.isEnabled() for button in (window.run_btn, window.batch_btn, window.marker_btn))
    window.run_simulation(); window.run_batch_simulation(); window.open_marker_export()
    assert warnings == [BLOCKED_REASON]*3 and not calls
    assert not window._busy and window.previous_result is None


def test_completed_preset_update_and_small_window_settings(window):
    window.custom_h_input.setValue(123); window.custom_y_input.setValue(17)
    assert window.settings.table.item(0, 1).text() == '123'
    window._update_custom_fields_from_scenario()
    assert window.settings.table.item(0, 1).text() == '460' and window.settings.table.item(0, 4).text() == '0'
    window.cat_combo.setCurrentIndex(1)
    assert window.settings.table.rowCount() == 12
    assert window.settings.table.item(0, 5).text() == '바닥 기울임 (미지원)'
    for mode in (0, 1):
        window.mode_combo.setCurrentIndex(mode); window.resize(820, 600); QApplication.processEvents()
        assert window.size().width() == 820 and not window.right_scroll.isVisible()
        for control in (window.w_input, window.d_input, window.h_input, window.mass_input, window.cat_combo, window.drop_combo, window.custom_h_input, window.duration_input):
            assert control.height() >= control.minimumSizeHint().height()
        for button in (window.run_btn, window.batch_btn, window.marker_btn): assert button.visibleRegion().contains(button.rect())
        window.form_scroll.ensureWidgetVisible(window.orientation_preview); QApplication.processEvents()
        assert window.orientation_preview.visibleRegion().contains(window.orientation_preview.rect())
        QTest.mouseClick(window.settings_button, Qt.LeftButton); QApplication.processEvents()
        assert window.settings_dialog and window.settings.isVisible()
        panel = window.settings; panel.physics_controls[0].setValue(73)
        window.settings_dialog.reject(); QApplication.processEvents()
        assert window.mass_input.value() == 25 and panel.physics_controls[0].value() == 25
    window.resize(1280, 720); QApplication.processEvents()
    assert window.right_scroll.isVisible() and window.orientation_preview.parentWidget() == window.preview_group


def test_run_metadata_matches_literal_release_and_preserves_previous(window, tmp_path, monkeypatch):
    for control, value in zip((window.w_input, window.d_input, window.h_input, window.com_x, window.com_y, window.com_z), (200, 120, 80, 3, -4, 2)): control.setValue(value)
    window.custom_h_input.setValue(250); window.custom_r_input.setValue(0); window.custom_p_input.setValue(0); window.custom_y_input.setValue(90)
    path = tmp_path/'literal.proc'; monkeypatch.setattr(QFileDialog, 'getSaveFileName', lambda *args: (str(path), ''))
    window.run_simulation(); wait(lambda: not window._busy)
    frame = DataLoader().load_result_csv(str(path)); declaration = artifact_simulation(read_identity(frame).values)
    assert declaration['mode'] == 'single_drop' and declaration['clock']['semantics'] == 'actual-engine-clock'
    assert declaration['clock']['samples'] == 63
    assert declaration['configuration']['physics_profile']['com_offset_mm'] == [3, -4, 2]
    np.testing.assert_allclose(frame[TIME_COLUMN].to_numpy(), np.arange(63)*.008, atol=1e-15, rtol=0)
    assert window.previous_result == str(path) and window.result_current
    window.mode_combo.setCurrentIndex(1)
    assert window.previous_result == str(path) and not window.result_current and path.exists()
    assert window.result_history[-1]['config']['sequence_profile']['steps'][0]['fixed_xyz_deg'] == [0, 0, 90]


@pytest.mark.parametrize('change', ['cancel', 'source', 'mode'])
def test_cancel_stale_worker_and_retry_keep_prior_destination(window, tmp_path, monkeypatch, change):
    path = tmp_path/'keep.proc'; path.write_bytes(b'previous output')
    window.previous_result = 'prior-result.proc'
    entered = threading.Event(); release = threading.Event()
    export = DataExporter.export_proc_csv
    def gated(self, filepath, *, cancelled=None):
        entered.set(); assert release.wait(10)
        return export(self, filepath, cancelled=cancelled)
    monkeypatch.setattr(QFileDialog, 'getSaveFileName', lambda *args: (str(path), ''))
    with monkeypatch.context() as patch:
        patch.setattr(DataExporter, 'export_proc_csv', gated)
        window.run_simulation(); wait(entered.is_set)
        assert not window.settings.apply_button.isEnabled()
        if change == 'cancel': window.cancel_simulation()
        elif change == 'source': window.custom_h_input.setValue(333)
        else: window.mode_combo.setCurrentIndex(1)
        assert window._busy and not window.cancel_run.isEnabled()
        release.set(); wait(lambda: not window._busy)
    assert path.read_bytes() == b'previous output' and window.previous_result == 'prior-result.proc'
    assert window.result_history[-1]['status'] == 'stale'
    if change == 'mode': window.mode_combo.setCurrentIndex(0)
    current = deepcopy(window.profiles.configs['single_drop'])
    window.run_simulation(); wait(lambda: not window._busy)
    declaration = artifact_simulation(read_identity(read_result_frame(path)).values)
    assert declaration['configuration']['sequence_profile']['steps'][0]['clearance_mm'] == current['sequence_profile']['steps'][0]['clearance_mm']
    assert window.result_history[-1]['status'] == 'produced'


def test_run_all_presets_freezes_configuration_and_exports_each_mode(window, tmp_path, monkeypatch):
    monkeypatch.setattr(QFileDialog, 'getExistingDirectory', lambda *args: str(tmp_path))
    window.run_batch_simulation(); wait(lambda: not window._busy, 30)
    assert len(window._batch_success_paths) == 17
    assert len(set(window._batch_success_paths)) == 17
    declarations = [artifact_simulation(read_identity(read_result_frame(path)).values) for path in window._batch_success_paths]
    assert all(item['mode'] == 'single_drop' and item['clock']['samples'] == 63 for item in declarations)
    assert [item['configuration']['sequence_profile']['steps'][0]['preset_id'] for item in declarations] == [spec.id for spec in window._batch_sequences]
    assert window.profiles.mode == 'single_drop' and len(window.profiles.configs['single_drop']['sequence_profile']['steps']) == 1


def test_queued_success_after_source_change_is_retained_without_adoption(window, tmp_path, monkeypatch):
    path = tmp_path/'completed-before-change.proc'; window.previous_result = 'prior-result.proc'
    written = threading.Event(); release = threading.Event(); export = DataExporter.export_proc_csv
    def after_publication(self, filepath, *, cancelled=None):
        result = export(self, filepath, cancelled=cancelled); written.set(); assert release.wait(10); return result
    monkeypatch.setattr(QFileDialog, 'getSaveFileName', lambda *args: (str(path), ''))
    monkeypatch.setattr(DataExporter, 'export_proc_csv', after_publication)
    window.run_simulation(); wait(written.is_set); window.custom_h_input.setValue(333); release.set(); wait(lambda: not window._busy)
    assert path.exists() and window.previous_result == 'prior-result.proc' and not window.result_current
    assert window.result_history[-1]['status'] == 'stale' and window.result_history[-1]['path'] == str(path)
    assert window.profiles.configs['single_drop']['sequence_profile']['steps'][0]['clearance_mm'] == 333


def test_marker_csv_current_settings_and_source_change_blocks_retry(window, tmp_path, monkeypatch):
    panel = window.settings; panel.marker_combo.setCurrentIndex(1); panel.marker_seed.setValue(2468); panel.use_layout_box.setChecked(True); panel.apply_settings()
    window.open_marker_export(); dialog = window.marker_dialog
    assert dialog.profile_combo.currentData() == '32' and dialog.seed.value() == 2468
    monkeypatch.setattr(QFileDialog, 'getExistingDirectory', lambda *args: str(tmp_path))
    dialog.generate(); wait(lambda: not dialog.busy)
    assert dialog.observed_path and dialog.open_button.isEnabled()
    from src.analysis.pipeline.parser import Parser
    loader = DataLoader(); header, source = loader.load_csv(dialog.observed_path)
    # Read metadata through the actual analysis parser; only observed.csv is used.
    from src.config.data_columns import FACE_PREFIX_TO_INFO
    parsed = Parser(FACE_PREFIX_TO_INFO).process(header, source)
    declaration = artifact_simulation(header['artifact_metadata'])
    assert declaration['route'] == 'marker_csv' and declaration['mode'] == 'single_drop'
    assert declaration['configuration']['observation_profile']['marker']['seed'] == 2468
    assert len(parsed) == 63
    previous = dialog.observed_path
    window.custom_h_input.setValue(321)
    assert dialog.source_stale and not dialog.generate_button.isEnabled()
    dialog.generate(); assert not dialog.busy and dialog.observed_path == previous
