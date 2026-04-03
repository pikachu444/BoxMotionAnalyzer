import numpy as np
from scipy.spatial.transform import Rotation as R

class Scenarios:
    """
    ISTA-6A Drop Scenarios for SIOC (Ships In Own Container).
    Focuses on Type G (TV/Monitor < 150 lbs/68kg) and Type H (LTL).
    """

    CATEGORIES = ["ISTA 6A Type G (TV/Monitor Parcel)", "ISTA 6A Type H (LTL)"]

    # Target orientations mapping.
    # Tuple: (Roll, Pitch, Yaw) in degrees.
    # Note: These are rough approximations based on Box Local Frame where X=Width, Y=Height, Z=Depth.
    # The exact ISTA edge/corner numbering logic requires identifying the shortest/longest edges.
    # For a TV (W > Y > Z), standard orientation assumes it's sitting upright.
    # Flat Bottom (Face 3 usually) is [0, 0, 0].
    # Flat Back (Face 5) or Front (Face 6) requires pitching.
    FACES = {
        "Flat_Bottom": (0, 0, 0),
        "Flat_Top": (180, 0, 0),
        "Flat_Front": (90, 0, 0),  # Pitch 90
        "Flat_Back": (-90, 0, 0),
        "Flat_Left": (0, 0, 90),   # Yaw 90
        "Flat_Right": (0, 0, -90)
    }

    @staticmethod
    def get_categories():
        return Scenarios.CATEGORIES

    @staticmethod
    def get_drop_sequences(category: str) -> list:
        """Returns the list of 17 (Type G) or 12 (Type H) drop sequences."""
        if "Type G" in category:
            # Type G: 1:Rear, 2:Bottom, 3:Screen, 4:Top, 5:Right, 6:Left
            return [
                "01_Edge_3-4",          # Screen-Top
                "02_Edge_3-6",          # Screen-Left
                "03_Edge_4-6",          # Top-Left
                "04_Corner_3-4-6",      # Screen-Top-Left
                "05_Corner_2-3-5",      # Bottom-Screen-Right
                "06_Edge_2-3",          # Bottom-Screen
                "07_Edge_1-2",          # Rear-Bottom
                "08_Face_3_Screen",
                "09_Face_1_Rear",
                "10_Face_5_Right",
                "11_Face_6_Left",
                "12_Face_4_Top",
                "13_Face_2_Bottom",
                "14_Edge_3-4_High",
                "15_Edge_3-6_High",
                "16_Corner_3-4-6_High",
                "17_Face_2_Bottom_High"
            ]
        elif "Type H" in category:
            # Type H: 1:Top, 2:Rear, 3:Bottom, 4:Screen, 5:Right, 6:Left
            return [
                "01_Tip_Face_4_Screen",
                "02_Tip_Face_2_Rear",
                "03_Tip_Face_6_Left",
                "04_Tip_Face_5_Right",
                "05_RotationalEdge_BottomLong",
                "06_RotationalEdge_BottomShort",
                "07_Face_3_Bottom",
                "08_Face_1_Top",
                "09_Face_5_Right",
                "10_Face_6_Left",
                "11_Face_2_Rear",
                "12_Face_4_Screen"
            ]
        return []

    @staticmethod
    def calculate_drop_height(category: str, sequence_name: str, mass_kg: float) -> float:
        """
        Dynamically calculates drop height (mm) based on ISTA rules and mass.
        Type G Threshold: 32kg (70 lbs). Type H uses different rules.
        """
        is_type_g = "Type G" in category
        is_high_drop = "High" in sequence_name

        if is_type_g:
            if mass_kg < 32.0:
                return 910.0 if is_high_drop else 460.0
            else:
                return 610.0 if is_high_drop else 300.0
        else:
            # Type H (LTL) Drops (300, 460, 810) depending on sequence and mass
            # Simplified map based on user's guidance
            if "Tip" in sequence_name or "Rotational" in sequence_name:
                return 200.0 # Standard tip height approximation
            if mass_kg < 32.0:
                return 810.0 if is_high_drop else 460.0
            else:
                return 460.0 if is_high_drop else 300.0

    @staticmethod
    def get_euler_angles(sequence_name: str, box_size: tuple, category: str = "Type G") -> tuple:
        """
        Returns (roll, pitch, yaw) in degrees to orient the box correctly.
        box_size: (w, h, d) mapping to (Local X, Local Y, Local Z)
        """
        w, h, d = box_size

        if "Face 3" in sequence_name or "Bottom" in sequence_name and "Edge" not in sequence_name and "Corner" not in sequence_name:
            return Scenarios.FACES["Flat_Bottom"]
        elif "Face 1" in sequence_name or "Top" in sequence_name and "Edge" not in sequence_name:
            return Scenarios.FACES["Flat_Top"]
        elif "Face 5" in sequence_name or "Front" in sequence_name:
            return Scenarios.FACES["Flat_Front"]
        elif "Face 6" in sequence_name or "Back" in sequence_name:
            return Scenarios.FACES["Flat_Back"]
        elif "Face 2" in sequence_name or "Left" in sequence_name:
            return Scenarios.FACES["Flat_Left"]
        elif "Face 4" in sequence_name or "Right" in sequence_name:
            return Scenarios.FACES["Flat_Right"]

        elif "Corner 3-4-6" in sequence_name:
            # Approximate corner rotation
            pitch = np.degrees(np.arctan2(d, h))
            roll = np.degrees(np.arctan2(w, np.sqrt(d**2 + h**2)))
            return (roll, pitch, 0.0)

        elif "Corner 2-3-5" in sequence_name:
            pitch = np.degrees(np.arctan2(d, h))
            roll = -np.degrees(np.arctan2(w, np.sqrt(d**2 + h**2)))
            return (roll, pitch, 0.0)

        elif "Edge 3-4" in sequence_name or "Bottom-Long" in sequence_name:
            # Roll along the long edge (X axis)
            angle = np.degrees(np.arctan2(w, h))
            return (angle, 0.0, 0.0)

        elif "Edge 3-6" in sequence_name or "Bottom-Short" in sequence_name:
            # Pitch along short edge (Z axis)
            angle = np.degrees(np.arctan2(d, h))
            return (0.0, angle, 0.0)

        # Default fallback
        return (0.0, 0.0, 0.0)

    @staticmethod
    def get_orientation_from_euler(roll: float, pitch: float, yaw: float) -> list:
        """
        Returns quaternion [w, x, y, z] for given roll, pitch, yaw (in degrees).
        Uses 'xyz' rotation order.
        """
        r = R.from_euler('xyz', [roll, pitch, yaw], degrees=True)
        return Scenarios._scipy_to_mujoco_quat(r.as_quat())

    @staticmethod
    def _scipy_to_mujoco_quat(scipy_quat):
        """
        Scipy uses [x, y, z, w]. MuJoCo uses [w, x, y, z].
        """
        x, y, z, w = scipy_quat
        return [w, x, y, z]
