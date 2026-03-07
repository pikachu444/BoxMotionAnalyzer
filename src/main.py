import sys
import os

# Ensure project root is in sys.path BEFORE importing any project modules.
# We need to add the PARENT directory of this script (project root) to sys.path
# so that 'import src.launcher' works correctly.
current_dir = os.path.dirname(os.path.abspath(__file__)) # src/
project_root = os.path.dirname(current_dir)              # root/

if project_root not in sys.path:
    sys.path.insert(0, project_root)

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QIcon
from src.config import config_visualization as config
from src.launcher import LauncherWindow

def main():
    """
    Main entry point for Box Motion Analyzer.
    Launches the unified launcher window.
    """
    app = QApplication(sys.argv)
    app.setWindowIcon(QIcon(config.APP_ICON_PATH))
    window = LauncherWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == '__main__':
    main()
