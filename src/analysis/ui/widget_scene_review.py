"""Compact scene review inside Step 1; the existing plot edits the range."""
from PySide6.QtCore import Signal, Qt
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QComboBox, QTableWidget, QTableWidgetItem, QAbstractItemView, QHeaderView, QSizePolicy)
from src.analysis.pipeline.intended_contact import feature_options, feature_label, feature_corners


MOTION_LABELS = {'stationary': 'Stationary', 'free_fall': 'Free-fall candidate',
                 'tip_or_rotation': 'Tilt / rotation', 'robot_handling': 'Handling candidate',
                 'tracking_jump': 'Abrupt pose change', 'unclear': 'Unclear'}


def support_cycle_label(cycle):
    """Keep measured phases short; no support-force or test-identity wording."""
    phases = cycle.get('phases', [])
    parts = []
    for key, label in (('rise', 'Rise'), ('fall', 'Fall')):
        ranges = [p for p in phases if p['phase'] == key]
        if len(ranges) == 1:
            a, b = ranges[0]['start_time_s'], ranges[0]['end_time_s']
            parts.append(f'{label} {a:.2f}–{b:.2f} s')
        elif ranges:
            parts.append(f'{label} ({len(ranges)})')
    count = cycle.get('cycle_count', 0)
    if count > 1:
        parts.append(f'{count} returns')
    elif cycle.get('returned') is True:
        parts.append('Returned')
    elif parts:
        parts.append('Return not observed' if cycle.get('returned') is False else 'Return unclear')
    return '   '.join(parts)


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
        self.add_button = QPushButton('Add range')
        self.remove_button = QPushButton('Remove')
        self.include_button = QPushButton('Include')
        self.exclude_button = QPushButton('Exclude')
        for button in (self.detect_button, self.open_review_button, self.save_review_button, self.geometry_button, self.add_button,
                       self.remove_button, self.include_button, self.exclude_button):
            tools.addWidget(button)
        self.motion_summary = QLabel()
        self.motion_summary.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        tools.addStretch()
        self.count_label = QLabel('No scenes')
        tools.addWidget(self.count_label)
        layout.addLayout(tools)
        self.table = QTableWidget(0, 8)
        self.table.setHorizontalHeaderLabels(['Scene', 'Start (s)', 'End (s)', 'Motion', 'Rotation (deg)', 'Review', 'Item', 'Intended contact'])
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
        # Measurements need the row width; the remaining toolbar space clips
        # them when the real Step 1 window uses desktop scaling.
        self.motion_summary.setWordWrap(True)
        layout.addWidget(self.motion_summary)
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
                      feature_label(row['intended_contact']['faces']) if row.get('intended_contact') else '—']
            details = ', '.join(row['tags'])
            if row['left_censored'] or row['right_censored']:
                details += ' Capture boundary or tracking gap cuts this interval.'
            if row['evidence_status'] != 'current':
                labels[3] = 'Re-detect after edit'
            previous = row.get('previous_review')
            if previous and row['decision'] == 'unreviewed':
                labels[5] = 'Review again'
            for j, label in enumerate(labels):
                item = QTableWidgetItem(label)
                item.setToolTip(f"{row['start']!r}–{row['end']!r} s\n{details}" if j < 5 else
                                str(row.get('geometry', {})) + '\n' + row.get('sequence_evidence', '')
                                + '\n' + row.get('eligibility_condition', ''))
                if j == 5 and previous:
                    item.setToolTip('Saved decision: ' + previous['decision'] + '\n'
                                    + '\n'.join(previous['reasons']))
                if j == 7:
                    item.setToolTip('Operator-specified local contact; independent of detected motion/items.'
                                    if row.get('intended_contact') else 'No intended contact specified.')
                self.table.setItem(i, j, item)
        self.table.blockSignals(False)
        self.count_label.setText(f"{sum(r['decision'] != 'unreviewed' for r in rows)} / {len(rows)} reviewed" if rows else 'No scenes')
        enabled = bool(rows)
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
        self._show_motion_geometry(row)
        self.item_combo.clear()
        self.item_combo.addItem('Unconfirmed', None)
        if row:
            self.item_combo.setToolTip(row.get('eligibility_condition', row.get('sequence_evidence', '')))
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

    def _show_motion_geometry(self, row):
        geometry = (row.get('motion_geometry', {}) if row and row['motion'] in
                    ('tip_or_rotation', 'robot_handling', 'unclear') else {})
        status = geometry.get('status')
        edge = geometry.get('pivot_edge')
        names = '–'.join(f'C{i + 1}' for i in edge) if edge else ''
        label = {
            'floor_pivot_compatible': f'Floor pivot candidate {names}',
            'support_unknown': f'Fixed edge {names}',
            'moving_edges': 'No fixed edge',
            'ambiguous_pivot': 'Ambiguous pivot',
            'insufficient_rotation': 'Small rotation',
            'floor_geometry_inconsistent': 'Below registered floor',
        }.get(status, '')
        if label:
            label += f"   Min travel {geometry['min_edge_max_travel_mm']:.2f} mm"
            height = geometry.get('opposite_edge_max_height_mm')
            if height is not None:
                label += f'   Height {height:.2f} mm'
            phases = support_cycle_label(row.get('support_cycle', {}))
            if phases:
                label += '   ' + phases
        self.motion_summary.setText(label)
        self.motion_summary.setVisible(bool(label))
        self.motion_summary.setToolTip(
            str(geometry) + '\n' + str(row.get('support_cycle', {}))
            + '\nObserved geometry; support force and trial intent are unverified.' if label else '')

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
