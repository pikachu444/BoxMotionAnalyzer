# run_pipeline.py 상단 예시

import os
import subprocess
import shutil # For directory operations if needed

# ==============================================================================
# USER-CONFIGURABLE BATCH EXECUTION PARAMETERS
# ==============================================================================

# --- 1. Dataset and Directory Configuration ---
# List of dataset names to process (without _raw.csv suffix)
DATASET_NAMES = ["DatasetA", "DatasetB", "Trial001"] 

# Base directory where original raw CSV files are located
BASE_INPUT_DIR = "data/raw_experiment_data" 

# Base directory where all processed results will be saved
BASE_OUTPUT_DIR = "results/pipeline_output" 

# --- 2. Python Executable and Script Paths ---
# Adjust if your python interpreter is named differently or scripts are elsewhere
PYTHON_EXE = "python3" # or "python"
SCRIPT_DIR = "." # Assuming all processing scripts are in the same dir as run_pipeline.py
                 # Or specify: "scripts/"

ALIGN_INPUT_GEN_SCRIPT = os.path.join(SCRIPT_DIR, "AlignBoxInputGenbyExperiment.py")
SMOOTH_MARKER_SCRIPT = os.path.join(SCRIPT_DIR, "SmoothMarkerData.py")
ALIGN_BOX_MAIN_SCRIPT = os.path.join(SCRIPT_DIR, "AlignBoxMain.py")
CALC_VELOCITY_SCRIPT = os.path.join(SCRIPT_DIR, "CalculateRigidBodyVelocity.py")
ANALYZE_FRAME_SCRIPT = os.path.join(SCRIPT_DIR, "AnalyzeTransformedFrame.py")
PLOT_TRANSFORMED_SCRIPT = os.path.join(SCRIPT_DIR, "PlotTransformedFrame.py")
# SLICE_RAW_SCRIPT = os.path.join(SCRIPT_DIR, "SliceRawData.py") # If SliceRawData.py is developed

# --- 3. Pipeline Stage Activation Flags ---
# Set to True to run the stage, False to skip
DO_SLICE_RAW_DATA = True         # If SliceRawData.py is implemented
DO_PARSING = True
DO_SMOOTH_MARKERS = True
DO_POSE_OPTIMIZATION = True
DO_VELOCITY_CALCULATION = True
DO_FRAME_ANALYSIS = True         # For AnalyzeTransformedFrame.py
DO_PLOT_TRANSFORMED_SAVE = True  # For PlotTransformedFrame.py (image saving mode)

# --- 4. Stage-Specific Parameters for Batch Execution ---

# Parameters for SliceRawData.py (if DO_SLICE_RAW_DATA is True)
# These could be dataset-specific if managed differently (e.g., dict per dataset)
SLICE_FILTER_BY = "frame"  # 'frame' or 'time'
SLICE_START_VAL = "1"      # String, will be converted by SliceRawData.py
SLICE_END_VAL = "500"     # String

# Parameters for CalculateRigidBodyVelocity.py
# These are for CLI args of CalculateRigidBodyVelocity.py.
# Internal params (like spline factors) are in CalculateRigidBodyVelocity.py itself.
CALC_VEL_METHOD_OVERRIDE = "spline" # 'spline', 'finite_difference', or None to use script's default
CALC_VEL_FD_ANG_METHOD = "quaternion" # 'matrix' or 'quaternion'

# Parameters for AnalyzeTransformedFrame.py (if DO_FRAME_ANALYSIS is True)
ANALYZE_FRAME_RANGE = "100 200" # "ALL", "single_frame_num", "start_frame end_frame"

# Parameters for PlotTransformedFrame.py (if DO_PLOT_TRANSFORMED_SAVE is True)
# This assumes we are saving images, not showing interactive plots in batch.
PLOT_ANIMATE_FLAG_FOR_SAVE = True # Use --animate for saving all frames in range
PLOT_TARGET_FRAME_FOR_SAVE = None # For static single image, e.g., 100. If None and animate, all frames.
                                  # This needs careful coordination with PLOT_ANIMATE_FLAG_FOR_SAVE
                                  # Simpler: always use --animate if saving multiple images from AnalyzeTransformedFrame output.
PLOT_HIDE_LABELS_FLAG = False
PLOT_LIN_VEL_SCALE = 0.2
PLOT_ANG_VEL_SCALE = 0.2
# ==============================================================================

def run_command(command_list, log_file_path=None):
    """Executes a command list using subprocess and handles errors."""
    command_str = ' '.join(command_list)
    print(f"  Executing: {command_str}")
    try:
        process = subprocess.run(command_list, capture_output=True, text=True, check=False) # check=False to handle error manually
        
        log_output = f"\n--- Command: {command_str} ---\n"
        log_output += f"Return Code: {process.returncode}\n"
        log_output += f"Stdout:\n{process.stdout}\n"
        if process.stderr:
            log_output += f"Stderr:\n{process.stderr}\n"

        if log_file_path:
            with open(log_file_path, 'a', encoding='utf-8') as lf:
                lf.write(log_output)

        if process.returncode != 0:
            print(f"  ERROR: Command failed with return code {process.returncode}.")
            print(f"  Stderr: {process.stderr.strip()}")
            return False
        return True
    except FileNotFoundError:
        print(f"  ERROR: Script or Python executable not found for command: {command_str}")
        if log_file_path:
            with open(log_file_path, 'a', encoding='utf-8') as lf:
                lf.write(f"\n--- ERROR: Script not found for command: {command_str} ---\n")
        return False
    except Exception as e:
        print(f"  ERROR: An unexpected error occurred while running command: {command_str}")
        print(f"  Exception: {e}")
        if log_file_path:
            with open(log_file_path, 'a', encoding='utf-8') as lf:
                lf.write(f"\n--- ERROR: Unexpected exception for command: {command_str}\n{e}\n ---\n")
        return False

def main():
    print("Starting batch processing pipeline...")
    os.makedirs(BASE_OUTPUT_DIR, exist_ok=True)

    for dataset_idx, dataset_name in enumerate(DATASET_NAMES):
        print(f"\nProcessing Dataset {dataset_idx + 1}/{len(DATASET_NAMES)}: {dataset_name}")
        print("==============================================================================")

        dataset_output_dir = os.path.join(BASE_OUTPUT_DIR, dataset_name)
        os.makedirs(dataset_output_dir, exist_ok=True)
        
        log_file = os.path.join(dataset_output_dir, f"{dataset_name}_pipeline_log.txt")
        # Clear log file for this dataset run
        with open(log_file, 'w', encoding='utf-8') as lf:
            lf.write(f"Pipeline Log for Dataset: {dataset_name}\n")
            lf.write(f"Timestamp: {pd.Timestamp.now()}\n")


        # --- Define file paths for this dataset ---
        # Raw input (potentially sliced later)
        current_raw_csv_for_parsing = os.path.join(BASE_INPUT_DIR, f"{dataset_name}_raw.csv")

        # Output of SliceRawData (if used)
        sliced_raw_csv = os.path.join(dataset_output_dir, f"{dataset_name}_sliced_raw.csv")
        
        # Output of AlignBoxInputGen (parsing)
        parsed_csv = os.path.join(dataset_output_dir, f"{dataset_name}_parsed.csv")
        
        # Output of SmoothMarkerData
        smoothed_markers_csv = os.path.join(dataset_output_dir, f"{dataset_name}_smoothed_markers.csv")
        
        # Output of AlignBoxMain (pose optimization)
        poses_csv = os.path.join(dataset_output_dir, f"{dataset_name}_poses.csv")
        
        # Output of CalculateRigidBodyVelocity (integrated kinematics)
        kinematics_integrated_csv = os.path.join(dataset_output_dir, f"{dataset_name}_kinematics_integrated.csv")
        
        # Output of AnalyzeTransformedFrame
        transformed_data_csv = os.path.join(dataset_output_dir, f"{dataset_name}_transformed_data.csv")
        
        # Output directory for PlotTransformedFrame images
        plot_transformed_images_base_dir = dataset_output_dir # PlotResults will be created under this by the script

        # --- Pipeline Stage Execution ---
        success_flag = True

        # STAGE 0: Slice Raw Data (Optional)
        if success_flag and DO_SLICE_RAW_DATA:
            print("\n--- Stage 0: Slicing Raw Data ---")
            # This assumes SliceRawData.py is implemented and available
            # cmd_slice = [PYTHON_EXE, SLICE_RAW_SCRIPT, 
            #              os.path.join(BASE_INPUT_DIR, f"{dataset_name}_raw.csv"), # Original raw
            #              sliced_raw_csv,
            #              "--filter_by", SLICE_FILTER_BY,
            #              "--start_val", SLICE_START_VAL,
            #              "--end_val", SLICE_END_VAL]
            # success_flag = run_command(cmd_slice, log_file)
            # if success_flag:
            #     current_raw_csv_for_parsing = sliced_raw_csv # Update input for next stage
            # else:
            #     print(f"Error in Slicing Raw Data for {dataset_name}. Halting pipeline for this dataset.")
            #     # According to user: "오류 발생시 중단" - so, break or exit
            #     # For now, let's make it exit the whole batch
            #     print("Batch processing halted due to error.")
            #     return 
            print("SliceRawData.py is not yet implemented. Using original raw CSV for parsing.")


        # STAGE 1: Parsing Raw Data
        if success_flag and DO_PARSING:
            print("\n--- Stage 1: Parsing Raw Data ---")
            cmd_parse = [PYTHON_EXE, ALIGN_INPUT_GEN_SCRIPT, current_raw_csv_for_parsing, parsed_csv]
            success_flag = run_command(cmd_parse, log_file)
            if not success_flag: print("Batch processing halted due to error."); return

        # STAGE 2: Smoothing Marker Data
        if success_flag and DO_SMOOTH_MARKERS:
            print("\n--- Stage 2: Smoothing Marker Data ---")
            cmd_smooth_markers = [PYTHON_EXE, SMOOTH_MARKER_SCRIPT, parsed_csv, smoothed_markers_csv]
            success_flag = run_command(cmd_smooth_markers, log_file)
            if not success_flag: print("Batch processing halted due to error."); return

        # STAGE 3: Pose Optimization
        if success_flag and DO_POSE_OPTIMIZATION:
            print("\n--- Stage 3: Pose Optimization (AlignBoxMain) ---")
            cmd_pose = [PYTHON_EXE, ALIGN_BOX_MAIN_SCRIPT, 
                        "--input_csv", smoothed_markers_csv, 
                        "--output_csv", poses_csv]
            success_flag = run_command(cmd_pose, log_file)
            if not success_flag: print("Batch processing halted due to error."); return

        # STAGE 4: Velocity Calculation
        if success_flag and DO_VELOCITY_CALCULATION:
            print("\n--- Stage 4: Velocity Calculation ---")
            cmd_vel = [PYTHON_EXE, CALC_VELOCITY_SCRIPT, 
                       poses_csv, 
                       kinematics_integrated_csv] # output_csv_path is now the integrated one
            if CALC_VEL_METHOD_OVERRIDE: # Only add if specified, else script uses its internal default
                cmd_vel.extend(["--velocity_method_override", CALC_VEL_METHOD_OVERRIDE])
            # fd_angular_method always has a default in CalculateRigidBodyVelocity.py's argparse
            # but we can pass the batch config's value to ensure it.
            cmd_vel.extend(["--fd_angular_method", CALC_VEL_FD_ANG_METHOD])
            
            success_flag = run_command(cmd_vel, log_file)
            if not success_flag: print("Batch processing halted due to error."); return

        # STAGE 5: Frame Analysis (AnalyzeTransformedFrame)
        if success_flag and DO_FRAME_ANALYSIS:
            print("\n--- Stage 5: Frame Analysis (Transformed Coordinates) ---")
            cmd_analyze = [PYTHON_EXE, ANALYZE_FRAME_SCRIPT,
                           "--kinematics_csv", kinematics_integrated_csv,
                           "--output_transformed_data_csv", transformed_data_csv,
                           "--frame_range"] + ANALYZE_FRAME_RANGE.split() # split() handles "ALL" or "start end"
            success_flag = run_command(cmd_analyze, log_file)
            if not success_flag: print("Batch processing halted due to error."); return
            
        # STAGE 6: Plot Transformed Frame (Save Images)
        if success_flag and DO_PLOT_TRANSFORMED_SAVE:
            print("\n--- Stage 6: Plotting Transformed Frame (Saving Images) ---")
            cmd_plot_transformed = [PYTHON_EXE, PLOT_TRANSFORMED_SCRIPT,
                                    "--transformed_data_csv", transformed_data_csv,
                                    "--save_images", # Activate saving
                                    "--base_save_dir", plot_transformed_images_base_dir] # Output under dataset_output_dir/PlotResults/
            if PLOT_ANIMATE_FLAG_FOR_SAVE: # If saving all frames as a sequence
                cmd_plot_transformed.append("--animate")
            elif PLOT_TARGET_FRAME_FOR_SAVE is not None: # If saving a single static frame
                cmd_plot_transformed.extend(["--target_frame_number", str(PLOT_TARGET_FRAME_FOR_SAVE)])
            # Add other plotting args if needed from batch config
            if PLOT_HIDE_LABELS_FLAG: cmd_plot_transformed.append("--hide_labels")
            cmd_plot_transformed.extend(["--lin_vel_scale", str(PLOT_LIN_VEL_SCALE)])
            cmd_plot_transformed.extend(["--ang_vel_scale", str(PLOT_ANG_VEL_SCALE)])

            success_flag = run_command(cmd_plot_transformed, log_file)
            # For plotting, an error might not need to halt the entire batch for other datasets
            # But based on "오류 발생시 중단", we will halt.
            if not success_flag: print("Batch processing halted due to error."); return

        print(f"--- Finished processing dataset: {dataset_name} ---")

    print("\n==============================================================================")
    print("All datasets processed successfully (or halted on first error).")
    print("==============================================================================")

if __name__ == "__main__":
    # Check if config.py can be imported by the pipeline script itself, as a pre-check
    try:
        import config as pipeline_config_check
        print(f"Pipeline: Successfully imported config.py (BOX_DIMS: {pipeline_config_check.BOX_DIMS[0]}...).")
    except ImportError:
        print("Pipeline CRITICAL ERROR: config.py not found. Ensure it's in the Python path.")
        exit(1)
    except AttributeError as e_cfg_pipe:
        print(f"Pipeline CRITICAL ERROR: Attribute {e_cfg_pipe} missing in config.py.")
        exit(1)
        
    main()