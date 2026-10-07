# Robot sequence UI and delivery state — PUB07

Last Reviewed: 2026-10-07

Production SimulationUI now connects sequence Preview/Apply, scope, Run/Marker
CSV, actual progress and partial retention on the development branch. The user
instructed continuation of the editable automatic-plan/continuous-run workflow.
On2026-10-07 the user confirmed proceeding with the described virtual software
control conditions, then requested a clearer GUI. UI confirmation remains pending. Existing
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

## Readability correction after user review

The user found the central ID/phase/tolerance prose incomprehensible and asked
what `Fixed X/Y/Z` and `Scope` meant. Main replaced that text with an Execution
preview card: selected/total count, excluded count, time limit, motion and grip
face. `Details…` opens separate Drops, Actions and Conditions tabs bound to the
actual saved/generated plan. Drop numbers/preset names replace internal IDs;
excluded rows remain explicit, ordered actions retain actual targets and limits.
The centre does not expand a phase list for every selected drop.

Table headings now use `X/Y/Z rotation (°)` and `Motion`; the left controls and
target preview use the same rotation wording. A short visible hint specifies
scene X→Y→Z order and Z-up. Angles set orientation; they are neither position
coordinates nor axis locks. Motion labels show Free fall, Virtual floor tip or
unavailable handling. `Drops to run` replaces `Run scope`, and loaded subsets use
`Saved selection`. This is a presentation change; numeric values, fixed-axis
rotation convention, applicability, engine and export contracts are preserved.

`mockups/robot_sequence_140/clarity125/` retains11 actual widget renders including
all three optional detail tabs and a loaded6.5 mm grip-radius case. Earlier production/proposal images remain
historical evidence. `ui-clarity-first.xml` preserved37 passes and2 failures from
old display-text assertions; the updated assertions retain hazard/unavailability
checks. The corrected GUI suite and independent review are recorded below.

Corrected affected GUI integration passed49 checks in76.19 s. The independent
clarity audit inspected10 original widgets and found one P2: grip sphere radius
was removed from the centre without appearing in Details. Main restored the
actual-plan radius in Conditions, retained the short centre, and added a
nondefault6.5 mm binding assertion to the existing loaded-plan preservation
test. The bounded geometry/H/selection recheck passed4 in4.62 s and the new
11-state render passed. Actions uses `Planned duration (s)` to distinguish
scheduled/minimum time from actual runtime and additional timeout waits.
The same reviewer rechecked the source,4-pass XML and original default/custom
Conditions renders and closed the radius P2. No material P0/P1/P2 remains in
that bounded readability correction. Final human GUI confirmation is still open.

## Labelled summary after the second user review

The user still found the central prose unclear and asked whether it was a log
or a permanently sized area. The centre is a pre-run settings summary, replaced
on Preview, never an accumulating runtime log. It now separates four labelled
rows: 실행 항목, 동작, 잡는 면, 시간 제한. The limit explicitly says 적용 후 최대
to distinguish a draft budget from the currently applied value on the left.
The form sizes to its contents; invalid/stale previews hide the grip/time rows
and show only status and the next action. No fixed120-pixel log area remains.

The disputed headers are now X/Y/Z축 회전 (°) and 동작 종류. Motion cells use
자유낙하, 바닥 기울임 (가상), or 미지원. The short hint explains scene-axis order
and Z-up; grip faces are box-local, and the automatic-face choice is named in
Korean. Display labels are separate from serialized face keys; schema, angles,
physics and actual execution remain unchanged.

`summary_rows125` retains11 complete widget states and an additional direct
summary-widget PNG. The first FHD render in `production-summary-rows-first-125`
failed target-fit after the four-row layout; its report is preserved. Reducing
Sequence layout spacing from6 to3 restored the full target without changing
font, five visible table rows or minimum target height. The corrected11-state
render passed. Affected GUI49 passed82.51 s before that spacing correction;
the final layout4 checks passed4.47 s afterwards. These are separate overlapping
software checks, not native input/viewer acceptance.
The same reviewer inspected all12 originals and found a clipped planned-time
header in Actions. Content-sized columns restored the seconds unit and target
rotation; bounded detail recheck3 passed4.86 s and refreshed11 states passed.
The reviewer closed that P2 with no other material P0/P1/P2 in this scope.
