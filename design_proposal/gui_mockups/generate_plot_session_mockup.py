import os
import sys
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QListWidget,
    QGroupBox,
    QLineEdit,
    QComboBox,
    QCheckBox,
    QFrame,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QDialog,
)
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import numpy as np


class PrototypePlotWindow(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Plot Window: Position_Set_A")
        self.resize(1100, 760)

        root = QVBoxLayout(self)

        controls = QHBoxLayout()
        controls.addWidget(QLabel("Y Scale:"))
        scale_combo = QComboBox()
        scale_combo.addItems(["Auto", "Normalize (z-score)", "SymLog"])
        controls.addWidget(scale_combo)

        legend_check = QCheckBox("Show Legend")
        legend_check.setChecked(True)
        controls.addWidget(legend_check)

        hover_check = QCheckBox("Hover")
        hover_check.setChecked(True)
        controls.addWidget(hover_check)

        controls.addStretch()
        controls.addWidget(QPushButton("Save PNG"))
        root.addLayout(controls)

        canvas = FigureCanvas(Figure(figsize=(10, 5), dpi=100))
        ax = canvas.figure.subplots()
        x = np.arange(0, 500)
        ax.plot(x, 0.02 * x + 20 * np.sin(x / 40), label="Position/CoM/P_TX")
        ax.plot(x, -0.015 * x + 15 * np.cos(x / 30), label="Position/CoM/P_TY")
        ax.plot(x, 0.01 * x + 8 * np.sin(x / 20), label="Position/CoM/P_TZ")
        ax.set_title("Position Session")
        ax.set_xlabel("Time (s)")
        ax.set_ylabel("Value")
        ax.grid(True)
        ax.legend(loc="upper right")
        canvas.figure.tight_layout()
        root.addWidget(canvas)

        cols = QLabel("Columns (6): Position/CoM/P_TX, Position/CoM/P_TY, Position/CoM/P_TZ, Position/CoM/P_RX, Position/CoM/P_RY, Position/CoM/P_RZ")
        cols.setWordWrap(True)
        root.addWidget(cols)


class PrototypeResultsAnalyzer(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Results Analyzer - Prototype")
        self.resize(1500, 920)

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)

        top = QHBoxLayout()
        root.addLayout(top, 1)

        left_group = QGroupBox("Result Columns")
        left_layout = QVBoxLayout(left_group)
        tree = QTreeWidget()
        tree.setHeaderLabel("Select Data to Plot")

        for category, leafs in {
            "Position": ["CoM/P_TX", "CoM/P_TY", "CoM/P_TZ", "CoM/P_RX", "CoM/P_RY", "CoM/P_RZ"],
            "Velocity": ["CoM/Global_V_TX", "CoM/Global_V_TY", "CoM/Global_V_TZ", "CoM/Global_V_RZ"],
            "Acceleration": ["CoM/Global_A_TX", "CoM/Global_A_TY", "CoM/Global_A_TZ"],
            "Analysis": ["C1/RelativeHeight", "C2/RelativeHeight", "C3/RelativeHeight"],
        }.items():
            cat_item = QTreeWidgetItem(tree, [category])
            for name in leafs:
                leaf = QTreeWidgetItem(cat_item, [name])
                leaf.setCheckState(0, Qt.Checked if category == "Position" else Qt.Unchecked)
        tree.expandAll()
        left_layout.addWidget(tree)

        quick = QHBoxLayout()
        quick.addWidget(QPushButton("Quick: Position"))
        quick.addWidget(QPushButton("Quick: Velocity"))
        quick.addWidget(QPushButton("Quick: Acc"))
        quick.addWidget(QPushButton("Clear"))
        left_layout.addLayout(quick)

        top.addWidget(left_group, 4)

        right_group = QGroupBox("Preview Plot")
        right_layout = QVBoxLayout(right_group)

        preview_canvas = FigureCanvas(Figure(figsize=(7, 4), dpi=100))
        ax = preview_canvas.figure.subplots()
        x = np.arange(0, 300)
        ax.plot(x, 0.02 * x + 10 * np.sin(x / 25), label="CoM/P_TX")
        ax.plot(x, -0.01 * x + 7 * np.cos(x / 20), label="CoM/P_TY")
        ax.set_title("Current Selection Preview")
        ax.set_xlabel("Time (s)")
        ax.set_ylabel("Value")
        ax.grid(True)
        ax.legend(loc="upper right")
        preview_canvas.figure.tight_layout()
        right_layout.addWidget(preview_canvas)

        toolbar_row = QHBoxLayout()
        toolbar_row.addWidget(QLabel("Selected columns: 6"))
        toolbar_row.addStretch()
        toolbar_row.addWidget(QPushButton("Plot Selected Results"))
        right_layout.addLayout(toolbar_row)

        top.addWidget(right_group, 6)

        manager_group = QGroupBox("Plot Window Manager")
        manager_layout = QVBoxLayout(manager_group)

        create_row = QHBoxLayout()
        create_row.addWidget(QLabel("Session Name:"))
        create_row.addWidget(QLineEdit("Position_Set_A"))
        create_row.addWidget(QPushButton("Create Plot Window"))
        create_row.addWidget(QPushButton("Update Selected"))
        create_row.addWidget(QPushButton("Open"))
        create_row.addWidget(QPushButton("Close"))
        manager_layout.addLayout(create_row)

        table = QTableWidget(3, 4)
        table.setHorizontalHeaderLabels(["Session", "Columns", "Scale", "Status"])
        rows = [
            ("Position_Set_A", "6", "Auto", "Opened"),
            ("Velocity_Set_B", "8", "Normalize", "Opened"),
            ("Height_Set_C", "3", "Auto", "Closed"),
        ]
        for r, row in enumerate(rows):
            for c, val in enumerate(row):
                table.setItem(r, c, QTableWidgetItem(val))
        table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        manager_layout.addWidget(table)

        hint = QLabel("Workflow: select related columns -> create popup window -> repeat for another domain (Position/Velocity/Analysis).")
        hint.setWordWrap(True)
        manager_layout.addWidget(hint)

        root.addWidget(manager_group, 0)


def save_screenshot(widget, path):
    widget.show()
    widget.raise_()
    QApplication.processEvents()
    pixmap = widget.grab()
    pixmap.save(path)


if __name__ == "__main__":
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    app = QApplication(sys.argv)

    results_win = PrototypeResultsAnalyzer()
    popup_win = PrototypePlotWindow(results_win)

    out_dir = os.path.join("design_proposal", "gui_mockups")
    os.makedirs(out_dir, exist_ok=True)

    save_screenshot(results_win, os.path.join(out_dir, "results_analyzer_prototype.png"))
    save_screenshot(popup_win, os.path.join(out_dir, "plot_window_prototype.png"))

    print("Saved screenshots:")
    print(os.path.join(out_dir, "results_analyzer_prototype.png"))
    print(os.path.join(out_dir, "plot_window_prototype.png"))
