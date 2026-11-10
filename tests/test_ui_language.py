from PySide6.QtCore import QSettings, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QDialog, QPushButton
from matplotlib import rcParams
import pytest

from src.analysis.app.main_window import MainApp
from src.analysis.compare.main_window import CompareMainWindow
from src.analysis.ui.dialog_processing_settings import ProcessingSettingsDialog
from src.config.config_analysis_ui import get_default_advanced_options
from src.launcher import LanguageOptions, LauncherWindow
from src.simulation.marker_fixtures import virtual_profile_32
from src.simulation.ui.main_window import SimulationUI
from src.simulation.ui.marker_profile_dialog import MarkerProfileDialog
from src.utils import ui_language
from src.visualization.control_panel import ControlPanel


@pytest.fixture
def language_app(tmp_path, monkeypatch):
    app = QApplication.instance() or QApplication([])
    old = app.property('interfaceLanguage')
    old_fonts = list(rcParams['font.sans-serif'])
    old_minus = rcParams['axes.unicode_minus']
    path = str(tmp_path / 'interface.ini')
    monkeypatch.setattr(ui_language, '_settings', lambda: QSettings(path, QSettings.IniFormat))
    yield app
    translator = getattr(app, 'qt_language_translator', None)
    if translator is not None:
        app.removeTranslator(translator)
        del app.qt_language_translator
    rcParams['font.sans-serif'] = old_fonts
    rcParams['axes.unicode_minus'] = old_minus
    app.setProperty('interfaceLanguage', old)


def test_apply_persists_for_next_launch_and_cancel_preserves_it(language_app):
    app = language_app
    ui_language.configure_language(app)
    window = LauncherWindow()
    window.show()
    try:
        assert window.btn_options.text() == 'Options'
        dialog = LanguageOptions(window)
        dialog.show()
        assert dialog.language.currentData() == 'en'
        dialog.language.setCurrentIndex(dialog.language.findData('ko'))
        QTest.mouseClick(next(b for b in dialog.findChildren(QPushButton) if b.text() == 'Apply'), Qt.LeftButton)
        assert dialog.result() == QDialog.Accepted
        assert ui_language.preferred_language() == 'ko'
        assert window.btn_options.text() == 'Options'
        assert app.property('interfaceLanguage') == 'en'

        retry = LanguageOptions(window)
        retry.show()
        assert retry.language.currentData() == 'ko'
        retry.language.setCurrentIndex(retry.language.findData('en'))
        QTest.mouseClick(next(b for b in retry.findChildren(QPushButton) if b.text() == 'Cancel'), Qt.LeftButton)
        assert retry.result() == QDialog.Rejected
        assert ui_language.preferred_language() == 'ko'
    finally:
        window.close()


def test_korean_windows_keep_display_and_data_separate(language_app):
    assert ui_language.save_language('ko')
    ui_language.configure_language(language_app)
    launcher = LauncherWindow()
    analysis = MainApp()
    comparison = CompareMainWindow()
    simulation = SimulationUI()
    controls = ControlPanel()
    processing = ProcessingSettingsDialog(get_default_advanced_options())
    profile = MarkerProfileDialog(virtual_profile_32())
    windows = (launcher, analysis, comparison, simulation, controls, processing, profile)
    try:
        assert launcher.btn_simulation.text() == '시뮬레이션'
        assert analysis.tab_widget.tabText(0) == '1단계: 씬'
        type_combo = analysis.original_widget.scene_panel.type_combo
        assert (type_combo.currentText(), type_combo.currentData()) == ('알 수 없음', 'Unknown')
        assert comparison.windowTitle() == '실험 비교'
        assert comparison.playback_panel.btn_master_play.text() == '재생'
        assert (simulation.mode_combo.currentText(), simulation.mode_combo.currentData()) == ('단일 낙하', 'single_drop')
        assert controls.box_checkbox.text() == '상자'
        assert processing.windowTitle() == '고급 처리 설정'
        assert profile.windowTitle() == '마커 프로필'
        profile.view_combo.setCurrentIndex(profile.view_combo.findData('FRONT'))
        assert (profile.view_combo.currentText(), profile.current_face) == ('앞면', 'FRONT')
    finally:
        for window in reversed(windows):
            window.close()
