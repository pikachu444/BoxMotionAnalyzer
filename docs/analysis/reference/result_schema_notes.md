# Code Structure Notes (Current)

Last Reviewed: 2026-06-10

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
- `src/config/result_metric_descriptors.py`
  - Drop Posture summary의 UI 표시명, group, 단위, tooltip, metric guide 설명, visual guide id
  - Step 2 `Experiment Summary`, Data Selection tooltip, 향후 compare window 설명의 공통 기준
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
- Drop posture summary 설명 metadata는 `result_metric_descriptors.py`에서 관리하며, 저장 스키마 키 자체는 `data_columns.py`의 `HeaderL1~HeaderL3`와 `DropPostureSummaryCols`를 기준으로 유지한다.
- Visualization long-format도 `Global_V_TX`, `BoxLocal_A_T_Norm` 같은 export metric 키를 그대로 사용

## 5. Drop Posture 스키마
- Frame metric (계산 기준 및 부호 규약)
  - `BetaDeg` (단위: degree)
    - **계산 기준**: 포즈에 의해 결정된 박스의 자동 기준면(Reference Face)의 법선 벡터(Normal)와 바닥 방향(Z=-1 등) 법선 벡터 사이의 절대 각도.
    - **부호 규약**: 항상 양수(0 ~ 180도).
  - `ThetaLongDeg` (단위: degree)
    - **계산 기준**: 기준면에 수평하게 놓인 로컬 긴 축(Long axis) 방향의 기울기 각도.
    - **부호 규약**: `asin((positive-side height - negative-side height) / local-axis length)`. 즉, 로컬 축의 양의 방향(Positive) 코너가 음의 방향(Negative) 코너보다 높을 때 양수(+).
    - **해석 주의점**: 첫 충격(first impact) 이전에는 물리적으로 의미가 명확하지만, 그 이후 여러 코너가 닿으면서 요동칠 때는 직관과 다를 수 있음 (추후 검토 필요).
  - `ThetaShortDeg` (단위: degree)
    - **계산 기준**: 기준면에 수평하게 놓인 로컬 짧은 축(Short axis) 방향의 기울기 각도.
    - **부호 규약**: `ThetaLongDeg`와 동일. 로컬 짧은 축의 양의 방향이 더 높을 때 양수(+).
  - `CminIndex` (단위: index, 1~8)
    - **계산 기준**: 해당 프레임에서 절대 높이(Z좌표)가 가장 낮은 코너의 번호. 코너 번호는 로컬 좌표계 C1~C8 기준.
  - `DeltaH_mm` (단위: mm)
    - **계산 기준**: 해당 프레임에서 기준면(Reference Face)을 구성하는 4개 코너 중 가장 높은 코너의 높이에서 가장 낮은 코너의 높이를 뺀 값.
    - **부호 규약**: 항상 양수. 0에 가까울수록 기준면이 바닥과 평행함을 의미.

- Summary metric (계산 기준)
  - `BetaAtT1MinusDeg`: t1- 시점의 BetaDeg 값. `T1Detected=False`이면 NaN.
  - `MaxBetaDeg`: 선택 구간 전체에서 BetaDeg의 최댓값.
  - `ThetaLongAtT1MinusDeg`: t1- 시점의 ThetaLongDeg 값. `T1Detected=False`이면 NaN.
  - `MaxAbsThetaLongDeg`: 구간 전체 |ThetaLongDeg|의 최댓값.
  - `ThetaShortAtT1MinusDeg`: t1- 시점의 ThetaShortDeg 값. `T1Detected=False`이면 NaN.
  - `MaxAbsThetaShortDeg`: 구간 전체 |ThetaShortDeg|의 최댓값.
  - `DeltaHAtT1Minus_mm`: t1- 시점의 DeltaH_mm 값. `T1Detected=False`이면 NaN.
  - `MaxDeltaH_mm`: 구간 전체 DeltaH_mm의 최댓값.
  - `CminAtT1MinusIndex`: t1- 시점의 CminIndex 값. `T1Detected=False`이면 NaN.
  - `T1MinusTimeSec`: t1- 시각(초). `T1Detected=False`이면 NaN.
  - `ReferenceFace`: 기준면 레이블 (예: `BOTTOM`, `SIDE_X_POS`). 아래 별도 항목 참고.
  - `LongAxis`, `ShortAxis`: 기준면의 긴 축/짧은 축 레이블 (예: `LocalAxis0`).
  - `T1Detected`: `ImpactEvent`가 확인되어 t1-이 정의된 경우 True.
  - `ImpactDetected`: 접촉 threshold 또는 motion evidence 기반으로 충격이 감지된 경우 True.
  - `SustainedContactDetected`: slice 후반부 낮은 plateau가 지속된 경우 True.
  - `ContactState`: `NoContact`, `Approach`, `ImpactEvent`, `SustainedContact` 중 하나.
  - `ContactConfidence`: 0.0~1.0 사이 접촉 신뢰도. evidence 개수와 종류에 따라 산출.
  - `ContactDetectionMethod`: 사용된 evidence 조합 (예: `threshold+motion+plateau`).
  - `ImpactSequence`: impact event 구간 접촉 이벤트 순서 문자열 (예: `C2 -> {C2,C3} -> C5`).
  - `ImpactEventCount`: ImpactSequence에서 집계된 별개 이벤트 수.
  - `FirstImpactTimeSec`: ImpactSequence 첫 이벤트 시각(초).
  - `FirstImpactContact`: ImpactSequence 첫 이벤트 접촉 코너 표기 (예: `C2`, `{C1,C2}`).

- `ContactState`는 `NoContact`, `Approach`, `ImpactEvent`, `SustainedContact` 중 하나다.
- 접촉 판정은 단일 threshold가 아니라 최저 코너 높이의 절대 높이, 하강/저점/반전, 낮은 plateau, 접촉 corner set 지속성을 함께 보는 evidence 기반 summary다.
- `t1-`는 `ImpactEvent`가 확인될 때만 정의한다.
- 접촉 frame이 없거나 slice가 이미 낮은 plateau 상태로 시작하면 t1 기반 summary는 `NaN`으로 저장한다.
- 접촉이 없어도 frame metric과 `Max*` summary, 기준면, contact state summary는 계산한다.
- Step 2 `Experiment Summary`는 descriptor group 순서에 따라 `Posture -> Impact -> Contact`로 표시한다.
- `T1Detected=False`이면 UI에서는 t1 기반 summary를 `N/A`로 표시한다. 저장값은 기존 `.proc` 호환을 위해 `NaN`을 유지한다.
- `ImpactSequence`는 impact event 구간에서 검출한 접촉 이벤트 순서다.
  - 최소 2 frame 연속 접촉만 이벤트로 인정한다.
  - 동시 접촉은 `{C1,C2}`처럼 하나의 이벤트로 묶어 표기한다.
  - 예: `{C1,C2} -> C5 -> {C6,C7,C8}`

## 5-1. ReferenceFace 의미 및 설계 결정

**현재 동작**: `ReferenceFace`는 t1- 시점(또는 t1-이 없으면 slice 첫 프레임)에서, 법선 벡터가 아래 방향을 가장 강하게 향하는 박스 면을 자동으로 선택한다.

**사용자 기대와의 차이**: `ReferenceFace`가 낙하 직전 접근 자세의 기준면이 아니라, 첫 충격 이후 실제로 바닥과 닿은 면을 가리킨다고 오해할 수 있다.

**설계 결정 (현행 유지)**:
- `ReferenceFace`는 **접근(Approach) 자세 기준면**으로 정의한다. 즉, 충격 직전 t1-에서의 자세 기준이다.
- 실제 충격 접촉 코너는 `FirstImpactContact`와 `ImpactSequence`가 별도로 기록하므로 중복 저장할 필요가 없다.
- `ApproachReferenceFace` / `ImpactContactFace` 분리는 현재 범위에 포함하지 않는다. 필요하다면 향후 `ImpactContactFace` 컬럼을 `FirstImpactContact`로부터 역산해 추가할 수 있다.
- 이 결정은 `result_metric_descriptors.py`의 `ReferenceFace` descriptor long_description에도 반영한다.


## 6. 구버전 대비 변경 포인트
- `_Ana` 접미사 기반 표기 -> `BoxLocal_` 접두사 표기로 전환
- `Norm_V`, `Norm_A` 류 표기 -> `*_Norm` 표기로 통일
- `TestSets` 운영 구조 분리:
  - `TestSets/Input/` (tracked)
  - `TestSets/Output/` (ignored)

## 7. 유지보수 가이드
스키마 변경 시에는 아래 4개를 항상 함께 수정해야 한다.
1. `src/config/data_columns.py`
2. `src/config/result_metric_descriptors.py` (Drop Posture summary 설명/tooltip/guide 변경 시)
3. `src/utils/header_converter.py`
4. `src/analysis/*` 계산 모듈 (`velocity_calculator.py`, `frame_analyzer.py`, `drop_posture_post_processor.py`)
5. `src/analysis/ui/widget_results_analyzer.py`
6. `src/config/config_visualization.py`
7. `src/visualization/data_handler.py`

그리고 `tests/test_header_converter_acceleration.py`,
`tests/test_result_format_layout.py`,
`tests/test_results_analyzer_experiment_summary.py`,
`tests/test_real_drop_posture_physics.py`,
`tests/test_real_data_flow.py`,
`tests/test_visualization_data_handler.py`를 함께 갱신해야 회귀를 방지할 수 있다.

85인치 실제 데이터 검증은 `TestSets/Input/VDTest_S5_001.csv`의 `TestBox_85` 데이터를 사용한다. 접촉 flow 검증은 `2.45s-3.05s` slice를 85인치 치수로 처리하고, export/reload 후 pose/corner 좌표에서 `BetaAtT1MinusDeg`, `DeltaHAtT1Minus_mm`, `CminAtT1MinusIndex`를 독립 재계산해 summary 값과 비교한다.
