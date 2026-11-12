"""Comparison compatibility entry points for the shared metric guide."""
from src.analysis.compare.impact_metrics import METRICS
from src.analysis.compare.posture_metrics import POSTURE_METRICS
from src.config.result_metric_descriptors import get_drop_posture_summary_descriptors, get_metric_registry
from src.config.metric_interpretation import READING_GUIDE, READING_GUIDE_KO
from src.analysis.ui.shared_metric_guide import SharedMetricGuideDialog


def metric_entries():
    return [(entry.source_key, entry.display_name, entry.unit, entry.long_description)
            for entry in get_metric_registry() if entry.context == 'compare']


def guide_key_for_summary(field):
    for key, descriptor in POSTURE_METRICS.items():
        if descriptor['column'] == field:
            return key
    return {'FirstImpactContact': 'first_contact', 'FinalFace': 'final_face',
            'ContactConfidence': 'contact_confidence'}.get(field, 'summary:' + field)



class MetricGuideDialog(SharedMetricGuideDialog):
    pass
