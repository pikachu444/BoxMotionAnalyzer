"""Compact help assembled from the comparison's existing metric definitions."""
from html import escape

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QDialog, QDialogButtonBox, QTabWidget, QTextBrowser, QVBoxLayout

from src.analysis.compare.impact_metrics import METRICS
from src.analysis.compare.posture_metrics import POSTURE_METRICS
from src.config.result_metric_descriptors import get_drop_posture_summary_descriptors


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
        self.setWindowTitle('Metric guide')
        self.resize(660, 540)
        self.setMinimumSize(420, 320)
        layout = QVBoxLayout(self)
        self.tabs = QTabWidget()
        self.reading = QTextBrowser()
        self.reading.setHtml(READING_GUIDE)
        self.metrics = QTextBrowser()
        entries = metric_entries()
        self.metrics.setHtml(''.join(
            f'<h3 id="{escape(key)}">{escape(name)}{escape(" (" + unit + ")" if unit else "")}</h3>'
            f'<p>{escape(description)}</p>' for key, name, unit, description in entries))
        self.tabs.addTab(self.reading, 'Reading the table')
        self.tabs.addTab(self.metrics, 'Metrics')
        layout.addWidget(self.tabs)
        self.buttons = QDialogButtonBox(QDialogButtonBox.Close)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)
        if selected_key in {key for key, *_ in entries}:
            self.tabs.setCurrentIndex(1)
            QTimer.singleShot(0, lambda: self.metrics.scrollToAnchor(selected_key))
