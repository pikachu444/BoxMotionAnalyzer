# Code Structure Analysis: Data Column Naming & Consistency

## 1. Problem Identification (The "Missing Column" Issue)

During the refactoring process, a discrepancy arose between the column names generated during analysis and the column names expected by the visualization/export UI. This led to data not appearing in the selection tree.

### Core Issues

1.  **Implicit Transformation (Hidden Coupling)**
    *   **Generation:** The analysis module (`FrameAnalyzer.py`) generates columns using keys from `AnalysisCols` (e.g., `CoM_Vx_Ana`).
    *   **Transformation:** The `DataLoader` uses `src/utils/header_converter.py` to parse flat CSVs into Multi-Header DataFrames. This process uses Regular Expressions to **rename** columns.
        *   Example: `CoM_Vx_Ana` is transformed into `(Velocity, CoM, VX_Ana)`.
    *   **Consumption:** The UI (`WidgetResultsAnalyzer.py`) and Config (`DISPLAY_RESULT_COLUMNS`) expected the original names or explicitly hardcoded transformed names. When we tried to use `AnalysisCols` constants to fix hardcoding, the UI looked for `CoM_Vx_Ana`, but the DataFrame actually contained `VX_Ana` in the 3rd level.

2.  **Double Definition (Fragmented Truth)**
    *   `src/config/data_columns.py` defines constants for generation (`AnalysisCols.COM_VX_ANA` = "CoM_Vx_Ana") and constants for consumption (`HeaderL3.VX` = "VX").
    *   There was no programmatic link ensuring that the transformation of `AnalysisCols` results in a valid `HeaderL3` constant.
    *   Developers must manually ensure that `header_converter.py` regex outputs match `HeaderL3` definitions.

3.  **Traceability**
    *   The transformation logic lives in regex patterns within `utils/header_converter.py`, making it difficult to statically analyze where a column name "goes" or where it "came from".

## 2. Proposed Countermeasures (Long-term Improvements)

To prevent such issues in the future and improve maintainability:

### A. Explicit Mapping (Remove Regex Magic)
Instead of relying on regex pattern matching to guess the hierarchy, define the hierarchy explicitly at the source.

*   **Action:** Redefine `AnalysisCols` to store the full Multi-Index tuple, or a mapping dictionary.
    ```python
    # Future AnalysisCols
    COM_VX_ANA = ("Velocity", "CoM", "VX_Ana")
    ```
*   **Benefit:** The conversion becomes a direct lookup or is unnecessary. Generation and Consumption share the exact same key.

### B. Consistent Naming (Remove Rename Step)
If the analysis produces "CoM_Vx_Ana", the final output should ideally keep that name or use it consistently.

*   **Action:** Update `FrameAnalyzer` to output columns named `VX_Ana` directly if that is the desired final key.
*   **Benefit:** Removes the need for the `header_converter` to rename columns, reducing complexity.

### C. Type Safety / Schema Validation
Use a schema definition system (like Pydantic or a custom registry) that enforces valid column names.

*   **Action:** Create a registry of allowed columns. Both the Producer (Analysis) and Consumer (UI) must register their columns against this registry.
*   **Benefit:** Mismatches are caught at startup or test time, not at runtime when a user clicks a button.

## 3. Summary
The current fix (defining `HeaderL3.VX_ANA` constants) is a necessary bridge. However, the underlying architectural tension is the **implicit renaming** of data columns between the Analysis and Visualization layers. Flattening this logic or making it explicit is the recommended path forward.
