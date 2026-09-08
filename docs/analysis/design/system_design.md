# 소프트웨어 설계 문서 (현재 기준): Box Motion Analyzer GUI

Last Reviewed: 2026-09-08

## 1. 개요
이 문서는 현재 구현된 Box Motion Analyzer의 분석 GUI 구조를 요약한다. 목표는 대용량 raw CSV를 scene 단위로 재사용 가능하게 만들고, processing과 결과 분석을 단계적으로 분리하는 것이다.

## 2. 상위 구조
- `src/main.py`
  - 애플리케이션 진입점
- `src/launcher.py`
  - 분석 GUI와 3D 시각화 GUI를 선택하는 런처
- `src/analysis/`
  - 분석 파이프라인과 분석용 GUI
- `src/visualization/`
  - 3D 시각화 GUI
- `src/config/`
  - 설정값과 컬럼 정의

## 3. 분석 GUI 설계
분석 GUI는 `MainApp` 하나로 묶이고, 내부는 Step 1 / Step 1.5 / Step 2 탭으로 분리된다.

### 3.1. Step 1: Raw Data Slice
- 원본 CSV 로드
- 파싱 기반 미리보기 플롯
- 선택적 Marker Flip Review
  - 추적 gap/freeze, 마커 열 재연결, 포즈 불연속 후보 탐색
  - 각 후보에서 `None / Local X 180 / Local Y 180 / Local Z 180` 가설 비교
  - 추천 축과 작업자 승인/선택 축 분리
  - 경계 전후 안정 구간과 orientation residual 시각화
- 승인된 이벤트의 분석 면 할당을 누적 적용한 별도 v3 corrected CSV 저장 (XYZ/ID 보존)
- corrected CSV 저장 성공 후에만 활성 입력 전환
- Plot target / axis 선택
- Slice Range 지정
- `.slice` 저장
- 미리보기 플롯과 하단 제어 영역 사이에는 세로 splitter가 있어, 창 높이 증가분이 플롯에 우선 배분되고 사용자가 플롯 높이를 직접 조절할 수 있다.

### 3.2. Step 1.5: Slice Processing
- `.slice` 로드
- `.slice` 메타에 포함된 box dimensions 자동 적용
- Optional Result Resampling 지정
- `Processing Mode` 선택 (`Raw / Smoothing / Advanced`)
- `Advanced Settings...` 다이얼로그 사용
- processing 실행
- processing 완료 후 낙하 자세 비교용 post-processing 지표 계산
- `.proc` 저장
- Step 1과 같은 splitter 기반 상단 plot / 우측 패널 / 하단 controls 구조를 유지한다.

### 3.3. Step 2: Results Analysis
- 결과 폴더 선택
- 결과 목록에서 `.proc` 선택
- Multi-header 결과 컬럼 트리 표시
- `Group By (Metric / Object)` 전환
- 현재 트리를 유지한 검색 필터
- Drop Posture `Experiment Summary` grouped table 표시
- Drop Posture metric guide와 descriptor 기반 tooltip 표시
- 메인 플롯 비교
- 팝업 플롯 열기
- 선택 시점 분석
- point export
- scenario export
- 상단 분석 제어 영역과 하단 메인 플롯 사이에는 세로 splitter가 있어, 기본 레이아웃을 유지하면서도 메인 플롯 높이를 수동 조절할 수 있다.
- Step 2의 Time Window는 현재 파일과 timeline 정보를 담당하고, 본문 상단 row는 `Result Files / Data Selection / Experiment Summary`로 구성한다.
- `Peak & Point Selection`과 `Export Analysis Input`은 Main Plot 옆 하단 패널에 배치한다.

### 3.4. Step 간 연결
- Step 1은 원본 CSV를 보존하고, 필요하면 별도 corrected CSV를 만든 뒤 현재 활성 입력에서 `.slice`를 생성한다.
- Step 1.5는 `.slice`를 열어 `.proc`를 생성한다.
- Step 2는 결과 폴더에서 `.proc`를 선택해 연다.
- `.proc`는 기존 result CSV와 동일한 multi-header 구조를 사용한다.
- processing 결과에는 Full/Slice timeline metadata가 함께 포함된다.
- corrected 입력을 사용한 경우 `.slice`와 `.proc`에는 실제 corrected source, 원본 이름/SHA-256, 전체 검토 결정과 승인 수가 함께 전달된다.
- processing 결과에는 낙하각, 방향 각도, 최저 코너, 기준면 코너 높이 차이, 접촉 상태와 같은 Drop Posture metric도 포함된다.

## 4. 핵심 설계 원칙

### 4.1. 파이프라인 제어와 UI 분리
- UI는 설정 수집과 결과 표시를 담당한다.
- 실제 분석 순서 제어는 `PipelineController`가 담당한다.
- Result Resampling처럼 UI/Qt와 무관한 계산 로직은 순수 모듈로 분리한다.
- processing mode 라벨과 기본 preset 같은 UI 정책은 `src/config/config_analysis_ui.py`에서 관리한다.
- Marker Flip Review는 분석 결과 포즈를 사후 회전하는 단계가 아니다. Step 1에서 원시 마커 열의 의미를 검토하고 corrected source를 만드는 입력 정리 단계다.
- `PipelineController`는 이미 corrected CSV에 반영된 열 순열을 다시 적용하지 않는다.

### 4.2. 컬럼 정의의 중앙 관리
- 컬럼명, Multi-header 규칙, Results Analyzer 표시 순서는 `src/config/data_columns.py`에서 관리한다.
- Drop Posture summary의 표시명, group, tooltip, metric guide 설명은 `src/config/result_metric_descriptors.py`에서 관리한다.
- Results Analyzer는 raw multi-header tuple을 유지한 채, UI에서만 `Metric-first`와 `Object-first` 두 가지 계층으로 재구성한다.
- 새 분석 결과를 추가할 때도 우선 이 파일 기준으로 맞춘다.

### 4.3. 단계 파일 기반 처리
- 처리 단계 내부는 여전히 DataFrame 기반으로 동작한다.
- 단, 사용자 workflow 개선을 위해 scene 재사용용 `.slice`와 processed result 재사용용 `.proc`를 도입한다.
- 입력 파일 흐름은 `original CSV -> optional corrected CSV -> .slice -> .proc`다.
- corrected CSV는 측정 좌표 숫자를 회전하거나 보간하지 않고, 승인된 경계 이후의 마커 XYZ 열을 가역 순열로 재배치한다.
- 여러 이벤트는 시간순 suffix에 누적 적용하며, 매 저장 시 최초 관측 스트림에서 다시 계산해 중간 결정 변경이 뒤쪽 배치에 정확히 반영되도록 한다.
- `.slice`는 raw CSV 구조를 유지한 scene 파일이다.
- `.proc`는 기존 result CSV와 같은 multi-header 결과 구조를 사용한다.
- Result Resampling을 사용하는 경우에는 전체 slice baseline processing 결과를 먼저 만들고, 최종 결과 컬럼을 보간해 새 중간 timestamp row만 merge한다.
- `Limit to Time Range`가 켜진 경우에는 지정 구간 안에서만 중간 result row를 추가하고, 꺼진 경우에는 전체 slice 결과 구간에 추가한다.
- Result Resampling은 분석 정확도 향상 기능이 아니라 결과 시간축 보간 기능이며, 기존 timestamp의 position/velocity/acceleration/analysis 값은 유지한다.

### 4.4. 분석 단계와 후처리의 분리
- Step 1은 "원본에서 scene slice 만들기"에 집중한다.
- Step 1.5는 "slice에 processing 적용하기"에 집중한다.
- Step 2는 "결과 보기, 지점 추출, 시나리오 생성"에 집중한다.

## 5. 주요 컴포넌트
- `MainApp`
- `WidgetRawDataProcessing`
  - 원본/활성/review 기준 데이터 상태를 분리한다.
  - 검토 결정이 바뀐 상태에서는 `.slice` 생성을 막고 corrected source 저장을 요구한다.
- `WidgetSliceProcessing`
- `WidgetResultsAnalyzer`
- `CompareMainWindow`
  - 런처에서 독립적으로 열리는 다중 실험 비교 창. 요약표, 동기화된 3D 뷰어, 비교 그래프 레이아웃을 담당한다.
- `ComparisonModel`
  - 비교 윈도우에서 사용할 파일 목록, 파싱된 결과, 기준(baseline) 실험 설정 등을 관리한다.
- `PlotPopupDialog`
- `DataSelectionDialog`
- `PlotManager`
- `PipelineController`
- `artifact_io`
  - corrected source의 원자적 저장과 원본 식별 정보/결정 이력 보존을 담당한다.
- `MarkerFlipAnalyzer` / `FaceAssignmentAnalyzer`
  - 공통 후보 탐색과 v2 호환 모델을 유지한다. 새 GUI는 면 할당 후 실제 자세를 다시 계산하는 FaceAssignmentAnalyzer를 사용하며 자동 추천은 검증 대기다.
- `MarkerFlipReviewDialog`
  - 추천과 승인을 분리해 표시하고, 작업자 override와 안정 구간 그래프를 제공한다.
- `UniformResampler`
- `Parser`, `Slicer`, `Smoother`, `PoseOptimizer`, `VelocityCalculator`, `FrameAnalyzer`
- `DropPosturePostProcessor`
  - processing 완료 결과에서 Drop Posture frame/summary metric을 계산한다.
  - 접촉 판정은 threshold 단독이 아니라 높이, 하강/반전, 낮은 plateau, corner set 지속성을 함께 보는 evidence 기반 summary로 계산한다.
  - `ImpactEvent`가 없으면 `t1-` 기반 summary는 만들지 않고, 접촉 없는 구간도 frame metric과 max summary는 유지한다.
- `result_metric_descriptors`
  - Drop Posture summary UI label, tooltip, metric guide 설명, visual guide id를 정의한다.
  - Step 2 `3. Drop/Impact Summary`와 향후 compare window가 같은 설명 기준을 재사용하게 한다.
  - `ReferenceFace` descriptor는 접근(Approach) 자세 기준면임을 명시한다. 실제 충격 코너는 `FirstImpactContact`가 별도 기록한다.
  - `SustainedContact` 상태는 UI에서 `Stable floor contact`로 표시한다.

세부 책임은 `component_specs.txt`를 따른다.

## 6. 현재 설계상 유의점
- Marker Flip의 v3 mechanics는 독립적으로 선언한 비대칭 합성 배치와 실제 Parser/PoseOptimizer/GUI 저장 흐름으로 확인한다. 자동 추천은 보류 중이며 MuJoCo와 실제 OptiTrack 정답 검증은 남아 있다. 상세 실행 근거와 다음 작업은 `../reference/marker_flip_review_findings.md`, `../reference/marker_flip_fixture_contract.md`를 따른다.
- `.slice`는 line 0~1에 scene / box / timeline metadata를 가진다.
- `.slice`는 processing 재개용 파일이며, 원본 `.csv`를 다시 열지 않고 Step 1.5부터 시작할 수 있다.
- Step 2는 저장된 `.proc`만 직접 열 수 있다.
- Results Analyzer에는 현재 "현재 선택 컬럼으로 팝업 열기" 흐름이 구현되어 있다.
- popup subset 편집용 대화상자 파일은 존재하지만 메인 UI 버튼 흐름에는 노출되지 않는다.
- 문서상 과거 `main_app.py`나 prototype 기반 흐름은 더 이상 기준으로 보지 않는다.

## 7. 관련 설계 문서
- GUI 상세: `gui_overview.md`
- 데이터 구조: `../reference/pipeline_data_structures.txt`
- 컴포넌트 책임: `component_specs.txt`
- 시나리오 export 형식: `../reference/scenario_export_format.md`
- 개략 흐름: `workflow.txt`
- 레이아웃 개요: `gui_sketch.txt`
