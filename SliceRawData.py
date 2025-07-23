# --- START OF FILE SliceRawData.py ---
import argparse
import os

def slice_raw_data_csv(input_filepath, output_filepath, filter_by_type, start_value, end_value):
    """ Slices a raw experimental data CSV file based on frame number or time range. The first 8 lines (header/metadata) are preserved. Data lines are filtered.

    Args:
        input_filepath (str): Path to the source raw experimental data CSV file.
        output_filepath (str): Path for the sliced raw CSV file to be saved.
        filter_by_type (str): Criterion for filtering ('frame' or 'time').
        start_value (float or int): Starting value for the filter range (inclusive).
        end_value (float or int): Ending value for the filter range (inclusive).
    """
    print(f"--- Slicing Raw Data ---")
    print(f"Input file: {input_filepath}")
    print(f"Output file: {output_filepath}")
    print(f"Filter by: {filter_by_type}")
    print(f"Start value: {start_value}, End value: {end_value}")

    # Validate filter type
    if filter_by_type not in ['frame', 'time']:
        print(f"Error: Invalid filter_by_type '{filter_by_type}'. Must be 'frame' or 'time'.")
        return

    # Convert start/end values to appropriate types
    try:
        if filter_by_type == 'frame':
            start_val_typed = int(start_value)
            end_val_typed = int(end_value)
        else: # 'time'
            start_val_typed = float(start_value)
            end_val_typed = float(end_value)
    except ValueError:
        print(f"Error: Could not convert start/end values to the correct type for '{filter_by_type}' filter.")
        return

    if start_val_typed > end_val_typed:
        print(f"Error: Start value ({start_val_typed}) cannot be greater than end value ({end_val_typed}).")
        return

    lines_read = 0
    lines_written = 0
    header_lines_to_copy = 8 # As per AlignBoxInputGenbyExperiment.py structure

    try:
        with open(input_filepath, mode='r', encoding='utf-8-sig') as infile, \
             open(output_filepath, mode='w', encoding='utf-8', newline='') as outfile:

            for i, line_content in enumerate(infile):
                lines_read += 1
                if i < header_lines_to_copy:
                    outfile.write(line_content)
                    lines_written += 1
                    continue # Move to next line after writing header

                # --- Process Data Lines (from 9th line, index 8 onwards) ---
                current_data_line_raw = line_content.strip()
                if not current_data_line_raw: # Skip empty lines
                    continue

                current_data_fields = [field.strip() for field in current_data_line_raw.split(',')]

                # Extract FrameNumber (col 0) and Time (col 1)
                frame_number_str_raw = ""
                time_value_str_raw = ""
                current_value_for_filter = None

                try:
                    if len(current_data_fields) > 0:
                        frame_number_str_raw = current_data_fields[0]
                    if len(current_data_fields) > 1:
                        time_value_str_raw = current_data_fields[1]

                    if filter_by_type == 'frame':
                        if frame_number_str_raw:
                            try:
                                current_value_for_filter = int(float(frame_number_str_raw))
                            except ValueError:
                                continue # Skip if frame number cannot be parsed
                        else:
                            continue
                    elif filter_by_type == 'time':
                        if time_value_str_raw:
                            try:
                                current_value_for_filter = float(time_value_str_raw)
                            except ValueError:
                                continue # Skip if time cannot be parsed
                        else:
                            continue
                except IndexError:
                    continue # Skip malformed lines

                # Apply filter
                if current_value_for_filter is not None:
                    if start_val_typed <= current_value_for_filter <= end_val_typed:
                        outfile.write(line_content)
                        lines_written += 1
                # else: (already handled by continue statements above if parsing failed)
                    # print(f"Debug: Line {lines_read}, value for filter was None.")

        print(f"--- Slicing Complete ---")
        print(f"Total lines read: {lines_read}")
        print(f"Total lines written (including headers): {lines_written}")
        if lines_written <= header_lines_to_copy and lines_read > header_lines_to_copy :
            print(f"Warning: No data lines matched the filter criteria [{start_val_typed} - {end_val_typed}] for type '{filter_by_type}'.")
        elif lines_read == 0 :
            print(f"Warning: Input file '{input_filepath}' was empty or could not be read properly.")

    except FileNotFoundError:
        print(f"Error: Input file '{input_filepath}' not found.")
    except Exception as e:
        print(f"An error occurred during slicing: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Slices a raw experimental data CSV based on frame number or time range. The first 8 lines (headers/metadata) are preserved."
    )
    parser.add_argument("input_raw_csv", type=str, help="Path to the input raw experimental data CSV file.")
    parser.add_argument("output_sliced_csv", type=str, help="Path to save the sliced (filtered) raw CSV file.")
    parser.add_argument("--filter_by", type=str, required=True, choices=['frame', 'time'], help="Criterion for filtering: 'frame' or 'time'.")
    parser.add_argument("--start_val", type=str, required=True, help="Starting value for the filter range (inclusive). Integer for 'frame', float for 'time'.")
    parser.add_argument("--end_val", type=str, required=True, help="Ending value for the filter range (inclusive). Integer for 'frame', float for 'time'.")

    args = parser.parse_args()

    slice_raw_data_csv(
        args.input_raw_csv,
        args.output_sliced_csv,
        args.filter_by,
        args.start_val,
        args.end_val
    )

# --- END OF FILE SliceRawData.py ---