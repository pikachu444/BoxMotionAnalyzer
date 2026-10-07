# Dynamic gripper sequence implementation — PUB07

Last Reviewed: 2026-10-07

Plan Spec: `ISTA6A-PLAN-20261001-v1`. Branch `issue140-dynamic-robot-sequence`,
base `2e3dea4b97fdb274501adf58ef6ae3744e3a0895`. Backend checkpoint `9c3e263`
is followed by production GUI binding on this branch. The user instructed
continuation of the editable preset-to-continuous-run workflow. Separate new
UI confirmation remains pending after the user's readability correction request.
On2026-10-07 the user confirmed the described virtual software control conditions
(attachment distance/alignment/speed/spin, tracking/rest limits, dwell,
timeout/retries). Additional numerical diagnostic bounds remain proposed; no
baseline promotion or experimental accuracy was authorized.
The literal confirmation scope is retained in
`robot_sequence_140_confirmation.json`; the later GUI readability request is
not treated as UI approval. Prior diagnostic RunReports remain unchanged.
No full issue completion, native acceptance, experimental accuracy, new baseline,
trial approval, or migration is claimed.

## Public fixtures proposed for review

All dimensions, masses, Type labels and actions below are virtual inputs. They
are not inferred from filenames, screen sizes, or measured experiments. The
existing preset ID is a planned-drop reference, not certification that a virtual
handling template reproduces that ISTA apparatus or procedure.

| Case | Geometry mm; mass kg; COM mm | Handling and independent expectations |
| --- | --- | --- |
| A | 200/120/80; 1; 0/0/0 | Upward accessible face, 100 mm nominal clearance, two releases, second orientation Z30°, pickup between releases, exactly one engine build and strictly increasing actual time |
| A-spin | 200/120/80; 1; 3/-4/2 | Release halfway through 0.8 s translation toward 80/30/190 mm and XYZ15/10/60°. Actual nonzero linear/angular velocity, exact same-step state preservation; COM velocity uses `v_origin + omega_world × R offset` |
| B | 300/180/90; 2; 0/0/0 | One virtual airborne release; inertia independently calculated from cuboid dimensions/mass |
| C | 120/100/60; 0.5; 0/0/0 | A distinct small cuboid and inertia, one airborne release |
| H | 200/120/80; 1; 0/0/0 | Local edge point +X100/Z−40 mm, world edge from actual supported initial state, Y15° target; actual floor force before release, actual rotation over10°. No air-drop clearance is substituted for supported rotation |
| held | 200/120/80; 1; 0/0/0 | Attach and hold without release; explicitly partial, no automatic free-fall/trial approval |

Optional floor translation and a180° flip are separate dynamic phases. A selected
subset retains the complete planned list and explicit omitted step IDs. The G17
hazard block remains unavailable. External conveyance is not silently added to
the robot endpoint path. Unknown Type remains unknown; repeated samples of A do
not add geometry/family coverage or experimental repetition `n`.

## Proposed operational and numerical bounds

| Quantity | Proposed bound | Purpose and impact |
| --- | --- | --- |
| Attachment point distance | 2 mm maximum | Reject remote attachment; compare sphere endpoint and actual box face point |
| Attachment normal mismatch | 5° maximum | Reject misaligned local face/tool normals |
| Endpoint relative speed / relative spin | 30 mm/s / 0.2 rad/s maximum | Avoid attaching moving/spinning bodies without a bounded transition |
| Dynamic target position / attitude | 5 mm / 3° maximum | Measure gripper and actual attached-box tracking; scheduled trajectory completion alone does not pass |
| Rest linear/angular speed | 15 mm/s / 0.15 rad/s maximum | Phase transition with 0.15 s continuous dwell, never whole-run rest exit |
| Phase timeout / additional attempts | 3 s / 1 retry | Failure is reported with partial history; retries remeasure actual relative transform |
| Supported-motion penetration | 3 mm maximum | Applies to supported orient/floor move only. Dynamic impact soft penetration is recorded, not silently projected or accepted as measured contact accuracy |
| Runtime weld state toggle | exact same time/qpos/qvel and body snapshots | Software invariant; actual next integration reaction is separately recorded |
| Measured weld closure | 1e−12 m / 1e−12 rad | Bounded double-precision diagnostic, not suction accuracy |
| Frame/COM position transform | 1e−10 mm | Bounded arithmetic diagnostic; body origin is not COM |
| Finite-step COM displacement derivative | 25 mm/s absolute | Next 2 ms step includes gravity19.62 mm/s plus finite-step rotational error; this does not redefine instantaneous export aliases |

Default synthetic gripper mass is max(1 kg, box mass); its explicit diagonal
inertia uses the same cuboid-size formula at that gripper mass rather than the
tiny sphere's inferred inertia. Sphere radius5 mm, drive/attach time constants
0.01/0.02 s, damping ratio1, weld torque scale1 m, contact margin0 mm, timestep
0.002 s, solver iterations100. These opt-in settings leave single-drop contact
settings unchanged. They model ideal actuation/attachment, not physical suction
capacity, leak, damage, robot-arm accuracy, or calibrated package inertia.

The operational control bounds listed in the confirmation question were
confirmed for virtual software testing. Other numerical test bounds remain
proposed until review. Diagnostic test success does not approve them. No regression
baseline is regenerated. Experimental acceptance stays unavailable in #104.

## Actual implementation boundary

`robot_profiles.py` adds an explicit `RobotExecutionPlan` and phase envelopes.
The PUB06 sequence profile may carry it; existing config-only documents still
round-trip and remain blocked at `require_executable`. Geometry, physics and
planned-step binding changes invalidate applicability. Source/history documents
retain prior settings rather than rewriting previous numbers or approvals.

`RobotSequenceEngine` subclasses the single engine and adds a dynamic freejoint
gripper and a noncolliding mocap target. The target drive weld is always active;
the box attachment weld is toggled at runtime. Only target poses change during
motion. Box qpos/qvel/time are never assigned by the runner. Initial attach and
pickup measure the current face anchor and relative origin/rotation, then write
body-based weld anchor/quaternion fields. Endpoint velocities use world origin
Jacobians plus angular lever arms. Freejoint frame alignment is explicitly off.

The runner owns complete/partial/cancelled/time-limit/failure outcomes. It uses
one engine build and actual clock throughout, including settle/hold and later
pickup. Partial histories and structured evidence are retained on failure;
`retain_partial` can publish an incomplete direct capture to a unique side file
without replacing a previous complete result. Public status stays incomplete.
Production GUI workers retain failure/cancel/time-limit history to unique side
files, preserve previous results, and expose partial-save errors, including stale
jobs and the viewer bridge. A failed Marker CSV run cannot publish completed
observations. Only the matching finished worker can adopt a completed result.
Interrupted attach/release boundaries explicitly retain an unavailable next
integration reaction with its reason. They can publish an incomplete side file;
only completed transitions may claim a recorded reaction. Build/run/export bind
the effective plan to the immutable captured source, and the runner also checks
that binding at every integration checkpoint.
Viewer cancellation/native behavior is unverified. Smooth gripper retraction
after release changes the target only, with no box reset.

Floor–box and gripper–box contacts are filtered by unordered geom pairs and force.
The recorded legacy contact fields mean floor contact in this new runner;
gripper contact is separately recorded. Existing single-drop recorder is intact.

## Producer, consumer and truth separation

The direct exporter and Marker CSV producer reuse existing actual-time trajectory,
corruption and atomic publication code. Marker geometry must match an explicitly
bound execution plan; changing to layout dimensions does not silently adapt a
robot plan. Existing marker example18/32/custom semantic identities remain intact.

Robot public declarations use `pub07-dynamic-gripper-v1`, retain configured
profiles/source/seed/clock/frame/transforms, and add normal `execution_status`.
Measured phase/toggle/pose/v/omega/relative-transform truth stays in full evaluation
metadata, never observed Raw or production analysis metadata. The initial robot
record is supported, so the legacy initial `release_state` explicitly says
unavailable; actual release states live in separate sequence evidence.

The existing public artifact metadata whitelist transports the declaration
through Raw/storage/results/Compare; single-drop version and numeric aliases
remain unchanged. Unsupported versions, missing source, stale applicability,
invalid enums/units/time, nonfinite values and unexpected fields are rejected.
No observation-model expansion, resampling, threshold change or trial automation
is introduced. Production UI binding is pending human mockup approval.

## Development evidence

### Production GUI binding and current verification

Sequence Settings binds handling, upward attachment face, and entire/selected
scope to an explicit condition Preview. Planned XYZ/orientation/order, physics,
and markers remain editable. Apply requires a current applicable Preview; a
loaded custom plan retains its exact phases and numerical settings. Loaded
multi-step subsets display `Captured selection` with their saved IDs. Browsing
another row does not silently change that subset. Expanding scope requires a new
Preview. G17 hazard remains blocked; H uses an explicitly virtual supported
template, labelled `Virtual support; ISTA unverified`.
The subsequent user readability correction replaces central debug prose with
a compact count/motion/grip/time card and an optional structured Details dialog.
Rotation and Motion headings replace Fixed XYZ and Scope. Virtual H/unavailable
status remains visible; all saved IDs, phase targets and limits remain bound.

Run and Marker CSV use the actual one-state runner. Visible robot time budget
can reach3600 s; individual phases retain60 s limits and Single drop retains
its60 s cap. New generated plans expose a conservative budget from their phase
durations/timeouts/retries; loaded plans retain the requested budget. Progress
uses actual engine time and the executing selected phase. Marker dialog scalar
identity comes from the frozen producer configuration, not a browsed table row.

`ui-final-affected-integration.xml` records159 passing checks in139.98 s, including
15 new production-GUI tests,53 backend tests and existing GUI/profile/metadata
preservation. The GUI tests execute two-release export/reload, a loaded two-step
subset, selected-drop8 Marker dialog Generate/export/reload, H time-limit partial,
cancel/stale source, and injected partial-save failures. The viewer cancellation
test forces headless integration and is not native viewer acceptance.

`production-reviewed-125` retains7 fresh actual widget PNGs and RunReport;
`pub06-preservation-ui-reviewed` retains12 existing-workspace renders. FHD output
is1920×1080 at Qt process DPR1.25; it does not verify native OS125/input.
`full-G16-current/RunReport.json` records a fresh public200/120/80 mm,1 kg virtual
plan: selected16 of17 planned drops, explicit omitted hazard, one engine,
16 releases,11962 samples and95.69 s actual clock. That diagnostic retained
config/truth/report, not a full-G16 observed Raw file. Numeric approval and
experimental repetition remain0; previous failures and separate retries remain.
Backend commit `9c3e263` passed hosted CI37543122942. Current GUI commit CI,
publication and remaining approvals are tracked in PR151.
The same independent read-only reviewer closed all4 production GUI P2 findings
after inspecting the corrected source,159-pass XML and all7 actual PNGs. No
material P0/P1/P2 remains in that bounded audit. This does not certify native
behavior, numerical acceptance, current-source CI or complete #140 acceptance.

After the user readability request, central preview prose was replaced by a
compact card and structured optional Details. Corrected actual GUI integration
`ui-clarity-current.xml` passed49 checks in76.19 s. Fresh widget renders11 include
the three detail tabs and nondefault6.5 mm actual grip-radius display. A bounded
geometry/H/selection recheck passed4 in4.62 s. First37-pass/2-old-label-assertion failures are retained
separately in `ui-clarity-first.xml`, not overwritten.

At clean `e1547ab`, a separate real whole-G16 Marker producer saved11962 observed
Raw rows, one engine/16 releases and exact selected1–16/omitted17 metadata.
The original verification harness used a result-file loader on Raw and failed
after producing the capture; its `RunReport.json` is preserved. Correct Raw
loading of that retained capture passed in the separate
`full-G16-producer-e1547ab/RawReloadReport.json` (fresh0/reused1). This validates
saved whole-plan observations/reload, not independently measured package accuracy.
The subsequent pre-run summary uses four labelled rows with content-sized height;
error/stale states use two rows. The user subsequently requested English UI
consistency and deferred Korean localization. English labels and automatic-face
wording retain the exact serialized face enum via userData. The initial window
requests1280×900 logical pixels, capped to the usable screen including title/border
allowance; mode changes preserve manual size. Fresh affected GUI40 pass58.63 s,
final layout5 pass4.69 s, separate small-screen startup1 passes2.54 s, and actual
13-state Qt1.25 renders pass. Same-reviewer bounded English/startup review found
no material P0/P1/P2. No physics/time/rotation convention or metadata schema was
changed; latest-source CI is tracked in PR151. Native/human acceptance stays separate.

Original failures remain under `tmp/issue140`: import/invocation smoke failures,
first dynamic tracking failure, H rotation/floor-support failures, original
JUnit and support-limit scoping failure. Corrected runtime suite26 passed21.81 s
(`robot-support-scope-fixed.xml`). Extended suite26 passed plus one old-import
failure (`robot-extended.xml`); that failure and the later production-analysis
retry are distinct executions. PUB06 profiles/metadata57 passed9.64 s
(`preservation-first.xml`). Source commit is still base with dirty/new code.

`python -m src.simulation.robot_validation --output <new-directory>` generates
fresh cases A/B/H/held, direct files and a public observed capture, versioned
RunReport, explicit configuration/source hashes and separate truth. First run
`diagnostics-proposed` produced4 fresh cases in13.459 s, reused0, approved0,
experimental n0 and status `needs_review`. It is not a full repository/native/
measured run or final independent acceptance.

Later bounded checks: backend/export/PUB06 integration131 passed44.93 s;
explicit frame/Type and required phase contracts28 passed35.50 s;
real event-label mutation plus full Raw pipeline and partial-file retention2
passed13.97 s; compiled-gripper/source binding and PUB06 metadata38 passed13.42 s;
side-face/unknown Type, example32/custom marker identity and failure/cancel6
passed6.54 s. Counts overlap and are not summed. Each XML is separately retained.
The normal observer requires explicit literal virtual registration to classify
two free-falls; without independent registered geometry it retains unclear
evidence. Held-only registered observations produce no free-fall candidate.

The later `diagnostics-backend-current/RunReport.json` records4 fresh cases in
13.697 s against the latest explicit H category/compiled physics bindings. All
count/continuity diagnostics passed; overall status remains `needs_review`,
approved0/reused0/experimental n0. Existing GUI preservation initially passed33
and failed1 because Qt scale was1.0 while that test requires1.25; the original
failure remains in `existing-ui-preservation.xml`. A process-scale125 retry is
separate evidence and does not verify actual Windows OS125 input.
That retry passed34 checks in35.91 s (`existing-ui-preservation-125.xml`).

The distinct read-only backend reviewer found no P0/P1 and7 material P2s:
missing stage-state continuity, incomplete ordered toggle/reaction checks,
toggle-boundary partial rejection, ignored phase settings, insufficient phase
chronology, inconsistent incomplete status/coverage, and mutable effective-plan
source mismatch. Main added guards and real export/reload negative controls;
same-reviewer correction verification is pending. The first correction suite
passed50 and failed1 in64.53 s because the NaN rejection test expected a returned
failure while the schema correctly raised `ValueError`; both the original and
corrected executions are retained separately. No acceptance follows from a
static finding or a correction before its verification.

A separate fresh moving/spinning offset-COM diagnostic inspected74 consecutive
detached, force-free2 ms pairs. Independent `delta COM velocity - gravity*dt`
maximum absolute component errors were0.00008918/0.00016618/0.00001066 mm/s;
world angular-momentum differences were1.133e-8/2.608e-8/4.440e-9 kg*m²/s.
These observed differences are recorded with `needs_review`; no unapproved
numerical threshold is promoted. This checks COM/angular momentum rather than
incorrectly requiring the spinning, offset body origin to be ballistic or
asymmetric torque-free angular velocity to stay constant.

The corrected affected integration passed154 in72.94 s
(`review-corrections-integration.xml`). The later source guards and all-snapshot
relative-transform comparison received a separate bounded check:16 passed,
37 deselected in15.38 s (`review-state-binding-final.xml`), including11 evidence
controls,4 actual immediate-boundary partial exports/reloads and source chronology.
The current fresh diagnostic report has4 cases in18.615 s, approved0/reused0/n0,
and `needs_review`. Counts overlap; they are not a total test or trial count.
The same reviewer read the current code/tests and stored results, closed all7
material P2s within the backend checkpoint and found no remaining P0/P1 or
material P2 in that bounded correction scope. The reviewer did not execute tests.
Human UI/fixture/tolerance approval, production UI/native/CI and full issue
completion remain pending. All source snapshots,
original failures and retries remain separately identified.
