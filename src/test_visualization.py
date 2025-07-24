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
    Tests the full data loading and initial UI setup by mocking QFileDialog
    and calling the handler method directly.
    """
    app = QApplication.instance() or QApplication(sys.argv)
    window = MainApp()

    project_root = get_project_root()
    test_csv_path = os.path.join(project_root, "TestSets", "VDTest_S5_001.csv")

    mock_get_open_file_name.return_value = (test_csv_path, "CSV Files (*.csv)")

    print(f"--- STARTING TEST: Calling open_csv_file method directly ---")

    # Call the handler method directly to ensure synchronous execution
    window.open_csv_file()

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

    # 4. Verify slice range initialization
    start_val = window.le_slice_start.text()
    end_val = window.le_slice_end.text()
    print(f"Slice range: Start={start_val}, End={end_val}")
    assert float(start_val) > 0, "Slice start time is not valid."
    assert float(end_val) > float(start_val), "Slice end time is not valid."

    print("\n[SUCCESS] All checks passed. Application is working as expected.")


if __name__ == "__main__":
    try:
        run_test()
    except Exception as e:
        print(f"\n[FAILURE] An exception occurred during testing: {e}")
        import traceback
        traceback.print_exc()
