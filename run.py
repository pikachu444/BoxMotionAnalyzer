# run.py
import sys
from PySide6.QtWidgets import QApplication
from src.main_app import MainApp

if __name__ == '__main__':
    """
    Application entry point.
    Always run this script from the project root directory.
    Example: python3 run.py
    """
    app = QApplication(sys.argv)
    window = MainApp()
    window.show()
    sys.exit(app.exec())
