import json
from pathlib import Path
from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest
from src.analysis.app.main_window import MainApp
from src.simulation.scene_review_fixtures import install_ui_fixture, public_raw
app=QApplication.instance() or QApplication([])
w=MainApp(); w.tab_widget.setCurrentIndex(0); c=w.original_widget
p=public_raw(Path('tmp/gui177/step1')); install_ui_fixture(c,p)
w.show(); QTest.qWait(300)
records=[]
for width,height in [(1510,800),(1100,720),(820,600)]:
 w.resize(width,height); QTest.qWait(200)
 w.grab().save(f'tmp/gui177/step1/before_{width}x{height}.png')
 records.append(dict(request=[width,height],actual=[w.width(),w.height()],font=w.font().toString(),dpr=w.devicePixelRatioF(),table=[c.scene_panel.table.x(),c.scene_panel.table.y(),c.scene_panel.table.width(),c.scene_panel.table.height()],source=str(p.resolve())))
Path('tmp/gui177/step1/before.json').write_text(json.dumps(records,indent=2),encoding='utf-8')
w.close()
