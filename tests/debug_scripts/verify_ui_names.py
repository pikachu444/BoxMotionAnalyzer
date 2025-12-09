from PySide6.QtWidgets import QApplication, QComboBox
from src.config import config_visualization as config
import sys

def test_ui_names():
    app = QApplication.instance() or QApplication(sys.argv)

    combo = QComboBox()
    print("--- Verifying ComboBox Population ---")
    for display, internal in config.PLOT_DATA_DISPLAY_MAP.items():
        combo.addItem(display, internal)
        print(f"Added Item: '{display}' -> Data: '{internal}'")

    # Check item 0
    combo.setCurrentIndex(0)
    current_text = combo.currentText()
    current_data = combo.currentData()

    print(f"\nItem 0 Selected:")
    print(f"  Text (User sees): '{current_text}'")
    print(f"  Data (Code sees): '{current_data}'")

    # Verification
    expected_display = list(config.PLOT_DATA_DISPLAY_MAP.keys())[0]
    expected_data = list(config.PLOT_DATA_DISPLAY_MAP.values())[0]

    if current_text == expected_display and current_data == expected_data:
        print("\nSUCCESS: UI Mapping works as expected.")
    else:
        print(f"\nFAILURE: Expected '{expected_display}'/'{expected_data}', got '{current_text}'/'{current_data}'")

if __name__ == "__main__":
    test_ui_names()
