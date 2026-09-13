import os
from PySide6.QtWidgets import QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QSplitter, QFileDialog, QMessageBox, QFrame, QLabel, QApplication, QSizePolicy
from PySide6.QtCore import Qt, QEventLoop

from src.analysis.compare.data_model import ComparisonModel
from src.analysis.pipeline.artifact_io import _sha256_file
from src.analysis.compare.ui_panels import CompareControlPanel, CompareTablePanel, CompareGraphPanel
from src.analysis.compare.playback_panel import ComparePlaybackPanel

class CompareMainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Experiment Comparison")
        self.resize(1200, 800)
        
        self.model = ComparisonModel()
        
        # Central widget and layout (Grey background)
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(6, 6, 6, 6)
        main_layout.setSpacing(2)
        self.warning_label = QLabel('No results loaded.')
        self._summary_status = 'No results loaded.'
        self.warning_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.warning_label.setTextFormat(Qt.PlainText)
        main_layout.addWidget(self.warning_label)
        
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
        self.control_panel.setMaximumWidth(310)
        self.table_panel = CompareTablePanel()
        self.graph_panel = CompareGraphPanel()
        self.playback_panel = ComparePlaybackPanel(self.model)
        
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
        
        self.splitter.addWidget(self.control_panel)
        self.splitter.addWidget(self.right_splitter)
        self.splitter.setStretchFactor(0, 0)
        self.splitter.setStretchFactor(1, 1)
        self.splitter.setSizes([300, 900])
        
        # Connect signals
        self.control_panel.add_files_requested.connect(self._on_add_files)
        self.control_panel.remove_file_requested.connect(self._on_remove_file)
        self.control_panel.baseline_changed.connect(self._on_baseline_changed)
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
        
    def _on_remove_file(self, name: str):
        self.model.remove_file(name)
        self._refresh_ui()
        
    def _on_add_files(self):
        filepaths, _ = QFileDialog.getOpenFileNames(
            self,
            "Select Processed Results",
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
                    self.statusBar().showMessage(f'Loading {path}…')
                    QApplication.processEvents(QEventLoop.ExcludeUserInputEvents)
                    self.model.load_file(path, replace_name=replace_name)
                    new_files_added = True
                except Exception as e:
                    QMessageBox.warning(self, "Load Error", f"Failed to load {path}:\n{str(e)}")
        finally:
            self.control_panel.setEnabled(True)
        self.statusBar().showMessage('Loading complete.')
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

    def _update_view_status(self):
        aligned_sources = {self.model.identities[name].source_kind
                           for name, timeline in self.model.timelines.items() if timeline.aligned}
        mixed = self.control_panel.cb_view.currentData() == 'aligned' and len(aligned_sources) > 1
        self.warning_label.setText(self._summary_status + ('   Mixed sources' if mixed else ''))

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
        self.control_panel.update_files(files, baseline, self.model, impact)
        excluded = [name for name in files if impact['files'][name]['reasons']]
        self._summary_status = ('No results loaded.' if not files else
                                f'{len(files)} files   Repeats: {len(files) - len(excluded)} included, {len(excluded)} excluded')
        self.warning_label.setToolTip('Overlaid curves do not establish compatible repeat trials. See file Details for exclusions.')
        
        # Update Table
        diff_data = self.model.get_summary_differences()
        self.table_panel.update_table(diff_data, baseline, impact, self.model.get_contact_comparison())
        
        # Update Plot Targets (collect all DropPosture metrics for now)
        targets = []
        for df in self.model.datasets.values():
            targets.extend(col for col in df.columns if col[:2] == ('Analysis', 'DropPosture'))
        targets = sorted(set(targets))
                
        # Replace changed viewers before reading their stored individual rows.
        # A rewritten file can have fewer samples than the previous version.
        self.playback_panel.refresh_viewers()
        self.graph_panel.set_plot_targets(targets)
        self._on_view_changed()

    def closeEvent(self, event):
        self.playback_panel.stop()
        for viewer in self.playback_panel.widgets.values():
            viewer.cleanup()
        super().closeEvent(event)

