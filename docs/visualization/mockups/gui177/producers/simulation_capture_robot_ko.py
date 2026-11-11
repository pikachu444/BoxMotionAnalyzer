"""One native Korean Robot settings capture using generated defaults."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from PySide6.QtGui import QFontInfo
from PySide6.QtCore import QPoint
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QScrollArea
from src.utils import ui_language
from src.simulation.ui.main_window import SimulationUI

app = QApplication([])
ui_language.preferred_language = lambda: 'ko'
ui_language.configure_language(app)
window = SimulationUI()
window.show()
window.mode_combo.setCurrentIndex(1)
QTest.qWait(40)
payload = window._capture_config()
destination = Path('tmp/gui177/simulation')
captures = []
for width, height in ((1510, 800), (1100, 720), (820, 600)):
    window.resize(width, height)
    QTest.qWait(40)
    if window._narrow:
        window._show_settings()
        app.processEvents()
        window.settings_dialog.findChild(QScrollArea).verticalScrollBar().setValue(0)
        target = window.settings_dialog
    else:
        target = window
        window.right_scroll.verticalScrollBar().setValue(0)
    app.processEvents()
    image_path = destination / f'robot-corrected-ko-{width}x{height}-settings.png'
    target.grab().save(str(image_path))
    captures.append(dict(path=image_path.as_posix(), client_size=[target.width(), target.height()],
        window_client_size=[window.width(), window.height()], control_bboxes={name: [
            getattr(window.settings, name).mapTo(target, QPoint()).x(),
            getattr(window.settings, name).mapTo(target, QPoint()).y(),
            getattr(window.settings, name).width(), getattr(window.settings, name).height()]
            for name in ('handling', 'attachment_face', 'run_scope', 'table', 'apply_button', 'cancel_button')}))
    assert window._capture_config() == payload
files = ['src/simulation/ui/main_window.py', 'src/simulation/ui/mode_settings.py',
         'src/simulation/ui/marker_export_dialog.py', 'src/utils/ui_text_ko.py', 'tests/test_gui177_simulation.py']
dirty = subprocess.check_output(['git', 'diff', '--name-only', 'HEAD', '--', *files], text=True).splitlines()
report = dict(base_sha=subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
    source_tree_state='working tree' if dirty else 'clean checkout at base_sha', dirty_source_files=dirty,
    source_file_sha256={name: hashlib.sha256(Path(name).read_bytes()).hexdigest() for name in files},
    capture=image_path.as_posix(), captures=captures, client_size=[window.settings_dialog.width(), window.settings_dialog.height()],
    app_font=app.font().toString(), resolved_font=QFontInfo(app.font()).family(),
    platform=app.platformName(), dpr=window.devicePixelRatioF(), logical_dpi=window.logicalDpiX(),
    input_kind='SimulationUI generated default Robot ModeProfiles fixture v1',
    input_sha256=hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=True).encode()).hexdigest(),
    payload_unchanged=window._capture_config() == payload,
    handling=[dict(display=window.settings.handling.itemText(i), key=window.settings.handling.itemData(i)) for i in range(4)])
(destination / 'robot-corrected-metadata.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
window.settings_dialog.reject()
window.close()
app.processEvents()
