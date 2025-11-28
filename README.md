# Box Motion Analyzer

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
*   **데이터 플로팅:** 선택한 객체(코너, 마커)의 위치, 속도, 가속도 등을 2D 그래프로 실시간 확인 및 비교할 수 있습니다.
*   **심층 분석:** 특정 프레임 구간을 확대하거나, 마우스 오버 시 정확한 수치를 확인하는 툴팁 기능을 제공합니다.

---

## 📂 프로젝트 구조

이 프로젝트는 유지보수와 확장성을 위해 다음과 같이 모듈화된 폴더 구조를 갖습니다.

*   **`src/`**: 소스 코드 루트
    *   **`main.py`**: 프로그램의 통합 진입점 (Launcher 실행).
    *   **`launcher.py`**: 분석 도구와 시각화 도구를 연결하는 런처 윈도우.
    *   **`analysis/`**: 데이터 분석 관련 핵심 로직 및 UI.
        *   `core/`: 파이프라인, 데이터 로더 등 핵심 모듈.
        *   `ui/`: 분석 관련 위젯 및 다이얼로그.
    *   **`visualization/`**: 3D 시각화 관련 코드 (PyVista, Qt 위젯).
    *   **`config/`**: 설정 파일 중앙 관리 (`config_visualization.py` 등).
    *   **`utils/`**: 공용 유틸리티 스크립트.
*   **`docs/`**: 개발 문서 및 참고 자료.
*   **`data/`**: 데이터 입출력 폴더 (테스트 데이터 포함).
*   **`tests/`**: 통합 테스트 및 구조 검증 스크립트.

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
실행 시 **Launcher Window**가 열리며, 여기서 **Data Processing** (분석) 또는 **3D Visualization** (시각화) 버튼을 클릭하여 원하는 작업을 시작할 수 있습니다.

---

## 🏗️ 빌드 방법 (배포용 실행 파일 생성)

`PyInstaller`를 사용하여 독립 실행형(`.exe`) 파일을 생성할 수 있습니다.

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
