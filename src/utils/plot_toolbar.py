"""Localized labels for the standard Matplotlib Qt toolbar."""

from matplotlib.backends.backend_qtagg import NavigationToolbar2QT
from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWidgets import QSizePolicy, QToolButton

from src.utils.ui_language import active_language, tr


class PlotToolbar(NavigationToolbar2QT):
    coordinate_message = Signal(str)

    def __init__(self, canvas, parent=None, coordinates=True, *, vertical=False):
        super().__init__(canvas, parent, coordinates=coordinates and not vertical)
        if vertical:
            self.setOrientation(Qt.Orientation.Vertical)
            self.setAllowedAreas(Qt.ToolBarArea.LeftToolBarArea | Qt.ToolBarArea.RightToolBarArea)
            self.setIconSize(QSize(16, 16))
            self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
            self.setFixedWidth(max(34, self.sizeHint().width()))
        for action in self.actions():
            if action.isSeparator():
                continue
            button = self.widgetForAction(action)
            if isinstance(button, QToolButton):
                button.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
            if active_language() == 'ko':
                label = action.text()
                # The marker editor uses "Back" to name a face.
                action.setText(tr('Previous view' if label == 'Back' else label))
                action.setToolTip(tr(action.toolTip()))

    def set_message(self, message):
        super().set_message(message)
        self.coordinate_message.emit(message)
