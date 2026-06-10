from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QSlider, QLabel, QGroupBox, QCheckBox, QFrame
)
from PySide6.QtCore import Qt, QTimer
from src.visualization.vista_widget import VistaWidget
from src.analysis.compare.data_model import ComparisonModel

class ComparePlaybackPanel(QGroupBox):
    def __init__(self, model: ComparisonModel):
        super().__init__("3D Playback & Sync")
        self.model = model
        self.widgets: dict[str, VistaWidget] = {}
        self.local_controls: dict[str, dict] = {}
        
        main_layout = QVBoxLayout(self)
        
        # Master Playback Controls
        master_control_layout = QHBoxLayout()
        self.chk_sync = QCheckBox("Sync All Viewers")
        self.chk_sync.setChecked(True)
        self.chk_sync.stateChanged.connect(self._on_sync_toggled)
        master_control_layout.addWidget(self.chk_sync)
        
        self.btn_master_play = QPushButton("Master Play")
        self.btn_master_play.clicked.connect(self.toggle_master_playback)
        master_control_layout.addWidget(self.btn_master_play)
        
        self.master_slider = QSlider(Qt.Horizontal)
        self.master_slider.valueChanged.connect(self._on_master_slider_changed)
        master_control_layout.addWidget(self.master_slider)
        
        main_layout.addLayout(master_control_layout)
        
        # 3D Viewers layout
        self.viewers_widget = QWidget()
        self.viewers_layout = QHBoxLayout(self.viewers_widget)
        main_layout.addWidget(self.viewers_widget, stretch=1)
        
        # Master Playback state
        self.is_master_playing = False
        self.master_current_frame = 0
        self.max_frames = 0
        self.master_timer = QTimer(self)
        self.master_timer.setInterval(50)
        self.master_timer.timeout.connect(self._on_master_timer)

    def refresh_viewers(self):
        # Clean up old viewers
        for w in self.widgets.values():
            self.viewers_layout.removeWidget(w.parentWidget())
            w.parentWidget().deleteLater()
        self.widgets.clear()
        
        # Clean up local timers
        for controls in self.local_controls.values():
            controls["timer"].stop()
            controls["timer"].deleteLater()
        self.local_controls.clear()
        
        self.max_frames = 0
        for name, handler in self.model.visualization_handlers.items():
            if handler.n_frames > self.max_frames:
                self.max_frames = handler.n_frames
                
            container = QFrame()
            v_layout = QVBoxLayout(container)
            v_layout.setContentsMargins(2, 2, 2, 2)
            
            vw = VistaWidget(data_handler=handler)
            v_layout.addWidget(vw, stretch=1)
            
            # Local controls
            local_ctrl_layout = QHBoxLayout()
            btn_play = QPushButton("Play")
            slider = QSlider(Qt.Horizontal)
            slider.setMaximum(max(0, handler.n_frames - 1))
            
            local_ctrl_layout.addWidget(btn_play)
            local_ctrl_layout.addWidget(slider)
            
            timer = QTimer(self)
            timer.setInterval(50)
            
            self.local_controls[name] = {
                "btn": btn_play,
                "slider": slider,
                "timer": timer,
                "is_playing": False,
                "frame": 0,
                "n_frames": handler.n_frames
            }
            
            # Use default args lambda to capture name correctly
            btn_play.clicked.connect(lambda checked=False, n=name: self._toggle_local_playback(n))
            slider.valueChanged.connect(lambda val, n=name: self._on_local_slider_changed(n, val))
            timer.timeout.connect(lambda n=name: self._on_local_timer(n))
            
            lbl_name = QLabel(name)
            lbl_name.setStyleSheet("font-size: 11px; color: #a0a0a0;")
            
            v_layout.addLayout(local_ctrl_layout)
            v_layout.addWidget(lbl_name, alignment=Qt.AlignCenter)
            
            self.viewers_layout.addWidget(container)
            self.widgets[name] = vw
            
        if self.max_frames > 0:
            self.master_slider.setMaximum(self.max_frames - 1)
        else:
            self.master_slider.setMaximum(0)
            
        self.master_slider.setValue(0)
        self._on_master_slider_changed(0)
        self._on_sync_toggled()

    def _on_sync_toggled(self):
        is_sync = self.chk_sync.isChecked()
        self.btn_master_play.setEnabled(is_sync)
        self.master_slider.setEnabled(is_sync)
        
        if is_sync:
            for n, ctrl in self.local_controls.items():
                if ctrl["is_playing"]:
                    self._toggle_local_playback(n)
                ctrl["btn"].setEnabled(False)
                ctrl["slider"].setEnabled(False)
            self._on_master_slider_changed(self.master_slider.value())
        else:
            if self.is_master_playing:
                self.toggle_master_playback()
            for ctrl in self.local_controls.values():
                ctrl["btn"].setEnabled(True)
                ctrl["slider"].setEnabled(True)

    def toggle_master_playback(self):
        self.is_master_playing = not self.is_master_playing
        if self.is_master_playing:
            self.btn_master_play.setText("Master Pause")
            if self.master_slider.value() >= self.master_slider.maximum():
                self.master_slider.setValue(0)
            self.master_timer.start()
        else:
            self.btn_master_play.setText("Master Play")
            self.master_timer.stop()

    def _on_master_timer(self):
        val = self.master_slider.value() + 1
        if val > self.master_slider.maximum():
            self.toggle_master_playback()
        else:
            self.master_slider.setValue(val)

    def _on_master_slider_changed(self, value):
        if not self.chk_sync.isChecked():
            return
        self.master_current_frame = value
        for name, vw in self.widgets.items():
            handler = self.model.visualization_handlers[name]
            alignment_offset = self.model.alignment_frames.get(name, 0)
            baseline_offset = self.model.alignment_frames.get(self.model.baseline_name, 0) if self.model.baseline_name else 0
            
            relative_frame = value - baseline_offset + alignment_offset
            
            if relative_frame < 0:
                relative_frame = 0
            elif relative_frame >= handler.n_frames:
                relative_frame = handler.n_frames - 1
                
            vw.update_view(relative_frame)
            
            if name in self.local_controls:
                self.local_controls[name]["slider"].blockSignals(True)
                self.local_controls[name]["slider"].setValue(relative_frame)
                self.local_controls[name]["slider"].blockSignals(False)

    def _toggle_local_playback(self, name):
        ctrl = self.local_controls[name]
        ctrl["is_playing"] = not ctrl["is_playing"]
        if ctrl["is_playing"]:
            ctrl["btn"].setText("Pause")
            if ctrl["slider"].value() >= ctrl["slider"].maximum():
                ctrl["slider"].setValue(0)
            ctrl["timer"].start()
        else:
            ctrl["btn"].setText("Play")
            ctrl["timer"].stop()

    def _on_local_timer(self, name):
        ctrl = self.local_controls[name]
        val = ctrl["slider"].value() + 1
        if val > ctrl["slider"].maximum():
            self._toggle_local_playback(name)
        else:
            ctrl["slider"].setValue(val)

    def _on_local_slider_changed(self, name, value):
        if self.chk_sync.isChecked():
            return
        vw = self.widgets.get(name)
        if vw:
            vw.update_view(value)
