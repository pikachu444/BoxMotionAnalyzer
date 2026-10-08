# Initial conditions and limited contact fitting — PUB09

Last Reviewed: 2026-10-08

Plan Spec: `ISTA6A-PLAN-20261001-v1`. Implementation starts from refreshed
`origin/main@da4a91048692f0cc5a5769028f4299ac8c61583c`, including PR151/PUB07 and
PR153/PUB08. Issues134/142 and their comments were read at intake (zero comments).
This is an API/CLI feature. Existing single-drop defaults, robot state/clock and
export columns remain. GUI seed/profile controls, PUB10 camera/noise, launcher
localization, registration, deformation and measured calibration are excluded.

## Reproducible use

With application requirements, pytest and MuJoCo3.6.0 installed, run from the repo:

```powershell
python -m src.simulation.calibration_cli demo --output tmp/issue142/new-demo
python -m pytest -q tests/test_initial_conditions.py tests/test_contact_calibration.py
```

Every output must be a new directory. `demo` writes the public protocol rules
before reference generation, generates four actual synthetic references, freezes
their identities, runs timestep/solver diagnostics on both fit motions, searches
one normal damping-ratio grid, saves the selected profile, and evaluates two
independent holdout motions. Both holdouts also run fresh seeded engines, contact
save/reopen, direct PROC save/reopen, observed Raw generation, actual production
Parser/PipelineController processing, PROC reopen and truth mutation/deletion
controls. Ambiguous or missed production t2 is retained in comparison output.
Synthetic contact-reference holdout and production-observed holdout have separate
required denominators. `execution_status=pass` means the production path ran;
endpoint acceptance stays `needs_review`, including missed t1/t2.

Separate stages are executable using files created by the demo:

```powershell
python -m src.simulation.calibration_cli convergence --protocol tmp/issue142/new-demo/protocol.json --profile tmp/issue142/new-demo/base-profile.json --output tmp/issue142/new-convergence
python -m src.simulation.calibration_cli fit --protocol tmp/issue142/new-demo/protocol.json --profile tmp/issue142/new-demo/base-profile.json --references tmp/issue142/new-demo/fit-references.json --convergence tmp/issue142/new-convergence/convergence-input.json --output tmp/issue142/new-fit
python -m src.simulation.calibration_cli holdout --protocol tmp/issue142/new-demo/protocol.json --fit-result tmp/issue142/new-fit/fit-result.json --references tmp/issue142/new-demo/holdout-references.json --output tmp/issue142/new-holdout
python -m src.simulation.calibration_cli run --configuration tmp/issue142/new-demo/production/corner-holdout/engine/configuration.json --output tmp/issue142/new-seed-run
```

The equivalent API is `initial_condition`, `contact_profile`, `configured`,
`engine_from_config`, `freeze_protocol`, `convergence`, `fit`, `evaluate_holdout`.
`configured` captures the complete source settings and preserves legacy scalar
aliases. `fit` requires a complete convergence-report mapping. It accepts exactly
the fit reference cases; even one extra holdout case is an error. A missing
reference must have a frozen null identity and remains unavailable. Corrupt or
missing previously frozen references fail rather than becoming normal absence.
The new configuration JSON is intended for this CLI; current GUI controls do not
edit/display arbitrary seed fields or contact profiles.
Reopened references, case results, convergence, fit and holdout have reusable
strict validators. A fit result retains its base profile, fit references and
convergence evidence; it contains no holdout references. The reader reconstructs
the exact candidate profiles, required cases/endpoints, rules, summaries, scores
and ties before allowing holdout execution. Nested extra fields, empty/duplicate
populations and re-sealed favorable selections are rejected. Digests establish
declared content identity, not authentication of deliberately fabricated input.

## Seed, frame and clock

`InitialCondition` has schema1, plan_spec, seed ID, source kind/motion ID/original
artifact SHA256, authored content hash, position/quaternion/velocities, independent
velocity frames/reference points, units, seed mode and reference-clock offset.
Unsupported fields, versions, units, frames, nonfinite values and nonunit
quaternions are rejected. Authored q and -q retain different input identities
while generating the same physical attitude.
Numeric strings and booleans are rejected. Explicit empty source/inertia/margin
declarations are errors; defaults apply only when these arguments are omitted.

Position is explicitly `body_origin`, `geocenter` or `com`. For the only supported
sharp centered cuboid, body origin equals geocenter. Quaternion order is WXYZ,
right-handed active local-to-world; it transforms original body axes into MuJoCo
world Z-up. Linear velocity is mm/s at the selected origin/geocenter/COM point;
angular velocity is rad/s. Each can independently use `world` or `body` axes.
Body axes remain original geometric axes even with a rotated inertial frame.

For local COM offset c, canonical input uses:

```text
p_COM = p_origin + R*c
omega_world = R*omega_body
v_COM = v_origin + omega_world cross (R*c)
```

COM pose/velocity inputs subtract the appropriate lever arm. Original body
frames are pinned with compiler alignfree=false and freejoint align=false. The
joint's actual qpos/dof addresses receive origin world m/s and body rad/s;
independent point Jacobians verify their physical meaning. Seed application is
pre-build only. Applying it to a built engine or robot runner is rejected; robot
moving releases never reset state/clock. Existing height/quaternion calls keep
their old behavior. The legacy setter cannot overwrite an explicit seed;
choosing an explicit seed before build replaces the authored legacy start pose.

A new seeded engine starts at actual data.time=0. Reference time is a separate
declared relation `reference_time = engine_time + reference_time_s`; exports
retain actual engine times. The source identifies the snapshot/reference clock;
this exact synthetic offset is not a claim of measured synchronization accuracy.
`release` means this declared release starts at the seed. `precontact` has unknown
history before the seed. Its first visible contact is `visible_floor_impact`,
not a full-release first impact; global t1/t2 remain unavailable. Later visible
contact kinds and actual brackets remain available as diagnostics. Initial
support likewise cannot manufacture an airborne t1.

## Contact profile and actual application

`ContactParameterProfile` is explicit opt-in, schema1 with version/digest/source,
and always `calibration_status=uncalibrated`, `approval=proposed`. It supports
primitive cuboid/plane, mass kg, local COM mm, positive principal inertia at COM
in kg*m² and principal-to-original-body WXYZ orientation. Positive moments and
all triangle inequalities are required. Full tensors, origin moments, repair by
clamping, rounded/deformable geometry and unsupported solver formats are rejected.
The legacy homogeneous cuboid moments applied at an offset COM are separately
named as an assumption; they are not a measured mass distribution. Valid inertia
does not establish that the actual package's mass is confined to this cuboid.

Normal inputs are MuJoCo positive-format solref `[timeconst_s, damping_ratio]`
and solimp. Damping ratio is not restitution and these controls are not named
material SI stiffness/damping. The supported integrator/solver are Euler/Newton;
timestep, iterations and tolerance are explicit. Profiles enforce
timeconst≥2*timestep, and convergence requires it against the largest timestep,
so reference-safety clamping cannot silently change fixed physical conditions.
Cone, enable/disable flags, gravity, geometry type/size, actual COM/inertia/frame,
solver and each geom's requested settings are checked against compiled values.

Sliding friction is dimensionless. Torsional and rolling coefficients are in
metres. condim3 includes sliding, condim4 adds torsion, condim6 adds rolling.
Fitting an inactive torsional/rolling family is rejected. Floor and box receive
identical friction/solref/solimp/condim and explicit equal priority/solmix. Their
activation margins are independently declared in mm and **add**: box5/floor0
preserves the previous effective5mm. Margin does not represent corner curvature
or physical deformation. Actual contact records retain dim, five friction
coefficients, solref/solimp and effective inclusion margin. These values must
match the declared combination, alongside existing contact point/wrench checks.

The conventions were checked against official
[freejoint](https://mujoco.readthedocs.io/en/3.6.0/XMLreference.html#body-freejoint),
[contact parameters](https://mujoco.readthedocs.io/en/3.6.0/modeling.html#contact-parameters),
and [solver parameters](https://mujoco.readthedocs.io/en/3.6.0/modeling.html#solver-parameters),
using independent MJCF probes preserved under `tmp/issue142/advisor`.

## Frozen evaluation and fitting

`EvaluationProtocol` fixes version/content hash, required cases and motion groups,
fit/holdout split, source-bound seed/configuration and reference identities,
eligible/required endpoints, policy/version/hash and separate user approval scope,
half-open event window, one t1 alignment/chronological t2, endpoint modality,
units, objective scaling/weight, tolerance and label uncertainty, one parameter
family, candidate bounds/grid, exact execution budget/stopping, tie rule, missing
penalty and aggregation. Event kind approval is inherited from PUB08; numeric
thresholds, these diagnostic tolerances/ranges, label uncertainty and baseline
promotion remain proposed. A changed protocol has a new digest; author a new
version for changed evaluation rules and retain prior files/results. Files are
never overwritten by the CLI. Proposed diagnostics require no default promotion.

Variants of the same original motion use its original source motion ID and one
motion_group. Reprocessing/seed/observation variants cannot split that ID or group
between fit and holdout. Distinct original motions may share a capture artifact;
artifact count alone does not establish independent motion count. The API cannot
discover deliberately falsified original motion identities; authors must preserve
the real original-motion mapping. Altered seed/mass/COM/inertia approach identity
blocks contact fitting, rather than letting contact parameters compensate for it.

Each candidate changes exactly one active parameter family; remaining physical
input is fixed. The first implementation searches normal damping ratio, with
sliding/torsional/rolling single-family APIs available under applicability guards.
The objective preserves every required fit endpoint and penalizes unavailable,
ambiguous, failed, out-of-window or not-detected values. Selection first minimizes
missing count, then the fixed weighted objective. Every candidate runs; there is
no holdout-based early stop. Parameter truth stays in reference-generation
evidence and is absent from the fitter's reference payload. Reference records
contain endpoint values/status/units and source hashes only.

Selected profile identity is saved before holdout. Multiple tied profiles are
ambiguous; missing required values make identification unavailable. Unique on the
grid is not a uniquely identified physical material property. Reference generated
by the same simulator establishes self-consistency only. The separate holdout
reports never choose candidates or change the objective/t2/endpoint/window.

Protocol `pub09-synthetic-protocol-v2` fixes observed holdout t1/t2 alongside
synthetic endpoints. Endpoints currently supported are chronological Δt12 s, COM
rebound rise mm between the designated t1/t2 when t2 is a rebound recontact,
final origin X mm and final rotation angle deg. If the earliest t2 is a new-feature
impact, rebound rise stays unavailable; it never selects a later rebound.
The draft v1 files, which reported interval COM rise for either t2 kind, are
retained under `demo-current`; they are not final-source acceptance evidence.
Final endpoints use the actual integration sample at the declared window boundary;
events use the existing half-open window. Missing event ordinals do not create
zero timing/rise. Actual brackets, sample times and topology accompany results.
The production observed comparison reuses PUB08 ordered matching and one t1 shift;
actual ambiguity/missed rebound stays visible and is not a fitter success claim.

Convergence runs both fit cases at2/1/0.5ms and Newton10/100iterations before
fitting, preserving physical settings/windows and native timestamps. Changes
compare timesteps at fixed iterations and iterations at fixed timestep. Endpoint
values/statuses, event brackets and topology are retained separately; no forced
output resampling or assumed monotonic contact convergence is used. This suite
records sensitivity, not approved convergence or measured package accuracy.

## Storage, denominator and evidence boundaries

Optional `initial_condition`/`contact_profile` configuration fields are validated
without disabling old guards. Advanced single-drop public metadata uses
`pub09-explicit-state-v1`; legacy PUB06/PUB07 generators remain supported. Public
seed projection contains only identity, mode and clock/prehistory declaration;
pose/velocity samples and full seed inputs remain evaluation-only. Contact input
settings remain public declarations. Actual compiled profile, initial state,
source and clock bind export/reopen. Differences exclude incompatible Compare
settings; they do not infer equivalence with an absent declaration. Existing
Y-up transform and finite-interval derivative/initial-NaN export policy remain.

Reports preserve required/evaluable/pass/ambiguous/unavailable/failed plus
not_detected/out_of_window/reported counts and both required/evaluable denominators.
`within_proposed_tolerance` is diagnostic only; `pass` is0 until numeric approval.
Partial coverage cannot become whole pass. Numerical status is needs_review,
physical status pending, calibration uncalibrated. Missing measured references
are unavailable, not automatically replaced by synthetic records. Finite JSON is
required. Functional exceptions, source corruption and missing frozen evidence
write failure RunReports and return nonzero.
Non-demo failures retain the protocol's planned engine count (fit budget,
convergence grid, holdout population, or one seed run). An unreadable protocol
leaves the expected count unavailable with a reason rather than reporting zero.

RunReport records commit/dirty/source hashes before execution, completion hashes,
UTC/KST, environment, exact command, schema/protocol/profile/reference identities,
expected/actual/differences, fresh/reused/unexecuted coverage and exception traces.
Uninstrumented memory/optimizer counts and native/measured work are explicitly
unavailable/unexecuted. A run during source edits is not final-source evidence.
Original `demo-first` reference-field collision and `seed-first.xml` JSON tuple/list
assertion failure are retained separately from corrected results. Local execution,
independent review and final-source hosted CI publication are indexed separately
in `contact_calibration_evidence_v1.json` after they complete.
The original independent review found five defects: re-sealed fit population
omission, weak nested reference validation, missing observed denominators, failed
CLI budget shrinkage, and explicit empty declarations replaced by defaults.
Original reproduction records are under `tmp/issue142/reviewer-original`;
post-review runs and review records use separate paths. No detector thresholds or
contact inputs were changed to improve the observed result.

The post-review local demo completed29/29 fresh engines,0reused/failed/unexecuted,
with unchanged product source hashes in582.96s. It recovered damping ratio0.2
on the authored synthetic grid only. Synthetic holdout has4required/4evaluable;
production-observed holdout has4required/0evaluable/4not_detected. Both have0passes
and whole_protocol_pass=false. Ballistic COM discrepancy at0.2s decreases from
1.958mm to0.979mm to0.489mm for2/1/0.5ms; contact endpoints need not converge
monotonically.408 affected local checks passed. These numbers are local proposed
diagnostics; final-source hosted CI is a separate publication gate.
Independent correction review is PASS: all five original findings closed,
220 independent affected tests passed, all26 native contact/evaluation payloads
matched their hashes and re-extracted endpoints, both151-row Raw/PROC/metadata
paths matched, and a separate valid current CLI holdout ran2fresh engines.
Original attacks were re-applied to the new valid payload and rejected before
holdout execution. Requested advisor/reviewer dispatch settings are recorded in
the evidence index; actual model routing is unverified because authoritative
runtime introspection is unavailable. Final CI and merge status is tracked in
#142 and its linked PR.

Before merge, a final data-integrity check reproduced stale nested profile
acceptance through Python's boolean/number equality. Each selected/candidate
profile is now validated directly, compiled declarations reject numeric strings
and booleans, and derived endpoint/summary/convergence/holdout comparisons keep
booleans distinct from numbers while allowing equivalent numeric int/float
values. The original attacks and419 final affected checks are retained separately.
The first-source `8bc1faa` hosted CI passed1,521 tests and29 fresh PUB09 engines;
that run is supporting prior evidence. Final guard source requires its own full
hosted CI before merge. Physical inputs, protocol v2 and endpoint rules are unchanged.
Final independent delta review is PASS: all three integrity findings and the
original five are closed,95 current affected checks and2 fresh holdout engines
passed, and the original contacts matched endpoint re-extraction. No material
P0/P1/P2 remains in the bounded review scope. These records supplement the earlier
220-check independent review; counts overlap and are not a unique-test total.
