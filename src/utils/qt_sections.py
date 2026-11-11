"""Compact file identity controls for the desktop workflow."""
import os
from pathlib import PurePath

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QLabel, QMenu, QSizePolicy
from src.utils.ui_language import tr


def find_result_column_index(combo, column):
    """Compare column values across Qt's tuple/list UserRole representations."""
    if not isinstance(column, (tuple, list)) or len(column) != 3:
        return -1
    key = tuple(column)
    for index in range(combo.count()):
        value = combo.itemData(index)
        if isinstance(value, (tuple, list)) and tuple(value) == key:
            return index
    return -1


class ElidedPathLabel(QLabel):
    def __init__(self, text='', parent=None):
        super().__init__(parent)
        self._path_text = text
        self.setWordWrap(False)
        self.setText(text)

    def setText(self, text):
        self._path_text = text
        super().setText(self.fontMetrics().elidedText(text, Qt.TextElideMode.ElideMiddle,
                                                    max(1, self.width() - 4)))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.setText(self._path_text)


def unique_path_labels(paths):
    """Return the shortest parent suffix that distinguishes each file path."""
    paths = [os.fspath(path) for path in paths]
    parts = [PurePath(path).parts for path in paths]
    identities = [os.path.normcase(os.path.normpath(path)) for path in paths]
    labels = []
    for index, path_parts in enumerate(parts):
        for count in range(1, len(path_parts) + 1):
            suffix = os.path.join(*path_parts[-count:])
            if all(identities[index] == identities[other]
                   or os.path.normcase(suffix) != os.path.normcase(
                       os.path.join(*other_parts[-count:]) if other_parts else paths[other])
                   for other, other_parts in enumerate(parts)):
                break
        labels.append(suffix if path_parts else paths[index])
    return labels


def set_path_label(label, path, empty='No file', *, display_name=None):
    """Show the filename; retain the full path for inspection and copying."""
    path = os.fspath(path) if path else ''
    label.setTextFormat(Qt.TextFormat.PlainText)
    label.setText((display_name if display_name is not None else os.path.basename(path))
                  if path else tr(empty))
    label.setToolTip(path)
    label.setProperty('fullPath', path)
    label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
    label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse
                                 | Qt.TextInteractionFlag.TextSelectableByKeyboard)
    if not label.property('pathMenuConnected'):
        label.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)

        def show_menu(position):
            menu = QMenu(label)
            action = menu.addAction(tr('Copy path'))
            action.setEnabled(bool(label.property('fullPath')))
            if menu.exec(label.mapToGlobal(position)) is action:
                QApplication.clipboard().setText(label.property('fullPath'))

        label.customContextMenuRequested.connect(show_menu)
        label.setProperty('pathMenuConnected', True)
