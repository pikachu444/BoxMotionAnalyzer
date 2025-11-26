import pandas as pd
import numpy as np
import sys

# Add src directory to path to allow imports from project root
sys.path.insert(0, './')

from src.data_loader import DataLoader
from src.analysis.parser import Parser
from src.analysis.pose_optimizer import PoseOptimizer
from src.analysis.velocity_calculator import VelocityCalculator
from src.analysis.frame_analyzer import FrameAnalyzer
from src.config import config_app
from src.config.data_columns import RelativeHeightCols, FACE_PREFIX_TO_INFO

def run_real_data_test():
    """
    Loads a real CSV file and runs it through the full analysis pipeline
    to verify the final output contains the relative height columns.
    """
    print("--- Testing Pipeline with Real Data (small_test.csv) ---")

    # 1. Load Data
    print("Loading data...")
    loader = DataLoader()
    try:
        header_info, raw_data = loader.load_csv("TestSets/small_test.csv")
    except FileNotFoundError as e:
        print(f"[FAIL] Could not find test file. Error: {e}")
        return

    # 2. Instantiate all analyzers
    print("Instantiating analyzers...")
    parser = Parser(face_prefix_map=FACE_PREFIX_TO_INFO)
    pose_optimizer = PoseOptimizer(
        box_dims=config_app.BOX_DIMS,
        face_definitions=config_app.FACE_DEFINITIONS,
        local_box_corners=config_app.LOCAL_BOX_CORNERS
    )
    velocity_calculator = VelocityCalculator()
    frame_analyzer = FrameAnalyzer()

    # 3. Run the full pipeline
    print("Running Parser...")
    parsed_df = parser.process(header_info, raw_data)
    print(f"DataFrame has {len(parsed_df.columns)} columns after Parser.")

    print("Running PoseOptimizer...")
    df_after_pose = pose_optimizer.process(parsed_df.copy())
    print(f"DataFrame has {len(df_after_pose.columns)} columns after PoseOptimizer.")

    print("Running VelocityCalculator...")
    df_after_velo = velocity_calculator.process(df_after_pose.copy())
    print(f"DataFrame has {len(df_after_velo.columns)} columns after VelocityCalculator.")

    print("Running FrameAnalyzer...")
    final_df = frame_analyzer.process(df_after_velo.copy())
    print(f"DataFrame has {len(final_df.columns)} columns after FrameAnalyzer.")

    # 4. Final Verification
    print("\n--- Verification ---")
    final_cols = final_df.columns.tolist()

    # Check for one of the relative height columns
    expected_col = f'C1{RelativeHeightCols.H_ANA_SUFFIX}' # "C1_H_Ana"

    if expected_col in final_cols:
        print(f"[PASS] Final DataFrame contains the relative height column: '{expected_col}'")
        print("All features appear to be working correctly with real data.")
    else:
        print(f"[FAIL] Final DataFrame does NOT contain the relative height column: '{expected_col}'")
        print("The 'relative height' feature failed with the real data test.")
        # print("\nFinal Columns:", final_cols) # Uncomment for debugging

if __name__ == "__main__":
    run_real_data_test()
