# Minimal independent MuJoCo fixture contract for #74

Last Reviewed: 2026-09-08

This is the next implementation task, not a claim that the current simulation exporter already meets this contract. Limit work to the recording/coordinate/layout/oracle portions of #80–#84 needed for #74; broader simulation UI, comprehensive presets, batch matrices and general export redesign remain separate.

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
6. `manifest.json`: schema/version, fixture ID, source hash (private only), code revision, engine version, timestep/substeps, initial state, box/layout/coordinate policies, seed/noise/occlusion specifications, file hashes, and event oracle. No detector outputs in truth fields.
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

## Next-task prompt

Implement only the minimal independent MuJoCo fixture generator described here in C:\SourceCodes\BoxMotionAnalyzer. First read AGENTS.md, #74/#79–#84, this contract, marker_flip_review_findings.md and current Git diff. Preserve existing work. Correct actual-time recording and world/body/COM transforms in mujoco_engine.py; add explicit layout and independent fault generation with separate truth/observed/manifest outputs in the smallest appropriate simulation module. Avoid the old exporter’s history mutation, assumed dt, and zero rotation fields. Generate public asymmetric healthy and X/Y/Z fixtures, then two-event and gap controls. Run them through the real Parser, FaceAssignmentAnalyzer and PoseOptimizer, compare against separately declared oracle, and report input/expected/actual errors without tuning thresholds to pass. Keep VDTest-derived outputs private and defer that layout until registration is verified. Leave automatic recommendations disabled until the measured evidence justifies a separate decision. Update this contract and implementation_todo.md with actual results and remaining work. Present changes and an English commit message with Korean explanation for commit approval; request push and merge approvals separately. Do not auto-close #74.
