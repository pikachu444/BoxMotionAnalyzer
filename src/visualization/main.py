import sys
from PySide6.QtWidgets import QApplication
from launcher_window import LauncherWindow

def main():
    """Main function to run the application."""
    app = QApplication(sys.argv)
    window = LauncherWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == '__main__':
    main()
