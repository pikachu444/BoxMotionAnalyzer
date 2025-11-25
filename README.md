# Box Motion Analyzer

This is a GUI application for analyzing the motion of a box from motion capture data.

## How to Run

To run the application, execute the `run.py` script from the project root directory:

```bash
python3 run.py
```

## Features

*   **Data Visualization:** Load and visualize motion capture data.
*   **Analysis Pipeline:** Run a data processing pipeline to analyze box motion.
*   **Scenario Export:** Export analysis results to a CSV file.
    *   **Automatic Offset Calculation:** Automatically select the three lowest corners for the analysis scenario.
    *   **Manual Offset Selection:** Manually select three corners.
    *   **Manual Height Input:** Manually specify the height of the selected corners, overriding the calculated values.
