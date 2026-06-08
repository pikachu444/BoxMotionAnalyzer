# Code Structure Notes (Current)

Last Reviewed: 2026-06-09

## 1. 목적
결과 컬럼 스키마를 Analysis/UI/Export 전 구간에서 일관되게 유지하기 위한 현재 구조를 요약한다.

## 2. 데이터 흐름
1. `PoseOptimizer`가 포즈 컬럼(`P_TX`~`P_RZ`)과 코너 좌표를 생성
2. `VelocityCalculator`가 Global 속도/가속도 및 코너 속도(`Global_V_*`)를 계산
3. `FrameAnalyzer`가 BoxLocal 속도/가속도(`BoxLocal_*`)와 Analysis 결과를 계산
4. `DropPosturePostProcessor`가 처리 완료 결과에서 낙하 자세 비교용 frame metric과 summary metric을 계산
5. Export 시 `convert_to_multi_header()`가 flat 컬럼명을 Multi-Header로 변환
6. `WidgetResultsAnalyzer`는 `DISPLAY_RESULT_COLUMNS` 기준으로 트리/플롯 항목을 표시하고, UI에서는 `Metric-first` / `Object-first` 계층 전환과 검색 필터를 제공한다
7. `Visualization`은 export된 `HeaderL3` metric 키를 long-format 내부 컬럼에도 그대로 재사용한다

## 3. 단일 진실원(SoT)
- `src/config/data_columns.py`
  - `PoseCols`, `VelocityCols`, `AnalysisCols`: 계산/저장용 컬럼명
  - `DropPostureCols`, `DropPostureSummaryCols`: 낙하 자세 비교용 계산/저장 컬럼명
  - `HeaderL1~HeaderL3`: Multi-Header 키 정의
  - `DISPLAY_RESULT_COLUMNS`: Results Analyzer 표시 스펙
- `src/config/config_visualization.py`
  - visualization 내부 metric 키와 UI metric metadata 정의
  - `DF_*` metric 상수는 `HeaderL3` export 키를 직접 재사용

실제 동작 규칙은 위 파일을 기준으로 본다.

## 4. 현재 스키마 요약
- CoM Position: `P_T*` 후 `P_R*`
- CoM Velocity/Acceleration: `BoxLocal_*` 먼저, `Global_*` 나중
- Norm은 `*_Norm` 표기로 고정
- Corner는 Translation 성분만 사용하며 Velocity에는 `Global_V_T_Norm` 포함
- Drop posture frame metric은 `(Analysis, DropPosture, *)`에 저장한다.
- Drop posture summary metric은 `(Analysis, DropPostureSummary, *)`에 저장하며, `.proc` CSV 호환성을 위해 모든 row에 같은 값을 반복한다.
- Visualization long-format도 `Global_V_TX`, `BoxLocal_A_T_Norm` 같은 export metric 키를 그대로 사용

## 5. Drop Posture 스키마
- Frame metric
  - `BetaDeg`: 자동 기준면 normal과 아래 방향 사이 각도
  - `ThetaLongDeg`: 기준면의 긴 방향 높이 기울기 각도
  - `ThetaShortDeg`: 기준면의 짧은 방향 높이 기울기 각도
  - `CminIndex`: 해당 frame에서 가장 낮은 코너 번호
  - `DeltaH_mm`: 해당 frame의 최고 코너와 최저 코너 높이 차이
- Summary metric
  - `BetaAtT1MinusDeg`, `MaxBetaDeg`
  - `ThetaLongAtT1MinusDeg`, `MaxAbsThetaLongDeg`
  - `ThetaShortAtT1MinusDeg`, `MaxAbsThetaShortDeg`
  - `DeltaHAtT1Minus_mm`, `MaxDeltaH_mm`
  - `CminAtT1MinusIndex`, `T1MinusTimeSec`
  - `ReferenceFace`, `LongAxis`, `ShortAxis`, `T1Detected`
  - `ImpactSequence`, `ImpactEventCount`, `FirstImpactTimeSec`, `FirstImpactContact`
- `t1-`는 최저 코너가 `floor_level + contact_threshold_mm` 이하로 처음 들어오기 직전 frame이다.
- 접촉 frame이 없으면 최저 코너 높이가 가장 낮은 frame을 fallback으로 사용하고 `T1Detected=False`로 저장한다.
- `ImpactSequence`는 같은 threshold로 검출한 접촉 이벤트 순서다.
  - 최소 2 frame 연속 접촉만 이벤트로 인정한다.
  - 동시 접촉은 `{C1,C2}`처럼 하나의 이벤트로 묶어 표기한다.
  - 예: `{C1,C2} -> C5 -> {C6,C7,C8}`

## 6. 구버전 대비 변경 포인트
- `_Ana` 접미사 기반 표기 -> `BoxLocal_` 접두사 표기로 전환
- `Norm_V`, `Norm_A` 류 표기 -> `*_Norm` 표기로 통일
- `TestSets` 운영 구조 분리:
  - `TestSets/Input/` (tracked)
  - `TestSets/Output/` (ignored)

## 7. 유지보수 가이드
스키마 변경 시에는 아래 4개를 항상 함께 수정해야 한다.
1. `src/config/data_columns.py`
2. `src/utils/header_converter.py`
3. `src/analysis/*` 계산 모듈 (`velocity_calculator.py`, `frame_analyzer.py`, `drop_posture_post_processor.py`)
4. `src/analysis/ui/widget_results_analyzer.py`
5. `src/config/config_visualization.py`
6. `src/visualization/data_handler.py`

그리고 `tests/test_header_converter_acceleration.py`,
`tests/test_result_format_layout.py`,
`tests/test_visualization_data_handler.py`를 함께 갱신해야 회귀를 방지할 수 있다.
