Last Reviewed: 2026-03-16

# 3D Visualization Inspector Redesign Plan

이 문서는 `src/visualization/`의 Inspector 관련 UI와 용어 체계를 Data Processing / export 스키마 기준으로 다시 정리하기 위한 작업 계획을 정리한다.

## 문서 사용 원칙
- 이번 visualization Inspector 개편 작업은 이 문서를 단일 계획 문서로 사용한다.
- 다음 세션에서 이 작업을 다시 시작할 때는 먼저 이 문서를 본다.
- `docs/visualization/guide.md`는 현재 구현 설명용 문서이고, 이 문서는 앞으로 진행할 변경 계획용 문서다.
- 같은 작업에 대한 추가 TODO나 설계 메모를 다른 문서에 중복해서 흩어 쓰지 않는다.

## 배경
- 현재 visualization UI는 `Object Inspector`, `Information Log` 같은 용어를 사용하지만, 실제 데이터 의미와 완전히 맞지 않는다.
- Data Processing / export 기준으로는 `CoM`, `C1~C8`, marker가 서로 다른 성격의 객체인데, 현재 Inspector에서는 같은 리스트에 섞여 보인다.
- metric 표기도 `Position X`, `Velocity X`처럼 단순해서 `Global Frame`인지 `Box Local Frame`인지 알기 어렵다.
- 내부 컬럼명도 `RigidBody_Position_*`, `vel_x` 같은 legacy / placeholder 이름이 남아 있어, 현재 결과 CSV 스키마의 `CoM`, `Global_*`, `BoxLocal_*` 의미와 어긋난다.

## 핵심 문제

### 1. 중심 객체 용어 불일치
- Data Processing / export 기준 중심 객체는 `Center of Mass (CoM)`이다.
- 현재 visualization 내부에서는 중심 position을 `RigidBody_Position_*`처럼 다루고 있어 의미 혼선을 만든다.

### 2. 객체 유형 혼합
- `CoM`, `Corners`, `Markers`는 지원하는 metric이 다르다.
- 현재 Inspector는 object id를 한 리스트에 넣어 모두 같은 방식으로 선택하게 한다.
- 그 결과 marker를 선택해도 velocity / acceleration 같은 unsupported metric과 같은 UI를 공유하게 된다.

### 3. 좌표계 표기 부족
- velocity / acceleration은 `Global Frame`과 `Box Local Frame` 구분이 중요하다.
- 현재 visualization UI에는 이 구분이 거의 드러나지 않는다.

## 목표
- visualization UI 용어를 Data Processing / export 스키마와 일치시킨다.
- 중심 객체는 `RigidBody`가 아니라 `Center of Mass (CoM)` 기준으로 통일한다.
- Inspector에서 객체 유형을 `CoM / Corners / Markers` 대분류로 나눈다.
- metric 라벨에 좌표계를 명시한다.
- visualization 내부 long-format 컬럼명도 현재 의미에 맞게 정리한다.

## 용어 통일안

### 패널명
- `Object Inspector` -> `Scene Inspector`
- `Information Log` -> `Frame Inspector`

### 객체 용어
- 중심 객체: `Center of Mass (CoM)`
- 코너: `C1` ~ `C8`
- 마커: marker id 그대로 유지

### 좌표계 용어
- `Global` -> `Global Frame`
- `BoxLocal` -> `Box Local Frame`

## Inspector 재설계안

### 기본 구조
- 현재 단일 `QListWidget` 기반 object list를 그룹형 Inspector로 바꾼다.
- 구현 후보는 `QTreeWidget`을 기본안으로 본다.

### 그룹 구조
- `Center of Mass`
  - `CoM`
- `Corners`
  - `C1`
  - `C2`
  - `C3`
  - `C4`
  - `C5`
  - `C6`
  - `C7`
  - `C8`
- `Markers`
  - marker id 목록

### 설계 의도
- `CoM`, `Corners`, `Markers`가 서로 다른 데이터 타입이라는 점을 UI에서 즉시 드러낸다.
- marker는 marker끼리, corner는 corner끼리 묶어 의미를 분리한다.
- 이후 object type별 metric 제한 로직을 붙이기 쉽게 만든다.

## Metric 노출 규칙

### CoM
- `Position X (Global Frame)`
- `Position Y (Global Frame)`
- `Position Z (Global Frame)`
- `Velocity X (Global Frame)`
- `Velocity Y (Global Frame)`
- `Velocity Z (Global Frame)`
- `Speed (Global Frame)`
- `Velocity X (Box Local Frame)`
- `Velocity Y (Box Local Frame)`
- `Velocity Z (Box Local Frame)`
- 2차 확장 후보
  - `Acceleration X/Y/Z (Global Frame)`
  - `Acceleration X/Y/Z (Box Local Frame)`

### Corners
- `Position X (Global Frame)`
- `Position Y (Global Frame)`
- `Position Z (Global Frame)`
- `Velocity X (Global Frame)`
- `Velocity Y (Global Frame)`
- `Velocity Z (Global Frame)`
- `Speed (Global Frame)`
- 2차 확장 후보
  - `Acceleration X/Y/Z (Global Frame)`

### Markers
- `Position X (Global Frame)`
- `Position Y (Global Frame)`
- `Position Z (Global Frame)`

### 규칙
- marker가 선택된 상태에서는 velocity / acceleration metric을 콤보박스에서 노출하지 않는다.
- 여러 객체를 동시에 선택할 때는 공통으로 지원되는 metric만 노출하거나, 지원되지 않는 객체는 plot / inspector에서 제외한다.
- 1차 구현에서는 서로 다른 object type을 동시에 선택하는 경우를 제한하는 방안도 허용한다.

## Frame Inspector 재설계안

### 공통 항목
- `Frame`
- `Time (s)`

### CoM
- `Position X (Global Frame)`
- `Position Y (Global Frame)`
- `Position Z (Global Frame)`
- `Velocity X (Global Frame)`
- `Velocity Y (Global Frame)`
- `Velocity Z (Global Frame)`
- `Speed (Global Frame)`
- `Velocity X (Box Local Frame)`
- `Velocity Y (Box Local Frame)`
- `Velocity Z (Box Local Frame)`

### Corners
- `Position X (Global Frame)`
- `Position Y (Global Frame)`
- `Position Z (Global Frame)`
- `Velocity X (Global Frame)`
- `Velocity Y (Global Frame)`
- `Velocity Z (Global Frame)`
- `Speed (Global Frame)`

### Markers
- `Position X (Global Frame)`
- `Position Y (Global Frame)`
- `Position Z (Global Frame)`

### 표시 원칙
- 지원되지 않는 값을 무조건 같은 표에 `N/A`로 채우기보다, object type에 따라 보여줄 행 자체를 바꾸는 쪽을 우선한다.
- 단, 여러 유형을 동시에 보여줘야 하는 경우에는 `N/A`를 허용한다.

## 내부 데이터 모델 정리안

### canonical long-format 컬럼
- `frame`
- `time`
- `entity_id`
- `entity_type`
- `position_global_x`
- `position_global_y`
- `position_global_z`
- `velocity_global_x`
- `velocity_global_y`
- `velocity_global_z`
- `velocity_box_local_x`
- `velocity_box_local_y`
- `velocity_box_local_z`

### 2차 확장 후보
- `acceleration_global_x`
- `acceleration_global_y`
- `acceleration_global_z`
- `acceleration_box_local_x`
- `acceleration_box_local_y`
- `acceleration_box_local_z`

### entity_type 분류 규칙
- `com`
  - `CoM`
- `corner`
  - `C1` ~ `C8`
- `marker`
  - 나머지 marker ids

## 구현 범위 제안

### 1차
- `DataHandler`
  - `entity_type` 분류 추가
  - canonical internal column naming 정리
- `ControlPanel`
  - grouped Inspector 도입
  - object type별 metric 목록 동적 변경
- `MainWindow`
  - plot / frame inspector 로직을 object type 기준으로 분리
- `InfoLogWidget`
  - `Frame Inspector` 기준 라벨 반영
- `config_visualization.py`
  - legacy / placeholder 컬럼명 정리
  - UI label / metric mapping 정리

### 2차
- acceleration metric 노출 확대
- mixed selection 정책 정교화
- `Frame Inspector`에서 좌표계 설명을 더 명시적으로 제공

## 비범위
- marker velocity / acceleration 자체를 새로 계산하는 작업
- analysis export 스키마 변경
- 3D scene rendering 방식 대개편

## 완료 기준
- `CoM`, `Corners`, `Markers`가 Inspector에서 명확히 분리된다.
- 중심 객체 관련 값은 `RigidBody`가 아니라 `CoM` 기준으로 표현된다.
- marker 선택 시 unsupported metric이 보이지 않는다.
- metric 이름만 보고도 `Global Frame` / `Box Local Frame`을 구분할 수 있다.
- visualization 내부 naming과 UI vocabulary가 Data Processing / export 의미와 일치한다.
