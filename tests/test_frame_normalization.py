import unittest
import pandas as pd
import os
from src.visualization.data_handler import DataHandler
from src.config.data_columns import HeaderL1, HeaderL2, HeaderL3

class TestFrameNormalization(unittest.TestCase):
    def setUp(self):
        self.test_csv_path = "data/test_frame_offset.csv"
        os.makedirs("data", exist_ok=True)

    def tearDown(self):
        if os.path.exists(self.test_csv_path):
            os.remove(self.test_csv_path)

    def test_frame_starts_at_zero(self):
        """
        Creates a CSV with frames 100, 101, 102.
        Verifies that DataHandler normalizes them to 0, 1, 2.
        """
        # Construct MultiIndex columns
        cols = pd.MultiIndex.from_tuples([
            (HeaderL1.INFO, HeaderL2.FRAME, HeaderL3.NUM),
            (HeaderL1.INFO, HeaderL2.TIME, HeaderL3.TIME),
            (HeaderL1.POS, 'C1', HeaderL3.PX),
            (HeaderL1.POS, 'C1', HeaderL3.PY),
            (HeaderL1.POS, 'C1', HeaderL3.PZ)
        ])

        # Frames start at 100
        data = [
            [100, 0.0, 1.0, 0, 0],
            [101, 0.1, 1.1, 0, 0],
            [102, 0.2, 1.2, 0, 0]
        ]

        df = pd.DataFrame(data, columns=cols)
        df.to_csv(self.test_csv_path, index=False)

        handler = DataHandler()
        success = handler.load_analysis_result(self.test_csv_path)

        self.assertTrue(success, "Failed to load CSV")

        # Check loaded dataframe frames
        loaded_frames = handler.visualization_dataframe['Frame'] # Config mapping
        self.assertEqual(loaded_frames.min(), 0, "Frames did not start at 0")
        self.assertEqual(loaded_frames.max(), 2, "Frames max is incorrect")
        self.assertEqual(handler.n_frames, 3, "n_frames is incorrect")

if __name__ == '__main__':
    unittest.main()
