from PySide6.QtWidgets import QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QSplitter, QFileDialog, QMessageBox, QFrame, QLabel, QApplication
from PySide6.QtCore import Qt, QEventLoop

from src.analysis.compare.data_model import ComparisonModel
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
        main_layout.setContentsMargins(10, 10, 10, 10)
        self.warning_label = QLabel('No results loaded.')
        self.warning_label.setWordWrap(True)
        self.warning_label.setTextFormat(Qt.PlainText)
        main_layout.addWidget(self.warning_label)
        
        # White card frame
        content_frame = QFrame()
        content_frame.setObjectName("MainContentFrame")
        content_layout = QHBoxLayout(content_frame)
        content_layout.setContentsMargins(5, 5, 5, 5)
        
        # Splitter to divide controls from data views
        self.splitter = QSplitter(Qt.Horizontal)
        content_layout.addWidget(self.splitter)
        
        main_layout.addWidget(content_frame)
        
        # Panels
        self.control_panel = CompareControlPanel()
        self.control_panel.setMinimumWidth(250)  # GUI Principle: Rigid & Bounded Sizing
        self.table_panel = CompareTablePanel()
        self.graph_panel = CompareGraphPanel()
        self.playback_panel = ComparePlaybackPanel(self.model)
        
        # Right side: 3-tier vertical split (GUI Principle: No Unnecessary Tabs)
        self.right_splitter = QSplitter(Qt.Vertical)
        self.right_splitter.addWidget(self.table_panel)     # 1. Summary Table (Top)
        self.right_splitter.addWidget(self.playback_panel)  # 2. 3D Playback (Middle)
        self.right_splitter.addWidget(self.graph_panel)     # 3. Comparison Plot (Bottom)
        self.right_splitter.setSizes([300, 210, 250])       # Show motion rows and graph axis labels initially.
        
        self.splitter.addWidget(self.control_panel)
        self.splitter.addWidget(self.right_splitter)
        self.splitter.setSizes([300, 900])
        
        # Connect signals
        self.control_panel.add_files_requested.connect(self._on_add_files)
        self.control_panel.remove_file_requested.connect(self._on_remove_file)
        self.control_panel.baseline_changed.connect(self._on_baseline_changed)
        self.graph_panel.plot_target_changed.connect(self._on_plot_target_changed)
        self.control_panel.view_changed.connect(self._on_view_changed)
        self.playback_panel.elapsed_changed.connect(self._on_elapsed_changed)
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
            
        new_files_added = False
        self.playback_panel.stop()
        self.control_panel.setEnabled(False)
        for path in filepaths:
            try:
                self.statusBar().showMessage(f'Loading {path}…')
                QApplication.processEvents(QEventLoop.ExcludeUserInputEvents)
                self.model.load_file(path)
                new_files_added = True
            except Exception as e:
                QMessageBox.warning(self, "Load Error", f"Failed to load {path}:\n{str(e)}")
        self.control_panel.setEnabled(True)
        self.statusBar().showMessage('Loading complete.')
        if new_files_added:
            self._refresh_ui()
            
    def _on_baseline_changed(self, new_baseline: str):
        self.model.set_baseline(new_baseline)
        self._refresh_ui()
        
    def _on_plot_target_changed(self, target: str):
        if not target:
            self.graph_panel.update_plot({}, '')
            return
        # Extract group, component, metric from target string (e.g., 'Analysis | DropPosture | ThetaLongDeg')
        parts = [p.strip() for p in target.split('|')]
        if len(parts) == 3:
            individual = self.control_panel.cb_view.currentData()
            series_dict = self.model.get_timeseries_data(parts[0], parts[1], parts[2], individual=individual)
            xlabel = 'Elapsed since t1− (s)'
            if individual:
                xlabel = 'Recorded time (s)' if self.model.timelines[individual].times is not None else 'Sample row (time unavailable)'
            labels = {name: f'{i + 1}. {name[:24]} [{self.model.identities[name].source_kind}]' for i, name in enumerate(series_dict)}
            self.graph_panel.update_plot(series_dict, parts[2], xlabel=xlabel, labels=labels)
            if individual is None and self.playback_panel.current_elapsed is not None:
                self.graph_panel.set_elapsed_cursor(self.playback_panel.current_elapsed)

    def _on_view_changed(self):
        self.model.max_gap_sec = self.control_panel.gap_limit.value()
        self._on_plot_target_changed(self.graph_panel.cb_plot_target.currentText())
        self.playback_panel._on_master_slider_changed(self.playback_panel.master_slider.value())

    def _on_elapsed_changed(self, elapsed):
        if self.control_panel.cb_view.currentData() is None:
            self.graph_panel.set_elapsed_cursor(elapsed)
            
    def _refresh_ui(self):
        files = list(self.model.datasets.keys())
        baseline = self.model.baseline_name
        impact = self.model.get_impact_comparison()
        self.control_panel.update_files(files, baseline, self.model, impact)
        excluded = [name for name in files if impact['files'][name]['reasons']]
        mixed_sources = len({identity.source_kind for identity in self.model.identities.values()}) > 1
        self.warning_label.setText(
            ('No results loaded.' if not files else
             f'{len(files)} files. Repeat summary: {len(files) - len(excluded)} included, '
             f'{len(excluded)} excluded. Select a file for details.'
             + (' Mixed sources; overlay is visual only.' if mixed_sources else '')))
        
        # Update Table
        diff_data = self.model.get_summary_differences()
        self.table_panel.update_table(diff_data, baseline, impact)
        
        # Update Plot Targets (collect all DropPosture metrics for now)
        targets = []
        for df in self.model.datasets.values():
            targets.extend(' | '.join(col) for col in df.columns if col[:2] == ('Analysis', 'DropPosture'))
        targets = sorted(set(targets))
                
        self.graph_panel.set_plot_targets(targets)
        
        # Update Playback Panel Viewers
        self.playback_panel.refresh_viewers()

    def closeEvent(self, event):
        self.playback_panel.stop()
        for viewer in self.playback_panel.widgets.values():
            viewer.cleanup()
        super().closeEvent(event)

