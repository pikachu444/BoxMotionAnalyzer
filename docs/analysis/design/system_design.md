# 소프트웨어 설계 문서 (현재 기준): Box Motion Analyzer GUI

Last Reviewed: 2026-03-08

## 1. 개요
이 문서는 현재 구현된 Box Motion Analyzer의 분석 GUI 구조를 요약한다. 목표는 원본 CSV 기반 분석 파이프라인과 결과 분석 기능을 하나의 PySide6 애플리케이션 안에서 일관되게 제공하는 것이다.

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
분석 GUI는 `MainApp` 하나로 묶이고, 내부는 Step 1 / Step 2 탭으로 분리된다.

### 3.1. Step 1: Raw Data Processing
- 원본 CSV 로드
- 파싱 기반 미리보기 플롯
- Plot target / axis 선택
- Slice Range 지정
- 분석 실행
- 결과 CSV export

### 3.2. Step 2: Results Analysis
- 결과 폴더 / 파일 선택
- Multi-header 결과 컬럼 트리 표시
- 메인 플롯 비교
- 팝업 플롯 열기
- 선택 시점 분석
- point export
- scenario export

### 3.3. Step 간 연결
- Step 1에서 결과를 export하면 Step 2가 방금 저장한 파일을 자동 로드한다.
- export 시 Full/Slice timeline metadata가 결과 CSV에 함께 저장된다.

## 4. 핵심 설계 원칙

### 4.1. 파이프라인 제어와 UI 분리
- UI는 설정 수집과 결과 표시를 담당한다.
- 실제 분석 순서 제어는 `PipelineController`가 담당한다.

### 4.2. 컬럼 정의의 중앙 관리
- 컬럼명, Multi-header 규칙, Results Analyzer 표시 순서는 `src/config/data_columns.py`에서 관리한다.
- 새 분석 결과를 추가할 때도 우선 이 파일 기준으로 맞춘다.

### 4.3. 단일 DataFrame 기반 처리
- 중간 단계마다 파일을 만들지 않고 DataFrame을 누적 확장한다.
- 최종 결과만 export 단계에서 CSV로 저장한다.

### 4.4. 분석 결과와 후처리의 분리
- Step 1은 "계산과 저장"에 집중한다.
- Step 2는 "불러오기, 비교, 지점 추출, 시나리오 생성"에 집중한다.

## 5. 주요 컴포넌트
- `MainApp`
- `WidgetRawDataProcessing`
- `WidgetResultsAnalyzer`
- `PlotPopupDialog`
- `DataSelectionDialog`
- `PlotManager`
- `PipelineController`
- `Parser`, `Slicer`, `Smoother`, `PoseOptimizer`, `VelocityCalculator`, `FrameAnalyzer`

세부 책임은 `component_specs.txt`를 따른다.

## 6. 현재 설계상 유의점
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
