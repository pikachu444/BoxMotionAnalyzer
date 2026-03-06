import os
import sys

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('QT_QPA_FONTDIR', r'C:\Windows\Fonts')

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QGroupBox,
    QCheckBox,
    QComboBox,
    QListWidget,
    QTreeWidget,
    QTreeWidgetItem,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QSplitter,
    QFrame,
    QDialog,
)
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import numpy as np


class Step1MockWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('Step 1 - Raw Data Processing (Improved Mock)')
        self.resize(1280, 860)

        root = QWidget()
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)

        title = QLabel('Step 1: Raw Data Processing')
        title.setStyleSheet('font-weight: 600; font-size: 18px;')
        layout.addWidget(title)

        cfg = QGroupBox('1. Configuration')
        cfg_l = QVBoxLayout(cfg)

        r1 = QHBoxLayout()
        r1.addWidget(QLabel('Raw CSV:'))
        p = QLineEdit('C:/Data/Experiment1.csv')
        r1.addWidget(p, 1)
        r1.addWidget(QPushButton('Load...'))
        cfg_l.addLayout(r1)

        r2 = QHBoxLayout()
        r2.addWidget(QLabel('Box Dims (L/W/H):'))
        r2.addWidget(QLineEdit('1820'))
        r2.addWidget(QLineEdit('1110'))
        r2.addWidget(QLineEdit('164'))
        cfg_l.addLayout(r2)
        layout.addWidget(cfg)

        prev = QGroupBox('2. Preview & Slicing')
        prev_l = QVBoxLayout(prev)

        r3 = QHBoxLayout()
        r3.addWidget(QPushButton('Select Data...'))
        r3.addWidget(QLabel('Selected: RigidBody_1'))
        r3.addSpacing(24)
        r3.addWidget(QLabel('Axis:'))
        c = QComboBox()
        c.addItems(['Position-X', 'Position-Y', 'Position-Z'])
        r3.addWidget(c)
        r3.addWidget(QPushButton('Open Preview Plot'))
        prev_l.addLayout(r3)

        r4 = QHBoxLayout()
        chk = QCheckBox('Enable Time Slicing')
        chk.setChecked(True)
        r4.addWidget(chk)
        r4.addWidget(QLabel('Start:'))
        r4.addWidget(QLineEdit('20.0'))
        r4.addWidget(QLabel('End:'))
        r4.addWidget(QLineEdit('30.0'))
        prev_l.addLayout(r4)

        preview_canvas = FigureCanvas(Figure(figsize=(10, 3), dpi=100))
        ax = preview_canvas.figure.subplots()
        x = np.linspace(0, 100, 400)
        y = 40 + 10 * np.sin(x / 6)
        ax.plot(x, y, color='#2b6cb0', linewidth=1.8, label='RigidBody_1 Position-X')
        ax.axvspan(20, 30, color='#68d391', alpha=0.35, label='Selected Slice')
        ax.set_title('Preview Timeline')
        ax.set_xlabel('Time (s)')
        ax.set_ylabel('Value')
        ax.grid(True, alpha=0.3)
        ax.legend(loc='upper right')
        preview_canvas.figure.tight_layout()
        prev_l.addWidget(preview_canvas)

        layout.addWidget(prev, 1)

        exe = QGroupBox('3. Execution')
        exe_l = QHBoxLayout(exe)
        exe_l.addWidget(QLabel("Output: 'result_01.csv'"))
        exe_l.addStretch()
        run = QPushButton('Run Analysis & Save')
        run.setStyleSheet('font-weight: 600; padding: 6px 12px;')
        exe_l.addWidget(run)
        layout.addWidget(exe)


class Step2MockWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('Step 2 - Results Analysis (Improved Mock)')
        self.resize(1400, 940)

        root = QWidget()
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)

        title = QLabel('Step 2: Results Analysis')
        title.setStyleSheet('font-weight: 600; font-size: 18px;')
        layout.addWidget(title)

        ctx = QGroupBox('Selected File Context')
        ctx_l = QVBoxLayout(ctx)

        row1 = QHBoxLayout()
        row1.addWidget(QLabel('Active File: result_01.csv'))
        row1.addStretch()
        row1.addWidget(QLabel('Rows: 1201'))
        ctx_l.addLayout(row1)

        row2 = QHBoxLayout()
        row2.addWidget(QLabel('Full Timeline: 0.0s ~ 100.0s'))
        row2.addSpacing(30)
        row2.addWidget(QLabel('Slice Timeline: 20.0s ~ 30.0s'))
        row2.addSpacing(30)
        row2.addWidget(QLabel('Selected Columns: 3'))
        row2.addStretch()
        ctx_l.addLayout(row2)

        timeline = QFrame()
        timeline.setFrameShape(QFrame.StyledPanel)
        timeline_l = QHBoxLayout(timeline)
        timeline_l.setContentsMargins(0, 0, 0, 0)
        left = QWidget(); left.setStyleSheet('background:#d1d5db;')
        mid = QWidget(); mid.setStyleSheet('background:#68d391;')
        right = QWidget(); right.setStyleSheet('background:#d1d5db;')
        timeline_l.addWidget(left, 20)
        timeline_l.addWidget(mid, 10)
        timeline_l.addWidget(right, 70)
        timeline.setFixedHeight(18)
        ctx_l.addWidget(timeline)
        layout.addWidget(ctx)

        splitter = QSplitter(Qt.Horizontal)

        left_panel = QGroupBox('1. Result Files')
        left_l = QVBoxLayout(left_panel)
        row = QHBoxLayout()
        row.addWidget(QLineEdit('D:/Data/Experiment1_Results'))
        row.addWidget(QPushButton('Browse...'))
        left_l.addLayout(row)
        files = QListWidget()
        files.addItems(['result_01.csv', 'result_02.csv', 'result_03.csv'])
        files.setCurrentRow(0)
        left_l.addWidget(files)
        splitter.addWidget(left_panel)

        mid_panel = QGroupBox('2. Data Selection & Popup Plot')
        mid_l = QVBoxLayout(mid_panel)
        tree = QTreeWidget()
        tree.setHeaderLabel('Columns')
        top1 = QTreeWidgetItem(tree, ['Velocity'])
        for k in ['X', 'Y', 'Z']:
            n = QTreeWidgetItem(top1, [k])
            n.setCheckState(0, Qt.Checked)
        top2 = QTreeWidgetItem(tree, ['Acceleration'])
        for k in ['X', 'Y', 'Z']:
            n = QTreeWidgetItem(top2, [k])
            n.setCheckState(0, Qt.Unchecked)
        tree.expandAll()
        mid_l.addWidget(tree)

        btn_row = QHBoxLayout()
        btn_row.addWidget(QPushButton('Clear Selection'))
        btn_row.addWidget(QPushButton('Open Popup Plot'))
        btn_row.addWidget(QPushButton('Update Popup Plot'))
        mid_l.addLayout(btn_row)

        win_group = QGroupBox('Popup Windows')
        win_l = QVBoxLayout(win_group)
        table = QTableWidget(2, 4)
        table.setHorizontalHeaderLabels(['Window', 'Columns', 'Sync Cursor', 'Status'])
        vals = [
            ('Velocity_XYZ', '3', 'On', 'Opened'),
            ('Acc_XYZ', '3', 'Off', 'Closed'),
        ]
        for r, rowvals in enumerate(vals):
            for c, val in enumerate(rowvals):
                table.setItem(r, c, QTableWidgetItem(val))
        table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        win_l.addWidget(table)
        mid_l.addWidget(win_group)
        splitter.addWidget(mid_panel)

        right_panel = QGroupBox('3. Point & Export')
        right_l = QVBoxLayout(right_panel)
        r = QHBoxLayout()
        r.addWidget(QLabel('Target:'))
        cb = QComboBox()
        cb.addItems(['Velocity/X', 'Velocity/Y', 'Velocity/Z'])
        r.addWidget(cb)
        r.addWidget(QPushButton('Find Abs. Max'))
        right_l.addLayout(r)
        right_l.addWidget(QLabel('Selected: T=25.4s, Value=1.23'))
        right_l.addWidget(QPushButton('Export Point Data...'))

        export_group = QGroupBox('Export Analysis Input (Advanced)')
        export_group.setCheckable(True)
        export_group.setChecked(False)
        export_l = QVBoxLayout(export_group)
        export_l.addWidget(QLabel('Manual Offset / Manual Height / Run Time / Step / Scene Name'))
        export_l.addWidget(QPushButton('Export Scenario CSV'))
        right_l.addWidget(export_group)
        right_l.addStretch()
        splitter.addWidget(right_panel)

        splitter.setSizes([300, 500, 420])
        layout.addWidget(splitter, 1)

        plot_group = QGroupBox('Main Plot Preview (Selected File)')
        plot_l = QVBoxLayout(plot_group)
        canvas = FigureCanvas(Figure(figsize=(11, 3), dpi=100))
        ax = canvas.figure.subplots()
        x = np.linspace(20, 30, 300)
        ax.plot(x, 0.4 * np.sin(x * 2.2), label='Velocity/X')
        ax.plot(x, 0.3 * np.cos(x * 1.8), label='Velocity/Y')
        ax.plot(x, 0.25 * np.sin(x * 1.2 + 1), label='Velocity/Z')
        ax.set_xlabel('Time (s)')
        ax.set_ylabel('Value')
        ax.grid(True, alpha=0.3)
        ax.legend(loc='upper right')
        canvas.figure.tight_layout()
        plot_l.addWidget(canvas)
        layout.addWidget(plot_group)


class PopupMockWindow(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('Popup Plot - Velocity_XYZ (Synced)')
        self.resize(960, 620)

        l = QVBoxLayout(self)

        top = QHBoxLayout()
        top.addWidget(QLabel('Y Scale: Auto'))
        top.addWidget(QLabel('|'))
        top.addWidget(QLabel('Cursor Sync: On'))
        top.addStretch()
        top.addWidget(QPushButton('Save PNG'))
        l.addLayout(top)

        canvas = FigureCanvas(Figure(figsize=(9, 5), dpi=100))
        ax = canvas.figure.subplots()
        x = np.linspace(20, 30, 400)
        ax.plot(x, np.sin(x * 2.2), label='Velocity/X')
        ax.plot(x, np.cos(x * 1.8), label='Velocity/Y')
        ax.plot(x, np.sin(x * 1.1 + 0.8), label='Velocity/Z')
        ax.axvline(25.4, color='r', linestyle='--', linewidth=1, label='Selected Point')
        ax.set_title('Popup Graph (Synced)')
        ax.set_xlabel('Time (s)')
        ax.set_ylabel('Value')
        ax.grid(True, alpha=0.3)
        ax.legend(loc='upper right')
        canvas.figure.tight_layout()
        l.addWidget(canvas)

        l.addWidget(QLabel('Columns: Velocity/X, Velocity/Y, Velocity/Z'))


def save_widget(widget, path):
    widget.show()
    QApplication.processEvents()
    pix = widget.grab()
    pix.save(path)


if __name__ == '__main__':
    app = QApplication(sys.argv)
    app.setFont(QFont('Arial', 9))

    out_dir = os.path.join('design_proposal', 'gui_mockups')
    os.makedirs(out_dir, exist_ok=True)

    step1 = Step1MockWindow()
    step2 = Step2MockWindow()
    popup = PopupMockWindow()

    save_widget(step1, os.path.join(out_dir, 'step1_improved_mock.png'))
    save_widget(step2, os.path.join(out_dir, 'step2_improved_mock.png'))
    save_widget(popup, os.path.join(out_dir, 'step2_popup_improved_mock.png'))

    print('Saved:')
    print(os.path.join(out_dir, 'step1_improved_mock.png'))
    print(os.path.join(out_dir, 'step2_improved_mock.png'))
    print(os.path.join(out_dir, 'step2_popup_improved_mock.png'))
