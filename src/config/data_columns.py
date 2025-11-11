from dataclasses import dataclass

@dataclass(frozen=True)
class TimeCols:
    TIME: str = "Time"
    FRAME: str = "Frame"

@dataclass(frozen=True)
class RawMarkerCols:
    X_SUFFIX: str = "_X"
    Y_SUFFIX: str = "_Y"
    Z_SUFFIX: str = "_Z"
    FACEINFO_SUFFIX: str = "_FaceInfo"

@dataclass(frozen=True)
class RigidBodyCols:
    BASE_NAME: str = "RigidBody_Position"
    POS_X: str = "RigidBody_Position_X"
    POS_Y: str = "RigidBody_Position_Y"
    POS_Z: str = "RigidBody_Position_Z"

@dataclass(frozen=True)
class SourceCols:
    POSE: str = "Pose_Source"

@dataclass(frozen=True)
class PoseCols:
    T_PREFIX: str = "Box_T"
    R_PREFIX: str = "Box_R"
    POS_X: str = "Box_Tx"
    POS_Y: str = "Box_Ty"
    POS_Z: str = "Box_Tz"
    ROT_X: str = "Box_Rx"
    ROT_Y: str = "Box_Ry"
    ROT_Z: str = "Box_Rz"

@dataclass(frozen=True)
class VelocityCols:
    COM_V_PREFIX: str = "CoM_V"
    ANG_W_PREFIX: str = "AngVel_W"
    COM_VX: str = "CoM_Vx"
    COM_VY: str = "CoM_Vy"
    COM_VZ: str = "CoM_Vz"
    ANG_WX: str = "AngVel_Wx"
    ANG_WY: str = "AngVel_Wy"
    ANG_WZ: str = "AngVel_Wz"
    COM_V_NORM: str = "CoM_V_Norm"
    ANG_W_NORM: str = "AngVel_W_Norm"

@dataclass(frozen=True)
class CornerVelocityCols:
    VX_SUFFIX: str = "_Vx"
    VY_SUFFIX: str = "_Vy"
    VZ_SUFFIX: str = "_Vz"

@dataclass(frozen=True)
class CornerCoordCols:
    X_SUFFIX: str = "_X"
    Y_SUFFIX: str = "_Y"
    Z_SUFFIX: str = "_Z"

FACE_PREFIX_TO_INFO = {
    'F': 'Front',
    'B': 'Back',
    'L': 'Left',
    'R': 'Right',
    'T': 'Top',
    'FA': 'Front',
    'BA': 'Back'
}

@dataclass(frozen=True)
class AnalysisCols:
    COM_VX_ANA: str = "CoM_Vx_Ana"
    COM_VY_ANA: str = "CoM_Vy_Ana"
    COM_VZ_ANA: str = "CoM_Vz_Ana"
    ANG_WX_ANA: str = "AngVel_Wx_Ana"
    ANG_WY_ANA: str = "AngVel_Wy_Ana"
    ANG_WZ_ANA: str = "AngVel_Wz_Ana"
    COM_V_NORM_ANA: str = "CoM_V_Norm_Ana"
    ANG_W_NORM_ANA: str = "AngVel_W_Norm_Ana"
    FLOOR_N_X_ANA: str = "Floor_N_X_Ana"
    FLOOR_N_Y_ANA: str = "Floor_N_Y_Ana"
    FLOOR_N_Z_ANA: str = "Floor_N_Z_Ana"
    FLOOR_P_X_ANA: str = "Floor_P_X_Ana"
    FLOOR_P_Y_ANA: str = "Floor_P_Y_Ana"
    FLOOR_P_Z_ANA: str = "Floor_P_Z_Ana"

@dataclass(frozen=True)
class RelativeHeightCols:
    H_ANA_SUFFIX: str = "_H_Ana"


@dataclass(frozen=True)
class AnalysisInputHeightCols:
    AIH_ANA_SUFFIX: str = "_AIH_Ana"


# --- GUI Display Name Constants ---
@dataclass(frozen=True)
class DisplayNames:
    RB_CENTER: str = "Rigid Body Center"
    MARKER_PREFIX: str = "Marker "

# --- Multi-Header Constants ---
@dataclass(frozen=True)
class HeaderL1:
    POS: str = "Position"
    VEL: str = "Velocity"
    POSE: str = "Pose"
    INFO: str = "Info"
    ETC: str = "Etc"
    ANALYSIS: str = "Analysis"
    ANALYSIS_SCENARIO: str = "Analysis Scenario"

@dataclass(frozen=True)
class HeaderL2:
    RB: str = "RigidBody"
    COM: str = "CoM"
    ANG: str = "Angular"
    BOX_T: str = "BoxTranslation"
    BOX_R: str = "BoxRotation"
    FLOOR_N: str = "FloorNormal"
    FLOOR_P: str = "FloorPoint"
    FRAME: str = "Frame"
    TIME: str = "Time"
    POSE_SRC: str = "Pose"
    UNKNOWN: str = "Unknown"

@dataclass(frozen=True)
class HeaderL3:
    PX: str = "PX"
    PY: str = "PY"
    PZ: str = "PZ"
    VX: str = "VX"
    VY: str = "VY"
    VZ: str = "VZ"
    WX: str = "WX"
    WY: str = "WY"
    WZ: str = "WZ"
    TX: str = "TX"
    TY: str = "TY"
    TZ: str = "TZ"
    RX: str = "RX"
    RY: str = "RY"
    RZ: str = "RZ"
    NX: str = "NX"
    NY: str = "NY"
    NZ: str = "NZ"
    FACE: str = "FaceInfo"
    NUM: str = "Number"
    SEC: str = "s"
    TIME: str = "Time"
    SRC: str = "Source"
    NORM_V: str = "Norm_V"
    NORM_W: str = "Norm_W"
    REL_H: str = "RelativeHeight"
    ANALYSIS_INPUT_H: str = "AnalysisInputHeight"

# --- Result File Column Constants ---
RESULT_TIME_COL = (HeaderL1.INFO, HeaderL2.TIME, HeaderL3.TIME)

# List of columns to be displayed in the result analyzer's selection tree.
# This helps to avoid cluttering the view with too many options.
DISPLAY_RESULT_COLUMNS = [
    # Analysis results for Center of Mass (CoM) Velocity
    (HeaderL1.VEL, HeaderL2.COM, "VX_Ana"),
    (HeaderL1.VEL, HeaderL2.COM, "VY_Ana"),
    (HeaderL1.VEL, HeaderL2.COM, "VZ_Ana"),
    (HeaderL1.VEL, HeaderL2.COM, f"{HeaderL3.NORM_V}_Ana"),

    # Analysis results for Angular Velocity
    (HeaderL1.VEL, HeaderL2.COM, "WX_Ana"),
    (HeaderL1.VEL, HeaderL2.COM, "WY_Ana"),
    (HeaderL1.VEL, HeaderL2.COM, "WZ_Ana"),
    (HeaderL1.VEL, HeaderL2.COM, f"{HeaderL3.NORM_W}_Ana"),

    # Relative Height for each of the 8 corners
    (HeaderL1.ANALYSIS, "C1", HeaderL3.REL_H),
    (HeaderL1.ANALYSIS, "C2", HeaderL3.REL_H),
    (HeaderL1.ANALYSIS, "C3", HeaderL3.REL_H),
    (HeaderL1.ANALYSIS, "C4", HeaderL3.REL_H),
    (HeaderL1.ANALYSIS, "C5", HeaderL3.REL_H),
    (HeaderL1.ANALYSIS, "C6", HeaderL3.REL_H),
    (HeaderL1.ANALYSIS, "C7", HeaderL3.REL_H),
    (HeaderL1.ANALYSIS, "C8", HeaderL3.REL_H),

    # Corner Velocities for each of the 8 corners
    (HeaderL1.VEL, "C1", HeaderL3.VX),
    (HeaderL1.VEL, "C1", HeaderL3.VY),
    (HeaderL1.VEL, "C1", HeaderL3.VZ),
    (HeaderL1.VEL, "C2", HeaderL3.VX),
    (HeaderL1.VEL, "C2", HeaderL3.VY),
    (HeaderL1.VEL, "C2", HeaderL3.VZ),
    (HeaderL1.VEL, "C3", HeaderL3.VX),
    (HeaderL1.VEL, "C3", HeaderL3.VY),
    (HeaderL1.VEL, "C3", HeaderL3.VZ),
    (HeaderL1.VEL, "C4", HeaderL3.VX),
    (HeaderL1.VEL, "C4", HeaderL3.VY),
    (HeaderL1.VEL, "C4", HeaderL3.VZ),
    (HeaderL1.VEL, "C5", HeaderL3.VX),
    (HeaderL1.VEL, "C5", HeaderL3.VY),
    (HeaderL1.VEL, "C5", HeaderL3.VZ),
    (HeaderL1.VEL, "C6", HeaderL3.VX),
    (HeaderL1.VEL, "C6", HeaderL3.VY),
    (HeaderL1.VEL, "C6", HeaderL3.VZ),
    (HeaderL1.VEL, "C7", HeaderL3.VX),
    (HeaderL1.VEL, "C7", HeaderL3.VY),
    (HeaderL1.VEL, "C7", HeaderL3.VZ),
    (HeaderL1.VEL, "C8", HeaderL3.VX),
    (HeaderL1.VEL, "C8", HeaderL3.VY),
    (HeaderL1.VEL, "C8", HeaderL3.VZ),

    # Analysis Input Height for each of the 8 corners
    (HeaderL1.ANALYSIS_SCENARIO, "C1", HeaderL3.ANALYSIS_INPUT_H),
    (HeaderL1.ANALYSIS_SCENARIO, "C2", HeaderL3.ANALYSIS_INPUT_H),
    (HeaderL1.ANALYSIS_SCENARIO, "C3", HeaderL3.ANALYSIS_INPUT_H),
    (HeaderL1.ANALYSIS_SCENARIO, "C4", HeaderL3.ANALYSIS_INPUT_H),
    (HeaderL1.ANALYSIS_SCENARIO, "C5", HeaderL3.ANALYSIS_INPUT_H),
    (HeaderL1.ANALYSIS_SCENARIO, "C6", HeaderL3.ANALYSIS_INPUT_H),
    (HeaderL1.ANALYSIS_SCENARIO, "C7", HeaderL3.ANALYSIS_INPUT_H),
    (HeaderL1.ANALYSIS_SCENARIO, "C8", HeaderL3.ANALYSIS_INPUT_H),
]

# --- Corner Name Mapping ---
CORNER_NAME_MAP = {
    'C1': 'LeftBottomRear', 'C2': 'RightBottomRear', 'C3': 'RightTopRear', 'C4': 'LeftTopRear',
    'C5': 'LeftBottomFront', 'C6': 'RightBottomFront', 'C7': 'RightTopFront', 'C8': 'LeftTopFront'
}
