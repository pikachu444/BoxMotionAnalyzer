"""Actual PUB07 production widgets and profile bindings; native input is separate."""
import argparse
from datetime import datetime,timezone,timedelta
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import sys
from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest
from .ui.main_window import SimulationUI
from .mode_profiles import ModeProfiles
from .robot_validation import fixture
from src.utils.marker_profile_identity import envelope,digest


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',required=True)
    root=Path(parser.parse_args().output);root.mkdir(parents=True,exist_ok=False)
    app=QApplication.instance() or QApplication([]);dpr=app.primaryScreen().devicePixelRatio()
    window=SimulationUI();stamp=datetime.now(timezone.utc)
    paths=['src/simulation/ui/main_window.py','src/simulation/ui/mode_settings.py','src/simulation/ui/marker_export_dialog.py',
        'src/simulation/robot_ui_validation.py','tests/test_robot_sequence_gui.py']
    report=envelope('RunReport',run_id='pub07-ui-'+stamp.strftime('%Y%m%dT%H%M%SZ'),utc=stamp.isoformat(),
        kst=stamp.astimezone(timezone(timedelta(hours=9))).isoformat(),tier='actual-production-widget-render',
        command=[sys.executable,*sys.argv],code=dict(commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
            dirty=subprocess.check_output(['git','status','--porcelain','--untracked-files=no'],text=True).splitlines(),
            source_sha256={p:hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in paths}),
        environment=dict(platform=app.platformName(),process_scale=os.environ.get('QT_SCALE_FACTOR'),dpr=dpr),
        fresh=True,reused=False,native=dict(status='not_executed',reason='Widget render does not establish native input/viewer/OS125'),
        approval=dict(fixture='proposed',tolerance='proposed',baseline='no promotion',trial='not_evaluated'),
        experimental=dict(status='unavailable',reason='#104 separate'),states=[],completion='running')
    def capture(name,small=False):
        size=(820,600) if small else (math.ceil(1920/dpr),math.ceil(1080/dpr))
        window.resize(*size);window.show();QTest.qWait(70);window.resize(*size);app.processEvents()
        for control in (window.run_btn,window.batch_btn,window.marker_btn):
            assert control.visibleRegion().contains(control.rect()),'Primary actions clipped'
        fits=None
        if not small:
            rect=window.orientation_preview.rect();rect.moveTopLeft(window.orientation_preview.mapTo(window.right_scroll.viewport(),rect.topLeft()))
            fits=window.right_scroll.viewport().rect().contains(rect);assert fits,'Actual target preview clipped'
            assert window.settings.table.viewport().height()>=5*window.settings.table.rowHeight(0),'Five planned rows must fit'
        pixmap=window.grab();assert pixmap.save(str(root/(name+'.png')))
        config=window.profiles.configs[window.profiles.mode]
        report['states'].append(dict(name=name,pixels=[pixmap.width(),pixmap.height()],dpr=pixmap.devicePixelRatio(),
            target_fits=fits,configuration_hash=digest(config),mode=config['mode'],
            selected_step_ids=config['sequence_profile'].get('execution_plan',{}).get('selected_step_ids'),
            actual_preview=window.settings.sequence_preview.text(),preview_count=window.settings.preview_count.text(),
            preview_time=window.settings.preview_time.text(),actual_label=window.result_label.text(),status='passed'))
    try:
        capture('single-default');window.mode_combo.setCurrentIndex(1)
        window.settings.handling.setCurrentIndex(1);window.settings.preview_sequence()
        assert not window.run_btn.isEnabled() and 'Hazard' in window.settings.sequence_preview.text()
        capture('G-entire-unavailable')
        window.settings.run_scope.setCurrentIndex(1);window.settings.table.selectRow(7)
        window.settings.attachment_face.setCurrentText('+X');window.settings.preview_sequence()
        assert '+X face' in window.settings.sequence_preview.text();capture('G-selected-preview')
        details=window.settings.sequence_details_dialog();details.show();QTest.qWait(70)
        for index,name in enumerate(('G-details-drops','G-details-actions','G-details-conditions')):
            details.layout().itemAt(0).widget().setCurrentIndex(index);app.processEvents()
            assert details.grab().save(str(root/(name+'.png')))
            report['states'].append(dict(name=name,scope='Actual optional review dialog',status='passed'))
        details.close();details.deleteLater()
        window.settings.apply_settings();assert window.run_btn.isEnabled();capture('G-selected-applied')
        state=ModeProfiles();state.switch('robot_sequence');state.set_config(fixture(family='floor_supported',two=False))
        window._apply_profiles(state);window.settings.preview_sequence()
        assert 'Virtual tip on floor' in window.settings.sequence_preview.text();capture('H-supported-preview')
        capture('H-small-main',True);window._show_settings();app.processEvents();dialog=window.settings_dialog
        dialog.resize(820,600);QTest.qWait(70);dialog.resize(820,600);app.processEvents()
        scroll=dialog.layout().itemAt(0).widget();scroll.ensureWidgetVisible(window.settings.apply_button);app.processEvents()
        for control in (window.settings.apply_button,window.settings.cancel_button):assert control.visibleRegion().contains(control.rect())
        pixmap=dialog.grab();assert pixmap.save(str(root/'H-small-settings.png'))
        report['states'].append(dict(name='H-small-settings',pixels=[pixmap.width(),pixmap.height()],dpr=pixmap.devicePixelRatio(),
            scope='Actual scrolled Settings with Apply/Cancel reachable',status='passed'))
        dialog.reject()
        custom=fixture(family='floor_supported',two=False);custom['sequence_profile']['execution_plan']['physics']['radius_mm']=6.5
        state=ModeProfiles();state.switch('robot_sequence');state.set_config(custom)
        window._apply_profiles(state);window.settings.preview_sequence();details=window.settings.sequence_details_dialog()
        details.layout().itemAt(0).widget().setCurrentIndex(2);details.show();QTest.qWait(70)
        assert details.grab().save(str(root/'custom-grip-conditions.png'))
        report['states'].append(dict(name='custom-grip-conditions',scope='Actual loaded custom grip radius6.5mm',status='passed'))
        details.close();details.deleteLater();report['completion']='passed'
    except BaseException as error:report.update(completion='failed',failure=repr(error));raise
    finally:
        window.close();(root/'RunReport.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(status=report['completion'],states=len(report['states']),dpr=dpr)))


if __name__=='__main__':main()
