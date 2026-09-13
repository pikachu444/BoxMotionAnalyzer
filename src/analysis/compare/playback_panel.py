import numpy as np
import pandas as pd
from PySide6.QtWidgets import (QVBoxLayout, QHBoxLayout, QPushButton, QSlider, QLabel,
                               QGroupBox, QFrame, QScrollArea, QWidget, QSizePolicy, QLayout)
from PySide6.QtCore import Qt, QTimer, QElapsedTimer, Signal
from PySide6.QtGui import QColor

from src.visualization.vista_widget import VistaWidget
from src.config import config_visualization as k
from src.utils.result_time import ResultTimeline


class ComparePlaybackPanel(QGroupBox):
    elapsed_changed = Signal(float)
    sample_changed = Signal(str, int)

    def __init__(self, model):
        super().__init__('3D')
        self.setMinimumHeight(230)
        self.model = model
        self.widgets = {}
        self.local_controls = {}
        self.containers = {}
        self._dataset_versions = {}
        self.view_mode = 'individual'
        self.selected_file = None
        self.show_labels = False
        self.bounds = None
        self.current_elapsed = None
        self.clock = QElapsedTimer()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(3)
        controls = QHBoxLayout()
        self.btn_master_play = QPushButton('Play')
        self.btn_master_play.clicked.connect(self.toggle_master_playback)
        controls.addWidget(self.btn_master_play)
        self.master_slider = QSlider(Qt.Horizontal)
        self.master_slider.valueChanged.connect(self._on_master_slider_changed)
        self.master_slider.sliderPressed.connect(self.stop)
        controls.addWidget(self.master_slider, stretch=1)
        self.time_label = QLabel('No file')
        controls.addWidget(self.time_label)
        layout.addLayout(controls)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.viewers_widget = QWidget()
        self.viewers_layout = QHBoxLayout(self.viewers_widget)
        self.viewers_layout.setContentsMargins(0, 0, 0, 0)
        self.viewers_layout.setSpacing(4)
        self.viewers_layout.setSizeConstraint(QLayout.SetMinimumSize)
        self.scroll.setWidget(self.viewers_widget)
        layout.addWidget(self.scroll, stretch=1)
        self.master_timer = QTimer(self)
        self.master_timer.setInterval(30)
        self.master_timer.timeout.connect(self._on_master_timer)
        self.set_view('individual', None)

    def stop(self):
        self.master_timer.stop()
        self.btn_master_play.setText('Play')

    def set_labels_visible(self, visible):
        self.show_labels = visible
        for viewer in self.widgets.values():
            viewer.set_actor_visibility(k.SK_ACTOR_LABELS, visible)

    def refresh_viewers(self):
        """Keep live cameras and rows unless that file's data actually changed."""
        changed = set(self._dataset_versions) ^ set(self.model.datasets)
        changed.update(name for name, df in self.model.datasets.items()
                       if self._dataset_versions.get(name) is not df)
        if changed:
            self.stop()
        for name in changed:
            viewer = self.widgets.pop(name, None)
            if viewer is not None:
                viewer.cleanup()
            container = self.containers.pop(name, None)
            if container is not None:
                self.viewers_layout.removeWidget(container)
                container.deleteLater()
            self.local_controls.pop(name, None)
            self._dataset_versions.pop(name, None)
        for name, df in self.model.datasets.items():
            if name in self.containers:
                continue
            self._dataset_versions[name] = df
            container = QFrame()
            container.setMinimumWidth(230)
            layout = QVBoxLayout(container)
            layout.setContentsMargins(4, 2, 4, 2)
            layout.setSpacing(2)
            heading = QHBoxLayout()
            swatch = QLabel()
            swatch.setFixedSize(12, 5)
            swatch.setStyleSheet(f'background-color: {self.model.file_colors[name]}')
            heading.addWidget(swatch)
            title = QLabel()
            title.setText(title.fontMetrics().elidedText(name, Qt.ElideMiddle, 210))
            title.setTextFormat(Qt.PlainText)
            title.setToolTip(self.model.file_paths[name])
            title.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
            heading.addWidget(title, stretch=1)
            layout.addLayout(heading)
            handler = self.model.visualization_handlers.get(name)
            if handler is not None:
                viewer = VistaWidget(data_handler=handler)
                viewer.setMinimumSize(220, 125)
                viewer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Ignored)
                viewer.setToolTip('View follows box centre')
                layout.addWidget(viewer, stretch=1)
                self.widgets[name] = viewer
            label = QLabel()
            label.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
            layout.addWidget(label)
            self.local_controls[name] = {'label': label, 'title': title,
                                         'camera_initialized': False, 'last_box_centre': None, 'row': 0}
            self.containers[name] = container
            self.viewers_layout.addWidget(container)
        self.bounds = self.model.elapsed_bounds()
        self.set_view(self.view_mode, self.selected_file)

    def set_view(self, mode, selected_file):
        self.stop()
        self.view_mode = mode
        self.selected_file = selected_file if selected_file in self.model.datasets else None
        aligned = mode == 'aligned'
        for name, container in self.containers.items():
            container.setVisible(aligned or name == self.selected_file)
        self.master_slider.blockSignals(True)
        if aligned:
            self.master_slider.setRange(0, 100000)
            value = 0
            if self.bounds is not None and self.current_elapsed is not None:
                start, end = self.bounds
                value = round(100000 * (self.current_elapsed - start) / (end - start)) if end > start else 0
            self.master_slider.setValue(value)
            self.master_slider.setEnabled(self.bounds is not None)
            self.btn_master_play.setEnabled(self.bounds is not None)
        else:
            name = self.selected_file
            rows = len(self.model.datasets[name]) if name else 0
            row = self.local_controls.get(name, {}).get('row', 0)
            self.master_slider.setRange(0, max(0, rows - 1))
            self.master_slider.setValue(row)
            self.master_slider.setEnabled(rows > 0)
            self.btn_master_play.setEnabled(bool(name and self.model.timelines[name].times is not None))
        self.master_slider.blockSignals(False)
        self._on_master_slider_changed(self.master_slider.value())

    def toggle_master_playback(self):
        if self.master_timer.isActive():
            self.stop()
            return
        if not self.btn_master_play.isEnabled():
            return
        if self.master_slider.value() == self.master_slider.maximum():
            self.master_slider.setValue(0)
        if self.view_mode == 'aligned':
            self.play_start = self.current_elapsed
        else:
            self.play_start = self.model.timelines[self.selected_file].times[self.master_slider.value()]
        self.clock.restart()
        self.btn_master_play.setText('Pause')
        self.master_timer.start()

    def _on_master_timer(self):
        elapsed = self.play_start + self.clock.elapsed() / 1000
        if self.view_mode == 'aligned':
            start, end = self.bounds
            self.master_slider.setValue(round(100000 * (elapsed - start) / (end - start)) if end > start else 0)
            if elapsed >= end:
                self.stop()
        else:
            name = self.selected_file
            times = self.model.timelines[name].times
            row = (len(times) - 1 if elapsed >= times[-1]
                   else ResultTimeline(times, 0., '').nearest_row(elapsed, self.model.max_gap_sec))
            self._show_row(name, row, remember=True)
            self.time_label.setText(f'{elapsed:.3f} s')
            if row is not None:
                self.master_slider.blockSignals(True)
                self.master_slider.setValue(row)
                self.master_slider.blockSignals(False)
                self.sample_changed.emit(name, row)
            if elapsed >= times[-1]:
                self.stop()

    def _on_master_slider_changed(self, value):
        if self.view_mode == 'individual':
            name = self.selected_file
            if name not in self.local_controls:
                self.time_label.setText('No file')
                self.time_label.setToolTip('')
                return
            self._show_row(name, value, remember=True)
            times = self.model.timelines[name].times
            self.time_label.setText(f'{times[value]:.3f} s' if times is not None else f'Sample {value + 1}')
            self.time_label.setToolTip('Recorded time' if times is not None else 'Sample row (time unavailable)')
            self.sample_changed.emit(name, value)
            return
        if self.bounds is None:
            self.time_label.setText('Alignment unavailable')
            self.time_label.setToolTip('')
            for name in self.local_controls:
                self._show_row(name, None)
            return
        start, end = self.bounds
        self.current_elapsed = start + (end - start) * value / 100000
        self.time_label.setText(f'{self.current_elapsed:+.3f} s')
        self.time_label.setToolTip('Time from the last sample before contact')
        self.elapsed_changed.emit(self.current_elapsed)
        for name in self.local_controls:
            self._show_row(name, self.model.playback_row(name, self.current_elapsed))

    def _show_row(self, name, row, *, remember=False):
        viewer = self.widgets.get(name)
        if viewer is not None:
            # Invalid or unavailable samples must never retain a previous pose.
            viewer.hide()
        control = self.local_controls[name]
        timeline = self.model.timelines[name]
        available = viewer is not None and row is not None
        if available:
            frame = self.model.visualization_handlers[name].get_frame_data(row)
            points = frame[[k.DF_POS_X, k.DF_POS_Y, k.DF_POS_Z]].apply(pd.to_numeric, errors='coerce').to_numpy(dtype=float)
            available = len(points) > 0 and bool(np.isfinite(points).all())
        if viewer is not None:
            viewer.setVisible(available)
        if row is None:
            control['label'].setText('Unavailable here' if timeline.aligned else 'Alignment unavailable')
            control['label'].setToolTip(timeline.reason or 'Outside this recording or inside a gap')
            return
        if remember:
            control['row'] = row
        time_text = f'{timeline.times[row]:.3f} s' if timeline.times is not None else 'time unavailable'
        control['label'].setText(f'Sample {row + 1}  {time_text}' if available else 'Position unavailable')
        control['label'].setToolTip(f'Sample {row + 1}: {time_text}' if available else 'No finite position data for this sample')
        if available:
            viewer.update_view(row)
            viewer.set_actor_visibility(k.SK_ACTOR_LABELS, self.show_labels)
            color = QColor(self.model.file_colors[name])
            actor = viewer.actors.get(k.SK_ACTOR_BOX_EDGES)
            if actor is not None:
                actor.GetProperty().SetColor(color.redF(), color.greenF(), color.blueF())
            box_frame = frame.loc[frame[k.DF_OBJECT_ID].isin(k.BOX_CORNERS_LABELS)]
            box_points = box_frame[[k.DF_POS_X, k.DF_POS_Y, k.DF_POS_Z]].to_numpy(dtype=float)
            complete_box = len(box_points) == 8 and box_frame[k.DF_OBJECT_ID].nunique() == 8
            centre = box_points.mean(axis=0) if complete_box else None
            if not control['camera_initialized']:
                fit_points = box_points if complete_box else points
                low, high = fit_points.min(axis=0), fit_points.max(axis=0)
                bounds = tuple(value for a, b in zip(low, high) for value in (a - 1, b + 1))
                viewer.view_isometric()
                viewer.plotter.reset_camera(bounds=bounds)
                control['camera_initialized'] = True
            elif centre is not None and control['last_box_centre'] is not None:
                delta = centre - control['last_box_centre']
                if np.any(delta):
                    camera = viewer.plotter.camera
                    # Translate the current view, preserving user rotation,
                    # zoom and pan offset instead of fitting every frame.
                    camera.position = tuple(np.asarray(camera.position) + delta)
                    camera.focal_point = tuple(np.asarray(camera.focal_point) + delta)
                    viewer.plotter.reset_camera_clipping_range()
            if centre is not None:
                control['last_box_centre'] = centre
            viewer.plotter.render()

    def closeEvent(self, event):
        self.stop()
        for viewer in self.widgets.values():
            viewer.cleanup()
        super().closeEvent(event)
