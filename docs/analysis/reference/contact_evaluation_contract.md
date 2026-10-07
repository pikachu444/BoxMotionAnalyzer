# First and subsequent floor-impact evaluation — PUB08

Last Reviewed: 2026-10-08

Plan Spec: `ISTA6A-PLAN-20261001-v1`. Development starts at current
`origin/main@78b6c797916f421530327b061ced098fc30060d8`, including merged PUB07
PR #151. Issues #142, #143 and launcher-language issue #152 are excluded.
The parent #134 and #141 had no comments at the initial read. This work adds a
read-only evaluator and CLI; the existing single-drop UI, defaults and exports
and #120 whole-record/local-event semantics stay intact.

## Scope and approval

`t1` means the first qualifying detached floor impact in the selected release;
`t2` means the first subsequent qualifying impact in that same release. A new
corner/edge/face strike while prior corners stay loaded and a rebound recontact
both qualify. Pickup/attachment ends the release. An initially supported Type H
box has no invented t1 onset. Attached floor contact is retained separately;
gripper-only contact is ineligible. The evaluator does not certify ISTA or
measure package peak load.

The new `pub08-synthetic-v1` threshold policy is **proposed**. The user's #140 operational
approval does not approve these thresholds. On 2026-10-08, after a plain
explanation, the user explicitly chose both new-feature and rebound impact
as t2 candidates, choosing the first one in time. The separate synthetic numeric
question remains pending. Literal scope is in `contact_event_141_confirmation.json`.
Numerical accuracy tolerances and
baseline promotion are separate, with no automatic pass or baseline creation.

`contact_policy.frozen_protocol()` defines public expectations independently of
evaluator output, before any execution. The CLI writes policy/protocol and their
digests before generation or processing. Thresholds have not been tuned to
actual results. Hand-specified logic controls are distinct from actual MuJoCo
trajectories and from unavailable measured data.

| Proposed quantity | Value and interpretation |
| --- | --- |
| Corner load ON/OFF | 0.05/0.01 N; individual floor points mapped to material corners |
| Closing speed | At least 50 mm/s at the preceding material-corner sample |
| Corner mapping | Maximum body-local distance 0.5 mm |
| Rearm | No load and corner clearance at least 0.5 mm for 20 ms; latched until onset |
| Rebound rearm | Every corner clear and no floor load for 20 ms |
| Onset resolution | 4 ms; conflicting independently armed nearby onsets retained ambiguous |
| Ordered correspondence | Single t1 offset, chronological 20 ms gate; multiple counterparts ambiguous |
| Designated analysis t2 | Second eligible existing stable contact-set run; physical kind unverified |

## Actual collection and coordinate contract

`MuJoCoEngine.enable_contact_recording(source_identity)` is opt-in. The existing
engine hooks capture every actual 2 ms integration step. `ContactRecorder`
copies `MjData` and forwards only that copy, including mocap/constraints and
solver state. It never writes live qpos/qvel/clock or feeds truth to analysis.
The PUB07 runner remains one model/state/clock. No extra contact fields are
inserted into the existing history/export or public observation metadata.

`ContactRecording` uses schema_version 1, plan_spec and source/model identities,
MuJoCo 3.6.0, actual timestep and execution status. Required samples contain
origin, COM, local-to-world rotation, world velocities, all eight world material
corners/velocities, actual attachment state, and individual contacts. World is
MuJoCo Z-up; local is the original box-body origin, not contact or COM origin.
Positions are mm, linear velocities mm/s, angular velocities rad/s, time s,
force N and torque N*m. Unsupported versions, clock gaps, wrong frames/units,
nonfinite data, inconsistent corners/COM/velocities, source changes and contact
point/wrench contradictions are errors. The evaluator preserves null/status.

Each contact retains geom/body IDs and names, role, distance, inclusion margin,
world midpoint, world and body-local box surface point, world frame rows,
contact wrench on geom2, signed box world force/torque, closing speed and
constraint address. The normal points geom1 to geom2. For box-side sign `s`,
box surface is `midpoint + s * distance/2 * normal`. World force on box is
`s * frame.T @ contact_force`. Stored torque is at the **midpoint**, not the
projected surface. Moving its reference requires the cross-product moment arm.
Point Jacobians and solver forces refer to the same forwarded state/time;
pre-onset classification uses the preceding material corner velocity.

These meanings were checked against [official contact types](https://mujoco.readthedocs.io/en/stable/APIreference/APItypes.html#mjcontact),
[contact force API](https://mujoco.readthedocs.io/en/stable/APIreference/APIfunctions.html#mj-contactforce),
[MuJoCo 3.6 simulation loop](https://mujoco.readthedocs.io/en/3.6.0/programming/simulation.html#simulation-loop)
and [3.6 plane-box source](https://raw.githubusercontent.com/google-deepmind/mujoco/3.6.0/src/engine/engine_collision_primitive.c).
Independent advisor scripts/reports are retained under `tmp/issue141/advisor`.
Their transform/wrench and 500-step data-copy probes verify software semantics,
not approved numerical tolerances or measured package behavior.

## Events and comparison

A recorded contact episode is a continuous interval containing floor contact
points, including inactive/soft-margin points; it is not an impact count.
Material-corner load onsets use ON/OFF hysteresis. A fast armed onset can be a
first impact, new feature impact or rebound recontact. Slow complete approach
evidence yields support_transition. No rearm yields chatter. Contradictory
motion or unmappable loaded points remain ambiguous. An edge requires adjacent
corners; a face requires four coplanar face corners. Diagonal pairs/partial
support are not promoted to complete features.

Force onset uses `(previous sample, onset sample]`. Geometric floor crossing
uses the actual corner height zero crossing and its own bracket. The difference
is retained when evaluable; no crossing remains unavailable, including a box
resting above the geometric plane due to margin. Known designated events outside
the half-open evaluation window are out_of_window. Incomplete recording cannot
establish absence; intact missing modality is unavailable, corrupt data or a
calculation exception is failed. An absent qualifying designated t2 is
not_detected. Initial support has unavailable t1 prehistory.

`observed_events` exposes the existing postprocessor's whole-record contact mask
and runs of at least two observations. It leaves t1-minus separate from run
onset and never pretends these runs are independently verified impacts. Only
observed CSV and explicitly declared geometry/settings enter production
Parser/PipelineController. No contact recording or truth label is an input.
All result samples use the actual Raw clock; analysis world Y-up is transformed
once to MuJoCo world for comparison.

If the first legacy run and existing t1-minus refer to different events, the
adapter marks the first run ambiguous. It cannot skip that run to find a later
favorable anchor. Actual runs require a separate `ContactObservationPair`
binding the Raw SHA-256, recording/source identities and policy digest. This
pair is checked by the comparator and is never passed to the observed analyzer.

`compare_events` aligns the first event once and matches subsequent events in
time order. It retains unmatched truth, extra detector events, ambiguity and
out-of-window events. It cannot replace designated analysis t2 with a later
better-fitting run. Coverage distinguishes first_only from first_and_subsequent;
valid means a value/correspondence is available, not approved physical accuracy.
Both matched Δt12 and declared endpoint interval differences are saved, so a
late unmatched second event does not hide timing error. Pre-event pose/velocity
comparisons retain both actual sample times. Numerical acceptance stays
needs_review and measured accuracy is unavailable.

## Execution and evidence

Run from the repository using an environment with requirements and MuJoCo 3.6.0:

```powershell
python -m pytest -q tests/test_contact_evaluation.py --junitxml=tmp/issue141/contacts.xml
python -m src.simulation.contact_validation --output tmp/issue141/fresh-contacts
```

Every output directory must be new. Original failures are preserved, not
overwritten by retries. The CLI executes nine frozen logic controls, actual
face/corner/rebound physics, and the real PUB07 two-release producer with saved
contacts, observed CSV, full Raw processing, observed scene slicing/reopening,
processed result reopening, and truth-label/deletion controls. RunReport stores
commit/dirty and source hashes, command, environment, input/protocol identity,
expected/actual, fresh/reused coverage, failure traceback and reasons for
unexecuted native/measured work. Required functional failures return nonzero.
Hosted CI includes this tier and preserves its evidence.

At the first implementation checkpoint, 27 public/contract/order/preservation
checks passed. The first full production attempt retained nine successful logic
controls and then failed because the harness omitted production slice bounds;
`production-first/RunReport.json` contains the original traceback and source
identity. The correction supplies the actual observed interval. That first
failure is not replaced by a successful later report. Final execution, independent
review and publication evidence will be appended after they complete.

The second production attempt (`production-retry1`) failed on a 32-row observed
slice because the existing production analyzer requires at least 50 records.
The correction uses the existing 50-row padding contract, producing 132/108-row
scene slices; it does not reduce the analyzer's minimum. A redundant run begun
before that finding was interrupted and retained as `production-current` with
`RunReport-aborted.json`, not counted as a completed run.

| Evidence under `tmp/issue141` | Result and scope |
| --- | --- |
| `production-padding-fixed/RunReport.json` | 13 fresh functional cases, zero reused, 763.16 s; nine logical controls, three actual physics paths, and actual two-release producer/whole Raw/observed scenes/save/reopen/truth isolation |
| `comparison-current/RunReport.json` | Six bounded current-comparator replays, zero new physics/optimizer calls; retained Raw/proc/recording identities checked |
| `affected-expanded.xml` | 168 passed: event and related robot/export/metadata preservation checks at that source checkpoint |
| `observer-preservation.xml` | 76 passed, one existing skipped check; whole-record/local-event preservation |
| `raw-pairing.xml` | 36 passed: latest source pairing and ambiguous-anchor guards at that checkpoint |

The full production run loaded an earlier comparator snapshot, identified by
source hashes in its report. The bounded replay preserves that original report
and records the changed comparison: whole-record two-release t1 changes from a
false correspondence to ambiguous/no-first-match. Both observed scene results
remain first-only. The actual corner run has an ambiguous t2 correspondence;
the actual elastic rebound is not detected by the existing observer. These are
reported diagnostic outcomes, not detector-accuracy passes. Final hosted CI must
run the complete tier fresh at the published source; earlier successes cannot
substitute for that check. Independent review and publication are pending.
