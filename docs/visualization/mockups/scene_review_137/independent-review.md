# PUB04 independent review

Last Reviewed: 2026-10-04

Reviewer: one GPT-6.1 Sol / High, read-only; no additional agents.
Base: `3a38b496ce2dedd2570479c8a77fef03d78961aa`.
First candidate: `0c5bd078dc8630b5301af2c62d2e7f8f64725054`.
The reviewer received issue/parent/scope constraints, base/head, changed files,
commands/results, approved mockup and final FHD/minimum screenshots, and native
failure evidence. Code, transitions, transport, expected values, regressions and
completion claims were included in the review request.

## First completed report

No P0/P1 findings. Two P2 findings:

1. `scene_review_flow.py:245,459`, `scene_workflow_state.py:91`: additional
   derived signals could save Raw millimeter units for speed, angular rate/span,
   marker count and acceleration diagnostics. A read-only in-memory probe
   confirmed inaccurate transport declarations; plotted values were unchanged.
   Main correction: one explicit nine-signal mapping for capture/validation/open,
   negative unit tests and observed Raw per-signal save/reopen checks.
2. `artifact_io.py:669`: changing dimensions of a schema-2 confirmed slice
   without a trial record cleared its identity without preserving it. History
   before `confirm_item` can contain only the unconfirmed state. A read-only
   mocked file probe reproduced lost prior confirmation. Main correction:
   retain `previous_review` and append `geometry_changed` before invalidation,
   using the shared history snapshot helper. Test unchanged/repeated dimensions,
   explicit operator identity without a record, and slice-to-proc propagation.

The reviewer inspected approved/final FHD edited/Details and final 820x600
Details screenshots and found them consistent with the approved design.
The 98-test clean candidate run, 19 renders and #135 fresh coverage matched
the supplied evidence. Native visual/external-input acceptance remains
unexecuted; keep #137 open, #104 separate and #113/#138 onward out of scope.

## Same-reviewer correction recheck

Reviewed `be9fd42b26d120741318c1af1c9a178c897d3884`: both P2 findings
resolved; no new P0/P1/P2. Read-only in-memory checks confirmed all nine units
and mismatch rejection. Prior identity/history preservation, repeated geometry
changes and slice-to-proc tests address the second finding. The CI path test
preserves full identity while permitting elision. Declaring synthetic COM fixes
the test availability assumption without production behavior changes.

Recorded 41-pass/32-pass-1-fail/corrected-nine-signal-replay results agreed with
the report. Final clean corrected-head command additionally passed 42 checks
(`tmp/issue137/corrected-head.xml`), and 19 renders passed with exact code head,
environment/Raw identity in [execution.json](final/execution.json). Required CI
must pass before merging. Native remains unexecuted. No P2 is deferred.

The same reviewer verified the final exact-head records: 42 passed with zero
failures/errors/skips and 19/19 render states with matching code/environment/Raw
SHA. Updated FHD edited/Details and 820x600 Details remain consistent with the
reviewed layout. Local regression/render publication gates are met; required CI
is still the merge gate. No new findings; native follow-up keeps #137 open.

## Hosted initial-size harness recheck

After CI stopped at initial FHD height 1061 instead of 1080 (962 passed, eight
subtests), the same reviewer checked `46d2e7153837b182f11a726957242f5fa358a649`.
No production changes, no weakened size/button/canvas/Details/QTest assertions.
Exposure/settle/second resize matches existing layout policy. Workflow only
relocates the identical PUB04 125% commands earlier; all checks remain.
Verified 25 GUI passes and 19 renders at exact clean head, DPR 1.25, matching
logical requested/actual size and Raw SHA. [125% manifest](final-125/execution.json).
Representative screenshots remain consistent. No new findings; local gates
met. Earlier P2 remain resolved. Required hosted CI still gates merge; native
acceptance is unexecuted and #137 remains open.
