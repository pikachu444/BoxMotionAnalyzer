# Box Motion Analyzer GUI 설계 원칙 (GUI Principles)

Last Reviewed: 2026-09-14

사용자가 현재 파일, 선택한 데이터와 다음 행동을 쉽게 알 수 있도록 구성한다. 설명 문단과 긴 제목을 늘리기보다 파일 열기, 검토, 처리, 결과 보기의 동작을 연결한다.

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

## 2. 창 크기에 맞는 레이아웃
- 핵심 행동과 결과에 공간을 먼저 배분한다. 부가 설정은 접고 긴 폼에는 스크롤을 제공한다.
- 컴포넌트의 최소 크기를 합친 결과가 실제 화면보다 커지지 않게 한다. 기본 창과 작은 창에서 버튼, 표의 행, 범례와 재생 정보를 읽을 수 있어야 한다.

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

## 6. 짧은 이름과 필요한 상태
- Step 1 / 1.5 / 2의 단계 구분은 유지하되 패널마다 번호를 강제로 붙이지 않는다. 버튼은 Open, Review, Run처럼 행동을 나타내는 짧은 이름을 쓴다.
- 저장 컬럼 키, 알고리즘 버전, 내부 점수 이름을 기본 화면의 제목과 범례로 사용하지 않는다. 단위와 판단에 필요한 불확실성은 짧게 표시하고 자세한 근거는 필요한 곳에서 확인하게 한다.
- 안내 문단이나 장식 기호로 조작의 부재를 메우지 않는다. 현재 파일명, 선택, 저장 전후 상태가 서로 맞아야 한다.

## 7. 실제 사용 흐름 확인
- 같은 역할의 조작은 일관되게 제공하되 모든 화면에 같은 도구를 무조건 복제하지 않는다. 해당 화면의 판단에 필요한 도구를 우선한다.
- 서로 다른 입력으로 파일 변경, 선택, 미리보기, 저장과 재열기를 확인한다. 창이 그려졌거나 화면 밖 버튼을 코드로 누를 수 있다는 사실만으로 사용성을 판단하지 않는다.
- 코너 식별자와 물리량, 실제 관측과 보정 미리보기, 가상 검증과 실측 정확도를 구분한다. 측정값을 보기 좋게 바꾸지 않는다.
