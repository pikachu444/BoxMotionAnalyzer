# Drop Result Comparison Plan

Last Reviewed: 2026-09-11

## 1. 목적
여러 낙하 실험 결과 `.proc`를 같은 기준으로 비교해, 반복 실험 간 자세 편차와 충격 경로 차이를 설명할 수 있게 한다.

현재 구현 범위는 단일 실험 결과에 Drop Posture frame/summary metric과 충격 시퀀스 summary를 저장하고, Step 2 Results Analysis의 `Experiment Summary`에서 확인하는 것은 물론, 런처의 `Experiment Comparison` 전용 윈도우를 통해 여러 결과를 다중 비교하는 기능까지 포함한다.

## 2. 현재 완료 기준
- processing 완료 및 Result Resampling merge 이후 `DropPosturePostProcessor`가 실행된다.
- 접촉 판정은 단일 threshold만 사용하지 않고, 최저 코너 높이의 절대 높이, 하강/저점/반전, 낮은 높이 plateau, 접촉 corner set 지속성을 함께 보는 evidence 기반으로 수행한다.
- 접촉 상태는 `NoContact`, `Approach`, `ImpactEvent`, `SustainedContact`로 요약한다.
- `t1-`는 `ImpactEvent`가 확인될 때만 정의하며, 접촉이 없거나 이미 낮은 plateau 상태로 시작한 slice에서는 t1 관련 summary를 `NaN`으로 둔다.
- 기준면은 `t1-`가 있으면 그 frame에서, 없으면 slice 첫 valid frame에서 아래 방향을 가장 많이 향한 박스 면으로 자동 추정한다.
- frame metric은 `Analysis / DropPosture`에 저장한다.
- summary metric은 `.proc` 호환성을 위해 `Analysis / DropPostureSummary` 상수 컬럼으로 반복 저장한다.
- `DeltaH_mm`은 8개 전체 코너 높이 범위가 아니라, 기준면을 이루는 코너들의 높이 차이로 계산한다.
- 충격 시퀀스 `ImpactSequence`는 최소 2 frame 이상 지속된 접촉 이벤트만 사용하며, 동시 접촉은 `{C1,C2}`처럼 그룹으로 표기한다.
- Results Analysis는 summary를 `3. Drop/Impact Summary` grouped table에 표시하고, frame metric은 컨럼 트리에서 선택해 plot할 수 있다.
- `3. Drop/Impact Summary`의 표시 순서는 `Posture -> Impact -> Contact`이다.
- Drop Posture summary label, tooltip, metric guide 설명은 `src/config/result_metric_descriptors.py`의 descriptor metadata를 공통 기준으로 사용한다.
- `Metric Guide...` 버튼은 summary table 아래 푸터에 배치하며, Posture / Impact / Contact 3개 그룹 일러스트레이션과 지표 설명을 표시한다.
- `SustainedContact` 상태는 UI에서 `Stable floor contact`로 표시한다.
- `ReferenceFace`는 접근(Approach) 자세 기준면이다. 실제 충격 코너는 `FirstImpactContact`가 별도 기록한다.

## 3. 구현 완료된 비교 기능 (Experiment Comparison)
1. 비교 전용 윈도우
   - 런처에서 독립 창으로 연다.
   - 여러 `.proc` 파일을 선택하고 기준 실험을 지정한다.
   - 탭(Tab) 방식을 배제하고, 좌측 설정 사이드바와 우측 3단 뷰어(요약표, 3D 뷰어, 비교 플롯)를 한 화면에 동시 노출하는 입체적 카드 레이아웃을 사용한다.
2. 비교 지표 테이블
   - 모든 파일의 개별 summary를 표시하고, 출처·메타데이터·시간 조건이 호환되는 파일만 기준 실험 대비 차이를 표시한다. 평균 집계는 구현하지 않는다.
   - 파일을 선택하면 출처와 모든 제외 사유를 확인할 수 있다. 값이 없거나 여러 행에서 상수가 아닌 summary는 유효한 첫 값으로 대체하지 않는다.
3. 비교 그래프
   - canonical 실제 시간과 유효한 `T1MinusTimeSec`가 있는 파일은 `t - t1_minus` 축에 표시한다. 파일별 원래 샘플링 시각을 유지한다.
   - 겹쳐 보기는 시각적 검토용이며 출처가 다르거나 집계에서 제외된 파일이 있다는 경고를 계속 표시한다.
   - 개별 보기에서는 실제 시간, 시간이 없으면 명시적인 sample row 축을 제공한다. 시간이나 t1을 0으로 만들지 않는다.
   - 툴바를 세로로 우측에 배치하여 가로 공간 효율을 높였다.
4. 3D 비교 재생
   - 공통 elapsed 시계와 그래프 커서를 공유하며 실제 저장된 가장 가까운 샘플을 표시한다. 목표 시각과 선택된 샘플 시각은 구분한다.
   - 간격 제한(초, 초기 0.1)은 표시 정책이다. 긴 간격 내부·범위 밖·유효하지 않은 위치에서는 뷰어를 숨기고 이유를 표시한다. 보간이나 끝점 고정을 하지 않는다.
   - Sync를 끄면 개별 샘플 탐색이 가능하다. 유효한 기록 시간이 있는 파일만 개별 시간 재생을 제공한다.
   - 자세한 저장 계약과 호환성 필드는 [result_schema_notes.md](../reference/result_schema_notes.md)를 따른다.

## 4. 검증 방향
- 단순 컬럼 존재 테스트가 아니라, 물리적으로 예상 가능한 synthetic 자세에서 각도와 코너 높이 차이가 수치적으로 맞는지 검증한다.
- 실제 raw data slice에서 접촉 없음, impact event, 낮은 plateau 상태를 나눠 검증한다.
- 기존 flow test 예제 `TestSets/Input/VDTest_S5_001.csv`의 `TestBox_85` 데이터를 85인치 실제 예제로 사용한다.
- 과거 `(2082.9, 1046.6, 254.4)` mm 추정치를 사용한 검사는 실물 규격/원점/축 등록을 검증한 증거가 아니다. 그 값을 실제 모델 메타데이터로 자동 채우지 않는다. VDTest 독립 등록 자료는 현재 unavailable/pending이다.
- `TestBox_85` 접촉 검증은 바닥 접촉 slice `2.45s-3.05s`를 잘라 pipeline 처리, export, DataHandler reload, DataLoader reload까지 수행한다.
- 실제 데이터 검증은 결과 컬럼을 그대로 신뢰하지 않고, 코너 좌표와 회전벡터에서 각도/높이/접촉 근거를 독립 재계산해 비교한다.
- 비교 기능은 동일 실험을 두 번 로드했을 때 차이가 0에 가까운지, 의도적으로 기울인 synthetic 결과의 차이가 입력 각도와 일치하는지 확인한다.
- #83/#76 검사에서는 실제 직렬화 `.proc`의 서로 다른 샘플률/불규칙 간격/긴 gap, 원본 frame 번호, 각 필수 메타데이터 누락과 출처 분리를 확인한다. fabricated `real` 선언은 단위 계약 증거이며 실제 측정 검증으로 보고하지 않는다.

## 5. #83/#76 실행 확인 (2026-09-11)

아래 결과는 별도 `issue83-provenance-time` worktree에서 실행했다. 원본 #74
체크아웃은 수정하지 않았다. Python 실행 파일만 원본 `.venv`에서 공유하고
`src.__file__`가 새 worktree를 가리키는 것을 확인했다.

| 입력 / 증거 분류 | 기대 결과 | 실제 결과 |
| --- | --- | --- |
| 직렬화한 contract `.proc`, 서로 다른 절대 시각·샘플률·불규칙 dt, 원본 frame 100/104/108 (`unit_contract`) | 각자의 실제 `t-t1` 정렬, frame 번호를 샘플 위치로 혼동하지 않음 | 정렬된 곡선 시각과 선택 row 확인. 원본 frame이 건너뛰어도 3개 row만 렌더링 |
| 각 필수 identity 필드 누락 또는 한 필드 변경, source class 변경 (`unit_contract`) | 모든 해당 사유를 표시하고 baseline 차이 제외 | 개별 summary/그래프를 유지하면서 제외. fabricated real 선언은 실측 증거가 아님 |
| 중복/역행/비유한 time, canonical 누락·legacy-only·열 충돌, t1 누락/false/범위 밖 (`unit_contract`) | 동기화 unavailable; 0/frame fallback 없음 | 각 입력의 제외 이유와 개별 보기 경로 확인 |
| 1.031→2.0 s gap, limit 0.1 s (`unit_contract`) | 그래프 선 단절, gap 내부/범위 밖 3D unavailable | NaN break와 hidden viewport 확인. 단절 양 끝의 실제 값 보존 |
| 공개 MuJoCo 생성 raw에서 truth/event 파일을 제거한 뒤 corrected/slice/proc 저장 (`synthetic_integration`) | production은 safe identity만 읽고 원본 bytes와 출처를 보존 | truth 접근 없이 round-trip. 선언한 box 치수와 다른 slice 저장은 차단 |
| 공개 32-marker X collision, 실제 MainApp의 파일 선택→수동 보정→재열기→slice→proc (`synthetic_integration`) | 100행, 원본 XYZ·보정 이력·출처 및 실제 처리 설정 보존, 기존 수치 기준 유지 | 100행 유지, synthetic identity 완비. 최대 위치 오차 0.00012165 mm, 회전 오차 0.00007496°; 최종 선택 검사 73.21 s. 실제 OptiTrack 정확도 아님 |
| 위 GUI-produced `.proc` 두 복사본을 실제 Compare 파일 선택 창에서 열기 (`synthetic_integration`) | 둘 다 synthetic, 호환, baseline 차이 0, 동일 t1 | 100/100행, 제외 사유 없음, t1=0.136 s. 독립 실험 두 번이나 반복 실험 통계 증거가 아님 |
| 실제 CompareMainWindow: 빈 상태·파일 선택·loading·malformed·unknown·gap·긴 파일명·900×650 resize (`unit_contract` inputs / real GUI path) | 상태/제외 사유를 읽고 개별 탐색 가능 | actual Qt events/file dialogs로 확인. widget capture와 실제 VTK viewport capture를 분리해 점검 |

재현 명령은 저장소 루트에서 실행한다. 이 worktree에서는 `python` 대신
`C:/SourceCodes/BoxMotionAnalyzer/.venv/Scripts/python.exe`를 사용했다.

```powershell
python -m pytest tests/test_compare_model.py tests/test_artifact_provenance.py tests/test_comparison_gui.py -q
python -m pytest tests/test_processing_semantics.py tests/test_slice_dimension_provenance_gui.py -q
python -m pytest tests/test_header_converter_acceleration.py tests/test_visualization_data_handler.py tests/test_visualization_proc_support.py tests/test_artifact_io_filters.py tests/test_marker_flip_artifact_io.py -q
python -m pytest tests/test_slice_batch_processing.py tests/test_processing_mode_config.py tests/test_pipeline_resampling_options.py tests/test_range_limited_resampling.py tests/test_results_analyzer_experiment_summary.py -q
python -m pytest 'tests/test_marker_face_gui_flow.py::test_production_mainapp_face_review_save_and_process[collision_face]' -q
```

마지막 collision 검사는 선택한 전체 pipeline 검사다. 매 편집마다 #74 전체
행렬을 재실행하지 않았다. `tmp/issue83_gui/`에 empty/loading/malformed/gap/
unknown/resize 화면과 `individual_3d.png`가 있고,
`tmp/issue83_public_compare/`에 실제 공개 산출물 쌍의 화면·viewport·결과 JSON이
있다. Windows의 Qt `grab()`은 native VTK 영역을 검게 캡처할 수 있어 실제
렌더러의 viewport를 별도 캡처했다. 영상을 만들거나 화면을 합성하지 않았다.

처음 검사에서 pandas의 중복 열 처리와 Qt에 넘긴 numpy bool, 초기 카메라가
바닥만 보이던 문제를 발견해 수정했다. 초기 임시 검사 폴더의 상위 경로가
없어 난 setup error는 입력 검증 성공으로 세지 않았다. 최종 관련 검사와
독립 리뷰/CI는 서로 다른 검증 단계다. 실제 OptiTrack 비교 쌍, 자동 marker
추천 정확도, #75 장면 검토, #77 물리 지표 및 전체 #78 검증은 남아 있다.

### 독립 리뷰에서 확인한 다섯 결함과 수정

| 재현 입력 | 기존 문제 | 수정 후 기대/실제 |
| --- | --- | --- |
| 같은 GUI-produced 공개 collision 포즈에 실제 접촉 설정 1mm/20mm로 postprocess | t1은 0.136/0.120 s로 달라지는데 고정 처리 버전 때문에 호환으로 표시 | 실제 실행 설정 JSON/hash가 달라지고 `ProcessingSemanticsVersion` 및 `ProcessingSettingsJson` 불일치로 제외. 기존 XYZ/물리식은 바꾸지 않음 |
| 시작 0/1/100/1000 s, 10Hz, gap limit 0.1 s | 표현 오차 `0.10000000000000009`를 긴 gap으로 오판 | 원시 timestamp에서 공통 ULP 비교 후 표시 x만 elapsed로 변환. 정상 간격은 단절 0; 실제 0.100001 s 및 큰 epoch의 초과 gap은 거부, 1ps cap 유지 |
| Info/Artifact만 제거하고 정상 canonical time/t1 유지 | unknown 파일이 공통 overlay/3D/시간 범위에 참여 | unknown/invalid source는 공통 동기화 제외. 같은 파일의 개별 recorded-time 그래프·샘플 탐색은 유지 |
| 정상 세 행 `.proc`의 CoM X 한 셀을 `bad`로 변경 | 샘플 이동 시 예외로 이전 정상 자세가 남음 | 위치를 numeric-coerce하고 viewer를 먼저 숨김. 해당 행은 unavailable, 다른 정상 파일은 계속 갱신. 실제 Qt signal 경로에 예외 없음 |
| 일반 box 치수 누락, Artifact 치수 200/120/80인 `.slice`에서 300/120/80 보완 | 모순된 파일을 먼저 저장하고 UI를 잠근 뒤 processing에서 거부 | direct update와 실제 GUI 모두 저장 전 거부. 원본 bytes·300 입력·편집 가능 상태 보존. 200/120/80 보완은 정상 저장 후 잠금 |

처리 설정 검사는 active 필터/미분/spline/접촉/trim/padding/resampling 정책의
단일 변경과 같은 설정의 다른 시작 시각/샘플률을 직렬화해 비교한다. 꺼진
필터의 미사용 cutoff 변경은 다른 실행으로 기록하지 않는다. 실제 resampling
단계의 factor/linear 정책도 확인한다. raw 선언으로 실행 이력을 채우거나,
JSON/hash 불일치·상수 아님·누락을 기본값으로 복구하지 않는다.

접촉 설정 재현은 새 전체 포즈 추정을 두 번 돌리지 않고, 실제 GUI가 만든
동일한 포즈/실행 이력을 복사해 production postprocess만 각각 실행했다.
초기 검사 준비에서 이미 계산된 DropPosture 열을 다시 입력해 join 충돌이
났으며, 재처리 입력에서 그 파생 열만 제거했다. 원래 포즈와 실행 이력은
보존했다. 이 실패는 수정된 검사의 성공과 별도로 기록한다.
관련 결과는 `tmp/issue74_gui/collision_face/contact_settings_regression.json`과
`contact_1mm.proc`, `contact_20mm.proc`에 있다. GUI 추가 증거는
`tmp/issue83_gui/invalid_position.png`, `source_only_individual.png`,
`dimension_rejection.png`, `dimension_editable_after_failure.png`,
`dimension_match_saved.png`다. 최종 소스 SHA와 검사 시점은
`tmp/issue83_execution.json`에 기록한다. 독립 재리뷰와 같은-head CI는 아직
별도 완료 조건이며, 실측 검증과 이슈 전체 완료로 확대하지 않는다.
