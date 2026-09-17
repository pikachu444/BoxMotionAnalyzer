# Event-local Marker Review

Last Reviewed: 2026-09-17

Issue: [#112](https://github.com/pikachu444/BoxMotionAnalyzer/issues/112).
Common contract: [#111](https://github.com/pikachu444/BoxMotionAnalyzer/issues/111).
The source lifetime contract is also the integration boundary for #121; this change
does not add its raw-context plot or change the modal approval surface.

## Computation

`MarkerReviewWorker` pins the loaded review stream and prepares an owned snapshot
in cancellable chunks off the GUI thread. File digests are checked before and
after execution. `marker_review.scan_observations` reads actual time and stable
marker channels only. No pose estimates, truth files, event manifests, expected
axes, case IDs or private calibration are detector inputs.

The scan detects common-ID rigid rotation, centered label/set discontinuities,
shape changes, marker availability transitions, timestamp gaps and held/reconnect
boundaries. It is O(N) in recording length for a fixed marker layout. Kabsch and
pair distances depend on M; assignment can cost O(M^3), but runs only after a
large centered labeled displacement. This is not a constant-total-runtime claim.
A held run without a reconnect does not produce repeated events. Missing rows
and actual timestamp gaps remain missing; no motion is interpolated.

Candidate recall and recommendation support are separate. Common finite points
can reveal an angular boundary below the full-layout coverage threshold. The
original full-layout coverage denominator and rigid-support gate still apply to
recommendations. Distorted geometry remains a review candidate, not a supported
flip. A held/reconnect boundary retains conservative abstention, recorded as held
evidence rather than falsely calling a continuous timestamp sequence a time gap.
Neither a gap nor held coordinates identify the physical cause.

## Budget and unchanged gates

| Operation per event | Maximum actual frame fits |
| --- | ---: |
| Pre baseline, adjacent real rows | 5 |
| Post baseline, adjacent real rows | 5 |
| NONE refit | 5 |
| X refit | 5 |
| Y refit | 5 |
| Z refit | 5 |
| Total | 30 |

Each actual minimization retains Nelder-Mead, maxiter=1500, xatol=1e-4 and
fatol=1e-4. These are inherited numerical settings, not accuracy/confidence
estimates. There is no automatic retry, expanding window or global search.
Five samples are not a fixed-duration interval; actual indices/times are saved.
The pre and post baseline each start from their own observed face-Kabsch seed.
Timestamp gaps inside either window also restart the seed. Hypotheses use their
own post baseline seed and real refits. Original and Refit none stay distinct.

The face-continuity-v1 gates remain: at least three common samples, 0.80 coverage,
maximum pairwise window motion 30 degrees, best residual at most 35 degrees,
NONE improvement at least 20 degrees, score margin at least 0.15, plus existing
face-rank/rigid-support/gap guards and arithmetic-roundoff allowances. Invalid
samples stay in requested-window denominators. Solver nonconvergence does not
become valid evidence. Failing support yields an explicit unavailable/abstaining
candidate; unexpected execution exceptions discard the new run.

## Identity, cache and approval

The execution identity includes original and active source digests, a load
revision, observation digest including channel order and actual time, dimensions,
face geometry, base faces, full prior decision history, explicit registration,
actual analyzer/optimizer settings, policy version `event-local-1`, and the
computed sample windows. The existing face mechanics algorithm remains 3.1 and
the numerical recommendation gate remains face-continuity-v1.

The UI has one session cache of completed results. The lookup key includes actual
analyzer configuration before evaluation, not only a filename or dimensions.
Custom injected optimizer factories bypass cache. A cancelled, failed or stale
run never replaces the cache. No disk cache is introduced. Source/geometry/face
history changes prevent reuse; decisions are never automatically approved from
cache. Each result retains the exact window identity in its evidence.

The current capture's dimensions must be explicitly confirmed before Review.
Existing defaults can be edited but cannot authorize a review. Loading another
source clears confirmation. Validated v3 derivatives restore their recorded
dimensions without automatically confirming a new review. Changes invalidate
candidate/approval use immediately, even if a value is changed back. Historical
decisions and saved derivative files remain intact.

Source and request identity are checked at completion and again at Done. Byte
digests run in the cancellable worker, with file signatures checked before/after
hashing and when consuming the result. Done starts an asynchronous source check
before committing choices, so the GUI never performs a full-file completion hash.
Source digest and face context are checked again before saving. `Done` changes pending
memory only; `Save corrected` writes and activates a separate validated file.
With an empty completed review and prior decisions, the dialog explicitly offers
Done to record zero approvals or Cancel to preserve the previous review. The
zero-approval save still materializes base faces and writes v3 context.

XYZ, marker IDs and original bytes remain unchanged. Full chronological face
history is materialized once from base faces at save, including suffix slices.
Old v2 files retain their separate read path; existing v3 files remain readable.
New `review_policy`, geometry and optimizer context fields are additive; missing
old execution identity is not promoted to a new cache entry.
Loading a scene registration with unchanged dimensions preserves an already
validated corrected stream; it does not rewrite the review's face geometry.
Pending review evidence is invalidated, and a dimension change always requires
review again. This preserves corrected-source handoff into registered scenes.

## Cancellation and UI

Cancellation is checked during preparation, scan iteration, between fits, at
every optimizer frame, in the actual SciPy objective and iteration callback, and
before publishing. Chunk concatenation and NumPy array/median operations are
finite noninterruptible operations; large-input latency includes these costs.
There is no forceful QThread termination or blocking GUI-thread wait.

Progress names preparation, scan and event/fit phases. Cancel remains visible in
the expanded correction panel. On cancellation the action displays Cancelling
until QThread has finished; source changes and new calculations stay locked.
Completion is consumed only after thread cleanup. Cancellation requested after
worker completion but before the queued GUI handler still discards that result.
Both MainApp and Step 1 close request cancellation and retry close after cleanup.

Cancelled/failed runs preserve prior decisions, dirty state and active files.
Controls are restored from the current validity and pending-save state rather
than all being blindly enabled. An invalidated review cannot save corrected data
or flow into scenes/slices until explicitly reviewed again. Dialog Cancel and
save-dialog cancellation preserve pending choices; write failure supports retry.

## Verification evidence and limits

The baseline was remote main `346b7b26bc36730c802f1961f819f928d77ee685`, with no
open PRs at implementation start. Implementation is on a separate worktree.
Publication and final required CI are recorded in the PR rather than inferred
from a local test count.

- No-event worker tests: 1,000 / 10,000 / 100,000 rows, zero optimizer calls.
- Fixed two boundaries: 100 / 1,000 / 10,000 rows, 60 requested frame fits total;
  baseline and actual four-hypothesis process calls are counted separately.
- Actual minimization counters additionally record frame fits, iterations and
  objective evaluations. Injected call counts are not timing benchmarks.
- Actual SciPy X/Y/Z, repeat, gap, smooth genuine rotation, unsupported rotation,
  held and missing-marker cases use independent literal matrices/times. Two short
  pose-jump-only parity cases compare the old path with the new path: 10% shape
  distortion and four permanently missing markers. The old path is a recall
  comparison, not a source for physical expectations.
- The four independently specified continuity captures now exercise the new
  observation-only detector in the public evaluator. Its separate full pose pass
  serves the recovery oracle; it is never passed into review.
- Fault-injected Qt tests cover each fit, queued completion, close, source and
  dimensions changes, failure and empty-result decision replacement. They are
  separate from real SciPy timing.
- Six real MainApp public correction/save/reopen/processing cases passed locally
  (including reordered annotations and suffix pose); 194.99 s is suite duration,
  not review latency or a physical-accuracy metric.
- Actual Qt/Matplotlib at 1510x800 logical and measured DPR 1.25 passed reachable
  controls, preview without approval, three actual SciPy cancels, save cancel,
  injected write failure, successful retry/reopen and active-review close.
  Original screenshots and `execution.json` are retained in `tmp/issue112/gui`.

Reference environment: Windows, Intel Core i9-11900H (8 cores / 16 logical
processors), Python 3.13.5, NumPy 2.3.5, SciPy 1.16.3, PySide6 6.10.1. The public
GUI input has 32 frames, 18 markers and declared 200x120x80 mm geometry; SHA-256
`b255b4f43a6248fd50842f6352524c7f519c6011218f6f30eb936951cf080eb4`.
Three click-to-restored-UI observations were 0.05265 / 0.01326 / 0.01313 seconds.
After moving Done verification off the GUI thread, a second run passed with
0.03258 / 0.01194 / 0.01042 seconds. Future GUI reports use distinct run directories
to preserve prior execution evidence.
This meets the proposed one-second local usability target for this small input;
it is not an all-input bound, hosted-CI wall-time gate or calibration result.

Reproduction (from the worktree, using the configured Python environment):

```text
python -m pytest tests/test_event_local_marker_review.py tests/test_marker_review_lifecycle.py -q
python -m pytest tests/test_marker_face_gui_flow.py -k "production_mainapp or reordered" -q
python -m src.simulation.continuity_fixtures --output tmp/issue112/continuity
# In a fresh process with QT_SCALE_FACTOR=1.25:
python -m pytest tests/test_marker_review_gui.py -q
```

Independent review found and prompted fixes for low-coverage candidate omission,
held abstention, within-window gap seeds, cache settings identity, empty-review
recovery and completion hashing on the GUI thread. The numerical reviewer
independently reran eight targeted tests; lifecycle tests also cover cancellation
of Done verification without replacing prior approvals. A second independent
review verified source/close/cache safety, zero-approval v3 saving, the asynchronous
Done check and same-numeric-dimensions registration handoff. Both reviews ended
without blocking findings after corrections. Final CI evidence belongs to the PR.
Existing 0.1 mm / 0.1 degree numerical
gates are unchanged. Synthetic and GUI evidence do not validate actual tracking
error causes, physical recovery, ISTA compliance or real calibration; #104 remains
separate and unverified. #121 context inspection is still future work.
