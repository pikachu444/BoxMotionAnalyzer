# Box Motion Analyzer GUI 설계 원칙 (GUI Principles)

Last Reviewed: 2026-06-10

본 애플리케이션의 프론트엔드는 "엔지니어링/분석 툴"로서의 직관성과 정보 밀도를 극대화하기 위해 다음의 7가지 설계 원칙을 따릅니다.

## 1. 순정(Native) 시스템 렌더링 유지 (Native Consistency)
- 각 패널을 감쌀 때는 시스템이 기본으로 제공하는 '얇고 깔끔한 까만색 선(Native Border)'을 그대로 유지합니다.
- 패널 내부의 마진(Margin)과 여백(Padding)은 타이트(Tight)하게 유지하여 정보 밀도를 높입니다.
- 억지로 두꺼운 CSS 테두리를 주입하여, 선 중간에 제목이 위치하는 순정 디자인을 훼손해서는 안 됩니다.

**[예시]**
```python
# 별도의 CSS 강제 없이 순정 객체만을 상속받아 사용
class MyPanel(QGroupBox):
    def __init__(self):
        super().__init__("Panel Title")
```

## 2. 견고한 레이아웃 (Rigid & Bounded Sizing)
- 레이아웃이 단순히 `Stretch`에 의존하여 무한정 늘어지거나 화면 축소 시 찌그러지지 않아야 합니다.
- 각 핵심 컴포넌트(사이드바, 주요 플롯 등)는 명확한 최소 크기(`MinimumWidth`, `MinimumHeight`)를 가져 레이아웃의 형태를 고정합니다.

**[예시]**
```python
self.control_panel = CompareControlPanel()
self.control_panel.setMinimumWidth(250)
```

## 3. 일관된 위계와 동선 (Consistent Hierarchy)
- **조작 및 설정 (Input/Control):** 사용자 입력, 파일 로드, 세부 설정 패널은 화면의 **좌측** 또는 상단에 배치합니다.
- **결과 및 시각화 (Output/View):** 요약표, 3D 재생, 시계열 그래프 등 핵심 시각화 요소는 화면의 **우측(메인) 영역**에 정보의 흐름에 따라 상단에서 하단으로 깊이가 깊어지도록 배치합니다.

**[예시]**
```python
# 우측 레이아웃 상하 배치 예시
self.right_splitter.addWidget(self.table_panel)    # 상단: 요약표
self.right_splitter.addWidget(self.playback_panel) # 중단: 3D
self.right_splitter.addWidget(self.graph_panel)    # 하단: 그래프
```

## 4. 불필요한 탭(Tab) 지양 (No Unnecessary Tabs)
- 서로 비교하거나 연관지어 분석해야 하는 데이터(예: 요약 테이블과 3D 재생 화면)를 볼 때 탭을 전환하며 보는 것을 지양합니다.
- 핵심 결과들은 스플리터(Splitter)를 활용해 한 화면에 상하/좌우로 오버레이하거나 동시 노출하여 직관적인 분석을 돕습니다.

**[예시]**
```python
# 탭 위젯 대신 스플리터 사용
self.splitter = QSplitter(Qt.Horizontal)
self.splitter.addWidget(self.control_panel)
self.splitter.addWidget(self.right_splitter)
```

## 5. 입체적 카드 레이아웃 (Depth & Card Structure)
- 창 전체 배경을 단일 색상으로 평면적으로 덮지 않습니다.
- 윈도우 바탕은 기본 회색(Grey)으로 유지하고, 핵심 내용물을 얇은 테두리가 있는 하얀색 상자(White Card) 안에 담아 입체적으로 분리합니다.

**[예시]**
```python
main_layout = QVBoxLayout(central_widget)
main_layout.setContentsMargins(10, 10, 10, 10) # 윈도우 바탕의 회색 여백

content_frame = QFrame()
content_frame.setStyleSheet("background-color: #ffffff; border: 1px solid #cccccc;")
main_layout.addWidget(content_frame)
```

## 6. 작업 흐름을 명시하는 넘버링 (Workflow Numbering)
- 애매한 패널 이름 대신, 사용자가 무엇을 먼저 해야 할지 파악할 수 있도록 각 패널 제목에 직관적인 넘버링을 부여합니다.

**[예시]**
```python
class CompareControlPanel(QGroupBox):
    def __init__(self):
        super().__init__("1. Result Files") # 직관적 넘버링 적용
```

## 7. 기능적 통일성 유지 (Feature Parity)
- 특정 화면에 존재하는 유용한 기본 기능(예: 그래프 네비게이션 툴바)은 다른 화면의 동일한 뷰어에도 누락 없이 100% 동일하게 제공해야 합니다.

**[예시]**
```python
# 다른 화면과 통일되도록 네비게이션 툴바 반드시 포함
from matplotlib.backends.backend_qtagg import NavigationToolbar2QT

self.toolbar = NavigationToolbar2QT(self.canvas, self)
layout.addWidget(self.toolbar)
layout.addWidget(self.canvas)
```
