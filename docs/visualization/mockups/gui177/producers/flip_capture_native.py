import sys,json,hashlib,subprocess,importlib.util
from pathlib import Path
sys.path[:0]=['.','tests']
from PySide6.QtWidgets import QApplication,QDialogButtonBox
from PySide6.QtGui import QFontInfo,QRegion
from PySide6.QtCore import QPoint
import test_marker_review_layout as fixture
from src.analysis.ui.dialog_marker_flip_review import MarkerFlipReviewDialog
app=QApplication.instance() or QApplication([])
out=Path('tmp/gui177/flip')
base=subprocess.check_output(['git','show','HEAD:src/analysis/ui/dialog_marker_flip_review.py'])
import src.utils.qt_sections as sections
baseline_sections={}
exec(compile(subprocess.check_output(['git','show','HEAD:src/utils/qt_sections.py']), 'baseline_sections', 'exec'), baseline_sections)
sections.CollapsibleSection=baseline_sections['CollapsibleSection']
(out/'baseline_dialog.py').write_bytes(base)
spec=importlib.util.spec_from_file_location('baseline_dialog',out/'baseline_dialog.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
records=[]
for stage,cls in [('before-native',module.MarkerFlipReviewDialog),('after-native',MarkerFlipReviewDialog)]:
 for language in ['en','ko']:
  if language == 'ko':
   from matplotlib import rcParams
   rcParams['font.sans-serif'] = ['Malgun Gothic', 'Noto Sans CJK KR', 'NanumGothic', 'Apple SD Gothic Neo', *rcParams['font.sans-serif']]
   rcParams['axes.unicode_minus'] = False
  app.setProperty('interfaceLanguage',language)
  fixture.MarkerFlipReviewDialog=cls
  for size in [(1280,740),(820,600)]:
   d,data=fixture.layout_fixture(6);d.resize(*size);d.show();fixture.settle(app,d)
   def bbox(w):
    p=w.mapTo(d,QPoint());return [p.x(),p.y(),w.width(),w.height()]
   def fully(w,r):return w.isVisible() and not r.isEmpty() and QRegion(r).subtracted(w.visibleRegion()).isEmpty()
   record={'stage':stage,'language':language,'requested':size,'actual':[d.width(),d.height()],'application_font':app.font().toString(),'actual_font_family':QFontInfo(d.font()).family(),'actual_point_size':QFontInfo(d.font()).pointSizeF(),'DPR':d.devicePixelRatioF(),'logical_DPI':d.logicalDpiX(),'platform':app.platformName(),'capture_kind':'QWidget.grab; no desktop occlusion inspection','fixture':'test_marker_review_layout.layout_fixture(6)','data_sha256':hashlib.sha256(data.to_csv().encode()).hexdigest(),'source_revision':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),'source_sha256':hashlib.sha256(base if stage.startswith('before') else Path('src/analysis/ui/dialog_marker_flip_review.py').read_bytes()).hexdigest(),'events':[c.event_id for c in d.candidates],'approval':[w.isChecked() for w in d._approval_checkboxes],'axes':[w.currentData() for w in d._axis_combos],'checkbox_object_ids':[id(w) for w in d._approval_checkboxes],'combo_object_ids':[id(w) for w in d._axis_combos],'visible_rows':sum(fully(d.table.viewport(),d.table.visualItemRect(d.table.item(r,0))) for r in range(6)),'bbox':{name:bbox(w) for name,w in [('table',d.table),('original',d.context_canvas),('preview',d.evidence_canvas),('done',d.button_box.button(QDialogButtonBox.Ok)),('cancel',d.button_box.button(QDialogButtonBox.Cancel))]},'plot_axes_bbox':[list(c.figure.axes[0].get_window_extent().bounds) for c in (d.context_canvas,d.evidence_canvas)]}
   d.grab().save(str(out/f'{stage}-{language}-{size[0]}x{size[1]}.png'));records.append(record)
   if stage.startswith('after'):
    d._show_evidence();app.processEvents();d.evidence_dialog.grab().save(str(out/f'evidence-{language}-{size[0]}.png'))
   d.close();d.deleteLater();app.processEvents()
(out/'native-captures.json').write_text(json.dumps(records,indent=2),encoding='utf-8')
