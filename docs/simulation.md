# 박스 낙하 시뮬레이션 문서

Last Reviewed: 2026-09-12

현재 simulation은 WIP이다. #74용 별도 생성기 `src/simulation/marker_fixtures.py`는 실제 `data.time`, 갱신된 body origin/COM/회전을 기록하고 정상 정답과 고장 관측을 분리한다. 기존 GUI의 `data_exporter.py`도 실제 시각·회전을 비파괴적으로 저장하도록 보완했다. 이 직접 `.proc` 출력은 분석 solver를 실행한 결과가 아니며 #74의 독립 관측/정답 경로를 대체하지 않는다. 명세와 실행 방법은 [독립 fixture 계약](analysis/reference/marker_flip_fixture_contract.md), 검증 결과와 한계는 [조사 결과](analysis/reference/marker_flip_review_findings.md)를 따른다. 아래 물리 결과 설명은 실제 실험 정확도 보장이 아니다.

본 문서는 MuJoCo 엔진을 활용하여 박스 낙하 실험을 시뮬레이션하고 데이터를 생성하는 기능에 대한 공식 문서입니다.

## 1. 개요 (Overview)
기존의 박스 낙하 실험 분석 프로그램은 실제 모션 캡처 시스템(OptiTrack 등)에서 추출된 `.csv` 또는 가공된 `.proc` 데이터를 기반으로 동작합니다.
하지만 실제 실험 환경 구축이나 반복적인 물리적 낙하 테스트는 높은 비용과 시간이 소모됩니다.
이를 해결하기 위해, 오픈소스 물리 엔진인 **MuJoCo**를 활용하여 박스 모델링, 중력, 충돌, 반발력 등의 물리적 요소를 가상으로 구현하여, 실제 실험과 유사한 데이터를 소프트웨어적으로 생성할 수 있는 시뮬레이션 기능을 추가하였습니다.

기존 GUI는 `.proc`를 직접 내보낸다. #74 검증은 별도의 `observed.csv`를 실제 분석 파이프라인에 넣고, 독립적인 `truth_pose.csv`와 비교한다. 두 저장 경로의 완성도와 검증 범위를 구분해야 한다.

### 오류 구간을 지정한 관측 생성 (#82)

`python -m src.simulation.corruption_export --trajectory tmp/trajectory.json --spec tmp/faults.json --example 18 --seed 42 --output tmp/new_observation`은 독립 시간·자세 궤적에 지정한 가림, 정지, 재연결 점프, 노이즈, ID 교환과 강체 추정의 반회전을 적용한다. 기존 고정 예제 밖의 오류 구간을 재현할 때 사용한다. 입력 형식과 연산 순서는 [fixture 계약](analysis/reference/marker_flip_fixture_contract.md#general-observation-specification-82)에 있다.

출력 `observed.csv`는 물리 `Marker`와 추정 `Rigid Body Marker`를 분리하며 현재 Step 1은 후자만 분석한다. 따라서 물리 마커만 가리거나 ID를 바꾸면 현재 분석 입력은 그대로다. 강체 추정 채널의 오류는 별도로 지정해야 한다. 정답과 오류 지정은 별도 파일에 보존하고 분석기에 전달하지 않는다. 출력 경로가 이미 있으면 덮어쓰지 않는다. 새 GUI나 자동 보정 승인 기능을 추가한 것이 아니며 실제 OptiTrack 오류 분포를 재현했다고 해석하지 않는다.

Step 1에서 `observed.csv`를 열고 사용한 profile의 `box_dims_mm`를 `Box Dimensions`에 입력한다(18마커 예제는 200/120/80 mm). 현재 raw CSV 열기는 이 치수를 자동 반영하지 않는다. 예를 들어 물리 F1을 가린 뒤 B1과 ID를 바꾼 입력에서도 Step 1의 F1/B1 그래프는 solved 채널을 표시하므로 물리 채널의 빈 구간이 나타나지 않는다. 실제 물리 가림을 보고 싶다면 별도 `Marker` 열을 확인해야 한다.

### 연속 촬영 예제 (#75)

`python -m src.simulation.scene_fixtures --case drops --output tmp/scene_recording`은 공개 300×180×90 mm 박스와 32개 마커로 연속 입력을 만든다. 분석 입력은 `observed.csv`, 선택적 정적 등록은 `registration.json`이다. `truth_pose.csv`, `truth_events.json`은 검출 후 평가용으로 분리한다. 입력에 시험 번호·운동 종류·오류 구간 정답을 넣지 않으며 검출기는 정답 파일을 열지 않는다.

| case | 삽입한 운동과 확인할 결과 |
| --- | --- |
| drops | 들어 올림·유지 뒤 1.6/4.4초에 같은 자세로 100 mm 해제. 실제 MuJoCo 낙하 둘과 반동·재접촉을 기록. 검출은 낙하 후보 둘과 별도 취급·대기 구간을 반환 |
| handling | 지지 모서리 기준 15도 기울임·복귀, 공중 90도 회전·복귀, 바닥 수평 이동. 자유낙하로 분류하지 않음 |
| tracking | 관측 마커 부분집합 변경, 누락, 정상 180도 회전, 별도 solver 반회전·위치 점프. 정상 회전과 불연속 후보를 구분 |
| partial | 첫 해제가 촬영 전이고 마지막 접촉이 촬영 후인 잘린 기록. 원래 frame/time을 유지하고 양 끝의 불완전한 낙하 표시 |

시간 간격은 실제 0.008초다. 낙하 단계는 질량 1 kg, COM 중심, 마찰 0.7, `solref=(0.02,0.5)`, 접촉 margin 0을 사용한다. 취급 단계는 지정한 운동이며 물리 장치나 ISTA 시험을 재현한 것이 아니다. 엔진의 첫 접촉은 해제 0.144초 후이며 약 6.16 mm의 연성 접촉 침투도 정답에 그대로 남긴다. 이를 숨기려고 허용오차를 바꾸지 않는다. 선택적 독립 좌표 잡음은 카메라 오차를 보정한 모델이 아니다. 이 예제의 성공은 실측 정확도나 ISTA 적합성을 입증하지 않는다.

## 2. 주요 기능 및 컴포넌트

### 2.1 MuJoCo 엔진 통합 (`src/simulation/engine/mujoco_engine.py`)
- **역할:** 강체 동역학(Rigid Body Dynamics) 시뮬레이션을 수행합니다.
- **기록:** `record_samples`는 초기 상태를 포함해 지정한 샘플 수를 저장한다. timestep 0.002 s, substeps 4의 실제 간격은 0.008 s이며, 120 FPS 요청이 정확히 실현된다고 간주하지 않는다. 기록 전 `mj_forward`를 호출하고 배열을 복사한다. `Center`는 기존 body-origin 별칭을 유지하며, `COM`, `RotationMatrix`, `QuaternionWXYZ`를 별도로 기록한다.
- **주요 설정 변수:**
  - `size`: 박스 로컬 X/Y/Z의 전체 길이 (mm 단위). 엔진이 MuJoCo geom의 half-extents로 변환한다.
  - `mass` (Mass): 박스의 무게 (kg).
  - `friction` (Friction): 바닥면과 박스 사이의 마찰 계수 (기본값: 0.5).
  - `elasticity`: 기존 이름을 유지하는 접촉 감쇠 제어값. `solref`의 시간상수는 0.02 s, 감쇠비는 `max(0.01, 1-value)`다. GUI 기본값은 0.15이며, 측정된 반발 계수가 아니다.
  - `com_offset` (Center of Mass Offset): 기하학적 중심과 실제 질량 중심 간의 차이 (TV, 세탁기 등 편향된 하중 모델링 시 유용).

### 2.2 표준 낙하 시나리오 (`src/simulation/scenarios.py`)
국제 포장 화물 테스트 규격(예: ISTA, ASTM 등)을 참고하여 다양한 낙하 자세(Orientation)를 쿼터니언(Quaternion) 형식으로 제공합니다.

현재 목록이 ISTA 절차를 재현한다고 검증된 것은 아니다. Type H의 지지·기울임·해제 동작은 구현되지 않았고, Type G 17번에는 hazard block 형상이 없다. 편심 COM을 넣은 박스의 표준 접촉 자세도 별도 검토가 필요하다. 아래 목록은 현재 제공하는 자세 기능을 설명한다.

- **면 낙하 (Face Drop):**
  - 바닥(Bottom), 상단(Top), 전면(Front), 후면(Back), 좌측면(Left), 우측면(Right)
- **모서리 낙하 (Corner Drop):**
  - 특정 꼭짓점이 바닥에 가장 먼저 닿도록 회전시킨 자세.
  - 예: `Corner_2-3-5 (Front-Bottom-Right)` 등 총 8개의 꼭짓점 시나리오 지원.
  - **검증 목표:** 충돌 후 텀블링과 반대편 모서리의 속도·가속도 변화를 재현한다. 실제 실험과의 일치는 별도 검증이 필요하다.
- **선 낙하 (Edge Drop):**
  - 모서리 선이 바닥과 평행하게 닿도록 회전.
  - 예: 전면-하단 선 (Front-Bottom Edge) 등.

> **중요:** 특히 Type G의 `Face / Edge / Corner` 자세는 규격이 `roll / pitch / yaw` 숫자를 직접 주는 형태가 아니라,  
> “어느 면/선/점이 먼저 충돌해야 하는가”를 정의하는 방식입니다.  
> 따라서 시뮬레이터는 박스 치수 `(Width, Height, Depth)`를 이용해 해당 접촉 자세를 만족하는 회전을 계산해야 합니다.
>
> 이 동작을 확인할 때 참고한 외부 URL은 아래와 같습니다.
> - ANSI storefront: https://webstore.ansi.org/standards/ansi/istaprojectamazonsioc2018
> - Public excerpt used for sequence / orientation cross-checks:
>   https://d39w7f4ix9f5s9.cloudfront.net/32/98/c52dd6b841f18bcb8af679b1f1ac/9.TESTING_thumbnail_ISTA%20Project%206-Amazon.com-SIOC%2018-18.pdf
>
> 관련 로컬 경로:
> - [simulation_external_reference_notes.md](/root/BoxMotionAnalyzer/docs/simulation_external_reference_notes.md)
> - [ISTA_6_AMAZON_SIOC_REFERENCE.md](/root/BoxMotionAnalyzer/docs/ISTA_6_AMAZON_SIOC_REFERENCE.md)
> - [scenarios.py](/root/BoxMotionAnalyzer/src/simulation/scenarios.py)
>
> 참고한 외부 URL:
> - ANSI storefront: https://webstore.ansi.org/standards/ansi/istaprojectamazonsioc2018
> - Public excerpt used for cross-checking: https://d39w7f4ix9f5s9.cloudfront.net/32/98/c52dd6b841f18bcb8af679b1f1ac/9.TESTING_thumbnail_ISTA%20Project%206-Amazon.com-SIOC%2018-18.pdf
>
> 관련 로컬 문서/코드 경로:
> - `/root/BoxMotionAnalyzer/docs/simulation_external_reference_notes.md`
> - `/root/BoxMotionAnalyzer/docs/ISTA_6_AMAZON_SIOC_REFERENCE.md`
> - `/root/BoxMotionAnalyzer/src/simulation/scenarios.py`

### 2.3 데이터 익스포터 (Digital Twin Data Pipeline) (`src/simulation/data_exporter.py`)
Exporter `simulation-pose-actual-time-v1`은 엔진의 기록을 변경하지 않고 `.proc`를 만든다. 같은 history를 같은 exporter 또는 새 exporter로 반복 저장한 무노이즈 결과는 동일하다.

- 실제 `time`은 초 단위이며 유한하고 엄격히 증가해야 한다. 빈 기록, 중복·역행·NaN·무한대 시각은 저장 전에 오류가 된다. 고정 1/120초로 대체하지 않는다.
- 저장은 목적 파일과 같은 디렉터리의 짧은 고유 임시 이름에 UTF-8 CSV를 완성하고 flush·fsync·close한 뒤 `os.replace`한다. 쓰기·디스크 반영·교체 실패는 기존 목적 파일의 bytes를 보존하며, 새 경로에는 불완전한 최종 파일을 남기지 않는다. 실패한 임시 파일을 정리하되 정리도 실패하면 원래 오류와 임시 경로를 함께 전달한다. 프로세스 강제 종료·전원 차단까지 복구하는 저널 기능은 아니다.
- 월드 벡터는 `A=[[1,0,0],[0,0,1],[0,-1,0]]`로 변환한다. 박스 로컬 축과 코너 정의는 유지하므로 `R_app=A R_mujoco`이다. 양쪽 기저를 바꾸는 `A R A^T`를 적용하면 이 로컬 코너와 맞지 않는다.
- `Position/CoM/P_TX,P_TY,P_TZ`는 기존 기하 중심/body origin을 유지한다. 실제 질량 중심은 `Simulation/InertialCOM/X_mm,Y_mm,Z_mm`에 별도로 기록한다. 두 위치의 차이는 회전된 로컬 COM offset이다.
- `Position/CoM/P_RX,P_RY,P_RZ`는 분석 solver와 같은 **회전벡터(rad)**이다. Euler 각이 아니다. `Simulation/BodyPose/QW,QX,QY,QZ`에는 정규화하고 인접 내적이 음수일 때 부호를 바꾼 `wxyz` 쿼터니언을 기록한다. 회전벡터의 ±π 표현 경계를 미분하지 않는다.
- GUI 초기 방향의 Fixed X/Y/Z는 MuJoCo 월드에서 적용하는 extrinsic `xyz`, degree 표시다. Euler 시계열 export/unwrap은 추가하지 않는다. Euler는 ±180° 분기와 gimbal lock에서 표현이 유일하지 않으므로 물리 각속도의 근거로 쓰지 않는다.
- 선속도는 `(p[i]-p[i-1])/dt[i]`의 뒤쪽 구간 평균이다. 가속도는 연속 구간 평균 속도의 차이를 두 구간 중점 간격 `(dt[i-1]+dt[i])/2`로 나눈 값이다. 결과는 구간 끝 행에 붙이지만 순간 미분 정답이라고 주장하지 않는다. 첫 속도 행과 첫 두 가속도 행은 NaN이다. 단일 샘플은 자세만 유효하다.
- 각속도는 `rotvec(R[i] R[i-1]^-1)/dt[i]`로 구한 **Y-up 월드 좌표계 rad/s** 구간 회전율이다. `Global_V_RX/RY/RZ`와 norm에 저장한다. 각가속도는 이 월드 벡터 차이를 같은 중점 간격으로 나눈 rad/s²이고 `Global_A_RX/RY/RZ`에 저장한다. 박스 로컬 각속도로 오해하지 않는다. 회전축이 구간 내 변하는 경우 유한 구간 추정량이다.
- 쿼터니언 부호만 반전되면 운동은 0이다. 충분히 샘플링된 실제 180° 회전과 여러 바퀴 회전은 계속 운동으로 기록된다. 연속 샘플 사이 실제 회전이 π 이상이면 shortest-arc에서 방향/회전 수가 모호해진다. 저장 pose만으로 그 aliasing을 복원하거나 검출한다고 주장하지 않는다.
- optional Gaussian noise는 Y-up **corner 관측**에만 적용하고 corner 속도·가속도도 그 관측에서 계산한다. body pose와 실제 COM은 무노이즈 simulation truth를 유지하므로 noisy corners와 강체 일치하지 않는다. 입력 history는 그대로다. local PCG64 RNG와 명시적 seed로 반복 가능하며 GUI 기본 seed는 0이다. 이 노이즈는 센서 교정 모델이 아니다.
- `Info/Artifact`는 synthetic 출처와 알고 있는 치수·좌표·단위·생성 버전만 선언한다. model/layout/ISTA Type/t1/Analysis 처리 기록은 만들지 않는다. 실제 실행 설정은 `Info/Simulation`에 별도로 기록하며 통계 비교를 허용하는 Analysis 설정 지문을 대체하지 않는다. 기존 출력의 출처를 소급 추정하지 않는다.

정확한 tuple/type/결측 및 소비자 정책은 [결과 스키마](analysis/reference/result_schema_notes.md)의 Simulation 항목을 따른다. 수학/필드 근거: [SciPy rotation vector](https://docs.scipy.org/doc/scipy/reference/generated/scipy.spatial.transform.Rotation.as_rotvec.html), [Euler convention and singularity](https://docs.scipy.org/doc/scipy/reference/generated/scipy.spatial.transform.Rotation.as_euler.html), [MuJoCo mjData의 xpos/xipos/xquat](https://mujoco.readthedocs.io/en/stable/APIreference/APItypes.html#mjdata).

### 2.4 시뮬레이션 GUI (`src/simulation/ui/main_window.py`)
메인 런처의 **[Simulation] 탭**에서 마우스 클릭만으로 손쉽게 시뮬레이션을 수행하고 `.proc` 파일로 저장할 수 있습니다.
1. 박스 크기(Width, Depth, Height)와 질량(Mass), 마찰 및 Contact damping control 입력.
2. 낙하 높이(Drop Height, mm) 및 낙하 자세 시나리오 선택.
3. **Simulation Duration(s):** 시뮬레이션을 몇 초 동안 실행할지 설정할 수 있습니다. (기본 2초. 낙하 높이가 높을 경우 시간을 늘려야 합니다.)
4. [Run Current Sequence]를 누르고 저장 파일을 선택한다. Show 3D Viewer를 끄면 SimulationThread가 실행·저장하고, 켜면 기존 MuJoCo viewer 경로를 사용한다.
5. 이후 메인 [Analysis & Visualization] 탭에서 생성된 파일을 로드하여 3D 시각화 가능.

파일/폴더 선택을 취소하면 시뮬레이션을 시작하지 않는다. 단일 실행과 Batch 모두 실행 중에는 두 실행 버튼을 잠그고 완료·오류 뒤 복구한다. viewer 경로는 설정한 기록 시간이 끝나도 viewer를 닫은 뒤에 저장한다. Batch는 파일마다 교체를 완료한 후 다음 항목으로 넘어가며, 실패한 항목에서 중단한다. 그 전에 완료한 파일은 유지한다. Batch 전체를 한꺼번에 되돌리는 저장 방식은 아니다.

현재 GUI의 `Roll / Pitch / Yaw` 값은 표준 시나리오를 선택했을 때 **자동 계산된 결과를 보여주는 필드**로 이해해야 합니다.  
특히 Type G에서는 `Edge` / `Corner` 자세의 기울기 크기가 박스 크기 비율에 따라 달라져야 하므로, 이 값은 수동 상수로 고정되면 안 됩니다.

사용자가 표준 자세에서 작은 perturbation을 주고 싶을 수 있으므로, 시뮬레이션 UI는 다음 흐름을 지원하는 것이 적절합니다.
- 표준 시나리오를 선택하면 `Roll / Pitch / Yaw`를 자동 계산해서 채운다.
- 사용자가 각도를 직접 수정하면 이를 수동 perturbation으로 간주한다.
- 현재 자세를 보여주는 작은 박스 프리뷰를 함께 표시해, 접촉 면과 기울어진 방향을 직관적으로 확인할 수 있게 한다.
- 표준값과 다른 값이 들어오면 기존처럼 경고 메시지를 표시한다.

## 3. 박스 모델링 방법론 (Box Modeling)

시뮬레이터에서 박스를 정의할 때 중요한 물리적 요소는 다음과 같습니다:

- **크기 (Dimensions) 및 로컬 축 매핑:**
  - 사용자가 입력하는 전체 크기는 다음과 같이 박스의 로컬 좌표계 축과 매칭되며, 내부적으로 **절반 길이(Half-extents)** 로 변환되어 적용됩니다.
    - **Width (가로):** 로컬 **X축**
    - **Height (높이):** 로컬 **Y축**
    - **Depth / Thickness (깊이):** 로컬 **Z축**
- **글로벌 좌표계 변환 (Global Coordinate Transformation):**
  - MuJoCo 엔진은 내부적으로 **Z-up (Z축이 위를 향함)** 좌표계를 사용하지만, 기존 분석 시스템 및 3D 시각화는 `WORLD_VERTICAL_AXIS_INDEX = 1` 기준의 **Y-up** 좌표계를 사용합니다.
  - 데이터 내보내기(`DataExporter`) 시 호환성을 위해 `[X_mujoco, Y_mujoco, Z_mujoco]` 좌표가 `[X, Z, -Y]` 형태의 **Y-up 글로벌 좌표계로 자동 변환**되어 `.proc` 파일에 저장됩니다.
  - 지면 상대 높이는 변환된 Y축 기준이다. 연성 접촉과 margin 때문에 정지 상태에서도 기하학적 높이가 정확히 0이라는 보장은 없다.
- **무게 중심 (Center of Mass, CoM):**
  - **좌표계 기준:** CoM 오프셋은 위에서 설명한 박스의 **로컬 좌표계(X=Width, Y=Height, Z=Depth)**를 기준으로 합니다. 즉, 박스의 기하학적 정중앙이 `(0, 0, 0)`이며, 입력한 값(mm)만큼 질량 중심이 내부적으로 이동합니다.
  - GUI의 기존 Y 오프셋 기본값 `-200 mm`는 모델 가정이며 실제 제품의 측정값이 아니다. 회전 발생 여부는 접촉력의 작용선과 초기 상태에도 의존하므로, 텀블링에 비영점 COM 오프셋이 항상 필요한 것은 아니다. 공개 충돌 fixture는 COM 오프셋 0을 사용한다.
- **관성 텐서 (Inertia Tensor):**
  - 엔진은 `size`와 `mass`로 균일 직육면체의 주관성 모멘트를 계산해 지정 COM에 명시한다. COM을 이동해도 관성값을 그대로 쓰는 가정은 편심 제품의 실측 질량 분포를 재현하지 않는다.

## 4. 시뮬레이션 관찰과 검증 한계
아래 항목은 모델에서 관찰할 운동의 예이며, 실제 충돌의 정확도를 검증한 결과로 사용하지 않는다:
- **초기 자유 낙하:** 중력만 작용할 때 실제 COM의 가속도가 아래 방향 9.81m/s²다. 회전하는 박스의 코너와 body origin에는 회전 운동 성분이 더해지므로 모두 같은 가속도라고 볼 수 없다.
- **1차 충돌 (Impact):** 접촉력으로 병진·회전 운동이 변한다. 접촉점이 고정 pivot이 되거나 수직 속도가 반드시 0/양수로 바뀐다고 가정하지 않는다. 접촉 감쇠와 기록 간격에 따라 보이는 변화가 다르다.
- **텀블링 (Tumbling):** COM을 지나지 않는 접촉력은 회전을 바꿀 수 있다. 각 코너의 속도는 `v_COM + omega × r`이며, `r`은 COM에서 코너로 향하는 월드 벡터다. 반대편 코너의 가속도 크기와 방향은 초기 자세·회전·접촉 조건에 의존한다.
- **안정화 (Resting):** 마찰과 접촉 감쇠로 운동이 줄어드는지 관찰한다. 지정한 기록 시간 안에 정지한다고 보장하지 않는다.

(해당 검증 그래프는 `docs/images/proposal_tv_velocity_corner.png`에서 확인할 수 있습니다.)

## 5. 접촉 모델과 현재 검증 범위
`condim=4`는 법선·접선 마찰과 비틀림 마찰을 포함하지만 구름 마찰은 포함하지 않는다. box margin 5 mm는 접촉 활성 거리이며 둥근 모서리 반경이 아니다. 연성 접촉에서는 기하학적 관통이 발생할 수 있다. 설정과 의미는 [MuJoCo contact 모델](https://mujoco.readthedocs.io/en/stable/computation/index.html#contact)과 [solref](https://mujoco.readthedocs.io/en/stable/modeling.html#solver-parameters)를 따른다.

공개 fixture는 관측 오류와 분석 흐름의 합성 검증용이다. 실제 포장재 변형·충격 내구성·ISTA 합격 여부를 예측하는 검증된 디지털 트윈으로 취급하지 않는다. 구체적인 입력과 결과는 위 fixture 계약과 조사 결과에 기록한다.

## 6. #81 exporter 실행 확인 (2026-09-11~12)

| 입력 | 기대 결과 | 확인 결과 |
|---|---|---|
| 해석적 stationary, X/Y/Z, composite, 불규칙 dt, 720° 회전, quaternion 부호 반전 | 실제 dt 미분, 코너/회전 일치, 부호만의 가짜 운동 없음 | `tests/test_simulation_export.py`로 확인. 단위 계약 근거이며 실측 정확도 근거가 아님 |
| 같은 history 반복 export, seed 12/13 noise, invalid time | 원본 불변, 같은 seed 재현, 다른 seed 관측 변화, invalid time 거부 | 저장 bytes/배열 및 corner 관측 미분 확인 |
| 1/2/63행 export→DataLoader→DataHandler, 구형 norm 열 누락 | 초기 미확정 norm 결측 유지, 유효 성분으로만 구형 fallback | 독립 리뷰에서 발견한 전부 NaN→0 변조 수정. 명시된 norm은 그대로 보존하고, 열이 없을 때만 세 성분이 모두 유한한 행에서 계산 |
| 실제 MuJoCo 200×120×80mm, COM offset (3,-4,2)mm, 15 samples | body pose·8 corners·inertial COM round-trip | 최대 좌표 오차 1e-10mm 이내의 수치 검사 통과 |
| 실제 SimulationUI 공개 박스, 1kg, 100mm 낙하, 초기 xyz (20,35,-15)°, 0.5s, noise OFF | Run→파일 선택→저장→production 3D 재열기, 실제 비영 회전, synthetic 표시 | 63행, 실제 dt 0.008s, 자세 변화 0.721727rad, 코너 재구성 최대 오차 2.274e-13mm. t1/Analysis identity 없음을 표시하고 개별 조회만 허용 |
| 기존/새 목적 경로에서 CSV 본문 쓰기·fsync·교체 실패 | 기존 bytes 유지, 새 불완전 파일 없음, 오류 전달 후 재시도 가능 | 실제 CSV header 뒤 본문 실패를 포함해 확인. 임시 파일 정리와 같은 exporter 재시도·3행 재열기 통과 |
| Windows에서 기존 목적 파일의 교체를 잠근 뒤 viewer 실행 | 실패 안내, 기존 파일 보존, 실행 버튼 복구 | 실제 native 파일 선택→viewer 종료→WinError 5 확인. 잠금 해제 후 같은 입력을 재실행해 63행 저장·재열기 성공 |
| 단일/Batch 파일 선택 취소, worker 쓰기 실패, Batch 두 번째 파일 교체 실패 | 취소 시 실행 안 함, 실패 후 버튼 복구, Batch는 완료 파일 보존 후 중단 | 실제 Qt dialog 취소 및 worker 경로 확인. Batch 첫 파일은 63행으로 열리고 기존 두 번째 파일은 보존되며 후속 파일은 생성되지 않음 |
| 실제 native GUI에서 현재 Type G Batch 목록 실행 | 목록의 각 결과 저장 후 재열기 | 17개 파일 저장 성공. 단일 결과와 함께 총 18개를 production loader/handler로 재열어 각각 63행·0.008s 간격 확인. 코너/COM 재구성 최대 오차 각각 2.558e-13/2.278e-13mm |

GUI 검사는 실제 Qt widget/worker/file dialog 및 VTK renderer를 실행한다. widget 화면의 native VTK 부분은 Windows grab에서 검게 잡혀 별도 `plotter.screenshot` 원본으로 8개 꼭짓점 표시를 확인했다. Native viewer 오류·재시도·Batch는 Windows UI를 직접 조작했다. 현재 데스크톱의 최대화 화면에서 확인했으며 1920×1080/125% 배율의 전체 레이아웃 검증은 아니다. Batch 17개 모두를 GUI로 그렸다는 뜻도 아니다. 영상은 만들지 않았다.

독립 코드 담당은 기존 파일 손상 재현, 실제 Windows 잠금/해제, 최종 diff와 회귀 결과를 직접 확인했다. 물리 담당은 같은 실제 MuJoCo history를 이전/현재 exporter에 넣어 1·2·15·63행과 seeded noise 결과가 bytes까지 같고, 좌표·COM·결측·실제 시간이 유지됨을 확인했다. 주 에이전트도 최종 diff, 재열기 수치와 화면을 확인했다. 두 담당자의 최종 통합 리뷰에서 차단 지적은 남지 않았다.

| 리뷰 지적 | 수정 및 재확인 |
|---|---|
| 직접 쓰기는 본문 실패 시 기존 결과를 header로 덮어씀 | 완성한 임시 파일만 교체하도록 수정. 기존/새 파일 실패와 재시도 확인 |
| 목적 파일명을 임시 이름에 붙이면 유효한 긴 이름도 저장 실패 | 짧은 고유 prefix로 수정. 250자 목적 파일명 교체·재열기 독립 재확인 |
| 임시 파일 정리 오류의 추가 설명이 UI에서 사라짐 | worker/viewer 오류 메시지에 exception notes 전달. 원래 오류와 임시 경로 보존 재확인 |

실행 증거는 로컬 작업 트리의 `tmp/issue81_gui/`(입력·저장·재열기 화면, VTK 원본, result.json), `tmp/issue81_native/`(입력, viewer, 오류/성공 화면, observations.json, reopened.json)에 있다. 이 ignored 경로는 배포 자료가 아니다. 회귀 범위는 두 `test_simulation_export*.py` 파일이며 전체 #74 matrix를 반복하지 않았다. GUI 검사 초기에 QObject의 `thread()`를 worker로 오인한 판정과 UI 최소 0.5s에 맞지 않는 0.1s 입력을 수정했다. Qt 대기 중 Python writer가 실행되도록 event 처리 사이 GIL을 양보했으며 제한 시간과 수치 허용 오차는 늘리지 않았다.

남은 항목: 커밋·push·새 커밋 CI·병합, 알려진 실측 회전 사례와의 축/부호 교정. 사용자는 2026-09-12에 커밋·push·병합의 계속 진행을 승인했다. 기존 PR #89 CI 34600918652는 변경 전 `b0fd685`의 결과다. 현재 저장 안정성 결과는 실제 OptiTrack 정확도, ISTA 적합성 또는 #81 전체 완료가 아니다.

후속 시험 해석에서는 확인한 [2018 SIOC 원문](https://d39w7f4ix9f5s9.cloudfront.net/32/98/c52dd6b841f18bcb8af679b1f1ac/9.TESTING_thumbnail_ISTA%20Project%206-Amazon.com-SIOC%2018-18.pdf)과 실제 시험에 적용한 판본을 구분해야 한다. 적용 판본은 아직 시험 기록으로 확인되지 않았다. Type G/H 선택에는 제품·중량·치수·운송 취급 기록이 필요하며, 반복 자세나 일부만 찍힌 운동만으로 고유 시험 번호를 확정할 수 없다. Type H 지지/해제 조건과 원문의 경계값·hazard 표기 충돌을 해결한 뒤 #75 자동 구간 검출용 정답을 정의한다. 접근하지 못했거나 충돌하는 절차를 임의 임계값으로 채우지 않는다.
