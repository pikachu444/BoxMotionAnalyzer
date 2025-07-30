#--- START OF FILE CalculateRigidBodyVelocity.py ---
import argparse
import numpy as np
import pandas as pd
from scipy.spatial.transform import Rotation
from scipy.interpolate import UnivariateSpline  # For spline fitting
from scipy.signal import butter, filtfilt  # For Butterworth filter

# --- Configuration Loading ---
import config
BOX_DIMS = config.BOX_DIMS
LOCAL_BOX_CORNERS = config.LOCAL_BOX_CORNERS

# --- Utility / Filter Functions ---
def apply_butter_lowpass_filter_to_series(data_series_1d, cutoff_hz, fs, order):
    """Applies a Butterworth low-pass filter to a 1D data series."""
    if cutoff_hz is None or cutoff_hz <= 0 or fs <= 0:
        return data_series_1d  # No filtering if params invalid or fs not available
    nyquist_freq = 0.5 * fs
    if cutoff_hz >= nyquist_freq:
        print(f" Warning: Low-pass cutoff ({cutoff_hz}Hz) >= Nyquist ({nyquist_freq}Hz). Filtering skipped for series.")
        return data_series_1d

    normalized_cutoff = cutoff_hz / nyquist_freq
    try:
        b, a = butter(order, normalized_cutoff, btype='low', analog=False)
        series_to_filter = data_series_1d.astype(np.float64)
        original_nan_mask = np.isnan(series_to_filter)
        if np.any(original_nan_mask):
            series_to_filter_nonan = pd.Series(series_to_filter).interpolate(method='linear').fillna(method='bfill').fillna(method='ffill').values
            if np.isnan(series_to_filter_nonan).any():
                print(f"  Warning: Could not fully interpolate NaNs before filtering. Original series returned.")
                return data_series_1d
            filtered_values = filtfilt(b, a, series_to_filter_nonan)
            filtered_values[original_nan_mask] = np.nan
            return filtered_values

        return filtfilt(b, a, series_to_filter)
    except ValueError as e_filt:
        print(f"  Warning: Butterworth filter error (cutoff: {cutoff_hz}Hz, order: {order}): {e_filt}. Original series returned.")
        return data_series_1d

def apply_filter_to_ndim_data(data_ndim, time_s, fs, filter_func, **filter_params):
    """Applies a 1D filter_func to each column of N-D data."""
    filtered_data = np.copy(data_ndim)
    for i_col in range(data_ndim.shape[1]):
        filtered_data[:, i_col] = filter_func(data_ndim[:, i_col], **filter_params, fs=fs, time_s=time_s)
    return filtered_data

def apply_moving_average_to_series(data_series_1d, window_size):
    """Applies moving average to a 1D data series."""
    if window_size is None or int(window_size) <= 1:
        return data_series_1d
    return pd.Series(data_series_1d).rolling(window=int(window_size), center=True, min_periods=1).mean().values

def apply_ma_to_ndim_data(data_ndim, window_size):
    """Applies moving average to each column of N-D data."""
    smoothed_data = np.copy(data_ndim)
    for i_col in range(data_ndim.shape[1]):
        smoothed_data[:, i_col] = apply_moving_average_to_series(data_ndim[:, i_col], window_size)
    return smoothed_data

def numerical_derivative_finite_diff(y_values, t_values):
    """Calculates numerical derivative using finite differences (handles varying dt)."""
    if len(y_values) != len(t_values):
        raise ValueError("y/t length mismatch.")
    if len(y_values) < 2:
        return np.zeros_like(y_values, dtype=float)
    y_np = np.asarray(y_values)
    t_np = t_values.astype(float)
    dy_dt = np.zeros_like(y_np, dtype=float)
    dt_0 = t_np[1] - t_np[0]
    dy_dt[0] = (y_np[1] - y_np[0]) / dt_0 if dt_0 > 1e-9 else 0.0
    for i in range(1, len(y_np) - 1):
        den = t_np[i+1] - t_np[i-1]
        if abs(den) <= 1e-9:
            dt_f = t_np[i+1] - t_np[i]
            dt_b = t_np[i] - t_np[i-1]
            if dt_f > 1e-9 and dt_b > 1e-9:
                dy_dt[i] = 0.5 * (((y_np[i+1] - y_np[i]) / dt_f) + ((y_np[i] - y_np[i-1]) / dt_b))
            elif dt_f > 1e-9:
                dy_dt[i] = (y_np[i+1] - y_np[i]) / dt_f
            elif dt_b > 1e-9:
                dy_dt[i] = (y_np[i] - y_np[i-1]) / dt_b
            else:
                dy_dt[i] = 0.0
        else:
            dy_dt[i] = (y_np[i+1] - y_np[i-1]) / den
    if len(y_np) > 1:
        dt_N = t_np[-1] - t_np[-2]
        dy_dt[-1] = (y_np[-1] - y_np[-2]) / dt_N if dt_N > 1e-9 else 0.0
    return dy_dt

def ensure_quaternion_continuity(quaternions_scipy_fmt):
    """Ensures quaternion continuity (SciPy format [x,y,z,w]) by flipping signs."""
    q_proc = np.copy(quaternions_scipy_fmt)
    for i in range(1, len(q_proc)):
        if np.dot(q_proc[i-1], q_proc[i]) < 0:
            q_proc[i] *= -1
    return q_proc

# --- Velocity Calculation Core Functions ---
def calculate_translational_velocity_spline(positions_t, time_s, s_factor=0, spline_degree=3):
    """Calculates translational velocity from positions using spline differentiation."""
    num_frames, num_dims = positions_t.shape
    velocities_t = np.zeros_like(positions_t)
    print(f" Spline for Translation: s_factor={s_factor}, degree={spline_degree}")
    for dim_idx in range(num_dims):
        try:
            if not np.all(np.diff(time_s) > 0):
                sort_indices = np.argsort(time_s)
                time_s_sorted = time_s[sort_indices]
                positions_t_sorted_dim = positions_t[sort_indices, dim_idx]
                if not np.all(np.diff(time_s_sorted) > 1e-9):
                    raise ValueError("Time values are not strictly increasing or contain duplicates, cannot fit spline.")
            else:
                time_s_sorted = time_s
                positions_t_sorted_dim = positions_t[:, dim_idx]

            spl = UnivariateSpline(time_s_sorted, positions_t_sorted_dim, k=spline_degree, s=s_factor if s_factor > 1e-9 else 0)
            velocities_t[:, dim_idx] = spl.derivative(n=1)(time_s)
        except Exception as e:
            print(f"    Warning: Spline for position dim {dim_idx} failed: {e}. Velocities for this dim set to zero.")
            velocities_t[:, dim_idx] = 0.0
    return velocities_t

def calculate_angular_velocity_spline_from_quaternions(quaternions_continuous_t, time_s, s_factor=0, spline_degree=3):
    """Calculates angular velocity (world) from quaternions using spline differentiation."""
    num_frames, num_q_comps = quaternions_continuous_t.shape
    angular_velocities_world_t = np.zeros((num_frames, 3))
    if num_frames < 2:
        return angular_velocities_world_t
    print(f" Spline for Rotation (Quaternions): s_factor={s_factor}, degree={spline_degree}")

    q_spline_t = np.zeros_like(quaternions_continuous_t)
    dq_dt_spline_t = np.zeros_like(quaternions_continuous_t)

    time_s_sorted_for_quat = time_s
    quaternions_sorted_for_spline = quaternions_continuous_t
    if not np.all(np.diff(time_s) > 0):
        sort_indices_q = np.argsort(time_s)
        time_s_sorted_for_quat = time_s[sort_indices_q]
        quaternions_sorted_for_spline = quaternions_continuous_t[sort_indices_q, :]
        if not np.all(np.diff(time_s_sorted_for_quat) > 1e-9):
            print("    Warning: Time values for quaternion spline are not strictly increasing or contain duplicates. Spline may fail.")
            time_s_sorted_for_quat = time_s
            quaternions_sorted_for_spline = quaternions_continuous_t

    for k_comp in range(num_q_comps):
        try:
            spl_q = UnivariateSpline(time_s_sorted_for_quat, quaternions_sorted_for_spline[:, k_comp], k=spline_degree, s=s_factor if s_factor > 1e-9 else 0)
            q_spline_t[:, k_comp] = spl_q(time_s)
            dq_dt_spline_t[:, k_comp] = spl_q.derivative(n=1)(time_s)
        except Exception as e:
            print(f"    Warning: Spline for quaternion component {k_comp} failed: {e}. Using zeros for derivative.")
            q_spline_t[:, k_comp] = quaternions_continuous_t[:, k_comp]
            dq_dt_spline_t[:, k_comp] = 0.0

    for i in range(num_frames):
        q_i_sp = q_spline_t[i]
        dq_dt_i_sp = dq_dt_spline_t[i]

        w_s, x_s, y_s, z_s = q_i_sp[3], q_i_sp[0], q_i_sp[1], q_i_sp[2]
        dw_s, dx_s, dy_s, dz_s = dq_dt_i_sp[3], dq_dt_i_sp[0], dq_dt_i_sp[1], dq_dt_i_sp[2]

        omega_body_x = 2 * (-x_s*dw_s + w_s*dx_s + z_s*dy_s - y_s*dz_s)
        omega_body_y = 2 * (-y_s*dw_s - z_s*dx_s + w_s*dy_s + x_s*dz_s)
        omega_body_z = 2 * (-z_s*dw_s + y_s*dx_s - x_s*dy_s + w_s*dz_s)
        ang_vel_body = np.array([omega_body_x, omega_body_y, omega_body_z])
        
        try:
            R_i = Rotation.from_quat(q_i_sp).as_matrix()
        except ValueError:
            R_i = np.identity(3)
        angular_velocities_world_t[i] = R_i @ ang_vel_body
    return angular_velocities_world_t

def calculate_angular_velocity_matrix_based_fd(rot_vectors_rad, time_s):
    """FD-based angular velocity (world) using rotation matrix differentiation."""
    num_frames = len(rot_vectors_rad)
    angular_velocities_world = np.zeros((num_frames, 3))
    if num_frames < 2:
        return angular_velocities_world
    rot_matrices = Rotation.from_rotvec(rot_vectors_rad).as_matrix()
    dR_dt = np.zeros_like(rot_matrices)
    for r_idx in range(3):
        for c_idx in range(3):
            dR_dt[:, r_idx, c_idx] = numerical_derivative_finite_diff(rot_matrices[:, r_idx, c_idx], time_s)
    for i in range(num_frames):
        R_i = rot_matrices[i]
        dR_dt_i = dR_dt[i]
        omega_skew_matrix = dR_dt_i @ R_i.T
        omega_skew_antisym = 0.5 * (omega_skew_matrix - omega_skew_matrix.T)
        angular_velocities_world[i] = [omega_skew_antisym[2,1], omega_skew_antisym[0,2], omega_skew_antisym[1,0]]
    return angular_velocities_world

def calculate_angular_velocity_quaternion_based_fd(rot_vectors_rad, time_s):
    """FD-based angular velocity (world) using quaternion differentiation."""
    num_frames = len(rot_vectors_rad)
    angular_velocities_world = np.zeros((num_frames, 3))
    if num_frames < 2:
        return angular_velocities_world
    quaternions_scipy = Rotation.from_rotvec(rot_vectors_rad).as_quat()
    continuous_quaternions = ensure_quaternion_continuity(quaternions_scipy)
    dq_dt_scipy = np.zeros_like(continuous_quaternions)
    for k_comp in range(4):
        dq_dt_scipy[:, k_comp] = numerical_derivative_finite_diff(continuous_quaternions[:, k_comp], time_s)
    for i in range(num_frames):
        q_i = continuous_quaternions[i]
        dq_dt_i = dq_dt_scipy[i]
        w_s, x_s, y_s, z_s = q_i[3], q_i[0], q_i[1], q_i[2]
        dw_s, dx_s, dy_s, dz_s = dq_dt_i[3], dq_dt_i[0], dq_dt_i[1], dq_dt_i[2]
        omega_body_x = 2 * (-x_s*dw_s + w_s*dx_s + z_s*dy_s - y_s*dz_s)
        omega_body_y = 2 * (-y_s*dw_s - z_s*dx_s + w_s*dy_s + x_s*dz_s)
        omega_body_z = 2 * (-z_s*dw_s + y_s*dx_s - x_s*dy_s + w_s*dz_s)
        ang_vel_body = np.array([omega_body_x, omega_body_y, omega_body_z])
        R_i = Rotation.from_quat(q_i).as_matrix()
        angular_velocities_world[i] = R_i @ ang_vel_body
    return angular_velocities_world

# --- Main Processing Pipeline Function ---
def process_kinematics_pipeline(df_input, velocity_method_flag, use_pose_lpf_flag, pose_lpf_cutoff_val, pose_lpf_order_val, use_pose_ma_flag, pose_ma_window_val, spline_s_pos_val, spline_s_rot_val, spline_k_val, fd_angular_method_val, use_vel_lpf_flag, vel_lpf_cutoff_val, vel_lpf_order_val):
    """ Main pipeline to process pose data and calculate velocities with optional smoothing/filtering. """
    df = df_input.copy()
    time_s = df['Time'].values.astype(float)

    # Initial pose data from DataFrame
    current_positions_lab = df[['Box_Tx', 'Box_Ty', 'Box_Tz']].values
    original_rot_vectors_lab = df[['Box_Rx', 'Box_Ry', 'Box_Rz']].values

    current_quaternions_lab = ensure_quaternion_continuity(
        Rotation.from_rotvec(original_rot_vectors_lab).as_quat()
    )

    fs = 0.0
    if len(time_s) > 1:
        time_diffs = np.diff(time_s)
        if np.all(time_diffs > 1e-9):
            mean_dt = np.mean(time_diffs)
            fs = 1.0 / mean_dt
            print(f"  Info: Calculated sampling frequency (fs) = {fs:.2f} Hz for filtering.")
        else:
            print("  Warning: Time steps are not consistently positive or are too small. fs set to 0. Filters needing fs might be skipped.")
    if fs <= 0 and (use_pose_lpf_flag or use_vel_lpf_flag):
        print("  Warning: Valid sampling frequency (fs) could not be determined. Frequency-dependent filters will be skipped.")

    print("\n--- Starting Kinematics Processing Pipeline ---")

    # STAGE 1: Pose Data - Initial Low-Pass Filter
    if use_pose_lpf_flag and pose_lpf_cutoff_val is not None and pose_lpf_cutoff_val > 0 and fs > 0:
        print(f"  Applying STAGE 1: Pose Low-Pass Filter (Cutoff: {pose_lpf_cutoff_val} Hz, Order: {pose_lpf_order_val})")
        for i_col in range(current_positions_lab.shape[1]):
            current_positions_lab[:, i_col] = apply_butter_lowpass_filter_to_series(
                current_positions_lab[:, i_col], pose_lpf_cutoff_val, fs, pose_lpf_order_val)
        for i_col in range(current_quaternions_lab.shape[1]):
            current_quaternions_lab[:, i_col] = apply_butter_lowpass_filter_to_series(
                current_quaternions_lab[:, i_col], pose_lpf_cutoff_val, fs, pose_lpf_order_val)
    else:
        print("  Skipping STAGE 1: Pose Low-Pass Filter.")

    # STAGE 2: Pose Data - Moving Average
    if use_pose_ma_flag and pose_ma_window_val is not None and pose_ma_window_val > 1:
        print(f"  Applying STAGE 2: Pose Moving Average (Window: {pose_ma_window_val})")
        current_positions_lab = apply_ma_to_ndim_data(current_positions_lab, pose_ma_window_val)
        current_quaternions_lab = apply_ma_to_ndim_data(current_quaternions_lab, pose_ma_window_val)
    else:
        print("  Skipping STAGE 2: Pose Moving Average.")

    # STAGE 3: Velocity Calculation
    com_velocities_calculated_lab = np.zeros_like(current_positions_lab)
    angular_velocities_calculated_lab = np.zeros((len(df), 3))

    if velocity_method_flag == 'spline':
        print(f"  Executing STAGE 3: Velocity Calculation via SPLINE method")
        com_velocities_calculated_lab = calculate_translational_velocity_spline(
            current_positions_lab, time_s, spline_s_pos_val, spline_k_val)
        angular_velocities_calculated_lab = calculate_angular_velocity_spline_from_quaternions(
            current_quaternions_lab, time_s, spline_s_rot_val, spline_k_val)
    elif velocity_method_flag == 'finite_difference':
        print(f"  Executing STAGE 3: Velocity Calculation via FINITE DIFFERENCE method")
        for i_col in range(current_positions_lab.shape[1]):
            com_velocities_calculated_lab[:, i_col] = numerical_derivative_finite_diff(current_positions_lab[:, i_col], time_s)
        print(f"    FD Angular Sub-Method: {fd_angular_method_val} (applied to original rotation vectors)")
        if fd_angular_method_val == 'matrix':
            angular_velocities_calculated_lab = calculate_angular_velocity_matrix_based_fd(original_rot_vectors_lab, time_s)
        else:
            angular_velocities_calculated_lab = calculate_angular_velocity_quaternion_based_fd(original_rot_vectors_lab, time_s)
    else:
        raise ValueError(f"Invalid velocity_method_flag: {velocity_method_flag}")

    # STAGE 4: Velocity Data - Final Low-Pass Filter
    final_com_velocities_lab = com_velocities_calculated_lab
    final_angular_velocities_lab = angular_velocities_calculated_lab

    if use_vel_lpf_flag and vel_lpf_cutoff_val is not None and vel_lpf_cutoff_val > 0 and fs > 0:
        print(f"  Applying STAGE 4: Velocity Low-Pass Filter (Cutoff: {vel_lpf_cutoff_val} Hz, Order: {vel_lpf_order_val})")
        for i_col in range(final_com_velocities_lab.shape[1]):
            final_com_velocities_lab[:, i_col] = apply_butter_lowpass_filter_to_series(
                final_com_velocities_lab[:, i_col], vel_lpf_cutoff_val, fs, vel_lpf_order_val)
        for i_col in range(final_angular_velocities_lab.shape[1]):
            final_angular_velocities_lab[:, i_col] = apply_butter_lowpass_filter_to_series(
                final_angular_velocities_lab[:, i_col], vel_lpf_cutoff_val, fs, vel_lpf_order_val)
    else:
        print("  Skipping STAGE 4: Velocity Low-Pass Filter.")

    print("--- Kinematics Processing Pipeline Finished ---")

    # Update DataFrame with final calculated velocities
    df['CoM_Vx'] = final_com_velocities_lab[:,0]
    df['CoM_Vy'] = final_com_velocities_lab[:,1]
    df['CoM_Vz'] = final_com_velocities_lab[:,2]
    df['AngVel_Wx'] = final_angular_velocities_lab[:,0]
    df['AngVel_Wy'] = final_angular_velocities_lab[:,1]
    df['AngVel_Wz'] = final_angular_velocities_lab[:,2]

    # --- Corner Velocity Calculation ---
    print("Calculating corner velocities...")
    rotations_for_corners = Rotation.from_quat(current_quaternions_lab)

    for c_idx in range(LOCAL_BOX_CORNERS.shape[0]):
        corner_velocities_frame_t = np.zeros((len(df), 3))
        for i_frame in range(len(df)):
            R_lab_i = rotations_for_corners[i_frame].as_matrix()
            v_com_i = final_com_velocities_lab[i_frame, :]
            omega_i = final_angular_velocities_lab[i_frame, :]
            r_local_corner = LOCAL_BOX_CORNERS[c_idx]
            r_world_from_com = R_lab_i @ r_local_corner
            corner_velocities_frame_t[i_frame, :] = v_com_i + np.cross(omega_i, r_world_from_com)
        
        df[f'C{c_idx}_Vx'] = corner_velocities_frame_t[:, 0]
        df[f'C{c_idx}_Vy'] = corner_velocities_frame_t[:, 1]
        df[f'C{c_idx}_Vz'] = corner_velocities_frame_t[:, 2]
    print("Corner velocity calculation complete.")

    return df

def main():
    # ==============================================================================
    # USER-CONFIGURABLE PIPELINE STAGES & PARAMETERS
    # ==============================================================================
    # Set 'active' to True to enable a stage, False to disable. Parameters are used only if the stage is active.

    # --- Core Velocity Calculation Method ---
    # This can be overridden by a command-line argument for more flexibility if needed,
    # but for now, it's a top-level script configuration.
    # 'spline' or 'finite_difference'
    VELOCITY_CALCULATION_METHOD = 'spline'  # 'finite_difference' or 'spline'

    # --- STAGE 1: Pose Data Pre-processing: Initial Low-Pass Filter ---
    USE_POSE_LOWPASS_FILTER = False
    POSE_LPF_CUTOFF_HZ = 20.0   # Cutoff frequency in Hz
    POSE_LPF_ORDER = 4          # Filter order

    # --- STAGE 2: Pose Data Pre-processing: Moving Average ---
    USE_POSE_MOVING_AVERAGE = True
    POSE_MA_WINDOW = 3          # Window size (odd integer recommended, <=1 to effectively disable)

    # --- STAGE 3a: Spline Method Specific Parameters (used if VELOCITY_CALCULATION_METHOD is 'spline') ---
    SPLINE_S_FACTOR_POSITION = 1e-2 # Smoothing factor 's' for position spline. 0 for interpolation.
    SPLINE_S_FACTOR_ROTATION = 1e-3 # Smoothing factor 's' for rotation (quaternion) spline.
    SPLINE_DEGREE = 3               # Degree of the spline (e.g., 3 for cubic)

    # --- STAGE 3b: Finite Difference Method Specific Parameters (angular sub-method is from CLI arg) ---
    # (No extra script-level parameters here for FD beyond what CLI provides for angular method)

    # --- STAGE 4: Velocity Data Post-processing: Final Low-Pass Filter ---
    USE_VELOCITY_LOWPASS_FILTER = False
    VELOCITY_LPF_CUTOFF_HZ = 8.0 # Cutoff frequency in Hz
    VELOCITY_LPF_ORDER = 4        # Filter order
    # ==============================================================================

    parser = argparse.ArgumentParser(
        description="Calculates kinematics from box pose sequence CSV, producing a single integrated output. "
                    "Pipeline stages (filtering, smoothing, calculation method) are configured within the script."
    )
    parser.add_argument("--input_csv_path",
                        help="Path to input box pose sequence CSV (e.g., output of AlignBoxMain.py).")
    parser.add_argument("--output_csv_path",
                        help="Path to save the integrated output CSV with all kinematics data.")
    # Allow overriding the core velocity calculation method and FD angular method via CLI for flexibility
    parser.add_argument("--velocity_method_override", default=VELOCITY_CALCULATION_METHOD,
                        choices=['finite_difference', 'spline'],
                        help=f"Overrides the VELOCITY_CALCULATION_METHOD set in script. Default: {VELOCITY_CALCULATION_METHOD}")
    parser.add_argument("--fd_angular_method", default="quaternion", 
                        choices=['matrix', 'quaternion'],
                        help="Angular velocity sub-method if 'finite_difference' is chosen for velocity calculation. Default: quaternion.")

    args = parser.parse_args()

    # Use CLI override for velocity_method if provided
    actual_velocity_method = args.velocity_method_override

    print(f"--- Calculate Rigid Body Velocity (Integrated Output) ---")
    print(f"Input CSV: {args.input_csv_path}")
    print(f"Output CSV (Integrated): {args.output_csv_path}")
    print(f"BOX_DIMS for corner calculations from config.py: {BOX_DIMS.tolist()}")
    print(f"--- Pipeline Configuration ---")
    print(f"  Core Velocity Calculation Method: {actual_velocity_method}")
    print(f"  STAGE 1 - Pose LPF: Active={USE_POSE_LOWPASS_FILTER}, Cutoff={POSE_LPF_CUTOFF_HZ}Hz, Order={POSE_LPF_ORDER}")
    print(f"  STAGE 2 - Pose MA: Active={USE_POSE_MOVING_AVERAGE}, Window={POSE_MA_WINDOW}")
    if actual_velocity_method == 'spline':
        print(f"  STAGE 3a - Spline Params: S_Pos={SPLINE_S_FACTOR_POSITION}, S_Rot={SPLINE_S_FACTOR_ROTATION}, Degree={SPLINE_DEGREE}")
    elif actual_velocity_method == 'finite_difference':
        print(f"  STAGE 3b - FD Angular Sub-Method: {args.fd_angular_method}")
    print(f"  STAGE 4 - Velocity LPF: Active={USE_VELOCITY_LOWPASS_FILTER}, Cutoff={VELOCITY_LPF_CUTOFF_HZ}Hz, Order={VELOCITY_LPF_ORDER}")
    print(f"----------------------------------------------------------")

    try:
        df_input_data = pd.read_csv(args.input_csv_path)
        if df_input_data.empty:
            print("Input CSV file is empty. Exiting.")
            return
        
        df_kinematics_output = process_kinematics_pipeline(
            df_input_data,
            actual_velocity_method, # From CLI or script default
            USE_POSE_LOWPASS_FILTER, POSE_LPF_CUTOFF_HZ, POSE_LPF_ORDER,
            USE_POSE_MOVING_AVERAGE, POSE_MA_WINDOW,
            SPLINE_S_FACTOR_POSITION, SPLINE_S_FACTOR_ROTATION, SPLINE_DEGREE,
            args.fd_angular_method, # From CLI, used if FD method chosen
            USE_VELOCITY_LOWPASS_FILTER, VELOCITY_LPF_CUTOFF_HZ, VELOCITY_LPF_ORDER
        )

        df_kinematics_output.to_csv(args.output_csv_path, index=False, float_format='%.8f')
        print(f"Integrated kinematics data successfully saved to '{args.output_csv_path}'")
        
        print(f"--- Processing Complete ---")

    except FileNotFoundError:
        print(f"Error: Input file '{args.input_csv_path}' not found.")
    except ValueError as ve:
        print(f"ValueError during processing: {ve}")
        import traceback
        traceback.print_exc() # Print full traceback for ValueErrors too
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        import traceback
        traceback.print_exc()

# if name == 'main': main()
if __name__ == "__main__":
    main()

# --- END OF FILE CalculateRigidBodyVelocity.py ---