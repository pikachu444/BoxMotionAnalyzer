from dataclasses import dataclass
import re

import numpy as np
from scipy.spatial.transform import Rotation as R


@dataclass(frozen=True)
class DropSequenceSpec:
    id: str
    kind: str
    faces: tuple[int, ...] = ()
    height_rule: str = "standard"
    variant: str | None = None

class Scenarios:
    """
    ISTA-6A Drop Scenarios for SIOC (Ships In Own Container).
    Focuses on Type G (TV/Monitor < 150 lbs/68kg) and Type H (LTL).
    """

    CATEGORIES = ["ISTA 6A Type G (TV/Monitor Parcel)", "ISTA 6A Type H (LTL)"]
    TYPE_G_SEQUENCES = (
        DropSequenceSpec("01_Edge_3-4", "edge", (3, 4)),
        DropSequenceSpec("02_Edge_3-6", "edge", (3, 6)),
        DropSequenceSpec("03_Edge_4-6", "edge", (4, 6)),
        DropSequenceSpec("04_Corner_3-4-6", "corner", (3, 4, 6)),
        DropSequenceSpec("05_Corner_2-3-5", "corner", (2, 3, 5)),
        DropSequenceSpec("06_Edge_2-3", "edge", (2, 3)),
        DropSequenceSpec("07_Edge_1-2", "edge", (1, 2)),
        DropSequenceSpec("08_Face_3_Screen", "face", (3,)),
        DropSequenceSpec("09_Face_1_Rear", "face", (1,)),
        DropSequenceSpec("10_Face_5_Right", "face", (5,)),
        DropSequenceSpec("11_Face_6_Left", "face", (6,)),
        DropSequenceSpec("12_Face_4_Top", "face", (4,)),
        DropSequenceSpec("13_Face_2_Bottom", "face", (2,)),
        DropSequenceSpec("14_Edge_3-4_High", "edge", (3, 4), height_rule="high"),
        DropSequenceSpec("15_Edge_3-6_High", "edge", (3, 6), height_rule="high"),
        DropSequenceSpec("16_Corner_3-4-6_High", "corner", (3, 4, 6), height_rule="high"),
        DropSequenceSpec("17_Face_2_Bottom_High", "face", (2,), height_rule="high"),
    )
    TYPE_H_SEQUENCES = (
        DropSequenceSpec("01_Tip_Face_4_Screen", "tip", (4,), height_rule="tip"),
        DropSequenceSpec("02_Tip_Face_2_Rear", "tip", (2,), height_rule="tip"),
        DropSequenceSpec("03_Tip_Face_6_Left", "tip", (6,), height_rule="tip"),
        DropSequenceSpec("04_Tip_Face_5_Right", "tip", (5,), height_rule="tip"),
        DropSequenceSpec("05_RotationalEdge_BottomLong", "rotational_edge", (3,), height_rule="tip", variant="bottom_long"),
        DropSequenceSpec("06_RotationalEdge_BottomShort", "rotational_edge", (3,), height_rule="tip", variant="bottom_short"),
        DropSequenceSpec("07_Face_3_Bottom", "face", (3,)),
        DropSequenceSpec("08_Face_1_Top", "face", (1,)),
        DropSequenceSpec("09_Face_5_Right", "face", (5,)),
        DropSequenceSpec("10_Face_6_Left", "face", (6,)),
        DropSequenceSpec("11_Face_2_Rear", "face", (2,)),
        DropSequenceSpec("12_Face_4_Screen", "face", (4,)),
    )

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
    def get_drop_sequence_specs(category: str) -> list[DropSequenceSpec]:
        if "Type G" in category:
            return list(Scenarios.TYPE_G_SEQUENCES)
        if "Type H" in category:
            return list(Scenarios.TYPE_H_SEQUENCES)
        return []

    @staticmethod
    def get_drop_sequences(category: str) -> list:
        """Returns the display ids for the current category's drop sequences."""
        return [spec.id for spec in Scenarios.get_drop_sequence_specs(category)]

    @staticmethod
    def get_drop_sequence_spec(category: str, sequence) -> DropSequenceSpec | None:
        if isinstance(sequence, DropSequenceSpec):
            return sequence

        for spec in Scenarios.get_drop_sequence_specs(category):
            if spec.id == sequence:
                return spec

        normalized = Scenarios._normalize_sequence_name(str(sequence))
        for spec in Scenarios.get_drop_sequence_specs(category):
            if Scenarios._normalize_sequence_name(spec.id) == normalized:
                return spec
        return None

    @staticmethod
    def calculate_drop_height(category: str, sequence_name: str | DropSequenceSpec, mass_kg: float) -> float:
        """
        Dynamically calculates drop height (mm) based on ISTA rules and mass.
        Type G Threshold: 32kg (70 lbs). Type H uses different rules.
        """
        is_type_g = "Type G" in category
        spec = Scenarios.get_drop_sequence_spec(category, sequence_name)
        is_high_drop = spec is not None and spec.height_rule == "high"
        is_tip_or_rotational = spec is not None and spec.height_rule == "tip"

        if is_type_g:
            if mass_kg < 32.0:
                return 910.0 if is_high_drop else 460.0
            else:
                return 610.0 if is_high_drop else 300.0
        else:
            # Type H (LTL) Drops (300, 460, 810) depending on sequence and mass
            if is_tip_or_rotational:
                return 200.0
            if mass_kg < 32.0:
                return 810.0 if is_high_drop else 460.0
            else:
                return 460.0 if is_high_drop else 300.0

    @staticmethod
    def get_euler_angles(sequence_name: str | DropSequenceSpec, box_size: tuple, category: str = "Type G") -> tuple:
        """
        Returns (roll, pitch, yaw) in degrees to orient the box correctly.
        box_size: (w, h, d) mapping to (Local X, Local Y, Local Z)
        """
        spec = Scenarios.get_drop_sequence_spec(category, sequence_name)
        contact_normals = Scenarios._get_contact_normals(spec, sequence_name, box_size, category)
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
    def _get_contact_normals(
        sequence_spec: DropSequenceSpec | None,
        sequence_name: str | DropSequenceSpec,
        box_size: tuple,
        category: str,
    ) -> list[np.ndarray]:
        face_normals = Scenarios._face_normals_for_category(category)
        if sequence_spec is not None and sequence_spec.faces and sequence_spec.kind != "rotational_edge":
            return [face_normals[number] for number in sequence_spec.faces]

        normalized = Scenarios._normalize_sequence_name(str(sequence_name))
        bottom_face = 3 if "Type H" in category else 2
        screen_face = 4 if "Type H" in category else 3
        right_face = 5
        width, _, depth = box_size

        if sequence_spec is not None and sequence_spec.kind == "rotational_edge":
            variant = sequence_spec.variant
        elif "ROTATIONALEDGE_BOTTOMLONG" in normalized:
            variant = "bottom_long"
        elif "ROTATIONALEDGE_BOTTOMSHORT" in normalized:
            variant = "bottom_short"
        else:
            variant = None

        if variant == "bottom_long":
            side_face = screen_face if width >= depth else right_face
            return [face_normals[bottom_face], face_normals[side_face]]

        if variant == "bottom_short":
            side_face = right_face if width >= depth else screen_face
            return [face_normals[bottom_face], face_normals[side_face]]

        face_numbers = Scenarios._extract_face_numbers(str(sequence_name))
        if face_numbers:
            return [face_normals[number] for number in face_numbers]

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
