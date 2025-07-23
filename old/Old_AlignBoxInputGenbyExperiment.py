# --- START OF FILE AlignBoxInputGenbyExperiment.py (Modified as per original structure) ---

import csv
import argparse

# ### MODIFIED ###: FACE_PREFIX_TO_INFO will be imported from config.py
# Original FACE_PREFIX_TO_INFO dictionary is now moved to config.py
try:
    import config # Attempt to import the config file
    FACE_PREFIX_TO_INFO = config.FACE_PREFIX_TO_INFO
    print("Successfully loaded FACE_PREFIX_TO_INFO from config.py in AlignBoxInputGenbyExperiment.")
except ImportError:
    print("Error: Could not import config.py. Make sure it's in the same directory or Python path.")
    print("Using fallback default configurations for FACE_PREFIX_TO_INFO in AlignBoxInputGenbyExperiment.")
    # Fallback definition if config.py is not available
    FACE_PREFIX_TO_INFO = {
        'F': "FRONT",
        'B': "BACK",
        'L': "LEFT",
        'R': "RIGHT",
        'T': "TOP",
        'FA': "FRONT",  # Front Additional, treated as FRONT
        'BA': "BACK",  # Back Additional, treated as BACK
        'M': "BOTTOM"  # Defined by rule, though not attached in the experiment
    }
except AttributeError:
    print("Error: FACE_PREFIX_TO_INFO not found in config.py.")
    print("Using fallback default configurations for FACE_PREFIX_TO_INFO in AlignBoxInputGenbyExperiment.")
    # Fallback definition if attribute is missing in config.py
    FACE_PREFIX_TO_INFO = {
        'F': "FRONT",
        'B': "BACK",
        'L': "LEFT",
        'R': "RIGHT",
        'T': "TOP",
        'FA': "FRONT",  # Front Additional, treated as FRONT
        'BA': "BACK",  # Back Additional, treated as BACK
        'M': "BOTTOM"  # Defined by rule, though not attached in the experiment
    }
# ### END OF MODIFICATION ###


# OUTPUT_CSV_HEADERS will be generated dynamically.

def parse_experiment_raw_data_all_frames(input_filepath, output_filepath):
    """
    Parses all data frames from an experimental raw data CSV file (e.g., from a motion capture system)
    and converts the marker information into a "wide" format CSV file.
    In the output, each row represents a single frame. Columns include FrameNumber, Time,
    and then FaceInfo, X, Y, Z coordinates for each detected marker
    (e.g., M1_FaceInfo, M1_X, M1_Y, M1_Z, M2_FaceInfo, M2_X...).

    This function targets 'Position' data for markers that meet these criteria:
    - Type: "Rigid Body Marker"
    - Parent: Has a parent (belongs to a specific Rigid Body)
    - Name: Contains a colon (':') separating the Rigid Body name and marker identifier.

    Args:
        input_filepath (str): Path to the source experimental data CSV file.
        output_filepath (str): Path for the converted CSV file to be saved.
    """
    try:
        with open(input_filepath, mode='r', encoding='utf-8-sig') as infile:
            lines = infile.readlines()
    except FileNotFoundError:
        print(f"Error: Input file '{input_filepath}' not found.")
        return
    except Exception as e:
        print(f"Error reading input file: {e}")
        return

    if len(lines) < 9:
        print(
            "Error: File does not have enough data lines (minimum 9 lines required for metadata, 7 header lines, and at least 1 data line).")
        return

    # Extract header information (line numbers are 0-indexed for Python lists)
    # Based on VDTest_S4.csv structure:
    # Line 3 (index 2): Type information
    # Line 4 (index 3): Name information
    # Line 5 (index 4): ID information
    # Line 6 (index 5): Parent information
    # Line 7 (index 6): Category information (Position, Rotation)
    # Line 8 (index 7): Component information (X, Y, Z, W)
    # Line 9 (index 8): First actual data frame line
    try:
        type_header_raw = lines[2].strip()
        name_header_raw = lines[3].strip()
        id_header_raw = lines[4].strip()
        parent_header_raw = lines[5].strip()
        category_header_raw = lines[6].strip()
        component_header_raw = lines[7].strip()

        type_header = [h.strip() for h in type_header_raw.split(',')]
        name_header = [h.strip() for h in name_header_raw.split(',')]
        id_header = [h.strip() for h in id_header_raw.split(',')]
        parent_header = [h.strip() for h in parent_header_raw.split(',')]
        category_header = [h.strip() for h in category_header_raw.split(',')]
        component_header = [h.strip() for h in component_header_raw.split(',')]

    except IndexError:
        print(
            "Error: An error occurred while parsing header lines in the CSV file (fewer lines than expected). Please check the file format.")
        return
    except Exception as e:
        print(f"Exception during header parsing: {e}")
        return

    processed_frames_data = []
    ordered_unique_marker_identifiers = []  # To maintain the order of markers as they are first encountered/processed
    seen_marker_identifiers = set()  # To track unique marker identifiers efficiently

    # Process actual data lines (starting from line 9, index 8)
    for frame_line_index in range(8, len(lines)):
        current_data_line_raw = lines[frame_line_index].strip()
        if not current_data_line_raw:  # Skip empty lines
            continue

        current_data_line = [d.strip() for d in current_data_line_raw.split(',')]

        # Extract FrameNumber and Time from the current data line
        frame_number_str = ""
        time_value_str = ""
        try:
            if len(current_data_line) > 0:
                frame_number_str = current_data_line[0]  # First column for FrameNumber
            if len(current_data_line) > 1:
                time_value_str = current_data_line[1]  # Second column for Time

            try:
                frame_number = str(int(float(frame_number_str))) if frame_number_str else str(frame_line_index - 8 + 1)
            except ValueError:
                frame_number = str(frame_line_index - 8 + 1)
                if frame_number_str:
                    print(
                        f"Warning: Could not parse frame number '{frame_number_str}' from line {frame_line_index + 1}. Using sequential frame number {frame_number}.")

            time_value = "N/A"
            if time_value_str:
                try:
                    float(time_value_str)
                    time_value = time_value_str
                except ValueError:
                    print(
                        f"Warning: Could not parse time value '{time_value_str}' from line {frame_line_index + 1}. Using '{time_value}'.")

        except IndexError:
            print(
                f"Warning: Could not read frame number or time from line {frame_line_index + 1} (line too short or malformed). Skipping this line.")
            continue

        current_frame_output_dict = {'FrameNumber': frame_number, 'Time': time_value}

        # Determine the minimum length among all headers and the current data line
        try:
            min_len = min(len(type_header), len(name_header), len(id_header),
                          len(parent_header), len(category_header),
                          len(component_header), len(current_data_line))
        except ValueError:
            print(
                f"Error: Some header lines or data line {frame_line_index + 1} might be empty or failed to parse. Skipping this frame.")
            continue

        # Use copies of headers sliced to min_len for processing this line
        temp_type_header = type_header[:min_len]
        temp_name_header = name_header[:min_len]
        # temp_id_header = id_header[:min_len] # Not used in loop, can be omitted if not needed elsewhere
        temp_parent_header = parent_header[:min_len]
        temp_category_header = category_header[:min_len]
        temp_component_header = component_header[:min_len]
        temp_current_data_line = current_data_line[:min_len] # Data line also sliced

        if len(current_data_line) < min_len: # This check is technically redundant if temp_current_data_line is used
                                             # but kept for explicitness as in original.
            print(
                f"Warning: Data line {frame_line_index + 1} (Frame {frame_number}) has fewer columns ({len(current_data_line)}) than some headers. Processing based on {min_len} columns.")

        markers_found_in_this_frame = 0
        # Iterate through columns to find marker data
        # Loop up to min_len - 3 (or range(min_len - 2)) because we access i, i+1, i+2
        for i in range(min_len - 2):  # Ensure there's room for X, Y, Z
            current_type = temp_type_header[i]
            current_parent = temp_parent_header[i]
            full_marker_name = temp_name_header[i]

            is_target_marker_x = (
                    current_type == "Rigid Body Marker" and
                    current_parent and # Ensure it has a parent (belongs to a specific Rigid Body)
                    ':' in full_marker_name and # Name contains a colon
                    temp_category_header[i] == "Position" and # Category is Position
                    temp_component_header[i].upper() == 'X' # Component is X
            )

            if is_target_marker_x:
                # Check if the next two columns are Y and Z components
                is_y_component_valid = (
                        # temp_type_header[i+1] == current_type and # Assuming type is same for Y,Z
                        # temp_name_header[i+1] ... similar for name if needed for strict check
                        temp_category_header[i + 1] == "Position" and
                        temp_component_header[i + 1].upper() == 'Y'
                )
                is_z_component_valid = (
                        # temp_type_header[i+2] == current_type and
                        temp_category_header[i + 2] == "Position" and
                        temp_component_header[i + 2].upper() == 'Z'
                )

                if is_y_component_valid and is_z_component_valid:
                    name_parts = full_marker_name.split(':', 1)
                    if len(name_parts) < 2 or not name_parts[1]: # Check if marker identifier part exists
                        continue # Skip if marker identifier is missing

                    marker_identifier = name_parts[1].replace(" ", "_") # Use part after colon, replace spaces

                    # Determine FaceInfo based on the prefix of the marker identifier
                    prefix_for_face = ""
                    if marker_identifier.startswith("FA"):
                        prefix_for_face = "FA"
                    elif marker_identifier.startswith("BA"):
                        prefix_for_face = "BA"
                    elif marker_identifier: # Check if marker_identifier is not empty
                        prefix_for_face = marker_identifier[0]
                    
                    # ### MODIFIED ###: FACE_PREFIX_TO_INFO is now sourced from config or fallback
                    face_info = FACE_PREFIX_TO_INFO.get(prefix_for_face.upper())
                    face_info_str = face_info if face_info is not None else ""

                    if face_info is None and prefix_for_face: # Only warn if prefix existed but had no mapping
                        print(
                            f"Warning: For frame {frame_number}, marker '{full_marker_name}', prefix '{prefix_for_face}' has no face info mapping. FaceInfo will be empty.")

                    try:
                        # Accessing data from temp_current_data_line ensures it's within bounds
                        x_val = temp_current_data_line[i] 
                        y_val = temp_current_data_line[i + 1]
                        z_val = temp_current_data_line[i + 2]

                        if not x_val or not y_val or not z_val:  # Check for empty coordinate values
                            continue
                        try:
                            float(x_val);
                            float(y_val);
                            float(z_val)  # Validate if coordinates are numeric
                        except ValueError:
                            print(
                                f"Warning: For frame {frame_number}, marker '{full_marker_name}', coordinate values ('{x_val}', '{y_val}', '{z_val}') include non-numeric. Skipping this marker for this frame.")
                            continue

                        # Define column names for FaceInfo, X, Y, Z for this marker
                        col_face_name = f"{marker_identifier}_FaceInfo"
                        col_x_name = f"{marker_identifier}_X"
                        col_y_name = f"{marker_identifier}_Y"
                        col_z_name = f"{marker_identifier}_Z"

                        # Add marker identifier to ordered list if new, to maintain column order
                        if marker_identifier not in seen_marker_identifiers:
                            ordered_unique_marker_identifiers.append(marker_identifier)
                            seen_marker_identifiers.add(marker_identifier)

                        # Add FaceInfo, X, Y, Z data to the current frame's dictionary in the desired order
                        current_frame_output_dict[col_face_name] = face_info_str
                        current_frame_output_dict[col_x_name] = x_val
                        current_frame_output_dict[col_y_name] = y_val
                        current_frame_output_dict[col_z_name] = z_val

                        markers_found_in_this_frame += 1
                    except IndexError: # This should ideally not be reached if min_len logic is correct
                        print(
                            f"Warning: Index error while accessing coordinate data for marker '{full_marker_name}' in frame {frame_number}. Skipping.")
                        continue
                    # No need to manually increment i here, the for loop handles it.
                    # i += 2 was incorrect here as the outer loop already iterates.

        if markers_found_in_this_frame > 0:
            processed_frames_data.append(current_frame_output_dict)
        elif frame_line_index >= 8:  # If it's a data line but no valid markers were found
            print(
                f"Info: No valid 'Rigid Body Marker' position data found for frame {frame_number} (line {frame_line_index + 1}).")

    if not processed_frames_data:
        print("No valid marker data found to convert across all frames.")
        return

    # Construct the final header for the output CSV
    final_output_headers = ['FrameNumber', 'Time']  # Start with FrameNumber and Time
    # Sort unique marker identifiers alphabetically for consistent grouping of marker columns
    ordered_unique_marker_identifiers.sort()
    for marker_id in ordered_unique_marker_identifiers:
        # Add columns for each marker in the order: FaceInfo, X, Y, Z
        final_output_headers.extend([
            f"{marker_id}_FaceInfo",
            f"{marker_id}_X",
            f"{marker_id}_Y",
            f"{marker_id}_Z"
        ])

    try:
        with open(output_filepath, mode='w', encoding='utf-8', newline='') as outfile:
            writer = csv.DictWriter(outfile, fieldnames=final_output_headers,
                                    restval='')  # Use restval for missing keys
            writer.writeheader()
            writer.writerows(processed_frames_data)
        print(
            f"Converted file successfully saved to '{output_filepath}'. Total {len(processed_frames_data)} frames processed.")
    except Exception as e:
        print(f"Error writing converted CSV file: {e}")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description="Converts experimental raw data CSV (e.g., from motion capture) to a standard 'wide' format CSV. Processes all frames.")
    parser.add_argument("input_csv_path", type=str, help="Path to the input experimental raw data CSV file")
    parser.add_argument("output_csv_path", type=str, help="Path for the output standardized wide format CSV file")

    args = parser.parse_args()
    parse_experiment_raw_data_all_frames(args.input_csv_path, args.output_csv_path)
# --- END OF FILE AlignBoxInputGenbyExperiment.py (Modified as per original structure) ---