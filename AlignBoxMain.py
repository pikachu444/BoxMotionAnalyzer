import numpy as np
from scipy.optimize import minimize
from scipy.spatial.transform import Rotation as R
import csv
import argparse
import json # Not explicitly used in the current version, but kept from original

# --- Configuration Loading ---
import config
BOX_DIMS = config.BOX_DIMS
FACE_DEFINITIONS = config.FACE_DEFINITIONS
LOCAL_BOX_CORNERS = config.LOCAL_BOX_CORNERS


def load_wide_formatted_csv(filepath):
    """
    Loads marker data from a "wide" formatted CSV file.
    Each row is a frame. Columns are FrameNumber, Time,
    then for each marker: {MarkerID}_FaceInfo, {MarkerID}_X, {MarkerID}_Y, {MarkerID}_Z.
    """
    frames_data = []
    try:
        with open(filepath, mode='r', encoding='utf-8') as infile:
            reader = csv.DictReader(infile)
            if not reader.fieldnames:
                print(f"Error: CSV file '{filepath}' has no header or is empty.")
                return []

            for row_idx, row in enumerate(reader):
                frame_number = row.get('FrameNumber', str(row_idx + 1))  # Default to row index if missing
                time_value = row.get('Time', "0.0")  # Default to 0.0 if missing

                current_frame_markers = []
                # Dynamically find marker data from columns based on suffixes
                processed_marker_ids_in_frame = set()

                # Iterate through column names to find marker data groups
                for col_name in row:
                    if col_name.endswith("_X"):
                        marker_id_prefix = col_name[:-2]  # Extract marker identifier (e.g., "F1" from "F1_X")

                        # Avoid processing the same marker multiple times if X,Y,Z appear separately
                        if marker_id_prefix in processed_marker_ids_in_frame:
                            continue

                        try:
                            # Check if all required columns for this marker exist
                            x_col = f"{marker_id_prefix}_X"
                            y_col = f"{marker_id_prefix}_Y"
                            z_col = f"{marker_id_prefix}_Z"
                            faceinfo_col = f"{marker_id_prefix}_FaceInfo"  # Expected FaceInfo column name

                            if not (x_col in row and y_col in row and z_col in row):
                                continue

                            x_val_str = row[x_col]
                            y_val_str = row[y_col]
                            z_val_str = row[z_col]

                            if not x_val_str or not y_val_str or not z_val_str:
                                continue

                            x_val = float(x_val_str)
                            y_val = float(y_val_str)
                            z_val = float(z_val_str)

                            face_info = row.get(faceinfo_col, "").strip().upper()
                            marker_name = marker_id_prefix

                            face_key = face_info if face_info and face_info not in ["NONE", "NULL", "ANY", ""] else None
                            if face_key and face_key not in FACE_DEFINITIONS: # Uses FACE_DEFINITIONS from config
                                print(
                                    f"Warning (Frame {frame_number}): Invalid FaceInfo '{face_key}' for marker '{marker_id_prefix}'. Treating as no face info.")
                                face_key = None

                            current_frame_markers.append({
                                'id': marker_id_prefix,
                                'name': marker_name,
                                'face_key': face_key,
                                'cam_coords': np.array([x_val, y_val, z_val])
                            })
                            processed_marker_ids_in_frame.add(marker_id_prefix)
                        except ValueError as e:
                            print(
                                f"Warning (Frame {frame_number}): Could not parse coordinate data for marker prefix '{marker_id_prefix}'. Error: {e}. Skipping this marker for this frame.")
                            continue
                        except KeyError as e:
                            print(
                                f"Warning (Frame {frame_number}): Missing expected column for marker prefix '{marker_id_prefix}'. Error: {e}. Skipping this marker.")
                            continue

                if current_frame_markers:
                    frames_data.append({
                        'FrameNumber': frame_number,
                        'Time': time_value,
                        'markers': current_frame_markers
                    })

    except FileNotFoundError:
        print(f"Error: Input CSV file '{filepath}' not found.")
        return []
    except Exception as e:
        print(f"Error loading wide CSV file: {e}")
        return []

    print(f"Loaded data for {len(frames_data)} frames from wide CSV file.")
    return frames_data


def distance_point_to_box_surface_overall(point_local, box_half_dims):
    """Calculates the shortest distance from a point to the overall surface of an AABB."""
    closest_p_on_box = np.clip(point_local, -box_half_dims, box_half_dims)
    distance = np.linalg.norm(point_local - closest_p_on_box)
    return distance


def distance_point_to_assigned_face_surface_and_bounds(point_local, face_key, box_dims_param): # box_dims_param is BOX_DIMS from config
    """Calculates distance from a point to its assigned face, considering boundaries."""
    if face_key not in FACE_DEFINITIONS: # Uses FACE_DEFINITIONS from config
        return distance_point_to_box_surface_overall(point_local, box_dims_param / 2.0)

    face_def = FACE_DEFINITIONS[face_key]
    axis_idx = face_def['axis_idx']
    direction = face_def['direction']
    bound_axes_indices = face_def['bound_axes_indices']
    box_half_dims = box_dims_param / 2.0

    point_coord_on_normal_axis = point_local[axis_idx]
    face_plane_coord = direction * box_half_dims[axis_idx]
    d_plane = np.abs(point_coord_on_normal_axis - face_plane_coord)

    d_boundary_sq_sum = 0.0
    point_coord_in_plane_1 = point_local[bound_axes_indices[0]]
    half_dim_in_plane_1 = box_half_dims[bound_axes_indices[0]]
    d_bound_1 = np.maximum(0, np.abs(point_coord_in_plane_1) - half_dim_in_plane_1)
    d_boundary_sq_sum += d_bound_1 ** 2

    point_coord_in_plane_2 = point_local[bound_axes_indices[1]]
    half_dim_in_plane_2 = box_half_dims[bound_axes_indices[1]]
    d_bound_2 = np.maximum(0, np.abs(point_coord_in_plane_2) - half_dim_in_plane_2)
    d_boundary_sq_sum += d_bound_2 ** 2

    total_distance = np.sqrt(d_plane ** 2 + d_boundary_sq_sum)
    return total_distance


def objective_function(params, frame_marker_data):
    """Cost function for optimization for a single frame's marker data."""
    T_guess = params[:3]
    rot_vec_guess = params[3:]
    try:
        R_obj_guess = R.from_rotvec(rot_vec_guess)
        R_inv_guess = R_obj_guess.inv()
    except ValueError:
        return np.inf

    box_half_dims_overall = BOX_DIMS / 2.0 # Uses BOX_DIMS from config
    total_sq_distance = 0.0

    for marker_info in frame_marker_data:
        m_cam = marker_info['cam_coords']
        face_key = marker_info['face_key']
        m_local_guess = R_inv_guess.apply(m_cam - T_guess)

        if face_key is not None and face_key in FACE_DEFINITIONS: # Uses FACE_DEFINITIONS from config
            dist = distance_point_to_assigned_face_surface_and_bounds(m_local_guess, face_key, BOX_DIMS) # Uses BOX_DIMS from config
        else:
            dist = distance_point_to_box_surface_overall(m_local_guess, box_half_dims_overall)
        total_sq_distance += dist ** 2

    return total_sq_distance


def get_box_world_corners(pose_params):
    """
    Calculates the 3D world coordinates of the 8 corners of the box.
    Uses LOCAL_BOX_CORNERS from config.py.
    """
    #Use LOCAL_BOX_CORNERS directly from config
    # Ensure LOCAL_BOX_CORNERS is available globally (loaded from config at script start)    
    T = pose_params[:3]
    rot_vec = pose_params[3:]
    try:
        rot_obj = R.from_rotvec(rot_vec)
    except ValueError:
        rot_obj = R.identity()
    
    #Apply rotation to LOCAL_BOX_CORNERS from config
    world_corners = rot_obj.apply(LOCAL_BOX_CORNERS) + T
    return world_corners


# --- Main Execution ---
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Optimize box pose for each frame from a wide-formatted CSV and save results including corner coordinates.")
    parser.add_argument('--input_csv', type=str, required=True,
                        help="Path to the wide-formatted CSV file (e.g., output of SmoothMarkerData.py).")
    parser.add_argument('--output_csv', type=str, required=True,
                        help="Path to save the box pose sequence CSV file.")
    args = parser.parse_args()

    # Ensure config constants are loaded before use
    if 'BOX_DIMS' not in globals() or 'FACE_DEFINITIONS' not in globals() or 'LOCAL_BOX_CORNERS' not in globals():
        print("Critical Error: Configuration constants (BOX_DIMS, FACE_DEFINITIONS, LOCAL_BOX_CORNERS) not loaded correctly. Exiting.")
        exit(1)


    all_frames_input_data = load_wide_formatted_csv(args.input_csv)

    if not all_frames_input_data:
        print("No data loaded from input CSV. Exiting.")
        exit()

    output_pose_data = []

    output_headers = ['FrameNumber', 'Time',
                      'Box_Tx', 'Box_Ty', 'Box_Tz',
                      'Box_Rx', 'Box_Ry', 'Box_Rz',
                      'Pose_Source']
    for i in range(8):
        output_headers.extend([f'C{i}_X', f'C{i}_Y', f'C{i}_Z'])

    previous_optimized_T = None
    previous_optimized_rot_vec = None

    for frame_idx, frame_data in enumerate(all_frames_input_data):
        frame_number = frame_data['FrameNumber']
        time_value = frame_data['Time']
        current_frame_markers = frame_data['markers']

        if not current_frame_markers:
            print(f"Frame {frame_number}: No markers to process. Skipping optimization for this frame.")
            continue

        print(f"\nProcessing Frame: {frame_number} (Time: {time_value})")
        observed_marker_coords_for_frame = np.array([m['cam_coords'] for m in current_frame_markers])

        if frame_idx == 0 or previous_optimized_T is None or previous_optimized_rot_vec is None:
            initial_T_guess = np.mean(observed_marker_coords_for_frame, axis=0)
            initial_rot_vec_guess = np.array([0.01, -0.01, 0.01])
            print(f"  Using default initial guess for Frame {frame_number}.")
        else:
            initial_T_guess = previous_optimized_T
            initial_rot_vec_guess = previous_optimized_rot_vec
            print(f"  Using previous frame's optimized pose as initial guess for Frame {frame_number}.")

        initial_params = np.concatenate([initial_T_guess, initial_rot_vec_guess])
        
        result = minimize(objective_function, # objective_function uses global BOX_DIMS, FACE_DEFINITIONS
                          initial_params,
                          args=(current_frame_markers,),
                          method='Nelder-Mead',
                          options={'maxiter': 1500, 'disp': False, 'xatol': 1e-4, 'fatol': 1e-4})

        if result.success:
            optimized_params = result.x
            optimized_T = optimized_params[:3]
            optimized_rot_vec = optimized_params[3:]
            previous_optimized_T = optimized_T
            previous_optimized_rot_vec = optimized_rot_vec
            print(
                f"  Frame {frame_number} - Optimization Succeeded. Iterations: {result.nit}, Final Cost: {result.fun:.3e}")
        else:
            print(f"  Frame {frame_number} - Optimization FAILED. Message: {result.message}")
            optimized_params = result.x 
            optimized_T = optimized_params[:3]
            optimized_rot_vec = optimized_params[3:]
            if frame_idx > 0:
                previous_optimized_T = None
                previous_optimized_rot_vec = None
        
        world_corners = get_box_world_corners(optimized_params) # get_box_world_corners uses global LOCAL_BOX_CORNERS

        row_data = {
            'FrameNumber': frame_number, 'Time': time_value,
            'Box_Tx': optimized_T[0], 'Box_Ty': optimized_T[1], 'Box_Tz': optimized_T[2],
            'Box_Rx': optimized_rot_vec[0], 'Box_Ry': optimized_rot_vec[1], 'Box_Rz': optimized_rot_vec[2],
            'Pose_Source': "Optimized" if result.success else "OptimizationFailed"
        }
        for i_corner, corner_coords in enumerate(world_corners):
            row_data[f'C{i_corner}_X'] = corner_coords[0]
            row_data[f'C{i_corner}_Y'] = corner_coords[1]
            row_data[f'C{i_corner}_Z'] = corner_coords[2]
        output_pose_data.append(row_data)

    if output_pose_data:
        try:
            with open(args.output_csv, mode='w', encoding='utf-8', newline='') as outfile:
                writer = csv.DictWriter(outfile, fieldnames=output_headers)
                writer.writeheader()
                writer.writerows(output_pose_data)
            print(
                f"\nBox pose sequence successfully saved to '{args.output_csv}'. Total {len(output_pose_data)} frames processed and saved.")
        except Exception as e:
            print(f"Error writing output CSV file: {e}")
    else:
        print("No pose data was generated to save.")