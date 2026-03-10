Last Reviewed: 2026-03-10

# Processing Mode Implementation Plan

이 문서는 Step 1의 processing mode 확장 작업을 다음 세션에서도 이어서 진행할 수 있도록 임시 계획을 정리한 문서다.

## 작업 목표
- Step 1에 `Standard / Raw / Advanced` processing mode를 추가한다.
- `Advanced Settings...` 다이얼로그를 통해 세부 처리 단계를 제어할 수 있게 한다.
- 이후 velocity/acceleration 미분 방식을 분리하고, 마지막으로 실제 수치 파라미터까지 GUI와 연결한다.

## 현재 합의된 방향
- Step 1 메인 화면에 `Processing Mode` 그룹을 추가한다.
- 선택 방식은 `QRadioButton` 3개를 사용한다.
  - `Standard`
  - `Raw`
  - `Advanced`
- `Advanced`를 선택하면 `Advanced Settings...` 버튼이 활성화된다.
- 모드 설명은 `Summary:` 같은 라벨 없이, 아래 한 줄 설명만 표시한다.
  - `Standard uses smoothing and filtering for more stable results.`
  - `Raw minimizes processing and may produce noisier velocity and acceleration.`
  - `Advanced lets you customize each processing stage.`
- 실제 GUI 구현에서는 설명 문자열을 위젯 생성 코드에 직접 하드코딩하지 않고, 한 곳에 모은 문자열 상수 또는 설정용 변수로 관리한다.

## 확정된 작업 순서
1. mockup 확정
2. `Standard / Raw / Advanced` 1차 GUI + 동작 구현
3. velocity / acceleration 미분 방식 분리
4. 실제 수치 파라미터 편집 GUI와 동작 연결

## 1단계: mockup 확정

### 현재 mockup 파일
- `docs/analysis/design/gui_mockups/step1_processing_mode_mock_v32.png`
- `docs/analysis/design/gui_mockups/step1_advanced_settings_mock_v32.png`

### mockup 생성 스크립트
- `docs/analysis/design/gui_mockups/generate_step1_step2_recommend_mockup_v31.py`

### 확인 포인트
- `Processing Mode` 그룹 위치가 Step 1 레이아웃에 자연스러운지
- `Advanced Settings...` 버튼 활성화 흐름이 직관적인지
- Advanced dialog 섹션 순서와 설명 문구가 사용자 관점에서 이해 가능한지

## 2단계: 1차 GUI + 동작 구현

### 목적
- 사용자가 `Standard`, `Raw`, `Advanced` 중 하나를 고를 수 있게 한다.
- `Advanced`일 때만 세부 설정 다이얼로그를 열 수 있게 한다.
- 이 단계에서는 숫자 파라미터 편집까지는 하지 않는다.

### Step 1 메인 화면
- `Processing Mode` 그룹 추가
- `QRadioButton`
  - `Standard`
  - `Raw`
  - `Advanced`
- `QPushButton("Advanced Settings...")`
- 현재 선택 모드 설명 라벨 1개

### Advanced dialog 섹션 순서
1. `Marker Smoothing`
2. `Range Edge Handling`
3. `Pose`
4. `Derivative Method`
5. `Velocity`
6. `Acceleration`

### Advanced dialog 버튼
- `Cancel`
- `OK`
- 현재 단계에서는 `Apply` 버튼을 두지 않는다.

### Advanced dialog에서 1차로 노출할 항목
- `Marker Smoothing`
  - enable on/off
  - method selection
- `Range Edge Handling`
  - `Stable (recommended)`
  - `Fast (less accurate near range edges)`
- `Pose`
  - pose low-pass filter on/off
  - pose moving average on/off
- `Derivative Method`
  - `Spline`
  - `Finite Difference`
- `Velocity`
  - velocity low-pass filter on/off
- `Acceleration`
  - acceleration low-pass filter on/off

### 동작 원칙
- `Standard`
  - 현재 기본 config 기반
  - smoothing/filtering 사용
- `Raw`
  - smoothing/filtering 최대한 비활성화
  - derivative method는 raw에 가까운 경로로 설정
- `Advanced`
  - 다이얼로그에서 저장한 사용자 설정 사용

### 주의사항
- 현재 코드에는 velocity/acceleration 미분 방식이 하나의 method로 묶여 있다.
- 따라서 2단계에서는 `Derivative Method`를 velocity/acceleration 공통 옵션으로 먼저 연결한다.

### 예상 수정 파일
- `src/analysis/ui/widget_raw_data_processing.py`
- `src/analysis/pipeline/pipeline_controller.py`
- `src/analysis/pipeline/velocity_calculator.py`
- 필요 시 `src/config/config_analysis.py`

## 3단계: velocity / acceleration method 분리

### 목적
- 현재 공통으로 묶인 미분 방식을 velocity와 acceleration에서 각각 선택 가능하게 분리한다.

### 구현 방향
- config 분리
  - `VELOCITY_CALCULATION_METHOD`
  - `ACCELERATION_CALCULATION_METHOD`
- `VelocityCalculator` 내부 상태 분리
  - `self.velocity_method`
  - `self.acceleration_method`
- GUI도 이를 반영하도록 확장

### 이 단계에서 바뀔 수 있는 UI
- `Derivative Method` 섹션을 다음 중 하나로 확장
  - velocity / acceleration 개별 method
  - 또는 공통 method + 개별 override

### 예상 수정 파일
- `src/config/config_analysis.py`
- `src/analysis/pipeline/velocity_calculator.py`
- `src/analysis/ui/widget_raw_data_processing.py`

## 4단계: 실제 수치 파라미터 편집 연결

### 목적
- 단순 on/off와 method 선택뿐 아니라, 실제 filter/spline 파라미터도 GUI에서 편집할 수 있게 한다.

### 후보 파라미터
- marker smoothing
  - Butterworth cutoff
  - Butterworth order
  - moving average window
- pose
  - pose LPF cutoff/order
  - pose moving average window
- derivative
  - spline factor
  - spline degree
- velocity
  - velocity LPF cutoff/order
- acceleration
  - acceleration LPF cutoff/order

### 구현 원칙
- GUI에서 입력한 값이 실제 분석 실행 config로 전달되어야 한다.
- UI 상태, 실행 config, calculator 내부 설정이 서로 일관되게 연결되어야 한다.

### 예상 수정 파일
- `src/analysis/ui/widget_raw_data_processing.py`
- `src/analysis/ui/` 아래 새 dialog 파일이 필요하면 추가
- `src/analysis/pipeline/pipeline_controller.py`
- `src/analysis/pipeline/velocity_calculator.py`
- `src/analysis/pipeline/smoother.py`
- `src/config/config_analysis.py`

## Range Edge Handling 관련 메모
- 기존 내부 개념인 `early / late trimming`은 사용자에게 그대로 노출하지 않는다.
- 사용자 언어로는 `Range Edge Handling`으로 표현한다.
- 선택지는 다음과 같이 유지한다.
  - `Stable (recommended)`
  - `Fast (less accurate near range edges)`
- 의미:
  - `Stable`: 선택 구간 경계 근처의 계산 안정성을 높이기 위해 숨겨진 여유 구간을 더 오래 유지
  - `Fast`: 더 일찍 잘라 계산량은 줄이지만 경계 근처 정확도는 떨어질 수 있음

## Raw mode 관련 메모
- raw mode는 단순히 marker smoothing만 끄는 것이 아니다.
- 최소한 다음 항목도 함께 검토해야 한다.
  - marker smoothing
  - pose low-pass filter
  - pose moving average
  - velocity low-pass filter
  - acceleration low-pass filter
  - derivative method

## 구현 전에 다시 확인할 질문
- `Raw`에서 derivative method를 무조건 `Finite Difference`로 강제할지
- `Advanced`에서 `Range Edge Handling`을 1차부터 노출할지
- 2단계에서는 숫자 파라미터를 완전히 숨길지, read-only 표시만 둘지

## 현재 결론
- 먼저 2단계까지 구현하고 사용 가능한 흐름을 만든다.
- method 분리와 수치 파라미터 편집은 그 다음 단계로 분리한다.
- 이번 확장 작업은 작은 단계로 나누어 진행한다.


## Layout tuning constants policy (Step 1)
- Step 1 bottom control row layout tuning values (minimum widths, fixed description height, stretch ratios) are managed in `src/config/config_analysis_ui.py`.
- `src/analysis/ui/widget_raw_data_processing.py` should consume those constants instead of hard-coded numeric literals.
- 목적: 해상도/폰트 조건이 달라질 때 코드 로직 수정 없이 설정값만 조정할 수 있도록 유지보수성을 높인다.
