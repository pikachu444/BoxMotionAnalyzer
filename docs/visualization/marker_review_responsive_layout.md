# Marker review responsive layout (#136 / PUB03)

Last Reviewed: 2026-10-02

Plan Spec: ISTA6A-PLAN-20261001-v1. Parent: #134. This changes only the
remaining layout delta after #121 / PR #129; #112 / PR #126 lifecycle and
#135 / PR #146 capture regression remain preservation requirements.

## Mockup review before implementation

The main agent inspected production code, workflow documents, issue #136 and
the relevant merged PRs. A test-only Qt prototype, without production changes,
was rendered at 820×600 with a long public source filename: one candidate,
24 candidates, and 24 candidates with Details expanded, both graph views.
These are widget/render evidence, not native Windows confirmation.

Observed baseline: the evidence graph loses its y-axis title at 820×600,
and the long filename is cut without an ellipsis. Proposed layout:

- Below 1100 logical pixels wide, use Original observations / Axis preview
  tabs. Keep the candidate table and explicit Apply OFF/ON visible above them.
- At wider sizes show both graphs side by side, preserving the last tab choice
  when returning to a small window. Do not recreate plots on layout transitions.
- Keep up to three table rows when original context is available, with vertical
  scrolling to every candidate; keep Details collapsible and internally scrollable.
- Elide the filename in the middle; retain the complete path in the existing
  tooltip and Copy path action. Plot titles, axes, ticks, numbers and units use
  adaptive Matplotlib layout on every draw/resize, including tab activation.
- Keep original XYZ selection, event cursor, navigation toolbar, Around event,
  recommendation, preview, explicit Apply, Done and Cancel semantics.
- Loading/cancellation/errors remain in the owning Step 1 panel, not in a new
  dialog state; verify them with existing worker gates and public UI fixtures.

Prototype renders are retained in [mockups/marker_review_136](mockups/marker_review_136/):
one candidate and 24 candidates, with collapsed/expanded Details and both views.
Baseline: `tmp/issue136/baseline-820-expanded.png`. The user explicitly approved
this proposal on 2026-10-02 before the main agent changed production code.

## Evidence and completion boundaries

Required checks: 820×600 and the current target Windows desktop; long filenames;
one and 24+ candidates; expanded Details; no recommendation; no candidates;
loading/error; pan/zoom/Around event; preview without approval; explicit Apply;
Cancel; source replacement; compute cancellation/retry; stale completions.
Record widget geometry/render, QTest input, and native Windows capture/external
input separately. Unexecuted native checks remain pending. No new processing
schema, detector gates, approval policy or numeric regression baseline is added.
Calibrated measured validation stays unavailable/pending in #104.

## Preimplementation execution (2026-10-02)

Code: `0250a7dc1afd491a6fa381febce71f1bc9335bb0` (main, dirty only for
this layout document and prototype images). Windows 11 build 26200, Python
3.13.5, PySide6 6.10.1, Matplotlib 3.10.7, SciPy 1.16.3, NumPy 2.3.5,
pandas 2.3.3. Qt platform `windows`, target desktop 2560×1440 logical pixels,
available 2560×1392, DPR 1.0. This is baseline evidence, not verification of
the proposed production implementation.

```powershell
.venv/Scripts/python.exe tmp/issue136/mockup.py
.venv/Scripts/python.exe -m pytest -q tests/test_capture_regression.py tests/test_marker_review_lifecycle.py tests/test_marker_flip_review_dialog.py tests/test_marker_flip_raw_widget.py --junitxml=tmp/issue136/baseline-core.xml -o faulthandler_timeout=60
.venv/Scripts/python.exe -m pytest -q tests/test_marker_review_context.py --junitxml=tmp/issue136/baseline-context.xml -o faulthandler_timeout=60
.venv/Scripts/python.exe -m src.analysis.regression.runner --manifest tmp/issue135/assets_v2/corpus.json --asset-root tmp/issue135/assets_v2 --output tmp/issue136/capture-full-baseline --tier full
```

The preservation suite passed **103 tests and three subtests**; the separate
context suite passed **four tests** (including public Raw through the real modal
worker/dialog, QTest pan, Around event, preview/approval, save cancel/error/retry,
reopen and source replacement). These four tests are widget/QTest evidence;
they are not external Windows input confirmation. The full fresh
runner passed with loaded=6, approved=6, fresh=6, reused=0, failed=0,
unexecuted=0; optimizer calls=449. Its immutable RunReport retains exact source,
decision, independent analytic expectation and tolerance identities, all scene
comparisons and `calibration_status=pending`. Existing corpus v2 seed=135001;
no numeric bounds/baselines changed. Prototype positions and residual curves
are independently declared UI fixtures, not fitted or physical ground truth.

An earlier combined baseline pytest run was interrupted before completion;
it has no aggregate pass claim. The completed preservation rerun above is the
reported result. Matplotlib faulthandler output during long fresh optimization
is diagnostic stack evidence, not a failed test.

Native Windows baseline confirmation is **pending**: Computer Use located
the real Qt window, but its native screenshot was black; explicit activation
failed with `failed to activate captured window`. A directly launched Python
window also produced a black capture. No external click/pan/zoom was executed
on unverifiable coordinates. Widget renders do not substitute for this check.

## Implemented layout and verification

The main agent implemented the approved responsive layout in
`dialog_marker_flip_review.py`. Below 1100 logical pixels, two tabs use the full
plot width. Wider windows show both existing panels. Reparenting does not
recreate axes, clear navigation history or transfer approval. The last tab is
restored when shrinking. Both canvases use constrained layout on every draw;
the evidence y-axis uses `Relative rotation (°)` to keep the unit and title
inside the short, expanded-Details/no-recommendation view. Empty candidates
show `No event selected`. Long filenames elide in the middle and retain the
full source tooltip and existing Copy path action.

The owning Step 1 panel keeps progress and compute Cancel outside its scrolling
Details area, so cancellation remains reachable at small sizes. Worker/result
identity, calculation gates, OFF/preview/Apply/Done/Cancel and corrected saving
are unchanged. No new processing object, detector policy or baseline is added.

Executed commands after implementation:

```powershell
.venv/Scripts/python.exe -m pytest -x -q tests/test_marker_review_layout.py tests/test_marker_review_lifecycle.py --junitxml=tmp/issue136/layout-lifecycle.xml -o faulthandler_timeout=60
$env:QT_SCALE_FACTOR='1.25'
.venv/Scripts/python.exe -m pytest -x -q tests/test_marker_review_layout.py --junitxml=tmp/issue136/layout-125.xml -o faulthandler_timeout=60
Remove-Item Env:QT_SCALE_FACTOR
.venv/Scripts/python.exe tests/manual_marker_review.py --case details --size 820x600
```

Layout/lifecycle: **34 passed** at the measured target DPR 1.0. Layout at DPR
1.25: **13 passed**. Cases cover 820×600/1280×740, one/24 candidates, expanded
Details, no recommendation, unavailable preview, empty candidates, complete
source identity, exact unmodified XYZ/time/NaN and evidence curves, rendered
axis/tick/offset/unit bounds, all action reachability, table scrolling to the
last event, pan/zoom, 1099/1100 transitions, event recentring, Around event,
preview without approval, explicit Apply and Cancel. Public Raw lifecycle cases
render actual busy/error-restored states, cancel or inject a computation error,
retry and inspect the real dialog without replacing previous approvals.
`tmp/issue136/widget-target`, `widget-1.25` and `lifecycle` retain JSON/PNG;
per-case reports distinguish literal UI inputs from pipeline/fresh processing.
CI runs the new widget suite and a separate 125% run, retaining `tmp/issue136`.
Selected final widget renders (not native captures):
[820×600 original](marker_review_136_evidence/820-original.png),
[820×600 preview](marker_review_136_evidence/820-preview.png),
[125% unavailable](marker_review_136_evidence/820-unavailable-125.png),
[1280×740 paired](marker_review_136_evidence/1280-paired.png).

Initial failures are retained: an overbroad test counted locator ticks outside
the view interval (not rendered), then a real overlong y-title in the shortest
preview, a blank empty-candidate figure, and hidden compute Cancel. The test
now measures only actually drawn ticks; the three product problems were fixed.
An intermediate scroll-to-Cancel fix moved the horizontal viewport and was
replaced by the fixed progress/Cancel row before final verification.

Native retry after implementation located the real 820×600 Details dialog and
read its Windows accessibility tree (two tabs, original target, toolbar,
Details and Done/Cancel). The screenshot was still black. Clicking the observed
Axis preview accessibility item failed with `failed to activate captured window`.
This is attempted native inspection, **not a native visual or input pass**.
Native one/many/Details/loading/error/no-recommendation/pan/zoom/Apply/Cancel
checks at minimum and target settings remain environment-confirmation pending.
The helper CLI also supports `--case one|many|details|unavailable|empty|loading|error|raw`
and `--size 1280x740` for later verification; loading/error use explicitly
test-only optimizer fixtures, and raw uses the production optimizer.

Final preservation command and result:

```powershell
.venv/Scripts/python.exe -m pytest -q tests/test_marker_flip_review_dialog.py tests/test_marker_flip_raw_widget.py tests/test_marker_flip_artifact_io.py tests/test_marker_review_context.py tests/test_marker_review_lifecycle.py tests/test_event_local_marker_review.py tests/test_capture_regression.py --junitxml=tmp/issue136/preservation.xml -o faulthandler_timeout=120
```

**146 passed and three subtests passed** in 314.02 seconds. This includes real
modal source replacement, completed-but-queued cancellation, stale file/revision/
dimension workers, cancelled Done verification, save error/cancel/retry,
corrected reopening and public fresh full capture isolation. Post-change fresh
RunReport: `tmp/issue135/pytest_6e5c7f8513df4945a2f156377e27b25e/full/run_report.json`.
All six approved scenes fresh, zero reused/failed/unexecuted, 449 optimizer calls;
source/reference/truth/manifest hashes unchanged and no forbidden truth reads.
GUI and calibration statuses remain pending. These executed the base commit
`0250a7d` plus the dirty changes being published by this PR; no analysis semantics
or baseline was modified. Final layout reports after the literal UI hypothesis
values/cursor assertions were clarified: `layout-final-target.xml` and
`layout-final-125.xml`, **13 passed at each DPR** (34.32/38.22 seconds).

The requested single independent GPT-6.1 Sol/high reviewer completed read-only
code/test/document and visual-render inspection with **no P0/P1/P2 code findings**.
The reviewer independently inspected preservation JUnit (146 tests + three
subtests; zero failures/errors/skips) and fresh full RunReport, and ran an
additional offscreen Python fixture probe (exit 0) for detached snapshot,
1100→1099→1280→820 transitions, exact tab counts, rendered in-view label bounds,
canvas reachability and reject/deferred destruction guards. This extra probe
is offscreen evidence, not native input. Two earlier stdin exploration probes
were terminated without verdicts and have no pass claim. Copy path is the
existing shared helper, statically reviewed with fullPath/tooltip checks; its
native menu operation was not exercised. `git diff --check` passed.

Publication must keep #136 open and the PR draft while required
native confirmation is missing, even if automated CI passes. #104 remains
the separate measured calibration/accuracy pending track.
