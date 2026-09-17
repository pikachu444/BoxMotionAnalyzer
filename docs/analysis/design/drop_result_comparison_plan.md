# Drop Result Comparison Plan

Last Reviewed: 2026-09-17

## 1. 목적
여러 낙하 실험 결과 `.proc`를 같은 기준으로 비교해, 반복 실험 간 자세 편차와 충격 경로 차이를 설명할 수 있게 한다.

현재 구현 범위는 단일 실험 결과에 Drop Posture frame/summary metric과 충격 시퀀스 summary를 저장하고, Step 2 Results Analysis의 `Summary`에서 확인하는 것은 물론, 런처의 `Experiment Comparison` 전용 윈도우를 통해 여러 결과를 다중 비교하는 기능까지 포함한다.

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
- Results Analysis는 summary를 `Summary` grouped table에 표시하고, frame metric은 컬럼 트리에서 선택해 plot할 수 있다.
- `Summary`의 표시 순서는 `Posture -> Impact -> Contact`이다.
- Drop Posture summary label, tooltip, metric guide 설명은 `src/config/result_metric_descriptors.py`의 descriptor metadata를 공통 기준으로 사용한다.
- `Metric guide` 버튼은 summary table 아래 푸터에 배치하며, Posture / Impact / Contact 3개 그룹 일러스트레이션과 지표 설명을 표시한다.
- `SustainedContact` 상태는 UI에서 `Stable floor contact`로 표시한다.
- `ReferenceFace`는 접근(Approach) 자세 기준면이다. 실제 충격 코너는 `FirstImpactContact`가 별도 기록한다.

## 3. 구현 완료된 비교 기능 (Experiment Comparison)
1. 비교 전용 윈도우
   - 런처에서 독립 창으로 연다.
   - 여러 `.proc` 파일을 선택하고 기준 실험을 지정한다.
   - 좌측 파일 선택과 우측 요약표·3D·그래프를 사용한다. 상세 메타데이터와 간격 설정은 접어서 연다.
2. 비교 지표 테이블
   - `Details`는 기존 파일별 summary와 호환 파일의 기준 대비 차이를 유지한다. `Pre-contact`는 접촉 전 운동 추정값, `Repeats`는 호환되는 서로 다른 관측의 지표별 통계를 표시한다. Summary 옆의 Experimental/Diagnostic 표시는 아래 #77의 미보정 범위를 유지한다.
   - 파일을 선택하면 출처와 모든 제외 사유를 확인할 수 있다. 값이 없거나 여러 행에서 상수가 아닌 summary는 유효한 첫 값으로 대체하지 않는다.
3. 비교 그래프
   - canonical 실제 시간과 유효한 `T1MinusTimeSec`가 있는 파일은 `t - t1_minus` 축에 표시한다. 파일별 원래 샘플링 시각을 유지한다.
   - 겹쳐 보기는 시각적 검토용이며 출처가 다르거나 집계에서 제외된 파일이 있다는 경고를 계속 표시한다.
   - 개별 보기에서는 실제 시간, 시간이 없으면 명시적인 sample row 축을 제공한다. 시간이나 t1을 0으로 만들지 않는다.
   - 표시 이름과 단위를 저장 키에서 분리한다. 파일별 고정 색과 실제 이름 범례를 사용하며, 각도의 기본 축 폭은 최소 1도다. 저장값과 사용자의 확대는 유지한다.
   - Cmin은 하나의 최저 코너 ID로 점과 C1~C8 축을 사용한다. 최저점 동률이나 전체 접촉부위를 뜻하지 않는다. 요약 비교도 ID를 빼지 않고 기준 ID와의 같은/다름을 표시한다.
4. 3D 비교 재생
   - 공통 elapsed 시계와 그래프 커서를 공유하며 실제 저장된 가장 가까운 샘플을 표시한다. 목표 시각과 선택된 샘플 시각은 구분한다.
   - 간격 제한(초, 초기 0.1)은 표시 정책이다. 긴 간격 내부·범위 밖·유효하지 않은 위치에서는 뷰어를 숨기고 이유를 표시한다. 보간이나 끝점 고정을 하지 않는다.
   - 공통 View의 기본 Individual은 선택 파일의 곡선·3D를 함께 제어한다. Aligned는 기존 충격 직전 표본을 0초로 맞춘다. 시간 미확정 자료는 Sample 1부터 탐색하고 유효한 기록 시간만 재생한다.
   - 보기·기준 변경에서 파일별 행과 카메라를 보존하고 실제 데이터가 바뀐 뷰어만 교체한다.
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
추천 정확도와 전체 #78 검증은 남아 있다. 이후 #75와 #77의 구현 단위는 현재 `implementation_todo.md`에서 구분한다.

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


## 6. #77 접촉 전 운동과 반복 관측 비교

사용자는 Step 1에서 자동 검출 구간을 검토하고 Step 1.5에서 처리한 `.proc`를 기존 런처의 `Experiment Comparison`에서 연다. 요약표의 `Pre-contact`, `Repeats`, `Details`를 바꿔 개별 추정값, 반복 통계, 기존 진단값을 확인한다. 출처는 파일 열에 표시하며, 제외 사유는 파일 상세와 값의 tooltip에서 확인한다. 새로운 장면 관리 팝업은 만들지 않는다.

확인한 코드상 `Position/CoM/P_TX...`는 기하학적 중심이다. 실제 COM은 별도 등록값으로 계산해야 한다. 기존 저장 속도는 중앙 미분과 필터 때문에 첫 접촉 표본을 포함할 수 있다. 새 추정기는 저장된 원래 pose와 실제 초 단위 시간에서 `t1-`로 끝나는 한쪽 이차 적합을 계산한다. 적합에는 접촉 이후 자세 표본이나 저장 Velocity 열을 쓰지 않는다. 접촉 구간을 확인하기 위해 다음 실제 timestamp와 접촉 summary는 읽는다. `t1-` 자체는 현재 접촉 알고리즘의 추정 시점이며 힘 센서로 확인한 접촉 시점은 아니다.

| 지표 | 값과 의미 | 보류할 조건 |
| --- | --- | --- |
| Vertical velocity | 기하 중심의 Y 속도, m/s, 위쪽 양수 | Y 자료나 적합 근거 부족 |
| Horizontal speed | 기하 중심 XZ 속력, m/s | X/Z 중 한 성분이라도 사용 불가 |
| Angular speed | 상대 회전에서 구한 세계 좌표 각속력, rad/s | 회전 누락·지원 각도/잔차 초과 |
| Velocity-equivalent height | 등록 COM의 하강속도로 구한 `1000 v_y²/(2g)`, mm | 검토·확정된 2018-03 G 자유낙하가 아니거나 COM/바닥/좌표 등록 불일치, 비하강 |

강체의 한 점은 `p + R c`로 움직인다. 따라서 COM이 기하 중심에서 벗어나 있으면 회전도 COM의 수직 속도에 기여한다. 기하 중심을 COM으로 자동 대체하지 않는다. 이 관계는 [MIT Press 강체 역학](https://mitp-content-server.mit.edu/books/content/sectbyfn/books_pres_0/9579/sicm_edition_2.zip/chapter002.html)의 병진·회전 분해에 따른다. `g=9.80665 m/s²`는 [BIPM의 관용 표준값](https://jcgm.bipm.org/vim/en/2.12.html)이다. 등가높이는 속도를 높이 단위로 표현한 분석값이며 실제 놓은 높이나 ISTA 합격 기준이 아니다. 시험에서 의도한 접촉 부위와 실제 관측을 비교하려면 시험 항목이나 사용자가 알고 있는 의도가 관측 결과와 별도로 주어져야 한다. 자동 검출한 접촉을 그대로 의도로 복사해 일치 판정을 만들지 않는다.

지원 범위는 최대 40 ms 창, 최소 5표본과 20 ms 길이, 최대 간격 20 ms이다. 원래 marker smoothing과 결과 resampling이 꺼져 있고 창 안의 pose가 Optimized이며 분석 면 할당이 같아야 한다. 위치 성분 적합 RMS 1 mm, 상대 회전 RMS 0.01 rad, 창의 기준 회전/이웃 회전 변위 0.25 rad 이내를 지원한다. 이것들은 실측으로 보정되지 않은 보수적인 소프트웨어 제한이며 ISTA 임계값이 아니다. 회전축이 바뀌는 분석식 두 경로의 약 0.15% 이내 결과를 일반적인 정확도 보장으로 확대하지 않는다. 정상 물리 운동도 이 범위를 벗어나면 보류할 수 있다.

통계는 기존 출처·모델·치수·타입·항목·마커 배치·실행 설정·시간 호환성 검사를 통과한 파일에서만 계산한다. 원 촬영 해시, 검토 구간, 항목이 같은 복사본·보정본은 한 관측으로 센다. 같은 촬영의 별도 구간도 통계적 독립성이 입증된 것은 아니다. 각 지표의 유효한 n, 평균, 최솟값, 최댓값, 범위를 따로 계산하며 n<3은 부족 표시를 한다. 각 낙하의 등가높이를 먼저 구한 뒤 평균한다.

첫 접촉·명시적으로 기록된 최종 면·접촉 confidence는 진단값이다. 접촉 범주의 기준 파일 일치는 의도한 목표 접촉 일치가 아니다. 현재 pipeline이 최종 면을 기록하지 않으면 해당 n은 0이며 ReferenceFace로 채우지 않는다. 각운동 추정이 지원되지 않아도 자체 사건 계약을 통과한 진단값의 집계는 따로 유지한다. #118의 저장 사건 일관성 계약과 상태별 confidence 집계는 `../reference/result_schema_notes.md`를 따른다. 저장 파일은 수정하지 않으며 다시 열 때 동일 근거에서 계산한다.

2026-09-12 사용자는 이 실험에 목표각도가 없음을 명확히 했다. 목표각도 오차는 #77 요구사항에서 제거한다. 각도 기준 자료를 요구하거나 해당 지표를 자료 부족으로 표시하지 않는다. 실제 접촉 전 자세, 접촉 부위·순서, 반복 관측 사이의 차이가 분석 대상이다. 기존 자세·접촉 진단값과 비교 기능을 먼저 재사용하고, 시뮬레이터의 대표 자세를 실험의 정답 자세로 사용하지 않는다.

자세 시간곡선, 기준 파일과의 차이, 접촉 빈도·기준 범주 일치는 이미 구현되어 있다. 아래 의도 접촉 비교는 이 흐름을 확장한다. 실측 접촉 시점·미분·방향·비교 정확도 검증은 #78에서 pending으로 추적하며, #77의 최종 CI·병합 상태는 연결된 PR에서 확인한다.

### 의도 접촉과 관측 접촉의 비교

Step 1에서 자동 검출 구간을 포함한 뒤 한 행을 선택하고, 등록한 박스 로컬 면·모서리·꼭짓점을 `Set contact`로 지정한다. 관측 항목 후보에 없는 부위도 지정할 수 있다. 예를 들어 실제로 BOTTOM 면이 닿은 기록에도 모서리 의도를 남겨 차이를 확인한다. 선택은 검출 결과에서 자동으로 채우지 않으며 Type·판본·COM 확정이나 목표각도는 필요하지 않다. `Contact unspecified`를 적용하면 의도를 지운다.

등록한 로컬 face 교집합으로 의도 코너 집합 T를 만든다. 결과의 C1–C8은 1부터 시작하며 면 6개, 실제 모서리 12개, 꼭짓점 8개만 유효하다. 저장된 첫 접촉 집합 O가 같은 형상이면 `Match`, 서로 다른 유효 형상이면 `Different`, 근거가 없거나 단일 형상이 아니면 `Unclear`다. 예를 들어 BOTTOM의 {C1,C2,C5,C6}을 의도했는데 {C1,C5}가 관측되면 `Different`다. 이는 접촉 형상의 차이이며 해당 면에 전혀 닿지 않았다거나 시험에 실패했다는 뜻은 아니다.

기존 비교 창의 `Contact`에서 파일별 의도, 추정 접촉, 판정, 촬영 시간축의 접촉 시각을 본다. 접촉 시각은 기존 높이 밴드·지속 표본 알고리즘의 추정값이며 힘 센서 정답이 아니다. 저장된 실행 형상·면 정의·좌표축·바닥 및 검토 등록이 일치해야 한다. 현재 자유낙하 구간의 접촉 전 한 표본과 접촉 두 표본이 연속·유효해야 하며, 기존 접촉 높이 기준의 공중→바닥 전이가 있어야 한다. 저장 코너·자세·첫 시점·두 표본의 접촉 집합을 기존 정책으로 대조한다. 등록 위치 허용값을 넘는 바닥 관통, 지지 회전, 잘린 사건, 추적 실패·면 할당 변경 또는 결과 재표본화는 `Unclear`로 남긴다. 접촉 비교에 속도 적합용 40 ms/5표본 조건을 적용하지 않는다.

집계는 같은 출처·모델·형상·마커·실행 설정·등록과 의도 부위를 만족하는 서로 다른 관측에 한정한다. Type·시험 번호는 로컬 형상 비교에 필수가 아니며 `Local n`은 ISTA 시험 횟수가 아니다. n은 `Match`와 `Different`의 합이며 `Unclear`와 제외 수는 따로 표시한다. 같은 촬영·구간은 시험 번호를 달리 적어도 한 번만 세고, 의도가 서로 충돌하는 사본은 집계에서 모두 제외한다. 파일별 비교 결과는 그대로 볼 수 있다. 기존 시험별 통계·원본·보정본·개별 그래프·3D 비교는 유지한다.

의도는 작업 파일과 `.slice`/`.proc`의 검토 JSON으로 전달된다. 동일 근거 재검출·항목 식별·재열기에서 유지하며 구간·형상·설정·시험 맥락이 바뀌면 활성 의도를 해제한다. 형상 변경과 재열기 재계산으로 검토가 무효화될 때 이전 의도는 `previous_review`에 보존한다. 기존 파일에 의도가 없으면 관측에서 채우지 않고 `Unclear`로 표시한다.

독립 물리 리뷰에서 저장 TOP/실제 BOTTOM 불일치, 한 표본 뒤 접촉 집합 변경, 바닥 관통, 보간 표본, 불필요한 시험 번호 요구를 발견해 수정했다. 각 반례의 재검토에서 앞 네 경우는 사유와 함께 `Unclear`, 미확정 Type의 유효 로컬 BOTTOM은 `Match`와 n=1을 확인했다. 코드 리뷰에서 형상 변경 시 의도 이력 소실을 수정했고 실제 Qt 조작으로 이력 보존을 재확인했다.

공개 MuJoCo 낙하는 현재 `.proc`를 직접 재열어 1.736/1.744/1.752초의 최저 코너 +7.942830/−2.488860/−6.163873 mm를 확인했다. 바닥 0 mm, 등록 허용값 1 mm를 초과하므로 최종 결과는 `Unclear`다. 초기 리뷰 전의 `Match` 화면은 최종 증거로 사용하지 않는다. 별도 분석식 입력은 바닥 도달 후 두 표본을 유지하며 면 일치·모서리와 면의 차이·의도 미지정을 각각 확인한다. 원본, 정답, 실행 및 화면 증거는 `tmp/issue77_contact_gui_20260912/`에 분리 보존한다. 가상 자료의 소프트웨어 동작 확인이며 실측 접촉 정확도나 ISTA 적합성 검증은 아니다.


### 입력과 독립 리뷰 결과 (2026-09-12)

| 입력 | 기대와 확인 결과 |
| --- | --- |
| 분석식 직렬화 입력: 3/-4/0 m/s, 세계 Z 회전 2 rad/s, 명시적 zero COM | 수직 -4, 수평 3, 각속력 2, 등가높이 815.772970 mm. 저장 Velocity를 999999로 바꾸거나 접촉 뒤 반발값을 바꿔도 유지 |
| 서로 다른 SHA의 분석식 반복 -1/-2/-3 m/s | 유효 n=3, 평균 -2, 최소 -3, 최대 -1, 범위 2. 등가높이 평균은 각 높이를 먼저 계산한 237.933783 mm. 복사본/동일 원 촬영의 보정본은 n을 늘리지 않음 |
| 실제 pipeline이 저장한 공개 MuJoCo 낙하 `.proc` | 1.696~1.736 s의 접촉 전 6표본에서 -1.34398536144 m/s. 별도 보존한 truth의 같은 표본에 대한 -1.3439700 m/s와 근접. 과거 중앙 미분값 -1.3043499 m/s는 사용하지 않음. H 미확정이므로 등가높이 없음 |
| 실제 pipeline이 저장한 공개 지지 기울임 `.proc` | 충격 t1이 없어 4개 접촉 전 운동 지표 보류. 회전을 낙하 충격으로 대신 계산하지 않음 |
| 같은 처리 조건의 smoothed 입력 3개 | 원래 pose의 접촉 전 추정은 보류, 유효한 접촉 진단값 n=3은 유지 |
| fabricated real 선언과 synthetic/dummy/public/unknown 선언 혼합 | 출처가 다른 값은 실험 통계에서 제외. 이 검사는 실측 입력 검증이 아님 |

직접 계산과 파일 해시는 `tmp/issue77_actual_metrics_20260912/execution.json`, 집계/기존 비교 검사는 `tmp/issue77_comparison_model.xml`과 `tmp/issue77_comparison_followup.xml`에 남겼다. 첫 집계 검사에서 단일 접촉 fixture를 `{C3}`로 잘못 작성한 실패가 있었고, 실제 `_contact_label`의 `C3` 저장 계약을 확인해 입력을 고쳤다. 기대 통계나 허용 오차를 완화하지 않았다.

2026-09-13에는 이 수동 확인을 기존 `test_marker_face_gui_flow.py`의 공개 면 낙하 실행에 연결했다. 생성기 1.3의 300×180×90 mm·32마커·100표본 입력에서 작업자가 0.520초의 X 보정을 승인하고, 실제 MainApp의 Raw 처리·`.proc` 저장 후 정식 reader로 지표를 계산한다. 기존 한 번의 자세 추정과 1/20 mm 접촉 설정 비교를 재사용하며 별도 정상 Raw 실행을 추가하지 않는다. 가상 자료의 `not_applicable` 타입을 유지하므로 G 전용 환산 높이는 보류한다.

| 실제 저장 결과의 입력 | 사전에 정한 기대 | 확인한 값 |
| --- | --- | --- |
| 0.096–0.136초의 접촉 전 6표본 | 수직 −1.343970 m/s, 수평 0.0291547595 m/s, 각속력 0 rad/s | −1.3439713027 m/s, 0.0291541566 m/s, 0.0000367027 rad/s |
| 이미 계산한 자세의 원본 프레임 60–71을 선택해 postprocess·저장·재열기 | 12표본의 지속 접촉, 새 충격·t1 없음, 운동 수치 4개 보류 | `SustainedContact`, 정확한 원본 자세·시간·범위 보존, 수치 4개 모두 사유와 함께 보류 |

기하 접촉 진단의 첫 표본은 0.144초다. 기존 저장 중앙 미분은 접촉 이후 표본을 포함할 수 있어 정답으로 사용하지 않는다. 분리된 정답과 같은 저장 자세를 각각 고정 6점 가중치로 미분해 대조했다. 재열린 자세의 기존 0.1 mm/0.1° 허용값에서 유도한 속도 오차 상한은 0.02232143 m/s, 일정한 정답 자세의 각속력 상한은 0.52204045 rad/s이다. 특히 각속력 상한은 느슨하므로 실측 정확도 보장이 아니며, 동일 저장 자세의 계산 대조와 구분한다. 목표각도나 확정 G 항목을 주입하지 않는다.

단일 실제 실행은 55.85초에 통과했다. 새 공개 수치·해시 보고서는 `tmp/issue84_public_metrics/collision_face-y9ux47z3/public_impact_metrics.json`에 있고, 이후 실행도 고유 폴더를 사용해 과거 1.2 자료를 보존한다. CI에는 이 수치 JSON만 추가 보존한다. 이 작업은 기존 지표의 원본부터 결과까지의 회귀 검증이며 새 분석 기능이나 실측·ISTA 검증 완료를 뜻하지 않는다.

독립 코드 리뷰는 검사 종료 시점의 파일 변경이 보고서만 실패로 바꾸고 CI에는 전달되지 않는 결함을 재현했다. 최종 파일 변경·삭제를 보고서에 먼저 보존한 뒤 검사 자체도 실패하게 수정하고, 임시 파일의 두 반례에서 직접 재확인했다. 이 보고 단계 수정 뒤 정상 Raw 처리는 반복하지 않았다. 독립 물리 검토는 실제 저장 자세와 분리 정답을 직접 계산해 지표와 지속 접촉 보류를 확인했다. 최종 CI·병합 상태와 #84의 나머지 범위는 이슈와 PR에 기록한다.

| 독립 지적 | 수정과 재검토 |
| --- | --- |
| 단일 위치 오류가 큰 RMS에도 유효 속도/높이로 통과 | 성분별 RMS 지원 판정. Y +1000 mm 반례는 RMS 339.817878 mm와 사유를 남기고 수직/높이만 보류. 물리 담당 직접 재현·수정 확인 |
| 비고정축 큰 회전에 이차 적합 편향 약 5% | 0.25 rad 지원 범위로 한정. 원 반례는 보류하고 지원 안의 두 경로를 독립식으로 재확인. 소규모 잔차가 실측 정확도를 보장하지 않음 |
| raw/corrected 파일을 별도 실험으로 집계 | OriginalSourceSha256 정규화. 실제 직렬화한 쌍에서 n=1과 중복 사유를 코드 담당 재확인 |
| pose 추정 조건 실패가 진단 통계도 막음 | 관측 identity와 pose 지원 판정 분리. smoothing 3개에서 속도 n=0, 접촉/confidence n=3 재확인 |
| 선택적 SceneReview의 null 구조가 파일 열기를 막음 | 명시적 구조 검증. identity/candidate/detection=null 파일도 기존 개별 그래프/summary로 열림 |
| 실제 반복 제외 수와 배너/상세 불일치 | 같은 집계 이유를 배너와 상세에서 사용. 혼합 출처의 지속 경고와 파일별 출처도 보존 |

이 단위의 실제 입력은 `unit_contract`와 `synthetic_integration`이다. 독립적으로 라벨링한 실측 비교나 ISTA 적합성 검증은 수행하지 않았다. 물리·코드 검토자는 구현 설명만이 아니라 변경 코드, 직렬화 파일, 독립 반례와 실행 기록을 직접 확인했다. GUI 최종 실행과 CI/병합 상태는 아래 후속 기록 및 PR에서 구분한다.


### 실제 비교 창 확인

Windows 125% 배율에서 실제 CompareMainWindow/VTK를 실행했다. 창은 1510×800 logical, 테두리 포함 1887.5×1031.25 physical로 1920×1080 안에 들어가는 크기였다. 모니터 해상도를 변경한 검증은 아니다. QtTest로 실제 버튼·모드·기준 선택·삭제·스크롤을 작동시켰고 파일 선택 반환 경로는 주입했다. 외부 마우스로 전체 운영 환경을 인증한 것은 아니다.

- 세 관측의 n=3/평균 -2/범위 2, 복사본 추가 후 n 유지와 제외 이유, 기준 변경, 삭제 후 n=2, 재열기 후 n=3, 취소 후 기존 파일 보존을 확인했다.
- 실제 공개 낙하/기울임 `.proc`에서 수치와 보류 이유, 파일별 출처, 혼합 출처의 지속 경고를 확인했다. 원래 `.proc` bytes와 계산용 DataFrame은 변하지 않았다. 실제 VTK 박스/마커 렌더를 별도로 확인했으며 Qt 캡처의 검은 native 영역을 합성해 채우지 않았다.
- 기본 표가 두 행만 보이던 분할을 조정해 네 운동 지표를 처음부터 보여준다. 긴 3D 파일명은 중간 말줄임과 전체 tooltip으로 바꿨다. 데이터 후 x축 제목을 붙일 때 여백을 다시 계산하도록 고쳐 제목 잘림을 해소했다. 통계의 추가 진단 행과 개별 3D 조작에는 스크롤을 사용한다.

`tmp/issue77_comparison_gui_20260912/audit.json`이 단계별 결과를 연결한다. `run_01/01_repeats_duplicate.png`는 실제 중복 제외 통계, `run_02/02_public_inputs_precontact.png`는 공개 처리 결과와 미확정 H/기울임 보류, `run_02/03_public_drop_vtk.png`는 실제 3D 렌더다. 최종 기본 배치는 `run_06_final_layout/01_final_default_metrics_plot.png`로 확인했다. x축 제목의 하단 경계는 -6.194 px에서 +18.750 px로 바뀌어 canvas 안에 있다. 주 에이전트도 화면과 실행 JSON, 현재 코드 해시를 직접 대조했다.

중간 하네스의 불필요한 스크롤 존재 가정과 NumPy bool JSON 직렬화 오류는 별도 실패로 보존했다. 그래프 제목 잘림은 실제 제품 문제였으며 수정 후 해당 화면만 다시 확인했다. 이미 통과한 수치·저장·이벤트 흐름을 이유 없이 재실행하지 않았다. 두 독립 리뷰를 마쳤으며 최종 CI·병합 결과는 #77과 연결 PR에 기록한다.


### 첫 원격 CI에서 확인한 식별값 읽기 문제

PR #93의 첫 CI 34669654729는 원본·보정본 중복 제외 사유 검사에서 실패했다. pandas 3.0.5가 숫자로만 된 `OriginalSourceSha256`를 Python int로 읽어 유효한 관측 키를 만들지 못했다. 기존 pandas 2.3.3에서는 문자열로 읽혀 로컬 검사를 통과했던 차이다. 원본 해시 열에도 문자열 converter를 명시했고, 정수에서 해시를 추측해 복원하지 않는다. 선행 0을 포함한 해시도 정확한 문자열로 재열린다.

격리한 pandas 3.0.5에서 실제 직렬화·로더·호환성·집계 경로를 확인하고, 기존 2.3.3에서는 원 실패 사례와 새 해시 보존 사례만 다시 확인했다. 기대 n이나 허용 오차는 바꾸지 않았다. 수치 추정과 GUI 코드는 그대로이며 해당 독립 승인은 유지된다. 기록은 `tmp/issue77_pandas3_fix.xml`과 `tmp/issue77_pandas2_fix.xml`이다. 최종 원격 CI 결과는 PR에 기록한다.

## 7. #118 저장 사건 모순 차단 (2026-09-17)

기준 main은 `3ace8159f8504b0cc1c11e923f03494c5448f6f0`이다. 사용자가 계획과 기존 Details/Repeats의 최소 표시 목업을 승인했다. 저장 진단을 보존하되 선언·실제 시간 연결·출처를 입증하지 못하면 제외하는 정책을 적용했다. 정확한 계약·legacy 변경 범위는 `../reference/result_schema_notes.md`의 Recorded first-event consistency를 따른다. #119의 중복 해소나 #120의 bounded 검출/재계산은 구현하지 않았다.

### 독립 기대값과 실행

입력은 공개 `impact_metric_fixtures.make_frame()`의 명시적 시간·저장값과 `test_contact_comparison.contact_frame()`의 독립 코너 기하/시간이다. seed나 비공개 실자료는 사용하지 않았다. contact_frame의 바닥 코너 집합은 `{C1,C2,C5,C6}`, t1/사건/다음 표본은 0.072/0.080/0.088초로 미리 정해져 있다. 저장 confidence 0.75는 스키마 검증용 literal이며 검출기의 물리 정답이나 기하 재계산 점수가 아니다.

| 입력/조작 | 독립 기대값 | 결과 |
| --- | --- | --- |
| ImpactDetected=False, NoContact인데 stale 접촉값 유지 | 접촉/confidence unavailable, 각각 n=0 | 직접 계산과 저장·재열기 일치 |
| flag/state 한 필드 변경, 누락·중복 열·행 충돌, NaN/Inf/off-timeline/중복·역행 시간 | 해당 사건 제외 및 원인 | 회귀 통과 |
| smoothing, 3표본 사건, raw pose 성분 부재 | 속도 unavailable; 접촉 `{C1,C2}`, confidence .75 유지 | 통과; 사건과 미분 적합 지원 분리 |
| 정상 비충격, 잘못된 confidence, tracking_jump 선언 | 첫 접촉 n=0; 상태/오류 구분 | 직접 계산·재열기·Qt 통과 |
| 공개 정상/모순 파일 한 쌍 | first_contact n=1, confidence n=1/mean=.75; Contact Match=1/Unclear=1 | Qt 조작과 새 모델 재열기 일치; 입력 bytes 불변 |
| legacy Contact의 사건 뒤 C8 NaN | 기존 Unclear 유지 | #120 경계 회귀 통과 |

Windows Python 3.13.5, NumPy 2.2.4, pandas 2.2.3, SciPy 1.15.2의 초기 계산/모델 검사 225개가 통과했다. 기존 프로젝트 가상환경(Python 3.13.5, Qt/PySide6 6.10.1, MuJoCo 3.6.0)에서는 `QT_SCALE_FACTOR=1.25`로 다음 검사를 실행해 **244 passed**를 얻었다:

```text
python -m pytest -q tests/test_impact_metrics.py tests/test_impact_comparison.py tests/test_contact_comparison.py tests/test_compare_model.py tests/test_impact_comparison_gui.py tests/test_contact_comparison_gui.py tests/test_comparison_gui.py tests/test_comparison_layout.py --basetemp tmp/issue118/pytest_final1 --disable-warnings --tb=short --junitxml=tmp/issue118/all.xml
```

화면 검토 후 짧은 사유 표시를 수정한 최종 GUI 재실행은 `tests/test_impact_comparison_gui.py` **5 passed**이며 `tmp/issue118/gui_final.xml`에 남았다. 독립 리뷰의 최초 관련 검사 **169 passed**, tracking-jump 수정 재검사 **9 passed**도 별도로 확인했다. 로컬 필수 범위에 skip은 없었다. 초기 sandbox 임시 폴더 접근 실패, 기본 Python의 MuJoCo 부재로 인한 GUI 수집 실패, 새 테스트의 표시명 대소문자 불일치는 성공으로 세지 않았다. 각각 실행 환경·기존 환경 선택·테스트 표시명을 바로잡았으며 수치 기대값은 완화하지 않았다.

### 실제 화면과 독립 수정

실제 CompareMainWindow/Qt 위젯에서 Open, 모드 전환, 스크롤 및 값/사유를 검사했다. 파일 선택 반환값은 주입하고 QTest 입력을 사용했다. 측정 크기는 **1510×800 logical, DPR 1.25**다. 외부 Windows 조작 도구에는 이 실행 창이 노출되지 않아 OS 네이티브 마우스 검증 완료로 보고하지 않는다. Qt 캡처의 검은 OpenGL 자식 영역은 별도 VTK 원본 렌더로 확인했고 합성하지 않았다. 레이아웃 단위 검사의 mock VTK와 이 실제 렌더 검증을 구분한다.

- `tmp/issue118/qt_b744b474`: 초기 Details의 전체 필드 사유가 셀 높이를 넘는 것을 발견한 화면.
- `tmp/issue118/qt_51b46040`: 최종 Details/Repeats, 별도 `vtk.png`, 입력 hash와 literal n을 담은 `execution.json`. 첫 접촉 행 24 logical px, 표 viewport 49 px로 사유가 읽힌다. 이후 재실행은 고유 `qt_*` 폴더에 보존하며 CI도 공개 결과를 artifact로 보관한다.
- 공개 GUI `valid.proc` SHA-256: `0aa2bee8c4cc16aef5b2f3de1c3a64a3d9ffb4f4f31a9b0372c09c491c4b3059`; `stale.proc`: `ff49f8d69e35cdd0ce91a9651254ba8225683adcaef2a2d89426523d385fa138`.

독립 리뷰는 tracking_jump 선언이 저장 접촉 진단에 남는 누락을 찾아 공통 검사와 직렬화 회귀를 추가하도록 했다. 자가검토에서는 비충격 상태의 잘못된 confidence 표시와 긴 셀 사유를 수정했다. 리뷰어가 수정 코드·문서·최종 화면을 다시 대조해 남은 actionable 지적이 없음을 확인했다. 실측 물리 정확도·보정 확률·ISTA 합격 판정은 이 검증으로 주장하지 않는다. 최종 commit/PR/필수 CI는 연결 PR에서 추적하며, 사용자 검토 전 병합·자동 병합·이슈 종료를 하지 않는다.
