--- START OF FILE NewSmoothMarkerData.py ---
import argparse
import pandas as pd
import numpy as np
from scipy.signal import butter, filtfilt
import config

MARKER_PREFIX_ID = config.MARKER_PREFIX_ID

def calculate_sampling_frequency(time_series_s):
    """ Calculates the average sampling frequency from a pandas Series of time values. """
    if len(time_series_s) < 2:
        print("Warning: Not enough data points in Time series to calculate sampling frequency (need at least 2).")
        return None

    try:
        time_values = pd.to_numeric(time_series_s, errors='coerce')
    except Exception as e:
        print(f"Warning: Could not convert Time series to numeric due to an error: {e}. Cannot calculate sampling frequency.")
        return None

    if time_values.isna().all():
        print("Warning: All time values are non-numeric or NaN after conversion. Cannot calculate sampling frequency.")
        return None

    time_values_cleaned = time_values.dropna()
    if len(time_values_cleaned) < 2:
        print("Warning: Not enough valid numeric time data points after cleaning NaNs (need at least 2).")
        return None

    time_diffs = time_values_cleaned.diff().dropna()
    if time_diffs.empty:
        print("Warning: No valid time differences found (e.g., only one unique time value after NaNs). Cannot calculate sampling frequency.")
        return None

    if (time_diffs <= 0).any():
        num_non_positive = (time_diffs <= 0).sum()
        print(f"Warning: Found {num_non_positive} non-positive or zero time differences. This may indicate issues with time data (e.g., non-increasing time).")
        time_diffs = time_diffs[time_diffs > 0]
        if time_diffs.empty:
            print("Warning: All time differences were non-positive. Cannot calculate sampling frequency.")
            return None

    mean_delta_t = time_diffs.mean()
    if mean_delta_t <= 1e-9:
        print(f"Warning: Mean delta T is non-positive or extremely small ({mean_delta_t:.2e}). Cannot calculate valid sampling frequency.")
        return None

    fs = 1.0 / mean_delta_t
    print(f"Info: Estimated sampling frequency: {fs:.2f} Hz (based on mean Δt = {mean_delta_t:.4f} s)")
    return fs

def apply_smoothing_to_series(data_series_s, method_sequence, fs, butter_cutoff_hz, butter_order, ma_window_size):
    """ Applies a sequence of smoothing methods to a data series. Handles NaN values by interpolation and ffill/bfill before smoothing. """
    smoothed_series = data_series_s.copy()

    # Handle NaN values before smoothing
    original_nan_mask = smoothed_series.isna()
    if original_nan_mask.any():
        smoothed_series = smoothed_series.interpolate(method='linear')
        smoothed_series = smoothed_series.fillna(method='ffill')
        smoothed_series = smoothed_series.fillna(method='bfill')
        if smoothed_series.isna().any():
            return data_series_s

    for method_idx, method in enumerate(method_sequence):
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

            required_len = 3 * (butter_order + 1)
            if len(smoothed_series) > required_len:
                try:
                    values_to_filter = smoothed_series.astype(np.float64).values
                    filtered_values = filtfilt(b, a, values_to_filter)
                    smoothed_series = pd.Series(filtered_values, index=smoothed_series.index, name=smoothed_series.name)
                except ValueError as e:
                    print(f"  Error: Failed to apply Butterworth filter to series {data_series_s.name}: {e}. Check data length and NaN values. Skipping.")
            else:
                print(f"  Warning: Data series length ({len(smoothed_series)}) for {data_series_s.name} is too short for Butterworth filter (order {butter_order}, requires > {required_len}). Skipping Butterworth.")

        elif method == 'moving_average':
            if ma_window_size <= 1:
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
    """ Smooths X, Y, Z coordinate data for all markers in the DataFrame. """
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
            original_series = df[col_name]
            numeric_series = pd.to_numeric(original_series, errors='coerce')

            if numeric_series.isna().all() and not original_series.isna().all():
                print(f"  Warning: Column {col_name} for marker {marker_id} became all NaNs after trying to convert to numeric. Original non-numeric data was present. Skipping smoothing for this column.")
                smoothed_df[col_name] = original_series
                continue
            elif numeric_series.isna().all():
                print(f"  Info: Column {col_name} for marker {marker_id} contains all NaN or non-coercible values. Skipping smoothing for this column.")
                smoothed_df[col_name] = original_series
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
            smoothed_df.rename(columns={col_name: MARKER_PREFIX_ID + col_name}, inplace=True)

    return smoothed_df

def main():
    # --- User-configurable parameters (editable in script) ---
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
        processed_df.to_csv(args.output_csv_path, index=False, float_format='%.8f')
        print(f"--- Smoothing Complete ---")
        print(f"Smoothed data successfully saved to '{args.output_csv_path}'")
        print(f"--------------------------")
    except Exception as e:
        print(f"Error writing smoothed data to output CSV file '{args.output_csv_path}': {e}")

# if name == 'main': main()
if __name__ == "__main__":
    main()

# --- END OF FILE