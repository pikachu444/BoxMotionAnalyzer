from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QTableWidget, QTableWidgetItem, QHeaderView, QListWidget, QComboBox, QSplitter
)
from PySide6.QtCore import Qt, Signal
import matplotlib.pyplot as plt
from matplotlib.figure import Figure
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas

class CompareTablePanel(QWidget):
    """Displays differences in Drop Posture Summary metrics."""
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        lbl = QLabel("Drop/Impact Summary Differences (vs Baseline)")
        lbl.setStyleSheet("font-weight: bold; font-size: 14px;")
        layout.addWidget(lbl)
        
        self.table = QTableWidget()
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        layout.addWidget(self.table)

    def update_table(self, diff_data: dict[str, dict], baseline_name: str):
        if not diff_data:
            self.table.clear()
            self.table.setRowCount(0)
            self.table.setColumnCount(0)
            return

        # Prepare rows (metrics) and columns (datasets)
        datasets = list(diff_data.keys())
        if not datasets:
            return
            
        metrics = list(diff_data[datasets[0]]["summary"].keys())
        
        self.table.setRowCount(len(metrics))
        self.table.setColumnCount(len(datasets))
        self.table.setHorizontalHeaderLabels(datasets)
        self.table.setVerticalHeaderLabels(metrics)

        for c, ds_name in enumerate(datasets):
            ds_info = diff_data[ds_name]
            is_baseline = (ds_name == baseline_name)
            
            for r, metric in enumerate(metrics):
                val = ds_info["summary"].get(metric, "N/A")
                diff = ds_info["diffs"].get(metric, None)
                
                if is_baseline:
                    display_text = f"{val}"
                else:
                    if isinstance(diff, (int, float)):
                        display_text = f"{val} ({diff:+.2f})"
                    else:
                        display_text = f"{val} (vs {diff})" if diff != "Match" else f"{val}"
                        
                item = QTableWidgetItem(display_text)
                item.setTextAlignment(Qt.AlignCenter)
                self.table.setItem(r, c, item)
                
        self.table.resizeColumnsToContents()

class CompareGraphPanel(QWidget):
    """Displays overlaid time-series metrics from multiple files."""
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        lbl = QLabel("Time-History Overlay")
        lbl.setStyleSheet("font-weight: bold; font-size: 14px;")
        layout.addWidget(lbl)
        
        self.fig = Figure(figsize=(5, 3), dpi=100)
        self.canvas = FigureCanvas(self.fig)
        self.ax = self.fig.add_subplot(111)
        layout.addWidget(self.canvas)

    def update_plot(self, series_dict: dict, metric_name: str):
        self.ax.clear()
        
        if not series_dict:
            self.ax.set_title("No Data to Plot", color="red")
            self.canvas.draw()
            return
            
        colors = plt.get_cmap('tab10').colors
        
        for i, (name, series) in enumerate(series_dict.items()):
            color = colors[i % len(colors)]
            self.ax.plot(series.index.values, series.values, label=name, color=color)
            
        self.ax.set_xlabel("Time (s)")
        self.ax.set_ylabel(metric_name)
        self.ax.grid(True)
        self.ax.legend()
        self.fig.tight_layout()
        self.canvas.draw()

class CompareControlPanel(QWidget):
    """Controls for file selection, baseline designation, and plotting target."""
    add_files_requested = Signal()
    baseline_changed = Signal(str)
    plot_target_changed = Signal(str)

    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        
        # Files List
        self.file_list = QListWidget()
        layout.addWidget(QLabel("Loaded Files:"))
        layout.addWidget(self.file_list)
        
        self.btn_add_files = QPushButton("Load .proc files...")
        self.btn_add_files.clicked.connect(self.add_files_requested.emit)
        layout.addWidget(self.btn_add_files)
        
        # Baseline selector
        layout.addWidget(QLabel("Baseline Experiment:"))
        self.cb_baseline = QComboBox()
        self.cb_baseline.currentTextChanged.connect(self.baseline_changed.emit)
        layout.addWidget(self.cb_baseline)
        
        # Plot target selector
        layout.addWidget(QLabel("Plot Target:"))
        self.cb_plot_target = QComboBox()
        self.cb_plot_target.currentTextChanged.connect(self.plot_target_changed.emit)
        layout.addWidget(self.cb_plot_target)
        
        layout.addStretch()

    def update_files(self, file_names: list[str], baseline: str):
        # Update List
        self.file_list.clear()
        self.file_list.addItems(file_names)
        
        # Update Baseline Combo Box without triggering signal
        self.cb_baseline.blockSignals(True)
        self.cb_baseline.clear()
        self.cb_baseline.addItems(file_names)
        if baseline in file_names:
            self.cb_baseline.setCurrentText(baseline)
        self.cb_baseline.blockSignals(False)

    def set_plot_targets(self, targets: list[str]):
        current = self.cb_plot_target.currentText()
        self.cb_plot_target.blockSignals(True)
        self.cb_plot_target.clear()
        self.cb_plot_target.addItems(targets)
        if current in targets:
            self.cb_plot_target.setCurrentText(current)
        elif targets:
            self.cb_plot_target.setCurrentIndex(0)
            # Re-emit manually to render first target
            self.cb_plot_target.blockSignals(False)
            self.plot_target_changed.emit(self.cb_plot_target.currentText())
            return
        self.cb_plot_target.blockSignals(False)
