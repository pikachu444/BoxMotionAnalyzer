# Independent production review — #138 / PUB05

Last Reviewed: 2026-10-06

**Outcome: APPROVE the reviewed production software delta.** The P1 and P2 findings are corrected and rechecked. No P0, P1 or P2 findings remain; none are deferred. Required hosted CI remains a separate publication gate. This verdict does not close #138.

The review was read-only, performed by the existing `profile_ui_review` reviewer. No additional agents were used, and no production, test, documentation or publisher evidence files were edited.

## Exact source binding

Workspace: `C:/SourceCodes/BoxMotionAnalyzer`  
Branch: `issue138-marker-profile-semantics`  
Base and dirty HEAD: `1f654faddd44eedf7ff6e807d85f5e08559f8b13`

The authoritative [review snapshot](C:/SourceCodes/BoxMotionAnalyzer/docs/visualization/mockups/marker_profile_138/production/review_snapshot.json) binds all **34 changed/new production, test and workflow files** through `code.sha256`.

- Snapshot file SHA256: `885938ece6635e5ba7e15e2be49cdebe592acfb57f0461b0f30bec3340b90f69`
- SHA256 of its complete `code.sha256` mapping, serialized as UTF-8 JSON with sorted keys and separators `(',', ':')`: `09ab3dec0aca428963599465d7fedc4817d412c789380172b98aa5090c22ba4c`
- All 34 file hashes matched. The Git delta contained no unlisted or extra production/test/workflow paths. The final verification found no subsequent source changes.

The [preserved correction snapshot before wording changes](C:/SourceCodes/BoxMotionAnalyzer/docs/visualization/mockups/marker_profile_138/production/review_snapshot_before_wording.json) has file SHA256:

`b089c169bee60176f1eb14101b4889abeb42a4b230c49b9dc06b078fa5ec9d5a`

Only `artifact_metadata.py`, `marker_profile_identity.py` and their two reason-string test files changed between that snapshot and the final snapshot.

## Resolved findings

**P1 — declared local support could be bypassed by observational perturbations.**  
Locations: [pose_optimizer.py](C:/SourceCodes/BoxMotionAnalyzer/src/analysis/pipeline/pose_optimizer.py:223), [artifact_metadata.py](C:/SourceCodes/BoxMotionAnalyzer/src/utils/artifact_metadata.py:127).

The independent reproduction used six face-centre markers on a 200×120×80 box:

```text
F1 [0,0,40]       B1 [0,0,-40]
R1 [100,0,0]      L1 [-100,0,0]
T1 [0,60,0]       M1 [0,-60,0]
```

The declared first-order constraint rank is 3. Adding these literal observation-only vectors, multiplied by 0.01mm, previously caused the actual Raw optimizer to emit `Optimized`:

```text
[[1,2,0],[-2,1,0],[0,2,-1],
 [0,-1,2],[1,0,2],[-2,0,-1]]
```

This bypassed the declared source’s support limitation under the current solver. The correction gates every declared support status other than `supported` before optimization and adds an unavailable-source aggregation exclusion.

Independent rechecks passed:

- Observation perturbation multipliers 0, 0.01, 0.1 and 1 all produced `UnidentifiableGeometry`.
- Six pose coordinates and all 24 corner coordinates remained NaN.
- Observed columns and metadata attributes remained exact.
- Actual writer→loader→parser→pipeline→proc reload→`ComparisonModel` tests passed for unavailable and ambiguous declarations, including explicit exclusion reasons and zero aggregate counts.
- Unchanged complete-profile collinear cases with 3, 4 and 5 Front markers still recovered their analytic trajectories; corresponding face-only cases remained unavailable.

**P2 — blocked export lacked a visible explanation.**  
Location: [marker_export_dialog.py](C:/SourceCodes/BoxMotionAnalyzer/src/simulation/ui/marker_export_dialog.py:248).

Importing an ambiguous or unavailable layout disabled Generate while retaining an instruction to generate observations. The correction now displays the actual support reason in the status and Generate tooltip, uses it for direct `generate()` calls, and clears it upon returning to a supported profile.

Independent Qt checks passed at DPR1 and DPR1.25. Previous output path, identity, compatibility information and Open remained preserved. Original blocked-export images show the reason and necessary actions within the 820×600 client.

## Mathematical wording boundary

The final wording correctly limits the rank condition to the **current solver’s local method**:

> This layout lacks local six-DOF support for the current solver.

The aggregation reason states that the declared layout fails the local pose rank guard.

Rank3 alone is not a general proof of global nonidentifiability. Exact opposite face-centre constraints can constrain a unique orientation through higher-order conditions. `global_uniqueness_status` remains `unavailable`; neither the correction nor this review asserts an exhaustive uniqueness result. The historical `UnidentifiableGeometry` status spelling remains unchanged.

## Independent execution and reuse boundary

Initial independent commands, using `.venv/Scripts/python.exe`, Windows Qt and `PYTHONDONTWRITEBYTECODE=1`:

```powershell
$env:QT_SCALE_FACTOR='1'
.venv/Scripts/python.exe -m pytest -q tests/test_marker_profile_identity.py tests/test_marker_profile_gui.py --maxfail=1 --basetemp=tmp/reviewer138/pytest-temp-100 --junitxml=tmp/reviewer138/identity-gui-100.xml

$env:QT_SCALE_FACTOR='1.25'
.venv/Scripts/python.exe -m pytest -q tests/test_marker_profile_gui.py --maxfail=1 --basetemp=tmp/reviewer138/pytest-temp-125 --junitxml=tmp/reviewer138/gui-125.xml
```

These passed **47** and **7** cases respectively during the initial audit. They did not establish the subsequently discovered P1 boundary. An earlier attempt stopped after 29 passes because I had not created the reviewer output parent directory; creating that directory corrected the tooling error.

Fresh independent corrected-source probes used direct Python calls with fresh case directories under `tmp/reviewer138`:

- `test_declared_layout_support_producer_pipeline_and_result_roundtrip(case, monkeypatch, kind)` for `ambiguous` and `unavailable`.
- `test_public_collinear_face_export_recovers_whole_pose(case, monkeypatch, count)` and `test_face_only_profile_stays_unavailable_in_pose_solver(count)` for counts 3, 4 and 5.
- `test_export_blocked_reason_and_previous_output_preserved(app, kind)` for both blocked types, in separate DPR1 and DPR1.25 processes.
- A separate literal perturbation probe checked exact observations/attrs and all pose/corner NaNs.

Only test evidence paths were redirected into `tmp/reviewer138`; tested production behavior and assertions were unchanged. All calls exited successfully.

These corrected algorithm probes preceded the final reason-string-only changes. Their **unchanged algorithm scope is reused**, not presented as fresh execution against the final wording snapshot. Final hash, source-text, documentation, report and pixel checks were fresh.

I independently read the original Main JUnit outcomes: corrected core **91**, consumers **146**, Qt125 GUI/export **14**, final wording/profile **50**, and final wording Qt125 GUI **9**, all with zero failures, errors or skips. These are separate runs, not additive unique coverage.

## UI, oracle and reporting checks

Actual code and state paths preserve immutable presets/source snapshots, distinct draft/valid Preview/applied state, explicit Apply, Cancel, atomic save/retry and pending-draft reopen. Stale worker events cannot replace current state or previous outputs. Legacy meaning remains unknown, unsupported declarations are rejected, and author-only compatibility retains the other provenance and processing gates.

Same-face swaps preserve the Raw centre/objective; mapping-only reuse requires scoped review and does not infer numerical pose change. Display offsets and gestures retain physical coordinates, identities and results.

I inspected production FHD, small-window, Qt125, invalid, edited, unavailable and ambiguous images, including the final scoped export reason. Names, selected-marker coordinates, face counts, toolbar association and necessary actions are acceptable within the reviewed states.

All **60 final editor PNGs** matched recorded dimensions, logical-size×DPR and current renderer hashes. FHD originals are 1920×1080 and 2400×1350; no upscaling was inferred. Final RunReports correctly separate widget coverage, approval counts, native status and inapplicable capture/accuracy/memory fields.

Expectations use literal geometry, independent perturbations, analytic rigid motions and explicit state transitions. No experimental truth was used as analysis input. Performance approval is structural—retained buffers, cancellable bounded placement and bounded caches—not a native latency, FPS or RSS certification.

## Exclusions and publication boundary

The following remain unexecuted or unapproved:

- External native screen/input acceptance, actual Windows OS125%, native chooser/save-failure/retry/reopen and accessibility acceptance. Qt process scaling and QTest are separate evidence.
- Independently calibrated measured accuracy and a validated real dataset under #104.
- Migration, trial, physical tolerance or baseline approval.
- Required clean-commit hosted `synthetic-integration` CI.

The #113 registration user feature remains excluded; existing static adapter/source binding was reviewed. Delivered #135/#136/#137 behavior and native follow-ups remain separate. #139/#143 are outside this review.

**The reviewed production source is approved for the next publication steps subject to required hosted CI. Native follow-up remains open, and #138 must not be closed on this verdict.**
