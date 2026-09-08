# Minimal independent MuJoCo fixture contract for #74

Last Reviewed: 2026-09-08

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

## Next-task prompt

Continue #74 evidence work in C:\SourceCodes\BoxMotionAnalyzer. Read AGENTS.md, current #74/#79–#84, this contract, marker_flip_review_findings.md and Git state first. Use the existing independent generator instead of rebuilding it. Address explicitly recorded failures before expanding the matrix. Separate candidate triggers from correction recommendations and numerical convergence from identifiable pose. For the next real-data step, inspect the available VDTest_S5_001 CSV Rigid Body Marker channels and establish Motive-to-analysis origin/axis registration using independent calibration evidence; do not infer the transform from the detector's preferred correction. Record private source SHA, units, dimensions, face counts and numerical surface residuals. If that calibration evidence is unavailable, report the exact missing input; do not fabricate a production profile or claim a labeled flip. Keep derived capture coordinates private. Preserve the 0.1 mm / 0.1 degree synthetic gates, automatic recommendation OFF, and original XYZ. Broader GUI/export/preset changes remain separate. Update existing status documents, show actual inputs/expected/actual results, and keep commit/push/merge authorization separate. Do not auto-close #74.
