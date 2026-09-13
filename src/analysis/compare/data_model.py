import os
from dataclasses import replace

import numpy as np
import pandas as pd

from src.analysis.pipeline.data_loader import DataLoader
from src.analysis.pipeline.artifact_io import _sha256_file
from src.utils.artifact_metadata import read_identity, compatibility_reasons, SOURCE_KINDS, FIELDS
from src.utils.result_time import timeline_from_frame, segmented_series
from src.visualization.data_handler import DataHandler
from src.analysis.compare.impact_metrics import calculate_impact_metrics, METRICS
from src.analysis.compare.contact_metrics import calculate_contact_comparison


class ComparisonModel:
    def __init__(self):
        self.data_loader = DataLoader()
        self.datasets = {}
        self.file_paths = {}
        self.file_hashes = {}
        self.visualization_handlers = {}
        self.identities = {}
        self.timelines = {}
        self.impact_results = {}
        self.contact_results = {}
        self.baseline_name = None
        # Adjustable display policy, not a physical detection threshold.
        self.max_gap_sec = 0.1

    def load_file(self, filepath, *, replace_name=None):
        if replace_name is not None:
            if replace_name not in self.datasets:
                raise ValueError('The result to replace is no longer loaded.')
            name = replace_name
        else:
            name = os.path.basename(filepath)
            base, ext = os.path.splitext(name)
            count = 1
            while name in self.datasets:
                name = f'{base}_{count}{ext}'
                count += 1
        digest = _sha256_file(filepath)
        df = self.data_loader.load_result_csv(filepath)
        identity = read_identity(df)
        timeline = timeline_from_frame(df)
        impact = calculate_impact_metrics(df)
        contact = calculate_contact_comparison(df)
        if identity.source_kind not in SOURCE_KINDS - {'unknown_legacy'}:
            reason = 'Synchronization unavailable: unknown or invalid source class; individual review only'
            timeline = replace(timeline, reason='; '.join(filter(None, (timeline.reason, reason))))
        handler = DataHandler()
        visualizable = handler.load_analysis_result(filepath)
        if digest != _sha256_file(filepath):
            raise ValueError('The result changed while loading. Open it again.')
        self.datasets[name] = df
        self.file_paths[name] = os.path.abspath(filepath)
        self.file_hashes[name] = digest
        self.identities[name] = identity
        self.timelines[name] = timeline
        self.impact_results[name] = impact
        self.contact_results[name] = contact
        self.visualization_handlers.pop(name, None)
        if visualizable:
            self.visualization_handlers[name] = handler
        if self.baseline_name is None:
            self.baseline_name = name
        return name

    def set_baseline(self, name):
        if name in self.datasets:
            self.baseline_name = name

    def remove_file(self, name):
        for entries in (self.datasets, self.file_paths, self.file_hashes, self.visualization_handlers, self.identities, self.timelines,
                        self.impact_results, self.contact_results):
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

    def status_text(self, name, *, repeat_reasons=None):
        source = self.identities[name].source_kind
        reasons = self.exclusion_reasons(name)
        summary = 'Comparison compatible' if not reasons else 'Baseline differences unavailable'
        if repeat_reasons is not None:
            summary += '; repeats excluded' if repeat_reasons else '; repeats included'
        time_status = self.timelines[name].reason or 'Actual-time alignment available'
        return f'{source}\n{summary}\n{time_status}'

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

    def get_impact_comparison(self):
        """Per-observation values and compatible, distinct-observation summaries."""
        if self.baseline_name is None:
            return {'files': {}, 'statistics': {}, 'source': None}
        order = [self.baseline_name] + [name for name in self.datasets if name != self.baseline_name]
        files, seen = {}, set()
        for name in order:
            result = self.impact_results[name]
            reasons = self.exclusion_reasons(name)
            if result.observation_key is None:
                reasons.append('Reviewed observation identity unavailable')
            elif not reasons:
                if result.observation_key in seen:
                    reasons.append('Same capture and reviewed interval already counted')
                else:
                    seen.add(result.observation_key)
            files[name] = {'result': result, 'reasons': reasons}
        statistics = {}
        baseline = self.impact_results[self.baseline_name]
        for key, descriptor in METRICS.items():
            values = [item['result'].metrics[key].value for item in files.values()
                      if not item['reasons'] and not item['result'].metrics[key].reason]
            if descriptor['kind'] == 'numeric':
                values = [float(value) for value in values
                          if isinstance(value, (int, float, np.number))
                          and not isinstance(value, (bool, np.bool_)) and np.isfinite(value)]
                stats = {'n': len(values), 'mean': float(np.mean(values)) if values else None,
                         'min': min(values) if values else None, 'max': max(values) if values else None,
                         'range': max(values) - min(values) if values else None}
            else:
                counts = {}
                for value in values:
                    if isinstance(value, str) and value:
                        counts[value] = counts.get(value, 0) + 1
                reference = baseline.metrics[key]
                stats = {'n': sum(counts.values()), 'counts': counts,
                         'reference': reference.value if not reference.reason else None}
                stats['matching'] = counts.get(stats['reference'], 0) if stats['reference'] is not None else None
            statistics[key] = stats
        return {'files': {name: files[name] for name in self.datasets},
                'statistics': statistics, 'source': self.identities[self.baseline_name].source_kind}

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

    def get_contact_comparison(self):
        """Per-file results; compatible repeats share an independently set target."""
        stats = {'n': 0, 'Match': 0, 'Different': 0, 'Unclear': 0, 'excluded': 0}
        if self.baseline_name is None:
            return {'files': {}, 'statistics': stats, 'intended': ''}
        baseline = self.contact_results[self.baseline_name]
        choices = {}
        for name, contact in self.contact_results.items():
            observation = self.impact_results[name].observation_key
            key = observation[:3] if observation is not None else None
            if key is not None and contact.target_key is not None:
                choices.setdefault(key, set()).add(contact.target_key)
        order = [self.baseline_name] + [n for n in self.datasets if n != self.baseline_name]
        files, seen = {}, set()
        for name in order:
            contact = self.contact_results[name]
            observation = self.impact_results[name].observation_key
            key = observation[:3] if observation is not None else None
            reasons = self._contact_exclusion_reasons(name)
            if baseline.target_key is None:
                reasons.append('Baseline intended contact is unspecified')
            elif contact.target_key != baseline.target_key:
                reasons.append('Intended contact differs from the baseline')
            if contact.registration_sha256 != baseline.registration_sha256:
                reasons.append('Contact registration differs from the baseline')
            if key is None:
                reasons.append('Reviewed observation identity unavailable')
            elif len(choices.get(key, set())) > 1:
                reasons.append('Conflicting intended contacts for the same observation')
            elif not reasons:
                if key in seen:
                    reasons.append('Same capture and reviewed interval already counted')
                else:
                    seen.add(key)
            files[name] = {'result': contact, 'reasons': reasons, 'source': self.identities[name].source_kind}
            if reasons:
                stats['excluded'] += 1
            else:
                stats[contact.outcome] += 1
                if contact.outcome != 'Unclear':
                    stats['n'] += 1
        return {'files': {n: files[n] for n in self.datasets}, 'statistics': stats, 'intended': baseline.intended}

    def _contact_exclusion_reasons(self, name):
        """Local contact observations do not require an inferred ISTA item.

        Keep all source/model/layout/settings/schema/time checks. Optional trial
        identity does not turn a local-geometry summary into an ISTA trial count.
        """
        optional = {'IstaType', 'ScenarioId', 'ScenarioKind'}
        missing = {f'{field}: missing' for field in optional}
        baseline, candidate = self.identities[self.baseline_name], self.identities[name]
        reasons = [f'{label} {reason}' for label, identity in (('baseline', baseline), ('file', candidate))
                   for reason in identity.exclusion_reasons() if reason not in missing]
        for field in FIELDS:
            if field not in optional | {'GeneratorVersion'} and baseline.values.get(field) != candidate.values.get(field):
                reasons.append(f'{field}: mismatch in local contact comparison')
        for label, key in (('baseline', self.baseline_name), ('file', name)):
            if self.timelines[key].reason:
                reasons.append(f'{label} {self.timelines[key].reason}')
        return list(dict.fromkeys(reasons))

    def elapsed_bounds(self):
        timelines = [value.elapsed for value in self.timelines.values() if value.aligned]
        return (min(value[0] for value in timelines), max(value[-1] for value in timelines)) if timelines else None

    def playback_row(self, name, elapsed):
        return self.timelines[name].nearest_row(elapsed, self.max_gap_sec)
