# Analysis Implementation TODO

Last Reviewed: 2026-06-09

This is the handoff document for ongoing Analysis GUI, Drop Posture, and experiment comparison work. Read it before continuing related implementation. Current behavior is documented in `gui_overview.md`, architecture in `system_design.md`, and result schema details in `../reference/result_schema_notes.md`.

Use `[O]` for completed items and `[ ]` for remaining items. When a task is completed, change its checkbox to `[O]` and update the stable design/reference documents. Keep this file focused on active handoff items, not as a permanent design archive.

## TODO List
- [O] Add Drop Posture frame and summary metrics after processing.
- [O] Store Drop Posture summary columns in `.proc` results.
- [O] Add `ImpactSequence`, contact state, contact confidence, and contact detection method.
- [O] Replace the old Step 2 one-line `Drop Posture Summary` with a grouped summary table.
- [O] Add descriptor metadata for Drop Posture summary labels, units, tooltips, metric guide text, and visual guide ids.
- [O] Add `Metric Guide...` dialog backed by descriptor metadata.
- [O] Add real `TestBox_85` contact-slice flow verification using `TestSets/Input/VDTest_S5_001.csv`.
- [O] Link this handoff document from root `AGENTS.md` and `docs/documentation_index.md`.
- [ ] Review and update Step 2 panel numbering:
  - `1. Result Files`
  - `2. Data Selection`
  - `3. Drop/Impact Summary` or `3. Drop Posture Summary`
  - `4. Peak & Point Selection`
  - `5. Export Analysis Input`
- [ ] Replace the current `15 metrics` summary status with one short interpretation message:
  - Impact found: `Impact detected`
  - No impact found in the selected time window: `No impact detected`
  - Missing Drop Posture summary columns: `Drop Posture data unavailable`
- [ ] Use clearer user-facing wording for `SustainedContact`.
  - Raw/internal label: `SustainedContact`
  - Recommended summary/table label: `Stable floor contact`
  - Guide explanation: `The selected time window is already in a low, stable contact state, so t1-based impact values are not assigned.`
- [ ] Move `Metric Guide...` below the summary table unless implementation review finds a stronger reason to keep it in the title row.
- [ ] Reconsider the summary panel title.
  - `Experiment Summary` is broad and may imply full experiment-level comparison.
  - Recommended default: `3. Drop/Impact Summary`.
- [ ] Verify tooltip behavior manually and with UI tests.
  - Intended behavior: Qt hover tooltip appears when the mouse cursor rests on a summary table row or DropPosture item in the Data Selection tree.
- [ ] Redesign the Metric Guide layout around three grouped sections instead of many small repeated diagrams:
  - `Posture`
  - `Impact`
  - `Contact`
- [ ] Replace the current simple Qt-painted diagrams with clearer illustrations or maintainable visual assets.
- [ ] Document every Drop Posture result metric with calculation basis, units, sign convention, and interpretation before changing formulas.
- [ ] Review `ReferenceFace` semantics.
  - Current behavior: face whose normal points most strongly downward at the reference frame.
  - User expectation: face or contact region associated with actual floor contact after first impact.
  - Consider splitting into `ApproachReferenceFace` and `ImpactContactFace`.
- [ ] Review signed angle behavior for `ThetaLongDeg` and `ThetaShortDeg`.
  - Current formula is effectively `asin((positive-side height - negative-side height) / local-axis length)`.
  - Positive means the positive side of the chosen local axis is higher than the negative side.
  - Investigate plot cases where long/short angles look physically confusing outside the pre-impact interpretation window.
- [ ] Add synthetic and real-data tests for signed angle interpretation:
  - positive long-axis lift
  - negative long-axis lift
  - positive/negative short-axis lift
  - real `TestBox_85` sanity check around and after `t1-`
- [ ] Update stable docs after each completed item:
  - `gui_overview.md`
  - `system_design.md`
  - `drop_result_comparison_plan.md`
  - `../reference/result_schema_notes.md`

## Reference Images
- User-provided reference images are layout/composition references only. Do not copy them exactly.
- Resolve conflicts in favor of current application structure, existing Step 2 UI patterns, descriptor-driven metric definitions, and maintainable code.
- Current reference images:
  - `C:/SourceCodes/BoxMotionAnalyzer/.codex-remote-attachments/019ea7d4-f1a5-76e0-bebe-1d5c4b5afed3/c242cca6-d9b2-429c-a78c-c56057d6329a/1-Photo-1.jpg`
    - Conceptual reference for launcher-level `Compare Results`, MVP scope grouping, summary table, side-by-side 3D comparison, and event-aligned plot composition.
  - `C:/SourceCodes/BoxMotionAnalyzer/.codex-remote-attachments/019ea7d4-f1a5-76e0-bebe-1d5c4b5afed3/c242cca6-d9b2-429c-a78c-c56057d6329a/2-Photo-2.jpg`
    - Denser desktop layout reference for compare workspace structure: left file/settings rail, top comparison summary table, synchronized 3D playback, and event-aligned comparison plot.

## Image Generation Prompt Starters
- Posture illustration:
  `Technical engineering illustration, clean white background, semi-transparent rectangular TV shipping box tilted above a flat floor plane, eight corners labeled C1 to C8 according to local box coordinates: C1(-X,-Y,-Z), C2(+X,-Y,-Z), C3(+X,+Y,-Z), C4(-X,+Y,-Z), C5(-X,-Y,+Z), C6(+X,-Y,+Z), C7(+X,+Y,+Z), C8(-X,+Y,+Z). Highlight the automatically selected reference face facing downward, show beta angle between reference-face normal and downward floor normal, show long direction arrow and short direction arrow on the reference face, show DeltaH vertical bracket between highest and lowest reference-face corners, highlight Cmin lowest corner in red. Minimal labels, no decorative background, precise CAD-like style.`
- Impact illustration:
  `Technical engineering illustration for drop test impact timing, clean white background. Show a tilted transparent box descending toward a floor, with a horizontal time axis below labeled approach, t1-, first impact, later impacts. Mark t1- as the frame just before first impact. Highlight first impact corner C2 touching the floor, then show an impact sequence strip C2 -> {C2,C3} -> C5 with simultaneous contacts grouped in braces. Use simple arrows, clear callouts, restrained colors, CAD-like style.`
- Contact illustration:
  `Technical engineering illustration for contact detection evidence in a box drop test, clean white background. Show a floor line and a small height-versus-time curve for the lowest box corner. Include threshold band near floor, descending approach slope, impact event marker, rebound/turning point, and sustained low plateau region. Next to the plot show a transparent box with one or two corners near the floor. Label ContactState examples: NoContact, Approach, ImpactEvent, SustainedContact. Minimal text, precise engineering diagram style.`

## Later Work: Experiment Comparison GUI
- [ ] Keep the compare window as a launcher-level feature, not as another panel inside Step 2.
- [ ] Confirm the next scope in `drop_result_comparison_plan.md`.
- [ ] Implement first:
  - multiple `.proc` file loading
  - baseline experiment selection
  - comparison target selection
  - summary difference table
  - time-history overlay graph
- [ ] Implement later:
  - side-by-side 3D playback
  - synchronized playback
  - event-based time alignment
- [ ] Reuse Drop Posture descriptor metadata for compare-window labels, tooltips, and metric guide text.
- [ ] Add compare-window tests:
  - loading the same `.proc` twice produces near-zero differences
  - controlled synthetic/fixture differences produce expected metric deltas
