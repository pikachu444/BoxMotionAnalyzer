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
from src.visualization.control_panel import ControlPanel

def test_independence_and_box_edges():
    app = QApplication.instance()
    if not app:
        app = QApplication(sys.argv)

    assert len(MainWindow.open_windows) == 0

    # 1. Create first window and load data
    window1 = MainWindow.create_and_show()
    data_path = os.path.join(project_root, 'data', 'test_real_data_result.csv')
    success = window1.data_handler.load_analysis_result(data_path)
    assert success, "Failed to load data in Window 1"

    from src.config import config_visualization as config
    # Verify loaded state
    assert window1.data_handler.n_frames > 0
    assert window1.vista_widget.actors is not None

    window1.set_frame(0)

    # Change some state in Window 1 (Toggle off Box Edges)
    window1.control_panel.box_edges_checkbox.setChecked(False)
    # Give UI a moment to process the signal
    app.processEvents()

    # Verify Box Edges are disabled in Window 1
    assert not window1.vista_widget.actors[config.SK_ACTOR_BOX_EDGES].GetVisibility(), "Box edges should be disabled in Window 1"

    # 2. Create second window
    window2 = MainWindow.create_and_show()

    # Assert second window has no data loaded initially
    assert window2.data_handler.n_frames == 0, "Window 2 should start empty"
    assert window2.loaded_result_path is None, "Window 2 should have no file path"

    # Load data in second window
    success2 = window2.data_handler.load_analysis_result(data_path)
    assert success2, "Failed to load data in Window 2"

    # Verify Box Edges state is INDEPENDENT (should be default True in Window 2)
    assert window2.control_panel.box_edges_checkbox.isChecked(), "Box edges should be enabled by default in Window 2"
    # Note: Window 2's actors are initialized on first data load or frame set.
    window2.set_frame(0)
    assert window2.vista_widget.actors[config.SK_ACTOR_BOX_EDGES].GetVisibility(), "Box edges should be enabled in Window 2's actor manager"

    # Verify Window 1 is STILL disabled
    assert not window1.vista_widget.actors[config.SK_ACTOR_BOX_EDGES].GetVisibility(), "Window 1 state should remain unchanged"

    # 3. Clean up
    for instance in list(MainWindow.open_windows):
        instance.close()
    MainWindow.open_windows.clear()

if __name__ == "__main__":
    test_independence_and_box_edges()
    print("PASS: Multi-window independence and Box Edges test passed successfully.")
