import sys
import os
import unittest
import pandas as pd
import matplotlib

# Use a non-interactive backend for testing
matplotlib.use('Agg')

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from matplotlib.figure import Figure
from matplotlib.backends.backend_agg import FigureCanvasAgg as FigureCanvas

from src.plot_manager import PlotManager

class TestPlotTitle(unittest.TestCase):

    def setUp(self):
        """Set up a PlotManager and a dummy DataFrame."""
        self.fig = Figure()
        self.canvas = FigureCanvas(self.fig)
        self.plot_manager = PlotManager(self.canvas, self.fig)

        # Create a sample multi-header DataFrame
        columns = [
            ('Position', 'RigidBody', 'PX'),
            ('Velocity', 'CoM', 'VX')
        ]
        data = {
            ('Position', 'RigidBody', 'PX'): [10, 11],
            ('Velocity', 'CoM', 'VX'): [20, 21]
        }
        time_index = pd.Index([0.1, 0.2], name='Time')
        multi_index_cols = pd.MultiIndex.from_tuples(columns)
        self.test_df = pd.DataFrame(data, columns=multi_index_cols, index=time_index)

    def test_plot_title_with_tuples(self):
        """
        Tests that the draw_plot method correctly formats the title when given tuple column names.
        """
        print("\n--- Testing plot title generation with multi-header columns ---")

        columns_to_test = [('Position', 'RigidBody', 'PX'), ('Velocity', 'CoM', 'VX')]

        # Call the method to be tested
        self.plot_manager.draw_plot(self.test_df, columns_to_test)

        # Verification
        actual_title = self.plot_manager.ax.get_title()
        expected_title = "Plot for: Position.RigidBody.PX, Velocity.CoM.VX"

        self.assertEqual(actual_title, expected_title, "The plot title is not formatted correctly for tuple columns.")
        print("[PASS] Plot title is correctly formatted.")

if __name__ == "__main__":
    unittest.main()
