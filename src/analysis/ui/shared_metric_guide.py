"""One searchable, context-qualified renderer for both result hosts."""
from html import escape
from pathlib import Path

from PySide6.QtCore import Qt, QTimer, QEvent, QPoint
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (QDialog, QDialogButtonBox, QVBoxLayout, QHBoxLayout, QLineEdit,
    QComboBox, QLabel, QTabWidget, QScrollArea, QWidget, QGridLayout, QFrame, QTextBrowser, QSizePolicy, QPushButton)

from src.config.result_metric_descriptors import get_metric_registry, get_series_metric_descriptor
from src.config.metric_interpretation import READING_GUIDE, READING_GUIDE_KO
from src.utils.ui_language import active_language, tr


class GuideDiagram(QLabel):
    def __init__(self, group, parent=None):
        super().__init__(parent)
        self.original = QPixmap(str(Path(__file__).with_name('assets') / ('guide_' + group.lower() + '.png')))
        self.setWordWrap(True)
        self.setMinimumWidth(0)
        self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)
        self.setAlignment(Qt.AlignCenter)
        self.setToolTip(tr('Conceptual illustration; definitions and cautions below remain authoritative.'))
        if self.original.isNull():
            self.setText(tr('Diagram unavailable. Read the geometry, timing and cautions below.'))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if not self.original.isNull():
            scaled = self.original.scaledToWidth(max(1, self.width()), Qt.SmoothTransformation)
            self.setPixmap(scaled)
            self.setFixedHeight(scaled.height())


class SharedMetricGuideDialog(QDialog):
    def __init__(self, parent=None, selected_key=None):
        super().__init__(parent)
        self.setWindowTitle(tr('Metric guide'))
        self.resize(1100, 760)
        self.setMinimumSize(640, 480)
        self.entries = get_metric_registry()
        self.focused_metric = None
        layout = QVBoxLayout(self)
        controls = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText(tr('Search metrics'))
        self.search.setAccessibleName(tr('Search metrics'))
        self.classification = QComboBox()
        for label, key in (('All', 'all'), ('Posture', 'Posture'), ('Impact', 'Impact'),
                           ('Contact', 'Contact'), ('Comparison context', 'compare'), ('Selected series', 'step2:series')):
            self.classification.addItem(tr(label), key)
        controls.addWidget(self.search, 1)
        controls.addWidget(self.classification)
        layout.addLayout(controls)
        self.context_label = QLabel()
        self.context_label.setWordWrap(True)
        layout.addWidget(self.context_label)
        self.tabs = QTabWidget()
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.content = QWidget()
        self.content.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self.content.setMinimumWidth(0)
        self.grid = QGridLayout(self.content)
        self.grid.setContentsMargins(6, 6, 6, 6)
        self.grid.setSpacing(12)
        self.scroll.setWidget(self.content)
        self.groups, self.cards, self.group_layouts = {}, {}, {}
        self.diagram_windows = {}
        self.ko = active_language() == 'ko'
        for name in ('Posture', 'Impact', 'Contact', 'Comparison context', 'Selected series'):
            panel = QWidget()
            panel.setMinimumWidth(0)
            panel.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
            body = QVBoxLayout(panel)
            title = QLabel('<h2>' + escape(tr(name)) + '</h2>')
            body.addWidget(title)
            if name not in ('Comparison context', 'Selected series'):
                body.addWidget(GuideDiagram(name))
                view_diagram = QPushButton(tr('View diagram'))
                view_diagram.setProperty('guide_scroll_target', True)
                view_diagram.installEventFilter(self)
                view_diagram.clicked.connect(lambda _=False, group=name: self._open_diagram(group))
                body.addWidget(view_diagram)
            self.groups[name] = panel
            self.group_layouts[name] = body
            for entry in self.entries:
                group = 'Comparison context' if entry.context == 'compare' else entry.group.value
                if group != name:
                    continue
                self._add_entry(entry, body)
            body.addStretch()
        self.empty_label = QLabel(tr('No metrics match the search and classification.'))
        self.empty_label.setWordWrap(True)
        self.grid.addWidget(self.empty_label, 5, 0, 1, 2)
        self.tabs.addTab(self.scroll, tr('Metric definitions'))
        self.reading = QTextBrowser()
        self.reading.setHtml(READING_GUIDE_KO if self.ko else READING_GUIDE)
        self.tabs.addTab(self.reading, tr('Interpretation'))
        layout.addWidget(self.tabs, 1)
        self.buttons = QDialogButtonBox(QDialogButtonBox.Close)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)
        self.search.textChanged.connect(self._filter)
        self.classification.currentIndexChanged.connect(self._filter)
        self.scroll.viewport().installEventFilter(self)
        self._columns = None
        self._reflow()
        self._filter()
        self.focus_metric(selected_key)

    def _add_entry(self, entry, body):
        card = QFrame()
        card.setFocusPolicy(Qt.StrongFocus)
        card.installEventFilter(self)
        card.setMinimumWidth(0)
        card.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        card.setObjectName(entry.stable_id)
        card.setProperty('metric_id', entry.stable_id)
        card.setStyleSheet('QFrame:focus {border: 2px solid #4075a3;}')
        card.setAccessibleName(entry.label_ko if self.ko else entry.display_name)
        box = QVBoxLayout(card)
        box.setContentsMargins(8, 6, 8, 6)
        label = entry.label_ko if self.ko else entry.display_name
        definition = entry.definition_ko if self.ko else entry.long_description
        caution = entry.caution_ko if self.ko else entry.caution
        heading = QLabel('<b>' + escape(label) + escape(' (' + entry.unit + ')' if entry.unit else '') + '</b>')
        heading.setWordWrap(True)
        heading.setMinimumWidth(0)
        heading.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        box.addWidget(heading)
        for text in (definition, (tr('Caution') + ': ' + caution) if caution else '',
                     tr('Time/reference') + ': ' + (entry.time_reference_ko if self.ko else entry.time_reference)
                     + ' / ' + (entry.reference_ko if self.ko else entry.reference)):
            if text:
                paragraph = QLabel(text)
                paragraph.setTextFormat(Qt.PlainText)
                paragraph.setWordWrap(True)
                paragraph.setMinimumWidth(0)
                paragraph.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
                box.addWidget(paragraph)
        body.addWidget(card)
        self.cards[entry.stable_id] = card
        return card

    def eventFilter(self, obj, event):
        if obj is self.scroll.viewport() and event.type() == QEvent.Resize:
            self._reflow()
        if (obj.property('metric_id') or obj.property('guide_scroll_target')) and event.type() == QEvent.FocusIn:
            QTimer.singleShot(0, obj, lambda card=obj: self._scroll_to_card(card))
        return super().eventFilter(obj, event)

    def _reflow(self):
        columns = 2 if self.scroll.viewport().width() >= 1000 else 1
        if columns == self._columns:
            return
        self._columns = columns
        for panel in self.groups.values():
            self.grid.removeWidget(panel)
        placements = [('Posture', 0, 0), ('Contact', 1, 0), ('Impact', 0, 1)] if columns == 2 else [
            ('Posture', 0, 0), ('Impact', 1, 0), ('Contact', 2, 0)]
        for name, row, column in placements:
            self.grid.addWidget(self.groups[name], row, column)
        self.grid.addWidget(self.groups['Comparison context'], 3, 0, 1, columns)
        self.grid.addWidget(self.groups['Selected series'], 4, 0, 1, columns)
        self.grid.setColumnStretch(0, 1)
        self.grid.setColumnStretch(1, 1 if columns == 2 else 0)

    def _filter(self, *_):
        query = self.search.text().casefold().split()
        category = self.classification.currentData()
        visible = 0
        for entry in self.entries:
            group = 'compare' if entry.context == 'compare' else 'step2:series' if entry.context == 'step2:series' else entry.group.value
            text = ' '.join((entry.stable_id, entry.display_name, entry.label_ko, entry.long_description,
                             entry.definition_ko, *entry.aliases)).casefold()
            show = (category == 'all' or category == group) and all(term in text for term in query)
            self.cards[entry.stable_id].setVisible(show)
            visible += show
        for name, panel in self.groups.items():
            ids = [e.stable_id for e in self.entries if ('Comparison context' if e.context == 'compare' else 'Selected series' if e.context == 'step2:series' else e.group.value) == name]
            panel.setVisible(any(not self.cards[key].isHidden() for key in ids))
        self.empty_label.setVisible(not visible)

    def focus_metric(self, key=None, *, context=None):
        if isinstance(key, (tuple, list)):
            if tuple(key[:2]) == ('Analysis', 'DropPostureSummary'):
                key = 'step2:summary:' + str(key[2])
            else:
                descriptor = get_series_metric_descriptor(key)
                if descriptor is not None:
                    self._set_series_entry(descriptor)
                    key = descriptor.stable_id
                else:
                    key = None
        if key and key not in self.cards and 'compare:' + key in self.cards:
            key = 'compare:' + key
        if not key or not key.startswith('step2:series:'):
            self._clear_series_entry()
        for identity, card in self.cards.items():
            selector = 'QFrame[metric_id="' + identity + '"]'
            card.setStyleSheet(selector + ':focus {border: 2px solid #4075a3;} ' +
                (selector + ' {border: 1px solid #4075a3; background: #edf5fc;}' if identity == key else ''))
        self.focused_metric = key if key in self.cards else None
        self.context_label.setText(tr('Selected series') if key and key.startswith('step2:series:') else tr('Comparison context') if context == 'compare' or (key and key.startswith('compare:'))
                                   else tr('Saved result summary'))
        if self.focused_metric:
            self.search.clear()
            self.classification.setCurrentIndex(0)
            self.tabs.setCurrentIndex(0)
            QTimer.singleShot(0, self, self._reveal_target)
        else:
            self.tabs.setCurrentIndex(1)
            self.scroll.verticalScrollBar().setValue(0)
            self.reading.verticalScrollBar().setValue(0)

    def _set_series_entry(self, descriptor):
        previous = [entry for entry in self.entries if entry.context == 'step2:series']
        if previous and previous[0].stable_id == descriptor.stable_id:
            return
        self._clear_series_entry()
        self.entries = self.entries + (descriptor,)
        body = self.group_layouts['Selected series']
        card = self._add_entry(descriptor, body)
        body.removeWidget(card)
        body.insertWidget(max(1, body.count() - 1), card)
        self._filter()

    def _clear_series_entry(self):
        previous = [entry for entry in self.entries if entry.context == 'step2:series']
        for entry in previous:
            card = self.cards.pop(entry.stable_id)
            self.group_layouts['Selected series'].removeWidget(card)
            card.hide()
            card.deleteLater()
        self.entries = tuple(entry for entry in self.entries if entry.context != 'step2:series')
        if previous:
            self._filter()

    def _reveal_target(self):
        if self.focused_metric in self.cards:
            card = self.cards[self.focused_metric]
            card.setFocus(Qt.OtherFocusReason)
            self._scroll_to_card(card)

    def _scroll_to_card(self, card):
        self.scroll.horizontalScrollBar().setValue(0)
        top = card.mapTo(self.content, QPoint(0, 0)).y()
        self.scroll.verticalScrollBar().setValue(max(0, top - 12))

    def _open_diagram(self, group):
        if group not in self.diagram_windows:
            dialog = QDialog(self)
            dialog.setWindowTitle(tr(group) + ' — ' + tr('Diagram'))
            dialog.resize(1100, 760)
            body = QVBoxLayout(dialog)
            scroll = QScrollArea()
            label = QLabel()
            pixmap = QPixmap(str(Path(__file__).with_name('assets') / ('guide_' + group.lower() + '.png')))
            if pixmap.isNull():
                label.setText(tr('Diagram unavailable. Read the geometry, timing and cautions below.'))
            else:
                label.setPixmap(pixmap)
            scroll.setWidget(label)
            scroll.setFocusPolicy(Qt.StrongFocus)
            body.addWidget(scroll)
            buttons = QDialogButtonBox(QDialogButtonBox.Close)
            buttons.rejected.connect(dialog.hide)
            body.addWidget(buttons)
            self.diagram_windows[group] = dialog
        self.diagram_windows[group].show()
        self.diagram_windows[group].raise_()

    def closeEvent(self, event):
        event.ignore()
        self.hide()

    def reject(self):
        self.hide()
