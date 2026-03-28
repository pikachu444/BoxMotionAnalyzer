import os
import sys
from pathlib import Path
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QComboBox, QPushButton, QDoubleSpinBox, QCheckBox,
    QGroupBox, QFormLayout, QMessageBox, QFileDialog, QProgressBar
)
from PySide6.QtCore import Qt, QThread, Signal

# Import logic modules
from src.simulation.engine import MuJoCoEngine
from src.simulation.scenarios import Scenarios
from src.simulation.data_exporter import DataExporter

class SimulationThread(QThread):
    finished_signal = Signal(str)
    error_signal = Signal(str)

    def __init__(self, engine, params, filepath):
        super().__init__()
        self.engine = engine
        self.params = params
        self.filepath = filepath

    def run(self):
        try:
            # 1. Build initial state
            self.engine.set_initial_state(self.params['height'], self.params['quat'])

            # 2. Run headless (viewer is disabled in thread to prevent GLFW crash)
            history = self.engine.run_simulation(show_viewer=False)

            # 3. Export
            exporter = DataExporter(history, self.params['add_noise'], self.params['noise_std'])
            output_path = exporter.export_raw_csv(self.filepath)

            self.finished_signal.emit(output_path)

        except Exception as e:
            self.error_signal.emit(f"Simulation Failed: {str(e)}")

class SimulationUI(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Simulation Setup")
        self.resize(500, 600)

        self.layout = QVBoxLayout(self)

        self._init_box_group()
        self._init_scenario_group()
        self._init_noise_group()
        self._init_export_group()

        self.run_btn = QPushButton("Run Simulation && Export")
        self.run_btn.clicked.connect(self.run_simulation)
        self.layout.addWidget(self.run_btn)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)
        self.progress_bar.hide()
        self.layout.addWidget(self.progress_bar)

        self.layout.addStretch()

    def _init_box_group(self):
        group = QGroupBox("Box Parameters")
        form = QFormLayout(group)

        self.w_input = QDoubleSpinBox()
        self.w_input.setRange(10, 5000)
        self.w_input.setValue(1000)

        self.d_input = QDoubleSpinBox()
        self.d_input.setRange(10, 5000)
        self.d_input.setValue(1000)

        self.h_input = QDoubleSpinBox()
        self.h_input.setRange(10, 5000)
        self.h_input.setValue(1000)

        self.mass_input = QDoubleSpinBox()
        self.mass_input.setRange(0.1, 10000)
        self.mass_input.setValue(100.0)

        form.addRow("Width (mm):", self.w_input)
        form.addRow("Depth (mm):", self.d_input)
        form.addRow("Height (mm):", self.h_input)
        form.addRow("Mass (kg):", self.mass_input)

        self.layout.addWidget(group)

    def _init_scenario_group(self):
        group = QGroupBox("Drop Scenario (ISTA-6A)")
        form = QFormLayout(group)

        self.cat_combo = QComboBox()
        self.cat_combo.addItems(["Parcel_Light", "Parcel_Medium", "Parcel_Heavy", "LTL", "Custom"])
        self.cat_combo.currentIndexChanged.connect(self._on_cat_changed)

        self.drop_combo = QComboBox()
        self.drop_combo.addItems([
            "Flat_Bottom", "Flat_Top", "Flat_Front", "Flat_Back", "Flat_Left", "Flat_Right",
            "Edge_Bottom_Front", "Corner_Bottom_Front_Left"
        ])

        self.custom_h_input = QDoubleSpinBox()
        self.custom_h_input.setRange(10, 10000)
        self.custom_h_input.setValue(810)
        self.custom_h_input.setEnabled(False)

        self.custom_r_input = QDoubleSpinBox()
        self.custom_r_input.setRange(-180, 180)
        self.custom_r_input.setValue(0)
        self.custom_r_input.setEnabled(False)

        self.custom_p_input = QDoubleSpinBox()
        self.custom_p_input.setRange(-180, 180)
        self.custom_p_input.setValue(0)
        self.custom_p_input.setEnabled(False)

        self.custom_y_input = QDoubleSpinBox()
        self.custom_y_input.setRange(-180, 180)
        self.custom_y_input.setValue(0)
        self.custom_y_input.setEnabled(False)

        form.addRow("Category:", self.cat_combo)
        form.addRow("Drop Type:", self.drop_combo)
        form.addRow("Custom Height (mm):", self.custom_h_input)
        form.addRow("Custom Roll (deg):", self.custom_r_input)
        form.addRow("Custom Pitch (deg):", self.custom_p_input)
        form.addRow("Custom Yaw (deg):", self.custom_y_input)

        self.layout.addWidget(group)

    def _on_cat_changed(self):
        is_custom = self.cat_combo.currentText() == "Custom"
        self.drop_combo.setEnabled(not is_custom)
        self.custom_h_input.setEnabled(is_custom)
        self.custom_r_input.setEnabled(is_custom)
        self.custom_p_input.setEnabled(is_custom)
        self.custom_y_input.setEnabled(is_custom)

    def _init_noise_group(self):
        group = QGroupBox("Noise Simulation")
        layout = QVBoxLayout(group)

        self.noise_cb = QCheckBox("Add Gaussian Noise to simulate real MoCap sensor")
        self.noise_std_input = QDoubleSpinBox()
        self.noise_std_input.setRange(0.01, 100)
        self.noise_std_input.setValue(1.0)
        self.noise_std_input.setPrefix("Std Dev (mm): ")

        layout.addWidget(self.noise_cb)
        layout.addWidget(self.noise_std_input)
        self.layout.addWidget(group)

    def _init_export_group(self):
        group = QGroupBox("Visualization")
        layout = QVBoxLayout(group)

        self.viewer_cb = QCheckBox("Show 3D Viewer during Simulation")
        self.viewer_cb.setChecked(True)

        layout.addWidget(self.viewer_cb)
        self.layout.addWidget(group)

    def run_simulation(self):
        # 1. Gather Params
        size = (self.w_input.value(), self.d_input.value(), self.h_input.value())
        mass = self.mass_input.value()

        cat = self.cat_combo.currentText()
        if cat == "Custom":
            height = self.custom_h_input.value()
            quat = Scenarios.custom_orientation(
                self.custom_r_input.value(),
                self.custom_p_input.value(),
                self.custom_y_input.value()
            )
        else:
            height = Scenarios.get_drop_height(cat)
            quat = Scenarios.get_orientation(self.drop_combo.currentText(), size)

        params = {
            'height': height,
            'quat': quat,
            'add_noise': self.noise_cb.isChecked(),
            'noise_std': self.noise_std_input.value(),
            'show_viewer': self.viewer_cb.isChecked()
        }

        # 2. Select Output File
        filepath, _ = QFileDialog.getSaveFileName(
            self, "Save Simulation CSV", str(Path("data") / "sim_data.csv"), "CSV Files (*.csv)"
        )
        if not filepath:
            return

        # 3. Setup Engine
        self.run_btn.setEnabled(False)
        self.progress_bar.show()

        engine = MuJoCoEngine(size=size, mass=mass)

        # 4. Run Simulation
        if params['show_viewer']:
            # Run in main thread because mujoco.viewer (GLFW) MUST run on the main thread
            try:
                engine.set_initial_state(params['height'], params['quat'])
                history = engine.run_simulation(show_viewer=True)

                exporter = DataExporter(history, params['add_noise'], params['noise_std'])
                output_path = exporter.export_raw_csv(filepath)

                self.on_sim_finished(output_path)
            except Exception as e:
                self.on_sim_error(f"Simulation Failed: {str(e)}")
        else:
            # Run headless in background thread
            self.thread = SimulationThread(engine, params, filepath)
            self.thread.finished_signal.connect(self.on_sim_finished)
            self.thread.error_signal.connect(self.on_sim_error)
            self.thread.start()

    def on_sim_finished(self, output_path):
        self.run_btn.setEnabled(True)
        self.progress_bar.hide()
        QMessageBox.information(self, "Success", f"Simulation completed and saved to:\n{output_path}\n\nYou can now load this in Data Analysis.")

    def on_sim_error(self, err_msg):
        self.run_btn.setEnabled(True)
        self.progress_bar.hide()
        QMessageBox.critical(self, "Error", err_msg)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = SimulationUI()
    win.show()
    sys.exit(app.exec())
