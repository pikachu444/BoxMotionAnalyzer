# Box Motion Analyzer

Last Reviewed: 2026-03-19

**Box Motion Analyzer**는 모션 캡처 데이터(CSV)를 기반으로 박스와 마커의 움직임을 정밀하게 분석하고, 이를 3D 환경에서 시각화하는 통합 GUI 애플리케이션입니다.

## 🚀 주요 기능

### 1. 데이터 분석 (Data Analysis)
*   **분석 파이프라인 (Analysis Pipeline):** 원본 모션 데이터를 로드하여 전처리(스무딩), 자세 최적화(Pose Optimization), 속도 계산 등의 과정을 자동으로 수행합니다.
*   **결과 검증:** 분석된 데이터의 무결성을 검증하고, 필수 데이터(Rigid Body Pose 등)의 존재 여부를 확인합니다.
*   **시나리오 내보내기 (Scenario Export):** 분석 결과를 표준화된 포맷의 CSV 파일로 내보냅니다. 이 파일은 시각화 툴에서 바로 로드할 수 있습니다.
    *   **자동/수동 오프셋:** 코너 높이를 기반으로 가장 낮은 3개 코너를 자동 선택하거나 수동으로 지정하여 분석 시나리오를 생성할 수 있습니다.

### 2. 3D 시각화 (3D Visualization)
*   **실시간 렌더링:** 분석된 박스와 마커의 움직임을 PyVista 기반의 3D 뷰포트에서 재생합니다.
*   **인터랙티브 제어:** 재생/일시정지, 프레임 슬라이더 이동, 시점 제어 등이 가능합니다.
*   **데이터 플로팅:** 선택한 객체의 위치, 속도, 가속도, velocity norm 시계열을 2D 그래프로 확인하고 비교할 수 있습니다.
*   **심층 분석:** 프레임 구간 필터와 상세 플롯 팝업을 제공하며, 팝업에서는 마우스 오버로 정확한 수치를 확인할 수 있습니다.

---

## 📂 프로젝트 구조

이 프로젝트는 유지보수와 확장성을 위해 다음과 같이 모듈화된 폴더 구조를 갖습니다.

*   **`src/`**: 소스 코드 루트
    *   **`main.py`**: 프로그램의 통합 진입점. Launcher를 실행합니다.
    *   **`launcher.py`**: 분석 GUI와 3D 시각화 GUI를 여는 런처 윈도우입니다.
    *   **`analysis/`**: 데이터 분석 관련 핵심 로직 및 UI.
        *   `app/`: 분석 메인 윈도우(`MainApp`)와 상위 UI 조립 코드
        *   `pipeline/`: parser, slicer, smoother, pose optimizer, velocity calculator, frame analyzer 등 분석 파이프라인
        *   `ui/`: Step 1/Step 2 위젯, 플롯, 대화상자
    *   **`visualization/`**: 3D 시각화 관련 코드(PyVista, Qt 위젯, 결과 로더)
    *   **`config/`**: 설정 파일, 컬럼 정의, 아이콘/이미지 리소스
    *   **`utils/`**: 공용 유틸리티 스크립트.
*   **`docs/`**: 개발 문서 및 참고 자료.
*   **`data/`**: 데이터 입출력 폴더 (테스트 데이터 포함).
*   **`tests/`**: 통합 테스트 및 구조 검증 스크립트.

### 현재 GUI 흐름

*   **Launcher**
    *   `src/main.py` -> `src/launcher.py`
*   **Data Analysis**
    *   `src/analysis/app/main_window.py`
    *   Step 1: Raw Data Processing
    *   Step 2: Results Analysis
    *   Step 1/Step 2의 메인 플롯은 창 크기 변화에 따라 더 크게 확장되도록 조정되어 있으며, 세로 splitter로 높이를 수동 조절할 수 있습니다.
*   **3D Visualization**
    *   `src/visualization/main_window.py`
    *   입력은 분석 결과로 export한 multi-header `.proc` 파일입니다.

---

## 📘 문서 안내

문서 목적에 따라 아래 경로를 우선 참고하세요.

*   **루트 `README.md`**: 프로젝트 개요, 실행 방법, 빌드/테스트 안내
*   **`docs/documentation_index.md`**: `docs/` 폴더 전체 안내
*   **`docs/analysis/`**: 분석 기능 설계 문서와 참조 문서
*   **`docs/visualization/`**: 3D visualization 가이드와 레이아웃 설계 문서
*   **`docs/launcher/`**: 런처 관련 레이아웃 스케치와 메모

---

## 🛠️ 실행 방법

### 1. 필수 라이브러리 설치
프로젝트 실행을 위해 `requirements.txt`에 명시된 의존성 패키지를 설치해야 합니다.

```bash
pip install -r requirements.txt
```

### 2. 애플리케이션 실행
프로젝트 루트 디렉토리에서 아래 명령어를 입력하여 실행합니다.

```bash
python src/main.py
```
실행 시 **Launcher Window**가 열리며, 여기서 아래 두 흐름 중 하나를 시작할 수 있습니다.

*   **Data Processing**: 원본 CSV를 불러와 분석하고 결과를 `.proc` 중심 workflow로 저장
*   **3D Visualization**: export된 `.proc` 결과 파일을 열어 3D/2D로 탐색

### 3. 분석 결과 export와 visualization의 관계

시각화 창은 원본 raw CSV를 직접 읽지 않습니다.  
분석 GUI에서 export한 **multi-header `.proc` 결과 파일**을 입력으로 사용합니다.
UI 기준으로는 `.proc`만 노출합니다.

---

## 🏗️ 빌드 방법 (배포용 실행 파일 생성)

이 프로젝트는 **Windows 배포**를 기준으로 `PyInstaller`를 사용해 독립 실행형(`.exe`) 파일을 생성합니다.

### 1. `build.bat` 사용 (Windows 권장)
`build.bat` 파일을 더블 클릭하거나 명령 프롬프트에서 실행한 후, 원하는 모드를 선택하세요.
*   **1 (Folder):** 폴더 형태(`dist/BoxMotionAnalyzer/`)로 빌드. (빠른 실행, 개발용)
*   **2 (Single File):** 단일 파일(`dist/BoxMotionAnalyzer.exe`)로 빌드. (배포용)

### 2. `python build.py` 직접 실행
```bash
# 폴더 방식 (onedir)
python build.py onedir

# 단일 파일 방식 (onefile)
python build.py onefile
```

### 3. 아이콘/리소스 포함

빌드 시 실행 파일 아이콘과 런처/창 아이콘에 필요한 리소스는 `src/config/images/` 아래 파일을 사용합니다.
Windows에서 최종 아이콘 확인 시에는 아래를 함께 점검하세요.

*   탐색기에서 보이는 `.exe` 아이콘
*   실행 후 창 좌상단 아이콘
*   작업표시줄 아이콘

---

## 🧪 테스트 실행

변경된 구조에서 전체 데이터 흐름(분석 -> 저장 -> 시각화)이 정상 동작하는지 검증하려면 통합 테스트를 실행하세요.

```bash
python -m unittest tests/test_pipeline_integration.py
```

GUI 없이 진입점 로직만 빠르게 검증하려면:
```bash
python -m unittest tests/test_launch_headless.py
```
