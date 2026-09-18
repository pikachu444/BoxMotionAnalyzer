# Analysis Implementation TODO

Last Reviewed: 2026-09-18

This is the handoff document for ongoing Analysis GUI, Drop Posture, and experiment comparison work. Read it before continuing related implementation. Current behavior is documented in `gui_overview.md`, architecture in `system_design.md`, and result schema details in `../reference/result_schema_notes.md`.

Use `[O]` for completed items and `[ ]` for remaining items. When a task is completed, change its checkbox to `[O]` and update the stable design/reference documents. Keep this file focused on active handoff items, not as a permanent design archive.

## TODO List
- [O] #115: Connect the general observation exporter to observed-only review, explicit widget approval, corrected/slice round trips and real Raw reprocessing. Preserve missing rows and report unavailable contact instead of aborting on all-NaN corners. See `../reference/general_export_recovery.md`; final independent review/CI/merge evidence belongs to the PR.
- [O] #114: Add optional Simulation marker CSV generation with public/imported layout preview, explicit layout dimensions, cancellable worker, new-folder publication and observed-only Step 1 handoff. Direct `.proc` export remains available. See `../../simulation.md` and `../../visualization/synthetic_marker_export_layout.md`; required CI and merge are recorded in the PR.
- [O] #121: Embed original observation context next to the existing local-axis preview, with marker/body selection, actual-time event cursor, pan/zoom and Around event. Preserve pending choices and the existing modal/source verification/save gates. See `../../visualization/marker_review_context_layout.md`; CI and merge are recorded in the PR.
- [O] #123: Show existing vertical speed on first detection, retain finite selected raw/derived signals on re-detection, restore valid workspace choices and discard old-source callbacks. Existing ranges, review decisions and saves remain unchanged. See `../../visualization/scene_signal_layout.md`; final review/CI/merge evidence is in the PR.
- [O] #117: Add individual posture and distinct-trial summaries with metric-specific compatibility, context conflict resolution, categorical corner/sequence counts and the geometric lowest-corner gap. See `posture_repeat_layout.md` and `../reference/posture_comparison_execution.md`; final CI/merge status is recorded in the PR.
- [O] #122: Mark the baseline directly in existing file tables and add one shared Metric guide using current descriptors, including #117. Preserve file/mode/graph selection; retain compact two-line headers and full identity tooltips. See `comparison_help_layout.md`; final review/CI/merge evidence is in the PR.
- [O] #116: Investigate whole-box recovery and remove only the demonstrated false rejection of a three-marker collinear face. Public 3/4/5-marker face exports recover the declared pose; face-only geometry remains unavailable in the solver. No expanded restrictions, certification UI, convention version or hash migration. See `../reference/layout_and_contact_investigation.md`; final CI/merge evidence is in the PR.
- #120 investigation completed; original bounded-policy implementation deferred. Seven normal public-input paths did not reproduce isolated corner loss. Preserve whole-record replay; the all-marker-loss crash was already fixed by #115/PR #127. See `../reference/layout_and_contact_investigation.md` and the issue findings. This is not implementation completion of the original proposal.
- #113 is excluded by the 2026-09-18 user decision. Do not add experiment registration or require it as a dependency. #119 representative-reprocessing selection UI is also excluded. #104 remains separate real calibration.
- [O] #112: Implement observation-only scanning, bounded event-local pose/refits, source/configuration identity, explicit dimensions and cooperative cancellation through SciPy and close. Existing face gates, XYZ/ID invariance and corrected-source handoff are retained. Public parity, call-count, lifecycle and measured DPR 1.25 GUI evidence and independent-review fixes are recorded in `../reference/marker_review_execution.md`. Required CI and publication are tracked in the PR. #121 now provides raw-context inspection; #104 real calibration remains separate.
- [O] #119: Implement canonical-exact-v1 metric-wise observation resolution and minimal Repeats/Contact evidence UI. Related checks: 314 passed; final GUI correction checks: 18 passed; independent core re-review: 111 passed, and independent UI correction recheck passed with no remaining findings. Real Qt/VTK measured 1510×800 logical / DPR 1.25. Merged in PR #125. See drop_result_comparison_plan.md section 8. Authoritative revision selection remains out of scope; the previous stop-before-merge instruction was superseded on 2026-09-18.
- [O] #118: Implement recorded first-event consistency, state-specific confidence and visible exclusions. Local 244-test verification, final 5-test GUI rerun and independent correction review passed; see `drop_result_comparison_plan.md`. Published in PR #124 and merged as 99b1f1e after required CI 35193845672 passed; #118 is closed. #119 metric-wise deduplication is delivered; #120's proposed bounded event policy is deferred after investigation.
- [O] #106: Keep Step 2 file, curves, point selection and exports in one result context; preserve open launcher windows. Native 243-row tilt to 27-row drop switching and exact point export, independent code/physics review and active-batch close regression passed. PR #107 merged as `b39b966` after CI `34765216913` passed reviewed head `ad0d410`.
- [O] #106: Connect scene saving, single/batch processing, result viewing and comparison; simplify Step 1/1.5/2 controls. Native single 27-row and batch 34-row/34-row handoffs, cancellation and window checks passed; independent code/physics findings were corrected and rechecked. PR #108 merged as `1c5777e` after CI `34770782163` passed reviewed head `3135c0a`, including hosted 125% replay. The local replay OS-hover failure remains recorded separately.
- [O] #106: Simplify comparison controls and metric names; correct corner-ID presentation, units, angular scale and individual/aligned viewing. Distinct-file native interaction and final Windows Qt/VTK rendering, save/reopen regressions and independent code/physics/UI correction rechecks passed. Final external desktop input was interrupted; native limits and Qt evidence are separated in `gui_overview.md`. PR #109 merged as `378cc45` after CI `34777069440` passed reviewed head `16628dd`, including the hosted 125% replay.
- [O] #106: Fit Simulation actions to the window and prioritize marker-correction decisions and plots over diagnostic detail. Actual Qt 125% small-window interaction, 63-sample MuJoCo export/reopen, 241-row correction save/separate-process reopen and independent code/physics/UI review passed. Original data and explicit approval are preserved; Step 1 position units follow source metadata. Execution limits and corrections are in `gui_overview.md`; required CI and publication are tracked in the linked PR.
- [O] Retain #84 public validation context and failure reports, execute deliberate oracle-offset and omitted-correction controls through real pose validation, and preserve original files and normal reports. Actual CLI results and independently reproduced/fixed report-integrity defects are recorded in `../reference/marker_flip_review_findings.md`. The Windows lane retains public JSON/JUnit evidence; final CI/publication status is tracked in #84 and its PR.
- [O] Connect the existing public face-drop MainApp/Raw/proc execution to precontact metrics in required CI, retaining synthetic identity and actual-time evidence. Reuse the same optimized poses for a 12-row sustained-contact control; no additional normal Raw run is added. Independent review fixed final input-change/deletion failure propagation. See `drop_result_comparison_plan.md` for values, bounds and execution limits; final CI/publication status is tracked in #84 and its PR.
- [O] Complete #84 public noise/freeze/genuine-rotation acceptance, generic export-to-scene coverage, per-test Level 1/2 reporting, and current-checkout independence from captures. Preserve all local capture bytes while removing their Git tracking; public schema/viewer tests use literal canonical geometry and real consistency checks require an explicit local path. Execution, limitations and independent review are in `../reference/marker_flip_review_findings.md`; final CI/publication is tracked in #84 and its PR.
- [O] Complete #78 release GUI replay using retained public results at 125%: Step 1/1.5/2, Comparison, many ranges/files, actual input/cancel/error paths and independent review. Window lifecycle, long paths, rotation display, legend/3D and small-summary defects were fixed and independently rechecked. See `gui_overview.md` section 7; final CI/publication is recorded in #78 and its PR. No extra Raw processing is needed to check these layouts.
- [ ] Complete independent real calibration in [#104](https://github.com/pikachu444/BoxMotionAnalyzer/issues/104). All listed categories are unavailable; Level 3 external access remains optional/manual. Per the user's scope decision, these obligations are separate from public/synthetic software completion. Local captures and historical Git objects are preserved.
- [O] Implement and execute #82 generic trajectory/profile/corruption-specification API and CLI. Physical visibility/ID routing and solved half-turn faults are independent; original truth/time/frame and existing output files are preserved. Actual MuJoCo inputs and MainApp reopening, plus independent code/physics findings and corrections, are recorded in `../reference/marker_flip_review_findings.md`. CI/publication status is recorded in #82 and its PR; real error-model validation remains pending in #104.
- [O] Implement and independently review the first #77 unit: experimental precontact geometric-centre velocity, angular speed, conditional registered-COM equivalent height and distinct-observation summaries in existing Comparison. Actual serialized public results, negative controls, source exclusions, duplicate counting and Qt/VTK use were verified. Scope, findings and evidence are in `drop_result_comparison_plan.md`; final CI/publication status is recorded in #77 and its linked PR.
- [O] Implement #77 intended first-contact agreement in existing Step 1 and Comparison. Independent local face/edge/corner choices survive workspace/slice/proc reopening; exact contact sets yield Match/Different, unsupported evidence yields Unclear, and duplicate/conflicting observations do not inflate Local n. Independent code/physics review findings were fixed and rechecked; actual Qt flows and public MuJoCo penetration rejection are recorded in `drop_result_comparison_plan.md`. Existing posture plots and diagnostics are reused. These experiments have no target angle. Final CI/merge status is recorded in #77 and its PR; independent real validation remains pending in #104.
- [O] Implement bounded #81 SimulationUI exporter actual-time/pose/non-destructive path. Details and input/expected/actual evidence are in `../../simulation.md`; direct Simulation output remains synthetic and does not claim Analysis processing or real validation.
- [O] Preserve previous Simulation results on write/replace failure; restore controls and support retry. Independent code/physics checks, real viewer failure/retry, Batch success/failure and production reload are recorded in [simulation.md](../../simulation.md); publication is recorded below.
- [O] Publish the reviewed saving changes in [PR #89](https://github.com/pikachu444/BoxMotionAnalyzer/pull/89). Head `c03e1d5` passed CI [34615506467](https://github.com/pikachu444/BoxMotionAnalyzer/actions/runs/34615506467) and merged as `da2137d` on 2026-09-12 KST. #81 is closed for software delivery; its independent real-orientation validation remains pending in #104.
- [O] Implement the first useful #75 unit: automatic observed-motion candidates in existing Step 1, relative-rotation/velocity plots, review/edit/include/exclude, conditional registered posture matches, and reviewed `.slice`/`.proc` transport. See `gui_overview.md`, `../../simulation_external_reference_notes.md` and `../../simulation.md` for inputs, physics and limits. The manual scene popup remains rolled back.
- [O] Run the actual MainApp from capture loading through included-slice saving, Raw processing and Step 2 plotting/reopening; independently review code and physical meaning. Two synthetic falls retain ambiguous H identities, and the real capture exposes its rotation and missing tail without inventing a trial number. Detailed outcomes and the native mouse limitation are in `gui_overview.md` section 2.4.
- [O] Publish that first #75 unit in [PR #90](https://github.com/pikachu444/BoxMotionAnalyzer/pull/90). Head `6e1777e` passed Windows CI [34624845120](https://github.com/pikachu444/BoxMotionAnalyzer/actions/runs/34624845120) and merged as `ec9812b` on 2026-09-12 KST. The issue remains open.
- [O] Add selected-trajectory support geometry and `.slice`/`.proc` evidence preservation. Public tilt/return gives 77.645714 mm, while center rotation and floor dragging have no fixed floor pivot. Independent review corrected floor penetration and near-45-degree starting-face ambiguity. The internal evidence remains after simplifying the Step 1 display; see `gui_overview.md` and `../../simulation_external_reference_notes.md` for execution and limits. This does not identify H trials.
- [O] Publish support geometry in [PR #91](https://github.com/pikachu444/BoxMotionAnalyzer/pull/91). Head `0e77022` passed Windows CI [34630053718](https://github.com/pikachu444/BoxMotionAnalyzer/actions/runs/34630053718) and merged as `23534fb` on 2026-09-12 KST.
- [O] Implement and independently review #75 whole-record review restoration. Separate actual MainApp processes preserved unfinished rows, manual additions/deletions, selection and 77.645714 mm support evidence; continued review exported a slice that reopened in Step 1.5. Pending registration, plot-target loss, filename collisions and reference-edition findings were corrected and rechecked. See `gui_overview.md` and `../reference/result_schema_notes.md` for outcomes and limits. [PR #92](https://github.com/pikachu444/BoxMotionAnalyzer/pull/92) passed CI 34634363058 at head `1d6b278` and merged as `ff5ef04` on 2026-09-12 KST.
- [O] Connect complete fixed-edge rise/return motion automatically in existing Step 1 and retain measured phases as internal evidence. Public normal/elevated/repeated motion and confusing controls, actual workspace/slice/proc reopening, and independent code/physics corrections are recorded in `gui_overview.md`. Raw activity ranges and operator decisions remain intact; trial intent stays unconfirmed. Final CI/merge status is recorded in #75 and its PR.
- [O] Connect #75 approved-face corrections to scene detection. Registered axes/corners now follow full approval history; unregistered relative references remain separate. Actual corrected-source save, separate MainApp reopen and Raw processing preserved the selected 12 frames and metadata. Independent reviews fixed unclear-range merging and stale version-refresh evidence; both counterexamples passed rechecks. See `gui_overview.md` for execution limits. Final CI/merge status is recorded in #75 and its PR.
- [O] Remove unnecessary support-height and edge details from Step 1 while retaining internal detection evidence and saved review meaning. Actual MainApp reopening preserves the original 351-point B1 curve, selected range, review decisions and registration; deletion hides the range and disables slice export. Independent review fixes preserve real selector visibility and concise Item uncertainty reasons. See `gui_overview.md`; final CI/merge status is recorded in #75 and its PR.
- [O] Complete #75 explicit test-record association in existing Step 1, including repeated/partial attempts and G16/G17/H support/rotation identities. Recorded identity and observed agreement remain separate; apparatus/contact force and missing trial context remain unverified. Public analytic and existing motion inputs, actual MainApp save/reopen/Raw execution, and independent review corrections are in `gui_overview.md` section 2.5. Final CI/merge status is tracked in #75 and its PR. Real labeled accuracy is an external follow-up, not a software delivery gate. Automation `boxmotionanalyzer-74` remains PAUSED; do not resume it without instruction.
- [O] Implement Issue #74 v3 analysis face-assignment mechanics; #74 closed after PR #102 and CI 34740245043 passed reviewed head `553c2692cdb70ad185b63d1bffc9389ffd25f9a9`, merged as `1c8ecf8` on 2026-09-13 KST.
  - Keep every event OFF until explicit operator approval.
  - Separate recommendation axis from operator-selected axis.
  - Preserve Rigid Body Marker XYZ/IDs; apply chronological per-row analysis face assignments. Read v2 permutations separately.
  - Save a separate corrected CSV atomically and activate it only after success.
  - Propagate original/corrected source identity and the full decision history into `.slice` and `.proc`.
  - Deterministic asymmetric fixtures check X/Y/Z pose consistency, cumulative faces, and corrected/suffix slice round-trip. Legacy detector tests do not validate the new model's accuracy.
- [O] Execute the minimal public independent MuJoCo fixture task in `../reference/marker_flip_fixture_contract.md`.
  - Actual time, body origin/COM/rotation and independent truth/observed files are recorded. Nine noiseless pose-mechanics cases meet the unchanged numerical gates; four controls provide abstention diagnostics only.
  - Two-constraint false success is rejected; real GUI X-flow preserves all 100 samples after correcting slice endpoint precision. Detailed input/expected/actual results are in `../reference/marker_flip_review_findings.md`.
  - Those earlier runs kept recommendations disabled. The 3.1 conditional continuity policy below has its own acceptance evidence.
- [O] Implement and independently review #74 conditional continuity recommendations. Actual 24-marker challenges and GUI corrected/slice/proc persistence passed after fixing observed-boundary and whole-window stability defects; see `../reference/marker_flip_review_findings.md`. Required CI and merge status are tracked in #74 and its PR. Real tracking accuracy is separate from software completion.
- [ ] Establish private VDTest_S5_001 Motive-to-box origin/axis registration from independent calibration evidence before using its layout. Calibration is unavailable and deferred; it does not block the public collision lane. Do not publish capture-derived coordinates.
  - CSV and 32 constraints inspected; independent physical dimensions, pivot/axis relation and mounting/face evidence were not found in the repository. Details and exact missing inputs: `../reference/marker_flip_review_findings.md`.
- [O] Accept explicit local JSON layouts in the independent generator and harness, retaining the public default. Public custom dimensions/coordinates were checked numerically and through the real GUI save/reload flow. This does not complete VDTest registration.
- [O] Reject insufficient local face-constraint rank and unknown faces; clear pose/corners with explicit status. Full rank is only a necessary local guard, not proof of global uniqueness.
- [O] Complete independent review of the public 32-marker face/edge/corner collision lane and current v3 persistence integrity fixes. [PR #87](https://github.com/pikachu444/BoxMotionAnalyzer/pull/87) merged on 2026-09-11 after two independent reviews and head `67cba01` CI run 34589028534 passed. This does not close #74.
- [O] Implement bounded #83/#76 provenance/compatibility and actual-time comparison mechanics. Artifact metadata survives raw/corrected/slice/proc; incompatible identities and invalid time exclude baseline differences while preserving individual review. See result_schema_notes.md for the contract and drop_result_comparison_plan.md for input/expected/actual evidence.
  - Independent-review corrections cover executed processing-settings JSON/hash, raw-time gap roundoff, source-only unknown synchronization exclusion, nonnumeric position sample safety, and pre-write validation in existing slice-dimension repair. [PR #88](https://github.com/pikachu444/BoxMotionAnalyzer/pull/88) merged on 2026-09-11 as `9085d85` after review and CI.
- [ ] Validate the required real comparison categories in #104. #83/#76 closed on 2026-09-12 for software delivery after separate code, execution, review and CI checks; their independent real comparison pairs and timing references remain pending. This closure does not claim real calibration or establish independently calibrated accuracy.
- [ ] Validate solver-derived constraint error models and ambiguous/genuine motion cases. Research and implementation status: `../reference/marker_flip_review_findings.md`.
- [ ] Validate Issue #74 recommendation gates against labeled real OptiTrack capture categories.
  - Collect or identify captures with known no-flip, X/Y/Z relabel, gap-only, freeze/reconnect, genuine physical rotation, low coverage, and ambiguous evidence outcomes.
  - Record expected boundary and operator-reviewed axis independently of the detector.
  - Tune thresholds only from this real-capture set; synthetic fixtures remain mechanics/integration evidence, not production-accuracy evidence.
- [O] Add Drop Posture frame and summary metrics after processing.
- [O] Store Drop Posture summary columns in `.proc` results.
- [O] Add `ImpactSequence`, contact state, contact confidence, and contact detection method.
- [O] Replace the old Step 2 one-line `Drop Posture Summary` with a grouped summary table.
- [O] Add descriptor metadata for Drop Posture summary labels, units, tooltips, metric guide text, and visual guide ids.
- [O] Add `Metric Guide...` dialog backed by descriptor metadata.
- [O] Add real `TestBox_85` contact-slice flow verification using `TestSets/Input/VDTest_S5_001.csv`.
- [O] Link this handoff document from root `AGENTS.md` and `docs/documentation_index.md`.
- [O] Review and update Step 2 panel numbering:
  - `1. Result Files`
  - `2. Data Selection`
  - `3. Drop/Impact Summary` or `3. Drop Posture Summary`
  - `4. Peak & Point Selection`
  - `5. Export Analysis Input`
- [O] Replace the current `15 metrics` summary status with one short interpretation message:
  - Impact found: `Impact detected`
  - No impact found in the selected time window: `No impact detected`
  - Missing Drop Posture summary columns: `Drop Posture data unavailable`
- [O] Use clearer user-facing wording for `SustainedContact`.
  - Raw/internal label: `SustainedContact`
  - Recommended summary/table label: `Stable floor contact`
  - Guide explanation: stable low contact can coexist with an earlier impact and t1; stable contact alone does not establish a new impact.
- [O] Move `Metric Guide...` below the summary table unless implementation review finds a stronger reason to keep it in the title row.
- [O] Reconsider the summary panel title.
  - `Experiment Summary` is broad and may imply full experiment-level comparison.
  - Recommended default: `3. Drop/Impact Summary`.
- [O] Verify tooltip behavior manually and with UI tests.
  - Intended behavior: Qt hover tooltip appears when the mouse cursor rests on a summary table row or DropPosture item in the Data Selection tree.
- [O] Redesign the Metric Guide layout around three grouped sections instead of many small repeated diagrams:
  - `Posture`
  - `Impact`
  - `Contact`
- [O] Replace the current simple Qt-painted diagrams with clearer illustrations or maintainable visual assets.
- [O] Document every Drop Posture result metric with calculation basis, units, sign convention, and interpretation before changing formulas.
- [O] Review `ReferenceFace` semantics.
  - Current behavior: face whose normal points most strongly downward at the reference frame.
  - User expectation: face or contact region associated with actual floor contact after first impact.
  - Consider splitting into `ApproachReferenceFace` and `ImpactContactFace`.
- [O] Review signed angle behavior for `ThetaLongDeg` and `ThetaShortDeg`.
  - Current formula is effectively `asin((positive-side height - negative-side height) / local-axis length)`.
  - Positive means the positive side of the chosen local axis is higher than the negative side.
  - Investigate plot cases where long/short angles look physically confusing outside the pre-impact interpretation window.
- [O] Add synthetic and real-data tests for signed angle interpretation:
  - positive long-axis lift
  - negative long-axis lift
  - positive/negative short-axis lift
  - real `TestBox_85` sanity check around and after `t1-`
- [O] Update stable docs after each completed item:
  - `gui_overview.md`
  - `system_design.md`
  - `drop_result_comparison_plan.md`
  - `../reference/result_schema_notes.md`

## Reference Images
- User-provided reference images are layout/composition references only. Do not copy them exactly.
- Resolve conflicts in favor of current application structure, existing Step 2 UI patterns, descriptor-driven metric definitions, and maintainable code.
- Current reference images:
  - `../../images/compare_gui_conceptual_layout.jpg`
    - Conceptual reference for launcher-level `Compare Results`, MVP scope grouping, summary table, side-by-side 3D comparison, and event-aligned plot composition.
  - `../../images/compare_gui_dense_desktop_layout.jpg`
    - Denser desktop layout reference for compare workspace structure: left file/settings rail, top comparison summary table, synchronized 3D playback, and event-aligned comparison plot.

## Image Generation Prompt Starters
- Posture illustration:
  `Technical engineering illustration, clean white background, semi-transparent rectangular TV shipping box tilted above a flat floor plane, eight corners labeled C1 to C8 according to local box coordinates: C1(-X,-Y,-Z), C2(+X,-Y,-Z), C3(+X,+Y,-Z), C4(-X,+Y,-Z), C5(-X,-Y,+Z), C6(+X,-Y,+Z), C7(+X,+Y,+Z), C8(-X,+Y,+Z). Highlight the automatically selected reference face facing downward, show beta angle between reference-face normal and downward floor normal, show long direction arrow and short direction arrow on the reference face, show DeltaH vertical bracket between highest and lowest reference-face corners, highlight Cmin lowest corner in red. Minimal labels, no decorative background, precise CAD-like style.`
- Impact illustration:
  `Technical engineering illustration for drop test impact timing, clean white background. Show a tilted transparent box descending toward a floor, with a horizontal time axis below labeled approach, t1-, first impact, later impacts. Mark t1- as the frame just before first impact. Highlight first impact corner C2 touching the floor, then show an impact sequence strip C2 -> {C2,C3} -> C5 with simultaneous contacts grouped in braces. Use simple arrows, clear callouts, restrained colors, CAD-like style.`
- Contact illustration:
  `Technical engineering illustration for contact detection evidence in a box drop test, clean white background. Show a floor line and a small height-versus-time curve for the lowest box corner. Include threshold band near floor, descending approach slope, impact event marker, rebound/turning point, and sustained low plateau region. Next to the plot show a transparent box with one or two corners near the floor. Label ContactState examples: NoContact, Approach, ImpactEvent, SustainedContact. Minimal text, precise engineering diagram style.`

## Later Work: Experiment Comparison GUI
- [O] Keep the compare window as a launcher-level feature, not as another panel inside Step 2.
- [O] Confirm the next scope in `drop_result_comparison_plan.md`.
