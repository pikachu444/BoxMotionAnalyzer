from dataclasses import dataclass

@dataclass(frozen=True)
class TimeCols:
    TIME: str = "Time"
    FRAME: str = "Frame"

@dataclass(frozen=True)
class RawMarkerCols:
    # Example raw marker column name: F_Marker_1_X
    # We will handle the dynamic part (e.g., "F_Marker_1") in the code,
    # but define the suffixes.
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
    COM_VX: str = "CoM_Vx"
    COM_VY: str = "CoM_Vy"
    COM_VZ: str = "CoM_Vz"
    ANG_WX: str = "AngVel_Wx"
    ANG_WY: str = "AngVel_Wy"
    ANG_WZ: str = "AngVel_Wz"

@dataclass(frozen=True)
class CornerVelocityCols:
    # Example corner velocity column: C0_Vx
    # The prefix (e.g., "C0") will be generated dynamically.
    VX_SUFFIX: str = "_Vx"
    VY_SUFFIX: str = "_Vy"
    VZ_SUFFIX: str = "_Vz"

FACE_PREFIX_TO_INFO = {
    'F': 'Front',
    'B': 'Back',
    'L': 'Left',
    'R': 'Right',
    'T': 'Top',
    'FA': 'Front-Aux',
    'BA': 'Back-Aux'
}

@dataclass(frozen=True)
class AnalysisCols:
    COM_VX_ANA: str = "CoM_Vx_Ana"
    COM_VY_ANA: str = "CoM_Vy_Ana"
    COM_VZ_ANA: str = "CoM_Vz_Ana"
    ANG_WX_ANA: str = "AngVel_Wx_Ana"
    ANG_WY_ANA: str = "AngVel_Wy_Ana"
    ANG_WZ_ANA: str = "AngVel_Wz_Ana"
    FLOOR_N_X_ANA: str = "Floor_N_X_Ana"
    FLOOR_N_Y_ANA: str = "Floor_N_Y_Ana"
    FLOOR_N_Z_ANA: str = "Floor_N_Z_Ana"
    FLOOR_P_X_ANA: str = "Floor_P_X_Ana"
    FLOOR_P_Y_ANA: str = "Floor_P_Y_Ana"
    FLOOR_P_Z_ANA: str = "Floor_P_Z_Ana"
