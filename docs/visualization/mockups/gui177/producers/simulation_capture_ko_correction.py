"""Capture the three Korean GUI-08 display corrections with generated defaults."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from PySide6.QtGui import QFontInfo
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QScrollArea
from src.utils import ui_language
from src.simulation.ui.main_window import SimulationUI

destination = Path('tmp/gui177/simulation')
app = QApplication([])
captures = []
ui_language.preferred_language = lambda: 'en'
ui_language.configure_language(app)
english = SimulationUI()
english.show()
english.resize(1100, 720)
QTest.qWait(40)
path = destination / 'ko-corrected-en-1100x720-sequence.png'
english.grab().save(str(path))
captures.append(dict(path=path.as_posix(), language='en', client_size=[english.width(), english.height()]))
english.close()
ui_language.preferred_language = lambda: 'ko'
ui_language.configure_language(app)
window = SimulationUI()
window.show()
window.resize(820, 600)
QTest.qWait(40)
initial = window._capture_config()
path = destination / 'ko-corrected-ko-820x600-sequence.png'
window.grab().save(str(path))
captures.append(dict(path=path.as_posix(), language='ko', client_size=[window.width(), window.height()]))
window._show_settings()
app.processEvents()
for index, label in ((1, 'physics'), (2, 'markers')):
    window.settings.tabs.setCurrentIndex(index)
    app.processEvents()
    window.settings_dialog.findChild(QScrollArea).verticalScrollBar().setValue(0)
    app.processEvents()
    path = destination / f'ko-corrected-820x600-{label}-dialog.png'
    window.settings_dialog.grab().save(str(path))
    captures.append(dict(path=path.as_posix(), client_size=[window.settings_dialog.width(), window.settings_dialog.height()]))
window.settings_dialog.accept()
app.processEvents()
window.open_marker_export()
dialog = window.marker_dialog
dialog.resize(820, 600)
app.processEvents()
dialog.canvas.draw()
path = destination / 'ko-corrected-820x600-marker-csv.png'
dialog.grab().save(str(path))
captures.append(dict(path=path.as_posix(), client_size=[dialog.width(), dialog.height()]))
assert window._capture_config() == initial
source_files = ['src/simulation/ui/main_window.py', 'src/simulation/ui/mode_settings.py',
    'src/simulation/ui/marker_export_dialog.py', 'src/utils/ui_text_ko.py', 'tests/test_gui177_simulation.py']
source_hashes = {name: hashlib.sha256(Path(name).read_bytes()).hexdigest() for name in source_files}
report = dict(base_sha=subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
    source_tree_state='working tree', source_file_sha256=source_hashes,
    dirty_source_files=subprocess.check_output(['git', 'diff', '--name-only', 'HEAD', '--', *source_files], text=True).splitlines(),
    input_kind='SimulationUI public default ModeProfiles generated fixture v1',
    input_sha256=hashlib.sha256(json.dumps(initial, sort_keys=True, ensure_ascii=True).encode()).hexdigest(),
    payload_unchanged=True, language='ko', app_font=app.font().toString(),
    resolved_font=QFontInfo(app.font()).family(), platform=app.platformName(),
    dpr=window.devicePixelRatioF(), logical_dpi=window.logicalDpiX(), captures=captures,
    fault_displays=[dialog.kind.itemText(i) for i in range(dialog.kind.count())],
    fault_keys=[dialog.kind.itemData(i) for i in range(dialog.kind.count())],
    layout_dimensions_display=dialog.dimensions.text())
(destination / 'ko-corrected-metadata.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
dialog.reject()
window.close()
app.processEvents()
