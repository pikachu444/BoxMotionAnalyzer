"""
Temporary mockup/reference generator for analysis GUI layout exploration.

This script is not the current source of truth for the implemented UI.
Keep it only as a reference when discussing future GUI ideas or comparing
rough layout directions. If it diverges from the shipped UI, trust the code
under `src/analysis/` and the current-state docs first.
"""

import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QPA_FONTDIR", r"C:\Windows\Fonts")

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMainWindow,
    QPushButton,
    QRadioButton,
    QSplitter,
    QTextEdit,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qtagg import NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure
import numpy as np


class Step1MockWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Step 1 - Raw Data Processing (Temporary Mock Reference)")
        self.resize(1320, 860)

        root = QWidget()
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)

        title = QLabel("Step 1: Raw Data Processing")
        title.setStyleSheet("font-weight: 600; font-size: 18px;")
        layout.addWidget(title)

        group = QGroupBox("Raw Data Processing")
        group_layout = QVBoxLayout(group)

        top_layout = QHBoxLayout()

        plot_container = QWidget()
        plot_layout = QVBoxLayout(plot_container)
        plot_layout.setContentsMargins(0, 0, 0, 0)

        fig = Figure(figsize=(7, 4), dpi=100)
        preview_canvas = FigureCanvas(fig)
        plot_layout.addWidget(NavigationToolbar(preview_canvas, self))
        plot_layout.addWidget(preview_canvas)

        ax = fig.subplots()
        x = np.linspace(0, 100, 400)
        y = 40 + 10 * np.sin(x / 6)
        ax.plot(x, y, color="#2b6cb0", linewidth=1.8, label="RigidBody_Position_X")
        ax.axvspan(20, 30, color="#68d391", alpha=0.35, label="Slice Range")
        ax.set_title("Raw Data Preview")
        ax.set_xlabel("Time (s)")
        ax.set_ylabel("Value")
        ax.grid(True, alpha=0.3)
        ax.legend(loc="upper right")
        fig.tight_layout()

        right_panel = QVBoxLayout()
        right_panel.addWidget(QPushButton("Load CSV File..."))
        right_panel.addWidget(QLabel("C:/Data/Experiment1.csv"))

        box_dims = QGroupBox("Box Dimensions (mm)")
        box_dims_layout = QGridLayout(box_dims)
        box_dims_layout.addWidget(QLabel("L:"), 0, 0)
        box_dims_layout.addWidget(QLineEdit("1820.0"), 0, 1)
        box_dims_layout.addWidget(QLabel("W:"), 1, 0)
        box_dims_layout.addWidget(QLineEdit("1110.0"), 1, 1)
        box_dims_layout.addWidget(QLabel("H:"), 2, 0)
        box_dims_layout.addWidget(QLineEdit("164.0"), 2, 1)
        right_panel.addWidget(box_dims)

        log_output = QTextEdit()
        log_output.setReadOnly(True)
        log_output.setPlainText(
            "[INFO] Loaded C:/Data/Experiment1.csv\n"
            "[INFO] Preview parsing complete.\n"
            "[INFO] Default target 'RigidBody Center' selected for plotting."
        )
        right_panel.addWidget(log_output)

        top_layout.addWidget(plot_container, 8)
        top_layout.addLayout(right_panel, 3)
        group_layout.addLayout(top_layout)

        bottom_controls = QHBoxLayout()

        plot_options = QGroupBox("Plot Options")
        plot_options_layout = QHBoxLayout(plot_options)
        plot_options_layout.addWidget(QPushButton("Select Data..."))
        plot_options_layout.addWidget(QLabel("Selected: RigidBody Center"))
        plot_options_layout.addWidget(QLabel("Axis:"))
        axis_combo = QComboBox()
        axis_combo.addItems(["Position-X", "Position-Y", "Position-Z"])
        plot_options_layout.addWidget(axis_combo)
        bottom_controls.addWidget(plot_options, 5)

        slice_group = QGroupBox("Slice Range")
        slice_group.setCheckable(True)
        slice_group.setChecked(True)
        slice_layout = QHBoxLayout(slice_group)
        slice_layout.addWidget(QLabel("Start:"))
        slice_layout.addWidget(QLineEdit("20.0"))
        slice_layout.addWidget(QLabel("End:"))
        slice_layout.addWidget(QLineEdit("30.0"))
        bottom_controls.addWidget(slice_group, 4)

        run_controls = QVBoxLayout()
        run_controls.addWidget(QPushButton("Run Analysis"))
        run_controls.addWidget(QPushButton("Export Results to CSV"))
        bottom_controls.addLayout(run_controls, 2)

        group_layout.addLayout(bottom_controls)
        layout.addWidget(group, 1)


class Step2MockWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Step 2 - Results Analysis (Temporary Mock Reference)")
        self.resize(1460, 980)

        root = QWidget()
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)

        title = QLabel("Step 2: Results Analysis")
        title.setStyleSheet("font-weight: 600; font-size: 18px;")
        layout.addWidget(title)

        context_group = QGroupBox("Time Window")
        context_layout = QVBoxLayout(context_group)

        row1 = QHBoxLayout()
        row1.addWidget(QLabel("Active File:"))
        row1.addWidget(QLabel("result_01.csv"))
        row1.addStretch()
        row1.addWidget(QLabel("Number of Samples:"))
        row1.addWidget(QLabel("1201"))
        context_layout.addLayout(row1)
        context_layout.addWidget(QLabel("Full: 0.000s ~ 100.000s | Slice: 20.000s ~ 30.000s"))

        timeline = QFrame()
        timeline.setFrameShape(QFrame.StyledPanel)
        timeline_l = QHBoxLayout(timeline)
        timeline_l.setContentsMargins(0, 0, 0, 0)
        timeline_l.setSpacing(0)
        left = QWidget()
        left.setStyleSheet("background:#d7dbe0;")
        mid = QWidget()
        mid.setStyleSheet("background:#89cf8a;")
        right = QWidget()
        right.setStyleSheet("background:#d7dbe0;")
        timeline_l.addWidget(left, 200)
        timeline_l.addWidget(mid, 100)
        timeline_l.addWidget(right, 700)
        timeline.setFixedHeight(18)
        context_layout.addWidget(timeline)
        layout.addWidget(context_group)

        splitter = QSplitter(Qt.Horizontal)

        left_panel = QGroupBox("1. Result Files")
        left_l = QVBoxLayout(left_panel)
        top_row = QHBoxLayout()
        top_row.addWidget(QPushButton("Select Result Folder..."))
        top_row.addStretch()
        left_l.addLayout(top_row)
        path_row = QHBoxLayout()
        path_row.addWidget(QLabel("Folder Path:"))
        path_row.addWidget(QLineEdit("D:/Data/Experiment1_Results"))
        left_l.addLayout(path_row)
        files = QListWidget()
        files.addItems(["result_01.csv", "result_02.csv", "result_03.csv"])
        files.setCurrentRow(0)
        left_l.addWidget(files)
        splitter.addWidget(left_panel)

        mid_panel = QGroupBox("2. Data Selection")
        mid_l = QVBoxLayout(mid_panel)
        tree = QTreeWidget()
        tree.setHeaderLabel("Select Data to Plot")

        velocity = QTreeWidgetItem(tree, ["Velocity"])
        vel_com = QTreeWidgetItem(velocity, ["CoM"])
        for key in ["BoxLocal_V_TX", "BoxLocal_V_TY", "BoxLocal_V_TZ", "Global_V_T_Norm"]:
            item = QTreeWidgetItem(vel_com, [key])
            item.setCheckState(0, Qt.Checked)

        acceleration = QTreeWidgetItem(tree, ["Acceleration"])
        acc_com = QTreeWidgetItem(acceleration, ["CoM"])
        for key in ["BoxLocal_A_TX", "BoxLocal_A_TY", "BoxLocal_A_TZ"]:
            item = QTreeWidgetItem(acc_com, [key])
            item.setCheckState(0, Qt.Checked)

        analysis = QTreeWidgetItem(tree, ["Analysis"])
        c1 = QTreeWidgetItem(analysis, ["C1"])
        rel_h = QTreeWidgetItem(c1, ["RelativeHeight"])
        rel_h.setCheckState(0, Qt.Checked)

        position = QTreeWidgetItem(tree, ["Position"])
        pos_com = QTreeWidgetItem(position, ["CoM"])
        for key in ["P_TX", "P_TY"]:
            item = QTreeWidgetItem(pos_com, [key])
            item.setCheckState(0, Qt.Unchecked)

        tree.expandAll()
        mid_l.addWidget(tree)

        btn_row = QHBoxLayout()
        btn_row.addWidget(QPushButton("Clear Selection"))
        btn_row.addWidget(QPushButton("Plot Selected Results"))
        btn_row.addWidget(QPushButton("Open Popup (Current Selection)"))
        mid_l.addLayout(btn_row)

        btn_row2 = QHBoxLayout()
        btn_row2.addStretch()
        btn_row2.addWidget(QPushButton("Close All Popups"))
        mid_l.addLayout(btn_row2)

        mid_l.addWidget(QLabel("Opened Popups: 2"))
        mid_l.addWidget(QLabel("Checked Columns: 8"))
        splitter.addWidget(mid_panel)

        right_panel = QGroupBox("3. Point Analysis & Export")
        right_l = QVBoxLayout(right_panel)

        point_group = QGroupBox("Point Analysis")
        point_layout = QVBoxLayout(point_group)

        row_pa = QHBoxLayout()
        row_pa.addWidget(QLabel("Target:"))
        target_combo = QComboBox()
        target_combo.addItems(
            [
                "Velocity/CoM/BoxLocal_V_TX",
                "Velocity/CoM/BoxLocal_V_TY",
                "Analysis/C1/RelativeHeight",
            ]
        )
        row_pa.addWidget(target_combo)
        row_pa.addWidget(QPushButton("Find Abs. Max"))
        point_layout.addLayout(row_pa)

        selected_row = QHBoxLayout()
        selected_row.addWidget(QLabel("Selected: T=25.400s"))
        selected_row.addStretch()
        selected_row.addWidget(QPushButton("Export Point Data..."))
        point_layout.addLayout(selected_row)
        right_l.addWidget(point_group)

        export_group = QGroupBox("4. Export Analysis Input")
        export_l = QVBoxLayout(export_group)

        flags_row = QHBoxLayout()
        flags_row.addWidget(QCheckBox("Manual Offset"))
        flags_row.addWidget(QCheckBox("Manual Height"))
        flags_row.addStretch()
        export_l.addLayout(flags_row)

        grid = QGridLayout()
        for idx, label in enumerate(["Offset0:", "Offset1:", "Offset2:"]):
            grid.addWidget(QLabel(label), idx, 0)
            combo = QComboBox()
            combo.addItems(["C1", "C2", "C3", "C4", "C5", "C6", "C7", "C8"])
            grid.addWidget(combo, idx, 1)
            grid.addWidget(QLineEdit("H"), idx, 2)
        export_l.addLayout(grid)

        form = QFormLayout()
        form.addRow("Run Time:", QLineEdit("0.1"))
        form.addRow("Step:", QLineEdit("1e-7"))
        form.addRow("Scene Name:", QLineEdit("Drop1"))
        export_l.addLayout(form)
        export_l.addWidget(QPushButton("Export Scenario CSV"))
        right_l.addWidget(export_group)
        right_l.addStretch()
        splitter.addWidget(right_panel)

        splitter.setSizes([320, 620, 500])
        layout.addWidget(splitter, 1)

        plot_group = QGroupBox("Main Plot")
        plot_l = QVBoxLayout(plot_group)

        fig = Figure(figsize=(11, 3), dpi=100)
        canvas = FigureCanvas(fig)
        plot_l.addWidget(NavigationToolbar(canvas, self))
        plot_l.addWidget(canvas)

        ax = fig.subplots()
        x = np.linspace(20, 30, 300)
        ax.plot(x, 0.4 * np.sin(x * 2.2), label="Velocity/CoM/BoxLocal_V_TX")
        ax.plot(x, 0.3 * np.cos(x * 1.8), label="Velocity/CoM/BoxLocal_V_TY")
        ax.plot(x, 0.25 * np.sin(x * 1.2 + 1), label="Velocity/CoM/BoxLocal_V_TZ")
        ax.plot(x, 4.0 + 0.7 * np.sin(x * 0.9), label="Analysis/C1/RelativeHeight")
        ax.axvline(25.4, color="r", linestyle="--", linewidth=1)
        ax.set_xlabel("Time (s)")
        ax.set_ylabel("Value")
        ax.grid(True, alpha=0.3)
        ax.legend(loc="upper right", ncol=2)
        fig.tight_layout()
        layout.addWidget(plot_group)


class PopupMockWindow(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Popup Plot - Popup_1")
        self.resize(1000, 700)

        l = QVBoxLayout(self)

        fig = Figure(figsize=(9, 6), dpi=100)
        canvas = FigureCanvas(fig)
        l.addWidget(NavigationToolbar(canvas, self))
        l.addWidget(canvas)

        ax = fig.subplots()
        x = np.linspace(20, 30, 400)
        ax.plot(x, np.sin(x * 2.2), label="Velocity/CoM/BoxLocal_V_TX")
        ax.plot(x, np.cos(x * 1.8), label="Velocity/CoM/BoxLocal_V_TY")
        ax.plot(x, np.sin(x * 1.1 + 0.8), label="Velocity/CoM/BoxLocal_V_TZ")
        ax.axvline(25.4, color="r", linestyle="--", linewidth=1, label="Selected Time")
        ax.set_title("Popup Plot - Popup_1")
        ax.set_xlabel("Time (s)")
        ax.set_ylabel("Value")
        ax.grid(True, alpha=0.3)
        ax.legend(loc="upper right")
        fig.tight_layout()

        l.addWidget(QLabel("Clicking the popup plot syncs the selected time back to Step 2."))


class Step1ProcessingModeMockWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Step 1 - Raw Data Processing (Processing Mode Mock)")
        self.resize(1440, 900)

        root = QWidget()
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)

        title = QLabel("Step 1: Raw Data Processing")
        title.setStyleSheet("font-weight: 600; font-size: 18px;")
        layout.addWidget(title)

        group = QGroupBox("Raw Data Processing")
        group_layout = QVBoxLayout(group)

        top_layout = QHBoxLayout()

        plot_container = QWidget()
        plot_layout = QVBoxLayout(plot_container)
        plot_layout.setContentsMargins(0, 0, 0, 0)

        fig = Figure(figsize=(7, 4), dpi=100)
        preview_canvas = FigureCanvas(fig)
        plot_layout.addWidget(NavigationToolbar(preview_canvas, self))
        plot_layout.addWidget(preview_canvas)

        ax = fig.subplots()
        x = np.linspace(0, 100, 400)
        y = 40 + 10 * np.sin(x / 6)
        ax.plot(x, y, color="#2b6cb0", linewidth=1.8, label="RigidBody_Position_X")
        ax.axvspan(20, 30, color="#68d391", alpha=0.35, label="Slice Range")
        ax.set_title("Raw Data Preview")
        ax.set_xlabel("Time (s)")
        ax.set_ylabel("Value")
        ax.grid(True, alpha=0.3)
        ax.legend(loc="upper right")
        fig.tight_layout()

        right_panel = QVBoxLayout()
        right_panel.addWidget(QPushButton("Load CSV File..."))
        right_panel.addWidget(QLabel("C:/Data/Experiment1.csv"))

        box_dims = QGroupBox("Box Dimensions (mm)")
        box_dims_layout = QGridLayout(box_dims)
        box_dims_layout.addWidget(QLabel("L:"), 0, 0)
        box_dims_layout.addWidget(QLineEdit("1820.0"), 0, 1)
        box_dims_layout.addWidget(QLabel("W:"), 1, 0)
        box_dims_layout.addWidget(QLineEdit("1110.0"), 1, 1)
        box_dims_layout.addWidget(QLabel("H:"), 2, 0)
        box_dims_layout.addWidget(QLineEdit("164.0"), 2, 1)
        right_panel.addWidget(box_dims)

        log_output = QTextEdit()
        log_output.setReadOnly(True)
        log_output.setPlainText(
            "[INFO] Loaded C:/Data/Experiment1.csv\n"
            "[INFO] Preview parsing complete.\n"
            "[INFO] Temporary mock reference only.\n"
            "[INFO] Current mode: Raw\n"
            "[INFO] Smoothing mode uses the default smoothing and filtering pipeline."
        )
        right_panel.addWidget(log_output)

        top_layout.addWidget(plot_container, 8)
        top_layout.addLayout(right_panel, 3)
        group_layout.addLayout(top_layout)

        bottom_controls = QHBoxLayout()

        plot_options = QGroupBox("Plot Options")
        plot_options_layout = QHBoxLayout(plot_options)
        plot_options_layout.addWidget(QPushButton("Select Data..."))
        plot_options_layout.addWidget(QLabel("Selected: RigidBody Center"))
        plot_options_layout.addWidget(QLabel("Axis:"))
        axis_combo = QComboBox()
        axis_combo.addItems(["Position-X", "Position-Y", "Position-Z"])
        plot_options_layout.addWidget(axis_combo)
        bottom_controls.addWidget(plot_options, 4)

        slice_group = QGroupBox("Slice Range")
        slice_group.setCheckable(True)
        slice_group.setChecked(True)
        slice_layout = QHBoxLayout(slice_group)
        slice_layout.addWidget(QLabel("Start:"))
        slice_layout.addWidget(QLineEdit("20.0"))
        slice_layout.addWidget(QLabel("End:"))
        slice_layout.addWidget(QLineEdit("30.0"))
        bottom_controls.addWidget(slice_group, 3)

        processing_group = QGroupBox("Processing Mode")
        processing_layout = QVBoxLayout(processing_group)

        radio_row = QHBoxLayout()
        raw = QRadioButton("Raw")
        raw.setChecked(True)
        smoothing = QRadioButton("Smoothing")
        advanced = QRadioButton("Advanced")
        radio_row.addWidget(raw)
        radio_row.addWidget(smoothing)
        radio_row.addWidget(advanced)
        radio_row.addStretch()
        adv_button = QPushButton("Advanced Settings...")
        adv_button.setEnabled(False)
        radio_row.addWidget(adv_button)
        processing_layout.addLayout(radio_row)

        mode_description = QLabel(
            "Raw minimizes processing and may produce noisier velocity and acceleration."
        )
        mode_description.setWordWrap(True)
        mode_description.setStyleSheet("color: #4a5568;")
        processing_layout.addWidget(mode_description)
        bottom_controls.addWidget(processing_group, 5)

        run_controls = QVBoxLayout()
        run_controls.addWidget(QPushButton("Run Analysis"))
        run_controls.addWidget(QPushButton("Export Results to CSV"))
        bottom_controls.addLayout(run_controls, 2)

        group_layout.addLayout(bottom_controls)
        layout.addWidget(group, 1)


class AdvancedProcessingDialogMock(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Advanced Processing Settings")
        self.resize(1120, 700)

        root = QVBoxLayout(self)
        content = QGridLayout()
        content.setColumnStretch(0, 1)
        content.setColumnStretch(1, 1)
        content.setHorizontalSpacing(18)
        content.setVerticalSpacing(14)
        root.addLayout(content)

        left_column = QVBoxLayout()
        left_column.setSpacing(14)
        right_column = QVBoxLayout()
        right_column.setSpacing(14)
        content.addLayout(left_column, 0, 0)
        content.addLayout(right_column, 0, 1)

        marker_group = QGroupBox("Marker Smoothing")
        marker_layout = QVBoxLayout(marker_group)
        marker_note = QLabel(
            "Controls how raw marker tracks are smoothed before pose estimation begins."
        )
        marker_note.setWordWrap(True)
        marker_note.setStyleSheet("color: #4a5568;")
        marker_layout.addWidget(marker_note)
        marker_toggle = QCheckBox("Enable marker smoothing")
        marker_toggle.setChecked(True)
        marker_layout.addWidget(marker_toggle)
        marker_toggle_note = QLabel(
            "Recommended for smoothing mode. Disabling this keeps the marker data closer to the raw input."
        )
        marker_toggle_note.setWordWrap(True)
        marker_toggle_note.setStyleSheet("color: #718096; font-size: 11px; margin-left: 18px;")
        marker_layout.addWidget(marker_toggle_note)
        marker_form = QFormLayout()
        method_combo = QComboBox()
        method_combo.addItems(["Butterworth -> Moving Average", "Butterworth", "Moving Average"])
        marker_form.addRow("Method:", method_combo)
        marker_layout.addLayout(marker_form)
        left_column.addWidget(marker_group)

        range_group = QGroupBox("Range Edge Handling")
        range_layout = QVBoxLayout(range_group)
        range_note = QLabel(
            "Controls how the selected time range is handled near the start and end boundaries."
        )
        range_note.setWordWrap(True)
        range_note.setStyleSheet("color: #4a5568;")
        range_layout.addWidget(range_note)
        range_form = QFormLayout()
        trimming_combo = QComboBox()
        trimming_combo.addItems([
            "Stable (recommended)",
            "Fast (less accurate near range edges)",
        ])
        range_form.addRow("Mode:", trimming_combo)
        range_layout.addLayout(range_form)
        range_hint = QLabel(
            "Stable keeps a small hidden margin around the selected range during calculations. "
            "Fast trims earlier and can be less reliable near the boundaries."
        )
        range_hint.setWordWrap(True)
        range_hint.setStyleSheet("color: #718096; font-size: 11px;")
        range_layout.addWidget(range_hint)
        left_column.addWidget(range_group)

        pose_group = QGroupBox("Pose")
        pose_layout = QVBoxLayout(pose_group)
        pose_note = QLabel(
            "Pose options affect the rigid-body position and orientation before velocity and acceleration are derived."
        )
        pose_note.setWordWrap(True)
        pose_note.setStyleSheet("color: #4a5568;")
        pose_layout.addWidget(pose_note)
        pose_lpf = QCheckBox("Pose low-pass filter")
        pose_ma = QCheckBox("Pose moving average")
        pose_ma.setChecked(True)
        pose_layout.addWidget(pose_lpf)
        pose_layout.addWidget(QLabel("  Reduces fast pose jitter before derivatives are computed."))
        pose_layout.itemAt(pose_layout.count() - 1).widget().setStyleSheet("color: #718096; font-size: 11px;")
        pose_layout.addWidget(pose_ma)
        pose_layout.addWidget(QLabel("  Applies a small moving average to pose data for additional stabilization."))
        pose_layout.itemAt(pose_layout.count() - 1).widget().setStyleSheet("color: #718096; font-size: 11px;")
        left_column.addWidget(pose_group)

        derivative_group = QGroupBox("Derivative Method")
        derivative_layout = QVBoxLayout(derivative_group)
        derivative_note = QLabel(
            "Selects how velocity and acceleration are derived from pose data."
        )
        derivative_note.setWordWrap(True)
        derivative_note.setStyleSheet("color: #4a5568;")
        derivative_layout.addWidget(derivative_note)
        method_form = QFormLayout()
        velocity_method = QComboBox()
        velocity_method.addItems(["Spline", "Finite Difference"])
        acceleration_method = QComboBox()
        acceleration_method.addItems(["Spline", "Finite Difference"])
        spline_position = QLineEdit("0.010000")
        spline_rotation = QLineEdit("0.001000")
        spline_degree = QLineEdit("3")
        method_form.addRow("Velocity:", velocity_method)
        method_form.addRow("Acceleration:", acceleration_method)
        method_form.addRow("Position spline factor:", spline_position)
        method_form.addRow("Rotation spline factor:", spline_rotation)
        method_form.addRow("Spline degree:", spline_degree)
        derivative_layout.addLayout(method_form)
        derivative_hint = QLabel(
            "Spline is smoother and more stable. Finite Difference is closer to raw derivatives but noisier."
        )
        derivative_hint.setWordWrap(True)
        derivative_hint.setStyleSheet("color: #718096; font-size: 11px;")
        derivative_layout.addWidget(derivative_hint)
        derivative_layout.addWidget(QLabel("These spline parameters are used when either derivative method is set to Spline."))
        derivative_layout.itemAt(derivative_layout.count() - 1).widget().setWordWrap(True)
        derivative_layout.itemAt(derivative_layout.count() - 1).widget().setStyleSheet("color: #718096; font-size: 11px;")
        right_column.addWidget(derivative_group)

        velocity_group = QGroupBox("Velocity")
        velocity_layout = QVBoxLayout(velocity_group)
        velocity_note = QLabel(
            "Post-processing applied after velocity has been calculated."
        )
        velocity_note.setWordWrap(True)
        velocity_note.setStyleSheet("color: #4a5568;")
        velocity_layout.addWidget(velocity_note)
        vel_lpf = QCheckBox("Velocity low-pass filter")
        velocity_layout.addWidget(vel_lpf)
        vel_hint = QLabel(
            "Useful when the derived velocity still contains rapid oscillations."
        )
        vel_hint.setWordWrap(True)
        vel_hint.setStyleSheet("color: #718096; font-size: 11px; margin-left: 18px;")
        velocity_layout.addWidget(vel_hint)
        right_column.addWidget(velocity_group)

        acc_group = QGroupBox("Acceleration")
        acc_layout = QVBoxLayout(acc_group)
        acc_note = QLabel(
            "Post-processing applied after acceleration has been calculated."
        )
        acc_note.setWordWrap(True)
        acc_note.setStyleSheet("color: #4a5568;")
        acc_layout.addWidget(acc_note)
        acc_lpf = QCheckBox("Acceleration low-pass filter")
        acc_layout.addWidget(acc_lpf)
        acc_hint = QLabel(
            "Recommended when acceleration is too noisy. Corner acceleration is derived from the filtered CoM and angular acceleration."
        )
        acc_hint.setWordWrap(True)
        acc_hint.setStyleSheet("color: #718096; font-size: 11px; margin-left: 18px;")
        acc_layout.addWidget(acc_hint)
        right_column.addWidget(acc_group)

        left_column.addStretch()
        right_column.addStretch()

        buttons = QHBoxLayout()
        buttons.addStretch()
        buttons.addWidget(QPushButton("Cancel"))
        ok_button = QPushButton("OK")
        ok_button.setDefault(True)
        buttons.addWidget(ok_button)
        root.addLayout(buttons)


class Step1SliceWorkflowMockWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Step 1 - Slice First Workflow (Temporary Mock Reference)")
        self.resize(1500, 940)

        root = QWidget()
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)

        title = QLabel("Step 1: Load, Slice, and Process")
        title.setStyleSheet("font-weight: 600; font-size: 18px;")
        layout.addWidget(title)

        status_row = QHBoxLayout()
        for text, style in [
            ("Source: Loaded", "background:#e6fffa; color:#234e52;"),
            ("Slice: Ready", "background:#ebf8ff; color:#2a4365;"),
            ("Result: In Memory", "background:#f0fff4; color:#22543d;"),
        ]:
            chip = QLabel(text)
            chip.setStyleSheet(
                "padding: 6px 10px; border-radius: 11px; font-weight: 600; "
                f"{style}"
            )
            status_row.addWidget(chip)
        status_row.addStretch()
        layout.addLayout(status_row)

        group = QGroupBox("Raw Data Processing")
        group_layout = QVBoxLayout(group)

        top_layout = QHBoxLayout()

        plot_container = QWidget()
        plot_layout = QVBoxLayout(plot_container)
        plot_layout.setContentsMargins(0, 0, 0, 0)

        fig = Figure(figsize=(8.4, 4.5), dpi=100)
        preview_canvas = FigureCanvas(fig)
        plot_layout.addWidget(NavigationToolbar(preview_canvas, self))
        plot_layout.addWidget(preview_canvas)

        ax = fig.subplots()
        x = np.linspace(0, 120, 600)
        y = 50 + 6 * np.sin(x / 8) + 1.2 * np.cos(x / 2.5)
        ax.plot(x, y, color="#1f4f8a", linewidth=1.7, label="RigidBody Center / Position-X")
        ax.axvspan(39.2, 70.8, color="#b2f5ea", alpha=0.45, label="Processing Range (with padding)")
        ax.axvspan(40, 70, color="#68d391", alpha=0.55, label="User Slice")
        ax.set_title("Raw Data Preview")
        ax.set_xlabel("Time (s)")
        ax.set_ylabel("Value")
        ax.grid(True, alpha=0.25)
        ax.legend(loc="upper right")
        fig.tight_layout()

        right_panel = QVBoxLayout()
        right_panel.addWidget(QPushButton("Load CSV File..."))
        right_panel.addWidget(QLabel("D:/DropTest/Run_07.csv"))

        source_group = QGroupBox("Source Summary")
        source_layout = QFormLayout(source_group)
        source_layout.addRow("Full Range:", QLabel("0.000s ~ 120.000s"))
        source_layout.addRow("Rows:", QLabel("4,812,114"))
        source_layout.addRow("Selected Target:", QLabel("RigidBody Center"))
        right_panel.addWidget(source_group)

        slice_summary = QGroupBox("Slice Summary")
        slice_summary_layout = QFormLayout(slice_summary)
        slice_summary_layout.addRow("User Slice:", QLabel("40.000s ~ 70.000s"))
        slice_summary_layout.addRow("Padding:", QLabel("0.800s on each side"))
        slice_summary_layout.addRow("Processing Range:", QLabel("39.200s ~ 70.800s"))
        slice_summary_layout.addRow("Prepared Slice Rows:", QLabel("128,401"))
        right_panel.addWidget(slice_summary)

        log_output = QTextEdit()
        log_output.setReadOnly(True)
        log_output.setPlainText(
            "[INFO] Loaded D:/DropTest/Run_07.csv\n"
            "[INFO] Preview parsing complete.\n"
            "[INFO] Slice prepared and cached.\n"
            "[INFO] Saved slice artifact: run_07_slice_40_70.parquet\n"
            "[INFO] Processing completed. Result is available in memory.\n"
            "[INFO] Open Step 2 to inspect before exporting."
        )
        right_panel.addWidget(log_output)

        top_layout.addWidget(plot_container, 8)
        top_layout.addLayout(right_panel, 3)
        group_layout.addLayout(top_layout)

        middle_controls = QHBoxLayout()

        plot_options = QGroupBox("Plot Options")
        plot_options_layout = QHBoxLayout(plot_options)
        plot_options_layout.addWidget(QPushButton("Select Data..."))
        plot_options_layout.addWidget(QLabel("Selected: RigidBody Center"))
        plot_options_layout.addWidget(QLabel("Axis:"))
        axis_combo = QComboBox()
        axis_combo.addItems(["Position-X", "Position-Y", "Position-Z"])
        plot_options_layout.addWidget(axis_combo)
        middle_controls.addWidget(plot_options, 4)

        slice_group = QGroupBox("Slice Settings")
        slice_layout = QGridLayout(slice_group)
        slice_layout.addWidget(QLabel("Start:"), 0, 0)
        slice_layout.addWidget(QLineEdit("40.0"), 0, 1)
        slice_layout.addWidget(QLabel("End:"), 0, 2)
        slice_layout.addWidget(QLineEdit("70.0"), 0, 3)
        slice_layout.addWidget(QLabel("Padding Mode:"), 1, 0)
        padding_combo = QComboBox()
        padding_combo.addItems(["Auto (from processing settings)", "Manual"])
        slice_layout.addWidget(padding_combo, 1, 1, 1, 3)
        middle_controls.addWidget(slice_group, 5)

        processing_group = QGroupBox("Processing Settings")
        processing_layout = QVBoxLayout(processing_group)
        mode_row = QHBoxLayout()
        raw = QRadioButton("Raw")
        standard = QRadioButton("Standard")
        standard.setChecked(True)
        advanced = QRadioButton("Advanced")
        mode_row.addWidget(raw)
        mode_row.addWidget(standard)
        mode_row.addWidget(advanced)
        mode_row.addStretch()
        settings_btn = QPushButton("Advanced Settings...")
        mode_row.addWidget(settings_btn)
        processing_layout.addLayout(mode_row)

        resampling_row = QHBoxLayout()
        resampling_row.addWidget(QCheckBox("Enable Resampling"))
        resampling_factor = QComboBox()
        resampling_factor.addItems(["2x", "3x", "4x"])
        resampling_row.addWidget(resampling_factor)
        resampling_row.addStretch()
        processing_layout.addLayout(resampling_row)

        processing_hint = QLabel(
            "Processing settings can change without rebuilding the raw slice. "
            "Only the in-memory result becomes stale."
        )
        processing_hint.setWordWrap(True)
        processing_hint.setStyleSheet("color: #4a5568;")
        processing_layout.addWidget(processing_hint)
        middle_controls.addWidget(processing_group, 5)

        group_layout.addLayout(middle_controls)

        action_group = QGroupBox("Workflow Actions")
        action_layout = QGridLayout(action_group)
        action_layout.addWidget(QPushButton("Prepare Slice"), 0, 0)
        action_layout.addWidget(QPushButton("Save Slice As..."), 0, 1)
        action_layout.addWidget(QPushButton("Run Processing"), 0, 2)
        action_layout.addWidget(QPushButton("Open in Step 2"), 0, 3)
        action_layout.addWidget(QPushButton("Export Final Result"), 0, 4)

        slice_state = QLabel("Slice state: Ready")
        slice_state.setStyleSheet("font-weight: 600; color: #2a4365;")
        action_layout.addWidget(slice_state, 1, 0, 1, 2)

        process_state = QLabel("Result state: Processed in memory")
        process_state.setStyleSheet("font-weight: 600; color: #22543d;")
        action_layout.addWidget(process_state, 1, 2, 1, 2)

        export_state = QLabel("Export state: Not exported yet")
        export_state.setStyleSheet("font-weight: 600; color: #744210;")
        action_layout.addWidget(export_state, 1, 4)
        group_layout.addWidget(action_group)

        stale_notice = QLabel(
            "If slice range changes: re-prepare slice and re-run processing. "
            "If only processing settings change: re-run processing only."
        )
        stale_notice.setStyleSheet("color: #744210;")
        group_layout.addWidget(stale_notice)

        layout.addWidget(group, 1)


class Step2InMemoryResultMockWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Step 2 - In-Memory Result Review (Temporary Mock Reference)")
        self.resize(1500, 980)

        root = QWidget()
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)

        title = QLabel("Step 2: Results Analysis")
        title.setStyleSheet("font-weight: 600; font-size: 18px;")
        layout.addWidget(title)

        info_banner = QLabel(
            "Viewing in-memory result from Step 1. Export is optional and can be done after review."
        )
        info_banner.setStyleSheet(
            "background:#fffaf0; color:#744210; border:1px solid #f6ad55; "
            "padding:8px 10px; border-radius:6px;"
        )
        layout.addWidget(info_banner)

        context_group = QGroupBox("Time Window")
        context_layout = QVBoxLayout(context_group)

        row1 = QHBoxLayout()
        row1.addWidget(QLabel("Active Source:"))
        row1.addWidget(QLabel("run_07_slice_40_70.parquet"))
        row1.addStretch()
        row1.addWidget(QLabel("Result State:"))
        row1.addWidget(QLabel("In Memory"))
        row1.addStretch()
        row1.addWidget(QLabel("Samples:"))
        row1.addWidget(QLabel("12,801"))
        context_layout.addLayout(row1)
        context_layout.addWidget(QLabel("Full: 0.000s ~ 120.000s | Slice: 40.000s ~ 70.000s | Processing Range: 39.200s ~ 70.800s"))

        timeline = QFrame()
        timeline.setFrameShape(QFrame.StyledPanel)
        timeline_l = QHBoxLayout(timeline)
        timeline_l.setContentsMargins(0, 0, 0, 0)
        timeline_l.setSpacing(0)
        left = QWidget()
        left.setStyleSheet("background:#d7dbe0;")
        mid = QWidget()
        mid.setStyleSheet("background:#68d391;")
        right = QWidget()
        right.setStyleSheet("background:#d7dbe0;")
        timeline_l.addWidget(left, 333)
        timeline_l.addWidget(mid, 250)
        timeline_l.addWidget(right, 417)
        timeline.setFixedHeight(18)
        context_layout.addWidget(timeline)
        layout.addWidget(context_group)

        splitter = QSplitter(Qt.Horizontal)

        left_panel = QGroupBox("1. Result Source")
        left_l = QVBoxLayout(left_panel)
        left_l.addWidget(QLabel("Current Session Result"))
        session_list = QListWidget()
        session_list.addItems(
            [
                "In-memory result (current)",
                "run_05_result.csv",
                "run_06_result.csv",
            ]
        )
        session_list.setCurrentRow(0)
        left_l.addWidget(session_list)
        left_l.addWidget(QPushButton("Import Exported Result..."))
        splitter.addWidget(left_panel)

        mid_panel = QGroupBox("2. Data Selection")
        mid_l = QVBoxLayout(mid_panel)
        tree = QTreeWidget()
        tree.setHeaderLabel("Select Data to Plot")

        velocity = QTreeWidgetItem(tree, ["Velocity"])
        vel_com = QTreeWidgetItem(velocity, ["CoM"])
        for key in ["Box Local X", "Box Local Y", "Box Local Z", "Global Norm"]:
            item = QTreeWidgetItem(vel_com, [key])
            item.setCheckState(0, Qt.Checked)

        acceleration = QTreeWidgetItem(tree, ["Acceleration"])
        acc_com = QTreeWidgetItem(acceleration, ["CoM"])
        for key in ["Box Local X", "Box Local Y", "Box Local Z"]:
            item = QTreeWidgetItem(acc_com, [key])
            item.setCheckState(0, Qt.Unchecked)

        analysis = QTreeWidgetItem(tree, ["Analysis"])
        c1 = QTreeWidgetItem(analysis, ["C1"])
        rel_h = QTreeWidgetItem(c1, ["Relative Height"])
        rel_h.setCheckState(0, Qt.Checked)

        tree.expandAll()
        mid_l.addWidget(tree)

        btn_row = QHBoxLayout()
        btn_row.addWidget(QPushButton("Clear Selection"))
        btn_row.addWidget(QPushButton("Plot Selected Results"))
        btn_row.addWidget(QPushButton("Open Popup"))
        mid_l.addLayout(btn_row)

        status_row = QHBoxLayout()
        status_row.addWidget(QLabel("Checked Columns: 5"))
        status_row.addStretch()
        status_row.addWidget(QPushButton("Export Final Result"))
        mid_l.addLayout(status_row)
        splitter.addWidget(mid_panel)

        right_panel = QGroupBox("3. Review Actions")
        right_l = QVBoxLayout(right_panel)

        summary_group = QGroupBox("Session Summary")
        summary_layout = QFormLayout(summary_group)
        summary_layout.addRow("Source File:", QLabel("Run_07.csv"))
        summary_layout.addRow("Slice Artifact:", QLabel("run_07_slice_40_70.parquet"))
        summary_layout.addRow("Processing Mode:", QLabel("Standard"))
        summary_layout.addRow("Export:", QLabel("Pending"))
        right_l.addWidget(summary_group)

        action_row = QHBoxLayout()
        action_row.addWidget(QPushButton("Back to Step 1"))
        action_row.addWidget(QPushButton("Export Final Result"))
        right_l.addLayout(action_row)

        point_group = QGroupBox("Point Analysis")
        point_layout = QVBoxLayout(point_group)
        target_row = QHBoxLayout()
        target_row.addWidget(QLabel("Target:"))
        target_combo = QComboBox()
        target_combo.addItems(["Velocity / CoM / Box Local X", "Velocity / CoM / Global Norm"])
        target_row.addWidget(target_combo)
        point_layout.addLayout(target_row)
        find_row = QHBoxLayout()
        find_row.addWidget(QPushButton("Abs Max"))
        find_row.addWidget(QPushButton("Max"))
        find_row.addWidget(QPushButton("Min"))
        find_row.addStretch()
        point_layout.addLayout(find_row)
        point_layout.addWidget(QLabel("Selected Point: 54.270s"))
        point_layout.addWidget(QPushButton("Export Point Data..."))
        right_l.addWidget(point_group)

        right_l.addStretch()
        splitter.addWidget(right_panel)

        splitter.setSizes([300, 700, 430])
        layout.addWidget(splitter, 1)

        plot_group = QGroupBox("Main Plot")
        plot_l = QVBoxLayout(plot_group)

        fig = Figure(figsize=(11, 3.4), dpi=100)
        canvas = FigureCanvas(fig)
        plot_l.addWidget(NavigationToolbar(canvas, self))
        plot_l.addWidget(canvas)

        ax = fig.subplots()
        x = np.linspace(40, 70, 400)
        ax.plot(x, 0.45 * np.sin(x * 0.45), label="Velocity / CoM / Box Local X")
        ax.plot(x, 0.30 * np.cos(x * 0.52), label="Velocity / CoM / Box Local Y")
        ax.plot(x, 0.25 * np.sin(x * 0.34 + 1.4), label="Velocity / CoM / Box Local Z")
        ax.plot(x, 4.3 + 0.6 * np.sin(x * 0.16), label="Analysis / C1 / Relative Height")
        ax.axvline(54.27, color="#c53030", linestyle="--", linewidth=1.2)
        ax.set_xlabel("Time (s)")
        ax.set_ylabel("Value")
        ax.grid(True, alpha=0.3)
        ax.legend(loc="upper right", ncol=2)
        fig.tight_layout()
        layout.addWidget(plot_group)


def save_widget(widget, path):
    widget.show()
    QApplication.processEvents()
    pix = widget.grab()
    pix.save(path)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setFont(QFont("Arial", 9))

    out_dir = os.path.join("docs", "analysis", "design", "gui_mockups")
    os.makedirs(out_dir, exist_ok=True)

    step1 = Step1MockWindow()
    step2 = Step2MockWindow()
    popup = PopupMockWindow()

    save_widget(step1, os.path.join(out_dir, "step1_improved_mock_v31.png"))
    save_widget(step2, os.path.join(out_dir, "step2_improved_mock_v31.png"))
    save_widget(popup, os.path.join(out_dir, "step2_popup_improved_mock_v31.png"))

    step1_modes = Step1ProcessingModeMockWindow()
    advanced_dialog = AdvancedProcessingDialogMock()
    step1_slice_workflow = Step1SliceWorkflowMockWindow()
    step2_in_memory = Step2InMemoryResultMockWindow()

    save_widget(step1_modes, os.path.join(out_dir, "step1_processing_mode_mock_v32.png"))
    save_widget(advanced_dialog, os.path.join(out_dir, "step1_advanced_settings_mock_v32.png"))
    save_widget(step1_slice_workflow, os.path.join(out_dir, "step1_slice_workflow_mock_v33.png"))
    save_widget(step2_in_memory, os.path.join(out_dir, "step2_in_memory_result_mock_v33.png"))

    print("Saved:")
    print(os.path.join(out_dir, "step1_improved_mock_v31.png"))
    print(os.path.join(out_dir, "step2_improved_mock_v31.png"))
    print(os.path.join(out_dir, "step2_popup_improved_mock_v31.png"))
    print(os.path.join(out_dir, "step1_processing_mode_mock_v32.png"))
    print(os.path.join(out_dir, "step1_advanced_settings_mock_v32.png"))
    print(os.path.join(out_dir, "step1_slice_workflow_mock_v33.png"))
    print(os.path.join(out_dir, "step2_in_memory_result_mock_v33.png"))
