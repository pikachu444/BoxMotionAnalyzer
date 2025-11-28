# Box Motion Analyzer

This project is a GUI application for analyzing and visualizing box motion data. It consists of two main components: **Data Analysis** and **3D Visualization**.

## Project Structure

The codebase has been refactored into a modular structure:

- **`src/`**: Source code root
  - **`analysis/`**: Logic for data processing, parsing, and pipeline control.
  - **`visualization/`**: 3D visualization using PyVista and Qt.
  - **`config/`**: Centralized configuration files (e.g., `config_visualization.py`).
  - **`utils/`**: Shared utility scripts.
  - **`launcher.py`**: The unified window for launching Analysis or Visualization tools.
  - **`main.py`**: The main entry point of the application.

- **`docs/`**: Documentation files (Developer guides, legacy READMEs, etc.).
- **`data/`**: Directory for input/output CSV data.
- **`tests/`**: Test suite (includes structural verification and integration tests).

## How to Run

### Requirements
Install dependencies using pip:
```bash
pip install -r requirements.txt
```

### Launch the Application
Run the unified entry point from the project root:
```bash
python src/main.py
```
This will open the **Launcher Window**, where you can choose between "Data Processing" and "3D Visualization".

## How to Build

To create a standalone executable (using PyInstaller):

```bash
python build.py [onedir|onefile]
```
- `onedir`: Creates a folder with the executable (faster build, faster startup).
- `onefile`: Creates a single `.exe` file (easier distribution, slower startup).

On Windows, you can also use:
```batch
build.bat
```

## Testing

Run the integration tests to verify the pipeline:
```bash
python -m unittest tests/test_pipeline_integration.py
```
