# --- START OF FILE CalculateRigidBodyVelocitySmoother.py ---
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
    y_np, t_np = np.asarray(y_values), t_values.astype(float)
    dy_dt = np.zeros_like(y_np, dtype=float)
    dt_0 = t_np[1] - t_np[0]
    dy_dt[0] = (y_np[1] - y_np[0]) / dt_0 if dt_0 > 1e-9 else 0.0
    for i in range(1, len(y_np) - 1):
        den = t_np[i+1] - t_np[i-1]
        if abs(den) <= 1e-9:
            dt_f, dt_b = t_np[i+1]-t_np[i], t_np[i]-t_np[i-1]
            if dt_f > 1e-9 and dt_b > 1e-9:
                dy_dt[i] = 0.5*(((y_np[i+1]-y_np[i])/dt_f) + ((y_np[i]-y_np[i-1])/dt_b))
            elif dt_f > 1e-9:
                dy_dt[i] = (y_np[i+1]-y_np[i])/dt_f
            elif dt_b > 1e-9:
                dy_dt[i] = (y_np[i]-y_np[i-1])/dt_b
            else:
                dy_dt[i] = 0.0
        else:
            dy_dt[i] = (y_np[i+1]-y_np[i-1])/den
    if len(y_np) > 1:
        dt_N = t_np[-1] - t_np[-2]
        dy_dt[-1] = (y_np[-1]-y_np[-2])/dt_N if dt_N > 1e-9 else 0.0
    return dy_dt

def ensure_quaternion_continuity(quaternions_scipy_fmt):
    """Ensures quaternion continuity (SciPy format [x,y,z,w]) by flipping signs."""
    q_proc = np.copy(quaternions_scipy_fmt)
    for i in range(1, len(q_proc)):
        if np.dot(q_proc[i-1], q_proc[i]) < 0:
            q_proc[i] *= -1
    return q_proc

# --- Velocity Calculation Core Functions ---
# ... (이하 기존 코드 동일, 생략) ...

# --- Main Processing Pipeline Function ---
# ... (이하 기존 코드 동일, 생략) ...

def main():
    # ============================================================================== 
    # USER-CONFIGURABLE PIPELINE STAGES & PARAMETERS 
    # ============================================================================== 
    # ... (이하 기존 코드 동일, 생략) ...

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

# --- END OF FILE CalculateRigidBodyVelocitySmoother.py ---