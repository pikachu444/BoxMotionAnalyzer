# Export Analysis Scenario 형식 설명서

Last Reviewed: 2026-03-08

이 문서는 현재 `WidgetResultsAnalyzer.export_analysis_scenario()`가 생성하는 파일 형식을 설명한다.

## 1. 출력 형식
- 결과는 텍스트 기반 CSV 파일이다.
- 총 7줄 구조를 사용한다.
  - 1~6줄: `키,값`
  - 7줄: 나머지 `키,값` 쌍을 한 줄에 이어 붙인 형식

예시:
```text
1,Left
2,Right
3,Bottom
4,Top
5,Rear
6,Front
cat,Corner_Drop_2nd,drop_name,Scene01,...,run_time,0.1,tmin,1e-7
```

## 2. UI 입력과 필드 매핑
- `Scene Name` -> `drop_name`
- `Run Time` -> `run_time`
- `Step` -> `tmin`
- `Manual Offset`, `Manual Height` 체크 상태는 `variable_1..3`, `value_1..3` 계산 방식에 영향을 준다

## 3. 고정 필드
- `1~6`: `Left`, `Right`, `Bottom`, `Top`, `Rear`, `Front`
- `cat`: 항상 `Corner_Drop_2nd`
- `variable_4`, `value_4`: 항상 `OFFSET`, `0.0`

## 4. offset 코너 결정 규칙

### 4.1. 자동 offset
- `Manual Offset`이 꺼져 있으면 자동 규칙을 사용한다.
- 현재 선택된 시점 row에서 `Analysis / C1~C8 / RelativeHeight`를 비교한다.
- 가장 낮은 코너를 찾고, 그 코너가 속한 4개 그룹 안에서 높이가 가장 낮은 3개를 선택한다.
- 선택된 코너 이름은 `CORNER_NAME_MAP`으로 사람이 읽는 이름으로 변환되어 `variable_1..3`에 저장된다.
- 해당 높이값은 `value_1..3`에 저장된다.

### 4.2. 수동 offset
- `Manual Offset`이 켜져 있으면 사용자가 고른 `Offset0~2`를 그대로 사용한다.
- `Manual Height`가 꺼져 있으면 현재 선택 시점의 `RelativeHeight` 값을 사용한다.
- `Manual Height`가 켜져 있으면 텍스트 입력값을 그대로 `value_1..3`에 사용한다.

## 5. 속도 필드
- `variable_5..7`
  - `ANG_VEL_X`
  - `ANG_VEL_Y`
  - `ANG_VEL_Z`
- `variable_8..10`
  - `TRA_VEL_X`
  - `TRA_VEL_Y`
  - `TRA_VEL_Z`

속도 값은 현재 선택된 시점 row의 CoM velocity 컬럼에서 읽는다.

주의:
- `Manual Offset`과 `Manual Height`가 모두 켜진 경우, 구현상 높이값은 수동 입력을 사용하고 속도값은 `0.0`으로 채운다.

## 6. 기타 고정 값
- `variable_11..13`
  - `POSI_FROM_CENT_X`
  - `POSI_FROM_CENT_Y`
  - `POSI_FROM_CENT_Z`
- `variable_14..16`
  - `ROT_ANG_VEL_X`
  - `ROT_ANG_VEL_Y`
  - `ROT_ANG_VEL_Z`

현재 구현에서는 위 값들을 모두 `0.0`으로 출력한다.
