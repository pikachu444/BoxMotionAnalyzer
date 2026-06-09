import os
from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from src.config.result_metric_descriptors import (
    DropPostureSummaryGroup,
    ResultMetricDescriptor,
)


class DropPostureMetricGuideDialog(QDialog):
    def __init__(self, descriptors: tuple[ResultMetricDescriptor, ...], parent=None):
        super().__init__(parent)
        self.setWindowTitle("Drop Posture Metric Guide")
        self.resize(800, 600)

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
        main_layout = QVBoxLayout(content)

        groups = {}
        for descriptor in descriptors:
            if descriptor.group not in groups:
                groups[descriptor.group] = []
            groups[descriptor.group].append(descriptor)

        assets_dir = os.path.join(os.path.dirname(__file__), "assets")

        for group, group_descriptors in groups.items():
            group_layout = QVBoxLayout()
            group_label = QLabel(group.value)
            group_label.setStyleSheet("font-size: 16px; font-weight: 600; margin-top: 12px; margin-bottom: 8px;")
            group_layout.addWidget(group_label)

            image_name_map = {
                DropPostureSummaryGroup.POSTURE: "guide_posture.png",
                DropPostureSummaryGroup.IMPACT: "guide_impact.png",
                DropPostureSummaryGroup.CONTACT: "guide_contact.png",
            }
            image_name = image_name_map.get(group)
            if image_name:
                image_path = os.path.join(assets_dir, image_name)
                img_label = QLabel()
                pixmap = QPixmap(image_path)
                if not pixmap.isNull():
                    img_label.setPixmap(pixmap.scaledToWidth(600, Qt.TransformationMode.SmoothTransformation))
                    img_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                else:
                    img_label.setText(f"[Image not found: {image_name}]")
                    img_label.setStyleSheet("color: red;")
                group_layout.addWidget(img_label)

            for descriptor in group_descriptors:
                text = QLabel(
                    f"<b>{descriptor.display_name}</b>"
                    f"{f' ({descriptor.unit})' if descriptor.unit else ''}<br>"
                    f"{descriptor.long_description}"
                )
                text.setWordWrap(True)
                text.setTextFormat(Qt.TextFormat.RichText)
                text.setStyleSheet("margin-top: 4px; margin-bottom: 4px; padding-left: 10px;")
                group_layout.addWidget(text)

            main_layout.addLayout(group_layout)

        main_layout.addStretch()
        scroll.setWidget(content)
        root_layout.addWidget(scroll)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        root_layout.addWidget(buttons)
