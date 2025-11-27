import sys
import os

# Add project root to sys.path to ensure absolute imports work
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from PySide6.QtWidgets import QApplication
from src.visualization.launcher_window import LauncherWindow

def main():
    app = QApplication(sys.argv)
    window = LauncherWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == '__main__':
    main()
