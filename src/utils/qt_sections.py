"""Compact disclosure and file identity controls for the desktop workflow."""
import os

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QMenu, QSizePolicy, QToolButton, QVBoxLayout, QWidget


class CollapsibleSection(QWidget):
    def __init__(self, title, content_widget, expanded=False, parent=None):
        super().__init__(parent)
        self.content = content_widget
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        self.button = QToolButton()
        self.button.setText(title)
        self.button.setCheckable(True)
        self.button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.button.toggled.connect(self.setExpanded)
        layout.addWidget(self.button)
        layout.addWidget(self.content)
        self.setExpanded(expanded)

    def setExpanded(self, expanded):
        self.button.setChecked(expanded)
        self.button.setArrowType(Qt.ArrowType.DownArrow if expanded else Qt.ArrowType.RightArrow)
        self.content.setVisible(expanded)


def set_path_label(label, path, empty='No file'):
    """Show the filename; retain the full path for inspection and copying."""
    path = os.fspath(path) if path else ''
    label.setTextFormat(Qt.TextFormat.PlainText)
    label.setText(os.path.basename(path) if path else empty)
    label.setToolTip(path)
    label.setProperty('fullPath', path)
    label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
    label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse
                                 | Qt.TextInteractionFlag.TextSelectableByKeyboard)
    if not label.property('pathMenuConnected'):
        label.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)

        def show_menu(position):
            menu = QMenu(label)
            action = menu.addAction('Copy path')
            action.setEnabled(bool(label.property('fullPath')))
            if menu.exec(label.mapToGlobal(position)) is action:
                QApplication.clipboard().setText(label.property('fullPath'))

        label.customContextMenuRequested.connect(show_menu)
        label.setProperty('pathMenuConnected', True)
