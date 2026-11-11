"""Shared presentation and L01 lifecycle contracts using generated UI inputs."""
from copy import deepcopy
import hashlib

import pytest
from matplotlib import rcParams
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from PySide6.QtCore import QCoreApplication, QEvent, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QLabel, QToolButton, QVBoxLayout, QWidget
from shiboken6 import getCppPointer, isValid

from src.analysis.app.main_window import MainApp
from src.analysis.pipeline.marker_flip import MarkerCorrectionDecision
from src.utils.plot_toolbar import PlotToolbar
from src.utils.qt_sections import set_path_label, unique_path_labels
from src.utils import ui_language


@pytest.fixture
def app():
    return QApplication.instance() or QApplication([])


def test_vertical_toolbar_preserves_actions_keyboard_and_coordinate_route(app, monkeypatch):
    host = QWidget()
    canvas = FigureCanvasQTAgg(Figure())
    calls = []
    for callback in ('home', 'back', 'forward', 'configure_subplots', 'edit_parameters', 'save_figure'):
        monkeypatch.setattr(PlotToolbar, callback, lambda _self, *_, name=callback: calls.append(name))
    toolbar = PlotToolbar(canvas, host, vertical=True)
    layout = QVBoxLayout(host)
    layout.addWidget(toolbar)
    messages = []
    toolbar.coordinate_message.connect(messages.append)
    try:
        host.show()
        app.processEvents()
        assert toolbar.orientation() == Qt.Orientation.Vertical
        assert toolbar.iconSize().width() == toolbar.iconSize().height() == 16
        assert 34 <= toolbar.width() <= 44
        assert not hasattr(toolbar, 'locLabel')
        assert set(toolbar._actions) == {
            'home', 'back', 'forward', 'pan', 'zoom', 'configure_subplots', 'edit_parameters', 'save_figure'}
        for name, action in toolbar._actions.items():
            button = toolbar.widgetForAction(action)
            assert button.focusPolicy() & Qt.FocusPolicy.TabFocus
            if name in ('pan', 'zoom'):
                button.setFocus()
                QTest.keyClick(button, Qt.Key.Key_Space)
                assert toolbar.mode.name == name.upper()
                QTest.keyClick(button, Qt.Key.Key_Space)
                assert not toolbar.mode
            else:
                # Empty Matplotlib history disables Back/Forward; exercise their
                # original callbacks as if populated history enabled them.
                if name in ('back', 'forward'):
                    assert not action.isEnabled()
                    action.setEnabled(True)
                action.trigger()
        assert calls == ['home', 'back', 'forward', 'configure_subplots', 'edit_parameters', 'save_figure']
        toolbar.set_message('Time=1.250 s; X=42 mm')
        assert messages == ['Time=1.250 s; X=42 mm']
        toolbar.setFixedHeight(80)
        app.processEvents()
        extension = toolbar.findChild(QToolButton, 'qt_toolbar_ext_button')
        assert extension.isVisible() and extension.menu() is not None
        menu = extension.menu()
        for name, action in toolbar._actions.items():
            if toolbar.widgetForAction(action).isVisible():
                continue
            assert action in menu.actions()
            for _ in range(2 if name in ('pan', 'zoom') else 1):
                menu.popup(toolbar.mapToGlobal(toolbar.rect().bottomRight()))
                app.processEvents()
                QTest.mouseClick(menu, Qt.MouseButton.LeftButton,
                                 pos=menu.actionGeometry(action).center())
                app.processEvents()
            if name in ('pan', 'zoom'):
                assert not toolbar.mode
            else:
                assert calls.count(name) == 2
        horizontal = PlotToolbar(canvas, host)
        horizontal.set_message('original coordinates')
        assert horizontal.locLabel.text() == 'original coordinates'
    finally:
        host.close()
        host.deleteLater()
        app.processEvents()


def test_shortest_unique_path_labels_preserve_copy_identity(app):
    paths = ['C:/one/capture.proc', 'C:/two/capture.proc', 'C:/one/different.proc',
             'C:/one/capture.proc', 'C:/deep/one/capture.proc']
    labels = unique_path_labels(paths)
    assert labels[0] == labels[3]
    assert len(set(labels)) == 4
    assert labels[2] == 'different.proc'
    assert 'one' in labels[0] and 'two' in labels[1] and 'deep' in labels[4]
    label = QLabel()
    set_path_label(label, paths[0], display_name=labels[0])
    assert label.text() == labels[0]
    assert label.toolTip() == label.property('fullPath') == paths[0]
    assert label.textInteractionFlags() & Qt.TextInteractionFlag.TextSelectableByKeyboard
    assert unique_path_labels([]) == []
    assert unique_path_labels(['', 'a.proc']) == ['', 'a.proc']


@pytest.mark.parametrize('language', ['en', 'ko'])
def test_small_analysis_window_executes_hidden_tools_from_native_overflow(app, monkeypatch, language):
    previous_language = app.property('interfaceLanguage')
    previous_fonts = list(rcParams['font.sans-serif'])
    previous_minus = rcParams['axes.unicode_minus']
    previous_translator = getattr(app, 'qt_language_translator', None)
    monkeypatch.setattr(ui_language, 'preferred_language', lambda: language)
    ui_language.configure_language(app)
    calls = []
    for callback in ('configure_subplots', 'edit_parameters', 'save_figure'):
        monkeypatch.setattr(PlotToolbar, callback, lambda _self, *_, name=callback: calls.append(name))
    window = MainApp()
    try:
        window.show()
        app.processEvents()
        window.resize(820, 600)
        app.processEvents()
        toolbar = window.original_widget.toolbar
        assert (window.width(), window.height()) == (820, 600)
        extension = toolbar.findChild(QToolButton, 'qt_toolbar_ext_button')
        assert extension.isVisible() and extension.menu() is not None
        menu = extension.menu()
        for name, action in toolbar._actions.items():
            if toolbar.widgetForAction(action).isVisible():
                continue
            assert action in menu.actions()
            if not action.isEnabled():
                continue
            for _ in range(2 if name in ('pan', 'zoom') else 1):
                menu.popup(toolbar.mapToGlobal(toolbar.rect().bottomRight()))
                app.processEvents()
                QTest.mouseClick(menu, Qt.MouseButton.LeftButton,
                                 pos=menu.actionGeometry(action).center())
                app.processEvents()
            if name in ('pan', 'zoom'):
                assert not toolbar.mode
            elif name in ('configure_subplots', 'edit_parameters', 'save_figure'):
                assert name in calls
        assert 'save_figure' in calls
    finally:
        window.close()
        window.deleteLater()
        app.processEvents()
        app.setProperty('interfaceLanguage', previous_language)
        translator = getattr(app, 'qt_language_translator', None)
        if translator is not None and translator is not previous_translator:
            app.removeTranslator(translator)
            if previous_translator is None:
                del app.qt_language_translator
            else:
                app.qt_language_translator = previous_translator
        rcParams['font.sans-serif'] = previous_fonts
        rcParams['axes.unicode_minus'] = previous_minus


def test_active_page_status_remembers_last_message_and_scopes_background_logs(app):
    window = MainApp()
    try:
        window.original_widget.log_message.emit('[INFO] File loaded and parsed.')
        assert window.statusBar().currentMessage() == 'File loaded and parsed.'
        window.tab_widget.setCurrentWidget(window.processing_widget)
        assert window.statusBar().currentMessage() == 'Step 1.5: No slice loaded'
        window.original_widget.log_message.emit('[INFO] Hidden scene update')
        assert window.statusBar().currentMessage() == 'Step 1.5: No slice loaded'
        window.processing_widget.log_message.emit('[INFO] Slice ready')
        assert window.statusBar().currentMessage() == 'Slice ready'
        window.tab_widget.setCurrentWidget(window.result_widget)
        window.result_widget.log_message.emit('[INFO] Result selected')
        window.pipeline_controller.log_message.emit('[INFO] Background processing')
        assert window.statusBar().currentMessage() == 'Result selected'
        window.tab_widget.setCurrentWidget(window.original_widget)
        assert window.statusBar().currentMessage() == 'Hidden scene update'
        window.tab_widget.setCurrentWidget(window.processing_widget)
        assert window.statusBar().currentMessage() == 'Background processing'
        window.tab_widget.setCurrentWidget(window.result_widget)
        assert window.statusBar().currentMessage() == 'Result selected'
    finally:
        window.close()
        window.deleteLater()
        app.processEvents()


def test_l01_actual_analysis_identity_and_state_survive_reentry_and_close_refusal(app, tmp_path):
    from src.launcher import LauncherWindow
    from src.simulation.scene_review_fixtures import install_ui_fixture, public_raw

    launcher = LauncherWindow()
    launcher.open_data_processing()
    window = launcher.data_processing_window
    raw = window.original_widget
    try:
        source = public_raw(tmp_path)
        source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
        install_ui_fixture(raw, source, state='edited')
        pending = MarkerCorrectionDecision('pending-ui-fixture', .2, recommendation_axis='X')
        raw.marker_correction_decisions = [pending]
        raw.marker_review_dirty = True
        raw.scene_panel.table.selectRow(1)
        session = raw.scene_session
        rows = deepcopy(session.rows)
        selected = raw.scene_panel.selected_id()
        source_path, parsed = raw.source_path, raw.parsed_data
        pointer = getCppPointer(window)
        for minimized in (False, True):
            if minimized:
                window.showMinimized()
                app.processEvents()
            launcher.open_data_processing()
            app.processEvents()
            assert launcher.data_processing_window is window
            assert getCppPointer(window) == pointer
            assert raw.source_path == source_path and raw.parsed_data is parsed
            assert raw.scene_session is session and session.rows == rows
            assert raw.scene_panel.selected_id() == selected
            assert raw.marker_correction_decisions == [pending] and raw.marker_review_dirty
            assert hashlib.sha256(source.read_bytes()).hexdigest() == source_hash
            assert window.isVisible() and not window.isMinimized()
        window.processing_widget.single_running = True
        assert window.close() is False
        launcher.open_data_processing()
        assert launcher.data_processing_window is window and getCppPointer(window) == pointer
        assert raw.scene_session is session and session.rows == rows
        window.processing_widget.single_running = False
        assert window.close() is True
        launcher.open_data_processing()
        replacement = launcher.data_processing_window
        assert replacement is not window and getCppPointer(replacement) != pointer
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        assert not isValid(window)
        assert launcher.data_processing_window is replacement
    finally:
        for item in (window, launcher.data_processing_window, launcher):
            if item is not None and isValid(item):
                item.close()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
