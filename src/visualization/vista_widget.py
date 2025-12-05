import pyvista as pv
from PySide6.QtWidgets import QWidget, QVBoxLayout
from pyvistaqt import QtInteractor
import numpy as np
import pandas as pd
from src.config import config_visualization as config
from src.config import config_app
from .data_handler import DataHandler

class VistaWidget(QWidget):
    def __init__(self, data_handler: DataHandler, parent=None, testing_mode=False):
        super().__init__(parent)
        self.data_handler = data_handler
        self.plotter = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        if not testing_mode:
            self.plotter = QtInteractor(self)
            layout.addWidget(self.plotter.interactor)

        # --- Centralized Actor and PolyData Management ---
        k = config
        self.actors = {k.SK_ACTOR_BOX: None, k.SK_ACTOR_MARKERS: {}, k.SK_ACTOR_LABELS: {}}
        self.polydata = {k.SK_ACTOR_BOX: None, k.SK_ACTOR_MARKERS: {}, k.SK_ACTOR_LABELS: {}}

        if not testing_mode:
            self._setup_scene()

    def _setup_scene(self):
        """Initial setup of the plotter and permanent actors."""
        s = config.STYLE
        k = config
        self.plotter.set_background(s[k.SK_GROUND][k.SK_COLOR])
        self.plotter.add_axes(interactive=False)

        # Determine Up Axis from Global Config
        # WORLD_VERTICAL_AXIS_INDEX: 1 (Y-up) or 2 (Z-up)
        up_axis_idx = getattr(config_app, 'WORLD_VERTICAL_AXIS_INDEX', 2)

        if up_axis_idx == 1:
            # Y-Up
            ground_direction = (0, 1, 0)
            ground_center = (0, -1, 0) # Slightly below origin along Y
            self.plotter.camera.up = (0, 1, 0)
        else:
            # Z-Up (Default)
            ground_direction = (0, 0, 1)
            ground_center = (0, 0, -1) # Slightly below origin along Z
            self.plotter.camera.up = (0, 0, 1)

        ground = pv.Plane(
            center=ground_center,
            direction=ground_direction,
            i_size=s[k.SK_GROUND][k.SK_SIZE][0],
            j_size=s[k.SK_GROUND][k.SK_SIZE][1]
        )
        self.plotter.add_mesh(
            ground,
            color=s[k.SK_GROUND][k.SK_COLOR],
            opacity=s[k.SK_GROUND][k.SK_OPACITY]
        )

    def _update_polydata_points(self, pd_dict, key, points):
        """Helper to safely update points of a PolyData object in our dict."""
        if pd_dict.get(key) is None:
            pd_dict[key] = pv.PolyData(points)
        else:
            if pd_dict[key].n_points != points.shape[0]:
                # This handles cases where marker counts might differ, though not expected with current data
                pd_dict[key].points = np.resize(pd_dict[key].points, points.shape)
            pd_dict[key].points[:] = points
            pd_dict[key].Modified()

    def update_view(self, frame_number: int):
        """Updates the 3D view to a specific frame."""
        if self.plotter is None or self.data_handler.visualization_dataframe is None: return
        frame_df = self.data_handler.get_frame_data(frame_number)
        if frame_df is None or frame_df.empty: return

        s = config.STYLE
        k = config

        # --- Update Box ---
        box_points = self._get_points_for_ids(frame_df, k.BOX_CORNERS_LABELS)
        if box_points is not None:
            if self.actors[k.SK_ACTOR_BOX] is None:
                faces = np.hstack([([4] + face[k.SK_CORNER_INDICES]) for face in k.BOX_FACES])
                self.polydata[k.SK_ACTOR_BOX] = pv.PolyData(box_points, faces=faces)
                self.actors[k.SK_ACTOR_BOX] = self.plotter.add_mesh(
                    self.polydata[k.SK_ACTOR_BOX], style='surface',
                    color=s[k.SK_BOX][k.SK_COLOR], opacity=s[k.SK_BOX][k.SK_OPACITY],
                    name="box"
                )
                self.polydata[k.SK_ACTOR_LABELS][k.SK_ACTOR_BOX] = pv.PolyData(box_points)
                self.actors[k.SK_ACTOR_LABELS][k.SK_ACTOR_BOX] = self.plotter.add_point_labels(
                    self.polydata[k.SK_ACTOR_LABELS][k.SK_ACTOR_BOX], k.BOX_CORNERS_LABELS,
                    name="box_labels", font_size=s[k.SK_LABELS][k.SK_FONT_SIZE_BOX]
                )
            else:
                self.polydata[k.SK_ACTOR_BOX].points = box_points
                self.polydata[k.SK_ACTOR_BOX].Modified()
                self._update_polydata_points(self.polydata[k.SK_ACTOR_LABELS], k.SK_ACTOR_BOX, box_points)

        # --- Update Markers (Dynamic) ---
        # 1. Identify all available objects in the data
        all_object_ids = self.data_handler.get_object_ids()
        # 2. Filter out Box Corners (C1~C8)
        all_marker_ids = [mid for mid in all_object_ids if mid not in k.BOX_CORNERS_LABELS]

        # 3. Group markers by Face based on FACE_KEYWORD_MAP
        grouped_markers = {}
        for mid in all_marker_ids:
            face_found = "ETC"
            mid_upper = mid.upper()

            # Check prefixes defined in FACE_KEYWORD_MAP
            for face_key, prefixes in k.FACE_KEYWORD_MAP.items():
                for prefix in prefixes:
                    if mid_upper.startswith(prefix):
                        face_found = face_key
                        break
                if face_found != "ETC":
                    break

            if face_found not in grouped_markers:
                grouped_markers[face_found] = []
            grouped_markers[face_found].append(mid)

        # 4. Render each group
        for face_name, marker_ids in grouped_markers.items():
            marker_points = self._get_points_for_ids(frame_df, marker_ids)

            if marker_points is not None:
                if face_name not in self.actors[k.SK_ACTOR_MARKERS]:
                    color = s[k.SK_MARKERS][k.SK_COLOR_MAP].get(face_name, 'grey')
                    self._update_polydata_points(self.polydata[k.SK_ACTOR_MARKERS], face_name, marker_points)
                    self.actors[k.SK_ACTOR_MARKERS][face_name] = self.plotter.add_mesh(
                        self.polydata[k.SK_ACTOR_MARKERS][face_name], color=color,
                        render_points_as_spheres=True, point_size=s[k.SK_MARKERS][k.SK_POINT_SIZE],
                        name=f"markers_{face_name}"
                    )
                    self._update_polydata_points(self.polydata[k.SK_ACTOR_LABELS], face_name, marker_points)
                    self.actors[k.SK_ACTOR_LABELS][face_name] = self.plotter.add_point_labels(
                        self.polydata[k.SK_ACTOR_LABELS][face_name], marker_ids,
                        font_size=s[k.SK_LABELS][k.SK_FONT_SIZE_MARKER],
                        name=f"labels_{face_name}"
                    )
                else:
                    self._update_polydata_points(self.polydata[k.SK_ACTOR_MARKERS], face_name, marker_points)
                    self._update_polydata_points(self.polydata[k.SK_ACTOR_LABELS], face_name, marker_points)

        self.plotter.render()

    # --- View Control Methods ---
    def reset_camera_view(self):
        """Resets the camera to fit all actors in the view."""
        if self.plotter:
            self.plotter.reset_camera()

    def view_xy_plane(self):
        """Sets view to XY plane (Looking along Z axis)."""
        if self.plotter:
            self.plotter.view_xy()
            self._adjust_camera_up()

    def view_xz_plane(self):
        """Sets view to XZ plane (Looking along Y axis)."""
        if self.plotter:
            self.plotter.view_xz()
            self._adjust_camera_up()

    def view_yz_plane(self):
        """Sets view to YZ plane (Looking along X axis)."""
        if self.plotter:
            self.plotter.view_yz()
            self._adjust_camera_up()

    def view_isometric(self):
        """Sets view to Isometric."""
        if self.plotter:
            self.plotter.view_isometric()
            self._adjust_camera_up()

    def _adjust_camera_up(self):
        """Ensures the camera's up vector matches the configured vertical axis."""
        up_axis_idx = getattr(config_app, 'WORLD_VERTICAL_AXIS_INDEX', 2)
        if up_axis_idx == 1: # Y-Up
            self.plotter.camera.up = (0, 1, 0)
        else: # Z-Up
            self.plotter.camera.up = (0, 0, 1)
        self.plotter.render()

    def _get_points_for_ids(self, df, ids):
        # Using .copy() to avoid SettingWithCopyWarning
        points_df = df[df[config.DF_OBJECT_ID].isin(ids)].copy()
        if points_df.empty: return None

        sorter = np.array(ids)
        points_df[config.DF_OBJECT_ID] = points_df[config.DF_OBJECT_ID].astype(pd.CategoricalDtype(categories=sorter, ordered=True))
        points_df = points_df.sort_values(config.DF_OBJECT_ID)
        # Use the standardized 'pos_x', 'pos_y', 'pos_z' columns
        return points_df[[config.DF_POS_X, config.DF_POS_Y, config.DF_POS_Z]].values

    def set_actor_visibility(self, actor_name: str, is_visible: bool):
        """Sets the visibility of actors."""
        if self.plotter is None: return
        k = config
        if actor_name == k.SK_ACTOR_BOX and self.actors[k.SK_ACTOR_BOX]:
            self.actors[k.SK_ACTOR_BOX].SetVisibility(is_visible)
        elif actor_name == k.SK_ACTOR_MARKERS:
            for actor in self.actors[k.SK_ACTOR_MARKERS].values():
                actor.SetVisibility(is_visible)
        elif actor_name == k.SK_ACTOR_LABELS:
            for actor in self.actors[k.SK_ACTOR_LABELS].values():
                actor.SetVisibility(is_visible)

        self.plotter.render()
