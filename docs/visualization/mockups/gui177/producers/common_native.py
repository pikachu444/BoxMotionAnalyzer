import json
import subprocess
import sys
import platform
import hashlib
from importlib.metadata import version
from pathlib import Path

from PySide6.QtCore import Qt, QSettings, QPoint
from PySide6.QtGui import QFontMetrics, QFontInfo, QRegion
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QLabel, QToolButton, QSplitter, QTableWidget

from src.analysis.app.main_window import MainApp
from src.utils import ui_language
from src.utils.app_identity import configure_qt_application
from src.utils.qt_sections import set_path_label
from src.simulation.scene_review_fixtures import install_ui_fixture, public_raw

app = QApplication([])
language = sys.argv[1]
assert language in ('en', 'ko')
output = Path(__file__).parent / f'common-native-v7-{language}'
output.mkdir()
original_settings = ui_language._settings
ui_language._settings = lambda: QSettings(str(output / 'interface.ini'), QSettings.Format.IniFormat)
assert ui_language.save_language(language)
configure_qt_application(app)


def rectangle(rect):
    return [rect.x(), rect.y(), rect.width(), rect.height()]


def minimum(widget):
    return dict(type=type(widget).__name__, name=widget.objectName(),
                minimum=[widget.minimumWidth(), widget.minimumHeight()],
                minimum_hint=[widget.minimumSizeHint().width(), widget.minimumSizeHint().height()],
                size_hint=[widget.sizeHint().width(), widget.sizeHint().height()])


source_paths = ['src/analysis/app/main_window.py', 'src/analysis/ui/widget_raw_data_processing.py',
    'src/analysis/ui/widget_scene_review.py', 'src/analysis/ui/widget_slice_processing.py',
    'src/analysis/ui/widget_results_analyzer.py', 'src/analysis/ui/plot_manager.py',
    'src/utils/plot_toolbar.py', 'src/utils/qt_sections.py', 'src/utils/ui_language.py',
    'src/utils/ui_text_ko.py', 'src/utils/app_identity.py', 'src/simulation/scene_review_fixtures.py']
source_hashes = {path: hashlib.sha256(Path(path).read_bytes()).hexdigest() for path in source_paths}
metadata = {
    'source_sha': subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
    'revision_note': 'working-tree GUI changes on baseline SHA',
    'platform': app.platformName(),
    'font': [app.font().family(), app.font().pointSizeF()],
    'actual_font': [QFontInfo(app.font()).family(), QFontInfo(app.font()).pointSizeF()],
    'versions': dict(python=platform.python_version(), **{name: version(name) for name in
                    ['numpy', 'pandas', 'matplotlib', 'PySide6', 'pyvista', 'vtk', 'pytest']}),
    'screens': [dict(geometry=rectangle(screen.geometry()), available=rectangle(screen.availableGeometry()),
                     dpi=screen.logicalDotsPerInch(), dpr=screen.devicePixelRatio()) for screen in app.screens()],
    'settings': 'isolated task INI; original ui_language._settings restored before process exit',
    'language': language,
    'source_files_sha256': source_hashes,
    'scope': 'Native Windows Qt widget grabs and font fallback glyph checks; not desktop foreground proof',
    'sizes': [],
}
try:
    window = MainApp()
    source = public_raw(output)
    source = source.rename(source.with_name('긴_실험_파일명_capture.csv'))
    source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
    install_ui_fixture(window.original_widget, source)
    metadata['input'] = dict(source_kind='handcrafted_dummy', source_sha256=source_hash,
        scene_count=24, include=2, exclude=22, generator='src.simulation.scene_review_fixtures.public_raw/install_ui_fixture')
    window.show()
    QTest.qWait(120)
    for width, height in ((1510, 800), (1100, 720), (820, 600)):
        window.resize(width, height)
        for index in range(3):
            window.tab_widget.setCurrentIndex(index)
            QTest.qWait(80)
            page = window.tab_widget.currentWidget()
            toolbar = page.toolbar
            overflow = toolbar.findChild(QToolButton, 'qt_toolbar_ext_button')
            menu_actions = overflow.menu().actions() if overflow.isVisible() and overflow.menu() else []
            inaccessible = [name for name, action in toolbar._actions.items()
                            if not toolbar.widgetForAction(action).isVisible() and action not in menu_actions]
            assert not inaccessible, inaccessible
            non_ascii = ''.join(action.text() for action in toolbar._actions.values())
            non_ascii += window.statusBar().currentMessage()
            if index == 0:
                non_ascii += window.original_widget.file_path_label.text()
            missing = sorted({character for character in non_ascii if ord(character) > 127
                              and not QFontMetrics(toolbar.font()).inFontUcs4(ord(character))})
            assert not missing, missing
            path = f'common-native-{language}-{width}x{height}-step{index}.png'
            window.grab().save(str(output / path))
            metadata['sizes'].append(dict(language=language, requested=[width, height],
                actual=[window.width(), window.height()], page=index, dpr=window.devicePixelRatioF(),
                frame_geometry=rectangle(window.frameGeometry()),
                minimum_widgets=[minimum(widget) for widget in [window, page, toolbar,
                    *page.findChildren(QSplitter), *page.findChildren(QTableWidget)]],
                dpi=window.logicalDpiX(), toolbar_width=toolbar.width(),
                icon_size=toolbar.iconSize().width(), overflow=overflow.isVisible(),
                missing_glyphs=missing, inaccessible_actions=inaccessible,
                status=window.statusBar().currentMessage(), capture=path))
            if index == 0:
                table = page.scene_panel.table
                viewport = table.viewport()
                visible = sum(not (rect := table.visualItemRect(table.item(row, 0))).isEmpty()
                              and QRegion(rect).subtracted(viewport.visibleRegion()).isEmpty()
                              for row in range(table.rowCount()))
                metadata['sizes'][-1]['table'] = dict(total_rows=table.rowCount(), complete_rows=visible,
                    header_height=table.horizontalHeader().height(), row_heights=[table.rowHeight(row) for row in range(4)],
                    scrollbar_height=table.horizontalScrollBar().height(),
                    scrollbar_visible=table.horizontalScrollBar().isVisible())
                if width >= 1100:
                    assert visible >= 4, visible
                def bounds(widget):
                    position = widget.mapTo(window, QPoint())
                    return [position.x(), position.y(), widget.width(), widget.height()]
                renderer = page.canvas.get_renderer()
                metadata['sizes'][-1]['bbox'] = dict(
                    canvas=bounds(page.canvas), table=bounds(table), toolbar=bounds(toolbar),
                    save_slice=bounds(page.save_slice_button), save_all=bounds(page.scene_panel.save_all_button),
                    save_process=bounds(page.save_process_button),
                    mpl_x_label=list(page.plot_manager.ax.xaxis.label.get_window_extent(renderer).bounds),
                    mpl_y_label=list(page.plot_manager.ax.yaxis.label.get_window_extent(renderer).bounds))
    assert hashlib.sha256(source.read_bytes()).hexdigest() == source_hash
    window.close()
    app.processEvents()
finally:
    ui_language._settings = original_settings
assert source_hashes == {path: hashlib.sha256(Path(path).read_bytes()).hexdigest() for path in source_paths}
metadata['source_files_unchanged_during_capture'] = True
outside = [(entry['requested'], key, bounds) for entry in metadata['sizes'] if entry['page'] == 0
           for key, bounds in entry['bbox'].items() if key.startswith('mpl_')
           and (bounds[0] < 0 or bounds[1] < 0
                or bounds[0] + bounds[2] > entry['bbox']['canvas'][2]
                or bounds[1] + bounds[3] > entry['bbox']['canvas'][3])]
metadata['axis_label_bbox_inside_canvas'] = not outside
(output / 'metadata.json').write_text(
    json.dumps(metadata, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps({key: value for key, value in metadata.items() if key != 'sizes'}, ensure_ascii=True))
print('captures:', len(metadata['sizes']))
assert not outside, outside
