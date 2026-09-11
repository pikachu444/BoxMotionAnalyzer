# Minimal independent MuJoCo fixture contract for #74

Last Reviewed: 2026-09-11

The minimal public example generator is implemented in `src/simulation/marker_fixtures.py`, with a separate production-analysis harness in `validate_marker_fixtures.py`. This does not make the legacy simulation exporter conformant. Scope remains the recording/coordinate/layout/oracle portions of #80–#84 needed for #74; broader simulation UI, comprehensive presets, batch matrices and general export redesign remain separate. Measured acceptance and remaining gaps are recorded in [the findings](marker_flip_review_findings.md).

## Recording and coordinates

- Record `data.time`, `data.xpos[body]`, `data.xmat[body]` (or `xquat`, wxyz), and `data.xipos[body]` separately. `xpos` is the body frame origin; `xipos` is the inertial COM. Call `mj_forward` after state changes / before sampling the derived transforms after stepping. Copy arrays, never retain mutable views.
- Use timestep 0.002 s and four steps per saved sample for the first fixture: measured time increment 0.008 s. Include the initial t=0 state. Do not generate timestamps using nominal 1/120 s or a separate loop counter.
- Convert world vectors with A = [[1,0,0],[0,0,1],[0,-1,0]] (MuJoCo Z-up to analysis Y-up); multiply meters by 1000 for millimeters. Keep box-local axes X=L, Y=W, Z=H unchanged. Then R_analysis=A R_mujoco. `A R A^T` applies only if the local basis is also transformed; do not copy that expression from #81 without identifying both bases.
- Verify a nonzero translation and nonidentity rotation with explicit axis vectors, eight corners, body origin, and COM offset. Require orthogonality and determinant +1. Validate local marker-to-world-to-local round trips independently of the detector.

Sources: [MuJoCo simulation](https://mujoco.readthedocs.io/en/stable/programming/simulation.html), [mjData](https://mujoco.readthedocs.io/en/stable/APIreference/APItypes.html#mjdata), [computation / kinematics](https://mujoco.readthedocs.io/en/stable/computation/index.html).

## Inputs and deliverables

1. Public explicit asymmetric layout (unequal face counts, off-center positions), dimensions, stable marker IDs, assigned faces and local XYZ, units, local origin, provenance and license. The existing handcrafted test is a mechanics example; do not fit a new layout to what the detector recommends.
2. Private VDTest_S5_001-derived layout only after verifying Motive-to-box origin/axis registration. Preserve source SHA and capture interval, marker ordering, face assignments and registration transform. A preview plus numerical surface residual checks must show FRONT/BACK/LEFT/RIGHT/TOP/BOTTOM counts and unknowns. Do not publish measured coordinates or derivatives.
3. `truth_pose.csv`: frame, actual time_s, body-origin xyz_mm, COM xyz_mm, unit quaternion (explicit order), rotation matrix; truth is captured before fault injection.
4. `truth_markers.csv`: frame/time, stable IDs and independently transformed world XYZ for the healthy local layout.
5. `observed.csv`: Motive-compatible six header rows plus two metadata rows; `Rigid Body Marker` solved constraints, Global/Millimeters. Keep any independent physical `Marker` data clearly separate. No v3 correction annotations in faulty input.
6. `observed.synthetic.json`: schema/version, fixture ID, source hash (private only), code revision and dirty state, generator/engine source hashes, engine version, timestep/substeps, initial state, box/layout/coordinate policies, seed/noise/dropout specifications, file hashes, and event oracle. No detector outputs in truth fields.
7. Case report: input, expected result, actual result, event/boundary/axis confusion, position and rotation error, surface RMSE, valid samples, failure/ambiguity classification. Keep proposed gates separate from measured results.

## Independent event oracle

Use 100 samples initially. Define half-turn matrices explicitly in the generator configuration: X=diag(1,-1,-1), Y=diag(-1,1,-1), Z=diag(-1,-1,1). At frame 30 (t=0.240), create a faulty solver pose R_observed=R_truth H, while the physical truth and motion remain unchanged. Constraint XYZ are produced from that faulty solver pose and the unchanged calibration layout. This is a solved-pose fault, not a physical marker-ID shuffle. For a legacy permutation-only fixture, specify the permutation by hand and give it a different fault kind.

| Case | Oracle / expected handling |
| --- | --- |
| Healthy | No applied correction; truth and observations agree |
| X / Y / Z solver half-turn | Boundary frame 30, declared local axis, manual v3 face correction should recover an identifiable analysis pose |
| Same axis twice | Frames 30 and 65 (t=0.520); faces return to baseline after second event |
| Different axes | Frames 30 and 65; independently multiply matrices and state expected final faces |
| Gap only | Frames 15–19 missing; no planted half-turn and no automatic correction |
| Gap then flip | Same gap plus frame-30 flip; do not place the known event inside an unobservable gap in the first case |
| Genuine rotation | Rotate truth as well as observation; must not present corrective recommendation as a proven fault |
| Incomplete/unknown faces | Explicit rejection or underdetermined status; no invented pair or face |
| Noise / ambiguous fit | Seeded variants; report error and abstention, not success by lowering thresholds |

Start noiseless and use explicit 0.1 mm translation / 0.1 degree geodesic rotation checks for the identifiable mechanics cases. These are initial numerical acceptance checks, not justified camera accuracy thresholds. If they fail, diagnose coordinate registration, identifiability, generation, or optimization. Never use the detector's correspondence table or recommendations to construct expected truth.

## Execution and scope

Run `.venv/Scripts/python.exe -m src.simulation.validate_marker_fixtures --case all --output tmp/mujoco_marker_validation` from the repository. For generation only, use `-m src.simulation.marker_fixtures`; `--seed` selects the noise seed. Each case receives the four input/truth/manifest files above; the harness adds `validation.json` and a combined `validation_summary.json`. Generated files and screenshots remain under ignored `tmp/`.

The built-in layout is `public-asymmetric-example-18`, 200×120×80 mm, with FRONT/BACK/RIGHT/LEFT/TOP/BOTTOM counts 4/3/3/3/3/2. It is an explicit example, not an OptiTrack installation standard. The engine starts with nonzero translation and rotation and COM offset (3,−4,2) mm, then free-falls without contact for 100 samples. This bounded lane does not validate collision physics or drop-standard presets. Constraint noise is independent 0.02 mm Gaussian stress, not a calibrated model of Motive solver errors. Dropout means missing solved constraints, not physical-marker visibility.

The detector receives observed CSV and explicit geometry only. The harness reads the independent oracle after candidate creation, and uses its axes solely to emulate manual approval. Finding declared boundaries and recovering pose does not demonstrate automatic axis selection. Unsupported rotations, freeze/reconnect, noise and low coverage are diagnostic controls; abstention alone is not correct classification. Automatic recommendations remain disabled.

## Custom layout input (generator 1.2)

Both generation and validation accept `--profile <local.json>`. Omission retains the existing public example. The JSON uses the same `example_profile()` schema: nonempty `profile_id`, `profile_version`, `publication`, `source`, `license`; `units=mm`, `origin=box-geometric-center`, `dimension_policy=absolute-mm`; explicit `box_dims_mm=[X,Y,Z]`; and `markers=[{id,face,xyz_mm}, ...]`. Local +X is RIGHT, +Y TOP, +Z FRONT; the opposite directions are LEFT/BOTTOM/BACK. No coordinates or dimensions are rescaled by the loader. Geometry changes require a different ID from the built-in public example and produce a different layout hash. A profile's source statement is user-supplied evidence, not software attestation of physical calibration.

The current raw analysis reader derives faces from marker-name prefixes F/B/R/L/T/M (FA/BA remain FRONT/BACK). The loader rejects incompatible ID/face combinations instead of silently analyzing a different face. Arbitrary naming conventions and a new raw face-map format are outside this minimal change. Exact ideal face geometry is still required within 1e-8 mm, with 1 mm minimum separation and non-collinear three-marker faces. This numerical geometry check is not a real-marker mounting tolerance. Do not project measured coordinates onto faces, relax the tolerance, or remove marker offsets merely to pass it; unresolved mounting/center offsets need a separately justified model.

Example execution, after supplying a reviewed local profile:

```powershell
.venv/Scripts/python.exe -m src.simulation.marker_fixtures --profile tmp/private_profile.json --case healthy --output tmp/private_layout_check --preview
.venv/Scripts/python.exe -m src.simulation.validate_marker_fixtures --profile tmp/private_profile.json --case healthy --output tmp/private_layout_check
.venv/Scripts/python.exe -m src.simulation.validate_marker_fixtures --profile tmp/private_profile.json --case x --output tmp/private_layout_check
```

`--preview` writes a box/marker/axis image alongside the generated files. The profile and its hash remain in the existing synthetic manifest. The test harness takes geometry through the explicit profile argument, not from the truth/event manifest; it later checks the layout hash. Analysis still receives only observed coordinates and dimensions. Custom body names use the profile ID. The no-contact recorder uses the profile dimensions and retains the original nonzero pose; its initial world Z is at least half the box diagonal plus 3.4 m for larger boxes. Mass 1 kg, COM offset (3,-4,2) mm and the short free-fall motion remain synthetic test settings, not recovered VDTest properties or an ISTA drop condition.

The exercised custom input is `tmp/custom_layout_validation/profile.json`: a public 240×132×100 mm, 18-marker example, explicitly unrelated to VDTest. Its healthy/X observed and truth files plus numerical reports are in the same directory. Capture-derived inspection output is separately ignored in `tmp/vdtest_registration/`; it is **not** an accepted generator profile. See the findings for the missing registration inputs. Keep private profiles and all generated derivatives in ignored/local storage; the CLI does not grant redistribution rights.

## Public collision lane (generator 1.2)

`--example 32 --motion face|edge|corner` selects a new public virtual 300×180×90 mm box with FRONT/BACK/LEFT/RIGHT/TOP/BOTTOM counts 11/12/3/3/3/0. Exact coordinates are the explicit `virtual_profile_32()` function; profile ID is `public-virtual-box-32`. This is neither a measured VDTest layout nor an approved attachment standard. Both built-in examples are immutable; changing their geometry requires a new custom ID. Private VDTest registration remains deferred and does not block this lane.

The three motions use existing Type G orientation functions with `08_Face_3_Screen_High`, `01_Edge_3-4`, and `04_Corner_3-4-6`. Only their contact orientation is reused. The lowest corner height is **100 mm**, not the preset schedule height. Initial lowest-point counts are independently checked as 4/2/1. Initial world XY is (0.12,-0.23) m, linear velocity (0.025,-0.015,0) m/s, angular velocity zero except the genuine-rotation control. Mass is 1 kg, COM offset zero, gravity (0,0,-9.81) m/s². Uniform cuboid principal inertia is (0.003375,0.008175,0.0102) kg m². Actual initial pose, velocity, compiled inertia, solver and both geom contact settings are recorded in the manifest.

The box friction input is 0.7 with torsional coefficient 0.01; condim 4 has no rolling resistance. Box margin 0.005 m activates contact and is not geometric rounding. `solref=(0.02,0.8)` results from legacy elasticity=0.2, which selects damping rather than a measured restitution coefficient. Floor and box compiled settings are both serialized; do not assume they are identical. Contact count, summed normal contact force, and minimum geometric corner height are sampled alongside each actual timestamp in the manifest parameters. With 0.002 s integration and 0.008 s recording, the first positive recorded force at 0.144 s locates onset within (0.136,0.144] s, not an independently measured exact impact instant.

Healthy and faulty observations share byte-identical numeric truth arrays. For collision X/Y/Z cases, the declared fault is frame 65 (0.520 s), separate from contact. Second events are frame 85 (0.680 s). Gap remains frames 15–19. Unsupported 90-degree/arbitrary rotations retain their separately defined frame 30. These choices are fixed in the generator before the detector runs; no detector-derived correction tables are used. A healthy collision may trigger review evidence, but never automatic correction. Freeze/reconnect and unsupported cases establish abstention only, not successful classification.

Example commands (use a different output directory for each motion because each case directory is named by case ID):

```powershell
.venv/Scripts/python.exe -m src.simulation.validate_marker_fixtures --example 32 --motion face --case healthy --output tmp/collision_validation/face
.venv/Scripts/python.exe -m src.simulation.validate_marker_fixtures --example 32 --motion face --case x --output tmp/collision_validation/face
.venv/Scripts/python.exe -m pytest tests/test_marker_face_gui_flow.py -k collision_face -q -s
```

Repeat the first two commands for edge/corner. Each invocation writes a summary of that invocation only; preserved per-case `validation.json` files are the combined evidence. The Qt-driven production GUI copies its observed/truth/corrected/slice/proc files and input/expected/actual report into ignored `tmp/issue74_gui/collision_face/`. Screenshots cover loaded input, approved X review, reloaded corrected source, and processed result. This is actual MainApp integration using Qt events, not a native manual mouse validation claim.

## Next-task prompt

The #74 collision/review scope merged through PR #87 on 2026-09-11. The bounded
#83/#76 follow-up is implemented separately in
`C:\SourceCodes\BoxMotionAnalyzer-worktrees\issue83-provenance-time`; confirm actual
Git status before continuing. Generator 1.3 adds only the safe artifact identity
described in `result_schema_notes.md` to observed CSV metadata; truth/event files
remain test-only. Custom and collision geometry above is unchanged.

Next task: review and finish publication of the bounded #83/#76 follow-up. Read
AGENTS.md, the latest issues, implementation_todo.md, result_schema_notes.md and
drop_result_comparison_plan.md. Verify source declarations and all exclusion
reasons, canonical time/t1, mixed sampling/gaps, original frame numbers and actual
GUI saved-file paths against the recorded commands. The public compatible pair
is two loads of one independently generated and processed result, not two trials.
Keep real compatible/mismatched captures pending when unavailable; do not infer
VDTest model geometry or request unavailable calibration again. Resolve independent
review findings with focused tests; preserve original XYZ and approval/recommendation
OFF defaults. Do not expand into #75/#77 or legacy exporter work. Show the final
diff, obtain separate commit/push/merge approvals and require same-head CI before
merge. Do not automatically close #74, #76 or #83 on synthetic evidence alone.
