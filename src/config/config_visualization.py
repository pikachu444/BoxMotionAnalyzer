# =========================================
#      Visualization Specific Configuration
# =========================================

import os
import numpy as np
from src.config.config_app import BOX_DIMS
from src.config.data_columns import (
    RigidBodyCols, TimeCols, HeaderL3, HeaderL1, HeaderL2
)

# 1. Geometry & Labels (Derived from config_app)
# -----------------------------------------
# Map global BOX_DIMS to BOX_SIZE expected by visualization
# config_app.BOX_DIMS is np.array([L, W, H])
BOX_SIZE = BOX_DIMS

# Box corner labels
# Note: config_app doesn't explicitly list labels C1..C8 in a list, so we define them here matching data_columns
BOX_CORNERS_LABELS = [
    "C1", "C2", "C3", "C4", "C5", "C6", "C7", "C8"
]

# Box faces defined by corner indices (Visualization specific)
# Using standard 0-7 indexing which matches LOCAL_BOX_CORNERS in config_app
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

# 4. Visualization Style & Color Configuration
# -----------------------------------------
STYLE = {
    "ground": {
        "center": [0, 0, -1], # A bit lower than the box
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

# 5. File Paths
# -----------------------------------------
# Relative to project root
DATA_DIR = "src/visualization/data/"
# Note: visualization/data was used for test data generation.
# We might want to move this to a global data/ folder later.
TEST_CSV_PATH = os.path.join(DATA_DIR, "testdata_box_marker.csv")


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

# For DataFrame columns
DF_FRAME = TimeCols.FRAME
DF_TIME = TimeCols.TIME
DF_OBJECT_ID = 'object_id'

# Column Mappings
DF_POS_X = RigidBodyCols.POS_X
DF_POS_Y = RigidBodyCols.POS_Y
DF_POS_Z = RigidBodyCols.POS_Z
DF_VEL_X = 'vel_x'
DF_VEL_Y = 'vel_y'
DF_VEL_Z = 'vel_z'

# 9. Launcher Window Configuration
# -----------------------------------------
LAUNCHER_TITLE = "3D Motion Analyzer"
# Use absolute path relative to src/visualization for image
# (Ideally images should also be centralized, but keeping relative logic for now)
LAUNCHER_ICON_PATH = os.path.join("src", "visualization", "images", "box_icon.png")
LAUNCHER_BTN_PROCESS_TEXT = "Data Processing"
LAUNCHER_BTN_VISUALIZE_TEXT = "3D Visualization"
