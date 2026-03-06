from dataclasses import dataclass


@dataclass(frozen=True)
class TimeCols:
    TIME: str = "Time"
    FRAME: str = "Frame"


@dataclass(frozen=True)
class TimelineMetaCols:
    FULL_START_SEC: str = "Timeline_FullStartSec"
    FULL_END_SEC: str = "Timeline_FullEndSec"
    SLICE_START_SEC: str = "Timeline_SliceStartSec"
    SLICE_END_SEC: str = "Timeline_SliceEndSec"


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
    T_PREFIX: str = "P_T"
    R_PREFIX: str = "P_R"
    POS_X: str = "P_TX"
    POS_Y: str = "P_TY"
    POS_Z: str = "P_TZ"
    ROT_X: str = "P_RX"
    ROT_Y: str = "P_RY"
    ROT_Z: str = "P_RZ"


@dataclass(frozen=True)
class VelocityCols:
    T_V_PREFIX: str = "Global_V_T"
    T_A_PREFIX: str = "Global_A_T"
    R_V_PREFIX: str = "Global_V_R"
    R_A_PREFIX: str = "Global_A_R"
    T_VX: str = "Global_V_TX"
    T_VY: str = "Global_V_TY"
    T_VZ: str = "Global_V_TZ"
    T_AX: str = "Global_A_TX"
    T_AY: str = "Global_A_TY"
    T_AZ: str = "Global_A_TZ"
    R_VX: str = "Global_V_RX"
    R_VY: str = "Global_V_RY"
    R_VZ: str = "Global_V_RZ"
    R_AX: str = "Global_A_RX"
    R_AY: str = "Global_A_RY"
    R_AZ: str = "Global_A_RZ"
    T_V_NORM: str = "Global_V_T_Norm"
    R_V_NORM: str = "Global_V_R_Norm"
    T_A_NORM: str = "Global_A_T_Norm"
    R_A_NORM: str = "Global_A_R_Norm"


@dataclass(frozen=True)
class CornerVelocityCols:
    VX_SUFFIX: str = "_Global_V_TX"
    VY_SUFFIX: str = "_Global_V_TY"
    VZ_SUFFIX: str = "_Global_V_TZ"
    NORM_SUFFIX: str = "_Global_V_T_Norm"


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
    # Box local coordinate results.
    T_VX_ANA: str = "BoxLocal_V_TX"
    T_VY_ANA: str = "BoxLocal_V_TY"
    T_VZ_ANA: str = "BoxLocal_V_TZ"
    R_VX_ANA: str = "BoxLocal_V_RX"
    R_VY_ANA: str = "BoxLocal_V_RY"
    R_VZ_ANA: str = "BoxLocal_V_RZ"
    T_V_NORM_ANA: str = "BoxLocal_V_T_Norm"
    R_V_NORM_ANA: str = "BoxLocal_V_R_Norm"
    T_AX_ANA: str = "BoxLocal_A_TX"
    T_AY_ANA: str = "BoxLocal_A_TY"
    T_AZ_ANA: str = "BoxLocal_A_TZ"
    R_AX_ANA: str = "BoxLocal_A_RX"
    R_AY_ANA: str = "BoxLocal_A_RY"
    R_AZ_ANA: str = "BoxLocal_A_RZ"
    T_A_NORM_ANA: str = "BoxLocal_A_T_Norm"
    R_A_NORM_ANA: str = "BoxLocal_A_R_Norm"
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
    ACC: str = "Acceleration"
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
    # Backward-compatible aliases for legacy references.
    TRN: str = COM
    ROT: str = ANG
    BOX_R: str = "BoxRotation"
    FLOOR_N: str = "FloorNormal"
    FLOOR_P: str = "FloorPoint"
    FRAME: str = "Frame"
    TIME: str = "Time"
    TIMELINE: str = "Timeline"
    POSE_SRC: str = "Pose"
    UNKNOWN: str = "Unknown"


@dataclass(frozen=True)
class HeaderL3:
    # New result key schema
    P_TX: str = "P_TX"
    P_TY: str = "P_TY"
    P_TZ: str = "P_TZ"
    P_RX: str = "P_RX"
    P_RY: str = "P_RY"
    P_RZ: str = "P_RZ"
    V_TX: str = "Global_V_TX"
    V_TY: str = "Global_V_TY"
    V_TZ: str = "Global_V_TZ"
    V_RX: str = "Global_V_RX"
    V_RY: str = "Global_V_RY"
    V_RZ: str = "Global_V_RZ"
    A_TX: str = "Global_A_TX"
    A_TY: str = "Global_A_TY"
    A_TZ: str = "Global_A_TZ"
    A_RX: str = "Global_A_RX"
    A_RY: str = "Global_A_RY"
    A_RZ: str = "Global_A_RZ"
    V_TNORM: str = "Global_V_T_Norm"
    V_RNORM: str = "Global_V_R_Norm"
    A_TNORM: str = "Global_A_T_Norm"
    A_RNORM: str = "Global_A_R_Norm"
    V_TX_ANA: str = "BoxLocal_V_TX"
    V_TY_ANA: str = "BoxLocal_V_TY"
    V_TZ_ANA: str = "BoxLocal_V_TZ"
    V_RX_ANA: str = "BoxLocal_V_RX"
    V_RY_ANA: str = "BoxLocal_V_RY"
    V_RZ_ANA: str = "BoxLocal_V_RZ"
    V_TNORM_ANA: str = "BoxLocal_V_T_Norm"
    V_RNORM_ANA: str = "BoxLocal_V_R_Norm"
    A_TX_ANA: str = "BoxLocal_A_TX"
    A_TY_ANA: str = "BoxLocal_A_TY"
    A_TZ_ANA: str = "BoxLocal_A_TZ"
    A_RX_ANA: str = "BoxLocal_A_RX"
    A_RY_ANA: str = "BoxLocal_A_RY"
    A_RZ_ANA: str = "BoxLocal_A_RZ"
    A_TNORM_ANA: str = "BoxLocal_A_T_Norm"
    A_RNORM_ANA: str = "BoxLocal_A_R_Norm"

    # Timeline context metadata
    TL_FULL_START_SEC: str = "FullStartSec"
    TL_FULL_END_SEC: str = "FullEndSec"
    TL_SLICE_START_SEC: str = "SliceStartSec"
    TL_SLICE_END_SEC: str = "SliceEndSec"

    # Backward-compatible aliases used by existing code paths.
    PX: str = P_TX
    PY: str = P_TY
    PZ: str = P_TZ
    VX: str = V_TX
    VY: str = V_TY
    VZ: str = V_TZ
    WX: str = V_RX
    WY: str = V_RY
    WZ: str = V_RZ
    AX: str = A_TX
    AY: str = A_TY
    AZ: str = A_TZ
    TX: str = P_TX
    TY: str = P_TY
    TZ: str = P_TZ
    RX: str = P_RX
    RY: str = P_RY
    RZ: str = P_RZ
    NORM_V: str = V_TNORM
    NORM_W: str = V_RNORM
    NORM_A: str = A_TNORM
    VX_ANA: str = V_TX_ANA
    VY_ANA: str = V_TY_ANA
    VZ_ANA: str = V_TZ_ANA
    WX_ANA: str = V_RX_ANA
    WY_ANA: str = V_RY_ANA
    WZ_ANA: str = V_RZ_ANA
    NORM_V_ANA: str = V_TNORM_ANA
    NORM_W_ANA: str = V_RNORM_ANA

    NX: str = "NX"
    NY: str = "NY"
    NZ: str = "NZ"
    FACE: str = "FaceInfo"
    NUM: str = "Number"
    SEC: str = "s"
    TIME: str = "Time"
    SRC: str = "Source"
    REL_H: str = "RelativeHeight"
    ANALYSIS_INPUT_H: str = "AnalysisInputHeight"


# --- Result File Column Constants ---
RESULT_TIME_COL = (HeaderL1.INFO, HeaderL2.TIME, HeaderL3.TIME)
RESULT_TIMELINE_FULL_START_COL = (HeaderL1.INFO, HeaderL2.TIMELINE, HeaderL3.TL_FULL_START_SEC)
RESULT_TIMELINE_FULL_END_COL = (HeaderL1.INFO, HeaderL2.TIMELINE, HeaderL3.TL_FULL_END_SEC)
RESULT_TIMELINE_SLICE_START_COL = (HeaderL1.INFO, HeaderL2.TIMELINE, HeaderL3.TL_SLICE_START_SEC)
RESULT_TIMELINE_SLICE_END_COL = (HeaderL1.INFO, HeaderL2.TIMELINE, HeaderL3.TL_SLICE_END_SEC)


# List of columns to be displayed in the result analyzer's selection tree.
# This helps to avoid cluttering the view with too many options.
DISPLAY_RESULT_COLUMNS = [
    # CoM Position (translation + rotation)
    (HeaderL1.POS, HeaderL2.COM, HeaderL3.P_TX),
    (HeaderL1.POS, HeaderL2.COM, HeaderL3.P_TY),
    (HeaderL1.POS, HeaderL2.COM, HeaderL3.P_TZ),
    (HeaderL1.POS, HeaderL2.COM, HeaderL3.P_RX),
    (HeaderL1.POS, HeaderL2.COM, HeaderL3.P_RY),
    (HeaderL1.POS, HeaderL2.COM, HeaderL3.P_RZ),

    # Corner Positions for each of the 8 corners (translation only)
    (HeaderL1.POS, "C1", HeaderL3.P_TX),
    (HeaderL1.POS, "C1", HeaderL3.P_TY),
    (HeaderL1.POS, "C1", HeaderL3.P_TZ),
    (HeaderL1.POS, "C2", HeaderL3.P_TX),
    (HeaderL1.POS, "C2", HeaderL3.P_TY),
    (HeaderL1.POS, "C2", HeaderL3.P_TZ),
    (HeaderL1.POS, "C3", HeaderL3.P_TX),
    (HeaderL1.POS, "C3", HeaderL3.P_TY),
    (HeaderL1.POS, "C3", HeaderL3.P_TZ),
    (HeaderL1.POS, "C4", HeaderL3.P_TX),
    (HeaderL1.POS, "C4", HeaderL3.P_TY),
    (HeaderL1.POS, "C4", HeaderL3.P_TZ),
    (HeaderL1.POS, "C5", HeaderL3.P_TX),
    (HeaderL1.POS, "C5", HeaderL3.P_TY),
    (HeaderL1.POS, "C5", HeaderL3.P_TZ),
    (HeaderL1.POS, "C6", HeaderL3.P_TX),
    (HeaderL1.POS, "C6", HeaderL3.P_TY),
    (HeaderL1.POS, "C6", HeaderL3.P_TZ),
    (HeaderL1.POS, "C7", HeaderL3.P_TX),
    (HeaderL1.POS, "C7", HeaderL3.P_TY),
    (HeaderL1.POS, "C7", HeaderL3.P_TZ),
    (HeaderL1.POS, "C8", HeaderL3.P_TX),
    (HeaderL1.POS, "C8", HeaderL3.P_TY),
    (HeaderL1.POS, "C8", HeaderL3.P_TZ),

    # CoM Velocities: BoxLocal first, then Global
    (HeaderL1.VEL, HeaderL2.COM, HeaderL3.V_TX_ANA),
    (HeaderL1.VEL, HeaderL2.COM, HeaderL3.V_TY_ANA),
    (HeaderL1.VEL, HeaderL2.COM, HeaderL3.V_TZ_ANA),
    (HeaderL1.VEL, HeaderL2.COM, HeaderL3.V_TNORM_ANA),
    (HeaderL1.VEL, HeaderL2.COM, HeaderL3.V_RX_ANA),
    (HeaderL1.VEL, HeaderL2.COM, HeaderL3.V_RY_ANA),
    (HeaderL1.VEL, HeaderL2.COM, HeaderL3.V_RZ_ANA),
    (HeaderL1.VEL, HeaderL2.COM, HeaderL3.V_RNORM_ANA),
    (HeaderL1.VEL, HeaderL2.COM, HeaderL3.V_TX),
    (HeaderL1.VEL, HeaderL2.COM, HeaderL3.V_TY),
    (HeaderL1.VEL, HeaderL2.COM, HeaderL3.V_TZ),
    (HeaderL1.VEL, HeaderL2.COM, HeaderL3.V_TNORM),
    (HeaderL1.VEL, HeaderL2.COM, HeaderL3.V_RX),
    (HeaderL1.VEL, HeaderL2.COM, HeaderL3.V_RY),
    (HeaderL1.VEL, HeaderL2.COM, HeaderL3.V_RZ),
    (HeaderL1.VEL, HeaderL2.COM, HeaderL3.V_RNORM),

    # CoM Accelerations: BoxLocal first, then Global
    (HeaderL1.ACC, HeaderL2.COM, HeaderL3.A_TX_ANA),
    (HeaderL1.ACC, HeaderL2.COM, HeaderL3.A_TY_ANA),
    (HeaderL1.ACC, HeaderL2.COM, HeaderL3.A_TZ_ANA),
    (HeaderL1.ACC, HeaderL2.COM, HeaderL3.A_TNORM_ANA),
    (HeaderL1.ACC, HeaderL2.COM, HeaderL3.A_RX_ANA),
    (HeaderL1.ACC, HeaderL2.COM, HeaderL3.A_RY_ANA),
    (HeaderL1.ACC, HeaderL2.COM, HeaderL3.A_RZ_ANA),
    (HeaderL1.ACC, HeaderL2.COM, HeaderL3.A_RNORM_ANA),
    (HeaderL1.ACC, HeaderL2.COM, HeaderL3.A_TX),
    (HeaderL1.ACC, HeaderL2.COM, HeaderL3.A_TY),
    (HeaderL1.ACC, HeaderL2.COM, HeaderL3.A_TZ),
    (HeaderL1.ACC, HeaderL2.COM, HeaderL3.A_TNORM),
    (HeaderL1.ACC, HeaderL2.COM, HeaderL3.A_RX),
    (HeaderL1.ACC, HeaderL2.COM, HeaderL3.A_RY),
    (HeaderL1.ACC, HeaderL2.COM, HeaderL3.A_RZ),
    (HeaderL1.ACC, HeaderL2.COM, HeaderL3.A_RNORM),

    # Relative Height for each of the 8 corners
    (HeaderL1.ANALYSIS, "C1", HeaderL3.REL_H),
    (HeaderL1.ANALYSIS, "C2", HeaderL3.REL_H),
    (HeaderL1.ANALYSIS, "C3", HeaderL3.REL_H),
    (HeaderL1.ANALYSIS, "C4", HeaderL3.REL_H),
    (HeaderL1.ANALYSIS, "C5", HeaderL3.REL_H),
    (HeaderL1.ANALYSIS, "C6", HeaderL3.REL_H),
    (HeaderL1.ANALYSIS, "C7", HeaderL3.REL_H),
    (HeaderL1.ANALYSIS, "C8", HeaderL3.REL_H),

    # Corner Velocities for each of the 8 corners (translation + norm)
    (HeaderL1.VEL, "C1", HeaderL3.V_TX),
    (HeaderL1.VEL, "C1", HeaderL3.V_TY),
    (HeaderL1.VEL, "C1", HeaderL3.V_TZ),
    (HeaderL1.VEL, "C1", HeaderL3.V_TNORM),
    (HeaderL1.VEL, "C2", HeaderL3.V_TX),
    (HeaderL1.VEL, "C2", HeaderL3.V_TY),
    (HeaderL1.VEL, "C2", HeaderL3.V_TZ),
    (HeaderL1.VEL, "C2", HeaderL3.V_TNORM),
    (HeaderL1.VEL, "C3", HeaderL3.V_TX),
    (HeaderL1.VEL, "C3", HeaderL3.V_TY),
    (HeaderL1.VEL, "C3", HeaderL3.V_TZ),
    (HeaderL1.VEL, "C3", HeaderL3.V_TNORM),
    (HeaderL1.VEL, "C4", HeaderL3.V_TX),
    (HeaderL1.VEL, "C4", HeaderL3.V_TY),
    (HeaderL1.VEL, "C4", HeaderL3.V_TZ),
    (HeaderL1.VEL, "C4", HeaderL3.V_TNORM),
    (HeaderL1.VEL, "C5", HeaderL3.V_TX),
    (HeaderL1.VEL, "C5", HeaderL3.V_TY),
    (HeaderL1.VEL, "C5", HeaderL3.V_TZ),
    (HeaderL1.VEL, "C5", HeaderL3.V_TNORM),
    (HeaderL1.VEL, "C6", HeaderL3.V_TX),
    (HeaderL1.VEL, "C6", HeaderL3.V_TY),
    (HeaderL1.VEL, "C6", HeaderL3.V_TZ),
    (HeaderL1.VEL, "C6", HeaderL3.V_TNORM),
    (HeaderL1.VEL, "C7", HeaderL3.V_TX),
    (HeaderL1.VEL, "C7", HeaderL3.V_TY),
    (HeaderL1.VEL, "C7", HeaderL3.V_TZ),
    (HeaderL1.VEL, "C7", HeaderL3.V_TNORM),
    (HeaderL1.VEL, "C8", HeaderL3.V_TX),
    (HeaderL1.VEL, "C8", HeaderL3.V_TY),
    (HeaderL1.VEL, "C8", HeaderL3.V_TZ),
    (HeaderL1.VEL, "C8", HeaderL3.V_TNORM),

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
