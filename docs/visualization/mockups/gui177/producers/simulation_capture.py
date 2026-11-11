import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import types

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from PySide6.QtCore import QPoint
from PySide6.QtGui import QRegion, QFontInfo
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
root = Path('tmp/gui177/simulation')
phase = sys.argv[1]
source_files = ['src/utils/qt_sections.py', 'src/simulation/ui/mode_settings.py',
                'src/simulation/ui/marker_export_dialog.py', 'src/simulation/ui/main_window.py']
source_hashes = {}
if '--baseline' in sys.argv:
    package = types.ModuleType('src.simulation.ui')
    package.__path__ = [str(Path('src/simulation/ui').resolve())]
    sys.modules['src.simulation.ui'] = package
for filename in source_files:
    if '--baseline' in sys.argv:
        source = subprocess.check_output(['git', 'show', 'HEAD:' + filename])
        name = filename[:-3].replace('/', '.')
        module = types.ModuleType(name)
        module.__file__ = filename
        module.__package__ = name.rpartition('.')[0]
        sys.modules[name] = module
        exec(compile(source, filename, 'exec'), module.__dict__)
    else:
        source = Path(filename).read_bytes()
    source_hashes[filename] = hashlib.sha256(source).hexdigest()
from src.simulation.ui.main_window import SimulationUI
from src.utils import ui_language
app = QApplication.instance() or QApplication([])
records = []
for language in ('en', 'ko'):
    ui_language.preferred_language = lambda: language
    ui_language.configure_language(app)
    for width, height in ((1510, 800), (1100, 720), (820, 600)):
        window = SimulationUI()
        window.show()
        window.resize(width, height)
        QTest.qWait(60)
        app.processEvents()
        config = window._capture_config()
        canonical = json.dumps(config, sort_keys=True, ensure_ascii=True)
        identity = hashlib.sha256(canonical.encode()).hexdigest()
        controls = {name: getattr(window, name) for name in (
            'mode_combo', 'run_btn', 'batch_btn', 'marker_btn', 'custom_r_input',
            'custom_p_input', 'custom_y_input', 'friction_input', 'com_y',
            'noise_cb', 'noise_std_input', 'orientation_preview')}
        screens = {}
        for index, tab in enumerate(('sequence', 'physics', 'markers')):
            window.settings.tabs.setCurrentIndex(index)
            app.processEvents()
            filename = f'{phase}-{language}-{width}x{height}-{tab}.png'
            window.grab().save(str(root / filename))
            screens[tab] = {name: dict(
                bbox=[widget.mapTo(window, QPoint()).x(), widget.mapTo(window, QPoint()).y(), widget.width(), widget.height()],
                visible=widget.isVisible(),
                fully_visible=widget.isVisible() and not widget.rect().isEmpty() and QRegion(widget.rect()).subtracted(widget.visibleRegion()).isEmpty(),
                font=widget.font().toString(), resolved_font=QFontInfo(widget.font()).family()) for name, widget in controls.items()}
            if window._narrow:
                window._show_settings()
                app.processEvents()
                window.settings_dialog.grab().save(str(root / f'{phase}-{language}-{width}x{height}-{tab}-dialog.png'))
                window.settings_dialog.accept()
                app.processEvents()
        window.settings.tabs.setCurrentIndex(0)
        window.mode_combo.setCurrentIndex(1)
        app.processEvents()
        window.grab().save(str(root / f'{phase}-{language}-{width}x{height}-robot.png'))
        window.mode_combo.setCurrentIndex(0)
        window.open_marker_export()
        app.processEvents()
        dialog = window.marker_dialog
        dialog.resize(width, height)
        app.processEvents()
        dialog.grab().save(str(root / f'{phase}-{language}-{width}x{height}-marker-csv.png'))
        marker_bboxes = {name: [getattr(dialog, name).mapTo(dialog, QPoint()).x(),
            getattr(dialog, name).mapTo(dialog, QPoint()).y(), getattr(dialog, name).width(),
            getattr(dialog, name).height()] for name in ('fault_section', 'kind', 'start', 'end', 'generate_button', 'cancel_button')}
        dialog.reject()
        app.processEvents()
        records.append(dict(language=language, requested_size=[width, height],
            client_size=[window.width(), window.height()], font=app.font().toString(),
            resolved_font=QFontInfo(app.font()).family(),
            dpr=window.devicePixelRatioF(), logical_dpi=window.logicalDpiX(),
            base_sha=subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
            source_tree_state='baseline modules loaded by git show' if '--baseline' in sys.argv else 'working tree',
            dirty_source_files=[] if '--baseline' in sys.argv else [name for name, value in source_hashes.items()
                if value != hashlib.sha256(subprocess.check_output(['git', 'show', 'HEAD:' + name])).hexdigest()],
            source_file_sha256=source_hashes, platform=app.platformName(),
            input_kind='SimulationUI public default ModeProfiles generated fixture v1',
            input_sha256=identity, payload=config, screenshots=screens, marker_bboxes=marker_bboxes))
        window.close()
        app.processEvents()
(root / f'{phase}-metadata.json').write_text(json.dumps(records, indent=2), encoding='utf-8')
