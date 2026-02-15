# Code Structure Notes (Current)

## 1. 목적
결과 컬럼 스키마를 Analysis/UI/Export 전 구간에서 일관되게 유지하기 위한 현재 구조를 요약한다.

## 2. 데이터 흐름
1. `PoseOptimizer`가 포즈 컬럼(`P_TX`~`P_RZ`)과 코너 좌표를 생성
2. `VelocityCalculator`가 Global 속도/가속도 및 코너 속도(`Global_V_*`)를 계산
3. `FrameAnalyzer`가 BoxLocal 속도/가속도(`BoxLocal_*`)와 Analysis 결과를 계산
4. Export 시 `convert_to_multi_header()`가 flat 컬럼명을 Multi-Header로 변환
5. `WidgetResultsAnalyzer`는 `DISPLAY_RESULT_COLUMNS` 기준으로 트리/플롯 항목을 표시

## 3. 단일 진실원(SoT)
- `src/config/data_columns.py`
  - `PoseCols`, `VelocityCols`, `AnalysisCols`: 계산/저장용 컬럼명
  - `HeaderL1~HeaderL3`: Multi-Header 키 정의
  - `DISPLAY_RESULT_COLUMNS`: Results Analyzer 표시 스펙

실제 동작 규칙은 위 파일을 기준으로 본다.

## 4. 현재 스키마 요약
- CoM Position: `P_T*` 후 `P_R*`
- CoM Velocity/Acceleration: `BoxLocal_*` 먼저, `Global_*` 나중
- Norm은 `*_Norm` 표기로 고정
- Corner는 Translation 성분만 사용하며 Velocity에는 `Global_V_T_Norm` 포함

## 5. 구버전 대비 변경 포인트
- `_Ana` 접미사 기반 표기 -> `BoxLocal_` 접두사 표기로 전환
- `Norm_V`, `Norm_A` 류 표기 -> `*_Norm` 표기로 통일
- `TestSets` 운영 구조 분리:
  - `TestSets/Input/` (tracked)
  - `TestSets/Output/` (ignored)

## 6. 유지보수 가이드
스키마 변경 시에는 아래 4개를 항상 함께 수정해야 한다.
1. `src/config/data_columns.py`
2. `src/utils/header_converter.py`
3. `src/analysis/*` 계산 모듈 (`velocity_calculator.py`, `frame_analyzer.py`)
4. `src/analysis/ui/widget_results_analyzer.py`

그리고 `tests/test_header_converter_acceleration.py`,
`tests/test_result_format_layout.py`를 함께 갱신해야 회귀를 방지할 수 있다.
