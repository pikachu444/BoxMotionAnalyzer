import sys
import os
from unittest.mock import patch
from PySide6.QtWidgets import QApplication
from main_app import MainApp

def get_project_root():
    """스크립트의 위치를 기준으로 프로젝트 루트 디렉토리를 찾습니다."""
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

@patch('PySide6.QtWidgets.QFileDialog.getOpenFileName')
def run_test(mock_get_open_file_name):
    """
    QFileDialog를 모킹하여 데이터 로딩 및 시각화/인터랙션 초기화를 테스트합니다.
    """
    app = QApplication.instance() or QApplication(sys.argv)
    window = MainApp()

    project_root = get_project_root()
    test_csv_path = os.path.join(project_root, "TestSets", "VDTest_S5_001.csv")

    # QFileDialog.getOpenFileName이 항상 테스트 파일 경로를 반환하도록 설정
    mock_get_open_file_name.return_value = (test_csv_path, "CSV Files (*.csv)")

    print(f"--- 테스트 시작: open_csv_file 메서드 호출 ---")

    # "CSV 파일 불러오기" 버튼 클릭을 시뮬레이션
    window.load_csv_button.click()

    # 시그널 처리를 위해 이벤트 루프를 잠시 실행
    QApplication.processEvents()

    print("\n--- 테스트 결과 검증 ---")

    # 1. 파일 경로 레이블 확인
    print(f"파일 경로 레이블: {window.file_path_label.text()}")
    assert window.file_path_label.text() == test_csv_path

    # 2. 드롭다운 메뉴 확인
    items = [window.combo_plot_data.itemText(i) for i in range(window.combo_plot_data.count())]
    print(f"플롯 대상 항목 수: {len(items)}")
    assert len(items) > 1
    assert "TestBox_85 (강체 중심)" in items

    # 3. 그래프 아이템 확인
    plot_items = window.plot_widget.getPlotItem().listDataItems()
    print(f"그래프 아이템 수: {len(plot_items)}")
    assert len(plot_items) > 0

    # 4. 분석 구간 초기값 확인
    start_val = window.le_slice_start.text()
    end_val = window.le_slice_end.text()
    print(f"분석 구간: Start={start_val}, End={end_val}")
    assert float(start_val) > 0
    assert float(end_val) > float(start_val)

    print("\n[최종 성공] 모든 버그 수정 및 기능이 정상적으로 동작했습니다.")


if __name__ == "__main__":
    run_test()
