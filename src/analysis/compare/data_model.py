import pandas as pd
from src.analysis.pipeline.data_loader import DataLoader
from src.visualization.data_handler import DataHandler
import os

class ComparisonModel:
    def __init__(self):
        self.data_loader = DataLoader()
        self.datasets: dict[str, pd.DataFrame] = {}
        self.visualization_handlers: dict[str, DataHandler] = {}
        self.alignment_frames: dict[str, int] = {}
        self.baseline_name: str | None = None

    def load_file(self, filepath: str) -> str:
        """
        Loads a .proc file and stores it. Returns the name/key of the loaded file.
        """
        name = os.path.basename(filepath)
        if name in self.datasets:
            # Append suffix if duplicate
            base, ext = os.path.splitext(name)
            count = 1
            while f"{base}_{count}{ext}" in self.datasets:
                count += 1
            name = f"{base}_{count}{ext}"

        df = self.data_loader.load_result_csv(filepath)
        self.datasets[name] = df
        
        # Load data handler for 3D visualization
        viz_handler = DataHandler()
        viz_handler.load_analysis_result(filepath)
        self.visualization_handlers[name] = viz_handler
        
        # Extract t1- frame for event alignment
        t1_frame = 0
        if "Analysis" in df.columns.levels[0] and "DropPostureSummary" in df.columns.levels[1]:
            summary_df = df["Analysis"]["DropPostureSummary"]
            if not summary_df.empty and "T1MinusFrame" in summary_df.columns:
                val = summary_df.iloc[0]["T1MinusFrame"]
                if not pd.isna(val):
                    t1_frame = int(val)
        self.alignment_frames[name] = t1_frame
        
        if self.baseline_name is None:
            self.baseline_name = name
            
        return name

    def set_baseline(self, name: str):
        if name in self.datasets:
            self.baseline_name = name

    def get_summary_differences(self) -> dict[str, dict[str, any]]:
        """
        Computes differences between each dataset and the baseline for DropPostureSummary metrics.
        Returns a dict mapping dataset name to a dict of metric differences.
        """
        if not self.baseline_name or self.baseline_name not in self.datasets:
            return {}

        baseline_df = self.datasets[self.baseline_name]
        
        # Helper to extract a single row of summary metrics from the DataFrame
        def _extract_summary(df: pd.DataFrame) -> dict[str, any]:
            summary = {}
            if "Analysis" in df.columns.levels[0] and "DropPostureSummary" in df.columns.levels[1]:
                # The summary metrics are usually repeated constants, so take the first valid row
                summary_df = df["Analysis"]["DropPostureSummary"]
                if not summary_df.empty:
                    first_row = summary_df.iloc[0]
                    for col in summary_df.columns:
                        summary[col] = first_row[col]
            return summary

        baseline_summary = _extract_summary(baseline_df)
        results = {}

        for name, df in self.datasets.items():
            summary = _extract_summary(df)
            diffs = {}
            for k, v in summary.items():
                b_v = baseline_summary.get(k)
                if pd.isna(v) or pd.isna(b_v):
                    diffs[k] = None
                    continue
                try:
                    # numeric diff
                    diffs[k] = v - b_v
                except TypeError:
                    # fallback for string columns like ContactState
                    diffs[k] = v if v != b_v else "Match"
            results[name] = {"summary": summary, "diffs": diffs}

        return results

    def get_timeseries_data(self, group: str, component: str, metric: str) -> dict[str, pd.Series]:
        """
        Returns time-series data for a given multi-level column across all datasets.
        """
        series_dict = {}
        for name, df in self.datasets.items():
            try:
                # Expects MultiIndex columns
                if (group, component, metric) in df.columns:
                    series_dict[name] = df[(group, component, metric)]
            except KeyError:
                pass
        return series_dict
