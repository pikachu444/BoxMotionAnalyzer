import sys
from PySide6.QtWidgets import QApplication
from unittest.mock import MagicMock, patch
from src.launcher import LauncherWindow

def test_launcher_reset():
    app = QApplication.instance() or QApplication(sys.argv)

    with patch('src.launcher.MainWindow') as MockVizWindow:
        launcher = LauncherWindow()

        # 1. First Launch
        print("Clicking Visualization Button (1st time)...")
        launcher.open_visualization()

        # Capture the first instance
        first_instance = launcher.main_window
        print(f"First Instance: {first_instance}")

        # Verify instantiation
        MockVizWindow.assert_called()
        call_count_1 = MockVizWindow.call_count
        print(f"Call count: {call_count_1}")

        # 2. Second Launch
        print("Clicking Visualization Button (2nd time)...")
        launcher.open_visualization()

        # Capture the second instance
        second_instance = launcher.main_window
        print(f"Second Instance: {second_instance}")

        # Verify re-instantiation
        call_count_2 = MockVizWindow.call_count
        print(f"Call count: {call_count_2}")

        if call_count_2 > call_count_1:
            print("SUCCESS: New instance created.")
        else:
            print("FAILURE: Instance reused.")

        if first_instance is not second_instance:
            print("SUCCESS: Objects are different.")
        else:
            print("FAILURE: Objects are identical.")

if __name__ == "__main__":
    test_launcher_reset()
