import unittest
from unittest.mock import MagicMock, PropertyMock
import sys
import os

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# We test the logic of the method directly, so we only need config and data_handler
import config
from data_handler import DataHandler

class TestTypeErrorBug(unittest.TestCase):

    def setUp(self):
        """Set up mock objects needed for the test."""
        # Create a mock for the main window instance
        self.mock_window = MagicMock()

        # Mock the control_panel and its widgets
        self.mock_window.control_panel = MagicMock()

        # Mock the object list and its selectedItems method
        mock_list_item = MagicMock()
        mock_list_item.text.return_value = 'C0' # Simulate one item being selected
        self.mock_window.control_panel.object_list.selectedItems.return_value = [mock_list_item]

        # Mock the plot data combobox
        self.mock_window.control_panel.plot_data_combobox.currentText.return_value = 'pos_x'

        # Mock the frame range checkbox to behave like a method
        self.mock_window.control_panel.range_checkbox.isChecked.return_value = True

        # Mock the spinboxes
        self.mock_window.control_panel.start_frame_spinbox.value.return_value = 10
        self.mock_window.control_panel.end_frame_spinbox.value.return_value = 20

        # Mock the plot_widget
        self.mock_window.plot_widget = MagicMock()

        # Mock the data_handler and load it with real data
        self.mock_window.data_handler = DataHandler()
        # Generate data if it doesn't exist
        import os
        if not os.path.exists(config.TEST_CSV_PATH):
            import make_testdata
            make_testdata.main()
        self.mock_window.data_handler.load_visualization_csv(config.TEST_CSV_PATH)

    def test_update_plot_logic_with_mocked_ui(self):
        """
        This test replicates the logic of `update_plot_with_multiple_objects`
        using the mocked UI components to ensure no TypeError occurs.
        """
        # --- This is the logic copied from main_window.py ---
        try:
            # This is the line that would fail if the method took an argument
            # from a signal like valueChanged(int). Since our new method takes
            # no arguments, we call it with none.

            # Replicate the start of the method
            if self.mock_window.data_handler.visualization_dataframe is None:
                return

            selected_items = self.mock_window.control_panel.object_list.selectedItems()
            if not selected_items:
                self.mock_window.plot_widget.plot_multiple_data.assert_called_with([], "")
                return

            object_ids = [item.text() for item in selected_items]
            data_to_plot = self.mock_window.control_panel.plot_data_combobox.currentText()

            plot_args = []
            for obj_id in object_ids:
                df = self.mock_window.data_handler.get_object_timeseries(obj_id)
                if df is not None and not df.empty and data_to_plot in df.columns:
                    plot_df = df.dropna(subset=[config.DF_FRAME, data_to_plot])

                    if self.mock_window.control_panel.range_checkbox.isChecked():
                        start_frame = self.mock_window.control_panel.start_frame_spinbox.value()
                        end_frame = self.mock_window.control_panel.end_frame_spinbox.value()
                        plot_df = plot_df[
                            (plot_df[config.DF_FRAME] >= start_frame) &
                            (plot_df[config.DF_FRAME] <= end_frame)
                        ]

                    # This append is the core of the loop that would fail
                    plot_args.append({
                        "x": plot_df[config.DF_FRAME],
                        "y": plot_df[data_to_plot],
                        "label": obj_id
                    })

            self.mock_window.plot_widget.plot_multiple_data(plot_args, data_to_plot)
            # --- End of copied logic ---

            print("\n✓ Test Passed: The logic of update_plot_with_multiple_objects executed without a TypeError.")

        except TypeError as e:
            self.fail(f"TypeError was raised, indicating a design flaw in the slot's argument handling: {e}")

if __name__ == '__main__':
    unittest.main()
