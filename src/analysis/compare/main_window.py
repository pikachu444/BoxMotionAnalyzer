import os
from PySide6.QtWidgets import QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QSplitter, QFileDialog, QMessageBox, QFrame, QLabel, QApplication, QSizePolicy
from PySide6.QtCore import Qt, QEvent, QEventLoop, QCoreApplication

from src.analysis.compare.data_model import ComparisonModel
from src.analysis.pipeline.artifact_io import _sha256_file
from src.analysis.compare.ui_panels import CompareControlPanel, CompareTablePanel, CompareGraphPanel
from src.analysis.compare.playback_panel import ComparePlaybackPanel
from src.utils.ui_language import tr
from src.utils.qt_sections import unique_path_labels, set_path_label

class CompareMainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(tr("Experiment Comparison"))
        self.resize(1510, 800)
        self.setMinimumSize(820, 600)
        
        self.model = ComparisonModel()
        
        # Central widget and layout (Grey background)
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(6, 6, 6, 6)
        main_layout.setSpacing(2)
        self.warning_label = QLabel()
        self._summary_status = tr('Files: {file_count} | Comparison observation groups: {observation_count}').format(file_count=0, observation_count=0)
        self._owner_exclusion_reasons = []
        self.warning_label.setText(self._summary_status)
        self.warning_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.warning_label.setTextFormat(Qt.PlainText)
        main_layout.addWidget(self.warning_label)
        self.alignment_label = QLabel(tr('No results loaded.'))
        self.alignment_label.setWordWrap(True)
        self.alignment_label.setTextFormat(Qt.PlainText)
        self.alignment_label.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        main_layout.addWidget(self.alignment_label)
        
        # White card frame
        content_frame = QFrame()
        content_frame.setObjectName("MainContentFrame")
        content_layout = QHBoxLayout(content_frame)
        content_layout.setContentsMargins(3, 3, 3, 3)
        content_frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        
        # Splitter to divide controls from data views
        self.splitter = QSplitter(Qt.Horizontal)
        content_layout.addWidget(self.splitter)
        
        main_layout.addWidget(content_frame, stretch=1)
        
        # Panels
        self.control_panel = CompareControlPanel()
        self.control_panel.setMinimumWidth(240)
        self.control_panel.setMaximumWidth(340)
        self.table_panel = CompareTablePanel()
        self.graph_panel = CompareGraphPanel()
        self.playback_panel = ComparePlaybackPanel(self.model)
        self.playback_panel.setMinimumHeight(180)
        
        # Right side: 3-tier vertical split (GUI Principle: No Unnecessary Tabs)
        self.right_splitter = QSplitter(Qt.Vertical)
        self.right_splitter.addWidget(self.table_panel)     # 1. Summary Table (Top)
        self.right_splitter.addWidget(self.playback_panel)  # 2. 3D Playback (Middle)
        self.right_splitter.addWidget(self.graph_panel)     # 3. Comparison Plot (Bottom)
        self.right_splitter.setChildrenCollapsible(False)
        self.right_splitter.setSizes([155, 270, 300])
        self.right_splitter.setStretchFactor(0, 0)
        self.right_splitter.setStretchFactor(1, 1)
        self.right_splitter.setStretchFactor(2, 1)
        self._summary_empty = None
        self._summary_restore_sizes = [155, 270, 300]
        
        self.splitter.addWidget(self.control_panel)
        self.splitter.addWidget(self.right_splitter)
        self.splitter.setStretchFactor(0, 0)
        self.splitter.setStretchFactor(1, 1)
        self.splitter.setSizes([300, 900])
        
        # Connect signals
        self.control_panel.add_files_requested.connect(self._on_add_files)
        self.control_panel.remove_file_requested.connect(self._on_remove_file)
        self.control_panel.baseline_changed.connect(self._on_baseline_changed)
        self.table_panel.resolution_details_changed.connect(self._on_resolution_details)
        self.table_panel.metric_context_changed.connect(self.control_panel.set_metric_context)
        self.table_panel.display_rows_changed.connect(self._on_summary_rows_changed)
        self.graph_panel.plot_target_changed.connect(self._on_plot_target_changed)
        self.control_panel.view_changed.connect(self._on_view_changed)
        self.control_panel.labels_changed.connect(self.playback_panel.set_labels_visible)
        self.playback_panel.elapsed_changed.connect(self._on_elapsed_changed)
        self.playback_panel.sample_changed.connect(self._on_sample_changed)
        # Set white card layout on grey background
        self.setStyleSheet("""
            QMainWindow {
                background-color: #f0f0f0;
            }
            #MainContentFrame {
                background-color: #ffffff;
                border: 1px solid #cccccc;
                border-radius: 2px;
            }
            QSplitter::handle {
                background-color: #e5e7eb;
            }
        """)
        self.table_panel.update_table({}, None)
        
    def _on_remove_file(self, name: str):
        self.model.remove_file(name)
        self._refresh_ui()
        
    def _on_add_files(self):
        filepaths, _ = QFileDialog.getOpenFileNames(
            self,
            tr("Select Processed Results"),
            "",
            "Processed Data (*.proc *.proc.csv *.csv)"
        )
        if not filepaths:
            return
        self.load_result_files(filepaths)

    def load_result_files(self, filepaths, *, deduplicate=False):
        """Accept saved results directly while preserving the current comparison."""
        pending = []
        if deduplicate:
            seen = set()
            for path in filepaths:
                key = os.path.normcase(os.path.realpath(path))
                if key in seen:
                    continue
                seen.add(key)
                matches = [name for name, existing in self.model.file_paths.items()
                           if key == os.path.normcase(os.path.realpath(existing))]
                try:
                    digest = _sha256_file(path)
                except OSError:
                    digest = None  # Let the regular loader report the read failure.
                if not matches:
                    pending.append((path, None))
                else:
                    pending.extend((path, name) for name in matches
                                   if digest != self.model.file_hashes.get(name))
        else:
            pending = [(path, None) for path in filepaths]
        if not pending:
            return
        new_files_added = False
        self.playback_panel.stop()
        self.control_panel.setEnabled(False)
        try:
            for path, replace_name in pending:
                try:
                    self.statusBar().showMessage(tr('Loading {}…').format(path))
                    QApplication.processEvents(QEventLoop.ExcludeUserInputEvents)
                    self.model.load_file(path, replace_name=replace_name)
                    new_files_added = True
                except Exception as e:
                    QMessageBox.warning(self, tr("Load Error"), tr('Failed to load {}:\n{}').format(path, str(e)))
        finally:
            self.control_panel.setEnabled(True)
        self.statusBar().showMessage(tr('Loading complete.'))
        if new_files_added:
            self._refresh_ui()
            
    def _on_baseline_changed(self, new_baseline: str):
        self.model.set_baseline(new_baseline)
        self._refresh_ui()
        
    def _on_plot_target_changed(self, target):
        if not target:
            self.graph_panel.update_plot({}, None)
            return
        individual = self.control_panel.selected_file if self.control_panel.cb_view.currentData() == 'individual' else None
        series_dict = self.model.get_timeseries_data(*target, individual=individual)
        xlabel = 'Time from pre-contact (s)'
        if individual:
            valid_time = self.model.timelines[individual].times is not None
            xlabel = 'Recorded time (s)' if valid_time else 'Sample'
            if not valid_time:
                series_dict = {name: series.set_axis(series.index + 1) for name, series in series_dict.items()}
        self.graph_panel.update_plot(series_dict, target, xlabel=xlabel,
                                     colors=self.model.file_colors, paths=self.model.file_paths)
        if individual is None and self.playback_panel.current_elapsed is not None:
            self.graph_panel.set_elapsed_cursor(self.playback_panel.current_elapsed)
        elif individual in self.playback_panel.local_controls:
            self._on_sample_changed(individual, self.playback_panel.local_controls[individual]['row'])

    def _on_view_changed(self):
        self.model.max_gap_sec = self.control_panel.gap_limit.value()
        self.playback_panel.set_view(self.control_panel.cb_view.currentData(), self.control_panel.selected_file)
        self._on_plot_target_changed(self.graph_panel.cb_plot_target.currentData())
        self._update_view_status()
        self.table_panel._show_resolution()

    def _on_resolution_details(self, text):
        self.control_panel.set_resolution_details(text)

    def _on_summary_rows_changed(self, rows):
        empty = rows == 0
        if empty == self._summary_empty:
            return
        previous_empty = self._summary_empty
        self._summary_empty = empty
        if empty:
            sizes = self.right_splitter.sizes()
            if previous_empty is False and sizes[0] > 0:
                self._summary_restore_sizes = sizes
            self.table_panel.setMinimumHeight(0)
            self.table_panel.setMaximumHeight(110)
            released = max(0, sizes[0] - 110)
            self.right_splitter.setSizes([min(110, sizes[0]), sizes[1], sizes[2] + released])
        else:
            self.table_panel.setMaximumHeight(16777215)
            self.table_panel.setMinimumHeight(150)
            self._restore_summary_splitter()

    def _restore_summary_splitter(self):
        total = sum(self.right_splitter.sizes())
        previous = sum(self._summary_restore_sizes)
        sizes = [round(size * total / previous) for size in self._summary_restore_sizes]
        sizes[-1] += total - sum(sizes)
        self.right_splitter.setSizes(sizes)

    def _update_view_status(self):
        aligned_sources = {self.model.identities[name].source_kind
                           for name, timeline in self.model.timelines.items() if timeline.aligned}
        mixed = self.control_panel.cb_view.currentData() == 'aligned' and len(aligned_sources) > 1
        self.warning_label.setText(self._summary_status + ('   ' + tr('Mixed sources') if mixed else ''))
        reasons = list(dict.fromkeys([timeline.reason for timeline in self.model.timelines.values() if timeline.reason]
                                    + self._owner_exclusion_reasons))
        summary = '; '.join(tr(reason) for reason in reasons[:2])
        if len(reasons) > 2:
            summary += '; ' + tr('{} more reasons; see File details.').format(len(reasons) - 2)
        self.alignment_label.setText(summary if reasons else
                                     tr('Actual-time alignment available') if self.model.datasets else tr('No results loaded.'))
        self.alignment_label.setToolTip('\n'.join(
            self.model.status_text(name) for name in self.model.datasets))

    def _on_elapsed_changed(self, elapsed):
        if self.control_panel.cb_view.currentData() == 'aligned':
            self.graph_panel.set_elapsed_cursor(elapsed)

    def _on_sample_changed(self, name, row):
        if self.control_panel.cb_view.currentData() == 'individual' and name == self.control_panel.selected_file:
            times = self.model.timelines[name].times
            self.graph_panel.set_elapsed_cursor(times[row] if times is not None else row + 1)
            
    def _refresh_ui(self):
        files = list(self.model.datasets.keys())
        baseline = self.model.baseline_name
        impact = self.model.get_impact_comparison()
        self._owner_exclusion_reasons = list(dict.fromkeys(
            reason for entry in impact['files'].values() for reason in entry['reasons']))
        file_labels = dict(zip(files, unique_path_labels(self.model.file_paths[name] for name in files)))
        self.table_panel.file_labels = file_labels
        self.control_panel.update_files(files, baseline, self.model, impact)
        observations = len(impact.get('observations', {}))
        self._summary_status = tr('Files: {file_count} | Comparison observation groups: {observation_count}').format(
            file_count=len(files), observation_count=observations)
        self.warning_label.setToolTip(tr('Overlaid curves do not establish compatible repeat trials. See file Details for exclusions.'))
        self._update_view_status()
        self.centralWidget().layout().activate()
        
        # Update Table
        diff_data = self.model.get_summary_differences()
        was_empty = self._summary_empty
        self.table_panel.update_table(diff_data, baseline, impact, self.model.get_contact_comparison(),
                                      self.model.get_posture_comparison())
        
        # Update Plot Targets (collect all DropPosture metrics for now)
        targets = []
        for df in self.model.datasets.values():
            targets.extend(col for col in df.columns if col[:2] == ('Analysis', 'DropPosture'))
        targets = sorted(set(targets))
                
        # Replace changed viewers before reading their stored individual rows.
        # A rewritten file can have fewer samples than the previous version.
        self.playback_panel.refresh_viewers()
        for name, controls in self.playback_panel.local_controls.items():
            title = controls['title']
            display_name = file_labels[name]
            set_path_label(title, self.model.file_paths[name], display_name=display_name)
            title.setText(title.fontMetrics().elidedText(display_name, Qt.ElideMiddle, 250))
        self.graph_panel.set_plot_targets(targets)
        self._on_view_changed()
        if was_empty and not self._summary_empty:
            # Owner status can change the space available above the splitter.
            QCoreApplication.sendPostedEvents(None, QEvent.LayoutRequest)
            self._restore_summary_splitter()

    def closeEvent(self, event):
        self.playback_panel.stop()
        for viewer in self.playback_panel.widgets.values():
            viewer.cleanup()
        super().closeEvent(event)

