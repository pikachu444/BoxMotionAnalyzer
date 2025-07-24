import sys
import os
from PySide6.QtWidgets import QApplication
from main_app import MainApp

def get_project_root():
    """스크립트의 위치를 기준으로 프로젝트 루트 디렉토리를 찾습니다."""
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def run_test():
    """
    GUI 상호작용 없이 데이터 로딩 로직을 테스트합니다.
    """
    # QApplication 인스턴스가 필요합니다.
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)

    # 메인 윈도우를 생성합니다.
    window = MainApp()

    # 테스트할 CSV 파일의 절대 경로를 구성합니다.
    project_root = get_project_root()
    test_csv_path = os.path.join(project_root, "TestSets", "VDTest_S5_001.csv")

    print(f"--- 테스트 시작: {test_csv_path} 파일 로딩 ---")

    # QFileDialog를 시뮬레이션하고, open_csv_file 내부 로직을 직접 실행합니다.
    try:
        # 1. 데이터 로드
        window.raw_data = window.data_loader.load_csv(test_csv_path)

        # 2. GUI 업데이트
        window.file_path_label.setText(test_csv_path)
        window.statusBar().showMessage("파일 로드 성공")
        window.log_output.append(f"[정보] {test_csv_path} 파일을 성공적으로 불러왔습니다.")

        # 3. 드롭다운 메뉴 채우기
        plottable_targets = window.data_loader.get_plottable_targets(window.raw_data)
        window.combo_plot_data.clear()
        window.combo_plot_data.addItems(plottable_targets)

        # 4. 결과 검증 및 출력
        print("--- 파싱된 컬럼 이름 확인 ---")
        print(window.raw_data.columns)
        print("--------------------------")

        print("--- 테스트 결과 ---")
        print(f"파일 경로 레이블: {window.file_path_label.text()}")
        print(f"상태바 메시지: {window.statusBar().currentMessage()}")
        print(f"로그 출력: \n{window.log_output.toPlainText()}")
        print("플롯 대상 드롭다운 메뉴 항목:")

        items = [window.combo_plot_data.itemText(i) for i in range(window.combo_plot_data.count())]
        for item in items:
            print(f"- {item}")

        # 5. 시각화 테스트
        print("\n--- 시각화 테스트 시작 ---")
        window.update_plot()

        plot_items = window.plot_widget.getPlotItem().listDataItems()
        if plot_items:
            print(f"[성공] 그래프에 {len(plot_items)}개의 데이터 아이템이 그려졌습니다.")
        else:
            print(f"[실패] 그래프에 데이터가 그려지지 않았습니다.")

        # 최종 성공 여부 확인
        if len(items) > 1 and plot_items:
             print("\n[최종 성공] 데이터 로딩 및 기본 시각화 기능이 정상적으로 동작했습니다.")
        else:
             print("\n[최종 실패] 기능이 올바르게 동작하지 않았습니다.")

    except Exception as e:
        print(f"\n[실패] 테스트 중 예외 발생: {e}")
        # 스택 트레이스를 포함하여 더 자세한 디버깅 정보 제공
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    run_test()
