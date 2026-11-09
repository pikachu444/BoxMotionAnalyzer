"""Compact help assembled from the comparison's existing metric definitions."""
from html import escape

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QDialog, QDialogButtonBox, QTabWidget, QTextBrowser, QVBoxLayout

from src.analysis.compare.impact_metrics import METRICS
from src.analysis.compare.posture_metrics import POSTURE_METRICS
from src.config.result_metric_descriptors import get_drop_posture_summary_descriptors
from src.utils.ui_language import active_language, tr


READING_GUIDE = """
<h3>Reading the comparison</h3>
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


def metric_entries():
    entries = [(key, descriptor['label'], descriptor['unit'], descriptor['tooltip'])
               for group in (METRICS, POSTURE_METRICS) for key, descriptor in group.items()]
    covered = {d['column'] for d in POSTURE_METRICS.values()} | {'FirstImpactContact', 'FinalFace', 'ContactConfidence'}
    entries.extend(('summary:' + d.column[2], d.display_name, d.unit, d.long_description)
                   for d in get_drop_posture_summary_descriptors() if d.column[2] not in covered)
    return entries


def guide_key_for_summary(field):
    for key, descriptor in POSTURE_METRICS.items():
        if descriptor['column'] == field:
            return key
    return {'FirstImpactContact': 'first_contact', 'FinalFace': 'final_face',
            'ContactConfidence': 'contact_confidence'}.get(field, 'summary:' + field)


class MetricGuideDialog(QDialog):
    def __init__(self, parent=None, selected_key=None):
        super().__init__(parent)
        self.setWindowTitle(tr('Metric guide'))
        self.resize(660, 540)
        self.setMinimumSize(420, 320)
        layout = QVBoxLayout(self)
        self.tabs = QTabWidget()
        self.reading = QTextBrowser()
        self.reading.setHtml(READING_GUIDE_KO if active_language() == 'ko' else READING_GUIDE)
        self.metrics = QTextBrowser()
        entries = metric_entries()
        self.metrics.setHtml(''.join(
            f'<h3 id="{escape(key)}">{escape(tr(name))}{escape(" (" + unit + ")" if unit else "")}</h3>'
            f'<p>{escape(tr(description))}</p>' for key, name, unit, description in entries))
        self.tabs.addTab(self.reading, tr('Reading the table'))
        self.tabs.addTab(self.metrics, tr('Metrics'))
        layout.addWidget(self.tabs)
        self.buttons = QDialogButtonBox(QDialogButtonBox.Close)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)
        if selected_key in {key for key, *_ in entries}:
            self.tabs.setCurrentIndex(1)
            QTimer.singleShot(0, lambda: self.metrics.scrollToAnchor(selected_key))
