# PUB01–PUB12 delivery and evidence status

Last Reviewed: 2026-10-13

Plan Spec: `ISTA6A-PLAN-20261001-v1`. This is the PUB12 audit for
[#134](https://github.com/pikachu444/BoxMotionAnalyzer/issues/134) and
[#145](https://github.com/pikachu444/BoxMotionAnalyzer/issues/145), against refreshed
`origin/main@698c0d5abd72d6634f9b4b0e8cde24af30b9cbec`. Issue bodies/comments,
merged PRs, their exact head CI, current call/save/reopen paths and original
available reports were compared. This audit changes documentation and tracking;
it does not rerun or relabel historical production runs as PUB12 executions.

## Delivery and publication

The issue column is the state checked at intake. Software delivery and complete
native/measured acceptance are separate. The original 2026-10-01 requirements
remain in the issues as historical requirements; the table below supersedes
their old implementation-status descriptions. All CI links below were checked
for success and exact `head_sha`, independently of PR merge state.

| PUB / issue | Delivered scope / current code | Merged PR | Source head → merge commit | Source-head CI |
| --- | --- | --- | --- | --- |
| PUB01 / [#113 OPEN](https://github.com/pikachu444/BoxMotionAnalyzer/issues/113) | Registration UI/integration unimplemented and **excluded by user decision**, with [original decision](https://github.com/pikachu444/BoxMotionAnalyzer/issues/113#issuecomment-5724646641). Existing static capture geometry/source lineage is delivered separately. No dependency is reinstated. | None | Not applicable | Not applicable |
| PUB02 / [#135 CLOSED](https://github.com/pikachu444/BoxMotionAnalyzer/issues/135) | Full observed Raw → fresh detection/replay → slice → PipelineController → PROC → Compare/scenario; `src/analysis/regression/runner.py`, `contracts.py`, `signatures.py`, pipeline `artifact_io.py`/`data_loader.py` | [#146](https://github.com/pikachu444/BoxMotionAnalyzer/pull/146) | `53265eea55553e4754d196a90e10016bc190d874` → `0250a7dc1afd491a6fa381febce71f1bc9335bb0` | [36979068143](https://github.com/pikachu444/BoxMotionAnalyzer/actions/runs/36979068143) |
| PUB03 / [#136 OPEN](https://github.com/pikachu444/BoxMotionAnalyzer/issues/136) | Responsive flip-review panels, drawn axes/units, fixed compute Cancel; `src/analysis/ui/dialog_marker_flip_review.py`, `widget_raw_data_processing.py` | [#147](https://github.com/pikachu444/BoxMotionAnalyzer/pull/147) | `f4f55f0bd77801fc603e4cf3d5d97d07052e6ad3` → `3a38b496ce2dedd2570479c8a77fef03d78961aa` | [37011751480](https://github.com/pikachu444/BoxMotionAnalyzer/actions/runs/37011751480) |
| PUB04 / [#137 OPEN](https://github.com/pikachu444/BoxMotionAnalyzer/issues/137) | Revert, save gate/counts, source-scoped viewport and ordered history; pipeline `scene_workflow_state.py`, `scene_workspace.py`, UI `scene_review_flow.py`/`widget_scene_review.py`, `artifact_io.py` | [#148](https://github.com/pikachu444/BoxMotionAnalyzer/pull/148) | `a6760c976909af6824295a3ccd61815efbe5f31e` → `1f654faddd44eedf7ff6e807d85f5e08559f8b13` | [37135346939](https://github.com/pikachu444/BoxMotionAnalyzer/actions/runs/37135346939) |
| PUB05 / [#138 OPEN](https://github.com/pikachu444/BoxMotionAnalyzer/issues/138) | Geometry/meaning/mapping identity; draft/Preview/Apply; atomic editor save/reopen and generation guards; `src/utils/marker_profile_identity.py`, `artifact_metadata.py`, simulation `profile_document.py`, `ui/marker_profile_dialog.py` | [#149](https://github.com/pikachu444/BoxMotionAnalyzer/pull/149) | `4b06c469647f322da9f1d46967f70d8db74ab0d2` → `d2e7656403b740da22d631f2ab8df6e100231ff1` | [37395011061](https://github.com/pikachu444/BoxMotionAnalyzer/actions/runs/37395011061) |
| PUB06 / [#139 OPEN](https://github.com/pikachu444/BoxMotionAnalyzer/issues/139) | Isolated per-mode profiles/settings; producer snapshots, public metadata transport and stale-worker cancellation; `src/simulation/mode_profiles.py`, `ui/mode_settings.py`, `ui/main_window.py`, `marker_export.py`, `data_exporter.py`, `src/utils/simulation_metadata.py` | [#150](https://github.com/pikachu444/BoxMotionAnalyzer/pull/150) | `2afdfb60531773c0cb3185f3b5fdf761f2947b57` → `2e3dea4b97fdb274501adf58ef6ae3744e3a0895` | [37491215034](https://github.com/pikachu444/BoxMotionAnalyzer/actions/runs/37491215034) |
| PUB07 / [#140 OPEN](https://github.com/pikachu444/BoxMotionAnalyzer/issues/140) | Explicit execution plan → dynamic one-state gripper → Run/Marker CSV/partial retention; `src/simulation/robot_profiles.py`, `engine/robot_sequence.py`, `robot_partial.py`, existing mode/UI/export routes | [#151](https://github.com/pikachu444/BoxMotionAnalyzer/pull/151) | `f1a66c9b867ef56a69de71aad31d2ebda3fa7d2e` → `78b6c797916f421530327b061ced098fc30060d8` | [37579195396](https://github.com/pikachu444/BoxMotionAnalyzer/actions/runs/37579195396) |
| PUB08 / [#141 CLOSED](https://github.com/pikachu444/BoxMotionAnalyzer/issues/141) | Opt-in timestep recording, corner-load event evaluation and ordered observed comparison; `src/simulation/contact_recording.py`, `contact_evaluation.py`, `contact_comparison.py`, `contact_validation.py` | [#153](https://github.com/pikachu444/BoxMotionAnalyzer/pull/153) | `1a057d2b4767e8c4c45bb28b2b0760ee0779f5da` → `da4a91048692f0cc5a5769028f4299ac8c61583c` | [37699587089](https://github.com/pikachu444/BoxMotionAnalyzer/actions/runs/37699587089) |
| PUB09 / [#142 CLOSED](https://github.com/pikachu444/BoxMotionAnalyzer/issues/142) | Opt-in seed/contact configuration, convergence, frozen fit and separate holdout, observed production export/reopen; `src/simulation/initial_conditions.py`, `contact_calibration.py`, `calibration_cli.py` | [#154](https://github.com/pikachu444/BoxMotionAnalyzer/pull/154) | `d0abe7c6f59cde26e2c1d8840d274e86d19247d7` → `7df201cd09cf4745385b986012bd9792dbbba8be` | [37750977113](https://github.com/pikachu444/BoxMotionAnalyzer/actions/runs/37750977113) |
| PUB10 / [#143 CLOSED](https://github.com/pikachu444/BoxMotionAnalyzer/issues/143) | Optional camera/assigned-face/group masks and actual-interval stationary OU after unchanged physics; `src/simulation/observation_profile.py`, `marker_corruption.py`, `observation_cli.py`, `observation_validation.py`, `src/utils/observation_metadata.py` | [#155](https://github.com/pikachu444/BoxMotionAnalyzer/pull/155) | `5a08ce3eba349eead79287b6d4436595fced16c9` → `5ecfdb88f780f38115cc998a33db3e963fe6abb4` | [37965002261](https://github.com/pikachu444/BoxMotionAnalyzer/actions/runs/37965002261) |
| PUB11 / [#144 CLOSED](https://github.com/pikachu444/BoxMotionAnalyzer/issues/144) | Fixed required protocols/test/step inventory; explicit representative resume and measured wrappers; `src/analysis/regression/evidence.py`, `runner.py`, `src/simulation/ci_evidence.py`, `tests/public_ci_inventory.json`, existing Windows workflow | [#156](https://github.com/pikachu444/BoxMotionAnalyzer/pull/156) | `492322c888e08ab0d8b84110d61bab496f576831` → `698c0d5abd72d6634f9b4b0e8cde24af30b9cbec` | [38286906108](https://github.com/pikachu444/BoxMotionAnalyzer/actions/runs/38286906108) |

Code paths refer to the audited tree at
[fixed main](https://github.com/pikachu444/BoxMotionAnalyzer/tree/698c0d5abd72d6634f9b4b0e8cde24af30b9cbec/src).
PUB06 config-only robot documents still fail `require_executable`; an applicable
PUB07 execution plan now passes that guard and selects `RobotSequenceEngine`.
This is already implemented in main, including Preview/Apply and incomplete side
files. G17 hazard, full ISTA apparatus certification and articulated-arm IK are
not implemented by these contracts.

## Executed populations and original evidence

The [main CI run 38297290908](https://github.com/pikachu444/BoxMotionAnalyzer/actions/runs/38297290908)
is successful at the audited merge commit. Its
[original artifact](https://github.com/pikachu444/BoxMotionAnalyzer/actions/runs/38297290908/artifacts/11771989275)
contains the following paths, relative to the artifact root. Eight CI source
file digests differ from local bytes only by Git's CRLF checkout representation;
their CI digests match the same commit's Git blobs rendered with CRLF. These
byte identities are kept distinct; no cross-environment cache reuse is claimed.
PUB12 reads these
reports; their execution belongs to that CI run. Required coverage is not a count
of independent experimental trials. The artifact has 30-day retention; fixed
source, contracts, compact indices and run links remain after expiry.

| PUB | Original execution and population | Contract / historical local index / review |
| --- | --- | --- |
| PUB01 | None; excluded. Static geometry used by PUB02 is not a registration UI. | #113 decision above |
| PUB02 | `issue144/full/run_report.json`: six Raw files/552 records, six approved scenes/452 PROC rows (449 valid + three approved unavailable); loaded/required/evaluable/pass/fresh six, reused/failed/unexecuted zero, 449 fit starts. Handling-only is a required case with zero included scenes. Independent analytic expectations and unchanged approved tolerances; successful fault-detection tests are separate. | [Capture contract](capture_regression.md), [historical compact index](capture_regression_validation.json) |
| PUB03 | Source-head CI plus required GUI lanes preserve 820×600/paired views, one/24 events, Details/loading/error/unavailable, pan/zoom, OFF/preview/Apply/Cancel and lifecycle. Historical 34 layout/lifecycle, 13 per-DPR layout and 146 preservation + three subtests overlap; do not sum. | [Delivery, original failure/native records and independent probe](../../visualization/marker_review_responsive_layout.md) |
| PUB04 | `issue137/render-125/execution.json` and `gui-125.xml`: 19 widget states, 25 GUI cases. Source/workspace/slice/PROC histories and nine derived signal units were corrected. QTest input is automatic input. | [Delivery and retained two P2 corrections](../../visualization/scene_review_workflow_137.md), [original review](../../visualization/mockups/scene_review_137/independent-review.md) |
| PUB05 | `issue138/render-125/execution.json`, `gui-125.xml`: actual editor/generation renders and tests; public18/32/custom/ambiguous/rank-deficient, source/draft/applied/reset/save/reopen. Historical 91/146/14 corrected checks and 30 states per DPR are separate scopes. | [Meaning contract](marker_profile_semantics.md), [delivery](../../visualization/marker_profile_138.md), [independent P1/P2 resolution](../../visualization/marker_profile_138_independent_review.md) |
| PUB06 | `issue139/contracts/RunReport.json`, `production-125/RunReport.json`: literal frame/COM/velocity/time, mode roundtrip and 12 actual GUI states; source and worker/save failures preserved. | [Mode contract](simulation_mode_contract.md), [delivery and production correction history](../../visualization/simulation_mode_139.md) |
| PUB07 | `issue144/pub07/raw/RunReport.json`: A/B/H/held, four fresh software cases, releases 2/1/1/0, no reused results, approved numerical zero and experimental n=0. Historical G16: one engine, 16 releases, 11,962 samples/95.69 s; retained Raw reload reused one capture/fresh zero. Sixteen releases are not 16 independent experiments. | [Robot contract and confirmations/review/failures](robot_sequence_contract.md) |
| PUB08 | `issue144/pub08/raw/RunReport.json`: 13 fresh functional cases = nine logical controls + three single physics paths + one actual two-release production case. Ordered matching retains ambiguous corner t2, whole-record ambiguity and missed rebound. Historical six comparison replays have no fresh physics; independent six recorder OFF/ON physics checks are a different population. | [Contact contract](contact_evaluation_contract.md), [index and six closed correction groups](contact_evaluation_evidence_v1.json) |
| PUB09 | `issue144/pub09/raw/RunReport.json`: 29 fresh engines = reference4 + convergence12 + fit6 + synthetic holdout2 + observed production2 + analytical3. Synthetic holdout required4/evaluable4/pass0; **observed holdout required4/evaluable0/not_detected4/pass0**. Neither whole protocol passes numerical acceptance. | [Calibration contract](contact_calibration_contract.md), [index with original five and final three integrity corrections](contact_calibration_evidence_v1.json) |
| PUB10 | `issue144/pub10/raw/RunReport.json`: eight fresh physics, 16 observations sharing those motions, 18 fresh production calls (two truth/label controls); 80 required endpoints, 76 evaluable/passed, one ambiguous, three unavailable, zero failed, **accuracy_pass=false**. Sixteen variants are not independent physics trials. | [Observation contract](observation_model_contract.md), [index with five resolved findings and later IO/CI corrections](observation_model_evidence_v1.json) |
| PUB11 | `issue144/{fast,capture,representative,full}/run_report.json`; fast/capture load six files/552 rows with production zero; representative selected/required/fresh one, unexecuted five. `ci-summary/run_report.json` validates 24 steps, 12 JUnit lanes, nine common reports. 1,757 testcase executions include duplicate lanes and exclude separate subtest counting. GUI wrapper reports widget/render pass, native/input/human pending. | [Tier/resume contract](regression_evidence.md), [index and four resolved P1 findings](regression_evidence_v1.json) |

`fresh` counts the actual processing/engine operation stated by each report;
`reused` states the reused artifact or motion. Required/evaluable/pass have their
own denominators: unavailable preservation can satisfy a software status check
without becoming a numerical or physical success. PUB09 proposed numeric pass
remains zero; PUB10's 76 software passes do not approve accuracy. Full PUB02 is
fresh only; representative resume cannot become full. Copies/lanes/samples do
not increase original trial n. Truth stays outside the production observed path.

Original local indices retain then-current commit, dirty source hashes,
environment, commands and failure/correction chronology. During PUB12, several
old local `tmp/issue135`, `tmp/issue141`, `tmp/issue142` and PUB10 full-run files
were not present at their indexed paths. These originals are **unavailable for
direct reinspection here**, not newly verified or silently replaced. Their
compact/embedded records and existing review reports remain historical evidence;
the source-bound main CI originals above independently establish current public
software execution. Available PUB10 reviewer reports and PUB11 correction/failed
attempt reports were read separately. Exact availability/digest checks and the
new independent audit outcome are recorded in #145. Missing historical files
do not establish experimental/native acceptance or measured performance.

Initial failures and later successes remain distinct: PUB02 v1 meaning mismatch;
PUB03 clipping/hidden Cancel; PUB04 CI37132419910 and37133853343;
PUB05 rejected mockups; PUB06 CI37487613060; PUB07 CI37576477292;
PUB08 production slice failures and superseded comparator; PUB09 initial and
derived-type failures; PUB10 CI37953999049 and pre-IO success37956884300;
PUB11 superseded/cancelled CI38284498730. See each delivery/index for original
source, reason and correction. A green earlier source is not the final gate.

## Schema, units, migration and CLI boundary

| Contract | Audited implementation / preservation |
| --- | --- |
| Capture fixture/signature/RunReport | `analysis/regression/contracts.py`: integer schema1, Plan Spec; half-open original records/time anchors; EOF never dereferenced. Parser/removal mapping and `artifact_io.py` retained slice records agree on reopen. |
| Scene workspace/review | Workspace/SceneReview schema2; nested history/plot_view schema1. `scene_workspace.py`, `scene_workflow_state.py`, `artifact_io.py` validate version/source/units and retain legacy handling. |
| Marker profile | Host Artifact SchemaVersion1 remains; complete profile/geometry/mapping/meaning envelope schema1; unchanged author hashes. Legacy partial face digest remains partial. No implicit approval/migration. |
| Simulation modes / robot | Mode/config/profile/document schema1 and explicit applicable RobotExecutionPlan. single_drop default; robot opt-in. Public SimulationMetadataJson excludes phase/fault/release truth; full evaluation metadata is separate. |
| Seed/contact/observation | Opt-in schema1/Plan Spec; WXYZ active local-to-world, seeded world Z-up, independent velocity frames/points; output Y-up mm/seconds. Direct simulation velocity aliases are mm/s; analysis drop metrics use m/s and rad/s. Actual time/frame/source identity persists through Raw/slice/PROC/Compare. |

Use the existing `.venv` from the repository root. CLI help and documented argument names were checked for
capture_corpus, analysis.regression.runner, mode_validation, robot_validation,
contact_validation, calibration_cli (demo/convergence/fit/holdout/run),
observation_cli, observation_validation and ci_evidence (prepare/run/verify).
Commands and output paths are in the linked contracts. Output attempt directories
must be new. Representative without `--scene`, fast/capture with selection,
missing required input and experimental without measured sources return nonzero.
No new migration, baseline/tolerance or contact-parameter promotion is performed.

## Remaining acceptance and completion rule

| Follow-up | Status, reason and required input/environment |
| --- | --- |
| PUB02 native GUI | New-corpus Step1/1.5 fresh processing, native chooser and 3D visibility pending; earlier local black viewport cause unconfirmed. Interactive Windows screen/activation and actual input needed. #135 software closure does not close this scope. |
| #136–#139 native | Issues remain OPEN. Black captures/activation failures prevented external screen/input acceptance; #139 GetCursorPos access denied. Widget grabs, QTest and Qt process1.25 do not verify actual Windows OS125. Repeat declared minimum/FHD/target states and save/cancel/retry on an accessible interactive desktop. |
| #140 native/numerical | Issue remains OPEN. Native viewer/input/OS125 and additional diagnostic bound promotion pending. Virtual operational controls were confirmed; further numerical/baseline/trial approval requires explicit review. |
| PUB08–10 numerical/model | Software issues CLOSED; proposed event/solver/noise thresholds, camera/contact calibration and measured accuracy pending. Chronological t2, PUB09 missed endpoints, PUB10 ambiguous/unavailable remain unchanged. |
| [#104](https://github.com/pikachu444/BoxMotionAnalyzer/issues/104) | OPEN: independently calibrated dimensions/frames, measured contact/trajectory, labels and synchronized evidence required. No validated measured dataset here; experimental tier blocked. Private captures/video/measurements are not published. |
| #113 / [#152](https://github.com/pikachu444/BoxMotionAnalyzer/issues/152) | #113 excluded, not completed. #152 language selection separate and deferred, not a child/completion condition of #134. |

PUB12 can complete after accurate mapping, link/CLI/schema validation, independent
read-only audit corrections and final-commit required CI/merge. Those conditions
do not require converting the above waits into success. #134 remains OPEN.
Publication, final commit CI, merge/main CI and #145 closure are updated in #145
after they happen; this document does not predict them or create a commit loop.

Main requested GPT-6.1 Sol/high; the running session has no authoritative model/
effort introspection, so actual routing is **unverified**. Independent review is
requested as GPT-6 Astra/high with `fork_turns=none`; the dispatch was accepted,
and the reviewer approved the corrected document mapping after one H-scope P2
was resolved. Actual runtime routing remains unverified. The original review
and final candidate CI/merge follow-up are recorded separately in #145.
Self-checks passed207 relative links,21 CLI help/error invocations,10 original
CI reports (nine common plus summary) and12 JUnit lanes/1,757 testcase executions.
These are documentation/original-evidence checks, not new physics runs.
No silent substitution.
