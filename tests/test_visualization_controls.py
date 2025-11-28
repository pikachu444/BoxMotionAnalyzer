import unittest
from unittest.mock import MagicMock, patch
import os

from PySide6.QtWidgets import QApplication, QWidget
from src.config import config_visualization as config
from src.visualization.data_handler import DataHandler
from src.visualization.vista_widget import VistaWidget
from src.visualization.main_window import MainWindow

# Helper class to satisfy type checks for QBoxLayout.addWidget
class MockQWidget(QWidget):
    # Accept arguments that VistaWidget accepts, but filter them for QWidget
    def __init__(self, data_handler=None, parent=None, **kwargs):
        super().__init__(parent) # Only pass parent to QWidget
        # Add mock methods if needed
        self.update_view = MagicMock()
        self.set_actor_visibility = MagicMock()
        self.plotter = MagicMock() # For property access

class TestControlLogic(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Ensure test data exists
        if not os.path.exists(config.TEST_CSV_PATH):
            from src.visualization import make_testdata
            make_testdata.main()

        # PySide6 application instance
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        # Setup DataHandler with real data
        self.data_handler = DataHandler()
        self.data_handler.load_analysis_result(config.TEST_CSV_PATH)

    @patch('src.visualization.vista_widget.QtInteractor')
    def test_visibility_control(self, MockQtInteractor):
        """
        Verify that set_actor_visibility correctly toggles the visibility
        of PyVista actors.
        """
        # --- Prepare Mocks ---
        # The plotter must have an .interactor attribute that is a QWidget
        mock_plotter = MagicMock()
        mock_plotter.interactor = MockQWidget()
        MockQtInteractor.return_value = mock_plotter

        # The plotter.add_mesh returns an actor (which we mock)
        # We need this actor to test SetVisibility calls
        mock_actor = MagicMock()
        mock_plotter.add_mesh.return_value = mock_actor
        mock_plotter.add_point_labels.return_value = mock_actor

        # --- Instantiate Widget ---
        # This calls layout.addWidget(self.plotter.interactor), which now works
        vista_widget = VistaWidget(self.data_handler, testing_mode=False)

        # --- Trigger Actor Creation ---
        # update_view calls add_mesh, populating vista_widget.actors
        vista_widget.update_view(0)

        self.assertIsNotNone(vista_widget.actors[config.SK_ACTOR_BOX], "Box actor should be created.")

        # --- Test Visibility Logic ---
        # 1. Hide Box
        vista_widget.set_actor_visibility("box", False)
        # Verify the mock actor received the call
        box_actor = vista_widget.actors[config.SK_ACTOR_BOX]
        box_actor.SetVisibility.assert_called_with(False)

        # 2. Show Box
        vista_widget.set_actor_visibility("box", True)
        box_actor.SetVisibility.assert_called_with(True)

        print("\n✓ Visibility control (Box) logic verified.")

    def test_animation_control(self):
        """
        Verify that playing/pausing updates the timer and frame changes trigger view updates.
        """
        # Use patch to replace VistaWidget with our MockQWidget
        # This ensures MainWindow can instantiate and add it to layout
        with patch('src.visualization.main_window.VistaWidget', side_effect=MockQWidget) as MockVistaClass:

            window = MainWindow()

            # Access the mock instance that MainWindow created
            mock_vista_instance = window.vista_widget

            # Manually load data to enable controls (populate n_frames)
            window.data_handler = self.data_handler
            window.animation_widget.set_frame_range(self.data_handler.n_frames)

            # --- Test 1: Play/Pause Logic ---
            # Initial state
            self.assertFalse(window.animation_timer.isActive(), "Timer should be stopped initially.")

            # Play
            window.toggle_animation(True)
            self.assertTrue(window.animation_timer.isActive(), "Timer should be active after Play.")

            # Pause
            window.toggle_animation(False)
            self.assertFalse(window.animation_timer.isActive(), "Timer should be stopped after Pause.")

            print("✓ Animation Play/Pause logic verified.")

            # --- Test 2: Frame Change Logic ---
            target_frame = 5
            window.set_frame(target_frame)

            # Check internal state
            self.assertEqual(window.current_frame, target_frame)

            # Check if update_view was called on our mock widget
            mock_vista_instance.update_view.assert_called_with(target_frame)

            print("✓ Frame change logic verified.")

if __name__ == '__main__':
    unittest.main()
