# =========================================
#    Box Corner Index & Axis Orientation
#    (오른손 법칙/Right-Handed, 최종본)
# =========================================
#
#           z+
#           ↑
#           |
#           7-------6
#          /|      /|
#         / |     / |
#        4-------5  |
#        |  |    |  |
#        |  3----|--2    ^ y+ (깊이, 화면 안쪽)
#        | /     | /
#        |/      |/
#        0-------1
#           |
#           +----→ x+
#
#  인덱스 및 좌표:
#   0: (minX, minY, minZ)  # 앞-왼-아래 (내 쪽 아래 왼쪽)
#   1: (maxX, minY, minZ)  # 앞-오른-아래
#   2: (maxX, maxY, minZ)  # 뒤-오른-아래 (화면 깊이+ 오른쪽)
#   3: (minX, maxY, minZ)  # 뒤-왼-아래 (화면 깊이+ 왼쪽)
#   4: (minX, minY, maxZ)  # 앞-왼-위
#   5: (maxX, minY, maxZ)  # 앞-오른-위
#   6: (maxX, maxY, maxZ)  # 뒤-오른-위
#   7: (minX, maxY, maxZ)  # 뒤-왼-위
#
#  * x+ : 오른쪽
#  * y+ : 화면 깊이(안쪽)
#  * z+ : 위
# =========================================

# =========================================
#      Application Configuration
# =========================================

import os
import sys
from collections import OrderedDict

import numpy as np
from src.config.data_columns import HeaderL2, RigidBodyCols, TimeCols
from src.config import config_app

# 1. Box Geometry & Labels
# -----------------------------------------
# Box dimensions (x, y, z) in mm
BOX_SIZE = np.array([2000, 1200, 200])

# Box corner labels in a fixed order
# Updated to match BoxMotionAnalyzer output (C1~C8)
BOX_CORNERS_LABELS = [
    "C1", "C2", "C3", "C4", "C5", "C6", "C7", "C8"
]

# Box faces defined by corner indices
BOX_FACES = [
    {"label": "BOTTOM", "corner_indices": [0, 1, 2, 3]},
    {"label": "TOP",    "corner_indices": [4, 5, 6, 7]},
    {"label": "FRONT",  "corner_indices": [0, 1, 5, 4]},
    {"label": "BACK",   "corner_indices": [3, 2, 6, 7]},
    {"label": "LEFT",   "corner_indices": [0, 3, 7, 4]},
    {"label": "RIGHT",  "corner_indices": [1, 2, 6, 5]},
]

# Face Keyword Map for dynamic marker coloring
# Matches marker ID prefixes to face labels.
FACE_KEYWORD_MAP = {
    "TOP":    ["TOP", "T"],
    "BOTTOM": ["BOTTOM", "BTM", "M"],
    "FRONT":  ["FRONT", "FA", "F"],
    "BACK":   ["BACK", "BA", "B"],
    "LEFT":   ["LEFT", "L"],
    "RIGHT":  ["RIGHT", "R"]
}

# 2. Marker Geometry & Labels
# -----------------------------------------
# Number of markers on each face (in the order of BOX_FACES)
MARKERS_PER_FACE = [8, 8, 3, 3, 3, 3]

# Marker labels generated based on the face and count
MARKER_LABELS = [
    f"MK_BTM_{i+1}" for i in range(MARKERS_PER_FACE[0])
] + [
    f"MK_TOP_{i+1}" for i in range(MARKERS_PER_FACE[1])
] + [
    f"MK_FRONT_{i+1}" for i in range(MARKERS_PER_FACE[2])
] + [
    f"MK_BACK_{i+1}" for i in range(MARKERS_PER_FACE[3])
] + [
    f"MK_LEFT_{i+1}" for i in range(MARKERS_PER_FACE[4])
] + [
    f"MK_RIGHT_{i+1}" for i in range(MARKERS_PER_FACE[5])
]

# 3. Animation Settings
# -----------------------------------------
N_FRAMES = 70
FPS = 30

# 5. Visualization Style & Color Configuration
# -----------------------------------------
STYLE = {
    "ground": {
        # Center and Direction are now dynamic based on WORLD_VERTICAL_AXIS_INDEX
        # But we keep size/color here.
        "size": [5000, 5000],
        "color": "white",
        "opacity": 0.5
    },
    "box": {
        "color": "lightblue",
        "opacity": 0.5,
        "line_width": 2
    },
    "labels": {
        "box_font_size": 10,
        "marker_font_size": 8
    },
    "markers": {
        "point_size": 10,
        "color_map": {
            "TOP": "red",
            "BOTTOM": "blue",
            "FRONT": "green",
            "BACK": "yellow",
            "LEFT": "purple",
            "RIGHT": "orange",
            "ETC": "grey" # Default color for unmatched markers
        }
    }
}


# 5. File Paths (Legacy, for reference)
# -----------------------------------------
DATA_DIR = "data/"
TEST_CSV_PATH = DATA_DIR + "testdata_box_marker.csv"


# 6. Entity / Inspector Configuration
# -----------------------------------------
ENTITY_TYPE_COM = "com"
ENTITY_TYPE_CORNER = "corner"
ENTITY_TYPE_MARKER = "marker"

ENTITY_ID_COM = "CoM"
ENTITY_GROUP_LABELS = OrderedDict([
    ("Center of Mass", ENTITY_TYPE_COM),
    ("Corners", ENTITY_TYPE_CORNER),
    ("Markers", ENTITY_TYPE_MARKER),
])


def is_corner_entity(entity_id: str) -> bool:
    return entity_id in BOX_CORNERS_LABELS


def classify_entity_id(entity_id: str) -> str:
    if entity_id == ENTITY_ID_COM:
        return ENTITY_TYPE_COM
    if is_corner_entity(entity_id):
        return ENTITY_TYPE_CORNER
    return ENTITY_TYPE_MARKER


# 7. UI Label Text Constants
# -----------------------------------------
LBL_POSITION = "Position"
LBL_VELOCITY = "Velocity"
LBL_ACCELERATION = "Acceleration"
LBL_VELOCITY_NORM = "Velocity Norm"
LBL_SPEED = LBL_VELOCITY_NORM
LBL_USE_FRAME_RANGE = "Use Frame Range"
LBL_START = "Start:"
LBL_END = "End:"
LBL_PLOT_DATA = "Plot Data:"
LBL_DISPLAY_OPTIONS = "Display Options"
LBL_OBJECT_INSPECTOR = "Scene Inspector"
LBL_INFO_LOG = "Frame Inspector"
LBL_PROPERTY = "Property"
LBL_FRAME = "Frame"
LBL_TIME_SECONDS = "Time (s)"
LBL_EMPTY_VALUE = "N/A"


# 8. Key Constants for Code Robustness
# -----------------------------------------
# For STYLE dictionary
SK_GROUND = 'ground'
SK_BOX = 'box'
SK_LABELS = 'labels'
SK_MARKERS = 'markers'

SK_CENTER = 'center'
SK_SIZE = 'size'
SK_COLOR = 'color'
SK_OPACITY = 'opacity'
SK_LINE_WIDTH = 'line_width'
SK_FONT_SIZE_BOX = 'box_font_size'
SK_FONT_SIZE_MARKER = 'marker_font_size'
SK_POINT_SIZE = 'point_size'
SK_COLOR_MAP = 'color_map'

# For Actor/PolyData dictionaries and face definitions
SK_ACTOR_BOX = 'box'
SK_ACTOR_MARKERS = 'markers'
SK_ACTOR_LABELS = 'labels'
SK_FACE_LABEL = 'label'
SK_CORNER_INDICES = 'corner_indices'

# For DataFrame columns used by visualization long format
DF_FRAME = TimeCols.FRAME
DF_TIME = TimeCols.TIME
DF_ENTITY_ID = "entity_id"
DF_OBJECT_ID = DF_ENTITY_ID
DF_ENTITY_TYPE = "entity_type"
DF_SOURCE_OBJECT_ID = "source_object_id"

DF_POS_GLOBAL_X = "position_global_x"
DF_POS_GLOBAL_Y = "position_global_y"
DF_POS_GLOBAL_Z = "position_global_z"
DF_VEL_GLOBAL_X = "velocity_global_x"
DF_VEL_GLOBAL_Y = "velocity_global_y"
DF_VEL_GLOBAL_Z = "velocity_global_z"
DF_VEL_GLOBAL_NORM = "velocity_global_norm"
DF_VEL_BOX_LOCAL_X = "velocity_box_local_x"
DF_VEL_BOX_LOCAL_Y = "velocity_box_local_y"
DF_VEL_BOX_LOCAL_Z = "velocity_box_local_z"
DF_VEL_BOX_LOCAL_NORM = "velocity_box_local_norm"
DF_ACC_GLOBAL_X = "acceleration_global_x"
DF_ACC_GLOBAL_Y = "acceleration_global_y"
DF_ACC_GLOBAL_Z = "acceleration_global_z"
DF_ACC_GLOBAL_NORM = "acceleration_global_norm"
DF_ACC_BOX_LOCAL_X = "acceleration_box_local_x"
DF_ACC_BOX_LOCAL_Y = "acceleration_box_local_y"
DF_ACC_BOX_LOCAL_Z = "acceleration_box_local_z"
DF_ACC_BOX_LOCAL_NORM = "acceleration_box_local_norm"

# Backward-compatible aliases used by existing visualization code and tests.
DF_POS_X = DF_POS_GLOBAL_X
DF_POS_Y = DF_POS_GLOBAL_Y
DF_POS_Z = DF_POS_GLOBAL_Z
DF_VEL_X = DF_VEL_GLOBAL_X
DF_VEL_Y = DF_VEL_GLOBAL_Y
DF_VEL_Z = DF_VEL_GLOBAL_Z
DF_SPEED_GLOBAL = DF_VEL_GLOBAL_NORM

# Legacy constants kept for compatibility with older code paths.
MH_LEVEL_DATATYPE = "data_type"
MH_LEVEL_OBJECT_ID = "object_id"
MH_LEVEL_AXIS = "axis"
MH_VAL_POSITION = "position"
MH_VAL_VELOCITY = "velocity"

PLOT_METRIC_LABELS = OrderedDict([
    (DF_POS_GLOBAL_X, "Position X (Global Frame)"),
    (DF_POS_GLOBAL_Y, "Position Y (Global Frame)"),
    (DF_POS_GLOBAL_Z, "Position Z (Global Frame)"),
    (DF_VEL_GLOBAL_X, "Velocity X (Global Frame)"),
    (DF_VEL_GLOBAL_Y, "Velocity Y (Global Frame)"),
    (DF_VEL_GLOBAL_Z, "Velocity Z (Global Frame)"),
    (DF_VEL_GLOBAL_NORM, "Velocity Norm (Global Frame)"),
    (DF_VEL_BOX_LOCAL_X, "Velocity X (Box Local Frame)"),
    (DF_VEL_BOX_LOCAL_Y, "Velocity Y (Box Local Frame)"),
    (DF_VEL_BOX_LOCAL_Z, "Velocity Z (Box Local Frame)"),
    (DF_VEL_BOX_LOCAL_NORM, "Velocity Norm (Box Local Frame)"),
    (DF_ACC_GLOBAL_X, "Acceleration X (Global Frame)"),
    (DF_ACC_GLOBAL_Y, "Acceleration Y (Global Frame)"),
    (DF_ACC_GLOBAL_Z, "Acceleration Z (Global Frame)"),
    (DF_ACC_GLOBAL_NORM, "Acceleration Norm (Global Frame)"),
    (DF_ACC_BOX_LOCAL_X, "Acceleration X (Box Local Frame)"),
    (DF_ACC_BOX_LOCAL_Y, "Acceleration Y (Box Local Frame)"),
    (DF_ACC_BOX_LOCAL_Z, "Acceleration Z (Box Local Frame)"),
    (DF_ACC_BOX_LOCAL_NORM, "Acceleration Norm (Box Local Frame)"),
])

ENTITY_TYPE_METRICS = {
    ENTITY_TYPE_COM: [
        DF_POS_GLOBAL_X,
        DF_POS_GLOBAL_Y,
        DF_POS_GLOBAL_Z,
        DF_VEL_GLOBAL_X,
        DF_VEL_GLOBAL_Y,
        DF_VEL_GLOBAL_Z,
        DF_VEL_GLOBAL_NORM,
        DF_VEL_BOX_LOCAL_X,
        DF_VEL_BOX_LOCAL_Y,
        DF_VEL_BOX_LOCAL_Z,
        DF_VEL_BOX_LOCAL_NORM,
        DF_ACC_GLOBAL_X,
        DF_ACC_GLOBAL_Y,
        DF_ACC_GLOBAL_Z,
        DF_ACC_GLOBAL_NORM,
        DF_ACC_BOX_LOCAL_X,
        DF_ACC_BOX_LOCAL_Y,
        DF_ACC_BOX_LOCAL_Z,
        DF_ACC_BOX_LOCAL_NORM,
    ],
    ENTITY_TYPE_CORNER: [
        DF_POS_GLOBAL_X,
        DF_POS_GLOBAL_Y,
        DF_POS_GLOBAL_Z,
        DF_VEL_GLOBAL_X,
        DF_VEL_GLOBAL_Y,
        DF_VEL_GLOBAL_Z,
        DF_VEL_GLOBAL_NORM,
        DF_ACC_GLOBAL_X,
        DF_ACC_GLOBAL_Y,
        DF_ACC_GLOBAL_Z,
        DF_ACC_GLOBAL_NORM,
    ],
    ENTITY_TYPE_MARKER: [
        DF_POS_GLOBAL_X,
        DF_POS_GLOBAL_Y,
        DF_POS_GLOBAL_Z,
    ],
}

PLOT_DATA_DISPLAY_MAP = OrderedDict(
    (PLOT_METRIC_LABELS[column], column)
    for column in ENTITY_TYPE_METRICS[ENTITY_TYPE_COM]
)

FRAME_INSPECTOR_ROWS = {
    ENTITY_TYPE_COM: {
        "position": [DF_POS_GLOBAL_X, DF_POS_GLOBAL_Y, DF_POS_GLOBAL_Z],
        "velocity": [
            DF_VEL_GLOBAL_X,
            DF_VEL_GLOBAL_Y,
            DF_VEL_GLOBAL_Z,
            DF_VEL_GLOBAL_NORM,
            DF_VEL_BOX_LOCAL_X,
            DF_VEL_BOX_LOCAL_Y,
            DF_VEL_BOX_LOCAL_Z,
            DF_VEL_BOX_LOCAL_NORM,
        ],
        "acceleration": [
            DF_ACC_GLOBAL_X,
            DF_ACC_GLOBAL_Y,
            DF_ACC_GLOBAL_Z,
            DF_ACC_GLOBAL_NORM,
            DF_ACC_BOX_LOCAL_X,
            DF_ACC_BOX_LOCAL_Y,
            DF_ACC_BOX_LOCAL_Z,
            DF_ACC_BOX_LOCAL_NORM,
        ],
    },
    ENTITY_TYPE_CORNER: {
        "position": [DF_POS_GLOBAL_X, DF_POS_GLOBAL_Y, DF_POS_GLOBAL_Z],
        "velocity": [DF_VEL_GLOBAL_X, DF_VEL_GLOBAL_Y, DF_VEL_GLOBAL_Z, DF_VEL_GLOBAL_NORM],
        "acceleration": [DF_ACC_GLOBAL_X, DF_ACC_GLOBAL_Y, DF_ACC_GLOBAL_Z, DF_ACC_GLOBAL_NORM],
    },
    ENTITY_TYPE_MARKER: {
        "position": [DF_POS_GLOBAL_X, DF_POS_GLOBAL_Y, DF_POS_GLOBAL_Z],
        "velocity": [],
        "acceleration": [],
    },
}


INSPECTOR_HELP_TEXT = {
    ENTITY_TYPE_COM: "CoM supports Global Frame and Box Local Frame velocity/acceleration metrics.",
    ENTITY_TYPE_CORNER: "Corners support Global Frame position, velocity, velocity norm, and acceleration metrics.",
    ENTITY_TYPE_MARKER: "Markers support Global Frame position metrics only.",
}


def get_metric_options(entity_type: str | None) -> list[tuple[str, str]]:
    if entity_type is None:
        entity_type = ENTITY_TYPE_COM
    return [
        (PLOT_METRIC_LABELS[column], column)
        for column in ENTITY_TYPE_METRICS.get(entity_type, ENTITY_TYPE_METRICS[ENTITY_TYPE_MARKER])
    ]


def get_metric_label(metric_key: str) -> str:
    return PLOT_METRIC_LABELS.get(metric_key, metric_key)


def get_frame_inspector_rows(
    entity_type: str | None,
    *,
    include_position: bool,
    include_velocity: bool,
    include_acceleration: bool,
) -> list[tuple[str, str]]:
    rows = [(LBL_FRAME, DF_FRAME), (LBL_TIME_SECONDS, DF_TIME)]
    if entity_type is None:
        return rows

    sections = FRAME_INSPECTOR_ROWS.get(entity_type, FRAME_INSPECTOR_ROWS[ENTITY_TYPE_MARKER])
    if include_position:
        rows.extend((get_metric_label(column), column) for column in sections["position"])
    if include_velocity:
        rows.extend((get_metric_label(column), column) for column in sections["velocity"])
    if include_acceleration:
        rows.extend((get_metric_label(column), column) for column in sections["acceleration"])
    return rows


def get_inspector_help_text(entity_type: str | None) -> str:
    if entity_type is None:
        entity_type = ENTITY_TYPE_COM
    return INSPECTOR_HELP_TEXT.get(entity_type, "")


# 9. Launcher Window Configuration
# -----------------------------------------
def _get_images_dir():
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return os.path.join(sys._MEIPASS, "src", "config", "images")
    return os.path.join(os.path.dirname(__file__), "images")


IMAGES_DIR = _get_images_dir()
LAUNCHER_TITLE = "3D Motion Analyzer"
APP_USER_MODEL_ID = "pikachu444.BoxMotionAnalyzer"
APP_ICON_PATH = os.path.join(IMAGES_DIR, "app_icon_taskbar.ico")
WINDOW_ICON_PATH = os.path.join(IMAGES_DIR, "app_icon_window.ico")
LAUNCHER_ICON_PATH = os.path.join(IMAGES_DIR, "launcher_image.png")
LAUNCHER_BTN_PROCESS_TEXT = "Data Processing"
LAUNCHER_BTN_VISUALIZE_TEXT = "3D Visualization"
