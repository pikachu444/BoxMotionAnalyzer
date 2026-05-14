import os
import sys
from pathlib import Path
import numpy as np
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QComboBox, QPushButton, QDoubleSpinBox, QCheckBox,
    QGroupBox, QFormLayout, QMessageBox, QFileDialog, QProgressBar
)
from PySide6.QtCore import Qt, QThread, Signal, QPointF, QSize
from PySide6.QtGui import QColor, QBrush, QPainter, QPen, QPolygonF
from scipy.spatial.transform import Rotation as R

# Import logic modules
from src.simulation.engine import MuJoCoEngine
from src.simulation.scenarios import Scenarios
from src.simulation.data_exporter import DataExporter


class OrientationPreviewWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.box_size = (1578.0, 930.0, 142.0)
        self.euler = (0.0, 0.0, 0.0)
        self.sequence_spec = None
        self.category = ""
        self.setMinimumSize(250, 180)

    def sizeHint(self):
        return QSize(260, 190)

    def set_preview_state(self, box_size, euler, sequence_spec, category):
        self.box_size = box_size
        self.euler = euler
        self.sequence_spec = sequence_spec
        self.category = category
        self.update()

    def _box_vertices(self):
        width, height, depth = self.box_size
        hx, hy, hz = width / 2.0, height / 2.0, depth / 2.0
        return np.array([
            [-hx, -hy, -hz],
            [hx, -hy, -hz],
            [hx, hy, -hz],
            [-hx, hy, -hz],
            [-hx, -hy, hz],
            [hx, -hy, hz],
            [hx, hy, hz],
            [-hx, hy, hz],
        ], dtype=float)

    def _face_map(self):
        if "Type H" in self.category:
            return {
                1: [3, 2, 6, 7],
                2: [0, 1, 2, 3],
                3: [0, 1, 5, 4],
                4: [4, 5, 6, 7],
                5: [1, 2, 6, 5],
                6: [0, 3, 7, 4],
            }
        return {
            1: [0, 1, 2, 3],
            2: [0, 1, 5, 4],
            3: [4, 5, 6, 7],
            4: [3, 2, 6, 7],
            5: [1, 2, 6, 5],
            6: [0, 3, 7, 4],
        }

    def _project(self, vertices):
        object_rot = R.from_euler("xyz", self.euler, degrees=True)
        # Floor-first preview: keep the world-down direction easy to read.
        # Keep camera roll at zero so the preview is not visually skewed.
        camera_rot = R.from_euler("xyz", [60.0, -18.0, 0.0], degrees=True)
        transformed = camera_rot.apply(object_rot.apply(vertices))
        projected = transformed[:, [0, 1]]
        depth = transformed[:, 2]
        return projected, depth

    def _to_widget_points(self, projected):
        available_width = max(self.width() - 20, 1)
        available_height = max(self.height() - 30, 1)
        mins = projected.min(axis=0)
        maxs = projected.max(axis=0)
        spans = np.maximum(maxs - mins, 1e-6)
        scale = min(available_width / spans[0], available_height / spans[1]) * 0.75
        center = (mins + maxs) / 2.0

        points = []
        for x_val, y_val in projected:
            px = (x_val - center[0]) * scale + self.width() / 2.0
            py = -(y_val - center[1]) * scale + self.height() / 2.0 + 6.0
            points.append(QPointF(px, py))
        return points

    def _get_visible_faces(self, face_map, depth):
        depth_by_face = {
            face_number: float(np.mean([depth[idx] for idx in indices]))
            for face_number, indices in face_map.items()
        }
        visible = set()
        for first, second in ((1, 3), (2, 4), (5, 6)):
            if depth_by_face[first] >= depth_by_face[second]:
                visible.add(first)
            else:
                visible.add(second)
        return visible

    def _contact_text(self):
        if self.sequence_spec is None or not getattr(self.sequence_spec, "faces", None):
            return "Contact: N/A"
        kind = str(getattr(self.sequence_spec, "kind", "contact")).capitalize()
        faces = "-".join(str(number) for number in self.sequence_spec.faces)
        return f"Contact: {kind} {faces}"

    def _draw_fixed_axes(self, painter):
        center = np.array([self.width() - 56.0, 48.0])
        axis_length = 24.0
        # Screen-fixed icon so axis labels remain stable and easy to read.
        axes = (
            ("X", np.array([1.0, 0.0]), QColor("#d84315")),
            ("Y", np.array([0.0, -1.0]), QColor("#2e7d32")),
            ("Z", np.array([-0.68, 0.68]), QColor("#1565c0")),
        )
        painter.setPen(QColor("#607d8b"))
        painter.drawText(int(center[0] - 34), int(center[1] - 26), "Fixed Axes")

        for label, vec2, color in axes:
            norm = np.linalg.norm(vec2)
            if norm < 1e-8:
                continue
            end = center + vec2 / norm * axis_length
            painter.setPen(QPen(color, 2.0))
            painter.drawLine(
                QPointF(float(center[0]), float(center[1])),
                QPointF(float(end[0]), float(end[1])),
            )
            painter.setPen(color)
            painter.drawText(int(end[0] + 3), int(end[1] + 3), label)

    def _draw_contact_highlight(self, painter, face_map, widget_points, visible_faces):
        if self.sequence_spec is None or not getattr(self.sequence_spec, "faces", None):
            return

        contact_kind = str(getattr(self.sequence_spec, "kind", "")).lower()
        # Tip/rotational-edge sequences still reference a primary contact face in the UI.
        if contact_kind in {"tip", "rotational_edge"}:
            contact_kind = "face"

        highlighted_faces = list(self.sequence_spec.faces)
        shared_vertices = None
        for face_number in highlighted_faces:
            vertex_set = set(face_map.get(face_number, []))
            shared_vertices = vertex_set if shared_vertices is None else shared_vertices & vertex_set

        if contact_kind == "face" and highlighted_faces:
            face_vertices = face_map.get(highlighted_faces[0])
            if not face_vertices:
                return
            is_visible = highlighted_faces[0] in visible_faces
            pen = QPen(QColor("#fb8c00") if is_visible else QColor(251, 140, 0, 170), 3 if is_visible else 2)
            if not is_visible:
                pen.setStyle(Qt.DashLine)
            painter.setPen(pen)
            painter.setBrush(Qt.NoBrush)
            painter.drawPolygon(QPolygonF([widget_points[idx] for idx in face_vertices]))
            return

        if contact_kind == "edge" and shared_vertices and len(shared_vertices) == 2:
            points = [widget_points[idx] for idx in sorted(shared_vertices)]
            # Edge/corner contacts remain visible when at least one adjacent face is front-facing.
            is_visible = any(face in visible_faces for face in highlighted_faces)
            pen = QPen(QColor("#ef6c00") if is_visible else QColor(239, 108, 0, 160), 4 if is_visible else 3)
            if not is_visible:
                pen.setStyle(Qt.DashLine)
            painter.setPen(pen)
            painter.drawLine(points[0], points[1])
            return

        if contact_kind == "corner" and shared_vertices and len(shared_vertices) == 1:
            point = widget_points[next(iter(shared_vertices))]
            is_visible = any(face in visible_faces for face in highlighted_faces)
            painter.setBrush(QBrush(QColor("#e53935")) if is_visible else Qt.NoBrush)
            corner_pen = QPen(QColor("#e53935") if is_visible else QColor(229, 57, 53, 170), 2.0)
            if not is_visible:
                corner_pen.setStyle(Qt.DashLine)
            painter.setPen(corner_pen)
            painter.drawEllipse(point, 6, 6)

    def paintEvent(self, event):
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.fillRect(self.rect(), QColor("#f7f9fb"))

        vertices = self._box_vertices()
        projected, depth = self._project(vertices)
        widget_points = self._to_widget_points(projected)
        face_map = self._face_map()
        visible_faces = self._get_visible_faces(face_map, depth)

        ordered_faces = sorted(
            face_map.items(),
            key=lambda item: float(np.mean([depth[idx] for idx in item[1]]))
        )

        highlight_faces = set(getattr(self.sequence_spec, "faces", ()))
        default_brush = QBrush(QColor("#d6dde5"))
        highlight_brush = QBrush(QColor("#ffe0b2"))
        edge_pen = QPen(QColor("#546e7a"), 1.3)

        for face_number, indices in ordered_faces:
            polygon = QPolygonF([widget_points[idx] for idx in indices])
            painter.setPen(edge_pen)
            painter.setBrush(highlight_brush if face_number in highlight_faces else default_brush)
            painter.drawPolygon(polygon)

        self._draw_contact_highlight(painter, face_map, widget_points, visible_faces)
        self._draw_fixed_axes(painter)

        painter.setPen(QColor("#455a64"))
        painter.drawText(10, 16, "Orientation Preview")
        painter.setPen(QColor("#546e7a"))
        painter.drawText(10, self.height() - 26, self._contact_text())
        painter.setPen(QColor("#607d8b"))
        painter.drawText(
            10,
            self.height() - 10,
            f"Fixed X {self.euler[0]:.1f}  Y {self.euler[1]:.1f}  Z {self.euler[2]:.1f}"
        )

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

        btn_layout = QHBoxLayout()
        self.run_btn = QPushButton("Run Current Sequence")
        self.run_btn.clicked.connect(self.run_simulation)

        self.batch_btn = QPushButton("Run Full Test Sequence (Batch)")
        self.batch_btn.clicked.connect(self.run_batch_simulation)

        btn_layout.addWidget(self.run_btn)
        btn_layout.addWidget(self.batch_btn)
        self.layout.addLayout(btn_layout)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.hide()
        self.layout.addWidget(self.progress_bar)

        self.layout.addStretch()

    def _init_box_group(self):
        group = QGroupBox("Box Parameters")
        form = QFormLayout(group)

        self.w_input = QDoubleSpinBox()
        self.w_input.setRange(10, 5000)
        self.w_input.setValue(1578.0) # Matches BOX_DIMS[0]

        self.d_input = QDoubleSpinBox()
        self.d_input.setRange(10, 5000)
        self.d_input.setValue(930.0) # Matches BOX_DIMS[1] (Height in legacy system)

        self.h_input = QDoubleSpinBox()
        self.h_input.setRange(10, 5000)
        self.h_input.setValue(142.0) # Matches BOX_DIMS[2] (Depth/Thickness in legacy system)

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
        self.com_z.setValue(0.0)

        self.com_y.setValue(-200.0) # Y is the height axis in legacy, offset here for tumbling
        self.com_y.setToolTip("A slight offset along the height axis (Y) is required for tumbling to occur during corner drops.")

        form.addRow("Width (Local X, mm):", self.w_input)
        form.addRow("Height (Local Y, mm):", self.d_input)
        form.addRow("Depth/Thickness (Local Z, mm):", self.h_input)
        form.addRow("Mass (kg):", self.mass_input)
        form.addRow("Friction:", self.friction_input)
        form.addRow("Restitution (Elasticity):", self.elasticity_input)
        form.addRow("CoM X Offset (Local mm):", self.com_x)
        form.addRow("CoM Y Offset (Local mm):", self.com_y)
        form.addRow("CoM Z Offset (Local mm):", self.com_z)

        self.layout.addWidget(group)

    def _init_scenario_group(self):
        group = QGroupBox("Drop Scenario (ISTA 6-Amazon.com SIOC)")
        form = QFormLayout(group)

        self.cat_combo = QComboBox()
        self.cat_combo.addItems(Scenarios.get_categories())
        self.cat_combo.currentIndexChanged.connect(self._on_cat_changed)

        self.drop_combo = QComboBox()
        self.drop_combo.currentIndexChanged.connect(self._update_custom_fields_from_scenario)

        self.custom_h_input = QDoubleSpinBox()
        self.custom_h_input.setRange(10, 10000)
        self.custom_h_input.setValue(810)

        self.custom_r_input = QDoubleSpinBox()
        self.custom_r_input.setRange(-180, 180)
        self.custom_r_input.setValue(0)

        self.custom_p_input = QDoubleSpinBox()
        self.custom_p_input.setRange(-180, 180)
        self.custom_p_input.setValue(0)

        self.custom_y_input = QDoubleSpinBox()
        self.custom_y_input.setRange(-180, 180)
        self.custom_y_input.setValue(0)

        self.preview_hint_label = QLabel(
            "Advanced: adjust fixed-axis X/Y/Z rotations about the box center for a manual perturbation. "
            "The preview updates live with Floor-First view and dashed hidden-contact cues."
        )
        self.preview_hint_label.setStyleSheet("color: gray; font-size: 11px;")
        self.preview_hint_label.setWordWrap(True)

        self.orientation_preview = OrientationPreviewWidget()

        self.info_label = QLabel("")
        self.info_label.setStyleSheet("color: #4CAF50; font-size: 11px;")
        self.info_label.setWordWrap(True)

        self.warning_label = QLabel("")
        self.warning_label.setStyleSheet("color: red; font-weight: bold; font-size: 11px;")
        self.warning_label.setWordWrap(True)

        # Connect manual user edits to trigger warning label
        self.custom_h_input.valueChanged.connect(self._check_for_modifications)
        self.custom_r_input.valueChanged.connect(self._check_for_modifications)
        self.custom_p_input.valueChanged.connect(self._check_for_modifications)
        self.custom_y_input.valueChanged.connect(self._check_for_modifications)

        # Connect mass/size input changes to update height/angles dynamically
        self.mass_input.valueChanged.connect(self._update_custom_fields_from_scenario)
        self.w_input.valueChanged.connect(self._update_custom_fields_from_scenario)
        self.d_input.valueChanged.connect(self._update_custom_fields_from_scenario)
        self.h_input.valueChanged.connect(self._update_custom_fields_from_scenario)
        self.custom_r_input.valueChanged.connect(self._update_orientation_preview)
        self.custom_p_input.valueChanged.connect(self._update_orientation_preview)
        self.custom_y_input.valueChanged.connect(self._update_orientation_preview)

        self.base_h, self.base_r, self.base_p, self.base_y = 810, 0, 0, 0

        form.addRow("Category:", self.cat_combo)
        form.addRow("Drop Sequence:", self.drop_combo)
        form.addRow("Height (mm):", self.custom_h_input)
        form.addRow("Fixed X Rot (deg):", self.custom_r_input)
        form.addRow("Fixed Y Rot (deg):", self.custom_p_input)
        form.addRow("Fixed Z Rot (deg):", self.custom_y_input)
        form.addRow("", self.preview_hint_label)
        form.addRow("Preview:", self.orientation_preview)
        form.addRow("", self.info_label)
        form.addRow("", self.warning_label)

        self.layout.addWidget(group)
        self._on_cat_changed() # Trigger initial population

    def _on_cat_changed(self):
        cat = self.cat_combo.currentText()

        self.drop_combo.blockSignals(True)
        self.drop_combo.clear()
        for spec in Scenarios.get_drop_sequence_specs(cat):
            self.drop_combo.addItem(spec.id, spec)
        self.drop_combo.blockSignals(False)
        self._update_custom_fields_from_scenario()

    def _update_custom_fields_from_scenario(self):
        cat = self.cat_combo.currentText()
        if self.drop_combo.count() == 0:
            return

        seq_spec = self.drop_combo.currentData()
        seq_name = self.drop_combo.currentText()
        mass = self.mass_input.value()
        box_size = (self.w_input.value(), self.d_input.value(), self.h_input.value())

        # Calculate dynamic height
        height = Scenarios.calculate_drop_height(cat, seq_spec or seq_name, mass)

        # Calculate euler angles passing category for correct face numbering
        roll, pitch, yaw = Scenarios.get_euler_angles(seq_spec or seq_name, box_size, category=cat)

        self.base_h, self.base_r, self.base_p, self.base_y = height, roll, pitch, yaw

        # Generate Context Info String
        is_type_g = "Type G" in cat
        weight_str = "< 32kg" if mass < 32.0 else ">= 32kg"
        drop_type_str = "High Drop" if "High" in seq_name else "Standard Drop" if is_type_g else ("Tip" if "Tip" in seq_name else "Drop")

        info_text = f"ℹ Standard Height: {height}mm (Rule: {cat.split(' ')[2]}, Mass {weight_str}, {drop_type_str})"
        self.info_label.setText(info_text)

        # Temporarily block signals so setting the values programmatically doesn't trigger user modification warnings
        self.custom_h_input.blockSignals(True)
        self.custom_r_input.blockSignals(True)
        self.custom_p_input.blockSignals(True)
        self.custom_y_input.blockSignals(True)

        self.custom_h_input.setValue(height)
        self.custom_r_input.setValue(roll)
        self.custom_p_input.setValue(pitch)
        self.custom_y_input.setValue(yaw)
        self.warning_label.setText("")

        self.custom_h_input.blockSignals(False)
        self.custom_r_input.blockSignals(False)
        self.custom_p_input.blockSignals(False)
        self.custom_y_input.blockSignals(False)
        self._update_orientation_preview()

    def _check_for_modifications(self):
        """Checks if current spinbox values deviate from the standard scenario base values."""
        h = self.custom_h_input.value()
        r = self.custom_r_input.value()
        p = self.custom_p_input.value()
        y = self.custom_y_input.value()

        # Check if values differ from base calculation
        if (abs(h - self.base_h) > 0.1 or abs(r - self.base_r) > 0.1 or
            abs(p - self.base_p) > 0.1 or abs(y - self.base_y) > 0.1):

            changes = []
            if abs(h - self.base_h) > 0.1: changes.append(f"Height ({self.base_h:.1f}➔{h:.1f})")
            if abs(r - self.base_r) > 0.1: changes.append(f"Roll ({self.base_r:.1f}➔{r:.1f})")
            if abs(p - self.base_p) > 0.1: changes.append(f"Pitch ({self.base_p:.1f}➔{p:.1f})")
            if abs(y - self.base_y) > 0.1: changes.append(f"Yaw ({self.base_y:.1f}➔{y:.1f})")

            self.warning_label.setText("⚠ Modified: " + ", ".join(changes))
        else:
            self.warning_label.setText("")

    def _update_orientation_preview(self):
        if self.drop_combo.count() == 0:
            return

        spec = self.drop_combo.currentData()
        box_size = (self.w_input.value(), self.d_input.value(), self.h_input.value())
        euler = (
            self.custom_r_input.value(),
            self.custom_p_input.value(),
            self.custom_y_input.value(),
        )
        self.orientation_preview.set_preview_state(box_size, euler, spec, self.cat_combo.currentText())

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

        # Always use the values from the spinboxes, because _update_custom_fields_from_scenario
        # ensures they are correctly populated based on the selection or custom user input.
        height = self.custom_h_input.value()
        quat = Scenarios.get_orientation_from_euler(
            self.custom_r_input.value(),
            self.custom_p_input.value(),
            self.custom_y_input.value()
        )

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

    def run_batch_simulation(self):
        cat = self.cat_combo.currentText()
        sequences = Scenarios.get_drop_sequence_specs(cat)

        if not sequences:
            return

        dir_path = QFileDialog.getExistingDirectory(self, "Select Directory to Save Batch Data", str(Path("data")))
        if not dir_path:
            return

        self.run_btn.setEnabled(False)
        self.batch_btn.setEnabled(False)
        self.progress_bar.setRange(0, len(sequences))
        self.progress_bar.setValue(0)
        self.progress_bar.show()

        self._batch_sequences = sequences
        self._batch_current_idx = 0
        self._batch_dir = dir_path
        self._batch_cat = cat
        self._batch_success_paths = []

        self._run_next_batch_sequence()

    def _run_next_batch_sequence(self):
        if self._batch_current_idx >= len(self._batch_sequences):
            self._on_batch_completed()
            return

        seq_spec = self._batch_sequences[self._batch_current_idx]
        seq_name = seq_spec.id
        mass = self.mass_input.value()
        box_size = (self.w_input.value(), self.d_input.value(), self.h_input.value())

        height = Scenarios.calculate_drop_height(self._batch_cat, seq_spec, mass)
        roll, pitch, yaw = Scenarios.get_euler_angles(seq_spec, box_size, category=self._batch_cat)
        quat = Scenarios.get_orientation_from_euler(roll, pitch, yaw)

        params = {
            'height': height,
            'quat': quat,
            'add_noise': self.noise_cb.isChecked(),
            'noise_std': self.noise_std_input.value(),
            'show_viewer': False, # Force headless for batch
            'duration': self.duration_input.value()
        }

        com_offset = (self.com_x.value(), self.com_y.value(), self.com_z.value())

        type_prefix = "TypeG" if "Type G" in self._batch_cat else "TypeH"
        clean_seq_name = seq_name.replace(" ", "").replace("/", "_").replace("[Low]", "").replace("[High]", "")
        file_name = f"{type_prefix}_{clean_seq_name}.proc"
        filepath = str(Path(self._batch_dir) / file_name)

        engine = MuJoCoEngine(
            size=box_size, mass=mass,
            friction=self.friction_input.value(),
            elasticity=self.elasticity_input.value(),
            com_offset=com_offset
        )

        self.thread = SimulationThread(engine, params, filepath)
        self.thread.finished_signal.connect(self._on_batch_step_finished)
        self.thread.error_signal.connect(self.on_sim_error)
        self.thread.start()

    def _on_batch_step_finished(self, output_path):
        self._batch_success_paths.append(output_path)
        self._batch_current_idx += 1
        self.progress_bar.setValue(self._batch_current_idx)
        self._run_next_batch_sequence()

    def _on_batch_completed(self):
        self.run_btn.setEnabled(True)
        self.batch_btn.setEnabled(True)
        self.progress_bar.hide()
        QMessageBox.information(self, "Batch Success", f"Successfully generated {len(self._batch_success_paths)} files in:\n{self._batch_dir}")

    def on_sim_finished(self, output_path):
        self.run_btn.setEnabled(True)
        self.batch_btn.setEnabled(True)
        self.progress_bar.hide()
        QMessageBox.information(self, "Success", f"Simulation completed and saved to:\n{output_path}\n\nYou can now load this in Data Analysis.")

    def on_sim_error(self, err_msg):
        self.run_btn.setEnabled(True)
        self.batch_btn.setEnabled(True)
        self.progress_bar.hide()
        QMessageBox.critical(self, "Error", err_msg)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = SimulationUI()
    win.show()
    sys.exit(app.exec())
