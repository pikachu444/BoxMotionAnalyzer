# Scene review signal selection

Last Reviewed: 2026-09-18

#123 keeps the existing single plot and Signal combo. The smallest change is
to select the existing Vertical speed signal on first scene detection, with
Relative rotation immediately beside it in the combo. There is no dashboard,
registration prompt, filter or new detection algorithm.

```text
Existing capture plot: Vertical speed (mm/s)
Existing scene list and selected interval
Existing Details / Include / Exclude / Save actions
Plot options: [Markers…]  Signal [Vertical speed (mm/s) v]
                                Relative rotation (deg)
                                existing signals …
```

On re-detection of the same source, keep the currently selected raw or derived
signal if it exists and has finite samples. If it is absent/unavailable, prefer
usable vertical speed, then usable relative rotation, then the normal raw
position view. An unavailable series never inherits the previous curve.
Opening another source resets derived-signal choices; a saved scene review
still restores its own valid signal selection. Errors and cancellation keep
the existing valid review; source changes discard old result callbacks.

The axis carries the signal name and units. A short tooltip explains that
unregistered vertical speed uses the marker-layout reference point, not a
verified box-center or COM measurement. Registered center/COM meanings follow
the existing detector's inputs. Rotation remains available for tipping and
other movement; no type, item, threshold, boundary or Include/Exclude rule
changes. Existing editable ranges and save gates remain in place.

Review at 1510×800 / DPR1.25 with Details expanded, using independently
declared translation and rotation captures through real CSV readers/detection.
Check initial view, explicit selection, manual range edit/re-detect,
Include/Exclude and saved review/slices. Test missing/empty signals and source
switching separately; do not substitute injected detection results for the
real detector execution. Evidence and independent review belong to the PR.

## Review and execution

The independent preimplementation review accepted this layout and required
finite-sample checks on the actual selected raw columns, retaining the latest
selection at completion, and checking old worker/source callbacks. These are
implemented using the existing source revision/path/SHA and Qt worker sender.
Cancellation remains explicit even after a worker has emitted a queued result.

`tests/test_scene_signal_gui.py` uses `write_observations` with 61 declared
samples, Y(t) = 2500 - 4905 t² mm and either no rotation or Z(t) = 45 t degrees.
The real CSV reader and detection worker consume observations only. Checks
compare vertical speed with -9810 t mm/s and relative rotation with the declared
angle; evaluator-only files are guarded against reads. Real widgets exercise
initial/default and keyboard-selected signals, manual range edits, re-detection,
Include/Exclude, saved workspace reopening and included slice export/read.
Separate availability probes cover missing/all-NaN/zero signals and center/COM
tooltip semantics. Held real workers exercise source replacement during both
normal detection and workspace opening; late error/cancel/result signals and
cancellation after computation but before queued delivery are also checked.

The actual MainApp was measured at 1510×800 logical / DPR1.25, with Details
expanded. `tmp/issue123/vertical.png`, `rotation.png` and corresponding JSON
retain the execution evidence. This is synthetic software validation, not
independently calibrated physical accuracy. The detector and thresholds did
not change. CI repeats the actual widgets at 125 percent; final CI and review
results belong to the PR.

The retained-result release replay also checks the workspace's saved signal
before explicitly selecting relative rotation for its existing tiny-angle and
zoom checks. It no longer assumes that every saved review uses rotation. This
was corrected after required CI exposed the old default-selection assumption;
the numerical detector and its tolerances were not changed.
