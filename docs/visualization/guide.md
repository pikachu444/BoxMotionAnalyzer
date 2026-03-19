# Visualization Guide

Last Reviewed: 2026-03-19

이 문서는 `src/visualization/` 아래 3D 시각화 기능이 어떤 구조로 동작하는지 설명한다.

## 1. 목적
- Step 1/Step 2 분석 GUI와 별도로, 결과 파일을 3D/2D로 탐색하는 전용 창을 제공한다.
- UI 기준 입력은 Box Motion Analyzer가 export한 multi-header `.proc` 결과 파일이다.

## 2. 진입점
- 전체 앱 진입점: `src/main.py`
- 시각화 창 진입점: `src/launcher.py` -> `LauncherWindow` -> `src.visualization.main_window.MainWindow`

## 3. 현재 구조
- `src/visualization/main_window.py`
  - 시각화 메인 창
  - 메뉴, 파일 열기, 프레임 이동, 플롯/로그 업데이트 조율
- `src/visualization/data_handler.py`
  - multi-header 결과 CSV를 읽고 long-format DataFrame으로 변환
- `src/visualization/vista_widget.py`
  - PyVista 기반 3D 렌더링
- `src/visualization/control_panel.py`
  - 표시 옵션, grouped `Scene Inspector`, metric 선택, frame range 필터
- `src/visualization/plot_widget.py`
  - 2D 시계열 플롯
- `src/visualization/plot_dialog.py`
  - 플롯 확대용 팝업 다이얼로그
- `src/visualization/info_log_widget.py`
  - 선택 entity의 현재 프레임 정보를 `Frame Inspector` 표 형식으로 표시
- `src/visualization/animation_widget.py`
  - 재생/정지와 프레임 이동 제어

## 4. 데이터 흐름
1. 사용자가 visualization 창에서 `.proc` 결과 파일을 연다.
2. `DataHandler.load_analysis_result()`가 multi-header 결과 파일을 읽는다.
3. Position 계열 컬럼을 기준으로 `CoM / Corners / Markers` entity를 식별한다.
4. 각 entity에 대해 frame/time/position/velocity/acceleration을 long-format DataFrame으로 정리한다.
   이때 metric 컬럼 키는 visualization 전용 이름을 새로 만들지 않고 export의 `HeaderL3` 키를 그대로 재사용한다.
5. `MainWindow`가 현재 frame 기준으로 3D 뷰, 2D plot, `Frame Inspector`를 갱신한다.

## 5. 설정 파일
- 시각화 전용 설정은 `src/config/config_visualization.py`에 있다.
- 분석 GUI 공통 설정은 `src/config/config_app.py`, `src/config/data_columns.py`와 연결된다.
- 과거 단일 `config.py` 구조는 더 이상 현재 기준 문서가 아니다.

## 6. 현재 동작 특성
- visualization은 분석 결과 파일을 직접 읽는다. 원본 raw CSV를 바로 읽는 흐름이 아니다.
- `DataHandler`는 결과 파일의 `Position`, `Velocity`, `Acceleration`, `Info` multi-header를 해석한다.
- UI에서는 `.proc`만 노출해 raw `.csv`와의 혼동을 줄인다.
- visualization 내부 metric 키도 export 스키마를 그대로 따른다.
  - 예: `P_TX`, `Global_V_TX`, `Global_V_T_Norm`, `BoxLocal_A_T_Norm`
- `Scene Inspector`는 `Center of Mass / Corners / Markers` 그룹으로 entity를 나눠 보여준다.
- 선택한 entity type에 따라 plot metric 목록이 달라진다.
  - `CoM`: position, global velocity/velocity norm, box-local velocity/velocity norm, global acceleration, box-local acceleration
  - `Corners`: position, global velocity/velocity norm, global acceleration
  - `Markers`: position만 지원
- metric 콤보박스 아래 help label이 현재 선택 유형에서 지원되는 좌표계와 metric 범위를 설명한다.
- 선택이 없을 때는 mixed-type selection 제한과 “metric 목록이 그룹에 따라 바뀐다”는 기본 안내를 먼저 보여준다.
- 1차 구현에서는 서로 다른 entity type의 동시 선택을 제한한다.
- `PlotWidget` 더블클릭 시 `PlotDialog`가 열려 확대 플롯을 볼 수 있다.
- frame range 체크박스와 spinbox로 선택 구간만 플롯할 수 있다.

## 7. 참고할 구현 포인트
- 결과 파일 헤더 규칙이 바뀌면 다음을 함께 확인해야 한다.
  - `src/config/data_columns.py`
  - `src/visualization/data_handler.py`
  - `docs/analysis/reference/csv_multi_header_schema.md`
- object id / entity grouping 방식이 바뀌면 `DataHandler.load_analysis_result()`와 `ControlPanel.populate_scene_inspector()`를 함께 점검해야 한다.
- 새 속성(예: additional norms or derived metrics)을 시각화에 추가할 때는 아래 순서로 확인하는 것이 안전하다.
  - `config_visualization.PLOT_DATA_DISPLAY_MAP`
  - `DataHandler`
  - `PlotWidget`
  - `InfoLogWidget`
