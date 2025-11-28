import unittest
from unittest.mock import MagicMock, patch
from PySide6.QtWidgets import QApplication

# Adjust imports to be absolute from project root
from src.visualization.launcher_window import LauncherWindow
from src.config import config_visualization as config

# Ensure QApplication exists
app = QApplication.instance() or QApplication([])

class TestVisualizationLauncher(unittest.TestCase):
    def test_launcher_init(self):
        """
        Verify that the launcher window initializes without errors.
        """
        launcher = LauncherWindow()
        self.assertIsNotNone(launcher)
        self.assertEqual(launcher.windowTitle(), config.LAUNCHER_TITLE)

    @patch('src.visualization.launcher_window.MainApp')
    def test_launch_data_processing(self, MockMainApp):
        """
        Verify that clicking the Data Processing button instantiates and shows MainApp.
        """
        # Setup mock
        mock_app_instance = MockMainApp.return_value

        launcher = LauncherWindow()

        # Determine which button is which by text or connection
        # But we can call the slot method directly for reliable testing
        launcher.open_data_processing()

        # Verify
        MockMainApp.assert_called_once()
        mock_app_instance.show.assert_called_once()

    @patch('src.visualization.launcher_window.MainWindow')
    def test_launch_visualization(self, MockMainWindow):
        """
        Verify that clicking the Visualization button instantiates and shows MainWindow.
        """
        # Setup mock
        mock_window_instance = MockMainWindow.return_value

        launcher = LauncherWindow()

        # Call the slot
        launcher.open_visualization()

        # Verify
        MockMainWindow.assert_called_once()
        mock_window_instance.show.assert_called_once()

if __name__ == '__main__':
    unittest.main()
