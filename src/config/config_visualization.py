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

import numpy as np
from src.config.data_columns import (
    RigidBodyCols, TimeCols, HeaderL3
)
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
            "RIGHT": "orange"
        }
    }
}


# 5. File Paths (Legacy, for reference)
# -----------------------------------------
DATA_DIR = "data/"
TEST_CSV_PATH = DATA_DIR + "testdata_box_marker.csv"


# 6. Multi-Header CSV Constants
# -----------------------------------------
MH_LEVEL_DATATYPE = 'data_type'
MH_LEVEL_OBJECT_ID = 'object_id'
MH_LEVEL_AXIS = 'axis'
MH_VAL_POSITION = 'position'
MH_VAL_VELOCITY = 'velocity'


# 7. UI Label Text Constants
# -----------------------------------------
LBL_POSITION = "Position"
LBL_VELOCITY = "Velocity"
LBL_SPEED = "Speed"
LBL_USE_FRAME_RANGE = "Use Frame Range"
LBL_START = "Start:"
LBL_END = "End:"
LBL_PLOT_DATA = "Plot Data:"
LBL_DISPLAY_OPTIONS = "Display Options"
LBL_OBJECT_INSPECTOR = "Object Inspector"
LBL_INFO_LOG = "Information Log"
LBL_PROPERTY = "Property"


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

# For DataFrame columns (SSOT from src.config.data_columns)
DF_FRAME = TimeCols.FRAME
DF_TIME = TimeCols.TIME
DF_OBJECT_ID = 'object_id' # This is internal to visualizer's long format, or we can map it if needed.
                           # But for now, DataHandler creates this column.
                           # Wait, DataHandler.load_analysis_result will need to produce this.

# Mapping RigidBodyCols to internal keys if we want to keep 'pos_x' style or use full names.
# The plan said: DF_POS_X = RigidBodyCols.POS_X
# This means the DataFrame column name will be 'RigidBody_Position_X'.
DF_POS_X = RigidBodyCols.POS_X
DF_POS_Y = RigidBodyCols.POS_Y
DF_POS_Z = RigidBodyCols.POS_Z
# Note: Velocity columns might need similar mapping if used.
DF_VEL_X = 'vel_x' # Placeholder if not in RigidBodyCols
DF_VEL_Y = 'vel_y'
DF_VEL_Z = 'vel_z'


# 9. Launcher Window Configuration
# -----------------------------------------
import os
LAUNCHER_TITLE = "3D Motion Analyzer"
# Use absolute path relative to this config file's location
LAUNCHER_ICON_PATH = os.path.join(os.path.dirname(__file__), "images", "box_icon.png")
LAUNCHER_BTN_PROCESS_TEXT = "Data Processing"
LAUNCHER_BTN_VISUALIZE_TEXT = "3D Visualization"
