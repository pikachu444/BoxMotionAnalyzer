"""PUB06 review-only Qt mockups. No production actions or output generation."""
import argparse
import json
import os
from pathlib import Path
import sys
import math
import hashlib
import subprocess
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QComboBox, QPushButton, QTabWidget, QFormLayout, QDoubleSpinBox,
    QTableWidget, QTableWidgetItem, QHeaderView, QLineEdit, QGroupBox, QSpinBox)
from src.simulation.ui.main_window import SimulationUI
from src.simulation.scenarios import Scenarios


class MockSimulation(SimulationUI):
    configuration_changed=Signal()

    def _update_custom_fields_from_scenario(self):
        super()._update_custom_fields_from_scenario()
        # Legacy preset/reset updates intentionally block individual controls.
        # Publish the completed snapshot rather than waiting for those signals.
        self.configuration_changed.emit()

    def __init__(self, mode='single_drop', state='default', category=None):
        super().__init__()
        self.setWindowTitle('Simulation — #139 mockup')
        self._single_controls=None
        self.scenario_group=self.drop_combo.parentWidget()
        # Reuse the existing painter and preset target semantics. Detach the
        # preview from the scenario form before any mode hides its controls.
        self.scenario_group.layout().takeRow(self.orientation_preview)
        self.orientation_preview.setParent(None)
        if category is not None:self.cat_combo.setCurrentIndex(Scenarios.CATEGORIES.index(category))
        row = QHBoxLayout()
        row.addWidget(QLabel('Mode'))
        self.mode = QComboBox()
        self.mode.addItem('Single drop', 'single_drop')
        self.mode.addItem('Robot sequence', 'robot_sequence')
        self.mode.setCurrentIndex(mode == 'robot_sequence')
        row.addWidget(self.mode, 1)
        self.profiles_button=QPushButton('Settings…');row.addWidget(self.profiles_button)
        self.profiles_button.setToolTip('Optional: save or load settings. Single drop runs with the controls below.')
        self.layout.insertLayout(1, row)
        self.mode_hint=QLabel('');self.mode_hint.setWordWrap(True)
        self.layout.insertWidget(2,self.mode_hint);self.mode_hint.hide()
        self.result = QLabel('')
        self.result.setWordWrap(True)
        self.layout.insertWidget(self.layout.count()-2, self.result)
        self.sequence_summary = QGroupBox('Sequence')
        summary = QVBoxLayout(self.sequence_summary)
        self.sequence_drop=QComboBox()
        self.sequence_drop.addItems([spec.id for spec in Scenarios.get_drop_sequence_specs(self.cat_combo.currentData())])
        summary.addWidget(self.sequence_drop)
        summary.addWidget(QLabel('Edit order and initial pose in Settings…'))
        self.sequence_drop.currentIndexChanged.connect(self._update_orientation_preview)
        self.form_layout.insertWidget(1, self.sequence_summary)
        self.sequence_summary.hide()
        self.cancel_run = QPushButton('Cancel')
        self.cancel_run.hide()
        self.layout.insertWidget(self.layout.count()-1, self.cancel_run)
        for button in (self.run_btn, self.batch_btn, self.marker_btn):
            button.clicked.disconnect()
        self.mode.currentIndexChanged.connect(self.change_mode)
        if mode == 'robot_sequence': self.change_mode()
        if state == 'returned':
            self.drop_combo.setCurrentIndex(2)
            self.custom_h_input.setValue(123.0)
            self.custom_y_input.setValue(17.0)
            self.result.setText('Previous result: single-drop-01.proc')
        elif state == 'cancelled':
            self.result.setText('Cancelled. Previous result: single-drop-01.proc')
        elif state == 'running':
            self.result.setText('Running… Previous result: single-drop-01.proc')
            self.progress_bar.show(); self.progress_bar.setValue(46)
            self.cancel_run.show()
            self.mode.setEnabled(False);self.profiles_button.setEnabled(False);self.form_scroll.setEnabled(False)
            for button in (self.run_btn,self.batch_btn,self.marker_btn): button.setEnabled(False)
        elif state == 'blocked':
            self.result.setText('Sequence simulation is not implemented. Previous results are preserved.')
        self.result.setVisible(bool(self.result.text()))
        self.layout.addStretch()
        self._fit_form()

    def _update_orientation_preview(self):
        if not hasattr(self,'mode') or self.mode.currentData()!='robot_sequence':
            return super()._update_orientation_preview()
        index=self.sequence_drop.currentIndex()
        category=self.cat_combo.currentData()
        spec=Scenarios.get_drop_sequence_specs(category)[index]
        box_size=(self.w_input.value(),self.d_input.value(),self.h_input.value())
        euler=tuple(round(float(value),2) for value in Scenarios.get_euler_angles(spec,box_size,category))
        height=Scenarios.calculate_drop_height(category,spec,self.mass_input.value())
        # Display the configured active row in the same Scenario form. These
        # read-only robot controls never replace the saved single-drop values.
        self.drop_combo.blockSignals(True);self.drop_combo.setCurrentIndex(index);self.drop_combo.blockSignals(False)
        for control,value in zip((self.custom_h_input,self.custom_r_input,self.custom_p_input,self.custom_y_input),
                (height,*euler)):
            control.blockSignals(True);control.setValue(value);control.blockSignals(False)
        self.warning_label.hide()
        self.orientation_preview.set_preview_state(
            (self.w_input.value(),self.d_input.value(),self.h_input.value()),
            euler,spec,category)

    def _on_cat_changed(self):
        super()._on_cat_changed()
        if hasattr(self,'sequence_drop'):
            self.sequence_drop.blockSignals(True);self.sequence_drop.clear()
            self.sequence_drop.addItems([spec.id for spec in Scenarios.get_drop_sequence_specs(self.cat_combo.currentData())])
            self.sequence_drop.blockSignals(False)

    def _fit_form(self):
        # Review the actual content height, not a maximized empty scroll area.
        # A smaller window keeps scrolling; the primary actions stay reachable.
        self.form_layout.activate()
        height=self.form_layout.sizeHint().height()+2*self.form_scroll.frameWidth()
        self.form_scroll.widget().setMinimumHeight(self.form_layout.sizeHint().height())
        self.form_scroll.setMaximumHeight(height)
        self.layout.setAlignment(Qt.AlignTop)

    def content_height(self):
        self._fit_form()
        form_height=self.form_layout.sizeHint().height()+2*self.form_scroll.frameWidth()
        return self.layout.sizeHint().height()-self.form_scroll.sizeHint().height()+form_height

    def change_mode(self):
        robot = self.mode.currentData() == 'robot_sequence'
        if robot and self._single_controls is None:
            self._single_controls=(self.drop_combo.currentIndex(),tuple(c.value() for c in
                (self.custom_h_input,self.custom_r_input,self.custom_p_input,self.custom_y_input)))
        elif not robot and self._single_controls is not None:
            index,values=self._single_controls
            self.drop_combo.blockSignals(True);self.drop_combo.setCurrentIndex(index);self.drop_combo.blockSignals(False)
            for control,value in zip((self.custom_h_input,self.custom_r_input,self.custom_p_input,self.custom_y_input),values):
                control.blockSignals(True);control.setValue(value);control.blockSignals(False)
            self._single_controls=None
            self._check_for_modifications()
        self.scenario_group.show()
        self.sequence_summary.hide()
        for control in (self.cat_combo,self.drop_combo,self.custom_h_input,self.rotation_section):control.setEnabled(not robot)
        self.mode_hint.setText('Configure and save drop order in Settings… Execution is not available yet.' if robot else '')
        self.mode_hint.hide()
        for button in (self.run_btn,self.batch_btn,self.marker_btn):
            button.setEnabled(not robot)
            button.setToolTip('Sequence simulation is not implemented.' if robot else '')
        self.result.setText('')
        self._update_orientation_preview()
        self._fit_form()

    def closeEvent(self,event):
        # Review-only states have no live worker and must not inherit its close gate.
        event.accept()


class MockProfiles(QWidget):
    def __init__(self, mode='single_drop', invalid=False, source=None):
        super().__init__()
        self.source=source;self.initial_mode=mode;self.invalid=invalid
        self._last_mode=mode;self._names={}
        category=source.cat_combo.currentData() if source else Scenarios.CATEGORIES[0]
        specs=Scenarios.get_drop_sequence_specs(category)
        type_name='Type H' if 'Type H' in category else 'Type G'
        self.setWindowTitle('Simulation settings — #139 mockup')
        layout = QVBoxLayout(self)
        top = QHBoxLayout(); top.addWidget(QLabel('Mode'))
        self.mode = QLabel('Single drop' if mode=='single_drop' else 'Robot sequence')
        top.addWidget(self.mode,1)
        layout.addLayout(top)
        self.tabs = QTabWidget(); layout.addWidget(self.tabs)
        sequence = QWidget(); seq = QVBoxLayout(sequence)
        names = QFormLayout(); self.name = QLineEdit(f'Current {type_name} presets' if mode=='robot_sequence' else 'Current single drop')
        names.addRow('Sequence profile',self.name)
        robot = QComboBox();self.robot_model=robot; robot.addItem('Gripper proxy'); names.addRow('Robot model',robot)
        robot.setEnabled(mode=='robot_sequence'); seq.addLayout(names)
        self.table = QTableWidget(len(specs),6)
        self.table.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.table.setHorizontalHeaderLabels(['Preset','Clearance (mm)','Fixed X (°)','Fixed Y (°)','Fixed Z (°)','Scope'])
        self.table.setToolTip('Fixed world XYZ in MuJoCo Z-up; extrinsic xyz degrees. Not a marker-local half turn.')
        self.table.horizontalHeader().setSectionResizeMode(0,QHeaderView.Stretch)
        for c in range(1,6): self.table.horizontalHeader().setSectionResizeMode(c,QHeaderView.ResizeToContents)
        box_size=(source.w_input.value(),source.d_input.value(),source.h_input.value()) if source else (1578.,930.,142.)
        mass=source.mass_input.value() if source else 25.
        self._preset_key=(mode,category,box_size,mass);self._last_active=source.drop_combo.currentIndex() if source else 0
        rows=[[spec.id.replace('_',' '),f'{Scenarios.calculate_drop_height(category,spec,mass):g}',
            *[f'{value:.2f}' for value in Scenarios.get_euler_angles(spec,box_size,category)],
            'Hazard block unavailable' if spec.variant=='hazard_face2' else
            'Supported motion unavailable' if spec.kind in ('tip','rotational_edge') else 'Free-fall preset'] for spec in specs]
        if mode=='single_drop' and source is not None:
            active=source.drop_combo.currentIndex()
            rows[active]=[source.cat_combo.currentText()+' / '+source.drop_combo.currentText(),*[f'{control.value():g}' for control in
                (source.custom_h_input,source.custom_r_input,source.custom_p_input,source.custom_y_input)],rows[active][-1]]
        for r in range(self.table.rowCount()):
            for c,text in enumerate(rows[r]): self.table.setItem(r,c,QTableWidgetItem(text))
        if invalid:
            self.table.item(1,1).setText('NaN')
            self.table.item(1,1).setBackground(Qt.GlobalColor.yellow)
        # Both modes show the same preset browser; single execution uses only
        # the selected row. Extra rows never become extra planned single drops.
        visible_rows=5
        self.table.setFixedHeight(self.table.horizontalHeader().height()+2*self.table.frameWidth()
            +visible_rows*self.table.rowHeight(0))
        seq.addWidget(self.table)
        actions=QHBoxLayout()
        self.order_buttons=[]
        for text in ('Add drop','Remove','Move up','Move down'):
            button=QPushButton(text); button.setEnabled(mode=='robot_sequence'); actions.addWidget(button);self.order_buttons.append(button)
        seq.addLayout(actions)
        self.sequence_hint=QLabel(f'{len(specs)} preset steps. Sequence execution unavailable (#140).' if mode=='robot_sequence' else f'1 selected / {len(specs)} presets. Run selected preset only.')
        seq.addWidget(self.sequence_hint)
        self.tabs.addTab(sequence,'Sequence')
        physics=QWidget(); form=QFormLayout(physics)
        form.addRow('Physics profile',QLineEdit('Current physics'))
        for label,value,low,high in [('Mass (kg)',25,.1,10000),('Friction',.5,0,5),('Contact damping',.15,0,1),('COM X (mm)',0,-2500,2500),('COM Y (mm)',-200,-2500,2500),('COM Z (mm)',0,-2500,2500)]:
            control=QDoubleSpinBox(); control.setRange(low,high); control.setValue(value); form.addRow(label,control)
        self.tabs.addTab(physics,'Physics')
        observation=QWidget(); form=QFormLayout(observation)
        form.addRow('Observation profile',QLineEdit('Current observations'))
        for label,choices in [('Direct corner noise',['Off','Gaussian']),('Marker profile',['Public example 18','Public example 32','Custom']),('Marker faults',['None','Missing samples','Local 180° half-turn','Gaussian noise'])]:
            combo=QComboBox(); combo.addItems(choices)
            if label=='Marker profile':
                self.marker_profile=combo;marker_row=QHBoxLayout();marker_row.addWidget(combo,1)
                for title in ('Import layout…','Edit marker layout…'):
                    button=QPushButton(title);marker_row.addWidget(button)
                    if title=='Edit marker layout…':button.clicked.connect(self.edit_marker)
                form.addRow(label,marker_row)
            else:form.addRow(label,combo)
        corner=QHBoxLayout();corner_std=QDoubleSpinBox();corner_std.setValue(1);corner_std.setSuffix(' mm');corner_std.setEnabled(False)
        corner.addWidget(QLabel('Std'));corner.addWidget(corner_std);corner.addWidget(QLabel('Seed 0'));form.addRow('Corner noise',corner)
        channel=QComboBox();channel.addItems(['Solved rigid-body markers','Physical markers']);channel.setEnabled(False);form.addRow('Marker channel',channel)
        interval=QHBoxLayout()
        for value in (.24,.32):
            time=QDoubleSpinBox();time.setDecimals(4);time.setValue(value);time.setSuffix(' s');time.setEnabled(False);interval.addWidget(time)
        form.addRow('Recorded interval',interval)
        fault=QHBoxLayout();axis=QComboBox();axis.addItems(['X','Y','Z']);axis.setEnabled(False)
        fault.addWidget(QLabel('Local axis'));fault.addWidget(axis)
        std=QDoubleSpinBox();std.setDecimals(3);std.setValue(.02);std.setSuffix(' mm');std.setEnabled(False)
        fault.addWidget(QLabel('Std'));fault.addWidget(std);form.addRow('Marker fault',fault)
        seed=QSpinBox();seed.setMaximum(2147483647);seed.setValue(74082);form.addRow('Marker seed',seed)
        self.tabs.addTab(observation,'Markers and noise')
        self.status=QLabel('Drop 2 clearance must be finite. Changes were not applied.' if invalid else 'Current preset plan; ISTA procedure validation is pending.')
        self.status.setWordWrap(True)
        if invalid:self.status.setStyleSheet('color: #a32919;')
        layout.addWidget(self.status)
        buttons=QHBoxLayout()
        for text in ('Open settings…','Save settings…'):
            button=QPushButton(text); button.setEnabled(not invalid or text=='Open settings…');buttons.addWidget(button)
        buttons.addStretch()
        self.apply=QPushButton('Use in Simulation'); self.apply.setEnabled(not invalid);buttons.addWidget(self.apply)
        self.apply.setToolTip('Use these settings in Simulation. This does not save a file or run a simulation.')
        self.cancel=QPushButton('Cancel');buttons.addWidget(self.cancel);layout.addLayout(buttons)
        layout.addStretch()
        self.setMinimumWidth(820)
        layout.setAlignment(Qt.AlignTop)
        self.tabs.currentChanged.connect(self._fit_tab)
        self._fit_tab()
        self.resize(820,self.content_height())

    def refresh(self):
        if self.source is None:return
        source=self.source;mode=source.mode.currentData();robot=mode=='robot_sequence'
        if mode!=self._last_mode:
            self._names[self._last_mode]=self.name.text()
            self.name.setText(self._names.get(mode,'Current '+source.cat_combo.currentText()+' presets' if robot else 'Current single drop'))
            self._last_mode=mode
        self.mode.setText('Robot sequence' if robot else 'Single drop')
        self.robot_model.setEnabled(robot)
        for button in self.order_buttons:button.setEnabled(robot)
        category=source.cat_combo.currentData();specs=Scenarios.get_drop_sequence_specs(category)
        box=(source.w_input.value(),source.d_input.value(),source.h_input.value())
        active=source.sequence_drop.currentIndex() if robot else source.drop_combo.currentIndex()
        if robot and self.name.text() in ('Current Type G presets','Current Type H presets'):
            self.name.setText('Current '+source.cat_combo.currentText()+' presets')
        key=(mode,category,box,source.mass_input.value())
        # Static preset rows change only with mode/category/geometry/mass.
        # Ordinary selected-pose edits update the relevant cells in place.
        rows=range(len(specs)) if key!=self._preset_key else {active,self._last_active}
        self.table.blockSignals(True);self.table.setRowCount(len(specs))
        for r in rows:
            if not 0<=r<len(specs):continue
            spec=specs[r]
            values=[spec.id.replace('_',' '),f'{Scenarios.calculate_drop_height(category,spec,source.mass_input.value()):g}',
                *[f'{value:.2f}' for value in Scenarios.get_euler_angles(spec,box,category)],
                'Hazard block unavailable' if spec.variant=='hazard_face2' else
                'Supported motion unavailable' if spec.kind in ('tip','rotational_edge') else 'Free-fall preset']
            if not robot and r==active:
                values[1:5]=[f'{control.value():g}' for control in
                    (source.custom_h_input,source.custom_r_input,source.custom_p_input,source.custom_y_input)]
            for c,value in enumerate(values):
                item=self.table.item(r,c)
                if item is None:self.table.setItem(r,c,QTableWidgetItem(value))
                elif item.text()!=value:item.setText(value)
        if self.invalid:
            self.table.item(1,1).setText('NaN');self.table.item(1,1).setBackground(Qt.GlobalColor.yellow)
        self.table.selectRow(active);self.table.blockSignals(False)
        self._preset_key=key;self._last_active=active
        self.sequence_hint.setText(f'{len(specs)} preset steps. Sequence execution unavailable (#140).' if robot else f'1 selected / {len(specs)} presets. Run selected preset only.')
        self._fit_tab()

    def _fit_tab(self):
        page_height=self.tabs.currentWidget().sizeHint().height()
        self.tabs.setFixedHeight(page_height+self.tabs.tabBar().sizeHint().height()+4)

    def content_height(self):
        # Preferred size follows the active tab, without stretching short forms
        # to the longest tab. Larger user windows still retain a visible footer.
        self._fit_tab()
        self.layout().activate()
        return self.layout().sizeHint().height()

    def edit_marker(self):
        from src.simulation.ui.marker_profile_dialog import MarkerProfileDialog
        from src.simulation.marker_fixtures import load_profile
        self.editor=MarkerProfileDialog(load_profile(example='32' if self.marker_profile.currentIndex()==1 else '18'),parent=self)
        self.editor.show()


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',required=True);parser.add_argument('--interactive',action='store_true');args=parser.parse_args()
    root=Path(args.output);root.mkdir(parents=True,exist_ok=True)
    app=QApplication.instance() or QApplication([])
    report=dict(schema_version=1,plan_spec='ISTA6A-PLAN-20261001-v1',
        object_type='pub06_mockup_evidence',fresh=True,created_at=datetime.now(timezone.utc).isoformat(),
        source=dict(commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
            tracked_changes=subprocess.check_output(['git','status','--short','--untracked-files=no'],cwd=ROOT,text=True).splitlines(),
            script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()),
        command=[sys.executable,*sys.argv],python=sys.version,
        fixture='Current Type G17 and Type H12 preset browsers; G17 hazard and H supported motion unavailable; single executes only one selected preset',
        marker_seed=74082,simulation_seed='Not applicable: no simulation executed',
        independent_expectations=['Type G17 ordered preset rows, face3 at row8 and edge3/4 at row1; Type H12, face4 at row1',
            'Mode round-trip preserves original single controls and preset',
            'Small controls retain minimum readable height; scrolled preview fully contained',
            'Busy settings Apply disabled; table and selector agree in both directions'],
        unexecuted=['Native Windows input','Actual OS125 display verification','Production UI binding','Measured experiment validation'],
        scope='Review-only mockup; no production execution or native input',qt_platform=app.platformName(),
        qt_scale_factor=os.environ.get('QT_SCALE_FACTOR'),screen_dpr=app.primaryScreen().devicePixelRatio(),
        os_scale='Not inferred from Qt process scale; native OS125 remains separate',states=[])
    for state,mode,tab in [('default','single_drop',0),('sequence','robot_sequence',0),('edge','robot_sequence',0),('type_h','robot_sequence',0),('physics','robot_sequence',1),('observation','robot_sequence',2),('returned','single_drop',0),('invalid','robot_sequence',0),('blocked','robot_sequence',0),('running','single_drop',0),('cancelled','single_drop',0)]:
        board=QWidget();board.setWindowTitle('Simulation — #139 mockup')
        row=QHBoxLayout(board);row.setContentsMargins(10,10,10,10);row.setSpacing(12)
        main_window=MockSimulation(mode,state,Scenarios.CATEGORIES[1] if state=='type_h' else None);profile=MockProfiles(mode,state=='invalid',main_window);profile.tabs.setCurrentIndex(tab)
        if state=='running':profile.setEnabled(False)
        profile.setMinimumWidth(0)
        main_window.setFixedWidth(430)
        row.addWidget(main_window)
        right=QVBoxLayout();row.addLayout(right,1)
        right.addWidget(profile)
        preview_group=QGroupBox('Preset target')
        preview_layout=QVBoxLayout(preview_group)
        preview_layout.addWidget(main_window.orientation_preview)
        right.addWidget(preview_group,1)
        profile.show()
        main_window.profiles_button.clicked.connect(lambda checked=False,p=profile:p.setVisible(not p.isVisible()))
        profile.cancel.clicked.connect(profile.hide)
        profile.table.itemSelectionChanged.connect(lambda m=main_window,p=profile:
            (m.sequence_drop if m.mode.currentData()=='robot_sequence' else m.drop_combo).setCurrentIndex(p.table.currentRow()) if p.table.currentRow()>=0 else None)
        main_window.sequence_drop.currentIndexChanged.connect(lambda index,m=main_window,p=profile:p.table.selectRow(index) if m.mode.currentData()=='robot_sequence' else None)
        main_window.drop_combo.currentIndexChanged.connect(lambda index,m=main_window,p=profile:p.table.selectRow(index) if m.mode.currentData()=='single_drop' else None)
        main_window.configuration_changed.connect(profile.refresh)
        for signal in (main_window.mode.currentIndexChanged,main_window.cat_combo.currentIndexChanged,
                main_window.w_input.valueChanged,main_window.d_input.valueChanged,main_window.h_input.valueChanged,
                main_window.mass_input.valueChanged,main_window.custom_h_input.valueChanged,
                main_window.custom_r_input.valueChanged,main_window.custom_p_input.valueChanged,main_window.custom_y_input.valueChanged):
            signal.connect(profile.refresh)
        if mode=='robot_sequence':profile.table.selectRow(1 if state=='invalid' else 0 if state in ('edge','type_h') else 7)
        else:profile.table.selectRow(main_window.drop_combo.currentIndex())
        if state=='edge':
            main_window.sequence_drop.setCurrentIndex(7)
            assert profile.table.currentRow()==7 and main_window.orientation_preview.sequence_spec.faces==(3,)
            main_window.sequence_drop.setCurrentIndex(0)
            assert profile.table.currentRow()==0 and main_window.orientation_preview.sequence_spec.faces==(3,4)
        if state=='default':
            original=tuple(c.value() for c in (main_window.custom_h_input,main_window.custom_r_input,main_window.custom_p_input,main_window.custom_y_input))
            main_window.mode.setCurrentIndex(1)
            assert profile.mode.text()=='Robot sequence' and profile.order_buttons[0].isEnabled()
            profile.table.selectRow(7)
            main_window.mode.setCurrentIndex(0)
            assert profile.mode.text()=='Single drop' and not profile.order_buttons[0].isEnabled()
            assert tuple(c.value() for c in (main_window.custom_h_input,main_window.custom_r_input,main_window.custom_p_input,main_window.custom_y_input))==original
            main_window.cat_combo.setCurrentIndex(1)
            assert profile.table.rowCount()==12 and profile.table.item(0,5).text()=='Supported motion unavailable'
            main_window.cat_combo.setCurrentIndex(0)
            main_window.custom_h_input.setValue(123.);main_window.custom_y_input.setValue(17.)
            assert profile.table.item(0,1).text()=='123' and profile.table.item(0,4).text()=='17'
            main_window._update_custom_fields_from_scenario()
            assert profile.table.item(0,1).text()=='460' and profile.table.item(0,4).text()=='0'
            assert main_window.orientation_preview.euler==(-98.68,0.,0.)
        dpr=app.primaryScreen().devicePixelRatio()
        board.resize(math.ceil(1920/dpr),math.ceil(1080/dpr));board.show();app.processEvents()
        assert main_window.orientation_preview.isVisible(), 'Both modes must retain the preset target preview.'
        assert main_window.orientation_preview.sequence_spec.faces, 'Preview must retain a target highlight.'
        if state=='running':assert not profile.apply.isEnabled(), 'Busy state must block all settings application paths.'
        assert preview_group.rect().contains(main_window.orientation_preview.geometry()), 'Preview must stay inside its panel.'
        if state=='sequence':
            assert main_window.orientation_preview.sequence_spec.faces==(3,)
        elif state=='edge':
            assert main_window.orientation_preview.sequence_spec.faces==(3,4)
        assert profile.table.viewport().height()>=5*profile.table.rowHeight(0)
        if mode=='robot_sequence':
            if state=='type_h':
                assert profile.table.rowCount()==12 and profile.table.item(0,5).text()=='Supported motion unavailable'
                assert main_window.orientation_preview.sequence_spec.faces==(4,)
            else:
                assert profile.table.rowCount()==17
                assert profile.table.item(16,5).text()=='Hazard block unavailable'
        # Render at original resolution, never upscale a smaller raster.
        pixmap=board.grab();name=f'{state}-fhd.png';assert pixmap.save(str(root/name))
        assert pixmap.width()>=1920 and pixmap.height()>=1080
        report['states'].append(dict(state=state,logical=[board.width(),board.height()],pixels=[pixmap.width(),pixmap.height()],
            dpr=pixmap.devicePixelRatio(),screenshot=name,composition='One simulation workspace with optional settings and the existing preview',
            panels=dict(simulation=[main_window.width(),main_window.height()],settings=[profile.width(),profile.height()]),
            form_scroll_maximum=main_window.form_scroll.verticalScrollBar().maximum(),
            table_empty_rows=0,preset_rows=profile.table.rowCount(),sequence_steps=profile.table.rowCount() if mode=='robot_sequence' else 1,
            preview=dict(visible=True,preset=main_window.orientation_preview.sequence_spec.id,
                faces=list(main_window.orientation_preview.sequence_spec.faces),euler=list(main_window.orientation_preview.euler),
                meaning='Preset target, not a predicted impact after custom rotation')))
        board.close();board.deleteLater();app.processEvents()
    # Independent round-trip expectation: the original single controls and
    # preset remain unchanged while selecting a different sequence preview.
    roundtrip=MockSimulation()
    original=tuple(c.value() for c in (roundtrip.custom_h_input,roundtrip.custom_r_input,roundtrip.custom_p_input,roundtrip.custom_y_input))
    preset=roundtrip.drop_combo.currentData().id
    roundtrip.mode.setCurrentIndex(1);roundtrip.sequence_drop.setCurrentIndex(7)
    assert roundtrip.orientation_preview.sequence_spec.faces==(3,)
    assert roundtrip.custom_h_input.value()==910.
    roundtrip.mode.setCurrentIndex(0)
    assert roundtrip.drop_combo.currentData().id==preset
    assert tuple(c.value() for c in (roundtrip.custom_h_input,roundtrip.custom_r_input,roundtrip.custom_p_input,roundtrip.custom_y_input))==original
    assert roundtrip.orientation_preview.euler==original[1:]
    report['preview_roundtrip']='Passed: select sequence row8 face3/910mm, then restore original single preset and all four controls'
    roundtrip.orientation_preview.deleteLater();roundtrip.deleteLater()
    for mode in ('single_drop','robot_sequence'):
        window=MockSimulation(mode,'blocked' if mode=='robot_sequence' else 'default')
        window.form_layout.insertWidget(window.form_layout.count()-1,window.orientation_preview)
        window._fit_form()
        window.resize(820,600);window.show();app.processEvents()
        for control in (window.w_input,window.d_input,window.h_input,window.mass_input,window.duration_input):
            assert control.height()>=control.minimumSizeHint().height(), 'Small-window fields must retain readable height.'
        if mode=='single_drop':
            for control in (window.cat_combo,window.drop_combo,window.custom_h_input):
                assert control.height()>=control.minimumSizeHint().height(), 'Single-drop controls must retain readable height.'
        for button in (window.run_btn,window.batch_btn,window.marker_btn):
            rectangle=button.rect();rectangle.moveTopLeft(button.mapTo(window,rectangle.topLeft()))
            assert window.rect().contains(rectangle), 'Primary action must remain inside the small window.'
        pixmap=window.grab();name=f'{mode}-820x600.png';pixmap.save(str(root/name))
        report['states'].append(dict(state=mode,logical=[window.width(),window.height()],pixels=[pixmap.width(),pixmap.height()],dpr=pixmap.devicePixelRatio(),screenshot=name))
        window.form_scroll.verticalScrollBar().setValue(window.form_scroll.verticalScrollBar().maximum());app.processEvents()
        preview_rect=window.orientation_preview.rect()
        preview_rect.moveTopLeft(window.orientation_preview.mapTo(window.form_scroll.viewport(),preview_rect.topLeft()))
        assert window.form_scroll.viewport().rect().contains(preview_rect), 'Small-window scrolling must expose the complete preview.'
        pixmap=window.grab();name=f'{mode}-preview-820x600.png';pixmap.save(str(root/name))
        report['states'].append(dict(state=mode+' scrolled preview',logical=[window.width(),window.height()],pixels=[pixmap.width(),pixmap.height()],dpr=pixmap.devicePixelRatio(),screenshot=name,
            scope='Same small form scrolled to bottom; readable settings remain above'))
        window.close();window.deleteLater();app.processEvents()
        source=MockSimulation(mode)
        profile=MockProfiles(mode,source=source);profile.resize(820,600);profile.show();app.processEvents()
        apply_top=profile.apply.mapTo(profile,profile.apply.rect().topLeft()).y()
        status_bottom=profile.status.mapTo(profile,profile.status.rect().bottomLeft()).y()
        assert 0 <= apply_top-status_bottom <= 20, 'Footer must stay next to profile content.'
        assert profile.rect().contains(profile.apply.geometry()), 'Apply must remain inside the small window.'
        pixmap=profile.grab();name=f'{mode}-profiles-820x600.png';pixmap.save(str(root/name))
        report['states'].append(dict(state=mode+' profiles',logical=[profile.width(),profile.height()],pixels=[pixmap.width(),pixmap.height()],dpr=pixmap.devicePixelRatio(),screenshot=name,
            scope='Forced-size resize stress; default settings height follows active content',footer_gap=apply_top-status_bottom))
        profile.close();profile.deleteLater();app.processEvents()
        source.orientation_preview.deleteLater()
        source.deleteLater()
    (root/'evidence.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(states=len(report['states']),dpr=report['screen_dpr'])))
    if args.interactive:
        window=MockSimulation()
        window.form_layout.insertWidget(window.form_layout.count()-1,window.orientation_preview);window._fit_form()
        window.resize(820,600);window.show()
        profile=MockProfiles(source=window)
        window.profiles_button.clicked.connect(profile.show)
        app.exec()


if __name__=='__main__':main()
