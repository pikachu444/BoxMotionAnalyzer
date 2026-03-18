# Box Motion Analyzer v2.2 GUI 구조 설명서

Last Reviewed: 2026-03-18

## 개요
이 문서는 현재 구현된 분석 GUI의 구조를 설명한다. 기준 코드는 `src/analysis/app/main_window.py`, `src/analysis/ui/widget_raw_data_processing.py`, `src/analysis/ui/widget_slice_processing.py`, `src/analysis/ui/widget_results_analyzer.py`이다.

## 1. 전체 구조
- 메인 분석 창은 `QTabWidget` 기반의 3단계 흐름으로 구성된다.
- `Step 1: Raw Data Slice`
  - 원본 CSV 로드, 미리보기, 슬라이스 범위 지정, `.slice` 저장
- `Step 1.5: Slice Processing`
  - `.slice` 로드, processing mode / resampling 설정, processing 실행, `.proc` 저장
- `Step 2: Results Analysis`
  - `.proc` 또는 기존 결과 `.csv` 로드, 컬럼 선택 플롯, 팝업 플롯, 지점 분석, 시나리오 CSV 내보내기
- 하단 `QStatusBar`는 파일 로드, 처리 진행, 저장 성공/실패 상태를 표시한다.

## 2. Step 1: Raw Data Slice
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
- `Slice Output`
  - `Scene Name`
  - 고정 padding 설명 (`50 rows on each side`)
  - 최근 저장된 `.slice` 경로 표시
- 실행 버튼
  - `Save Scene Slice`

### 2.3. 주요 동작
- 파일 로드 시 `DataLoader`와 `Parser`가 즉시 미리보기용 데이터를 준비한다.
- `Save Scene Slice`는 현재 박스 크기, 슬라이스 범위, scene 이름을 사용해 `.slice` 파일을 저장한다.
- `.slice`는 기존 raw CSV 구조를 유지하지만, 상단 2줄에는 scene / box / timeline metadata를 추가한다.
- 저장 시 선택 구간 양옆에 `50 rows` padding을 포함한다.

## 3. Step 1.5: Slice Processing
`WidgetSliceProcessing`이 담당한다.

### 3.1. 상단 레이아웃
- 좌측: Matplotlib 그래프와 네비게이션 툴바
  - `.slice`를 다시 파싱한 `parsed_data`를 기준으로 preview를 그린다.
- 우측: 제어 패널
  - `Load Slice File...`
  - 선택된 `.slice` 경로 표시
  - `Slice Summary`
    - source
    - user range
    - padded range
  - `Box Dimensions (mm)`
    - `.slice` 메타에 저장된 box 치수를 읽어 자동으로 채운다
  - 로그 출력 텍스트 영역

### 3.2. 하단 컨트롤
- `Plot Options`
  - Step 1과 같은 preview 선택 구조를 유지한다
- `Resampling`
  - processing 전에 uniform time grid로 샘플을 보간할지 결정한다
- `Processing Mode`
  - Raw / Smoothing / Advanced
  - `Advanced Settings...` 다이얼로그 재사용
- `Processing Output`
  - 현재 처리 상태
  - 최근 저장된 `.proc` 경로
- 실행 버튼
  - `Run Processing`
  - `Save Processed Result`

### 3.3. 주요 동작
- `.slice`를 열면 `DataLoader.load_csv()`와 `Parser.process()`를 다시 사용해 parsed slice를 준비한다.
- processing은 `PipelineController.run_analysis_from_parsed()`를 통해 실행한다.
- 완료된 결과는 `.proc` 저장 전까지 임시 상태로 유지된다.

## 4. Step 2: Results Analysis
`WidgetResultsAnalyzer`가 담당한다.

### 4.1. Time Window 영역
- Active File
- Number of Samples
- Full timeline / Slice timeline 정보 문자열
- Slice 구간을 시각적으로 보여주는 막대형 타임라인

### 4.2. 본문 3분할 레이아웃
- `1. Result Files`
  - `Select Result Folder...`
  - 읽기 전용 Folder Path
  - 결과 `.proc` / `.csv` 목록
- `2. Data Selection`
  - 결과 컬럼 트리 (`QTreeWidget`)
  - 내부 선택값은 `(L1, L2, L3)` tuple을 유지하지만, 사용자에게는 `Velocity X (Box Local Frame)` 같은 표시명을 노출
  - 트리 아래 안내 라벨이 raw export key 대신 표시명이 보인다는 점을 예시와 함께 설명
  - `Clear Selection`
  - `Plot Selected Results`
  - `Open Popup (Current Selection)`
  - `Close All Popups`
  - Opened Popups / Checked Columns 상태 표시
- `3. Peak & Point Selection`
  - `Target`
  - 현재 Target 기준으로 peak search가 동작한다는 안내 라벨
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

### 4.3. 하단 메인 플롯
- 현재 체크된 결과 컬럼을 한 그래프에 겹쳐서 표시한다.
- 범례와 타겟 선택 문자열은 raw schema key를 직접 이어붙이지 않고, export 의미를 풀어쓴 표시명을 사용한다.
- 그래프 클릭 시 가장 가까운 시점을 선택한다.
- 선택된 시점은 붉은 수직선 커서와 선택 정보 레이블로 반영된다.

### 4.4. 팝업 플롯
- `PlotPopupDialog`는 현재 체크된 컬럼 집합으로 별도 창을 연다.
- 팝업 그래프도 클릭 가능하며, 선택된 시간이 메인 Step 2와 동기화된다.
- 현재 구현은 "현재 선택 항목으로 팝업 열기"만 지원하며, 별도 subset 편집 버튼은 노출하지 않는다.

## 5. 현재 사용자 흐름
1. Step 1에서 원본 CSV를 로드한다.
2. 필요한 데이터와 축, 슬라이스 범위를 조정한다.
3. `.slice`를 저장한다.
4. Step 1.5에서 저장한 `.slice`를 연다.
5. 필요하면 resampling factor와 processing mode를 조정한다.
6. processing을 실행한다.
7. `.proc`를 저장한다.
8. Step 2에서 결과 폴더를 선택하고 저장된 `.proc`를 목록에서 연다.
9. Step 2에서 컬럼을 체크하고 메인 플롯 또는 팝업 플롯으로 비교한다.
10. 특정 시점을 선택하거나 최대값을 찾아 point export 또는 scenario export를 수행한다.
