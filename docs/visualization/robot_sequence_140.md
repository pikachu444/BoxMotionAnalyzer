# Robot sequence UI and delivery state — PUB07

Last Reviewed: 2026-10-07

Production SimulationUI now connects sequence Preview/Apply, scope, Run/Marker
CSV, actual progress and partial retention on the development branch. The user
instructed continuation of the editable automatic-plan/continuous-run workflow.
Separate original UI and numerical approval questions remain pending. Existing
PUB06 workspace and Single drop behavior are preserved.

`mockups/robot_sequence_140/generate_mockups.py` subclasses the existing workspace
for presentation, disconnects production run actions and adds proposed handling,
attachment, run scope and Preview controls. It reuses the original contact-target
painter, left Mode/Settings and expanding right preview; it does not change
coordinates, physical identity, marker correction or backend inputs.

## Review and actual images

The first `proposal125`11-state originals remain locally preserved. A distinct
GPT-6.1 Sol/High read-only reviewer inspected all images and identified5 P2s:
H text on G rows, elapsed time beyond Duration, absent condition Preview,
16-step text above a17-row table, and absent narrow Settings controls.
Main corrected the script and produced `corrected125`13 states. The same
reviewer rechecked the original images/code and closed all5 presentation findings,
with no new P0/P1 or blocking presentation P2 in this bounded scope.

FHD original PNGs are1920×1080, logical1536×864, Qt process DPR1.25. The small
main and Settings fixtures are820×600 logical,1025×750 actual. The Windows Qt
platform is used. Process scaling is not actual Windows OS125 confirmation;
these are widget renders, not native desktop input/viewer acceptance.

Corrected selected-drop, condition-Preview and actual H12 images were shown
inline in conversation before requesting human approval. The async approval
question is pending. Prior #139 approval is not treated as new #140 approval.

The full G17/H12 browser is preserved. Entire plan and selected drop are distinct.
An unavailable G17 hazard blocks the entire plan; the edited16-row plan retains
an explicit omitted-test disclosure. The static running, failure/retry,
cancel/partial, invalid/applicability and previous-result labels are public UI
fixtures, not proof that those production worker actions are implemented.

The original proposal Preview used fixed prose. Production Preview now binds the
selected IDs, upward attachment face, handling/support template, actual edited
XYZ/orientation, pivot and proposed control conditions. Numeric fixtures and transition tolerances
remain separately proposed in
`../analysis/reference/robot_sequence_contract.md`.

## Production widgets and review

`mockups/robot_sequence_140/production125/` contains7 fresh actual production
widget PNGs and the original RunReport, captured at process DPR1.25. FHD target
preview and primary actions fit; narrow Settings uses scrolling to expose the
Open/Save/Use/Cancel footer. These are actual Qt widget renders, not desktop
input or viewer captures. Previous proposal originals are retained separately.

The same independent reviewer identified4 production P2s and closed all4 after
Main corrections: selected-drop Marker scalar binding, lost partial-save errors
on cancel/stale/viewer routes, inaccurate scope for loaded subsets, and H support
labelling. The recheck inspected current source, tests, all7 original production
PNGs and159-pass affected-integration XML. No material P0/P1/P2 remains in that
bounded GUI audit. It does not approve numeric conditions or native behavior.

15 new GUI tests execute actual two-release export/reload, saved subset1+8 with
exact selected IDs, selected-drop8 Marker dialog Generate/reload, source guards,
partial histories and failed-save status. The viewer bridge test uses headless
integration; actual viewer input remains unexecuted. Existing PUB06 production
render12-state preservation also passed. Evidence is under `tmp/issue140`.

## Remaining work

Current-source required PR/main CI, publication/merge and separate approval
questions remain outstanding in PR151. Native input/viewer/actual
OS125 remain unexecuted; previous #138/#139 failures are preserved. #104 measured
validation is separate and unavailable. #113 is excluded; #141–143 are not started.
