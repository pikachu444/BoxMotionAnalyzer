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
            history = self.engine.run_simulation(show_viewer=False, stop_condition_time=self.params['duration'])

            # 3. Export
            exporter = DataExporter(history, self.params['add_noise'], self.params['noise_std'])
            output_path = exporter.export_proc_csv(self.filepath)

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
        self.w_input.setValue(1570)

        self.d_input = QDoubleSpinBox()
        self.d_input.setRange(10, 5000)
        self.d_input.setValue(300)

        self.h_input = QDoubleSpinBox()
        self.h_input.setRange(10, 5000)
        self.h_input.setValue(950)

        self.mass_input = QDoubleSpinBox()
        self.mass_input.setRange(0.1, 10000)
        self.mass_input.setValue(25.0)

        # According to ASTM D4521 / TAPPI standards for corrugated board
        # Kinetic/Static friction is typically 0.4 to 0.6. We default to 0.5.
        self.friction_input = QDoubleSpinBox()
        self.friction_input.setRange(0.0, 5.0)
        self.friction_input.setSingleStep(0.1)
        self.friction_input.setValue(0.5)
        self.friction_input.setToolTip("Corrugated cardboard typical friction: 0.4 ~ 0.6")

        # Corrugated boxes absorb energy. Restitution (bounciness) is usually low.
        self.elasticity_input = QDoubleSpinBox()
        self.elasticity_input.setRange(0.0, 1.0)
        self.elasticity_input.setSingleStep(0.05)
        self.elasticity_input.setValue(0.15)
        self.elasticity_input.setToolTip("Corrugated cardboard typical restitution: 0.1 ~ 0.2")

        self.com_x = QDoubleSpinBox()
        self.com_x.setRange(-2500, 2500)
        self.com_x.setValue(0.0)
        self.com_y = QDoubleSpinBox()
        self.com_y.setRange(-2500, 2500)
        self.com_y.setValue(0.0)
        self.com_z = QDoubleSpinBox()
        self.com_z.setRange(-2500, 2500)
        self.com_z.setValue(-200.0)
        self.com_z.setToolTip("A slight offset is required for tumbling to occur during corner drops in a perfect simulation.")

        form.addRow("Width (Local X, mm):", self.w_input)
        form.addRow("Depth (Local Y, mm):", self.d_input)
        form.addRow("Height (Local Z, mm):", self.h_input)
        form.addRow("Mass (kg):", self.mass_input)
        form.addRow("Friction:", self.friction_input)
        form.addRow("Restitution (Elasticity):", self.elasticity_input)
        form.addRow("CoM X Offset (Local mm):", self.com_x)
        form.addRow("CoM Y Offset (Local mm):", self.com_y)
        form.addRow("CoM Z Offset (Local mm):", self.com_z)

        self.layout.addWidget(group)

    def _init_scenario_group(self):
        group = QGroupBox("Drop Scenario (ISTA-6A)")
        form = QFormLayout(group)

        self.cat_combo = QComboBox()
        self.cat_combo.addItems(Scenarios.get_categories() + ["Custom"])
        self.cat_combo.currentIndexChanged.connect(self._on_cat_changed)

        self.drop_combo = QComboBox()
        self.drop_combo.addItems([
            "Flat_Bottom", "Flat_Top", "Flat_Front", "Flat_Back", "Flat_Left", "Flat_Right",
            "Edge_3_4 (Bottom-Right)", "Edge_3_5 (Front-Bottom)", "Corner_2-3-5 (Front-Bottom-Right)"
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
        group = QGroupBox("Simulation Settings & Visualization")
        form = QFormLayout(group)

        self.duration_input = QDoubleSpinBox()
        self.duration_input.setRange(0.5, 60.0)
        self.duration_input.setSingleStep(0.5)
        self.duration_input.setValue(2.0)

        self.viewer_cb = QCheckBox("Show 3D Viewer during Simulation")
        self.viewer_cb.setChecked(True)

        info_label = QLabel("Tip: When the 3D Viewer opens, you can use your Mouse:\n"
                            "- Left Click + Drag: Rotate Camera\n"
                            "- Right Click + Drag: Translate Camera\n"
                            "- Scroll: Zoom\n"
                            "- Double Click on Box: Apply physical perturbation (force)")
        info_label.setStyleSheet("color: gray; font-size: 11px;")

        form.addRow("Simulation Duration (s):", self.duration_input)
        form.addRow("", self.viewer_cb)
        form.addRow("", info_label)

        self.layout.addWidget(group)

    def run_simulation(self):
        # 1. Gather Params
        size = (self.w_input.value(), self.d_input.value(), self.h_input.value())
        mass = self.mass_input.value()
        friction = self.friction_input.value()
        elasticity = self.elasticity_input.value()

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
            'show_viewer': self.viewer_cb.isChecked(),
            'duration': self.duration_input.value()
        }

        com_offset = (self.com_x.value(), self.com_y.value(), self.com_z.value())

        # 2. Select Output File
        filepath, _ = QFileDialog.getSaveFileName(
            self, "Save Simulation Data", str(Path("data") / "sim_data.proc"), "PROC Files (*.proc)"
        )
        if not filepath:
            return

        # 3. Setup Engine
        self.run_btn.setEnabled(False)
        self.progress_bar.show()

        engine = MuJoCoEngine(size=size, mass=mass, friction=friction, elasticity=elasticity, com_offset=com_offset)

        # 4. Run Simulation
        if params['show_viewer']:
            # Run in main thread because mujoco.viewer (GLFW) MUST run on the main thread
            try:
                engine.set_initial_state(params['height'], params['quat'])
                history = engine.run_simulation(show_viewer=True, stop_condition_time=params['duration'])

                exporter = DataExporter(history, params['add_noise'], params['noise_std'])
                output_path = exporter.export_proc_csv(filepath)

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
