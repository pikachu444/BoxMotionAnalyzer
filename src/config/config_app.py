# --- START OF FILE Newconfig.py ---
import numpy as np

# --- Project-wide Units and Coordinate System Convention ---
# All length units are assumed to be in millimeters (mm) unless otherwise specified.
# All time units are assumed to be in seconds (s) unless otherwise specified.
# Box Local Coordinate System:
# The origin is at the geometric center of the box.
# Local X-axis: Along the length (L) of the box.
# Local Y-axis: Along the width (W) of the box.
# Local Z-axis: Along the height (H) of the box.
# This forms a right-handed coordinate system.
# The interpretation of L, W, H for BOX_DIMS = [dimX, dimY, dimZ] is:
# L = BOX_DIMS[0] (along local X)
# W = BOX_DIMS[1] (along local Y)
# H = BOX_DIMS[2] (along local Z)
# World/Camera Coordinate System:
# As defined by the motion capture system or input data.
# The transformations (T, R) in AlignBoxMain.py map points from the
# box local coordinate system to this world/camera coordinate system.

# --- Box Configuration ---
# 65 incm model 65U8000F
BOX_DIMS = np.array([1578.0, 930.0, 142.0]) # L, W, H in (mm) corresponding to local X, Y, Z axes
# 75 inch model 75U8000F
# BOX_DIMS = np.array([1820.0, 1110.0, 164.0]) # L, W, H in (mm) corresponding to local X, Y, Z axes

# --- Derived Box Geometry (calculated from BOX_DIMS) ---
_L_box, _W_box, _H_box = BOX_DIMS # Unpack for clarity in local corner/edge definitions
_hl, _hw, _hh = _L_box / 2.0, _W_box / 2.0, _H_box / 2.0

# Standard 8 local corners, ordered for consistency.
# Origin at box center. Axes: X (Length), Y (Width), Z (Height).
# This order matches the one historically used in AlignBoxMain's get_box_world_corners
# and is critical for FACE_DEFINITIONS.
LOCAL_BOX_CORNERS = np.array([
    [-_hl, -_hw, -_hh], # 0
    [ _hl, -_hw, -_hh], # 1
    [ _hl,  _hw, -_hh], # 2
    [-_hl,  _hw, -_hh], # 3
    [-_hl, -_hw,  _hh], # 4
    [ _hl, -_hw,  _hh], # 5
    [ _hl,  _hw,  _hh], # 6
    [-_hl,  _hw,  _hh]  # 7
])

# Box edges defined by pairs of corner indices from LOCAL_BOX_CORNERS
# This order is for drawing a typical box wireframe.
BOX_EDGES_AS_CORNER_INDICES = np.array([
    [0, 1], [1, 2], [2, 3], [3, 0], # Edges for face at Z = -_hh
    [4, 5], [5, 6], [6, 7], [7, 4], # Edges for face at Z = +_hh
    [0, 4], [1, 5], [2, 6], [3, 7]  # Vertical connecting edges
])

# --- Face Definitions ---
# Uses corner indexing from LOCAL_BOX_CORNERS defined above.
# Local X, Y, Z axes of the box are assumed to align with BOX_DIMS[0], BOX_DIMS[1], BOX_DIMS[2].
# Current FACE_DEFINITIONS imply:
# TOP/BOTTOM faces are normal to local Y-axis.
# RIGHT/LEFT faces are normal to local X-axis.
# FRONT/BACK faces are normal to local Z-axis.
FACE_DEFINITIONS = {
    "TOP":    {'axis_idx': 1, 'direction': 1,  'bound_axes_indices': [0, 2], 'corners': [2, 3, 7, 6]}, # +Y face
    "BOTTOM": {'axis_idx': 1, 'direction': -1, 'bound_axes_indices': [0, 2], 'corners': [0, 1, 5, 4]}, # -Y face
    "RIGHT":  {'axis_idx': 0, 'direction': 1,  'bound_axes_indices': [1, 2], 'corners': [1, 2, 6, 5]}, # +X face
    "LEFT":   {'axis_idx': 0, 'direction': -1, 'bound_axes_indices': [1, 2], 'corners': [0, 4, 7, 3]}, # -X face
    "FRONT":  {'axis_idx': 2, 'direction': 1,  'bound_axes_indices': [0, 1], 'corners': [4, 5, 6, 7]}, # +Z face
    "BACK":   {'axis_idx': 2, 'direction': -1, 'bound_axes_indices': [0, 1], 'corners': [0, 3, 2, 1]}  # -Z face
}

# --- Marker Input Configuration (used in AlignBoxInputGenbyExperiment.py) ---
FACE_PREFIX_TO_INFO = {
    'F': "FRONT", 'B': "BACK", 'L': "LEFT", 'R': "RIGHT", 'T': "TOP",
    'FA': "FRONT", 'BA': "BACK", 'M': "BOTTOM"
}

# --- Floor Definition and Visualization Parameters ---
# These parameters define the floor plane in the world coordinate system and
# how it should be visualized relative to the box.
# Basic definition of the floor plane:
# Assumes a horizontal floor. The primary characteristic is its level (height)
# along the world's vertical axis.
# It's CRUCIAL to know which axis is "up" in the world/camera coordinate system
# output by the motion capture system.
# Common conventions: Y-up or Z-up.
WORLD_VERTICAL_AXIS_INDEX = 1 # 0 for X-up, 1 for Y-up, 2 for Z-up.
# IMPORTANT: Set this according to your motion capture data's world coordinate system.
# Example: If OptiTrack/Vicon typically use Y as up, set this to 1.
FLOOR_LEVEL = 0.0 # The coordinate value of the floor along the WORLD_VERTICAL_AXIS_INDEX (mm).
# Example: If floor is at Y=0 in world coordinates, and Y is up, this is 0.0.

# Visualization size of the floor for plotting, relative to the box dimensions.
# This is used by PlotResults_Matplotlib.py to draw a representative rectangular area for the floor.
# The floor will be centered (in its plane) around the projection of the box's typical location or world origin.
FLOOR_VIS_SCALE_FACTOR = 5.0 # Default scale factor. 1.0 means floor visual extent matches box's L and W projection.
# Increase this (e.g., 1.5, 2.0) if the plotted floor appears too small.

# The actual dimensions for plotting the floor rectangle will be:
# Dim1_plot = BOX_DIMS[<axis_for_L_projection>] * FLOOR_VIS_SCALE_FACTOR
# Dim2_plot = BOX_DIMS[<axis_for_W_projection>] * FLOOR_VIS_SCALE_FACTOR
# Which BOX_DIMS components (L, W, or H) are used for these depends on which world axis is vertical
# and how the floor plane is oriented.
# For a horizontal floor (normal along WORLD_VERTICAL_AXIS_INDEX):
# If WORLD_VERTICAL_AXIS_INDEX = 1 (Y is up), floor is XZ plane.
# Plot floor width typically relates to BOX_DIMS[0] (L, local X).
# Plot floor depth typically relates to BOX_DIMS[2] (H, local Z, if box is lying flat).
# Or, more generally, use the two non-vertical BOX_DIMS components.
# Let's define which BOX_DIMS indices to use for floor visualization width and depth:
# These indices refer to BOX_DIMS (0 for L, 1 for W, 2 for H).
# This assumes the floor visualization is aligned with two of the box's principal dimensions' scale.
FLOOR_VIS_DIM1_BOX_DIMS_IDX = 0 # Use BOX_DIMS[0] (L) for the first dimension of the plotted floor.
FLOOR_VIS_DIM2_BOX_DIMS_IDX = 1 # Use BOX_DIMS[1] (W) for the second dimension of the plotted floor.
# If the box is typically flat, L and W are appropriate.
# If it's upright, perhaps L and H (BOX_DIMS[2]) would be better.
# This choice depends on the typical orientation and how you want the floor to scale.

# Calculated half-extents for plotting (PlotResults_Matplotlib.py will use these)
# These will be calculated here for convenience, so other scripts just use the values.
# Note: These are half-extents from the center point where the floor is drawn.
_floor_plot_dim1_full = BOX_DIMS[FLOOR_VIS_DIM1_BOX_DIMS_IDX] * FLOOR_VIS_SCALE_FACTOR
_floor_plot_dim2_full = BOX_DIMS[FLOOR_VIS_DIM2_BOX_DIMS_IDX] * FLOOR_VIS_SCALE_FACTOR

PLOT_FLOOR_HALF_EXTENT_1 = _floor_plot_dim1_full / 2.0
PLOT_FLOOR_HALF_EXTENT_2 = _floor_plot_dim2_full / 2.0

MARKER_PREFIX_ID = 'MRK'

print(f"Config file (config.py) loaded. BOX_DIMS: {BOX_DIMS}, Floor plot half-extents: ({PLOT_FLOOR_HALF_EXTENT_1}, {PLOT_FLOOR_HALF_EXTENT_2})")

# --- END OF FILE Newconfig.py ---
