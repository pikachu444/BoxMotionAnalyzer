"""Shared reading guidance for recorded result contexts."""
READING_GUIDE = """
<h3>Reading the comparison</h3>
<p><b>Detector versus accepted contact.</b> The detector's onset and the first accepted contact set lasting at least two samples can differ. The prior t1- sample must actually exist; a first-row onset supplies none. Existing comparison checks can reject inconsistent saved event brackets without rewriting timestamps.</p>
<p><b>Saved samples versus fits.</b> Step 2 saved geometric-centre derivatives use mm/s at a recorded sample. The ideal geometric speed-equivalent height uses g=9810 mm/s² under its approved scenario gates. The separate comparison height uses a one-sided quadratic fit to an explicitly registered inertial COM position path, g=9.80665 m/s², and already returns mm. Identical units or zero COM offset do not make method and time identical.</p>
<p><b>Baseline</b> identifies the reference file. Changing it does not choose an
authoritative reprocessing or change the selected file. Match baseline counts
agreement with that category, not with the intended contact.</p>
<p><b>Time and position.</b> Pre-contact is the recorded last sample before the
first impact. Whole-window values cover the complete processed interval and
require equivalent windows for repeats. Historical CoM position columns refer
to the box geometric centre. Velocity-equivalent height uses an explicitly
registered inertial COM offset; it is not release height.</p>
<p><b>Units.</b> Position and height are mm, time is seconds, comparison velocity
is m/s, angular speed is rad/s and posture angles are degrees. World Y is up.</p>
<p><b>Repeats.</b> n counts compatible, distinct trials for each metric. Copies
and reprocessings do not add trials. Invalid values and conflicting valid
variants are excluded per metric. Fewer than 3 is marked low; small spread is
not a pass criterion. Corner IDs and contact sequences use category counts.</p>
<p><b>Unavailable and excluded.</b> A missing value lacks supported evidence.
An individual value may still be excluded from repeats because its conditions,
reference face or window differ. Hover over the value or n, or open Details for
the reason. Overlaid curves do not establish compatible repeated trials.</p>
<p><b>Interpretation.</b> Experimental estimates and Diagnostic geometry/contact
fields have not been independently calibrated against measured trials.
Contact confidence is an algorithm score, not a probability. Contact compares
independently recorded intent with an inferred feature; Different is not an
automatic ISTA failure. ReferenceFace is not FinalFace or a target angle.</p>
"""

READING_GUIDE_KO = """
<h3>비교표 읽기</h3>
<p><b>검출과 인정 접촉.</b> 검출기 시작과 두 표본 이상 지속되는 첫 인정 접촉 시각은 다를 수 있습니다. t1-는 실제 앞선 표본이 있어야 하며 첫 행에서 시작하면 만들지 않습니다. 기존 비교 검증이 기록 시각의 모순을 거절해도 원본 시각은 고치지 않습니다.</p>
<p><b>저장 표본과 fit.</b> Step 2 기하중심 저장 미분은 실제 표본의 mm/s 값입니다. 이상적 기하중심 환산높이는 승인된 시나리오에서 중력9810 mm/s²를 사용합니다. 별도 비교 환산높이는 명시적으로 등록한 관성 질량중심 위치 경로의 편측2차 fit과 중력9.80665 m/s²를 사용하며 이미mm입니다. 단위가 같거나 COM 오프셋이0이어도 방식·시각은 다릅니다.</p>
<p><b>기준.</b> 기준 파일을 지정합니다. 바꿔도 대표 재처리 결과나 선택한 파일은 그대로입니다.
기준 일치는 기준 범주와의 일치를 세며 시험에서 의도한 접촉과는 별개입니다.</p>
<p><b>시간과 위치.</b> 접촉 전은 첫 충격 직전에 기록된 마지막 샘플입니다.
전체 구간 값은 처리한 구간 전체를 포함하며 반복 시험을 비교할 때는 구간이 같아야 합니다.
과거 CoM 위치 열은 상자의 기하학적 중심을 뜻합니다. 속도 환산 높이는 등록한 관성 질량 중심
오프셋을 사용하며 방출 높이와는 별개입니다.</p>
<p><b>단위.</b> 위치와 높이는 mm, 시간은 초, 비교 속도는 m/s, 각속력은 rad/s, 자세 각도는 도입니다.
월드 Y축은 위쪽입니다.</p>
<p><b>반복 시험.</b> n은 지표별로 호환되는 개별 시험 수입니다. 복사본과 재처리 결과는 시험 수를 늘리지 않습니다.
무효 값과 서로 충돌하는 결과는 지표별로 제외합니다. 3개 미만은 적음으로 표시하며 작은 산포를 합격 조건으로 쓰지 않습니다.
꼭짓점 ID와 접촉 순서는 범주별로 집계합니다.</p>
<p><b>사용 불가 및 제외.</b> 근거가 부족하면 값을 표시하지 않습니다.
개별 값이 있어도 조건, 기준 면 또는 시간 범위가 다르면 반복 집계에서 제외할 수 있습니다.
이유는 값이나 n에 포인터를 올리거나 상세 정보를 열어 확인하세요. 겹쳐 표시된 곡선만으로 호환성을 판단할 수 없습니다.</p>
<p><b>해석.</b> 실험적 추정과 진단 형상·접촉 값은 독립 실측 시험으로 교정되지 않았습니다.
접촉 신뢰도는 알고리즘 점수입니다. 접촉 비교는 독립 기록한 의도와 추정 특징을 비교하며 불일치만으로 ISTA 불합격을 판정하지 않습니다.
ReferenceFace는 FinalFace나 목표 각도와 별개입니다.</p>
"""
