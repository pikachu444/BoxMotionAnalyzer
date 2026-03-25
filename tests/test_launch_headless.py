import sys
import os
import unittest
import importlib
from unittest.mock import patch, MagicMock

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

try:
    from PySide6.QtWidgets import QApplication
    from src.launcher import LauncherWindow
    HAS_QT = True
except ModuleNotFoundError:
    QApplication = None
    LauncherWindow = None
    HAS_QT = False

class TestHeadlessLaunch(unittest.TestCase):
    @unittest.skipUnless(HAS_QT, "PySide6 is required for main entrypoint tests.")
    def test_main_function(self):
        """
        Verifies that src.main.main() initializes QApplication and shows LauncherWindow
        using mocks to avoid actual GUI creation and Segfaults.
        """
        print("\n[Test] Verifying src/main.py logic via Mocks...")

        main_module = importlib.import_module("src.main")

        with patch.object(main_module, "QApplication") as MockQApp, patch.object(
            main_module, "LauncherWindow"
        ) as MockLauncher:
            mock_app_instance = MagicMock()
            MockQApp.return_value = mock_app_instance

            mock_window_instance = MagicMock()
            MockLauncher.return_value = mock_window_instance

            # Run main()
            # It calls sys.exit(app.exec()), so we expect SystemExit
            with self.assertRaises(SystemExit):
                main_module.main()

        print("[Pass] src.main.main() ran to completion (sys.exit).")

        # Verification
        # 1. QApplication should be instantiated
        MockQApp.assert_called()

        # 2. LauncherWindow should be instantiated
        MockLauncher.assert_called_once()

        # 3. window.show() should be called
        mock_window_instance.show.assert_called_once()

        # 4. app.exec() should be called
        mock_app_instance.exec.assert_called_once()
        print("[Pass] All main() steps verified: App created, Window shown, Exec called.")

    @classmethod
    def setUpClass(cls):
        if HAS_QT:
            cls.app = QApplication.instance() or QApplication([])

    @unittest.skipUnless(HAS_QT, "PySide6 is required for launcher window tests.")
    @patch('src.launcher.MainWindow.create_and_show')
    def test_launcher_can_open_multiple_visualization_windows(self, mock_create_and_show):
        first_window = MagicMock()
        second_window = MagicMock()
        mock_create_and_show.side_effect = [first_window, second_window]

        window = LauncherWindow()
        try:
            window.open_visualization()
            window.open_visualization()
        finally:
            window.close()

        self.assertEqual(mock_create_and_show.call_count, 2)
        first_window.close.assert_not_called()

if __name__ == '__main__':
    unittest.main()
