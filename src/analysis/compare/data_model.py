import os
from dataclasses import replace

import numpy as np
import pandas as pd

from src.analysis.pipeline.data_loader import DataLoader
from src.utils.artifact_metadata import read_identity, compatibility_reasons, SOURCE_KINDS
from src.utils.result_time import timeline_from_frame, segmented_series
from src.visualization.data_handler import DataHandler


class ComparisonModel:
    def __init__(self):
        self.data_loader = DataLoader()
        self.datasets = {}
        self.visualization_handlers = {}
        self.identities = {}
        self.timelines = {}
        self.baseline_name = None
        # Adjustable display policy, not a physical detection threshold.
        self.max_gap_sec = 0.1

    def load_file(self, filepath):
        name = os.path.basename(filepath)
        base, ext = os.path.splitext(name)
        count = 1
        while name in self.datasets:
            name = f'{base}_{count}{ext}'
            count += 1
        df = self.data_loader.load_result_csv(filepath)
        identity = read_identity(df)
        timeline = timeline_from_frame(df)
        if identity.source_kind not in SOURCE_KINDS - {'unknown_legacy'}:
            reason = 'Synchronization unavailable: unknown or invalid source class; individual review only'
            timeline = replace(timeline, reason='; '.join(filter(None, (timeline.reason, reason))))
        handler = DataHandler()
        visualizable = handler.load_analysis_result(filepath)
        self.datasets[name] = df
        self.identities[name] = identity
        self.timelines[name] = timeline
        if visualizable:
            self.visualization_handlers[name] = handler
        if self.baseline_name is None:
            self.baseline_name = name
        return name

    def set_baseline(self, name):
        if name in self.datasets:
            self.baseline_name = name

    def remove_file(self, name):
        for entries in (self.datasets, self.visualization_handlers, self.identities, self.timelines):
            entries.pop(name, None)
        if self.baseline_name == name:
            self.baseline_name = next(iter(self.datasets), None)

    def exclusion_reasons(self, name):
        if self.baseline_name is None:
            return ['No baseline selected']
        reasons = compatibility_reasons(self.identities[self.baseline_name], self.identities[name])
        for label, key in (('baseline', self.baseline_name), ('file', name)):
            if self.timelines[key].reason:
                reasons.append(f'{label} {self.timelines[key].reason}')
        return list(dict.fromkeys(reasons))

    def status_text(self, name):
        source = self.identities[name].source_kind
        reasons = self.exclusion_reasons(name)
        summary = 'Comparison compatible' if not reasons else 'Excluded from aggregation / baseline differences'
        time_status = self.timelines[name].reason or 'Actual-time alignment available'
        return f'{source} · {summary}\n{time_status}'

    def get_summary_differences(self):
        """Per-file values and compatible baseline differences. No mean/statistics."""
        if self.baseline_name is None:
            return {}

        def summary(df):
            result = {}
            seen = set()
            for i, col in enumerate(df.columns):
                if col[:2] == ('Analysis', 'DropPostureSummary'):
                    series = df.iloc[:, i]
                    result[col[2]] = series.iloc[0] if col[2] not in seen and series.nunique(dropna=False) == 1 else np.nan
                    seen.add(col[2])
            return result

        baseline = summary(self.datasets[self.baseline_name])
        results = {}
        for name, df in self.datasets.items():
            values = summary(df)
            reasons = self.exclusion_reasons(name)
            diffs = {}
            for key, value in values.items():
                reference = baseline.get(key)
                if reasons or pd.isna(value) or pd.isna(reference):
                    diffs[key] = None
                elif isinstance(value, (bool, np.bool_)) or isinstance(reference, (bool, np.bool_)):
                    diffs[key] = 'Match' if value == reference else str(value)
                else:
                    try:
                        diffs[key] = value - reference
                    except TypeError:
                        diffs[key] = 'Match' if value == reference else str(value)
            results[name] = {'summary': values, 'diffs': diffs, 'reasons': reasons,
                             'source': self.identities[name].source_kind}
        return results

    def get_timeseries_data(self, group, component, metric, *, individual=None):
        result = {}
        for name, df in self.datasets.items():
            if individual is not None and name != individual:
                continue
            column = (group, component, metric)
            positions = [i for i, value in enumerate(df.columns) if value == column]
            if len(positions) != 1:
                continue
            timeline = self.timelines[name]
            values = pd.to_numeric(df.iloc[:, positions[0]], errors='coerce').to_numpy(dtype=float)
            if individual is not None:
                xs = timeline.times if timeline.times is not None else np.arange(len(df))
            elif timeline.aligned:
                xs = timeline.elapsed
            else:
                continue
            result[name] = segmented_series(values, timeline.times, self.max_gap_sec,
                                            origin=0. if individual is not None else timeline.t1) if timeline.times is not None else pd.Series(values, index=xs)
        return result

    def elapsed_bounds(self):
        timelines = [value.elapsed for value in self.timelines.values() if value.aligned]
        return (min(value[0] for value in timelines), max(value[-1] for value in timelines)) if timelines else None

    def playback_row(self, name, elapsed):
        return self.timelines[name].nearest_row(elapsed, self.max_gap_sec)
