# Simulation mode and output contracts (PUB06)

Last Reviewed: 2026-10-06

Plan Spec: `ISTA6A-PLAN-20261001-v1`. New envelopes use `schema_version: 1`.
This document describes the implemented backend contract. Production UI binding,
human mockup approval, final integration review and publication remain pending.

The same independent reviewer confirmed correction of all backend findings,
including quaternion/release binding and preflight geometry checks before output
directory creation. Final affected producer checks passed89; existing marker,
artifact, capture-regression and scene preservation checks passed265. These are
scoped software checks, not production UI/native or final #139 acceptance.

The latest review-only UI proposal uses one shared preset-browser/settings/
preview arrangement. It shows the existing G17 or H12 lists; `single_drop`
still has one selected planned drop regardless of visible browser row count.
Preset rows are not experimental repetitions `n`. The lists are current
uncalibrated configurations, not a verified complete ISTA procedure. G17 hazard
geometry and H supported/rotation/release behavior remain unimplemented.
No new engine or reinterpretation of existing output follows from this UI
proposal; production binding requires the user's #139 mockup approval.

## Settings and identity

`SimulationModeConfiguration` separates `mode` (`single_drop` or
`robot_sequence`) from sequence, physics and observation profiles. Each profile
declares a profile ID and a `synthetic_configuration` source ID. The sequence
contains ordered `PlannedDrop` entries with stable step ID, existing category and
preset ID, clearance in mm and fixed XYZ attitude in degrees. Attitude uses the
existing MuJoCo Z-up, extrinsic XYZ convention. Edited angles remain explicit
inputs; selecting a preset does not certify a physical test procedure.

`SimulationProfilesDocument` saves both configurations, selected mode, original
source snapshots and source-bound edit history. Switching modes preserves each
configuration. The canonical content hash covers the complete document. Reload
validates schema/plan, enums, source, finite values, marker identity and every
history transition. It rejects unsupported declarations and never upgrades
`approval_status: not_evaluated`. Saving uses a temporary file and atomic replace;
failure preserves an existing document and the primary error.

The marker section reuses PUB05 author profile, geometry, semantic and
correspondence identities. A saved editor document retains its applied profile
and pending draft/history. The selected marker profile must match that applied
profile. Display camera, zoom, translation and face offsets are absent from
physics and geometry identity. Example18/32 are public synthetic layouts.

Physics retains the existing cuboid contact inputs: kg, mm, friction,
`contact_damping_control` (the legacy `elasticity` input), and local COM offset.
Observation configuration separates seeded direct corner noise from marker
profile, explicit layout-box choice, marker seed and existing marker fault
settings. Direct corner noise never enters marker truth/corruption generation.
No observation model expansion or physical calibration is implied.

## Actual producer and storage routes

The current routes are `DataExporter.from_engine` → atomic `.proc` export and
`generate_marker_capture` → `history_to_trajectory` → existing corruption writer
→ staged observed/truth directory publication. With an explicit `mode_config`,
both validate the captured inputs against the effective engine/observation
settings. Marker export rejects robot mode before constructing an engine.
Existing callers without this new configuration retain their original output
contract; missing historical mode/profile/release semantics remain unknown.
Production UI passing the new snapshot is a pending integration step.

`SimulationMetadata` is the full direct/evaluation record: captured configuration
and hash, actual compiled timestep/gravity/inertia/contact settings, actual engine
clock, initial release pose and instantaneous velocities, full observation
configuration and the sealed public declaration. Direct results store it at
`Info / Simulation / MetadataJson`; marker generation stores it only in the
separate `observed.synthetic.json` evaluation manifest. Explicit layout-box use
retains `requested_source_configuration` alongside the effective engine geometry.

`SimulationSourceMetadata` is the safe declaration serialized as the scalar
artifact field `SimulationMetadataJson`. It carries mode, source kind/run ID,
generator/version, route and seed, declared input profiles and identities, actual
recording bounds/count/intervals, units and origin/frame conversion policy.
Marker fault windows/events, release positions/velocities, phase/contact labels
and truth file references are excluded. Its public observation declaration has
its own schema/plan envelope. Unknown extra fields, stale hashes, wrong units or
frames and nonfinite values block declared success.
All nested public objects use explicit field allowlists. Marker interpretation
hashes must match the artifact's complete PUB05 declaration. An opaque
`settings_hash` distinguishes the declared marker fault settings without exposing
their kind/window/axis/std; seeds remain separate evidence identity.

The field follows the existing artifact whitelist through observed CSV,
corrected-source save/reload, slice save/reload, result serialization, result
loader and Compare. Raw loader/parser validate a present declaration; result
loader checks a constant declaration and actual timestamps. Slices retain the
original source clock and may contain a subset within its bounds. Direct exports
must match the source recording count/endpoints. No resampling occurs.
The public clock also hashes the complete actual timestamp array. Full records
validate that identity and interval summary; slices keep source identity and
bounds. Raw Time parsing reuses the existing scalar parser to preserve original
floating-point decimals. Both lower opt-in export APIs bind metadata to actual
noise/profile/corruption/history/release inputs before publication.

## Coordinates, time and legacy aliases

The engine uses right-handed Z-up world coordinates. Export/analysis uses
right-handed Y-up with `A = [[1,0,0],[0,0,1],[0,-1,0]]`,
`p_output = A @ p_engine`, `R_output = A @ R_engine`. Local coordinates remain
unchanged. Units are mm, seconds, mm/s and rad/s.

For the existing centered cuboid, body origin equals geometric center. Its local
origin-to-geocenter offset is `[0,0,0]`; origin-to-COM is the configured local
offset. The policies are `p_point = p_origin + R @ offset` and
`v_point = v_origin + omega_world cross (R @ offset)`.
`Position / CoM` remains the historical body-origin/geocenter alias;
`Simulation / InertialCOM` remains the actual inertial COM. Existing position,
finite-interval derivative, initial NaN and quaternion/rotation columns are
unchanged. `ExportVersion` stays `simulation-pose-actual-time-v1`.

The recorder snapshots instantaneous free-joint velocity only in its first
frame. Translation is world-frame mm/s; angular velocity is body-frame rad/s and
is transformed by the recorded rotation to world rad/s. This follows the
[MuJoCo free-joint contract](https://github.com/google-deepmind/mujoco/blob/main/doc/overview.rst).
It does not reinterpret backward-interval exported velocity as release velocity.
Old histories without instantaneous velocity keep an explicit unavailable reason.

Times are actual `data.time`. Sample/frame identity is not seconds. The existing
0.002-s engine and four substeps produce approximately 0.008-s recording intervals
for a requested 120 FPS; output rates are never forced to match that request.

## Compare, source populations and follow-up

Real/legacy artifacts do not require the new optional field. Existing eligibility
checks remain; absence does not prove a particular mode or profile. A declared
contract compared with an absent contract is excluded from inferred equivalence.
Invalid declarations are rejected or reported as comparison exclusions.
Comparable settings use mode, sequence/physics/observation configuration and
transforms; run IDs, generator builds, actual recording length and random seeds
identify evidence rather than repeat settings. Marker author names/hashes are
handled by existing geometry/semantic/correspondence equivalence. Source-kind,
model, processing, reviewed scene/trial identity and observation resolution still
apply. UUIDs, files and settings do not manufacture trial repetition count `n`.

`robot_sequence` provides an editable configuration contract only. Its current
generator cannot declare successful output. `require_executable` gives the
specific missing attach/pickup/release engine reason. #140 can consume ordered
steps and physics/observation snapshots, add explicit phase/release records and
connect the producer at this guard. It must introduce a supported generator/
schema contract before robot output passes validation. Dynamic robots, IK,
attachment, pickup and multiple releases are outside PUB06; #143 observation
expansion and #104 measured calibration are separate.

## Verification checkpoint

Independent literal fixture: 200/120/80-mm box, +90° Z rotation, 250-mm clearance,
local COM `[3,-4,2]`, origin `[0,0,290]`, COM `[4,3,292]`, free-joint velocity
`[.1,.2,.3,1,2,3]`, world angular velocity `[-2,1,3]`, output origin `[0,290,0]`
and COM `[4,292,-3]`. Actual times are `[0,.008,.016]`. Software tolerances are
1e-12 mm, 1e-14 rad/s and 1e-15 s for these bounded fixtures; no physical
acceptance threshold or baseline is regenerated/approved.

Fresh backend consumer checkpoint: 195 tests passed. After interim independent
review, five defects in nested truth allowlists, marker identity, time identity,
opaque observation settings and lower producer binding were corrected; expanded
backend checks passed260 in49.92s. Immutable commands/results are recorded in
`tmp/issue139/metadata-consumers-fixed.xml` and `backend-review-fixed-3.xml`.
The separate CLI
`python -m src.simulation.mode_validation --output <new-directory>` writes a
versioned RunReport with source state, environment, inputs, expected/actual/
difference/tolerance and failure boundary. Earlier failing reports remain beside
corrected successes. Static/widget/native evidence and final independent
acceptance are separate; see [UI evidence](../../visualization/simulation_mode_139.md).
