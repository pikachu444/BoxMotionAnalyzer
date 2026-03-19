# GUI Validation Plan

Last Reviewed: 2026-03-19

## 목적
이 문서는 `Codex CLI Agent`가 직접 GUI를 검증하지 못하는 현재 환경을 전제로,
GUI 실행이 가능한 다른 AGENT에게 `BoxMotionAnalyzer-slice-mockup`의 GUI 검증 작업을 넘기기 위한 실행 계획서다.

현재 `Codex CLI Agent`가 작업 중인 환경에서는 `PySide6` 기반 GUI를 직접 띄워 검증할 수 없다.
따라서 이 문서는 "Codex CLI Agent가 대신 수행하는 문서 검토/코드 검토"가 아니라,
GUI 검증이 가능한 AGENT가 실제 화면을 열어 workflow와 파일 포맷 전환(`.slice`, `.proc`)을 검증하도록 요청하는 문서다.

이 문서의 범위는 아래를 포함한다.
- Launcher
- Analysis GUI Step 1 / Step 1.5 / Step 2
- 3D Visualization GUI
- 파일 확장자/filter 노출 방식
- `.slice`, `.proc`의 실제 로드/저장 흐름
- legacy 결과 `.csv`와 UI 노출 정책의 관계

## 검증 원칙
- 가능하면 Windows GUI 환경에서 실행한다.
- 검증 AGENT는 기본적으로 코드 수정 없이 재현, 관찰, 기록에 집중한다.
- `Codex CLI Agent`는 이 문서를 작성하고 범위를 정리하는 역할만 맡고, 실제 GUI 판정은 GUI 실행이 가능한 AGENT가 수행한다.
- 문제를 발견하면 즉시 고치지 말고 재현 절차와 증거를 먼저 남긴다.
- 각 항목은 `Pass / Fail / Blocked` 중 하나로 판정한다.

## 사전 준비
- 작업 경로: `/root/BoxMotionAnalyzer-slice-mockup`
- 권장 실행 명령:

```bash
python src/main.py
```

- 빠른 smoke input:
  - `TestSets/Input/small_test.csv`
- 현실 데이터 확인용 input:
  - `TestSets/Input/VDTest_S5_001.csv`
- UI 목록 비노출 확인용 legacy 결과 파일:
  - `data/test_real_data_result.csv`

## 산출물 준비
검증 중 생성되는 파일은 새 폴더에 모은다.

권장 폴더 예:
- `data/gui_validation_runs/2026-03-19/`

권장 산출물:
- Step 1에서 만든 `.slice` 2개 이상
- Step 1.5 single run으로 만든 `.proc` 1개
- Step 1.5 batch run으로 만든 `.proc` 여러 개
- 실패/이상 동작의 스크린샷
- 검증 결과 메모

## 검증 시나리오

### 1. Launcher Smoke
- 앱을 실행한다.
- Launcher가 정상 표시되는지 확인한다.
- Analysis GUI 진입 버튼이 열리는지 확인한다.
- Visualization GUI 진입 버튼이 열리는지 확인한다.
- 각 창을 열고 닫았을 때 앱이 비정상 종료되지 않는지 확인한다.

기대 결과:
- 런처 진입이 정상이다.
- 각 버튼이 의도한 창을 연다.
- 창 전환/종료 중 크래시가 없다.

### 2. Step 1: Raw Data Slice
- `small_test.csv`를 연다.
- 플롯이 표시되는지 확인한다.
- `Select Data...`, 축 선택, Slice Range 입력이 동작하는지 확인한다.
- scene 이름을 바꿔 `.slice` 파일을 2개 이상 저장한다.
  - 예: `batch_a`, `batch_b`
- 저장 후 마지막 경로와 로그가 갱신되는지 확인한다.

기대 결과:
- raw `.csv`만 열기 대상에 노출된다.
- preview plot이 깨지지 않는다.
- `.slice` 저장이 성공하고 저장 경로가 보인다.

### 3. Step 1.5: Single Slice Processing
- 방금 만든 `.slice` 중 하나를 연다.
- `Slice Summary`와 box dimensions가 metadata 기준으로 채워지는지 확인한다.
- `Raw / Smoothing / Advanced` 전환이 정상인지 확인한다.
- 필요하면 resampling을 켜고 factor를 바꿔본다.
- `Run Processing`을 실행한다.
- 완료 후 `Save Processed Result`로 `.proc`를 저장한다.

기대 결과:
- `.slice`만 열기 대상에 노출된다.
- processing 완료 후 `.proc` 저장이 가능하다.
- 저장 경로와 상태 라벨이 정상 갱신된다.

### 4. Step 1.5: Batch Processing
- Step 1에서 `.slice`를 저장한 폴더를 선택한다.
- `Overwrite existing .proc`를 끈 상태로 `Run Batch Processing`을 실행한다.
- 요약 문자열(`total / processed / skipped / failed`)을 기록한다.
- 같은 폴더에서 다시 한 번 실행해 skip이 발생하는지 확인한다.
- `Overwrite existing .proc`를 켠 뒤 다시 실행해 overwrite가 동작하는지 확인한다.

기대 결과:
- batch folder 선택이 가능하다.
- `.slice` 파일만 스캔한다.
- overwrite off일 때 기존 `.proc`는 skip 된다.
- overwrite on일 때 다시 처리된다.
- summary와 로그가 정책과 일치한다.

### 5. Step 2: Results Analysis
- batch 또는 single run으로 만든 `.proc`가 있는 폴더를 선택한다.
- 결과 목록에 `.proc`가 보이는지 확인한다.
- legacy 결과 `.csv`는 그대로는 목록에 보이지 않는지 확인한다.
- 컬럼 트리 체크, 메인 플롯, 팝업 플롯, point export, scenario export를 확인한다.

기대 결과:
- Step 2는 `.proc`만 직접 다룬다.
- UI 목록에는 raw/legacy `.csv`가 섞여 보이지 않는다.
- 파일 전환 시 타임라인 바와 컨텍스트 라벨이 갱신된다.
- plot / popup / export 흐름이 깨지지 않는다.

### 6. 3D Visualization
- visualization 창에서 batch 또는 single run으로 만든 `.proc`를 연다.
- 재생/정지, 프레임 슬라이더, 시점 변경, Scene Inspector, Plot, Frame Inspector를 확인한다.
- legacy 결과 `.csv`는 그대로는 열리지 않는지 확인한다.

기대 결과:
- visualization은 raw `.csv`가 아니라 결과 파일을 연다.
- visualization은 `.proc`만 직접 연다.
- UI에서는 raw/legacy `.csv`를 직접 선택하지 않게 한다.
- entity 선택, frame 이동, plot 확대, frame range filtering이 정상이다.

### 7. File Extension / Dialog Filter
- Step 1 file open dialog가 raw `.csv` 기준인지 확인한다.
- Step 1 save dialog가 `.slice` 기준인지 확인한다.
- Step 1.5 file open dialog가 `.slice` 기준인지 확인한다.
- Step 1.5 save dialog가 `.proc` 기준인지 확인한다.
- Visualization open dialog가 `.proc` 결과 파일 기준인지 확인한다.
- Step 2 결과 목록과 Visualization open 대상이 같은 `.proc` 결과 파일 집합을 참조하는지 확인한다.

기대 결과:
- 각 단계는 자기 역할에 맞는 확장자만 노출한다.
- 결과 파일 기준은 Step 2와 Visualization에서 모두 `.proc`로 일치한다.

## 증빙 방식
각 시나리오마다 아래를 남긴다.
- 실행 날짜/환경
- 사용한 입력 파일 경로
- 생성된 출력 파일 경로
- Pass / Fail / Blocked 판정
- 실패 시 스크린샷 경로
- 실패 시 재현 절차

## 보고 형식
검증 AGENT는 결과를 아래 형식으로 정리한다.

```text
GUI Validation Report

Environment
- OS
- Python version
- Launch command

Results
- Launcher: Pass/Fail/Blocked
- Step 1: Pass/Fail/Blocked
- Step 1.5 Single: Pass/Fail/Blocked
- Step 1.5 Batch: Pass/Fail/Blocked
- Step 2: Pass/Fail/Blocked
- Visualization (.proc): Pass/Fail/Blocked
- Legacy .csv UI filtering: Pass/Fail/Blocked
- File Extension / Filter: Pass/Fail/Blocked

Findings
- ID
- Severity
- Repro steps
- Expected
- Actual
- Evidence
```

## 다른 AGENT에게 바로 전달할 프롬프트
아래 프롬프트를 그대로 넘겨도 된다.

```text
Work in /root/BoxMotionAnalyzer-slice-mockup.
Read docs/analysis/design/gui_validation_plan.md first and execute the GUI validation exactly as written.
Assume Codex CLI Agent already reviewed the code and prepared this handoff because the current CLI environment cannot run PySide6 GUI validation.
Do not change code during the validation pass unless explicitly asked.
Focus on reproducing behavior, capturing evidence, and reporting findings with exact file paths and concrete steps.
If the environment blocks GUI execution, report the blocker clearly and stop at that point.
```
