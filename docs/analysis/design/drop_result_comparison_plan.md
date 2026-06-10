# Drop Result Comparison Plan

Last Reviewed: 2026-06-10

## 1. 목적
여러 낙하 실험 결과 `.proc`를 같은 기준으로 비교해, 반복 실험 간 자세 편차와 충격 경로 차이를 설명할 수 있게 한다.

현재 구현 범위는 단일 실험 결과에 Drop Posture frame/summary metric과 충격 시퀀스 summary를 저장하고, Step 2 Results Analysis의 `Experiment Summary`에서 확인하는 것까지다. 비교 전용 윈도우는 후속 작업으로 남긴다.

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

## 3. 후속 작업 계획
1. 비교 전용 윈도우 (Compare Results)
   - 런처에서 Results Analysis와 별도의 독립 창으로 연다.
   - 여러 `.proc` 파일을 선택하고 기준 실험을 지정한다.
   - (개선된 방향) 탭(Tab) 방식을 배제하고, 좌측 설정 사이드바와 우측 3단 뷰어(요약표, 3D 뷰어, 비교 플롯)를 한 화면에 동시 노출하는 견고한 직각 레이아웃을 사용한다.
2. 비교 지표 테이블
   - `ContactState`, `ContactConfidence`, `BetaAtT1MinusDeg`, 방향 각도, `DeltaH`, `Cmin`, 기준면, `ImpactSequence`를 기준 실험 대비 차이와 함께 표시한다.
   - `t1-`가 없는 실험은 t1 기반 값 대신 frame metric과 max summary를 중심으로 비교한다.
3. 비교 그래프
   - 선택한 metric을 시간축에 겹쳐 표시한다.
   - 원시 시간과 1차 충격 기준 정렬 시간을 전환할 수 있게 한다.
4. 3D 비교 재생
   - 선택 실험 단일 재생과 기준/비교 좌우 재생을 제공한다.
   - 동시 재생은 `t1` 또는 `t1-` 기준으로 정렬한다.

## 4. 검증 방향
- 단순 컬럼 존재 테스트가 아니라, 물리적으로 예상 가능한 synthetic 자세에서 각도와 코너 높이 차이가 수치적으로 맞는지 검증한다.
- 실제 raw data slice에서 접촉 없음, impact event, 낮은 plateau 상태를 나눠 검증한다.
- 기존 flow test 예제 `TestSets/Input/VDTest_S5_001.csv`의 `TestBox_85` 데이터를 85인치 실제 예제로 사용한다.
- 85인치 치수는 repo에 명시 값이 있으면 그 값을 우선 사용하고, 없으면 실제 데이터 안정 구간에서 추정한 `(2082.9, 1046.6, 254.4)` mm를 테스트 fixture로 사용한다.
- `TestBox_85` 접촉 검증은 바닥 접촉 slice `2.45s-3.05s`를 잘라 pipeline 처리, export, DataHandler reload, DataLoader reload까지 수행한다.
- 실제 데이터 검증은 결과 컬럼을 그대로 신뢰하지 않고, 코너 좌표와 회전벡터에서 각도/높이/접촉 근거를 독립 재계산해 비교한다.
- 비교 기능은 동일 실험을 두 번 로드했을 때 차이가 0에 가까운지, 의도적으로 기울인 synthetic 결과의 차이가 입력 각도와 일치하는지 확인한다.
