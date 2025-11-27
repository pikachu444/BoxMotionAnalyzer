import unittest
import pandas as pd
import numpy as np
import os
from src.visualization.data_handler import DataHandler
from src.visualization import config
from src.config.data_columns import TimeCols, RigidBodyCols

class TestVisualizationIntegration(unittest.TestCase):
    def setUp(self):
        self.handler = DataHandler()
        self.test_csv_path = "test_analysis_result.csv"
        
        # Create a mock analysis result CSV
        # Columns: Time, RigidBody_Position_X/Y/Z, C1_X/Y/Z, ...
        data = {
            TimeCols.TIME: [0.0, 0.1, 0.2],
            RigidBodyCols.POS_X: [100, 101, 102],
            RigidBodyCols.POS_Y: [200, 201, 202],
            RigidBodyCols.POS_Z: [300, 301, 302],
            "C1_X": [10, 11, 12],
            "C1_Y": [20, 21, 22],
            "C1_Z": [30, 31, 32],
            "MK_BTM_1_X": [1, 2, 3],
            "MK_BTM_1_Y": [4, 5, 6],
            "MK_BTM_1_Z": [7, 8, 9]
        }
        self.df = pd.DataFrame(data)
        self.df.to_csv(self.test_csv_path, index=False)

    def tearDown(self):
        if os.path.exists(self.test_csv_path):
            os.remove(self.test_csv_path)

    def test_load_analysis_result(self):
        success = self.handler.load_analysis_result(self.test_csv_path)
        self.assertTrue(success, "Failed to load analysis result")
        
        # Check basic properties
        self.assertEqual(self.handler.n_frames, 3)
        
        # Check object IDs
        # Should include RigidBody_Position, C1, MK_BTM_1
        # RigidBodyCols.POS_X is "RigidBody_Position_X" -> ID "RigidBody_Position"
        expected_ids = ["RigidBody_Position", "C1", "MK_BTM_1"]
        for eid in expected_ids:
            self.assertIn(eid, self.handler.object_ids)
            
        # Check data content for C1 at frame 0
        c1_data = self.handler.get_object_timeseries("C1")
        self.assertIsNotNone(c1_data)
        self.assertEqual(len(c1_data), 3)
        
        # Check values using config constants
        # config.DF_POS_X should be RigidBodyCols.POS_X ("RigidBody_Position_X")
        # But wait, in DataHandler we renamed 'pos_x' to config.DF_POS_X.
        # So the column name in the long dataframe should be "RigidBody_Position_X".
        
        self.assertIn(config.DF_POS_X, c1_data.columns)
        self.assertEqual(c1_data.iloc[0][config.DF_POS_X], 10) # C1_X at frame 0
        
        # Check RigidBody data
        rb_data = self.handler.get_object_timeseries("RigidBody_Position")
        self.assertEqual(rb_data.iloc[0][config.DF_POS_X], 100)

if __name__ == '__main__':
    unittest.main()
