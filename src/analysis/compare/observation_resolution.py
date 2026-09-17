"""Resolve already validated metric variants without selecting an authority.

Capture identity and compatibility are supplied by the caller. File hashes only
identify evidence; they never create a trial or rank processing revisions.
"""
import math
from numbers import Real


POLICY = 'canonical-exact-v1'


def canonical_value(value, kind):
    if kind == 'numeric':
        if isinstance(value, bool) or not isinstance(value, Real):
            raise ValueError('Expected a finite numeric value')
        value = float(value)
        if not math.isfinite(value):
            raise ValueError('Expected a finite numeric value')
        return 0.0 if value == 0 else value
    if kind == 'contact':
        if (not isinstance(value, tuple) or len(value) != 2 or
                not value[0] or value[1] not in ('Match', 'Different')):
            raise ValueError('Valid observed contact and outcome unavailable')
        return value
    if not isinstance(value, str) or not value:
        raise ValueError('Valid category unavailable')
    return value


def resolve_observations(variants, kinds, *, group_conflicts=None, metric_conflicts=None):
    """Return per-metric evidence and stable observation order, with no I/O.

Each variant has name/sha256/path/observation_key/reasons/metrics. Metrics are
objects with value and reason attributes. A reason always vetoes its value.
group_conflicts is used for conflicting independent Contact intentions only.
metric_conflicts carries independently validated, per-observation metric context
conflicts (for example incompatible whole-window definitions of reprocessings).
"""
    groups, files = {}, {}
    for variant in variants:
        name, key = variant['name'], variant['observation_key']
        reasons = list(variant['reasons'])
        if key is None:
            reasons.append('Reviewed observation identity unavailable')
        files[name] = {'reasons': list(dict.fromkeys(reasons)), 'metric_resolution': {}}
        for metric, kind in kinds.items():
            raw = variant['metrics'][metric]
            value, reason = None, raw.reason
            if not reason:
                try:
                    value = canonical_value(raw.value, kind)
                except (ValueError, TypeError, OverflowError) as error:
                    reason = str(error)
            files[name]['metric_resolution'][metric] = dict(
                status='ineligible' if reasons else 'invalid' if reason else 'contributing',
                value=value, reason=reason, observation_key=key,
                sha256=variant['sha256'], path=variant['path'])
        if not reasons:
            groups.setdefault(key, []).append(variant)
    observations = {}
    for key in sorted(groups, key=repr):
        members = sorted(groups[key], key=lambda v: (v['sha256'], v['path'], v['name']))
        resolved = {}
        for metric in kinds:
            entries = [dict(file=v['name'], **files[v['name']]['metric_resolution'][metric]) for v in members]
            valid = [entry for entry in entries if not entry['reason']]
            values = {entry['value'] for entry in valid}
            metric_conflict = (metric_conflicts or {}).get(key, {}).get(metric, '')
            forced = (group_conflicts or {}).get(key, '') or metric_conflict
            conflict = bool(forced) or len(values) > 1
            status = 'conflict' if conflict else 'invalid' if not valid else 'equivalent' if len(valid) > 1 else 'contributing'
            reason = (forced or 'Conflicting valid variants disagree (canonical exact equality)') if conflict else ''
            value = next(iter(values)) if valid and not conflict else None
            for entry in entries:
                # Invalid values remain invalid even when other valid values conflict.
                if not entry['reason']:
                    entry.update(status=status, reason=reason)
                files[entry['file']]['metric_resolution'][metric].update(
                    status=entry['status'], reason=entry['reason'])
            resolved[metric] = dict(status=status, value=value, reason=reason,
                                    reason_code='conflicting_metric_context' if metric_conflict else
                                    'conflicting_valid_variants' if conflict and not forced else
                                    'conflicting_intended_contacts' if forced else
                                    'no_valid_variant' if not valid else '',
                                    sources=[entry['file'] for entry in valid] if not conflict else [],
                                    variants=entries)
        observations[key] = resolved
    return dict(files=files, observations=observations, resolution_policy=POLICY)
