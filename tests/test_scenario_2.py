import sys
import os
import pytest
from PySide6.QtWidgets import QApplication

# Ensure correct path
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from src.launcher import LauncherWindow
from src.visualization.main_window import MainWindow

def test_new_visualization_window_action():
    # Setup QApplication if it doesn't exist
    app = QApplication.instance()
    if not app:
        app = QApplication(sys.argv)

    # Assert initial state
    assert len(MainWindow.open_windows) == 0, "There should be no instances initially"

    # 1. Create first window
    window1 = MainWindow.create_and_show()

    # Assert one window is open
    assert len(MainWindow.open_windows) == 1, "One window should be created"

    # 2. Trigger "File -> New Visualization Window" action programmatically
    # Simulating what the GUI does
    window1.open_new_visualization_window()

    # Assert two windows are open
    assert len(MainWindow.open_windows) == 2, "Second window should be created from File menu action"

    # 3. Trigger "File -> New Visualization Window" from the second window
    window2 = MainWindow.open_windows[1]
    window2.open_new_visualization_window()

    # Assert three windows are open
    assert len(MainWindow.open_windows) == 3, "Third window should be created from File menu action"

    # 5. Clean up
    for instance in list(MainWindow.open_windows):
        instance.close()
    MainWindow.open_windows.clear()

if __name__ == "__main__":
    test_new_visualization_window_action()
    print("PASS: File > New Visualization Window test passed successfully.")
