# Box Motion Analyzer

Last Reviewed: 2026-11-16

모션 캡처로 기록한 박스 낙하 시험을 살펴보는 데스크톱 프로그램입니다. 긴 촬영 기록에서 시험 구간을 선택하고, 필요한 마커 보정을 검토한 뒤 움직임과 충돌 직전 상태를 분석합니다. 회차 결과 비교, 3D 재생, CAE 초기조건 CSV 저장을 지원합니다. 촬영 CSV가 없어도 MuJoCo로 가상 낙하 결과를 만들어 재생하거나, 합성 마커 관측을 생성해 분석 흐름을 사용해 볼 수 있습니다.

A desktop application for reviewing box-drop motion captures: select trial intervals, review optional marker-face corrections, inspect motion and pre-impact results, compare trials, replay motion in 3D, and export CAE initial conditions. MuJoCo can generate synthetic motion and marker observations without a measured capture.

분석값은 입력 관측과 설정에 따른 계산 결과입니다. 실제 포장재의 변형·반발·텀블링, 실제 로봇 동작과 카메라 오차에 대한 독립 실측 정확도는 확인되지 않았습니다. 가상 데이터의 소프트웨어 검사가 실측 정확도나 ISTA 적합성을 보증하지 않습니다.

## 설치와 실행 / Install and run

Windows에서 Python 3.13을 설치하고 저장소를 내려받은 뒤, **저장소 루트**의 PowerShell에서 실행합니다. Python 3.13은 [공개 Windows CI](.github/workflows/public-marker-validation.yml)에서 사용하는 버전이며, 다른 버전의 지원 범위를 뜻하지 않습니다.

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe src/main.py
```

설치와 실행에 같은 가상환경 인터프리터를 사용하므로 별도 활성화는 필요하지 않습니다. 테스트용 추가 설치는 아래 개발 검사에서 안내합니다.

런처에서 작업을 선택합니다. 아래 버튼명은 기본 언어인 영어 기준입니다.

| 버튼 | 시작할 작업 |
| --- | --- |
| `Data Processing` | 촬영 CSV에서 구간을 검토하고 `.slice`를 처리해 `.proc` 저장 |
| `Compare Results` | 여러 `.proc`의 요약표, 기준 실험 대비 차이, 동기화 재생과 그래프 확인 |
| `3D Visualization` | 저장한 `.proc`의 박스·마커 움직임과 시계열 탐색 |
| `Simulation` | 단일 낙하 또는 가상 로봇 계획 실행, `.proc`나 합성 관측 CSV 생성 |

`Options`에서 `English` 또는 `한국어`를 선택하고 `Apply`로 저장하면 **다음 실행부터** 적용됩니다. 열린 창과 진행 중인 작업은 현재 언어를 유지합니다. 언어 설정은 파일 형식·단위·수치 계산을 바꾸지 않습니다. Windows 파일 선택 창과 일부 그래프 편집 창의 문구는 운영체제·라이브러리를 따릅니다.

## 입력 준비와 파일 역할 / Inputs and files

원본 입력은 현재 파서가 읽는 **여러 헤더 행을 가진 모션 캡처 CSV**입니다. 처음 두 행의 메타데이터와 뒤의 Type/Name/ID/Parent/Category/Component 헤더, Frame/Time과 마커 XYZ 구조를 유지해야 합니다. 분석은 `Rigid Body Marker`의 강체 추정 좌표를 사용하며, 물리 `Marker` 관측 채널과 구분합니다. 마커 이름과 면 배정도 현재 입력 규칙에 맞아야 합니다. 임의의 XYZ 표를 CSV로 저장한 것만으로 같은 입력이 되지는 않습니다.

[작은 공개 형식 예제](data/testdata_box_marker.csv)로 헤더 구조를 확인하고, [분석 GUI 안내](docs/analysis/design/gui_overview.md)와 [입력 파서](src/analysis/pipeline/parser.py)를 참고하세요. 이 예제는 형식 확인용이며 실측 정확도나 완전한 낙하 시험을 보증하는 기준 자료가 아닙니다.

촬영한 박스의 **치수(mm)**를 확인하고 화면의 축 정의에 맞춰 입력하세요. 길이는 mm, 시간은 s를 기준으로 사용합니다. 기본으로 표시된 치수를 자신의 시험 치수로 간주하지 마세요. 마커 검토와 자세 계산에 사용할 치수는 사용자가 확인해야 합니다.

| 파일 | 내용과 사용하는 곳 |
| --- | --- |
| 촬영 `.csv` | 원본 관측. `Data Processing`의 Step 1에서 열기 |
| corrected `.csv` | 승인한 마커 검토 결정을 포함한 별도 관측 파일. 원본을 보존하고 후속 구간 저장에 사용 |
| `.slice` | 검토한 관측 구간과 치수·범위·보정 등 메타데이터. Step 1.5의 처리 입력 |
| `.proc` | 분석 결과 또는 시뮬레이션 운동을 담는 다중 헤더 결과. Step 2, 비교창, 3D 시각화 입력 |
| CAE 시나리오 `.csv` | 선택한 시점 또는 수동 조건으로 만드는 별도 초기조건. 운동 재생용 `.proc`와 다른 파일 |
| Point `.csv` | 선택한 시점의 값 저장. 운동 전체의 재생 파일과 구분 |

## 첫 분석 / First capture analysis

1. **촬영 열기와 치수 확인:** 런처의 `Data Processing` → Step 1의 `Open capture...`로 호환되는 CSV를 엽니다. 박스 치수(mm)와 마커 표시를 확인합니다.
2. **필요한 경우에만 마커 검토:** `Review`에서 불연속 후보와 면 배정 보정을 검토합니다. 적용할 결정은 명시적으로 승인하고 `Save corrected`로 별도 파일에 저장합니다. 현재 면 배정 보정은 이름·ID·측정 XYZ를 보존합니다. 검토나 저장이 자동 승인을 뜻하지 않습니다.
3. **시험 구간 선택:** `Detect scenes`로 후보를 찾고 범위와 `Include`/`Exclude`를 확인합니다. 수동 범위 추가·조정도 가능합니다. 보정 입력이 바뀌었다면 저장할 구간을 다시 확인합니다. 필요하면 `Test record...`로 독립 시험 기록을 연결하되 기록된 시험 항목과 관측 결과를 구분합니다.
4. **처리 입력 전달:** `Save and Process`로 선택한 구간을 `.slice`로 저장해 Step 1.5로 넘깁니다. **이 버튼은 계산을 자동 시작하지 않습니다.** 한 파일은 Single, 여러 파일은 Batch로 준비됩니다. 저장 취소·부분 실패 시 처리 화면으로 넘기지 않습니다. `.slice`를 따로 저장해 나중에 `Open slice...`나 `Open folder...`로 여는 방법도 있습니다.
5. **방법을 확인하고 실행:** 치수·선택 구간·처리 방법을 확인합니다. Single은 `Run` 뒤 `Save and View`로 `.proc`를 저장하고 엽니다. Batch는 `Run batch` 후 이번에 저장 성공한 결과를 `View Results`로 엽니다. 실패·건너뛴 항목의 상태는 별도로 확인합니다.
6. **결과 읽기:** Step 2에서 자세·코너 높이·속도·가속도와 접촉 전후 그래프를 확인합니다. `Metric guide`에서 지표의 뜻·단위·유효 상태를 읽고, 여러 회차는 `Compare Results`에서 비교합니다.

| 처리 방법 | 선택할 때 알아둘 점 |
| --- | --- |
| `Raw` — 기본값 | 처리를 최소화하며 속도·가속도에 잡음이 더 드러날 수 있음 |
| `Smoothing` | 스무딩·필터를 적용하는 처리 방법 |
| `Advanced` | 처리 단계의 설정을 직접 조절하는 방법 |

Raw가 유일한 방법은 아닙니다. 기본 결과 재샘플링은 OFF이며, 선택적으로 처리 후 시간축 보간을 적용할 수 있습니다. 이는 새 측정 표본을 얻는 것과 다릅니다. 기존 `.slice`에 치수가 없으면 Step 1.5에서 치수를 입력하고 `Apply dimensions`를 누른 뒤 처리합니다. 정상적으로 저장한 구간의 치수와 범위는 파일에서 확인할 수 있습니다.

자세한 Single/Batch 연결과 저장 규칙은 [작업 흐름](docs/analysis/design/workflow.txt), 화면별 설명은 [GUI 안내](docs/analysis/design/gui_overview.md)를 참고하세요.

## 결과 해석·비교·3D 재생 / Read, compare and replay

`Compare Results`에서 여러 `.proc`를 추가하고 기준(Baseline) 결과를 선택해 요약값과 차이를 확인합니다. 낙하 자세·코너 높이·접촉 상태·속도 등의 정의는 Step 2와 비교창의 공통 `Metric guide`에서 확인할 수 있습니다.

동기화의 기준인 `t1−`는 **추정된 첫 접촉 직전의 기록 표본**입니다. 시간·출처가 불명확하거나 해당 구간이 끊긴 결과는 그 시점의 동기화에서 제외하고 개별로 확인할 수 있습니다. 값이 없으면 결측·제외 사유를 함께 확인하세요. 같은 관측 파일을 복사해 추가해도 독립 반복 횟수가 늘어나지 않습니다.

`3D Visualization`은 `.proc`를 열어 박스와 마커를 재생합니다. 재생·일시정지, 프레임 이동, 시점 회전·확대·이동, 구간 선택과 상세 그래프 탐색을 지원합니다. 위치·속도·가속도와 속력 그래프를 보고 필요한 객체를 비교할 수 있습니다. 원본 촬영 CSV나 CAE 초기조건 CSV를 직접 재생하는 창은 아닙니다.

런처의 `3D Visualization`을 다시 누르거나 시각화 창의 `File > New Visualization Window`로 독립 창을 추가할 수 있습니다. 자세한 조작은 [3D 시각화 가이드](docs/visualization/guide.md)를 참고하세요.

## CAE 초기조건 CSV / CAE initial conditions

Step 2의 `CAE export`에서 `Export Scenario CSV`로 별도 초기조건을 저장합니다. 자동 오프셋은 선택 시점의 코너 높이로 세 코너를 정하고, 수동 오프셋은 지정한 코너를 사용합니다.

`Manual Offset`과 `Manual Height`를 모두 켜면 수동 높이와 **기본 정지 조건(속도 6개가 0)**을 사용합니다. `Use selected-time velocities`를 명시적으로 켜면 선택 행의 유효한 선속도·각속도 6개를 사용합니다. 다른 모드에서는 선택 행의 속도를 사용합니다. 수동 높이 모드에서 벗어나면 이 선택은 OFF로 돌아갑니다.

선택 시점은 자동으로 `t1−`가 되는 것이 아닙니다. 내보내는 값은 선택 표본의 분석 좌표계 성분이며, 별도 교정된 관성 COM 속도라는 보증도 아닙니다. 7행 파일 구조·단위·입력 제한은 [시나리오 형식](docs/analysis/reference/scenario_export_format.md)을 참고하세요.

## 촬영 없이 사용하기 / Simulation

`Simulation`은 강체 낙하와 가상 취급 동작을 생성합니다. 박스 치수·질량·질량중심 오프셋·마찰과 접촉 설정을 확인하고 목적에 맞는 경로를 선택하세요.

### 직접 운동 결과 생성

- **`Single drop`:** 면·모서리 선·꼭짓점 등의 프리셋 또는 초기 회전을 선택하고 `Run`으로 실행해 `.proc`를 저장합니다. 저장한 파일은 `3D Visualization`에서 열 수 있습니다.
- **`Run all presets`:** 선택한 종류의 기존 자유낙하 프리셋을 각각 실행합니다. 하나의 연속 로봇 계획이나 검증된 완전한 ISTA 시험 절차를 뜻하지 않습니다.
- **`Robot sequence`:** 설정에서 취급 방식·부착면·순서·위치·자세와 실행 범위를 확인하고 `Preview sequence` → `Use in Simulation`으로 실행 계획을 적용한 뒤 `Run`을 누릅니다. 실행 가능한 계획이 없거나 변경 후 다시 확인하지 않은 계획은 실행을 차단합니다. 로봇 모드에서는 `Run all presets` 대신 연속 계획 하나를 `Run`으로 실행합니다.

`Settings…`에서 설정을 확인하고 `Open settings…`/`Save settings…`로 파일을 읽거나 저장할 수 있습니다. 설정을 적용하는 동작은 `Use in Simulation`입니다. 기본 Single drop의 자유낙하 프리셋과 Robot sequence의 가상 지지·회전 동작은 서로 다른 범위입니다. G17 hazard block은 지원하지 않으며 Type H의 가상 지지 동작을 실제 장치나 규격 적합성으로 해석하지 않습니다.

직접 `.proc` 저장은 엔진이 기록한 운동을 내보내는 경로로, 마커 관측을 자세 분석기로 처리한 결과와 구분합니다. Simulation 월드의 위쪽은 Z, 분석 월드의 위쪽은 Y입니다. 생성 경로의 좌표 변환과 파일 설명은 [시뮬레이션 안내](docs/simulation.md), 모드·실행 계획은 [모드 계약](docs/analysis/reference/simulation_mode_contract.md)과 [로봇 실행 계약](docs/analysis/reference/robot_sequence_contract.md)을 참고하세요.

### 합성 마커 관측으로 분석 흐름 사용

`Marker CSV…`에서 공개 예제 또는 JSON 마커 배치를 선택하고 관측을 생성할 수 있습니다. 배치 좌표는 mm이며 박스 치수에 자동 확대되지 않습니다. 치수가 다르면 `Use layout box`로 배치 치수를 사용합니다. 생성된 `observed.csv`를 `Open in Step 1`로 열어 위 분석 절차를 진행하세요. 표시된 치수와 보정 결정은 사용자가 확인합니다.

누락·반회전·잡음 옵션은 관측 오류를 시험하기 위한 합성 설정입니다. 기본 Faults는 None입니다. 실제 카메라의 오차 분포를 교정한 모델은 아닙니다. 물리 마커 채널만 바꾼 오류가 분석에 쓰는 강체 추정 채널까지 바꾸는 것은 아닙니다. 같은 폴더의 정답 파일은 평가용이며 분석 입력으로 함께 넣지 않습니다.

### 고급 API/CLI

다음 기능은 기존 API/CLI와 명시적인 입력 파일을 사용하는 고급 경로입니다. 모든 항목을 편집하는 GUI가 있다는 뜻은 아닙니다.

| 목적 | 안내 |
| --- | --- |
| 카메라 가시성·가림·시간 상관 잡음을 관측에 적용 | [관측 모델](docs/analysis/reference/observation_model_contract.md) |
| 초기 위치·자세·선속도·각속도와 접촉 설정, 수렴 진단·제한된 fit/holdout 평가 | [초기조건과 제한 교정](docs/analysis/reference/contact_calibration_contract.md) |
| 실제 엔진 timestep 접촉 기록과 관측의 첫·후속 충돌, 반등·지지 전환 대조 | [접촉 사건 평가](docs/analysis/reference/contact_evaluation_contract.md) |
| 오류 구간을 지정한 합성 관측 및 연속 촬영 예제 | [관측 생성 계약](docs/analysis/reference/marker_flip_fixture_contract.md), [시뮬레이션 안내](docs/simulation.md) |

합성 자료의 일관성 평가와 실제 제품의 물리 교정은 다른 작업입니다. 독립 실측 검증은 자료 미확보로 미실시 종료됐으며 실제 정확도가 확인된 상태가 아닙니다.

## 개발 검사 / Developer checks

앱을 실행하는 데 pytest 설치나 전체 회귀 실행은 필요하지 않습니다. 검사를 실행하려면 같은 가상환경에 테스트 도구를 추가합니다. 공개 CI의 Python 3.13·MuJoCo 3.6.0 지정을 맞추려면 다음과 같이 설치하세요.

```powershell
.\.venv\Scripts\python.exe -m pip install pytest "mujoco==3.6.0"
```

이는 CI의 Python·MuJoCo 지정에 맞추는 절차입니다. 전체 의존성 잠금이나 Windows 화면·Qt/OpenGL 환경까지 같아진다는 뜻은 아닙니다. CI의 화면 설정과 필수 검사 목록은 [Windows CI](.github/workflows/public-marker-validation.yml)를 기준으로 확인합니다.

먼저 파일 역할과 슬라이스 치수 저장의 작은 연결 검사를 실행할 수 있습니다.

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/test_artifact_io_filters.py
```

분석→저장→시각화 로더 연결과 런처 진입점 검사는 별도로 실행할 수 있습니다. 아래 검사는 Qt 환경을 사용합니다. 진입점 검사는 일부 호출을 모의하므로 실제 창의 사용성까지 증명하지 않습니다.

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/test_pipeline_integration.py tests/test_launch_headless.py
```

이 작은 검사들은 전체 캡처 회귀나 실측 정확도 검증이 아닙니다. 전체 Raw를 새로 처리하는 `full` 실행은 오래 걸릴 수 있으므로 첫 실행 절차와 분리합니다. 합성 corpus 생성, representative/full 실행과 재개 조건은 [캡처 회귀 안내](docs/analysis/reference/capture_regression.md)와 [회귀 단계·실행 기록](docs/analysis/reference/regression_evidence.md)을 참고하세요. 생성 명령의 출력 폴더는 매번 새 경로를 사용합니다. 공개 소프트웨어 검사에는 비공개 촬영 자료가 필요하지 않습니다.

## Windows 실행 파일 빌드 / Build

저장소 루트에서 같은 가상환경으로 실행합니다.

```powershell
.\.venv\Scripts\python.exe build.py onedir
.\.venv\Scripts\python.exe build.py onefile
```

| 모드 | 결과 경로 |
| --- | --- |
| `onedir` | `dist/onedir/BoxMotionAnalyzer/` — 폴더 전체를 배포 |
| `onefile` | `dist/onefile/BoxMotionAnalyzer.exe` |

`build.bat`를 실행해 1(Folder) 또는 2(Single File)를 선택할 수도 있습니다. 이 스크립트는 루트 `.venv`, 없으면 상위 `.venv`를 먼저 찾으므로 의도한 환경을 사용하는지 확인하세요. 아이콘·이미지는 `src/config/images/`를 사용합니다. 배포 확인에는 실행 파일·창·작업표시줄 아이콘과 실제 실행을 포함합니다.

## 구조와 더 읽을 문서 / Structure and guides

| 경로 | 역할 |
| --- | --- |
| `src/main.py`, `src/launcher.py` | 앱 시작과 런처 |
| `src/analysis/` | CSV 처리, 구간·마커 검토, Single/Batch 분석, 결과·비교 GUI |
| `src/visualization/` | `.proc` 로더, 3D 재생과 그래프 |
| `src/simulation/` | MuJoCo, 관측 생성, 가상 로봇 계획과 고급 CLI |
| `src/config/`, `src/utils/` | 설정·컬럼 정의·리소스와 공용 기능 |
| `tests/`, `data/` | 검사와 공개 형식 예제 |

- 사용자 절차: [분석 GUI](docs/analysis/design/gui_overview.md), [작업 흐름](docs/analysis/design/workflow.txt), [3D 시각화](docs/visualization/guide.md), [시뮬레이션](docs/simulation.md)
- 저장 형식: [결과 스키마](docs/analysis/reference/csv_multi_header_schema.md), [결과 필드](docs/analysis/reference/result_schema_notes.md), [CAE 초기조건](docs/analysis/reference/scenario_export_format.md)
- 개발 안내: [저장소 작업 규칙](AGENTS.md), [현재 설계](docs/analysis/design/system_design.md), [GUI 지표의 구현·검증 범위](docs/visualization/gui_metric_parity/validation_report.md)
- 전체 탐색과 전달 기록: [문서 인덱스](docs/documentation_index.md), [공개 기능·실행 근거](docs/analysis/reference/pub_delivery_status.md)

현재 사용 안내와 과거 실행 기록은 구분해서 읽으세요. 과거 기록의 날짜·버전·실패 이력은 해당 실행의 범위를 나타내며, 현재 소프트웨어의 존재 여부나 독립 실측 정확도를 대신하지 않습니다.
