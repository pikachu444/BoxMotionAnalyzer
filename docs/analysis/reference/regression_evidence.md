# Regression tiers and CI evidence — PUB11

Last Reviewed: 2026-10-13

PUB11 software is published: PR #156 merged after head492322c CI38286906108 succeeded; merge698c0d5 main CI38297290908 also succeeded. [PUB12 source/CI/original-report mapping and waits](pub_delivery_status.md). Historical evidence-index publication fields describe their capture time; issue #144 records the completed publication.

Plan Spec: `ISTA6A-PLAN-20261001-v1`. PUB11 extends the existing PUB02 runner
and measures the existing PUB07–10 validation CLIs. Production algorithms,
approved PUB02 reference/tolerance bytes, correction OFF, chronological t2,
single-drop defaults and source/record/frame/unit guards remain in place.
Registration #113, localization #152, measured validation #104 and final roadmap
cleanup #145 are separate work.

## Execution

Use the existing `.venv` from the repository root. Every asset, attempt and
summary directory must be new; failures and prior files are preserved.

```powershell
.venv/Scripts/python.exe -m src.simulation.capture_corpus --output tmp/pub11-assets
.venv/Scripts/python.exe -m src.analysis.regression.runner --manifest tmp/pub11-assets/corpus.json --asset-root tmp/pub11-assets --output tmp/pub11-fast --tier fast
.venv/Scripts/python.exe -m src.analysis.regression.runner --manifest tmp/pub11-assets/corpus.json --asset-root tmp/pub11-assets --output tmp/pub11-capture --tier capture
.venv/Scripts/python.exe -m src.analysis.regression.runner --manifest tmp/pub11-assets/corpus.json --asset-root tmp/pub11-assets --output tmp/pub11-one --tier representative --scene tracking_OFF-scene-0
.venv/Scripts/python.exe -m src.analysis.regression.runner --manifest tmp/pub11-assets/corpus.json --asset-root tmp/pub11-assets --output tmp/pub11-resume --tier representative --scene tracking_OFF-scene-0 --resume tmp/pub11-one/run_report.json
.venv/Scripts/python.exe -m src.analysis.regression.runner --manifest tmp/pub11-assets/corpus.json --asset-root tmp/pub11-assets --output tmp/pub11-full --tier full
.venv/Scripts/python.exe -m src.simulation.ci_evidence run --component pub09 --output tmp/pub11-calibration
```

`ci_evidence run` also accepts `pub07`, `pub08`, `pub10`, and `gui` (with the
existing retained `--trial-report`). `experimental` explicitly returns
blocked/nonzero because no verified measured sources/independent labels are
available. An unrequested experimental tier stays pending in public software
reports. A synthetic reference never replaces missing experimental evidence.

| Tier | Successful scope | Production reuse |
| --- | --- | --- |
| fast | Required source content, reviewed schema/profile/approval/baseline/tolerance and small artifact preflight | No production requested |
| capture | All six required Raw loads, fresh candidates and source-bound replay | No production requested |
| representative | Explicit selected approved scenes, current guards, save/reopen/Compare/export | Explicit resume only; report remains representative |
| full | All six required approved scenes of the declared PUB02 corpus, fresh production and all comparisons | Rejected |
| gui | The actual stated widget/selection/reopen/export and render-buffer checks | Retained PROC replay; fresh processing remains zero |
| experimental | Only verified measured input/independent-label scope, currently blocked | No measured execution claimed |

PUB02 v2 has an explicit adapter with six **required case IDs**, including the
zero-included-scene `handling_only`, and six approved scene IDs. Other corpus
versions have no implicit adapter. `protocol.json` fixes required cases,
selected scenes, original half-open anchors, expected metric statuses/values,
source/motion group/profile/seed, approvals/tolerances and identity before
processing. It is neither a generated baseline nor a numerical promotion.

## Counts and attempts

Loaded files/rows, approved/selected scenes, processing started/completed,
fresh/reused, failed/unexecuted and required/evaluable/passed are different
dimensions. Processing completion makes a scene fresh; a later save/reopen/
comparison failure also makes it failed. These dimensions are not forced into
one partition. Completion here includes successful required persistence and
comparison. An unavailable metric with its approved expected status can satisfy
a software preservation check without establishing numerical/physical accuracy.
Negative controls that correctly detect faults remain separate from normal full
regression. Missing, ambiguous, failed, skipped or unapproved required execution
does not become full success.

`loaded` counts distinct actually loaded input files, including source-bound
preflight reads in fast. `preflight_loaded_files` retains case/content/row scope
even when a later required source or baseline fails. Repeated preflight/detection
reads do not double the file count. Fast still reports zero detection/production.

`attempt-start.json`, immutable per-scene checkpoints, final `run_report.json`,
`junit.xml` and `summary.md` retain attempt identity and errors. Cooperative
cancellation/KeyboardInterrupt writes failure evidence; after a hard process kill,
the latest completed checkpoint can be supplied to `--resume`. Earlier failed
or incomplete scenes retry fresh in the new attempt. An existing output directory
is refused. I/O failures remain nonzero; a filesystem unable to write a report
can only retain its prior files and the calling process error/log.

A one-shot worker interrupt or cancellation stops initiating subsequent
production scenes. The first exception/traceback, prior successful checkpoints,
required protocol and actual unexecuted scope remain in the failed attempt.
Explicit representative resume revalidates completed scenes and retries missing
or interrupted scenes fresh in a new directory.

Reuse checks full input/content identities, successful completed scene status,
saved signature equality, slice/PROC/scenario hashes, exact original record/time
correspondence, source/settings/profile/correction linkage, actual PROC reopening,
current Compare and scenario bytes, and current all-time residual/metric guards.
It copies the validated triplet into the new attempt and retains the origin run
and predecessor report digest. Failure/corruption/stale identity is nonpass.
Location changes alone do not change identity. Raw content/anchors, approval
set/decision/date/basis, profile/meaning, geometry/frame/units, effective settings,
reference content/tolerance content/version, analysis source content/semantics,
Python/dependencies/platform and numerical environment changes invalidate reuse.
Content digests establish integrity, not authenticity against wholesale forgery.

## Existing validators and measurements

The wrapper invokes existing entry points in a fresh process, saves their original
report/log under `raw/`, and links them by digest. Its common RunReport uses schema1
and the Plan Spec. PUB07–10 proposed numerical diagnostics remain needs_review,
independently of successful required software execution. PUB02 required approved
numerical comparison missing/proposed still returns nonzero.

| Validator | Fixed required software population | Kept separate |
| --- | --- | --- |
| PUB07 | Four dynamics cases, releases 2/1/1/0 | Numerical approved0, measured n0 |
| PUB08 | Nine logical controls, three actual singles, one actual two-release production case | Physical correspondence/threshold approval |
| PUB09 demo | 29 engines: reference4, convergence12, fit6, synthetic holdout2, observed-production2, analytical3 | Synthetic holdout4 versus observed holdout4; no approved numeric passes |
| PUB10 | Physics8, observations16, production18, endpoints80 | Physics reused for variants; variants are not independent motions/trials |

The two additional PUB10 production calls are label-change and truth-deletion
controls. Production-observed PUB09 holdout retains its existing four
`not_detected` endpoints; reporting does not convert them to detection/correction
success. Existing truth isolation tests and entry-point controls still run.

Duration uses `perf_counter`. Memory is the process peak working set (Windows
GetProcessMemoryInfo), including imports, not incremental allocations. Production
optimizer calls are actual `PoseOptimizer` fit-start callbacks; review refits are
outside this count. Actual production input/result rows and attempt outcomes are
recorded without feeding any evaluation labels into the analyzer. Unmeasured
fields need unavailable status/reason, never an inferred zero.

## Required CI and GUI scope

The existing required Windows job and its 120-minute timeout are retained.
`tests/public_ci_inventory.json` fixes exact test node IDs and required step IDs.
`ci_evidence prepare` writes the required protocol before collection/execution and
checks collection against the reviewed inventory. Deleted tests do not silently
shrink the denominator. Every original validation step stays required.
`ci_evidence verify --require-step-outcomes` checks actual hosted step outcomes,
all required JUnit node populations/classifications/skips and source-matched
tier/component reports. Missing/duplicate/skipped jobs/tests, stale reports or
partial/reused full results fail. The always-running upload preserves protocols,
logs, original reports, trajectories, JUnit, JSON and readable summaries under
`tmp/issue144`. No private data runner is used.

Native evidence is separate from QTest input, widget grabs and VTK render pixels.
The explicit legacy release-GUI adapter reports those automatic scopes only.
Native window image content/3D visibility, external input and human review remain
pending unless independently inspected. Screenshot presence cannot satisfy them.
New-corpus Step1/1.5 native processing and native save chooser from PUB02 stay
pending. FHD/minimum existing GUI requirements remain enforced; no product UI was
added. Current local/review/CI/publication results are recorded in the delivery
evidence index and issue #144 after execution, without replacing earlier failures.

## Delivery evidence

The [versioned local evidence index](regression_evidence_v1.json) links source
digests, original logs, current tier attempts, review findings and preserved GUI
failures. The corrected implementation passed130 affected checks, including actual
full processing, one-shot worker cancellation and partial-success explicit resume.
Earlier127 checks,2 focused checks and standalone CLI attempts remain separate.
The read-only independent reviewer reproduced four P1 findings; corrected
positive fixtures pass and all original attacks fail. Required final-head hosted
CI and merge are tracked in [#144](https://github.com/pikachu444/BoxMotionAnalyzer/issues/144).
Local supporting runs do not replace that gate.
