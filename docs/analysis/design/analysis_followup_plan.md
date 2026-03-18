# Analysis Follow-up Plan

Last Reviewed: 2026-03-18

## 목적
이 문서는 현재 구현된 `Step 1 / Step 1.5 / Step 2` workflow 이후에 남아 있는 후속 작업을 정리한다.

현재 기준 구현 범위는 아래까지 완료된 상태다.
- Step 1에서 raw `.csv`를 열고 `.slice`를 저장
- Step 1.5에서 `.slice`를 열고 processing 후 `.proc`를 저장
- Step 2에서 결과 폴더 기반으로 `.proc` 또는 기존 결과 `.csv`를 선택해 분석
- Step 간 cross-step 열기 버튼 제거

이 문서는 "현재 구현된 기능"을 설명하는 문서가 아니라, 다음 세션에서 이어서 작업할 항목을 정리하는 문서다.

## 현재 남은 핵심 작업

### 1. Step 1.5 Batch Processing 추가
현재 Step 1.5는 `.slice` 파일을 하나씩 열어 processing하는 흐름만 지원한다.

다음 단계에서는 동일한 processing 설정으로 여러 `.slice` 파일을 한 번에 처리하는 batch workflow를 추가한다.

핵심 방향:
- 대상은 `Step 1.5`로 한정한다.
- `Step 2`의 폴더 + 리스트 구조는 그대로 유지한다.
- 기존 single-file processing 흐름은 유지한다.
- batch processing은 "추가 기능"으로 넣고, 현재 UI를 크게 뒤엎지 않는다.

### 2. 실제 GUI 수동 검증
현재 구현은 코드/문서 기준으로 정리됐지만, 실제 Windows GUI에서 아래를 다시 확인해야 한다.
- Step 1 하단 control 폭과 정렬이 자연스러운지
- Step 1.5 하단 control 폭과 정렬이 자연스러운지
- plot 영역이 작아지지 않았는지
- splitter 기본 비율이 기존 사용감과 크게 다르지 않은지
- Step 2의 폴더 + 리스트 결과 탐색이 실사용에 충분한지

### 3. 테스트 보강
현재는 syntax check와 일부 round-trip smoke test 중심이다.

남은 테스트 작업:
- `.slice` 저장 후 다시 load해서 processing 가능한지
- `.proc` 저장 후 Step 2에서 읽을 수 있는지
- batch processing 추가 후 skip/overwrite 정책이 의도대로 동작하는지

## Batch Processing 계획

### 1. 목표 동작
사용자가 Step 1.5에서 특정 폴더를 선택하면, 그 안의 `.slice` 파일들을 현재 processing 설정으로 순차 처리하고 `.proc` 파일로 저장할 수 있어야 한다.

예:
- `scene_01.slice` -> `scene_01.proc`
- `scene_02.slice` -> `scene_02.proc`

### 2. 파일명 정책
- 기본 정책은 `.slice`와 같은 base name을 사용해 `.proc`를 만든다.
- 예:
  - `impact_01.slice` -> `impact_01.proc`
  - `impact_02.slice` -> `impact_02.proc`

현재 계획에서는 mode별 다른 출력 파일을 동시에 보관하는 복잡한 naming은 도입하지 않는다.
즉, batch processing은 "현재 선택된 하나의 processing 설정을 폴더 전체에 적용한다"는 전제를 둔다.

### 3. 기존 `.proc` 처리 정책
가장 중요한 기본 정책은 `skip existing` 이다.

기본 동작:
- 같은 base name의 `.proc`가 이미 있으면 건너뛴다.

옵션:
- `[ ] Overwrite existing .proc`

의미:
- unchecked: 기존 `.proc`가 있으면 skip
- checked: 기존 `.proc`가 있으면 overwrite

이 체크박스는 `Run Batch Processing` 버튼 근처에 둔다.

### 4. UI 방향
Step 1.5에 아래 요소를 추가하는 방향을 우선 검토한다.

- `Select Slice Folder...`
- 선택된 폴더 경로 표시
- `Run Batch Processing`
- `[ ] Overwrite existing .proc`
- batch 결과 요약 라벨 또는 로그 출력

중요 원칙:
- 현재 single-file workflow를 해치지 않는다.
- 기존 plot / right panel / bottom controls 구조를 크게 깨지 않는다.
- batch 기능 때문에 plot 영역이 작아지지 않도록 한다.

### 5. 실행 결과 요약
batch processing 완료 후 최소한 아래 정보를 사용자에게 제공해야 한다.
- total files
- processed
- skipped
- failed

예:
- `Batch complete: total=16, processed=4, skipped=12, failed=0`

### 6. 구현 순서
1. Step 1.5 UI에 batch controls 추가
2. 지정 폴더의 `.slice` 파일 목록 스캔
3. 현재 processing 설정으로 순차 실행
4. `.proc` 저장 경로 계산
5. `Overwrite existing .proc` 체크박스 정책 반영
6. 처리 결과 요약 출력
7. 문서/테스트 갱신

## 구현 시 주의점
- batch processing은 아직 구현되지 않았으므로, 현재 문서에서는 "현재 기능"처럼 서술하지 않는다.
- Step 2는 계속 결과 분석 탭으로 유지한다.
- Step 1이나 Step 2에 batch 기능을 끼워 넣지 않는다.
- 기존 single-file `.slice -> .proc` 흐름은 반드시 유지한다.
- UI 단순성을 해치지 않도록 cross-step shortcut 버튼은 다시 만들지 않는다.

## 다음 세션 재개 시 우선 확인 파일
- `src/analysis/ui/widget_slice_processing.py`
- `src/analysis/app/main_window.py`
- `src/analysis/pipeline/artifact_io.py`
- `src/analysis/pipeline/pipeline_controller.py`
- `docs/analysis/design/gui_overview.md`
- `docs/analysis/design/system_design.md`
- 이 문서
