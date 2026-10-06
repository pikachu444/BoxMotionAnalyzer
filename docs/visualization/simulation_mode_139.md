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
