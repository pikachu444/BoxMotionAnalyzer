from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFrame,
    QGridLayout,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from src.config.result_metric_descriptors import (
    DropPostureVisualGuide,
    ResultMetricDescriptor,
)


class DropPostureGuideDiagram(QFrame):
    def __init__(self, guide_id: DropPostureVisualGuide, parent=None):
        super().__init__(parent)
        self.guide_id = guide_id
        self.setFrameStyle(QFrame.Shape.StyledPanel)
        self.setMinimumSize(150, 96)

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor("#ffffff"))

        floor_pen = QPen(QColor("#5b6470"), 2)
        accent_pen = QPen(QColor("#2563eb"), 2)
        box_pen = QPen(QColor("#1f2937"), 2)
        fill_color = QColor(37, 99, 235, 42)

        w = self.width()
        h = self.height()
        floor_y = int(h * 0.74)
        painter.setPen(floor_pen)
        painter.drawLine(14, floor_y, w - 14, floor_y)

        if self.guide_id in {
            DropPostureVisualGuide.BETA,
            DropPostureVisualGuide.THETA,
            DropPostureVisualGuide.DELTA_H,
            DropPostureVisualGuide.CMIN,
            DropPostureVisualGuide.REFERENCE_FACE,
        }:
            tilted = [
                QPointF(w * 0.22, h * 0.56),
                QPointF(w * 0.72, h * 0.38),
                QPointF(w * 0.82, h * 0.58),
                QPointF(w * 0.32, h * 0.76),
            ]
            painter.setPen(box_pen)
            painter.setBrush(fill_color)
            painter.drawPolygon(tilted)

            if self.guide_id == DropPostureVisualGuide.BETA:
                painter.setPen(accent_pen)
                painter.drawArc(QRectF(w * 0.22, h * 0.45, 58, 46), 0, 42 * 16)
                painter.drawText(QRectF(w * 0.28, h * 0.44, 48, 22), Qt.AlignCenter, "Beta")
            elif self.guide_id == DropPostureVisualGuide.THETA:
                painter.setPen(accent_pen)
                painter.drawLine(QPointF(w * 0.31, h * 0.69), QPointF(w * 0.72, h * 0.45))
                painter.drawLine(QPointF(w * 0.64, h * 0.43), QPointF(w * 0.72, h * 0.45))
                painter.drawLine(QPointF(w * 0.68, h * 0.52), QPointF(w * 0.72, h * 0.45))
                painter.drawText(QRectF(w * 0.32, h * 0.30, 70, 22), Qt.AlignCenter, "Long/Short")
            elif self.guide_id == DropPostureVisualGuide.DELTA_H:
                painter.setPen(accent_pen)
                x = int(w * 0.84)
                y1 = int(h * 0.38)
                y2 = int(h * 0.76)
                painter.drawLine(x, y1, x, y2)
                painter.drawLine(x - 7, y1, x + 7, y1)
                painter.drawLine(x - 7, y2, x + 7, y2)
                painter.drawText(QRectF(x - 44, y1 + 8, 42, 22), Qt.AlignRight, "DeltaH")
            elif self.guide_id == DropPostureVisualGuide.CMIN:
                painter.setPen(accent_pen)
                painter.setBrush(QColor("#ef4444"))
                painter.drawEllipse(QPointF(w * 0.32, h * 0.76), 5, 5)
                painter.drawText(QRectF(w * 0.20, h * 0.78, 48, 18), Qt.AlignCenter, "Cmin")
            else:
                painter.setPen(accent_pen)
                painter.drawText(QRectF(0, 8, w, 22), Qt.AlignCenter, "Reference face")
            return

        if self.guide_id == DropPostureVisualGuide.TIMING:
            painter.setPen(accent_pen)
            y = int(h * 0.48)
            x1 = int(w * 0.18)
            x2 = int(w * 0.78)
            painter.drawLine(x1, y, x2, y)
            painter.drawLine(x2 - 8, y - 6, x2, y)
            painter.drawLine(x2 - 8, y + 6, x2, y)
            painter.drawLine(int(w * 0.54), y - 18, int(w * 0.54), y + 18)
            painter.drawLine(int(w * 0.66), y - 18, int(w * 0.66), y + 18)
            painter.drawText(QRectF(w * 0.43, y + 18, 48, 20), Qt.AlignCenter, "t1-")
            painter.drawText(QRectF(w * 0.58, y + 18, 62, 20), Qt.AlignCenter, "impact")
            return

        if self.guide_id == DropPostureVisualGuide.IMPACT_SEQUENCE:
            painter.setPen(accent_pen)
            labels = ["C2", "C3", "C5"]
            for idx, label in enumerate(labels):
                x = int(w * (0.22 + idx * 0.26))
                painter.drawEllipse(QPointF(x, h * 0.48), 16, 16)
                painter.drawText(QRectF(x - 16, h * 0.48 - 10, 32, 20), Qt.AlignCenter, label)
                if idx < len(labels) - 1:
                    painter.drawLine(x + 18, int(h * 0.48), int(w * (0.22 + (idx + 1) * 0.26)) - 18, int(h * 0.48))
            return

        painter.setPen(accent_pen)
        painter.drawText(QRectF(0, 16, w, 24), Qt.AlignCenter, "Contact")
        painter.drawText(QRectF(0, 44, w, 24), Qt.AlignCenter, "evidence")


class DropPostureMetricGuideDialog(QDialog):
    def __init__(self, descriptors: tuple[ResultMetricDescriptor, ...], parent=None):
        super().__init__(parent)
        self.setWindowTitle("Drop Posture Metric Guide")
        self.resize(760, 560)

        root_layout = QVBoxLayout(self)
        intro = QLabel(
            "Drop Posture metrics describe the selected experiment's posture and contact summary. "
            "The same descriptor metadata drives this guide, summary table labels, and tooltips."
        )
        intro.setWordWrap(True)
        root_layout.addWidget(intro)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        grid = QGridLayout(content)
        grid.setColumnStretch(1, 1)

        current_row = 0
        current_group = None
        for descriptor in descriptors:
            if descriptor.group != current_group:
                current_group = descriptor.group
                group_label = QLabel(current_group.value)
                group_label.setStyleSheet("font-weight: 600; margin-top: 8px;")
                grid.addWidget(group_label, current_row, 0, 1, 2)
                current_row += 1

            diagram = DropPostureGuideDiagram(descriptor.visual_guide)
            grid.addWidget(diagram, current_row, 0)

            text = QLabel(
                f"<b>{descriptor.display_name}</b>"
                f"{f' ({descriptor.unit})' if descriptor.unit else ''}<br>"
                f"{descriptor.long_description}"
            )
            text.setWordWrap(True)
            text.setTextFormat(Qt.TextFormat.RichText)
            grid.addWidget(text, current_row, 1)
            current_row += 1

        scroll.setWidget(content)
        root_layout.addWidget(scroll)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        root_layout.addWidget(buttons)
