import unittest
from unittest.mock import patch, MagicMock
from PySide6.QtWidgets import QApplication, QWidget

# Absolute imports
from src.visualization.main_window import MainWindow

app = QApplication.instance() or QApplication([])

class MockQWidget(QWidget):
    """Helper to satisfy layout.addWidget type checks and basic method calls"""
    def __init__(self, *args, **kwargs):
        parent = kwargs.get('parent', None)
        super().__init__(parent)

        # Add methods expected by MainWindow
        self.set_actor_visibility = MagicMock()
        self.update_view = MagicMock()
        # MainWindow also accesses plotter via keyPressEvent, but that might not be triggered in smoke test
        self.plotter = MagicMock()

class TestVisualizationSmoke(unittest.TestCase):
    @patch('src.visualization.main_window.VistaWidget', side_effect=MockQWidget) # Mock 3D widget
    def test_app_startup(self, MockVistaWidget):
        """
        Smoke test to verify that the MainWindow can be instantiated
        without crashing (dependencies import correctly).
        """
        # Note: MockVistaWidget is instantiated by MainWindow

        window = MainWindow()
        self.assertIsNotNone(window)
        self.assertEqual(window.windowTitle(), "3D Motion Analyzer")

        # Cleanup
        window.close()

if __name__ == '__main__':
    unittest.main()
