# --- START OF FILE IntegrateVisualizationData.py ---
import argparse
import pandas as pd
import sys
import os

def integrate_data_for_visualization(kinematics_path: str, markers_path: str, transformed_path: str, output_path: str) -> None:
    """
    Integrates data from three distinct CSV sources into a single, unified CSV file suitable for all visualization purposes.

    This function merges data based on 'FrameNumber', ensuring that all relevant
    information (lab-frame kinematics, marker positions, and analysis-frame data)
    for each frame is consolidated into one row.

    Args:
        kinematics_path (str):
            Path to the kinematics CSV file (e.g., '_kinematics_integrated.csv').
            This file contains pose, corner coordinates, and calculated velocities.
        markers_path (str):
            Path to the smoothed markers CSV file (e.g., '_smoothed_markers.csv').
            This file contains the world coordinates of each marker.
        transformed_path (str):
            Path to the transformed analysis data CSV (e.g., '_analysis_frame_data.csv').
            This file contains data represented in the box's local coordinate system.
        output_path (str):
            Path where the final, integrated CSV file will be saved.

    Returns:
        None. The result is saved to a file. The script will exit with an error
        code if the process fails.
    """
    print("--- Starting Data Integration for Visualization ---")

    # A dictionary to hold dataframes, loaded one by one with validation.
    dataframes = {}

    # Define the input files and their corresponding keys for the dictionary.
    input_files = {
        'kinematics': kinematics_path,
        'markers': markers_path,
        'transformed': transformed_path
    }

    # Step 1: Load all required dataframes with robust error handling.
    for key, path in input_files.items():
        print(f"-> Loading '{key}' data from: {os.path.basename(path)}")
        if not os.path.exists(path):
            print(f"   [ERROR] File not found: {path}", file=sys.stderr)
            sys.exit(1)
        
        try:
            df = pd.read_csv(path)
            if 'FrameNumber' not in df.columns:
                print(f"   [ERROR] 'FrameNumber' column is missing in {path}. This column is essential for merging.", file=sys.stderr)
                sys.exit(1)
            dataframes[key] = df
            print(f"   ...Loaded {len(df)} rows.")
        except pd.errors.EmptyDataError:
            print(f"   [WARNING] The file {path} is empty. The final output may lack '{key}' data.", file=sys.stderr)
            # Create an empty DataFrame with just the merge key to allow the process to continue.
            dataframes[key] = pd.DataFrame({'FrameNumber': []})
        except Exception as e:
            print(f"   [ERROR] Failed to read {path} due to an unexpected error: {e}", file=sys.stderr)
            sys.exit(1)

    # Step 2: Merge the dataframes sequentially.
    # We use an 'outer' join to ensure that no frame is lost, even if it only
    # exists in one of the input files.
    print("\n-> Merging all data sources based on 'FrameNumber'...")

    # Start with the kinematics dataframe as the base.
    df_integrated = dataframes['kinematics']

    # Merge with markers data.
    # Suffixes are added to resolve potential column name conflicts (e.g., 'Time').
    df_integrated = pd.merge(df_integrated, dataframes['markers'], on='FrameNumber', how='outer', suffixes=('', '_markers'))
    print("   ...Merged kinematics and markers.")

    # Merge the result with transformed data.
    df_integrated = pd.merge(df_integrated, dataframes['transformed'], on='FrameNumber', how='outer', suffixes=('', '_transformed'))
    print("   ...Merged with transformed analysis data.")

    # Step 3: Clean up redundant columns created during the merge.
    # The 'Time' column from the base 'kinematics' dataframe is considered the authoritative one.
    cols_to_drop = [col for col in df_integrated.columns if col.endswith('_markers') or col.endswith('_transformed')]
    if cols_to_drop:
        print(f"\n-> Cleaning up redundant columns: {cols_to_drop}")
        df_integrated.drop(columns=cols_to_drop, inplace=True)

    # Step 4: Sort the final dataframe by 'FrameNumber' to ensure chronological order.
    # This is crucial for animations and time-series plots.
    # Handle potential non-numeric FrameNumber values gracefully.
    try:
        df_integrated['FrameNumber'] = pd.to_numeric(df_integrated['FrameNumber'])
        df_integrated.sort_values(by='FrameNumber', inplace=True)
        print("-> Sorted final data by 'FrameNumber'.")
    except ValueError:
        print("   [WARNING] 'FrameNumber' column contains non-numeric values. Sorting as strings.", file=sys.stderr)
        df_integrated.sort_values(by='FrameNumber', inplace=True)

    # Step 5: Save the final integrated dataframe to the output path.
    output_dir = os.path.dirname(output_path)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
        
    print(f"\n-> Saving integrated data to: {output_path}")
    try:
        df_integrated.to_csv(output_path, index=False, float_format='%.8f')
        print("\n--- Data Integration Successful ---")
        print(f"   Final integrated file contains {len(df_integrated)} rows and {len(df_integrated.columns)} columns.")
    except IOError as e:
        print(f"   [ERROR] Could not write to output file {output_path}. Check permissions and path. Error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"   [ERROR] An unexpected error occurred while saving the file: {e}", file=sys.stderr)
        sys.exit(1)

# --- END OF FILE IntegrateVisualizationData.py ---