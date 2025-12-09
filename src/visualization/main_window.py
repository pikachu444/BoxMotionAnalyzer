import sys
from PySide6.QtWidgets import (
    QMainWindow, QVBoxLayout, QHBoxLayout, QWidget, QFileDialog, QApplication
)
from PySide6.QtGui import QAction
from PySide6.QtCore import QTimer, Qt
import numpy as np

from src.config import config_visualization as config
from .data_handler import DataHandler
from .vista_widget import VistaWidget
from .control_panel import ControlPanel
from .plot_widget import PlotWidget
from .plot_dialog import PlotDialog
from .animation_widget import AnimationWidget
from .info_log_widget import InfoLogWidget

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("3D Motion Analyzer")
        self.setGeometry(100, 100, 1800, 1000)

        self.current_frame = 0

        # 1. Create core components
        self.data_handler = DataHandler()
        self.vista_widget = VistaWidget(self.data_handler)
        self.control_panel = ControlPanel()
        self.plot_widget = PlotWidget()
        self.info_log_widget = InfoLogWidget()
        self.animation_widget = AnimationWidget()

        # 2. Set up the main layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        # Top part with 3D view and right panel
        top_layout = QHBoxLayout()
        top_layout.addWidget(self.vista_widget, 6)

        right_panel_layout = QVBoxLayout()
        right_panel_layout.addWidget(self.control_panel)
        right_panel_layout.addWidget(self.plot_widget)
        right_panel_layout.addWidget(self.info_log_widget)
        top_layout.addLayout(right_panel_layout, 4)

        # Add top layout and bottom animation widget to the main vertical layout
        main_layout.addLayout(top_layout)
        main_layout.addWidget(self.animation_widget)
        main_layout.setStretchFactor(top_layout, 1) # Give more space to the top part

        self._create_menu_bar()
        self.statusBar().showMessage("Ready. Please open a CSV file.")

        self.animation_timer = QTimer(self)
        self.animation_timer.timeout.connect(self.advance_frame)

        self._connect_signals()

    def _connect_signals(self):
        # Connect signals from the animation widget
        self.animation_widget.frame_changed.connect(self.set_frame)
        self.animation_widget.play_toggled.connect(self.toggle_animation)

        # Connect signals from the control panel
        self.control_panel.visibility_changed.connect(self.vista_widget.set_actor_visibility)
        self.control_panel.object_selected.connect(self.update_plot_with_multiple_objects)

        # Connect frame range controls to the plot update method
        self.control_panel.range_checkbox.stateChanged.connect(self.update_plot_with_multiple_objects)
        self.control_panel.start_frame_spinbox.valueChanged.connect(self.update_plot_with_multiple_objects)
        self.control_panel.end_frame_spinbox.valueChanged.connect(self.update_plot_with_multiple_objects)

        # Connect plot widget's double click signal
        self.plot_widget.doubleClicked.connect(self.show_plot_dialog)

        # Connect signals for the info log
        self.control_panel.object_selected.connect(self.update_info_log)
        self.info_log_widget.log_pos_checkbox.stateChanged.connect(self.update_info_log)
        self.info_log_widget.log_vel_checkbox.stateChanged.connect(self.update_info_log)
        self.info_log_widget.log_speed_checkbox.stateChanged.connect(self.update_info_log)

        # Connect frame range controls to the plot update method
        self.control_panel.range_checkbox.stateChanged.connect(self.update_plot_with_multiple_objects)
        self.control_panel.start_frame_spinbox.valueChanged.connect(self.update_plot_with_multiple_objects)
        self.control_panel.end_frame_spinbox.valueChanged.connect(self.update_plot_with_multiple_objects)

    def _create_menu_bar(self):
        menu_bar = self.menuBar()

        # File Menu
        file_menu = menu_bar.addMenu("&File")
        open_action = QAction("&Open Visualization CSV...", self)
        open_action.triggered.connect(self.open_csv_file)
        file_menu.addAction(open_action)
        file_menu.addSeparator()
        exit_action = QAction("&Exit", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # View Menu
        view_menu = menu_bar.addMenu("&View")

        reset_view_action = QAction("&Reset Camera (Fit)", self)
        reset_view_action.setShortcut("R")
        reset_view_action.triggered.connect(self.vista_widget.reset_camera_view)
        view_menu.addAction(reset_view_action)

        view_menu.addSeparator()

        view_xy_action = QAction("View &XY Plane (Alt+1)", self)
        view_xy_action.setShortcut("Alt+1")
        view_xy_action.triggered.connect(self.vista_widget.view_xy_plane)
        view_menu.addAction(view_xy_action)

        view_xz_action = QAction("View X&Z Plane (Alt+2)", self)
        view_xz_action.setShortcut("Alt+2")
        view_xz_action.triggered.connect(self.vista_widget.view_xz_plane)
        view_menu.addAction(view_xz_action)

        view_yz_action = QAction("View &YZ Plane (Alt+3)", self)
        view_yz_action.setShortcut("Alt+3")
        view_yz_action.triggered.connect(self.vista_widget.view_yz_plane)
        view_menu.addAction(view_yz_action)

        view_iso_action = QAction("View &Isometric (Alt+4)", self)
        view_iso_action.setShortcut("Alt+4")
        view_iso_action.triggered.connect(self.vista_widget.view_isometric)
        view_menu.addAction(view_iso_action)

    def open_csv_file(self):
        filepath, _ = QFileDialog.getOpenFileName(self, "Open CSV", "", "CSV Files (*.csv)")
        if filepath:
            self.statusBar().showMessage(f"Loading {filepath}...")
            success = self.data_handler.load_analysis_result(filepath)
            if success:
                self.animation_widget.set_frame_range(self.data_handler.n_frames)
                self.control_panel.populate_object_list(self.data_handler.get_object_ids())

                # Set the range for the frame spinboxes
                max_frame = self.data_handler.n_frames - 1
                self.control_panel.start_frame_spinbox.setRange(0, max_frame)
                self.control_panel.end_frame_spinbox.setRange(0, max_frame)
                self.control_panel.end_frame_spinbox.setValue(max_frame)

                self.set_frame(0)
                # Auto-fit camera to scene
                self.vista_widget.reset_camera_view()
                self.statusBar().showMessage("File loaded successfully.", 5000)
            else:
                self.statusBar().showMessage("Failed to load file.", 5000)

    def set_frame(self, frame_number: int):
        self.current_frame = frame_number
        frame_data = self.data_handler.get_frame_data(self.current_frame)
        if frame_data is not None and not frame_data.empty:
            time_value = frame_data[config.DF_TIME].iloc[0]
            self.vista_widget.update_view(self.current_frame)
            self.animation_widget.update_frame_display(
                self.current_frame, self.data_handler.n_frames, time_value
            )
            self.update_info_log() # Update log on frame change

    def toggle_animation(self, is_playing: bool):
        if is_playing and self.data_handler.visualization_dataframe is not None:
            self.animation_timer.start(1000 // config.FPS)
        else:
            self.animation_timer.stop()

    def advance_frame(self):
        new_frame = (self.current_frame + 1) % self.data_handler.n_frames
        self.set_frame(new_frame)

    def keyPressEvent(self, event):
        """Handle key press events."""
        key = event.key()
        if key == Qt.Key.Key_Q:
            self.close()
        else:
            super().keyPressEvent(event)

    def update_plot_with_multiple_objects(self):
        """
        Updates the plot widget based on the current state of the control panel.

        This method is designed as a generic "state-changed" slot. It's connected
        to multiple signals (object selection, frame range changes, etc.).
        Instead of accepting arguments from signals (which may have different types),
        it re-evaluates the complete UI state from the control panel each time it's called.
        This makes the connection robust and decoupled from the signal's signature.
        """
        if self.data_handler.visualization_dataframe is None:
            return

        selected_items = self.control_panel.object_list.selectedItems()
        if not selected_items:
            self.plot_widget.plot_multiple_data([], "")
            return

        object_ids = [item.text() for item in selected_items]
        # Retrieve the internal column name (e.g., 'pos_x' or 'RigidBody_Position_X')
        # stored in the UserData of the combobox items.
        data_to_plot = self.control_panel.plot_data_combobox.currentData()

        plot_args = []
        for obj_id in object_ids:
            df = self.data_handler.get_object_timeseries(obj_id)
            if df is not None and not df.empty and data_to_plot in df.columns:
                plot_df = df.dropna(subset=[config.DF_FRAME, data_to_plot])

                # --- Filter by frame range if enabled ---
                if self.control_panel.range_checkbox.isChecked():
                    start_frame = self.control_panel.start_frame_spinbox.value()
                    end_frame = self.control_panel.end_frame_spinbox.value()
                    plot_df = plot_df[
                        (plot_df[config.DF_FRAME] >= start_frame) &
                        (plot_df[config.DF_FRAME] <= end_frame)
                    ]

                plot_args.append({
                    "x": plot_df[config.DF_FRAME],
                    "y": plot_df[data_to_plot],
                    "label": obj_id
                })

        self.plot_widget.plot_multiple_data(plot_args, data_to_plot)

    def update_info_log(self):
        """Updates the information log based on selections."""
        selected_items = self.control_panel.object_list.selectedItems()
        if not selected_items:
            self.info_log_widget.update_info_log([])
            return

        object_ids = [item.text() for item in selected_items]
        frame_df = self.data_handler.get_frame_data(self.current_frame)
        if frame_df is None:
            return

        log_data = []
        for obj_id in object_ids:
            obj_data_row = frame_df[frame_df[config.MH_LEVEL_OBJECT_ID] == obj_id]
            if obj_data_row.empty:
                log_data.append({'object_id': obj_id}) # Add empty dict to show column
                continue

            item_data = {'object_id': obj_id}

            # Basic Info (always shown)
            item_data['frame'] = self.current_frame
            item_data['time'] = obj_data_row[config.DF_TIME].iloc[0]

            # Position
            if self.info_log_widget.log_pos_checkbox.isChecked():
                item_data[config.DF_POS_X] = obj_data_row[config.DF_POS_X].iloc[0]
                item_data[config.DF_POS_Y] = obj_data_row[config.DF_POS_Y].iloc[0]
                item_data[config.DF_POS_Z] = obj_data_row[config.DF_POS_Z].iloc[0]

            # Velocity
            if self.info_log_widget.log_vel_checkbox.isChecked():
                item_data[config.DF_VEL_X] = obj_data_row[config.DF_VEL_X].iloc[0]
                item_data[config.DF_VEL_Y] = obj_data_row[config.DF_VEL_Y].iloc[0]
                item_data[config.DF_VEL_Z] = obj_data_row[config.DF_VEL_Z].iloc[0]

            # Speed (Magnitude)
            if self.info_log_widget.log_speed_checkbox.isChecked():
                vx = obj_data_row[config.DF_VEL_X].iloc[0]
                vy = obj_data_row[config.DF_VEL_Y].iloc[0]
                vz = obj_data_row[config.DF_VEL_Z].iloc[0]
                speed = np.linalg.norm([vx, vy, vz])
                item_data[config.LBL_SPEED.lower()] = speed

            log_data.append(item_data)

        self.info_log_widget.update_info_log(log_data)


    def show_plot_dialog(self):
        """Creates and shows the detailed plot dialog."""
        plot_args = self.plot_widget.current_plot_args
        y_label = self.plot_widget.y_axis_label

        if not plot_args:
            return # Don't show dialog if there's nothing to plot

        dialog = PlotDialog(plot_args, y_label, self)
        dialog.exec()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
