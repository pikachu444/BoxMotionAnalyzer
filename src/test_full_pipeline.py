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

class TestReceiver(QObject):
    """
    PipelineController의 analysis_finished 시그널을 받기 위한 슬롯.
    """
    final_df = None

    @Slot(pd.DataFrame)
    def on_analysis_finished(self, result_df: pd.DataFrame):
        print("\n--- TestReceiver: Received analysis_finished signal! ---")
        self.final_df = result_df

def main():
    """
    전체 분석 파이프라인을 테스트합니다.
    """
    print("--- Full Pipeline Integration Test ---")

    test_csv_path = os.path.join(root_dir, 'TestSets', 'VDTest_S5_001.csv')

    print(f"Loading test file: {test_csv_path}")
    if not os.path.exists(test_csv_path):
        print(f"[ERROR] Test file not found at: {test_csv_path}")
        return

    # 1. 데이터 로드
    loader = DataLoader()
    header_info, raw_df = loader.load_csv(test_csv_path)
    print(f"DataLoader loaded {len(raw_df)} rows.")

    # 2. 파이프라인 컨트롤러 및 리시버 초기화
    controller = PipelineController()
    receiver = TestReceiver()
    controller.analysis_finished.connect(receiver.on_analysis_finished)
    controller.log_message.connect(print) # 컨트롤러 로그를 콘솔에 출력

    # 3. 테스트용 GUI 설정값 생성
    gui_config = {
        'slice_filter_by': 'time',
        'slice_start_val': raw_df['Time'].astype(float).min() + 1.0, # 예시: 1초부터
        'slice_end_val': raw_df['Time'].astype(float).min() + 3.0,   # 예시: 3초까지
    }
    print(f"\nRunning pipeline with config: {gui_config}")

    # 4. 파이프라인 실행
    controller.run_analysis(gui_config, header_info, raw_df)

    # 5. 결과 확인
    print("\n--- Final Result Verification ---")
    if receiver.final_df is None:
        print("[ERROR] Pipeline did not return a DataFrame.")
    elif receiver.final_df.empty:
        print("[WARNING] Pipeline returned an empty DataFrame.")
    else:
        print(f"Final DataFrame shape: {receiver.final_df.shape}")
        print(f"Final DataFrame columns: {list(receiver.final_df.columns)}")

        # 모든 분석 단계의 결과가 포함되었는지 핵심 컬럼들로 확인
        expected_cols = ['CoM_Vx', 'Box_Tx', 'AngVel_Wx', 'CoM_Vx_Ana']
        missing_cols = [col for col in expected_cols if col not in receiver.final_df.columns]

        if not missing_cols:
            print("\n[SUCCESS] Key columns from all analysis stages are present in the final DataFrame.")
        else:
            print(f"\n[ERROR] The following key columns are missing: {missing_cols}")

    print("\n--- Full Pipeline Integration Test Finished ---")

if __name__ == "__main__":
    main()
