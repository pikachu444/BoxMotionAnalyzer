import os
import sys
from pathlib import Path
import numpy as np
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QComboBox, QPushButton, QDoubleSpinBox, QCheckBox,
    QGroupBox, QFormLayout, QMessageBox, QFileDialog, QProgressBar,
    QScrollArea, QSizePolicy
)
from PySide6.QtCore import Qt, QThread, Signal, QPointF, QSize
from PySide6.QtGui import QColor, QBrush, QPainter, QPen, QPolygonF
from scipy.spatial.transform import Rotation as R

# Import logic modules
from src.simulation.engine import MuJoCoEngine
from src.simulation.scenarios import Scenarios
from src.simulation.data_exporter import DataExporter
from src.utils.qt_sections import CollapsibleSection


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
        transformed = object_rot.apply(vertices) @ self._camera_basis().T
        projected = transformed[:, [0, 1]]
        depth = transformed[:, 2]
        return projected, depth

    @staticmethod
    def _camera_basis():
        """One world Z-up camera for both the box and the world-axis icon."""
        direction = np.ones(3) / np.sqrt(3)
        right = np.cross(-direction, [0., 0., 1.])
        right /= np.linalg.norm(right)
        up = np.cross(right, -direction)
        return np.array([right, up, direction])

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
            return "Preset target unavailable"
        kind = str(getattr(self.sequence_spec, "kind", "contact")).lower()
        kind = {"rotational_edge": "Rotational edge, face", "tip": "Tip, face"}.get(kind, kind.capitalize())
        faces = "-".join(str(number) for number in self.sequence_spec.faces)
        return f"Preset: {kind} {faces}"

    def _draw_fixed_axes(self, painter):
        center = np.array([self.width() - 56.0, 48.0])
        axis_length = 24.0
        projected_axes = np.eye(3) @ self._camera_basis().T
        for label, vector, color in zip("XYZ", projected_axes, (QColor("#d84315"), QColor("#2e7d32"), QColor("#1565c0"))):
            end = center + vector[:2] * [1., -1.] * axis_length
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
        painter.drawText(10, 16, "Initial pose")
        painter.setPen(QColor("#546e7a"))
        painter.drawText(10, self.height() - 26, self._contact_text())
        painter.setPen(QColor("#607d8b"))
        painter.drawText(
            10,
            self.height() - 10,
            f"Fixed XYZ (°): {self.euler[0]:.1f}, {self.euler[1]:.1f}, {self.euler[2]:.1f}"
        )

def simulation_error_message(error):
    return '\n'.join([f'Simulation Failed: {error}', *getattr(error, '__notes__', [])])


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
            exporter = DataExporter.from_engine(history, self.engine, self.params)
            output_path = exporter.export_proc_csv(self.filepath)

            self.finished_signal.emit(output_path)

        except Exception as e:
            self.error_signal.emit(simulation_error_message(e))

class SimulationUI(QWidget):
    def closeEvent(self, event):
        marker_dialog = getattr(self, 'marker_dialog', None)
        if marker_dialog is not None and marker_dialog.busy:
            marker_dialog.cancel()
            event.ignore()
            return
        worker = self.__dict__.get('thread')
        # Keep the worker and batch queue alive until their completion/error
        # callbacks have restored the controls, including the gap between jobs.
        if ((isinstance(worker, QThread) and worker.isRunning())
                or not self.run_btn.isEnabled()):
            event.ignore()
            return
        super().closeEvent(event)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Simulation")
        self.resize(500, 600)
        self.marker_dialog = None
        self.analysis_windows = []

        self.layout = QVBoxLayout(self)
        self.experimental_label = QLabel("Experimental")
        self.experimental_label.setStyleSheet("color: #916000;")
        self.experimental_label.setToolTip("Uncalibrated free-fall presets; supported Type H rotation and the Type G hazard block are not simulated.")
        self.layout.addWidget(self.experimental_label)

        self.form_scroll = QScrollArea()
        self.form_scroll.setWidgetResizable(True)
        self.form_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        form_widget = QWidget()
        self.form_layout = QVBoxLayout(form_widget)
        self.form_layout.setContentsMargins(4, 4, 4, 4)
        self.form_scroll.setWidget(form_widget)
        self.layout.addWidget(self.form_scroll, 1)

        self._init_box_group()
        self._init_scenario_group()
        self._init_export_group()
        self.form_layout.addWidget(self.physics_section)
        self._init_noise_group()
        self.form_layout.addStretch()

        btn_layout = QHBoxLayout()
        self.run_btn = QPushButton("Run")
        self.run_btn.clicked.connect(self.run_simulation)

        self.batch_btn = QPushButton("Run all presets")
        self.batch_btn.setToolTip("Run the existing free-fall presets; this is not a complete ISTA test sequence.")
        self.batch_btn.clicked.connect(self.run_batch_simulation)

        self.marker_btn = QPushButton("Marker CSV…")
        self.marker_btn.setToolTip('Generate synthetic observations for Step 1 using the current simulation inputs.')
        self.marker_btn.clicked.connect(self.open_marker_export)

        btn_layout.addWidget(self.run_btn)
        btn_layout.addWidget(self.batch_btn)
        btn_layout.addWidget(self.marker_btn)
        self.layout.addLayout(btn_layout)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.hide()
        self.layout.addWidget(self.progress_bar)

    def open_marker_export(self):
        if not self.run_btn.isEnabled():
            return
        from src.simulation.ui.marker_export_dialog import MarkerExportDialog
        simulation = dict(mass=self.mass_input.value(), friction=self.friction_input.value(),
            elasticity=self.elasticity_input.value(),
            com_offset=(self.com_x.value(), self.com_y.value(), self.com_z.value()),
            height=self.custom_h_input.value(), duration=self.duration_input.value(),
            quat=Scenarios.get_orientation_from_euler(self.custom_r_input.value(),
                self.custom_p_input.value(), self.custom_y_input.value()))
        self.marker_dialog = MarkerExportDialog(simulation,
            (self.w_input.value(), self.d_input.value(), self.h_input.value()), self)
        # Window modality preserves the captured Simulation inputs until close.
        self.marker_dialog.setWindowModality(Qt.WindowModal)
        self.marker_dialog.setAttribute(Qt.WA_DeleteOnClose)
        self.marker_dialog.finished.connect(lambda _: setattr(self, 'marker_dialog', None))
        self.marker_dialog.open_observations.connect(self._open_marker_observations)
        self.marker_dialog.show()

    def _open_marker_observations(self, filepath):
        from src.analysis.app.main_window import MainApp
        from src.utils.artifact_metadata import DIMENSIONS
        window = MainApp()
        try:
            raw = window.original_widget
            raw.load_csv_path(filepath)
            # Read this exported file, never the dialog's subsequently selected
            # layout or the separate truth/event files. Approval remains off.
            dimensions = raw.header_info['artifact_metadata']
            for edit, key in zip((raw.le_box_l, raw.le_box_w, raw.le_box_h), DIMENSIONS):
                edit.setText(str(dimensions[key]))
        except Exception as error:
            window.close()
            window.deleteLater()
            QMessageBox.warning(self.marker_dialog or self, 'Cannot open observations', str(error))
            return
        window.setAttribute(Qt.WA_DeleteOnClose)
        window.setWindowTitle('Synthetic observations: ' + Path(filepath).parent.name)
        self.analysis_windows.append(window)
        window.destroyed.connect(lambda: self.analysis_windows.remove(window))
        window.show()

    def _init_box_group(self):
        group = QGroupBox("Box")
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

        # Uncalibrated contact-model input, not a measured material property.
        self.friction_input = QDoubleSpinBox()
        self.friction_input.setRange(0.0, 5.0)
        self.friction_input.setSingleStep(0.1)
        self.friction_input.setValue(0.5)
        self.friction_input.setToolTip("MuJoCo sliding friction input; validate it against the intended surfaces.")

        # Preserve the legacy numeric control while describing its actual mapping.
        self.elasticity_input = QDoubleSpinBox()
        self.elasticity_input.setRange(0.0, 1.0)
        self.elasticity_input.setSingleStep(0.05)
        self.elasticity_input.setValue(0.15)
        self.elasticity_input.setToolTip("Sets solref damping ratio = max(0.01, 1 - value), with time constant 0.02 s. This is not a coefficient of restitution.")

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
        self.com_y.setToolTip("Assumed local COM offset; it can change contact dynamics. It is not required for all tumbling motion.")

        for widget, axis, meaning in ((self.w_input, "X", "width"), (self.d_input, "Y", "height"), (self.h_input, "Z", "depth")):
            widget.setToolTip(f"Box local {axis} {meaning} in mm. Simulation world Z is up; analysis world Y is up.")
        form.addRow("Width X (mm):", self.w_input)
        form.addRow("Height Y (mm):", self.d_input)
        form.addRow("Depth Z (mm):", self.h_input)
        form.addRow("Mass (kg):", self.mass_input)
        self.form_layout.addWidget(group)

        physics = QWidget()
        physics_form = QFormLayout(physics)
        physics_form.setContentsMargins(8, 0, 0, 0)
        physics_form.addRow("Friction:", self.friction_input)
        physics_form.addRow("Contact damping:", self.elasticity_input)
        for axis, control in (("X", self.com_x), ("Y", self.com_y), ("Z", self.com_z)):
            control.setToolTip(f"Local {axis} offset from the geometric box centre in mm. " + control.toolTip())
            physics_form.addRow(f"COM {axis} (mm):", control)
        self.physics_section = CollapsibleSection("Physics", physics)

    def _init_scenario_group(self):
        group = QGroupBox("Scenario")
        form = QFormLayout(group)

        self.cat_combo = QComboBox()
        for category in Scenarios.get_categories():
            self.cat_combo.addItem("Type G" if "Type G" in category else "Type H", category)
        self.cat_combo.setToolTip("SIOC free-fall presets. Type H supported rotation and the G17 hazard block are not simulated.")
        self.cat_combo.currentIndexChanged.connect(self._on_cat_changed)

        self.drop_combo = QComboBox()
        self.drop_combo.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
        self.drop_combo.setMinimumContentsLength(18)
        self.drop_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.drop_combo.currentIndexChanged.connect(self._update_custom_fields_from_scenario)

        self.custom_h_input = QDoubleSpinBox()
        self.custom_h_input.setRange(10, 10000)
        self.custom_h_input.setValue(810)
        self.custom_h_input.setToolTip("Initial vertical clearance from the lowest box corner to the floor, in mm.")

        self.custom_r_input = QDoubleSpinBox()
        self.custom_r_input.setRange(-180, 180)
        self.custom_r_input.setValue(0)

        self.custom_p_input = QDoubleSpinBox()
        self.custom_p_input.setRange(-180, 180)
        self.custom_p_input.setValue(0)

        self.custom_y_input = QDoubleSpinBox()
        self.custom_y_input.setRange(-180, 180)
        self.custom_y_input.setValue(0)

        self.orientation_preview = OrientationPreviewWidget()
        self.orientation_preview.setToolTip("Simulation world Z is up. Highlight shows the preset target, not a predicted contact after manual rotation.")

        self.warning_label = QLabel("")
        self.warning_label.setStyleSheet("color: #916000;")
        self.warning_label.hide()

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

        form.addRow("Type:", self.cat_combo)
        form.addRow("Preset:", self.drop_combo)
        form.addRow("Initial clearance (mm):", self.custom_h_input)
        form.addRow(self.orientation_preview)
        rotation = QWidget()
        rotation_form = QFormLayout(rotation)
        rotation_form.setContentsMargins(8, 0, 0, 0)
        for axis, control in (("X", self.custom_r_input), ("Y", self.custom_p_input), ("Z", self.custom_y_input)):
            control.setToolTip("Fixed world-axis XYZ rotation about the geometric box centre, in degrees; not a marker-local half-turn.")
            rotation_form.addRow(f"Fixed {axis} (°):", control)
        self.rotation_section = CollapsibleSection("Rotation", rotation)
        form.addRow(self.rotation_section)
        form.addRow(self.warning_label)

        self.form_layout.addWidget(group)
        self._on_cat_changed() # Trigger initial population

    def _on_cat_changed(self):
        cat = self.cat_combo.currentData()

        self.drop_combo.blockSignals(True)
        self.drop_combo.clear()
        for spec in Scenarios.get_drop_sequence_specs(cat):
            text = spec.id.replace("_", " ").replace("RotationalEdge", "Rotational edge").replace("BottomLong", "bottom long").replace("BottomShort", "bottom short")
            text = text.replace("MostCritical DefaultFace6", "critical face 6 default")
            self.drop_combo.addItem(text, spec)
            self.drop_combo.setItemData(self.drop_combo.count() - 1, spec.id, Qt.ToolTipRole)
        self.drop_combo.blockSignals(False)
        self._update_custom_fields_from_scenario()

    def _update_custom_fields_from_scenario(self):
        cat = self.cat_combo.currentData()
        if self.drop_combo.count() == 0:
            return

        seq_spec = self.drop_combo.currentData()
        seq_name = seq_spec.id
        self.drop_combo.setToolTip(seq_name)
        mass = self.mass_input.value()
        box_size = (self.w_input.value(), self.d_input.value(), self.h_input.value())

        # Calculate dynamic height
        height = Scenarios.calculate_drop_height(cat, seq_spec or seq_name, mass)

        # Calculate euler angles passing category for correct face numbering
        roll, pitch, yaw = Scenarios.get_euler_angles(seq_spec or seq_name, box_size, category=cat)

        self.base_h, self.base_r, self.base_p, self.base_y = height, roll, pitch, yaw

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
        self.warning_label.hide()

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

            self.warning_label.setText("Custom")
            self.warning_label.setToolTip(f"Preset clearance {self.base_h:g} mm; fixed XYZ {self.base_r:g}, {self.base_p:g}, {self.base_y:g} degrees.")
            self.warning_label.show()
        else:
            self.warning_label.setText("")
            self.warning_label.hide()

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
        self.orientation_preview.set_preview_state(box_size, euler, spec, self.cat_combo.currentData())

    def _init_noise_group(self):
        group = QWidget()
        layout = QVBoxLayout(group)

        self.noise_cb = QCheckBox("Corner noise")
        self.noise_cb.setToolTip("Seed 0 for repeatable stress data, not calibrated sensor noise. Body pose remains simulation truth.")
        self.noise_std_input = QDoubleSpinBox()
        self.noise_std_input.setRange(0.01, 100)
        self.noise_std_input.setValue(1.0)
        self.noise_std_input.setPrefix("Std (mm): ")

        layout.addWidget(self.noise_cb)
        layout.addWidget(self.noise_std_input)
        self.noise_section = CollapsibleSection("Noise", group)
        self.form_layout.addWidget(self.noise_section)

    def _init_export_group(self):
        group = QGroupBox("Run options")
        form = QFormLayout(group)

        self.duration_input = QDoubleSpinBox()
        self.duration_input.setRange(0.5, 60.0)
        self.duration_input.setSingleStep(0.5)
        self.duration_input.setValue(2.0)

        self.viewer_cb = QCheckBox("Show viewer")
        self.viewer_cb.setChecked(True)

        self.viewer_cb.setToolTip("Drag to rotate, right-drag to pan, scroll to zoom. Double-click applies a force to the box.")

        form.addRow("Duration (s):", self.duration_input)
        form.addRow("", self.viewer_cb)
        self.form_layout.addWidget(group)

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
        self.batch_btn.setEnabled(False)
        self.marker_btn.setEnabled(False)
        self.progress_bar.show()

        engine = MuJoCoEngine(size=size, mass=mass, friction=friction, elasticity=elasticity, com_offset=com_offset)

        # 4. Run Simulation
        if params['show_viewer']:
            # Run in main thread because mujoco.viewer (GLFW) MUST run on the main thread
            try:
                engine.set_initial_state(params['height'], params['quat'])
                history = engine.run_simulation(show_viewer=True, stop_condition_time=params['duration'])

                exporter = DataExporter.from_engine(history, engine, params)
                output_path = exporter.export_proc_csv(filepath)

                self.on_sim_finished(output_path)
            except Exception as e:
                self.on_sim_error(simulation_error_message(e))
        else:
            # Run headless in background thread
            self.thread = SimulationThread(engine, params, filepath)
            self.thread.finished_signal.connect(self.on_sim_finished)
            self.thread.error_signal.connect(self.on_sim_error)
            self.thread.start()

    def run_batch_simulation(self):
        cat = self.cat_combo.currentData()
        sequences = Scenarios.get_drop_sequence_specs(cat)

        if not sequences:
            return

        dir_path = QFileDialog.getExistingDirectory(self, "Select Directory to Save Batch Data", str(Path("data")))
        if not dir_path:
            return

        self.run_btn.setEnabled(False)
        self.batch_btn.setEnabled(False)
        self.marker_btn.setEnabled(False)
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
        self.marker_btn.setEnabled(True)
        self.progress_bar.hide()
        QMessageBox.information(self, "Batch Success", f"Successfully generated {len(self._batch_success_paths)} files in:\n{self._batch_dir}")

    def on_sim_finished(self, output_path):
        self.run_btn.setEnabled(True)
        self.batch_btn.setEnabled(True)
        self.marker_btn.setEnabled(True)
        self.progress_bar.hide()
        QMessageBox.information(self, "Success", f"Simulation completed and saved to:\n{output_path}\n\nYou can now load this in Data Analysis.")

    def on_sim_error(self, err_msg):
        self.run_btn.setEnabled(True)
        self.batch_btn.setEnabled(True)
        self.marker_btn.setEnabled(True)
        self.progress_bar.hide()
        QMessageBox.critical(self, "Error", err_msg)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = SimulationUI()
    win.show()
    sys.exit(app.exec())
