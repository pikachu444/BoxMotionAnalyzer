# Slice / Processing Refactor Plan

Last Reviewed: 2026-03-18

## 목적
이 문서는 대용량 raw CSV를 scene 단위로 재사용 가능하게 만들기 위해, 현재 Step 1 중심 구조를 `Step 1 / Step 1.5 / Step 2`로 재구성하는 작업 계획을 정리한다.

핵심 목표는 아래와 같다.

- 큰 raw `.csv`를 매번 다시 열지 않도록 한다.
- scene 단위 slice를 저장해 재시작 후 바로 이어서 작업할 수 있게 한다.
- processing 실행을 slice 이후 단계로 분리한다.
- 기존 GUI의 구조와 레이아웃 감각을 최대한 유지한다.
- 특히 기존 Step 1 / Step 2의 plot 영역 크기와 splitter 기반 비율을 해치지 않는다.

## 현재 구조 요약

### 현재 Step 1
- raw CSV load
- parsed preview 생성
- slice range 지정
- resampling / processing mode 지정
- `Run Analysis`
- `Export Results to CSV`

### 현재 Step 2
- export된 결과 CSV 로드
- 결과 컬럼 플롯
- popup plot
- point export
- scenario export

### 현재 병목
- raw CSV가 크면 재실행/재시작 시 다시 load + parse해야 한다.
- slice와 processing이 한 번에 묶여 있어 scene 재사용이 어렵다.
- Step 2는 이미 결과 분석 UI가 밀도가 높아서 processing 입력 UI까지 넣기 어렵다.

## 목표 구조

### Step 1: Raw Data Slice
- 입력: `.csv`
- 역할:
  - raw CSV load
  - preview plot
  - scene 범위 선택
  - `.slice` 저장

### Step 1.5: Slice Processing
- 입력: `.slice`
- 역할:
  - slice load
  - processing mode / resampling / advanced settings 적용
  - processing 실행
  - `.proc` 저장

### Step 2: Results Analysis
- 입력: `.proc`
- 역할:
  - 결과 폴더 선택 및 파일 목록 탐색
  - 결과 시각화
  - peak / point 선택
  - point export
  - scenario export

## 파일 체계

### `.csv`
- raw 원본 파일
- Step 1 입력만 담당

### `.slice`
- raw CSV와 같은 텍스트 기반 구조를 유지한 scene 파일
- line 0~1: 메타 정보
- line 2~7: raw CSV 헤더 재구성
- line 8~: 선택 구간 + padding rows

권장 메타 예시:

```csv
BoxMotionAnalyzer Slice File,version=1,source=Run_07.csv,created=2026-03-17T12:34:56
scene=impact_02,box_l=1820.000,box_w=1110.000,box_h=164.000,full_start=0.000,full_end=100.000,user_start=40.000,user_end=70.000,padded_start=39.200,padded_end=70.800,pad_rows=50,row_count=128401
```

### `.proc`
- 기존 결과 `.csv` 포맷과 동일한 구조의 processed result 파일
- 확장자만 `.proc`
- current Step 2가 기대하는 result CSV 구조를 그대로 따르므로, Step 2 재사용성을 높인다.

## 주요 설계 결정

### 1. `.slice`는 새 바이너리 포맷을 만들지 않는다
- 기존 raw CSV 구조를 최대한 유지해 DataLoader / Parser 재사용성을 확보한다.
- 구현 난이도를 낮추고 사용자가 파일 의미를 직관적으로 이해할 수 있게 한다.

### 2. `.proc`는 기존 result CSV 구조를 그대로 따른다
- Step 2의 결과 로딩 로직을 최대한 유지한다.
- point export / scenario export 기능을 그대로 재사용한다.

### 3. padding은 좌우 50 rows 고정
- scene slice 저장 시 좌우로 50행씩 여유를 포함한다.
- processing mode별 padding 정책을 Step 1에서 미리 복잡하게 풀지 않는다.

### 4. processing 결과 저장은 Step 1.5 책임
- Step 1은 scene slice 저장까지만 담당
- Step 1.5는 processing 결과 생성 및 저장 담당
- Step 2는 결과 보기와 후처리 export 담당

### 5. 기존 GUI 레이아웃은 최대한 유지
- Step 1의 top plot + right panel + bottom controls 구조 유지
- Step 2의 Time Window + 3분할 + Main Plot 구조 유지
- plot이 작아지지 않도록 splitter 비율과 min width 정책 재검토 필요

## 구현 단계

### Phase 1. Slice 파일 저장 가능하게 만들기
- Step 1에서 raw CSV load 후 선택 구간(+padding 50 rows)을 `.slice`로 저장
- 현재 `header_info`로 raw header 6줄 재구성
- Step 1 UI에서 `Run Analysis` 대신 `Save Scene Slice` 중심으로 역할 조정

### Phase 2. Step 1.5 추가
- 새 `WidgetSliceProcessing` 추가
- `.slice` load 후 current DataLoader / Parser 재사용
- processing mode / resampling / advanced settings UI 배치
- `Run Processing`, `Save Processed Result` 추가

### Phase 3. Processing 파이프라인 단계화
- 현재 `PipelineController.run_analysis()` 내부를 재구성
- raw + parsed 입력 준비 단계와 processing 실행 단계를 분리
- 기존 알고리즘 모듈(Smoother / PoseOptimizer / VelocityCalculator / FrameAnalyzer)은 유지

### Phase 4. Step 2 입력 확장
- `.proc`를 current result loader가 읽을 수 있게 확장
- 기존 point/scenario export 유지

### Phase 5. 문서 및 테스트 정리
- GUI 설계 문서, workflow 문서, system design 문서 갱신
- 2단계 구조를 전제로 한 설명 수정
- 오래된 테스트 경로와 현재 구조가 섞인 부분 정리

## 예상 수정 대상
- `src/analysis/app/main_window.py`
- `src/analysis/ui/widget_raw_data_processing.py`
- `src/analysis/ui/widget_results_analyzer.py`
- `src/analysis/pipeline/pipeline_controller.py`
- `src/analysis/pipeline/data_loader.py`
- `src/config/config_analysis_ui.py`
- `docs/analysis/design/gui_overview.md`
- `docs/analysis/design/system_design.md`
- `docs/analysis/design/workflow.txt`

새 파일 후보:

- `src/analysis/ui/widget_slice_processing.py`

## 구현 시 주의점
- Step 1과 Step 2의 기존 plot 크기, splitter 동작, min width 정책을 먼저 보존해야 한다.
- Step 2는 processing 입력 UI를 흡수하지 않고 결과 분석 탭으로 유지해야 한다.
- 다음 Step을 대신 열어주는 cross-step 버튼은 두지 않고, 각 Step이 자기 단계 파일을 직접 열도록 유지한다.
- `.slice` / `.proc`는 앱 사용자가 단계 의미를 쉽게 이해할 수 있도록 단순하게 유지한다.

## 다음 세션 재개 기준
- 현재 작업 브랜치: `codex/slice-first-workflow-followup`
- 현재 작업 worktree: `/root/BoxMotionAnalyzer-slice-mockup`
- 재개 시 우선 확인 파일:
  - `src/analysis/app/main_window.py`
  - `src/analysis/ui/widget_raw_data_processing.py`
  - `src/analysis/ui/widget_results_analyzer.py`
  - `src/analysis/pipeline/pipeline_controller.py`
  - 이 문서
