import unittest
import os
from unittest.mock import MagicMock, patch

# Absolute imports
from src.visualization.data_handler import DataHandler
from src.visualization.vista_widget import VistaWidget
from src.config import config_visualization as config

# Need QApplication for VistaWidget
from PySide6.QtWidgets import QApplication, QWidget

# Helper class to satisfy type checks for QBoxLayout.addWidget if needed
# (VistaWidget adds plotter.interactor to layout)
class MockQWidget(QWidget):
    pass

app = QApplication.instance() or QApplication([])

class TestVisualizationOffscreenRunner(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Generate test data if missing
        if not os.path.exists(config.TEST_CSV_PATH):
            from src.visualization import make_testdata
            make_testdata.main()

    def setUp(self):
        self.data_handler = DataHandler()
        self.data_handler.load_analysis_result(config.TEST_CSV_PATH)

    @patch('src.visualization.vista_widget.QtInteractor')
    def test_update_view_logic(self, MockQtInteractor):
        """
        Test the update_view logic without rendering (Offscreen/Mock).
        """
        # Mock the plotter
        mock_plotter = MagicMock()
        mock_plotter.interactor = MockQWidget() # Satisfy layout.addWidget
        MockQtInteractor.return_value = mock_plotter

        # Mock add_mesh to return a mock actor
        mock_actor = MagicMock()
        mock_plotter.add_mesh.return_value = mock_actor
        mock_plotter.add_point_labels.return_value = mock_actor

        # Create widget
        widget = VistaWidget(self.data_handler, testing_mode=False)

        # Call update_view
        widget.update_view(0)

        # Verify that add_mesh was called (meaning data was processed)
        self.assertTrue(mock_plotter.add_mesh.called)

        # Verify box actor is stored
        self.assertIsNotNone(widget.actors[config.SK_ACTOR_BOX])

if __name__ == '__main__':
    unittest.main()
