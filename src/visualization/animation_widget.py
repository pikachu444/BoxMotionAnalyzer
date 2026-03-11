from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QLabel, QSlider, QPushButton, QFrame
)
from PySide6.QtCore import Qt, Signal

class AnimationWidget(QWidget):
    """
    A widget dedicated to animation controls (slider, buttons).
    """
    frame_changed = Signal(int)
    play_toggled = Signal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)

        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)

        # --- Widgets ---
        self.frame_label = QLabel("Frame: 0 / 0")
        self.timeline_slider = QSlider(Qt.Orientation.Horizontal)
        self.play_pause_button = QPushButton("Play")
        self.play_pause_button.setCheckable(True)

        # --- Layout ---
        main_layout.addWidget(self.play_pause_button)
        main_layout.addWidget(self.frame_label)
        main_layout.addWidget(self.timeline_slider, 1) # Give slider stretching priority

        # --- Connections ---
        self.timeline_slider.valueChanged.connect(self.frame_changed.emit)
        self.play_pause_button.toggled.connect(self.on_play_pause_toggled)

    def on_play_pause_toggled(self, checked):
        self.play_pause_button.setText("Pause" if checked else "Play")
        self.play_toggled.emit(checked)

    def set_frame_range(self, max_frames):
        self.timeline_slider.setRange(0, max_frames - 1)

    def update_frame_display(self, frame_number, total_frames, time_value):
        self.frame_label.setText(f"Frame: {frame_number} / {total_frames}  (Time: {time_value:.3f}s)")
        self.timeline_slider.blockSignals(True)
        self.timeline_slider.setValue(frame_number)
        self.timeline_slider.blockSignals(False)
