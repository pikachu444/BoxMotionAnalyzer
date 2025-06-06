# --- START OF FILE CalculateRigidBodyVelocity.py (Revised for config and comments) ---
import argparse
import numpy as np
import pandas as pd
from scipy.spatial.transform import Rotation

# --- Configuration Loading ---
try:
    import config
    # Load BOX_DIMS to be used if --box_dims is not provided by user
    BOX_DIMS_FROM_CONFIG = config.BOX_DIMS
    # Load pre-calculated LOCAL_BOX_CORNERS from config.py
    LOCAL_BOX_CORNERS_FROM_CONFIG = config.LOCAL_BOX_CORNERS
    # print("Successfully loaded BOX_DIMS and LOCAL_BOX_CORNERS from config.py in CalculateRigidBodyVelocity.")
except ImportError:
    print("Warning: Could not import config.py. Using fallback configurations for BOX_DIMS and LOCAL_BOX_CORNERS.")
    BOX_DIMS_FROM_CONFIG = np.array([1820.0, 1110.0, 164.0]) # Fallback BOX_DIMS
    _L, _W, _H = BOX_DIMS_FROM_CONFIG
    _hl, _hw, _hh = _L / 2.0, _W / 2.0, _H / 2.0
    LOCAL_BOX_CORNERS_FROM_CONFIG = np.array([ # Fallback LOCAL_BOX_CORNERS
        [-_hl, -_hw, -_hh], [ _hl, -_hw, -_hh], [ _hl,  _hw, -_hh], [-_hl,  _hw, -_hh],
        [-_hl, -_hw,  _hh], [ _hl, -_hw,  _hh], [ _hl,  _hw,  _hh], [-_hl,  _hw,  _hh]
    ])
except AttributeError as e:
    print(f"Warning: An attribute ({e}) not found in config.py. Using fallback configurations.")
    BOX_DIMS_FROM_CONFIG = np.array([1820.0, 1110.0, 164.0]) # Fallback BOX_DIMS
    _L, _W, _H = BOX_DIMS_FROM_CONFIG
    _hl, _hw, _hh = _L / 2.0, _W / 2.0, _H / 2.0
    LOCAL_BOX_CORNERS_FROM_CONFIG = np.array([ # Fallback LOCAL_BOX_CORNERS
        [-_hl, -_hw, -_hh], [ _hl, -_hw, -_hh], [ _hl,  _hw, -_hh], [-_hl,  _hw, -_hh],
        [-_hl, -_hw,  _hh], [ _hl, -_hw,  _hh], [ _hl,  _hw,  _hh], [-_hl,  _hw,  _hh]
    ])

# --- Utility Functions ---
# get_box_local_corners function is removed as LOCAL_BOX_CORNERS_FROM_CONFIG is used.
# If --box_dims is provided, local corners are calculated ad-hoc in process_kinematics.

def numerical_derivative(y_values, t_values):
    """
    Calculates the numerical derivative of y_values with respect to t_values.
    Uses central difference for interior points, forward/backward for endpoints,
    and handles varying time steps.
    """
    if len(y_values) != len(t_values):
        raise ValueError("y_values and t_values must have the same length.")
    if len(y_values) < 2:
        # Return array of zeros with the same shape as y_values
        # This handles scalar y_values (if y_values is 1D) or multi-column y_values (if y_values is 2D)
        return np.zeros_like(y_values, dtype=float)

    # Ensure y_values is a numpy array for consistent operations
    y_values_np = np.asarray(y_values)
    dy_dt = np.zeros_like(y_values_np, dtype=float)
    t_values = t_values.astype(float)

    # First point: forward difference
    dt_0 = t_values[1] - t_values[0]
    dy_dt[0] = (y_values_np[1] - y_values_np[0]) / dt_0 if dt_0 > 1e-9 else 0.0

    # Interior points: central difference
    for i in range(1, len(y_values_np) - 1):
        denominator = t_values[i+1] - t_values[i-1]
        if abs(denominator) <= 1e-9: # If t_i-1 and t_i+1 are too close, or t_i is not centered
            # Fallback logic for unstable central difference
            dt_forward = t_values[i+1] - t_values[i]
            if dt_forward > 1e-9:
                dy_dt[i] = (y_values_np[i+1] - y_values_np[i]) / dt_forward
            else: # If forward is also problematic, use backward
                dt_backward = t_values[i] - t_values[i-1]
                if dt_backward > 1e-9:
                    dy_dt[i] = (y_values_np[i] - y_values_np[i-1]) / dt_backward
                else:
                    dy_dt[i] = 0.0 # All intervals too small
        else:
            dy_dt[i] = (y_values_np[i+1] - y_values_np[i-1]) / denominator

    # Last point: backward difference
    if len(y_values_np) > 1: # Ensure there is at least one point before the last
        dt_N = t_values[-1] - t_values[-2]
        dy_dt[-1] = (y_values_np[-1] - y_values_np[-2]) / dt_N if dt_N > 1e-9 else 0.0
            
    return dy_dt

def ensure_quaternion_continuity(quaternions_scipy_format):
    """Ensures quaternion continuity (SciPy format [x,y,z,w])."""
    q_processed = np.copy(quaternions_scipy_format)
    for i in range(1, len(q_processed)):
        if np.dot(q_processed[i-1], q_processed[i]) < 0:
            q_processed[i] *= -1
    return q_processed

# --- Angular Velocity Calculation Methods ---
def calculate_angular_velocity_matrix_based(rot_vectors_rad, time_s):
    """Calculates angular velocity (world frame) via rotation matrix differentiation."""
    num_frames = len(rot_vectors_rad)
    angular_velocities_world = np.zeros((num_frames, 3))
    if num_frames < 2: return angular_velocities_world

    rot_matrices = Rotation.from_rotvec(rot_vectors_rad).as_matrix() # Shape (N, 3, 3)

    # Numerical derivative of each of the 9 components of R(t)
    dR_dt_components = []
    for r_idx in range(3):
        for c_idx in range(3):
            dR_dt_components.append(numerical_derivative(rot_matrices[:, r_idx, c_idx], time_s))
    # Reshape dR_dt_components into (num_frames, 3, 3)
    dR_dt = np.stack(dR_dt_components, axis=-1).reshape(num_frames, 3, 3)


    for i in range(num_frames):
        R_i = rot_matrices[i]
        dR_dt_i = dR_dt[i]
        omega_skew_matrix = dR_dt_i @ R_i.T
        # Robust extraction: (omega_skew - omega_skew.T) / 2
        omega_skew_antisym = 0.5 * (omega_skew_matrix - omega_skew_matrix.T)
        angular_velocities_world[i] = [omega_skew_antisym[2, 1], omega_skew_antisym[0, 2], omega_skew_antisym[1, 0]]
    return angular_velocities_world

def calculate_angular_velocity_quaternion_based(rot_vectors_rad, time_s):
    """Calculates angular velocity (world frame) via quaternion differentiation."""
    num_frames = len(rot_vectors_rad)
    angular_velocities_world = np.zeros((num_frames, 3))
    if num_frames < 2: return angular_velocities_world

    quaternions_scipy = Rotation.from_rotvec(rot_vectors_rad).as_quat() # Format [x,y,z,w]
    continuous_quaternions = ensure_quaternion_continuity(quaternions_scipy)
    
    # Numerical derivative of each of the 4 components of q(t)
    dq_dt_scipy_components = []
    for k in range(4): # For x, y, z, w components
        dq_dt_scipy_components.append(numerical_derivative(continuous_quaternions[:, k], time_s))
    dq_dt_scipy = np.stack(dq_dt_scipy_components, axis=-1) # Shape (N, 4)


    for i in range(num_frames):
        q_i = continuous_quaternions[i] # [x,y,z,w]
        dq_dt_i = dq_dt_scipy[i]      # [dx,dy,dz,dw]

        # Convert to standard quaternion q_std = [w, x, y, z] for formula application
        w_s, x_s, y_s, z_s = q_i[3], q_i[0], q_i[1], q_i[2]
        dw_s, dx_s, dy_s, dz_s = dq_dt_i[3], dq_dt_i[0], dq_dt_i[1], dq_dt_i[2]

        # Omega in body frame from d(q_std)/dt and q_std
        # Using formula: omega_body_x = 2*(-x*dw + w*dx + z*dy - y*dz), etc.
        omega_body_x = 2 * (-x_s*dw_s + w_s*dx_s + z_s*dy_s - y_s*dz_s)
        omega_body_y = 2 * (-y_s*dw_s - z_s*dx_s + w_s*dy_s + x_s*dz_s)
        omega_body_z = 2 * (-z_s*dw_s + y_s*dx_s - x_s*dy_s + w_s*dz_s)
        angular_velocity_body = np.array([omega_body_x, omega_body_y, omega_body_z])

        R_i = Rotation.from_quat(q_i).as_matrix() # q_i is [x,y,z,w] for from_quat
        angular_velocities_world[i] = R_i @ angular_velocity_body
    return angular_velocities_world

# --- Main Processing Function ---
def process_kinematics(df_input, ang_vel_method='matrix', box_dims_override_xyz=None):
    """
    Processes pose data to calculate CoM velocity, angular velocity, and optionally corner velocities.
    Args:
        df_input (pd.DataFrame): Input DataFrame with pose data.
        ang_vel_method (str): Method for angular velocity ('matrix' or 'quaternion').
        box_dims_override_xyz (list/np.array, optional): User-provided box dimensions [L,W,H] to override config.
                                                        If None, BOX_DIMS from config.py (via global) is used.
    """
    df = df_input.copy()
    required_cols = ['Time', 'Box_Tx', 'Box_Ty', 'Box_Tz', 'Box_Rx', 'Box_Ry', 'Box_Rz']
    if not all(col in df.columns for col in required_cols):
        # This check ensures the input CSV has the necessary pose information.
        raise ValueError(f"Input CSV is missing one or more required columns for pose: {required_cols}")

    time_s = df['Time'].values
    positions_m = df[['Box_Tx', 'Box_Ty', 'Box_Tz']].values
    rot_vectors_rad = df[['Box_Rx', 'Box_Ry', 'Box_Rz']].values

    # 1. Translational Velocity (CoM Velocity)
    # Calculate derivative for each position component (X, Y, Z)
    com_velocities_mps_components = []
    for i in range(positions_m.shape[1]): # Should be 3 for X,Y,Z
        com_velocities_mps_components.append(numerical_derivative(positions_m[:, i], time_s))
    com_velocities_mps = np.stack(com_velocities_mps_components, axis=-1) # Shape (N, 3)
    
    df['CoM_Vx'] = com_velocities_mps[:,0]
    df['CoM_Vy'] = com_velocities_mps[:,1]
    df['CoM_Vz'] = com_velocities_mps[:,2]

    # 2. Angular Velocity (World Frame)
    if ang_vel_method == 'matrix':
        angular_velocities_radps = calculate_angular_velocity_matrix_based(rot_vectors_rad, time_s)
    elif ang_vel_method == 'quaternion':
        angular_velocities_radps = calculate_angular_velocity_quaternion_based(rot_vectors_rad, time_s)
    else:
        raise ValueError(f"Unknown angular velocity method: {ang_vel_method}. Choose 'matrix' or 'quaternion'.")
    df['AngVel_Wx'] = angular_velocities_radps[:,0] # World frame angular velocity
    df['AngVel_Wy'] = angular_velocities_radps[:,1]
    df['AngVel_Wz'] = angular_velocities_radps[:,2]

    # 3. Corner Velocities
    # Determine which local_corners definition to use for this calculation.
    _local_corners_for_calc = None
    if box_dims_override_xyz is not None:
        # If user provides --box_dims, calculate local corners based on that.
        print(f"  Info: Calculating local corners for corner velocities using provided --box_dims: {box_dims_override_xyz}")
        L_override, W_override, H_override = box_dims_override_xyz
        hl_o, hw_o, hh_o = L_override / 2.0, W_override / 2.0, H_override / 2.0
        _local_corners_for_calc = np.array([
            [-hl_o, -hw_o, -hh_o], [ hl_o, -hw_o, -hh_o], [ hl_o,  hw_o, -hh_o], [-hl_o,  hw_o, -hh_o],
            [-hl_o, -hw_o,  hh_o], [ hl_o, -hw_o,  hh_o], [ hl_o,  hw_o,  hh_o], [-hl_o,  hw_o,  hh_o]
        ])
    elif 'LOCAL_BOX_CORNERS_FROM_CONFIG' in globals() and LOCAL_BOX_CORNERS_FROM_CONFIG is not None:
        # Otherwise, use the pre-calculated LOCAL_BOX_CORNERS from config.py
        # (which are derived from BOX_DIMS_FROM_CONFIG)
        # print(f"  Info: Using LOCAL_BOX_CORNERS from config.py for corner velocities.")
        _local_corners_for_calc = LOCAL_BOX_CORNERS_FROM_CONFIG
    else:
        # This case should be rare if config loading and fallbacks work.
        print("  Warning: Local box corners could not be determined. Skipping corner velocity calculation.")

    if _local_corners_for_calc is not None:
        # print(f"  Info: Proceeding with corner velocity calculation.")
        num_frames = len(df)
        # Get Rotation objects for all frames (already have rot_vectors_rad)
        rotations_obj = Rotation.from_rotvec(rot_vectors_rad) 

        for c_idx in range(_local_corners_for_calc.shape[0]): # Iterate through 8 corners
            corner_vels_for_this_corner = np.zeros((num_frames, 3)) # To store Vx, Vy, Vz for this corner for all frames
            for i in range(num_frames): # Iterate through each frame
                R_i = rotations_obj[i].as_matrix()
                v_com_i = com_velocities_mps[i, :] # CoM velocity for this frame
                omega_world_i = angular_velocities_radps[i, :] # World angular velocity for this frame
                
                # Vector from CoM to corner in local_corners_for_calc frame
                r_local_c_i = _local_corners_for_calc[c_idx] 
                # Transform this local vector to world frame
                r_world_from_com_i = R_i @ r_local_c_i
                
                # Velocity of corner = v_CoM + omega_world x (R * r_local_corner)
                corner_vels_for_this_corner[i, :] = v_com_i + np.cross(omega_world_i, r_world_from_com_i)
            
            # Add columns to DataFrame for this corner's velocities
            df[f'C{c_idx}_Vx'] = corner_vels_for_this_corner[:, 0]
            df[f'C{c_idx}_Vy'] = corner_vels_for_this_corner[:, 1]
            df[f'C{c_idx}_Vz'] = corner_vels_for_this_corner[:, 2]
        # print("  Corner velocity calculation complete.")
    # No 'else' needed here to add NaN columns, as main save logic will check column existence.
    
    return df

def main():
    parser = argparse.ArgumentParser(description="Calculates velocities from box pose sequence CSV.")
    parser.add_argument("input_csv_path", help="Path to input box pose sequence CSV.")
    parser.add_argument("--output_center_kinematics", default="center_kinematics.csv", help="Output for center kinematics.")
    parser.add_argument("--output_corner_velocities", default="corner_velocities.csv", help="Output for corner velocities.")
    parser.add_argument("--output_integrated_file", default=None, help="Optional integrated output CSV.")
    parser.add_argument("--ang_vel_method", default="matrix", choices=['matrix', 'quaternion'], help="Angular velocity calculation method.")
    
    # If --box_dims is NOT provided, its value will be None.
    # process_kinematics will then use BOX_DIMS_FROM_CONFIG (via LOCAL_BOX_CORNERS_FROM_CONFIG).
    parser.add_argument("--box_dims", type=float, nargs=3, default=None, 
                        help="Override box dimensions (L W H) from config.py for corner velocities (e.g., 1820 1110 164). If not provided, uses BOX_DIMS from config.py.")
    args = parser.parse_args()

    # Determine which box dimensions are effectively being used for corner calculations
    # This is mainly for informing the user. process_kinematics handles the logic.
    effective_dims_source = ""
    if args.box_dims:
        effective_dims_source = f"command line (--box_dims): {args.box_dims}"
    elif 'BOX_DIMS_FROM_CONFIG' in globals() and BOX_DIMS_FROM_CONFIG is not None:
        effective_dims_source = f"config.py (BOX_DIMS): {BOX_DIMS_FROM_CONFIG.tolist()}"
    else:
        effective_dims_source = "Not determined (fallback or error)"


    print(f"--- Calculate Rigid Body Velocity ---")
    print(f"Input: {args.input_csv_path}")
    print(f"Angular Vel Method: {args.ang_vel_method}")
    print(f"Effective Box Dims for corner velocity calculation from: {effective_dims_source}")
    if not args.box_dims and not ('BOX_DIMS_FROM_CONFIG' in globals() and BOX_DIMS_FROM_CONFIG is not None):
        print("  Warning: Corner velocities will likely not be calculated as box dimensions are unavailable.")
    print(f"------------------------------------")

    try:
        df_input = pd.read_csv(args.input_csv_path)
        if df_input.empty:
            print("Input CSV is empty. Exiting.")
            return
        
        # Pass args.box_dims directly. process_kinematics will decide whether to use it
        # or fall back to config-derived local corners.
        df_kinematics = process_kinematics(df_input, args.ang_vel_method, args.box_dims)

        # Save Center Kinematics
        center_cols = ['FrameNumber', 'Time', 
                       'Box_Tx', 'Box_Ty', 'Box_Tz', 
                       'Box_Rx', 'Box_Ry', 'Box_Rz', # Original Pose
                       'CoM_Vx', 'CoM_Vy', 'CoM_Vz', # Center of Mass Velocities
                       'AngVel_Wx', 'AngVel_Wy', 'AngVel_Wz'] # Angular Velocities (World)
        
        center_cols_to_save = [col for col in center_cols if col in df_kinematics.columns]
        if not all(c in center_cols_to_save for c in ['CoM_Vx', 'AngVel_Wx']): # Quick check for core velocity columns
            print(f"Warning: Core center kinematics columns (e.g., CoM_Vx, AngVel_Wx) missing. File '{args.output_center_kinematics}' may be incomplete or not saved.")
        
        if len(center_cols_to_save) > 2: # Ensure more than just FrameNumber, Time
            try:
                df_kinematics[center_cols_to_save].to_csv(args.output_center_kinematics, index=False, float_format='%.8f')
                print(f"Center kinematics saved to '{args.output_center_kinematics}'")
            except Exception as e:
                print(f"Error saving center kinematics to '{args.output_center_kinematics}': {e}")
        else:
            print(f"Info: Not enough center kinematics columns found to save for '{args.output_center_kinematics}'.")


        # Save Corner Velocities
        # Corner velocities are only calculated if box_dims_override_xyz was effectively non-None in process_kinematics
        # which depends on args.box_dims or BOX_DIMS_FROM_CONFIG.
        # The reliable check is if the columns 'C0_Vx', etc. exist in df_kinematics.
        if 'C0_Vx' in df_kinematics.columns: # Check if first corner's X-velocity column exists
            corner_vel_cols_to_save = ['FrameNumber', 'Time']
            all_expected_corner_cols_found = True
            for i in range(8): 
                for axis in ['Vx', 'Vy', 'Vz']:
                    col_name = f'C{i}_{axis}'
                    if col_name in df_kinematics.columns:
                        corner_vel_cols_to_save.append(col_name)
                    else:
                        # print(f"  Debug: Missing corner velocity column for saving: {col_name}")
                        all_expected_corner_cols_found = False # Optional: be strict
                        # If strict, could break here or just note it. For now, save what's available.
            
            if len(corner_vel_cols_to_save) > 2: # More than just FrameNumber, Time
                try:
                    df_kinematics[corner_vel_cols_to_save].to_csv(args.output_corner_velocities, index=False, float_format='%.8f')
                    print(f"Corner velocities saved to '{args.output_corner_velocities}'")
                    if not all_expected_corner_cols_found:
                         print(f"  Warning: Some expected corner velocity columns were missing but output was still generated for '{args.output_corner_velocities}'.")
                except Exception as e:
                    print(f"Error saving corner velocities to '{args.output_corner_velocities}': {e}")
            else:
                 print(f"Info: Found 'C0_Vx' but could not gather sufficient corner velocity columns to save for '{args.output_corner_velocities}'.")
        else:
            # This message implies that process_kinematics did not add C0_Vx,
            # likely because _local_corners_for_calc was None.
            print(f"Info: Corner velocity column 'C0_Vx' not found in processed data. Skipping save for '{args.output_corner_velocities}'.")


        # Save Integrated File (Optional)
        if args.output_integrated_file:
            try:
                df_kinematics.to_csv(args.output_integrated_file, index=False, float_format='%.8f')
                print(f"Integrated data saved to '{args.output_integrated_file}'")
            except Exception as e:
                print(f"Error writing integrated CSV to '{args.output_integrated_file}': {e}")
        
        print(f"--- Processing Complete ---")

    except FileNotFoundError:
        print(f"Error: Input file '{args.input_csv_path}' not found.")
    except ValueError as ve: # Catch ValueErrors from data checks (e.g. missing columns)
        print(f"ValueError during processing: {ve}")
    except Exception as e: # Catch any other unexpected errors
        print(f"An unexpected error occurred: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    main()
# --- END OF FILE CalculateRigidBodyVelocity.py (Revised for config and comments) ---