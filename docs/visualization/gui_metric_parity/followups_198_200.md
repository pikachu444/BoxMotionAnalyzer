# Public follow-ups #198–#200

Last Reviewed: 2026-11-12

Baseline: main `fc1a624dd66fc24a12bf5a35901991d23d5dc194`, PR #197.
The open issues were checked against the current remote main and open PRs;
none had an existing implementation or PR at intake.

## #198 Point selection on entirely missing results

Implementation and independent verification are complete. The original
native Windows Qt canvas regression reproduces selection at .1 seconds despite
no usable result values: main and popup no-target cases fail, while both
target-present controls pass (2 failed, 2 passed). The correction must preserve
valid zero, partial-NaN results, selected time across target changes, full-row
Point CSV and the existing CAE modes. The shared selection/button/export gate
now accepts only existing display-schema observations (finite numeric values or
supported corner identities), excluding time, Frame, Info, Artifact and arbitrary
text. A missing target no longer bypasses this gate; a NaN target does not erase
a valid time when another result channel is usable.

The writer's native QTest regression run passed 15 tests in 13.30 s, covering
both canvas connections, zero/finite/partial-NaN values, categorical identities,
full three-level-row UTF-8/precision export, replacement, failed load, cancel,
Clear and stale export entry points. Existing CAE/export regressions are included
in independent verification below.

Independent native command: `python -m pytest
tests/test_gui_metric_parity_workflows.py tests/test_gui_metric_parity_exports.py
tests/test_result_file_context.py tests/test_result_presentation.py
tests/test_workflow_navigation.py -q` returned **123 passed** in 91.38 s.
Both ManualHeight rest and selected-time velocity exports, cancel/failure
preservation, existing result context and navigation are covered by that scope.
The reviewer separately loaded baseline source read-only in memory and executed
10 original native canvas cases: baseline no-target main/popup select .1/index1
and enable exports; current all-missing cases reject, while zero and partial-NaN
controls retain time selection and popup behavior. No source files were reverted.

## #199 Saved precontact timing versus detector evidence

Implementation and bounded CAE verification are complete. The correction
is limited to new snapshot/target publications and their replayed evidence;
the existing declaration validator and complete contact owner retain their APIs.
Detector onset and a later accepted persistent contact set remain distinct.
The shared helper replays the existing detector and accepted sets, checks exact
saved times separately, and reuses declaration provenance/gap checks on an
ephemeral accepted-event bracket. It never rewrites the input result. The true
detector sample must also lie within the reviewed interval; malformed review
context cannot become an absent-review fallback.

Before correction, the stale adjacent pair test failed because target error
was incorrectly available at 0 degrees. The fresh postprocessor control retains
t1-=.07200000000000001 s, event=.08 s, target error=0 degrees, vertical velocity
=-400 mm/s and geometric speed-equivalent height `400²/(2*9810)` mm. The stale
pair rejects all new event-dependent fields while ContactState remains available;
the complete contact owner keeps Match/Unclear semantics. A transient contact
at row10 followed by the accepted set at row11 retains detector t1- at row9.

Independent CAE review found and verified corrections for detector/review range
containment and malformed-review error propagation. Both new normal/stale and
transient tests pass on the intended virtual environment, with no remaining
bounded physical/evidence finding.

Independent regression command: `python -m pytest
tests/test_gui_metric_parity_contract.py tests/test_contact_comparison.py
tests/test_impact_metrics.py tests/test_impact_comparison.py
tests/test_posture_comparison.py tests/test_drop_posture_post_processor.py
tests/test_contact_evaluation.py tests/test_contact_calibration.py -q`
returned **475 passed, 1 skipped**, with 41 existing deliberate fixture warnings,
in 57.29 s. Combined with the disjoint 123-test GUI/export scope this is
**598 passed, 1 skipped**; overlapping writer/main checks are not added to it.
An independent five-case baseline/current script also reproduced fresh/stale
publication and the delayed accepted event at .088 s with detector t1-=.072 s.
The independent reviewer reported no remaining source/test findings in scope.

Final main-agent check: `python -m pytest -q
tests/test_gui_metric_parity_contract.py tests/test_gui_metric_parity_exports.py
tests/test_final_face_resampling_contract.py tests/test_contact_comparison.py
tests/test_drop_posture_post_processor.py --junitxml=tmp/followups-pure-final.xml`
returned **272 passed, 1 skipped**, with two existing deliberate overflow-control
warnings, in 14.12 s. The unchanged skip is the optional real-capture check
requiring `BMA_REAL_CAPTURE`; no measured input was supplied. Validation-router tests:
**5 passed**. An earlier main-agent run used a nonexistent test filename and
collected no tests; a subsequent run during the review correction had one
new-test assertion failure (review/slice mismatch preceded the intended guard).
The final run above supersedes those attempts without deleting their assertions.

## #200 FinalFace tail support

The actual UniformResampler + postprocessor characterization has **2 passed**
checks (uniform and nonuniform six-sample input). The 6-to-16 case preserves
the current behavior and the original-support arithmetic. It does not approve
a numerical policy. See the [decision record](final_face_tail_decision.md).
The issue remains open pending the user's choice; product behavior is unchanged.

## Environment and limits

Local Windows, Python 3.13.5, PySide6 6.10.1, NumPy 2.3.5, pandas 2.3.3 and
SciPy 1.16.3. The local Qt platform uses the native Windows default.
Public generated input only; no Raw optimization, full capture replay, native
solver campaign, measured calibration or private consumer adoption is required
for these bounded local checks. Final PR required CI is a separate publication gate.
Local implementation is ready for publication; final-head CI/merge status belongs
to the live PR and linked issue completion records, rather than this pre-CI record.
