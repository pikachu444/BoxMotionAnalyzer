# Scene review workflow (#137 / PUB04)

Last Reviewed: 2026-10-04

Plan Spec: ISTA6A-PLAN-20261001-v1. Parent: #134.
Status: approved production implementation and automatic checks are available.
Independent review found no P0/P1; both P2 corrections passed the same reviewer's
recheck, with no outstanding findings.
Publication and required CI are tracked in PR #148. Native visual/external input acceptance
is not executed because window capture/activation failed; #137 remains open.

## Starting state and scope

Started on clean `main`, HEAD and fetched `origin/main`
`3a38b496ce2dedd2570479c8a77fef03d78961aa`; created
`fix/137-scene-review-workflow`. No user edits were present or removed.
Read root AGENTS.md (no nested AGENTS.md found), issue #137 in full, parent
#134's PUB04 and common contracts, PRs #90/#92/#103/#108/#130/#146/#147,
implementation_todo, gui_overview, system_design, design_docs_guide,
scene_signal_layout, marker_review_responsive_layout and result_schema_notes.

#135 / PR #146 and #136 / PR #147 are delivered. Their previous native
limitations remain recorded; they do not block this implementation.
#113 experiment registration and its proposed integration are excluded by
the user's decision. Existing active/original SHA, source revision, corrected
lineage and capture-bound trial record must still be validated. #104 measured
calibration is a separate unavailable/pending track. #138 onward is outside scope.

## Existing paths and demonstrated gaps

| Path | Reuse | Delta to implement after approval |
| --- | --- | --- |
| `scene_review_flow._select_scene` | Row selection updates current range and the existing SpanSelector band | Retain plot limits when refresh or selection clearing redraws |
| `widget_raw_data_processing.update_plot` | Raw/derived signals, markers and selected range | Drawing clears axes; preserve source/signal-specific pan and zoom |
| `scene_workspace.save_workspace/restore_session` | Atomic source-bound unfinished work, edits, additions, removals, signal and target restoration; evidence recomputation | No viewport saved; add versioned view transport and validate before replacing work |
| `SceneReviewSession.set_range/refresh` | Keep edited bounds through re-detection; clear stale identity/contact | Add Revert using stored `auto_start/auto_end`; preserve general review/edit history instead of dropping it when no trial record exists |
| `SceneReviewSession.set_context` | Type/edition invalidate identity/contact while retaining inclusion decisions | Preserve and display Type basis; do not infer Type or actual order from names, mass or table position |
| `_update_scene_gates`, `_save_slice`, `save_included_scenes` | Explicit Include/Exclude and all-rows-reviewed export rule | One gate for counts/reasons and direct saves; currently UI and callable save conditions differ, e.g. active scene detection |
| `_scene_dimensions_changed`, `_scene_callback_is_current` | Registration mismatch invalidation, source revision/path/hash callback guard, explicit cancellation | Dimension edits without registration do not invalidate scene review; strengthen current detection context checks without discarding unrelated choices |

Unknown trial identity remains analysable under existing rules. Explicit scene
Include and saved marker correction are the applicable export approvals; an
Unknown Type must not be silently promoted to a confirmed trial. Workspace
saving remains available for unfinished work.

## Proposed UI for approval

The first representative images shown were the required 820×600 stress cases.
The user noted their cramped presentation. FHD 1920×1080 is now the primary
review canvas, with 820×600 retained separately for minimum-window checks.

- Keep the existing original plot, toolbar, signal choice, table and range inputs.
- Add `Revert detected range` beside Include/Exclude and a single current
  `Detected`, `Edited` or `Manual` range line. Manual rows have no detected
  original: disable Revert with a concise reason. Revert clears affected approval
  and identity; it does not automatically Include or confirm a trial.
- Rename the current save action `Save current (n)...`. Move the existing
  `Save included (n)...` out of optional Details beside current saving and
  Save and Process. Counts describe included export targets; the shared
  block reason explains why they cannot yet be saved.
- Keep a short block reason such as `Review 4 remaining`, `Detection running`
  or `Save correction first`; expose full detail by tooltip/log if needed.
- Show `Type basis` in Details. Source declarations and eligibility suggestions
  do not constitute a verified test order. Preserve operator/test-record basis.
- Let optional Details scroll at the small size. Preserve every optional control
  and the main save actions. Fit source filename and graph axes/units to the
  available viewport, retaining full path/Copy path.
- At FHD, limit the bottom controls to about 130 logical pixels and allocate
  remaining height to the graph and scene table instead of stretched control gaps.

Representative FHD renders:
[edited range](mockups/scene_review_137/1920x1080-edited.png),
[Type basis and Details](mockups/scene_review_137/1920x1080-details.png).
Small-window cases: [edited](mockups/scene_review_137/820x600-edited.png),
[manual](mockups/scene_review_137/820x600-manual.png),
[blocked](mockups/scene_review_137/820x600-blocked.png),
[Details](mockups/scene_review_137/820x600-details.png).
Other renders include no scenes, one scene, 24 scenes, loading and error.

The preserved PNGs are disposable instance changes in `generate_mockups.py`,
created before production UI edits. The prototype's count/reason strings were
illustrative; the user approved the FHD/minimum-window mockup on 2026-10-03.
The historical generator requires base `3a38b49`; current production renders use
`python -m src.simulation.scene_review_validation`. The fixture sets explicit
operator Include/Exclude states solely to render those states; detection never
automatically includes handling candidates.

## Fixture and preimplementation evidence

`generate_mockups.py` declares 601 observations at 0.02 s spacing, world Y up,
mm positions `x=20+30t`, `y=1000+100 sin(0.8t)`, `z=0`, local rotation
`Z=15 sin(t)` degrees and the public asymmetric 18-marker geometry.
The existing exporter writes Raw, and actual DataLoader/Parser read it.
UI candidates are separately specified at `[0.10+0.5i, 0.35+0.5i]` capture
seconds using the existing inclusive GUI range API. Edited current bounds
are 0.14–0.30 s; declared pan/zoom is x=0–3 s and y=-100–100 mm/s.
These are layout inputs, not production detector expected labels or physical
accuracy evidence. A future record contract must explicitly adapt the existing
inclusive GUI ranges to the Plan Spec's half-open original records.

Raw SHA-256:
`fc61614f75c66fc3f98d88cd232fec7c62aaf0281eae1e39f7d002794652c2e5`.
The versioned [mockup evidence](mockups/scene_review_137/mockup-evidence.json)
records input identity, actual logical sizes, view limits, states and environment.
Windows 11 build 26200, Python 3.13.5, PySide6 6.10.1,
Matplotlib 3.10.7, Qt platform `windows`, desktop DPR 1.0;
available target screen 2560×1392 logical pixels.

```powershell
.venv/Scripts/python.exe docs/visualization/mockups/scene_review_137/generate_mockups.py
.venv/Scripts/python.exe -m pytest -q tests/test_scene_review_gui.py tests/test_scene_workspace.py tests/test_scene_workspace_gui.py tests/test_scene_signal_gui.py tests/test_scene_artifact_io.py tests/test_scene_processing_handoff.py tests/test_scene_trial_record.py tests/test_marker_review_layout.py tests/test_marker_review_lifecycle.py tests/test_capture_regression.py --junitxml=tmp/issue137/baseline.xml -o faulthandler_timeout=60
```

Unchanged-production baseline: **204 passed in 398.20 s**. This is preservation
baseline evidence, not verification of #137's proposed behavior. The existing
#135 test performs fresh processing and retains its own immutable reports at
`tmp/issue135/pytest_ef10c98bf08f420c8e84f9ce96f5c432/`.
A 60 s faulthandler snapshot occurred during its production optimizer fixture;
execution continued and passed. No detector tolerances or baseline were altered.
Its RunReport is `pass`: loaded/approved/fresh=6 each, reused/failed/unexecuted=0,
optimizer calls=449, with GUI and calibration explicitly pending.

Native attempt used the installed computer-use plugin and a disposable public
820×600 edited mockup. Window enumeration/accessibility succeeded. The screen
capture was black. Clicking the observed Details element 69 failed with
`Error: failed to activate captured window`; selection refresh and one explicit
activation retry failed identically. Evidence: `tmp/issue137/native-preapproval/`
contains `capture-black.png` and versioned `native-attempt.json`.
Native visual/external input acceptance is **not executed**, including FHD and
target-screen acceptance. Widget/render evidence does not replace it.

## Approval and implementation

The user gave this issue's explicit mockup approval (`승인`) after the FHD
representative images were shown. The applicable instruction was:
“production UI 변경 전에 … 변경 지점·상태를 보여준 뒤 목업 승인을 받으세요.”
#136 approval was not used to authorize this layout. No other implementation,
verification, correction, commit, push, PR or merge approval is needed.

After approval, the main agent made all production/test/document changes.
The deltas above use `schema_version` and `plan_spec` for changed
transport objects, explicit legacy handling and rejection of incompatible
version/source/unit/clock data. Preserve whole-workspace history and slice/proc
review context while recomputing evidence from observations. Keep stored
viewport reuse scoped to its source, signal and targets; reset for a replacement
source and avoid applying a previous signal's y limits to a fallback signal.

Verification covers real public Raw detection and independently defined state fixtures:
selection/edit/re-detection/add/remove/Revert; Include/Exclude; signal and
pan/zoom; current/batch gate counts/reasons; save/reopen/workspace/slice;
cancel/error/retry; source/geometry/Type changes; cancelled/stale workers;
minimum/FHD/target screens, long names, empty/single/24-row and loading/error
states. Run affected preservation tests and required CI; distinguish new tests,
Qt/QTest, native execution and measured calibration.

Once implementation and execution evidence are ready, create exactly one
GPT-6.1 Sol / High read-only independent reviewer with no additional agents.
Supply requirements, base/head, changed paths, commands/results and mockup/final
screens. Resolve P0/P1 through the same reviewer; document any deferred P2.
Then commit and push, create an English-followed-by-Korean PR and merge after
required CI passes. Leave only unexecuted native follow-ups pending; do not
close #137 or claim all GUI acceptance if those remain.

## Production behavior and validation evidence

`SceneReviewSession` records ordered source-bound pre-change snapshots through
range edits/Revert, Include/Exclude, additions/deletions and evidence/Type context
changes. Revert restores stored detection bounds, recomputes only that interval
and leaves it unreviewed. Manual rows have no detected original; Revert is disabled.
Adding after every automatic row is removed creates a clean manual row rather
than copying another scene's evidence/approval. Type source declarations remain
unconfirmed for trial approval until explicitly selected or matched by a test
record. Record removal clears its dependent Type basis; a basis-only confirmation
does not erase an unchanged independent intended contact.

The current/included save gate supplies button counts, short block reasons and
direct callable save checks. It covers pending review, busy workers even after
queued busy-state release, pending correction, source/dimension mismatches and
range bounds. A chooser returning after source/review/context changes cannot
write the earlier request. Cancel and failure keep operator work; retry remains
possible. Existing partial batch failure keeps written files but returns no
processing handoff. Workspace saving remains available for unfinished review.

Viewport x/y limits are captured per source revision/signal/targets during
redraw. A first signal switch shares capture-time x limits but uses its own y
scale. Workspace restore validates the contract, source hash, original capture
clock and units before replacing work. The limits apply only to matching
available signal/targets. New captures reset the viewport. Slice/proc transport
retains edited/detected bounds and complete history without inventing the missing
full-source plot or approval from padded observations.

Production renders are in [final evidence](mockups/scene_review_137/final/execution.json):
[FHD edited](mockups/scene_review_137/final/1920x1080-edited.png),
[FHD Details](mockups/scene_review_137/final/1920x1080-details.png),
[820x600 Details](mockups/scene_review_137/final/820x600-details.png),
[target screen](mockups/scene_review_137/final/2560x1392-details.png).
All 19 production states pass requested logical size and main button access;
Details disclosure remains the route to optional workspace/trial controls.
Wide Details gives trial buttons visible space; narrow Details scrolls. The
820x600 MainApp itself is checked, not only its inner widget.

Execution on base `3a38b49` with recorded working-tree modifications used Windows
11 build 26200, Python 3.13.5, PySide6 6.10.1, Matplotlib 3.10.7 and Qt `windows`.
The published candidate commit/required CI supply exact final-commit execution.
Input SHA and independent analytic/UI expectations are the same as the approved
fixture above. Real `write_sequence`/analytic Raw tests independently exercise
detection, source/registration, workspace reopen and conditional trial records.
Fixture injection tests only UI topology/state transport; they do not establish
detector classification or measured accuracy.

| Evidence | Command / report | Actual result |
| --- | --- | --- |
| Baseline before implementation | pytest command above; `tmp/issue137/baseline.xml` | 204 passed |
| Affected preservation, including fresh #135 and #136 | `python -m pytest -q tests/test_scene_workflow_state.py tests/test_scene_workflow_gui.py tests/test_scene_review_gui.py tests/test_scene_workspace.py tests/test_scene_workspace_gui.py tests/test_scene_signal_gui.py tests/test_scene_artifact_io.py tests/test_scene_processing_handoff.py tests/test_scene_trial_record.py tests/test_trial_record_integration.py tests/test_trial_record_gui.py tests/test_marker_review_layout.py tests/test_marker_review_lifecycle.py tests/test_marker_flip_raw_widget.py tests/test_raw_data_processing.py tests/test_slice_dimension_provenance_gui.py tests/test_capture_regression.py --junitxml=tmp/issue137/preservation.xml -o faulthandler_timeout=90` | 261 passed, 6 subtests passed; 2 failed, subsequently fixed |
| Replay both failures and affected layouts | `python -m pytest -q tests/test_trial_record_gui.py tests/test_marker_flip_raw_widget.py tests/test_scene_workflow_gui.py tests/test_scene_workspace.py --junitxml=tmp/issue137/preservation-fixes.xml` | 53 passed, 3 subtests passed |
| Final minimum/FHD QWidget/MainApp, QTest, current/batch save, failure/retry, workspace/slice/proc and stale geometry | `python -m pytest -q tests/test_scene_workflow_gui.py --junitxml=tmp/issue137/workflow-final.xml` | 25 passed |
| Final Type/record/contact scope and invalid versions/source/clock/units | `python -m pytest -q tests/test_scene_trial_record.py tests/test_scene_artifact_io.py tests/test_scene_workflow_state.py tests/test_intended_contact.py --junitxml=tmp/issue137/context-contract-final.xml` | 126 passed |
| Workspace/legacy review preservation | `python -m pytest -q tests/test_scene_workflow_state.py tests/test_scene_workspace.py tests/test_scene_workspace_gui.py --junitxml=tmp/issue137/workspace-final.xml` | 41 passed (before final Type/time hardening; its contracts replayed above) |
| Final 125% Qt execution | `$env:QT_SCALE_FACTOR='1.25'; python -m pytest -q tests/test_scene_workflow_gui.py --junitxml=tmp/issue137/gui-final-125.xml` | 25 passed |
| Production rendering | `python -m src.simulation.scene_review_validation --output tmp/issue137/final-production` | 19 states passed; widget renders, not native capture |

The first workspace attempt exposed NumPy limit scalars against strict JSON
numeric validation; capture now converts them to plain floats. Source replacement
also exposed transient combo/panel redraw caching during reset; the completed
reset now clears that transient view. The preservation failures were clipped
wide Details trial buttons (fixed minimum visible height) and an incomplete
metadata test double (now declares its legacy schema). Subsequent minimum MainApp
render caught an 11-pixel height expansion; narrow scrolling now fits exactly
820x600. Failed reports remain in `tmp/issue137`; none is recorded as passed.
No numerical tolerances, physical baseline or #135/#136 completion was changed.

The #135 full fresh processing preservation test passed within the affected
run. Its RunReport still has loaded/approved/fresh=6, reused/failed/unexecuted=0
and 449 optimizer calls; GUI and measured calibration remain separately pending.
Its own immutable run folder identifies exact inputs/config and fresh outputs.

## Independent review and publication

Clean candidate `0c5bd078dc8630b5301af2c62d2e7f8f64725054` passed
`python -m pytest -q tests/test_scene_workflow_state.py tests/test_scene_workflow_gui.py tests/test_scene_trial_record.py tests/test_scene_artifact_io.py --junitxml=tmp/issue137/candidate-head.xml`
(98 passed) and production rendering to `tmp/issue137/candidate-head-render`
(19 passed, manifest records exact head/environment/Raw identity).

One read-only GPT-6.1 Sol / High found no P0/P1 and two P2 issues;
[report and correction tracking](mockups/scene_review_137/independent-review.md).
Main fixed all derived-unit declarations and slice geometry invalidation history.
No finding is deferred. Required CI on the first candidate failed at the old
long-path layout expectation (14 passed before stopping):
[37132419910](https://github.com/pikachu444/BoxMotionAnalyzer/actions/runs/37132419910).
The test now checks retained full path/tooltip, displayed text selection and
actual width, preserving the approved filename elision.

Correction commands (same Windows/Python environment as above):

- `python -m pytest -q tests/test_processing_window_layout.py tests/test_scene_workflow_state.py tests/test_scene_artifact_io.py --junitxml=tmp/issue137/review-fixes.xml`: 41 passed, including nine independent unit expectations/mismatch negatives and unrecorded operator slice-to-proc history.
- `python -m pytest -q tests/test_scene_signal_gui.py tests/test_scene_workflow_gui.py tests/test_slice_dimension_provenance_gui.py --junitxml=tmp/issue137/review-gui-fixes.xml`: 32 passed, one new test failed because an unregistered synthetic COM correctly leaves rotation bound unavailable; no production defect. The independent fixture now explicitly declares COM at the box centre.
- `python -m pytest -q tests/test_scene_signal_gui.py::test_all_observed_derived_views_save_and_reopen_with_declared_units --junitxml=tmp/issue137/review-all-signals.xml`: passed; all nine observed derived signals save/reopen their declared units and expected independent x/y limits.
- Exact clean corrected commit `be9fd42b26d120741318c1af1c9a178c897d3884`: `python -m pytest -q tests/test_processing_window_layout.py tests/test_scene_workflow_state.py tests/test_scene_artifact_io.py tests/test_scene_signal_gui.py::test_all_observed_derived_views_save_and_reopen_with_declared_units --junitxml=tmp/issue137/corrected-head.xml`: 42 passed, 98.81 s. Production renderer with `--output tmp/issue137/corrected-head-render`: 19 states passed. The committed final screens/manifest are from that clean code head and retain the exact input SHA and environment.

[PR #148](https://github.com/pikachu444/BoxMotionAnalyzer/pull/148) contains the
English/Korean change and execution summary. Independent recheck is complete;
required CI must pass before merging. Final publication status and the check
run tied to the published head are available on that PR.
Native acceptance is the remaining issue follow-up below.

## Native limitation and remaining acceptance

The production FHD attempt used the installed computer-use skill. Enumeration
and accessibility identified the original plot, edited 0.14-0.30 s range,
stored 0.10-0.35 s bounds, Revert element 41 and blocked current/included saves.
The capture was black; clicking Revert failed before input with
`Error: failed to activate captured window`. A fresh enumeration/get_window and
one explicit activation recovery failed identically. Evidence:
[production attempt](mockups/scene_review_137/native/production-attempt.json),
[black capture](mockups/scene_review_137/native/production-black.png),
[preserved preapproval attempt](mockups/scene_review_137/native/preapproval-attempt.json).
Only task-owned disposable windows were cleaned up afterwards.

Native visual and external input acceptance remain **not executed**, including
820x600/FHD/target long-name and empty/single/24-scene/edit/blocked/loading/error
states; external selection/edit/add/delete/Revert/Include/Exclude;
signal/pan/zoom; actual save chooser/cancel/error/retry and workspace/slice reopen.
Repeat these on an interactive Windows desktop where capture/activation works,
using the public input above. Widget/render/QTest success does not close those
items. #137 remains open for this follow-up. #113 registration integration is
not applicable by user scope; source identity/lineage is still tested. #104
measured calibration remains a separate pending track. No #138 work began.
