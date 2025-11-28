import sys
import os
from PySide6.QtWidgets import QApplication
from src.launcher import LauncherWindow

def main():
    """
    Main entry point for Box Motion Analyzer.
    Launches the unified launcher window.
    """
    # Ensure project root is in sys.path
    project_root = os.path.dirname(os.path.abspath(__file__))
    if project_root not in sys.path:
        sys.path.append(project_root)

    app = QApplication(sys.argv)
    window = LauncherWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == '__main__':
    main()
