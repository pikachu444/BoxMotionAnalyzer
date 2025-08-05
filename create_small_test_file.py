import os
import sys
import pandas as pd

# src 폴더를 경로에 추가
script_dir = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(script_dir, 'src'))

from data_loader import DataLoader

def create_small_csv():
    """
    기존의 큰 CSV 파일에서 헤더와 일부 데이터만 추출하여 작은 테스트용 CSV를 만듭니다.
    """
    print("--- Creating Small Test CSV ---")

    large_csv_path = os.path.join(script_dir, 'TestSets', 'VDTest_S5_001.csv')
    small_csv_path = os.path.join(script_dir, 'TestSets', 'small_test.csv')

    if not os.path.exists(large_csv_path):
        print(f"[ERROR] Source file not found: {large_csv_path}")
        return

    # 원본 파일 읽기 (헤더 8줄 + 데이터)
    try:
        with open(large_csv_path, 'r', encoding='utf-8-sig') as f:
            lines = f.readlines()
    except Exception as e:
        print(f"[ERROR] Failed to read source file: {e}")
        return

    if len(lines) < 18: # 헤더 8줄 + 데이터 최소 10줄
        print("[ERROR] Source file is too small to create a test file.")
        return

    # 헤더 8줄과 데이터 10줄을 합쳐 새로운 파일 내용 생성
    new_content_lines = lines[:8] + lines[8:18]

    # 새로운 파일 작성
    try:
        with open(small_csv_path, 'w', encoding='utf-8') as f:
            f.writelines(new_content_lines)
        print(f"Successfully created small test file at: {small_csv_path}")
        print(f"Total lines written: {len(new_content_lines)}")
    except Exception as e:
        print(f"[ERROR] Failed to write small test file: {e}")

if __name__ == "__main__":
    create_small_csv()
