from PySide6.QtWidgets import QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QSplitter, QFileDialog, QMessageBox
from PySide6.QtCore import Qt

from src.analysis.compare.data_model import ComparisonModel
from src.analysis.compare.ui_panels import CompareControlPanel, CompareTablePanel, CompareGraphPanel
from src.analysis.compare.playback_panel import ComparePlaybackPanel

class CompareMainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Experiment Comparison")
        self.resize(1200, 800)
        
        self.model = ComparisonModel()
        
        # Central widget and layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        
        # Splitter to divide controls from data views
        self.splitter = QSplitter(Qt.Horizontal)
        main_layout.addWidget(self.splitter)
        
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
        self.right_splitter.setSizes([200, 400, 300])       # Allocate initial heights
        
        self.splitter.addWidget(self.control_panel)
        self.splitter.addWidget(self.right_splitter)
        self.splitter.setSizes([300, 900])
        
        # Connect signals
        self.control_panel.add_files_requested.connect(self._on_add_files)
        self.control_panel.baseline_changed.connect(self._on_baseline_changed)
        self.control_panel.plot_target_changed.connect(self._on_plot_target_changed)
        
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
        for path in filepaths:
            try:
                self.model.load_file(path)
                new_files_added = True
            except Exception as e:
                QMessageBox.warning(self, "Load Error", f"Failed to load {path}:\n{str(e)}")
                
        if new_files_added:
            self._refresh_ui()
            
    def _on_baseline_changed(self, new_baseline: str):
        self.model.set_baseline(new_baseline)
        self._refresh_ui()
        
    def _on_plot_target_changed(self, target: str):
        if not target:
            return
        # Extract group, component, metric from target string (e.g., 'Analysis | DropPosture | ThetaLongDeg')
        parts = [p.strip() for p in target.split('|')]
        if len(parts) == 3:
            series_dict = self.model.get_timeseries_data(parts[0], parts[1], parts[2])
            self.graph_panel.update_plot(series_dict, parts[2])
            
    def _refresh_ui(self):
        files = list(self.model.datasets.keys())
        baseline = self.model.baseline_name
        self.control_panel.update_files(files, baseline)
        
        # Update Table
        diff_data = self.model.get_summary_differences()
        self.table_panel.update_table(diff_data, baseline)
        
        # Update Plot Targets (collect all DropPosture metrics for now)
        targets = []
        if files:
            first_df = self.model.datasets[files[0]]
            if "Analysis" in first_df.columns.levels[0] and "DropPosture" in first_df.columns.levels[1]:
                metrics = first_df["Analysis"]["DropPosture"].columns
                targets = [f"Analysis | DropPosture | {m}" for m in metrics]
                
        self.control_panel.set_plot_targets(targets)
        
        # Update Playback Panel Viewers
        self.playback_panel.refresh_viewers()

