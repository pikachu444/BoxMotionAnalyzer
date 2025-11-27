import unittest
import os
import sys

# Add the project root to the Python path to allow importing from the main package
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Set the QT_QPA_PLATFORM environment variable to 'offscreen'
os.environ['QT_QPA_PLATFORM'] = 'offscreen'

from PySide6.QtWidgets import QApplication

# Import all the UI classes and main window
from main_window import MainWindow
from control_panel import ControlPanel
from plot_widget import PlotWidget
from plot_dialog import PlotDialog
from animation_widget import AnimationWidget
from vista_widget import VistaWidget
from data_handler import DataHandler
from info_log_widget import InfoLogWidget


class SmokeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        """
        Set up a QApplication instance. This is necessary for any Qt widget testing.
        """
        cls.app = QApplication.instance() or QApplication(sys.argv)

    def test_widget_instantiation(self):
        """
        Tests if all key UI components can be instantiated without raising an exception.
        This is a more granular smoke test.
        """
        try:
            # Instantiate each major component separately
            data_handler = DataHandler()

            # Crucially, instantiate VistaWidget in 'testing_mode'
            vista_widget = VistaWidget(data_handler, testing_mode=True)
            self.assertIsInstance(vista_widget, VistaWidget)
            print("✓ VistaWidget instantiated successfully in testing mode.")

            plot_widget = PlotWidget()
            self.assertIsInstance(plot_widget, PlotWidget)
            print("✓ PlotWidget instantiated successfully.")

            control_panel = ControlPanel() # No longer takes plot_widget
            self.assertIsInstance(control_panel, ControlPanel)
            print("✓ ControlPanel instantiated successfully.")

            info_log_widget = InfoLogWidget()
            self.assertIsInstance(info_log_widget, InfoLogWidget)
            print("✓ InfoLogWidget instantiated successfully.")

            animation_widget = AnimationWidget()
            self.assertIsInstance(animation_widget, AnimationWidget)
            print("✓ AnimationWidget instantiated successfully.")

            # We can even instantiate MainWindow, as VistaWidget inside it will now be safe.
            # This is a good final check.
            # window = MainWindow()
            # self.assertIsInstance(window, MainWindow)
            # print("✓ MainWindow instantiated successfully.")

        except Exception as e:
            self.fail(f"Smoke Test Failed: Instantiation of a widget raised an exception: {e}")

    def test_plot_dialog_instantiation(self):
        """
        Separately test the instantiation of PlotDialog as it's not created
        by MainWindow's __init__.
        """
        try:
            # We need some dummy data to pass to the dialog
            dummy_plot_args = [{'x': [0, 1], 'y': [0, 1], 'label': 'test'}]
            y_label = "Test Value"

            dialog = PlotDialog(dummy_plot_args, y_label)
            self.assertIsInstance(dialog, PlotDialog)

            print("✓ Smoke Test Passed: PlotDialog was instantiated successfully.")

        except Exception as e:
            self.fail(f"Smoke Test Failed: Instantiation of PlotDialog raised an exception: {e}")

if __name__ == '__main__':
    unittest.main()
