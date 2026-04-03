import re

import numpy as np
from scipy.spatial.transform import Rotation as R

class Scenarios:
    """
    ISTA-6A Drop Scenarios for SIOC (Ships In Own Container).
    Focuses on Type G (TV/Monitor < 150 lbs/68kg) and Type H (LTL).
    """

    CATEGORIES = ["ISTA 6A Type G (TV/Monitor Parcel)", "ISTA 6A Type H (LTL)"]

    # Local axes: X=Right(+), Y=Top(+), Z=Screen(+)
    TYPE_G_FACE_NORMALS = {
        1: np.array([0.0, 0.0, -1.0]),  # Rear
        2: np.array([0.0, -1.0, 0.0]),  # Bottom
        3: np.array([0.0, 0.0, 1.0]),   # Screen
        4: np.array([0.0, 1.0, 0.0]),   # Top
        5: np.array([1.0, 0.0, 0.0]),   # Right
        6: np.array([-1.0, 0.0, 0.0]),  # Left
    }
    TYPE_H_FACE_NORMALS = {
        1: np.array([0.0, 1.0, 0.0]),   # Top
        2: np.array([0.0, 0.0, -1.0]),  # Rear
        3: np.array([0.0, -1.0, 0.0]),  # Bottom
        4: np.array([0.0, 0.0, 1.0]),   # Screen
        5: np.array([1.0, 0.0, 0.0]),   # Right
        6: np.array([-1.0, 0.0, 0.0]),  # Left
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
        contact_normals = Scenarios._get_contact_normals(sequence_name, box_size, category)
        if not contact_normals:
            return (0.0, 0.0, 0.0)
        return Scenarios._get_euler_from_contact_normals(contact_normals)

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

    @staticmethod
    def _face_normals_for_category(category: str):
        return Scenarios.TYPE_H_FACE_NORMALS if "Type H" in category else Scenarios.TYPE_G_FACE_NORMALS

    @staticmethod
    def _normalize_sequence_name(sequence_name: str) -> str:
        return re.sub(r"[^A-Z0-9]+", "_", sequence_name.upper()).strip("_")

    @staticmethod
    def _extract_face_numbers(sequence_name: str) -> list[int]:
        normalized = Scenarios._normalize_sequence_name(sequence_name)
        match = re.search(r"(?:FACE|EDGE|CORNER)_([1-6](?:_[1-6]){0,2})", normalized)
        if not match:
            return []
        return [int(part) for part in match.group(1).split("_")]

    @staticmethod
    def _get_contact_normals(sequence_name: str, box_size: tuple, category: str) -> list[np.ndarray]:
        face_normals = Scenarios._face_normals_for_category(category)
        face_numbers = Scenarios._extract_face_numbers(sequence_name)
        if face_numbers:
            return [face_normals[number] for number in face_numbers]

        normalized = Scenarios._normalize_sequence_name(sequence_name)
        bottom_face = 3 if "Type H" in category else 2
        screen_face = 4 if "Type H" in category else 3
        right_face = 5
        width, _, depth = box_size

        if "ROTATIONALEDGE_BOTTOMLONG" in normalized:
            side_face = screen_face if width >= depth else right_face
            return [face_normals[bottom_face], face_normals[side_face]]

        if "ROTATIONALEDGE_BOTTOMSHORT" in normalized:
            side_face = right_face if width >= depth else screen_face
            return [face_normals[bottom_face], face_normals[side_face]]

        return []

    @staticmethod
    def _normalize_vector(vector: np.ndarray) -> np.ndarray:
        norm = np.linalg.norm(vector)
        if norm == 0:
            raise ValueError("Zero-length vector cannot be normalized.")
        return vector / norm

    @staticmethod
    def _canonicalize_axis(vector: np.ndarray) -> np.ndarray:
        for value in vector:
            if abs(value) > 1e-8:
                return vector if value > 0 else -vector
        return vector

    @staticmethod
    def _select_reference_axis(local_down: np.ndarray, normals: list[np.ndarray]) -> np.ndarray:
        if len(normals) > 1:
            for idx in range(len(normals)):
                for jdx in range(idx + 1, len(normals)):
                    axis = np.cross(normals[idx], normals[jdx])
                    if np.linalg.norm(axis) > 1e-8:
                        axis = axis - np.dot(axis, local_down) * local_down
                        if np.linalg.norm(axis) > 1e-8:
                            axis = Scenarios._canonicalize_axis(axis)
                            return Scenarios._normalize_vector(axis)

        candidates = [
            np.array([1.0, 0.0, 0.0]),
            np.array([0.0, 1.0, 0.0]),
            np.array([0.0, 0.0, 1.0]),
        ]
        best_axis = candidates[0]
        best_norm = -1.0
        for candidate in candidates:
            axis = candidate - np.dot(candidate, local_down) * local_down
            axis_norm = np.linalg.norm(axis)
            if axis_norm > best_norm:
                best_axis = axis
                best_norm = axis_norm
        best_axis = Scenarios._canonicalize_axis(best_axis)
        return Scenarios._normalize_vector(best_axis)

    @staticmethod
    def _get_euler_from_contact_normals(contact_normals: list[np.ndarray]) -> tuple:
        local_down = Scenarios._normalize_vector(np.sum(contact_normals, axis=0))
        local_x = Scenarios._select_reference_axis(local_down, contact_normals)
        local_up = -local_down
        local_y = Scenarios._normalize_vector(np.cross(local_up, local_x))

        local_basis = np.column_stack((local_x, local_y, local_up))
        world_basis = np.column_stack((
            np.array([1.0, 0.0, 0.0]),
            np.array([0.0, 1.0, 0.0]),
            np.array([0.0, 0.0, 1.0]),
        ))
        rotation = R.from_matrix(world_basis @ local_basis.T)
        euler = rotation.as_euler("xyz", degrees=True)

        normalized = []
        for angle in euler:
            wrapped = ((float(angle) + 180.0) % 360.0) - 180.0
            normalized.append(0.0 if abs(wrapped) < 1e-6 else wrapped)
        return tuple(normalized)
