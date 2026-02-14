# Result Item Hierarchy & Naming (Current Baseline)

This document summarizes the current baseline used by the analysis pipeline and GUI result tree.

## 1) Level-1 categories

The multi-header level-1 grouping currently uses:

- `Position`
- `Velocity`
- `Acceleration`
- `Height`-related analysis categories

## 2) Level-2 naming policy

For motion quantities, level-2 naming follows a physical-axis policy:

- `Translation` (`TRN`)
- `Rotation` (`ROT`)

Legacy mixed aliases (for example, `COM` / `BOX_T` / `BOX_R`) are intentionally avoided in new mappings.

## 3) Velocity/Acceleration field families

Current field families in the pipeline include:

- Translation velocity: `T_VX`, `T_VY`, `T_VZ`, `T_V_Norm`
- Rotation velocity: `R_VX`, `R_VY`, `R_VZ`, `R_V_Norm`
- Translation acceleration: `T_AX`, `T_AY`, `T_AZ`, `T_A_Norm`
- Rotation acceleration: `R_AX`, `R_AY`, `R_AZ`, `R_A_Norm`

## 4) Notes

- This file is for alignment/reference so future UI hierarchy changes can be reviewed against a single source of truth.
- If hierarchy policy changes again, update this document in the same PR as mapping and test updates.
