# 소프트웨어 설계 문서 (현재 기준): Box Motion Analyzer GUI

Last Reviewed: 2026-03-17

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
- Plot target / axis 선택
- Slice Range 지정
- `.slice` 저장
- 미리보기 플롯과 하단 제어 영역 사이에는 세로 splitter가 있어, 창 높이 증가분이 플롯에 우선 배분되고 사용자가 플롯 높이를 직접 조절할 수 있다.

### 3.2. Step 1.5: Slice Processing
- `.slice` 로드
- `.slice` 메타에 포함된 box dimensions 자동 적용
- Optional uniform resampling 지정
- `Processing Mode` 선택 (`Raw / Smoothing / Advanced`)
- `Advanced Settings...` 다이얼로그 사용
- processing 실행
- `.proc` 저장
- 저장된 `.proc`를 Step 2로 전달
- Step 1과 같은 splitter 기반 상단 plot / 우측 패널 / 하단 controls 구조를 유지한다.

### 3.3. Step 2: Results Analysis
- 결과 폴더 / 파일 선택
- 단일 `.proc` 파일 직접 열기
- Multi-header 결과 컬럼 트리 표시
- 메인 플롯 비교
- 팝업 플롯 열기
- 선택 시점 분석
- point export
- scenario export
- 상단 분석 제어 영역과 하단 메인 플롯 사이에는 세로 splitter가 있어, 기본 레이아웃을 유지하면서도 메인 플롯 높이를 수동 조절할 수 있다.

### 3.4. Step 간 연결
- Step 1은 `.slice`를 만든 뒤 Step 1.5로 넘긴다.
- Step 1.5는 `.proc`를 저장한 뒤 Step 2가 그 파일을 열게 한다.
- `.proc`는 기존 result CSV와 동일한 multi-header 구조를 사용한다.
- processing 결과에는 Full/Slice timeline metadata가 함께 포함된다.

## 4. 핵심 설계 원칙

### 4.1. 파이프라인 제어와 UI 분리
- UI는 설정 수집과 결과 표시를 담당한다.
- 실제 분석 순서 제어는 `PipelineController`가 담당한다.
- resampling factor 기반 옵션 보정 규칙처럼 UI/Qt와 무관한 계산 로직은 순수 모듈로 분리한다.
- processing mode 라벨과 기본 preset 같은 UI 정책은 `src/config/config_analysis_ui.py`에서 관리한다.

### 4.2. 컬럼 정의의 중앙 관리
- 컬럼명, Multi-header 규칙, Results Analyzer 표시 순서는 `src/config/data_columns.py`에서 관리한다.
- 새 분석 결과를 추가할 때도 우선 이 파일 기준으로 맞춘다.

### 4.3. 단계 파일 기반 처리
- 처리 단계 내부는 여전히 DataFrame 기반으로 동작한다.
- 단, 사용자 workflow 개선을 위해 scene 재사용용 `.slice`와 processed result 재사용용 `.proc`를 도입한다.
- `.slice`는 raw CSV 구조를 유지한 scene 파일이다.
- `.proc`는 기존 result CSV와 같은 multi-header 결과 구조를 사용한다.
- resampling을 사용하는 경우에도 parsed slice 이후 DataFrame을 uniform time grid로 재구성한 뒤 후속 분석을 수행한다.

### 4.4. 분석 단계와 후처리의 분리
- Step 1은 "원본에서 scene slice 만들기"에 집중한다.
- Step 1.5는 "slice에 processing 적용하기"에 집중한다.
- Step 2는 "결과 보기, 지점 추출, 시나리오 생성"에 집중한다.

## 5. 주요 컴포넌트
- `MainApp`
- `WidgetRawDataProcessing`
- `WidgetSliceProcessing`
- `WidgetResultsAnalyzer`
- `PlotPopupDialog`
- `DataSelectionDialog`
- `PlotManager`
- `PipelineController`
- `artifact_io`
- `UniformResampler`
- `Parser`, `Slicer`, `Smoother`, `PoseOptimizer`, `VelocityCalculator`, `FrameAnalyzer`

세부 책임은 `component_specs.txt`를 따른다.

## 6. 현재 설계상 유의점
- `.slice`는 line 0~1에 scene / box / timeline metadata를 가진다.
- `.slice`는 processing 재개용 파일이며, 원본 `.csv`를 다시 열지 않고 Step 1.5부터 시작할 수 있다.
- Step 2는 저장된 `.proc` 또는 기존 결과 `.csv`만 열 수 있다.
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
