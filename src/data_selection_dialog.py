from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QListWidget, QDialogButtonBox, QAbstractItemView
)

class DataSelectionDialog(QDialog):
    def __init__(self, all_items, selected_items, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Select Data to Plot")
        self.resize(300, 400)

        self.list_widget = QListWidget()
        self.list_widget.setSelectionMode(QAbstractItemView.SelectionMode.MultiSelection)
        self.list_widget.addItems(all_items)

        # 이전에 선택했던 항목들을 다시 선택 상태로 만듭니다.
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            if item.text() in selected_items:
                item.setSelected(True)

        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)

        layout = QVBoxLayout()
        layout.addWidget(self.list_widget)
        layout.addWidget(button_box)
        self.setLayout(layout)

    def get_selected_items(self):
        """선택된 항목들의 텍스트 리스트를 반환합니다."""
        return [item.text() for item in self.list_widget.selectedItems()]
