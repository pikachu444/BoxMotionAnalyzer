"""Independent product Qt rendering/input review for issue 188.

Last Reviewed: 2026-11-12
No solver or optimizer is run. Generated fixtures are not experimental truth.
"""
import hashlib
import json
import os
from pathlib import Path
import sys

os.environ.setdefault('QT_QPA_PLATFORM', 'windows')
ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'tests')]

import numpy as np
import pandas as pd
from PySide6.QtCore import Qt, qVersion
from PySide6.QtGui import QRegion
from PySide6.QtTest import QTest
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QApplication, QDialogButtonBox, QFormLayout, QPushButton, QScrollArea, QLabel
from src.analysis.pipeline.artifact_io import save_slice_file
from src.analysis.pipeline.data_loader import DataLoader
from src.analysis.pipeline.parser import Parser
from src.analysis.ui.widget_slice_processing import WidgetSliceProcessing
from src.analysis.ui.widget_results_analyzer import WidgetResultsAnalyzer
from src.analysis.ui.shared_metric_guide import SharedMetricGuideDialog, GuideDiagram
from src.analysis.ui.dialog_metric_guide import DropPostureMetricGuideDialog
from src.analysis.compare.metric_guide import MetricGuideDialog
from src.analysis.compare.main_window import CompareMainWindow
from src.config.data_columns import FACE_PREFIX_TO_INFO
from src.config.result_metric_descriptors import get_drop_posture_summary_descriptors
from src.simulation.corruption_export import write_observations
from src.simulation.marker_fixtures import example_profile
from src.utils import ui_language
from test_gui_metric_parity_contract import metric_frame

OUT = ROOT / 'docs/visualization/gui_metric_parity/ui_evidence'
INPUTS = OUT / 'product_inputs'
INPUTS.mkdir(parents=True, exist_ok=True)
RECORDS, CHECKS, FINDINGS = [], [], []


def settle(app):
    for _ in range(6):
        app.processEvents()
    QTest.qWait(10)


def full(widget):
    return widget.isVisible() and QRegion(widget.rect()).subtracted(widget.visibleRegion()).isEmpty()


def check(name, condition, **details):
    record = dict(name=name, result='pass' if condition else 'fail', **details)
    CHECKS.append(record)
    if not condition:
        FINDINGS.append(record)
    return condition


def capture(app, widget, name, size):
    widget.resize(*size)
    widget.show()
    settle(app)
    path = OUT / (name + '.png')
    widget.grab().save(str(path))
    actual = [widget.width(), widget.height()]
    record = dict(name=name, requested_client=list(size), actual_client=actual,
                  font=widget.font().toString(), device_pixel_ratio=widget.devicePixelRatioF(),
                  path=path.relative_to(ROOT).as_posix())
    if isinstance(widget, WidgetSliceProcessing):
        record.update(settings_viewport=[widget.settings_scroll.viewport().width(),widget.settings_scroll.viewport().height()],
                      card_columns=widget.card_columns, top_height=widget.context_splitter.height(),
                      right_width=widget.context_group.width(), log_height=widget.log_group.height(),
                      footer_height=widget.action_stack.height(),
                      horizontal_scroll_max=widget.settings_scroll.horizontalScrollBar().maximum())
    if isinstance(widget, SharedMetricGuideDialog):
        record.update(content_width=widget.scroll.viewport().width(), columns=widget._columns,
                      focused_metric=widget.focused_metric, entries=len(widget.cards))
    RECORDS.append(record)
    check(name + ': exact client', actual == list(size), actual=actual, requested=list(size))
    return record


def dispose(app, widget):
    if isinstance(widget, WidgetResultsAnalyzer):
        widget.close_all_popups()
    if isinstance(widget, CompareMainWindow):
        widget.playback_panel.stop()
        for viewer in list(widget.playback_panel.widgets.values()):
            viewer.cleanup()
    widget.close()
    widget.deleteLater()
    settle(app)


def make_inputs():
    t = np.arange(21) * .02
    truth = dict(schema_version=1, source_kind='handcrafted_dummy',
                 coordinate_policy='world-y-up-box-local-fixed-center-v1', time_s=t,
                 body_origin_mm=np.column_stack([10 + 200*t, np.full(len(t),1000.), t*0]),
                 rotation_matrix=np.repeat(np.eye(3)[None],len(t),axis=0), frame=np.arange(len(t)))
    observations = INPUTS / 'analytic_observations'
    if not (observations / 'observed.csv').exists():
        write_observations(observations, truth, example_profile(), dict(schema_version=1,events=[]))
    raw_path = observations / 'observed.csv'
    header, raw = DataLoader().load_csv(str(raw_path))
    slice_path = INPUTS / 'product_generated_affine_motion_0p1_to_0p3.slice'
    save_slice_file(filepath=str(slice_path),header_info=header,raw_data=raw,source_path=str(raw_path),
                    full_start=0.,full_end=.4,user_start=.1,user_end=.3,
                    box_dims=(200.,120.,80.),pad_rows=0)
    result_path = INPUTS / 'product_generated_registered_contact_A.proc'
    frame = metric_frame()
    # Literal geometry expectation for the identity fixture; no producer is used
    # to invent a graph series or an independent numerical oracle.
    frame[('Analysis','DropPosture','BetaDeg')] = 0.
    frame.to_csv(result_path,index=False)
    copied = INPUTS / 'product_generated_registered_contact_A_copy.proc'
    copied.write_bytes(result_path.read_bytes())
    return slice_path,result_path,copied


def review_processing(app, lang, size, slice_path):
    page = WidgetSliceProcessing(DataLoader(),Parser(FACE_PREFIX_TO_INFO))
    check(f'{lang} processing slice load {size}',page.load_slice_file(str(slice_path)))
    initial=capture(app,page,f'product-process-{lang}-{size[0]}x{size[1]}',size)
    target=430 if size[0]>=1300 else 345 if size[0]>=950 else 265
    log_target=104 if size[0]>=1300 else 90 if size[0]>=950 else 80
    check(f'{lang} responsive initial top target {size}',abs(initial['top_height']-target)<=3,
          actual=initial['top_height'],target=target)
    check(f'{lang} responsive initial Log target {size}',initial['log_height']==log_target,
          actual=initial['log_height'],target=log_target)
    expected = 5 if page.settings_scroll.viewport().width() >= 1300 else 3 if page.settings_scroll.viewport().width() >= 950 else 2
    check(f'{lang} processing card columns {size}',page.card_columns==expected,
          columns=page.card_columns, expected=expected)
    check(f'{lang} processing fixed footer {size}',all(full(w) for w in (page.run_button,page.save_proc_button,page.save_view_button)))
    check(f'{lang} processing no horizontal settings scroll {size}',page.settings_scroll.horizontalScrollBar().maximum()==0)
    page.rb_processing_advanced.setChecked(True)
    page.settings_scroll.ensureWidgetVisible(page.processing_settings_button)
    settle(app)
    check(f'{lang} processing Advanced settings reachable {size}',full(page.processing_settings_button))
    page.rb_processing_raw.setChecked(True)
    page.cb_enable_resampling.setChecked(True)
    page.cb_limit_resampling_range.setChecked(True)
    page.settings_scroll.ensureWidgetVisible(page.le_resampling_range_end)
    settle(app)
    check(f'{lang} processing range field reachable {size}',full(page.le_resampling_range_end))
    selected = page.workflow_splitter.sizes()
    page.workflow_splitter.setSizes([max(190,selected[0]-20),selected[1]+20])
    chosen=page.workflow_splitter.sizes()
    page.input_mode_combo.setCurrentIndex(1)
    check(f'{lang} batch disables plot controls {size}',not page.plot_options.isEnabled())
    capture(app,page,f'product-process-batch-{lang}-{size[0]}x{size[1]}',size)
    page.input_mode_combo.setCurrentIndex(0)
    settle(app)
    check(f'{lang} mode switch preserves splitter {size}',page.workflow_splitter.sizes()==chosen)
    page.resize(size[0],size[1]+40)
    settle(app)
    page.resize(*size)
    settle(app)
    restored=page.workflow_splitter.sizes()
    check(f'{lang} real resize roundtrip preserves user splitter {size}',
          all(abs(a-b)<=2 for a,b in zip(chosen,restored)),before=chosen,after=restored)
    page.hide()
    page.show()
    settle(app)
    check(f'{lang} hide/show does not reseed splitter {size}',page.workflow_splitter.sizes()==restored)
    page._set_batch_controls_enabled(False)
    check(f'{lang} moved controls remain locked {size}',all(not w.isEnabled() for w in
        (page.input_mode_combo,page.select_data_button,page.rb_processing_raw,page.overwrite_proc_checkbox)))
    page._set_batch_controls_enabled(True)
    dispose(app,page)


def review_results(app,lang,size,path):
    page = WidgetResultsAnalyzer(DataLoader())
    check(f'{lang} result saved proc load {size}',page.load_result_file(str(path)))
    page.tool_tabs.setCurrentIndex(1)
    capture(app,page,f'product-results-{lang}-{size[0]}x{size[1]}',size)
    check(f'{lang} result export footer reachable {size}',full(page.export_scenario_button))
    check(f'{lang} result default velocity option OFF {size}',not page.use_selected_velocities_checkbox.isChecked()
          and not page.use_selected_velocities_checkbox.isEnabled())
    page.offset_manual_checkbox.setChecked(True)
    page.manual_height_checkbox.setChecked(True)
    page._select_time_by_xdata(.072)
    page._update_scenario_origin()
    check(f'{lang} option enabled in manual height {size}',page.use_selected_velocities_checkbox.isEnabled())
    page.use_selected_velocities_checkbox.setChecked(True)
    if size==(820,600):
        capture(app,page,f'product-results-selected-{lang}',size)
    page.manual_height_checkbox.setChecked(False)
    check(f'{lang} option reset when leaving manual height {size}',not page.use_selected_velocities_checkbox.isEnabled()
          and not page.use_selected_velocities_checkbox.isChecked())
    check(f'{lang} core target row retained {size}','TargetPostureError_deg' in page.resolved_summary)
    if lang=='en' and size==(820,600):
        axis=page.plot_manager.ax
        axis.xaxis.label.set_fontsize(13)
        axis.yaxis.label.set_fontsize(14)
        page.toolbar.edit_parameters()
        settle(app)
        dialog=page.toolbar._fedit_dialog
        check('Actual Matplotlib Customize dialog opened',dialog.isVisible())
        title=None
        for form in dialog.findChildren(QFormLayout):
            for row in range(form.rowCount()):
                label=form.itemAt(row,QFormLayout.LabelRole)
                field=form.itemAt(row,QFormLayout.FieldRole)
                if label and label.widget() and label.widget().text()=='Title' and field:
                    title=field.widget()
        if title is None:
            raise RuntimeError('Installed Customize Title field is unavailable')
        title.setText('Public widget review')
        QTest.mouseClick(dialog.bbox.button(QDialogButtonBox.Apply),Qt.LeftButton)
        settle(app)
        check('Actual Customize Apply executed',axis.get_title()=='Public widget review')
        capture(app,dialog,'product-customize-dialog',(dialog.width(),dialog.height()))
        QTest.mouseClick(dialog.bbox.button(QDialogButtonBox.Ok),Qt.LeftButton)
        page._draw_result_columns([('Position','CoM','P_TY')])
        settle(app)
        check('Text font choices survive actual Customize Apply and redraw',
              (axis.xaxis.label.get_fontsize(),axis.yaxis.label.get_fontsize())==(13,14),
              limitation='Installed Customize does not expose axis-label font size; 13/14 were set on actual Text objects before opening it.')
    dispose(app,page)


def review_guide(app,lang):
    guide = MetricGuideDialog()
    check(f'{lang} compare wrapper shared renderer',isinstance(guide,SharedMetricGuideDialog))
    step = DropPostureMetricGuideDialog(get_drop_posture_summary_descriptors())
    check(f'{lang} Step2 wrapper shared renderer',isinstance(step,SharedMetricGuideDialog))
    dispose(app,step)
    guide.focus_metric('step2:summary:BetaAtT1MinusDeg')
    for size in ((1100,760),(640,480)):
        capture(app,guide,f'product-guide-{lang}-{size[0]}x{size[1]}',size)
        guide.scroll.verticalScrollBar().setValue(0)
        settle(app)
        capture(app,guide,f'product-guide-diagram-{lang}-{size[0]}x{size[1]}',size)
    thresholds=[]
    for target in (999,1000,1001):
        guide.resize(target+44,760)
        settle(app)
        guide.resize(guide.width()+target-guide.scroll.viewport().width(),760)
        settle(app)
        thresholds.append(dict(content_width=guide.scroll.viewport().width(),columns=guide._columns))
    check(f'{lang} Guide actual width thresholds',thresholds==[
        dict(content_width=999,columns=1),dict(content_width=1000,columns=2),dict(content_width=1001,columns=2)],cases=thresholds)
    guide.resize(640,480)
    guide.search.setText('hidden-target')
    guide.classification.setCurrentIndex(3)
    target='step2:summary:TargetPostureError_deg'
    guide.focus_metric(target)
    settle(app)
    check(f'{lang} hidden target revealed',guide.focused_metric==target and guide.cards[target].hasFocus()
          and guide.search.text()=='' and guide.classification.currentIndex()==0)
    guide.search.setFocus()
    seen=[]
    outside=[]
    close=guide.buttons.button(QDialogButtonBox.Close)
    close_reached=False
    for _ in range(len(guide.cards)+20):
        focused=app.focusWidget()
        QTest.keyClick(focused or guide,Qt.Key_Tab)
        settle(app)
        focused=app.focusWidget()
        key=focused.property('metric_id') if focused else None
        if key and key not in seen:
            seen.append(key)
            top=focused.mapTo(guide.scroll.viewport(),focused.rect().topLeft()).y()
            if top < 0 or top >= guide.scroll.viewport().height():
                outside.append(dict(key=key,heading_y=top))
        close_reached |= focused is close
    check(f'{lang} all Guide entries keyboard reachable',set(seen)==set(guide.cards),visited=len(seen),expected=len(guide.cards))
    check(f'{lang} Guide keyboard headings scroll into view',not outside,outside=outside)
    check(f'{lang} Guide fixed Close keyboard reachable',close_reached)
    check(f'{lang} Guide content fits viewport after threshold reflows',
          guide.content.width()<=guide.scroll.viewport().width()
          and guide.scroll.horizontalScrollBar().maximum()==0,
          viewport=guide.scroll.viewport().width(),content=guide.content.width(),
          horizontal_scroll_max=guide.scroll.horizontalScrollBar().maximum())
    guide.focus_metric('step2:summary:TargetPostureError_deg')
    settle(app)
    QTest.keyClick(guide.cards[target],Qt.Key_Tab)
    settle(app)
    capture(app,guide,f'product-guide-keyboard-{lang}',(640,480))
    guide.search.setText('no metric has this phrase')
    settle(app)
    check(f'{lang} Guide empty filter message',guide.empty_label.isVisible())
    guide.focus_metric('unknown-owner-key')
    check(f'{lang} unknown target Interpretation top',guide.tabs.currentIndex()==1 and guide.reading.verticalScrollBar().value()==0)
    QTest.keyClick(guide,Qt.Key_Escape)
    check(f'{lang} Guide Escape hides',not guide.isVisible())
    guide.show()
    guide.focus_metric('compare:vertical_velocity')
    settle(app)
    check(f'{lang} Guide same instance reopen context',guide.isVisible() and guide.focused_metric=='compare:vertical_velocity')
    missing=GuideDiagram('Missing')
    check(f'{lang} missing diagram text alternative',missing.original.isNull() and bool(missing.text()))
    missing.deleteLater()
    review_diagrams(app,guide,lang)
    dispose(app,guide)


def review_diagrams(app,guide,lang):
    for size in ((640,480),(1100,760)):
        guide.resize(*size)
        guide.show()
        guide.focus_metric('step2:summary:BetaAtT1MinusDeg')
        settle(app)
        for group in ('Posture','Impact','Contact'):
            button=next(w for w in guide.groups[group].findChildren(QPushButton)
                        if w.text()==ui_language.tr('View diagram'))
            guide.raise_()
            guide.activateWindow()
            guide.search.setFocus()
            reached=False
            for _ in range(len(guide.cards)+20):
                QTest.keyClick(app.focusWidget() or guide,Qt.Key_Tab)
                settle(app)
                if app.focusWidget() is button:
                    reached=True
                    break
            check(f'{lang} {group} diagram button Tab reachable {size}',reached and full(button))
            QTest.keyClick(button,Qt.Key_Space)
            settle(app)
            dialog=guide.diagram_windows[group]
            check(f'{lang} {group} diagram keyboard opens owned window {size}',dialog.isVisible()
                  and dialog.parentWidget() is guide)
            scroll=dialog.findChild(QScrollArea)
            label=scroll.widget()
            original=QPixmap(str(ROOT/'src/analysis/ui/assets'/('guide_'+group.lower()+'.png')))
            check(f'{lang} {group} full original pixels/aspect {size}',label.pixmap().size()==original.size(),
                  original_pixels=[original.width(),original.height()],display_pixels=[label.pixmap().width(),label.pixmap().height()])
            capture(app,dialog,f'product-diagram-{group.lower()}-{lang}-{size[0]}x{size[1]}',size)
            close=dialog.findChild(QDialogButtonBox).button(QDialogButtonBox.Close)
            check(f'{lang} {group} diagram fixed Close fully visible {size}',full(close))
            for bar,key in ((scroll.horizontalScrollBar(),Qt.Key_Right),(scroll.verticalScrollBar(),Qt.Key_Down)):
                scroll.setFocus()
                for _ in range(bar.maximum()//max(1,bar.singleStep())+2):
                    QTest.keyClick(scroll,key)
                    app.processEvents()
                check(f'{lang} {group} full image keyboard reaches {key.name} edge {size}',bar.value()==bar.maximum())
            if group=='Posture' and size==(640,480):
                capture(app,dialog,f'product-diagram-posture-panned-{lang}',size)
            scroll.setFocus()
            QTest.keyClick(scroll,Qt.Key_Tab)
            settle(app)
            check(f'{lang} {group} diagram Close keyboard reachable {size}',app.focusWidget() is close)
            QTest.keyClick(close,Qt.Key_Space)
            settle(app)
            check(f'{lang} {group} diagram Close hides {size}',not dialog.isVisible())
            guide._open_diagram(group)
            settle(app)
            check(f'{lang} {group} diagram same object reopens {size}',guide.diagram_windows[group] is dialog
                  and dialog.isVisible())
            QTest.keyClick(dialog,Qt.Key_Escape)
            settle(app)
            check(f'{lang} {group} diagram Escape hides {size}',not dialog.isVisible())
    guide._open_diagram('Missing')
    settle(app)
    missing=guide.diagram_windows['Missing']
    label=missing.findChild(QScrollArea).widget()
    check(f'{lang} full-size missing image has text alternative',bool(label.text()) and label.pixmap().isNull())
    missing.hide()


def review_comparison(app,lang,paths):
    window=CompareMainWindow()
    window.load_result_files([str(p) for p in paths])
    window.table_panel.table.setCurrentCell(0,1)
    window.control_panel.file_list.setCurrentRow(0)
    capture(app,window,f'product-compare-{lang}-1100x720',(1100,720))
    for i,viewer in enumerate(window.playback_panel.widgets.values()):
        viewer.update_view(0)
        actor=viewer.actors.get('box')
        check(f'{lang} actual VTK box actor {i}',actor is not None and actor.GetVisibility(),
              bounds=list(actor.GetBounds()) if actor is not None else None)
        if actor is not None:
            viewer.plotter.reset_camera(bounds=actor.GetBounds())
        else:
            viewer.reset_camera_view()
        viewer.plotter.render()
        settle(app)
        render=viewer.plotter.screenshot(str(OUT/f'product-vtk-render-{lang}-{i}.png'),return_img=True)
        check(f'{lang} actual VTK rendered scene {i}',float(np.std(render))>0,
              pixel_shape=list(render.shape),pixel_std=float(np.std(render)),
              camera_scope='Display camera fitted to loaded box actor; no geometry or calculation change')
    native=window.screen().grabWindow(window.winId())
    native.save(str(OUT/f'product-compare-native-{lang}.png'))
    panel=window.control_panel
    text=panel.details.toPlainText()
    check(f'{lang} diagnostics initially closed',panel.diagnostics_dialog is None)
    check(f'{lang} basic details omit raw provenance','sha256' not in text.casefold() and str(ROOT) not in text
          and 'ProcessingSettingsJson' not in text)
    check(f'{lang} synthetic label explicit',('Synthetic validation data' if lang=='en' else '가상 검증 데이터') in text)
    check(f'{lang} actual 3D viewers created',bool(window.playback_panel.widgets),viewers=len(window.playback_panel.widgets))
    check(f'{lang} supported comparison graph populated',window.graph_panel.cb_plot_target.count()>0
          and bool(window.graph_panel.plot_manager.ax.lines),targets=window.graph_panel.cb_plot_target.count())
    window.control_panel.cb_view.setCurrentIndex(1)
    settle(app)
    window.playback_panel.master_slider.setValue(min(5,window.playback_panel.master_slider.maximum()))
    settle(app)
    capture(app,window,f'product-compare-aligned-{lang}-820x600',(820,600))
    panel._open_diagnostics()
    capture(app,panel.diagnostics_dialog,f'product-diagnostics-{lang}',(800,600))
    check(f'{lang} diagnostics keep raw evidence',str(ROOT) in panel.diagnostics_text.toPlainText())
    panel.diagnostics_dialog.hide()
    dispose(app,window)


def main():
    app=QApplication.instance() or QApplication([])
    slice_path,result_path,copied=make_inputs()
    for lang in ('en','ko'):
        ui_language.preferred_language=lambda value=lang:value
        ui_language.configure_language(app)
        for size in ((1510,800),(1100,720),(820,600)):
            review_processing(app,lang,size,slice_path)
            review_results(app,lang,size,result_path)
        review_guide(app,lang)
        review_comparison(app,lang,(result_path,copied))
    sources=('src/analysis/ui/widget_slice_processing.py','src/analysis/ui/widget_results_analyzer.py',
             'src/analysis/ui/shared_metric_guide.py','src/analysis/compare/ui_panels.py')
    result=dict(platform=app.platformName(),qt=qVersion(),scope='Native-platform Qt render buffers and QTest/widget input; no native desktop input, OS125 or human approval',
        source_hashes={s:hashlib.sha256((ROOT/s).read_bytes()).hexdigest() for s in sources},captures=RECORDS,
        checks=CHECKS,findings=FINDINGS)
    (OUT/'product_checks.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(captures=len(RECORDS),checks=len(CHECKS),failures=FINDINGS),ensure_ascii=False))


if __name__=='__main__':
    main()
