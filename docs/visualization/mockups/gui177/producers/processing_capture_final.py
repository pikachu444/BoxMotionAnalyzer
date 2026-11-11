import hashlib, importlib.util, json, subprocess, sys
from pathlib import Path
sys.path[:0]=[str(Path.cwd()),str(Path.cwd()/'tests')]
from PySide6.QtWidgets import QApplication,QPushButton
from PySide6.QtCore import QPoint
from PySide6.QtGui import QFontInfo
from src.analysis.pipeline.data_loader import DataLoader
from src.analysis.pipeline.parser import Parser
from src.analysis.ui.widget_slice_processing import WidgetSliceProcessing
from src.config.data_columns import FACE_PREFIX_TO_INFO
from src.utils import ui_language
from src.utils.app_identity import configure_qt_application
phase, language=sys.argv[1:3]
out=Path('tmp/gui177/processing')
source_path=Path('src/analysis/ui/widget_slice_processing.py')
source_bytes=source_path.read_bytes()
if phase.startswith('before'):
 import src.utils.qt_sections as sections
 for module_name,filename in [('baseline_sections','baseline_sections.py'),('baseline_processing','baseline_processing.py')]:
  spec=importlib.util.spec_from_file_location(module_name,out/filename)
  module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
  if module_name=='baseline_sections':sections.CollapsibleSection=module.CollapsibleSection
  else:WidgetSliceProcessing=module.WidgetSliceProcessing
 source_bytes=subprocess.check_output(['git','show','HEAD:src/analysis/ui/widget_slice_processing.py'])
app=QApplication([])
ui_language.preferred_language=lambda:language
configure_qt_application(app)
p=out/'public_generated_processing.slice'
w=WidgetSliceProcessing(DataLoader(),Parser(FACE_PREFIX_TO_INFO));assert w.load_slice_file(str(p))
w.show();app.processEvents()
for size in ((1510,800),(1100,720),(820,600)):
 w.resize(*size);app.processEvents();w.canvas.draw();app.processEvents()
 name=f'{phase}_{language}_{size[0]}x{size[1]}'
 assert w.grab().save(str(out/(name+'.png')))
 data={'producer':f'.venv/Scripts/python.exe tmp/gui177/processing/capture_final.py {phase} {language}',
       'source_revision':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
       'source_sha256':hashlib.sha256(source_bytes).hexdigest(),'source_path':source_path.as_posix(),
       'client':[w.width(),w.height()],'app_font':app.font().toString(),'actual_font_family':QFontInfo(w.font()).family(),
       'widget_font':w.font().toString(),'platform':app.platformName(),'language':language,
       'language_initialization':'configure_qt_application -> configure_language; fixture preference substitution; separate process per language; no saved preference or OS changes',
       'logical_dpi':w.logicalDpiX(),'DPR':w.devicePixelRatioF(),'input':p.as_posix(),
       'input_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),
       'source_kind':'generated _raw_bundle, 6 rows, four markers, no physical accuracy claim','rows':len(w.parsed_data),
       'buttons':{b.objectName() or b.text():[b.mapTo(w,QPoint()).x(),b.mapTo(w,QPoint()).y(),b.width(),b.height()] for b in w.findChildren(QPushButton)},
       'canvas':[w.canvas.width(),w.canvas.height()],'axes_bbox':list(w.plot_manager.ax.get_window_extent().bounds),
       'axis_title_pt':[w.plot_manager.ax.xaxis.label.get_fontsize(),w.plot_manager.ax.yaxis.label.get_fontsize()],
       'tick_pt':[t.get_fontsize() for t in w.plot_manager.ax.get_xticklabels()],
       'scope':'Native Windows QWidget.grab; no desktop occlusion, human approval, OS125, or physical validation claim'}
 (out/(name+'.json')).write_text(json.dumps(data,indent=2),encoding='utf-8')
w.close();w.deleteLater();app.processEvents()
