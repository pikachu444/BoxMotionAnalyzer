import os
import sys
import pandas as pd
from PySide6.QtCore import QObject, Slot, Signal

# 임포트 경로 설정을 위해 sys.path 조작 (테스트 스크립트에서만 사용)
script_dir = os.path.dirname(__file__)
if script_dir not in sys.path:
    sys.path.insert(0, script_dir)
root_dir = os.path.dirname(script_dir)
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from data_loader import DataLoader
from pipeline_controller import PipelineController

def create_small_test_csv_for_test():
    """
    테스트 실행을 위해 작은 CSV 파일을 생성합니다.
    """
    large_csv_path = os.path.join(root_dir, 'TestSets', 'VDTest_S5_001.csv')
    small_csv_path = os.path.join(root_dir, 'TestSets', 'small_test.csv')

    if not os.path.exists(large_csv_path):
        print(f"[ERROR] Source file not found: {large_csv_path}")
        return None
    try:
        with open(large_csv_path, 'r', encoding='utf-8-sig') as f:
            lines = f.readlines()
        if len(lines) < 18:
            return None
        new_content_lines = lines[:8] + lines[8:18]
        with open(small_csv_path, 'w', encoding='utf-8') as f:
            f.writelines(new_content_lines)
        print(f"Successfully created small test file at: {small_csv_path}")
        return small_csv_path
    except Exception:
        return None

class TestReceiver(QObject):
    final_df = None
    @Slot(pd.DataFrame)
    def on_analysis_finished(self, result_df: pd.DataFrame):
        print("\n--- TestReceiver: Received analysis_finished signal! ---")
        self.final_df = result_df

def main():
    print("--- Full Pipeline Integration Test with Small Data ---")

    small_csv_path = create_small_test_csv_for_test()
    if not small_csv_path:
        print("[FATAL] Could not create small test CSV. Aborting test.")
        return

    print(f"Loading test file: {small_csv_path}")

    loader = DataLoader()
    header_info, raw_df = loader.load_csv(small_csv_path)
    print(f"DataLoader loaded {len(raw_df)} rows.")

    controller = PipelineController()
    receiver = TestReceiver()
    controller.analysis_finished.connect(receiver.on_analysis_finished)
    controller.log_message.connect(print)

    gui_config = {
        'slice_filter_by': 'time',
        'slice_start_val': raw_df['Time'].astype(float).min(),
        'slice_end_val': raw_df['Time'].astype(float).max(),
    }
    print(f"\nRunning pipeline with config: {gui_config}")

    controller.run_analysis(gui_config, header_info, raw_df)

    print("\n--- Final Result Verification ---")
    if receiver.final_df is None:
        print("[ERROR] Pipeline did not return a DataFrame.")
    elif receiver.final_df.empty:
        print("[WARNING] Pipeline returned an empty DataFrame.")
    else:
        print(f"Final DataFrame shape: {receiver.final_df.shape}")
        expected_cols = ['CoM_Vx', 'Box_Tx', 'AngVel_Wx', 'CoM_Vx_Ana']
        missing_cols = [col for col in expected_cols if col not in receiver.final_df.columns]

        if not missing_cols:
            print("\n[SUCCESS] Key columns from all analysis stages are present.")
        else:
            print(f"\n[ERROR] The following key columns are missing: {missing_cols}")

    print("\n--- Full Pipeline Integration Test Finished ---")

if __name__ == "__main__":
    main()
