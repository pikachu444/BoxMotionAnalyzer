import sys
import os
import pytest
from PySide6.QtWidgets import QApplication

# Ensure correct path
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from src.visualization.main_window import MainWindow

def test_projections():
    app = QApplication.instance()
    if not app:
        app = QApplication(sys.argv)

    assert len(MainWindow.open_windows) == 0

    # 1. Create window
    window = MainWindow.create_and_show()
    data_path = os.path.join(project_root, 'data', 'test_real_data_result.csv')
    success = window.data_handler.load_analysis_result(data_path)
    assert success, "Failed to load data"

    # 2. Check initial projection (should be Perspective by default)
    assert not window.vista_widget.plotter.camera.GetParallelProjection(), "Should default to perspective projection"
    assert window.perspective_projection_action.isChecked(), "Perspective action should be checked"
    assert not window.parallel_projection_action.isChecked(), "Parallel action should be unchecked"

    # 3. Trigger Parallel Projection (Alt+6) via the method connected to the action
    window.enable_parallel_projection()
    app.processEvents()

    # Verify state changes to Parallel
    assert window.vista_widget.plotter.camera.GetParallelProjection(), "Camera should be parallel"
    assert not window.perspective_projection_action.isChecked(), "Perspective action should be unchecked"
    assert window.parallel_projection_action.isChecked(), "Parallel action should be checked"

    # 4. Trigger Perspective Projection (Alt+5) via the method connected to the action
    window.enable_perspective_projection()
    app.processEvents()

    # Verify state changes back to Perspective
    assert not window.vista_widget.plotter.camera.GetParallelProjection(), "Camera should be perspective"
    assert window.perspective_projection_action.isChecked(), "Perspective action should be checked"
    assert not window.parallel_projection_action.isChecked(), "Parallel action should be unchecked"

    # 5. Clean up
    for instance in list(MainWindow.open_windows):
        instance.close()
    MainWindow.open_windows.clear()

if __name__ == "__main__":
    test_projections()
    print("PASS: Projections (Alt+5/Alt+6) test passed successfully.")
