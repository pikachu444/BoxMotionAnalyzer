import os
import sys

os.environ['QT_QPA_PLATFORM'] = 'offscreen'
os.environ['QT_QPA_FONTDIR'] = r'C:\Windows\Fonts'

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(THIS_DIR))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QApplication,
    QGroupBox,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QDialog,
)

from src.analysis.main_window import MainApp


class PlotSessionPopupMock(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Plot Session - Position_Set_A")
        self.resize(980, 620)

        root = QVBoxLayout(self)
        top = QHBoxLayout()
        top.addWidget(QLabel("Y Scale: Auto | Normalize | SymLog"))
        top.addStretch()
        top.addWidget(QPushButton("Save PNG"))
        root.addLayout(top)

        canvas_box = QGroupBox("Plot Area")
        canvas_layout = QVBoxLayout(canvas_box)
        canvas_layout.addWidget(QLabel("[Matplotlib canvas area - session specific overlay plot]"))
        root.addWidget(canvas_box)

        root.addWidget(QLabel("Columns: Position/CoM/P_TX, Position/CoM/P_TY, Position/CoM/P_TZ, Position/CoM/P_RX, Position/CoM/P_RY, Position/CoM/P_RZ"))


class MainAppWithSessionMock(MainApp):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Box Motion Analyzer v2.2 - Proposed GUI (Mock)")
        self._add_session_manager_mock()

    def _add_session_manager_mock(self):
        result_layout = self.result_widget.layout()

        session_group = QGroupBox("Plot Session Manager (Proposed)")
        session_layout = QVBoxLayout(session_group)

        row = QHBoxLayout()
        row.addWidget(QLabel("Session Name:"))
        row.addWidget(QLineEdit("Position_Set_A"))
        row.addWidget(QPushButton("Create Window"))
        row.addWidget(QPushButton("Update From Selection"))
        row.addWidget(QPushButton("Open"))
        row.addWidget(QPushButton("Close"))
        session_layout.addLayout(row)

        table = QTableWidget(3, 4)
        table.setHorizontalHeaderLabels(["Session", "Columns", "Y Scale", "Status"])
        data = [
            ("Position_Set_A", "6", "Auto", "Opened"),
            ("Velocity_Set_B", "8", "Normalize", "Opened"),
            ("Height_Set_C", "3", "Auto", "Closed"),
        ]
        for r, vals in enumerate(data):
            for c, val in enumerate(vals):
                table.setItem(r, c, QTableWidgetItem(val))
        table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        session_layout.addWidget(table)

        session_layout.addWidget(QLabel("Flow: Select related columns in existing tree -> Create Window -> Repeat for Position/Velocity/Analysis"))
        result_layout.addWidget(session_group)


def save_widget(widget, out_path):
    widget.show()
    QApplication.processEvents()
    pixmap = widget.grab()
    pixmap.save(out_path)


if __name__ == '__main__':
    app = QApplication(sys.argv)
    app.setFont(QFont('Arial', 9))

    out_dir = os.path.join(PROJECT_ROOT, 'design_proposal', 'gui_mockups')
    os.makedirs(out_dir, exist_ok=True)

    before = MainApp()
    before.setWindowTitle('Box Motion Analyzer v2.2 - Current GUI')
    before.resize(1600, 980)

    after = MainAppWithSessionMock()
    after.resize(1600, 1080)

    popup = PlotSessionPopupMock(after)

    save_widget(before, os.path.join(out_dir, 'current_mainapp_full_mock.png'))
    save_widget(after, os.path.join(out_dir, 'proposed_mainapp_full_mock.png'))
    save_widget(popup, os.path.join(out_dir, 'proposed_plot_session_popup_mock.png'))

    print('Saved regenerated mockups.')
