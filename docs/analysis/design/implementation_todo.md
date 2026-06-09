# Analysis Implementation TODO

Last Reviewed: 2026-06-09

This is the handoff document for ongoing Analysis GUI, Drop Posture, and experiment comparison work. Read it before continuing related implementation. Current behavior is documented in `gui_overview.md`, architecture in `system_design.md`, and result schema details in `../reference/result_schema_notes.md`.

## 1. Current Work: Step 2 Experiment Summary
- Replace the old one-line `Drop Posture Summary` display with an `Experiment Summary` grouped table in Step 2.
- Keep the display order as `Posture -> Impact -> Contact`.
- Manage Drop Posture summary labels, tooltips, metric guide text, and visual guide ids through `src/config/result_metric_descriptors.py`.
- Do not hardcode metric explanation text inside UI code.
- Add a `Metric Guide...` dialog that reads descriptor long descriptions and shows simple visual guides.
- Show t1-based summary values as `N/A` in the UI when `T1Detected=False`.

## 2. Current Work Verification
- UI tests must verify `.proc` summary table group order, t1 `N/A` behavior, and descriptor-backed tooltips.
- Keep existing regression coverage for result layout, header conversion, Drop Posture post-processing, real physics slices, and real data flow.
- Use `TestSets/Input/VDTest_S5_001.csv` as the real `TestBox_85` fixture.
- If an explicit 85-inch dimension value exists in the repo, use it. If not, use the real-data estimated fixture dimensions `(2082.9, 1046.6, 254.4)` mm.
- For real contact verification, slice `2.45s-3.05s` and run pipeline processing, export, DataHandler reload, and DataLoader reload.
- Verify `BetaAtT1MinusDeg`, `DeltaHAtT1Minus_mm`, `CminAtT1MinusIndex`, `FirstImpactTimeSec`, `FirstImpactContact`, and `ImpactSequence` numerically from pose/corner coordinates, not just by checking column existence.

## 3. Current Work Documentation
- Update `gui_overview.md` for the Step 2 layout and `Experiment Summary` role.
- Update `system_design.md` to name descriptor metadata as the Drop Posture UI explanation source of truth.
- Update `drop_result_comparison_plan.md` to separate the current single-experiment summary work from the later compare window.
- Update `../reference/result_schema_notes.md` for Drop Posture summary behavior, t1 absence handling, and 85-inch real-data verification.
- Keep this TODO linked from root `AGENTS.md` and `docs/documentation_index.md`.

## 4. Next Work: Experiment Comparison GUI
- After the current Step 2 summary work is complete, read this file again before starting the compare window.
- Confirm the next scope in `drop_result_comparison_plan.md`.
- Keep the compare window as a launcher-level feature, not as another panel inside Step 2.
- Implement first: multiple `.proc` file loading, baseline experiment selection, comparison target selection, summary difference table, and time-history overlay graph.
- Implement later: side-by-side 3D playback, synchronized playback, and event-based time alignment.
- Reuse the same Drop Posture descriptor metadata for compare-window labels, tooltips, and metric guide text.
- Compare-window tests should verify that loading the same `.proc` twice produces near-zero differences and that controlled synthetic/fixture differences produce expected metric deltas.
