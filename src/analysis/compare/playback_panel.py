from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QSlider, QComboBox, QLabel
from PySide6.QtCore import Qt, QTimer
from src.visualization.vista_widget import VistaWidget
from src.analysis.compare.data_model import ComparisonModel

class ComparePlaybackPanel(QWidget):
    def __init__(self, model: ComparisonModel):
        super().__init__()
        self.model = model
        self.widgets: dict[str, VistaWidget] = {}
        
        self.is_playing = False
        self.current_frame = 0
        self.max_frames = 0
        self.alignment_mode = "Raw Time" # "Raw Time" or "Event-Aligned (t1-)"
        
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._on_timer_tick)
        self.timer.setInterval(33) # ~30 fps
        
        self._setup_ui()

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        # Controls
        control_layout = QHBoxLayout()
        self.btn_play = QPushButton("Play")
        self.btn_play.clicked.connect(self.toggle_playback)
        control_layout.addWidget(self.btn_play)
        
        self.slider = QSlider(Qt.Horizontal)
        self.slider.setMinimum(0)
        self.slider.setMaximum(100)
        self.slider.valueChanged.connect(self._on_slider_changed)
        control_layout.addWidget(self.slider)
        
        control_layout.addWidget(QLabel("Alignment:"))
        self.cb_alignment = QComboBox()
        self.cb_alignment.addItems(["Raw Time", "Event-Aligned (t1-)"])
        self.cb_alignment.currentTextChanged.connect(self._on_alignment_changed)
        control_layout.addWidget(self.cb_alignment)
        
        main_layout.addLayout(control_layout)
        
        # 3D Viewers layout
        self.viewers_widget = QWidget()
        self.viewers_layout = QHBoxLayout(self.viewers_widget)
        main_layout.addWidget(self.viewers_widget, stretch=1)
        
    def refresh_viewers(self):
        """Re-create the 3D viewers based on the current datasets in the model."""
        # Clean up old viewers
        for w in self.widgets.values():
            self.viewers_layout.removeWidget(w)
            w.deleteLater()
        self.widgets.clear()
        
        self.max_frames = 0
        for name, handler in self.model.visualization_handlers.items():
            if handler.n_frames > self.max_frames:
                self.max_frames = handler.n_frames
                
            container = QWidget()
            v_layout = QVBoxLayout(container)
            
            lbl = QLabel(name)
            lbl.setAlignment(Qt.AlignCenter)
            if name == self.model.baseline_name:
                lbl.setStyleSheet("font-weight: bold; color: blue;")
                
            v_layout.addWidget(lbl)
            
            vw = VistaWidget(data_handler=handler)
            v_layout.addWidget(vw, stretch=1)
            
            self.viewers_layout.addWidget(container)
            self.widgets[name] = vw
            
        # Update slider limits
        if self.max_frames > 0:
            self.slider.setMaximum(self.max_frames - 1)
        else:
            self.slider.setMaximum(0)
            
        self.slider.setValue(0)
        self._update_all_views(0)
        
    def toggle_playback(self):
        self.is_playing = not self.is_playing
        if self.is_playing:
            self.btn_play.setText("Pause")
            if self.current_frame >= self.slider.maximum():
                self.current_frame = 0
            self.timer.start()
        else:
            self.btn_play.setText("Play")
            self.timer.stop()
            
    def _on_timer_tick(self):
        self.current_frame += 1
        if self.current_frame > self.slider.maximum():
            self.current_frame = 0
            self.toggle_playback() # stop at end
        else:
            # Block signals to prevent recursive update from slider
            self.slider.blockSignals(True)
            self.slider.setValue(self.current_frame)
            self.slider.blockSignals(False)
            self._update_all_views(self.current_frame)
            
    def _on_slider_changed(self, val):
        self.current_frame = val
        self._update_all_views(val)
        
    def _on_alignment_changed(self, mode):
        self.alignment_mode = mode
        self._update_all_views(self.current_frame)
        
    def _update_all_views(self, base_frame: int):
        baseline = self.model.baseline_name
        baseline_t1 = self.model.alignment_frames.get(baseline, 0) if baseline else 0
        
        for name, vw in self.widgets.items():
            if self.alignment_mode == "Raw Time":
                target_frame = base_frame
            else:
                target_t1 = self.model.alignment_frames.get(name, 0)
                offset = target_t1 - baseline_t1
                target_frame = base_frame + offset
                
            # Clamp to valid range
            target_frame = max(0, min(target_frame, vw.data_handler.n_frames - 1))
            vw.update_view(target_frame)
