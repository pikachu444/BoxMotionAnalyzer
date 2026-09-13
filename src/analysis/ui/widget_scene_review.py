"""Compact scene review inside Step 1; the existing plot edits the range."""
from PySide6.QtCore import Signal, Qt
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QComboBox, QTableWidget, QTableWidgetItem, QAbstractItemView, QHeaderView, QMenu)
from src.analysis.pipeline.intended_contact import feature_options, feature_label, feature_corners
from src.analysis.pipeline.scene_trial_record import eligibility_suggestion


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
        self.detect_button = QPushButton('Detect scenes')
        self.open_review_button = QPushButton('Open review...')
        self.save_review_button = QPushButton('Save review...')
        self.geometry_button = QPushButton('Geometry...')
        self.geometry_button.setToolTip('Optional marker coordinates in box axes, floor height and COM.')
        self.trial_record_button = QPushButton('Test record...')
        record_menu = QMenu(self.trial_record_button)
        self.load_trial_record_action = record_menu.addAction('Load...')
        self.clear_trial_record_action = record_menu.addAction('Clear')
        self.trial_record_button.setMenu(record_menu)
        self.add_button = QPushButton('Add range')
        self.remove_button = QPushButton('Remove')
        self.include_button = QPushButton('Include')
        self.exclude_button = QPushButton('Exclude')
        for button in (self.detect_button, self.open_review_button, self.save_review_button, self.geometry_button, self.trial_record_button, self.add_button,
                       self.remove_button, self.include_button, self.exclude_button):
            tools.addWidget(button)
        tools.addStretch()
        self.count_label = QLabel('No scenes')
        tools.addWidget(self.count_label)
        layout.addLayout(tools)
        self.table = QTableWidget(0, 9)
        self.table.setHorizontalHeaderLabels(['Scene', 'Start (s)', 'End (s)', 'Motion', 'Rotation (deg)', 'Review', 'Item', 'Intended contact', 'Observed'])
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().hide()
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(7, QHeaderView.ResizeMode.Stretch)
        self.table.setMinimumHeight(110)
        layout.addWidget(self.table)
        identity = QHBoxLayout()
        identity.addWidget(QLabel('Type'))
        self.type_combo = QComboBox()
        self.type_combo.addItems(['Unknown', 'G', 'H'])
        identity.addWidget(self.type_combo)
        self.edition_combo = QComboBox()
        self.edition_combo.addItem('Edition unknown', None)
        self.edition_combo.addItem('2018-03', '2018-03')
        self.edition_combo.setToolTip('Applied edition from the test record. The available catalogue is 2018-03.')
        identity.addWidget(self.edition_combo)
        self.identify_button = QPushButton('Identify items')
        identity.addWidget(self.identify_button)
        self.item_combo = QComboBox()
        self.item_combo.setMinimumWidth(140)
        identity.addWidget(self.item_combo)
        self.confirm_button = QPushButton('Confirm item')
        self.confirm_button.setToolTip('Confirm only after checking eligibility and sequence in the test record.')
        identity.addWidget(self.confirm_button)
        self.intended_combo = QComboBox()
        self.intended_combo.addItem('Contact unspecified', None)
        for faces in feature_options():
            self.intended_combo.addItem(feature_label(faces), faces)
            corners = ', '.join(f'C{i}' for i in feature_corners(faces))
            self.intended_combo.setItemData(self.intended_combo.count() - 1, corners, Qt.ToolTipRole)
        self.intended_combo.setMinimumWidth(170)
        self.intended_combo.setMaximumWidth(230)
        self.intended_combo.setToolTip('Intended contact in registered box-local axes. Independent of the detected item.')
        identity.addWidget(self.intended_combo)
        self.set_intended_button = QPushButton('Set contact')
        identity.addWidget(self.set_intended_button)
        identity.addStretch()
        self.save_all_button = QPushButton('Save included...')
        identity.addWidget(self.save_all_button)
        layout.addLayout(identity)
        self.table.itemSelectionChanged.connect(self._selection_changed)
        self.include_button.clicked.connect(lambda: self._decide('include'))
        self.exclude_button.clicked.connect(lambda: self._decide('exclude'))
        self.remove_button.clicked.connect(self._remove)
        self.type_combo.currentTextChanged.connect(self._context_changed)
        self.edition_combo.currentIndexChanged.connect(self._context_changed)
        self.identify_button.clicked.connect(self._identify)
        self.confirm_button.clicked.connect(self._confirm)
        self.set_intended_button.clicked.connect(self._set_intended)
        self.refresh()

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
        self.count_label.setText(f"{sum(r['decision'] != 'unreviewed' for r in rows)} / {len(rows)} reviewed" if rows else 'No scenes')
        enabled = bool(rows)
        self.trial_record_button.setEnabled(enabled)
        self.clear_trial_record_action.setEnabled(bool(self.session and self.session.trial_record))
        suggestion = eligibility_suggestion(self.session.trial_record, applied_edition=self.session.applied_edition)['suggested_type'] if self.session and self.session.trial_record else None
        self.type_combo.setToolTip(f'2018-03 p.2 suggests Type {suggestion}; verify test eligibility.' if suggestion else '')
        for button in (self.add_button, self.remove_button, self.include_button, self.exclude_button):
            button.setEnabled(enabled)
        reviewed = enabled and self.session.all_reviewed
        self.identify_button.setEnabled(reviewed)
        self.save_all_button.setEnabled(reviewed and any(r['decision'] == 'include' for r in rows))
        if select_id:
            for i, row in enumerate(rows):
                if row['id'] == select_id:
                    self.table.selectRow(i)
                    break
        self._selection_changed()

    def _selection_changed(self):
        row = self.selected_row()
        self.item_combo.clear()
        self.item_combo.addItem('Unconfirmed', None)
        self.item_combo.setToolTip(_item_tooltip(row) if row else '')
        if row:
            for item in row['item_candidates']:
                self.item_combo.addItem(item, item)
            if row['identity']['confirmed']:
                self.item_combo.setCurrentText(row['identity']['scenario_id'])
        self.confirm_button.setEnabled(bool(row and row['item_candidates'] and self.session.all_reviewed
                                            and self.session.applied_edition))
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
            self.session.set_context(self.type_combo.currentText(), self.edition_combo.currentData())
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
