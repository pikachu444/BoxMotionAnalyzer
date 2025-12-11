import sys
import os
import unittest
from unittest.mock import patch, MagicMock

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

class TestHeadlessLaunch(unittest.TestCase):
    @patch('src.main.LauncherWindow')
    @patch('src.main.QApplication')
    def test_main_function(self, MockQApp, MockLauncher):
        """
        Verifies that src.main.main() initializes QApplication and shows LauncherWindow
        using mocks to avoid actual GUI creation and Segfaults.
        """
        print("\n[Test] Verifying src/main.py logic via Mocks...")

        # Delayed import to ensure patches are active if import triggers anything (it shouldn't)
        from src.main import main

        # Setup mocks
        mock_app_instance = MagicMock()
        MockQApp.return_value = mock_app_instance

        mock_window_instance = MagicMock()
        MockLauncher.return_value = mock_window_instance

        # Run main()
        # It calls sys.exit(app.exec()), so we expect SystemExit
        with self.assertRaises(SystemExit):
            main()

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

if __name__ == '__main__':
    unittest.main()
