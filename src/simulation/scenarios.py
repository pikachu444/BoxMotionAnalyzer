import numpy as np
from scipy.spatial.transform import Rotation as R

class Scenarios:
    """
    ISTA-6A Drop Scenarios for Parcel and LTL.
    Provides standard drop heights and orientations.
    """

    # Drop heights in mm
    HEIGHTS = {
        "Parcel_Light": 970,  # < 9.1kg (20lb)
        "Parcel_Medium": 810, # 9.1kg ~ 18.1kg (40lb)
        "Parcel_Heavy": 610,  # 18.1kg ~ 31.8kg (70lb)
        "LTL": 460            # Large items, standard drop height
    }

    @staticmethod
    def get_drop_height(category: str) -> float:
        """Returns the drop height in mm based on category."""
        return Scenarios.HEIGHTS.get(category, 810)

    @staticmethod
    def get_orientation(drop_type: str, box_size: tuple) -> list:
        """
        Returns quaternion [w, x, y, z] for a specific drop type.
        box_size: (width, depth, height) in mm
        drop_type: "Flat_Bottom", "Flat_Top", "Flat_Front", "Flat_Back", "Flat_Left", "Flat_Right",
                   "Edge_Bottom_Front", "Corner_Bottom_Front_Left", "Custom"
        """
        w, d, h = box_size

        # Default identity rotation
        quat = [1.0, 0.0, 0.0, 0.0]

        if drop_type == "Flat_Bottom":
            quat = [1.0, 0.0, 0.0, 0.0]
        elif drop_type == "Flat_Top":
            # 180 deg around X
            r = R.from_euler('x', 180, degrees=True)
            quat = Scenarios._scipy_to_mujoco_quat(r.as_quat())
        elif drop_type == "Flat_Front":
            # 90 deg around X
            r = R.from_euler('x', 90, degrees=True)
            quat = Scenarios._scipy_to_mujoco_quat(r.as_quat())
        elif drop_type == "Flat_Back":
            # -90 deg around X
            r = R.from_euler('x', -90, degrees=True)
            quat = Scenarios._scipy_to_mujoco_quat(r.as_quat())
        elif drop_type == "Flat_Left":
            # 90 deg around Y
            r = R.from_euler('y', 90, degrees=True)
            quat = Scenarios._scipy_to_mujoco_quat(r.as_quat())
        elif drop_type == "Flat_Right":
            # -90 deg around Y
            r = R.from_euler('y', -90, degrees=True)
            quat = Scenarios._scipy_to_mujoco_quat(r.as_quat())
        elif drop_type == "Edge_Bottom_Front":
            # Rotate such that the bottom-front edge hits first
            # We tilt around X axis by some angle so CG is over edge
            angle = np.degrees(np.arctan2(d, h))
            r = R.from_euler('x', angle, degrees=True)
            quat = Scenarios._scipy_to_mujoco_quat(r.as_quat())
        elif drop_type == "Corner_Bottom_Front_Left":
            # Rotate such that the bottom-front-left corner hits first
            # 1. Tilt around X (pitch) to balance CG over front edge
            pitch = np.degrees(np.arctan2(d, h))
            # 2. Tilt around Y (roll) to balance CG over corner
            roll = np.degrees(np.arctan2(w, np.sqrt(d**2 + h**2)))

            r = R.from_euler('xy', [pitch, roll], degrees=True)
            quat = Scenarios._scipy_to_mujoco_quat(r.as_quat())
        else:
            # Custom or unsupported
            pass

        return quat

    @staticmethod
    def custom_orientation(roll: float, pitch: float, yaw: float) -> list:
        """
        Returns quaternion [w, x, y, z] for custom roll, pitch, yaw (in degrees).
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
