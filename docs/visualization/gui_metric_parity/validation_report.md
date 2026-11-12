# GUI and metric parity verification

Last Reviewed: 2026-11-12

This record covers public software behavior and generated analytic inputs. It does not establish measured experimental accuracy, package qualification, private adoption or human GUI acceptance.

## Source and environment

The implementation started from public main `20dd4ce53a6d401fd6e219d6086b7600dba35ad7` (PR #186), the exact #188 baseline. The fixed implementation revision is `593c669a37ce485aa76b7881e79ff6b26360ce58`; its file hashes are recorded in `adoption_manifest.json`; required definitions and actual producer identities are recorded in `metric_contract.json`. Local verification uses Windows, Python3.13 and the declared project dependencies. Exact observed versions and final command receipts are added below before publication.

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

## Final local receipts

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

Publication is tracked in [PR #197](https://github.com/pikachu444/BoxMotionAnalyzer/pull/197). Both complete required hosted workflows must succeed on the same final head before merge. Source pin593c669 remains unchanged by these evidence-only commits; immutable workflow receipts and merge lifecycle are maintained on that PR.
