import numpy as np
import pandas as pd
from PySide6.QtWidgets import QVBoxLayout, QHBoxLayout, QPushButton, QSlider, QLabel, QGroupBox, QCheckBox, QFrame, QScrollArea, QWidget, QSizePolicy, QLayout
from PySide6.QtCore import Qt, QTimer, QElapsedTimer, Signal

from src.visualization.vista_widget import VistaWidget
from src.config import config_visualization as k
from src.utils.result_time import ResultTimeline


class ComparePlaybackPanel(QGroupBox):
    elapsed_changed = Signal(float)

    def __init__(self, model):
        super().__init__('3D samples · actual-time comparison')
        self.setMinimumHeight(240)
        self.model = model
        self.widgets = {}
        self.local_controls = {}
        self.containers = []
        self.bounds = None
        self.current_elapsed = None
        self.clock = QElapsedTimer()
        layout = QVBoxLayout(self)
        controls = QHBoxLayout()
        self.chk_sync = QCheckBox('Sync by t − t1−')
        self.chk_sync.setChecked(True)
        self.chk_sync.toggled.connect(self._on_sync_toggled)
        controls.addWidget(self.chk_sync)
        self.btn_master_play = QPushButton('Play')
        self.btn_master_play.clicked.connect(self.toggle_master_playback)
        controls.addWidget(self.btn_master_play)
        self.master_slider = QSlider(Qt.Horizontal)
        self.master_slider.setRange(0, 100000)
        self.master_slider.valueChanged.connect(self._on_master_slider_changed)
        self.master_slider.sliderPressed.connect(self.stop)
        controls.addWidget(self.master_slider)
        self.time_label = QLabel('Time unavailable')
        controls.addWidget(self.time_label)
        layout.addLayout(controls)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.viewers_widget = QWidget()
        self.viewers_layout = QHBoxLayout(self.viewers_widget)
        self.viewers_layout.setSizeConstraint(QLayout.SetMinimumSize)
        self.scroll.setWidget(self.viewers_widget)
        layout.addWidget(self.scroll)
        self.master_timer = QTimer(self)
        self.master_timer.setInterval(30)
        self.master_timer.timeout.connect(self._on_master_timer)

    def stop(self):
        self.master_timer.stop()
        self.btn_master_play.setText('Play')
        for control in self.local_controls.values():
            control['timer'].stop()
            control['play'].setText('Play samples')

    def refresh_viewers(self):
        self.stop()
        for widget in self.widgets.values():
            widget.cleanup()
        for container in self.containers:
            self.viewers_layout.removeWidget(container)
            container.deleteLater()
        for control in self.local_controls.values():
            control['timer'].deleteLater()
        self.containers.clear()
        self.widgets.clear()
        self.local_controls.clear()
        for name in self.model.datasets:
            container = QFrame()
            container.setMinimumWidth(250)
            layout = QVBoxLayout(container)
            title = QLabel()
            # Fit the minimum-width viewer; the tooltip retains the full path label.
            title.setText(title.fontMetrics().elidedText(name, Qt.ElideMiddle, 220))
            title.setToolTip(name)
            title.setTextFormat(Qt.PlainText)
            layout.addWidget(title)
            source = QLabel(self.model.identities[name].source_kind)
            source.setTextFormat(Qt.PlainText)
            layout.addWidget(source)
            label = QLabel()
            label.setWordWrap(True)
            layout.addWidget(label)
            handler = self.model.visualization_handlers.get(name)
            if handler is not None:
                viewer = VistaWidget(data_handler=handler)
                # Preserve a usable render surface; the existing scroll area
                # exposes the full sample card when the splitter is smaller.
                viewer.setMinimumSize(220, 160)
                viewer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Ignored)
                layout.addWidget(viewer, stretch=1)
                self.widgets[name] = viewer
            slider = QSlider(Qt.Horizontal)
            slider.setRange(0, len(self.model.datasets[name]) - 1)
            slider.valueChanged.connect(lambda row, n=name: self._show_row(n, row))
            slider.setToolTip('Individual sample browser; original row positions, not a time clock')
            layout.addWidget(slider)
            play = QPushButton('Play samples')
            layout.addWidget(play)
            timer = QTimer(self)
            timer.setInterval(30)
            timer.timeout.connect(lambda n=name: self._on_local_timer(n))
            play.clicked.connect(lambda checked=False, n=name: self._toggle_local_playback(n))
            self.local_controls[name] = {'slider': slider, 'label': label, 'play': play,
                                         'timer': timer, 'clock': QElapsedTimer(), 'camera_initialized': False}
            self.viewers_layout.addWidget(container)
            self.containers.append(container)
        self.bounds = self.model.elapsed_bounds()
        self.master_slider.setValue(0)
        self._on_sync_toggled()

    def _on_sync_toggled(self, *_):
        self.stop()
        enabled = self.chk_sync.isChecked() and self.bounds is not None
        self.btn_master_play.setEnabled(enabled)
        self.master_slider.setEnabled(enabled)
        for name, control in self.local_controls.items():
            control['slider'].setEnabled(not self.chk_sync.isChecked())
            control['play'].setEnabled(not self.chk_sync.isChecked() and self.model.timelines[name].times is not None)
            if not self.chk_sync.isChecked():
                self._show_row(name, control['slider'].value())
        if self.chk_sync.isChecked():
            self._on_master_slider_changed(self.master_slider.value())

    def toggle_master_playback(self):
        if self.master_timer.isActive():
            self.stop()
            return
        if self.bounds is None:
            return
        if self.master_slider.value() == self.master_slider.maximum():
            self.master_slider.setValue(0)
        self.play_start = self.current_elapsed
        self.clock.restart()
        self.btn_master_play.setText('Pause')
        self.master_timer.start()

    def _on_master_timer(self):
        elapsed = self.play_start + self.clock.elapsed() / 1000
        start, end = self.bounds
        self.master_slider.setValue(round(100000 * (elapsed - start) / (end - start)) if end > start else 0)
        if elapsed >= end:
            self.stop()

    def _on_master_slider_changed(self, value):
        if not self.chk_sync.isChecked():
            return
        if self.bounds is None:
            self.time_label.setText('Alignment unavailable')
            for name in self.local_controls:
                self._show_row(name, None)
            return
        start, end = self.bounds
        self.current_elapsed = start + (end - start) * value / 100000
        self.time_label.setText(f't − t1− = {self.current_elapsed:.6f} s')
        self.elapsed_changed.emit(self.current_elapsed)
        for name in self.local_controls:
            self._show_row(name, self.model.playback_row(name, self.current_elapsed))

    def _toggle_local_playback(self, name):
        control = self.local_controls[name]
        if control['timer'].isActive():
            control['timer'].stop()
            control['play'].setText('Play samples')
            return
        times = self.model.timelines[name].times
        if times is None:
            return
        row = control['slider'].value()
        if row == len(times) - 1:
            row = 0
            control['slider'].setValue(0)
        control['start'] = times[row]
        control['clock'].restart()
        control['play'].setText('Pause')
        control['timer'].start()

    def _on_local_timer(self, name):
        control = self.local_controls[name]
        times = self.model.timelines[name].times
        actual = control['start'] + control['clock'].elapsed() / 1000
        if actual >= times[-1]:
            self._show_row(name, len(times) - 1)
            self._toggle_local_playback(name)
            return
        row = ResultTimeline(times, 0., '').nearest_row(actual, self.model.max_gap_sec)
        self._show_row(name, row)

    def _show_row(self, name, row):
        viewer = self.widgets.get(name)
        if viewer is not None:
            # Hide before conversion/rendering so invalid data cannot retain
            # the previous valid pose when a Qt signal handler fails.
            viewer.hide()
        control = self.local_controls[name]
        timeline = self.model.timelines[name]
        available = viewer is not None and row is not None
        if available:
            frame = self.model.visualization_handlers[name].get_frame_data(row)
            points = frame[[k.DF_POS_X, k.DF_POS_Y, k.DF_POS_Z]].apply(pd.to_numeric, errors='coerce').to_numpy(dtype=float)
            # Do not leave a stale box/marker actor visible for invalid pose samples.
            available = len(points) > 0 and bool(np.isfinite(points).all())
        if viewer is not None:
            viewer.setVisible(available)
        if row is None:
            control['label'].setText(timeline.reason or '3D unavailable: outside range or within a gap')
            return
        time_text = f't={timeline.times[row]:.6f} s' if timeline.times is not None else 'time unavailable'
        delta = ''
        if self.chk_sync.isChecked() and timeline.aligned:
            delta = f' · sample elapsed={timeline.elapsed[row]:.6f} s'
        control['label'].setText(f'Sample {row + 1} · {time_text}{delta}' + ('' if available else '\n3D unavailable: no finite position data'))
        control['slider'].blockSignals(True)
        control['slider'].setValue(row)
        control['slider'].blockSignals(False)
        if available:
            viewer.update_view(row)
            if not control['camera_initialized']:
                # Vista's initial camera frames only the ground, before data
                # actors exist. Fit the actual sample once without tracking it.
                low, high = points.min(axis=0), points.max(axis=0)
                bounds = tuple(value for a, b in zip(low, high) for value in (a - 1, b + 1))
                viewer.plotter.camera_position = 'iso'
                viewer.plotter.reset_camera(bounds=bounds)
                viewer.plotter.camera.zoom(0.6)
                viewer.plotter.render()
                control['camera_initialized'] = True

    def closeEvent(self, event):
        self.stop()
        for viewer in self.widgets.values():
            viewer.cleanup()
        super().closeEvent(event)
