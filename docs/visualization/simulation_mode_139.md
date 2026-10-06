# Simulation mode contract — PUB06

Last Reviewed: 2026-10-06

Plan Spec: ISTA6A-PLAN-20261001-v1

## Start and preservation

Start branch `issue138-marker-profile-semantics` at
`4b06c469647f322da9f1d46967f70d8db74ab0d2`; origin main was
`d2e7656403b740da22d631f2ab8df6e100231ff1`. Their tracked source trees
matched. No tracked edits existed. The 380 untracked #138 evidence files
and unrelated issue112 worktree were retained. Main fetched and created
`issue139-simulation-mode-contract` from current origin/main without reset.
Full local start inventory is `tmp/issue139/start/`.

User chose the minimum robot_sequence profile: ordered drop presets,
clearance and initial attitude only. Robot path/attach/pickup/release execution
remains #140. Existing single-drop presets are uncalibrated model inputs.

Before implementation, Python3.13.5/PySide6 6.10.1/MuJoCo3.6.0 on Windows ran:
`.venv/Scripts/python.exe -m pytest -q tests/test_simulation_export.py tests/test_simulation_marker_export.py tests/test_simulation_scenarios.py`.
Result:53 passed in13.26s. This is scoped pre-change software evidence.

## Mockup and review

`mockups/simulation_mode_139/generate_mockups.py` creates review-only Qt
panels using the existing SimulationUI and marker editor. Production UI
is not modified by this script. Each FHD image is a1920x1080 logical review
board containing two original panels, not a full-screen production window.
At DPR1 the original PNG is1920x1080; at Qt process DPR1.25 it is2400x1350.
There is no raster enlargement. Standalone main/profile820x600 logical
checks have820x600/DPR1 and1025x750/DPR1.25 original pixels.

Commands: set QT_SCALE_FACTOR to1 or1.25 and run the script with --output
`docs/visualization/mockups/simulation_mode_139/render100` or `render125`.
Each run produced13 states with its evidence.json: default single, sequence,
physics, observation, returned settings, invalid, blocked, running, cancelled,
and standalone minimum main/profile windows for both modes.

One GPT-6.1 Sol/High read-only reviewer inspected the original renders.
Initial P2 findings: source mismatch, blocked-mode close gate, running controls,
missing marker editor entry/observation parameters, missing attitude/category
labels. Main corrected them; same-reviewer recheck found no remaining P0/P1
or presentation blockers. Static fixtures do not prove production behavior.
Human #139 mockup approval is pending; #138 approval is not reused.

The user's first-use comprehension question prompted a further correction:
`Settings…` is optional for Single drop, robot mode immediately explains
configuration/save-only use, marker editing is beside the marker selector, and
`Save settings…` differs from `Use in Simulation`. The same reviewer found the
workflow substantially clearer with no presentation blocker. The remaining Qt
ampersand mnemonic was changed to `Markers and noise`. Latest originals are
`final100/` and `final125/`; three final FHD images were shown in conversation.
The first combined render command exited1 after the DPR1 files were written;
separate DPR1.25 rerun completed13 states successfully. This is recorded as a
render invocation result, not native acceptance or production behavior.

## Spacing correction after user feedback

The user questioned excess whitespace. Main reduced the review-only sequence
table to its visible rows (up to8 before scrolling), moved sequence actions
directly underneath, fitted the main form to its actual content and fitted the
Settings panel to its active tab. The FHD board no longer stretches the main
panel to the entire1080-pixel height. Empty space outside panel borders is the
review canvas, not application content. Production UI is still unchanged.

Initial `spacing100/spacing125` clipped the single-drop preview because the
default QScrollArea size hint capped the preferred viewport. Those failed
inspection images are preserved. `spacing_verified100/spacing_verified125`
use the actual form-layout height and produced13 states each. Original FHD
PNG1920x1080/DPR1 and2400x1350/DPR1.25; standalone820x600 logical windows remain.
Structural assertions passed: no FHD scrolling for collapsed controls, complete
fixture table rows visible, and three primary buttons inside the small window.
Their evidence.json also records each actual panel's logical width/height.
The reviewer found one P3 remaining: forced820x600 Sequence settings separated
the content from the footer by270–300 logical pixels. Main capped the active
tab height, removed internal stretching and kept the footer next to the content.
The default Settings height now follows the active content. Forced820x600 is a
separate resize stress case with spare space below all actions.

`spacing_compact100/spacing_compact125` used the offscreen platform and rendered
unreadable fonts; these failed visual attempts remain preserved. Final Windows
Qt platform renders are `spacing_native_render100/spacing_native_render125`
(the folder name does not denote native input acceptance). Each invocation
produced13 states with original dimensions as above. Footer-gap assertions
also passed at both process scales. Same-reviewer presentation recheck closed
the P3: status-to-footer gap is7 logical pixels at both process scales and in
both modes; spare space below the actions does not separate the workflow.
No new clipping or button-access issue was found in FHD Sequence/Physics/
Markers and noise, invalid/cancelled/running images. This does not certify native
input, OS125 scaling, production behavior or human mockup approval.

Fresh commands: with QT_QPA_PLATFORM unset, set QT_SCALE_FACTOR to1 or1.25;
`.venv/Scripts/python.exe docs/visualization/mockups/simulation_mode_139/generate_mockups.py --output docs/visualization/mockups/simulation_mode_139/spacing_native_render100`
(use the125 output folder for1.25). Both exit0,13 states each. Only the
review-only script/document changed after HEAD91ab5ed; no production numerical
or UI implementation changed, so backend checks were not repeated for spacing.

## Rejected composition and restored preset preview

The user rejected the spacing correction: the dominant blank review board
remained, and Robot sequence had lost the existing box target image. The prior
review covered panel-internal gaps but missed these two user-visible defects;
its presentation conclusion is not acceptance of this rejected composition.
The old originals and review record remain preserved.

Main replaced the two-window canvas with one review-only simulation workspace:
controls on the left, optional Settings above the existing preview on the right.
Single drop starts with Settings closed. The existing OrientationPreviewWidget
is detached from the Scenario group's visibility before switching modes; it
remains visible in Robot sequence. Selecting the ordered drop updates its
existing preset target highlight and configured XYZ. No painter, physical
coordinate transform, marker editor or execution engine was redesigned.
Orange means the preset target, not a predicted impact after manual rotation.

Latest originals: `workspace_final150/` and `workspace_final125/`. The primary
window is1280x720 logical /1920x1080 actual /Qt process DPR1.5. The second is
1536x864 logical /1920x1080 actual /Qt process DPR1.25. These are fresh direct
Qt renders, not enlarged rasters and not proof of Windows OS125. Each command
uses the same script, QT_QPA_PLATFORM unset, the corresponding QT_SCALE_FACTOR
and --output directory; both exited0 with14 states. The added edge state shows
row2, faces3/4 and configuredXYZ0/35/0. Assertions also verify both-mode preview
visibility and panel bounds, complete fixture rows, single-mode fields/preset
unchanged after a mode round-trip, and820x600 primary-action bounds. The small
main-window stress fixture retains the preview in its scrolling form.

The initial `workspace150/` attempt is retained separately. The reviewer found
three P2 regressions in `workspace_final150/125`: compressed small-window
fields, enabled Settings while running, and one-way active-drop selection.
Main corrected them by attaching the small preview before first show and
preserving natural form minimum height, gating the whole busy Settings form,
and connecting selector-to-table as well as table-to-selector. Original
`workspace_corrected150/125` commands exited1 on the new minimum-height
assertion (preview attachment after show used a stale size hint); those partial
outputs are retained. Corrected `workspace_reviewed150/125` passed16 states.

Latest preserved originals are `workspace_verified150/125`,16 states each;
these add schema1/plan/source commit/dirty paths/script hash/UTC/command/input
and independent expectations to evidence.json. A separate small-window bottom
scroll image exposes the complete preview while the first image keeps numeric
and preset controls readable. Single/all mode round-trip, row-selection
synchronization and busy gate are software fixture checks. The same reviewer
closed all three P2 corrections on the reviewed originals/code and found no
additional P0/P1/P2 within the revised mockup scope. The narrow left column
still has spare space; the review does not claim all whitespace disappeared.
Verified output adds provenance without changing the reviewed composition.
Human approval and production binding remain pending; no native or
measured-trial acceptance is claimed.

## Shared layout and full current preset plans

The user rejected the enlarged single-drop preview and divergent mode layout.
The user also rejected the arbitrary two-step example as a representation of
ISTA work. These objections supersede the previously reviewed compositions.
Main retained one common Settings/table/preview arrangement for both modes;
the same Scenario form stays present. Single mode disables Robot model and
Add/Remove/Move, with its normal Run paths. Robot Scenario values show the
active configured step read-only, preserving the original single-control
snapshot for mode return. The preset browser is shared: Single runs only the
selected row, not all visible rows. The right preview stays at the same bounded
size in the two default Sequence views.

Current-plan fixtures reuse the existing Type G17 and Type H12 lists and
their existing clearance/orientation calculations. They are not asserted to
be the complete validated ISTA procedure. In particular, G17's hazard geometry
and Type H supported/tilt/rotation/release motions remain unavailable, as already
documented in `../simulation.md`. The table identifies these scope limits and
all Robot sequence execution remains blocked. There is no new scene engine or
automatic test approval. Type G/H category/standard eligibility and actual
experimental application remain separate decisions.

`ista_plan150/125` produced17 states each with exit0, including Type H. Original
FHD sizes remain1920x1080 and logical/DPR pairs1280x720/1.5 and1536x864/1.25.
The SciPy gimbal-lock warning from existing preset Euler conversion is retained
in the command result; it is a coordinate representation warning, not a native
acceptance or failed physical calculation. Both-mode preview, single-value
round-trip, selection sync, busy Settings gate and small-window controls/scroll
assertions passed. Preset values are reused for the layout fixture, not copied
as independent numerical expectations. Independent structural expectations
are G17/H12 counts, literal face/preset membership and unavailable status.
Earlier `consistent*` and `full_plan*` originals are retained. The reviewer
identified two P2 interaction defects: right-side mode state remained initial,
and category/input edits left stale preset rows. Main added current-source
refresh for mode/category/geometry/mass and pose changes, guarding both selection
connections by the current mode. Preset rows/items are reused; only relevant
source-key changes rebuild all values, and ordinary pose edits update affected
cells. The invalid fixture now selects its NaN row2 so the error is visible.

Latest originals are `ista_dynamic_final150/125`,17 states each/exit0. The
default fixture now exercises actual Single-to-Robot-to-Single switching,
row8 face3/910mm and restoration of the four original single values, Type G
to H12 and back, and explicit clearance123/XYZ-Z17 updates in the active table
row. These are independent UI expectations; no production trajectory was used
as a golden result. The review still found a reset-path P2: original controls
restored460/Z0 with signals blocked, while the table retained123/Z17. Those
`ista_dynamic_final*` failure images are preserved. Main emits a completed
configuration snapshot after the existing preset/reset method, then refreshes
the table; added post-reset literal table460/Z0 and preview(-98.68,0,0) checks.

Final originals `ista_reset_fixed150/125` each passed17 states/exit0. The same
reviewer closed both dynamic P2 findings, confirmed reset/preset-change values,
G/H names/counts and visible NaN row2, and found no additional P0/P1/P2 in the
corrected mockup scope. Narrow left-column whitespace remains. This review
does not certify actual user comprehension, native input, Windows OS125 or
production behavior. Production UI and human mockup approval remain pending.

## Native state

The computer-use skill initialized @oai/sky and identified exactly one
`Simulation — #139 mockup` window. Native accessibility listed the actual
default Edge3-4 preset,460mm clearance, mode and three run buttons. The
capture was not accepted as visual evidence, and activate_window failed
with `failed to activate captured window`. No native input acceptance is
claimed. Qt reported DPR1 without QT_SCALE_FACTOR. Registry LogPixels144
is insufficient to establish the target monitor's effective scaling;
actual Windows OS125 remains unexecuted. Prior #138 native records remain.
Fresh list_windows/get_window recovery retried activation once and produced
the same failure. No coordinates or stale element indexes were used afterward.

## Delivery state

`src/simulation/mode_profiles.py` implements isolated mode snapshots,
versioned sequence/physics/observation profiles, original settings snapshots,
source-bound edit history, guarded robot execution and atomic documents.
`tests/test_simulation_mode_profiles.py` ran21 tests in2.65s, all passed:
independent literal defaults/example18 author hash, mode switching and reload,
invalid/nonfinite/stale contracts, failure preservation and retry. Command:
`.venv/Scripts/python.exe -m pytest -q tests/test_simulation_mode_profiles.py --junitxml=tmp/issue139/profiles.xml`.
This is a core contract checkpoint, not final independent acceptance.

Backend metadata now follows direct export and marker producer through the
artifact whitelist, corrected/slice/proc serialization, raw/result readers and
Compare. Legacy callers without an explicit versioned snapshot stay unknown.
Full release/fault metadata is evaluation-only; public declarations contain
inputs/identities/actual clock/transforms. First-frame velocity capture preserves
existing derivative aliases and avoids per-sample metadata copies. Direct export
checks cancellation before atomic publication, preserving previous files.

Fresh producer/core checkpoint:93 passed in9.28s. Expanded metadata/storage/
Compare checkpoint:195 passed in45.16s. Commands/results are retained in
`tmp/issue139/core-export-fixed.xml` and `metadata-consumers-fixed.xml`.
`python -m src.simulation.mode_validation --output tmp/issue139/contracts-first`
passed literal rotated-COM/velocity/time, mode/save and truth-isolated observation
fixtures; its RunReport records dirty source/environment and independent bounds.
Original failures are preserved: `core-export.xml` (syntax parenthesis),
`metadata-first.xml` (shared transform-unit constants, fixed by deep copies), and
`metadata-consumers.xml` (a test treating the new optional field as universally
required, corrected without changing legacy eligibility). These are development
failures, distinct from corrected success; no baseline/tolerance was approved.

Interim independent backend audit identified one P1 and four P2 defects: nested
public truth keys, incomplete PUB05 cross-check, internal clock alteration,
indistinguishable private observation settings and unbound lower export inputs.
Main corrected all five and added regression mutations. Expanded backend suite:
260 passed in49.92s (`backend-review-fixed-3.xml`); fresh corrected RunReport:
`tmp/issue139/contracts-reviewed/RunReport.json`. Original correction failures
remain in `review-corrections.xml`, `review-corrections-fixed.xml`,
`backend-review-fixed.xml` and `backend-review-fixed-2.xml` (host schema fixture,
scalar Time conversion, missing fixture policy, and a test string value matching
the forbidden-key assertion). They are separate from the successful rerun.
The same reviewer closed findings1–4, then found two remaining P2 producer
bindings: quaternion-derived initial pose and geometry validation after mkdir.
Main corrected both and added sign-equivalence and same-path retry regressions.
Same-reviewer recheck found no additional P0/P1/P2 in the backend correction scope.
This is explicitly not production GUI/job/native/CI/final #139 acceptance.
Reviewer corrected an inaccurate default-layout dimension example; main verified
default18 dimensions200/120/80 and reproduced the actual mismatch with engine
300/180/80 against that layout.

Final affected producer checks:89 passed in17.16s
(`tmp/issue139/producer-binding-final.xml`); existing marker/corruption/artifact/
capture-regression/scene trial/workspace preservation:265 passed in177.28s
(`preservation.xml`). Timestamp array reuse check:70 passed in9.09s
(`export-array-reuse.xml`). Final backend literal RunReport passed at
`tmp/issue139/contracts-final-backend/RunReport.json`, including exact changed
source file hashes alongside commit/dirty paths. All reports are fresh scoped
software executions; overlapping counts are not summed as distinct tests.

Production UI binding/stale-worker lifecycle, remaining integration/CI, final
independent audit and publication are pending. The same reviewer is inspecting
the backend checkpoint read-only; no final acceptance is claimed. Production UI
waits for human mockup approval. See
`../analysis/reference/simulation_mode_contract.md` for the implemented contract.
#104 measured accuracy is separate;
no validated experimental dataset, trial approval, baseline or tolerance
promotion is claimed. #113 registration user feature remains excluded.
