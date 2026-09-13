from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QTableWidget, QTableWidgetItem, QHeaderView, QListWidget, QComboBox, QSplitter,
    QGroupBox, QFrame, QListWidgetItem, QPlainTextEdit, QDoubleSpinBox,
    QScrollArea, QSizePolicy, QFormLayout, QCheckBox, QLayout
)
from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtGui import QColor, QIcon, QPixmap
from matplotlib.figure import Figure
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
import pandas as pd

from src.config.result_metric_descriptors import METRIC_DESCRIPTORS
from src.analysis.ui.plot_manager import PlotManager, plot_result_series, configure_result_axis
from src.analysis.compare.impact_metrics import METRICS
from src.config.data_columns import (get_result_metric_display_name, get_result_metric_tooltip,
                                     format_result_value, is_corner_id_column)
from src.utils.qt_sections import CollapsibleSection, find_result_column_index

SOURCE_LABELS = {'real': 'Real', 'mujoco_synthetic': 'MuJoCo',
                 'handcrafted_dummy': 'Constructed', 'public_external': 'Public',
                 'unknown_legacy': 'Unknown'}

class CompareTablePanel(QGroupBox):
    """Displays differences in Drop Posture Summary metrics."""
    def __init__(self):
        super().__init__("Summary")
        # Keep at least one metric row beneath the controls and table header.
        self.setMinimumHeight(150)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(4)
        modes = QHBoxLayout()
        self.view_combo = QComboBox()
        self.view_combo.addItems(['Pre-contact', 'Repeats', 'Details', 'Contact'])
        modes.addWidget(self.view_combo)
        self.validation_badge = QLabel('Experimental')
        self.validation_badge.setStyleSheet('color: #805d00;')
        self.validation_badge.setToolTip('Not independently calibrated against measured trials.')
        self.validation_badge.hide()
        modes.addWidget(self.validation_badge)
        self.cohort_label = QLabel()
        modes.addWidget(self.cohort_label)
        modes.addStretch()
        layout.addLayout(modes)
        self._table_data = ({}, None, None)
        self._contact_data = None
        self.view_combo.currentIndexChanged.connect(self._render)
        
        self.table = QTableWidget()
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        layout.addWidget(self.table)

    def update_table(self, diff_data: dict[str, dict], baseline_name: str, impact=None, contact=None):
        self._table_data = (diff_data, baseline_name, impact)
        self._contact_data = contact
        self.view_combo.setVisible(impact is not None)
        self._render()

    def _render(self):
        diff_data, baseline_name, impact = self._table_data
        self.cohort_label.clear()
        self.validation_badge.setText('Diagnostic' if impact is None or self.view_combo.currentIndex() == 2 else 'Experimental')
        self.validation_badge.setVisible(bool(diff_data))
        if self.view_combo.currentIndex() == 3 and self._contact_data is not None:
            self._render_contact(self._contact_data)
            return
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
        # Contact rows contain a filename and source on separate lines. Qt
        # retains their heights across clear()/setRowCount(), so measure the
        # current mode instead of carrying those heights into numeric rows.
        self.table.resizeRowsToContents()

    def _render_contact(self, contact):
        self.table.clear()
        files = contact['files']
        self.table.setRowCount(len(files))
        self.table.setColumnCount(5 if files else 0)
        if not files:
            return
        self.table.setHorizontalHeaderLabels(['File', 'Intended', 'Observed (estimated)', 'Result', 'Contact (s)'])
        stats = contact['statistics']
        if contact['intended']:
            self.cohort_label.setText(f"Local n={stats['n']}   Match {stats['Match']}   Different {stats['Different']}   Unclear {stats['Unclear']}")
            self.cohort_label.setToolTip('Compatible, distinct observations with baseline intent: '
                + contact['intended'] + f". {stats['excluded']} excluded."
                + (' Fewer than 3 comparable observations.' if stats['n'] < 3 else ''))
        else:
            self.cohort_label.setText('Baseline contact unspecified')
        for row, (name, data) in enumerate(files.items()):
            result = data['result']
            labels = [name + '\n' + SOURCE_LABELS.get(data['source'], 'Unknown'), result.intended or '—',
                      result.observed or '—', result.outcome, self._number(result.time_s)]
            for col, label in enumerate(labels):
                item = QTableWidgetItem(label)
                detail = [name, result.reason] + data['reasons']
                if col == 3:
                    detail.append('Exact contact-feature comparison. Different can include a corner or edge of the intended face; it is not an ISTA failure.')
                item.setToolTip('\n'.join(part for part in detail if part))
                self.table.setItem(row, col, item)
        self.table.resizeColumnsToContents()
        for col in range(5):
            self.table.setColumnWidth(col, min(260, max(95, self.table.columnWidth(col))))
        self.table.resizeRowsToContents()
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
                column = ('Analysis', 'DropPostureSummary', metric)
                if is_corner_id_column(column):
                    val = format_result_value(column, val)
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
        self.table.resizeRowsToContents()

from matplotlib.backends.backend_qtagg import NavigationToolbar2QT as NavigationToolbar

class CompareGraphPanel(QGroupBox):
    """File colours and canonical metric keys are shared with the other views."""
    plot_target_changed = Signal(object)

    def __init__(self):
        super().__init__("Graph")
        self.setMinimumHeight(270)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(3)
        target_layout = QHBoxLayout()
        self.cb_plot_target = QComboBox()
        self.cb_plot_target.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
        self.cb_plot_target.setMinimumContentsLength(12)
        self.cb_plot_target.currentIndexChanged.connect(
            lambda *_: self.plot_target_changed.emit(self.cb_plot_target.currentData()))
        target_layout.addWidget(self.cb_plot_target, stretch=1)
        self.fig = Figure(figsize=(5, 3), dpi=100)
        self.canvas = FigureCanvas(self.fig)
        self.canvas.setMinimumSize(200, 130)
        self.canvas.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Ignored)
        self.toolbar = NavigationToolbar(self.canvas, self)
        self.toolbar.setIconSize(QSize(16, 16))
        self.toolbar.locLabel.setVisible(False)
        for action in self.toolbar.actions():
            tooltip = action.toolTip() or ''
            if 'Configure subplots' in tooltip or 'Edit axis' in tooltip:
                action.setVisible(False)
        layout.addLayout(target_layout)

        # A scrollable, single-line key never covers the measured data.
        self.legend_scroll = QScrollArea()
        self.legend_scroll.setWidgetResizable(True)
        self.legend_scroll.setFrameShape(QFrame.NoFrame)
        self.legend_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.legend_scroll.setFixedHeight(32)
        self.legend_widget = QWidget()
        self.legend_layout = QHBoxLayout(self.legend_widget)
        self.legend_layout.setContentsMargins(0, 0, 0, 0)
        self.legend_layout.setSizeConstraint(QLayout.SetMinimumSize)
        self.legend_labels = {}
        self.legend_scroll.setWidget(self.legend_widget)
        target_layout.addWidget(self.legend_scroll, stretch=1)
        target_layout.addWidget(self.toolbar)
        layout.addWidget(self.canvas, stretch=1)
        self.plot_manager = PlotManager(self.canvas, self.fig)
        self.cursor = None

    def set_plot_targets(self, targets):
        current = self.cb_plot_target.currentData()
        self.cb_plot_target.blockSignals(True)
        self.cb_plot_target.clear()
        for column in targets:
            self.cb_plot_target.addItem(get_result_metric_display_name(*column), column)
            self.cb_plot_target.setItemData(self.cb_plot_target.count() - 1,
                                           get_result_metric_tooltip(column), Qt.ToolTipRole)
        index = find_result_column_index(self.cb_plot_target, current)
        if index < 0:
            index = find_result_column_index(self.cb_plot_target, ('Analysis', 'DropPosture', 'BetaDeg'))
        self.cb_plot_target.setCurrentIndex(max(0, index) if targets else -1)
        self.cb_plot_target.blockSignals(False)
        self.plot_target_changed.emit(self.cb_plot_target.currentData())

    def update_plot(self, series_dict, column, *, xlabel='Time from pre-contact (s)', colors=None, paths=None):
        self.plot_manager.reset_axes()
        ax = self.plot_manager.ax
        self.cursor = None
        while self.legend_layout.count():
            item = self.legend_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.legend_labels.clear()
        for name, series in series_dict.items():
            color = (colors or {}).get(name, '#1f77b4')
            plot_result_series(ax, series.index, series.values, column, label=name, color=color)
            chip = QWidget()
            chip_layout = QHBoxLayout(chip)
            chip_layout.setContentsMargins(0, 0, 8, 0)
            swatch = QLabel()
            swatch.setFixedSize(14, 4)
            swatch.setStyleSheet(f'background-color: {color}')
            label = QLabel()
            label.setTextFormat(Qt.PlainText)
            label.setText(label.fontMetrics().elidedText(name, Qt.ElideMiddle, 190))
            label.setMinimumWidth(label.sizeHint().width())
            label.setToolTip((paths or {}).get(name, name))
            label.setProperty('fileKey', name)
            label.setProperty('fileColor', color)
            chip_layout.addWidget(swatch)
            chip_layout.addWidget(label)
            self.legend_layout.addWidget(chip)
            self.legend_labels[name] = label
        self.legend_layout.addStretch()
        self.legend_scroll.setVisible(bool(series_dict))
        if column:
            configure_result_axis(ax, [column])
        if not series_dict:
            ax.text(.5, .5, 'No data for this view', transform=ax.transAxes,
                    ha='center', va='center', color='#666666')
        ax.set_xlabel(xlabel)
        ax.grid(True)
        self.plot_manager._initialize_hover_annotation()
        self.fig.tight_layout(pad=.3)
        self.canvas.draw()

    def set_elapsed_cursor(self, elapsed):
        if self.cursor is None:
            self.cursor = self.plot_manager.ax.axvline(elapsed, color='black', linestyle='--', linewidth=1,
                                                       label='_cursor')
        else:
            self.cursor.set_xdata([elapsed, elapsed])
        self.canvas.draw_idle()


class CompareControlPanel(QGroupBox):
    add_files_requested = Signal()
    remove_file_requested = Signal(str)
    baseline_changed = Signal(str)
    view_changed = Signal()
    labels_changed = Signal(bool)

    def __init__(self):
        super().__init__('Files')
        layout = QVBoxLayout(self)
        buttons = QHBoxLayout()
        self.btn_add_files = QPushButton('Open')
        self.btn_add_files.clicked.connect(self.add_files_requested.emit)
        self.btn_remove_file = QPushButton('Remove')
        self.btn_remove_file.clicked.connect(self._on_remove_clicked)
        buttons.addWidget(self.btn_add_files)
        buttons.addWidget(self.btn_remove_file)
        layout.addLayout(buttons)
        self.file_list = QListWidget()
        self.file_list.setTextElideMode(Qt.ElideMiddle)
        self.file_list.setMinimumHeight(100)
        layout.addWidget(self.file_list, stretch=1)
        form = QFormLayout()
        self.cb_view = QComboBox()
        self.cb_view.addItem('Individual', 'individual')
        self.cb_view.addItem('Aligned', 'aligned')
        self.cb_view.setItemData(1, 'Time zero is the last sample before contact. Includes later samples.', Qt.ToolTipRole)
        self.cb_view.currentIndexChanged.connect(lambda *_: self.view_changed.emit())
        form.addRow('View', self.cb_view)
        self.cb_baseline = QComboBox()
        self.cb_baseline.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
        self.cb_baseline.setMinimumContentsLength(10)
        self.cb_baseline.currentIndexChanged.connect(
            lambda *_: self.baseline_changed.emit(self.cb_baseline.currentData() or ''))
        form.addRow('Baseline', self.cb_baseline)
        layout.addLayout(form)
        self.details = QPlainTextEdit()
        self.details.setReadOnly(True)
        self.details.setMinimumHeight(70)
        self.details.setMaximumHeight(145)
        self.details_section = CollapsibleSection('Details', self.details)
        settings = QWidget()
        settings_form = QFormLayout(settings)
        settings_form.setContentsMargins(0, 0, 0, 0)
        self.gap_limit = QDoubleSpinBox()
        self.gap_limit.setDecimals(4)
        self.gap_limit.setRange(.0001, 3600)
        self.gap_limit.setValue(.1)
        self.gap_limit.setSuffix(' s')
        self.gap_limit.setToolTip('Display continuity only. Do not connect samples across a longer gap.')
        self.gap_limit.valueChanged.connect(lambda *_: self.view_changed.emit())
        settings_form.addRow('Gap limit', self.gap_limit)
        self.labels_check = QCheckBox('Labels')
        self.labels_check.toggled.connect(self.labels_changed.emit)
        settings_form.addRow(self.labels_check)
        self.settings_section = CollapsibleSection('Settings', settings)
        layout.addWidget(self.details_section)
        layout.addWidget(self.settings_section)
        self.file_list.currentItemChanged.connect(self._on_selection_changed)

    @property
    def selected_file(self):
        item = self.file_list.currentItem()
        return item.data(Qt.UserRole) if item else None

    def _on_remove_clicked(self):
        if self.selected_file:
            self.remove_file_requested.emit(self.selected_file)

    def _on_selection_changed(self, current, *_):
        self.details.setPlainText(current.toolTip() if current else '')
        self.btn_remove_file.setEnabled(current is not None)
        self.view_changed.emit()

    @staticmethod
    def _short_status(model, name):
        timeline = model.timelines[name]
        if timeline.times is None:
            return 'Time unavailable'
        if model.identities[name].source_kind == 'unknown_legacy':
            return 'Source unknown'
        if not timeline.aligned:
            return 'No alignment'
        return 'Not comparable' if model.exclusion_reasons(name) else 'Ready'

    def update_files(self, file_names, baseline, model=None, impact=None):
        selected = self.selected_file
        previous_row = self.file_list.currentRow()
        self.file_list.blockSignals(True)
        self.file_list.clear()
        for name in file_names:
            repeat_reasons = impact['files'][name]['reasons'] if impact else None
            status = self._short_status(model, name) if model else ''
            item = QListWidgetItem(name + ('\n' + status if status else ''))
            item.setData(Qt.UserRole, name)
            details = name
            if model:
                color = model.file_colors[name]
                swatch = QPixmap(12, 12)
                swatch.fill(QColor(color))
                item.setIcon(QIcon(swatch))
                item.setData(Qt.UserRole + 1, color)
                details = model.file_paths[name] + '\n' + model.status_text(name, repeat_reasons=repeat_reasons)
                reasons = model.exclusion_reasons(name) + (repeat_reasons or [])
                details += '\n\n' + '\n'.join(dict.fromkeys(reasons))
                details += '\n\n' + '\n'.join(f'{key}: {value}' for key, value in model.identities[name].values.items())
            item.setToolTip(details)
            self.file_list.addItem(item)
        if file_names:
            row = file_names.index(selected) if selected in file_names else min(max(0, previous_row), len(file_names) - 1)
            self.file_list.setCurrentRow(row)
        self.file_list.blockSignals(False)
        current = self.file_list.currentItem()
        self.details.setPlainText(current.toolTip() if current else '')
        self.btn_remove_file.setEnabled(current is not None)
        self.cb_baseline.blockSignals(True)
        self.cb_baseline.clear()
        for name in file_names:
            self.cb_baseline.addItem(name, name)
            if model:
                self.cb_baseline.setItemData(self.cb_baseline.count() - 1, model.file_paths[name], Qt.ToolTipRole)
        self.cb_baseline.setCurrentIndex(self.cb_baseline.findData(baseline))
        self.cb_baseline.blockSignals(False)
