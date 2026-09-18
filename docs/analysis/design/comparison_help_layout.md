# Comparison reference and metric guide

Last Reviewed: 2026-09-18

## Small layout reviewed before implementation

```text
Summary [Posture v] Diagnostic                      [Metric guide]
Metric                    capture_A…proc     Baseline (Constructed)
                          Constructed        capture_B…proc
Pre-contact Beta (deg)     10                 20
```

Use a short Baseline/source line in file-column headers (Pre-contact, Details,
Posture) and the file cell in Contact. The label is text, independent of color
and filename length. Keep existing elision and full path tooltips. The two-file
case must show the marker without horizontal scrolling at 1510×800 / DPR 1.25.
Actual regression testing found that a third header line clipped the first row
by 2 pixels at the compact Summary height. The final layout keeps two lines by
placing Baseline and source together above the filename, preserving row space.

Repeats modes keep their current statistics layout. The Match baseline header
names its reference in a tooltip, and the compact cohort line also includes the
elided baseline filename with full identity in its tooltip.

The same Metric guide action stays on the right of the Summary mode row in all
six modes, including empty data. It opens a compact non-persistent dialog with
two tabs: Reading the table and Metrics. The first gives short shared scope,
units/reference-point, exclusion, repeat-count and contact interpretation notes.
The second reuses existing impact/posture/summary descriptors in a scrollable
list of names, units and explanations, initially focused on the selected metric
when available. No permanent panel, wizard, calculation or stored setting.

Keep selection, table mode/scroll, graph choice, Individual/Aligned mode and
playback behavior when the baseline changes. Validate long filenames, shifted
actual times, excluded sources, empty state, help open/close and both new #117
modes using real widgets; retain direct VTK capture separately from Qt grabs.

## Execution and review

`tests/test_comparison_reference_gui.py` supplies two public literal posture
files with declared 10/20 degree rotations and the second actual clock shifted
by 1.5 seconds. It exercises both baseline choices in all six Summary modes,
the common guide open/close action, empty and incompatible-model states, full
path tooltips, and real Qt/VTK rendering at 1510×800 / measured DPR 1.25. These
are display/state fixtures, not physical-accuracy validation. Input hashes and
direct VTK/Qt captures are retained under `tmp/issue122` and uploaded by CI.

Independent review identified that the existing stable-contact descriptor
incorrectly implied that stable contact always removes t1. The shared source
description now permits an earlier impact followed by a stable low tail, matching
the existing calculation. No contact algorithm changed. Review also prompted
explicit filename elision per column width, because Qt's multiline header
elision clipped the distinctive filename suffix. Full identity remains in the
tooltip. Final rereview, local results and exact-head CI/merge are in the PR.

Local related checks passed 39 tests with 1 optional real-capture test skipped
because `BMA_REAL_CAPTURE` was not supplied (68.91 s). The final actual GUI
recheck, including playback-position retention, passed 2 tests (17.88 s).
The skipped real-capture consistency check is not claimed as physical validation.
