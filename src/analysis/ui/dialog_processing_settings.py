from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QDialog,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QWidget,
    QVBoxLayout,
)

from src.config import config_analysis_ui as ui_config


class ProcessingSettingsDialog(QDialog):
    def __init__(self, current_options: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle(ui_config.ADVANCED_DIALOG_TITLE)
        self.resize(
            ui_config.ADVANCED_DIALOG_LAYOUT["width"],
            ui_config.ADVANCED_DIALOG_LAYOUT["height"],
        )
        self._current_options = dict(current_options)
        self._setup_ui()
        self._load_options()

    def _setup_ui(self):
        root = QVBoxLayout(self)
        margins = ui_config.ADVANCED_DIALOG_LAYOUT["contents_margins"]
        root.setContentsMargins(*margins)
        root.setSpacing(ui_config.ADVANCED_DIALOG_LAYOUT["section_spacing"])

        content_layout = QGridLayout()
        content_layout.setColumnStretch(0, 1)
        content_layout.setColumnStretch(1, 1)
        content_layout.setHorizontalSpacing(ui_config.ADVANCED_DIALOG_LAYOUT["column_spacing"])
        content_layout.setVerticalSpacing(ui_config.ADVANCED_DIALOG_LAYOUT["section_spacing"])
        root.addLayout(content_layout)

        left_column = QVBoxLayout()
        left_column.setSpacing(ui_config.ADVANCED_DIALOG_LAYOUT["section_spacing"])
        right_column = QVBoxLayout()
        right_column.setSpacing(ui_config.ADVANCED_DIALOG_LAYOUT["section_spacing"])
        content_layout.addLayout(left_column, 0, 0)
        content_layout.addLayout(right_column, 0, 1)

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

        self.marker_butterworth_group = QGroupBox(ui_config.FIELD_LABELS["marker_butterworth_group"])
        marker_butterworth_form = QFormLayout(self.marker_butterworth_group)
        self.spin_marker_cutoff = self._create_double_spinbox(0.1, 200.0, 2, 0.5)
        self.spin_marker_order = self._create_int_spinbox(1, 10)
        marker_butterworth_form.addRow(ui_config.FIELD_LABELS["marker_butterworth_cutoff"], self.spin_marker_cutoff)
        marker_butterworth_form.addRow(ui_config.FIELD_LABELS["marker_butterworth_order"], self.spin_marker_order)
        marker_layout.addWidget(self.marker_butterworth_group)

        self.marker_ma_group = QGroupBox(ui_config.FIELD_LABELS["marker_ma_group"])
        marker_ma_form = QFormLayout(self.marker_ma_group)
        self.spin_marker_ma_window = self._create_int_spinbox(1, 101)
        marker_ma_form.addRow(ui_config.FIELD_LABELS["marker_ma_window"], self.spin_marker_ma_window)
        marker_layout.addWidget(self.marker_ma_group)

        self.marker_savgol_group = QGroupBox(ui_config.FIELD_LABELS["marker_savgol_group"])
        marker_savgol_layout = QVBoxLayout(self.marker_savgol_group)
        marker_savgol_hint = QLabel(ui_config.FIELD_HINTS["marker_savgol"])
        marker_savgol_hint.setWordWrap(True)
        marker_savgol_hint.setStyleSheet("color: #718096; font-size: 11px;")
        marker_savgol_layout.addWidget(marker_savgol_hint)
        marker_savgol_form = QFormLayout()
        self.spin_marker_savgol_window = self._create_int_spinbox(3, 201)
        self.spin_marker_savgol_polyorder = self._create_int_spinbox(1, 10)
        marker_savgol_form.addRow(ui_config.FIELD_LABELS["marker_savgol_window"], self.spin_marker_savgol_window)
        marker_savgol_form.addRow(ui_config.FIELD_LABELS["marker_savgol_polyorder"], self.spin_marker_savgol_polyorder)
        marker_savgol_layout.addLayout(marker_savgol_form)
        marker_layout.addWidget(self.marker_savgol_group)
        left_column.addWidget(marker_group)

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
        left_column.addWidget(range_group)

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
        pose_form = QFormLayout()
        self.spin_pose_lpf_cutoff = self._create_double_spinbox(0.1, 200.0, 2, 0.5)
        self.spin_pose_lpf_order = self._create_int_spinbox(1, 10)
        self.spin_pose_ma_window = self._create_int_spinbox(1, 101)
        pose_form.addRow(ui_config.FIELD_LABELS["pose_lpf_cutoff"], self.spin_pose_lpf_cutoff)
        pose_form.addRow(ui_config.FIELD_LABELS["pose_lpf_order"], self.spin_pose_lpf_order)
        pose_form.addRow(ui_config.FIELD_LABELS["pose_ma_window"], self.spin_pose_ma_window)
        pose_layout.addLayout(pose_form)
        left_column.addWidget(pose_group)

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
        self.spin_spline_position = self._create_double_spinbox(0.0, 10.0, 6, 0.001)
        self.spin_spline_rotation = self._create_double_spinbox(0.0, 10.0, 6, 0.001)
        self.spin_spline_degree = self._create_int_spinbox(1, 5)
        derivative_form.addRow(ui_config.FIELD_LABELS["spline_position_factor"], self.spin_spline_position)
        derivative_form.addRow(ui_config.FIELD_LABELS["spline_rotation_factor"], self.spin_spline_rotation)
        derivative_form.addRow(ui_config.FIELD_LABELS["spline_degree"], self.spin_spline_degree)
        derivative_layout.addLayout(derivative_form)
        derivative_hint = QLabel(ui_config.FIELD_HINTS["derivative_method"])
        derivative_hint.setWordWrap(True)
        derivative_hint.setStyleSheet("color: #718096; font-size: 11px;")
        derivative_layout.addWidget(derivative_hint)
        spline_hint = QLabel(ui_config.FIELD_HINTS["spline_parameters"])
        spline_hint.setWordWrap(True)
        spline_hint.setStyleSheet("color: #718096; font-size: 11px;")
        derivative_layout.addWidget(spline_hint)
        right_column.addWidget(derivative_group)

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
        velocity_form = QFormLayout()
        self.spin_velocity_lpf_cutoff = self._create_double_spinbox(0.1, 200.0, 2, 0.5)
        self.spin_velocity_lpf_order = self._create_int_spinbox(1, 10)
        velocity_form.addRow(ui_config.FIELD_LABELS["velocity_lpf_cutoff"], self.spin_velocity_lpf_cutoff)
        velocity_form.addRow(ui_config.FIELD_LABELS["velocity_lpf_order"], self.spin_velocity_lpf_order)
        velocity_layout.addLayout(velocity_form)
        right_column.addWidget(velocity_group)

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
        acceleration_form = QFormLayout()
        self.spin_acceleration_lpf_cutoff = self._create_double_spinbox(0.1, 200.0, 2, 0.5)
        self.spin_acceleration_lpf_order = self._create_int_spinbox(1, 10)
        acceleration_form.addRow(ui_config.FIELD_LABELS["acceleration_lpf_cutoff"], self.spin_acceleration_lpf_cutoff)
        acceleration_form.addRow(ui_config.FIELD_LABELS["acceleration_lpf_order"], self.spin_acceleration_lpf_order)
        acceleration_layout.addLayout(acceleration_form)
        right_column.addWidget(acceleration_group)

        left_column.addStretch()
        right_column.addStretch()

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

        self.cb_marker_smoothing.toggled.connect(self._update_enabled_state)
        self.cb_pose_lpf.toggled.connect(self._update_enabled_state)
        self.cb_pose_ma.toggled.connect(self._update_enabled_state)
        self.cb_velocity_lpf.toggled.connect(self._update_enabled_state)
        self.cb_acceleration_lpf.toggled.connect(self._update_enabled_state)
        self.combo_marker_method.currentIndexChanged.connect(self._update_enabled_state)
        self.combo_velocity_method.currentIndexChanged.connect(self._update_enabled_state)
        self.combo_acceleration_method.currentIndexChanged.connect(self._update_enabled_state)

    def _load_options(self):
        self.cb_marker_smoothing.setChecked(self._current_options.get("enable_marker_smoothing", True))
        self._set_combo_data(
            self.combo_marker_method,
            self._current_options.get("marker_smoothing_method_sequence", []),
        )
        self.spin_marker_cutoff.setValue(self._current_options.get("marker_butterworth_cutoff_hz", 10.0))
        self.spin_marker_order.setValue(self._current_options.get("marker_butterworth_order", 4))
        self.spin_marker_ma_window.setValue(self._current_options.get("marker_moving_average_window", 3))
        self.spin_marker_savgol_window.setValue(self._current_options.get("marker_savgol_window_length", 7))
        self.spin_marker_savgol_polyorder.setValue(self._current_options.get("marker_savgol_polyorder", 3))
        self._set_combo_data(
            self.combo_range_handling,
            self._current_options.get("trimming_strategy", "late"),
        )
        self.cb_pose_lpf.setChecked(self._current_options.get("use_pose_lowpass_filter", False))
        self.spin_pose_lpf_cutoff.setValue(self._current_options.get("pose_lpf_cutoff_hz", 20.0))
        self.spin_pose_lpf_order.setValue(self._current_options.get("pose_lpf_order", 4))
        self.cb_pose_ma.setChecked(self._current_options.get("use_pose_moving_average", False))
        self.spin_pose_ma_window.setValue(self._current_options.get("pose_moving_average_window", 3))
        self._set_combo_data(
            self.combo_velocity_method,
            self._current_options.get("velocity_method", "spline"),
        )
        self._set_combo_data(
            self.combo_acceleration_method,
            self._current_options.get("acceleration_method", "spline"),
        )
        self.spin_spline_position.setValue(self._current_options.get("spline_s_factor_position", 1e-2))
        self.spin_spline_rotation.setValue(self._current_options.get("spline_s_factor_rotation", 1e-3))
        self.spin_spline_degree.setValue(self._current_options.get("spline_degree", 3))
        self.cb_velocity_lpf.setChecked(self._current_options.get("use_velocity_lowpass_filter", False))
        self.spin_velocity_lpf_cutoff.setValue(self._current_options.get("velocity_lpf_cutoff_hz", 8.0))
        self.spin_velocity_lpf_order.setValue(self._current_options.get("velocity_lpf_order", 4))
        self.cb_acceleration_lpf.setChecked(self._current_options.get("use_acceleration_lowpass_filter", False))
        self.spin_acceleration_lpf_cutoff.setValue(self._current_options.get("acceleration_lpf_cutoff_hz", 8.0))
        self.spin_acceleration_lpf_order.setValue(self._current_options.get("acceleration_lpf_order", 4))
        self._update_enabled_state()

    def _set_combo_data(self, combo: QComboBox, target_value):
        for index in range(combo.count()):
            if combo.itemData(index) == target_value:
                combo.setCurrentIndex(index)
                return

    def _create_double_spinbox(self, minimum, maximum, decimals, step):
        spinbox = QDoubleSpinBox()
        spinbox.setRange(minimum, maximum)
        spinbox.setDecimals(decimals)
        spinbox.setSingleStep(step)
        return spinbox

    def _create_int_spinbox(self, minimum, maximum):
        spinbox = QSpinBox()
        spinbox.setRange(minimum, maximum)
        return spinbox

    def _set_widget_visible(self, widget: QWidget, visible: bool):
        widget.setVisible(visible)
        widget.setEnabled(visible)

    def _update_enabled_state(self):
        marker_enabled = self.cb_marker_smoothing.isChecked()
        self.combo_marker_method.setEnabled(marker_enabled)
        selected_methods = list(self.combo_marker_method.currentData() or [])
        show_butterworth = marker_enabled and "butterworth" in selected_methods
        show_moving_average = marker_enabled and "moving_average" in selected_methods
        show_savgol = marker_enabled and "savitzky_golay" in selected_methods

        self._set_widget_visible(self.marker_butterworth_group, show_butterworth)
        self._set_widget_visible(self.marker_ma_group, show_moving_average)
        self._set_widget_visible(self.marker_savgol_group, show_savgol)

        self.spin_pose_lpf_cutoff.setEnabled(self.cb_pose_lpf.isChecked())
        self.spin_pose_lpf_order.setEnabled(self.cb_pose_lpf.isChecked())
        self.spin_pose_ma_window.setEnabled(self.cb_pose_ma.isChecked())

        spline_enabled = (
            self.combo_velocity_method.currentData() == "spline"
            or self.combo_acceleration_method.currentData() == "spline"
        )
        self.spin_spline_position.setEnabled(spline_enabled)
        self.spin_spline_rotation.setEnabled(spline_enabled)
        self.spin_spline_degree.setEnabled(spline_enabled)

        self.spin_velocity_lpf_cutoff.setEnabled(self.cb_velocity_lpf.isChecked())
        self.spin_velocity_lpf_order.setEnabled(self.cb_velocity_lpf.isChecked())
        self.spin_acceleration_lpf_cutoff.setEnabled(self.cb_acceleration_lpf.isChecked())
        self.spin_acceleration_lpf_order.setEnabled(self.cb_acceleration_lpf.isChecked())

    def get_settings(self) -> dict:
        return {
            "enable_marker_smoothing": self.cb_marker_smoothing.isChecked(),
            "marker_smoothing_method_sequence": list(self.combo_marker_method.currentData()),
            "marker_butterworth_cutoff_hz": self.spin_marker_cutoff.value(),
            "marker_butterworth_order": self.spin_marker_order.value(),
            "marker_moving_average_window": self.spin_marker_ma_window.value(),
            "marker_savgol_window_length": self.spin_marker_savgol_window.value(),
            "marker_savgol_polyorder": self.spin_marker_savgol_polyorder.value(),
            "trimming_strategy": self.combo_range_handling.currentData(),
            "use_pose_lowpass_filter": self.cb_pose_lpf.isChecked(),
            "pose_lpf_cutoff_hz": self.spin_pose_lpf_cutoff.value(),
            "pose_lpf_order": self.spin_pose_lpf_order.value(),
            "use_pose_moving_average": self.cb_pose_ma.isChecked(),
            "pose_moving_average_window": self.spin_pose_ma_window.value(),
            "velocity_method": self.combo_velocity_method.currentData(),
            "acceleration_method": self.combo_acceleration_method.currentData(),
            "spline_s_factor_position": self.spin_spline_position.value(),
            "spline_s_factor_rotation": self.spin_spline_rotation.value(),
            "spline_degree": self.spin_spline_degree.value(),
            "use_velocity_lowpass_filter": self.cb_velocity_lpf.isChecked(),
            "velocity_lpf_cutoff_hz": self.spin_velocity_lpf_cutoff.value(),
            "velocity_lpf_order": self.spin_velocity_lpf_order.value(),
            "use_acceleration_lowpass_filter": self.cb_acceleration_lpf.isChecked(),
            "acceleration_lpf_cutoff_hz": self.spin_acceleration_lpf_cutoff.value(),
            "acceleration_lpf_order": self.spin_acceleration_lpf_order.value(),
        }
