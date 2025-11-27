import sys
from PySide6.QtWidgets import QApplication
import pyvista as pv

# Ensure pyvista uses an offscreen plotter
pv.OFF_SCREEN = True

from data_handler import DataHandler
from vista_widget import VistaWidget

def main():
    """
    Runs the core logic of loading data and rendering the first frame
    in an offscreen plotter, then saves a screenshot.
    This avoids GUI-related platform issues for testing.
    """
    # We still need a QApplication instance for Qt components
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)

    print("Initializing components for offscreen test...")
    data_handler = DataHandler()

    # We don't need the full MainWindow, just the VistaWidget
    # The QtInteractor inside VistaWidget will respect pv.OFF_SCREEN
    vista_widget = VistaWidget(data_handler)

    csv_path = "data/testdata_box_marker.csv"
    print(f"Loading data from {csv_path}...")
    success = data_handler.load_visualization_csv(csv_path)

    if not success:
        print("Failed to load CSV data. Aborting test.")
        sys.exit(1)

    print("Updating view to frame 0...")
    vista_widget.update_view(0)

    # Add a light for better visibility in the screenshot
    vista_widget.plotter.add_light(pv.Light(position=(5, 5, 5), intensity=1))
    vista_widget.plotter.camera_position = 'iso'
    vista_widget.plotter.reset_camera()

    screenshot_path = "test_output.png"
    print(f"Saving screenshot to {screenshot_path}...")
    vista_widget.plotter.screenshot(screenshot_path)

    print("Offscreen runner test completed successfully.")

    # Important to close the plotter to free up resources
    vista_widget.plotter.close()
    app.quit()


if __name__ == '__main__':
    main()
