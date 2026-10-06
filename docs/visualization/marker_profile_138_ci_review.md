# Bounded CI correction review — #138 / PR149

Last Reviewed: 2026-10-06

**Outcome: APPROVE the test-only CI correction.** No P0, P1 or P2 findings remain in this bounded delta. The prior production approval remains unchanged. A successful full hosted rerun at the new committed head is still required before merge.

The review was read-only; no agents were spawned and no files were edited.

The correction is bound to:

- Original base: `1f654faddd44eedf7ff6e807d85f5e08559f8b13`
- Reviewed production commit: `2b1a57d7200c89ef723b03506fd1666cda418459`
- [Correction snapshot](C:/SourceCodes/BoxMotionAnalyzer/docs/visualization/mockups/marker_profile_138/production/ci_correction_snapshot.json) SHA256: `adf3b316c59dbcebc98696f12c49d36d6f84938d5a343e6897c47b53ee550815`
- Canonical `code.sha256` mapping SHA256: `01430226ddf5f2bdd2ba63baeb7bd21208da96b94638ffb8d3d38bd4b231031e`
- Changed [GUI test](C:/SourceCodes/BoxMotionAnalyzer/tests/test_marker_profile_gui.py:74) SHA256: `33ad3de6169a80a57bb8f8d48deaf1ab01b82a0ca3b019afa286f6839fffc063`

All 34 source/test/workflow hashes matched before and after independent execution. Only this test file differs from the approved production source mapping.

The original [hosted failure](https://github.com/pikachu444/BoxMotionAnalyzer/actions/runs/37388388560) contains **57 passes and one failure**: the initially shown client was `(1920,1061)` instead of `(1920,1080)`. Its desktop record confirms physical 1920×1080 at DPR1. This is consistent with Windows fitting the initially decorated window.

The four added lines assert window exposure, re-request the exact logical client size and settle events before the original strict assertion. This matches the delivered #137 harness and existing profile renderer. No size tolerance, oracle, document invariant, 2D retention, button or gesture assertion was removed or relaxed. No production, renderer, identity or numerical behavior changed.

Independent bounded calls ran in separate Qt processes at DPR1 and DPR1.25:

```python
from PySide6.QtWidgets import QApplication
from test_marker_profile_gui import (
    test_display_gestures_and_resize_preserve_profile_and_2d,
)

app = QApplication([])
for size in ((1920, 1080), (820, 600)):
    test_display_gestures_and_resize_preserve_profile_and_2d(app, size)
```

Both processes exited successfully. All four corrected size cases passed the strict requested-client and original state/gesture assertions. Execution used `.venv/Scripts/python.exe`, `PYTHONDONTWRITEBYTECODE=1`, and separate `QT_SCALE_FACTOR=1` and `1.25` settings, with `tests` added to the import path.

I also verified the retained fresh Main JUnits: **9 passes at each DPR**, with zero failures, errors or skips. The original failure remains preserved. The 60 production PNGs are correctly classified as reused unchanged renderer evidence; they were not represented as fresh correction captures.

This correction validates the requested **logical client**, not complete decorated-window visibility on a physical FHD desktop. External native input/screen acceptance, actual OS125%, native chooser/retry/reopen and accessibility remain unexecuted. #104 measured accuracy remains separate and unavailable. No migration, trial, tolerance or baseline approval is added, and this verdict does not close #138.
