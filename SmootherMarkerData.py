# --- START OF FILE SmoothMarkerData.py ---
import argparse
import pandas as pd
import numpy as np
from scipy.signal import butter, filtfilt

def calculate_sampling_frequency(time_series_s):
    """
    Calculates the average sampling frequency from a pandas Series of time values.
    Args:
        time_series_s (pd.Series): A pandas Series containing time values.
    Returns:
        float: Estimated sampling frequency in Hz, or None if calculation fails.
    """
    if len(time_series_s) < 2:
        print("Warning: Not enough data points in Time series to calculate sampling frequency (need at least 2).")
        return None

    try:
        # Ensure time values are numeric, converting if necessary. Coerce errors to NaT/NaN.
        time_values = pd.to_numeric(time_series_s, errors='coerce')
    except Exception as e: # Broad exception for unexpected conversion issues
        print(f"Warning: Could not convert Time series to numeric due to an error: {e}. Cannot calculate sampling frequency.")
        return None

    if time_values.isna().all():
        print("Warning: All time values are non-numeric or NaN after conversion. Cannot calculate sampling frequency.")
        return None
    
    # Drop NaNs that might have been coerced if original data had non-numeric strings
    time_values_cleaned = time_values.dropna()
    if len(time_values_cleaned) < 2:
        print("Warning: Not enough valid numeric time data points after cleaning NaNs (need at least 2).")
        return None

    time_diffs = time_values_cleaned.diff().dropna() # Calculate differences and drop first NaN

    if time_diffs.empty:
        print("Warning: No valid time differences found (e.g., only one unique time value after NaNs). Cannot calculate sampling frequency.")
        return None
        
    if (time_diffs <= 0).any():
        num_non_positive = (time_diffs <= 0).sum()
        print(f"Warning: Found {num_non_positive} non-positive or zero time differences. This may indicate issues with time data (e.g., non-increasing time).")
        # Filter out non-positive differences before calculating mean
        time_diffs = time_diffs[time_diffs > 0]
        if time_diffs.empty:
            print("Warning: All time differences were non-positive. Cannot calculate sampling frequency.")
            return None
            
    mean_delta_t = time_diffs.mean()
    
    if mean_delta_t <= 1e-9: # Effectively zero or negative
        print(f"Warning: Mean delta T is non-positive or extremely small ({mean_delta_t:.2e}). Cannot calculate valid sampling frequency.")
        return None
        
    fs = 1.0 / mean_delta_t
    print(f"Info: Estimated sampling frequency: {fs:.2f} Hz (based on mean Δt = {mean_delta_t:.4f} s)")
    return fs

def apply_smoothing_to_series(data_series_s, method_sequence, fs,
                              butter_cutoff_hz, butter_order, ma_window_size):
    """
    Applies a sequence of smoothing methods to a data series.
    Handles NaN values by interpolation and ffill/bfill before smoothing.
    Args:
        data_series_s (pd.Series): The input data series.
        method_sequence (list): List of strings specifying smoothing methods ('butterworth', 'moving_average').
        fs (float): Sampling frequency.
        butter_cutoff_hz (float): Butterworth cutoff frequency in Hz.
        butter_order (int): Butterworth filter order.
        ma_window_size (int): Moving average window size.
    Returns:
        pd.Series: The smoothed data series.
    """
    smoothed_series = data_series_s.copy()

    # Handle NaN values before smoothing
    original_nan_mask = smoothed_series.isna()
    if original_nan_mask.any():
        # print(f"  Debug: Series for {data_series_s.name} has {original_nan_mask.sum()} NaN(s). Applying interpolation.")
        smoothed_series = smoothed_series.interpolate(method='linear')
        smoothed_series = smoothed_series.fillna(method='ffill') # Fill remaining NaNs at the beginning
        smoothed_series = smoothed_series.fillna(method='bfill') # Fill remaining NaNs at the end (if any)
        
        if smoothed_series.isna().any(): # If still NaNs (e.g., all NaNs in original series)
            # print(f"  Warning: Could not fill all NaNs in series {data_series_s.name}. Returning original series for this column.")
            return data_series_s 

    for method_idx, method in enumerate(method_sequence):
        # print(f"  Debug: Applying method '{method}' to series {data_series_s.name} (Pass {method_idx+1})")
        if method == 'butterworth':
            if fs is None or fs <= 0:
                print(f"  Warning: Invalid sampling frequency ({fs}) for series {data_series_s.name}. Skipping Butterworth filter.")
                continue
            
            nyquist_freq = 0.5 * fs
            if not (0 < butter_cutoff_hz < nyquist_freq):
                print(f"  Warning: Butterworth cutoff frequency ({butter_cutoff_hz} Hz) must be positive and less than Nyquist frequency ({nyquist_freq} Hz) for series {data_series_s.name}. Skipping Butterworth filter.")
                continue

            wn = butter_cutoff_hz / nyquist_freq 
            
            try:
                b, a = butter(butter_order, wn, btype='low', analog=False)
            except ValueError as e:
                print(f"  Error: Failed to design Butterworth filter for series {data_series_s.name}: {e}. Skipping.")
                continue

            required_len = 3 * (butter_order + 1) # Heuristic for filtfilt padlen
            if len(smoothed_series) > required_len:
                try:
                    # Ensure input to filtfilt is a NumPy array of float64
                    values_to_filter = smoothed_series.astype(np.float64).values
                    filtered_values = filtfilt(b, a, values_to_filter)
                    smoothed_series = pd.Series(filtered_values, index=smoothed_series.index, name=smoothed_series.name)
                except ValueError as e: # Handles issues like data too short, or NaNs if any slipped through
                    print(f"  Error: Failed to apply Butterworth filter to series {data_series_s.name}: {e}. Check data length and NaN values. Skipping.")
            else:
                print(f"  Warning: Data series length ({len(smoothed_series)}) for {data_series_s.name} is too short for Butterworth filter (order {butter_order}, requires > {required_len}). Skipping Butterworth.")
        
        elif method == 'moving_average':
            if ma_window_size <= 1:
                # print(f"  Info: Moving average window size ({ma_window_size}) for series {data_series_s.name} is <= 1. No MA smoothing applied.")
                continue 
            
            current_ma_window_size = int(ma_window_size)
            if len(smoothed_series) < current_ma_window_size:
                 print(f"  Warning: Data series length ({len(smoothed_series)}) for {data_series_s.name} is shorter than MA window size ({current_ma_window_size}). MA will use min_periods=1.")
            
            if current_ma_window_size % 2 == 0:
                print(f"  Info: MA window size ({current_ma_window_size}) for series {data_series_s.name} is even. An odd window size is generally preferred for a symmetric, centered moving average.")
            
            try:
                smoothed_series = smoothed_series.rolling(window=current_ma_window_size, center=True, min_periods=1).mean()
            except Exception as e:
                print(f"  Error: Failed to apply moving average to series {data_series_s.name}: {e}. Skipping.")
        else:
            print(f"  Warning: Unknown smoothing method '{method}' for series {data_series_s.name}. Skipping.")
            
    return smoothed_series

def smooth_marker_data_in_df(df, method_sequence, butter_cutoff_hz, butter_order, ma_window_size):
    """
    Smooths X, Y, Z coordinate data for all markers in the DataFrame.
    Args:
        df (pd.DataFrame): Input DataFrame with marker data.
        method_sequence (list): List of smoothing methods.
        butter_cutoff_hz (float): Butterworth cutoff Hz.
        butter_order (int): Butterworth order.
        ma_window_size (int): Moving average window size.
    Returns:
        pd.DataFrame: DataFrame with smoothed coordinate data, or None if critical error.
    """
    if 'Time' not in df.columns:
        print("Error: 'Time' column not found in CSV. This is required to calculate sampling frequency for filtering.")
        return None
    
    fs = calculate_sampling_frequency(df['Time'])
    if fs is None:
        print("Error: Could not determine sampling frequency from 'Time' column. Aborting smoothing process.")
        return None

    marker_ids_found = set()
    for col_name in df.columns:
        if col_name.endswith("_X"):
            marker_id = col_name[:-2]
            if f"{marker_id}_Y" in df.columns and f"{marker_id}_Z" in df.columns:
                marker_ids_found.add(marker_id)
    
    if not marker_ids_found:
        print("Info: No marker coordinate columns (e.g., ID_X, ID_Y, ID_Z) found in the CSV. Returning original data.")
        return df

    print(f"Info: Found the following marker IDs to process: {sorted(list(marker_ids_found))}")
    smoothed_df = df.copy()

    for marker_id in sorted(list(marker_ids_found)):
        print(f"Processing marker: {marker_id}")
        for axis in ['X', 'Y', 'Z']:
            col_name = f"{marker_id}_{axis}"
            # print(f"  Smoothing column: {col_name}")
            
            original_series = df[col_name]
            # Ensure the series is numeric, coercing non-numeric to NaN
            # This is important as filters expect numeric data.
            numeric_series = pd.to_numeric(original_series, errors='coerce') 

            if numeric_series.isna().all() and not original_series.isna().all():
                 print(f"  Warning: Column {col_name} for marker {marker_id} became all NaNs after trying to convert to numeric. Original non-numeric data was present. Skipping smoothing for this column.")
                 smoothed_df[col_name] = original_series # Keep original non-numeric data
                 continue
            elif numeric_series.isna().all(): # Original was already all NaNs or uncoercible
                 print(f"  Info: Column {col_name} for marker {marker_id} contains all NaN or non-coercible values. Skipping smoothing for this column.")
                 smoothed_df[col_name] = original_series # Keep as is
                 continue

            smoothed_values = apply_smoothing_to_series(
                numeric_series, 
                method_sequence, 
                fs,
                butter_cutoff_hz, 
                butter_order, 
                ma_window_size
            )
            smoothed_df[col_name] = smoothed_values
            
    return smoothed_df

def main():
    # --- User-configurable parameters (editable in script) ---
    # Sequence of smoothing methods to apply.
    # Options for each element in the list: 'butterworth', 'moving_average'
    # Example: Butterworth only: SMOOTHING_METHOD_SEQUENCE = ['butterworth']
    # Example: Moving average only: SMOOTHING_METHOD_SEQUENCE = ['moving_average']
    # Example: MA then Butterworth: SMOOTHING_METHOD_SEQUENCE = ['moving_average', 'butterworth']
    SMOOTHING_METHOD_SEQUENCE = ['butterworth', 'moving_average'] # Default: Butterworth then MA

    # Butterworth low-pass filter parameters
    BUTTERWORTH_CUTOFF_FREQ_HZ = 10.0  # Cutoff frequency in Hz (e.g., 10 Hz for human motion)
    BUTTERWORTH_ORDER = 4             # Filter order (e.g., 2, 3, or 4)

    # Moving Average filter parameters
    MA_WINDOW_SIZE = 3                # Window size (an odd integer like 3, 5, 7 is common for good centering)
    # --- End of User-configurable parameters ---

    parser = argparse.ArgumentParser(
        description="Smooths marker coordinate data (X, Y, Z) from a wide-formatted CSV file. "
                    "Applies a sequence of filtering methods (e.g., Butterworth, Moving Average). "
                    "Parameters for filters are set within the script."
    )
    parser.add_argument("input_csv_path", type=str, 
                        help="Path to the input wide-format CSV file containing marker data (e.g., output of AlignBoxInputGenbyExperiment.py).")
    parser.add_argument("output_csv_path", type=str, 
                        help="Path where the CSV file with smoothed marker data will be saved.")
    
    args = parser.parse_args()

    print(f"--- Starting Marker Data Smoothing ---")
    print(f"Input CSV: {args.input_csv_path}")
    print(f"Output CSV: {args.output_csv_path}")
    print(f"Configured smoothing sequence: {SMOOTHING_METHOD_SEQUENCE}")
    if 'butterworth' in SMOOTHING_METHOD_SEQUENCE:
        print(f"  Butterworth params: Cutoff Frequency = {BUTTERWORTH_CUTOFF_FREQ_HZ} Hz, Order = {BUTTERWORTH_ORDER}")
    if 'moving_average' in SMOOTHING_METHOD_SEQUENCE:
        print(f"  Moving Average params: Window Size = {MA_WINDOW_SIZE}")
    print(f"------------------------------------")

    try:
        # Use low_memory=False if CSV has mixed types in columns, which can sometimes cause issues
        df = pd.read_csv(args.input_csv_path, low_memory=False)
    except FileNotFoundError:
        print(f"Error: Input file '{args.input_csv_path}' not found.")
        return
    except Exception as e:
        print(f"Error reading input CSV file '{args.input_csv_path}': {e}")
        return

    if df.empty:
        print("Info: Input CSV file is empty. Nothing to process.")
        try:
            # Still attempt to write an empty file or header if that's desired behavior
            df.to_csv(args.output_csv_path, index=False)
            print(f"Info: Empty input, an empty CSV file was saved to '{args.output_csv_path}'")
        except Exception as e:
            print(f"Error writing empty output CSV file: {e}")
        return

    processed_df = smooth_marker_data_in_df(df, 
                                            SMOOTHING_METHOD_SEQUENCE,
                                            BUTTERWORTH_CUTOFF_FREQ_HZ,
                                            BUTTERWORTH_ORDER,
                                            MA_WINDOW_SIZE)

    if processed_df is None:
        print("Critical error during smoothing process. Output file will not be saved.")
        return

    try:
        # Save with a common float format for consistency
        processed_df.to_csv(args.output_csv_path, index=False, float_format='%.8f')
        print(f"--- Smoothing Complete ---")
        print(f"Smoothed data successfully saved to '{args.output_csv_path}'")
        print(f"--------------------------")
    except Exception as e:
        print(f"Error writing smoothed data to output CSV file '{args.output_csv_path}': {e}")

if __name__ == '__main__':
    main()
# --- END OF FILE SmoothMarkerData.py ---