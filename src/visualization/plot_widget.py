from PySide6.QtWidgets import QWidget, QVBoxLayout, QFrame
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from PySide6.QtCore import Signal

class PlotWidget(QWidget):
    doubleClicked = Signal()
    DEFAULT_Y_AXIS_LABEL = "Value"

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_plot_args = []
        self.y_axis_label = self.DEFAULT_Y_AXIS_LABEL

        # --- Create a frame to provide a border ---
        frame = QFrame(self)
        frame.setFrameShape(QFrame.StyledPanel)
        frame.setFrameShadow(QFrame.Sunken)

        # Main layout for this widget
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(frame)

        # Layout for the contents of the frame
        frame_layout = QVBoxLayout(frame)
        frame_layout.setContentsMargins(0, 0, 0, 0)
        self.canvas = FigureCanvas(Figure(figsize=(5, 3)))
        frame_layout.addWidget(self.canvas)

        self.ax = self.canvas.figure.subplots()

        self.canvas.mouseDoubleClickEvent = self.on_double_click

    def plot_multiple_data(self, plot_args: list[dict], y_axis_label: str = "Value"):
        """Plots multiple lines on the same graph and stores the data for the popup."""
        self.current_plot_args = plot_args
        self.y_axis_label = self.DEFAULT_Y_AXIS_LABEL

        self.ax.clear()

        for args in plot_args:
            self.ax.plot(args["x"], args["y"], label=args["label"])

        self.ax.set_title("")
        self.ax.set_xlabel("Time (s)")
        self.ax.set_ylabel(self.DEFAULT_Y_AXIS_LABEL)

        if plot_args:
            self.ax.legend()

        self.ax.grid(True)
        self._refresh_layout()

    def on_double_click(self, event):
        """Emits a signal when the canvas is double-clicked."""
        self.doubleClicked.emit()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._refresh_layout()

    def _refresh_layout(self):
        self.canvas.figure.tight_layout()
        self.canvas.draw_idle()
