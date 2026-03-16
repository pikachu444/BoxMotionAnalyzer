import os
import sys
import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

# Ensure project root is in path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.config import config_visualization as config
from src.visualization.main_window import MainWindow


class TestGuiInteraction(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance()
        if cls.app is None:
            cls.app = QApplication(sys.argv)

    def setUp(self):
        self.window = MainWindow()

        self.update_view_patcher = patch.object(self.window.vista_widget, "update_view")
        self.mock_update_view = self.update_view_patcher.start()
        self.setup_realistic_mock_data()

    def tearDown(self):
        self.update_view_patcher.stop()
        self.window.close()

    def setup_realistic_mock_data(self):
        n_frames = 100
        frames = np.arange(n_frames)
        times = frames * 0.01

        grouped_entities = {
            config.ENTITY_TYPE_COM: [config.ENTITY_ID_COM],
            config.ENTITY_TYPE_CORNER: [f"C{i}" for i in range(1, 9)],
            config.ENTITY_TYPE_MARKER: ["F1", "B2", "MK_1", "LEFT_1", "T_Marker"],
        }

        dfs = []
        for entity_type, entity_ids in grouped_entities.items():
            for entity_id in entity_ids:
                df = pd.DataFrame()
                df[config.DF_FRAME] = frames
                df[config.DF_TIME] = times
                df[config.DF_ENTITY_ID] = entity_id
                df[config.DF_ENTITY_TYPE] = entity_type
                df[config.DF_SOURCE_OBJECT_ID] = entity_id

                df[config.DF_POS_X] = np.linspace(0, 10, n_frames)
                df[config.DF_POS_Y] = np.full(n_frames, 5.0)
                df[config.DF_POS_Z] = np.sin(frames * 0.1) * 10

                if entity_type == config.ENTITY_TYPE_MARKER:
                    df[config.DF_VEL_X] = np.nan
                    df[config.DF_VEL_Y] = np.nan
                    df[config.DF_VEL_Z] = np.nan
                    df[config.DF_VEL_GLOBAL_NORM] = np.nan
                    df[config.DF_VEL_BOX_LOCAL_X] = np.nan
                    df[config.DF_VEL_BOX_LOCAL_Y] = np.nan
                    df[config.DF_VEL_BOX_LOCAL_Z] = np.nan
                    df[config.DF_VEL_BOX_LOCAL_NORM] = np.nan
                    df[config.DF_ACC_GLOBAL_X] = np.nan
                    df[config.DF_ACC_GLOBAL_Y] = np.nan
                    df[config.DF_ACC_GLOBAL_Z] = np.nan
                    df[config.DF_ACC_GLOBAL_NORM] = np.nan
                    df[config.DF_ACC_BOX_LOCAL_X] = np.nan
                    df[config.DF_ACC_BOX_LOCAL_Y] = np.nan
                    df[config.DF_ACC_BOX_LOCAL_Z] = np.nan
                    df[config.DF_ACC_BOX_LOCAL_NORM] = np.nan
                else:
                    df[config.DF_VEL_X] = 1.0
                    df[config.DF_VEL_Y] = 0.0
                    df[config.DF_VEL_Z] = np.cos(frames * 0.1)
                    df[config.DF_VEL_GLOBAL_NORM] = np.sqrt(
                        df[config.DF_VEL_X] ** 2
                        + df[config.DF_VEL_Y] ** 2
                        + df[config.DF_VEL_Z] ** 2
                    )
                    df[config.DF_ACC_GLOBAL_X] = 0.3
                    df[config.DF_ACC_GLOBAL_Y] = 0.0
                    df[config.DF_ACC_GLOBAL_Z] = 0.1
                    df[config.DF_ACC_GLOBAL_NORM] = np.sqrt(
                        df[config.DF_ACC_GLOBAL_X] ** 2
                        + df[config.DF_ACC_GLOBAL_Y] ** 2
                        + df[config.DF_ACC_GLOBAL_Z] ** 2
                    )
                    if entity_type == config.ENTITY_TYPE_COM:
                        df[config.DF_VEL_BOX_LOCAL_X] = 0.5
                        df[config.DF_VEL_BOX_LOCAL_Y] = 0.25
                        df[config.DF_VEL_BOX_LOCAL_Z] = 0.0
                        df[config.DF_VEL_BOX_LOCAL_NORM] = np.sqrt(
                            df[config.DF_VEL_BOX_LOCAL_X] ** 2
                            + df[config.DF_VEL_BOX_LOCAL_Y] ** 2
                            + df[config.DF_VEL_BOX_LOCAL_Z] ** 2
                        )
                        df[config.DF_ACC_BOX_LOCAL_X] = 0.2
                        df[config.DF_ACC_BOX_LOCAL_Y] = 0.1
                        df[config.DF_ACC_BOX_LOCAL_Z] = 0.0
                        df[config.DF_ACC_BOX_LOCAL_NORM] = np.sqrt(
                            df[config.DF_ACC_BOX_LOCAL_X] ** 2
                            + df[config.DF_ACC_BOX_LOCAL_Y] ** 2
                            + df[config.DF_ACC_BOX_LOCAL_Z] ** 2
                        )
                    else:
                        df[config.DF_VEL_BOX_LOCAL_X] = np.nan
                        df[config.DF_VEL_BOX_LOCAL_Y] = np.nan
                        df[config.DF_VEL_BOX_LOCAL_Z] = np.nan
                        df[config.DF_VEL_BOX_LOCAL_NORM] = np.nan
                        df[config.DF_ACC_BOX_LOCAL_X] = np.nan
                        df[config.DF_ACC_BOX_LOCAL_Y] = np.nan
                        df[config.DF_ACC_BOX_LOCAL_Z] = np.nan
                        df[config.DF_ACC_BOX_LOCAL_NORM] = np.nan

                dfs.append(df)

        long_df = pd.concat(dfs, ignore_index=True)
        self.window.data_handler.visualization_dataframe = long_df
        self.window.data_handler.n_frames = n_frames
        self.window.data_handler.entity_groups = grouped_entities
        self.window.data_handler.entity_type_map = {
            entity_id: entity_type
            for entity_type, entity_ids in grouped_entities.items()
            for entity_id in entity_ids
        }
        self.window.data_handler.object_ids = self.window.data_handler.get_object_ids()

        self.window.animation_widget.set_frame_range(n_frames)
        self.window.control_panel.populate_scene_inspector(grouped_entities)
        self.window.set_frame(0)

    def _find_tree_item(self, label: str):
        items = self.window.control_panel.object_tree.findItems(
            label,
            Qt.MatchFlag.MatchExactly | Qt.MatchFlag.MatchRecursive,
            0,
        )
        self.assertTrue(items, f"Tree item not found: {label}")
        return items[0]

    def test_animation_playback(self):
        self.assertEqual(self.window.current_frame, 0)
        self.window.animation_widget.play_pause_button.click()
        self.assertTrue(self.window.animation_timer.isActive())

        for _ in range(5):
            self.window.advance_frame()

        self.assertEqual(self.window.current_frame, 5)
        self.assertEqual(self.window.animation_widget.timeline_slider.value(), 5)
        self.mock_update_view.assert_called_with(5)

    def test_same_type_multi_selection_updates_plot_and_frame_inspector(self):
        tree = self.window.control_panel.object_tree
        c1_item = self._find_tree_item("C1")
        c2_item = self._find_tree_item("C2")

        tree.clearSelection()
        tree.setCurrentItem(c1_item)
        c1_item.setSelected(True)
        tree.setCurrentItem(c2_item)
        c2_item.setSelected(True)
        self.app.processEvents()

        self.window.update_plot_with_multiple_objects()
        plot_args = self.window.plot_widget.current_plot_args
        self.assertEqual(len(plot_args), 2)
        self.assertEqual(sorted(arg["label"] for arg in plot_args), ["C1", "C2"])

        self.window.update_info_log()
        table = self.window.info_log_widget.info_table
        self.assertEqual(table.columnCount(), 3)
        headers = [table.horizontalHeaderItem(i).text() for i in range(table.columnCount())]
        self.assertEqual(headers[0], config.LBL_PROPERTY)
        self.assertEqual(sorted(headers[1:]), ["C1", "C2"])

    def test_marker_selection_filters_metric_options(self):
        tree = self.window.control_panel.object_tree
        marker_item = self._find_tree_item("F1")

        tree.clearSelection()
        tree.setCurrentItem(marker_item)
        marker_item.setSelected(True)
        self.app.processEvents()

        combo_labels = [
            self.window.control_panel.plot_data_combobox.itemText(i)
            for i in range(self.window.control_panel.plot_data_combobox.count())
        ]
        self.assertEqual(
            combo_labels,
            [
                "Position X (Global Frame)",
                "Position Y (Global Frame)",
                "Position Z (Global Frame)",
            ],
        )

    def test_com_selection_shows_norm_and_acceleration_metrics_and_help(self):
        tree = self.window.control_panel.object_tree
        com_item = self._find_tree_item(config.ENTITY_ID_COM)

        tree.clearSelection()
        tree.setCurrentItem(com_item)
        com_item.setSelected(True)
        self.app.processEvents()

        combo_labels = [
            self.window.control_panel.plot_data_combobox.itemText(i)
            for i in range(self.window.control_panel.plot_data_combobox.count())
        ]
        self.assertIn("Velocity Norm (Global Frame)", combo_labels)
        self.assertIn("Acceleration X (Global Frame)", combo_labels)
        self.assertIn("Acceleration Norm (Box Local Frame)", combo_labels)
        self.assertIn("Box Local Frame", self.window.control_panel.inspector_help_label.text())

    def test_mixed_type_selection_is_restricted_to_one_entity_type(self):
        tree = self.window.control_panel.object_tree
        corner_item = self._find_tree_item("C1")
        marker_item = self._find_tree_item("F1")

        tree.clearSelection()
        tree.setCurrentItem(corner_item)
        corner_item.setSelected(True)
        tree.setCurrentItem(marker_item)
        marker_item.setSelected(True)
        self.app.processEvents()

        self.assertEqual(self.window.control_panel.get_selected_entity_ids(), ["F1"])


if __name__ == "__main__":
    unittest.main()
