"""Exercise FRAME-1/1 with generated fixtures and a public reference profile."""
import numpy as np
import pandas as pd
import pytest

from bma_shared_core import nearest_sample_position
from test_shared_row_adapter import VECTORS


def prepare_frame_table(times, frames):
    numeric_frames = pd.to_numeric(pd.Series(frames, dtype=object), errors="coerce")
    if frames is None or numeric_frames.isna().all():
        numeric_frames = np.arange(len(times))
    else:
        numeric_frames -= numeric_frames.min()
    table = pd.DataFrame({
        "frame": numeric_frames,
        "time": pd.to_numeric(pd.Series(times), errors="coerce"),
    }).dropna()
    table["frame"] = table["frame"].astype(int)
    return table.drop_duplicates().sort_values("frame").reset_index(drop=True)


def map_target(table, target, gap):
    times = table["time"].to_numpy()
    if not len(times) or target < times.min() or target > times.max():
        return None
    try:
        row = nearest_sample_position(times, target)
    except ValueError:
        row = (table["time"] - target).abs().idxmin()
    selected = table.iloc[row]
    error = abs(float(selected["time"]) - target)
    if not np.isfinite(gap) or gap <= 0:
        raise ValueError("Expected a positive finite gap")
    if error > 0:
        ordered = np.unique(times)
        right = np.searchsorted(ordered, target)
        intervals = np.diff(ordered)
        median_dt = np.median(intervals) if len(intervals) else 0
        if 0 < right < len(ordered) and intervals[right - 1] > max(gap, 3 * median_dt):
            return None
    if error > gap:
        return None
    return int(selected["frame"]), float(selected["time"]), error


def alignment_reason(times, frames, summary, gap):
    first = summary.iloc[0]
    detected = first["T1Detected"]
    if pd.isna(detected):
        return "invalid_flag"
    try:
        detected = bool(float(detected))
    except (ValueError, TypeError):
        flag = str(detected).strip().lower()
        if flag not in ("true", "yes", "y", "false", "no", "n"):
            return "invalid_flag"
        detected = flag in ("true", "yes", "y")
    if not detected:
        return "t1_not_detected"
    try:
        t1 = float(first.get("T1MinusTimeSec"))
    except (ValueError, TypeError):
        return "invalid_t1"
    if not np.isfinite(t1):
        return "invalid_t1"
    if map_target(prepare_frame_table(times, frames), t1, gap) is None:
        return "t1_timestamp_gap_too_large"
    return ""


def frame_lookup(times, frames, t1, reason, relative, gap):
    if reason:
        return None
    try:
        relative = float(relative)
    except (ValueError, TypeError):
        return None
    if not np.isfinite(relative):
        return None
    mapping = map_target(prepare_frame_table(times, frames), t1 + relative, gap)
    if mapping is None:
        return None
    frame, timestamp, error = mapping
    return {
        "frame_index": frame, "timestamp_sec": timestamp, "error_sec": error,
        "requested_relative_time_sec": relative, "relative_time_sec": timestamp - t1,
    }


@pytest.mark.parametrize("case", VECTORS, ids=lambda case: case["id"])
def test_fixed_frame_and_kernel_profiles(case):
    times, frames = case["times"], case["frames"]
    t1, relative, gap = case["t1"], case["relative"], case["allowed_gap"]
    expected = case["expected"]
    if expected["kernel"] == "ValueError":
        with pytest.raises(ValueError):
            nearest_sample_position(times, t1 + relative)
    else:
        assert nearest_sample_position(times, t1 + relative) == expected["kernel"]
    summary = pd.DataFrame({"T1Detected": [True] * len(times), "T1MinusTimeSec": t1})
    reason = alignment_reason(times, frames, summary, gap)
    assert (not reason) is expected["frame_aligned"]
    if not expected["frame_aligned"]:
        assert reason == "t1_timestamp_gap_too_large"
    mapping = frame_lookup(times, frames, t1, reason, relative, gap)
    if expected["frame"] is None:
        assert mapping is None
    else:
        assert mapping == {
            "frame_index": expected["frame"], "timestamp_sec": expected["time"],
            "error_sec": expected["error"], "requested_relative_time_sec": relative,
            "relative_time_sec": expected["time"] - t1,
        }


@pytest.mark.parametrize(("times", "frames", "expected"), [
    ([np.nan, 0, 0, 0.125], [99, 100.25, 100.75, 104.5], [(1, 0), (5, 0.125)]),
    ([0, 0.125], ["bad", "bad"], [(0, 0), (1, 0.125)]),
    ([0, 0.125], ["bad", 100], [(0, 0.125)]),
    ([0, 0.125], None, [(0, 0), (1, 0.125)]),
])
def test_frame_preparation(times, frames, expected):
    assert list(prepare_frame_table(times, frames).itertuples(index=False, name=None)) == expected


def test_frame_summary_and_override_order():
    times, frames = [0.0, 0.125], [100, 104]
    assert alignment_reason(times, frames, pd.DataFrame({"T1Detected": [False]}), 0.05) == "t1_not_detected"
    for flag in ["yes", 2, "nan"]:
        summary = pd.DataFrame({"T1Detected": [flag], "T1MinusTimeSec": [0.0]})
        assert alignment_reason(times, frames, summary, 0.05) == ""
    summary = pd.DataFrame({"T1Detected": [np.nan], "T1MinusTimeSec": [0.0]})
    assert alignment_reason(times, frames, summary, 0.05) == "invalid_flag"
    assert frame_lookup(times, frames, 0.0, "", -1, 0) is None
    with pytest.raises(ValueError, match="positive finite gap"):
        frame_lookup(times, frames, 0.0, "", 0, 0)


@pytest.mark.parametrize(("flags", "anchors"), [
    ([True, False], [0.0, 0.0]),
    ([True, True], [0.0, 0.125]),
])
def test_frame_alignment_uses_first_summary_row(flags, anchors):
    times, frames = [0.0, 0.125], [100, 104]
    summary = pd.DataFrame({"T1Detected": flags, "T1MinusTimeSec": anchors})
    assert alignment_reason(times, frames, summary, 0.05) == ""


@pytest.mark.parametrize(("field", "value", "expected"), [
    pytest.param("relative", "bad", None, id="F1-R1"),
    pytest.param("relative", None, None, id="F1-R2"),
    pytest.param("T1MinusTimeSec", "bad", "invalid_t1", id="F1-T1"),
    pytest.param("T1Detected", "bad", "invalid_flag", id="F1-D1"),
])
def test_frame_rejection_counterexamples(field, value, expected):
    times, frames = [0.0, 0.125], [100, 104]
    if field == "relative":
        assert frame_lookup(times, frames, 0.0, "", value, 0.05) is expected
    else:
        values = {"T1Detected": [True], "T1MinusTimeSec": [0.0]}
        values[field] = [value]
        summary = pd.DataFrame(values)
        # For these malformed values only: invalid_t1 -> t1_time_invalid;
        # invalid_flag -> t1_detected_invalid. Missing t1 also uses invalid_t1.
        assert alignment_reason(times, frames, summary, 0.05) == expected


@pytest.mark.parametrize(("flag", "expected"), [
    (False, "t1_not_detected"), (0, "t1_not_detected"), ("false", "t1_not_detected"),
    (np.nan, "invalid_flag"), ("nan", ""), ("yes", ""), ("y", ""), (2, ""), (-1, ""),
])
def test_frame_legacy_flag_interpretation(flag, expected):
    summary = pd.DataFrame({"T1Detected": [flag], "T1MinusTimeSec": [0.0]})
    assert alignment_reason([0.0, 0.125], [100, 104], summary, 0.05) == expected


def test_frame_rejection_precedes_table_preparation_and_gap_validation():
    times, frames = [0.0, 0.125], [np.inf, 104]
    summary = pd.DataFrame({"T1Detected": ["bad"], "T1MinusTimeSec": ["bad"]})
    assert alignment_reason(times, frames, summary, 0) == "invalid_flag"
    summary.loc[0, "T1Detected"] = True
    assert alignment_reason(times, frames, summary, 0) == "invalid_t1"
    assert frame_lookup(times, frames, 0.0, "unaligned", "bad", 0) is None
    assert frame_lookup(times, frames, 0.0, "", None, 0) is None
