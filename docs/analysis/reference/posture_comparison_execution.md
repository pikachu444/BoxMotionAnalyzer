# Posture repeat verification

Last Reviewed: 2026-09-18

Issue: [#117](https://github.com/pikachu444/BoxMotionAnalyzer/issues/117).
Contract and preimplementation mockup: `../design/posture_repeat_layout.md`.

## Implemented scope

Compare has optional Posture and Posture repeats modes in its existing Summary
table. Existing experimental motion, Details, contact comparison, graphs and
playback remain available. Saved Beta, signed long/short tilt, face height range,
whole-window maxima and contact sequence are checked against available geometry.
The new lowest-corner gap is computed only in comparison; no schema change.

ReferenceFace is the most downward-facing of six faces at the producer's
reference sample (t1-minus, otherwise first valid pose). It is not FinalFace.
Reference-face repeats require a matching maximum-area face and local axes.
Side-face values remain individually visible; corner gap is not rejected merely
because the reference is a side face. Exact lowest-height ties give zero mm and
a non-unique category with counts, without unique-corner agreement.

Each observation's valid contexts are resolved before trial compatibility and
the existing per-metric exact-value duplicate resolver. Valid context conflicts
exclude that metric for the observation, including when it is not the baseline.
Invalid reprocessings cannot hide a valid copy. If the baseline observation has
no valid numeric summary but independently verified geometry/window context,
that context alone can define the cohort; its invalid number remains excluded.
Invalid reference declarations cannot supply this fallback.

Whole-window contact replay uses the original complete height sequence and
recorded threshold. Missing geometry is not cropped/interpolated and the
existing contact guards are unchanged. Replaying this policy checks saved
consistency, not independent physical contact accuracy.

## Reproducible evidence

- `python -m pytest -q tests/test_posture_comparison.py tests/test_observation_resolution.py tests/test_metric_variant_comparison.py tests/test_impact_comparison.py`
- Set `QT_SCALE_FACTOR=1.25`, then
  `python -m pytest -q tests/test_posture_comparison_gui.py tests/test_impact_comparison_gui.py -o faulthandler_timeout=90`.
- Windows CI runs the new core tests in the required public contract stage and
  the real GUI test in a separate 125% stage. Final revision and results are in
  the PR; screenshots and input hashes are uploaded under `tmp/issue117`.

Final local targeted runs on Python 3.13.5: 105 core/resolver/impact contract
tests passed (36.17 s), and 7 actual GUI tests passed (29.36 s). The public
summary classifies 105+6 as unit/GUI contracts and the one complete generated
observation-to-comparison run as synthetic integration. No real-validation
case is counted as passed by these runs.

The core oracle uses literal heights and explicitly constructed Rz geometry of
a 200×80×120 mm box. Three separate declared captures at 10/20/30 degrees have
mean 20, minimum 10, maximum 30 and range 20 degrees. A fourth copy does not
increase n. Non-unique corners are categories, never arithmetic values. Tests
cover missing t1, no-contact automatic windows, side faces, differing windows,
incomplete geometry, identity incompatibility, invalid/identical/conflicting
reprocessings, baseline/load-order changes and per-metric exclusions.

The GUI test uses actual Qt/VTK at 1510×800 logical size and measured DPR 1.25,
with QTest keyboard/mouse interaction and supplied file-dialog paths. The test
also generates a public CSV (seed 74082, `specified_input('healthy')`), reopens it
with the normal reader, executes the real raw optimizer, saves `.proc` and opens
it in Compare. Truth/manifest reads are blocked during analysis. Its declared
fixed orientation supplies the independent bound of 0.1 degree; the first local
execution measured max Beta 0.000396751 degrees. This is synthetic software
validation, not camera or measured-trial accuracy.

Qt whole-window grabs can show the native OpenGL area black; a separate direct
VTK render capture verifies the rendered box. The retained GUI report records
that distinction, logical dimensions, DPR, input hashes and pass/fail.

## Review and corrections

Independent read-only design review preceded implementation. Code review found
that applying baseline context before observation resolution could hide valid
copies or choose one conflicting reprocessing; this was corrected and tested
in every load order and with all baselines. A further scalar-only invalid
baseline case now preserves independently valid context without contributing
the corrupt value. UI evidence was independently reviewed. Final rereview and
required CI results are recorded in the PR before merge.

No new trial-registration workflow, target angle, calibrated tolerance,
probability or pass/fail criterion was introduced. Independent measured
repeatability remains the separate #104 task.
