"""Compact scene review inside Step 1; the existing plot edits the range."""
from PySide6.QtCore import Signal, Qt
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QComboBox, QTableWidget, QTableWidgetItem, QAbstractItemView, QHeaderView, QMenu, QGridLayout, QGroupBox)
from src.analysis.pipeline.intended_contact import feature_options, feature_label, feature_corners
from src.analysis.pipeline.scene_trial_record import eligibility_suggestion
from src.utils.ui_language import tr


MOTION_LABELS = {'stationary': 'Stationary', 'free_fall': 'Free-fall candidate',
                 'tip_or_rotation': 'Tilt / rotation', 'robot_handling': 'Handling candidate',
                 'tracking_jump': 'Abrupt pose change', 'unclear': 'Unclear'}


def _item_tooltip(row):
    record = row.get('record_evidence')
    if record:
        status = 'confirmed' if row['identity']['confirmed'] else 'unconfirmed'
        notes = [f'Recorded item {status}; observed agreement is separate.']
        if record.get('attempt_id'):
            notes.append(f"Attempt {record['attempt_id']}; anchor {record['anchor_time_s']} s.")
        reasons = {'ambiguous_anchors': 'Multiple anchors fall within this interval.',
                   'overlapping_included_ranges': 'Anchor belongs to overlapping included intervals.',
                   'contradictory_order': 'Performed order conflicts with capture anchors.',
                   'no_anchor': 'No explicit anchor in this interval.',
                   'not_included': 'Include this interval before linking an item.',
                   'handling_record': 'Recorded as handling, without a trial item.'}
        if record['association'] in reasons:
            notes.append(reasons[record['association']])
        elif not record['confirmation_supported']:
            notes.append('Record Type, item or applied edition remains unconfirmed.')
        return '\n'.join(notes)
    notes = [row.get('sequence_evidence', ''), row.get('eligibility_condition', '')]
    geometry = row.get('geometry', {})
    if geometry.get('status') == 'registration_required':
        notes.append('Box and floor registration required.')
    elif geometry.get('status') == 'registered':
        crossings = geometry.get('floor_crossings', [])
        if not crossings:
            notes.append('Floor approach not established.')
        elif not crossings[0].get('approach_feature'):
            notes.append('Approach feature unclear.')
    return '\n'.join(note for note in notes if note)


def _observed_label(row):
    evidence = row.get('observed_consistency')
    if not evidence:
        return '—'
    if evidence['motion'] == 'different':
        return 'Different motion'
    if evidence['approach'] == 'different':
        return 'Different approach'
    if evidence['approach'] == 'match':
        return 'Approach matches'
    if evidence['motion'] == 'unavailable':
        return 'Unavailable'
    return 'Rotation observed' if row['motion'] == 'tip_or_rotation' else 'Free fall observed'


class SceneReviewWidget(QWidget):
    row_selected = Signal(object)
    changed = Signal()
    error = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.session = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        tools = QHBoxLayout()
        self.detect_button = QPushButton(tr('Detect scenes'))
        self.open_review_button = QPushButton(tr('Open review...'))
        self.save_review_button = QPushButton(tr('Save review...'))
        self.geometry_button = QPushButton(tr('Geometry...'))
        self.geometry_button.setToolTip(tr('Optional marker coordinates in box axes, floor height and COM.'))
        self.trial_record_button = QPushButton(tr('Test record...'))
        record_menu = QMenu(self.trial_record_button)
        self.load_trial_record_action = record_menu.addAction(tr('Load...'))
        self.clear_trial_record_action = record_menu.addAction(tr('Clear'))
        self.trial_record_button.setMenu(record_menu)
        self.add_button = QPushButton(tr('Add range'))
        self.remove_button = QPushButton(tr('Remove'))
        self.include_button = QPushButton(tr('Include'))
        self.exclude_button = QPushButton(tr('Exclude'))
        self.revert_button = QPushButton(tr('Revert detected range'))
        for button in (self.detect_button, self.add_button, self.remove_button,
                       self.include_button, self.exclude_button, self.revert_button):
            button.setMinimumWidth(button.sizeHint().width())
        for button in (self.detect_button, self.add_button, self.remove_button):
            tools.addWidget(button)
        tools.addStretch()
        layout.addLayout(tools)
        decisions = QHBoxLayout()
        for button in (self.include_button, self.exclude_button, self.revert_button):
            decisions.addWidget(button)
        decisions.addStretch()
        layout.addLayout(decisions)
        info = QHBoxLayout()
        self.range_label = QLabel(tr('No scene selected'))
        self.count_label = QLabel(tr('No scenes'))
        info.addWidget(self.range_label, 1)
        info.addWidget(self.count_label)
        layout.addLayout(info)
        self.table = QTableWidget(0, 9)
        self.table.setHorizontalHeaderLabels([tr('Scene'), tr('Start (s)'), tr('End (s)'), tr('Motion'), tr('Rotation (deg)'), tr('Review'), tr('Item'), tr('Intended contact'), tr('Observed')])
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().hide()
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().moveSection(5, 1)
        self.table.setVerticalScrollMode(QAbstractItemView.ScrollPerItem)
        layout.addWidget(self.table)
        layout.addStretch()
        identity = QHBoxLayout()
        identity.addWidget(QLabel(tr('Type')))
        self.type_combo = QComboBox()
        for kind in ('Unknown', 'G', 'H'):
            self.type_combo.addItem(tr(kind), kind)
        identity.addWidget(self.type_combo)
        self.edition_combo = QComboBox()
        self.edition_combo.addItem(tr('Edition unknown'), None)
        self.edition_combo.addItem('2018-03', '2018-03')
        self.edition_combo.setToolTip(tr('Applied edition from the test record. The available catalogue is 2018-03.'))
        identity.addWidget(self.edition_combo)
        self.identify_button = QPushButton(tr('Identify items'))
        identity.addWidget(self.identify_button)
        self.item_combo = QComboBox()
        self.item_combo.setMinimumWidth(140)
        identity.addWidget(self.item_combo)
        self.confirm_button = QPushButton(tr('Confirm item'))
        self.confirm_button.setToolTip(tr('Confirm only after checking eligibility and sequence in the test record.'))
        identity.addWidget(self.confirm_button)
        self.intended_combo = QComboBox()
        self.intended_combo.addItem(tr('Contact unspecified'), None)
        for faces in feature_options():
            self.intended_combo.addItem(feature_label(faces), faces)
            corners = ', '.join(f'C{i}' for i in feature_corners(faces))
            self.intended_combo.setItemData(self.intended_combo.count() - 1, corners, Qt.ToolTipRole)
        self.intended_combo.setMinimumWidth(170)
        self.intended_combo.setMaximumWidth(230)
        self.intended_combo.setToolTip(tr('Intended contact in registered box-local axes. Independent of the detected item.'))
        identity.addWidget(self.intended_combo)
        self.set_intended_button = QPushButton(tr('Set contact'))
        identity.addWidget(self.set_intended_button)
        identity.addStretch()
        self.save_all_button = QPushButton(tr('Save included...'))
        self.type_group = QGroupBox(tr('Test type and item'))
        grid = QGridLayout(self.type_group)
        grid.setContentsMargins(7, 7, 7, 7)
        grid.setSpacing(5)
        self.type_basis_label = QLabel(tr('Type basis: Unconfirmed'))
        grid.addWidget(identity.takeAt(0).widget(), 0, 0)
        grid.addWidget(self.type_combo, 0, 1)
        grid.addWidget(self.edition_combo, 1, 0, 1, 2)
        grid.addWidget(self.type_basis_label, 2, 0, 1, 2)
        grid.addWidget(self.identify_button, 3, 0, 1, 2)
        grid.addWidget(self.item_combo, 4, 0)
        grid.addWidget(self.confirm_button, 4, 1)
        grid.addWidget(self.intended_combo, 5, 0)
        grid.addWidget(self.set_intended_button, 5, 1)
        grid.setRowStretch(6, 1)
        self.table.horizontalScrollBar().rangeChanged.connect(self.update_viewport_minimum)
        self.table.itemSelectionChanged.connect(self._selection_changed)
        self.include_button.clicked.connect(lambda: self._decide('include'))
        self.exclude_button.clicked.connect(lambda: self._decide('exclude'))
        self.remove_button.clicked.connect(self._remove)
        self.revert_button.clicked.connect(self._revert)
        self.type_combo.currentIndexChanged.connect(self._context_changed)
        self.type_combo.activated.connect(self._type_selected)
        self.edition_combo.currentIndexChanged.connect(self._context_changed)
        self.identify_button.clicked.connect(self._identify)
        self.confirm_button.clicked.connect(self._confirm)
        self.set_intended_button.clicked.connect(self._set_intended)
        self.refresh()
        self.update_viewport_minimum()

    def selected_id(self):
        if not self.table.selectionModel().selectedRows():
            return None
        item = self.table.item(self.table.currentRow(), 0)
        return item.text() if item else None

    def selected_row(self):
        row_id = self.selected_id()
        return self.session.row(row_id) if row_id and self.session else None

    def selected_ids(self):
        return [self.table.item(i.row(), 0).text() for i in self.table.selectionModel().selectedRows()]

    def refresh(self, select_id=None):
        reveal_selection = select_id is not None
        select_id = select_id or self.selected_id()
        self.table.blockSignals(True)
        rows = self.session.rows if self.session else []
        self.table.setRowCount(len(rows))
        for i, row in enumerate(rows):
            labels = [row['id'], f"{row['start']:.6f}", f"{row['end']:.6f}",
                      MOTION_LABELS[row['motion']],
                      f"{row['rotation_deg']:.2f}" if row['rotation_deg'] is not None else '—',
                      row['decision'].title(), row['identity']['scenario_id'] or ', '.join(row['item_candidates']) or 'Unconfirmed',
                      feature_label(row['intended_contact']['faces']) if row.get('intended_contact') else '—',
                      _observed_label(row)]
            if row.get('record_evidence', {}).get('item') and not row['identity']['confirmed']:
                labels[6] = row['record_evidence']['item'] + ' ?'
            details = ', '.join(row['tags'])
            if row['left_censored'] or row['right_censored']:
                details += ' Full motion is not established within this interval.'
            if row['evidence_status'] != 'current':
                labels[3] = 'Re-detect after edit'
            previous = row.get('previous_review')
            if previous and row['decision'] == 'unreviewed':
                labels[5] = 'Review again'
            for j, label in enumerate(labels):
                item = QTableWidgetItem(label)
                item.setToolTip(f"{row['start']!r}–{row['end']!r} s\n{details}" if j < 5 else
                                row.get('sequence_evidence', '')
                                + '\n' + row.get('eligibility_condition', ''))
                if j == 5 and previous:
                    item.setToolTip('Saved decision: ' + previous['decision'] + '\n'
                                    + '\n'.join(previous['reasons']))
                if j == 6:
                    item.setToolTip(_item_tooltip(row))
                if j == 7:
                    item.setToolTip('Operator-specified local contact; independent of detected motion/items.'
                                    if row.get('intended_contact') else 'No intended contact specified.')
                if j == 8:
                    item.setToolTip(row.get('observed_consistency', {}).get('reason', 'No test record linked.'))
                self.table.setItem(i, j, item)
        self.table.blockSignals(False)
        self.count_label.setText(tr("{} / {} reviewed").format(sum(r['decision'] != 'unreviewed' for r in rows), len(rows)) if rows else tr('No scenes'))
        enabled = bool(rows)
        self.trial_record_button.setEnabled(enabled)
        self.clear_trial_record_action.setEnabled(bool(self.session and self.session.trial_record))
        suggestion = eligibility_suggestion(self.session.trial_record, applied_edition=self.session.applied_edition)['suggested_type'] if self.session and self.session.trial_record else None
        basis = self.session.type_basis if self.session else 'unconfirmed'
        basis_label = {'operator': 'Operator selection', 'test_record': 'Test record',
                       'source_declaration': 'Source declaration; confirm Type',
                       'legacy_unconfirmed': 'Previous selection; confirm Type', 'unconfirmed': 'Unconfirmed'}[basis]
        self.type_basis_label.setText(tr('Type basis: {}').format(tr(basis_label)))
        tip = 'Select Type against the test record. Filename, mass or row order cannot confirm a trial.'
        if suggestion:
            tip += f' 2018-03 p.2 suggests Type {suggestion}; verify test eligibility.'
        self.type_combo.setToolTip(tip)
        for button in (self.add_button, self.remove_button, self.include_button, self.exclude_button):
            button.setEnabled(enabled)
        reviewed = enabled and self.session.all_reviewed
        self.identify_button.setEnabled(reviewed)
        self.save_all_button.setEnabled(reviewed and any(r['decision'] == 'include' for r in rows))
        if select_id:
            for i, row in enumerate(rows):
                if row['id'] == select_id:
                    self.table.selectRow(i)
                    if reveal_selection:
                        self.table.scrollToItem(self.table.item(i, 0), QAbstractItemView.EnsureVisible)
                    break
        self._selection_changed()

    def _selection_changed(self):
        row = self.selected_row()
        self._update_range_display(row)
        self.item_combo.clear()
        self.item_combo.addItem(tr('Unconfirmed'), None)
        self.item_combo.setToolTip(_item_tooltip(row) if row else '')
        if row:
            for item in row['item_candidates']:
                self.item_combo.addItem(item, item)
            if row['identity']['confirmed']:
                self.item_combo.setCurrentText(row['identity']['scenario_id'])
        self.confirm_button.setEnabled(bool(row and row['item_candidates'] and self.session.all_reviewed
                                            and self.session.applied_edition
                                            and self.session.type_basis in ('operator', 'test_record')))
        self.intended_combo.setCurrentIndex(0)
        if row and row.get('intended_contact'):
            target = tuple(row['intended_contact']['faces'])
            for index in range(1, self.intended_combo.count()):
                if tuple(self.intended_combo.itemData(index)) == target:
                    self.intended_combo.setCurrentIndex(index)
                    break
        contact_ready = self.can_set_intended_contact()
        self.intended_combo.setEnabled(contact_ready)
        self.set_intended_button.setEnabled(contact_ready)
        self.row_selected.emit(row)
        self.changed.emit()

    def can_revert(self):
        row = self.selected_row()
        return bool(row and len(self.selected_ids()) == 1 and row['origin'] == 'automatic'
                    and row['auto_start'] is not None and row['auto_end'] is not None
                    and (row['start'], row['end']) != (row['auto_start'], row['auto_end']))

    def _update_range_display(self, row):
        self.revert_button.setEnabled(self.can_revert())
        if row is None:
            text, tip = 'No scene selected', 'Select an edited detected scene.'
        elif row['origin'] == 'manual':
            text = tr("Manual: {:.6g}–{:.6g} s    No detected range").format(row['start'], row['end'])
            tip = 'Manual scenes have no detected range to restore.'
        else:
            edited = (row['start'], row['end']) != (row['auto_start'], row['auto_end'])
            text = (tr("Edited: {:.6g}–{:.6g} s    ").format(row['start'], row['end']) if edited else '')
            text += tr("Detected: {:.6g}–{:.6g} s").format(row['auto_start'], row['auto_end'])
            tip = 'Restore detected bounds; review Include/Exclude again.'
        self.range_label.setText(tr(text))
        self.revert_button.setToolTip(tr(tip))

    def _revert(self):
        if self.session and self.can_revert():
            try:
                self.session.revert_detected_range(self.selected_id())
                self.refresh()
            except ValueError as exc:
                self.error.emit(str(exc))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.update_viewport_minimum()

    def update_viewport_minimum(self):
        table = self.table
        rows_header = table.verticalHeader()
        rows_header.setDefaultSectionSize(max(24, table.fontMetrics().height() + 7))
        row_height = rows_header.defaultSectionSize()
        window = self.window()
        rows = 4 if window.width() >= 1100 and window.height() >= 720 else 2
        header_height = table.horizontalHeader().sizeHint().height()
        horizontal = table.horizontalScrollBar()
        scrollbar_height = horizontal.sizeHint().height() if horizontal.maximum() else 0
        table.setFixedHeight(header_height + rows * row_height + 2 * table.frameWidth() + scrollbar_height)

    def can_set_intended_contact(self):
        row = self.selected_row()
        registration = self.session.result.registration if self.session else None
        return bool(row and len(self.selected_ids()) == 1
                    and row['decision'] == 'include' and row['evidence_status'] == 'current'
                    and registration is not None and registration.floor_y_mm is not None)

    def _set_intended(self):
        try:
            self.session.set_intended_contact(self.selected_id(), self.intended_combo.currentData())
            self.refresh()
        except ValueError as exc:
            self.error.emit(str(exc))

    def _decide(self, decision):
        if self.session:
            for row_id in self.selected_ids():
                self.session.set_decision(row_id, decision)
            self.refresh()

    def _remove(self):
        if self.session:
            for row_id in self.selected_ids():
                self.session.remove(row_id)
            self.refresh()

    def _context_changed(self):
        if self.session:
            self.session.set_context(self.type_combo.currentData(), self.edition_combo.currentData())
            self.refresh()

    def _type_selected(self):
        if self.session:
            self.session.set_context(self.type_combo.currentData(), self.edition_combo.currentData(),
                type_basis='unconfirmed' if self.type_combo.currentData() == 'Unknown' else 'operator')
            self.refresh()

    def _identify(self):
        try:
            self.session.identify()
            self.refresh()
        except ValueError as exc:
            self.error.emit(str(exc))

    def _confirm(self):
        try:
            self.session.confirm_item(self.selected_id(), self.item_combo.currentData())
            self.refresh()
        except ValueError as exc:
            self.error.emit(str(exc))
