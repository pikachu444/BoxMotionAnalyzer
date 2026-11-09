# Shared core consumer contracts

Last Reviewed: 2026-11-09

Source: [issue #158](https://github.com/pikachu444/BoxMotionAnalyzer/issues/158).

## 5. 정확한 계산·호출 계약

계약 ID와 버전은 `TIME-KERNEL/1`, `ROW-1/1`, `FRAME-1/1`이다. 이름이 다른 숫자를 반환하더라도 각자의 규약을 지킨 결과일 수 있다. 공유 함수 일치와 소비자 동작 일치를 혼동하지 않는다.

### TIME-KERNEL/1 — 순수 시간 선택

```python
def nearest_sample_position(times_sec: Sequence[float], target_sec: float) -> int | None:
    ...
```

- 단위는 실제 기록된 초다. 입력은 float 변환 가능한 1차원 값 배열과 target이다. 함수는 `float(target_sec)`와 `np.asarray(times_sec, dtype=float)`를 사용한다. bool과 숫자 문자열을 일괄 거부하는 새 정책은 넣지 않는다.
- 순서: target/배열 변환 → target 유한성 → 배열 차원·유한성 → 엄격 증가 → 빈 배열/범위 → 위치 선택이다. `([], NaN)`은 `None`이 아니라 `ValueError`다.
- 빈 배열 또는 유한한 범위 밖 target은 `None`. 단일 샘플은 정확히 같은 시각만 위치 0을 반환한다.
- 정확 일치는 해당 위치, 두 이웃 거리가 정확히 같으면 더 이른 timestamp의 위치다. `int` 위치를 반환하며 원본 frame ID를 추정하지 않는다.
- 잘못된 차원, NaN/Inf, 중복·역순, 변환 불가 입력은 부록 A에서 정한 `ValueError`다. 예외 문구는 공통 API의 동등성 기준이 아니며 예외 종류는 기준이다.
- 정렬·중복 제거·수정·보간·clamp·t1·gap 검사를 하지 않는다. caller의 입력을 변경하지 않는다. 일반 실수 시간 배열을 지원 대상으로 하며 complex/custom object/iterator를 지원한다고 확장 해석하지 않는다.

### ROW-1/1 — 공개 앱의 실제 행 선택

주요 진입점은 `timeline_from_frame(df).nearest_row(relative, max_gap_sec)`다. 공개 `ComparisonModel.playback_row()`는 timeline의 lookup을 위임 호출한다. `load_file()`의 source-class 정렬 제한과 비교·집계의 metadata 적격성 검사는 별도 경로다.

1. 시간 컬럼은 `('Info','Time','Time')`이다. `('Time','Time','Time')`만 있는 legacy 시간은 개별 조회에 쓸 수 있지만 t1 정렬의 대체 근거는 아니다. 서로 충돌하는 시간 컬럼, 비유한·빈·중복·감소 시간축은 정렬 불가다. reader의 동일 시간 컬럼 처리와 파일 선언 검증을 유지한다.
2. construction 순서는 시간 검증 → canonical time 존재 → t1 관련 두 컬럼이 각각 유일하고 행 전체에서 상수인지 확인 → 검출 flag 해석 → t1 float·유한성·파일 범위 확인이다.
3. t1 컬럼은 `('Analysis','DropPostureSummary','T1Detected')`, `('Analysis','DropPostureSummary','T1MinusTimeSec')`이다. flag는 문자열화 후 strip/lower한 값이 `true`, `1`, `1.0`인 경우에만 참이다. false flag도 누락·가변 t1-time 검사를 먼저 통과해야 한다.
4. 이 profile의 t1 construction은 t1이 기록 범위 안인지 확인하며, 인접 gap 때문에 t1 자체를 최근접 샘플에 붙여 검증하는 절차는 추가하지 않는다.
5. lookup 순서는 정렬 유효성 → `relative`가 `times - t1` 범위 안인지 → `target = t1 + relative` → 정확 샘플 일치 → 인접 두 시각의 gap → 최근접 위치다. exact hit은 gap 거절을 우회한다.
6. 인접 구간의 gap 규칙은 다음 **기존 식**을 유지한다. 새 물리 허용오차가 아니다.

```python
difference = float(right) - float(left)
roundoff = min(
    1e-12,
    4 * (np.spacing(abs(float(left)))
         + np.spacing(abs(float(right)))
         + np.spacing(abs(float(limit))))
)
rejected = difference > limit and difference - limit > roundoff
```

7. 정상 설정에서 공개 UI의 기본 gap 값은 0.1초다. 같은 이름의 다른 소비자 설정으로 대체하지 않는다. 부록 C에서 정책을 비교할 때만 명시한 값을 양쪽에 전달한다.
8. 결과는 0-based row 또는 `None`이다. 직접 생성한 legacy `ResultTimeline`에 비정상 시간축을 넣는 경로는 file construction과 다르다. 후보 구현의 strict 축에서만 공통 함수를 부르고, 기존 legacy 직접 호출 fallback을 보존한다.
9. 비정상 query·gap override의 기존 반환·예외 순서도 adapter의 before/after 검사 대상이다. 이를 정리한다는 이유로 모든 예외를 `None`으로 바꾸지 않는다. 정상 profile은 유한한 실수 query와 양의 유한한 gap을 사용한다.

### FRAME-1/1 — 정규화 frame을 반환하는 소비자 규약

이 profile은 공개 앱에 새 모드를 추가하는 요구가 아니다. 다른 소비자가 같은 함수를 도입할 때 보존해야 하는 계약이다. 공개 측은 생성 fixture와 reference harness를 제공하며, 실제 소비자 adapter 검증은 그 담당자가 수행한다.

**시간·frame 테이블 준비 순서:**

1. canonical 실제 시간 컬럼을 요구한다. 그 tuple이 중복이면 이 소비자의 기존 처리는 첫 컬럼을 사용한다. ROW-1 reader의 중복 처리로 통일하지 않는다.
2. frame 컬럼이 없거나 수치 변환 후 전부 missing이면 원래 row 위치를 frame 값으로 쓴다.
3. 수치 frame이 하나라도 있으면 **missing time 행을 버리기 전에** 최소 수치 frame을 빼서 정규화한다. 일부만 bad frame인 경우 전체를 row 위치로 대체하지 않는다.
4. 수치 frame/time으로 테이블을 만들고 어느 한쪽이라도 missing인 행을 버린다. 이는 `dropna` 동작이며 Inf까지 제거하는 규칙은 아니다.
5. 정규화 frame을 integer로 변환한다. 소수부는 버려진다. 비유한 frame의 integer 변환 실패를 자동 복구한다고 선언하지 않는다.
6. 동일한 `(frame,time)` 쌍만 제거하고 frame 순으로 정렬한다. 모든 중복 time 또는 모든 중복 frame을 제거하지 않는다. 같은 frame끼리의 정렬 안정성을 새로 보장하지 않는다.

**정렬과 lookup:**

- summary의 첫 row에서 검출 flag와 t1을 읽는다. 파일 전체가 상수인지 새로 검사하지 않는다. flag 해석 → t1 유한 float → 위 테이블 준비 → t1의 최근접 매핑 유효성 순서다.
- flag의 기존 해석에는 `yes`/`y`와 수치 truthiness도 포함된다. 문자열 `nan`과 실제 numeric NaN의 기존 처리는 다르다. 부록 C의 legacy 값 검사를 사용하며, 이번 작업에서 더 엄격하거나 관대한 규칙으로 고치지 않는다.
- t1 정렬은 실제 sample의 최근접 매핑을 요구한다. 기본 허용 오차는 0.05초다. t1 자체가 불허 gap 안에 있으면 정렬이 불가하며 이후 query가 exact endpoint여도 mapping은 불가다.
- lookup은 유효한 정렬 상태 확인 → relative 유한 float 확인 → 테이블 재준비 → 절대 target 선택 → gap 설정·정책 검사 → 반환 순서다. 기존 정렬 cache와 파일 교체 시 invalidation을 유지한다.
- 준비한 time이 유한·엄격 증가이면 공통 함수의 위치를 사용한다. 그 외에는 기존 거리 `idxmin()` 경로를 유지한다. fallback의 동률은 남은 테이블의 첫 row이며, 더 이른 timestamp라는 보장은 없다.
- 허용 gap 설정은 양의 유한값이어야 한다. 단, target이 범위 밖이면 gap override 유효성 검사보다 먼저 unavailable이 될 수 있다. exact target도 in-range 선택 후에는 override 검사를 수행한다.
- gap 검사는 아래 식이다. 정렬한 unique time은 **gap 진단용**이며 선택 입력을 정렬·복구하는 것이 아니다.

```text
error = abs(selected_time - target)
median_dt = median(positive differences of sorted unique recorded times)
            (그런 차이가 없으면 0)

error > 0 이고 target을 둘러싼 두 timestamp가 존재할 때:
    surrounding_gap > max(allowed_gap, 3 * median_dt) 이면 unavailable
error > allowed_gap 이면 unavailable
```

- 이 소비자 비교에는 ROW-1의 표현 오차 허용식을 추가하지 않는다.
- 반환 필드는 `frame_index`, `timestamp_sec`, `error_sec`, `requested_relative_time_sec`, `relative_time_sec`이며 마지막 값은 `selected_time - t1`이다. `frame_index`는 준비한 테이블에서 얻는다. 위치를 그대로 frame으로 쓰거나 원래 frame 최소값을 다시 더하지 않는다.
- 기존 거절 상태·문자열·예외를 소비자 안에서 전후 비교한다. `t1_not_detected`, `t1_timestamp_gap_too_large` 등을 새 공통 패키지 예외로 대체하지 않는다. 지원 밖 malformed 값의 모든 예외가 동일한 `ValueError`라고 일반화하지 않는다.

### 모델 계산·메타데이터·GUI를 구분

- 공개 timeline 자체는 비교 identity를 검사하지 않는다. 공개 `load_file()`은 알 수 없거나 잘못된 source class의 alignment를 추가 제한한다.
- 공개 앱은 겹쳐 보는 곡선과 호환 반복 시험의 집계를 구분한다. 모델 identity가 다른 결과를 집계에서 제외한다고 모든 정렬 overlay까지 금지하는 정책으로 변경하지 않는다.
- FRAME-1의 숫자 mapping은 비교 metadata 검사와 별도다. 동기 GUI의 baseline 호환성·정렬 적격성 검사는 해당 소비자에서 유지한다.
- metadata만 다른 생성 결과를 사용해 `숫자 mapping`, `집계 제외`, `GUI 표시 적격성`을 각각 검사한다. 어느 하나의 성공으로 나머지 성공을 대신하지 않는다.

## 7. 소비자 도입·승인·되돌리기

### 출처 영수증과 도입 기록

두 기록을 구분한다.

1. `bma_shared_core/SOURCE_RECEIPT.json`: package/version, contract ID, canonical public repository, public baseline, 배포 프로젝트의 `__init__.py`, `time_selection.py`, `pyproject.toml`, `README.md` 원본 SHA-256을 기록한다. 줄바꿈은 LF로 고정한다. source drift를 검사하는 파일이며 사용처 검증을 대신하지 않는다.
2. 소비자별 adoption record: 실제 채택한 공개 canonical commit, 계약 버전, 소비자 baseline/adapter 버전, 적용한 kernel hash, 관련 검증 결과·승인자·상태, 이전 승인 버전과 dependency pin을 기록한다.

source receipt에 자기 자신이 들어갈 commit SHA를 미리 써 넣는 순환 조건을 만들지 않는다. canonical 실제 commit은 commit이 생긴 뒤 CI artifact 또는 소비자 adoption record에 기록한다. `published_commit=null`인 후보의 hash 일치로 게시·배포 완료를 선언하지 않는다. 기존 receipt의 부가 필드는 호환성을 유지하며, 현재 상태 판정은 실제 공개 ref와 도입 기록에 근거한다.

adoption record의 최소 구조는 다음과 같다. 예시의 null은 완료된 실제 기록이 아니라 미결정 상태다.

```json
{
  "schema_version": 1,
  "canonical_repository": "https://github.com/pikachu444/BoxMotionAnalyzer",
  "canonical_commit": null,
  "package_version": "0.1.0.dev0",
  "kernel_contract": "TIME-KERNEL/1",
  "consumer_profile": "ROW-1/1",
  "consumer_baseline": null,
  "adapter_version": null,
  "adopted_kernel_sha256": null,
  "evidence": [],
  "status": "pending",
  "approved_by": null,
  "previous_adoption": null,
  "rollback_dependency_pin": null
}
```

adoption schema는 JSON Schema draft 2020-12로 작성하며 아래 형·상태 규칙을 고정한다. 예시만 보고 필드를 임의 생략하지 않는다.

| 필드 | 형·규칙 |
|---|---|
| `schema_version` | integer, 정확히 1 |
| `canonical_repository` | 이 문서의 공개 저장소 URL |
| `canonical_commit` | null 또는 40자리 소문자 hex SHA; approved에서는 SHA 필수 |
| `package_version` | 비어 있지 않은 string; package metadata·선택한 dependency pin의 버전과 일치 |
| `kernel_contract` | 정확히 `TIME-KERNEL/1` |
| `consumer_profile` | `ROW-1/1` 또는 `FRAME-1/1` |
| `consumer_baseline`, `adapter_version` | null 또는 비어 있지 않은 string; approved에서는 string 필수 |
| `adopted_kernel_sha256` | null 또는 64자리 소문자 hex; approved에서는 실제 hash 필수 |
| `evidence` | 비어 있지 않은 string들의 array; approved에서는 최소 1개. 각 참조는 실제 검사·보고로 해석 가능해야 함 |
| `status` | `pending`, `approved`, `rejected`, `rolled_back` 중 하나 |
| `approved_by` | null 또는 비어 있지 않은 string; approved에서는 담당자·역할 식별값 필수 |
| `previous_adoption` | null 또는 이전 승인 record 식별 string. 최초 도입만 null 허용 |
| `rollback_dependency_pin` | null 또는 비어 있지 않은 string; approved에서는 필수. 이전 의존성이 없었으면 정확히 `not-installed` |

위 모든 필드는 required이며 추가 필드는 schema version을 갱신해 정의한다. `approved` 조건부 필수값, 잘못된 hash 길이, unknown status, 빈 evidence를 거부하는 schema 시험과 최초 도입의 `previous_adoption=null`을 허용하는 시험을 둔다. `rolled_back`은 복원 대상(이전 승인 record 또는 최초 도입 전 consumer baseline)과 복원 실행 결과를 evidence로 가리킨다. 이전 승인 유무는 소비자 이력으로 확인하며 schema만으로 확인됐다고 처리하지 않는다. schema 통과 자체는 실제 source·검증·승인을 확인한 것이 아니다.

- 실제 승인 기록에서는 source·baseline·adapter·hash·evidence·승인자 필수값의 null을 허용하지 않는다. 최초 도입의 `previous_adoption=null`은 예외이며 이전 구현과 dependency 상태를 복원 자료로 남긴다.
- 공개 record에는 공개 commit과 생성 fixture·공개 로그만 쓴다. 비공개 소비자의 baseline·입력 identity·승인자·실험 결과는 그 소비자 내부에 둔다. 외부 보고에는 승인된 범위의 `passed / pending / failed`와 한계만 제공한다.
- `adapter_version`은 해당 소비자의 호출 규칙 revision이다. package version 및 kernel contract version과 구분한다. 동작 규약을 바꿀 때 기존 version의 의미를 덮어쓰지 않는다.

### 도입 순서와 승격 게이트

1. 기존 소비자 commit·설정·입력 identity를 고정한다. 새 결과를 정답으로 사용하지 않는다.
2. 처음에는 canonical 함수와 receipt를 같은 바이트로 가져온다. 기존 import shim을 유지한다. 함수를 따로 수정한 소비자 fork를 만들지 않는다.
3. 생성된 동일 배열에서 kernel 위치/예외가 같은지 확인한다. 공개·소비자의 최종 출력이 다른 사례는 부록 C의 profile별 expected로 확인한다.
4. 각 **실제 adapter**를 이전 구현과 비교한다. frame/row, timestamp, error, None, 상태·거절 이유·예외 종류·fallback이 보존돼야 한다. reference harness만 통과하면 실제 도입은 pending이다.
5. 소비자 담당자는 기존 실험 입력·설정으로 실제 결과의 전후 일치를 확인한다. 시간 함수만 바꾸는 이번 도입에서는 해당 실제 결과의 시간 대응과 t1/거절 상태를 확인한다. 전체 Raw 최적화·씬 정확도·지표 물리 교정을 수행한 것으로 확대하지 않는다.
6. 향후 처리 알고리즘을 공통화할 때는 별도 승인된 전체 Raw 대표값 회귀가 필요하다. 이번 순수 함수 검증을 그 근거로 재사용해 통과 처리하지 않는다.
7. source 동일성, 해당 실제 adapter의 before/after, 필요한 소비자 실험 근거·승인이 모두 있는 조합만 새 승인 버전으로 승격한다. 미검증·skip·실패가 있으면 이전 승인 버전을 현재 버전으로 유지한다.
8. 중복 vendor에서 dependency로 전환할 때도 정확한 버전 또는 immutable commit을 pin하고 같은 검증을 확인한다. 승인된 출처·소유자 결정을 확인한 뒤 전환한다.

되돌리기는 이전 kernel·adapter·dependency pin을 한 묶음으로 복원한다. 배포 환경에서도 이전 버전을 다시 불러와 고정 계약과 해당 소비자 mapping을 재확인한다. receipt·expected만 수정해 실패를 지우는 것은 복원이 아니다. GUI 작업은 별도 commit으로 분리해 시간 함수의 rollback이 화면 변경을 끌고 다니지 않게 한다.


## Reproduction

- Fixed kernel fixture: [shared_time_kernel_contract.py](../../tests/fixtures/shared_time_kernel_contract.py)
- Fixed profile fixture: [shared_time_profiles.json](../../tests/fixtures/shared_time_profiles.json)
- ROW checks: `python -m pytest tests/test_shared_row_adapter.py tests/test_compare_model.py`
- FRAME reference checks: `python -m pytest tests/test_shared_frame_reference.py`
- [Source receipt](../../bma_shared_core/SOURCE_RECEIPT.json) and [execution evidence](validation.md)
