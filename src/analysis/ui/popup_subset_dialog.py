from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QListWidget,
    QListWidgetItem,
    QDialogButtonBox,
    QLabel,
)


class PopupSubsetDialog(QDialog):
    def __init__(self, columns: list[tuple], preselected: list[tuple], parent=None):
        super().__init__(parent)
        self.setWindowTitle("Select Popup Subset")
        self.resize(450, 500)
        self._column_map: dict[str, tuple] = {}

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Choose columns for the popup plot:"))

        self.list_widget = QListWidget()
        layout.addWidget(self.list_widget)

        preselected_set = set(preselected)
        for col in columns:
            label = f"{col[0]}/{col[1]}/{col[2]}"
            self._column_map[label] = col

            item = QListWidgetItem(label)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Checked if col in preselected_set else Qt.Unchecked)
            self.list_widget.addItem(item)

        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def get_selected_columns(self) -> list[tuple]:
        selected: list[tuple] = []
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            if item.checkState() == Qt.Checked:
                selected.append(self._column_map[item.text()])
        return selected
