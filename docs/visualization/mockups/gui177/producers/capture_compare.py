"""Generated GUI-06 identity/layout evidence; not measured-trial validation."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / 'tests')]
from comparison_fixtures import write_proc
from PySide6.QtCore import qVersion
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from src.analysis.compare.main_window import CompareMainWindow
from src.utils.ui_language import configure_language
from unittest.mock import patch


def bbox(widget):
    geometry = widget.geometry()
    return [geometry.x(), geometry.y(), geometry.width(), geometry.height()]


stage = sys.argv[1]
output = ROOT / 'tmp/gui177/compare' / stage
output.mkdir(parents=True, exist_ok=True)
inputs = ROOT / 'tmp/gui177/compare/inputs'
paths = []
for parent in ('capture-alpha', 'capture-beta'):
    folder = inputs / parent
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / ('same_capture_' + 'long_name_' * 10 + '.proc')
    if not path.exists():
        write_proc(path)
    paths.append(path)

app = QApplication.instance() or QApplication([])
capture_head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
source_names = ('src/analysis/compare/main_window.py', 'src/analysis/compare/ui_panels.py',
                'src/analysis/compare/playback_panel.py', 'src/utils/qt_sections.py', 'src/utils/ui_text_ko.py')
clean_source = subprocess.run(['git', 'diff', '--quiet', 'HEAD', '--', *source_names], cwd=ROOT).returncode == 0
report = {'capture_head_sha': capture_head,
          'source_commit_sha': capture_head if clean_source else None,
          'source_state': ('listed source files match source_commit_sha' if clean_source else
                           'working-tree snapshot identified by source_files; capture HEAD alone is not the GUI implementation revision'),
          'source_files': {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in
                           source_names},
          'capture_kind': 'QWidget grab with real VistaWidget; separate VTK buffer',
          'qt': qVersion(), 'platform': app.platformName(), 'app_font': app.font().toString(),
          'input_generator': 'tests/comparison_fixtures.py::write_proc; contract-1',
          'seed': 'handcrafted_dummy, same geometry/capture contents in distinct parent paths',
          'inputs': [{'path': p.relative_to(ROOT).as_posix(), 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()} for p in paths],
          'views': []}
for language in (sys.argv[2:] or ('en', 'ko')):
    with patch('src.utils.ui_language.preferred_language', return_value=language):
        configure_language(app)
    window = CompareMainWindow()
    window.show()
    window.load_result_files([str(p) for p in paths])
    window.control_panel.cb_view.setCurrentIndex(1)
    if hasattr(window.control_panel, 'detail_tabs'):
        window.control_panel.detail_tabs.setCurrentIndex(1)
    sizes = ((1510, 800), (1100, 720), (820, 600))
    if os.environ.get('GUI177_CAPTURE_SIZE'):
        sizes = (tuple(map(int, os.environ['GUI177_CAPTURE_SIZE'].split('x'))),)
    for size in sizes:
        window.resize(*size)
        QTest.qWait(120)
        window.graph_panel.canvas.draw()
        app.processEvents()
        name = f'{language}-{size[0]}x{size[1]}'
        window.grab().save(str(output / f'{name}.png'))
        graph = window.graph_panel
        renderer = graph.canvas.get_renderer()
        view = {'language': language, 'requested_client_size': list(size), 'actual_client_size': [window.width(), window.height()],
                'dpr': window.devicePixelRatioF(), 'dpi': window.screen().logicalDotsPerInch(),
                'window_font': window.font().toString(), 'table_font': window.table_panel.table.font().toString(),
                'table_rows': window.table_panel.table.rowCount(), 'splitter': window.right_splitter.sizes(),
                'bboxes': {key: bbox(widget) for key, widget in {
                    'summary': window.table_panel, 'playback': window.playback_panel, 'graph': graph,
                    'open': window.control_panel.btn_add_files, 'remove': window.control_panel.btn_remove_file,
                    'table_mode': window.table_panel.view_combo, 'guide': window.table_panel.guide_button,
                    'play': window.playback_panel.btn_master_play, 'toolbar': graph.toolbar, 'canvas': graph.canvas}.items()},
                'figure_size_px': [graph.fig.bbox.width, graph.fig.bbox.height],
                'axis_text': {'title': graph.plot_manager.ax.title.get_text(),
                              'x': graph.plot_manager.ax.xaxis.label.get_text(),
                              'y': graph.plot_manager.ax.yaxis.label.get_text()},
                'axis_bboxes': {key: list(label.get_window_extent(renderer).bounds) for key, label in {
                    'title': graph.plot_manager.ax.title, 'x': graph.plot_manager.ax.xaxis.label,
                    'y': graph.plot_manager.ax.yaxis.label}.items()},
                'tick_bboxes': {key: [{'text': label.get_text(), 'bbox': list(label.get_window_extent(renderer).bounds)}
                                     for value, label in zip(axis.get_majorticklocs(), axis.get_ticklabels())
                                     if min(axis.get_view_interval()) <= value <= max(axis.get_view_interval())]
                                for key, axis in {'x': graph.plot_manager.ax.xaxis, 'y': graph.plot_manager.ax.yaxis}.items()},
                'axis_font_points': [graph.plot_manager.ax.xaxis.label.get_fontsize(), graph.plot_manager.ax.yaxis.label.get_fontsize()],
                'top_status': window.warning_label.text(), 'files': list(window.model.datasets),
                'observations': len(window.model.get_impact_comparison().get('observations', {}))}
        report['views'].append(view)
    for index, viewer in enumerate(window.playback_panel.widgets.values()):
        try:
            viewer.plotter.screenshot(str(output / f'{language}-vtk-buffer-{index}.png'))
        except Exception as error:
            report.setdefault('vtk_buffer_errors', []).append(str(error))
    window.close()
    window.deleteLater()
    app.processEvents()
(output / 'evidence.json').write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding='utf-8')
print(json.dumps({'stage': stage, 'views': len(report['views']), 'output': output.relative_to(ROOT).as_posix()}))
