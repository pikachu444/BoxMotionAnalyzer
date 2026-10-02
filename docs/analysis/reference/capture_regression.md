# Capture regression (#135)

Last Reviewed: 2026-10-02

## Scope

`src.analysis.regression.runner` connects existing production APIs through full observed Raw load → fresh scene detection → source-bound review replay → marker-based identification → slice save/reopen → Raw processing → proc save/reopen → Compare/scenario export. This implements only #135 of parent #134. No validated experimental input is available. Public analytical observations, independent analytical expectations and reviewed detector preservation snapshots have separate roles. #104 measured accuracy and physical calibration remain pending.

#113 registration is not a prerequisite. Static dimensions/floor/layout and known local offsets are declared for this corpus, and conflicting embedded Raw declarations block replay. #138's future marker meaning contract is tracked separately: current `legacy-face-assignment-v3` face/normal/half-turn-map digest is bound without migrating existing layout hashes.

## Commands and tiers

Run from the repository root on Windows:

```powershell
.venv/Scripts/python.exe -m src.simulation.capture_corpus --output tmp/capture-assets-v2
.venv/Scripts/python.exe -m src.analysis.regression.runner --manifest tmp/capture-assets-v2/corpus.json --asset-root tmp/capture-assets-v2 --output tmp/capture-full --tier full
.venv/Scripts/python.exe -m src.analysis.regression.runner --manifest tmp/capture-assets-v2/corpus.json --asset-root tmp/capture-assets-v2 --output tmp/capture-one --tier representative --scene two_drops-scene-0
.venv/Scripts/python.exe -m pytest tests/test_capture_regression.py -q --junitxml=tmp/capture-tests.xml
```

Asset/run directories must be new: no baseline overwrite, update-baseline option or proc cache. Capture tier verifies loading/detection/replay only. Representative requires explicit scene selection; approved scenes outside it remain unexecuted. Capture+selection is rejected. Full requires every declared approved scene freshly processed with exact source/row/time correspondence, save/reload and required comparisons. Fail/blocked/needs_review return nonzero. A successful core call followed by failed save remains both fresh and failed; counts describe separate dimensions. Actual optimizer fit starts survive exceptions. Partial file inventory is distinct from completed artifact triplets.

Approvals bind raw SHA256, original record bounds, raw time and neighboring observed-data digest. Candidate ordinal/proximity never transfers approval. Split, merged, missing, ambiguous, changed_boundary, stale_anchor and new unreviewed candidates require review. Included manual ranges retain separate identities and do not approve overlapping automatic candidates.

## Independent public corpus

Immutable `public-analytic-corpus-v2`, seed 135001, has six captures/552 Raw records and six included scenes/452 result records. The public example uses 18 asymmetric markers and a 200×120×80 mm box. It is not an experimental standard. Floor is world Y=0 mm, rotations map local to world. Time=`10+0.01*record` seconds; Frame=`1000+3*record` cannot substitute for time or identity.

| Capture | Raw records | Included [start,end) | Independent motion |
| --- | ---: | --- | --- |
| two_drops | 180 | [0,80), [100,180) | Two ballistic descents; intervening lift excluded |
| supported_H | 80 | [0,80) | Supported Z pivot, 0→0.2→0 rad→return |
| handling_only | 80 | none | Elevated horizontal handling; all candidates excluded |
| tracking_OFF | 80 | [0,80) | Missing marker rows 30…32; observed X half-turn from 55, explicit OFF |
| partial | 60 | [0,60) | −60 mm/s descent and slow Z rotation, no impact |
| two_flips | 72 | [0,72) | Observed X at 20/Y at 48, explicitly approved chronological correction |

Builder formulas specify center/rotation and separate literal C1…C8 coordinates. Detector or analysis outputs never generate pose/metric truth. Frozen automatic candidate intervals are reviewed **preservation snapshots**, all Exclude; included manual bounds come from explicit test definitions. Only observed coordinates, static geometry and processing options enter the optimizer. Reviewed test identity is attached as metadata after identification. References/truth are evaluated outside the production boundary.

Descent uses `tau=max(0,(record-start-8)*0.01)`, `center_y=max(60,280−9806.65*tau²/2)` mm. Prescribed sampled first contact is local record 30; t1− is record 29, hence raw 10.29/11.29 s. Expected precontact vertical velocity=−9.80665×0.21=−2.0593965 m/s, horizontal speed=hypot(0.02,0.003)=0.0202237484 m/s, spin=0. H maximum rotation=0.2×180/pi=11.4591559026°, final=0; partial final=0.059×180/pi=3.3804509913°.

OFF expects the observed half-turn, not recovery of missing physical truth. Three missing observations remain unavailable and existing whole-record contact becomes Unavailable. Unsupported physical contact/rebound/target posture/equivalent height/final face have explicit unavailable reasons, never zero. Legacy t2 absence differs from multiple contact transitions whose second time is not serialized.

## Reviewed baselines

Independent reviewer `requirements_review` approved public software formulas, replay and bounds on 2026-10-02 after two fresh proposed-gate probes showed exactly zero numerical variation (`tmp/issue135/probe_01`, `probe_02`, `repeat_variation.json`). This does not approve experimental/ISTA/native-GUI/full-run accuracy. Partial descent was fixed at −60 mm/s before acceptance processing to avoid equality at the existing strict −50 mm/s trend boundary.

All relative tolerances are zero. Center 0.1 mm/rotation 0.1° retain existing noiseless gates. Corner/floor 0.35 mm covers 0.1 mm plus 123.3 mm radius×sin(0.1°). Diagnostic angles use 0.1°, DeltaH 0.35 mm. Raw event gate 1e−8 s preserves a sample; 0.01 s sampling uncertainty is separate. Velocity 0.005 m/s/spin 0.01 rad/s are stricter noiseless gates, **not** worst-case propagated pose error: five-point quadratic endpoint ±0.1 mm would allow 0.0228571 m/s, and ±0.1° over 0.04 s gives 0.0873 rad/s. Repeats never automatically enlarge bounds. Missing/proposed tolerances are nonpass.

v1's failed full run exposed a reference meaning mismatch. `{C1,C2,C5,C6}` geometric contact had been compared to gated Compare first_contact. Manual intervals subdivide one continuously active capture; existing `recorded-first-event-consistency-v1` conservatively rejects eligibility when left-censored. Independently reviewed v2 keeps the required geometric set as `observed_first_contact` and expects gated `first_contact=unavailable`. No Raw/bounds/pose/numeric expectation/tolerance changed. Manifest records old/new/cause/impact/reviewer/date. v1 assets and failed full_01 remain immutable local evidence.

## Data and preservation contracts

Every envelope has schema_version=1/plan_spec=`ISTA6A-PLAN-20261001-v1`. Unsupported versions, missing required fields, nonfinite JSON, incompatible units/frame and stale sources block execution. Fixture carries source/profile/semantic/geometry/configuration identities and reviewed decisions. CaptureSignature includes all candidate evidence/mappings, marker quality/NaN/freeze/pose availability, file inventory, comparison exclusions/n and coverage. SceneSignature records event policy/status/time, metrics, canonical representative samples, unavailable reasons, jumps/extrema and full residual summaries. RunReport includes UTC/KST, code commit/dirty, dependencies/command, identities/tolerances, expected/actual/difference, first failed boundary/traceback, actual fit starts, duration and process peak working set. CLI execution leaves GUI and independent execution review pending until separately reviewed.

Original record identity excludes header/blank lines but includes malformed Time records before parsing/slicing. Parser preserves removed indices/reasons. Shared `recorded_seconds` and proc round_trip reads preserve clocks such as `11.120000000000001`. Additive `Info / Source / OriginalRecordIndex` and `Info / CaptureReplay / Json` plus slice SceneReview capture_replay carry exact source/config/geometry/row linkage. Legacy inclusive slice end is explicitly timestamp[b−1] for [a,b); EOF time[N] is never accessed and unknown exclusive time stays unavailable.

Ordinary new GUI slices also save optional `original_record_indices` metadata, preserving source indices across nested slicing and reopened corrected suffixes. Loader validates count/type/strict order and consistency with CaptureReplay if present. Old slices without this field retain only file-local indices; original capture correspondence is not inferred. This fixes the existing suffix GUI preservation test where source70…99 had otherwise reopened as0…29 after the additive record column was introduced.

Canonical solver position is geometric center; origin and COM are separate known body-local offsets: `p_center=p_origin+R*r_origin_to_center`, `p_com=p_origin+R*r_origin_to_com`; velocity includes `omega_world cross (R*r_origin_to_center)`. Nonzero-offset tests cover this term. Existing aliases, default correction OFF, single_drop behavior, units and seven-line scenario format remain unchanged. GUI/CLI share the serializer; an independent evaluator checks globally lowest permitted corner group, lowest three/order, floor heights and local velocity.

Every reference row/raw time/valid mask is required. All valid samples check center norm, SO(3) angle (quaternion sign equivalent), each of eight corner position norms and floor height errors. Missing/unauthorized masks fail; approved unavailable rows must remain all-NaN. No common-valid-only selection, interpolation, t2 realignment or zero fill. Small maxima/count/first-time/per-corner/reference-hash summaries enter Git; full trajectories remain local assets.

## Execution evidence and pending scope

Normal full passed: loaded6/approved6/fresh6/reused0/failed0/unexecuted0; 449 optimizer starts, 452 proc rows=449valid+3approved unavailable. Contact states: ImpactEvent, ImpactEvent, SustainedContact, Unavailable, Approach, NoContact. Maximum all-time residuals: center0.0002098201 mm, R0.0004042305°, corner0.0010677346 mm, floor0.0004760921 mm; zero bound violations. Per-scene expected/actual/bounds are in immutable RunReports. [Compact final evidence](capture_regression_validation.json) links full local reports, inputs and environment; CI uploads `tmp/issue135`.

Failure controls cover scene deletion, candidate split/merge/missing/ambiguity, handling inclusion, OFF forced correction, exchanged flip axes/shifted boundary, event shifts, corner swap, m/mm, stale proc, n inflation, missing→zero and an inter-sample spike below unchanged global extrema/jump maxima. Missing Raw/reference/tolerance approval and worker/slice/proc failures remain nonpass. Direct production boundaries forbid reference/truth sidecar reads; hashes of Raw/reference/truth/manifest remain unchanged. Actual processing after truth deletion/label corruption stays equal. Normal full success is distinct from successful negative-control tests.

Initial production/scenario preservation:212passed. Independent Loader/artifact/correction/Compare/workspace/header rerun:109passed. Required public CI retains existing GUI/collision/continuity checks and adds new full integration, truth isolation and failure tests.

Implementation and public automatic regression are complete subject to final review/CI publication. Native MainApp Step2 loads six fresh outputs, selects a sample, clicks the actual scenario export button and opens Compare; bytes/source hashes agree. GUI reuses6 proc/fresh0. Reviewed local screen2560×1440/DPR1.0/window1510×800. New-corpus native Step1/1.5 fresh processing and native save chooser remain pending. The local 3-D viewport was black, with cause unconfirmed, so visual playback is pending too. Existing GUI preservation evidence has separate scope. Experimental accuracy/physical calibration remains #104 pending.
