import sys
import os
import pytest
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt

# Ensure correct path
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from src.launcher import LauncherWindow
from src.visualization.main_window import MainWindow

def test_launcher_multi_window():
    # Setup QApplication if it doesn't exist
    app = QApplication.instance()
    if not app:
        app = QApplication(sys.argv)

    # 1. Initialize launcher
    launcher = LauncherWindow()

    # Assert initial state
    assert len(MainWindow.open_windows) == 0, "There should be no instances initially"

    # 2. Click 3D Visualization button first time
    launcher.btn_visualization.click()

    # Assert one window is open
    assert len(MainWindow.open_windows) == 1, "One window should be created"

    # 3. Click 3D Visualization button second time
    launcher.btn_visualization.click()

    # Assert two windows are open
    assert len(MainWindow.open_windows) == 2, "Two windows should be created"

    # 4. Click 3D Visualization button third time
    launcher.btn_visualization.click()

    # Assert three windows are open
    assert len(MainWindow.open_windows) == 3, "Three windows should be created"

    # 5. Clean up
    for instance in list(MainWindow.open_windows):
        instance.close()
    MainWindow.open_windows.clear()

if __name__ == "__main__":
    test_launcher_multi_window()
    print("PASS: Launcher multi-window test passed successfully.")
