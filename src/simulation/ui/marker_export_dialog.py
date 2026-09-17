"""Optional synthetic observations, separate from direct simulation results."""
import copy
from pathlib import Path

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from PySide6.QtCore import QThread, Signal, Qt
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QWidget, QLabel, QComboBox, QPushButton, QCheckBox, QSpinBox, QDoubleSpinBox,
    QLineEdit, QProgressBar, QFileDialog, QMessageBox, QSizePolicy)

from src.simulation.marker_fixtures import load_profile, draw_profile
from src.simulation.marker_export import generate_marker_capture
from src.utils.qt_sections import CollapsibleSection


class MarkerExportWorker(QThread):
    ready = Signal(str)
    failed = Signal(str)
    cancelled = Signal()
    progress = Signal(int, str)

    def __init__(self, destination, profile, simulation, faults, seed, parent=None):
        super().__init__(parent)
        self.arguments = copy.deepcopy((destination, profile, simulation, faults, seed))

    def run(self):
        try:
            path = generate_marker_capture(*self.arguments, cancelled=self.isInterruptionRequested,
                                           progress=self.progress.emit)
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
        self._update_actions()

    def _import_profile(self):
        path, _ = QFileDialog.getOpenFileName(self, 'Import marker layout', '', 'JSON files (*.json)')
        if not path:
            return
        try:
            profile = load_profile(path)
        except (OSError, ValueError, KeyError, TypeError, AttributeError, IndexError) as error:
            QMessageBox.warning(self, 'Invalid layout', str(error))
            return
        self.imported_profile = profile
        index = self.profile_combo.findData('custom')
        if index < 0:
            self.profile_combo.addItem('Imported: ' + profile['profile_id'], 'custom')
            index = self.profile_combo.count() - 1
        else:
            self.profile_combo.setItemText(index, 'Imported: ' + profile['profile_id'])
        self.profile_combo.setCurrentIndex(index)
        self._select_profile()

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
        self.controls.setEnabled(not self.busy)
        self.generate_button.setEnabled(not self.busy and self.dimensions.isChecked())
        self.cancel_button.setEnabled(self.busy)
        self.open_button.setEnabled(not self.busy and self.observed_path is not None)

    def generate(self):
        if self.busy or not self.dimensions.isChecked():
            return
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
        self.worker.progress.connect(self._progress)
        self.worker.ready.connect(self._ready)
        self.worker.failed.connect(self._failed)
        self.worker.cancelled.connect(lambda: self.status.setText('Cancelled. Previous results are preserved.'))
        self.worker.finished.connect(self._finished)
        self.progress.setValue(0); self.progress.show()
        self.status.setText('Generating synthetic marker observations…')
        self._update_actions()
        self.worker.start()

    def _progress(self, value, text):
        self.progress.setValue(value)
        self.status.setText(text)

    def _ready(self, path):
        self.observed_path = path
        self.status.setText('Ready: ' + Path(path).parent.name + '/observed.csv')
        self.status.setToolTip(path)

    def _failed(self, message):
        self.status.setText('Export failed: ' + message)

    def _finished(self):
        worker, self.worker = self.worker, None
        worker.deleteLater()
        self.progress.hide()
        self._update_actions()
        if self.close_requested:
            self.reject()

    def cancel(self):
        if self.worker is not None:
            self.worker.requestInterruption()
            self.cancel_button.setEnabled(False)
            self.status.setText('Cancelling…')

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
