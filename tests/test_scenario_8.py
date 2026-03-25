import sys
import os
import pytest
import weakref
from PySide6.QtWidgets import QApplication

# Ensure correct path
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from src.visualization.main_window import MainWindow

def test_window_cleanup():
    app = QApplication.instance()
    if not app:
        app = QApplication(sys.argv)

    assert len(MainWindow.open_windows) == 0

    # 1. Create a few windows
    w1 = MainWindow.create_and_show()
    w2 = MainWindow.create_and_show()
    w3 = MainWindow.create_and_show()

    assert len(MainWindow.open_windows) == 3

    # 2. Close windows one by one
    w1.close()
    app.processEvents()
    assert len(MainWindow.open_windows) == 2, "Window list should be 2 after closing w1"

    w2.close()
    app.processEvents()
    assert len(MainWindow.open_windows) == 1, "Window list should be 1 after closing w2"

    w3.close()
    app.processEvents()
    assert len(MainWindow.open_windows) == 0, "Window list should be empty after closing all"

    # Verify plotting widgets and data structures are properly freed by
    # ensuring no memory leak crashes the system when opening and closing
    # numerous instances
    for _ in range(10):
        w = MainWindow.create_and_show()
        w.close()
        app.processEvents()

    assert len(MainWindow.open_windows) == 0, "No leaked open windows"

if __name__ == "__main__":
    test_window_cleanup()
    print("PASS: Window close cleanup stability test passed successfully.")
