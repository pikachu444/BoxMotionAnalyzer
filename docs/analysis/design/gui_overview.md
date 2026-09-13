# Box Motion Analyzer v2.2 GUI 구조 설명서

Last Reviewed: 2026-09-13

## 개요
이 문서는 현재 구현된 분석 GUI의 구조를 설명한다. 기준 코드는 `src/analysis/app/main_window.py`, `src/analysis/ui/widget_raw_data_processing.py`, `src/analysis/ui/widget_slice_processing.py`, `src/analysis/ui/widget_results_analyzer.py`이다.

## 1. 전체 구조
- 메인 분석 창은 `QTabWidget` 기반의 3단계 흐름으로 구성된다.
- `Step 1: Raw Data Slice`
  - 원본 CSV 로드, 미리보기, 슬라이스 범위 지정, `.slice` 저장
- `Step 1.5: Slice Processing`
  - `.slice` 로드, processing mode / Result Resampling 설정, processing 실행, `.proc` 저장
- `Step 2: Results Analysis`
  - `.proc` 로드, 컬럼 선택 플롯, 팝업 플롯, 지점 분석, 시나리오 CSV 내보내기
- 하단 `QStatusBar`는 파일 로드, 처리 진행, 저장 성공/실패 상태를 표시한다.

## 2. Step 1: Raw Data Slice
`WidgetRawDataProcessing`이 담당한다.

### 2.1. 상단 레이아웃
- 좌측: Matplotlib 그래프와 네비게이션 툴바
  - 파일 로드 직후 파싱된 `parsed_data`를 기준으로 미리보기 그래프를 그린다.
  - `PlotManager`가 확대/축소, 마우스 오버, 슬라이스 구간 선택을 처리한다.
- 우측: 제어 패널
  - `Load CSV File...`
  - 선택된 파일 경로 표시
  - `Box Dimensions (mm)` 입력
  - `Marker Flip Review`
    - `Review Candidates...`
    - 현재 검토 이벤트 수와 승인 이벤트 수
    - 현재 활성 원본 또는 corrected CSV 경로
    - `Save Corrected Source...`
  - 로그 출력 텍스트 영역

### 2.2. 하단 컨트롤
- `Plot Options`
  - `Select Data...`
  - 선택된 대상 표시
  - 축 선택 콤보박스 (`Position-X`, `Position-Y`, `Position-Z`)
- `Slice Range`
  - 체크 가능한 그룹 박스
  - 활성화 시 `Start`, `End` 입력값과 그래프 구간 선택기가 동기화된다
- `Slice Output`
  - `Scene Name`
  - 고정 padding 설명 (`50 rows on each side`)
  - 최근 저장된 `.slice` 경로 표시
- 실행 버튼
  - `Save Scene Slice`

### 2.3. 주요 동작
- 파일 로드 시 `DataLoader`와 `Parser`가 즉시 미리보기용 데이터를 준비한다.
- `Review Candidates...`는 `Rigid Body Marker`의 자세 불연속 후보를 찾고, 각 경계에서 `보정 없음 / 로컬 X 180도 / 로컬 Y 180도 / 로컬 Z 180도` 면 할당 가설을 실제 PoseOptimizer로 다시 계산한다. 계산 중 로드·크기 변경·저장을 잠근다.
  - 로컬 축은 박스 로컬 주축이며, 실제 물리 회전 원인을 뜻하지 않는다.
  - 3.1은 보정할 경우 자세 불연속을 가장 줄이는 축을 조건부 추천한다. 오류 원인 판정이 아니며 모든 이벤트의 `Apply`는 기본 OFF다. 부족한 관측, 서로 비슷한 가설, 안정되지 않은 창은 추천을 보류한다.
  - 작업자가 축을 선택하고 승인한다. 대응 마커 쌍은 필요 없지만 모든 마커의 원래 분석 면이 알려져 있어야 한다.
  - 그래프와 상세 정보는 선택한 축의 실제 재계산 잔차와 면 적합 RMSE를 표시한다. 공통 표본에서 재계산한 NONE과 비교하며 점수 차이는 신뢰 확률이나 실제 마커 대응률이 아니다.
- 승인된 v3 보정은 XYZ와 ID를 그대로 두고 경계 이후 프레임별 분석 FaceInfo를 변경한다. 실제 물리 마커 좌표의 복원이나 Motive Rigid Body 포즈 수정은 아니다.
  - 이벤트는 시간순으로 누적 적용한다.
  - 같은 축을 두 번 적용하면 두 번째 경계 이후 면 할당이 원래대로 돌아온다.
  - 중간 이벤트를 OFF로 바꾸면 원래 면 할당에서 누적 상태를 다시 계산한다.
  - v2 열 교환 파일은 기존 의미로 읽는다. 새 면 보정과 혼합하지 않으며 새 검토에는 원본이 필요하다.
- 원본 CSV는 수정하지 않는다. `Save Corrected Source...`가 별도 corrected CSV를 원자적으로 저장한 뒤 성공한 경우에만 그 파일을 활성 입력으로 전환한다.
  - 저장을 취소하거나 저장에 실패하면 활성 데이터와 기존 검토 상태는 바뀌지 않는다.
  - 검토 결정이 저장되지 않은 동안에는 `.slice` 저장을 막아, 화면의 판단과 실제 파일 입력이 어긋나지 않게 한다.
  - corrected CSV에는 원본 식별·해시·헤더 메타데이터, 박스 크기·원래 면 할당·좌표 정책, 전체 결정과 증거를 기록한다. 크기나 원본이 바뀌면 기존 승인을 재사용하지 않는다.
- `Save Scene Slice`는 현재 박스 크기, 슬라이스 범위, scene 이름을 사용해 `.slice` 파일을 저장한다.
- `.slice`는 기존 raw CSV 구조를 유지하지만, 상단 2줄에는 scene / box / timeline metadata를 추가한다.
- corrected CSV에서 만든 `.slice`는 실제 corrected 파일명을 source로 기록하고, 원본 식별 정보와 전체 marker-correction 결정 이력도 전달한다.
- v3 corrected CSV를 다시 열면 승인 당시 박스 크기를 복원한다. 면 변경 경계를 넘는 스무딩·미분·결과 보간은 분리하며 경계 미분값을 임의로 채우지 않는다.
- 저장 시 선택 구간 양옆에 `50 rows` padding을 포함한다.

### 2.4. 촬영 구간 자동 검출 (#75)

`Detect scenes`는 고정 마커 배치의 상대 운동으로 낙하 후보, 기울임·회전, 취급 후보, 자세 점프, 대기·추적 불가 구간을 찾는다. 별도 수동 관리 팝업은 사용하지 않는다. 기존 그래프 아래 목록에서 구간을 선택하면 `Slice Range`와 그래프 선택 범위가 정확한 초 단위 값으로 동기화된다. `Signal`에서 상대 회전, 수직 속도, 마커 수와 정합 잔차를 볼 수 있다. 상대 회전은 최초 유효 자세와의 각도이며 누적 회전수는 아니다.

1. CSV를 열고 필요하면 `Geometry...`로 독립적으로 측정한 마커-박스 등록 정보를 선택한다. 파일 형식과 물리 전제는 [외부 자료·해석](../../simulation_external_reference_notes.md)을 따른다.
2. `Detect scenes`를 실행하고 각 구간을 그래프와 함께 확인한다. 여러 행을 선택해 `Include` 또는 `Exclude`할 수 있다. 원인 분류와 시험에 포함할지는 별개다.
3. 기존 시작·끝 입력이나 그래프에서 범위를 수정한다. 수정한 행은 미검토로 돌아가고 항목 확정이 해제된다. 재검출은 수동 범위·삭제·제외를 유지하면서 변경 범위의 근거를 다시 계산한다.
4. 모든 행의 포함 여부를 정한 뒤 `Identify items` 또는 `Save included...`를 사용한다. 저장은 선택 폴더 안의 새 하위 폴더에 포함한 `.slice`만 만든다. 개별 저장도 같은 검토 조건을 따른다. 자동 검출을 사용하지 않은 기존 수동 slice 저장은 유지한다.
5. Type과 실제 적용 판본은 시험 기록에서 확인한다. 등록된 박스와 바닥이 있을 때 바닥 접근 자세를 2018-03 표와 대조한다. 중복 자세의 시험 번호를 자동으로 확정하지 않는다. H 후보는 B04/B16 저중량 표의 조건부 후보이며 Type H 전체 항목 목록이 아니다. 판본·순서·적용 조건을 확인한 사용자만 `Confirm item`을 사용한다.
6. 의도한 접촉 부위를 알고 있다면 포함한 한 행에서 로컬 면·모서리·꼭짓점을 골라 `Set contact`를 누른다. 이 선택은 검출 후보와 독립적이며 Type·시험 번호·목표각도를 요구하지 않는다. 작업 파일과 결과 파일에 유지하고, 근거가 바뀌면 활성 선택을 해제한다. `Contact unspecified`로 선택을 지울 수 있다.

예를 들어 제공된 실측 파일은 약 1.6–3.1초의 90도 회전 후보를 보여준다. 이것만으로 로봇 회전인지 기울임 시험인지, Type G/H나 시험 번호가 무엇인지는 확정하지 않는다. 독립 박스 등록이 없는 입력에서는 COM 자유낙하·접촉 면을 확정하지 않는다. 가상 예제는 같은 자세의 두 낙하를 각각 찾고 취급과 대기를 남긴다. 실제 시험 정답에 대한 정확도는 아직 검증되지 않았다.

새 `.slice`의 검토 이력은 Step 1.5의 처리와 `.proc` 재열기에도 전달된다. 파일 하나는 선택한 구간의 근거와 전체 포함·제외 결정 목록을 보존한다. 시험 기록 기반 순서 추론, G16/G17 조건 및 H 지지·회전 시험의 완전한 항목 식별은 아직 제공하지 않는다.

승인된 v3 면 보정은 `Detect scenes`에도 적용한다. 등록된 마커 좌표에 전체 누적 승인 이력을 반영하므로, 보정 파일을 저장한 직후와 다시 연 뒤의 박스 면·코너 의미가 같다. 잘린 파일보다 앞선 승인도 적용하며, OFF인 이벤트나 실제 회전을 임의로 보정하지 않는다. 등록 없는 입력은 승인 상태가 바뀔 때 상대 운동의 기준을 나누고 그래프와 미분을 경계 너머로 연결하지 않는다. 기존 보정 파일의 작업을 열 때 계산 의미가 바뀐 구간은 이전 선택을 보존한 채 재검토한다. 등록·보정 맥락이 맞지 않으면 검출을 중단하고 활성 작업을 유지한다.

2026-09-13에는 공개 MuJoCo 32마커·300×180×90 mm 입력의 0.520초 X 승인으로 확인했다. 기존 검출의 승인 이후 180도 자세·C1 201.246118 mm 오류가 사라졌다. 실제 MainApp의 corrected 저장 직후와 별도 프로세스의 작업 재열기 모두 100표본을 복원했고, 정답 대비 최대 자세 오차는 3.45e-13도, 코너 오차는 6.57e-13 mm 이하였다. 선택한 프레임 60–71의 `.slice`에는 padding 포함 90행을 저장했다. Raw 모드가 선택한 12행을 처리했고, `.proc` 재열기에서도 정확한 시간 0.4800000000000003–0.5680000000000004초, 승인 이력과 미확정 항목이 유지됐다. 새 처리 결과의 최대 위치·회전·코너 오차는 각각 0.0000602 mm·0.0000500도·0.0001685 mm 이하였다. 원본과 별도 정답 파일은 변하지 않았다.

이 실행은 Qt 조작과 파일 경로 주입을 사용했다. 변경 없는 corrected 파일은 저장 버튼이 비활성이므로, 저장 직후 메모리 경로만 실제 저장 handler를 직접 호출해 확인했다. 버튼을 사용자가 눌렀다는 검증으로 보고하지 않는다. 화면은 Step 1의 선택 구간·미확정 상태와 Step 2의 C1 곡선·12표본·새 충격 없음 표시를 확인했다. 선택 구간에는 기존 접촉이 계속되며 보정 경계가 새 충격으로 바뀌지 않았다. 근거는 `tmp/issue75_corrected_scene_20260912/run_01/phase_1`과 `phase_2`에 있다. 이 전체 처리 후 추가한 미등록 경계 분리와 구버전 refresh 수정은 해당 반례로 따로 확인했고, 등록된 정상 optimizer를 반복하지 않았다. 가상 수치·저장 일관성 확인이고 실측 정확도나 ISTA 적합성 검증은 아니다.

| 보정 연결의 독립 리뷰 지적 | 수정 및 재검토 |
| --- | --- |
| 미등록 중력 운동의 양쪽 `unclear`가 승인 경계를 넘어 합쳐져 서로 다른 상대 기준을 요약 | 마지막 후보 생성도 경계에서 나눈다. 실제 0.520초 승인 반례가 0–0.512초와 0.520–0.792초로 분리되고 각 회전·변위가 독립 계산과 일치했다. |
| X→X 뒤 원래 상태로 돌아온 구간의 구버전 `refresh`가 과거 기하 근거와 Include를 유지 | 계산 버전 변경 시 모든 행을 재계산하고 이전 선택을 보존해 재검토한다. 0.80–0.95초의 기하·활동 근거가 새 결과와 같아졌다. 작업 파일 재열기는 기존의 행별 근거 비교를 유지하므로, 승인 전 구간도 연결된 활동 범위가 달라졌다면 재검토될 수 있다. |

검토를 중단할 때는 `Save review...`로 `.scene-review.json`을 저장한다. 미검토 행이 있어도 범위 수정·추가·삭제, 포함 여부, 시험 맥락과 선택한 행·신호를 보존한다. 새 실행의 `Open review...`는 참조 CSV를 읽고 근거를 다시 계산한 뒤 작업을 복원한다. CSV가 이동했으면 같은 내용의 파일을 지정할 수 있다. 보정 CSV로 검토했다면 그 파일을 참조한다. 재계산 결과나 설정·등록·검출 버전이 달라진 행은 이전 선택을 남기고 `Review again`으로 표시한다. 다시 포함 여부를 정하기 전에는 결과 slice를 저장할 수 없다. 작업 파일은 촬영 데이터 사본을 포함하지 않으며, 촬영 내용 불일치나 열기 취소 시 현재 작업을 유지한다.

2026-09-12에는 서로 다른 MainApp 실행에서 미완료 9행을 저장·복원했다. 0.4–2.0초 기울임의 77.645714 mm, 수동 범위·삭제·검토 상태·신호가 유지됐다. 검토를 마친 뒤 새 slice를 Step 1.5에서 열어 패딩 포함 301행과 선택 범위 201행, 동일한 측정 JSON을 확인했다. 활성 보정 CSV의 별도 경로·해시도 복원했다(이 경로 확인용 보정 파일에는 수정 이벤트가 없다). 저장값을 999 mm로 바꾼 경우에는 관측값을 다시 계산하고 이전 Include를 남긴 채 재검토로 전환했다. 가상 자료의 저장 일관성 확인이며 실측 정확도 검증은 아니다.

독립 코드·물리 리뷰에서 아래 지적을 수정하고 해당 입력으로 재확인했다.

| 지적 입력과 문제 | 수정 및 재확인 결과 |
| --- | --- |
| 바닥을 0 → 2 mm로 등록하고 재검출 전에 저장하면 이전 값 저장 | 현재 등록을 저장한다. 재열기 시 2 mm와 바닥 관통 상태, 이전 Include 및 미검토 상태가 유지된다. |
| Position-Y의 Marker B1 선택이 사라져 빈 그래프로 복원 | 표시 대상도 저장해 같은 B1_Y 곡선을 복원한다. |
| 편집한 ID `part 1`과 `part_1`이 같은 slice 파일명으로 변환 | 생성 가능한 구간 ID 형식만 읽어 충돌 입력을 내보내기 전에 거부한다. |
| 미확정 항목의 참고 판본을 바꿔도 현재 후보와 함께 복원 | 계산 출처 판본도 비교해 옛값을 별도 보존하고 현재 근거로 재검토한다. |

Step 1에는 파일 로드·구간 선택에 필요한 원본 위치와 상대 운동 신호, 검출 목록을 표시한다. 목록 아래의 모서리·높이·단계 요약과 `Least-moving edge travel (mm)`, `Opposite edge height (mm)` 선택지는 제거했다. 기존 작업에 두 신호가 저장돼 있으면 `Relative rotation (deg)`로 열며, 원본 Position-Y와 마커 선택은 그대로 복원한다. 높이와 고정 모서리 근거는 자동 구간 연결과 저장 이력에 계속 사용하며 별도로 입력하거나 알아야 하는 값이 아니다.

2026-09-13 실제 MainApp에서는 공개 왕복 입력 351행으로 기존 두 신호의 대체 선택을 확인했다. Position-Y의 `Marker B1`은 파싱된 시간·값 전체와 정확히 일치했고, 행 선택으로 0.432–1.168초에서 0.432–2.368초로 범위가 바뀌었다. 미검토 수동 행만 Exclude로 바꿔 저장한 뒤 별도 빈 MainApp에서 열어 결정·삭제 이력·등록·내부 기하·버전·마커와 범위를 보존했다. 전체 행 삭제 뒤에는 원본 곡선을 유지하고 선택 영역을 숨기며 두 slice 저장 버튼을 비활성화했다. 선택 범위와 곡선이 함께 보이는 최종 화면도 확인했다.

독립 리뷰에서 Position 재그리기 뒤 선택 영역이 축에서 분리되는 문제, 선택 해제 뒤에도 실제 표시가 남는 문제, Item에서 등록 필요 이유가 사라지는 문제를 재현하고 수정·재확인했다. 수동 CSV 범위도 보존한다. Item에는 등록 필요·바닥 접근 미확인·접근 부위 불명확 이유만 짧게 표시한다. 실행 근거는 로컬 `tmp/issue75_step1_cleanup_20260913/completed_ui_audit.json`에 있다. 최초 하네스의 잘못된 마커 표시명과 서로 다른 CSV 파서의 부동소수점 비트 비교 실패는 보존했으며, 기대값이나 물리 허용 오차를 바꾸지 않았다. 표시 보존은 실제 파싱 배열과 직접 대조했다. 이번 작업은 UI·저장 검증으로, Raw 처리나 실측 정확도 검증을 반복하지 않았다.

이 측정의 시작은 관측 범위의 첫 자세다. 새 검출은 같은 유효 추적 블록의 상승·중간 대기·하강을 전체 범위에서 다시 확인한다. 같은 모서리가 유일하게 고정되고, 반대 높이가 분명히 상승한 뒤 하강하며 모든 코너가 시작 자세로 복귀할 때 하나의 미검토 운동 후보로 묶는다. 이미 복귀한 동작 뒤의 반복은 추가하지 않는다. 한 원본 활동 안의 여러 복귀는 복귀 수를 내부 근거에 보존하며 한 시험으로 해석하지 않는다. 높은 고정 모서리도 같은 기하 분석이 가능하지만 해제·지지력·H 항목 번호는 확정하지 않는다.

기존 `Slice Range` 수정과 검토 결정은 유지한다. 화면에 묶어 표시하기 전의 원본 활동 범위도 보존하므로, 예전에 상승 구간만 골랐던 작업을 재열어도 그 범위를 전체 사이클에 맞춰 확장하거나 촬영 잘림으로 바꾸지 않는다. 수동 범위의 내부 근거도 해당 표본으로만 계산한다. 값과 단계는 검토 JSON에 보존되며 범위·등록·치수가 바뀌면 무효화된다. 검출 버전이나 재계산 근거가 바뀐 기존 작업은 앞서 설명한 `Review again` 규칙을 따른다. 표시 정리 자체는 검출 버전이나 계산값을 바꾸지 않는다.

자동 연결은 300×180×90 mm 공개 박스·32마커·0.008초 간격의 처방 궤적으로 확인했다. 정답과 삽입 기록은 관측 CSV·등록 파일과 분리했다. 한 왕복의 기존 상승 0.432–1.168초와 하강 1.632–2.368초가 0.432–2.368초의 한 미검토 후보가 됐고 최대 높이는 77.645714 mm였다. 피벗을 100 mm 올린 입력은 177.645714 mm, 반복 입력은 두 구간을 냈다. 중심 회전·끌기·이동 피벗·누락·부분 촬영·미복귀는 완전 왕복으로 연결하지 않았다. 이는 처방 운동의 검증이며 MuJoCo 동역학이나 실측 정확도 검증이 아니다.

같은 코드의 실제 MainApp에서 미완료 작업을 새 프로세스로 열고 재검출해 수동 상승 범위·삭제·포함 결정을 유지했다. 포함한 한 왕복을 Raw 처리하고 Step 2에서 다시 열어 243행, 원본 시간 0.432–2.368초, 단계·높이·미확정 시험 정보의 동일성을 확인했다. 이 정상 처리 실행 뒤 추가된 느린 운동·성능 검사는 해당 반례로 따로 확인했다. 최종 코드로 이전 작업을 열면 새 `steady_extent_policy` 설정을 근거 변경으로 감지해 이전 Include를 보존하고 재검토로 전환한다. 수치·단계·범위는 동일했다. 독립 리뷰는 실제 코드와 `.slice`·`.proc`를 각각 읽었다.

| 독립 리뷰 지적 | 수정 후 같은 입력의 결과 |
| --- | --- |
| 16초의 느린 상승에 ±0.02° 요동이 있으면 유지로 표시 | 연속 유지 구간 전체의 코너 이동도 검사해 미정으로 보류. 실제 30.5211 mm 이동값은 유지한다. |
| 느린 5° 왕복의 기하 근거와 대기 표시가 불일치 | 한 번·두 번 복귀 모두 회전으로 표시하고 원본 활동·범위·ID는 보존한다. |
| 등록이 없거나 미복귀 활동이 길게 이어지면 불필요한 전체 분석 반복 | 등록 없는 입력은 즉시 원본 활동 반환. 8회 계단 상승은 끝점 필요조건 선검사로 전체 분석 64 → 16회, 독립 실행 약 2.10 → 0.06초. 전체 알고리즘이 선형이라는 보장은 아니다. |

2026-09-12의 표시 정리 전 창에서는 단계 그래프와 느린 5° 왕복의 회전 표시·26.146723 mm·복귀를 확인했다. 125% 배율에서 창 테두리 포함 1887.5×1076.25 px로 1920×1080 안에 들어갔다. 당시 실행 전후 코드 해시는 같았다. 원본 활동은 느린 왕복을 대기로 분류했던 상태 그대로 별도 보존한다. 현재 화면에서는 그 높이·단계 상세를 표시하지 않는다.

재현 검사는 `test_support_cycles.py`와 `test_support_cycle_workflow.py`에 있다. 작업별 입력·실행·화면 근거는 로컬 `tmp/issue75_support_cycles_20260912/audit.json`에 기록했다. 전체 처리와 최종 수정의 좁은 재검증을 구분하며 공개 PR에는 수치·절차를 남긴다.

지지 회전 추가 실행에서는 공개 관측 파일의 0.4–2.0초를 선택해 C1–C5 피벗과 높이 0 → 77.645714 → 0 mm를 확인했다. 중심 회전 3.2–4.8초는 양끝 이동이 0이어도 중간에 최소 모서리 이동 142.302495 mm가 나타나 고정 모서리를 인정하지 않았다. 실제 `.slice`의 패딩 포함 301행을 Raw 처리한 뒤 `.proc`를 Step 2에서 재열어 선택한 201행, 프레임 50–250, 시간 0.4–2.0초와 측정 JSON·미확정 항목이 유지됨을 확인했다. 구간 전체 삭제 뒤 남던 곡선도 리뷰 지적에 따라 수정하고 실제 창에서 비워짐을 확인했다.

추가 물리 리뷰에서 찾은 45도 부근의 시작면 모호성은 별도 실제 Step 1 입력으로 확인했다. 당시 피벗 후보와 이동 신호는 유지하고 높이 수치·곡선은 보류했으며, 수치 오차를 과장하지 않는 축 범위도 확인했다. 표시를 제거한 뒤에도 이 내부 모호성 처리와 측정값은 유지한다. 앞의 전체 처리 저장물은 모호성 필드 추가 전 결과이며, 새 필드 보존은 별도 실제 CSV 기반 `.slice` 저장·재열기 검사에서 확인했다.

2026-09-12 실행 확인은 실제 `MainApp`을 연 Qt 통합 실행으로 수행했다. 실측 `VDTest_S5_001.csv`에서는 대기, 1.620833–3.1초의 회전, 대기, 마지막 추적 불가 구간을 구별했다. 시험 기록이 없으므로 ISTA 항목 정답으로 평가하지 않았다. 독립 MuJoCo 관측 파일에서는 두 낙하를 포함하고 나머지를 제외해 `.slice` 두 개를 저장했다. 첫 파일을 Step 1.5에서 Raw 처리해 134개 padding 포함 입력 행으로부터 34개 선택 구간 결과를 만들고, Step 2에서 위치·회전을 그렸다. 재열기 후 원본 프레임 198–231, 시간 1.584–1.848초와 검토 JSON이 보존됐으며 반복 자세의 H 항목 두 후보는 미확정 상태를 유지했다.

코드·물리 담당은 실제 소스와 저장 파일을 각각 읽어 재검토했다. 범위 수정 뒤 남던 낙하·부분 촬영 근거, COM 전제, 잘못된 자세의 코너 값, 왕복 회전 누락, 작업 중 버튼 상태, 긴 파일명 저장 및 취소 응답 지적을 수정했다. 위치·회전의 합성 정답 대조는 수치·저장 일관성 확인이며 실측 정확도가 아니다. 125% 배율의 실제 Qt 창에서 목록·파일명·출력 버튼 접근과 화면 크기를 확인했다. Windows 외부 마우스 도구는 창 활성화 오류로 조작하지 못했으므로 네이티브 마우스 검증으로 보고하지 않는다.

## 3. Step 1.5: Slice Processing
`WidgetSliceProcessing`이 담당한다.

### 3.1. 상단 레이아웃
- 좌측: Matplotlib 그래프와 네비게이션 툴바
  - `.slice`를 다시 파싱한 `parsed_data`를 기준으로 preview를 그린다.
- 우측: 제어 패널
  - `Load Slice File...`
  - 선택된 `.slice` 경로 표시
  - `Slice Summary`
    - source
    - user range
    - padded range
    - marker correction 검토 이벤트 수 / 승인 이벤트 수
  - `Box Dimensions (mm)`
    - `.slice` 메타에 저장된 box 치수를 읽어 자동으로 채운다
    - 기본적으로 입력은 비활성화한다
    - `.slice` 메타에 box 치수가 없으면 경고를 띄우고, 단일 처리에 한해 임시 수동 입력과 `.slice` 메타 저장 옵션을 제공한다
  - 로그 출력 텍스트 영역

### 3.2. 하단 컨트롤
- `Plot Options`
  - Step 1과 같은 preview 선택 구조를 유지한다
- `Result Resampling`
  - processing 완료 후 최종 결과 컬럼을 시간축에서 보간할지 결정한다
  - `Limit to Time Range`를 켜면 지정한 Start/End 시간 구간에만 중간 result row를 추가한다
  - 기존 timestamp row의 결과값은 보존하고, 새 중간 timestamp row만 `.proc` 결과에 삽입한다
- `Processing Mode`
  - Raw / Smoothing / Advanced
  - `Advanced Settings...` 다이얼로그 재사용
  - Advanced 설정에는 낙하 자세 post-processing의 접촉 높이 허용값(`Contact threshold (mm)`)도 포함된다
- `Processing Output`
  - 현재 처리 상태
  - 최근 저장된 `.proc` 경로
- 실행 버튼
  - `Run Processing`
  - `Save Processed Result`

### 3.3. 주요 동작
- `.slice`를 열면 `DataLoader.load_csv()`와 `Parser.process()`를 다시 사용해 parsed slice를 준비한다.
- processing은 `PipelineController.run_analysis_from_parsed()`를 통해 실행한다.
- batch processing은 각 `.slice` 파일의 box 치수를 파일별 메타에서 읽어 사용하며, box 치수가 없는 파일은 해당 파일만 실패 처리한다.
- processing과 Result Resampling이 끝난 뒤 `DropPosturePostProcessor`가 낙하 자세 비교용 지표를 계산한다.
  - 접촉 판정은 높이 threshold, 하강/저점/반전, 낮은 plateau, 접촉 corner set 지속성을 함께 보는 evidence 기반 summary로 계산한다.
  - 접촉 상태는 `NoContact`, `Approach`, `ImpactEvent`, `SustainedContact`로 요약한다.
  - 기준면은 `t1-`가 있으면 그 frame에서, 없으면 slice 첫 valid frame에서 아래 방향을 가장 많이 향한 박스 면으로 자동 추정한다.
  - `t1-`는 `ImpactEvent`가 확인될 때만 정의한다.
- 완료된 결과는 Step 1.5 내부에서 확인한 뒤 `.proc`로 저장한다.

## 4. Step 2: Results Analysis
`WidgetResultsAnalyzer`가 담당한다.

### 4.1. Time Window 영역
- Active File
- Number of Samples
- Full timeline / Slice timeline 정보 문자열
- Slice 구간을 시각적으로 보여주는 막대형 타임라인

### 4.2. 본문 상단 3분할 레이아웃
- `1. Result Files`
  - `Select Result Folder...`
  - 읽기 전용 Folder Path
  - 결과 `.proc` 목록
- `2. Data Selection`
  - `Group By` (`Metric / Object`)
  - `Search`
  - 결과 컬럼 트리 (`QTreeWidget`)
  - 내부 선택값은 `(L1, L2, L3)` tuple을 유지하지만, 사용자에게는 `Velocity X (Box Local Frame)` 같은 표시명을 노출
  - `Group By`는 동일한 결과 컬럼 집합을 `Metric -> Object -> Component` 또는 `Object -> Metric -> Component` 기준으로 다시 묶어 보여준다.
  - `Search`는 현재 트리를 평면 리스트로 바꾸지 않고, 일치한 leaf와 그 부모 경로만 남기는 필터로 동작한다.
  - 체크 상태는 `Group By` 전환이나 `Search` 필터와 무관하게 유지된다.
  - 트리 아래 안내 라벨이 raw export key 대신 표시명이 보인다는 점을 예시와 함께 설명
  - `Clear Selection`
  - `Plot Selected Results`
  - `Open Popup (Current Selection)`
  - `Close All Popups`
  - Opened Popups / Checked Columns 상태 표시
- `3. Drop/Impact Summary`
  - 선택된 `.proc`의 Drop Posture summary를 grouped key-value table로 표시한다.
  - 표시 순서는 `Posture -> Impact -> Contact`이다.
  - `Posture`에는 `Beta at t1-`, 방향 각도, `Cmin`, `DeltaH`, 기준면을 표시한다.
  - `Impact`에는 `t1-`, 첫 충격 시각, 첫 접촉 코너, `ImpactSequence`를 표시한다.
  - `Contact`에는 contact state, impact/sustained contact 여부, confidence, detection method를 낮은 우선순위로 표시한다.
  - `T1Detected=False`이면 t1 기반 값은 `N/A`로 표시한다.
  - Summary row tooltip과 `Metric Guide...` 설명창은 `src/config/result_metric_descriptors.py`의 descriptor metadata를 참조한다.
  - `Metric Guide...` 버튼은 summary table 아래 푸터에 배치한다.
  - Metric Guide 다이얼로그는 Posture / Impact / Contact 3개 그룹 단위 일러스트레이션과 해당 지표 설명을 표시한다.
  - `SustainedContact` 상태는 UI에서 `Stable floor contact`로 표시한다.

### 4.3. 하단 분석 패널
- `3. Peak & Point Selection`
  - `Target`
  - 현재 Target 기준으로 peak search가 동작한다는 안내 라벨
  - `Find: Abs Max / Max / Min`
  - `Selected Point`
  - `Export Point Data...`
- `4. Export Analysis Input`
  - `Manual Offset`
  - `Manual Height`
  - `Offset0~2`
  - `Run Time`
  - `Step`
  - `Scene Name`
  - `Export Scenario CSV`

### 4.4. 하단 메인 플롯
- 현재 체크된 결과 컬럼을 한 그래프에 겹쳐서 표시한다.
- 범례와 타겟 선택 문자열은 raw schema key를 직접 이어붙이지 않고, export 의미를 풀어쓴 표시명을 사용한다.
- 현재 체크된 컬럼 집합은 트리 정렬 방식과 검색 필터가 바뀌어도 유지된다.
- 그래프 클릭 시 가장 가까운 시점을 선택한다.
- 선택된 시점은 붉은 수직선 커서와 선택 정보 레이블로 반영된다.

### 4.5. 팝업 플롯
- `PlotPopupDialog`는 현재 체크된 컬럼 집합으로 별도 창을 연다.
- 팝업 그래프도 클릭 가능하며, 선택된 시간이 메인 Step 2와 동기화된다.
- 현재 구현은 "현재 선택 항목으로 팝업 열기"만 지원하며, 별도 subset 편집 버튼은 노출하지 않는다.

## 5. 현재 사용자 흐름
1. Step 1에서 원본 CSV 또는 기존 corrected CSV를 로드한다.
2. 필요한 경우 `Review Candidates...`에서 이벤트별 증거를 확인하고 Apply/축을 결정한다.
3. 검토 상태가 바뀌었다면 별도 corrected CSV를 저장해 활성 입력으로 전환한다.
4. 필요한 데이터와 축, 슬라이스 범위를 조정한다.
5. 활성 입력에서 `.slice`를 저장한다.
6. Step 1.5에서 저장한 `.slice`를 연다.
7. 필요하면 Result Resampling factor와 processing mode를 조정한다.
8. processing을 실행한다.
9. `.proc`를 저장한다.
10. Step 2에서 결과 폴더를 선택하고 저장된 `.proc`를 목록에서 연다.
11. Step 2에서 컬럼을 체크하고 메인 플롯 또는 팝업 플롯으로 비교한다.
12. 특정 시점을 선택하거나 최대값을 찾아 point export 또는 scenario export를 수행한다.

낙하 자세 비교 지표 확인:
- Step 1.5 processing 후 저장한 `.proc`에는 `Analysis / DropPosture` frame metric과 `Analysis / DropPostureSummary` summary metric이 포함된다.
- Step 2에서는 frame metric을 컬럼 트리에서 선택해 시간 이력으로 확인할 수 있고, summary metric은 `Experiment Summary` 영역에서 확인한다.
- 접촉이 없는 구간도 frame별 낙하 자세 metric과 max summary는 계산되며, `t1-` 의미가 필요한 summary만 비어 있을 수 있다.

참고:
- legacy 결과 `.csv`가 필요하면 파일 확장자를 `.proc`로 바꾼 뒤 연다.

## 6. Compare Results (비교 윈도우)
런처에서 독립적으로 실행되는 여러 실험 결과(`.proc`)의 비교 분석 전용 윈도우이다. 
`gui_principles.md`의 새로운 '입체적 카드 레이아웃 (회색 바탕 + 하얀 카드)' 원칙과 '작업 흐름을 명시하는 넘버링' 원칙에 따라 레이아웃이 구성되어 있다.

### 6.1. 좌측 사이드바 (Left Rail / Control Panel)
독립된 컨트롤 박스로 구성되며 최소 너비가 고정되어 있다.
- **1. Result Files:** 분석할 `.proc` 파일들을 로드하고 관리하며, 기준(Reference) 파일을 선택한다.
- 각 파일의 source class와 호환성 상태를 표시한다. 파일을 선택하면 누락·불일치한 모든 필드와 시간 제외 사유를 읽을 수 있다. 출처 불명 파일의 모델/배치/ISTA 타입은 추정하지 않는다.
- 출처 불명/유효하지 않은 source class는 시간과 t1이 있어도 공통 동기화에서 제외한다. 개별 시간 그래프와 샘플 탐색은 유지한다. 기준 차이의 호환성에는 실제 실행한 필터·미분·재표본화·접촉 설정의 식별값도 포함한다.
- Graph view에서 aligned overlay 또는 개별 파일을 선택한다. gap 제한은 초 단위 표시 정책(초기 0.1 s)이며 물리 오차 기준이 아니다.

### 6.2. 우측 메인 영역 (Main View Area)
탭(Tab) 없이 수직 스플리터(Vertical Splitter)를 통해 크게 3단으로 분할 배치된다.
1. **2. Experiment Summary (비교 요약 표):** 
   - `Pre-contact`에서 수직 속도·수평 속력·각속력과 조건부 등가높이를 확인한다. 값이 없으면 이유를 tooltip에서 읽는다.
   - `Repeats`는 호환되는 서로 다른 관측의 지표별 n·평균·범위와 접촉 진단 빈도를 표시한다. 복사본·같은 원본의 보정본을 중복으로 세지 않고 n<3은 부족 표시한다.
   - `Diagnostics`는 기존 개별 summary와 호환 파일의 기준 대비 차이를 유지한다. 자세·속도 값은 실측 정확도가 확인되지 않은 추정값이다. 적용 조건과 남은 기능은 `drop_result_comparison_plan.md`의 #77 항목을 따른다.
   - `Contact`는 Step 1에서 별도 지정한 의도와 추정 첫 접촉을 `Match`/`Different`/`Unclear`로 비교한다. 면 의도와 그 면의 모서리 접촉도 서로 다른 형상이다. `Local n`은 같은 출처·형상·처리·등록 및 의도의 관측 집계이며 Type·시험 번호가 없어도 가능하다. 바닥 관통·재표본화·불확실한 사건은 억지로 판정하지 않으며 이유는 tooltip에 표시한다.
2. **3D Animation (동기화 3D 뷰어):** 
   - `t - t1_minus` 공통 시계에서 가장 가까운 실제 샘플을 표시한다. 실제 선택 샘플 시각도 함께 표시하며, 파일 범위 밖이나 긴 gap 내부는 3D unavailable로 표시한다. Sync를 끄면 개별 샘플 탐색과 유효한 시간의 개별 재생을 사용할 수 있다.
3. **Time-History (시계열 비교 플롯):**
   - 실제 시간과 유효한 t1이 있는 파일은 elapsed 축에 겹쳐 보며 3D의 공통 커서를 공유한다. 다른 source class의 겹쳐 보기는 파일별 출처와 조건부 지속 경고를 표시하며 시각 검토로만 제공한다. 개별 보기의 시간이 없으면 `Sample row (time unavailable)`로 명시한다.
   - 툴바는 세로 방향으로 우측에 배치하여 가로 공간 활용도를 높였다.

The v3 loader and corrected/slice writers reject persisted analysis faces that disagree with the complete approved history and original face map. Valid suffix slices retain the cumulative effect of earlier events. Pose processing reports `UnknownFace` or `UnidentifiableGeometry` when face constraints cannot support the local six-DOF fit; unavailable pose/corners do not become detector evidence. This is a conservative local guard, not global uniqueness certification.
