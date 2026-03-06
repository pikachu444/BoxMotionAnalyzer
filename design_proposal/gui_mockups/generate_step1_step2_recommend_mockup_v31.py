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
    QSplitter,
    QFrame,
    QDialog,
    QGridLayout,
)
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qtagg import NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure
import numpy as np


class Step1MockWindowV31(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('Step 1 - Raw Data Processing (v3.1)')
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
        r3.addStretch()
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

        fig = Figure(figsize=(10, 3), dpi=100)
        preview_canvas = FigureCanvas(fig)
        prev_l.addWidget(NavigationToolbar(preview_canvas, self))
        prev_l.addWidget(preview_canvas)

        ax = fig.subplots()
        x = np.linspace(0, 100, 400)
        y = 40 + 10 * np.sin(x / 6)
        ax.plot(x, y, color='#2b6cb0', linewidth=1.8, label='RigidBody_1 Position-X')
        ax.axvspan(20, 30, color='#68d391', alpha=0.35, label='Selected Slice')
        ax.set_title('Preview Timeline')
        ax.set_xlabel('Time (s)')
        ax.set_ylabel('Value')
        ax.grid(True, alpha=0.3)
        ax.legend(loc='upper right')
        fig.tight_layout()

        layout.addWidget(prev, 1)

        exe = QGroupBox('3. Execution')
        exe_l = QHBoxLayout(exe)
        exe_l.addWidget(QLabel("Output: 'result_01.csv'"))
        exe_l.addStretch()
        run = QPushButton('Run Analysis & Save')
        run.setStyleSheet('font-weight: 600; padding: 6px 12px;')
        exe_l.addWidget(run)
        layout.addWidget(exe)


class Step2MockWindowV31(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('Step 2 - Results Analysis (v3.1)')
        self.resize(1460, 980)

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
        row2.addWidget(QLabel('Selected Columns: 8 (mixed scales allowed)'))
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

        mid_panel = QGroupBox('2. Data Selection')
        mid_l = QVBoxLayout(mid_panel)
        tree = QTreeWidget()
        tree.setHeaderLabel('Columns')

        vel = QTreeWidgetItem(tree, ['Velocity'])
        for k in ['X', 'Y', 'Z', 'Norm']:
            n = QTreeWidgetItem(vel, [k])
            n.setCheckState(0, Qt.Checked)

        acc = QTreeWidgetItem(tree, ['Acceleration'])
        for k in ['X', 'Y', 'Z']:
            n = QTreeWidgetItem(acc, [k])
            n.setCheckState(0, Qt.Checked)

        ana = QTreeWidgetItem(tree, ['Analysis'])
        h = QTreeWidgetItem(ana, ['RelativeHeight'])
        h.setCheckState(0, Qt.Checked)

        tree.expandAll()
        mid_l.addWidget(tree)

        btn_row = QHBoxLayout()
        btn_row.addWidget(QPushButton('Clear Selection'))
        btn_row.addWidget(QPushButton('Open Popup (Current Selection)'))
        btn_row.addWidget(QPushButton('Open Popup (Custom Subset)...'))
        mid_l.addLayout(btn_row)

        btn_row2 = QHBoxLayout()
        btn_row2.addWidget(QPushButton('Update Popup Plot'))
        btn_row2.addStretch()
        btn_row2.addWidget(QPushButton('Close All Popups'))
        mid_l.addLayout(btn_row2)

        popup_state = QGroupBox('Popup Plot Status')
        popup_state_l = QHBoxLayout(popup_state)
        popup_state_l.addWidget(QLabel('Opened Popups: 2'))
        popup_state_l.addSpacing(12)
        popup_state_l.addWidget(QLabel('Examples: Velocity_XYZ, Height_only'))
        popup_state_l.addStretch()
        mid_l.addWidget(popup_state)

        note = QLabel('User strategy: Main preview can overlay mixed scales. For clear comparison, open popup with similar-scale subset.')
        note.setWordWrap(True)
        mid_l.addWidget(note)

        splitter.addWidget(mid_panel)

        right_panel = QGroupBox('3. Point Analysis & Export')
        right_l = QVBoxLayout(right_panel)

        row_pa = QHBoxLayout()
        row_pa.addWidget(QLabel('Target:'))
        cb = QComboBox()
        cb.addItems(['Velocity/X', 'Velocity/Y', 'Velocity/Z', 'RelativeHeight'])
        row_pa.addWidget(cb)
        row_pa.addWidget(QPushButton('Find Abs. Max'))
        right_l.addLayout(row_pa)

        right_l.addWidget(QLabel('Selected: T=25.4s, Value=1.23'))
        right_l.addWidget(QPushButton('Export Point Data...'))

        export_group = QGroupBox('4. Export Analysis Input')
        export_l = QVBoxLayout(export_group)

        flags_row = QHBoxLayout()
        flags_row.addWidget(QCheckBox('Manual Offset'))
        flags_row.addWidget(QCheckBox('Manual Height'))
        flags_row.addStretch()
        export_l.addLayout(flags_row)

        grid = QGridLayout()
        grid.addWidget(QLabel('Offset0:'), 0, 0)
        c0 = QComboBox(); c0.addItems(['C1', 'C2', 'C3', 'C4', 'C5', 'C6', 'C7', 'C8'])
        grid.addWidget(c0, 0, 1)
        grid.addWidget(QLineEdit('H'), 0, 2)

        grid.addWidget(QLabel('Offset1:'), 1, 0)
        c1 = QComboBox(); c1.addItems(['C1', 'C2', 'C3', 'C4', 'C5', 'C6', 'C7', 'C8'])
        grid.addWidget(c1, 1, 1)
        grid.addWidget(QLineEdit('H'), 1, 2)

        grid.addWidget(QLabel('Offset2:'), 2, 0)
        c2 = QComboBox(); c2.addItems(['C1', 'C2', 'C3', 'C4', 'C5', 'C6', 'C7', 'C8'])
        grid.addWidget(c2, 2, 1)
        grid.addWidget(QLineEdit('H'), 2, 2)

        grid.addWidget(QLabel('Run Time:'), 3, 0)
        grid.addWidget(QLineEdit('0.1'), 3, 1, 1, 2)

        grid.addWidget(QLabel('Step:'), 4, 0)
        grid.addWidget(QLineEdit('1e-7'), 4, 1, 1, 2)

        grid.addWidget(QLabel('Scene Name:'), 5, 0)
        grid.addWidget(QLineEdit('Drop1'), 5, 1, 1, 2)

        export_l.addLayout(grid)
        export_l.addWidget(QPushButton('Export Scenario CSV'))
        right_l.addWidget(export_group)
        right_l.addStretch()
        splitter.addWidget(right_panel)

        splitter.setSizes([280, 650, 520])
        layout.addWidget(splitter, 1)

        plot_group = QGroupBox('Main Plot Preview (All Checked Columns Overlay)')
        plot_l = QVBoxLayout(plot_group)

        fig = Figure(figsize=(11, 3), dpi=100)
        canvas = FigureCanvas(fig)
        plot_l.addWidget(NavigationToolbar(canvas, self))
        plot_l.addWidget(canvas)

        ax = fig.subplots()
        x = np.linspace(20, 30, 300)
        ax.plot(x, 0.4 * np.sin(x * 2.2), label='Velocity/X')
        ax.plot(x, 0.3 * np.cos(x * 1.8), label='Velocity/Y')
        ax.plot(x, 0.25 * np.sin(x * 1.2 + 1), label='Velocity/Z')
        ax.plot(x, 4.0 + 0.7 * np.sin(x * 0.9), label='RelativeHeight')
        ax.plot(x, 0.8 * np.cos(x * 2.7), label='Acceleration/X')
        ax.set_xlabel('Time (s)')
        ax.set_ylabel('Value (Mixed Scale)')
        ax.grid(True, alpha=0.3)
        ax.legend(loc='upper right', ncol=2)
        fig.tight_layout()
        plot_l.addWidget(QLabel('Note: mixed-scale overlay is allowed here. Use popup for similar-scale comparison.'))

        layout.addWidget(plot_group)


class PopupMockWindowV31(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('Popup Plot - Velocity_XYZ (Synced)')
        self.resize(980, 690)

        l = QVBoxLayout(self)

        fig = Figure(figsize=(9, 5), dpi=100)
        canvas = FigureCanvas(fig)
        l.addWidget(NavigationToolbar(canvas, self))

        top = QHBoxLayout()
        top.addWidget(QLabel('Y Scale: Auto'))
        top.addWidget(QLabel('|'))
        top.addWidget(QLabel('Cursor Sync: On'))
        top.addStretch()
        top.addWidget(QPushButton('Save PNG'))
        l.addLayout(top)

        ax = fig.subplots()
        x = np.linspace(20, 30, 400)
        ax.plot(x, np.sin(x * 2.2), label='Velocity/X')
        ax.plot(x, np.cos(x * 1.8), label='Velocity/Y')
        ax.plot(x, np.sin(x * 1.1 + 0.8), label='Velocity/Z')
        ax.axvline(25.4, color='r', linestyle='--', linewidth=1, label='Selected Point')
        ax.set_title('Popup Graph (Synced, Multi-Column)')
        ax.set_xlabel('Time (s)')
        ax.set_ylabel('Value')
        ax.grid(True, alpha=0.3)
        ax.legend(loc='upper right')
        fig.tight_layout()

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

    step1 = Step1MockWindowV31()
    step2 = Step2MockWindowV31()
    popup = PopupMockWindowV31()

    save_widget(step1, os.path.join(out_dir, 'step1_improved_mock_v31.png'))
    save_widget(step2, os.path.join(out_dir, 'step2_improved_mock_v31.png'))
    save_widget(popup, os.path.join(out_dir, 'step2_popup_improved_mock_v31.png'))

    print('Saved:')
    print(os.path.join(out_dir, 'step1_improved_mock_v31.png'))
    print(os.path.join(out_dir, 'step2_improved_mock_v31.png'))
    print(os.path.join(out_dir, 'step2_popup_improved_mock_v31.png'))
