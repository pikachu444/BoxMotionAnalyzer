# Code Structure Notes (Current)

Last Reviewed: 2026-09-12

## 1. 목적
결과 컬럼 스키마를 Analysis/UI/Export 전 구간에서 일관되게 유지하기 위한 현재 구조를 요약한다.

## 2. 데이터 흐름
1. `PoseOptimizer`가 포즈 컬럼(`P_TX`~`P_RZ`)과 코너 좌표를 생성
2. `VelocityCalculator`가 Global 속도/가속도 및 코너 속도(`Global_V_*`)를 계산
3. `FrameAnalyzer`가 BoxLocal 속도/가속도(`BoxLocal_*`)와 Analysis 결과를 계산
4. `DropPosturePostProcessor`가 처리 완료 결과에서 낙하 자세 비교용 frame metric과 summary metric을 계산
5. Export 시 `convert_to_multi_header()`가 flat 컬럼명을 Multi-Header로 변환
6. `WidgetResultsAnalyzer`는 `DISPLAY_RESULT_COLUMNS` 기준으로 트리/플롯 항목을 표시하고, UI에서는 `Metric-first` / `Object-first` 계층 전환과 검색 필터를 제공한다
7. `Visualization`은 export된 `HeaderL3` metric 키를 long-format 내부 컬럼에도 그대로 재사용한다

## Scene review metadata (#75)

`SceneReviewJson=<JSON>` is optional in the existing second `.slice` metadata row.
Step 1.5 carries it as `scene_review_json`; `.proc` writes the constant string at
`('Info', 'SceneReview', 'Json')`. Legacy files without it remain readable.
Version 1 records the capture SHA-256, automatic and reviewed bounds, motion
evidence, include decision, censor flags, gravity episodes, detector settings,
optional static registration and its hash, conditional posture matches, separate
identity confirmation, and the working list's include/exclude decisions/deletions.
`gravity_evidence_start/end` are accepted differentiation-window centres, not
measured release/contact times. `floor_crossings` are geometric approach brackets,
not measured contact forces. Slice padding remains separate from reviewed bounds.
New slice metadata must describe an included interval with matching finite bounds.
Unknown Type/item can still be analyzed; it cannot supply a comparison identity.
Dimension changes clear registered geometry evidence and item confirmation.
Optional `candidate.motion_geometry` version 1 records the observation-range
reference time, floor and position tolerance, maximum/final relative rotation,
least-moving edge and its maximum endpoint travel, fixed-edge candidates, geometric
support status, starting-face angle gap/ambiguity guard/status, and opposite-edge
maximum height when defined. Lengths are mm and
angles are degrees. Corner indices are zero-based; the UI labels them C1–C8.
The starting downward face describes the first observed pose, not a confirmed
trial-start contact face. Fixed-edge motion does not establish support force or
trial intent. Range or geometry changes clear these measurements; `.proc` retains
the complete reviewed JSON rather than recalculating it from padded result rows.
Writes finish a temporary file before replacing the destination; a failed replace
keeps the prior slice and a cleanup failure remains attached to the primary error.

`*.scene-review.json` is a separate whole-record working file with
`kind=boxmotion-scene-review`, version 1. It records the active CSV path (relative
when possible) and SHA-256, box dimensions in mm, static registration, detection
settings/version, Type/edition context, all rows/deleted IDs/manual ID counter,
and selected row/signal/plot targets. Pending registration changes are saved from
the current input even before redetection; conflicting dimensions must be resolved
before saving. It does not embed observations or replace `.slice`.
Reopening parses the referenced CSV and recomputes each saved range. Cached
derived evidence is compared exactly after JSON normalization; it never feeds
the detector. Changed evidence or context returns the row to `unreviewed`, with
its previous decision/identity and reasons in `previous_review`. Confirmed items
must still belong to the recomputed candidates and supported edition. Saving is
atomic and rejects CSV destinations; unfinished reviews can be saved, while
included-slice export continues to require every row's review.

## Artifact identity and comparison time (#83 / #76)

`src/utils/artifact_metadata.py` owns the versioned public identity contract. The
Analysis pipeline's `artifact_io.save_proc_file` writer emits these constant columns,
each at `('Info', 'Artifact', field)`:

| Field | Stored type / meaning |
| --- | --- |
| SchemaVersion | String `1`; only exact version 1 is currently compatible |
| SourceKind | `real`, `public_external`, `mujoco_synthetic`, `handcrafted_dummy`, or `unknown_legacy` |
| ModelId | Explicit model identity; never inferred from a filename |
| BoxLengthMm, BoxWidthMm, BoxHeightMm | Positive finite numbers in mm |
| IstaType | Explicit reviewed type, or `not_applicable` for declared non-ISTA fixtures |
| ScenarioId, ScenarioKind | Explicit scenario identity and kind; synthetic cases do not approve an ISTA scene |
| MarkerLayoutId, MarkerLayoutHash | Explicit profile ID and stable geometry/assignment hash |
| ProcessingSemanticsVersion | `analysis-face-v3-time-v2:sha256:<digest>` of the executed policy JSON |
| CoordinatePolicy | Explicit world/local basis and origin policy identifier |
| UnitsPolicy | Explicit units contract identifier |
| GeneratorVersion | Required for synthetic/dummy input; otherwise may be blank |
| ProcessingSettingsJson | Canonical JSON of executed single-pass, result-resampling and postprocess policies |

Other than dimensions, fields are strings. Missing values serialize as blank CSV
cells (JSON `null` in source metadata). Readers do not fill missing schema/model/
type/layout values. Missing source class displays as `unknown_legacy`. A field
that varies across rows is invalid even if its first row appears usable.
Identity strings bypass CSV numeric/NA inference: `001` differs from `1`, `NA`
is a literal identifier, and a digits-only lowercase SHA-256 retains all 64 digits.

New writers set schema 1; reading old files does not declare them schema 1. A new
derived artifact may have the new container schema while retaining unknown source
identity. No metadata completeness check is evidence of physical calibration.
This applies to the Analysis writer and safe identity transport from the new public
observed-data generator. The Simulation UI exporter now declares its actual synthetic source and known
geometry/coordinate/unit/generator fields, with separate simulation settings below.
Earlier Simulation outputs without declarations remain unknown legacy; they are
not upgraded by filename or inferred geometry.

Safe source identity is a JSON object under `Artifact Metadata` in a generated
raw CSV's first metadata row. Corrected CSV and `.slice` retain it as
`artifact_metadata=<JSON>` in their existing second metadata row. The loader
accepts only the 16 fields above. This is separate from correction history and
from test-only `*.synthetic.json`; production never opens the truth/event manifest.
User-entered slice dimensions cannot silently contradict declared artifact dimensions.

`ProcessingSettingsJson` is exactly `('Info','Artifact','ProcessingSettingsJson')`,
constant across rows. The current schema-1 contract includes this field; older
15-field or fixed-version results remain readable but are excluded from baseline
differences/aggregation because they lack a verifiable executed settings record.
Canonical encoding uses sorted object keys, separators `,`/`:`, ASCII escaping,
finite JSON numbers and no indentation. The UTF-8 bytes produce the lowercase
SHA-256 digest in `ProcessingSemanticsVersion`. Missing/nonconstant/malformed JSON,
noncanonical encoding, unsupported version or a mismatching digest excludes the
file. A JSON object must contain nonempty `single_pass`, `result_resampling` and
`postprocess` stage records. This is provenance consistency, not authentication
of an externally supplied file or evidence of real-world accuracy.

The production controller records configured component settings after the stages
execute. Single-pass policy includes enabled marker-filter sequence and active
parameters, actual optimizer options/geometry/face definitions, active pose and
derivative filtering, spline/finite-difference policy, explicit floor/vertical-axis
settings, padding frame count and trimming policy. Inactive filter parameters are
omitted. Resampling records the actually executed factor, linear result-row policy
and full/limited scope; a limited interval uses selected offsets relative to the
slice, never absolute trial timestamps. Postprocessing records the threshold passed
to the processor and its configured geometry, face definitions, floor and axis.
No calculated t1, inferred sampling rate, data values, input path/hash or selected
absolute trial start/end enters the processing fingerprint. The same actual-dt
policy can therefore compare trials with different sampling rates and time origins.

Limited-range provenance uses `range_offset_encoding =
shortest-decimal-input-ulp-v1`. Subtract the exact binary64 endpoint and origin in
decimal arithmetic, then choose the shortest decimal offset (1 through 17
significant digits, nearest-even ties) whose distance from that exact difference
is at most `(ulp(endpoint) + ulp(origin)) / 2`. Serialize that candidate as a JSON
number; if no candidate qualifies, retain the binary64 difference. Zero remains
zero. This models the rounding uncertainty of the two input clock values rather
than imposing a fixed decimal-place grid. Non-finite inputs fail explicitly.
It affects only the settings fingerprint, never row selection, timestamps,
interpolation or physical calculations. It is separate from the graph/playback
gap comparison's raw-clock ULP/1ps policy and has no fixed time tolerance.

For example, slices starting at 1s and 100s with selected offsets 0.1–0.3s
produce the same settings; changing the endpoint by 1e-10s remains distinguishable
at both origins. Even a 1e-14s change remains distinguishable at a zero origin.
Precision remains limited by the original binary64 clocks: changes inside their
rounding uncertainty may share a fingerprint, and large clock origins can lose
fine timing distinctions before this function receives them. Universal identity
under arbitrary origin shifts or decimal rounding-boundary cases is not promised.
The encoding tag distinguishes this contract from older unnormalized limited-range
records; those records are not silently promoted or rewritten.

The execution record travels in the processed DataFrame's private attributes until
the Analysis writer emits the two artifact columns. The writer discards any raw
declaration of those processing fields when attaching a newly processed result;
absent execution records are not replaced with current defaults. Postprocess-only
execution on a legacy result cannot claim the missing earlier stages. Generator
source identity is separate from these executed settings.

Public generator examples explicitly declare a virtual model, absolute-mm layout,
`IstaType=not_applicable`, `ScenarioId=public-<motion>-v1` and
`ScenarioKind=synthetic_<motion>`. These describe the generator's standalone case,
not an approved physical test. Its coordinate policy is
`world-y-up-box-local-fixed-center-v1`; units policy
`bma-mm-s-rotvec-rad-summary-deg-v1` means mm and seconds, pose rotation vectors in
radians and DropPosture degree metrics. Generator version is 1.3. No actual CSV's
source/model/type is inferred from Motive-like headers or from its file name.

Comparison eligibility requires complete, constant identity, supported schema,
known source kind, and matching model, dimensions, type/scenario, layout ID/hash,
processing semantics, coordinates and units. Source classes cannot mix. Different
generator builds are permitted if those explicit contracts match; build IDs remain
visible. All failed keys are reported, not only the first mismatch. Unknown or
incompatible files keep individual summary/graph/3D sample review. Baseline
differences are withheld for excluded files. No aggregate mean/statistics is
implemented by this change; `get_summary_differences` remains baseline subtraction.
Unknown or invalid source classes are also excluded from the common overlay,
playback and elapsed bounds even when canonical time/t1 exist. Individual time or
sample-row review remains available. Known but incompatible source classes may
still be overlaid with a persistent warning; they never gain aggregate eligibility.

`src/utils/result_time.py` owns result time reading. Canonical time is exactly
`('Info', 'Time', 'Time')` in seconds. Event alignment requires constant
`('Analysis', 'DropPostureSummary', 'T1Detected') = True` and finite in-range
`('Analysis', 'DropPostureSummary', 'T1MinusTimeSec')`. Graphs and the playback clock
use elapsed seconds `t - t1_minus`. No `T1MinusFrame`, frame-zero, zero-time or
index fallback participates in synchronization.

Identical copies of a time *column* are accepted and collapsed where their tuples
match. Canonical plus legacy `('Time','Time','Time')` columns must have identical
numeric values. Conflicting columns, nonfinite time, duplicate *sample timestamps*,
or decreasing time disable alignment. Legacy-only time is available for individual
time plots, never as a replacement for missing canonical time. With no usable
time, individual graphs label the x-axis `Sample row (time unavailable)`.

Irregular positive sampling intervals are supported. The comparison UI exposes a
gap display limit in seconds (initially 0.1 s). This is a user-adjustable continuity
policy, not an error tolerance, measured acquisition cadence, or physical threshold.
Graphs insert a NaN break across longer intervals without deleting their endpoints.
Both graph and playback use one gap comparison on recorded timestamps. Up to four
combined floating-point ULPs, capped at 1e-12 seconds, account only for subtraction
roundoff at the configured limit. Exact decimal 0.1 s sampling is not fragmented
by `0.10000000000000009`; a true excess remains a gap. Large absolute timestamps
cannot enlarge this allowance into a physical tolerance.
At a common clock time, 3D chooses the nearest recorded sample within a continuous
interval (ties choose earlier); the actual chosen sample time is shown. No pose is
interpolated. Internal long gaps, invalid position samples, and times outside a
file's range show 3D unavailable rather than clamping/holding a pose. Different
sample rates do not imply simultaneous observations. Rendering uses row positions
0..N-1, independently of original frame labels such as 100,104,108.
Nonnumeric position cells are coerced to unavailable values. The comparison viewer
is hidden before validating a new sample, so a bad string cannot retain a stale
pose or prevent the other files from updating. Existing slice-dimension update
and manual-apply paths validate declared artifact dimensions before changing disk
or locking the GUI; a rejected value preserves the original bytes and editable input.

## 3. 단일 진실원(SoT)
- `src/config/data_columns.py`
  - `PoseCols`, `VelocityCols`, `AnalysisCols`: 계산/저장용 컬럼명
  - `DropPostureCols`, `DropPostureSummaryCols`: 낙하 자세 비교용 계산/저장 컬럼명
  - `HeaderL1~HeaderL3`: Multi-Header 키 정의
  - `DISPLAY_RESULT_COLUMNS`: Results Analyzer 표시 스펙
- `src/config/result_metric_descriptors.py`
  - Drop Posture summary의 UI 표시명, group, 단위, tooltip, metric guide 설명, visual guide id
  - Step 2 `Experiment Summary`, Data Selection tooltip, 향후 compare window 설명의 공통 기준
- `src/config/config_visualization.py`
  - visualization 내부 metric 키와 UI metric metadata 정의
  - `DF_*` metric 상수는 `HeaderL3` export 키를 직접 재사용

실제 동작 규칙은 위 파일을 기준으로 본다.

## 4. 현재 스키마 요약
- CoM Position: `P_T*` 후 `P_R*`
- CoM Velocity/Acceleration: `BoxLocal_*` 먼저, `Global_*` 나중
- Norm은 `*_Norm` 표기로 고정
- Corner는 Translation 성분만 사용하며 Velocity에는 `Global_V_T_Norm` 포함
- Drop posture frame metric은 `(Analysis, DropPosture, *)`에 저장한다.
- Drop posture summary metric은 `(Analysis, DropPostureSummary, *)`에 저장하며, `.proc` CSV 호환성을 위해 모든 row에 같은 값을 반복한다.
- Drop posture summary 설명 metadata는 `result_metric_descriptors.py`에서 관리하며, 저장 스키마 키 자체는 `data_columns.py`의 `HeaderL1~HeaderL3`와 `DropPostureSummaryCols`를 기준으로 유지한다.
- Visualization long-format도 `Global_V_TX`, `BoxLocal_A_T_Norm` 같은 export metric 키를 그대로 사용

## 5. Drop Posture 스키마
- Frame metric (계산 기준 및 부호 규약)
  - `BetaDeg` (단위: degree)
    - **계산 기준**: 포즈에 의해 결정된 박스의 자동 기준면(Reference Face)의 법선 벡터(Normal)와 바닥 방향(Z=-1 등) 법선 벡터 사이의 절대 각도.
    - **부호 규약**: 항상 양수(0 ~ 180도).
  - `ThetaLongDeg` (단위: degree)
    - **계산 기준**: 기준면에 수평하게 놓인 로컬 긴 축(Long axis) 방향의 기울기 각도.
    - **부호 규약**: `asin((positive-side height - negative-side height) / local-axis length)`. 즉, 로컬 축의 양의 방향(Positive) 코너가 음의 방향(Negative) 코너보다 높을 때 양수(+).
    - **해석 주의점**: 첫 충격(first impact) 이전에는 물리적으로 의미가 명확하지만, 그 이후 여러 코너가 닿으면서 요동칠 때는 직관과 다를 수 있음 (추후 검토 필요).
  - `ThetaShortDeg` (단위: degree)
    - **계산 기준**: 기준면에 수평하게 놓인 로컬 짧은 축(Short axis) 방향의 기울기 각도.
    - **부호 규약**: `ThetaLongDeg`와 동일. 로컬 짧은 축의 양의 방향이 더 높을 때 양수(+).
  - `CminIndex` (단위: index, 1~8)
    - **계산 기준**: 해당 프레임에서 절대 높이(Z좌표)가 가장 낮은 코너의 번호. 코너 번호는 로컬 좌표계 C1~C8 기준.
  - `DeltaH_mm` (단위: mm)
    - **계산 기준**: 해당 프레임에서 기준면(Reference Face)을 구성하는 4개 코너 중 가장 높은 코너의 높이에서 가장 낮은 코너의 높이를 뺀 값.
    - **부호 규약**: 항상 양수. 0에 가까울수록 기준면이 바닥과 평행함을 의미.

- Summary metric (계산 기준)
  - `BetaAtT1MinusDeg`: t1- 시점의 BetaDeg 값. `T1Detected=False`이면 NaN.
  - `MaxBetaDeg`: 선택 구간 전체에서 BetaDeg의 최댓값.
  - `ThetaLongAtT1MinusDeg`: t1- 시점의 ThetaLongDeg 값. `T1Detected=False`이면 NaN.
  - `MaxAbsThetaLongDeg`: 구간 전체 |ThetaLongDeg|의 최댓값.
  - `ThetaShortAtT1MinusDeg`: t1- 시점의 ThetaShortDeg 값. `T1Detected=False`이면 NaN.
  - `MaxAbsThetaShortDeg`: 구간 전체 |ThetaShortDeg|의 최댓값.
  - `DeltaHAtT1Minus_mm`: t1- 시점의 DeltaH_mm 값. `T1Detected=False`이면 NaN.
  - `MaxDeltaH_mm`: 구간 전체 DeltaH_mm의 최댓값.
  - `CminAtT1MinusIndex`: t1- 시점의 CminIndex 값. `T1Detected=False`이면 NaN.
  - `T1MinusTimeSec`: t1- 시각(초). `T1Detected=False`이면 NaN.
  - `ReferenceFace`: 기준면 레이블 (예: `BOTTOM`, `SIDE_X_POS`). 아래 별도 항목 참고.
  - `LongAxis`, `ShortAxis`: 기준면의 긴 축/짧은 축 레이블 (예: `LocalAxis0`).
  - `T1Detected`: `ImpactEvent`가 확인되어 t1-이 정의된 경우 True.
  - `ImpactDetected`: 접촉 threshold 또는 motion evidence 기반으로 충격이 감지된 경우 True.
  - `SustainedContactDetected`: slice 후반부 낮은 plateau가 지속된 경우 True.
  - `ContactState`: `NoContact`, `Approach`, `ImpactEvent`, `SustainedContact` 중 하나.
  - `ContactConfidence`: 0.0~1.0 사이 접촉 신뢰도. evidence 개수와 종류에 따라 산출.
  - `ContactDetectionMethod`: 사용된 evidence 조합 (예: `threshold+motion+plateau`).
  - `ImpactSequence`: impact event 구간 접촉 이벤트 순서 문자열 (예: `C2 -> {C2,C3} -> C5`).
  - `ImpactEventCount`: ImpactSequence에서 집계된 별개 이벤트 수.
  - `FirstImpactTimeSec`: ImpactSequence 첫 이벤트 시각(초).
  - `FirstImpactContact`: ImpactSequence 첫 이벤트 접촉 코너 표기 (예: `C2`, `{C1,C2}`).

- `ContactState`는 `NoContact`, `Approach`, `ImpactEvent`, `SustainedContact` 중 하나다.
- 접촉 판정은 단일 threshold가 아니라 최저 코너 높이의 절대 높이, 하강/저점/반전, 낮은 plateau, 접촉 corner set 지속성을 함께 보는 evidence 기반 summary다.
- `t1-`는 `ImpactEvent`가 확인될 때만 정의한다.
- 접촉 frame이 없거나 slice가 이미 낮은 plateau 상태로 시작하면 t1 기반 summary는 `NaN`으로 저장한다.
- 접촉이 없어도 frame metric과 `Max*` summary, 기준면, contact state summary는 계산한다.
- Step 2 `Experiment Summary`는 descriptor group 순서에 따라 `Posture -> Impact -> Contact`로 표시한다.
- `T1Detected=False`이면 UI에서는 t1 기반 summary를 `N/A`로 표시한다. 저장값은 기존 `.proc` 호환을 위해 `NaN`을 유지한다.
- `ImpactSequence`는 impact event 구간에서 검출한 접촉 이벤트 순서다.
  - 최소 2 frame 연속 접촉만 이벤트로 인정한다.
  - 동시 접촉은 `{C1,C2}`처럼 하나의 이벤트로 묶어 표기한다.
  - 예: `{C1,C2} -> C5 -> {C6,C7,C8}`

## 5-1. ReferenceFace 의미 및 설계 결정

**현재 동작**: `ReferenceFace`는 t1- 시점(또는 t1-이 없으면 slice 첫 프레임)에서, 법선 벡터가 아래 방향을 가장 강하게 향하는 박스 면을 자동으로 선택한다.

**사용자 기대와의 차이**: `ReferenceFace`가 낙하 직전 접근 자세의 기준면이 아니라, 첫 충격 이후 실제로 바닥과 닿은 면을 가리킨다고 오해할 수 있다.

**설계 결정 (현행 유지)**:
- `ReferenceFace`는 **접근(Approach) 자세 기준면**으로 정의한다. 즉, 충격 직전 t1-에서의 자세 기준이다.
- 실제 충격 접촉 코너는 `FirstImpactContact`와 `ImpactSequence`가 별도로 기록하므로 중복 저장할 필요가 없다.
- `ApproachReferenceFace` / `ImpactContactFace` 분리는 현재 범위에 포함하지 않는다. 필요하다면 향후 `ImpactContactFace` 컬럼을 `FirstImpactContact`로부터 역산해 추가할 수 있다.
- 이 결정은 `result_metric_descriptors.py`의 `ReferenceFace` descriptor long_description에도 반영한다.

## 5-2. Marker correction provenance

corrected CSV에서 만든 `.slice`를 처리한 경우 `.proc`에는 아래 provenance가 `(Info, MarkerCorrection, *)` 그룹으로 들어간다. CSV 호환성을 위해 각 값은 모든 결과 row에 반복된다.

- `SchemaVersion`
  - corrected source와 결정 JSON의 metadata schema version
- `AlgorithmVersion`
  - 후보 생성과 추천 evidence를 만든 marker-flip 알고리즘 버전
- `OriginalSource`
  - 최초 관측 원본 파일명
- `OriginalSourceSha256`
  - 최초 관측 원본 파일의 SHA-256 식별값
- `ReviewedSource`
  - 면 할당(v3) 또는 기존 열 순열(v2)이 반영된 corrected CSV 파일명
- `EventCount`
  - OFF/거절을 포함한 전체 검토 이벤트 수
- `ApprovedEventCount`
  - 작업자가 Apply ON으로 저장한 이벤트 수
- `EventsJson`
  - 이벤트별 경계, 추천 축, 추천 사유/evidence, 작업자 승인, 작업자 선택 축, 실제 열 순열, 알고리즘/gate 버전을 보존한 JSON

- `ContextJson`
  - v3 승인 당시 원본 면, 크기, 좌표 정책, 원본 메타데이터 및 해시

`EventCount`와 `ApprovedEventCount`는 다를 수 있다. OFF 판단도 감사 이력에 남긴다. `PipelineController`는 이 metadata를 보고 포즈를 사후 회전하거나 보정을 재적용하지 않는다. 실제 v3 FaceInfo는 corrected CSV/slice 본문의 annotation에서 읽어 PoseOptimizer에 전달한다. 보정 경계에서는 필터와 미분을 분리하며 경계 미분값은 미확정으로 남긴다.


## 6. 구버전 대비 변경 포인트
- `_Ana` 접미사 기반 표기 -> `BoxLocal_` 접두사 표기로 전환
- `Norm_V`, `Norm_A` 류 표기 -> `*_Norm` 표기로 통일
- `TestSets` 운영 구조 분리:
  - `TestSets/Input/` (tracked)
  - `TestSets/Output/` (ignored)

## 7. 유지보수 가이드
스키마 변경 시에는 아래 4개를 항상 함께 수정해야 한다.
1. `src/config/data_columns.py`
2. `src/config/result_metric_descriptors.py` (Drop Posture summary 설명/tooltip/guide 변경 시)
3. `src/utils/header_converter.py`
4. `src/analysis/*` 계산 모듈 (`velocity_calculator.py`, `frame_analyzer.py`, `drop_posture_post_processor.py`)
5. `src/analysis/ui/widget_results_analyzer.py`
6. `src/config/config_visualization.py`
7. `src/visualization/data_handler.py`

그리고 `tests/test_header_converter_acceleration.py`,
`tests/test_result_format_layout.py`,
`tests/test_results_analyzer_experiment_summary.py`,
`tests/test_real_drop_posture_physics.py`,
`tests/test_real_data_flow.py`,
`tests/test_visualization_data_handler.py`를 함께 갱신해야 회귀를 방지할 수 있다.

85인치 실제 데이터 검증은 `TestSets/Input/VDTest_S5_001.csv`의 `TestBox_85` 데이터를 사용한다. 접촉 flow 검증은 `2.45s-3.05s` slice를 85인치 치수로 처리하고, export/reload 후 pose/corner 좌표에서 `BetaAtT1MinusDeg`, `DeltaHAtT1Minus_mm`, `CminAtT1MinusIndex`를 독립 재계산해 summary 값과 비교한다.

## Simulation direct `.proc` additions (#81)

Simulation saves replace the destination only after a complete UTF-8 CSV has been
flushed and closed in the same directory. I/O failure preserves the previous file;
the three-level schema, version, numerical values and missing-value semantics do
not change. Failure cleanup and retry behavior are documented in [simulation.md](../../simulation.md).

These fields supplement the 16 `Info/Artifact` keys; they never replace them or
claim execution of the Analysis solver. Every new direct Simulation output has
`SourceKind=mujoco_synthetic`, `GeneratorVersion=simulation-pose-actual-time-v1`,
`CoordinatePolicy=world-y-up-box-local-fixed-center-v1` and
`UnitsPolicy=mm-s-rotvec-rad-global-angular-v1`. The UI passes configured local X/Y/Z
size as BoxLengthMm/BoxWidthMm/BoxHeightMm. A direct exporter caller lacking these
settings leaves dimensions blank. ModelId, IstaType, scenario/layout identity,
ProcessingSemanticsVersion and ProcessingSettingsJson remain blank. No t1 or
DropPosture metrics are fabricated; individual time/3D inspection works while
baseline differences and synchronization are excluded by the existing gates.

| Three-level tuple | Value and units |
|---|---|
| `Info / Simulation / ExportVersion` | Constant string `simulation-pose-actual-time-v1` |
| `Info / Simulation / SettingsJson` | Constant compact sorted JSON string: configured engine size/mass/friction/contact control/COM offset/initial state/timestep/duration/MuJoCo version when supplied by UI; derivative, pose, angular frame and noise policies |
| `Info / Simulation / Representation` | Constant `simulation-truth` or `body-pose-truth;noisy-corner-observations` |
| `Simulation / BodyPose / QW,QX,QY,QZ` | Four per-row float values, dimensionless normalized sign-continuous quaternion wxyz, unchanged local box basis to Y-up world |
| `Simulation / InertialCOM / X_mm,Y_mm,Z_mm` | Three per-row floats, actual inertial COM in Y-up world mm; legacy Position/CoM remains body origin |

Unknown additive Simulation/Info fields are ignored by existing DataHandler entity
selection and comparison identity readers. They do not become markers and are not
consumed as correction truth by #74. Safe core source metadata still drives the
existing source banners. JSON uses true/false and null; CSV missing values are empty
cells. Required time, quaternion and position values are finite or export fails.
One-sample histories retain pose and have unavailable derivatives. First velocity
and first two acceleration rows are NaN/empty, including angular derivatives.
Position/CoM/P_RX,P_RY,P_RZ retain the existing rotvec-rad contract, not Euler.
Global angular velocity and acceleration keys are rad/s and rad/s². Full formulas,
interval timing, aliasing and noise limitations are defined once in
[simulation.md](../../simulation.md#23-데이터-익스포터-digital-twin-data-pipeline-srcsimulationdata_exporterpy).
Simulation SettingsJson is not Analysis ProcessingSettingsJson and is not accepted
as its required stage record; no schema bypass or unverifiable identity backfill
is performed. Old consumers that require complete finite derivatives must mask the
initial unavailable samples rather than replace them with a claimed zero.
DataHandler preserves an explicitly stored norm column even when every value is
NaN. Only a missing norm column in a legacy file permits fallback: all three
components must be finite in that row. A partial/missing/non-finite component
leaves the norm unavailable. This policy applies to global and supported box-local
linear velocity/acceleration norms; it never substitutes zero for unknown motion.
