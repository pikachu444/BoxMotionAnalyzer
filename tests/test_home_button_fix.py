import unittest
import pandas as pd
import os
import sys
from PySide6.QtWidgets import QApplication
from src.main_app import MainApp

class TestHomeButtonFix(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        """Set up the QApplication instance once for all tests."""
        cls.app = QApplication.instance()
        if not cls.app:
            cls.app = QApplication(sys.argv)

    def setUp(self):
        """Set up the MainApp instance for testing."""
        self.window = MainApp()

    def test_clear_plot_preserves_axis_limits(self):
        """
        Test that the new clear_plot method removes data lines but
        preserves the current axis limits (zoom/pan state).
        """
        # 1. Create dummy data and plot it
        plot_manager = self.window.plot_manager2
        data = {'Value1': [10, 20, 30, 40, 50]}
        df = pd.DataFrame(data, index=[1, 2, 3, 4, 5])

        plot_manager.draw_plot(df, ['Value1'])

        # 2. Simulate a user zooming in by setting the axis limits manually
        zoomed_xlim = (1.5, 3.5)
        zoomed_ylim = (15, 35)
        plot_manager.ax.set_xlim(zoomed_xlim)
        plot_manager.ax.set_ylim(zoomed_ylim)

        # Store the zoomed limits before clearing
        xlim_before = plot_manager.ax.get_xlim()
        ylim_before = plot_manager.ax.get_ylim()
        self.assertEqual(xlim_before, zoomed_xlim)
        self.assertEqual(ylim_before, zoomed_ylim)

        # 3. Call the new clear_plot method
        plot_manager.clear_plot()

        # 4. Assert that the data lines are gone
        self.assertEqual(len(plot_manager.ax.lines), 0, "Data lines should be cleared.")

        # 5. Assert that the axis limits are preserved
        xlim_after = plot_manager.ax.get_xlim()
        ylim_after = plot_manager.ax.get_ylim()

        self.assertEqual(xlim_after, xlim_before, "X-axis limits should be preserved after clearing.")
        self.assertEqual(ylim_after, ylim_before, "Y-axis limits should be preserved after clearing.")

if __name__ == '__main__':
    unittest.main()
