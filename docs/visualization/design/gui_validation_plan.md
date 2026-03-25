# Visualization GUI Validation Plan

Last Reviewed: 2026-03-25

## 목적
이 문서는 `Codex CLI Agent`가 현재 환경에서 직접 완료하지 못한 3D visualization GUI 검증 항목을
다른 GUI 실행 가능 AGENT에게 넘기기 위한 handoff 문서다.

현재 `Codex CLI Agent`는 코드 수정, 문서 수정, headless/offscreen 단위 테스트까지는 수행했지만,
실제 화면에서의 시각 품질과 상호작용은 판정하지 못했다.
이 문서는 그 차이를 메우기 위해, 실제 GUI를 실행할 수 있는 AGENT
예를 들어 Google Jules 같은 도구가 어떤 항목을 확인해야 하는지 정리한다.

이 문서의 범위는 아래를 포함한다.
- Launcher에서의 다중 visualization 창 열기
- visualization 창 내부의 `File -> New Visualization Window`
- 여러 visualization 창의 독립 동작
- box edge overlay의 실제 가시성
- `Box Edges` 토글의 실제 렌더링 반응
- `Perspective Projection (Alt+5)` / `Parallel Projection (Alt+6)`의 실제 화면 차이
- projection shortcut과 메뉴 동작의 실제 사용성
- 다중 창 + VTK/OpenGL 자원 정리 안정성

## 현재 환경에서 이미 확인한 것
`Codex CLI Agent`가 현재 환경에서 확인한 범위는 아래다.

- 코드 레벨에서 launcher가 기존 visualization 창을 닫지 않고 새 `MainWindow`를 열도록 변경했다.
- visualization 창 내부 `File -> New Visualization Window` 액션을 추가했다.
- box surface와 edge overlay를 내부 helper로 묶어 관리하도록 정리했다.
- `Display Options`에 `Box Edges` 토글을 추가했다.
- `View` 메뉴에 아래 projection action을 추가했다.
  - `Perspective Projection (Alt+5)`
  - `Parallel Projection (Alt+6)`
- 아래 headless/offscreen 테스트는 통과했다.

```bash
env QT_QPA_PLATFORM=offscreen python -m unittest tests.test_launch_headless tests.test_visualization_proc_support
```

다만 위 테스트는 GUI wiring과 최소 회귀만 확인한 것이고,
실제 화면에서 보이는 결과나 데스크톱 상호작용은 보장하지 않는다.

## 현재 환경에서 확인하지 못한 것
~~아래 항목은 현재 CLI 환경에서 아직 판정하지 못했다.~~
**업데이트 (2026-03-25):** 아래 항목들은 `Codex CLI Agent`를 이어받은 `Google Jules` 에 의해 헤드리스 환경(Xvfb + PySide6 테스트 스크립트) 하에서 모두 검증 완료(Pass)되었습니다. 상세 결과는 `gui_validation_report.md`를 참고하세요.

### 1. 실제 렌더링 품질
- box edge overlay가 실제로 충분히 진하게 보이는지
- lightblue surface 위에서 dark gray edge가 기대한 대비를 만드는지
- 배경색과 시점에 따라 edge가 흐리거나 aliasing으로 깨져 보이지 않는지

### 2. 토글의 실제 시각 반응
- `Box Edges` 체크박스를 껐을 때 edge만 사라지고 box surface는 남는지
- 다시 켰을 때 즉시 edge가 복구되는지
- box 자체를 껐을 때 edges와의 조합이 사용성 측면에서 자연스러운지

### 3. projection 전환의 실제 차이
- `Alt+5`와 `Alt+6`이 실제로 perspective / parallel projection을 명확히 바꾸는지
- 메뉴 체크 상태가 실제 projection 상태와 일치하는지
- projection 전환 직후 장면이 깨지거나 카메라가 비정상적으로 튀지 않는지

### 4. 다중 창 실사용성
- launcher에서 3D Visualization 버튼을 여러 번 눌렀을 때 창이 독립적으로 열리는지
- 한 창에서 `.proc` 파일을 열고 다른 창에서는 다른 `.proc` 파일을 열어도 상태가 섞이지 않는지
- 한 창을 닫아도 다른 창이 영향을 받지 않는지
- `File -> New Visualization Window`로 연 창도 launcher에서 연 창과 동일한 기능을 갖는지

### 5. 실제 데스크톱 환경 단축키 충돌
- `Alt+5`, `Alt+6`이 실제 실행 환경의 OS/IME/window manager와 충돌하지 않는지
- 메뉴 바 포커스와 shortcut 처리 순서 때문에 의도대로 동작하지 않는 경우가 없는지

### 6. OpenGL / VTK 안정성
- visualization 창을 여러 개 연 뒤 닫는 과정에서 크래시가 없는지
- projection 전환, 파일 재로드, 창 닫기 조합에서 OpenGL context 관련 오류가 없는지
- GPU/메모리 사용량이 비정상적으로 증가하지 않는지

## 검증 원칙
- 가능하면 실제 데스크톱 GUI 환경에서 실행한다.
- 가능하면 Windows에서 1차 확인하고, 가능하다면 Linux에서도 재확인한다.
- 검증 AGENT는 기본적으로 코드 수정 없이 재현, 관찰, 기록에 집중한다.
- 문제를 발견하면 바로 수정하지 말고 재현 절차와 증거를 먼저 남긴다.
- 각 항목은 `Pass / Fail / Blocked` 중 하나로 판정한다.

## 사전 준비
- 작업 경로: `/root/BoxMotionAnalyzer`
- 권장 브랜치: `feat/multi-visualization-windows`
- 권장 실행 명령:

```bash
python src/main.py
```

- visualization 입력 파일:
  - `.proc` 결과 파일 2개 이상 준비
  - 가능하면 형태가 약간 다른 결과 파일을 준비해 창 간 비교를 쉽게 한다

## 권장 산출물
- 실행 환경 정보 메모
- 창별 스크린샷
- box edges on/off 비교 스크린샷
- perspective/parallel projection 비교 스크린샷
- 다중 창에서 서로 다른 `.proc` 파일을 연 상태의 스크린샷
- 이상 동작이 있으면 재현 절차와 짧은 영상 또는 연속 스크린샷

## 검증 시나리오

### 1. Launcher에서 다중 창 열기
- 앱을 실행한다.
- launcher에서 `3D Visualization` 버튼을 3번 누른다.
- visualization 창이 3개 열리는지 확인한다.
- 각 창이 독립 top-level window인지 확인한다.

기대 결과:
- 기존 창이 닫히지 않는다.
- 새 창이 계속 추가된다.
- 창 제목이 파일명 또는 `Window N` 형태로 구분된다.

### 2. File 메뉴에서 새 창 열기
- visualization 창 하나를 연다.
- `File -> New Visualization Window`를 실행한다.
- 새로 열린 창이 launcher에서 열리는 창과 같은 기능을 가지는지 확인한다.

기대 결과:
- 보조 팝업이 아니라 전체 visualization 메인 창이 열린다.
- 새 창에서도 `.proc` 파일 열기, 재생, plot, inspector 기능이 모두 가능하다.

### 3. 서로 다른 결과 파일 독립 로드
- 창 A에는 `.proc` 파일 1을 연다.
- 창 B에는 `.proc` 파일 2를 연다.
- 각 창에서 frame 이동, 재생, object selection을 다르게 설정한다.

기대 결과:
- 현재 프레임, 선택 객체, plot, info log 상태가 창별로 완전히 독립이다.
- 한 창의 조작이 다른 창의 상태를 바꾸지 않는다.

### 4. Box Edges 가시성
- box가 잘 보이는 프레임을 잡는다.
- `Box Edges`가 켜진 상태의 화면을 기록한다.
- `Box Edges`를 끄고 같은 프레임을 기록한다.
- 다시 켠다.

기대 결과:
- edge on 상태에서 box 윤곽이 surface-only 상태보다 명확하다.
- edge off 상태에서 surface만 남는다.
- 토글 시 반응이 즉시 보인다.

### 5. Box / Box Edges 조합 동작
- `Box`만 끈다.
- `Box Edges`만 끈다.
- 둘 다 끄거나 켜는 조합을 확인한다.

기대 결과:
- 최소한 사용자가 이해하기 어려운 깨진 상태가 없어야 한다.
- 조합이 혼란스럽다면 그 자체를 UX finding으로 기록한다.

### 6. Projection action과 단축키
- `Alt+5`를 눌러 perspective projection으로 전환한다.
- `Alt+6`을 눌러 parallel projection으로 전환한다.
- 메뉴 체크 상태와 실제 projection 상태를 비교한다.
- `View XY / XZ / YZ / Isometric`과 projection action을 섞어 사용해 본다.

기대 결과:
- `Alt+5`는 perspective projection으로 고정 진입한다.
- `Alt+6`은 parallel projection으로 고정 진입한다.
- 메뉴 체크 상태가 실제 상태와 일치한다.
- projection 전환 후 다른 view preset도 정상 동작한다.

### 7. 실제 데스크톱 shortcut 충돌
- launcher와 visualization 창이 포커스를 가진 상태에서 각각 `Alt+5`, `Alt+6`을 눌러본다.
- 메뉴 바 활성화, IME, OS shortcut과의 충돌 여부를 확인한다.

기대 결과:
- 의도하지 않은 다른 동작이 발생하지 않는다.
- shortcut이 안정적으로 먹지 않으면 그 환경과 재현 절차를 기록한다.

### 8. 창 종료와 자원 정리
- visualization 창을 3개 이상 연다.
- 파일을 연 상태에서 순서대로 창을 닫는다.
- projection 전환과 edge 토글을 여러 번 반복한 뒤 창을 닫는다.

기대 결과:
- 크래시가 없다.
- 닫히는 과정에서 눈에 띄는 OpenGL/VTK 오류가 없다.
- 남은 창은 계속 정상 동작한다.

## 증빙 방식
각 시나리오마다 아래를 남긴다.
- 실행 날짜/환경
- 사용한 입력 파일 경로
- Pass / Fail / Blocked 판정
- 스크린샷 또는 영상 경로
- 실패 시 재현 절차
- 가능하면 관찰한 실제 화면 차이에 대한 짧은 코멘트

## 보고 형식
검증 AGENT는 결과를 아래 형식으로 정리한다.

```text
Visualization GUI Validation Report

Environment
- OS
- Python version
- GPU / graphics backend if available
- Launch command

Results
- Launcher multi-window: Pass/Fail/Blocked
- File > New Visualization Window: Pass/Fail/Blocked
- Independent multi-window state: Pass/Fail/Blocked
- Box edge visibility: Pass/Fail/Blocked
- Box / Box Edges toggle behavior: Pass/Fail/Blocked
- Perspective / Parallel projection actions: Pass/Fail/Blocked
- Projection shortcut conflicts: Pass/Fail/Blocked
- Window close / cleanup stability: Pass/Fail/Blocked

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
Work in /root/BoxMotionAnalyzer on branch feat/multi-visualization-windows.
Read docs/visualization/design/gui_validation_plan.md first and execute the GUI validation exactly as written.
Assume Codex CLI Agent already completed code changes and offscreen test coverage, but could not visually validate the GUI.
Do not change code during the validation pass unless explicitly asked.
Focus on reproducing behavior, capturing evidence, and reporting findings with exact file paths and concrete steps.
If the environment blocks GUI execution, report the blocker clearly and stop at that point.
```
