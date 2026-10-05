# PUB05 production review packet — #138

Last Reviewed: 2026-10-06

Plan Spec: ISTA6A-PLAN-20261001-v1

## Review boundary and authorization

Main is the only writer, tester and publisher. Reuse the existing
`profile_ui_review` GPT-6.1 Sol / high reviewer: read-only, no additional agents.
Review the actual production delta and evidence, independently of conversation
history. Report severity, file/line, reproduction, impact and completion effect.
P0/P1 must be corrected and rechecked by this same reviewer before publication.

Base and current dirty HEAD: `1f654faddd44eedf7ff6e807d85f5e08559f8b13`.
Branch: `issue138-marker-profile-semantics`; origin is
`https://github.com/pikachu444/BoxMotionAnalyzer.git`. Initial tree was clean.
[Review snapshot](mockups/marker_profile_138/production/review_snapshot.json)
enumerates every changed/new production/test/workflow file and its SHA256.
Historical prototype files are evidence, not production imports.

The user approved the final interactive mockup on 2026-10-06, after this
reviewer's v11 gesture/visibility/caption approval. Source viewport SHA256 was
`f4192d9e479f84605b9eeff6a75f4ed113638dc332ee812c251decd8795c0b90`;
caption harness SHA256 was
`fc4935d77caa67fbc8e8fa4ea8ac843d4f4bf582be2583c2fb78c234d96e70a4`.
Main copied that viewport into the production package and connected the actual
editor/state/producer paths. Check that UI terms, menu positions and actual
painted marker readability remain acceptable.

## Requirements and exclusions

- Reuse example18/32, existing custom import/hash/coordinate/face-prefix checks,
  preview and #116's complete-profile collinear recovery. Add only missing
  semantic identity/version and Copy/Edit/Reset/Preview/Apply/save flows.
- Distinguish positions, label-to-position correspondence and meanings
  (label/face/normal/frame/axis/half-turn), including actual fixed code constants.
  Preserve literal old example hashes and author profile_version.
- Presets/source snapshots stay immutable. Draft and last valid Preview are
  distinct from applied profile. Reset targets the draft source, requires renewed
  Preview/Apply; Cancel leaves the parent unchanged. Save/reopen preserves source,
  draft, preview, applied identities/revisions and history; failure/retry is atomic.
- Record compatibility/status/reasons. Legacy missing semantics is unknown,
  cannot become compatible/approved. Unsupported versions, missing source,
  wrong units/frame/time, nonfinite values and stale identity cannot succeed.
- Sufficient complete local support allows a collinear face. Rank deficiency
  and independently witnessed global ambiguity are explicit unavailable/ambiguous.
  Full rank alone is not global uniqueness; names alone never certify face.
- Source/profile changes cancel obsolete jobs; stale Preview/worker events cannot
  overwrite current draft/applied state or previous results/decisions. Verify actual
  producer/export/save/reload/Raw/result/Compare consumption and scoped invalidation.
- Preserve single_drop default, baseline/source lineage, correction default OFF
  and preview vs explicit correction Apply. No automatic deletion, Include,
  trial approval, tolerance approval or baseline promotion. No truth analysis input.
- #135/146, #136/147, #137/148 are already delivered. Preserve their behavior and
  native follow-ups; do not block this implementation on older GUI evidence.
- #113 registration user feature is excluded by user decision. Existing static
  #135 geometry adapter/source binding remains in scope; no new registration UI.
  #104 measured validation is separate, with no validated real dataset assumed.
  Do not implement #139 onward/#143. Do not close #138 while native work remains.

## Actual delta and compatibility policy

`marker_semantics.py` shares actual constants among fixture generation, face
assignment and local half-turn analysis. `marker_profile_identity.py` implements
source-bound schema1/plan contracts and reads actual normal/prefix/corner/frame/
axis/half-turn constants. Full identity is for profile history; compact artifact
declaration retains source geometry without repeating the entire fixed policy.

Unchanged author hash: public18
`66ac8c6d2bcd9b531d532a23c2af7b04e72a7ae1ab1ae8aa8c0c8ec7ef77bafb`, public32
`d5405f1cf434c924070033748b4ca1e4661f10e190369d8f0bb0aac75fc97ff0`.
Geometry ignores label/order/author metadata; correspondence tracks label→XYZ;
semantic identity tracks label→face and fixed interpretation. Author/order-only
changes are compatible. Geometry/meaning changes are incompatible. Mapping-only
changes require scoped review, with `numerical_pose_change=not_inferred`.

The user's centre-invariance objection is explicitly preserved: same-face swaps
keep centroid and actual Raw face-surface objective/rank. #135 static-template
matching can instead change residual while retaining centre. Display offsets,
rotation/pan/zoom/face drag never edit physical coordinates, identity or results.
No stored numbers are rewritten and no migration is performed. Check actual
Compare author-only equivalence still retains source/model/trial/processing gates.

Layout support uses the existing relative rank tolerance1e-6 and a bounded search
for 23 signed-axis rotation witnesses at the declared centre, with existing face
arithmetic tolerance1e-8mm. Literal cube-edge geometry admits I and Ry(+90°) at
rank6. Such declared ambiguity blocks Apply/generation/aggregation and the Raw
consumer preserves observed records with AmbiguousGeometry and NaN pose/corners.
Absence of witnesses leaves global_uniqueness_status unavailable; no exhaustive
global search/real-world uniqueness certificate is claimed.

`ProfileEditorState` and atomic ProfileDocument preserve history/decisions.
`MarkerProfileDialog` connects table editing and retained viewport, pinned narrow
2D controls, selection and finite/stale/legacy/blocked states. Wide table width
and 55:45 preview allocation follow the approved design. `MarkerExportDialog`
adds copy/edit/import and per-job semantic snapshots/cancellation guards.

Fixtures/corruption/capture producers declare identity; metadata whitelist retains
it through corrected source, slice and proc. Loader/Parser validate actual channels;
Parser/PoseOptimizer/Controller transport observation declaration. Static scene
geometry must match a new declaration; legacy static adapters remain usable.
Step2 refuses explicitly invalid/stale declarations while legacy individual viewing
remains available with unknown semantics; Compare blocks unknown/incompatible
evidence. New corpus replay binds declaration to observed artifacts; old partial
`legacy-face-assignment-v3` digest and frozen assets stay historical.

Performance is structural: retained geometry/projection and artists, no 2D redraw
or name solve per 3D motion, one cancellable placement job, bounded candidate
batches, LRU8 and sample deque256. Placement deadlines are cooperative, not hard
latency/FPS guarantees. Import minimum separation now uses a nearest-neighbour
tree instead of allocating N×N distances. No memory-budget approval is inferred.

## Independent oracles and execution evidence

All commands use `.venv/Scripts/python.exe`, Windows11, Python3.13.5,
PySide6.10.1, MuJoCo3.6.0, NumPy2.3.5, pandas2.3.3, SciPy1.16.3,
Matplotlib3.10.7. Actual versions/head/dirty/input identities/seeds/differences/
tolerances and fresh/reused scope are in original reports/JUnit and the snapshot.
New test expectations are literal coordinates/matrices, analytic rigid motions,
centre/objective invariance, analytic static correspondence RMSE, independently
declared ambiguous geometry and explicit UI state transitions, not production
output copied as expected values. Observation seed74082; static UI has no seed.

Fresh final local commands:

```powershell
.venv/Scripts/python.exe -m pytest -q tests/test_marker_profile_identity.py tests/test_marker_profile_gui.py tests/test_collinear_profile_recovery.py tests/test_artifact_provenance.py tests/test_scene_face_corrections.py tests/test_result_file_context.py --maxfail=1 --junitxml=tmp/issue138/frozen-core-recheck-100.xml
.venv/Scripts/python.exe -m pytest -q tests/test_marker_profile_identity.py tests/test_processing_semantics.py tests/test_marker_flip_artifact_io.py tests/test_capture_regression.py --maxfail=1 --junitxml=tmp/issue138/frozen-contract-processing.xml
$env:QT_SCALE_FACTOR='1'
.venv/Scripts/python.exe -m src.simulation.profile_validation --output tmp/issue138/production-final-100
$env:QT_SCALE_FACTOR='1.25'
.venv/Scripts/python.exe -m pytest -q tests/test_marker_profile_gui.py --junitxml=tmp/issue138/frozen-gui-125.xml
.venv/Scripts/python.exe -m src.simulation.profile_validation --output tmp/issue138/production-final-125
.venv/Scripts/python.exe -m src.analysis.regression.runner --manifest tmp/issue135/assets_v2/corpus.json --asset-root tmp/issue135/assets_v2 --output tmp/issue138/legacy-capture-full --tier full
.venv/Scripts/python.exe -m pytest -q tests/test_marker_profile_identity.py --junitxml=tmp/issue138/semantic-evidence-level-recheck.xml
.venv/Scripts/python.exe -m src.simulation.public_validation_summary --junit tmp/issue138/semantic-evidence-level-recheck.xml --output tmp/issue138/semantic-evidence-level-summary.json --public-required
```

Core88 passed. Qt125 GUI7 passed; production renders30 states per DPR passed.
Legacy corpus6/6 fresh passed against unchanged frozen references, 0 reused;
legacy comparison counts remain0 because missing semantic evidence is unknown.
This is software preservation, never new trial/baseline approval. Final contract/
processing143 passed; its original JUnit records the per-case results.
Classification addendum: the actual producer/consumer ambiguity test is explicitly
Level2; other new contract/widget tests stay Level1. Fresh40 profile tests and
required summary passed (39Level1/1Level2). The first command mistakenly named a
nonexistent summary test module: exit4/0 collected, recorded as a command failure,
never a pass. No runtime policy changed in this one-line classification addition.

Earlier preservation passes: compatibility/Compare/posture/contact176;
metric-related204; geometry/capture107. Local workflow list runs: initial561
passed before a newly enforced legacy gate exposed old fake test declarations;
the next39 passed before an incoherent dimension declaration was exposed. Main
replaced those analytic fixture declarations with independent explicit geometry,
retained their old numeric oracles and did not weaken legacy gates. Remainder2:
629 passed and3 subtests,16 existing negative-case warnings. These were preliminary
source snapshots; clean-commit hosted CI is the final full-suite gate. Required
suite/125%-render commands live in `.github/workflows/public-marker-validation.yml`.

The first new whole-pipeline ambiguity test failed because FrameAnalyzer rebuilt
the table and dropped metadata. Main retains the validated observation declaration
at the controller output; fresh core recheck passed88. The earlier QTest offset
expectation1.2 was wrong: example18 default Front offset is.8, so +.2 is1.0;
Main corrected the independent expectation. Incomplete constant-edit import and
Pose_Source test-key errors were corrected before final passes. Failed attempts
are retained; they are not relabelled as acceptance passes.

The publication snapshot includes exact JUnit outcomes without summing repeated
runs. Legacy RunReport contains expected/actual/difference/tolerance and source/
manifest identities. No new physical tolerance or baseline was approved.

## Production images and limitations

- [32 FHD, original1920×1080](mockups/marker_profile_138/production/100/32-1920x1080-default-top.png)
- [18 FHD](mockups/marker_profile_138/production/100/18-1920x1080-default-top.png)
- [Small window lower controls](mockups/marker_profile_138/production/100/32-820x600-default-bottom.png)
- [Invalid cell and disabled actions](mockups/marker_profile_138/production/100/32-1920x1080-invalid-top.png)
- [Preview incompatible meaning, applied source unchanged](mockups/marker_profile_138/production/100/32-1920x1080-edited-top.png)
- [Rank-deficient and unknown legacy state](mockups/marker_profile_138/production/100/32-1920x1080-geometry-blocked-top.png)
- [Full-rank ambiguous state](mockups/marker_profile_138/production/100/32-1920x1080-ambiguous-top.png)
- [Qt125 FHD, original2400×1350](mockups/marker_profile_138/production/125/32-1920x1080-default-top.png)
- [DPR1 RunReport](mockups/marker_profile_138/production/100/execution.json)
- [DPR1.25 RunReport](mockups/marker_profile_138/production/125/execution.json)

Render checks inspect actual painted badges/titles/points, bounded state, button
containment, immutable source and correct gates. Default18/32 names have0 badge/
point/title occlusions in captured states. Arbitrary angles/imports may use explicit
limited-name/candidate-menu/2D fallback; do not claim universal overlap-free display.

Local physical desktop2560×1440, OS100%. Logical1920×1080 and820×600 captures
are original widget PNGs, with QtDPR1/1.25 recorded independently of OS scaling;
no upscaling. Native Windows Qt/widget/QTest is distinct from external native
screen/input acceptance. Retained black-capture/activation failures and current
disabled native CUA APIs leave actual OS125%, external gestures, native chooser/
save-failure/retry/reopen and accessibility unexecuted. Do not mark them passed.
Independent production verdict, required hosted CI and publication remain pending
at this review packet boundary. #138 remains open for native follow-up; #104 real
accuracy remains unavailable. No next issue is authorized by completion here.

## Same-reviewer correction boundary

The first formal production audit found one P1 and one P2, with no other
findings. Its original34-file snapshot is retained as
`production/review_snapshot_before_corrections.json`; it is historical evidence,
not a current acceptance record. The current review_snapshot is authoritative.

P1: declared six face centres (200×120×80) have rank3/unavailable under the
current solver's local rank guard. This is a method support limitation, not a
proof of global nonidentifiability; exact face centres can constrain a unique
orientation through higher-order constraints. Independent
per-marker lateral vectors
`[[1,2,0],[-2,1,0],[0,2,-1],[0,-1,2],[1,0,2],[-2,0,-1]]*0.01mm`
raise observed numerical rank to6 and previously produced Optimized pose.
Main gates declared unavailable as well as ambiguous before fitting, preserves
all observations/attrs with UnidentifiableGeometry and NaN pose/corners, and
excludes both declarations from Compare. The independent offsets use the existing
per-marker observation-only reconnect_jump API; truth/profile stay unchanged.
Writer→parser→pipeline→proc reload→actual ComparisonModel is tested for both
declarations, including zero aggregate counts and preserved input hashes.

P2: imported ambiguous/unavailable layouts disabled Generate silently. Main
shows the actual support reason in status/tooltip/direct generate, retains
previous output and compatibility/Open, and clears the block when a supported
profile is selected. Both blocked types have original820 captures at both DPRs.

Corrected core91 passed59.67s, including unchanged whole-collinear3/4/5 and
face-only cases. Corrected Qt125 profile+existing export14 passed32.63s. The
initial combined export command at Qt1 failed because an existing test explicitly
requires1.25 (13 passed,1 failed); the correct invocation passed14. This was
an execution-environment error, not a product failure or new tolerance.
Consumer/Compare146 passed131.64s, including the actual ComparisonModel zero
aggregate check after producer/pipeline/proc roundtrip. Editor render30
states per DPR freshly passed again after applicable RunReport fields were
completed (KST/UTC, semantics/dependencies/tier/schema, coverage/cache/duration,
exit/exception and explicit inapplicable-field reasons). Status enums now use
the parent contract; aggregate review-boundary status is needs_review while
automatic results are recorded separately. No native/experimental pass is added.

Additional commands:

```powershell
$env:QT_SCALE_FACTOR='1'
.venv/Scripts/python.exe -m pytest -q tests/test_marker_profile_identity.py tests/test_marker_profile_gui.py tests/test_collinear_profile_recovery.py tests/test_artifact_provenance.py tests/test_scene_face_corrections.py tests/test_result_file_context.py --maxfail=1 --junitxml=tmp/issue138/review-corrections-core.xml
.venv/Scripts/python.exe -m pytest -q tests/test_marker_profile_identity.py tests/test_compare_model.py tests/test_contact_comparison.py --maxfail=1 --junitxml=tmp/issue138/review-corrections-consumers.xml
.venv/Scripts/python.exe -m src.simulation.public_validation_summary --junit tmp/issue138/review-corrections-core.xml --output tmp/issue138/review-corrections-summary.json --public-required
.venv/Scripts/python.exe -m src.simulation.profile_validation --output tmp/issue138/production-corrected-100
$env:QT_SCALE_FACTOR='1.25'
.venv/Scripts/python.exe -m pytest -q tests/test_marker_profile_gui.py tests/test_simulation_marker_export_gui.py --junitxml=tmp/issue138/export-reason-recheck-125.xml
.venv/Scripts/python.exe -m src.simulation.profile_validation --output tmp/issue138/production-corrected-125
```

The subsequent wording-only correction explicitly scopes unavailable to the
current solver's local six-DOF support; no numerical or gating change was made.
Visible reason: "This layout lacks local six-DOF support for the current solver."
Aggregate exclusion: "declared layout fails local pose rank guard; individual
review only". Display-only offsets retain the physical centre and results;
correspondence-only reuse review does not infer a numerical pose change.
Fresh affected profile/editor50 passed182.92s at DPR1, and editor9 passed27.06s
at DPR1.25. These checks and30 renders per DPR bind that text to current code
and original pixels. The exact pre-wording correction snapshot is retained as
`production/review_snapshot_before_wording.json`, file SHA256
`b089c169bee60176f1eb14101b4889abeb42a4b230c49b9dc06b078fa5ec9d5a`.
The same reviewer's fresh corrected-gate probes preceded this reason-only edit;
only their unchanged algorithm scope is reused for the final text recheck.
Commands:

```powershell
$env:QT_SCALE_FACTOR='1'
.venv/Scripts/python.exe -m pytest -q tests/test_marker_profile_identity.py tests/test_marker_profile_gui.py --junitxml=tmp/issue138/review-wording-100.xml
.venv/Scripts/python.exe -m src.simulation.profile_validation --output tmp/issue138/production-wording-100
$env:QT_SCALE_FACTOR='1.25'
.venv/Scripts/python.exe -m pytest -q tests/test_marker_profile_gui.py --junitxml=tmp/issue138/review-wording-125.xml
.venv/Scripts/python.exe -m src.simulation.profile_validation --output tmp/issue138/production-wording-125
```

Same-reviewer bounded correction audit is APPROVE with no remaining P0/P1/P2;
the [unaltered final report](marker_profile_138_independent_review.md) binds the
34 source hashes and records exact fresh/reused limits. Required clean-commit
hosted CI still gates merge; no P2 is deferred. Final publication/CI status is
recorded in the linked PR. This does not close #138's native follow-up.
