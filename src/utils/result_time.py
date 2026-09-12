"""One physical time contract for result readers and comparison consumers."""
import csv
from dataclasses import dataclass

import numpy as np
import pandas as pd
from src.utils.artifact_metadata import DIMENSIONS

TIME_COLUMN = ('Info', 'Time', 'Time')
LEGACY_TIME_COLUMN = ('Time', 'Time', 'Time')
T1_COLUMN = ('Analysis', 'DropPostureSummary', 'T1MinusTimeSec')
T1_DETECTED_COLUMN = ('Analysis', 'DropPostureSummary', 'T1Detected')


def exceeds_gap_limit(left, right, limit):
    """Tolerate representation roundoff only, capped at one picosecond.

    A large absolute clock must not turn clock precision into a physical gap
    allowance. Beyond the cap, ambiguous coarse-clock intervals remain broken.
    """
    difference = float(right) - float(left)
    roundoff = min(1e-12, 4 * (np.spacing(abs(float(left))) +
                              np.spacing(abs(float(right))) + np.spacing(abs(float(limit)))))
    return difference > limit and difference - limit > roundoff


def read_result_frame(path):
    # pandas mangles duplicate headers. Restore the actual tuples so duplicates
    # can be validated rather than hidden behind .1 suffixes.
    with open(path, encoding='utf-8-sig', newline='') as stream:
        reader = csv.reader(stream)
        headers = [next(reader, []) for _ in range(3)]
    if not headers[0] or len({len(row) for row in headers}) != 1:
        raise ValueError('Result requires three equally sized header rows.')
    # Identity strings are opaque. Inference must not collapse ModelId 001 and
    # 1, convert a digits-only hash, or treat an ID such as NA as a missing value.
    converters = {i: str for i, col in enumerate(zip(*headers))
                  if (col[:2] == ('Info', 'Artifact') and col[2] not in DIMENSIONS)
                  or col == ('Info', 'MarkerCorrection', 'OriginalSourceSha256')}
    df = pd.read_csv(path, header=[0, 1, 2], converters=converters)
    df.columns = pd.MultiIndex.from_tuples(list(zip(*headers)))
    if df.empty:
        raise ValueError('Result contains no samples.')
    # Only identical copies of the same time tuple may be collapsed. Keep
    # conflicts visible to validation; never deduplicate sample rows.
    keep = []
    seen_time = {}
    for i, col in enumerate(df.columns):
        if col in (TIME_COLUMN, LEGACY_TIME_COLUMN):
            values = pd.to_numeric(df.iloc[:, i], errors='coerce').to_numpy(dtype=float)
            if col in seen_time and np.array_equal(seen_time[col], values, equal_nan=True):
                continue
            seen_time[col] = values
        keep.append(i)
    df = df.iloc[:, keep]
    return df


def time_values(df):
    candidates = [pd.to_numeric(df.iloc[:, i], errors='coerce').to_numpy(dtype=float)
                  for i, col in enumerate(df.columns) if col in (TIME_COLUMN, LEGACY_TIME_COLUMN)]
    # An index alone is never substituted for a declared time column.
    if not candidates:
        return None, 'Time unavailable: missing Info / Time / Time (seconds)'
    if any(not np.array_equal(candidates[0], values, equal_nan=True) for values in candidates[1:]):
        return None, 'Time unavailable: conflicting time columns'
    values = candidates[0]
    if not np.isfinite(values).all():
        return None, 'Time unavailable: nonfinite or nonnumeric sample'
    if len(values) == 0:
        return None, 'Time unavailable: empty samples'
    if np.any(np.diff(values) <= 0):
        return None, 'Time unavailable: duplicate or decreasing timestamps'
    return values, ''


def indexed_result(df):
    result = df.copy()
    values, error = time_values(df)
    result.attrs['time_error'] = error
    if values is not None:
        result.index = pd.Index(values, name='Time')
    return result


@dataclass(frozen=True)
class ResultTimeline:
    times: np.ndarray | None
    t1: float | None
    reason: str

    @property
    def aligned(self):
        return self.times is not None and self.t1 is not None and not self.reason

    @property
    def elapsed(self):
        return self.times - self.t1 if self.aligned else None

    def nearest_row(self, elapsed, max_gap_sec):
        """Actual sample, never interpolated. Ties use the earlier sample."""
        if not self.aligned:
            return None
        times = self.elapsed
        if elapsed < times[0] or elapsed > times[-1]:
            return None
        target = self.t1 + elapsed
        right = int(np.searchsorted(self.times, target))
        if right < len(times) and self.times[right] == target:
            return right
        if right == 0 or right == len(times) or exceeds_gap_limit(self.times[right - 1], self.times[right], max_gap_sec):
            return None
        return right - 1 if target - self.times[right - 1] <= self.times[right] - target else right


def timeline_from_frame(df):
    values, error = time_values(df)
    if error:
        return ResultTimeline(values, None, error)
    if TIME_COLUMN not in df.columns:
        return ResultTimeline(values, None, 'Alignment unavailable: canonical Info / Time / Time is missing (legacy time is individual-view only)')
    constants = []
    for col in (T1_DETECTED_COLUMN, T1_COLUMN):
        positions = [i for i, column in enumerate(df.columns) if column == col]
        if not positions:
            return ResultTimeline(values, None, f'Alignment unavailable: missing {col[2]}')
        series = df.iloc[:, positions[0]]
        if len(positions) != 1 or series.nunique(dropna=False) != 1:
            return ResultTimeline(values, None, f'Alignment unavailable: {col[2]} must be a single constant column')
        constants.append(series.iloc[0])
    detected, raw_t1 = constants
    if str(detected).strip().lower() not in ('true', '1', '1.0'):
        return ResultTimeline(values, None, 'Alignment unavailable: T1Detected is not true')
    try:
        t1 = float(raw_t1)
    except (TypeError, ValueError):
        t1 = float('nan')
    if not np.isfinite(t1) or not values[0] <= t1 <= values[-1]:
        return ResultTimeline(values, None, 'Alignment unavailable: T1MinusTimeSec is nonfinite or outside the file')
    return ResultTimeline(values, t1, '')


def segmented_series(values, recorded_times, max_gap_sec, *, origin=0.):
    """Inspect RAW recorded timestamps; subtract origin only for display x.

    Supplying already normalized elapsed time discards the clock's subtraction
    precision. Callers must pass recorded timestamps and a separate origin.
    """
    xs, ys = [], []
    times = np.asarray(recorded_times) - origin
    for i, (t, value) in enumerate(zip(times, values)):
        if i and exceeds_gap_limit(recorded_times[i - 1], recorded_times[i], max_gap_sec):
            xs.append((t + times[i - 1]) / 2)
            ys.append(np.nan)
        xs.append(t)
        ys.append(value)
    return pd.Series(ys, index=pd.Index(xs, name='Elapsed since t1− (s)'))
