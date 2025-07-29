from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QListWidget, QDialogButtonBox, QListWidgetItem
)

class DataSelectionDialog(QDialog):
    def __init__(self, all_items: list[str], selected_items: list[str], parent=None):
        super().__init__(parent)
        self.setWindowTitle("Select Data to Plot")
        self.resize(300, 400)

        self.list_widget = QListWidget()

        for item_text in all_items:
            item = QListWidgetItem(item_text)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            if item_text in selected_items:
                item.setCheckState(Qt.Checked)
            else:
                item.setCheckState(Qt.Unchecked)
            self.list_widget.addItem(item)

        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)

        layout = QVBoxLayout()
        layout.addWidget(self.list_widget)
        layout.addWidget(button_box)
        self.setLayout(layout)

    def get_selected_items(self) -> list[str]:
        """체크된 항목들의 텍스트 리스트를 반환합니다."""
        selected = []
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            if item.checkState() == Qt.Checked:
                selected.append(item.text())
        return selected
