import os
import sys
import pandas as pd
from PySide6.QtCore import QObject, Slot, Signal

# 임포트 경로 설정
script_dir = os.path.dirname(__file__)
if script_dir not in sys.path:
    sys.path.insert(0, script_dir)
root_dir = os.path.dirname(script_dir)
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from data_loader import DataLoader
from analysis.parser import Parser
from pipeline_controller import PipelineController
import app_config as config

class TestReceiver(QObject):
    final_df = None
    @Slot(pd.DataFrame)
    def on_analysis_finished(self, result_df: pd.DataFrame):
        print("\n--- TestReceiver: Received analysis_finished signal! ---")
        self.final_df = result_df

def main():
    """
    "파싱 결과 캐싱/공유" 아키텍처를 테스트합니다.
    """
    print("--- Full Pipeline Test with Caching Logic ---")

    # 1. 작은 테스트 CSV 파일 생성
    # (이전과 동일한 로직, 테스트의 독립성을 위해 내장)
    large_csv_path = os.path.join(root_dir, 'TestSets', 'VDTest_S5_001.csv')
    small_csv_path = os.path.join(root_dir, 'TestSets', 'small_test.csv')
    try:
        with open(large_csv_path, 'r', encoding='utf-8-sig') as f:
            lines = f.readlines()
        new_content_lines = lines[:8] + lines[8:18]
        with open(small_csv_path, 'w', encoding='utf-8') as f:
            f.writelines(new_content_lines)
    except Exception as e:
        print(f"[FATAL] Could not create small test CSV: {e}")
        return

    # 2. MainApp의 동작 모방: 데이터 로드 후 즉시 파싱
    print(f"Loading and parsing test file: {small_csv_path}")
    loader = DataLoader()
    parser = Parser(face_prefix_map=config.FACE_PREFIX_TO_INFO)

    header_info, raw_df = loader.load_csv(small_csv_path)
    parsed_data_cache = parser.process(header_info, raw_df) # 파싱 결과를 캐시에 저장

    print(f"DataLoader and Parser executed for preview. Parsed data shape: {parsed_data_cache.shape}")

    # 3. PipelineController 및 Receiver 초기화
    controller = PipelineController()
    receiver = TestReceiver()
    controller.analysis_finished.connect(receiver.on_analysis_finished)
    controller.log_message.connect(print)

    # 4. GUI 설정값 생성 및 파이프라인 실행
    # 이제 parsed_data_cache를 함께 전달
    gui_config = {
        'slice_filter_by': 'time',
        'slice_start_val': parsed_data_cache.index.min(),
        'slice_end_val': parsed_data_cache.index.max(),
    }
    print(f"\nRunning pipeline with cached parsed data...")
    controller.run_analysis(gui_config, header_info, raw_df, parsed_data_cache)

    # 5. 결과 확인
    print("\n--- Final Result Verification ---")
    if receiver.final_df is not None:
        print(f"Final DataFrame shape: {receiver.final_df.shape}")
        # 파이프라인이 캐시된 데이터를 사용하고, 모든 분석을 거쳐 컬럼이 추가되었는지 확인
        # 초기 파싱 컬럼 수보다 최종 컬럼 수가 많아야 함
        if len(receiver.final_df.columns) > len(parsed_data_cache.columns):
             print("\n[SUCCESS] Pipeline seems to have executed all stages on cached data.")
        else:
             print("\n[ERROR] Pipeline did not add new analysis columns.")
    else:
        print("[ERROR] Pipeline did not return a DataFrame.")

    print("\n--- Full Pipeline Test with Caching Logic Finished ---")

if __name__ == "__main__":
    main()
