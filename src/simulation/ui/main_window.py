import os
import sys
from pathlib import Path
from copy import deepcopy
import numpy as np
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QComboBox, QPushButton, QDoubleSpinBox, QCheckBox,
    QGroupBox, QFormLayout, QMessageBox, QFileDialog, QProgressBar,
    QScrollArea, QSizePolicy, QDialog, QStyle
)
from PySide6.QtCore import Qt, QThread, Signal, QPointF, QSize, QTimer
from PySide6.QtGui import QColor, QBrush, QPainter, QPen, QPolygonF
from scipy.spatial.transform import Rotation as R

# Import logic modules
from src.simulation.engine import MuJoCoEngine
from src.simulation.engine.robot_sequence import RobotSequenceEngine, SequenceFailure
from src.simulation.robot_partial import retain_partial
from src.simulation.scenarios import Scenarios
from src.simulation.data_exporter import DataExporter
from src.utils.qt_sections import CollapsibleSection
from src.simulation.mode_profiles import ModeProfiles, require_executable, BLOCKED_REASON, drop_step
from .mode_settings import ModeSettings, preset_steps


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
            f"Box rotation (°) X / Y / Z: {self.euler[0]:.1f}, {self.euler[1]:.1f}, {self.euler[2]:.1f}"
        )

def simulation_error_message(error):
    return '\n'.join([f'Simulation Failed: {error}', *getattr(error, '__notes__', [])])


class SimulationThread(QThread):
    finished_signal = Signal(str)
    error_signal = Signal(str)
    cancelled_signal = Signal()
    progress_signal = Signal(float,float,str)

    def __init__(self, engine, params, filepath):
        super().__init__()
        self.engine = engine
        self.params = deepcopy(params)
        self.filepath = filepath
        self.partial_path=None;self.partial_error=None

    def run(self):
        try:
            # 1. Build initial state
            self.engine.set_initial_state(self.params['height'], self.params['quat'])

            # 2. Run headless (viewer is disabled in thread to prevent GLFW crash)
            history = self.engine.run_simulation(show_viewer=False, stop_condition_time=self.params['duration'],
                cancelled=self.isInterruptionRequested,progress=lambda current,limit:self.progress_signal.emit(current,limit,sequence_progress(self.engine)))

            # 3. Export
            exporter = DataExporter.from_engine(history, self.engine, self.params)
            output_path = exporter.export_proc_csv(self.filepath, cancelled=self.isInterruptionRequested)

            self.finished_signal.emit(output_path)

        except SequenceFailure as error:
            self.partial_path=save_partial(self.engine,self.filepath,error)
            if self.partial_path is None:self.partial_error='\n'.join(getattr(error,'__notes__',[])) or None
            if isinstance(error,InterruptedError):self.cancelled_signal.emit()
            else:self.error_signal.emit(simulation_error_message(error))
        except InterruptedError:
            self.cancelled_signal.emit()
        except Exception as e:
            self.error_signal.emit(simulation_error_message(e))


def sequence_progress(engine):
    if not isinstance(engine,RobotSequenceEngine) or engine.current_phase is None:return 'Running'
    phase=engine.current_phase;selected=engine.plan['selected_step_ids'];step=phase['step_id']
    index=selected.index(step)+1 if step in selected else 0
    return f"Drop {index} / {len(selected)} — {phase['kind']}"


def save_partial(engine,filepath,error):
    if not isinstance(engine,RobotSequenceEngine) or not engine.history:return None
    try:
        partial=retain_partial(filepath,engine);error.add_note('Partial capture: '+partial);return partial
    except Exception as failure:
        error.add_note('Partial capture was not saved: '+str(failure));return None

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
                or getattr(self, '_busy', False)):
            event.ignore()
            return
        super().closeEvent(event)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Simulation")
        # Leave room for the robot settings and target at startup, while keeping
        # the native title bar and borders inside the screen's usable area.
        available = self.screen().availableGeometry()
        border = self.style().pixelMetric(QStyle.PM_DefaultFrameWidth)
        title = self.style().pixelMetric(QStyle.PM_TitleBarHeight)
        self.resize(min(1280, available.width() - 2 * border - 24),
                    min(900, available.height() - title - 2 * border - 24))
        self.profiles = ModeProfiles()
        self._loading = True
        self._busy = False
        self._generation = 0
        self.result_history = []
        self.previous_result = None
        self.result_current = False
        self._robot_initialized = False
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
        self._init_mode_workspace(btn_layout)
        self._loading = False
        for control in self._value_controls(): control.valueChanged.connect(self._configuration_changed)
        for control in (self.noise_cb, self.viewer_cb): control.toggled.connect(self._configuration_changed)
        self._configuration_changed()

    def _init_mode_workspace(self, buttons):
        mode_row = QHBoxLayout(); mode_row.addWidget(QLabel('Mode'))
        self.mode_combo = QComboBox(); self.mode_combo.addItem('Single drop', 'single_drop'); self.mode_combo.addItem('Robot sequence', 'robot_sequence')
        mode_row.addWidget(self.mode_combo, 1)
        self.settings_button = QPushButton('Settings…'); mode_row.addWidget(self.settings_button)
        self.drop_combo.parentWidget().layout().takeRow(self.orientation_preview)
        self.orientation_preview.setParent(None)
        self.layout.removeWidget(self.experimental_label)
        self.layout.removeWidget(self.form_scroll); self.layout.removeItem(buttons); self.layout.removeWidget(self.progress_bar)
        self.workspace = QHBoxLayout(); self.layout.addLayout(self.workspace, 1)
        self.left_panel = QWidget(); left = QVBoxLayout(self.left_panel); left.setContentsMargins(0, 0, 0, 0)
        left.addWidget(self.experimental_label); left.addLayout(mode_row)
        left.addWidget(self.form_scroll, 1); left.addLayout(buttons); left.addWidget(self.progress_bar)
        self.cancel_run = QPushButton('Cancel'); self.cancel_run.clicked.connect(self.cancel_simulation); self.cancel_run.hide(); left.addWidget(self.cancel_run)
        self.result_label = QLabel(); self.result_label.setWordWrap(True); self.result_label.setTextFormat(Qt.PlainText); self.result_label.hide(); left.addWidget(self.result_label)
        left.addStretch()
        self.left_panel.setMaximumWidth(430); self.workspace.addWidget(self.left_panel, 1)
        self.settings = ModeSettings(self)
        self.right_scroll = QScrollArea(); self.right_scroll.setWidgetResizable(True)
        right_widget = QWidget(); right = QVBoxLayout(right_widget); right.setContentsMargins(4, 4, 4, 4)
        right.addWidget(self.settings)
        preview = QGroupBox('Preset target'); preview_layout = QVBoxLayout(preview); preview_layout.addWidget(self.orientation_preview)
        self.orientation_preview.setMinimumHeight(160)
        preview.setMinimumHeight(200); right.addWidget(preview, 1)
        self.right_scroll.setWidget(right_widget); self.workspace.addWidget(self.right_scroll, 2)
        self.preview_group = preview; self.preview_layout = preview_layout; self.right_layout = right
        self.settings_dialog = None; self._narrow = False
        self._action_tooltips = {button: button.toolTip() for button in (self.run_btn, self.batch_btn, self.marker_btn)}
        self.settings_button.clicked.connect(self._show_settings)
        self.mode_combo.currentIndexChanged.connect(self._switch_mode)
        self.settings.applied.connect(self._apply_profiles)
        self.settings.selected.connect(self._select_settings_step)
        self.settings.cancel_button.clicked.connect(lambda: self.settings_dialog.reject() if self.settings_dialog else None)
        for section in (self.rotation_section, self.physics_section, self.noise_section):
            section.button.toggled.connect(lambda *_: QTimer.singleShot(0, self._fit_form))
        self._fit_form()

    def _fit_form(self):
        self.form_layout.invalidate()
        self.form_layout.activate()
        height = self.form_layout.sizeHint().height()
        self.form_scroll.widget().setMinimumHeight(height)
        self.form_scroll.setMaximumHeight(height+2*self.form_scroll.frameWidth())

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, 'preview_group'): self._adapt_layout()

    def _adapt_layout(self):
        narrow = self.width() < 1050
        if narrow == self._narrow: return
        self._narrow = narrow
        if narrow:
            self.orientation_preview.setMinimumHeight(180)
            self.preview_layout.removeWidget(self.orientation_preview)
            self.form_layout.insertWidget(self.form_layout.count()-1, self.orientation_preview)
            self.right_scroll.hide(); self.left_panel.setMaximumWidth(16777215)
        else:
            self.orientation_preview.setMinimumHeight(160)
            self.form_layout.removeWidget(self.orientation_preview); self.preview_layout.addWidget(self.orientation_preview)
            self.right_scroll.show(); self.left_panel.setMaximumWidth(430)
        self._fit_form()
        QTimer.singleShot(0, self._fit_form)

    def _show_settings(self):
        if not self._narrow:
            self.right_scroll.ensureWidgetVisible(self.settings); self.settings.tabs.setFocus(); return
        if self.settings_dialog is not None: self.settings_dialog.raise_(); return
        dialog = QDialog(self); dialog.setWindowTitle('Simulation settings'); dialog.resize(820, 600)
        layout = QVBoxLayout(dialog); scroll = QScrollArea(); scroll.setWidgetResizable(True)
        self.right_layout.removeWidget(self.settings); scroll.setWidget(self.settings); layout.addWidget(scroll)
        self.settings_dialog = dialog
        def restore(_):
            if dialog.result() == QDialog.Rejected: self.settings.cancel_settings()
            scroll.takeWidget(); self.right_layout.insertWidget(0, self.settings)
            self.settings_dialog = None; dialog.deleteLater()
        dialog.finished.connect(restore); dialog.open()

    def _value_controls(self):
        return (self.w_input, self.d_input, self.h_input, self.mass_input, self.friction_input,
            self.elasticity_input, self.com_x, self.com_y, self.com_z, self.custom_h_input,
            self.custom_r_input, self.custom_p_input, self.custom_y_input, self.duration_input, self.noise_std_input)

    def _capture_config(self):
        config = deepcopy(self.profiles.configs[self.profiles.mode])
        config['size_mm'] = [self.w_input.value(), self.d_input.value(), self.h_input.value()]
        physics = config['physics_profile']
        physics.update(mass_kg=self.mass_input.value(), friction=self.friction_input.value(),
            contact_damping_control=self.elasticity_input.value(), com_offset_mm=[self.com_x.value(), self.com_y.value(), self.com_z.value()])
        config.update(duration_s=self.duration_input.value(), show_viewer=self.viewer_cb.isChecked())
        config['observation_profile']['corner'].update(enabled=self.noise_cb.isChecked(), std_mm=self.noise_std_input.value())
        if config['mode'] == 'single_drop':
            old = config['sequence_profile']['steps'][0]
            config['sequence_profile']['steps'] = [drop_step(self.cat_combo.currentData(), self.drop_combo.currentData().id,
                self.custom_h_input.value(), [self.custom_r_input.value(), self.custom_p_input.value(), self.custom_y_input.value()], step_id=old['step_id'])]
        return config

    def _configuration_changed(self, *_):
        if self._loading: return
        config = self._capture_config()
        if config != self.profiles.configs[self.profiles.mode]:
            self._invalidate_result('Settings changed. Previous results are preserved.')
            try: self.profiles.set_config(config)
            except ValueError as error: self.settings.status.setText(str(error)); return
        self.settings.reset(self.profiles)
        self._set_busy(self._busy)
        self._fit_form()

    def _invalidate_result(self, message, *, marker_source_changed=True):
        self.result_current = False
        dialog = self.marker_dialog
        if marker_source_changed and dialog is not None:
            dialog.source_stale = True
            if dialog.busy: dialog.cancel()
            dialog.status.setText('Simulation source changed. Reopen Marker CSV to use the current settings.')
            dialog._update_actions()
        if self._busy: self.cancel_simulation(message)
        elif self.previous_result:
            self.result_label.setText(message+' Previous result: '+self.previous_result); self.result_label.show()

    def _switch_mode(self):
        if self._loading: return
        self._configuration_changed()
        target = self.mode_combo.currentData()
        if target == self.profiles.mode: return
        if target == 'robot_sequence' and not self._robot_initialized:
            config = deepcopy(self.profiles.configs[target]); current = self.profiles.configs['single_drop']
            config['size_mm'] = deepcopy(current['size_mm']); config['physics_profile'] = deepcopy(current['physics_profile'])
            config['sequence_profile']['steps'] = preset_steps(self.cat_combo.currentData(), config['size_mm'], config['physics_profile']['mass_kg'])
            self.profiles.set_config(config); self._robot_initialized = True
        self._invalidate_result('Mode changed. Previous results are preserved.')
        self.profiles.switch(target); self._load_config()

    def _load_config(self):
        self._loading = True
        self.duration_input.setMaximum(3600 if self.profiles.mode=='robot_sequence' else 60)
        config = self.profiles.configs[self.profiles.mode]; physics = config['physics_profile']; corner = config['observation_profile']['corner']
        for control, value in zip(self._value_controls(), [*config['size_mm'], physics['mass_kg'], physics['friction'], physics['contact_damping_control'],
                *physics['com_offset_mm'], *([config['sequence_profile']['steps'][0]['clearance_mm'], *config['sequence_profile']['steps'][0]['fixed_xyz_deg']]), config['duration_s'], corner['std_mm']]):
            control.blockSignals(True); control.setValue(value); control.blockSignals(False)
        self.noise_cb.setChecked(corner['enabled']); self.viewer_cb.setChecked(config['show_viewer'])
        self.mode_combo.setCurrentIndex(self.mode_combo.findData(self.profiles.mode))
        self._display_step(config['sequence_profile']['steps'][0])
        self._loading = False
        self.settings.reset(self.profiles); self._set_busy(self._busy)

    def _display_step(self, step):
        self.cat_combo.blockSignals(True); self.cat_combo.setCurrentIndex(self.cat_combo.findData(step['category'])); self.cat_combo.blockSignals(False)
        self.drop_combo.blockSignals(True); self.drop_combo.clear()
        for spec in Scenarios.get_drop_sequence_specs(step['category']):
            text = spec.id.replace('_', ' ').replace('RotationalEdge', 'Rotational edge').replace('BottomLong', 'bottom long').replace('BottomShort', 'bottom short').replace('MostCritical DefaultFace6', 'critical face 6 default')
            self.drop_combo.addItem(text, spec); self.drop_combo.setItemData(self.drop_combo.count()-1, spec.id, Qt.ToolTipRole)
        index = next(i for i in range(self.drop_combo.count()) if self.drop_combo.itemData(i).id == step['preset_id'])
        self.drop_combo.setCurrentIndex(index); self.drop_combo.blockSignals(False)
        self.drop_combo.setToolTip(step['preset_id'])
        for control, value in zip((self.custom_h_input, self.custom_r_input, self.custom_p_input, self.custom_y_input), [step['clearance_mm'], *step['fixed_xyz_deg']]):
            control.blockSignals(True); control.setValue(value); control.blockSignals(False)
        spec = self.drop_combo.currentData()
        self.base_h = Scenarios.calculate_drop_height(step['category'], spec, self.mass_input.value())
        self.base_r, self.base_p, self.base_y = Scenarios.get_euler_angles(spec,
            (self.w_input.value(), self.d_input.value(), self.h_input.value()), category=step['category'])
        self._check_for_modifications(); self._update_orientation_preview()

    def _select_settings_step(self, step):
        if self._busy: return
        if step is None:
            self.preview_group.setTitle('Previous valid preview'); return
        draft = self.settings.draft.configs[self.settings.draft.mode]
        # Selecting a draft row previews it; it never applies or discards draft
        # physics/observation fields or searches an unrelated live category.
        if self.profiles.mode == self.settings.draft.mode == 'robot_sequence':
            self._display_step(step)
        spec = next(spec for spec in Scenarios.get_drop_sequence_specs(step['category']) if spec.id == step['preset_id'])
        self.orientation_preview.set_preview_state(tuple(draft['size_mm']), tuple(step['fixed_xyz_deg']), spec, step['category'])
        live = self.profiles.configs[self.profiles.mode]
        applied = self.profiles.mode == self.settings.draft.mode and step in live['sequence_profile']['steps'] and draft['size_mm'] == live['size_mm']
        self.preview_group.setTitle('Preset target' if applied else 'Settings preview')
        self._fit_form()

    def _apply_profiles(self, state):
        if self._busy: return
        self._invalidate_result('Settings applied. Previous results are preserved.')
        # Keep the current edit chain when adopting a separately loaded draft.
        # The imported document remains an explicit source snapshot in memory.
        self.settings_sources = getattr(self, 'settings_sources', []) + [state.document()]
        for config in state.configs.values(): self.profiles.set_config(config)
        self.profiles.switch(state.mode); self._robot_initialized = True; self._load_config()
        if self.settings_dialog is not None: self.settings_dialog.accept()

    def _set_busy(self, busy):
        self._busy = busy; robot = self.profiles.mode == 'robot_sequence'
        self.mode_combo.setEnabled(not busy); self.settings_button.setEnabled(not busy)
        self.form_scroll.setEnabled(not busy); self.settings.setEnabled(not busy)
        for control in (self.cat_combo, self.drop_combo, self.custom_h_input, self.rotation_section): control.setEnabled(not busy and not robot)
        reason=None
        if robot:
            try:require_executable(self._capture_config())
            except ValueError as error:reason=str(error)
        for button in (self.run_btn,self.marker_btn):
            button.setEnabled(not busy and reason is None);button.setToolTip(reason or self._action_tooltips[button])
        self.batch_btn.setEnabled(not busy and not robot)
        self.batch_btn.setToolTip('Use Run for one continuous robot plan.' if robot and reason is None else reason or self._action_tooltips[self.batch_btn])
        label=self.duration_input.parentWidget().layout().labelForField(self.duration_input)
        if label is not None:label.setText('Run time limit (s):' if robot else 'Duration (s):')
        self.progress_bar.setVisible(busy); self.cancel_run.setVisible(busy)
        self.cancel_run.setEnabled(busy and getattr(self, '_cancel_message', None) is None)
        if not busy: self.settings.select_row()

    def cancel_simulation(self, message='Cancelled. Previous results are preserved.'):
        if not self._busy: return
        self._generation += 1; self._cancel_message = message; self.cancel_run.setEnabled(False)
        self.result_label.setText('Cancelling…'+(' Previous result: '+self.previous_result if self.previous_result else '')); self.result_label.show()
        worker = self.__dict__.get('thread')
        if isinstance(worker, QThread) and worker.isRunning(): worker.requestInterruption()

    def _execution_config(self):
        config = self._capture_config(); require_executable(config); return config

    def open_marker_export(self):
        if self._busy: return
        try: config = self._execution_config()
        except ValueError as error: QMessageBox.warning(self, 'Cannot run', str(error)); return
        from src.simulation.ui.marker_export_dialog import MarkerExportDialog
        physics=config['physics_profile']
        simulation=dict(self._params(config),mass=physics['mass_kg'],friction=physics['friction'],
            elasticity=physics['contact_damping_control'],com_offset=tuple(physics['com_offset_mm']))
        self.marker_dialog = MarkerExportDialog(simulation,
            (self.w_input.value(), self.d_input.value(), self.h_input.value()), self)
        # Window modality preserves the captured Simulation inputs until close.
        self.marker_dialog.setWindowModality(Qt.WindowModal)
        self.marker_dialog.setAttribute(Qt.WA_DeleteOnClose)
        self.marker_dialog.finished.connect(lambda _: setattr(self, 'marker_dialog', None))
        self.marker_dialog.open_observations.connect(self._open_marker_observations)
        self.marker_dialog.settings_captured.connect(self._marker_settings_captured)
        self.marker_dialog.show()

    def _marker_settings_captured(self, marker):
        config = self._capture_config(); config['observation_profile']['marker'] = deepcopy(marker)
        self.profiles.set_config(config); self._invalidate_result('Observation settings changed. Previous results are preserved.', marker_source_changed=False)
        self.settings.reset(self.profiles)

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
            control.setToolTip("Box orientation: rotate about the scene X, then Y, then Z axes. Z points up. Values are angles in degrees.")
            rotation_form.addRow(f"{axis} rotation (°):", control)
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
        if hasattr(self, 'settings') and self.profiles.mode == 'robot_sequence' and not self._loading:
            self._update_orientation_preview(); self._configuration_changed(); return
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
        if hasattr(self, 'settings'): self._configuration_changed()

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

    @staticmethod
    def _params(config, *, viewer=None):
        step = config['sequence_profile']['steps'][0]
        corner = config['observation_profile']['corner']
        return dict(height=step['clearance_mm'], quat=Scenarios.get_orientation_from_euler(*step['fixed_xyz_deg']),
            add_noise=corner['enabled'], noise_std=corner['std_mm'], noise_seed=corner['seed'],
            show_viewer=config['show_viewer'] if viewer is None else viewer,
            duration=config['duration_s'], mode_config=deepcopy(config))

    @staticmethod
    def _engine(config):
        if config['mode']=='robot_sequence':return RobotSequenceEngine(config)
        physics = config['physics_profile']
        return MuJoCoEngine(size=tuple(config['size_mm']), mass=physics['mass_kg'],
            friction=physics['friction'], elasticity=physics['contact_damping_control'], com_offset=tuple(physics['com_offset_mm']))

    def run_simulation(self):
        if self._busy: return
        try: self._execution_config()
        except ValueError as error: QMessageBox.warning(self, 'Cannot run', str(error)); return
        filepath, _ = QFileDialog.getSaveFileName(self, 'Save Simulation Data', str(Path('data') / 'sim_data.proc'), 'PROC Files (*.proc)')
        if not filepath: return
        try:
            config = self._execution_config(); params = self._params(config); engine = self._engine(config)
        except Exception as error: self.on_sim_error(simulation_error_message(error)); return
        self._job_config = deepcopy(config)
        self._generation += 1; generation = self._generation; self._cancel_message = None
        self._set_busy(True); self.progress_bar.setRange(0, 100); self.progress_bar.setValue(0)
        self.result_label.setText('Running…'+(' Previous result: '+self.previous_result if self.previous_result else '')); self.result_label.show()
        if params['show_viewer']:
            # GLFW stays on the main thread. Engine checkpoints dispatch Cancel
            # and then test the captured generation before stepping/publishing.
            try:
                engine.set_initial_state(params['height'], params['quat'])
                history = engine.run_simulation(show_viewer=True, stop_condition_time=params['duration'],
                    cancelled=lambda: generation != self._generation,
                    progress=lambda current,limit:self._viewer_progress(engine,generation,current,limit))
                exporter = DataExporter.from_engine(history, engine, params)
                output = exporter.export_proc_csv(filepath, cancelled=lambda: generation != self._generation)
                self._set_busy(False)
                if generation == self._generation: self.on_sim_finished(output)
                else: self._show_cancelled()
            except SequenceFailure as error:
                partial=save_partial(engine,filepath,error);self._record_partial(partial,config,engine.sequence_evidence['completion'])
                if isinstance(error,InterruptedError):
                    self._set_busy(False);self._show_cancelled(partial,'\n'.join(getattr(error,'__notes__',[])) if partial is None else None)
                else:self.on_sim_error(simulation_error_message(error))
            except InterruptedError: self._set_busy(False); self._show_cancelled()
            except Exception as error: self.on_sim_error(simulation_error_message(error))
        else: self._start_worker(engine, params, filepath, batch=False)

    def _start_worker(self, engine, params, filepath, *, batch):
        self._job_config = deepcopy(params['mode_config'])
        worker = SimulationThread(engine, params, filepath); self.thread = worker; self._active_worker = worker
        generation = self._generation
        outcome = dict(kind='cancelled', value=None)
        # Do not restore controls or replace a running QThread from its custom
        # result signal: it has not exited yet. Adopt only on QThread.finished.
        worker.finished_signal.connect(lambda path: outcome.update(kind='success', value=path))
        worker.error_signal.connect(lambda error: outcome.update(kind='error', value=error))
        worker.cancelled_signal.connect(lambda: outcome.update(kind='cancelled', value=None))
        if isinstance(engine,RobotSequenceEngine):
            worker.progress_signal.connect(lambda current,limit,label:self._worker_progress(worker,generation,current,limit,label))
        worker.finished.connect(lambda: self._worker_finished(worker, generation, outcome, batch))
        worker.start()

    def _worker_progress(self,worker,generation,current,limit,label):
        if self._active_worker is worker and self._generation==generation:self._show_progress(current,limit,label)

    def _viewer_progress(self,engine,generation,current,limit):
        QApplication.processEvents()
        if self._generation==generation:self._show_progress(current,limit,sequence_progress(engine))

    def _show_progress(self,current,limit,label):
        self.progress_bar.setValue(min(100,int(100*current/limit)))
        self.result_label.setText(f'{label} — {current:.3f} s'+(' Previous result: '+self.previous_result if self.previous_result else ''))

    def _record_partial(self,path,config,status):
        if path:self.result_history.append(dict(status=status,path=path,config=deepcopy(config),partial=True))

    def _worker_finished(self, worker, generation, outcome, batch):
        if self._active_worker is not worker: return
        self._active_worker = None
        partial=getattr(worker,'partial_path',None)
        partial_error=getattr(worker,'partial_error',None)
        if partial:self._record_partial(partial,worker.params['mode_config'],worker.engine.sequence_evidence['completion'])
        if generation != self._generation:
            self.result_history.append(dict(status='stale', path=outcome['value'] if outcome['kind'] == 'success' else None,
                config=deepcopy(worker.params['mode_config']), reason=self._cancel_message))
            self._set_busy(False); self._show_cancelled(partial,partial_error); return
        if outcome['kind'] == 'success':
            if batch: self._on_batch_step_finished(outcome['value'])
            else: self.on_sim_finished(outcome['value'])
        elif outcome['kind'] == 'error': self.on_sim_error(outcome['value'])
        else: self._set_busy(False); self._show_cancelled(partial,partial_error)

    def _show_cancelled(self,partial=None,partial_error=None):
        self.result_label.setText((self._cancel_message or 'Cancelled. Previous results are preserved.')+
            (' Partial capture: '+partial if partial else '')+(' '+partial_error if partial_error else '')+
            (' Previous result: '+self.previous_result if self.previous_result else ''))
        self.result_label.show()

    def run_batch_simulation(self):
        if self._busy: return
        try: self._execution_config()
        except ValueError as error: QMessageBox.warning(self, 'Cannot run', str(error)); return
        if self.profiles.mode=='robot_sequence':
            QMessageBox.warning(self,'Cannot run','Use Run for the captured continuous robot plan.');return
        directory = QFileDialog.getExistingDirectory(self, 'Select Directory to Save Batch Data', str(Path('data')))
        if not directory: return
        try: self._batch_config = self._execution_config()
        except ValueError as error: QMessageBox.warning(self, 'Cannot run', str(error)); return
        self._batch_cat = self._batch_config['sequence_profile']['steps'][0]['category']
        self._batch_sequences = Scenarios.get_drop_sequence_specs(self._batch_cat)
        self._batch_current_idx = 0; self._batch_dir = directory; self._batch_success_paths = []
        self._generation += 1; self._cancel_message = None; self._set_busy(True)
        self.progress_bar.setRange(0, len(self._batch_sequences)); self.progress_bar.setValue(0)
        self._run_next_batch_sequence()

    def _run_next_batch_sequence(self):
        if self._batch_current_idx >= len(self._batch_sequences): self._on_batch_completed(); return
        spec = self._batch_sequences[self._batch_current_idx]; config = deepcopy(self._batch_config)
        physics = config['physics_profile']; category = self._batch_cat
        # Preserve legacy batch full precision; no GUI rounding/resampling.
        angles = Scenarios.get_euler_angles(spec, config['size_mm'], category=category)
        config['sequence_profile']['steps'] = [drop_step(category, spec.id,
            Scenarios.calculate_drop_height(category, spec, physics['mass_kg']), [float(v) for v in angles])]
        config['show_viewer'] = False
        prefix = 'TypeG' if 'Type G' in category else 'TypeH'
        name = spec.id.replace(' ', '').replace('/', '_').replace('[Low]', '').replace('[High]', '')
        filepath = str(Path(self._batch_dir) / f'{prefix}_{name}.proc')
        try: self._start_worker(self._engine(config), self._params(config, viewer=False), filepath, batch=True)
        except Exception as error: self.on_sim_error(simulation_error_message(error))

    def _remember_result(self, path):
        self.previous_result = path
        config = self._job_config
        self.result_current = config == self._capture_config()
        self.result_history.append(dict(status='produced', path=path, config=deepcopy(config)))
        self.result_label.setText('Previous result: '+path); self.result_label.show()

    def _on_batch_step_finished(self, output_path):
        self._remember_result(output_path); self._batch_success_paths.append(output_path); self._batch_current_idx += 1
        self.progress_bar.setValue(self._batch_current_idx); self._run_next_batch_sequence()

    def _on_batch_completed(self):
        self._set_busy(False)
        QMessageBox.information(self, 'Batch Success', f'Successfully generated {len(self._batch_success_paths)} files in:\n{self._batch_dir}')

    def on_sim_finished(self, output_path):
        self._remember_result(output_path); self._set_busy(False)
        partial=self._job_config['mode']=='robot_sequence' and self._job_config['sequence_profile']['execution_plan']['completion_policy']=='partial'
        if partial:self.result_history[-1].update(status='partial',partial=True)
        QMessageBox.information(self, 'Partial plan saved' if partial else 'Success',
            ('Partial plan saved to:\n' if partial else 'Simulation completed and saved to:\n')+output_path+'\n\nYou can now load this in Data Analysis.')

    def on_sim_error(self, err_msg):
        self._set_busy(False)
        self.result_label.setText('Failed. Previous results are preserved.'+(' Previous result: '+self.previous_result if self.previous_result else '')); self.result_label.show()
        QMessageBox.critical(self, 'Error', err_msg)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = SimulationUI()
    win.show()
    sys.exit(app.exec())
