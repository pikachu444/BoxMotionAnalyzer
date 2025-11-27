import unittest
from unittest.mock import MagicMock
from PySide6.QtWidgets import QApplication, QListWidget, QListWidgetItem

# Absolute imports
from src.visualization.control_panel import ControlPanel
from src.visualization import config

app = QApplication.instance() or QApplication([])

class TestTypeErrorBug(unittest.TestCase):
    def test_update_plot_slot_signature(self):
        """
        Verify that we can retrieve selected items from ControlPanel
        without relying on signal arguments that might cause TypeError.
        """
        panel = ControlPanel()

        # Populate list
        panel.populate_object_list(['C1', 'C2', 'MK_1'])

        # Select items programmatically
        # Note: In a real QListWidget, we need to set selection mode
        # The panel initializes it to ExtendedSelection.

        item1 = panel.object_list.item(0) # C1
        item1.setSelected(True)

        # Check selection logic
        selected_texts = [item.text() for item in panel.object_list.selectedItems()]
        self.assertIn('C1', selected_texts)

        # Check if internal signal logic works (we mocked the signal emission in previous tests,
        # but here we test the widget's internal state access)
        # This confirms that we can "pull" the state rather than relying on "push" arguments.
        self.assertEqual(len(selected_texts), 1)

if __name__ == '__main__':
    unittest.main()
