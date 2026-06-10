from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QTableWidget, QTableWidgetItem, QHeaderView, QListWidget, QComboBox, QSplitter,
    QGroupBox, QFrame
)
from PySide6.QtCore import Qt, Signal
import matplotlib.pyplot as plt
from matplotlib.figure import Figure
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
import pandas as pd

from src.config.result_metric_descriptors import METRIC_DESCRIPTORS
from src.analysis.ui.plot_manager import PlotManager

class CompareTablePanel(QGroupBox):
    """Displays differences in Drop Posture Summary metrics."""
    def __init__(self):
        super().__init__("Comparison Summary")
        layout = QVBoxLayout(self)
        
        self.table = QTableWidget()
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        layout.addWidget(self.table)

    def update_table(self, diff_data: dict[str, dict], baseline_name: str):
        if not diff_data:
            self.table.clear()
            self.table.setRowCount(0)
            self.table.setColumnCount(0)
            return

        datasets = list(diff_data.keys())
        if not datasets:
            return
            
        metrics = list(diff_data[datasets[0]]["summary"].keys())
        
        self.table.setRowCount(len(metrics))
        self.table.setColumnCount(len(datasets) + 1)
        self.table.setHorizontalHeaderLabels(["Property"] + datasets)
        
        for r, metric in enumerate(metrics):
            desc = METRIC_DESCRIPTORS.get(metric, {})
            label = desc.get("display_name", metric)
            unit = desc.get("unit", "")
            if unit:
                label += f" ({unit})"
                
            prop_item = QTableWidgetItem(label)
            tooltip = desc.get("tooltip", "")
            if tooltip:
                prop_item.setToolTip(tooltip)
                
            self.table.setItem(r, 0, prop_item)

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
                self.table.setItem(r, c + 1, item)
                
        self.table.resizeColumnsToContents()

class CompareGraphPanel(QGroupBox):
    """Displays overlaid time-series metrics from multiple files using PlotManager."""
    plot_target_changed = Signal(str)

    def __init__(self):
        super().__init__("Time-History Overlay")
        layout = QVBoxLayout(self)
        
        target_layout = QHBoxLayout()
        target_layout.addWidget(QLabel("Plot Target:"))
        self.cb_plot_target = QComboBox()
        self.cb_plot_target.currentTextChanged.connect(self.plot_target_changed.emit)
        target_layout.addWidget(self.cb_plot_target)
        target_layout.addStretch()
        layout.addLayout(target_layout)
        
        self.fig = Figure(figsize=(5, 3), dpi=100)
        self.canvas = FigureCanvas(self.fig)
        self.plot_manager = PlotManager(self.canvas, self.fig)
        layout.addWidget(self.canvas)

    def set_plot_targets(self, targets: list[str]):
        current = self.cb_plot_target.currentText()
        self.cb_plot_target.blockSignals(True)
        self.cb_plot_target.clear()
        self.cb_plot_target.addItems(targets)
        if current in targets:
            self.cb_plot_target.setCurrentText(current)
        elif targets:
            self.cb_plot_target.setCurrentIndex(0)
            self.cb_plot_target.blockSignals(False)
            self.plot_target_changed.emit(self.cb_plot_target.currentText())
            return
        self.cb_plot_target.blockSignals(False)

    def update_plot(self, series_dict: dict, metric_name: str):
        self.plot_manager.clear_plot()
        
        if not series_dict:
            self.plot_manager.ax.set_title("No Data to Plot", color="red")
            self.canvas.draw()
            return
            
        df = pd.DataFrame(series_dict)
        columns_to_plot = list(series_dict.keys())
        
        self.plot_manager.draw_plot(df, columns_to_plot)
        self.plot_manager.ax.set_ylabel(metric_name)
        self.plot_manager.enable_interactions(df)
        self.canvas.draw()

class CompareControlPanel(QFrame):
    """Controls for file selection, baseline designation."""
    add_files_requested = Signal()
    remove_file_requested = Signal(str)
    baseline_changed = Signal(str)

    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        
        # Files List
        self.file_list = QListWidget()
        layout.addWidget(QLabel("Loaded Files:"))
        layout.addWidget(self.file_list)
        
        btn_layout = QHBoxLayout()
        self.btn_add_files = QPushButton("Load .proc files...")
        self.btn_add_files.clicked.connect(self.add_files_requested.emit)
        self.btn_remove_file = QPushButton("Remove Selected")
        self.btn_remove_file.clicked.connect(self._on_remove_clicked)
        btn_layout.addWidget(self.btn_add_files)
        btn_layout.addWidget(self.btn_remove_file)
        layout.addLayout(btn_layout)
        
        # Baseline selector
        layout.addWidget(QLabel("Baseline Experiment:"))
        self.cb_baseline = QComboBox()
        self.cb_baseline.currentTextChanged.connect(self.baseline_changed.emit)
        layout.addWidget(self.cb_baseline)
        
        layout.addStretch()

    def _on_remove_clicked(self):
        selected = self.file_list.currentItem()
        if selected:
            self.remove_file_requested.emit(selected.text())

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
