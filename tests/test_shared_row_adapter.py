"""Fixed ROW-1/1 expectations, including legacy direct calls."""
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from src.utils.result_time import (
    T1_COLUMN,
    T1_DETECTED_COLUMN,
    TIME_COLUMN,
    ResultTimeline,
    timeline_from_frame,
)

VECTORS = json.loads(
    (Path(__file__).parent / "fixtures" / "shared_time_profiles.json").read_text(encoding="utf-8")
)


def result_frame(times, detected=True, t1=0.0):
    return pd.DataFrame({
        TIME_COLUMN: times,
        T1_DETECTED_COLUMN: detected,
        T1_COLUMN: t1,
    })


@pytest.mark.parametrize("case", VECTORS, ids=lambda case: case["id"])
def test_row_profile(case):
    timeline = timeline_from_frame(result_frame(case["times"], t1=case["t1"]))
    assert timeline.aligned is case["expected"]["row_aligned"]
    assert timeline.nearest_row(case["relative"], case["allowed_gap"]) == case["expected"]["row"]
    if not timeline.aligned:
        assert timeline.reason == "Time unavailable: duplicate or decreasing timestamps"


def test_legacy_direct_lookup():
    times = np.array([0.0, 0.125, 0.125, 0.25])
    assert ResultTimeline(times, 0.0, "").nearest_row(0.1875, 0.125) == 2
    assert not timeline_from_frame(result_frame(times)).aligned


def test_unrelated_extreme_interval_does_not_change_lookup():
    timeline = ResultTimeline(np.array([-1.7e308, 1.0e308, 1.1e308]), 0.0, "")
    with np.errstate(over="raise"):
        assert timeline.nearest_row(1.04e308, 1.5e307) == 1


@pytest.mark.parametrize("detected", ["yes", 2, "nan"])
def test_row_does_not_use_frame_flag_coercion(detected):
    timeline = timeline_from_frame(result_frame([0.0, 0.125], detected=detected))
    assert timeline.reason == "Alignment unavailable: T1Detected is not true"


def test_row_reports_summary_structure_before_false_flag():
    missing = result_frame([0.0, 0.125], detected=False).drop(columns=[T1_COLUMN])
    assert timeline_from_frame(missing).reason == "Alignment unavailable: missing T1MinusTimeSec"
    for field, values in [(T1_DETECTED_COLUMN, [True, False]), (T1_COLUMN, [0.0, 0.125])]:
        frame = result_frame([0.0, 0.125])
        frame[field] = values
        assert timeline_from_frame(frame).reason == (
            f"Alignment unavailable: {field[2]} must be a single constant column"
        )


def test_row_gap_and_malformed_query_order():
    timeline = timeline_from_frame(result_frame([0.0, 0.125]))
    assert timeline.nearest_row(0.0, 0) == 0
    assert timeline.nearest_row(-1.0, "bad gap") is None
    assert timeline.nearest_row(np.nan, "bad gap") is None
    assert timeline.nearest_row(np.inf, 0.125) is None
    assert timeline.nearest_row(0.03125, 0) is None
    with pytest.raises(ValueError, match="convert string to float"):
        timeline.nearest_row(0.03125, "bad gap")
    with pytest.raises(TypeError):
        timeline.nearest_row("bad query", 0.125)
    with pytest.raises(TypeError):
        timeline.nearest_row(None, 0.125)
    with pytest.raises(ValueError, match="ambiguous"):
        timeline.nearest_row(np.array([0.0, 0.125]), 0.125)


def test_row_gap_roundoff():
    for end, expected in [(1.1, 0), (1.1 + 1e-10, None)]:
        timeline = timeline_from_frame(result_frame([1.0, end], t1=1.0))
        assert timeline.nearest_row(0.01, 0.1) == expected


def test_comparison_playback_uses_shared_position(tmp_path, monkeypatch):
    from comparison_fixtures import write_proc
    from bma_shared_core import nearest_sample_position
    from src.analysis.compare.data_model import ComparisonModel
    from src.utils import result_time, sample_selection

    assert sample_selection.nearest_sample_position is nearest_sample_position
    assert result_time.nearest_sample_position is nearest_sample_position
    observed = []

    def track(times, target):
        observed.append((times.tolist(), target))
        return nearest_sample_position(times, target)

    monkeypatch.setattr(result_time, "nearest_sample_position", track)
    model = ComparisonModel()
    name = model.load_file(str(write_proc(tmp_path / "shared.proc", times=(0.0, 0.0625, 0.125), t1=0.0)))
    assert model.playback_row(name, 0.046875) == 1
    assert observed == [([0.0, 0.0625, 0.125], 0.046875)]
