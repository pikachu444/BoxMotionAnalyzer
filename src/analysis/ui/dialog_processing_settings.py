from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
)

from src.config import config_analysis_ui as ui_config


class ProcessingSettingsDialog(QDialog):
    def __init__(self, current_options: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle(ui_config.ADVANCED_DIALOG_TITLE)
        self.resize(700, 760)
        self._current_options = dict(current_options)
        self._setup_ui()
        self._load_options()

    def _setup_ui(self):
        root = QVBoxLayout(self)

        marker_group = QGroupBox(ui_config.SECTION_TITLES["marker_smoothing"])
        marker_layout = QVBoxLayout(marker_group)
        marker_note = QLabel(ui_config.SECTION_DESCRIPTIONS["marker_smoothing"])
        marker_note.setWordWrap(True)
        marker_note.setStyleSheet("color: #4a5568;")
        marker_layout.addWidget(marker_note)
        self.cb_marker_smoothing = QCheckBox(ui_config.FIELD_LABELS["enable_marker_smoothing"])
        marker_layout.addWidget(self.cb_marker_smoothing)
        marker_hint = QLabel(ui_config.FIELD_HINTS["enable_marker_smoothing"])
        marker_hint.setWordWrap(True)
        marker_hint.setStyleSheet("color: #718096; font-size: 11px; margin-left: 18px;")
        marker_layout.addWidget(marker_hint)
        marker_form = QFormLayout()
        self.combo_marker_method = QComboBox()
        for label, value in ui_config.MARKER_SMOOTHING_METHOD_CHOICES:
            self.combo_marker_method.addItem(label, userData=value)
        marker_form.addRow(ui_config.FIELD_LABELS["marker_smoothing_method"], self.combo_marker_method)
        marker_layout.addLayout(marker_form)
        root.addWidget(marker_group)

        range_group = QGroupBox(ui_config.SECTION_TITLES["range_edge_handling"])
        range_layout = QVBoxLayout(range_group)
        range_note = QLabel(ui_config.SECTION_DESCRIPTIONS["range_edge_handling"])
        range_note.setWordWrap(True)
        range_note.setStyleSheet("color: #4a5568;")
        range_layout.addWidget(range_note)
        range_form = QFormLayout()
        self.combo_range_handling = QComboBox()
        for label, value in ui_config.RANGE_EDGE_HANDLING_CHOICES:
            self.combo_range_handling.addItem(label, userData=value)
        range_form.addRow(ui_config.FIELD_LABELS["range_edge_handling"], self.combo_range_handling)
        range_layout.addLayout(range_form)
        range_hint = QLabel(ui_config.FIELD_HINTS["range_edge_handling"])
        range_hint.setWordWrap(True)
        range_hint.setStyleSheet("color: #718096; font-size: 11px;")
        range_layout.addWidget(range_hint)
        root.addWidget(range_group)

        pose_group = QGroupBox(ui_config.SECTION_TITLES["pose"])
        pose_layout = QVBoxLayout(pose_group)
        pose_note = QLabel(ui_config.SECTION_DESCRIPTIONS["pose"])
        pose_note.setWordWrap(True)
        pose_note.setStyleSheet("color: #4a5568;")
        pose_layout.addWidget(pose_note)
        self.cb_pose_lpf = QCheckBox(ui_config.FIELD_LABELS["pose_lowpass_filter"])
        self.cb_pose_ma = QCheckBox(ui_config.FIELD_LABELS["pose_moving_average"])
        pose_layout.addWidget(self.cb_pose_lpf)
        pose_lpf_hint = QLabel(f"  {ui_config.FIELD_HINTS['pose_lowpass_filter']}")
        pose_lpf_hint.setStyleSheet("color: #718096; font-size: 11px;")
        pose_layout.addWidget(pose_lpf_hint)
        pose_layout.addWidget(self.cb_pose_ma)
        pose_ma_hint = QLabel(f"  {ui_config.FIELD_HINTS['pose_moving_average']}")
        pose_ma_hint.setStyleSheet("color: #718096; font-size: 11px;")
        pose_layout.addWidget(pose_ma_hint)
        root.addWidget(pose_group)

        derivative_group = QGroupBox(ui_config.SECTION_TITLES["derivative_method"])
        derivative_layout = QVBoxLayout(derivative_group)
        derivative_note = QLabel(ui_config.SECTION_DESCRIPTIONS["derivative_method"])
        derivative_note.setWordWrap(True)
        derivative_note.setStyleSheet("color: #4a5568;")
        derivative_layout.addWidget(derivative_note)
        derivative_form = QFormLayout()
        self.combo_velocity_method = QComboBox()
        for label, value in ui_config.DERIVATIVE_METHOD_CHOICES:
            self.combo_velocity_method.addItem(label, userData=value)
        self.combo_acceleration_method = QComboBox()
        for label, value in ui_config.DERIVATIVE_METHOD_CHOICES:
            self.combo_acceleration_method.addItem(label, userData=value)
        derivative_form.addRow(ui_config.FIELD_LABELS["velocity_method"], self.combo_velocity_method)
        derivative_form.addRow(ui_config.FIELD_LABELS["acceleration_method"], self.combo_acceleration_method)
        derivative_layout.addLayout(derivative_form)
        derivative_hint = QLabel(ui_config.FIELD_HINTS["derivative_method"])
        derivative_hint.setWordWrap(True)
        derivative_hint.setStyleSheet("color: #718096; font-size: 11px;")
        derivative_layout.addWidget(derivative_hint)
        root.addWidget(derivative_group)

        velocity_group = QGroupBox(ui_config.SECTION_TITLES["velocity"])
        velocity_layout = QVBoxLayout(velocity_group)
        velocity_note = QLabel(ui_config.SECTION_DESCRIPTIONS["velocity"])
        velocity_note.setWordWrap(True)
        velocity_note.setStyleSheet("color: #4a5568;")
        velocity_layout.addWidget(velocity_note)
        self.cb_velocity_lpf = QCheckBox(ui_config.FIELD_LABELS["velocity_lowpass_filter"])
        velocity_layout.addWidget(self.cb_velocity_lpf)
        velocity_hint = QLabel(ui_config.FIELD_HINTS["velocity_lowpass_filter"])
        velocity_hint.setWordWrap(True)
        velocity_hint.setStyleSheet("color: #718096; font-size: 11px; margin-left: 18px;")
        velocity_layout.addWidget(velocity_hint)
        root.addWidget(velocity_group)

        acceleration_group = QGroupBox(ui_config.SECTION_TITLES["acceleration"])
        acceleration_layout = QVBoxLayout(acceleration_group)
        acceleration_note = QLabel(ui_config.SECTION_DESCRIPTIONS["acceleration"])
        acceleration_note.setWordWrap(True)
        acceleration_note.setStyleSheet("color: #4a5568;")
        acceleration_layout.addWidget(acceleration_note)
        self.cb_acceleration_lpf = QCheckBox(ui_config.FIELD_LABELS["acceleration_lowpass_filter"])
        acceleration_layout.addWidget(self.cb_acceleration_lpf)
        acceleration_hint = QLabel(ui_config.FIELD_HINTS["acceleration_lowpass_filter"])
        acceleration_hint.setWordWrap(True)
        acceleration_hint.setStyleSheet("color: #718096; font-size: 11px; margin-left: 18px;")
        acceleration_layout.addWidget(acceleration_hint)
        root.addWidget(acceleration_group)

        buttons = QHBoxLayout()
        buttons.addStretch()
        cancel_button = QPushButton(ui_config.FIELD_LABELS["cancel"])
        ok_button = QPushButton(ui_config.FIELD_LABELS["ok"])
        ok_button.setDefault(True)
        cancel_button.clicked.connect(self.reject)
        ok_button.clicked.connect(self.accept)
        buttons.addWidget(cancel_button)
        buttons.addWidget(ok_button)
        root.addLayout(buttons)

    def _load_options(self):
        self.cb_marker_smoothing.setChecked(self._current_options.get("enable_marker_smoothing", True))
        self._set_combo_data(
            self.combo_marker_method,
            self._current_options.get("marker_smoothing_method_sequence", []),
        )
        self._set_combo_data(
            self.combo_range_handling,
            self._current_options.get("trimming_strategy", "late"),
        )
        self.cb_pose_lpf.setChecked(self._current_options.get("use_pose_lowpass_filter", False))
        self.cb_pose_ma.setChecked(self._current_options.get("use_pose_moving_average", False))
        self._set_combo_data(
            self.combo_velocity_method,
            self._current_options.get("velocity_method", "spline"),
        )
        self._set_combo_data(
            self.combo_acceleration_method,
            self._current_options.get("acceleration_method", "spline"),
        )
        self.cb_velocity_lpf.setChecked(self._current_options.get("use_velocity_lowpass_filter", False))
        self.cb_acceleration_lpf.setChecked(self._current_options.get("use_acceleration_lowpass_filter", False))

    def _set_combo_data(self, combo: QComboBox, target_value):
        for index in range(combo.count()):
            if combo.itemData(index) == target_value:
                combo.setCurrentIndex(index)
                return

    def get_settings(self) -> dict:
        return {
            "enable_marker_smoothing": self.cb_marker_smoothing.isChecked(),
            "marker_smoothing_method_sequence": list(self.combo_marker_method.currentData()),
            "trimming_strategy": self.combo_range_handling.currentData(),
            "use_pose_lowpass_filter": self.cb_pose_lpf.isChecked(),
            "use_pose_moving_average": self.cb_pose_ma.isChecked(),
            "velocity_method": self.combo_velocity_method.currentData(),
            "acceleration_method": self.combo_acceleration_method.currentData(),
            "use_velocity_lowpass_filter": self.cb_velocity_lpf.isChecked(),
            "use_acceleration_lowpass_filter": self.cb_acceleration_lpf.isChecked(),
        }
