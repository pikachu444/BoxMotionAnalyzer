"""Actual existing settings controls and worker retain an opt-in PUB10 profile."""
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox

from src.simulation.mode_profiles import read_profiles, save_profiles
from src.utils.observation_metadata import artifact_observation
from test_observation_integration import configured
from test_simulation_modes_gui import window, wait


def test_profile_settings_save_apply_export_and_open_step1(window, tmp_path, monkeypatch):
    state,c=configured();source=tmp_path/'settings.json';saved=tmp_path/'saved.json'
    save_profiles(source,state)
    panel=window.settings
    monkeypatch.setattr(QFileDialog,'getOpenFileName',lambda *a:(str(source),''))
    monkeypatch.setattr(QFileDialog,'getSaveFileName',lambda *a:(str(saved),''))
    warnings=[]
    monkeypatch.setattr(QMessageBox,'warning',lambda *a:warnings.append(a[2]))
    QTest.mouseClick(panel.open_button,Qt.LeftButton)
    QTest.mouseClick(panel.save_button,Qt.LeftButton)
    assert read_profiles(saved).configs['single_drop']==c
    QTest.mouseClick(panel.apply_button,Qt.LeftButton)
    assert window.profiles.configs['single_drop']==c
    QTest.mouseClick(window.marker_btn,Qt.LeftButton)
    dialog=window.marker_dialog
    monkeypatch.setattr(QFileDialog,'getExistingDirectory',lambda *a:str(tmp_path))
    QTest.mouseClick(dialog.generate_button,Qt.LeftButton)
    wait(lambda:not dialog.busy,timeout=30)
    assert not warnings and dialog.observed_path,dialog.status.text()
    QTest.mouseClick(dialog.open_button,Qt.LeftButton)
    raw=window.analysis_windows[-1].original_widget
    assert raw.source_path==dialog.observed_path
    assert raw.parsed_data.F1_X.loc[.08:.152].isna().all()
    assert raw.parsed_data.B1_X.notna().all()
    assert not raw.marker_correction_decisions
    declaration=artifact_observation(raw.header_info['artifact_metadata'])
    assert declaration['profile_hash']==c['observation_profile']['marker']['observation_profile']['content_hash']
    evidence=Path('tmp/issue143/gui');evidence.mkdir(parents=True,exist_ok=True)
    for width,height in ((1920,1080),(1150,820)):
        window.resize(width,height);QApplication.processEvents()
        assert window.grab().save(str(evidence/f'settings-{width}x{height}.png'))
    assert dialog.grab().save(str(evidence/'export.png'))
    assert window.analysis_windows[-1].grab().save(str(evidence/'step1.png'))
    for analysis in window.analysis_windows:analysis.close()
