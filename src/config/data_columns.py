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
    Q_PREFIX: str = "Box_Q"
    POS_X: str = "Box_Tx"
    POS_Y: str = "Box_Ty"
    POS_Z: str = "Box_Tz"
    ROT_X: str = "Box_Rx"
    ROT_Y: str = "Box_Ry"
    ROT_Z: str = "Box_Rz"
    QUAT_X: str = "Box_Qx"
    QUAT_Y: str = "Box_Qy"
    QUAT_Z: str = "Box_Qz"
    QUAT_W: str = "Box_Qw"

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
    C1_VX: str = "C1_Vx"
    C1_VY: str = "C1_Vy"
    C1_VZ: str = "C1_Vz"
    C2_VX: str = "C2_Vx"
    C2_VY: str = "C2_Vy"
    C2_VZ: str = "C2_Vz"
    C3_VX: str = "C3_Vx"
    C3_VY: str = "C3_Vy"
    C3_VZ: str = "C3_Vz"
    C4_VX: str = "C4_Vx"
    C4_VY: str = "C4_Vy"
    C4_VZ: str = "C4_Vz"
    C5_VX: str = "C5_Vx"
    C5_VY: str = "C5_Vy"
    C5_VZ: str = "C5_Vz"
    C6_VX: str = "C6_Vx"
    C6_VY: str = "C6_Vy"
    C6_VZ: str = "C6_Vz"
    C7_VX: str = "C7_Vx"
    C7_VY: str = "C7_Vy"
    C7_VZ: str = "C7_Vz"
    C8_VX: str = "C8_Vx"
    C8_VY: str = "C8_Vy"
    C8_VZ: str = "C8_Vz"

@dataclass(frozen=True)
class CornerCoordCols:
    C1_X: str = "C1_X"
    C1_Y: str = "C1_Y"
    C1_Z: str = "C1_Z"
    C2_X: str = "C2_X"
    C2_Y: str = "C2_Y"
    C2_Z: str = "C2_Z"
    C3_X: str = "C3_X"
    C3_Y: str = "C3_Y"
    C3_Z: str = "C3_Z"
    C4_X: str = "C4_X"
    C4_Y: str = "C4_Y"
    C4_Z: str = "C4_Z"
    C5_X: str = "C5_X"
    C5_Y: str = "C5_Y"
    C5_Z: str = "C5_Z"
    C6_X: str = "C6_X"
    C6_Y: str = "C6_Y"
    C6_Z: str = "C6_Z"
    C7_X: str = "C7_X"
    C7_Y: str = "C7_Y"
    C7_Z: str = "C7_Z"
    C8_X: str = "C8_X"
    C8_Y: str = "C8_Y"
    C8_Z: str = "C8_Z"

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
    C1_H_ANA: str = "C1_H_Ana"
    C2_H_ANA: str = "C2_H_Ana"
    C3_H_ANA: str = "C3_H_Ana"
    C4_H_ANA: str = "C4_H_Ana"
    C5_H_ANA: str = "C5_H_Ana"
    C6_H_ANA: str = "C6_H_Ana"
    C7_H_ANA: str = "C7_H_Ana"
    C8_H_ANA: str = "C8_H_Ana"

# --- Multi-Header Constants ---
@dataclass(frozen=True)
class HeaderL1:
    POS: str = "Position"
    VEL: str = "Velocity"
    POSE: str = "Pose"
    INFO: str = "Info"
    ETC: str = "Etc"
    ANALYSIS: str = "Analysis"

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
    SRC: str = "Source"
    NORM_V: str = "Norm_V"
    NORM_W: str = "Norm_W"
    REL_H: str = "RelativeHeight"
