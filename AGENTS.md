# Agent Instructions for Box Motion Analyzer GUI Project

This document provides essential information for any AI agent working on this project. It serves as a guide to ensure consistency and adherence to the project goals.

## 1. Project Goal

The primary objective is to convert the existing script-based data analysis pipeline into a user-friendly GUI application using **PySide6**. The application should allow users to load data, interactively select an analysis range, and export the results, all without editing any code.

## 2. Core Design Document

All development must be based on the finalized design outlined in the **`design_proposal/software_design_document.md`**. This document is the single source of truth for all architectural and functional specifications.

## 3. Key Technologies

- **GUI Framework:** PySide6
- **Data Handling:** Pandas
- **Plotting:** PyQtGraph or Matplotlib (integrated with PySide6)

## 4. Core Implementation Principles

- **Non-Destructive Slicing:** When a user selects a time range on the graph, the original `RawData` DataFrame in memory is **not** modified. The slicing operation happens in-memory only when the analysis pipeline is executed, using the smaller, sliced data for performance.
- **Component-Based Architecture:** The code must follow the defined component structure (`MainApp`, `DataLoader`, `PlotManager`, `PipelineController`) to maintain separation of concerns.

## 5. Current Project Status

- **Phase:** Implementation
- **Status:** All design and planning phases are complete. Ready to begin implementation of the GUI application based on the design documents.
- **Next Step:** Start implementing the basic GUI skeleton (`MainApp`) as per the approved implementation plan.

## 6. Technical Notes & Workarounds

- **Qt Plugin Issues:** When running the PySide6 application in some environments, "Could not load the Qt platform plugin" errors can occur. To mitigate this, run the application with the `offscreen` platform plugin:
  ```bash
  QT_QPA_PLATFORM=offscreen python src/main_app.py
  ```
