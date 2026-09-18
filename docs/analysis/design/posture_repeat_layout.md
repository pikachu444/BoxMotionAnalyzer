# Posture comparison

Last Reviewed: 2026-09-18

## Layout reviewed before implementation

Keep the existing Compare window and its resizable Summary table. Append two
choices to the existing mode selector; no permanent panel or registration step.

```text
Summary   [Posture v]   Diagnostic
Metric                         trial A        trial B
Pre-contact Beta (deg)          12             14
Lowest-corner uniqueness gap (mm) 0             2
Whole-window max Beta (deg)     16             18

Summary   [Posture repeats v]   Diagnostic   Source: Constructed
Metric          n        Mean   Min   Max   Range   Counts   Match baseline
Beta            2 (low)   13     12    14    2       —        —
Lowest corner   2 (low)   —      —     —     —       ...      ...
Duplicate 1   Invalid 0   Conflict 0   Details at left
```

Numbers above illustrate placement only. Tooltips and existing expandable
Details show each metric's exclusion and duplicate resolution. The other four
modes, graph, individual/aligned viewing and playback remain available.

## Calculation and repeat scope

- Reuse saved pre-contact Beta, signed long/short tilt and reference-face height
  range; check constant summaries against geometry at the recorded t1-minus
  sample. Recorded event consistency is not independent contact validation.
- ReferenceFace is selected from all six faces, not inferred from FinalFace.
  Retain individual side-face values; pool reference-face angle/height diagnostics
  only for maximum-area faces with the same reference face and local axes.
- Lowest-corner uniqueness gap is the second-smallest minus smallest of eight
  finite world-Y corner heights at t1-minus. Exact ties give zero and a non-unique
  corner category. No near-tie threshold, confidence or acceptance score.
- Whole-window maxima and contact sequences are separately named. They require
  complete geometry and matching reviewed window definitions, sampling and
  reference context. With t1, compare the complete time grid relative to t1.
  Without t1, only uncensored automatically detected intervals with the same
  detection settings, evidence class/motion and time grid from interval start
  can pool. Manual unaligned windows remain individually visible. Different
  durations or arbitrary equal-duration windows do not pool.
- Reuse source/model/dimensions/layout/scenario/processing compatibility and
  #119 observation keys and per-metric resolution. Copies/reprocessing never
  become extra trials. Numerical summary checks allow only floating-point/CSV
  roundoff (absolute 1e-7 mm or degrees, relative 1e-9); they do not coalesce
  differing saved values in duplicate resolution. Window time comparison uses
  an absolute 1e-12 second roundoff allowance, not a physical tolerance.
- Numeric summaries show per-metric n/mean/min/max/range and n<3 notice.
  Corner and sequence values have category counts, never arithmetic means.
  Non-unique corner categories have no unique-corner agreement score.

## Validation

Independent literal heights, analytic rigid geometry and hand-calculated trial
tables cover arithmetic and eligibility. Actual Qt/VTK interaction at 1510×800
and measured DPR 1.25 checks both modes and retained controls. Synthetic results
do not validate real repeatability or physical accuracy; those remain #104.
