"""Versioned consistency of a recorded first event, not geometric verification.

The legacy producer uses the whole interval. This reader neither replays it with
new thresholds nor claims bounded first-contact evidence (issue #120).
"""
from dataclasses import asdict, dataclass
import json
import math

import numpy as np
import pandas as pd

from src.utils.artifact_metadata import read_identity, SOURCE_KINDS
from src.utils.processing_settings import validate_processing_record
from src.utils.result_time import timeline_from_frame, exceeds_gap_limit


SUMMARY = ('Analysis', 'DropPostureSummary')
CONTRACT_VERSION = 'recorded-first-event-consistency-v1'


@dataclass(frozen=True)
class FirstEventEvidence:
    state: str = ''
    status: str = 'unavailable'
    reasons: tuple[str, ...] = ()
    indices: tuple[int, ...] = ()
    times_s: tuple[float, ...] = ()
    contact_policy: str = ''
    gap_policy: str = 'not recorded; temporal adjacency only'
    contract_version: str = CONTRACT_VERSION
    geometry_verified: bool = False

    @property
    def valid(self):
        return self.status == 'recorded-consistent' and not self.reasons

    @property
    def reason(self):
        return '; '.join(self.reasons)

    def as_dict(self):
        return asdict(self)


def _constant(df, name):
    column = (*SUMMARY, name)
    positions = [i for i, value in enumerate(df.columns) if value == column]
    if len(positions) != 1:
        raise ValueError(f'{name}: missing or duplicate column')
    values = df.iloc[:, positions[0]]
    if not len(values) or values.nunique(dropna=False) != 1:
        raise ValueError(f'{name}: must be constant across the result')
    return values.iloc[0]


def _boolean(value, name):
    text = str(value).strip().lower()
    if text in ('true', '1', '1.0'):
        return True
    if text in ('false', '0', '0.0'):
        return False
    raise ValueError(f'{name}: invalid boolean')


def _number(value, name):
    if isinstance(value, (bool, np.bool_)):
        raise ValueError(f'{name}: expected a finite time')
    try:
        number = float(value)
    except (ValueError, TypeError):
        raise ValueError(f'{name}: expected a finite time') from None
    if not math.isfinite(number):
        raise ValueError(f'{name}: expected a finite time')
    return number


def validate_first_event(df, review=None):
    """Check declarations and actual-row bracketing without derivative support.

Non-resampled legacy output can establish a recorded event with the preceding
t1 sample and a following sample. This does not prove air-to-floor geometry or
persistence. Resampled legacy output lacks original-row identity and cannot do
so. An available scene gap policy also checks the prefix for hidden events.
"""
    state, policy = '', ''
    try:
        state = str(_constant(df, 'ContactState')).strip()
        if state not in ('NoContact', 'Approach', 'SustainedContact', 'ImpactEvent'):
            raise ValueError('ContactState: unknown state')
        flags, errors = {}, []
        for name in ('T1Detected', 'ImpactDetected'):
            try:
                flags[name] = _boolean(_constant(df, name), name)
            except ValueError as error:
                errors.append(str(error))
        if errors:
            raise ValueError('; '.join(errors))
        if state != 'ImpactEvent':
            stale = [name for name, value in flags.items() if value]
            for name in ('T1MinusTimeSec', 'FirstImpactTimeSec', 'FirstImpactContact'):
                if (*SUMMARY, name) in df.columns:
                    value = _constant(df, name)
                    if not pd.isna(value) and str(value).strip():
                        stale.append(name)
            if stale:
                raise ValueError(f'ContactState={state} conflicts with ' + ', '.join(stale))
            if state == 'NoContact':
                confidence = _number(_constant(df, 'ContactConfidence'), 'ContactConfidence')
                if confidence != 0:
                    raise ValueError('ContactConfidence: NoContact requires the recorded zero score')
            return FirstEventEvidence(state=state, status='no-impact',
                                      reasons=(f'No impact declared ({state})',))
        for name, value in flags.items():
            if not value:
                errors.append(f'{name}=False conflicts with ContactState=ImpactEvent')
        if errors:
            raise ValueError('; '.join(errors))
        t1 = _number(_constant(df, 'T1MinusTimeSec'), 'T1MinusTimeSec')
        impact = _number(_constant(df, 'FirstImpactTimeSec'), 'FirstImpactTimeSec')
        timeline = timeline_from_frame(df)
        if not timeline.aligned:
            raise ValueError(timeline.reason)
        matches = np.flatnonzero(timeline.times == impact)
        if len(matches) != 1:
            raise ValueError('FirstImpactTimeSec: must match one actual timeline sample')
        index = int(matches[0])
        if index == 0 or index + 1 >= len(df):
            raise ValueError('First contact needs a preceding sample and a following event sample')
        if timeline.times[index - 1] != t1:
            raise ValueError('T1MinusTimeSec: must be the actual sample immediately before first impact')

        identity = read_identity(df)
        if identity.errors:
            raise ValueError('; '.join(identity.errors))
        artifact = identity.values
        if artifact.get('SchemaVersion') != '1' or identity.source_kind not in SOURCE_KINDS - {'unknown_legacy'}:
            raise ValueError('First-event source/schema provenance unavailable; legacy individual view only')
        if (artifact.get('CoordinatePolicy') != 'world-y-up-box-local-fixed-center-v1'
                or artifact.get('UnitsPolicy') != 'bma-mm-s-rotvec-rad-summary-deg-v1'):
            raise ValueError('First-event coordinate/time units policy is unconfirmed')
        error = validate_processing_record(artifact.get('ProcessingSemanticsVersion'), artifact.get('ProcessingSettingsJson'))
        if error:
            raise ValueError(error)
        settings = json.loads(artifact['ProcessingSettingsJson'])
        policy = settings['postprocess'].get('contact_policy', '')
        if policy != 'drop-posture-evidence-v1':
            raise ValueError('Unsupported recorded contact policy')
        if settings['result_resampling'].get('enabled') is not False:
            raise ValueError('Original observed event samples are unproven in legacy resampled results')

        gap_policy = 'not recorded; temporal adjacency only'
        if review is not None:
            row = review['candidate']
            if row.get('evidence_status') != 'current':
                raise ValueError('Scene evidence changed; review it again')
            if 'tracking_jump' in (row.get('evidence_class'), row.get('motion')):
                raise ValueError('Scene is marked as a tracking jump, not supported physical motion')
            if row.get('left_censored'):
                raise ValueError('An earlier unobserved interval may hide first contact')
            if not row['start'] <= timeline.times[index - 1] < timeline.times[index + 1] <= row['end']:
                raise ValueError('First-event bracket extends outside the reviewed interval')
            detection = review.get('detection')
            if not isinstance(detection, dict) or not isinstance(detection.get('settings'), dict):
                raise ValueError('Recorded scene gap policy is unavailable')
            factor = detection['settings'].get('gap_factor')
            if factor is not None:
                factor = _number(factor, 'gap_factor')
                if factor <= 1:
                    raise ValueError('Recorded tracking-gap policy is invalid')
                limit = factor * float(np.median(np.diff(timeline.times)))
                if any(exceeds_gap_limit(a, b, limit) for a, b in
                       zip(timeline.times[:index + 1], timeline.times[1:index + 2])):
                    raise ValueError('First-event prefix or bracket crosses a recorded tracking gap')
                gap_policy = 'recorded scene gap_factor times median actual dt'
        indices = (index - 1, index, index + 1)
        return FirstEventEvidence(state=state, status='recorded-consistent', indices=indices,
                                  times_s=tuple(float(timeline.times[i]) for i in indices),
                                  contact_policy=policy, gap_policy=gap_policy)
    except (ValueError, TypeError, KeyError, AttributeError, OverflowError) as error:
        return FirstEventEvidence(state=state, contact_policy=policy, reasons=(str(error),))
