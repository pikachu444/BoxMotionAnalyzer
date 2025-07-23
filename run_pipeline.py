# --- START OF run_pipeline.py ---
import os
import subprocess
import pandas as pd
import sys

# =============================================================================
# USER-CONFIGURABLE BATCH EXECUTION PARAMETERS
# =============================================================================

# --- 1. Dataset and Directory Configuration ---
DATASET_NAMES = ["BOX_65_ISTA_FULL_RAW"]
BASE_INPUT_DIR = "data/raw"  # Use forward slashes for better cross-platform compatibility
BASE_OUTPUT_DIR = "results"

# --- 2. Python Executable and Script Paths ---
PYTHON_EXE = sys.executable  # Use the python executable that runs this script
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))  # Assume scripts are in the same directory

SLICE_RAW_SCRIPT = os.path.join(SCRIPT_DIR, "SliceRawData.py")
ALIGN_INPUT_GEN_SCRIPT = os.path.join(SCRIPT_DIR, "AlignBoxInputGenbyExperiment.py")
SMOOTH_MARKER_SCRIPT = os.path.join(SCRIPT_DIR, "SmootherMarkerData.py")
ALIGN_BOX_MAIN_SCRIPT = os.path.join(SCRIPT_DIR, "AlignBoxMain.py")
CALC_VELOCITY_SCRIPT = os.path.join(SCRIPT_DIR, "CalculateRigidBodyVelocitySmoother.py")
ANALYZE_FRAME_SCRIPT = os.path.join(SCRIPT_DIR, "AnalyzeTransformedFrame.py")

# Path to the new integration script
INTEGRATE_VIS_SCRIPT = os.path.join(SCRIPT_DIR, "IntegrateVisualizationData.py")

# Paths to visualization scripts
PLOT_LAB_FRAME_SCRIPT = os.path.join(SCRIPT_DIR, "PlotResults_Matplotlib_new.py")
PLOT_ANALYSIS_FRAME_SCRIPT = os.path.join(SCRIPT_DIR, "PlotTransformedFrame_new.py")
PYVISTA_VISUALIZER_SCRIPT = os.path.join(SCRIPT_DIR, "InteractiveVisualizer_PyVista.py")

# --- 3. Pipeline Stage Activation Flags ---
# Set these to True to run a stage, or False to skip it.
DO_SLICE_RAW_DATA = True
DO_PARSING = False
DO_SMOOTH_MARKERS = True
DO_POSE_OPTIMIZATION = False
DO_VELOCITY_CALCULATION = False  # True
DO_FRAME_ANALYSIS = False  # True
DO_INTEGRATE_DATA = True  # [NEW] Flag for the new integration step
DO_PLOT_MATPLOTLIB_LAB = True  # Set to False to avoid blocking the pipeline for quick checks
DO_PLOT_MATPLOTLIB_ANALYSIS = False  # Set to False to avoid blocking the pipeline for quick checks
DO_RUN_PYVISTA_VISUALIZER = False  # Set to True to launch the final interactive tool

# --- 4. Stage-Specific Parameters for Batch Execution ---
# For Stage 0: SliceRawData.py ---
SLICE_FILTER_BY = "time"
SLICE_START_VAL = "142"
SLICE_END_VAL = "148"

# For Stage 5: AnalyzeTransformedFrame.py ---
ANALYZE_FRAME_RANGE = "ALL"  # e.g., "ALL", "150", "150 200"

# =============================================================================

def run_command(command_list: list, log_file_path: str) -> bool:
    """
    Executes a command as a subprocess, logs its output, and returns success status.

    Args:
        command_list (list): A list of strings representing the command and its arguments.
        log_file_path (str): Path to the log file.

    Returns:
        bool: True if the command executed successfully (return code 0), False otherwise.
    """
    command_str = ' '.join(f'"{item}"' if ' ' in item else item for item in command_list)
    print(f"  EXECUTING: {command_str}")

    try:
        # Execute the command. Use utf-8 encoding for output.
        process = subprocess.run(
            command_list,
            capture_output=True,
            text=True,
            check=False,
            encoding='utf-8',
            errors='replace'
        )

        # Log the command and its full output.
        log_output = (
            f"\n{'=' * 80}\n"
            f"COMMAND: {command_str}\n"
            f"RETURN CODE: {process.returncode}\n\n"
            f"--- STDOUT ---\n{process.stdout}\n"
        )
        if process.stderr:
            log_output += f"--- STDERR ---\n{process.stderr}\n"

        with open(log_file_path, 'a', encoding='utf-8') as lf:
            lf.write(log_output)

        # Check for success.
        if process.returncode != 0:
            print(f"  [ERROR] Command failed with return code {process.returncode}.")
            print(f"  >> Check log file for details: {log_file_path}")
            return False

        print("  SUCCESS.")
        return True

    except FileNotFoundError:
        error_msg = f"  [ERROR] The command could not be executed. Make sure '{command_list[0]}' is a valid executable and scripts exist."
        print(error_msg, file=sys.stderr)
        with open(log_file_path, 'a', encoding='utf-8') as lf:
            lf.write(f"\n--- FILE NOT FOUND ERROR ---\n{error_msg}\n")
        return False
    except Exception as e:
        error_msg = f"  [ERROR] An unexpected exception occurred: {e}"
        print(error_msg, file=sys.stderr)
        with open(log_file_path, 'a', encoding='utf-8') as lf:
            lf.write(f"\n--- UNEXPECTED EXCEPTION ---\n{error_msg}\n")
        return False

def main():
    """ Main function to orchestrate the entire data processing and visualization pipeline. """
    print("Starting batch processing pipeline...")
    os.makedirs(BASE_OUTPUT_DIR, exist_ok=True)

    for dataset_idx, dataset_name in enumerate(DATASET_NAMES):
        print(f"\n[{dataset_idx + 1}/{len(DATASET_NAMES)}] Processing Dataset: {dataset_name}")
        print("-" * 80)

        # --- Setup directories and log file for the current dataset ---
        dataset_output_dir = os.path.join(BASE_OUTPUT_DIR, dataset_name)
        os.makedirs(dataset_output_dir, exist_ok=True)

        log_file = os.path.join(dataset_output_dir, f"{dataset_name}_pipeline_log.txt")
        with open(log_file, 'w', encoding='utf-8') as lf:
            lf.write(f"Pipeline Log for Dataset: {dataset_name}\n")
            lf.write(f"Timestamp: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

        # --- Dynamically define file paths and suffixes ---
        file_suffix = ""
        initial_input_csv = os.path.join(BASE_INPUT_DIR, f"{dataset_name}.csv")

        # --- STAGE 0: Slice Raw Data (Optional) ---
        input_for_parsing = initial_input_csv
        if DO_SLICE_RAW_DATA:
            print("[Stage 0/9] Slicing Raw Data...")
            file_suffix = f"_sliced_by_{SLICE_FILTER_BY}_{SLICE_START_VAL}_{SLICE_END_VAL}"
            sliced_raw_csv = os.path.join(dataset_output_dir, f"{dataset_name}{file_suffix}.csv")
            cmd = [PYTHON_EXE, SLICE_RAW_SCRIPT, initial_input_csv, sliced_raw_csv, "--filter_by", SLICE_FILTER_BY,
                   "--start_val", SLICE_START_VAL, "--end_val", SLICE_END_VAL]
            if not run_command(cmd, log_file):
                sys.exit(f"PIPELINE HALTED at Stage 0 for {dataset_name}.")
            input_for_parsing = sliced_raw_csv
        else:
            print("[Stage 0/9] Slicing Raw Data... SKIPPED")

        # --- Define paths for all subsequent stages ---
        parsed_csv = os.path.join(dataset_output_dir, f"{dataset_name}{file_suffix}_parsed.csv")
        smoothed_markers_csv = os.path.join(dataset_output_dir, f"{dataset_name}{file_suffix}_smoothed_markers.csv")
        poses_csv = os.path.join(dataset_output_dir, f"{dataset_name}{file_suffix}_poses.csv")
        kinematics_integrated_csv = os.path.join(dataset_output_dir, f"{dataset_name}{file_suffix}_kinematics_integrated.csv")
        analysis_frame_data_csv = os.path.join(dataset_output_dir, f"{dataset_name}{file_suffix}_analysis_frame_data.csv")
        # [NEW] The single source of truth for all visualizations
        visualization_integrated_csv = os.path.join(dataset_output_dir, f"{dataset_name}{file_suffix}_visualization_integrated.csv")

        # --- Pipeline Execution ---
        if DO_PARSING and not run_command([PYTHON_EXE, ALIGN_INPUT_GEN_SCRIPT, input_for_parsing, parsed_csv],
                                        log_file): sys.exit(f"PIPELINE HALTED at Stage 1 for {dataset_name}.")
        if DO_SMOOTH_MARKERS and not run_command([PYTHON_EXE, SMOOTH_MARKER_SCRIPT, parsed_csv, smoothed_markers_csv],
                                                log_file): sys.exit(f"PIPELINE HALTED at Stage 2 for {dataset_name}.")
        if DO_POSE_OPTIMIZATION and not run_command(
            [PYTHON_EXE, ALIGN_BOX_MAIN_SCRIPT, "--input_csv", smoothed_markers_csv, "--output_csv", poses_csv],
            log_file): sys.exit(f"PIPELINE HALTED at Stage 3 for {dataset_name}.")
        if DO_VELOCITY_CALCULATION and not run_command(
            [PYTHON_EXE, CALC_VELOCITY_SCRIPT, "--input_csv_path", poses_csv, "--output_csv_path",
            kinematics_integrated_csv], log_file): sys.exit(f"PIPELINE HALTED at Stage 4 for {dataset_name}.")
        if DO_FRAME_ANALYSIS and not run_command(
            [PYTHON_EXE, ANALYZE_FRAME_SCRIPT, "--kinematics_csv", kinematics_integrated_csv,
            "--output_transformed_data_csv", analysis_frame_data_csv, "--frame_range"] + ANALYZE_FRAME_RANGE.split(),
            log_file): sys.exit(f"PIPELINE HALTED at Stage 5 for {dataset_name}.")

        # [NEW] Stage 6: Data Integration
        if DO_INTEGRATE_DATA:
            print("\n[Stage 6/9] Integrating Data for Visualization...")
            cmd = [PYTHON_EXE, INTEGRATE_VIS_SCRIPT,
                "--kinematics_csv", kinematics_integrated_csv,
                "--markers_csv", smoothed_markers_csv,
                "--transformed_csv", analysis_frame_data_csv,
                "--output_csv", visualization_integrated_csv]
            if not run_command(cmd, log_file): sys.exit(f"PIPELINE HALTED at Stage 6 for {dataset_name}.")
        else:
            print("\n[Stage 6/9] Integrating Data... SKIPPED")

        # [MODIFIED] Stage 7: Matplotlib Visualization (now uses the integrated file)
        if DO_PLOT_MATPLOTLIB_LAB:
            print("\n[Stage 7a/9] Plotting with Matplotlib (Lab Frame)...")
            cmd = [PYTHON_EXE, PLOT_LAB_FRAME_SCRIPT, "--input_csv", visualization_integrated_csv]
            if not run_command(cmd, log_file): print(f"Warning: Matplotlib plot for Lab Frame was closed or failed.")
        else:
            print("\n[Stage 7a/9] Plotting (Lab Frame)... SKIPPED")

        if DO_PLOT_MATPLOTLIB_ANALYSIS:
            print("\n[Stage 7b/9] Plotting with Matplotlib (Analysis Frame)...")
            cmd = [PYTHON_EXE, PLOT_ANALYSIS_FRAME_SCRIPT, "--input_csv", visualization_integrated_csv]
            if not run_command(cmd, log_file):
                print(f"Warning: Matplotlib plot for Analysis Frame was closed or failed.")
        else:
            print("\n[Stage 7b/9] Plotting (Analysis Frame)... SKIPPED")

        # Stage 8: PyVista Interactive Visualization
        if DO_RUN_PYVISTA_VISUALIZER:
            print("\n[Stage 8/9] Running PyVista Interactive Visualizer...")
            cmd = [PYTHON_EXE, PYVISTA_VISUALIZER_SCRIPT, "--input_csv", visualization_integrated_csv]
            if not run_command(cmd, log_file):
                print(f"Warning: PyVista visualizer was closed or failed.")
        else:
            print("\n[Stage 8/9] Running PyVista Visualizer... SKIPPED")

        print(f"\n--- Successfully finished processing dataset: {dataset_name} ---")

    print("\n" + "=" * 80)
    print("All datasets processed successfully (or halted on first error).")
    print("=" * 80)

if __name__ == "__main__":
    main()

# --- END OF MODIFIED FILE run_pipeline.py ---