# 소프트웨어 설계 문서 (현재 기준): Box Motion Analyzer GUI

Last Reviewed: 2026-09-18

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
- `src/simulation/`
  - 기존 직접 `.proc` 출력과 선택적 마커 관측 생성. `history_trajectory`가 실제 시각·월드 축 변환·body origin/COM을 공통 제공하고 `marker_export`가 기존 `write_observations`를 호출한다. GUI는 완성된 관측 CSV만 별도 `MainApp`에 전달한다.
- `src/config/`
  - 설정값과 컬럼 정의

#123의 구간 신호 선택은 기존 단일 그래프를 사용한다. 검출 완료 시 현재 선택을 확인해 유효한 선택을 유지하고 첫 검출에는 수직 속도를 표시한다. 검출·작업 열기 콜백은 worker와 기존 파일 변경 번호·경로·SHA를 확인한다. 파일 교체 후 이전 결과·오류·취소가 새 작업에 적용되지 않으며, 완료 신호가 대기 중이어도 명시적 취소를 존중한다. 검출 알고리즘과 저장 스키마는 동일하다.

## 3. 분석 GUI 설계
분석 GUI는 `MainApp` 하나로 묶이고, 내부는 Step 1 / Step 1.5 / Step 2 탭으로 분리된다.

### 3.1. Step 1: Raw Data Slice
- 마커 검토의 원본 context는 `review_parsed_data`의 위치 열만 독립 복사한다. 별도 pose fitting이나 정답 파일 접근 없이 실제 시각·XYZ를 표시하며, dialog 종료 시 그래프와 복사본을 해제한다. 모달 종료 후 source/revision/dimensions 비교와 비동기 바이트 검증을 통과해야 선택을 반영한다.
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
- Single/Batch 입력과 결과를 별도로 보존한다. 좌측에는 입력·방법·실행 버튼을, 우측에는 단일 미리보기 또는 정확한 배치 파일 목록을 둔다. 세부 설정만 스크롤한다.

### 3.3. Step 2: Results Analysis
- 결과 폴더 선택
- 결과 목록에서 `.proc` 선택
- Multi-header 결과 컬럼 트리 표시
- `Group By (Metric / Object)` 전환
- 현재 트리를 유지한 검색 필터
- Drop Posture `Summary` grouped table 표시
- Drop Posture metric guide와 descriptor 기반 tooltip 표시
- 메인 플롯 비교
- 팝업 플롯 열기
- 선택 시점 분석
- point export
- scenario export
- 좌측 측정값 선택 영역과 우측 그래프 사이의 가로 splitter로 폭을 조절한다. 그래프 아래에서 점을 선택·저장하며, 전체 요약과 시나리오 출력 설정은 접어서 연다.
- 현재 파일·시간을 상단에 표시한다. Open/Folder/Compare는 기본 조작이며, 입력 경로는 파일명과 별도로 보존한다.

### 3.4. Step 간 연결
- Step 1은 원본 CSV를 보존하고, 필요하면 별도 corrected CSV를 만든 뒤 현재 활성 입력에서 `.slice`를 생성한다.
- Save and Process는 Step 1에서 저장에 성공한 정확한 경로 목록을 Step 1.5에 한 번 전달한다. 하나면 Single, 여러 개면 Batch를 준비하고 Run은 사용자가 실행한다.
- Step 1.5는 `.slice`를 열어 `.proc`를 생성한다. 단일 Save and View, 배치 View Results는 실제 저장된 결과 목록을 Step 2에 전달한다. 실패/건너뛴 파일을 새 결과로 전달하지 않는다.
- Step 2는 직접 파일/폴더를 열거나 전달된 결과를 읽는다. Compare는 현재/선택 결과를 기존 비교 창에 추가하며 이미 열린 경로와 기준 선택을 보존한다.
- 처리 중 입력 교체를 막는다. 미저장 단일 결과를 교체할 때만 Save/Discard/Cancel을 제공하며, 배치 전환은 단일 결과를 버리지 않는다. `.proc`는 임시 파일 작성 성공 후 교체한다.
- `.proc`는 기존 result CSV와 동일한 multi-header 구조를 사용한다.
- processing 결과에는 Full/Slice timeline metadata가 함께 포함된다.
- corrected 입력을 사용한 경우 `.slice`와 `.proc`에는 실제 corrected source, 원본 이름/SHA-256, 전체 검토 결정과 승인 수가 함께 전달된다.
- processing 결과에는 낙하각, 방향 각도, 최저 코너, 기준면 코너 높이 차이, 접촉 상태와 같은 Drop Posture metric도 포함된다.

### 3.5. 비교와 표시
- Compare의 Individual/Aligned 상태를 곡선과 3D가 공유한다. 파일별 색·선택·카메라·개별 행을 보존하며 데이터가 교체될 때만 해당 VTK 뷰어를 다시 만든다.
- 표시 이름·단위는 저장 키와 분리한다. 각도 자동 축 폭은 최소 1도이며 회전벡터에는 동일 폭의 rad를 적용한다. 미분량·길이·원본 값·사용자 확대는 바꾸지 않는다.
- 꼭짓점 ID는 점과 범주 축을 사용하고 요약에서 번호를 빼지 않는다. Step 2의 혼합 플롯은 별도 범주 축을 사용하며 점 선택·팝업·실패 시 복원도 해당 축을 유지한다.

### 지표별 관측 해소 (#119)

비교 계층은 기존 loader의 metric value/reason을 그대로 받아 compatibility → observation → metric variants → statistics 순서로 처리한다. `observation_resolution.py`는 I/O와 Qt가 없는 순수 해소기다. `data_model.py`의 Impact와 Contact adapter는 서로 다른 기존 호환성·유효성 계약을 유지한다. Contact의 intended-contact 충돌도 local 호환성과 registration 검사 후 그 집단 안에서만 찾는다.

canonical-exact-v1은 유한 float와 정규화된 범주를 정확히 비교한다. 표시 반올림·허용오차·baseline·로드 순서는 authority가 아니다. 관측 key의 고정 순서로 통계를 계산하며 출처 전체와 무효/충돌 근거를 반환한다. 재계산 시 현재 파일 집합을 사용하므로 교체·삭제 후 과거 근거가 남지 않는다. 비교 결과는 저장 파일을 변경하지 않는다.

## 4. 핵심 설계 원칙

자세 또는 코너가 불완전한 행은 원래 시간축에 유지한다. 프레임별 기하 지표는 유효한 행만 계산하지만, 전체 구간에 의존하는 접촉 계산에는 잘라낸 입력을 전달하지 않는다. 이 경우 접촉 요약은 `Unavailable`로 남기고 비교에서 자료 부족을 표시한다. 일반 exporter에서 실제 재계산까지의 검증과 정답 접근 차단은 [일반 생성 경로 검증](../reference/general_export_recovery.md)에 기록한다.

### 4.1. 파이프라인 제어와 UI 분리
- UI는 설정 수집과 결과 표시를 담당한다.
- 실제 분석 순서 제어는 `PipelineController`가 담당한다.
- Result Resampling처럼 UI/Qt와 무관한 계산 로직은 순수 모듈로 분리한다.
- processing mode 라벨과 기본 preset 같은 UI 정책은 `src/config/config_analysis_ui.py`에서 관리한다.
- Marker Flip Review는 분석 결과 포즈를 사후 회전하는 단계가 아니다. Step 1에서 원시 마커 열의 의미를 검토하고 corrected source를 만드는 입력 정리 단계다.
- `PipelineController`는 corrected CSV에 저장된 v3 행별 면 할당을 사용하며 승인 이력을 다시 적용하지 않는다. v2 열 순열은 별도 호환 경로로 읽는다.

### 4.2. 컬럼 정의의 중앙 관리
- 컬럼명, Multi-header 규칙, Results Analyzer 표시 순서는 `src/config/data_columns.py`에서 관리한다.
- Drop Posture summary의 표시명, group, tooltip, metric guide 설명은 `src/config/result_metric_descriptors.py`에서 관리한다.
- Results Analyzer는 raw multi-header tuple을 유지한 채, UI에서만 `Metric-first`와 `Object-first` 두 가지 계층으로 재구성한다.
- 새 분석 결과를 추가할 때도 우선 이 파일 기준으로 맞춘다.

### 4.3. 단계 파일 기반 처리
- 처리 단계 내부는 여전히 DataFrame 기반으로 동작한다.
- 단, 사용자 workflow 개선을 위해 scene 재사용용 `.slice`와 processed result 재사용용 `.proc`를 도입한다.
- 입력 파일 흐름은 `original CSV -> optional corrected CSV -> .slice -> .proc`다.
- v3 corrected CSV는 Rigid Body Marker XYZ와 ID를 보존하고, 승인된 경계 이후의 분석용 면 할당을 바꾼다. 저장과 로딩 시 최초 면 및 전체 승인 이력으로 재구성한 면과 실제 annotation을 대조하여 불일치를 거부한다. 경계 이후만 담은 slice에도 이전 사건의 누적 상태를 검증한다.
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
  - `utils/artifact_metadata.py`에서 출처/호환성 전체 사유를, `utils/result_time.py`에서 canonical timestamp와 t1 계약을 공유한다. 미호환 파일은 개별 열람을 유지하고 기준 차이/집계 대상에서 제외한다.
  - 그래프는 파일별 실제 elapsed 시각을 유지한다. 3D row ID는 원본 frame 번호와 분리하며 가장 가까운 실제 샘플 시각을 명시한다. 긴 gap/범위 밖은 보간·끝점 고정 없이 unavailable로 표시한다.
  - `utils/first_event_evidence.py`의 버전 있는 저장 사건 일관성 검증을 Impact/Contact가 공유한다. 진단의 사건 지원, 속도 적합 지원, 의도 접촉의 기하 검증을 분리하며 지표별 제외 사유를 Details/Repeats까지 전달한다. 기존 파일과 producer 정책은 수정하지 않는다. bounded 검출·저장 정책은 #120의 별도 범위다.
- `PlotPopupDialog`
- `DataSelectionDialog`
- `PlotManager`
- `PipelineController`
- `artifact_io`
  - corrected source의 원자적 저장과 원본 식별 정보/결정 이력 보존을 담당한다.
  - 별도 public artifact whitelist를 raw metadata → corrected/slice metadata → `Info/Artifact` proc 상수 열로 전달한다. test-only truth/event manifest를 읽지 않는다. 저장 형식은 `result_schema_notes.md`를 기준으로 한다.
  - 처리 설정은 raw 선언에서 복사하지 않는다. `processing_provenance.py`가 실행한 단계의 configured object/policy를 기록하고, `utils/processing_settings.py`가 canonical JSON과 식별 hash를 생성한다. 실행 이력이 없는 결과는 현재 기본값으로 호환 승격하지 않는다.
- `MarkerFlipAnalyzer` / `FaceAssignmentAnalyzer`
  - 기존 v2 호환 모델을 유지한다. FaceAssignmentAnalyzer는 실제 국소 refit의 조건부 NONE/X/Y/Z 추천을 제공하며 승인은 기본 OFF다.
- `marker_review` / `MarkerReviewWorker`
  - observation-only O(N) scan 후 이벤트별 최대 30 frame fits를 수행한다. 원본·활성 digest, 치수·geometry, face 이력, 실제 창과 계산 설정에 결과를 결합한다.
  - 준비·scan·optimizer·Done 검증의 협력 취소와 오래된 결과 폐기를 관리한다. 기존 승인·원본·corrected 저장 계약과 #121의 source 수명을 공유한다. [실행 계약](../reference/marker_review_execution.md)을 참고한다.
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
- Marker Flip의 v3 mechanics와 조건부 추천은 독립 공개 합성 입력·MuJoCo·실제 Parser/PoseOptimizer/GUI 저장 흐름으로 확인한다. 실제 OptiTrack 교정 정확도는 #104에서 미검증이다. 상세 근거는 `../reference/marker_flip_review_findings.md`, `../reference/marker_flip_fixture_contract.md`, `../reference/marker_review_execution.md`를 따른다.
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
