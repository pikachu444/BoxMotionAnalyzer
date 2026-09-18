import os
from dataclasses import replace

import numpy as np
import pandas as pd

from src.analysis.pipeline.data_loader import DataLoader
from src.analysis.pipeline.artifact_io import _sha256_file
from src.utils.artifact_metadata import read_identity, compatibility_reasons, SOURCE_KINDS, FIELDS
from src.utils.result_time import timeline_from_frame, segmented_series
from src.visualization.data_handler import DataHandler
from src.analysis.compare.impact_metrics import calculate_impact_metrics, METRICS, MetricValue
from src.analysis.compare.contact_metrics import calculate_contact_comparison
from src.analysis.compare.posture_metrics import (
    calculate_posture_metrics, POSTURE_METRICS, FACE_METRICS, repeat_reasons, context_difference, category_reference,
)
from src.analysis.compare.observation_resolution import resolve_observations, POLICY
from src.config.data_columns import is_corner_id_column, format_result_value


FILE_COLORS = ('#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd',
               '#8c564b', '#e377c2', '#7f7f7f', '#bcbd22', '#17becf')


class ComparisonModel:
    def __init__(self):
        self.data_loader = DataLoader()
        self.datasets = {}
        self.file_paths = {}
        self.file_hashes = {}
        self.file_colors = {}
        self._next_color = 0
        self.visualization_handlers = {}
        self.identities = {}
        self.timelines = {}
        self.impact_results = {}
        self.contact_results = {}
        self.posture_results = {}
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
        posture = calculate_posture_metrics(df)
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
        if name not in self.file_colors:
            self.file_colors[name] = FILE_COLORS[self._next_color % len(FILE_COLORS)]
            self._next_color += 1
        self.identities[name] = identity
        self.timelines[name] = timeline
        self.impact_results[name] = impact
        self.contact_results[name] = contact
        self.posture_results[name] = posture
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
        for entries in (self.datasets, self.file_paths, self.file_hashes, self.file_colors, self.visualization_handlers, self.identities, self.timelines,
                        self.impact_results, self.contact_results, self.posture_results):
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
            summary += '; repeats ineligible' if repeat_reasons else '; see metric-specific repeat status'
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
        diagnostic_keys = {'FirstImpactContact': 'first_contact', 'ContactConfidence': 'contact_confidence',
                           'FinalFace': 'final_face'}
        results = {}
        for name, df in self.datasets.items():
            values = summary(df)
            reasons = self.exclusion_reasons(name)
            metric_reasons = {column: self.impact_results[name].metrics[key].reason
                              for column, key in diagnostic_keys.items()}
            diffs = {}
            for key, value in values.items():
                reference = baseline.get(key)
                reference_invalid = (key in diagnostic_keys and
                    self.impact_results[self.baseline_name].metrics[diagnostic_keys[key]].reason)
                if reasons or metric_reasons.get(key) or reference_invalid or pd.isna(value) or pd.isna(reference):
                    diffs[key] = None
                elif is_corner_id_column(('Analysis', 'DropPostureSummary', key)):
                    column = ('Analysis', 'DropPostureSummary', key)
                    rendered = format_result_value(column, value)
                    reference_label = format_result_value(column, reference)
                    diffs[key] = ('Match' if rendered == reference_label else reference_label)
                    if rendered == 'Unknown' or reference_label == 'Unknown':
                        diffs[key] = None
                elif isinstance(value, (bool, np.bool_)) or isinstance(reference, (bool, np.bool_)):
                    diffs[key] = 'Match' if value == reference else str(reference)
                else:
                    try:
                        diffs[key] = value - reference
                    except TypeError:
                        diffs[key] = 'Match' if value == reference else str(reference)
            results[name] = {'summary': values, 'diffs': diffs, 'reasons': reasons,
                             'source': self.identities[name].source_kind,
                             'metric_reasons': metric_reasons,
                             'diagnostic_field_errors': self.impact_results[name].evidence['diagnostic_field_errors'],
                             'first_event': self.impact_results[name].evidence['first_event']}
        return results

    def get_impact_comparison(self):
        """Per-observation values and compatible, distinct-observation summaries."""
        if self.baseline_name is None:
            return {'files': {}, 'statistics': {}, 'source': None}
        variants = [self._variant(name, self.impact_results[name].metrics,
                                  self.exclusion_reasons(name)) for name in self.datasets]
        resolution = resolve_observations(variants, {key: d['kind'] for key, d in METRICS.items()})
        files = resolution['files']
        for name, item in files.items():
            item['result'] = self.impact_results[name]
        statistics = {}
        baseline = self.impact_results[self.baseline_name]
        for key, descriptor in METRICS.items():
            values = [metrics[key]['value'] for metrics in resolution['observations'].values()
                      if metrics[key]['status'] in ('contributing', 'equivalent')]
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
        return {**resolution, 'statistics': statistics,
                'source': self.identities[self.baseline_name].source_kind}

    def get_posture_comparison(self):
        if self.baseline_name is None:
            return {'files': {}, 'statistics': {}, 'source': None}
        baseline = self.posture_results[self.baseline_name]
        common_reasons = {name: compatibility_reasons(self.identities[self.baseline_name], self.identities[name])
                          for name in self.datasets}
        baseline_observation = self.impact_results[self.baseline_name].observation_key
        groups = {}
        for name, result in self.posture_results.items():
            observation = self.impact_results[name].observation_key
            if observation is not None and not common_reasons[name]:
                groups.setdefault(observation, []).append((name, result))
        contexts, conflicts = {}, {}
        for observation, members in groups.items():
            contexts[observation] = {}
            members.sort(key=lambda pair: (self.file_hashes[pair[0]], self.file_paths[pair[0]]))
            for key, descriptor in POSTURE_METRICS.items():
                if key not in FACE_METRICS and not descriptor['whole']:
                    continue
                candidates = [result for _, result in members if not result.metrics[key].reason
                              and not repeat_reasons(result, result, key)]
                # Resolve every observation's contexts before applying cohort
                # gates; a selected baseline is not a preferred reprocessing.
                if any(context_difference(a, b, key) for i, a in enumerate(candidates) for b in candidates[i+1:]):
                    conflicts.setdefault(observation, {})[key] = 'Conflicting valid posture contexts for the same observation'
                elif candidates:
                    contexts[observation][key] = candidates[0]
        baseline_contexts = contexts.get(baseline_observation, {})
        # A missing/corrupt scalar alone does not invalidate independently
        # verified geometry/window context. Use this only if no valid-value
        # context exists; invalid variants never veto a valid one above.
        for key, descriptor in POSTURE_METRICS.items():
            if (key in baseline_contexts or key in conflicts.get(baseline_observation, {})
                    or not (key in FACE_METRICS or descriptor['whole'])):
                continue
            fallback = [result for _, result in groups.get(baseline_observation, [])
                        if not repeat_reasons(result, result, key)]
            if fallback and not any(context_difference(a, b, key)
                                    for i, a in enumerate(fallback) for b in fallback[i+1:]):
                baseline_contexts[key] = fallback[0]
        variants = []
        for name, result in self.posture_results.items():
            # Actual time is validated by each metric. Missing t1 must not reject
            # whole-window diagnostics before their own support rules run.
            observation = self.impact_results[name].observation_key
            metrics = {}
            for key, metric in result.metrics.items():
                reason = repeat_reasons(result, result, key)
                needs_context = key in FACE_METRICS or POSTURE_METRICS[key]['whole']
                if needs_context and key not in conflicts.get(observation, {}):
                    if key not in baseline_contexts:
                        reason = '; '.join(filter(None, (reason, 'Baseline observation has no unambiguous valid posture comparison context')))
                    else:
                        reason = repeat_reasons(result, baseline_contexts[key], key)
                metrics[key] = MetricValue(metric.value, '; '.join(filter(None, (metric.reason, reason))))
            variants.append(self._variant(name, metrics, common_reasons[name]))
        resolution = resolve_observations(variants, {key: d['kind'] for key, d in POSTURE_METRICS.items()},
                                          metric_conflicts=conflicts)
        for name, item in resolution['files'].items():
            item['result'] = self.posture_results[name]
        statistics = {}
        for key, descriptor in POSTURE_METRICS.items():
            values = [metrics[key]['value'] for metrics in resolution['observations'].values()
                      if metrics[key]['status'] in ('contributing', 'equivalent')]
            if descriptor['kind'] == 'numeric':
                stats = dict(n=len(values), mean=float(np.mean(values)) if values else None,
                    min=min(values) if values else None, max=max(values) if values else None,
                    range=max(values) - min(values) if values else None)
            else:
                counts = {value: values.count(value) for value in sorted(set(values))}
                metric = baseline.metrics[key]
                reference = category_reference(metric.value) if not metric.reason else None
                stats = dict(n=len(values), counts=counts, reference=reference,
                             matching=counts.get(reference, 0) if reference is not None else None)
            statistics[key] = stats
        return {**resolution, 'statistics': statistics,
                'source': self.identities[self.baseline_name].source_kind}

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

    def _variant(self, name, metrics, reasons, *, local=False):
        observation = self.impact_results[name].observation_key
        return dict(name=name, sha256=self.file_hashes[name], path=self.file_paths[name],
                    observation_key=observation[:3] if local and observation is not None else observation,
                    reasons=reasons, metrics=metrics)

    def get_contact_comparison(self):
        """Local geometry uses its own gate; only eligible variants resolve."""
        stats = {'n': 0, 'Match': 0, 'Different': 0, 'Unclear': 0, 'excluded': 0, 'conflicts': 0}
        if self.baseline_name is None:
            return {'files': {}, 'statistics': stats, 'intended': '',
                    'observations': {}, 'resolution_policy': POLICY}
        baseline = self.contact_results[self.baseline_name]
        choices, common = {}, {}
        for name, contact in self.contact_results.items():
            reasons = self._contact_exclusion_reasons(name)
            if contact.registration_sha256 != baseline.registration_sha256:
                reasons.append('Contact registration differs from the baseline')
            common[name] = reasons
            observation = self.impact_results[name].observation_key
            key = observation[:3] if observation is not None else None
            if not reasons and key is not None and contact.target_key is not None:
                choices.setdefault(key, set()).add(contact.target_key)
        conflicts = {key: 'Conflicting intended contacts for the same observation'
                     for key, targets in choices.items() if len(targets) > 1}
        variants = []
        for name, contact in self.contact_results.items():
            reasons = list(common[name])
            if baseline.target_key is None:
                reasons.append('Baseline intended contact is unspecified')
            elif contact.target_key != baseline.target_key:
                reasons.append('Intended contact differs from the baseline')
            variants.append(self._variant(name,
                {'contact': MetricValue((contact.observed, contact.outcome), contact.reason)},
                reasons, local=True))
        resolution = resolve_observations(variants, {'contact': 'contact'}, group_conflicts=conflicts)
        for name, item in resolution['files'].items():
            item.update(result=self.contact_results[name], source=self.identities[name].source_kind)
            entry = item['metric_resolution']['contact']
            key = entry['observation_key']
            if not common[name] and key in conflicts:
                entry['group_reason'] = conflicts[key]
        for metrics in resolution['observations'].values():
            contact = metrics['contact']
            if contact['status'] == 'conflict':
                stats['conflicts'] += 1
            elif contact['status'] == 'invalid':
                stats['Unclear'] += 1
            else:
                stats[contact['value'][1]] += 1
                stats['n'] += 1
        # Historical file-based non-contribution count, not an observation count.
        stats['excluded'] = len(self.datasets) - stats['n'] - stats['Unclear']
        return {**resolution, 'statistics': stats, 'intended': baseline.intended}

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
