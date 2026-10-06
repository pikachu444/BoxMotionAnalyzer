"""Optional synthetic observations, separate from direct simulation results."""
import copy
import csv
import json
from itertools import islice
from pathlib import Path

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from PySide6.QtCore import QThread, Signal, Qt
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QWidget, QLabel, QComboBox, QPushButton, QCheckBox, QSpinBox, QDoubleSpinBox,
    QLineEdit, QProgressBar, QFileDialog, QMessageBox, QSizePolicy)

from src.simulation.marker_fixtures import load_profile, draw_profile
from src.simulation.marker_export import generate_marker_capture
from src.simulation.profile_document import read_document
from src.utils.marker_profile_identity import profile_identity, validate_identity, compatibility, artifact_identity, layout_support
from src.utils.artifact_metadata import metadata_from_source_rows
from .marker_profile_dialog import MarkerProfileDialog
from src.utils.qt_sections import CollapsibleSection


class MarkerExportWorker(QThread):
    ready = Signal(str)
    failed = Signal(str)
    cancelled = Signal()
    progress = Signal(int, str)

    def __init__(self, destination, profile, simulation, faults, seed, parent=None):
        super().__init__(parent)
        self.arguments = copy.deepcopy((destination, profile, simulation, faults, seed))
        self.profile_identity = profile_identity(profile)

    def run(self):
        try:
            path = generate_marker_capture(*self.arguments, cancelled=self.isInterruptionRequested,
                                           progress=self.progress.emit)
            with open(path, encoding='utf-8-sig', newline='') as stream:
                declared = artifact_identity(metadata_from_source_rows(list(islice(csv.reader(stream), 2))))
            if declared is None or declared['source_profile'] != self.arguments[1]:
                raise ValueError('Exported marker source identity does not match this job.')
            validate_identity(self.profile_identity)
            if self.isInterruptionRequested():
                raise InterruptedError()
        except InterruptedError:
            self.cancelled.emit()
        except Exception as error:
            self.failed.emit(str(error))
        else:
            self.ready.emit(path)


class MarkerExportDialog(QDialog):
    open_observations = Signal(str)

    def __init__(self, simulation, box_size, parent=None):
        super().__init__(parent)
        self.simulation = copy.deepcopy(simulation)
        self.original_size = tuple(box_size)
        self.profile = None
        self.imported_profile = None
        self.imported_document = None
        self.result_identity = None
        self.result_compatibility = None
        self._generation = 0
        self._cancel_reason = None
        self._layout_block_reason = None
        self.worker = None
        self.observed_path = None
        self.close_requested = False
        self.setWindowTitle('Synthetic marker CSV')
        self.resize(1000, 700)
        self.setMinimumSize(820, 600)
        layout = QVBoxLayout(self)
        self.controls = QWidget()
        form = QVBoxLayout(self.controls)
        form.setContentsMargins(0, 0, 0, 0)
        row = QHBoxLayout()
        row.addWidget(QLabel('Layout'))
        self.profile_combo = QComboBox()
        self.profile_combo.setMinimumContentsLength(28)
        self.profile_combo.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
        self.profile_combo.addItem('Public example: 18 markers', '18')
        self.profile_combo.addItem('Public example: 32 markers', '32')
        row.addWidget(self.profile_combo, 1)
        self.import_button = QPushButton('Import JSON…')
        row.addWidget(self.import_button)
        self.copy_button = QPushButton('Copy…'); self.edit_button = QPushButton('Edit…')
        row.addWidget(self.copy_button); row.addWidget(self.edit_button)
        form.addLayout(row)
        self.dimensions = QCheckBox()
        self.dimensions.setToolTip('Use these absolute layout dimensions for this export. Simulation controls are preserved.')
        form.addWidget(self.dimensions)
        self.figure = Figure(figsize=(8, 4), layout='constrained')
        self.canvas = FigureCanvasQTAgg(self.figure)
        self.axes = self.figure.add_subplot(111, projection='3d')
        form.addWidget(self.canvas, 1)
        fault_widget = QWidget()
        fields = QFormLayout(fault_widget)
        fields.setContentsMargins(8, 0, 0, 0)
        self.kind = QComboBox()
        for label, key in [('None', None), ('Missing samples', 'missing'),
                           ('Local 180° half-turn', 'flip_180_local_axis'), ('Gaussian noise', 'gaussian_noise')]:
            self.kind.addItem(label, key)
        fields.addRow('Fault', self.kind)
        self.channel = QComboBox()
        self.channel.addItem('Solved rigid-body markers', 'rigid_body_markers')
        self.channel.addItem('Physical markers', 'physical_markers')
        self.channel.setToolTip('Step 1 uses the solved channel. Physical-marker faults do not simulate a tracking solver response.')
        fields.addRow('Channel', self.channel)
        time_row = QHBoxLayout()
        self.start = QDoubleSpinBox(); self.end = QDoubleSpinBox()
        for control in (self.start, self.end):
            control.setRange(0, simulation['duration'])
            control.setDecimals(4)
            control.setSuffix(' s')
        self.start.setValue(min(.24, simulation['duration'] / 3))
        self.end.setValue(min(.32, simulation['duration'] * 2 / 3))
        time_row.addWidget(self.start); time_row.addWidget(QLabel('to')); time_row.addWidget(self.end)
        fields.addRow('Recorded interval', time_row)
        options = QHBoxLayout()
        self.axis = QComboBox(); self.axis.addItems(['X', 'Y', 'Z'])
        self.std = QDoubleSpinBox(); self.std.setRange(.001, 100); self.std.setDecimals(3)
        self.std.setValue(.02); self.std.setSuffix(' mm')
        self.seed = QSpinBox(); self.seed.setRange(0, 2147483647); self.seed.setValue(74082)
        options.addWidget(QLabel('Axis')); options.addWidget(self.axis)
        options.addWidget(QLabel('Std')); options.addWidget(self.std)
        options.addWidget(QLabel('Seed')); options.addWidget(self.seed)
        fields.addRow(options)
        self.fault_section = CollapsibleSection('Faults', fault_widget)
        form.addWidget(self.fault_section)
        names = QHBoxLayout()
        names.addWidget(QLabel('Output folder name'))
        self.output_name = QLineEdit('synthetic_markers')
        names.addWidget(self.output_name, 1)
        form.addLayout(names)
        layout.addWidget(self.controls, 1)
        self.note = QLabel('Synthetic observations. Truth and event files are separate evaluation outputs.')
        self.note.setWordWrap(True)
        self.note.setToolTip(f"Simulation snapshot: {simulation['duration']:g} s, clearance {simulation['height']:g} mm, "
            f"mass {simulation['mass']:g} kg, local COM {simulation['com_offset']} mm. "
            'Initial orientation and contact inputs are copied from Simulation. Direct corner noise is not applied.')
        layout.addWidget(self.note)
        self.status = QLabel('Choose a layout and generate observations.')
        self.status.setTextFormat(Qt.PlainText)
        self.status.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        self.progress = QProgressBar(); self.progress.hide()
        layout.addWidget(self.progress)
        actions = QHBoxLayout()
        self.generate_button = QPushButton('Generate…')
        self.cancel_button = QPushButton('Cancel'); self.cancel_button.setEnabled(False)
        self.open_button = QPushButton('Open in Step 1'); self.open_button.setEnabled(False)
        actions.addWidget(self.generate_button); actions.addWidget(self.cancel_button)
        actions.addStretch(); actions.addWidget(self.open_button)
        layout.addLayout(actions)
        self.profile_combo.currentIndexChanged.connect(self._select_profile)
        self.dimensions.toggled.connect(self._update_actions)
        self.import_button.clicked.connect(self._import_profile)
        self.copy_button.clicked.connect(lambda:self._edit_profile(copy_source=True))
        self.edit_button.clicked.connect(lambda:self._edit_profile(copy_source=False))
        self.kind.currentIndexChanged.connect(self._fault_controls)
        self.generate_button.clicked.connect(self.generate)
        self.cancel_button.clicked.connect(self.cancel)
        self.open_button.clicked.connect(self._open)
        self._select_profile()
        self._fault_controls()

    @property
    def busy(self):
        return self.worker is not None

    def _select_profile(self):
        if self.busy:
            self._cancel_job('Profile changed. Previous results are preserved.')
        selected = self.profile_combo.currentData()
        self.profile = copy.deepcopy(self.imported_profile) if selected == 'custom' else load_profile(example=selected)
        dims = tuple(self.profile['box_dims_mm'])
        self.dimensions.setText('Use layout box: ' + ' × '.join(f'{d:g}' for d in dims) + ' mm')
        self.dimensions.setChecked(dims == self.original_size)
        self.axes.clear()
        draw_profile(self.profile, self.axes)
        self.axes.legend(loc='upper left', bbox_to_anchor=(-.55, 1.))
        self.axes.set_title('Box-local marker layout')
        self.canvas.draw_idle()
        self._update_compatibility()
        self._update_actions()

    def _update_compatibility(self):
        if self.observed_path is None: return
        self.result_compatibility = compatibility(self.result_identity, profile_identity(self.profile))
        self.status.setText('Previous output: '+self.result_compatibility['status']+' with this profile.')
        self.status.setToolTip(' '.join(self.result_compatibility['reasons'])+
            ' Open uses the output’s own declared profile; no review or trial approval is inherited.')

    def _set_custom(self, profile, document=None, *, imported=False):
        self.imported_profile = copy.deepcopy(profile); self.imported_document = copy.deepcopy(document)
        index = self.profile_combo.findData('custom')
        label = ('Imported: ' if imported else 'Custom: ')+profile['profile_id']
        if index < 0:
            self.profile_combo.addItem(label, 'custom'); index = self.profile_combo.count()-1
        else: self.profile_combo.setItemText(index, label)
        if self.profile_combo.currentIndex() == index: self._select_profile()
        else: self.profile_combo.setCurrentIndex(index)

    def _edit_profile(self, *, copy_source):
        if self.busy: return
        original_identity = profile_identity(self.profile)
        document = self.imported_document if self.profile_combo.currentData() == 'custom' and not copy_source else None
        # Presets are immutable; Edit on a preset follows the same copy route.
        editor = MarkerProfileDialog(self.profile, document=document,
            copy_source=copy_source or self.profile_combo.currentData() != 'custom',
            previous_result_identity=self.result_identity, parent=self)
        try:
            if editor.exec() == QDialog.Accepted:
                if profile_identity(self.profile) != original_identity:
                    self.status.setText('Source changed while editing. This Apply was not adopted.')
                    return
                self._set_custom(editor.state.applied, editor.state.document())
        finally: editor.deleteLater()

    def _import_profile(self):
        path, _ = QFileDialog.getOpenFileName(self, 'Import marker layout', '', 'JSON files (*.json)')
        if not path:
            return
        try:
            value = json.loads(Path(path).read_text(encoding='utf-8-sig'))
            document = read_document(path).document() if isinstance(value, dict) and value.get('object_type') == 'MarkerProfileDocument' else None
            profile = load_profile(path)
        except (OSError, ValueError, KeyError, TypeError, AttributeError, IndexError) as error:
            QMessageBox.warning(self, 'Invalid layout', str(error))
            return
        self._set_custom(profile, document, imported=True)

    def _fault_controls(self):
        kind = self.kind.currentData()
        half_turn = kind == 'flip_180_local_axis'
        if half_turn:
            self.channel.setCurrentIndex(0)
        self.channel.setEnabled(bool(kind) and not half_turn)
        self.start.setEnabled(bool(kind)); self.end.setEnabled(bool(kind) and not half_turn)
        self.axis.setEnabled(half_turn)
        self.std.setEnabled(kind == 'gaussian_noise')
        self.seed.setEnabled(kind == 'gaussian_noise')

    def _update_actions(self):
        support = layout_support(self.profile)
        reason = support['reason'] if support['status'] != 'supported' else None
        self.controls.setEnabled(not self.busy)
        self.generate_button.setEnabled(not self.busy and self.dimensions.isChecked() and reason is None)
        self.generate_button.setToolTip(reason or '')
        self.cancel_button.setEnabled(self.busy)
        self.open_button.setEnabled(not self.busy and self.observed_path is not None)
        if not self.busy:
            if reason:
                self.status.setText(reason)
            elif self.status.text() == self._layout_block_reason:
                self.status.setText('Choose a layout and generate observations.')
        self._layout_block_reason = reason

    def generate(self):
        if self.busy or not self.dimensions.isChecked():
            return
        support = layout_support(self.profile)
        if support['status'] != 'supported':
            self.status.setText(support['reason']); return
        name = self.output_name.text().strip()
        if not name or name in ('.', '..') or any(c in name for c in '<>:"/\\|?*') or name.endswith(('.', ' ')):
            QMessageBox.warning(self, 'Output folder', 'Enter a new folder name without path separators.')
            return
        parent = QFileDialog.getExistingDirectory(self, 'Choose parent folder for a new capture', str(Path('data')))
        if not parent:
            return
        destination = str(Path(parent) / name)
        if Path(destination).exists():
            QMessageBox.warning(self, 'Output exists', 'Choose a new folder name. Existing files are preserved.')
            return
        faults = dict(kind=self.kind.currentData(), channel=self.channel.currentData(),
            start=self.start.value(), end=self.end.value(), axis=self.axis.currentText(), std_mm=self.std.value())
        self.worker = MarkerExportWorker(destination, self.profile, self.simulation, faults, self.seed.value(), self)
        worker = self.worker; self._generation += 1; generation = self._generation; self._cancel_reason = None
        worker.progress.connect(lambda value, text:self._job_event(worker, generation, self._progress, value, text))
        worker.ready.connect(lambda path:self._job_event(worker, generation, self._ready, path))
        worker.failed.connect(lambda message:self._job_event(worker, generation, self._failed, message))
        worker.cancelled.connect(lambda:self._cancelled(worker))
        worker.finished.connect(lambda:self._finished(worker))
        self.progress.setValue(0); self.progress.show()
        self.status.setText('Generating synthetic marker observations…')
        self._update_actions()
        self.worker.start()

    def _job_event(self, worker, generation, callback, *args):
        if self.worker is not worker or generation != self._generation or self._cancel_reason is not None:
            return
        callback(*args)

    def _cancelled(self, worker):
        if self.worker is worker:
            self.status.setText(self._cancel_reason or 'Cancelled. Previous results are preserved.')

    def _progress(self, value, text):
        self.progress.setValue(value)
        self.status.setText(text)

    def _ready(self, path):
        try:
            validate_identity(self.worker.profile_identity)
            if self.worker.profile_identity != profile_identity(self.profile):
                raise ValueError('Stale profile result rejected.')
        except ValueError as error:
            self._failed(str(error)); return
        self.observed_path = path
        self.result_identity = copy.deepcopy(self.worker.profile_identity)
        self.result_compatibility = compatibility(self.result_identity, profile_identity(self.profile))
        self.status.setText('Ready: ' + Path(path).parent.name + '/observed.csv')
        self.status.setToolTip(path)

    def _failed(self, message):
        self.status.setText('Export failed: ' + message)

    def _finished(self, completed):
        if self.worker is not completed: return
        worker, self.worker = self.worker, None
        worker.deleteLater()
        self.progress.hide()
        self._update_actions()
        if self.close_requested:
            self.reject()

    def cancel(self):
        self._cancel_job('Cancelled. Previous results are preserved.')

    def _cancel_job(self, reason):
        if self.worker is not None:
            self._generation += 1; self._cancel_reason = reason
            self.worker.requestInterruption()
            self.cancel_button.setEnabled(False)
            self.status.setText('Cancelling… '+reason)

    def _open(self):
        if not self.busy and self.observed_path is not None:
            self.open_observations.emit(self.observed_path)

    def reject(self):
        if self.busy:
            self.close_requested = True
            self.cancel()
            return
        super().reject()

    def closeEvent(self, event):
        if self.busy:
            self.close_requested = True
            self.cancel()
            event.ignore()
        else:
            super().closeEvent(event)
