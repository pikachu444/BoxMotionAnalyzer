# Synthetic marker export layout

Last Reviewed: 2026-09-18

Issue #114 adds one optional window from Simulation's fixed action row. Existing
Run and Run all presets continue to export direct synthetic `.proc` results.

```text
Simulation                         [Run] [Run all presets] [Marker CSV…]

Synthetic marker CSV                                  1000 × 700
+----------------------------------------------------------------+
| Layout [Public example: 18 markers v] [Import JSON…]             |
| Box: 200 × 120 × 80 mm   [ ] Use layout dimensions               |
|                                                                |
|                    box / markers / face legend                  |
|                    local X/Y/Z preview                          |
|                                                                |
| > Faults (default None)                                         |
|   Kind / Physical or Solved / start–end seconds / axis / seed    |
| Output name [synthetic_markers________________________]         |
| Synthetic observations. Separate truth files for evaluation.    |
| [progress or last result filename]                              |
| [Generate…] [Cancel]                         [Open in Step 1]     |
+----------------------------------------------------------------+
```

Profile coordinates remain absolute mm. Imported files use the existing profile
validator, and are labeled Imported, never approved experimental standards.
When the chosen layout dimensions differ from the original Simulation box,
the operator must explicitly choose those dimensions for this export. The
original Simulation controls are not overwritten. Clearance, initial rotation,
mass, COM offset, duration and contact inputs are captured when the window opens
and summarized in a tooltip. The existing direct corner-noise option is separate
from marker faults. No marker editor or registration workflow is added.

Generation runs in a cancellable worker. It uses the existing MuJoCo recording
path, a shared history adapter and `write_observations`. Faults are translated
from seconds to actual recorded sample indices, then validated by the existing
API. No custom fault algebra is added. The output is a new directory selected
under a parent folder; existing names are refused. A private staging directory
is published only after successful generation, and cancelled/failed staging is
removed without touching earlier results.

Only `observed.csv` is passed to a new Step 1 window. Truth pose/marker CSVs and
the evaluator manifest remain separate files and are not analysis inputs. A
new analysis window preserves any work already open elsewhere. Cancel/close
requests cooperative cancellation and waits for the worker to stop; it never
terminates a thread or opens a partial export.

Preimplementation review checks: fixed actions visible at 1510×800 / DPR1.25,
preview and dimensions agree, examples/imports are distinct, faults OFF, local
half-turns use the solved channel, no silently rescaled layout, and only the
successful observed path is handed off. Implementation and runtime evidence
are recorded in `../simulation.md` and the #114 PR.

The implemented window was independently reviewed. The real Qt evidence uses
1000×700 for this dialog and 1510×800 for Step 1 at measured DPR 1.25. The face
legend sits outside the box axes. Long imported IDs and output names retain the
fixed actions. Five final GUI cases passed; the related regression run passed
60 tests and six subtests. Independent core/direct/corruption and GUI checks
passed 55 tests. CI completion and merge remain PR-level evidence.
