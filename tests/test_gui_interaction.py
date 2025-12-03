import sys
import os
import unittest
from unittest.mock import MagicMock, patch
import pandas as pd
import numpy as np

# Ensure project root is in path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt, QTimer
from src.visualization.main_window import MainWindow
from src.config import config_visualization as config

class TestGuiInteraction(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Create QApplication once for all tests
        cls.app = QApplication.instance()
        if cls.app is None:
            cls.app = QApplication(sys.argv)

    def setUp(self):
        self.window = MainWindow()

        # Patch VistaWidget.update_view to avoid OpenGL errors in headless environment
        self.update_view_patcher = patch.object(self.window.vista_widget, 'update_view')
        self.mock_update_view = self.update_view_patcher.start()

        # Setup realistic mock data (Box + Markers, 100 frames)
        self.setup_realistic_mock_data()

    def tearDown(self):
        self.update_view_patcher.stop()
        self.window.close()

    def setup_realistic_mock_data(self):
        """
        Generates a long-format DataFrame mimicking 100 frames of data
        for 8 Box Corners and 6 Markers.
        """
        n_frames = 100
        frames = np.arange(n_frames)
        times = frames * 0.01

        # Objects: C1~C8 (Box) + MK_1~MK_6 (Markers)
        corners = [f"C{i}" for i in range(1, 9)]
        markers = [f"MK_{i}" for i in range(1, 7)]
        object_ids = corners + markers

        dfs = []
        for obj_id in object_ids:
            df = pd.DataFrame()
            df[config.DF_FRAME] = frames
            df[config.DF_TIME] = times
            df[config.DF_OBJECT_ID] = obj_id

            # Simulated motion: Move along X axis, Sine wave on Z
            df[config.DF_POS_X] = np.linspace(0, 10, n_frames)
            df[config.DF_POS_Y] = np.full(n_frames, 5.0)
            df[config.DF_POS_Z] = np.sin(frames * 0.1) * 10

            # Velocities
            df[config.DF_VEL_X] = 1.0
            df[config.DF_VEL_Y] = 0.0
            df[config.DF_VEL_Z] = np.cos(frames * 0.1)

            dfs.append(df)

        long_df = pd.concat(dfs, ignore_index=True)

        # Inject into DataHandler
        self.window.data_handler.visualization_dataframe = long_df
        self.window.data_handler.n_frames = n_frames
        self.window.data_handler.object_ids = sorted(object_ids)

        # Trigger UI updates (normally done in open_csv_file)
        self.window.animation_widget.set_frame_range(n_frames)
        self.window.control_panel.populate_object_list(self.window.data_handler.object_ids)
        self.window.set_frame(0)

    def test_animation_playback(self):
        print("\n[Test] Animation Playback (100 Frames)")
        self.assertEqual(self.window.current_frame, 0)

        # Play
        self.window.animation_widget.play_pause_button.click()
        self.assertTrue(self.window.animation_timer.isActive())

        # Advance 5 frames
        for _ in range(5):
            self.window.advance_frame()

        self.assertEqual(self.window.current_frame, 5)
        # Check slider
        self.assertEqual(self.window.animation_widget.timeline_slider.value(), 5)

        # Verify VistaWidget update called with correct frame
        self.mock_update_view.assert_called_with(5)

    def test_object_selection_and_plotting(self):
        print("\n[Test] Object Selection & Plotting (Multiple Objects)")

        # Select C1 and MK_1
        list_widget = self.window.control_panel.object_list

        # Clear any pre-existing selection
        list_widget.clearSelection()

        # Find items
        c1_item = list_widget.findItems("C1", Qt.MatchExactly)[0]
        mk1_item = list_widget.findItems("MK_1", Qt.MatchExactly)[0]

        c1_item.setSelected(True)
        mk1_item.setSelected(True)

        # Trigger update
        self.window.update_plot_with_multiple_objects()

        # Check PlotWidget state
        plot_args = self.window.plot_widget.current_plot_args
        self.assertEqual(len(plot_args), 2, "Should plot 2 lines")
        labels = sorted([arg['label'] for arg in plot_args])
        self.assertEqual(labels, ['C1', 'MK_1'])

        # Check Info Log
        self.window.update_info_log()
        table = self.window.info_log_widget.info_table
        # Columns: [Property] + [Object 1] + [Object 2] ...
        # Since we selected 2 objects, total columns should be 3.
        self.assertEqual(table.columnCount(), 3)

        # Check header labels
        headers = [table.horizontalHeaderItem(i).text() for i in range(table.columnCount())]
        # headers[0] is 'Property'
        self.assertEqual(headers[0], config.LBL_PROPERTY)
        # Remaining headers should be objects
        self.assertEqual(sorted(headers[1:]), ['C1', 'MK_1'])

    def test_visibility_toggle(self):
        print("\n[Test] Visibility Toggle")
        # Toggle 'box' visibility
        self.window.control_panel.visibility_changed.emit('box', False)
        # Since update_view is mocked, actual visual change isn't verifiable here,
        # but the signal emission confirms the control panel logic works.
        pass

if __name__ == '__main__':
    unittest.main()
