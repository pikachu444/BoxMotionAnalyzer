"""PUB06 review-only Qt mockups. No production actions or output generation."""
import argparse
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QComboBox, QPushButton, QTabWidget, QFormLayout, QDoubleSpinBox,
    QTableWidget, QTableWidgetItem, QHeaderView, QLineEdit, QGroupBox, QSpinBox)
from src.simulation.ui.main_window import SimulationUI


class MockSimulation(SimulationUI):
    def __init__(self, mode='single_drop', state='default'):
        super().__init__()
        self.setWindowTitle('Simulation — #139 mockup')
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
        summary.addWidget(QLabel('1   Face 3 — high     100 mm'))
        summary.addWidget(QLabel('2   Edge 3–4            150 mm'))
        summary.addWidget(QLabel('Edit order and initial pose in Settings…'))
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

    def change_mode(self):
        robot = self.mode.currentData() == 'robot_sequence'
        self.drop_combo.parentWidget().setVisible(not robot)
        self.sequence_summary.setVisible(robot)
        self.mode_hint.setText('Configure and save drop order in Settings… Execution is not available yet.' if robot else '')
        self.mode_hint.setVisible(robot)
        for button in (self.run_btn,self.batch_btn,self.marker_btn):
            button.setEnabled(not robot)
            button.setToolTip('Sequence simulation is not implemented.' if robot else '')
        self.result.setText('')

    def closeEvent(self,event):
        # Review-only states have no live worker and must not inherit its close gate.
        event.accept()


class MockProfiles(QWidget):
    def __init__(self, mode='single_drop', invalid=False, source=None):
        super().__init__()
        self.setWindowTitle('Simulation settings — #139 mockup')
        layout = QVBoxLayout(self)
        top = QHBoxLayout(); top.addWidget(QLabel('Mode'))
        self.mode = QLabel('Single drop' if mode=='single_drop' else 'Robot sequence')
        top.addWidget(self.mode,1)
        layout.addLayout(top)
        self.tabs = QTabWidget(); layout.addWidget(self.tabs,1)
        sequence = QWidget(); seq = QVBoxLayout(sequence)
        names = QFormLayout(); self.name = QLineEdit('Public sequence example' if mode=='robot_sequence' else 'Current single drop')
        names.addRow('Sequence profile',self.name)
        robot = QComboBox(); robot.addItem('Gripper proxy'); names.addRow('Robot model',robot)
        robot.setEnabled(mode=='robot_sequence'); seq.addLayout(names)
        self.table = QTableWidget(2 if mode=='robot_sequence' else 1,5)
        self.table.setMaximumHeight(220)
        self.table.setHorizontalHeaderLabels(['Preset','Clearance (mm)','Fixed X (°)','Fixed Y (°)','Fixed Z (°)'])
        self.table.setToolTip('Fixed world XYZ in MuJoCo Z-up; extrinsic xyz degrees. Not a marker-local half turn.')
        self.table.horizontalHeader().setSectionResizeMode(0,QHeaderView.Stretch)
        for c in range(1,5): self.table.horizontalHeader().setSectionResizeMode(c,QHeaderView.ResizeToContents)
        rows=[['Type G / Face 3 — high','100','0','0','0'],['Type G / Edge 3–4','150','0','35','0']]
        if mode=='single_drop' and source is not None:
            rows=[[source.cat_combo.currentText()+' / '+source.drop_combo.currentText(),*[f'{control.value():g}' for control in
                (source.custom_h_input,source.custom_r_input,source.custom_p_input,source.custom_y_input)]]]
        for r in range(self.table.rowCount()):
            for c,text in enumerate(rows[r]): self.table.setItem(r,c,QTableWidgetItem(text))
        if invalid:
            self.table.item(1,1).setText('NaN')
            self.table.item(1,1).setBackground(Qt.GlobalColor.yellow)
        seq.addWidget(self.table)
        actions=QHBoxLayout()
        for text in ('Add drop','Remove','Move up','Move down'):
            button=QPushButton(text); button.setEnabled(mode=='robot_sequence'); actions.addWidget(button)
        seq.addLayout(actions)
        seq.addWidget(QLabel('Configure and save drop order. Execution is not available yet.') if mode=='robot_sequence' else QLabel('Optional settings. You can run a single drop directly from Simulation.'))
        seq.addStretch()
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
        self.status=QLabel('Drop 2 clearance must be finite. Changes were not applied.' if invalid else 'Profile settings are uncalibrated synthetic inputs.')
        self.status.setWordWrap(True)
        if invalid:self.status.setStyleSheet('color: #a32919;')
        layout.addWidget(self.status)
        buttons=QHBoxLayout()
        for text in ('Open settings…','Save settings…'):
            button=QPushButton(text); button.setEnabled(not invalid or text=='Open settings…');buttons.addWidget(button)
        buttons.addStretch()
        self.apply=QPushButton('Use in Simulation'); self.apply.setEnabled(not invalid);buttons.addWidget(self.apply)
        self.apply.setToolTip('Use these settings in Simulation. This does not save a file or run a simulation.')
        buttons.addWidget(QPushButton('Cancel'));layout.addLayout(buttons)

    def edit_marker(self):
        from src.simulation.ui.marker_profile_dialog import MarkerProfileDialog
        from src.simulation.marker_fixtures import load_profile
        self.editor=MarkerProfileDialog(load_profile(example='32' if self.marker_profile.currentIndex()==1 else '18'),parent=self)
        self.editor.show()


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',required=True);parser.add_argument('--interactive',action='store_true');args=parser.parse_args()
    root=Path(args.output);root.mkdir(parents=True,exist_ok=True)
    app=QApplication.instance() or QApplication([])
    report=dict(scope='Review-only mockup; no production execution or native input',qt_platform=app.platformName(),
        qt_scale_factor=os.environ.get('QT_SCALE_FACTOR'),screen_dpr=app.primaryScreen().devicePixelRatio(),
        os_scale='Not inferred from Qt process scale; native OS125 remains separate',states=[])
    for state,mode,tab in [('default','single_drop',0),('sequence','robot_sequence',0),('physics','robot_sequence',1),('observation','robot_sequence',2),('returned','single_drop',0),('invalid','robot_sequence',0),('blocked','robot_sequence',0),('running','single_drop',0),('cancelled','single_drop',0)]:
        board=QWidget();board.setWindowTitle('#139 — profile review')
        row=QHBoxLayout(board);row.setContentsMargins(30,30,30,30);row.setSpacing(24)
        main_window=MockSimulation(mode,state);profile=MockProfiles(mode,state=='invalid',main_window);profile.tabs.setCurrentIndex(tab)
        for title,widget,weight in [('Simulation',main_window,2),('Settings…',profile,3)]:
            group=QGroupBox(title);layout=QVBoxLayout(group);layout.addWidget(widget)
            if title=='Settings…':group.setMaximumHeight(620)
            row.addWidget(group,weight,Qt.AlignTop if title=='Settings…' else Qt.AlignmentFlag(0))
        board.resize(1920,1080);board.show();app.processEvents()
        # Render at original resolution, never upscale a smaller raster.
        pixmap=board.grab();name=f'{state}-fhd.png';assert pixmap.save(str(root/name))
        assert pixmap.width()>=1920 and pixmap.height()>=1080
        report['states'].append(dict(state=state,logical=[board.width(),board.height()],pixels=[pixmap.width(),pixmap.height()],dpr=pixmap.devicePixelRatio(),screenshot=name,composition='Two original Qt panels on a review board'))
        board.close();board.deleteLater();app.processEvents()
    for mode in ('single_drop','robot_sequence'):
        window=MockSimulation(mode,'blocked' if mode=='robot_sequence' else 'default');window.resize(820,600);window.show();app.processEvents()
        pixmap=window.grab();name=f'{mode}-820x600.png';pixmap.save(str(root/name))
        report['states'].append(dict(state=mode,logical=[window.width(),window.height()],pixels=[pixmap.width(),pixmap.height()],dpr=pixmap.devicePixelRatio(),screenshot=name))
        window.close();window.deleteLater();app.processEvents()
        source=MockSimulation(mode)
        profile=MockProfiles(mode,source=source);profile.resize(820,600);profile.show();app.processEvents()
        pixmap=profile.grab();name=f'{mode}-profiles-820x600.png';pixmap.save(str(root/name))
        report['states'].append(dict(state=mode+' profiles',logical=[profile.width(),profile.height()],pixels=[pixmap.width(),pixmap.height()],dpr=pixmap.devicePixelRatio(),screenshot=name))
        profile.close();profile.deleteLater();app.processEvents()
        source.deleteLater()
    (root/'evidence.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(states=len(report['states']),dpr=report['screen_dpr'])))
    if args.interactive:
        window=MockSimulation();window.resize(820,600);window.show()
        profile=MockProfiles(source=window)
        window.profiles_button.clicked.connect(profile.show)
        app.exec()


if __name__=='__main__':main()
