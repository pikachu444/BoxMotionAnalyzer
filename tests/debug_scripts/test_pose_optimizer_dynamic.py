import unittest
from unittest.mock import patch
import numpy as np
import pandas as pd
from src.analysis.pose_optimizer import PoseOptimizer, _calculate_local_corners
from src.config import config_app
from src.config.data_columns import RawMarkerCols, TimeCols, CornerCoordCols

class TestPoseOptimizerDynamic(unittest.TestCase):
    def test_dynamic_box_dims(self):
        # 1. Setup Stale Config (Simulate Import Time)
        stale_dims = np.array([100.0, 100.0, 100.0])
        stale_corners = _calculate_local_corners(stale_dims)

        # Face definitions (dummy)
        face_defs = {}

        optimizer = PoseOptimizer(face_defs, stale_corners)

        # 2. Setup Data
        # Single frame, no markers (optimization will return initial guess 0,0,0 if markers are missing?
        # No, code handles empty markers by adding empty result or skipping?
        # Code: if not markers: results.append(...); continue
        # So we need at least one marker to trigger optimization logic.
        # But we want to test _get_box_world_corners output.
        # If optimization runs, it produces 'world_corners'.

        # Let's provide a marker at (50, 50, 50) and see.
        df = pd.DataFrame({
            f"M1{RawMarkerCols.X_SUFFIX}": [50.0],
            f"M1{RawMarkerCols.Y_SUFFIX}": [50.0],
            f"M1{RawMarkerCols.Z_SUFFIX}": [50.0],
            f"M1{RawMarkerCols.FACEINFO_SUFFIX}": ["NONE"]
        })

        # 3. Update Global Config to "New Dims" (Simulate User Input)
        new_dims = np.array([200.0, 200.0, 200.0])

        # We need to patch config_app.BOX_DIMS
        with patch('src.config.config_app.BOX_DIMS', new_dims):
            result_df = optimizer.process(df)

        # 4. Verify Output
        # C1 is typically (-L/2, -W/2, -H/2) rotated + T.
        # If optimizer found T=center, and R=identity.
        # Let's check the distance between C1 and C2.
        # C1: (-hl, -hw, -hh), C2: (+hl, -hw, -hh). Distance = 2*hl = L.

        c1_x = result_df[f"C1{CornerCoordCols.X_SUFFIX}"].iloc[0]
        c2_x = result_df[f"C2{CornerCoordCols.X_SUFFIX}"].iloc[0]
        c1_y = result_df[f"C1{CornerCoordCols.Y_SUFFIX}"].iloc[0]
        c2_y = result_df[f"C2{CornerCoordCols.Y_SUFFIX}"].iloc[0]

        dist = np.linalg.norm([c1_x - c2_x, c1_y - c2_y])

        print(f"Distance between C1 and C2: {dist}")
        print(f"Expected Distance (New L): {new_dims[0]}")
        print(f"Stale Distance (Old L): {stale_dims[0]}")

        # Allow small floating point error
        self.assertTrue(np.isclose(dist, new_dims[0], atol=1.0),
                        f"Corner distance {dist} should match new dimension {new_dims[0]}, not stale {stale_dims[0]}")

if __name__ == '__main__':
    unittest.main()
