import unittest

from src.config import config_app, config_visualization


class TestCoordinateConfigConsistency(unittest.TestCase):
    def test_visualization_faces_match_app_face_definitions(self):
        expected = {
            label: tuple(face["corners"])
            for label, face in config_app.FACE_DEFINITIONS.items()
        }
        actual = {
            face["label"]: tuple(face["corner_indices"])
            for face in config_visualization.BOX_FACES
        }
        self.assertEqual(actual, expected)


if __name__ == "__main__":
    unittest.main()
