# --- START OF FILE NewAnalyzeTransformedFrame.py ---
import argparse
import numpy as np
import pandas as pd
from scipy.spatial.transform import Rotation

# --- Configuration Loading ---
import config
LOCAL_BOX_CORNERS = config.LOCAL_BOX_CORNERS
WORLD_VERTICAL_AXIS_INDEX = config.WORLD_VERTICAL_AXIS_INDEX
FLOOR_LEVEL = config.FLOOR_LEVEL

# --- Helper Functions ---
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
    return R_ana_from_lab @ (point_lab - T_box_center_lab)

def create_rotation_frame_from_omega(omega_ana):
    """
    Creates a new local rotation coordinate frame {R} from an angular velocity vector expressed in the analysis frame {A}. The X-axis of {R} aligns with omega_ana.

    Args:
        omega_ana (np.array): Angular velocity vector in analysis frame.

    Returns:
        tuple: (R_R_A, x_R, y_R, z_R)
            R_R_A (np.array): 3x3 rotation matrix to transform from {A} to {R}.
            x_R, y_R, z_R (np.array): Basis vectors of {R} expressed in {A}.
            Returns (None, None, None, None) if omega is a zero vector.
    """
    omega_magnitude = np.linalg.norm(omega_ana)
    if omega_magnitude < 1e-9:  # Avoid division by zero for zero angular velocity
        # Return identity transformation if omega is zero
        identity_matrix = np.identity(3)
        return identity_matrix, identity_matrix[0], identity_matrix[1], identity_matrix[2]

    # 1. X-axis of {R} is the direction of omega_ana
    x_R = omega_ana / omega_magnitude

    # 2. Select a temporary vector that is not parallel to x_R
    #    by choosing the standard basis vector corresponding to the smallest component of x_R.
    axis_idx_min = np.argmin(np.abs(x_R))
    v_temp = np.zeros(3)
    v_temp[axis_idx_min] = 1.0

    # 3. Use Gram-Schmidt process to find orthogonal y_R and z_R
    #    It's conventional to create the third axis first, then the second.
    z_R_unnormalized = np.cross(x_R, v_temp)
    z_R = z_R_unnormalized / np.linalg.norm(z_R_unnormalized)

    y_R = np.cross(z_R, x_R)  # This will be a unit vector as z_R and x_R are unit and orthogonal

    # 4. Construct the rotation matrix R_R_A (transforms vectors from {A} to {R})
    R_R_A = np.vstack([x_R, y_R, z_R])

    return R_R_A, x_R, y_R, z_R

def process_single_frame(frame_row):
    """Processes a single frame of data to get transformed values."""
    processed_data = {}

    # 1. Extract Lab Frame Data
    try:
        T_box_lab = frame_row[['Box_Tx', 'Box_Ty', 'Box_Tz']].values.astype(float)
        rv_box_lab = frame_row[['Box_Rx', 'Box_Ry', 'Box_Rz']].values.astype(float)
        v_com_lab = frame_row[['CoM_Vx', 'CoM_Vy', 'CoM_Vz']].values.astype(float)
        omega_w_lab = frame_row[['AngVel_Wx', 'AngVel_Wy', 'AngVel_Wz']].values.astype(float)
    except KeyError as e:
        raise ValueError(f"Missing one of the core kinematics columns: {e}")

    processed_data['FrameNumber'] = frame_row['FrameNumber']
    processed_data['Time'] = frame_row.get('Time', np.nan)

    # 2. Lab Frame Vertical Coordinates of Corners
    vertical_axis_label = ['X', 'Y', 'Z'][WORLD_VERTICAL_AXIS_INDEX]
    for i in range(8):
        try:
            corner_coord_lab_i = frame_row[[f'C{i}_X', f'C{i}_Y', f'C{i}_Z']].values.astype(float)
            processed_data[f'C{i}_{vertical_axis_label}_Lab'] = corner_coord_lab_i[WORLD_VERTICAL_AXIS_INDEX]
        except KeyError:
            processed_data[f'C{i}_{vertical_axis_label}_Lab'] = np.nan

    # 3. Calculate Transformation: Lab {W} -> Analysis {A}
    try:
        R_W_B_lab = Rotation.from_rotvec(rv_box_lab).as_matrix()
    except ValueError as e:
        print(f"Warning: Invalid rotation vector for Frame {frame_row['FrameNumber']}: {rv_box_lab}. Skipping transformations.")
        # Fill all subsequent calculated fields with NaN
        nan_keys = ['Floor_N_X_Ana', 'Floor_N_Y_Ana', 'Floor_N_Z_Ana', 'Floor_P_X_Ana', 'Floor_P_Y_Ana', 'Floor_P_Z_Ana',
                    'CoM_V_Magnitude_Ana', 'CoM_Vx_Ana', 'CoM_Vy_Ana', 'CoM_Vz_Ana',
                    'AngVel_Magnitude_Ana', 'AngVel_Wx_Ana', 'AngVel_Wy_Ana', 'AngVel_Wz_Ana',
                    'RotFrameAxisX_X_Ana', 'RotFrameAxisX_Y_Ana', 'RotFrameAxisX_Z_Ana',
                    'RotFrameAxisY_X_Ana', 'RotFrameAxisY_Y_Ana', 'RotFrameAxisY_Z_Ana',
                    'RotFrameAxisZ_X_Ana', 'RotFrameAxisZ_Y_Ana', 'RotFrameAxisZ_Z_Ana',
                    'CoM_V_in_RotFrame_X', 'CoM_V_in_RotFrame_Y', 'CoM_V_in_RotFrame_Z']
        for k in nan_keys: processed_data[k] = np.nan
        return processed_data

    R_A_W = R_W_B_lab.T

    # 4. Transform Floor
    n_floor_lab, p_floor_lab = get_lab_floor_params(WORLD_VERTICAL_AXIS_INDEX, FLOOR_LEVEL)
    n_floor_ana = transform_vector(n_floor_lab, R_A_W)
    p_floor_ana = transform_point(p_floor_lab, R_A_W, T_box_lab)
    processed_data.update({
        'Floor_N_X_Ana': n_floor_ana[0], 'Floor_N_Y_Ana': n_floor_ana[1], 'Floor_N_Z_Ana': n_floor_ana[2],
        'Floor_P_X_Ana': p_floor_ana[0], 'Floor_P_Y_Ana': p_floor_ana[1], 'Floor_P_Z_Ana': p_floor_ana[2],
    })

    # 5. Transform Velocities to Analysis Frame {A}
    v_com_ana = transform_vector(v_com_lab, R_A_W)
    omega_ana = transform_vector(omega_w_lab, R_A_W)
    processed_data.update({
        'CoM_Vx_Ana': v_com_ana[0], 'CoM_Vy_Ana': v_com_ana[1], 'CoM_Vz_Ana': v_com_ana[2],
        'AngVel_Wx_Ana': omega_ana[0], 'AngVel_Wy_Ana': omega_ana[1], 'AngVel_Wz_Ana': omega_ana[2],
    })

    # --- NEW: Calculate velocity magnitudes and transform to Local Rotation Frame {R} ---
    v_com_magnitude = np.linalg.norm(v_com_ana)
    omega_magnitude = np.linalg.norm(omega_ana)
    processed_data['CoM_V_Magnitude_Ana'] = v_com_magnitude
    processed_data['AngVel_Magnitude_Ana'] = omega_magnitude

    # Create the local rotation frame {R} based on omega_ana
    R_R_A, x_R, y_R, z_R = create_rotation_frame_from_omega(omega_ana)

    # Transform v_com_ana into the new frame {R}
    v_com_in_R = R_R_A @ v_com_ana

    # Add new data to the output dictionary
    processed_data.update({
        'RotFrameAxisX_X_Ana': x_R[0], 'RotFrameAxisX_Y_Ana': x_R[1], 'RotFrameAxisX_Z_Ana': x_R[2],
        'RotFrameAxisY_X_Ana': y_R[0], 'RotFrameAxisY_Y_Ana': y_R[1], 'RotFrameAxisY_Z_Ana': y_R[2],
        'RotFrameAxisZ_X_Ana': z_R[0], 'RotFrameAxisZ_Y_Ana': z_R[1], 'RotFrameAxisZ_Z_Ana': z_R[2],
        'CoM_V_in_RotFrame_X': v_com_in_R[0],
        'CoM_V_in_RotFrame_Y': v_com_in_R[1],
        'CoM_V_in_RotFrame_Z': v_com_in_R[2],
    })

    # --- End of New Section ---

    # Add Box Info in Analysis Frame (for reference by plotting script)
    processed_data.update({
        'Box_Tx_Ana': 0.0, 'Box_Ty_Ana': 0.0, 'Box_Tz_Ana': 0.0,
        'Box_Rx_Ana': 0.0, 'Box_Ry_Ana': 0.0, 'Box_Rz_Ana': 0.0,
    })
    for i, corner_local in enumerate(LOCAL_BOX_CORNERS):
        processed_data[f'Box_LC{i}_X_Ana'] = corner_local[0]
        processed_data[f'Box_LC{i}_Y_Ana'] = corner_local[1]
        processed_data[f'Box_LC{i}_Z_Ana'] = corner_local[2]

    return processed_data

def main():
    parser = argparse.ArgumentParser(
        description="Analyzes specified frame(s) in a 'transformed' coordinate system where the box is at origin. "
                    "Outputs transformed data, including a new local rotation frame, to a CSV file."
    )
    parser.add_argument("--kinematics_csv", type=str, required=True, help="Path to the integrated kinematics CSV file from CalculateRigidBodyVelocitySmoother.py.")
    parser.add_argument("--output_transformed_data_csv", type=str, required=True, help="Path to save the transformed data CSV for the target frame(s).")
    parser.add_argument("--frame_range", nargs='*', default=["ALL"], help="Specify frame(s) to process: 'ALL' (default), <frame_num>, or <start_frame> <end_frame> (inclusive).")
    args = parser.parse_args()

    print(f"--- Analyzing Transformed Frame(s) with Local Rotation Frame ---")
    print(f"Input Kinematics CSV: {args.kinematics_csv}")
    print(f"Output Transformed CSV: {args.output_transformed_data_csv}")
    print(f"Frame Range: {' '.join(args.frame_range)}")
    print(f"-------------------------------------------------------------")

    try:
        df_full_kinematics = pd.read_csv(args.kinematics_csv)
    except FileNotFoundError:
        print(f"Error: Input file '{args.kinematics_csv}' not found.")
        return
    except Exception as e:
        print(f"Error reading input CSV: {e}")
        return

    if df_full_kinematics.empty:
        print("Input CSV is empty. Nothing to process.")
        return

    # Determine Target Frames based on --frame_range
    target_frames_df = pd.DataFrame()
    if len(args.frame_range) == 1 and args.frame_range[0].upper() == "ALL":
        target_frames_df = df_full_kinematics
    elif len(args.frame_range) == 1:
        try:
            target_fn = int(args.frame_range[0])
            target_frames_df = df_full_kinematics[df_full_kinematics['FrameNumber'] == target_fn]
            if target_frames_df.empty:
                print(f"Error: Target frame number {target_fn} not found.")
                return
        except ValueError:
            print(f"Error: Invalid single frame number '{args.frame_range[0]}'.")
            return
    elif len(args.frame_range) == 2:
        try:
            start_fn, end_fn = int(args.frame_range[0]), int(args.frame_range[1])
            if start_fn > end_fn:
                print(f"Error: Start frame ({start_fn}) > end frame ({end_fn}).")
                return
            target_frames_df = df_full_kinematics[(df_full_kinematics['FrameNumber'] >= start_fn) & (df_full_kinematics['FrameNumber'] <= end_fn)]
            if target_frames_df.empty:
                print(f"Error: No frames found in range {start_fn}-{end_fn}.")
                return
        except ValueError:
            print(f"Error: Invalid frame range '{' '.join(args.frame_range)}'.")
            return
    else:
        print("Error: Invalid --frame_range argument.")
        return

    print(f"Processing {len(target_frames_df)} frame(s)...")

    all_frames_output_data = []
    for index, frame_row in target_frames_df.iterrows():
        try:
            single_frame_output = process_single_frame(frame_row)
            all_frames_output_data.append(single_frame_output)
        except ValueError as ve:
            print(f"  Skipping FrameNumber {frame_row.get('FrameNumber', 'Unknown')} due to error: {ve}")
        except Exception as e:
            print(f"  An unexpected error occurred processing FrameNumber {frame_row.get('FrameNumber', 'Unknown')}: {e}")
            import traceback
            traceback.print_exc()

    if not all_frames_output_data:
        print("No data was successfully processed to save.")
    else:
        df_output = pd.DataFrame(all_frames_output_data)

        # Define a sensible column order for the output CSV
        ordered_cols = [
            'FrameNumber', 'Time',
            # Lab Frame Vertical Coords
            *[f'C{i}_{["X", "Y", "Z"][WORLD_VERTICAL_AXIS_INDEX]}_Lab' for i in range(8)],
            # Analysis Frame Velocities
            'CoM_V_Magnitude_Ana', 'CoM_Vx_Ana', 'CoM_Vy_Ana', 'CoM_Vz_Ana',
            'AngVel_Magnitude_Ana', 'AngVel_Wx_Ana', 'AngVel_Wy_Ana', 'AngVel_Wz_Ana',
            # Local Rotation Frame Data
            'RotFrameAxisX_X_Ana', 'RotFrameAxisX_Y_Ana', 'RotFrameAxisX_Z_Ana',
            'RotFrameAxisY_X_Ana', 'RotFrameAxisY_Y_Ana', 'RotFrameAxisY_Z_Ana',
            'RotFrameAxisZ_X_Ana', 'RotFrameAxisZ_Y_Ana', 'RotFrameAxisZ_Z_Ana',
            'CoM_V_in_RotFrame_X', 'CoM_V_in_RotFrame_Y', 'CoM_V_in_RotFrame_Z',
            # Analysis Frame Floor
            'Floor_N_X_Ana', 'Floor_N_Y_Ana', 'Floor_N_Z_Ana',
            'Floor_P_X_Ana', 'Floor_P_Y_Ana', 'Floor_P_Z_Ana',
            # Analysis Frame Box Info (for reference)
            'Box_Tx_Ana', 'Box_Ty_Ana', 'Box_Tz_Ana',
            'Box_Rx_Ana', 'Box_Ry_Ana', 'Box_Rz_Ana',
            *[f'Box_LC{i}_{axis}_Ana' for i in range(8) for axis in ['X', 'Y', 'Z']]
        ]

        final_cols_to_save = [col for col in ordered_cols if col in df_output.columns]
        extra_cols = [col for col in df_output.columns if col not in final_cols_to_save]
        final_cols_to_save.extend(extra_cols)

        try:
            df_output[final_cols_to_save].to_csv(args.output_transformed_data_csv, index=False, float_format='%.8f')
            print(f"Transformed data for {len(all_frames_output_data)} frame(s) saved to '{args.output_transformed_data_csv}'")
        except Exception as e:
            print(f"Error writing output CSV: {e}")

    print(f"--- Analysis Script Finished ---")

# if name == 'main': main()
if __name__ == "__main__":
    main()

# --- END OF FILE NewAnalyzeTransformedFrame.py ---