import unittest

import numpy as np
import pandas as pd

from src.analysis.pipeline.resampler import UniformResampler
from src.config.data_columns import TimeCols


class TestUniformResampler(unittest.TestCase):
    def test_resampler_creates_uniform_grid_and_reindexes_frames(self):
        df = pd.DataFrame(
            {
                TimeCols.FRAME: [10, 11, 12],
                "RigidBody_Position_X": [0.0, 10.0, 20.0],
                "Marker_FaceInfo": ["TOP", "TOP", "TOP"],
            },
            index=pd.Index([0.0, 0.1, 0.2], name=TimeCols.TIME),
        )

        result = UniformResampler(factor=2).process(df)

        self.assertEqual(len(result), 5)
        np.testing.assert_allclose(result.index.to_numpy(), np.array([0.0, 0.05, 0.1, 0.15, 0.2]))
        np.testing.assert_array_equal(result[TimeCols.FRAME].to_numpy(), np.arange(5))
        np.testing.assert_allclose(result["RigidBody_Position_X"].to_numpy(), np.array([0.0, 5.0, 10.0, 15.0, 20.0]))
        self.assertEqual(result["Marker_FaceInfo"].isna().sum(), 0)
        self.assertTrue((result["Marker_FaceInfo"] == "TOP").all())


if __name__ == "__main__":
    unittest.main()
