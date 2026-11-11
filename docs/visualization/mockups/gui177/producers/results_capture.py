import hashlib, json, os, subprocess, sys
from pathlib import Path
native = '--native' in sys.argv
if not native:
    os.environ['QT_QPA_PLATFORM'] = 'offscreen'
else:
    os.environ.pop('QT_QPA_PLATFORM', None)
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
import numpy as np
import pandas as pd
from PySide6.QtWidgets import QApplication, QFileDialog
from PySide6.QtGui import QFontInfo
from src.analysis.pipeline.data_loader import DataLoader
if sys.argv[1] == 'before':
    import types
    sections = types.ModuleType('src.utils.qt_sections')
    baseline_sections = subprocess.check_output(['git', 'show', 'HEAD:src/utils/qt_sections.py'], text=True, encoding='utf8')
    exec(compile(baseline_sections, 'baseline_sections', 'exec'), sections.__dict__)
    sys.modules['src.utils.qt_sections'] = sections
    module = types.ModuleType('baseline_results')
    baseline = subprocess.check_output(['git', 'show', 'HEAD:src/analysis/ui/widget_results_analyzer.py'], text=True, encoding='utf8')
    exec(compile(baseline, 'baseline_results', 'exec'), module.__dict__)
    WidgetResultsAnalyzer = module.WidgetResultsAnalyzer
else:
    from src.analysis.ui.widget_results_analyzer import WidgetResultsAnalyzer
from src.config.data_columns import HeaderL1, HeaderL2, HeaderL3, RESULT_TIME_COL

root = Path(__file__).parent
source = root / 'synthetic-result.proc'
beta = (HeaderL1.ANALYSIS, HeaderL2.DROP_POSTURE, HeaderL3.DROP_BETA_DEG)
frame = pd.DataFrame({RESULT_TIME_COL: np.arange(51)/100, beta: np.linspace(0, 20, 51)})
frame.columns = pd.MultiIndex.from_tuples(frame.columns)
frame.to_csv(source, index=False)
app = QApplication.instance() or QApplication([])
records = []
for lang in ('en', 'ko'):
    from src.utils import ui_language
    ui_language.preferred_language = lambda: lang
    ui_language.configure_language(app)
    for w, h in ((1510,800), (1100,720), (820,600)):
        widget = WidgetResultsAnalyzer(DataLoader())
        widget.resize(w,h)
        assert widget.load_result_file(str(source))
        widget._select_time_by_xdata(.2)
        # The display-only path is sanitized; data and loaded file identity remain unchanged.
        widget.result_folder_path_label.setText('tmp/gui177/results')
        widget.show(); app.processEvents()
        suffix = '-native' if native else ''
        widget.grab().save(str(root / f'{sys.argv[1]}-{lang}-{w}x{h}{suffix}.png'))
        rects = {}
        for name in ('canvas','toolbar','result_file_list','result_data_tree','experiment_summary_table', 'export_point_button'):
            obj = getattr(widget,name)
            p = obj.mapTo(widget, obj.rect().topLeft())
            rects[name] = [p.x(),p.y(),obj.width(),obj.height(),obj.isVisible()]
        axis = widget.plot_manager.ax.get_tightbbox(widget.canvas.get_renderer()).bounds
        record = {'lang':lang, 'requested':[w,h], 'actual':[widget.width(),widget.height()], 'font':widget.font().toString(), 'resolved_font':QFontInfo(widget.font()).family(), 'dpi':widget.logicalDpiX(), 'dpr':widget.devicePixelRatioF(), 'summary_rows':widget.experiment_summary_table.rowCount(), 'axis_tight_bbox':list(axis), 'rects':rects}
        if hasattr(widget, 'tool_tabs'):
            widget.tool_tabs.setCurrentIndex(1)
        else:
            widget.export_section.setExpanded(True)
        app.processEvents()
        widget.grab().save(str(root / f'{sys.argv[1]}-{lang}-{w}x{h}{suffix}-cae.png'))
        button = widget.export_scenario_button
        p = button.mapTo(widget, button.rect().topLeft())
        record['cae_button'] = [p.x(), p.y(), button.width(), button.height(), button.isVisible()]
        record['cae_tab_selected'] = hasattr(widget, 'tool_tabs') and widget.tool_tabs.currentIndex() == 1
        record['cae_button_fully_in_page'] = widget.rect().contains(p) and widget.rect().contains(button.mapTo(widget, button.rect().bottomRight())) and button.isVisible()
        records.append(record)
        if lang == 'en' and w == 1510:
            widget.offset_manual_checkbox.setChecked(True)
            widget.manual_height_checkbox.setChecked(True)
            for field, value in zip(widget.manual_height_inputs, ('1.25', '2.5', '3.75')):
                field.setText(value)
            widget.le_scene_name.setText('synthetic')
            destination = root / f'{sys.argv[1]}-scenario.csv'
            old_dialog = QFileDialog.getSaveFileName
            QFileDialog.getSaveFileName = lambda *_: (str(destination), '')
            try:
                widget.export_analysis_scenario()
            finally:
                QFileDialog.getSaveFileName = old_dialog
        widget.close(); widget.deleteLater(); app.processEvents()
metadata={'kind':'generated linear beta, 51 samples, seed: none; displayed folder redacted to repository-relative path', 'sha256':hashlib.sha256(source.read_bytes()).hexdigest(), 'scenario_sha256':hashlib.sha256((root / f'{sys.argv[1]}-scenario.csv').read_bytes()).hexdigest(), 'source_revision':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(), 'records':records}
(root / f'{sys.argv[1]}{suffix}.json').write_text(json.dumps(metadata,indent=2),encoding='utf8')
