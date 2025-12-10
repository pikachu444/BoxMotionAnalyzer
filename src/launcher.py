import sys
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QHBoxLayout,
    QVBoxLayout,
    QPushButton,
    QLabel,
    QSpacerItem,
    QSizePolicy
)
from PySide6.QtGui import QPixmap
from PySide6.QtCore import Qt, QSize

from src.config import config_visualization as config
from src.visualization.main_window import MainWindow
from src.analysis.main_window import MainApp

class LauncherWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(config.LAUNCHER_TITLE)
        self.setGeometry(300, 300, 600, 300)

        self.main_window = None
        self.data_processing_window = None

        # --- Main Layout ---
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)

        # --- Left Panel (Image) ---
        image_label = QLabel()
        pixmap = QPixmap(config.LAUNCHER_ICON_PATH)
        if pixmap.isNull():
            # In case the image is not found, show a text placeholder
            image_label.setText("Image not found")
            image_label.setAlignment(Qt.AlignCenter)
        else:
            image_label.setPixmap(pixmap.scaled(
                QSize(128, 128), Qt.KeepAspectRatio, Qt.SmoothTransformation
            ))
        image_label.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(image_label, 1) # Add with stretch factor 1

        # --- Right Panel (Buttons) ---
        right_panel_layout = QVBoxLayout()

        # Add some space at the top
        right_panel_layout.addSpacerItem(QSpacerItem(20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding))

        self.btn_data_processing = QPushButton(config.LAUNCHER_BTN_PROCESS_TEXT)
        self.btn_data_processing.clicked.connect(self.open_data_processing)
        self.btn_data_processing.setMinimumHeight(40)
        right_panel_layout.addWidget(self.btn_data_processing)

        self.btn_visualization = QPushButton(config.LAUNCHER_BTN_VISUALIZE_TEXT)
        self.btn_visualization.clicked.connect(self.open_visualization)
        self.btn_visualization.setMinimumHeight(40)
        right_panel_layout.addWidget(self.btn_visualization)

        # Add some space at the bottom
        right_panel_layout.addSpacerItem(QSpacerItem(20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding))

        main_layout.addLayout(right_panel_layout, 1) # Add with stretch factor 1

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
    window = LauncherWindow()
    window.show()
    sys.exit(app.exec())
