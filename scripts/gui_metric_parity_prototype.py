"""Actual Qt widget layout prototype for issue 188. No production mutations.

Last Reviewed: 2026-11-12
Run from the checkout with its declared PySide6/Matplotlib dependencies.
"""
import hashlib
import json
import os
from pathlib import Path
import sys

os.environ.setdefault('QT_QPA_PLATFORM', 'windows')
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import numpy as np
import pandas as pd
from PySide6.QtCore import Qt, QTimer, qVersion
from PySide6.QtGui import QRegion
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QDialog, QDialogButtonBox, QGridLayout,
    QGroupBox, QHBoxLayout, QLabel, QLineEdit, QScrollArea, QTabWidget,
    QTextBrowser, QVBoxLayout, QWidget,
)
from src.analysis.pipeline.data_loader import DataLoader
from src.analysis.pipeline.parser import Parser
from src.analysis.ui.widget_slice_processing import WidgetSliceProcessing
from src.analysis.ui.widget_results_analyzer import WidgetResultsAnalyzer
from src.config.data_columns import FACE_PREFIX_TO_INFO
from src.config.result_metric_descriptors import get_metric_registry
from src.utils import ui_language

OUT = ROOT / 'docs/visualization/gui_metric_parity/ui_evidence/prototype_replay'
OUT.mkdir(parents=True, exist_ok=True)


def text(en, ko):
    return ko if ui_language.active_language() == 'ko' else en


def card(title):
    group = QGroupBox(title)
    layout = QVBoxLayout(group)
    layout.setContentsMargins(7, 7, 7, 7)
    layout.setSpacing(6)
    return group, layout


class ProcessingPrototype(WidgetSliceProcessing):
    def _arrange_workflow(self):
        super()._arrange_workflow()
        if hasattr(self, 'setting_cards'):
            # Current product already owns the accepted composition. Historical
            # captures remain unchanged; replay never creates duplicate cards.
            self._prototype_reuses_product_layout = True
            return
        self.log_group.setParent(self.context_group)
        self.context_group.layout().addWidget(self.log_group)
        self.log_output.setMinimumSize(20, 40)
        self.log_group.setMinimumHeight(72)
        self.log_group.setMaximumHeight(104)
        self.log_output.setPlainText(text('Ready. No processing has been run.', '준비됨. 처리는 실행하지 않았습니다.'))
        self.plot_options, plot_layout = card(text('Plot Options', '그래프 옵션'))
        for widget in (self.select_data_button, self.combo_plot_axis, self.selected_data_label):
            plot_layout.addWidget(widget)
        plot_layout.addStretch()
        method_layout = self.method_controls.layout()
        radios = QHBoxLayout()
        self.rb_processing_standard.setText(text('Smoothing', '스무딩'))
        for widget in (self.rb_processing_raw, self.rb_processing_standard, self.rb_processing_advanced):
            method_layout.removeWidget(widget)
            radios.addWidget(widget)
        method_layout.insertLayout(0, radios)
        self.method_controls.setTitle(text('Processing Mode', '처리 방식'))
        self.output_group, output = card(text('Output', '출력'))
        for source in (self.result_status_label, self.proc_path_label):
            duplicate = QLabel(source.text())
            duplicate.setWordWrap(True)
            output.addWidget(duplicate)
        output.addStretch()
        self.batch_group, batch = card(text('Batch', '배치'))
        self.batch_hint = QLabel(text('Choose Batch above to process a folder.', '위에서 배치를 선택해 폴더를 처리합니다.'))
        self.batch_hint.setWordWrap(True)
        batch.addWidget(self.batch_hint)
        batch.addWidget(self.overwrite_proc_checkbox)
        self.overwrite_proc_checkbox.setEnabled(False)
        batch.addStretch()
        old = self.settings_scroll.takeWidget()
        self.settings_content = QWidget()
        self.settings_grid = QGridLayout(self.settings_content)
        self.settings_grid.setContentsMargins(6, 6, 6, 6)
        self.settings_grid.setSpacing(6)
        self.setting_cards = [self.plot_options, self.resampling_group, self.method_controls,
                              self.output_group, self.batch_group]
        for widget in self.setting_cards:
            widget.setParent(self.settings_content)
        old.deleteLater()
        self.settings_scroll.setWidget(self.settings_content)
        self.settings_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        for group, minimum in zip(self.setting_cards, (170,185,253,180,185)):
            group.setMinimumWidth(minimum)
        self.action_stack.setMinimumHeight(48)
        self.context_group.setMinimumWidth(260)
        self.context_splitter.setSizes([1100, 330])
        self._reflow()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        QTimer.singleShot(0, self._reflow)

    def _reflow(self):
        if not hasattr(self, 'settings_grid'):
            return
        width = self.settings_scroll.viewport().width()
        count = 5 if width >= 1300 else 3 if width >= 950 else 2
        minimum = max(w.minimumWidth() for w in self.setting_cards)
        if (width - (count + 1) * 6) / count < minimum:
            count = 1
        while self.settings_grid.count():
            self.settings_grid.takeAt(0)
        for column in range(5):
            self.settings_grid.setColumnStretch(column,1 if column < count else 0)
        for i, widget in enumerate(self.setting_cards):
            self.settings_grid.addWidget(widget, i // count, i % count)
        self.card_columns = count

    def _set_input_mode(self, index):
        super()._set_input_mode(index)
        if hasattr(self, 'plot_options'):
            self.plot_options.setEnabled(index == 0)
            self.overwrite_proc_checkbox.setEnabled(index == 1)


class ResultsPrototype(WidgetResultsAnalyzer):
    def _setup_ui(self):
        super()._setup_ui()
        if hasattr(self, 'use_selected_velocities_checkbox'):
            self.use_selected_velocity = self.use_selected_velocities_checkbox
            self.origin_summary = self.scenario_origin_label
            return
        layout = self.manual_height_checkbox.parentWidget().layout()
        index = layout.indexOf(self.manual_height_checkbox)
        self.use_selected_velocity = QCheckBox(text('Use selected-time velocities', '선택 시점 속도 함께 사용'))
        self.use_selected_velocity.setEnabled(False)
        layout.insertWidget(index + 1, self.use_selected_velocity)
        self.origin_summary = QLabel()
        self.origin_summary.setWordWrap(True)
        self.origin_summary.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.origin_summary.setTextFormat(Qt.PlainText)
        tab_layout = self.tool_tabs.widget(1).layout()
        tab_layout.insertWidget(tab_layout.indexOf(self.export_scenario_button), self.origin_summary)
        self.offset_manual_checkbox.toggled.connect(self._origin)
        self.manual_height_checkbox.toggled.connect(self._origin)
        self.use_selected_velocity.toggled.connect(self._origin)
        self._origin()

    def _origin(self, *_):
        manual = self.offset_manual_checkbox.isChecked() and self.manual_height_checkbox.isChecked()
        self.use_selected_velocity.setEnabled(manual)
        if not manual:
            self.use_selected_velocity.setChecked(False)
        if manual:
            message = text('Manual heights / selected-time velocities.\nMixed initial conditions.',
                           '수동 높이 / 선택 시점 속도\n혼합 초기조건') if self.use_selected_velocity.isChecked() else text(
                           'Manual heights / rest initial conditions.\nSix declared velocities: 0.',
                           '수동 높이 / 정지 초기조건\n선언한 여섯 속도: 0')
        else:
            message = text('Selected-time heights and analysis-frame velocities.', '선택 시점 높이와 분석 프레임 속도입니다.')
        self.origin_summary.setText(message + '\n' + text('mm / mm/s / rad/s', 'mm / mm/s / rad/s'))


class GuidePrototype(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(text('Metric guide', '지표 안내'))
        self.setMinimumSize(640, 480)
        layout = QVBoxLayout(self)
        filters = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText(text('Search definitions', '지표 설명 검색'))
        self.groups = QComboBox()
        self.groups.addItems([text('All', '전체'), text('Posture', '자세'), text('Impact', '충격'),
                              text('Contact', '접촉'), text('Comparison context', '비교 문맥')])
        filters.addWidget(self.search, 1)
        filters.addWidget(self.groups)
        layout.addLayout(filters)
        layout.addWidget(QLabel(text('Current context: Step 2 summary', '현재 문맥: Step 2 요약')))
        self.tabs = QTabWidget()
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.content = QWidget()
        self.grid = QGridLayout(self.content)
        self.grid.setContentsMargins(8, 8, 8, 8)
        self.grid.setSpacing(8)
        self.sections = {}
        self.entries = []
        definitions = get_metric_registry()
        for group in ('Posture', 'Impact', 'Contact', 'Comparison context'):
            title = {'Posture':'자세','Impact':'충격','Contact':'접촉','Comparison context':'비교 문맥'}[group]
            section, body = card(text(group, title))
            self.sections[group] = section
            for descriptor in definitions:
                actual = descriptor.group.value if descriptor.context == 'step2:summary' else 'Comparison context'
                if actual != group:
                    continue
                entry = QLabel()
                entry.setTextFormat(Qt.RichText)
                entry.setWordWrap(True)
                entry.setFocusPolicy(Qt.StrongFocus)
                name = descriptor.label_ko if ui_language.active_language() == 'ko' else descriptor.display_name
                definition = descriptor.definition_ko if ui_language.active_language() == 'ko' else descriptor.long_description
                caution = descriptor.caution_ko if ui_language.active_language() == 'ko' else descriptor.caution
                entry.setText(f'<b>{name}</b> ({descriptor.unit})<br>{definition}<br><i>{caution}</i>')
                body.addWidget(entry)
                self.entries.append((descriptor, entry, group))
        self.scroll.setWidget(self.content)
        self.tabs.addTab(self.scroll, text('Metric definitions', '지표 정의'))
        interpretation = QTextBrowser()
        interpretation.setPlainText(text('Individual values, aligned playback, and repeat statistics have different eligibility. '
            'Copies do not add trials. Missing evidence is unavailable; zero remains a real value. '
            'Experimental and physical labels do not establish measured accuracy or an automatic ISTA verdict.',
            '개별 값·시간 정렬·반복 집계의 조건은 다릅니다. 사본은 시험 수를 늘리지 않습니다. '
            '근거가 없으면 표시할 수 없음으로 남기고 실제 0과 구분합니다. 실험적·물리 지표 표시는 실측 정확도나 자동 ISTA 판정을 뜻하지 않습니다.'))
        self.tabs.addTab(interpretation, text('Interpretation', '해석 안내'))
        layout.addWidget(self.tabs, 1)
        self.empty = QLabel(text('No matching definitions.', '일치하는 지표 설명이 없습니다.'))
        self.empty.hide()
        layout.addWidget(self.empty)
        self.buttons = QDialogButtonBox(QDialogButtonBox.Close)
        self.buttons.rejected.connect(self.hide)
        layout.addWidget(self.buttons)
        self.search.textChanged.connect(self.filter)
        self.groups.currentIndexChanged.connect(self.filter)
        self.filter()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        QTimer.singleShot(0, self.reflow)

    def filter(self, *_):
        terms = self.search.text().casefold().split()
        selected = self.groups.currentIndex()
        visible = 0
        for descriptor, widget, group in self.entries:
            corpus = ' '.join((descriptor.stable_id, descriptor.display_name, descriptor.label_ko,
                               descriptor.long_description, descriptor.definition_ko, *descriptor.aliases)).casefold()
            group_index = ('Posture','Impact','Contact','Comparison context').index(group) + 1
            show = all(term in corpus for term in terms) and (selected == 0 or group_index == selected)
            widget.setVisible(show)
            visible += int(show)
        for group, section in self.sections.items():
            section.setVisible(any(not widget.isHidden() for _, widget, value in self.entries if value == group))
        self.empty.setVisible(not visible)
        self.reflow()

    def reflow(self):
        while self.grid.count():
            self.grid.takeAt(0)
        wide = self.scroll.viewport().width() >= 1000
        self.columns = 2 if wide else 1
        arrangement = {'Posture':(0,0), 'Contact':(1,0), 'Impact':(0,1), 'Comparison context':(2,0)} if wide else {
            'Posture':(0,0), 'Impact':(1,0), 'Contact':(2,0), 'Comparison context':(3,0)}
        for group, section in self.sections.items():
            row, col = arrangement[group]
            self.grid.addWidget(section,row,col,1,2 if wide and group == 'Comparison context' else 1)
        self.grid.setColumnStretch(0,1)
        self.grid.setColumnStretch(1,1 if wide else 0)


def sample_process(widget):
    widget.slice_path_label.setText('generated_affine_capture_trial_A.slice')
    widget.slice_source_label.setText('generated_affine_capture.csv')
    widget.slice_user_range_label.setText('0.100–0.300 s')
    widget.slice_padded_range_label.setText('0.000–0.400 s')
    widget.slice_marker_correction_label.setText(text('Not applied', '적용 안 함'))
    widget.box_dims_warning.setText(text('Dimensions read from slice', 'slice에서 읽은 치수'))
    for field, value in zip((widget.le_box_l,widget.le_box_w,widget.le_box_h),('200','120','80')):
        field.setText(value)
    widget.plot_manager.draw_plot(pd.DataFrame({'F1_X':np.linspace(10,90,21)}, index=np.linspace(0,.4,21)), ['F1_X'])


def sample_results(widget):
    widget.context_active_file_label.setText('generated_affine_capture_trial_A.proc')
    widget.context_rows_label.setText('11')
    widget.result_file_list.addItems(['generated_affine_capture_trial_A.proc', 'generated_tilt_capture_trial_B.proc'])
    widget.plot_manager.draw_plot(pd.DataFrame({('Position','CoM','P_TX'):np.linspace(30,70,11)}, index=np.linspace(.1,.3,11)),
                                  [('Position','CoM','P_TX')])
    widget.tool_tabs.setCurrentIndex(1)


def settle(app):
    for _ in range(8):
        app.processEvents()


def save(app, widget, name, size):
    widget.resize(*size)
    widget.show()
    settle(app)
    if isinstance(widget, ProcessingPrototype):
        target = 430 if size[0] == 1510 else 345 if size[0] == 1100 else 265
        right = 345 if size[0] == 1510 else 300 if size[0] == 1100 else 270
        widget.log_group.setMaximumHeight(104 if size[0] == 1510 else 90 if size[0] == 1100 else 80)
        widget.workflow_splitter.setSizes([target, max(1,widget.workflow_splitter.height()-target-4)])
        widget.context_splitter.setSizes([max(1,widget.context_splitter.width()-right-4),right])
        settle(app)
    screenshot = OUT / (name + '.png')
    widget.grab().save(str(screenshot))
    record = {'name':name, 'requested_client':list(size), 'actual_client':[widget.width(),widget.height()],
              'device_pixel_ratio':widget.devicePixelRatioF(), 'font':widget.font().toString(),
              'path':screenshot.relative_to(ROOT).as_posix()}
    if isinstance(widget, ProcessingPrototype):
        record.update(settings_viewport=[widget.settings_scroll.viewport().width(),widget.settings_scroll.viewport().height()],
                      settings_columns=widget.card_columns, top_height=widget.context_splitter.height(),
                      right_width=widget.context_group.width(), log_height=widget.log_group.height(),
                      footer_height=widget.action_stack.height(), horizontal_scroll_max=widget.settings_scroll.horizontalScrollBar().maximum())
    if isinstance(widget, GuidePrototype):
        record.update(content_width=widget.scroll.viewport().width(), columns=widget.columns,
                      visible_entries=sum(not entry.isHidden() for _,entry,_ in widget.entries))
    widget.hide()
    return record


def main():
    app = QApplication.instance() or QApplication([])
    records = []
    for lang in ('en','ko'):
        ui_language.preferred_language = lambda value=lang:value
        ui_language.configure_language(app)
        processing = ProcessingPrototype(DataLoader(),Parser(FACE_PREFIX_TO_INFO))
        sample_process(processing)
        results = ResultsPrototype(DataLoader())
        sample_results(results)
        guide = GuidePrototype()
        for size in ((1510,800),(1100,720),(820,600)):
            records.append(save(app,processing,f'prototype-process-{lang}-{size[0]}x{size[1]}',size))
            processing.input_mode_combo.setCurrentIndex(1)
            records.append(save(app,processing,f'prototype-process-batch-{lang}-{size[0]}x{size[1]}',size))
            processing.input_mode_combo.setCurrentIndex(0)
            records.append(save(app,results,f'prototype-results-{lang}-{size[0]}x{size[1]}',size))
        results.offset_manual_checkbox.setChecked(True)
        results.manual_height_checkbox.setChecked(True)
        records.append(save(app,results,f'prototype-results-rest-{lang}',(820,600)))
        results.use_selected_velocity.setChecked(True)
        records.append(save(app,results,f'prototype-results-selected-{lang}',(820,600)))
        results.manual_height_checkbox.setChecked(False)
        assert not results.use_selected_velocity.isEnabled() and not results.use_selected_velocity.isChecked()
        for size in ((1100,760),(640,480)):
            records.append(save(app,guide,f'prototype-guide-{lang}-{size[0]}x{size[1]}',size))
        guide.search.setText('TargetPostureError_deg')
        records.append(save(app,guide,f'prototype-guide-search-{lang}',(640,480)))
        guide.search.setText('no such metric never')
        records.append(save(app,guide,f'prototype-guide-empty-{lang}',(640,480)))
        for widget in (processing,results,guide):
            widget.close()
            widget.deleteLater()
        settle(app)
    report = {'historical_baseline_revision':'20dd4ce53a6d401fd6e219d6086b7600dba35ad7',
              'replay_source_hashes':{str(path):hashlib.sha256((ROOT/path).read_bytes()).hexdigest() for path in (
                  'src/analysis/ui/widget_slice_processing.py','src/analysis/ui/widget_results_analyzer.py')}, 'qt':qVersion(), 'platform':app.platformName(),
              'scope':'Historical prototype replay on current source; reuses final product cards/options when present. Outputs are separate from original captures and are not claimed pixel-identical. Each capture initializes proposed splitter targets. No native input/human/OS125 acceptance.',
              'screenshots':records}
    (OUT/'prototype_geometry.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'captures':len(records),'qt':qVersion(),'platform':app.platformName()},ensure_ascii=False))


if __name__ == '__main__':
    main()
