"""Bounded Qt check for on-demand Selected series Guide entries.

Last Reviewed: 2026-11-12
Run with the declared task Qt 6.12 environment; no optimizer or solver is run.
"""
from datetime import datetime, timezone
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
import PySide6
from PySide6.QtCore import QCoreApplication, QEvent, Qt, qVersion
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from shiboken6 import isValid

from src.analysis.pipeline.data_loader import DataLoader
from src.analysis.ui.widget_results_analyzer import WidgetResultsAnalyzer
from src.config.data_columns import RESULT_TIME_COL
from src.config.result_metric_descriptors import get_metric_registry
from src.utils import ui_language


OUT = ROOT / 'docs/visualization/gui_metric_parity/ui_evidence'
SOURCES = ('src/analysis/ui/shared_metric_guide.py', 'src/config/result_metric_descriptors.py',
           'src/analysis/ui/widget_results_analyzer.py')
COLUMNS = (
    (('Analysis','DropPosture','BetaDeg'), '°'),
    (('Velocity','CoM','Global_V_TY'), 'mm/s'),
    (('Velocity','CoM','BoxLocal_V_TX'), 'mm/s'),
    (('Position','CoM','P_RX'), 'rad'),
    (('Analysis','DropPosture','CminIndex'), ''),
    (('Analysis','C1','RelativeHeight'), 'mm'),
    (('Analysis','C2','RelativeHeight'), 'mm'),
    (('Velocity','C1','Global_V_TY'), 'mm/s'),
)


def settle(app):
    for _ in range(5):
        app.processEvents()
    QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
    app.processEvents()


def identity(column):
    return 'step2:series:' + ':'.join(column)


def hashes():
    return {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in SOURCES}


def main():
    started = datetime.now(timezone.utc).isoformat()
    source_before = hashes()
    app = QApplication.instance() or QApplication([])
    checks, captures, async_errors = [], [], []
    original_hook = sys.excepthook
    def exception_hook(kind, value, traceback):
        async_errors.append(str(value))
        original_hook(kind, value, traceback)
    sys.excepthook = exception_hook

    def check(name, condition, **details):
        checks.append(dict(name=name, result='pass' if condition else 'fail', **details))

    def capture(dialog, name):
        settle(app)
        path = OUT / (name + '.png')
        dialog.grab().save(str(path))
        captures.append(dict(path=path.relative_to(ROOT).as_posix(), client=[dialog.width(),dialog.height()],
            font=dialog.font().toString(), device_pixel_ratio=dialog.devicePixelRatioF(),
            focused_metric=dialog.focused_metric, viewport_width=dialog.scroll.viewport().width(),
            content_width=dialog.content.width(), horizontal_max=dialog.scroll.horizontalScrollBar().maximum()))

    def choose(page, column):
        index = next(i for i in range(page.find_max_target_combo.count())
                     if tuple(page.find_max_target_combo.itemData(i)) == column)
        page.find_max_target_combo.setCurrentIndex(index)
        page.open_metric_guide()

    for language in ('en','ko'):
        ui_language.preferred_language = lambda value=language:value
        ui_language.configure_language(app)
        page = WidgetResultsAnalyzer(DataLoader())
        frame = pd.DataFrame({RESULT_TIME_COL:[0.,.1],
            **{column:[np.nan,np.nan] for column,_ in COLUMNS}})
        frame.columns = pd.MultiIndex.from_tuples(frame.columns)
        page._activate_result_data(page._prepare_result_data(frame), 'public_selected_series.proc')
        page.checked_result_columns = {column for column,_ in COLUMNS}
        page.refresh_result_tree()
        page.resize(820,600)
        page.show()
        base_count = len(get_metric_registry())
        guide = None
        try:
            for width,height in ((1100,760),(640,480)):
                previous_key, previous_card = None, None
                for case,(column,expected_unit) in enumerate(COLUMNS):
                    choose(page,column)
                    current = page.metric_guide_dialog
                    if guide is None:
                        guide = current
                    guide.resize(width,height)
                    settle(app)
                    key = identity(column)
                    card = guide.cards.get(key)
                    descriptor = next((entry for entry in guide.entries if entry.stable_id==key),None)
                    prefix = f'{language}/{width}/{case}'
                    check(prefix+' actual client', (guide.width(),guide.height())==(width,height))
                    check(prefix+' host reuses dialog', current is guide)
                    check(prefix+' exact fulltuple identity', guide.focused_metric==key and descriptor is not None
                          and descriptor.column==column and descriptor.context=='step2:series')
                    check(prefix+' one on-demand card', len(guide.cards)==base_count+1
                          and sum(e.context=='step2:series' for e in guide.entries)==1)
                    check(prefix+' literal unit', descriptor is not None and descriptor.unit==expected_unit)
                    check(prefix+' explicit non-alias caution', descriptor is not None
                          and 'not a precontact snapshot' in descriptor.caution
                          and 'whole-window peak' in descriptor.caution and 'fitted comparison' in descriptor.caution)
                    check(prefix+' available definition for missing samples', bool(card) and not card.isHidden()
                          and frame[column].isna().all())
                    check(prefix+' card focus', bool(card) and card.hasFocus())
                    top = card.mapTo(guide.scroll.viewport(),card.rect().topLeft()).y() if card else -1
                    check(prefix+' heading visible', 0<=top<guide.scroll.viewport().height(), heading_y=top)
                    check(prefix+' no horizontal clipping', guide.content.width()<=guide.scroll.viewport().width()
                          and guide.scroll.horizontalScrollBar().maximum()==0)
                    if language=='ko':
                        check(prefix+' Korean label', descriptor is not None
                              and any('\uac00'<=c<='\ud7a3' for c in descriptor.label_ko))
                    if previous_key and previous_key!=key:
                        check(prefix+' stale tuple removed', previous_key not in guide.cards
                              and all(e.stable_id!=previous_key for e in guide.entries)
                              and not isValid(previous_card))
                    same_card = card
                    choose(page,column)
                    settle(app)
                    check(prefix+' same tuple reuses card', guide.cards.get(key) is same_card)
                    if case in (0,2):
                        capture(guide,f'product-series-{language}-{width}x{height}-{case}')
                    previous_key, previous_card = key, card

                # Same component labels on different objects remain different tuples.
                check(f'{language}/{width} object identities distinct',
                    identity(('Analysis','C1','RelativeHeight'))!=identity(('Analysis','C2','RelativeHeight')))
                guide.search.setText('hides the current target')
                guide.classification.setCurrentIndex(3)
                choose(page,COLUMNS[1][0])
                settle(app)
                check(f'{language}/{width} hidden target restores filters',guide.search.text()==''
                      and guide.classification.currentIndex()==0 and guide.tabs.currentIndex()==0)
                guide.search.setFocus()
                reached=False
                target_key=identity(COLUMNS[1][0])
                for _ in range(len(guide.cards)+20):
                    QTest.keyClick(app.focusWidget() or guide,Qt.Key_Tab)
                    settle(app)
                    if app.focusWidget() is guide.cards[target_key]:
                        reached=True
                        break
                target_card=guide.cards[target_key]
                top=target_card.mapTo(guide.scroll.viewport(),target_card.rect().topLeft()).y()
                check(f'{language}/{width} actual Tab reaches selected card',reached
                      and 0<=top<guide.scroll.viewport().height())

                unsupported=('Info','Unknown','Unknown')
                page.find_max_target_combo.addItem('unsupported',unsupported)
                page.find_max_target_combo.setCurrentIndex(page.find_max_target_combo.count()-1)
                page.open_metric_guide()
                settle(app)
                check(f'{language}/{width} unknown removes stale series',guide.focused_metric is None
                      and guide.tabs.currentIndex()==1 and len(guide.cards)==base_count
                      and not any(e.context=='step2:series' for e in guide.entries)
                      and not isValid(target_card))
                check(f'{language}/{width} unknown interpretation at top',guide.reading.verticalScrollBar().value()==0)
                if width==640:
                    capture(guide,f'product-series-unknown-{language}')
                choose(page,COLUMNS[0][0])
                settle(app)
                QTest.keyClick(guide,Qt.Key_Escape)
                check(f'{language}/{width} Escape hides',not guide.isVisible())
                choose(page,COLUMNS[2][0])
                settle(app)
                check(f'{language}/{width} reopen same host object',page.metric_guide_dialog is guide
                      and guide.isVisible() and guide.focused_metric==identity(COLUMNS[2][0]))

                # Queue several replacements before processing timers/deferred deletes.
                for column,_ in COLUMNS[:6]:
                    choose(page,column)
                settle(app)
                check(f'{language}/{width} rapid replacement leaves one final card',
                    guide.focused_metric==identity(COLUMNS[5][0]) and len(guide.cards)==base_count+1)
                guide.focus_metric(('Analysis','DropPostureSummary','CminMargin_mm'))
                settle(app)
                check(f'{language}/{width} summary clears row-specific card',
                    guide.focused_metric=='step2:summary:CminMargin_mm' and len(guide.cards)==base_count)
        finally:
            page.close_all_popups()
            page.close()
            page.deleteLater()
            settle(app)
    check('No asynchronous Qt callback exception',not async_errors, errors=async_errors)
    source_after=hashes()
    check('Relevant source unchanged during check',source_after==source_before)
    receipt=dict(started_utc=started,finished_utc=datetime.now(timezone.utc).isoformat(),
        python=sys.version,executable=str(Path(sys.executable).relative_to(ROOT)),pyside=PySide6.__version__,
        qt=qVersion(),platform=app.platformName(),source_hashes=source_after,
        scope='Actual native-platform Qt/QTest selected-series Guide context checks. In-memory all-missing public frame; no pipeline, optimizer, solver, external desktop click, OS125 or human acceptance.',
        checks=checks,captures=captures,failures=[entry for entry in checks if entry['result']=='fail'])
    (OUT/'product_series_qt612_recheck.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(qt=qVersion(),pyside=PySide6.__version__,checks=len(checks),captures=len(captures),failures=receipt['failures']),ensure_ascii=False))
    return 1 if receipt['failures'] else 0


if __name__=='__main__':
    raise SystemExit(main())
