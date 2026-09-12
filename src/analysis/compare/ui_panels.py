from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QTableWidget, QTableWidgetItem, QHeaderView, QListWidget, QComboBox, QSplitter,
    QGroupBox, QFrame, QListWidgetItem, QPlainTextEdit, QDoubleSpinBox
)
from PySide6.QtCore import Qt, Signal, QSize
import matplotlib.pyplot as plt
from matplotlib.figure import Figure
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
import pandas as pd

from src.config.result_metric_descriptors import METRIC_DESCRIPTORS
from src.analysis.ui.plot_manager import PlotManager
from src.analysis.compare.impact_metrics import METRICS

SOURCE_LABELS = {'real': 'Real', 'mujoco_synthetic': 'MuJoCo',
                 'handcrafted_dummy': 'Constructed', 'public_external': 'Public',
                 'unknown_legacy': 'Unknown'}

class CompareTablePanel(QGroupBox):
    """Displays differences in Drop Posture Summary metrics."""
    def __init__(self):
        super().__init__("Experiment Summary")
        layout = QVBoxLayout(self)
        modes = QHBoxLayout()
        self.view_combo = QComboBox()
        self.view_combo.addItems(['Pre-contact (experimental)', 'Repeats (experimental)', 'Diagnostics'])
        modes.addWidget(self.view_combo)
        self.cohort_label = QLabel()
        modes.addWidget(self.cohort_label)
        modes.addStretch()
        layout.addLayout(modes)
        self._table_data = ({}, None, None)
        self.view_combo.currentIndexChanged.connect(self._render)
        
        self.table = QTableWidget()
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        layout.addWidget(self.table)

    def update_table(self, diff_data: dict[str, dict], baseline_name: str, impact=None):
        self._table_data = (diff_data, baseline_name, impact)
        self.view_combo.setVisible(impact is not None)
        self._render()

    def _render(self):
        diff_data, baseline_name, impact = self._table_data
        self.cohort_label.clear()
        if impact is None or self.view_combo.currentIndex() == 2:
            self._render_diagnostics(diff_data, baseline_name)
            return
        if self.view_combo.currentIndex() == 1 and impact['source']:
            self.cohort_label.setText('Source: ' + SOURCE_LABELS.get(impact['source'], 'Unknown'))
        self.table.clear()
        if not impact['files']:
            self.table.setRowCount(0)
            self.table.setColumnCount(0)
            return
        if self.view_combo.currentIndex() == 1:
            self._render_statistics(impact)
        else:
            self._render_motion(impact, diff_data)
        self.table.resizeColumnsToContents()
        for col in range(1, self.table.columnCount()):
            self.table.setColumnWidth(col, min(220, max(95, self.table.columnWidth(col))))
        self.table.horizontalHeader().setTextElideMode(Qt.ElideMiddle)

    @staticmethod
    def _number(value):
        return '\u2014' if value is None else f'{value:.6g}'

    def _metric_item(self, key):
        descriptor = METRICS[key]
        label = descriptor['label']
        if descriptor['unit']:
            label += f" ({descriptor['unit']})"
        if descriptor['role'] == 'diagnostic':
            label += ' [diagnostic]'
        item = QTableWidgetItem(label)
        item.setToolTip(descriptor['tooltip'])
        return item

    def _render_motion(self, impact, diff_data):
        keys = [key for key, descriptor in METRICS.items() if descriptor['role'] == 'experimental']
        names = list(impact['files'])
        self.table.setRowCount(len(keys))
        self.table.setColumnCount(len(names) + 1)
        self.table.setHorizontalHeaderLabels(['Metric'] + [
            f"{name}\n{SOURCE_LABELS.get(diff_data[name]['source'], 'Unknown')}"
            for name in names])
        for r, key in enumerate(keys):
            self.table.setItem(r, 0, self._metric_item(key))
            for c, name in enumerate(names, 1):
                data = impact['files'][name]
                metric = data['result'].metrics[key]
                item = QTableWidgetItem(self._number(metric.value))
                item.setTextAlignment(Qt.AlignCenter)
                evidence = data['result'].evidence
                details = [metric.reason] if metric.reason else []
                details.extend(data['reasons'])
                if evidence.get('evaluation_time_s') is not None:
                    details.append(f"Evaluated at {evidence['evaluation_time_s']:.6g} s")
                if evidence.get('sample_count'):
                    details.append(f"Pre-contact window: {evidence['window_start_s']:.6g} to "
                                   f"{evidence['window_end_s']:.6g} s, {evidence['sample_count']} samples")
                item.setToolTip('\n'.join(details))
                self.table.setItem(r, c, item)
        for c, name in enumerate(names, 1):
            self.table.horizontalHeaderItem(c).setToolTip(
                name + '\n' + diff_data[name]['source'] + '\n' + '\n'.join(impact['files'][name]['reasons']))

    def _render_statistics(self, impact):
        self.table.setRowCount(len(METRICS))
        headers = ['Metric', 'n', 'Mean', 'Min', 'Max', 'Range', 'Counts', 'Match baseline']
        self.table.setColumnCount(len(headers))
        self.table.setHorizontalHeaderLabels(headers)
        for r, key in enumerate(METRICS):
            self.table.setItem(r, 0, self._metric_item(key))
            stats = impact['statistics'][key]
            n = stats['n']
            count = QTableWidgetItem(str(n) if n >= 3 else f'{n} (low)')
            count.setToolTip('Valid distinct observations. Fewer than 3 provide insufficient repeat evidence.')
            self.table.setItem(r, 1, count)
            for c, field in enumerate(('mean', 'min', 'max', 'range'), 2):
                self.table.setItem(r, c, QTableWidgetItem(self._number(stats.get(field))))
            counts = ', '.join(f'{value}: {total}' for value, total in sorted(stats.get('counts', {}).items()))
            self.table.setItem(r, 6, QTableWidgetItem(counts or '\u2014'))
            matches = stats.get('matching')
            item = QTableWidgetItem(f'{matches}/{n}' if matches is not None and n else '\u2014')
            item.setToolTip('Diagnostic agreement with the baseline category; not agreement with an intended trial target.')
            self.table.setItem(r, 7, item)

    def _render_diagnostics(self, diff_data, baseline_name):
        if not diff_data:
            self.table.clear()
            self.table.setRowCount(0)
            self.table.setColumnCount(0)
            return

        datasets = list(diff_data.keys())
        if not datasets:
            return
            
        metrics = list(dict.fromkeys(metric for info in diff_data.values() for metric in info['summary']))
        
        self.table.setRowCount(len(metrics))
        self.table.setColumnCount(len(datasets) + 1)
        self.table.setHorizontalHeaderLabels(["Property"] + [f'{name}\n{diff_data[name]["source"]}' for name in datasets])
        for i, name in enumerate(datasets):
            self.table.horizontalHeaderItem(i + 1).setToolTip(name + '\n' + '\n'.join(diff_data[name]['reasons']))
        
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
                
                if is_baseline or diff is None:
                    display_text = f"{val}"
                else:
                    if isinstance(diff, (int, float)):
                        display_text = f"{val} ({diff:+.2f})"
                    else:
                        display_text = f"{val} (vs {diff})" if diff != "Match" else f"{val}"
                        
                item = QTableWidgetItem(display_text)
                if ds_info['reasons']:
                    item.setToolTip('Individual value only; baseline difference unavailable.\n' + '\n'.join(ds_info['reasons']))
                item.setTextAlignment(Qt.AlignCenter)
                self.table.setItem(r, c + 1, item)
                
        self.table.resizeColumnsToContents()
        self.table.horizontalHeader().setTextElideMode(Qt.ElideMiddle)
        for column in range(1, self.table.columnCount()):
            self.table.setColumnWidth(column, min(220, max(155, self.table.columnWidth(column))))

from matplotlib.backends.backend_qtagg import NavigationToolbar2QT as NavigationToolbar

class CompareGraphPanel(QGroupBox):
    """Displays overlaid time-series metrics from multiple files using PlotManager."""
    plot_target_changed = Signal(str)

    def __init__(self):
        super().__init__("Time-History")
        layout = QVBoxLayout(self)
        
        target_layout = QHBoxLayout()
        target_layout.addWidget(QLabel("Plot Target:"))
        self.cb_plot_target = QComboBox()
        self.cb_plot_target.currentTextChanged.connect(self.plot_target_changed.emit)
        target_layout.addWidget(self.cb_plot_target, stretch=1)
        layout.addLayout(target_layout)
        
        self.fig = Figure(figsize=(5, 3), dpi=100)
        self.canvas = FigureCanvas(self.fig)
        self.toolbar = NavigationToolbar(self.canvas, self)
        
        # Set to vertical and reduce size
        self.toolbar.setOrientation(Qt.Vertical)
        self.toolbar.setIconSize(QSize(16, 16))
        self.toolbar.locLabel.setVisible(False) # Prevent layout jitter from hover text

        
        # Hide Configure subplots and Edit axis buttons
        for action in self.toolbar.actions():
            tt = action.toolTip() or ""
            if "Configure subplots" in tt or "Edit axis" in tt:
                action.setVisible(False)
                
        # Use QHBoxLayout to put canvas on left, toolbar on right
        plot_layout = QHBoxLayout()
        plot_layout.addWidget(self.canvas)
        plot_layout.addWidget(self.toolbar)
        
        layout.addLayout(plot_layout)
        
        self.plot_manager = PlotManager(self.canvas, self.fig)
        self.cursor = None

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
        self.plot_target_changed.emit(self.cb_plot_target.currentText())

    def update_plot(self, series_dict: dict, metric_name: str, *, xlabel='Elapsed since t1− (s)', labels=None):
        self.plot_manager.ax.clear()
        self.cursor = None
        
        if not series_dict:
            self.plot_manager.ax.set_title("No Data to Plot", color="red")
            self.canvas.draw()
            return
            
        # Plot each file at its own timestamps. A union DataFrame introduces
        # artificial NaNs for mixed rates and can erase otherwise valid curves.
        for name, series in series_dict.items():
            self.plot_manager.ax.plot(series.index, series.values, label=(labels or {}).get(name, name))
        self.plot_manager.ax.set_xlabel(xlabel)
        self.plot_manager.ax.set_ylabel(metric_name)
        self.plot_manager.ax.legend(fontsize=8)
        self.plot_manager.ax.grid(True)
        self.fig.tight_layout()
        self.canvas.draw()

    def set_elapsed_cursor(self, elapsed):
        if self.cursor is None:
            self.cursor = self.plot_manager.ax.axvline(elapsed, color='black', linestyle='--', linewidth=1)
        else:
            self.cursor.set_xdata([elapsed, elapsed])
        self.canvas.draw_idle()

class CompareControlPanel(QGroupBox):
    """Controls for file selection, baseline designation."""
    add_files_requested = Signal()
    remove_file_requested = Signal(str)
    baseline_changed = Signal(str)
    view_changed = Signal()

    def __init__(self):
        super().__init__("Result Files")
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
        layout.addWidget(QLabel('Graph view:'))
        self.cb_view = QComboBox()
        self.cb_view.currentIndexChanged.connect(lambda *_: self.view_changed.emit())
        layout.addWidget(self.cb_view)
        layout.addWidget(QLabel('Break gaps longer than (seconds):'))
        self.gap_limit = QDoubleSpinBox()
        self.gap_limit.setDecimals(4)
        self.gap_limit.setRange(0.0001, 3600)
        self.gap_limit.setValue(0.1)
        self.gap_limit.setToolTip('Display continuity policy only. No interpolation through longer gaps.')
        self.gap_limit.valueChanged.connect(lambda *_: self.view_changed.emit())
        layout.addWidget(self.gap_limit)
        self.details = QPlainTextEdit()
        self.details.setReadOnly(True)
        self.details.setPlaceholderText('Load results to inspect source and compatibility.')
        layout.addWidget(self.details)
        self.file_list.currentItemChanged.connect(self._show_details)
        
        layout.addStretch()

    def _on_remove_clicked(self):
        selected = self.file_list.currentItem()
        if selected:
            self.remove_file_requested.emit(selected.data(Qt.UserRole))

    def _show_details(self, current, *_):
        self.details.setPlainText(current.toolTip() if current else '')

    def update_files(self, file_names: list[str], baseline: str, model=None, impact=None):
        # Update List
        self.file_list.clear()
        for name in file_names:
            repeat_reasons = impact['files'][name]['reasons'] if impact else None
            status = model.status_text(name, repeat_reasons=repeat_reasons) if model else ''
            item = QListWidgetItem(name + '\n' + status)
            item.setData(Qt.UserRole, name)
            details = name + '\n' + status
            if model:
                details += '\n\n' + '\n'.join(model.exclusion_reasons(name))
                if repeat_reasons:
                    details += '\n\nRepeat summary exclusion:\n' + '\n'.join(repeat_reasons)
                details += '\n\nDeclared metadata:\n' + '\n'.join(f'{key}: {value}' for key, value in model.identities[name].values.items())
            item.setToolTip(details)
            self.file_list.addItem(item)
        if file_names:
            self.file_list.setCurrentRow(0)
        view = self.cb_view.currentData()
        self.cb_view.blockSignals(True)
        self.cb_view.clear()
        self.cb_view.addItem('Aligned overlay (visual only)', None)
        for name in file_names:
            self.cb_view.addItem('Individual: ' + name, name)
        index = self.cb_view.findData(view)
        self.cb_view.setCurrentIndex(max(0, index))
        self.cb_view.blockSignals(False)
        
        # Update Baseline Combo Box without triggering signal
        self.cb_baseline.blockSignals(True)
        self.cb_baseline.clear()
        self.cb_baseline.addItems(file_names)
        if baseline in file_names:
            self.cb_baseline.setCurrentText(baseline)
        self.cb_baseline.blockSignals(False)
