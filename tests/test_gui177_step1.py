"""Step 1 layout and session invariants for the issue 177 workflow."""
import pytest
from PySide6.QtCore import QPoint, QRect
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QFileDialog

from src.analysis.app.main_window import MainApp
from src.simulation.scene_review_fixtures import install_ui_fixture, public_raw, ui_session


def fully_visible(widget, rect=None):
    """Include every clipping ancestor, including a scroll area's viewport."""
    rect = QRect(rect or widget.rect())
    if not widget.isVisible():
        return False
    parent = widget.parentWidget()
    while parent is not None:
        rect.translate(widget.mapTo(parent, QPoint(0, 0)))
        if not parent.rect().contains(rect):
            return False
        widget, parent = parent, parent.parentWidget()
    return True


@pytest.fixture
def workspace(tmp_path):
    app = QApplication.instance() or QApplication([])
    window = MainApp()
    window.tab_widget.setCurrentIndex(0)
    capture = window.original_widget
    source = public_raw(tmp_path)
    install_ui_fixture(capture, source)
    session = ui_session(source, 8)
    for index, row in enumerate(session.rows):
        session.set_decision(row['id'], 'include' if index < 2 else 'exclude')
    capture.scene_session = capture.scene_panel.session = session
    capture._populate_scene_signals(session.result, 'Vertical speed (mm/s)')
    capture.scene_panel.refresh(session.rows[0]['id'])
    capture._update_scene_gates()
    window.show()
    QTest.qWait(100)
    yield window, capture, source
    window.close()
    window.deleteLater()
    app.processEvents()


@pytest.mark.parametrize('size,rows', [((1510, 800), 4), ((1100, 720), 4), ((820, 600), 2)])
def test_s01_rows_actions_and_decisions_survive_navigation(workspace, size, rows, monkeypatch):
    window, capture, source = workspace
    table = capture.scene_panel.table
    decisions = [r['decision'] for r in capture.scene_session.rows]
    assert decisions == ['include'] * 2 + ['exclude'] * 6
    assert capture._scene_save_gate(batch=True)[0] == 2
    monkeypatch.setattr(QFileDialog, 'getExistingDirectory', lambda *args: '')
    assert capture.save_included_scenes() in (None, [])
    assert [r['decision'] for r in capture.scene_session.rows] == decisions
    from src.analysis.ui import scene_review_flow
    from src.analysis.pipeline.pose_optimizer import PoseOptimizer
    monkeypatch.setattr(scene_review_flow, 'detect_scenes', lambda *a, **k: pytest.fail('unexpected detection'))
    monkeypatch.setattr(PoseOptimizer, 'process', lambda *a, **k: pytest.fail('unexpected optimization'))
    window.resize(*size)
    QTest.qWait(100)
    capture.review_scroll.ensureWidgetVisible(capture.scene_panel, 0, 0)
    QTest.qWait(50)
    assert (window.width(), window.height()) == size
    capture.canvas.draw()
    label_bbox = capture.plot_manager.ax.yaxis.label.get_window_extent(capture.canvas.get_renderer())
    assert label_bbox.y0 >= 0 and label_bbox.y1 <= capture.fig.bbox.height
    assert [table.horizontalHeader().logicalIndex(i) for i in range(9)] == [0, 5, 1, 2, 3, 4, 6, 7, 8]
    for row in range(rows):
        rect = table.visualItemRect(table.item(row, 0))
        assert fully_visible(table.viewport(), rect)
    # The same check must reject a deliberately scrolled-out row.
    table.scrollToBottom()
    assert not fully_visible(table.viewport(), table.visualItemRect(table.item(0, 0)))
    for button in (capture.save_slice_button, capture.scene_panel.save_all_button, capture.save_process_button):
        assert fully_visible(button)
    capture.capture_splitter.setSizes([220, 350])
    capture.capture_splitter.splitterMoved.emit(220, 1)
    before_sizes = capture.capture_splitter.sizes()
    window.tab_widget.setCurrentIndex(1)
    window.tab_widget.setCurrentIndex(0)
    QTest.qWait(50)
    assert [r['decision'] for r in capture.scene_session.rows] == decisions
    assert capture._scene_save_gate(batch=True)[0] == 2
    assert capture.capture_splitter.sizes() == before_sizes


def test_s02_long_source_unknown_and_identity_gate(workspace):
    window, capture, source = workspace
    panel = capture.scene_panel
    assert capture.file_path_label.toolTip() == str(source)
    assert panel.type_combo.currentData() == 'Unknown'
    assert panel.edition_combo.currentData() is None
    assert not panel.confirm_button.isEnabled()
    assert not panel.selected_row()['identity']['confirmed']
    assert panel.type_basis_label.text().endswith('Unconfirmed')


def test_s03_new_source_invalidates_old_scene_session(workspace, tmp_path):
    window, capture, source = workspace
    old = capture.scene_session
    second = tmp_path / 'second.csv'
    second.write_bytes(source.read_bytes())
    capture.load_csv_path(str(second))
    assert capture.source_path == str(second)
    assert capture.scene_session is None
    assert capture.scene_panel.session is None
    assert old.rows[0]['decision'] == 'include'
    assert not capture.scene_panel.save_all_button.isEnabled()


def test_scene_signal_display_is_translated_without_changing_identity(workspace, tmp_path, monkeypatch):
    from matplotlib import rcParams
    from PySide6.QtCore import QSettings
    from src.utils import ui_language

    window, capture, source = workspace
    app = QApplication.instance()
    previous = app.property('interfaceLanguage')
    fonts, unicode_minus = list(rcParams['font.sans-serif']), rcParams['axes.unicode_minus']
    settings = QSettings(str(tmp_path / 'language.ini'), QSettings.IniFormat)
    settings.setValue('interface/language', 'ko')
    monkeypatch.setattr(ui_language, '_settings', lambda: settings)
    ui_language.configure_language(app)
    try:
        key = capture.combo_plot_axis.currentData()
        capture.update_plot()
        assert capture.combo_plot_axis.currentData() == key == 'Vertical speed (mm/s)'
        assert capture.plot_manager.ax.get_ylabel() == '수직 속도 (mm/s)'
        assert capture.plot_manager.ax.get_legend().get_texts()[0].get_text() == '수직 속도 (mm/s)'
    finally:
        app.setProperty('interfaceLanguage', previous)
        capture.update_plot()
        rcParams['font.sans-serif'] = fonts
        rcParams['axes.unicode_minus'] = unicode_minus


def test_graph_labels_fit_after_resize_while_another_tab_is_selected(workspace):
    window, capture, source = workspace
    window.resize(1510, 800)
    QTest.qWait(50)
    window.tab_widget.setCurrentIndex(2)
    window.resize(820, 600)
    QTest.qWait(50)
    window.tab_widget.setCurrentIndex(0)
    QTest.qWait(100)
    capture.canvas.draw()
    bounds = capture.plot_manager.ax.yaxis.label.get_window_extent(capture.canvas.get_renderer())
    assert 0 <= bounds.y0 <= bounds.y1 <= capture.fig.bbox.height
