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

Same-reviewer correction recheck: pending. No P2 is deferred.
