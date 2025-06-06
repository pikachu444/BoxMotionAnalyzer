# --- START OF FILE AnalyzeTransformedFrame.py ---
import argparse
import numpy as np
import pandas as pd
from scipy.spatial.transform import Rotation

# --- Configuration Loading ---
import config
LOCAL_BOX_CORNERS = config.LOCAL_BOX_CORNERS
WORLD_VERTICAL_AXIS_INDEX = config.WORLD_VERTICAL_AXIS_INDEX
FLOOR_LEVEL = config.FLOOR_LEVEL
# BOX_DIMS = config.BOX_DIMS # For context or potential future use

def get_lab_floor_params(vertical_axis_idx, floor_level):
    """Defines the floor plane (normal and a point) in the lab/world coordinate system."""
    n_floor_lab = np.zeros(3)
    n_floor_lab[vertical_axis_idx] = 1.0
    p_floor_lab = np.zeros(3)
    p_floor_lab[vertical_axis_idx] = floor_level
    return n_floor_lab, p_floor_lab

def transform_vector(vector_lab, R_ana_from_lab):
    """Transforms a vector from lab to analysis frame (rotation only)."""
    return R_ana_from_lab @ vector_lab

def transform_point(point_lab, R_ana_from_lab, T_box_center_lab):
    """Transforms a point from lab to analysis frame."""
    # p_ana = R_ana_from_lab @ (p_lab - T_box_center_lab)
    return R_ana_from_lab @ (point_lab - T_box_center_lab)

def process_single_frame(frame_row, vertical_axis_idx_config, floor_level_config, local_box_corners_config):
    """Processes a single frame of data to get transformed values."""
    processed_data = {}

    # 1. Extract Lab Frame Data
    try:
        T_box_lab = frame_row[['Box_Tx', 'Box_Ty', 'Box_Tz']].values.astype(float)
        rv_box_lab = frame_row[['Box_Rx', 'Box_Ry', 'Box_Rz']].values.astype(float)
        v_com_lab = frame_row[['CoM_Vx', 'CoM_Vy', 'CoM_Vz']].values.astype(float)
        omega_w_lab = frame_row[['AngVel_Wx', 'AngVel_Wy', 'AngVel_Wz']].values.astype(float)
    except KeyError as e:
        raise ValueError(f"Missing one of the core kinematics columns in input data: {e}")
    except Exception as e:
        raise ValueError(f"Error extracting core kinematics data: {e}")


    processed_data['FrameNumber'] = frame_row['FrameNumber']
    processed_data['Time'] = frame_row.get('Time', np.nan) # Get time, default to NaN

    # 2. Lab Frame Vertical Coordinates of Corners
    vertical_axis_label = ['X', 'Y', 'Z'][vertical_axis_idx_config]
    for i in range(8): # 8 corners
        try:
            # Column names like C0_X, C0_Y, C0_Z are expected from the input CSV
            corner_coord_lab_i = frame_row[[f'C{i}_X', f'C{i}_Y', f'C{i}_Z']].values.astype(float)
            processed_data[f'C{i}_{vertical_axis_label}_Lab'] = corner_coord_lab_i[vertical_axis_idx_config]
        except KeyError:
            # If specific corner coordinate columns are missing, fill with NaN
            print(f"Warning: Corner C{i} coordinates missing for Frame {frame_row['FrameNumber']}. Vertical coord will be NaN.")
            processed_data[f'C{i}_{vertical_axis_label}_Lab'] = np.nan
        except Exception as e:
            print(f"Warning: Error processing C{i} lab vertical coord for Frame {frame_row['FrameNumber']}: {e}")
            processed_data[f'C{i}_{vertical_axis_label}_Lab'] = np.nan


    # 3. Calculate Transformation: Lab {W} -> Analysis {A}
    # R_W_B_lab: Rotation from Body {B} (box local) to World {W} (lab)
    try:
        R_W_B_lab = Rotation.from_rotvec(rv_box_lab).as_matrix()
    except ValueError as e:
        # If rotation vector is invalid, we can't proceed with this frame's transformation
        print(f"Warning: Invalid rotation vector for Frame {frame_row['FrameNumber']}: {rv_box_lab}. Skipping transformations for this frame. Error: {e}")
        # Fill transform-dependent fields with NaN or skip them
        nan_vector = np.array([np.nan, np.nan, np.nan])
        processed_data.update({ # Floor
            'Floor_N_X_Ana': nan_vector[0], 'Floor_N_Y_Ana': nan_vector[1], 'Floor_N_Z_Ana': nan_vector[2],
            'Floor_P_X_Ana': nan_vector[0], 'Floor_P_Y_Ana': nan_vector[1], 'Floor_P_Z_Ana': nan_vector[2],
            # Velocities
            'CoM_Vx_Ana': nan_vector[0], 'CoM_Vy_Ana': nan_vector[1], 'CoM_Vz_Ana': nan_vector[2],
            'AngVel_Wx_Ana': nan_vector[0], 'AngVel_Wy_Ana': nan_vector[1], 'AngVel_Wz_Ana': nan_vector[2],
        })
        # Also fill optional corner velocities if they were to be processed
        for i in range(8):
            processed_data.update({
                f'C{i}_Vx_Ana': np.nan, f'C{i}_Vy_Ana': np.nan, f'C{i}_Vz_Ana': np.nan
            })
        return processed_data # Return partially filled data

    # R_A_W: Rotation from World {W} (lab) to Analysis {A}
    R_A_W = R_W_B_lab.T

    # 4. Transform Floor
    n_floor_lab, p_floor_lab = get_lab_floor_params(vertical_axis_idx_config, floor_level_config)
    n_floor_ana = transform_vector(n_floor_lab, R_A_W)
    p_floor_ana = transform_point(p_floor_lab, R_A_W, T_box_lab) # T_box_lab is T_W_Borg_W

    processed_data['Floor_N_X_Ana'] = n_floor_ana[0]
    processed_data['Floor_N_Y_Ana'] = n_floor_ana[1]
    processed_data['Floor_N_Z_Ana'] = n_floor_ana[2]
    processed_data['Floor_P_X_Ana'] = p_floor_ana[0]
    processed_data['Floor_P_Y_Ana'] = p_floor_ana[1]
    processed_data['Floor_P_Z_Ana'] = p_floor_ana[2]

    # 5. Transform Velocities
    v_com_ana = transform_vector(v_com_lab, R_A_W)
    omega_w_ana = transform_vector(omega_w_lab, R_A_W) # omega_w_lab is already a world-frame vector

    processed_data['CoM_Vx_Ana'] = v_com_ana[0]
    processed_data['CoM_Vy_Ana'] = v_com_ana[1]
    processed_data['CoM_Vz_Ana'] = v_com_ana[2]
    processed_data['AngVel_Wx_Ana'] = omega_w_ana[0]
    processed_data['AngVel_Wy_Ana'] = omega_w_ana[1]
    processed_data['AngVel_Wz_Ana'] = omega_w_ana[2]

    # 6. (Optional) Transform Corner Velocities
    # Assumes input kinematics_csv (integrated file) might contain C{i}_Vx_Lab etc.
    # Or, if a separate corner_velocities_csv was to be used, that logic would go here.
    # For now, let's assume the integrated CSV is the source.
    for i in range(8):
        corner_vel_lab_cols = [f'C{i}_Vx', f'C{i}_Vy', f'C{i}_Vz']
        if all(col in frame_row for col in corner_vel_lab_cols):
            try:
                v_corner_lab_i = frame_row[corner_vel_lab_cols].values.astype(float)
                v_corner_ana_i = transform_vector(v_corner_lab_i, R_A_W)
                processed_data[f'C{i}_Vx_Ana'] = v_corner_ana_i[0]
                processed_data[f'C{i}_Vy_Ana'] = v_corner_ana_i[1]
                processed_data[f'C{i}_Vz_Ana'] = v_corner_ana_i[2]
            except (ValueError, TypeError) as e:
                print(f"Warning: Could not transform C{i} velocity for Frame {frame_row['FrameNumber']}: {e}")
                processed_data.update({f'C{i}_Vx_Ana': np.nan, f'C{i}_Vy_Ana': np.nan, f'C{i}_Vz_Ana': np.nan})
        else: # If original corner velocity columns are not present for this corner
            processed_data.update({f'C{i}_Vx_Ana': np.nan, f'C{i}_Vy_Ana': np.nan, f'C{i}_Vz_Ana': np.nan})


    # 7. Add Box Info in Analysis Frame (for reference by plotting script)
    processed_data.update({
        'Box_Tx_Ana': 0.0, 'Box_Ty_Ana': 0.0, 'Box_Tz_Ana': 0.0,
        'Box_Rx_Ana': 0.0, 'Box_Ry_Ana': 0.0, 'Box_Rz_Ana': 0.0,
    })
    for i, corner_local in enumerate(local_box_corners_config):
        processed_data[f'Box_LC{i}_X_Ana'] = corner_local[0]
        processed_data[f'Box_LC{i}_Y_Ana'] = corner_local[1]
        processed_data[f'Box_LC{i}_Z_Ana'] = corner_local[2]
        
    return processed_data

def main():
    parser = argparse.ArgumentParser(
        description="Analyzes specified frame(s) in a 'transformed' coordinate system where the box is at origin. "
                    "Outputs transformed floor, velocity data, and lab-frame corner vertical coordinates to a CSV file."
    )
    parser.add_argument("--kinematics_csv", type=str, required=True,
                        help="Path to the integrated kinematics CSV file (output of CalculateRigidBodyVelocity.py with --output_integrated_file). "
                             "Must contain Box_Txyz, Box_Rxyz, CoM_Vxyz, AngVel_Wxyz, and C0_X to C7_Z.")
    parser.add_argument("--output_transformed_data_csv", type=str, required=True,
                        help="Path to save the transformed data CSV for the target frame(s).")
    parser.add_argument("--frame_range", nargs='*', default=["ALL"],
                        help="Specify frame(s) to process: 'ALL' (default), <frame_num>, or <start_frame> <end_frame> (inclusive).")

    args = parser.parse_args()

    print(f"--- Analyzing Transformed Frame(s) ---")
    print(f"Kinematics CSV: {args.kinematics_csv}")
    print(f"Frame Range: {' '.join(args.frame_range)}")
    print(f"Output CSV: {args.output_transformed_data_csv}")
    print(f"Using WORLD_VERTICAL_AXIS_INDEX: {WORLD_VERTICAL_AXIS_INDEX} ({['X','Y','Z'][WORLD_VERTICAL_AXIS_INDEX]}-up in Lab Frame)")
    print(f"Using FLOOR_LEVEL (Lab Frame): {FLOOR_LEVEL}")
    print(f"------------------------------------")

    # 1. Load Full Kinematics Data
    try:
        df_full_kinematics = pd.read_csv(args.kinematics_csv)
    except FileNotFoundError:
        print(f"Error: Kinematics file '{args.kinematics_csv}' not found.")
        return
    except Exception as e:
        print(f"Error reading kinematics CSV: {e}")
        return

    if df_full_kinematics.empty:
        print("Input kinematics CSV is empty. Nothing to process.")
        return

    # 2. Determine Target Frames
    target_frames_df = pd.DataFrame() # Initialize an empty DataFrame for selected frames

    if len(args.frame_range) == 1 and args.frame_range[0].upper() == "ALL":
        target_frames_df = df_full_kinematics
        print(f"Processing all {len(target_frames_df)} frames.")
    elif len(args.frame_range) == 1:
        try:
            target_fn = int(args.frame_range[0])
            target_frames_df = df_full_kinematics[df_full_kinematics['FrameNumber'] == target_fn]
            if target_frames_df.empty:
                print(f"Error: Target frame number {target_fn} not found.")
                return
            print(f"Processing single target frame: {target_fn}")
        except ValueError:
            print(f"Error: Invalid single frame number '{args.frame_range[0]}'. Must be an integer or 'ALL'.")
            return
    elif len(args.frame_range) == 2:
        try:
            start_fn, end_fn = int(args.frame_range[0]), int(args.frame_range[1])
            if start_fn > end_fn:
                print(f"Error: Start frame ({start_fn}) cannot be greater than end frame ({end_fn}).")
                return
            target_frames_df = df_full_kinematics[
                (df_full_kinematics['FrameNumber'] >= start_fn) & (df_full_kinematics['FrameNumber'] <= end_fn)
            ]
            if target_frames_df.empty:
                print(f"Error: No frames found in range {start_fn}-{end_fn}.")
                return
            print(f"Processing frames from {start_fn} to {end_fn} (inclusive). Found {len(target_frames_df)} frames.")
        except ValueError:
            print(f"Error: Invalid frame range '{' '.join(args.frame_range)}'. Start and end must be integers.")
            return
    else:
        print("Error: Invalid --frame_range argument. Use 'ALL', <frame_num>, or <start_frame> <end_frame>.")
        return

    # 3. Process each target frame
    all_frames_output_data = []
    for index, frame_row in target_frames_df.iterrows():
        print(f"  Processing FrameNumber: {frame_row['FrameNumber']}...")
        try:
            single_frame_output = process_single_frame(
                frame_row,
                WORLD_VERTICAL_AXIS_INDEX,
                FLOOR_LEVEL,
                LOCAL_BOX_CORNERS
            )
            all_frames_output_data.append(single_frame_output)
        except ValueError as ve: # Catch errors from process_single_frame (e.g. missing columns)
            print(f"  Skipping FrameNumber {frame_row['FrameNumber']} due to error: {ve}")
        except Exception as e:
            print(f"  An unexpected error occurred processing FrameNumber {frame_row['FrameNumber']}: {e}")
            import traceback
            traceback.print_exc()


    # 4. Save to CSV
    if not all_frames_output_data:
        print("No data processed to save.")
    else:
        df_output = pd.DataFrame(all_frames_output_data)
        # Define column order for better readability (optional but good practice)
        # Start with identifiers, then lab coords, then analysis box, then floor, then velocities
        ordered_cols = ['FrameNumber', 'Time']
        vertical_axis_label_cfg = ['X', 'Y', 'Z'][WORLD_VERTICAL_AXIS_INDEX]
        for i in range(8): ordered_cols.append(f'C{i}_{vertical_axis_label_cfg}_Lab')
        
        ordered_cols.extend(['Box_Tx_Ana', 'Box_Ty_Ana', 'Box_Tz_Ana', 'Box_Rx_Ana', 'Box_Ry_Ana', 'Box_Rz_Ana'])
        for i in range(8):
            for axis in ['X', 'Y', 'Z']: ordered_cols.append(f'Box_LC{i}_{axis}_Ana')

        ordered_cols.extend(['Floor_N_X_Ana', 'Floor_N_Y_Ana', 'Floor_N_Z_Ana',
                             'Floor_P_X_Ana', 'Floor_P_Y_Ana', 'Floor_P_Z_Ana'])
        ordered_cols.extend(['CoM_Vx_Ana', 'CoM_Vy_Ana', 'CoM_Vz_Ana',
                             'AngVel_Wx_Ana', 'AngVel_Wy_Ana', 'AngVel_Wz_Ana'])
        for i in range(8):
            for axis_vel in ['Vx', 'Vy', 'Vz']: ordered_cols.append(f'C{i}_{axis_vel}_Ana')
        
        # Ensure all columns in ordered_cols actually exist in df_output to prevent KeyError
        # And add any extra columns that might have been generated but not in ordered_cols (e.g. if logic changes)
        final_cols_to_save = [col for col in ordered_cols if col in df_output.columns]
        extra_cols = [col for col in df_output.columns if col not in final_cols_to_save]
        final_cols_to_save.extend(extra_cols)

        try:
            df_output[final_cols_to_save].to_csv(args.output_transformed_data_csv, index=False, float_format='%.8f')
            print(f"Transformed data for {len(all_frames_output_data)} frame(s) saved to '{args.output_transformed_data_csv}'")
        except Exception as e:
            print(f"Error writing output CSV to '{args.output_transformed_data_csv}': {e}")

    print(f"--- Analysis Script Finished ---")

if __name__ == '__main__':
    main()
# --- END OF FILE AnalyzeTransformedFrame.py ---