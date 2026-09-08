# Issue #74: evidence, correction scope, and verification status

Last Reviewed: 2026-09-08

## Decision and evidence

Scope was checked against [#74](https://github.com/pikachu444/BoxMotionAnalyzer/issues/74) and its comments, parent/validation [#73](https://github.com/pikachu444/BoxMotionAnalyzer/issues/73) / [#78](https://github.com/pikachu444/BoxMotionAnalyzer/issues/78), and follow-ups [#79](https://github.com/pikachu444/BoxMotionAnalyzer/issues/79)–[#84](https://github.com/pikachu444/BoxMotionAnalyzer/issues/84). Their proposed thresholds and transforms are requirements to assess, not physical ground truth. This revision implements the subsequently approved face-assignment scope; it does not claim the original XYZ-permutation proposal handles all solved-pose errors.

**Confirmed:** Motive CSV distinguishes measured/reconstructed `Marker` trajectories from solved rigid-body marker constraints (the local Format 1.25 files label these `Rigid Body Marker`). Constraints describe the rigid body's solved pose and calibrated arrangement; they are not independent physical-marker observations and may remain available during occlusion. Source: [OptiTrack CSV export](https://docs.optitrack.com/motive/data-export/data-export-csv), [rigid body tracking](https://docs.optitrack.com/motive/rigid-body-tracking).

**Local evidence:** VDTest_S5_001 has both groups. The previous investigation found 32 channels in each group and 1,062 finite rigid-body poses out of 1,072 frames. Inverse-pose local-coordinate temporal RMSE was approximately 0.000834 mm for constraints and 2.88 mm for measured markers. This supports the solved-constraint interpretation; it does not prove a flip or verify the analysis box origin. Prefix classification gives FRONT 11, BACK 12, LEFT/RIGHT/TOP 3 each, BOTTOM 0. Physical labels and coordinate registration still need independent verification. Raw files and derived custom layouts remain private. The previously reported TestBox_85 78.1% is not a validated detection result.

**Inference:** A pure label permutation can recover coordinates only when the exported columns still contain the desired physical trajectories and a complete, correct correspondence is known. A solved-pose half-turn need not have any partner marker in an asymmetric arrangement. A Hungarian minimum-distance assignment always returns an assignment for a square finite cost matrix; that alone does not establish geometric validity. An admissible legacy mapping must be bijective, within tolerance, nonidentity, and satisfy p(p(i))=i. Partial correspondence is not an excuse to invent missing XYZ values.

**Approved model:** v3 `face_assignment` keeps constraint XYZ and identities, and changes their analysis face labels by a local half-turn. The point-to-assigned-face PoseOptimizer then recomputes the analysis pose. Face counts may differ and markers need not have symmetric partners. This is an interpretation of solver constraints, not restoration of measured physical markers or modification of the exported Motive rigid-body pose. It is suitable only when the chosen box-local half-turn and original face labels describe the error. Unknown faces, different pivot origins, non-half-turn errors, or nonrigid errors are not automatically repaired.

The face objective is a surface-distance fit rather than a fixed landmark fit. Low residual does not guarantee an identifiable pose: poorly distributed faces and flat/degenerate arrangements can leave degrees of freedom weakly constrained. For fixed point correspondences, see [Kabsch, 1976](https://doi.org/10.1107/S0567739476001873); it does not justify treating face centers as known marker positions.

## Thresholds and recommendations

Legacy layout correspondence = fraction of rotated layout markers whose assigned partners fall within tolerance. Event correspondence = fraction of pre/post median pairs within tolerance. Sample coverage = valid samples in the evidence windows. These have different denominators; none measures independent camera visibility for solved constraints. Issue #74's 80% is not sufficiently specified to equate them. A box-diagonal 5% distance tolerance and the weighted orientation/correspondence score have no empirical calibration here. Best-versus-second score margin is not a probability.

The new GUI therefore reports actual bounded re-fit angular residual and face-fit RMSE, keeps operator decisions OFF by default, and withholds automatic recommendations. Candidate generation remains heuristic and may miss events or flag genuine motion. Failed optimizations are excluded, and evidence windows do not bridge invalid samples or abnormally large time steps. Thresholds were not relaxed to make tests pass. Independent known-normal/known-fault data must measure event recall, false positives, boundary offset, axis confusion, pose error and ambiguity before recommending a gate.

## Implementation and reproduced defects

| Trigger / defect | Change | Evidence / remaining limit |
| --- | --- | --- |
| Asymmetric layout has no valid XYZ permutation | v3 face assignment, preserving XYZ/IDs | Explicit unequal-face synthetic X/Y/Z tests; not a real-capture validation |
| Minimum-distance result is outside tolerance or identity | Reject legacy mapping | Legacy mapping tests; no partial pair fabrication |
| Finite output from failed optimization | Exclude failed Source values from evidence | Failure-source test |
| Finite X with missing Y/Z | Require all XYZ finite | No invalid marker handed to optimization |
| Duplicate/reversed time | Reject review instead of treating duplicate samples as evidence | Explicit invalid-time test |
| Translation near coordinate zero | Physical-scale Nelder–Mead simplex | Original test error 2.81095 mm despite success; fixed without lowering 0.1 mm / 0.1 degree checks |
| Re-save, OFF changes, or suffix-only slice | Materialized per-row faces and original face context | Repeated materialization and suffix slice round-trip tests |
| Changed source/dimensions after approval | Bind context/hash and reject stale save | Source-change test; corrected slice dimensions cannot be independently changed |
| Filtering across a face change | Segment smoothing, differentiation and resampling | Segment-specific regression checks |
| Legacy integration fixture has no assigned markers but prefilled pose | Replace fixture with explicit healthy constraints and real Parser; missing pose remains unavailable | Do not preserve stale rotations to make a test succeed |

The pre-existing branch was `codex/issue-74-marker-flip-review`, HEAD `2030e9f`, with 15 modified tracked and 6 untracked files, nothing staged, and no PR for that head. Existing work was preserved; an ignored local snapshot is in `tmp/issue74_implementation_baseline/`. The working diff includes that prior implementation as well as this revision. No commit, push, or merge is authorized by implementation approval alone.

## External data availability

The OptiTrack sample archive was checked at file-list level and contains `.tak` simple movement/rotation captures, not a verified labeled flip CSV. Motive export and applicable use terms must be established before using it as a distributable fixture. The 6D-ViCuT Dryad record/README describes PhaseSpace/C3D data with two markers per box; that is not a Motive constraint flip oracle. No useful labeled real flip file was established. Dataset introduction pages and archive listings are not executed validation. Additional broad data collection is not part of this task.

## Acceptance boundaries and next action

The tests in `test_marker_face_assignment.py` exercise the production Parser/PoseOptimizer and versioned file paths with independently declared geometry/half-turn matrices. `test_marker_face_gui_flow.py` drives the real MainApp, real background review, real dialog and file I/O with Qt events. It does not substitute a detector, optimizer, or dialog factory. Native Windows driver attempts were unreliable at the file-dialog focus stage; record Qt-driven GUI verification separately from native manual testing. Local screenshots are ignored and no video is produced.

Executed 2026-09-08: a 100-row, 200×120×80 mm public asymmetric fixture with X solver half-turn at t=0.30 s was loaded in the real MainApp. The actual candidate was at 0.30 s; default approval OFF and no recommendation were verified, then X was approved and saved. Original bytes and all original numeric columns remained unchanged. Corrected source → slice → real processing → proc completed; the result carried ContextJson and the approved event. Independent comparison of that proc gave maximum position error 0.0001095 mm and rotation error 0.0002329 degrees against 0.1 mm / 0.1 degree checks. Boundary velocities at 0.29/0.30 s were unavailable. This validates that particular noiseless mechanics case, not physical-capture accuracy. The initial native click did open the synthetic CSV; repeatable full-flow verification used Qt events. The test-driver filename reset and GIL-starving wait were corrected during verification.

Final focused pipeline run: `test_marker_face_gui_flow.py`, `test_marker_face_assignment.py`, `test_pipeline_integration.py`, `test_velocity_calculator_acceleration.py`, `test_resampler.py`, `test_range_limited_resampling.py`, `test_pipeline_resampling_options.py`, and `test_marker_flip_artifact_io.py` passed together (29 tests). Checks include reloading approved geometry, non-fabricated boundary derivatives, one-row/spline segments, missing XYZ/stale pose, materialized suffix faces and cumulative reversibility. These outcomes, rather than the number of tests, define the verified scope.

Final GUI/compatibility run after adding explicit ON/OFF approval text: production GUI flow, review dialog, raw widget, raw processing, legacy detector, input validation, coordinate configuration and marker smoothing passed together (33 tests plus 5 subtests; the GUI flow overlaps the preceding run). A pre-existing long-filename mock plot test still emits a Matplotlib tight-layout warning. The actual review screenshot shows boundary 0.300000, no recommendation, explicit ON, selected X and the computed residual trace; processed output screenshot shows successful slice processing and save. No remaining failed check is being reported as a pass.

MuJoCo and labeled real OptiTrack validation remain open. The current work does not complete issue #74 or establish automatic detection accuracy. Follow the next-task prompt in [marker_flip_fixture_contract.md](marker_flip_fixture_contract.md). PR text must retain these limitations and must not use automatic issue-closing keywords for #74.
