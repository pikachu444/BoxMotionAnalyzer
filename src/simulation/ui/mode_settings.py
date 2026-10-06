"""Settings drafts for PUB06; applying settings never starts a simulation."""
from copy import deepcopy
import json
import math
from pathlib import Path
from uuid import uuid4

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QTabWidget, QLineEdit, QComboBox, QDoubleSpinBox, QSpinBox,
    QCheckBox, QPushButton, QTableWidget, QTableWidgetItem, QHeaderView,
    QFileDialog, QDialog, QSizePolicy, QTextEdit)
from src.simulation.mode_profiles import (ModeProfiles, drop_step, validate_config,
    read_profiles, save_profiles, BLOCKED_REASON, require_executable)
from src.simulation.robot_profiles import example_plan
from src.simulation.scenarios import Scenarios
from src.simulation.marker_fixtures import load_profile
from src.simulation.profile_document import read_document
from src.utils.marker_profile_identity import profile_identity
from src.utils.marker_profile_identity import digest
from .marker_profile_dialog import MarkerProfileDialog


def preset_steps(category, size, mass):
    # Settings previews use the same two-decimal controls as a selected preset.
    # Batch execution separately retains its original full-precision angles.
    return [drop_step(category, spec.id, Scenarios.calculate_drop_height(category, spec, mass),
        [round(float(v), 2) for v in Scenarios.get_euler_angles(spec, size, category)],
        step_id=f'preset-{index+1}') for index, spec in enumerate(Scenarios.get_drop_sequence_specs(category))]


class ModeSettings(QWidget):
    applied = Signal(object)
    selected = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._refreshing = False
        self._preset_key = None
        self._active_rows = {}
        self._examples = {key: load_profile(example=key) for key in ('18', '32')}
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)
        layout = QVBoxLayout(self); layout.setContentsMargins(0, 0, 0, 0)
        self.mode_label = QLabel(); layout.addWidget(self.mode_label)
        self.tabs = QTabWidget(); layout.addWidget(self.tabs)
        sequence = QWidget(); seq = QVBoxLayout(sequence)
        names = QFormLayout()
        self.sequence_name = QLineEdit(); names.addRow('Sequence profile', self.sequence_name)
        self.robot_model = QComboBox(); self.robot_model.addItem('Gripper proxy', 'gripper_proxy')
        names.addRow('Robot model', self.robot_model); seq.addLayout(names)
        self.handling = QComboBox()
        for label,key in [('Configuration only',None),('Public G airborne','airborne'),
                ('Public H supported 15°','floor_supported'),('Public held only','held_only')]:self.handling.addItem(label,key)
        self.attachment_face = QComboBox();self.attachment_face.addItems(['upward','+X','-X','+Y','-Y','+Z','-Z'])
        self.run_scope = QComboBox();self.run_scope.addItem('Entire plan','entire');self.run_scope.addItem('Selected drop','selected')
        self.run_scope.addItem('Captured selection','captured')
        self.preview_button=QPushButton('Preview sequence');self.preview_button.clicked.connect(self.preview_sequence)
        self.robot_fields=QWidget();fields=QFormLayout(self.robot_fields);fields.setContentsMargins(0,0,0,0)
        row=QHBoxLayout();row.addWidget(self.handling,2);row.addWidget(QLabel('Attach'));row.addWidget(self.attachment_face,1)
        fields.addRow('Handling',row)
        row=QHBoxLayout();row.addWidget(self.run_scope,1);row.addWidget(self.preview_button);fields.addRow('Run scope',row)
        seq.addWidget(self.robot_fields)
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(['Preset', 'Clearance (mm)', 'Fixed X (°)', 'Fixed Y (°)', 'Fixed Z (°)', 'Scope'])
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        for column in range(1, 6): self.table.horizontalHeader().setSectionResizeMode(column, QHeaderView.ResizeToContents)
        self.table.setToolTip('Fixed world XYZ in MuJoCo Z-up; extrinsic xyz degrees.')
        self.table.setFixedHeight(self.table.horizontalHeader().sizeHint().height()
            +5*self.table.verticalHeader().defaultSectionSize()+2*self.table.frameWidth())
        seq.addWidget(self.table)
        actions = QHBoxLayout(); self.order_buttons = []
        for text, action in [('Add drop', self.add_drop), ('Remove', self.remove_drop),
                ('Move up', lambda: self.move_drop(-1)), ('Move down', lambda: self.move_drop(1))]:
            button = QPushButton(text); button.clicked.connect(action); actions.addWidget(button); self.order_buttons.append(button)
        seq.addLayout(actions)
        self.sequence_hint = QLabel(); seq.addWidget(self.sequence_hint)
        self.sequence_preview=QTextEdit();self.sequence_preview.setReadOnly(True);self.sequence_preview.setFixedHeight(120)
        self.sequence_preview.hide();seq.addWidget(self.sequence_preview)
        self.tabs.addTab(sequence, 'Sequence')
        physics = QWidget(); form = QFormLayout(physics)
        self.physics_name = QLineEdit(); form.addRow('Physics profile', self.physics_name)
        self.physics_controls = []
        for label, low, high in [('Mass (kg)', .1, 10000), ('Friction', 0, 5), ('Contact damping', 0, 1),
                ('COM X (mm)', -2500, 2500), ('COM Y (mm)', -2500, 2500), ('COM Z (mm)', -2500, 2500)]:
            control = self.spin(low, high); form.addRow(label, control); self.physics_controls.append(control)
        self.tabs.addTab(physics, 'Physics')
        observation = QWidget(); form = QFormLayout(observation)
        self.observation_name = QLineEdit(); form.addRow('Observation profile', self.observation_name)
        self.corner_enabled = QCheckBox('Gaussian'); form.addRow('Direct corner noise', self.corner_enabled)
        row = QHBoxLayout(); self.corner_std = self.spin(.01, 100); self.corner_seed = QSpinBox(); self.corner_seed.setRange(0, 2147483647)
        row.addWidget(QLabel('Std (mm)')); row.addWidget(self.corner_std); row.addWidget(QLabel('Seed')); row.addWidget(self.corner_seed)
        form.addRow('Corner noise', row)
        self.marker_combo = QComboBox(); self.marker_combo.addItem('Public example 18', '18'); self.marker_combo.addItem('Public example 32', '32')
        row = QHBoxLayout(); row.addWidget(self.marker_combo, 1)
        for text, action in [('Import layout…', self.import_marker), ('Edit marker layout…', self.edit_marker)]:
            button = QPushButton(text); button.clicked.connect(action); row.addWidget(button)
        form.addRow('Marker profile', row)
        self.use_layout_box = QCheckBox('Use layout box dimensions'); form.addRow('', self.use_layout_box)
        self.fault_kind = QComboBox()
        for label, key in [('None', None), ('Missing samples', 'missing'), ('Local 180° half-turn', 'flip_180_local_axis'), ('Gaussian noise', 'gaussian_noise')]: self.fault_kind.addItem(label, key)
        form.addRow('Marker faults', self.fault_kind)
        self.channel = QComboBox(); self.channel.addItem('Solved rigid-body markers', 'rigid_body_markers'); self.channel.addItem('Physical markers', 'physical_markers')
        form.addRow('Marker channel', self.channel)
        row = QHBoxLayout(); self.start = self.spin(0, 60, 4); self.end = self.spin(0, 60, 4)
        row.addWidget(self.start); row.addWidget(self.end); form.addRow('Recorded interval (s)', row)
        row = QHBoxLayout(); self.axis = QComboBox(); self.axis.addItems(['X', 'Y', 'Z']); self.marker_std = self.spin(.001, 100, 3)
        row.addWidget(QLabel('Local axis')); row.addWidget(self.axis); row.addWidget(QLabel('Std (mm)')); row.addWidget(self.marker_std); form.addRow('Marker fault', row)
        self.marker_seed = QSpinBox(); self.marker_seed.setRange(0, 2147483647); form.addRow('Marker seed', self.marker_seed)
        self.tabs.addTab(observation, 'Markers and noise')
        self.status = QLabel('Current preset plan; ISTA procedure validation is pending.'); self.status.setWordWrap(True); self.status.setTextFormat(Qt.PlainText); layout.addWidget(self.status)
        actions = QHBoxLayout()
        self.open_button = QPushButton('Open settings…'); self.open_button.clicked.connect(self.open_settings); actions.addWidget(self.open_button)
        self.save_button = QPushButton('Save settings…'); self.save_button.clicked.connect(self.save_settings); actions.addWidget(self.save_button)
        actions.addStretch()
        self.apply_button = QPushButton('Use in Simulation'); self.apply_button.clicked.connect(self.apply_settings); actions.addWidget(self.apply_button)
        self.cancel_button = QPushButton('Cancel'); self.cancel_button.clicked.connect(self.cancel_settings); actions.addWidget(self.cancel_button)
        layout.addLayout(actions)
        self.table.itemSelectionChanged.connect(self.select_row)
        self.table.cellChanged.connect(lambda row, column: self.select_row() if column in (1, 2, 3, 4) else None)
        self.table.cellChanged.connect(self.invalidate_sequence_preview)
        self.marker_combo.currentIndexChanged.connect(self.change_marker)
        self.corner_enabled.toggled.connect(self.fault_controls)
        self.fault_kind.currentIndexChanged.connect(self.fault_controls)
        self.tabs.currentChanged.connect(self.fit_tab)
        for control in self.findChildren(QWidget):
            if isinstance(control,(QDoubleSpinBox,QSpinBox)):control.valueChanged.connect(self.invalidate_sequence_preview)
            elif isinstance(control,QLineEdit):control.textChanged.connect(self.invalidate_sequence_preview)
            elif isinstance(control,QComboBox):control.currentIndexChanged.connect(self.invalidate_sequence_preview)
            elif isinstance(control,QCheckBox):control.toggled.connect(self.invalidate_sequence_preview)
        self.fit_tab()

    def fit_tab(self):
        page = self.tabs.currentWidget()
        page.layout().activate()
        height = page.layout().sizeHint().height()+self.tabs.tabBar().sizeHint().height()+4
        self.tabs.setFixedHeight(height)
        self.layout().activate()
        self.setMaximumHeight(self.layout().sizeHint().height())

    @staticmethod
    def spin(low, high, decimals=2):
        control = QDoubleSpinBox(); control.setRange(low, high); control.setDecimals(decimals); return control

    def reset(self, state):
        self.live_state = state
        # Live state is already validated at mutation boundaries. Avoid replaying
        # its whole history or rehashing marker geometry on every spinbox edit.
        self.draft = deepcopy(state)
        self.show_config()

    def show_config(self):
        self._refreshing = True
        config = self.draft.configs[self.draft.mode]; robot = config['mode'] == 'robot_sequence'
        self.start.setMaximum(3600 if robot else 60);self.end.setMaximum(3600 if robot else 60)
        sequence = config['sequence_profile']; physics = config['physics_profile']; observation = config['observation_profile']
        plan=sequence.get('execution_plan')
        self.robot_fields.setVisible(robot);self.preview_button.setVisible(robot)
        self.handling.setCurrentIndex(self.handling.findData(plan['handling_family'] if plan else None))
        self.attachment_face.setCurrentText(plan['attachment_face'] if plan else 'upward')
        scope=(1 if len(plan['selected_step_ids'])==1 and len(sequence['steps'])>1 else
            2 if plan['selected_step_ids']!=[s['step_id'] for s in sequence['steps']] else 0) if plan else 0
        self.run_scope.model().item(2).setEnabled(plan is not None)
        self.run_scope.setItemText(2,f"Captured selection ({len(plan['selected_step_ids'])} / {len(sequence['steps'])})" if plan else 'Captured selection')
        self.run_scope.setItemData(2,', '.join(plan['selected_step_ids']) if plan else '',Qt.ToolTipRole)
        self.run_scope.setCurrentIndex(scope)
        self.sequence_preview.hide();self._preview_signature=None;self._preview_plan=None;self._preview_duration=config['duration_s']
        self.mode_label.setText('Robot sequence' if robot else 'Single drop')
        self.sequence_name.setText(sequence['profile_id']); self.robot_model.setEnabled(robot)
        for button in self.order_buttons: button.setEnabled(robot)
        selected = sequence['steps'][0]
        key = (selected['category'], tuple(config['size_mm']), physics['mass_kg'])
        if not robot and key != self._preset_key:
            self._preset_rows = preset_steps(*key); self._preset_key = key
        self.rows = deepcopy(sequence['steps'] if robot else self._preset_rows)
        active = min(self._active_rows.get(self.draft.mode, 0), len(self.rows)-1) if robot else next(i for i, step in enumerate(self.rows) if step['preset_id'] == selected['preset_id'])
        if robot and plan and self.run_scope.currentData()=='selected':active=next(i for i,s in enumerate(self.rows) if s['step_id']==plan['selected_step_ids'][0])
        if not robot: self.rows[active] = deepcopy(selected)
        self._paint_rows(active)
        self.physics_name.setText(physics['profile_id'])
        for control, value in zip(self.physics_controls, [physics['mass_kg'], physics['friction'], physics['contact_damping_control'], *physics['com_offset_mm']]): control.setValue(value)
        self.observation_name.setText(observation['profile_id'])
        corner = observation['corner']; self.corner_enabled.setChecked(corner['enabled']); self.corner_std.setValue(corner['std_mm']); self.corner_seed.setValue(corner['seed'])
        self.marker = deepcopy(observation['marker']); self._select_marker_name()
        self.use_layout_box.setChecked(self.marker['use_layout_box']); self.marker_seed.setValue(self.marker['seed'])
        fault = self.marker['faults']; self.fault_kind.setCurrentIndex(self.fault_kind.findData(fault['kind'])); self.channel.setCurrentIndex(self.channel.findData(fault['channel']))
        self.axis.setCurrentText(fault['axis']); self.start.setValue(fault['start']); self.end.setValue(fault['end']); self.marker_std.setValue(fault['std_mm'])
        self._refreshing = False; self.fault_controls(); self.fit_tab(); self.select_row()
        if robot and plan:
            try:
                require_executable(config);self._preview_signature=self._sequence_signature(self._base_candidate());self._preview_plan=deepcopy(plan)
            except ValueError:pass

    def _paint_rows(self, active):
        self.table.blockSignals(True); self.table.setRowCount(len(self.rows))
        for row, step in enumerate(self.rows):
            spec = next(item for item in Scenarios.get_drop_sequence_specs(step['category']) if item.id == step['preset_id'])
            plan=self.draft.configs[self.draft.mode]['sequence_profile'].get('execution_plan')
            virtual_support=plan and plan['handling_family']=='floor_supported' and step['step_id'] in plan['selected_step_ids']
            scope = ('Hazard block unavailable' if spec.variant == 'hazard_face2' else
                'Virtual support; ISTA unverified' if virtual_support else
                'Supported motion unavailable' if spec.kind in ('tip', 'rotational_edge') else 'Free-fall preset')
            for column, value in enumerate([step['preset_id'].replace('_', ' '), step['clearance_mm'], *step['fixed_xyz_deg'], scope]):
                text = f'{value:g}' if isinstance(value, (int, float)) else value
                item = self.table.item(row, column)
                if item is None:
                    item = QTableWidgetItem(text); self.table.setItem(row, column, item)
                    if column in (0, 5): item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                elif item.text() != text: item.setText(text)
        self.table.selectRow(active); self.table.blockSignals(False)
        self._active_rows[self.draft.mode] = active
        robot = self.draft.mode == 'robot_sequence'
        plan=self.draft.configs[self.draft.mode]['sequence_profile'].get('execution_plan')
        self.sequence_hint.setText((f"{len(plan['selected_step_ids'])} selected / {len(self.rows)} planned drops." if plan else
            f'{len(self.rows)} planned drops. Preview a handling profile before execution.') if robot else
            f'1 selected / {len(self.rows)} presets. Use in Simulation to run this preset.')

    def read_rows(self):
        rows = deepcopy(self.rows)
        for row, step in enumerate(rows):
            values = []
            for column in range(1, 5):
                try:
                    value = float(self.table.item(row, column).text())
                    if not math.isfinite(value): raise ValueError('must be finite')
                    low, high = (10, 10000) if column == 1 else (-180, 180)
                    if not low <= value <= high: raise ValueError(f'must be between {low} and {high}')
                except (ValueError, AttributeError) as error:
                    self.table.blockSignals(True); self.table.setCurrentCell(row, column)
                    self.table.scrollToItem(self.table.item(row, column)); self.table.blockSignals(False)
                    self.table.setFocus()
                    self.selected.emit(None)  # Retain and identify the last valid preview.
                    label = 'clearance' if column == 1 else 'Fixed '+('XYZ'[column-2])
                    raise ValueError(f'Drop {row+1} {label} {error}.') from error
                values.append(value)
            step['clearance_mm'] = values[0]; step['fixed_xyz_deg'] = values[1:]
        return rows

    def _base_candidate(self):
        config = deepcopy(self.draft.configs[self.draft.mode]); rows = self.read_rows()
        config['sequence_profile']['profile_id'] = self.sequence_name.text().strip()
        config['sequence_profile']['steps'] = rows if self.draft.mode == 'robot_sequence' else [rows[max(0, self.table.currentRow())]]
        physics = config['physics_profile']; physics['profile_id'] = self.physics_name.text().strip()
        values = [control.value() for control in self.physics_controls]
        physics.update(mass_kg=values[0], friction=values[1], contact_damping_control=values[2], com_offset_mm=values[3:])
        observation = config['observation_profile']; observation['profile_id'] = self.observation_name.text().strip()
        observation['corner'] = dict(enabled=self.corner_enabled.isChecked(), std_mm=self.corner_std.value(), seed=self.corner_seed.value())
        marker = deepcopy(self.marker); marker.update(seed=self.marker_seed.value(), use_layout_box=self.use_layout_box.isChecked(),
            faults=dict(kind=self.fault_kind.currentData(), channel=self.channel.currentData(), axis=self.axis.currentText(), start=self.start.value(), end=self.end.value(), std_mm=self.marker_std.value()))
        observation['marker'] = marker
        return validate_config(config)

    def _sequence_signature(self,config):
        return digest(dict(config=config,handling=self.handling.currentData(),face=self.attachment_face.currentText(),
            selection=self._selected_ids(config)))

    def _selected_ids(self,config):
        if self.run_scope.currentData()=='selected':return [config['sequence_profile']['steps'][max(0,self.table.currentRow())]['step_id']]
        if self.run_scope.currentData()=='captured':
            plan=config['sequence_profile'].get('execution_plan')
            if plan is None:raise ValueError('Choose an explicit run scope.')
            return list(plan['selected_step_ids'])
        return [s['step_id'] for s in config['sequence_profile']['steps']]

    def candidate(self):
        config=self._base_candidate()
        if config['mode']=='robot_sequence':
            if self.handling.currentData() is None:config['sequence_profile'].pop('execution_plan',None)
            elif self._preview_signature!=self._sequence_signature(config):
                raise ValueError('Plan changed. Preview sequence before applying or saving.')
            else:
                config['sequence_profile']['execution_plan']=deepcopy(self._preview_plan)
                config['duration_s']=self._preview_duration
        return validate_config(config)

    def invalidate_sequence_preview(self,*_):
        if self._refreshing:return
        self._preview_signature=None
        if self.sequence_preview.isVisible():self.sequence_preview.setPlainText('Preview is out of date. Preview sequence again.')

    def preview_sequence(self):
        try:
            config=self._base_candidate();family=self.handling.currentData()
            if family is None:raise ValueError(BLOCKED_REASON)
            selected=self._selected_ids(config)
            existing=config['sequence_profile'].get('execution_plan')
            if (existing and existing['handling_family']==family and existing['attachment_face']==self.attachment_face.currentText()
                    and existing['selected_step_ids']==selected):
                try:require_executable(config);plan=deepcopy(existing)
                except ValueError:plan=example_plan(config,family=family,attachment_face=self.attachment_face.currentText(),selected_step_ids=selected)
            else:plan=example_plan(config,family=family,attachment_face=self.attachment_face.currentText(),selected_step_ids=selected)
            self._preview_signature=self._sequence_signature(config);self._preview_plan=plan
            limits=plan['transition'];physics=plan['physics']
            if plan==existing:self._preview_duration=config['duration_s']
            else:
                budget=sum(p['duration_s'] for p in plan['phases'])
                budget+=limits['timeout_s']*sum(p['kind'] in ('approach','lift','orient','hold','floor_move','flip','contact','settle') for p in plan['phases'])
                budget+=sum(limits['timeout_s']+limits['retries']*(p['duration_s']+limits['timeout_s']) for p in plan['phases'] if p['kind'] in ('attach','pickup'))
                self._preview_duration=max(config['duration_s'],min(3600.,math.ceil(budget+1)))
            lines=[f"{len(selected)} / {len(config['sequence_profile']['steps'])} planned drops; {family}; face {plan['attachment_face']}.",
                f"Run time limit: {self._preview_duration:g} s. Phase durations total {sum(p['duration_s'] for p in plan['phases']):g} s; tracking/settle may take longer.",
                f"Attach: sphere {physics['radius_mm']:g} mm; distance ≤ {limits['distance_mm']:g} mm, normal ≤ {limits['normal_deg']:g}°, speed ≤ {limits['relative_speed_mm_s']:g} mm/s."]
            for step_id in selected:
                phases=[p for p in plan['phases'] if p['step_id']==step_id]
                motions=[str(p.get('target_xyz_deg')) for p in phases if 'target_xyz_deg' in p]
                pivots=[str(p['support_pivot_local_mm']) for p in phases if 'support_pivot_local_mm' in p]
                lines.append(f"{step_id}: {' / '.join(p['kind'] for p in phases)}; XYZ {', '.join(motions) or 'unchanged'}"+
                    (f"; support edge mm {', '.join(pivots)}" if pivots else ''))
            if plan['omitted_step_ids']:lines.append('Omitted: '+', '.join(plan['omitted_step_ids']))
            lines.append('Virtual handling conditions; experimental approval is not evaluated.')
            self.sequence_preview.setPlainText('\n'.join(lines));self.status.setText('Preview ready. Use in Simulation to apply.')
        except ValueError as error:
            self._preview_signature=None;self.sequence_preview.setPlainText(str(error));self.status.setText('Sequence cannot be applied.')
        self.sequence_preview.show();self.fit_tab()

    def select_row(self):
        if self._refreshing or self.table.currentRow() < 0: return
        old=self._active_rows.get(self.draft.mode)
        self._active_rows[self.draft.mode] = self.table.currentRow()
        if self.draft.mode=='robot_sequence' and self.run_scope.currentData()=='selected' and old!=self.table.currentRow():self.invalidate_sequence_preview()
        try: self.selected.emit(self.read_rows()[self.table.currentRow()])
        except ValueError as error: self.status.setText(str(error))

    def add_drop(self):
        try: self.rows = self.read_rows()
        except ValueError as error: self.status.setText(str(error)); return
        row = max(0, self.table.currentRow()); step = deepcopy(self.rows[row]); step['step_id'] = 'drop-'+uuid4().hex
        self.rows.insert(row+1, step); self._paint_rows(row+1)

    def remove_drop(self):
        if len(self.rows) == 1: self.status.setText('Keep at least one planned drop.'); return
        try: self.rows = self.read_rows()
        except ValueError as error: self.status.setText(str(error)); return
        row = max(0, self.table.currentRow()); self.rows.pop(row); self._paint_rows(min(row, len(self.rows)-1)); self.select_row()

    def move_drop(self, delta):
        row = self.table.currentRow(); target = row+delta
        if not 0 <= target < len(self.rows): return
        try: self.rows = self.read_rows()
        except ValueError as error: self.status.setText(str(error)); return
        self.rows[row], self.rows[target] = self.rows[target], self.rows[row]; self._paint_rows(target); self.select_row()

    def fault_controls(self):
        enabled = self.fault_kind.currentData() is not None
        for control in (self.channel, self.start, self.end): control.setEnabled(enabled)
        self.axis.setEnabled(self.fault_kind.currentData() == 'flip_180_local_axis')
        self.marker_std.setEnabled(self.fault_kind.currentData() == 'gaussian_noise')
        self.corner_std.setEnabled(self.corner_enabled.isChecked()); self.corner_seed.setEnabled(self.corner_enabled.isChecked())

    def _select_marker_name(self):
        profile = self.marker['profile']; key = next((key for key, value in self._examples.items() if profile == value), 'custom')
        if key == 'custom':
            index = self.marker_combo.findData(key)
            if index < 0: self.marker_combo.addItem('Custom: '+profile['profile_id'], key)
            else: self.marker_combo.setItemText(index, 'Custom: '+profile['profile_id'])
        self.marker_combo.setCurrentIndex(self.marker_combo.findData(key))

    def change_marker(self):
        if self._refreshing or self.marker_combo.currentData() == 'custom': return
        profile = deepcopy(self._examples[self.marker_combo.currentData()]); self.marker.update(profile=profile, identity=profile_identity(profile), document=None)

    def edit_marker(self):
        editor = MarkerProfileDialog(self.marker['profile'], document=self.marker['document'],
            copy_source=self.marker_combo.currentData() != 'custom', parent=self)
        try:
            if editor.exec() == QDialog.Accepted:
                profile = deepcopy(editor.state.applied); self.marker.update(profile=profile, identity=profile_identity(profile), document=editor.state.document())
                self._refreshing = True; self._select_marker_name(); self._refreshing = False
        finally: editor.deleteLater()

    def import_marker(self):
        path, _ = QFileDialog.getOpenFileName(self, 'Import marker layout', '', 'JSON files (*.json)')
        if not path: return
        try:
            value = json.loads(Path(path).read_text(encoding='utf-8-sig'))
            document = read_document(path).document() if value.get('object_type') == 'MarkerProfileDocument' else None
            profile = load_profile(path); self.marker.update(profile=profile, identity=profile_identity(profile), document=document)
            self._refreshing = True; self._select_marker_name(); self._refreshing = False
        except (OSError, ValueError, TypeError, AttributeError, KeyError) as error: self.status.setText(str(error))

    def apply_settings(self):
        try: self.draft.set_config(self.candidate())
        except ValueError as error: self.status.setText(str(error)+' Changes were not applied.'); return
        self.applied.emit(ModeProfiles.from_document(self.draft.document()))
        config=self.draft.configs[self.draft.mode]
        self.status.setText('Settings applied. '+(BLOCKED_REASON if self.draft.mode=='robot_sequence' and 'execution_plan' not in config['sequence_profile'] else ''))

    def cancel_settings(self):
        self.reset(self.live_state); self.status.setText('Changes cancelled. Previous results are preserved.')

    def open_settings(self):
        path, _ = QFileDialog.getOpenFileName(self, 'Open simulation settings', '', 'JSON files (*.json)')
        if not path: return
        try: candidate = read_profiles(path)
        except (OSError, ValueError, TypeError, KeyError) as error: self.status.setText(str(error)+' Settings were not loaded.'); return
        self.draft = candidate; self.show_config()
        size = candidate.configs[candidate.mode]['size_mm']
        self.status.setText('Loaded box: '+' × '.join(f'{v:g}' for v in size)+' mm. Use in Simulation to apply.')

    def save_settings(self):
        try:
            candidate = ModeProfiles.from_document(self.draft.document()); candidate.set_config(self.candidate())
            path, _ = QFileDialog.getSaveFileName(self, 'Save simulation settings', '', 'JSON files (*.json)')
            if path: save_profiles(path, candidate); self.status.setText('Settings saved. Simulation inputs are unchanged.')
        except (OSError, ValueError, TypeError, KeyError) as error: self.status.setText(str(error)+' Settings were not saved.')
