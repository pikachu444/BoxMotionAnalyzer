"""Measure existing prototype redraw costs; no face-drag implementation or acceptance."""
from __future__ import annotations

import argparse
import copy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
import subprocess
import sys
from time import perf_counter_ns

import matplotlib
import numpy as np
import PySide6
from PySide6.QtWidgets import QApplication

from finalize_exploded_visibility import FinalVisibilityPrototype
from generate_mockups import EXPECTED_HASHES, PLAN_SPEC
from generate_reviewed_mockups import settled
from src.simulation.marker_fixtures import load_profile, validate_profile


def measure(window, action, samples):
    calls = {"draw": 0, "layout_solver": 0}
    original_draw = window.canvas3.draw
    original_solver = window.untangle_ids

    def counted_draw(*args, **kwargs):
        calls["draw"] += 1
        return original_draw(*args, **kwargs)

    def counted_solver(*args, **kwargs):
        calls["layout_solver"] += 1
        return original_solver(*args, **kwargs)

    window.canvas3.draw = counted_draw
    window.untangle_ids = counted_solver
    records = []
    try:
        for _ in range(samples):
            calls.update(draw=0, layout_solver=0)
            start = perf_counter_ns()
            action()
            records.append(dict(elapsed_ms=(perf_counter_ns()-start)/1e6, **calls))
    finally:
        window.canvas3.draw = original_draw
        window.untangle_ids = original_solver
    times = [r["elapsed_ms"] for r in records]
    return dict(samples=records, median_ms=float(np.median(times)),
                min_ms=min(times), max_ms=max(times),
                p95_ms=float(np.percentile(times, 95)),
                p95_note="Descriptive quantile of this small sample, not an acceptance bound")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    app = QApplication.instance() or QApplication([])
    source = Path(__file__)
    report = dict(schema_version=1, plan_spec=PLAN_SPEC,
                  object_type="PrototypeNavigationCostProbe", utc=datetime.now(timezone.utc).isoformat(),
                  command=sys.argv, commit=subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
                  dirty=bool(subprocess.check_output(["git", "status", "--porcelain"], text=True).strip()),
                  source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
                  dependency_sha256={p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in
                                     (source.with_name("finalize_exploded_visibility.py"),
                                      source.with_name("compare_exploded_angles.py"),
                                      source.with_name("generate_exploded_mockups.py"),
                                      source.with_name("generate_marker_id_options.py"),
                                      source.with_name("generate_reviewed_mockups.py"),
                                      source.with_name("generate_preview_options.py"),
                                      source.with_name("generate_mockups.py"))},
                  environment=dict(os=platform.platform(), python=platform.python_version(),
                                   pyside=PySide6.__version__, matplotlib=matplotlib.__version__,
                                   qt_platform=app.platformName(), qt_process_dpr=app.primaryScreen().devicePixelRatio(),
                                   windows_os_scale_percent=100),
                  input=dict(kind="public-synthetic-static-geometry", profile_hashes=EXPECTED_HASHES,
                             seed=None, seed_reason="Deterministic static public geometry", units="mm",
                             frame="box-local-geometric-center", time_semantics="static-no-timeline"),
                  expected=dict(source_equality="exact canonical public fixture; draft/preview/applied unchanged",
                                cached_solver_calls=0, redraw_solver_calls=0, uncached_solver_calls=1),
                  timing_units="ms-per-synchronous-Python-call", timing_threshold=None,
                  timing_threshold_reason="Measurement only; no performance acceptance budget approved",
                  tolerance=None, tolerance_reason="Exact source equality; timing is a measured distribution",
                  native_status="not-executed-existing-capture-activation-error", production_changed=False,
                  status="measured-only", fresh=True, states=[],
                  prior_attempts=[dict(output="navigation_cost_100/evidence.json",
                                       status="work-count-invalid-timing-descriptive-only",
                                       reason="Read-only reviewer found redraw action captured original bound method before instrumentation; redraw count incorrectly0 instead of1. Fixed dynamic method lookup and assert; original timing samples retained without work-count acceptance.")],
                  limitations=["Not input-to-display latency or achieved interactive FPS.",
                               "No free rotation/pan/zoom or face drag tested here.",
                               "Current prototype synchronous draw cost; no production performance acceptance.",
                               "Qt125% is a process override, not an actual OS125% native test.",
                               "Constructor/startup excluded from timed samples; no real experimental dataset."])
    for example in ("32", "18"):
        assert validate_profile(load_profile(example=example)) == EXPECTED_HASHES[example]
        for size in ((1280, 960), (1920, 1080)):
            window = FinalVisibilityPrototype(example, size)
            settled(window, app, size)
            snapshots = copy.deepcopy((window.draft, window.valid_preview, window.applied))
            canonical = np.asarray([m["xyz_mm"] for m in load_profile(example=example)["markers"]])
            assert np.array_equal(window.source_xyz, canonical)
            state = dict(example=example, logical_size=list(size), dpr=window.devicePixelRatioF(),
                         canvas_pixel_size=[window.figure3.bbox.width, window.figure3.bbox.height],
                         profile_hash=EXPECTED_HASHES[example], camera=[25, 50, 30], radius_ratio=1,
                         measurements={})
            actions = [("existing_artists_redraw", lambda: window.canvas3.draw(), 12),
                       ("cached_names_overlay", window.selection_overlay, 5)]

            def uncached():
                window.layout_cache.clear()
                window.selection_overlay()

            actions.append(("uncached_names_layout", uncached, 3))
            for name, action, count in actions:
                result = measure(window, action, count)
                expected_solver = 1 if name == "uncached_names_layout" else 0
                assert all(r["layout_solver"] == expected_solver for r in result["samples"])
                if name == "existing_artists_redraw":
                    assert all(r["draw"] == 1 for r in result["samples"])
                assert (window.draft, window.valid_preview, window.applied) == snapshots
                assert np.array_equal(window.source_xyz, canonical)
                state["measurements"][name] = result
                print(json.dumps(dict(example=example, size=size, dpr=window.devicePixelRatioF(),
                                      action=name, median_ms=round(result["median_ms"], 2),
                                      draws=[r["draw"] for r in result["samples"]])), flush=True)
            state["source_difference"] = 0
            report["states"].append(state)
            (args.output/"evidence.json").write_text(json.dumps(report, indent=2, allow_nan=False)+"\n", encoding="utf-8")
            window.close()
    print(json.dumps(dict(status=report["status"], states=len(report["states"]), dpr=report["environment"]["qt_process_dpr"])), flush=True)


if __name__ == "__main__":
    main()
