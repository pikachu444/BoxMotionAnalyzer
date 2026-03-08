import sys
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QHBoxLayout,
    QVBoxLayout,
    QPushButton,
    QLabel,
)
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtCore import Qt, QSize

from src.config import config_visualization as config
from src.visualization.main_window import MainWindow
from src.analysis.main_window import MainApp

class LauncherWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(config.LAUNCHER_TITLE)
        self.setWindowIcon(QIcon(config.APP_ICON_PATH))
        self.resize(840, 380)

        self.main_window = None
        self.data_processing_window = None

        # --- Main Layout ---
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(18, 18, 18, 18)
        main_layout.setSpacing(22)
        main_layout.addStretch(1)

        # --- Left Panel (Image) ---
        image_label = QLabel()
        image_label.setFixedSize(384, 256)
        pixmap = QPixmap(config.LAUNCHER_ICON_PATH)
        if pixmap.isNull():
            # In case the image is not found, show a text placeholder
            image_label.setText("Image not found")
            image_label.setAlignment(Qt.AlignCenter)
        else:
            image_label.setPixmap(pixmap.scaled(
                QSize(384, 256), Qt.KeepAspectRatio, Qt.SmoothTransformation
            ))
        image_label.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(image_label, 0, Qt.AlignVCenter)

        # --- Right Panel (Buttons) ---
        right_panel = QWidget()
        right_panel.setFixedWidth(340)
        right_panel_layout = QVBoxLayout(right_panel)
        right_panel_layout.setContentsMargins(0, 0, 0, 0)
        right_panel_layout.setSpacing(14)
        right_panel_layout.addStretch(1)

        self.btn_data_processing = QPushButton(config.LAUNCHER_BTN_PROCESS_TEXT)
        self.btn_data_processing.clicked.connect(self.open_data_processing)
        self.btn_data_processing.setFixedSize(320, 50)
        right_panel_layout.addWidget(self.btn_data_processing, 0, Qt.AlignHCenter)

        self.btn_visualization = QPushButton(config.LAUNCHER_BTN_VISUALIZE_TEXT)
        self.btn_visualization.clicked.connect(self.open_visualization)
        self.btn_visualization.setFixedSize(320, 50)
        right_panel_layout.addWidget(self.btn_visualization, 0, Qt.AlignHCenter)

        right_panel_layout.addStretch(1)

        main_layout.addWidget(right_panel, 0, Qt.AlignVCenter)
        main_layout.addStretch(1)

    def open_visualization(self):
        """Opens the main 3D visualization window."""
        # Ensure any existing window is closed and a fresh instance is created
        if self.main_window is not None:
            self.main_window.close()

        self.main_window = MainWindow()
        self.main_window.show()

    def open_data_processing(self):
        """Opens the data processing window (MainApp)."""
        # Ensure any existing window is closed and a fresh instance is created
        if self.data_processing_window is not None:
            self.data_processing_window.close()

        self.data_processing_window = MainApp()
        self.data_processing_window.show()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    app.setWindowIcon(QIcon(config.APP_ICON_PATH))
    window = LauncherWindow()
    window.show()
    sys.exit(app.exec())
