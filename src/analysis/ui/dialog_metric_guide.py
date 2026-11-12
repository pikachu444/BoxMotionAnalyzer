"""Step 2 compatibility entry point for the shared metric guide."""
from src.analysis.ui.shared_metric_guide import SharedMetricGuideDialog


class DropPostureMetricGuideDialog(SharedMetricGuideDialog):
    def __init__(self, descriptors, parent=None):
        super().__init__(parent)
