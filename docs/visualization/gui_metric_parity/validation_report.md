# GUI and metric parity verification

Last Reviewed: 2026-11-12

This record covers public software behavior and generated analytic inputs. It does not establish measured experimental accuracy, package qualification, private adoption or human GUI acceptance.

## Source and environment

The implementation started from public main `20dd4ce53a6d401fd6e219d6086b7600dba35ad7` (PR #186), the exact #188 baseline. The fixed implementation revision is `97f92df772e0f7776d37a6b41bf7f3469fe7fc0f`; its file hashes are recorded in `adoption_manifest.json`; required definitions and actual producer identities are recorded in `metric_contract.json`. Local verification uses Windows, Python3.13 and the declared project dependencies. Exact observed versions and final command receipts are added below before publication.

## Independent verification and corrections

The numerical adviser and separate implementation auditor used GPT-6.1 Sol with xhigh reasoning. Their tests use analytic/literal expectations rather than values copied from the production outputs. The adviser consulted the installed NumPy/SciPy documentation and the official [NumPy gradient](https://numpy.org/doc/stable/reference/generated/numpy.gradient.html) and [SciPy rotation mean](https://docs.scipy.org/doc/scipy/reference/generated/scipy.spatial.transform.Rotation.mean.html) references. Actual sampled seconds, first-order boundary gradients and an equal-weight rotation mean remain the public methods.

Found, corrected and rechecked cases include:

- A row index was used in a contact replay instead of saved physical seconds; snapshot/window tests now use the saved clock, including a +100s translation.
- Snapshot pose/corner consistency and derivative method/filter/time/segment provenance were incomplete. Missing/unsupported declarations now leave the affected values unavailable.
- Peak descent needed the complete supported prefix; failed tracking or inconsistent prefix geometry now excludes that reducer while retaining an independently valid t1 snapshot.
- Saved summary aliases bypassed existing reference/contact/confidence owners. Owner reasons now remain intact; diagnostic flags/method/count also reject malformed or inconsistent values.
- Negative angular norms and overflowing horizontal/sweep arithmetic could appear available. Finite intermediate/result checks now reject those paths without inventing zeros or directions.
- Legacy missing FinalFace was being filled during display. Only the new producer publishes it; display validates recorded fields against stable-tail evidence. Unsettled and unavailable remain distinct.
- Resolved non-unique corner categories were passed through the legacy numeric-corner formatter. The summary now displays the validated tied set directly while preserving the legacy stored scalar.
- Guide aliases for existing Details fields were missing; registered targets and both host wrappers now use context-qualified identities, filters reset on a valid target and unknown keys open Interpretation.
- Long summary labels hid the value column, and Guide focus/descendant styling hid content. Wrapped bounded columns, card-specific styling and focus scrolling were rechecked at constrained sizes.
- Default tooltips retained full paths and raw resolution statuses. Those fields now remain in explicit Diagnostics. Contact context and whole-window interval display use the actual owner result.

The before/after actual-widget prototype and product review, actual client sizes, fonts, DPR, language, keyboard checks, Customize Apply and separate VTK renders are under `ui_evidence/`. Product evidence is independent of the main implementation. Original historical captures are not relabelled as final renders.

## Execution receipts

The final public command/JUnit receipts and collection inventory are recorded below and on the linked PR before merge. A completed test count alone does not establish physical equivalence. Optional real-capture skips remain skips. Generated examples are not independent measured repetitions.

The first large local GUI execution failed. A sequential minimal reproduction also failed after the existing common-window tests, so concurrent execution alone did not explain it. The initial premise was that a new summary resize callback or deferred widget deletion caused the failure. Explicit deferred-delete flushing and a queued resize probe both failed the same reproduction. The same minimal reproduction on unchanged baseline20dd4ce also failed (7 passes and1 Qt callback error). The project environment used PySide6/shiboken6.10.1; a task-local environment using6.12.0 passed the existing common-window tests followed by the new workflow tests (24 passes). No global installation or dependency pin changed. These controls show a baseline-source failure and a successful task-local runtime control; they do not isolate a Qt root cause. Failed runtime probes and the baseline control are retained in `execution_evidence/` and are not reported as passes.

## P07 real producer hop

The user explicitly approved keeping the existing Raw processing and instrumenting its actual bounded pose fitting, replacing the original optimizer-zero condition on 2026-11-12. The recorded clarification is in [#196](https://github.com/pikachu444/BoxMotionAnalyzer/issues/196). No production processing algorithm or optimizer stopping option changed.

`tests/gui_metric_parity_fixtures.py` freezes both independent analytic inputs and numerical limits before fitting. Each source has61 samples,18 solved/18 physical markers, declared Global/Millimeters, an included0.1–0.3s window of11 samples and the existing50-row padding (61 saved rows). Only the11 included rows are fitted after the existing early trim. Both actual CSV→slice→Raw→proc→Step2/Guide→Compare paths passed, with11+11=22 measured real SciPy optimizer calls. The first identity-only11-fit attempt passed the numerical limits but exposed the Point/Guide series-context connection; that failed run is retained separately and is not added to the final successful receipt.

| Actual saved result | Max position component error mm | Max orientation error rad | Max interior velocity component error mm/s |
|---|---:|---:|---:|
| Identity |0.0001171269514|0.000004404108563|0.002760525142|
| +1000mm offset and30° tilt |0.00004906348336|0.000002467328956|0.002013190185|
| Frozen limit |0.05|0.001|2.5|

The position limit contributes at most0.05/0.02=2.5mm/s to each central-difference interior velocity component. Boundary velocities are not assigned this bound. Whole-window angle/range limits0.1°/0.25mm were frozen before fitting; pure arithmetic/geometry cases remain at1e-9. These are numerical regression limits, not optimizer stopping guarantees or measured accuracy.

The independent adviser re-opened both saved results without rerunning optimization and checked raw/slice/proc clocks, profile, units, manifest hash, actual values and22-call receipt. Both results are usable NoContact with diagnostic score0; t1 metrics and the four-sample final tail remain unavailable. Two generated files do not become independent experimental repeats; comparison retains reviewed-window and maximum-area-face gates, with repeat n=0. The test also checks invalid metadata and absent approval gates.

See `pipeline_fixture_manifest.json` and `pipeline_hop_receipt.json` for the exact public inputs, expectations, frozen limits and observed errors. Actual Point series use their full column tuple and a distinct on-demand `step2:series` definition; they are not aliased to a t1 summary, whole-window peak or comparison fit.

## Scope limits

Actual OS125 and human acceptance are not run. Windows Qt widgets, QTest interactions and actual VTK buffers have their own evidence. The external Windows input helper returned `failed to activate captured window` on the initial attempt and one fresh-window retry; external native-input success is not claimed. The actual installed Customize dialog was opened and Apply exercised through the real Qt controls with Text sizes13/14 already set; this Matplotlib version has no axis-font-size field in that dialog.

The public source and adoption instructions are available for review. Private experimental/CAE regression, binding approval and consumer rollout remain the consumer owner's later work.

## Earlier local receipts before hosted corrections

The isolated executable is `tmp/issue188-qt612/Scripts/python.exe`: Windows Python3.13.5, PySide6/shiboken6.12.0, NumPy2.3.5, pandas2.3.3, SciPy1.16.3 and Matplotlib3.10.7. It uses the existing declared application dependencies through a local site-packages binding; the adoption manifest lists the observed versions. GUI processes ran sequentially. No OS-wide Qt, display or clipboard setting changed.

| Command / evidence | Exit and observed result |
|---|---|
| `python -m pytest tests/test_gui_metric_parity_contract.py tests/test_gui_metric_parity_exports.py -q --junitxml=tmp/parity-pure-final.xml` |0;211 collected/executed/passed,0 failed/skipped;2 intentional overflow-input warnings before finite rejection |
| `QT_OPENGL=desktop python -m pytest tests/test_gui_metric_parity_workflows.py -q --junitxml=tmp/parity-workflows-final.xml --basetemp=tmp/parity-workflows-final-run` |0;21 collected/executed/passed,0 failed/skipped;58.57s; actual two-input Raw receipt identical to independently reviewed receipt |
| `QT_QPA_PLATFORM=windows QT_OPENGL=desktop python -m pytest tests/test_gui177_common.py tests/test_gui177_processing.py tests/test_gui177_results.py tests/test_gui177_compare.py tests/test_results_analyzer_experiment_summary.py -q` |0;40 collected/executed/passed,0 failed/skipped;53.98s; independent unchanged native control |
| `QT_QPA_PLATFORM=windows QT_OPENGL=desktop QT_SCALE_FACTOR=1.25 python -m pytest tests/test_comparison_reference_gui.py -q` |0;2 collected/executed/passed,0 failed/skipped;24.08s; Qt scale factor, separate from actual OS125 |
| Independent `python -m src.simulation.ci_evidence prepare --output tmp/issue188-final-independent-freeze` |0; all12 collections exactly match frozen inventory |

The independent auditor compared check02 with the baseline:1,762 existing nodes retained in order,232 additions,1,994 total, no removals or duplicates. The other11 test jobs and required check IDs remain unchanged. Collection coverage is not execution evidence. The local whole check02 attempt stopped at an existing Windows clipboard assertion in `test_gui177_flip.py` (empty clipboard after Copy); that failed attempt is retained in `execution_evidence/parity_public_qt612.log` and is not a whole-suite pass. The required clean hosted Windows workflows remain the publication gate.

The final combined local GUI repeat terminated with Windows access violation0xC0000005 while PyVista initialized its interactor in `test_experiment_info_and_explicit_diagnostics_preserve_owner_values`; no complete JUnit result was produced. The raw failure is preserved in `execution_evidence/parity-gui-final.log`. This is additional failed execution evidence, not a numerical regression diagnosis or a pass. A separate run uses the CI-declared `QT_OPENGL=desktop`; clean hosted Mesa/Windows checks remain required.

The final late Selected series review uses native Windows Qt6.12.0:2 targeted EN/KO tests and434 independent UI conditions passed, with10 captures and stable observed source hashes. Replacement/reuse, unknown cleanup, full tuple/unit/reference context, constrained1100/640 widths, Tab access and heading visibility are covered by `ui_evidence/product_series_qt612_recheck.json` and `scripts/gui_metric_parity_series_check.py`. Earlier static Guide/P02/Customize/VTK review retains its original Qt6.10.1 scope.

A further affected-test execution collected `test_results_analyzer_experiment_summary.py`, whose module-level `QT_QPA_PLATFORM=offscreen` default selected offscreen QPA when the shell had not explicitly selected Windows. That run reported38 passes and2 narrow-window geometry failures; the combined VTK run also collected this module. These are preserved configuration-specific failures, not native Windows results. The controlled follow-up explicitly selects both `QT_QPA_PLATFORM=windows` and `QT_OPENGL=desktop`, as the CI workflow already does. No assertion or product layout is changed on the basis of an offscreen geometry comparison.

The independent UI reviewer reproduced both affected-layout failures exactly under offscreen QPA/Sans Serif9: context minimum366→296px moved the split438/366→464/340, and CAE content/checkbox minimum360px exceeded the254px viewport. Under native Windows/Malgun Gothic9, context minimum240px remained stable and the checkbox minimum180px fit the241px viewport. This explains those two geometry failures through the measured QPA/font difference; no product or assertion change was justified.

The unchanged affected40-test native Windows control passed40/40 in53.98s (exit0). The measured platform/font/geometry comparison is in `ui_evidence/product_qpa_control_qt612.json`; `execution_evidence/parity-affected-windows-control.xml` retains JUnit execution. No source or test assertion was changed for this correction of the execution configuration. Diagnostic logs normalize trailing blank spacing only.

Publication is tracked in [PR #197](https://github.com/pikachu444/BoxMotionAnalyzer/pull/197). Both complete required hosted workflows must succeed on the same final head before merge. The earlier source pin1da5ce5 includes the comparison-selection and Diagnostics corrections; earlier593c669 and28ff53a UI/numerical evidence retains its historical scope; immutable workflow receipts and merge lifecycle are maintained on that PR.

## Broader comparison selection correction

A native full check02 attempt on eeb151d exposed the existing local clipboard failures and three comparison cases. It was explicitly interrupted after known failures to run the focused reproduction; no complete JUnit/pass claim is made. The three focused comparison cases failed on that source: two expected the replaced File details/raw-tooltip contract; the third exposed a real selection feedback loop. Selecting a no-time file in the file list emitted view refresh, whose stale table Contact row reset the file list and playback to the previous file.

The final correction synchronizes the numeric file column or Contact file row before publishing typed context. Table-to-file selection remains supported, while model values, eligibility, calculations and time policy are unchanged. Legacy assertions now require Experiment info and preserve the missing ModelId diagnostic in the explicit window. The existing time regression asserts Contact row selection, switches to Pre-contact and checks column selection without losing the chosen file or its unavailable-time state.

The GPT-6.1 Sol xhigh auditor found no product blocker. It caught an added assertion that assumed a numeric column while Contact mode was active; the test was corrected to assert the Contact row and then explicitly switch modes. The42-case correction execution had41 passes and only that assertion failure; final targeted verification is recorded below. Failed/interrupted diagnostic text is retained in `execution_evidence/parity-check02-native-final.log`, `parity-legacy-comparison-before.log` and `parity-comparison-correction.log`. The pre-correction hosted public run43136164166 was canceled; it is not counted as a successful gate.

Final corrected targeted command: `QT_QPA_PLATFORM=windows QT_OPENGL=desktop python -m pytest tests/test_comparison_layout.py::test_calibration_badge_and_time_tooltip_follow_current_view -q` passed1/1 in4.09s, exit0. The same UI reviewer then passed106/106 native Qt/QTest conditions on fixed source28ff53a with real graph/playback widgets: both selection directions, Contact/numeric modes, distinct graph payload, missing-clock Sample state, baseline, removal and reordered reload. See `ui_evidence/product_selection_sync_qt612.json` and the two final captures. No optimizer/solver was run by this bounded UI check; no async Qt error or source drift occurred. The42-case correction run's real22-call Raw receipt was also byte-equivalent as parsed JSON to the independent saved-artifact receipt.

## Complete comparison diagnostic migration

A final caller search and independent audit found additional legacy tests expecting raw reasons in Experiment info or default tooltips. Their numerical/count/category oracles remain unchanged; assertions now open Diagnostics and verify the original evidence there, while requiring the raw text to be absent from defaults. No test node was removed or replaced by a skip.

The audit also identified source omissions: raw selected-cell details had been stored for tooltips but were not forwarded to Diagnostics in every mode, graph/playback title tooltips still exposed full paths, and top/playback alignment tooltips directly displayed untyped reason strings. The final source forwards original selected-cell text to read-only Diagnostics, keeps paths in internal properties/explicit Diagnostics, and uses short names and localized general explanations in default views. It does not parse those explanations into eligibility or change model values, status, count, gap or source-time policy. Cell-specific tests isolate the Selected table cell block and exclude the all-metric owner dump, so another metric cannot satisfy an assertion.

The same GPT-6.1 Sol xhigh auditor rechecked these corrections and found no remaining material blocker in the scoped migration. Actual execution:

| Native Windows command (QT_OPENGL=desktop) | Result |
|---|---|
| `python -m pytest tests/test_gui177_compare.py tests/test_comparison_layout.py tests/test_impact_comparison_gui.py tests/test_contact_comparison_gui.py tests/test_comparison_gui.py tests/test_gui_metric_parity_workflows.py -q` |51/51 passed,0 failed/skipped,196.46s,exit0 |
| `QT_SCALE_FACTOR=1.25 python -m pytest tests/test_impact_comparison_gui.py tests/test_contact_comparison_gui.py tests/test_comparison_gui.py tests/test_metric_variants_gui.py tests/test_comparison_reference_gui.py tests/test_gui177_compare.py::test_c02_owner_alignment_exclusion_is_visible_and_not_pooled -q` |13/13 passed,0 failed/skipped,139.32s,exit0; final strict cell-block checks and final playback tooltip correction |

Both commands explicitly set `QT_QPA_PLATFORM=windows`. JUnit receipts are in `execution_evidence/parity-all-comparison-final.xml` and `parity-diagnostics-scaled-final.xml`. The13-case run includes actual retained Qt/VTK screenshots and unchanged baseline/repeat/conflict arithmetic. Source1da5ce5 changes presentation and tests; numerical producers/reducers and their independently checked inputs/tolerances remain unchanged. Pre-correction hosted public run43137843387 was canceled rather than reported as a successful gate.

Final source collection gate: `python -m src.simulation.ci_evidence prepare --output tmp/issue188-final-publication-freeze` completed with exit0; all12 jobs still exactly match the frozen inventory, including1,994 check02 nodes. This confirms population preservation, not whole-suite execution.

## Hosted failure43140730694 and corrections

This hosted attempt **failed**. Intermediate progress statements incorrectly treated API step conclusions as passes: `continue-on-error` reports successful conclusions even when raw outcomes fail. The final gate correctly rejected check02, check03 and their derived summary check22. Actual check02:1,989 passed,5 failed,0 skipped and11 passed subtests (1,994 node IDs; JUnit counts subtests separately). Final gate:21/24 steps,11/12 JUnit jobs and8/9 reports passed. Those are failures, not missing bookkeeping to waive. The incorrect progress report was explicitly corrected to the user.

The five failed tests had three causes:

1. SciPy1.18 requires an explicit trailing single-axis dimension for Euler batches. The independent numerical adviser changed only the test input to `angles[:, None]`; the16 alternating±179° rotations, TOP oracle and tolerances remain unchanged. The test passes on SciPy1.16.3 and1.18.0 under the official batch-shape contract. Hosted SciPy was1.18.1.
2. The synchronous missing-dimension Apply reveal occurred before the queued initial splitter resized the viewport. The same UI reviewer reproduced the actual failure on native Qt6.12, then passed the unchanged failed test and25 bounded conditions after the product queued a current-state guarded reveal after initial sizing and final load/Single commit. Splitter values are preserved; no forced test-side scrolling or weakened assertion was used.
3. The v2 capture oracle hardcoded unavailable FinalFace. With the requested new producer, exactly three analytic scenes legitimately emit BOTTOM. This caused two full-capture tests and a cancellation/checkpoint test to fail. Independent Sol/xhigh review derived BOTTOM from declared identity/pivot geometry, then confirmed exactly those three oracle availability changes in newly generated v3 assets. All37 downloaded v2 files,6 raw hashes, trajectories, other metrics, approvals, tolerances and scene intervals were preserved. The active migration has separate review metadata and v1→v2 history; preflight requires approved, matching semantic-review records. No actual observed result was copied into an expected numerical value.

Original v2 assets and failed reports are archived byte-for-byte in `execution_evidence/ci_43140730694/`, with hashes in `failure_summary.json`. The main code reviewer checked the migration, protocol checks, negative review tests and QObject-bound current-state reveal and found no material blocker. The extra analytic migration regression adds one node:1,995 required check02 nodes, preserving all prior nodes. The numerical contract suite now passes156/156 with the same two intentional overflow-input warnings. Fresh full/cancel/GUI execution and the next hosted gate are recorded separately below.

### Correction execution on97f92df

`QT_QPA_PLATFORM=windows QT_OPENGL=desktop python -m pytest tests/test_capture_regression.py::test_fresh_full_capture_pipeline_preserves_every_approved_scene tests/test_capture_regression.py::test_actual_step2_compare_and_scenario_export_reuse_fresh_results tests/test_capture_regression.py::test_ci_reopens_full_evidence_and_rejects_independent_review_failures tests/test_regression_evidence.py::test_one_shot_cancel_keeps_successful_checkpoint_and_explicit_resume -q --basetemp=tmp/parity-hosted-fix-fresh --junitxml=tmp/parity-hosted-fix-fresh.xml` passed10/10 in75.01s,0 failed/error/skipped,exit0.

This was a clean tracked-source local execution on97f92df: all6 scenes freshly processed,0 reused/failed,449 real fits and452 approved result rows (3 missing tracking rows were not fitted). It exercised original-source/time preservation, protected-sidecar isolation, all metric comparisons, scenario guards, actual Step2/Compare/export, strict report-reopen fault rejection and explicit cancel/checkpoint/resume. The resumed representative attempt counted its reused scene separately from its fresh scene; it is not substituted for the6-scene fresh full run.

The independent GPT-6.1 Sol/xhigh adviser reopened all saved results with optimization disabled and verified132/132 strict metric comparisons, every v2/v3 preservation claim and all39 original ZIP entry hashes. It confirmed the10/10 JUnit result with no bounded numerical blocker. `execution_evidence/local_97f92df_fresh_v3.zip` retains fresh assets, results and reports at their original relative paths; its companion JSON records hashes, counts and scope. This local success does not relabel failed hosted43140730694 as passing. The final public merge still requires both complete required hosted workflows on the final head.

The next-attempt collection check `python -m src.simulation.ci_evidence prepare --output tmp/issue188-final-1995-freeze` exited0 and matched all12 frozen jobs. Check02 now has1,995 required nodes: all prior1,994 retained and one analytic migration regression added. Intermediate API conclusions are not treated as proof of passing continued steps; the complete raw-outcome gate is authoritative.
