import sys
import os
from unittest.mock import patch
from PySide6.QtWidgets import QApplication
from main_app import MainApp

def get_project_root():
    """Returns the project root directory based on the script's location."""
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

@patch('PySide6.QtWidgets.QFileDialog.getOpenFileName')
def run_test(mock_get_open_file_name):
    """
    Tests the core functionalities by mocking QFileDialog.
    Note: This test can't fully verify asynchronous GUI updates,
    but it checks the main logic path.
    """
    app = QApplication.instance() or QApplication(sys.argv)
    window = MainApp()

    project_root = get_project_root()
    test_csv_path = os.path.join(project_root, "TestSets", "VDTest_S5_001.csv")

    mock_get_open_file_name.return_value = (test_csv_path, "CSV Files (*.csv)")

    print(f"--- STARTING TEST: Simulating 'Load CSV' button click ---")

    # Simulate a click
    window.load_csv_button.click()

    # Allow the event loop to process some events
    QApplication.processEvents()

    print("\n--- VERIFYING TEST RESULTS ---")

    # 1. Verify file path label
    print(f"File path label: {window.file_path_label.text()}")
    assert window.file_path_label.text() == test_csv_path, "File path label was not updated."

    # 2. Verify list widget population
    items = [window.list_plot_data.item(i).text() for i in range(window.list_plot_data.count())]
    print(f"Number of plottable targets: {len(items)}")
    assert len(items) > 0, "Plottable targets list is empty."

    # 3. Verify graph plot items
    lines = window.plot_manager.ax.get_lines()
    print(f"Number of lines in plot: {len(lines)}")
    assert len(lines) > 0, "Graph was not drawn."

    print("\n[SUCCESS] Core functionalities seem to be working.")


if __name__ == "__main__":
    try:
        run_test()
    except Exception as e:
        print(f"\n[FAILURE] An exception occurred during testing: {e}")
        import traceback
        traceback.print_exc()
