"""Localized labels for the standard Matplotlib Qt toolbar."""

from matplotlib.backends.backend_qtagg import NavigationToolbar2QT

from src.utils.ui_language import active_language, tr


class PlotToolbar(NavigationToolbar2QT):
    def __init__(self, canvas, parent=None, coordinates=True):
        super().__init__(canvas, parent, coordinates=coordinates)
        if active_language() != 'ko':
            return
        for action in self.actions():
            if action.isSeparator():
                continue
            label = action.text()
            # The marker editor uses "Back" to name a face.
            action.setText(tr('Previous view' if label == 'Back' else label))
            action.setToolTip(tr(action.toolTip()))
