import unittest

import numpy as np
from scipy.spatial.transform import Rotation as R

from src.simulation.scenarios import Scenarios


TYPE_G = "ISTA 6A Type G (TV/Monitor Parcel)"
TYPE_H = "ISTA 6A Type H (LTL)"


class TestSimulationScenarios(unittest.TestCase):
    def test_sequence_registry_matches_ui_sequence_ids(self):
        type_g_specs = Scenarios.get_drop_sequence_specs(TYPE_G)
        type_h_specs = Scenarios.get_drop_sequence_specs(TYPE_H)

        self.assertEqual([spec.id for spec in type_g_specs], Scenarios.get_drop_sequences(TYPE_G))
        self.assertEqual([spec.id for spec in type_h_specs], Scenarios.get_drop_sequences(TYPE_H))
        self.assertEqual(len(type_g_specs), 17)
        self.assertEqual(len(type_h_specs), 12)

    def test_sequence_lookup_returns_structured_metadata(self):
        spec = Scenarios.get_drop_sequence_spec(TYPE_G, "08_Face_3_Screen_High")
        self.assertIsNotNone(spec)
        self.assertEqual(spec.kind, "face")
        self.assertEqual(spec.faces, (3,))
        self.assertEqual(spec.height_rule, "high")

    def _assert_target_vector_points_down(self, sequence_name, category, box_size, target_vector):
        roll, pitch, yaw = Scenarios.get_euler_angles(sequence_name, box_size, category=category)
        quat = Scenarios.get_orientation_from_euler(roll, pitch, yaw)
        rotation = R.from_quat([quat[1], quat[2], quat[3], quat[0]])
        local_target = np.array(target_vector, dtype=float)
        local_target = local_target / np.linalg.norm(local_target)
        world_contact = rotation.apply(local_target)

        np.testing.assert_allclose(world_contact, np.array([0.0, 0.0, -1.0]), atol=1e-6)

    def test_type_g_ui_face_sequence_uses_actual_face_numbering(self):
        box_size = (1578.0, 930.0, 142.0)
        self._assert_target_vector_points_down(
            "17_Hazard_Face2_Default",
            TYPE_G,
            box_size,
            (0.0, -930.0, 0.0),
        )
        self._assert_target_vector_points_down(
            "08_Face_3_Screen_High",
            TYPE_G,
            box_size,
            (0.0, 0.0, 142.0),
        )

    def test_type_g_edge_and_corner_sequences_use_dimension_weighted_tilt(self):
        box_size = (1578.0, 930.0, 142.0)
        edge_angles = Scenarios.get_euler_angles("01_Edge_3-4", box_size, category=TYPE_G)
        corner_angles = Scenarios.get_euler_angles("04_Corner_3-4-6", box_size, category=TYPE_G)
        second_corner_angles = Scenarios.get_euler_angles("14_Corner_1-2-6", box_size, category=TYPE_G)

        self.assertNotEqual(edge_angles, (0.0, 0.0, 0.0))
        self.assertNotEqual(corner_angles, (0.0, 0.0, 0.0))
        self.assertNotEqual(corner_angles, second_corner_angles)

        self._assert_target_vector_points_down(
            "01_Edge_3-4",
            TYPE_G,
            box_size,
            (0.0, 930.0, 142.0),
        )
        self._assert_target_vector_points_down(
            "04_Corner_3-4-6",
            TYPE_G,
            box_size,
            (-1578.0, 930.0, 142.0),
        )

    def test_type_h_sequences_use_different_face_numbering(self):
        box_size = (1578.0, 930.0, 142.0)
        top_angles = Scenarios.get_euler_angles("08_Face_1_Top", box_size, category=TYPE_H)
        rear_angles = Scenarios.get_euler_angles("11_Face_2_Rear", box_size, category=TYPE_H)

        self.assertNotEqual(top_angles, rear_angles)

        self._assert_target_vector_points_down(
            "08_Face_1_Top",
            TYPE_H,
            box_size,
            (0.0, 1.0, 0.0),
        )
        self._assert_target_vector_points_down(
            "11_Face_2_Rear",
            TYPE_H,
            box_size,
            (0.0, 0.0, -1.0),
        )

    def test_rotational_edge_sequences_follow_box_aspect_ratio(self):
        wide_box = (1578.0, 930.0, 142.0)
        deep_box = (142.0, 930.0, 1578.0)

        wide_long = Scenarios.get_euler_angles("05_RotationalEdge_BottomLong", wide_box, category=TYPE_H)
        wide_short = Scenarios.get_euler_angles("06_RotationalEdge_BottomShort", wide_box, category=TYPE_H)
        deep_long = Scenarios.get_euler_angles("05_RotationalEdge_BottomLong", deep_box, category=TYPE_H)

        self.assertNotEqual(wide_long, wide_short)
        self.assertNotEqual(wide_long, deep_long)

    def test_drop_height_still_depends_on_mass_and_sequence(self):
        self.assertEqual(
            Scenarios.calculate_drop_height(TYPE_G, "01_Edge_3-4", 25.0),
            460.0,
        )
        self.assertEqual(
            Scenarios.calculate_drop_height(TYPE_G, "08_Face_3_Screen_High", 25.0),
            910.0,
        )
        self.assertEqual(
            Scenarios.calculate_drop_height(TYPE_G, "16_Flat_MostCritical_DefaultFace6_High", 40.0),
            610.0,
        )
        self.assertEqual(
            Scenarios.calculate_drop_height(TYPE_H, "01_Tip_Face_4_Screen", 80.0),
            200.0,
        )


if __name__ == "__main__":
    unittest.main()
