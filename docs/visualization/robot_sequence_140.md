# Robot sequence UI proposal and delivery state — PUB07

Last Reviewed: 2026-10-07

The new UI is review-only. Human approval is pending, and production SimulationUI
still uses the approved PUB06 workspace and execution-button behavior.

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

The reviewer explicitly notes that Preview text is currently fixed proposal
prose: selection-to-profile/face/support conditions must be bound and audited
in production after human approval. Numeric fixtures and transition tolerances
remain separately proposed in
`../analysis/reference/robot_sequence_contract.md`.

## Remaining work

Production UI/profile Preview/Apply, execution selection/progress and partial
retention integration, stale-worker/retry checks, final independent audit,
required PR/main CI and merge remain outstanding. Native input/viewer/actual
OS125 remain unexecuted; previous #138/#139 failures are preserved. #104 measured
validation is separate and unavailable. #113 is excluded; #141–143 are not started.
