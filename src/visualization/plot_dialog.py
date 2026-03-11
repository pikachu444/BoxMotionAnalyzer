from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget, QVBoxLayout
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT, FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

class PlotDialog(QWidget):
    def __init__(self, plot_args: list[dict], y_axis_label: str, parent=None):
        super().__init__(parent)
        self.setWindowFlag(Qt.Window, True)
        self.setWindowModality(Qt.NonModal)
        self.setWindowTitle("Plot Details")
        self.setGeometry(200, 200, 800, 600)

        layout = QVBoxLayout(self)

        # Create a new FigureCanvas and Axes for the dialog
        self.canvas = FigureCanvas(Figure(figsize=(10, 8)))
        self.ax = self.canvas.figure.subplots()

        # Create the Matplotlib navigation toolbar
        self.toolbar = NavigationToolbar2QT(self.canvas, self)

        # Add widgets to the layout
        layout.addWidget(self.toolbar)
        layout.addWidget(self.canvas)

        # Plot the data directly on the dialog's axes
        self.plot_data(plot_args, y_axis_label)

        # --- Setup for hover annotations ---
        self.annot = self.ax.annotate(
            "", xy=(0,0), xytext=(-20,20),
            textcoords="offset points",
            bbox=dict(boxstyle="round", fc="w"),
            arrowprops=dict(arrowstyle="->")
        )
        self.annot.set_visible(False)
        self.canvas.mpl_connect("motion_notify_event", self.on_motion)

    def plot_data(self, plot_args: list[dict], y_axis_label: str):
        """A simplified plotting method for the dialog's own axes."""
        self.ax.clear()
        for args in plot_args:
            self.ax.plot(args["x"], args["y"], label=args["label"])
        self.ax.set_title(f"{y_axis_label} Timeseries (Detailed View)")
        self.ax.set_xlabel("Time (s)")
        self.ax.set_ylabel(y_axis_label)
        if len(plot_args) > 1:
            self.ax.legend()
        self.ax.grid(True)
        self.canvas.figure.tight_layout()
        self.canvas.draw()

    def on_motion(self, event):
        """Callback for mouse motion event to show data annotations."""
        # Check if the mouse is over the axes
        if event.inaxes != self.ax:
            self.annot.set_visible(False)
            self.canvas.draw_idle()
            return

        # Find the closest point on the plotted lines
        min_dist = float('inf')
        closest_artist = None

        for line in self.ax.get_lines():
            cont, ind = line.contains(event)
            if cont:
                # Get the distance to the mouse cursor
                x_data, y_data = line.get_data()
                point_index = ind['ind'][0]
                dist = (x_data[point_index] - event.xdata)**2 + (y_data[point_index] - event.ydata)**2

                if dist < min_dist:
                    min_dist = dist
                    closest_artist = {
                        "line": line,
                        "x": x_data[point_index],
                        "y": y_data[point_index]
                    }

        if closest_artist:
            # Update annotation text and position
            text = f"{closest_artist['line'].get_label()}: ({closest_artist['x']:.3f}, {closest_artist['y']:.2f})"
            self.annot.xy = (closest_artist['x'], closest_artist['y'])
            self.annot.set_text(text)
            self.annot.set_visible(True)
        else:
            self.annot.set_visible(False)

        self.canvas.draw_idle()
