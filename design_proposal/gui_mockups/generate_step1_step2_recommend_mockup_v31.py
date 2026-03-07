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


class Step1MockWindowV31(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Step 1 - Raw Data Processing (Current Mock)")
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


class Step2MockWindowV31(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Step 2 - Results Analysis (Current Mock)")
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


class PopupMockWindowV31(QDialog):
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


def save_widget(widget, path):
    widget.show()
    QApplication.processEvents()
    pix = widget.grab()
    pix.save(path)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setFont(QFont("Arial", 9))

    out_dir = os.path.join("design_proposal", "gui_mockups")
    os.makedirs(out_dir, exist_ok=True)

    step1 = Step1MockWindowV31()
    step2 = Step2MockWindowV31()
    popup = PopupMockWindowV31()

    save_widget(step1, os.path.join(out_dir, "step1_improved_mock_v31.png"))
    save_widget(step2, os.path.join(out_dir, "step2_improved_mock_v31.png"))
    save_widget(popup, os.path.join(out_dir, "step2_popup_improved_mock_v31.png"))

    print("Saved:")
    print(os.path.join(out_dir, "step1_improved_mock_v31.png"))
    print(os.path.join(out_dir, "step2_improved_mock_v31.png"))
    print(os.path.join(out_dir, "step2_popup_improved_mock_v31.png"))
