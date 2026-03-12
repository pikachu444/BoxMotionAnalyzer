# Box Motion Analyzer v2.2 GUI 구조 설명서

Last Reviewed: 2026-03-12

## 개요
이 문서는 현재 구현된 분석 GUI의 구조를 설명한다. 기준 코드는 `src/analysis/main_window.py`, `src/analysis/ui/widget_raw_data_processing.py`, `src/analysis/ui/widget_results_analyzer.py`이다.

## 1. 전체 구조
- 메인 분석 창은 `QTabWidget` 기반의 2단계 흐름으로 구성된다.
- `Step 1: Raw Data Processing`
  - 원본 CSV 로드, 미리보기, 슬라이스 범위 지정, 분석 실행, 결과 CSV 내보내기
- `Step 2: Results Analysis`
  - 결과 CSV 로드, 컬럼 선택 플롯, 팝업 플롯, 지점 분석, 시나리오 CSV 내보내기
- 하단 `QStatusBar`는 파일 로드, 분석 진행, 내보내기 성공/실패 상태를 표시한다.

## 2. Step 1: Raw Data Processing
`WidgetRawDataProcessing`이 담당한다.

### 2.1. 상단 레이아웃
- 좌측: Matplotlib 그래프와 네비게이션 툴바
  - 파일 로드 직후 파싱된 `parsed_data`를 기준으로 미리보기 그래프를 그린다.
  - `PlotManager`가 확대/축소, 마우스 오버, 슬라이스 구간 선택을 처리한다.
- 우측: 제어 패널
  - `Load CSV File...`
  - 선택된 파일 경로 표시
  - `Box Dimensions (mm)` 입력
  - 로그 출력 텍스트 영역

### 2.2. 하단 컨트롤
- `Plot Options`
  - `Select Data...`
  - 선택된 대상 표시
  - 축 선택 콤보박스 (`Position-X`, `Position-Y`, `Position-Z`)
- `Slice Range`
  - 체크 가능한 그룹 박스
  - 활성화 시 `Start`, `End` 입력값과 그래프 구간 선택기가 동기화된다
- `Resampling`
  - 분석 전에 uniform time grid로 샘플을 보간할지 결정한다
  - `Enable Resampling` 체크 시 factor(`2x` ~ `5x`)를 선택할 수 있다
  - 설명 라벨로 interpolation 기반 시간 해상도 증가 기능임을 안내한다
- `Processing Mode`
  - Standard / Raw / Advanced 라디오 버튼
  - 아래 설명 라벨로 현재 모드의 성격을 안내한다
- 실행 버튼
  - `Run Analysis`
  - `Export Results to CSV`

### 2.3. 주요 동작
- 파일 로드 시 `DataLoader`와 `Parser`가 즉시 미리보기용 데이터를 준비한다.
- `Run Analysis`는 현재 박스 크기, 슬라이스 범위, resampling 옵션, processing mode를 설정 딕셔너리로 만들어 `PipelineController`에 전달한다.
- `Export Results to CSV`는 최종 분석 결과에 Full/Slice timeline metadata를 추가한 뒤 multi-header CSV로 저장한다.
- 내보내기 성공 시 저장한 결과 파일을 Step 2에 즉시 로드하고, 탭도 Step 2로 전환한다.

## 3. Step 2: Results Analysis
`WidgetResultsAnalyzer`가 담당한다.

### 3.1. Time Window 영역
- Active File
- Number of Samples
- Full timeline / Slice timeline 정보 문자열
- Slice 구간을 시각적으로 보여주는 막대형 타임라인

### 3.2. 본문 3분할 레이아웃
- `1. Result Files`
  - `Select Result Folder...`
  - 읽기 전용 Folder Path
  - 결과 CSV 목록
- `2. Data Selection`
  - 결과 컬럼 트리 (`QTreeWidget`)
  - `Clear Selection`
  - `Plot Selected Results`
  - `Open Popup (Current Selection)`
  - `Close All Popups`
  - Opened Popups / Checked Columns 상태 표시
- `3. Peak & Point Selection`
  - `Target`
  - `Find: Abs Max / Max / Min`
  - `Selected Point`
  - `Export Point Data...`
- `4. Export Analysis Input`
  - `Manual Offset`
  - `Manual Height`
  - `Offset0~2`
  - `Run Time`
  - `Step`
  - `Scene Name`
  - `Export Scenario CSV`

### 3.3. 하단 메인 플롯
- 현재 체크된 결과 컬럼을 한 그래프에 겹쳐서 표시한다.
- 그래프 클릭 시 가장 가까운 시점을 선택한다.
- 선택된 시점은 붉은 수직선 커서와 선택 정보 레이블로 반영된다.

### 3.4. 팝업 플롯
- `PlotPopupDialog`는 현재 체크된 컬럼 집합으로 별도 창을 연다.
- 팝업 그래프도 클릭 가능하며, 선택된 시간이 메인 Step 2와 동기화된다.
- 현재 구현은 "현재 선택 항목으로 팝업 열기"만 지원하며, 별도 subset 편집 버튼은 노출하지 않는다.

## 4. 현재 사용자 흐름
1. Step 1에서 원본 CSV를 로드한다.
2. 필요한 데이터와 축, 슬라이스 범위를 조정한다.
3. 필요하면 resampling factor를 선택한다.
4. 분석을 실행한다.
5. 결과를 CSV로 내보낸다.
6. 저장 직후 Step 2가 열리고 방금 저장한 결과 파일이 자동 로드된다.
7. Step 2에서 컬럼을 체크하고 메인 플롯 또는 팝업 플롯으로 비교한다.
8. 특정 시점을 선택하거나 최대값을 찾아 point export 또는 scenario export를 수행한다.
