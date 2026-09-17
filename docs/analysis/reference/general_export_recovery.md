# General marker export recovery

Last Reviewed: 2026-09-18

Issue #115 connects the public `write_observations` API to the actual analysis
path. This is public synthetic integration evidence, not independently calibrated
capture accuracy (#104).

## Execution and independent expectations

`tests/test_general_export_recovery.py` specifies 72 samples, 10 ms spacing,
nonconsecutive frame IDs, origin `(17 + 20t, 200 - 5t, 11 + 3t)` mm and literal
identity or smooth local-Z rotation matrices. It uses the existing public
200 × 120 × 80 mm, 18-marker example and seed 74082. Expected poses are these
declared inputs, not optimizer output. The generated truth file is checked
against the input arrays before it is used by the evaluator.

Each matrix case uses the normal CSV loader/parser, event-local
`FaceAssignmentAnalyzer`, actual correction dialog widgets, corrected CSV
save/reload, padded `.slice` save/reload and the Raw `PipelineController`.
The selected 0.12–0.55 s range produces exactly 44 original samples. The
review uses at most the existing 30 nonlinear fits per candidate; no review
threshold or iteration limit was changed.

| Case | Recommendation / explicit operator action | Evaluation |
| --- | --- | --- |
| Healthy, smooth 180° rotation | No approved correction | Declared moving pose |
| Full missing rows | Abstention, OFF | Two unavailable poses, no invented motion |
| One missing marker | OFF | Remaining geometry still determines pose and all eight corners |
| Held observations and reconnect offset | Abstention, OFF | Frozen pose and prescribed offset, not hidden physical motion |
| X, Y, Z | Conditional axis; separate explicit approval | Corrected pose |
| X/X, X/Y, Y/X | Two separate approvals | Intermediate and final chronological face states |
| Gap plus X | Recommendation withheld across missing observations; explicit X selection | Available poses restored; gap remains unavailable |
| Two visible markers | No supported pose | All selected poses unavailable |
| Physical-channel-only missing/permuted labels | No solved-channel correction | Solved pose unchanged |

Position and rotation acceptance bounds remain the existing noise-free public
0.1 mm / 0.1° bounds. The shortest box dimension is 80 mm; a 0.1° rotation moves
a corner by at most 0.216 mm. These are numerical acceptance bounds, not camera
accuracy, classification thresholds or acceptance criteria for real tests.

Default Apply is OFF and changing the preview axis does not approve it. In the
X/Y case, approving only X or selecting Y instead of X leaves the independently
expected approximately 180° error in the affected suffix. XYZ, physical and
solved marker IDs, actual times, frame numbers, complete decisions and cumulative
faces survive serialization. Saved annotation/history disagreement and an
unsupported coordinate policy are explicitly rejected.

During production work an executable guard rejects reads of evaluator files
through `builtins.open`, `io.open` (including pathlib/pandas) and `os.open`.
The guard has deliberate failing controls. Only observations and legitimate
geometry reach analysis. Two independently specified physical narratives also
produce identical parsed solved observations: the same conditional recommendation
cannot establish whether a solver error or actual discontinuous motion occurred.
Existing separately authored 90°/arbitrary-axis negative controls remain in
the event-local and continuity suites; the general corruption schema is unchanged.

## Actual defect found and corrected

Whole-marker missing rows in this normal path produced unavailable poses and
eight unavailable corners. Postprocessing previously raised `All-NaN slice
encountered` while finding Cmin, aborting the whole analysis. A missing reference
pose or entirely missing smoothed heights could also fail.

Original rows and unavailable values now remain in the output. Per-frame geometry
is calculated only where pose and all corners are finite, with the first valid
pose as reference when no contact reference exists. With no valid pose the
reference face/axes and all posture metrics remain unavailable.

The contact algorithm depends on whole-record smoothing, global height range and
tail plateau evidence. Therefore incomplete pose/corner records receive
`ContactState=Unavailable`, method `insufficient_pose`, an unavailable confidence,
and no claimed impact/t1. This does not mean no contact occurred. Comparisons
report incomplete evidence. Fully valid records retain the original contact
algorithm, and its whole-record comparison guard is retained. No missing rows are
removed or interpolated and no event-bounding policy, new metadata field or
storage version is introduced. #120 remains a separate investigation.

## Reproduction and retained evidence

Environment: Python 3.13.5, NumPy/SciPy/PySide6 versions recorded with execution
artifacts (local SciPy 1.16.3, PySide6 6.10.1). Run:

```powershell
.venv/Scripts/python.exe -m pytest -q tests/test_general_export_recovery.py
.venv/Scripts/python.exe -m pytest -q tests/test_drop_posture_post_processor.py tests/test_contact_comparison.py tests/test_impact_metrics.py
$env:QT_SCALE_FACTOR='1.25'
.venv/Scripts/python.exe -m pytest -q 'tests/test_marker_face_gui_flow.py::test_production_mainapp_face_review_save_and_process[general_export]'
```

The per-case JSON in `tmp/issue115` separates recommendations, operator actions,
persistence and recovery; it records seed, runtime versions and before/after
input hashes, and writes failure status before propagating an assertion. CI
retains these reports and JUnit results. The production MainApp test uses actual
Qt file dialogs and buttons to open, approve, save/reopen, process and save `.proc`;
its input comes from the general API and is compared to predeclared analytic
poses. Local rendering was inspected at 1510 × 800 logical size / DPR 1.25.
Screenshots are under `tmp/issue74_gui/general_export`.

The existing real-capture posture check is skipped when its independent local
input is absent; a skip is not an accuracy pass. Independent review and final
CI/merge evidence are linked from the #115 PR.
