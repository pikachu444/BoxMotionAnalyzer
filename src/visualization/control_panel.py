from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QSlider, QPushButton,
    QCheckBox, QGroupBox, QListWidget, QListWidgetItem, QComboBox,
    QSpinBox
)
from PySide6.QtCore import Qt, Signal
from src.config import config_visualization as config

class ControlPanel(QWidget):
    frame_changed = Signal(int)
    play_toggled = Signal(bool)
    visibility_changed = Signal(str, bool)
    object_selected = Signal(list) # Now emits a list of strings

    def __init__(self, parent=None):
        super().__init__(parent)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)

        # --- Create and add widget groups ---
        display_group = self._create_display_group()
        inspector_group = self._create_inspector_group()

        main_layout.addWidget(display_group)
        main_layout.addWidget(inspector_group)
        main_layout.addStretch()

    def _create_display_group(self):
        group = QGroupBox(config.LBL_DISPLAY_OPTIONS)
        layout = QHBoxLayout(group)
        self.box_checkbox = QCheckBox("Box")
        self.box_checkbox.setChecked(True)
        self.box_checkbox.toggled.connect(lambda checked: self.visibility_changed.emit("box", checked))

        self.markers_checkbox = QCheckBox("Markers")
        self.markers_checkbox.setChecked(True)
        self.markers_checkbox.toggled.connect(lambda checked: self.visibility_changed.emit("markers", checked))

        self.labels_checkbox = QCheckBox("Labels")
        self.labels_checkbox.setChecked(True)
        self.labels_checkbox.toggled.connect(lambda checked: self.visibility_changed.emit("labels", checked))

        layout.addWidget(self.box_checkbox)
        layout.addWidget(self.markers_checkbox)
        layout.addWidget(self.labels_checkbox)
        layout.addStretch()
        return group

    def _create_inspector_group(self):
        group = QGroupBox(config.LBL_OBJECT_INSPECTOR)
        layout = QVBoxLayout(group)

        self.plot_data_combobox = QComboBox()
        # Use the mapping to display user-friendly names while storing internal column names as user data
        for display_name, col_name in config.PLOT_DATA_DISPLAY_MAP.items():
            self.plot_data_combobox.addItem(display_name, col_name)

        self.object_list = QListWidget()
        # --- Enable Multi-selection ---
        self.object_list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)

        # Use itemSelectionChanged for multi-selection instead of currentItemChanged
        self.object_list.itemSelectionChanged.connect(self.on_object_selection_changed)
        self.plot_data_combobox.currentTextChanged.connect(self.on_object_selection_changed)

        # --- Frame Range Controls ---
        range_layout = QHBoxLayout()
        self.range_checkbox = QCheckBox(config.LBL_USE_FRAME_RANGE)
        self.start_frame_spinbox = QSpinBox()
        self.end_frame_spinbox = QSpinBox()

        self.start_frame_spinbox.setEnabled(False)
        self.end_frame_spinbox.setEnabled(False)

        range_layout.addWidget(self.range_checkbox)
        range_layout.addWidget(QLabel(config.LBL_START))
        range_layout.addWidget(self.start_frame_spinbox)
        range_layout.addWidget(QLabel(config.LBL_END))
        range_layout.addWidget(self.end_frame_spinbox)
        range_layout.addStretch()

        self.range_checkbox.toggled.connect(self.start_frame_spinbox.setEnabled)
        self.range_checkbox.toggled.connect(self.end_frame_spinbox.setEnabled)

        layout.addWidget(QLabel(config.LBL_PLOT_DATA))
        layout.addWidget(self.plot_data_combobox)
        layout.addLayout(range_layout) # Add the new layout
        layout.addWidget(self.object_list)
        return group

    def on_object_selection_changed(self):
        # This signal is now connected to itemSelectionChanged, which doesn't pass items.
        # We get the list of selected items directly from the widget.
        selected_items = self.object_list.selectedItems()
        if selected_items:
            # Emit a signal with a list of the text of all selected items
            self.object_selected.emit([item.text() for item in selected_items])

    def populate_object_list(self, object_ids: list[str]):
        self.object_list.clear()
        self.object_list.addItems(object_ids)

    def set_frame_range(self, max_frames):
        self.timeline_slider.setRange(0, max_frames - 1)

    def update_frame_display(self, frame_number, total_frames, time_value):
        """Updates the frame label and slider position."""
        self.frame_label.setText(f"Frame: {frame_number} / {total_frames}  (Time: {time_value:.2f}s)")
        self.timeline_slider.blockSignals(True)
        self.timeline_slider.setValue(frame_number)
        self.timeline_slider.blockSignals(False)
