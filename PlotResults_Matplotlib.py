import numpy as np
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
from mpl_toolkits.mplot3d import Axes3D # Required for 3D plotting
import csv
import argparse

import config
BOX_DIMS = config.BOX_DIMS
FACE_DEFINITIONS = config.FACE_DEFINITIONS
# For plotting box wireframe
BOX_EDGES_AS_CORNER_INDICES = config.BOX_EDGES_AS_CORNER_INDICES
# For plotting floor
WORLD_VERTICAL_AXIS_INDEX = config.WORLD_VERTICAL_AXIS_INDEX
FLOOR_LEVEL = config.FLOOR_LEVEL
PLOT_FLOOR_HALF_EXTENT_1 = config.PLOT_FLOOR_HALF_EXTENT_1
PLOT_FLOOR_HALF_EXTENT_2 = config.PLOT_FLOOR_HALF_EXTENT_2

def load_box_pose_data_all_frames(filepath):
    """
    Loads all box pose data (including corner coordinates) from the box_pose_sequence.csv file.
    Returns a dictionary keyed by FrameNumber (string).
    Each value is a dictionary like {'corners': np.array, 'Time': str}.
    """
    all_frames_box_data = {}
    try:
        with open(filepath, mode='r', encoding='utf-8') as infile:
            reader = csv.DictReader(infile)
            if not reader.fieldnames:
                print(f"Error: Poses CSV file '{filepath}' has no header or is empty.")
                return {}

            for row_idx, row in enumerate(reader): # Added row_idx for robust FrameNumber
                frame_number_str = row.get('FrameNumber')
                if not frame_number_str:
                    # Fallback if FrameNumber column is missing or empty for a row
                    frame_number_str = str(row_idx + 1)
                    print(f"Warning: Missing FrameNumber in a row in '{filepath}'. Using row index {frame_number_str}.")
                    # continue # Or assign a default and proceed

                box_corners = np.zeros((8, 3))
                all_corners_found = True
                for i in range(8):
                    try:
                        # It's crucial that the CSV column names C{i}_X, C{i}_Y, C{i}_Z match
                        # what AlignBoxMain.py produces.
                        box_corners[i, 0] = float(row[f'C{i}_X'])
                        box_corners[i, 1] = float(row[f'C{i}_Y'])
                        box_corners[i, 2] = float(row[f'C{i}_Z'])
                    except (KeyError, ValueError) as e:
                        print(f"Error parsing corner C{i} for frame '{frame_number_str}' in '{filepath}': {e}. Row data: {row}")
                        all_corners_found = False
                        break # Stop processing this row if a corner is bad

                if all_corners_found:
                    all_frames_box_data[frame_number_str] = {
                        'corners': box_corners,
                        'Time': row.get('Time', 'N/A') # Get Time, default to N/A
                    }
                # else:
                    # print(f"Skipping frame {frame_number_str} due to corner parsing error.")


            print(f"Loaded box pose data for {len(all_frames_box_data)} frames from '{filepath}'.")
            return all_frames_box_data

    except FileNotFoundError:
        print(f"Error: Poses CSV file '{filepath}' not found.")
        return {}
    except Exception as e:
        print(f"Error loading poses CSV file '{filepath}': {e}")
        import traceback
        traceback.print_exc()
        return {}


def load_marker_data_all_frames(filepath):
    """
    Loads all marker data (FaceInfo, X, Y, Z) from the wide-formatted CSV file.
    Returns a dictionary keyed by FrameNumber (string).
    """
    all_frames_marker_data = {}
    try:
        with open(filepath, mode='r', encoding='utf-8') as infile:
            reader = csv.DictReader(infile)
            if not reader.fieldnames:
                print(f"Error: Markers CSV file '{filepath}' has no header or is empty.")
                return {}

            for row_idx, row in enumerate(reader): # Added row_idx
                frame_number_str = row.get('FrameNumber')
                if not frame_number_str:
                    frame_number_str = str(row_idx + 1)
                    print(f"Warning: Missing FrameNumber in a row in '{filepath}'. Using row index {frame_number_str}.")

                markers_in_this_frame = []
                # Iterate through keys to find marker data based on _X, _Y, _Z suffixes
                # This assumes marker IDs are extracted from column names like "MarkerID_X"
                processed_marker_ids = set()
                for col_name in row.keys():
                    if col_name.endswith("_X"):
                        marker_id = col_name[:-2] # Extract "MarkerID"
                        if marker_id in processed_marker_ids:
                            continue # Already processed this marker_id (e.g. if _Y, _Z seen first)
                        
                        x_col, y_col, z_col = f"{marker_id}_X", f"{marker_id}_Y", f"{marker_id}_Z"
                        face_col = f"{marker_id}_FaceInfo"

                        if x_col in row and y_col in row and z_col in row:
                            try:
                                x_val_str = row[x_col]
                                y_val_str = row[y_col]
                                z_val_str = row[z_col]
                                face_info = row.get(face_col, "") # Default to empty if no FaceInfo

                                # Ensure coordinates are not empty strings before float conversion
                                if x_val_str and y_val_str and z_val_str:
                                    x_val = float(x_val_str)
                                    y_val = float(y_val_str)
                                    z_val = float(z_val_str)

                                    markers_in_this_frame.append({
                                        'id': marker_id,
                                        'name': marker_id, # Use id as name for now
                                        'face_key': face_info.strip().upper() or None, # Ensure None if empty
                                        'cam_coords': np.array([x_val, y_val, z_val])
                                    })
                                    processed_marker_ids.add(marker_id)
                                # else:
                                #     print(f"Warning: Empty coordinate value for marker '{marker_id}' in frame {frame_number_str}, file '{filepath}'. Skipping.")
                            except ValueError: # Error converting to float
                                print(f"Warning: Could not parse coordinate data for marker '{marker_id}' in frame {frame_number_str} from '{filepath}'. Skipping this marker.")
                                continue
                            # except KeyError: # Should be caught by "if x_col in row..."
                            #     print(f"Warning: Missing coordinate column for marker '{marker_id}' in frame {frame_number_str}, file '{filepath}'. Skipping.")
                            #     continue
                
                if markers_in_this_frame:
                    all_frames_marker_data[frame_number_str] = markers_in_this_frame
            
            print(f"Loaded marker data for {len(all_frames_marker_data)} frames from '{filepath}'.")
            return all_frames_marker_data

    except FileNotFoundError:
        print(f"Error: Markers CSV file '{filepath}' not found.")
        return {}
    except Exception as e:
        print(f"Error loading markers CSV file '{filepath}': {e}")
        import traceback
        traceback.print_exc()
        return {}


def plot_box_wireframe_from_corners(ax, corners_world, color, label):
    """Helper function to draw the wireframe of a box from 8 world_corners."""
    # Use BOX_EDGES_AS_CORNER_INDICES from config
    lines = []
    is_first_edge = True # For applying label only to the first line segment
    for i, j in BOX_EDGES_AS_CORNER_INDICES: # Iterate through edge definitions
        line, = ax.plot([corners_world[i, 0], corners_world[j, 0]],
                        [corners_world[i, 1], corners_world[j, 1]],
                        [corners_world[i, 2], corners_world[j, 2]],
                        color=color, label=label if is_first_edge else None)
        lines.append(line)
        is_first_edge = False
    return lines


def plot_face_labels(ax, world_corners, face_definitions_dict): # face_definitions_dict is FACE_DEFINITIONS from config
    """Adds face labels to the matplotlib 3D plot using world_corners."""
    texts = []
    for face_name, face_def in face_definitions_dict.items():
        face_corner_indices = face_def.get('corners') # List of 4 corner indices for this face
        if face_corner_indices and len(face_corner_indices) == 4:
            # Ensure world_corners has enough points and indices are valid
            if all(idx < len(world_corners) for idx in face_corner_indices):
                face_actual_corners = world_corners[face_corner_indices]
                face_center = np.mean(face_actual_corners, axis=0)
                txt = ax.text(face_center[0], face_center[1], face_center[2], face_name,
                              color='purple', ha='center', va='center', fontsize=9, alpha=0.9,
                              bbox=dict(boxstyle='round,pad=0.2', fc='plum', alpha=0.3, ec='none'))
                texts.append(txt)
            # else:
            #     print(f"Warning: Invalid corner indices for face '{face_name}' or not enough corners in world_corners.")
        # else:
        #     print(f"Warning: 'corners' field missing or invalid for face '{face_name}' in FACE_DEFINITIONS.")
    return texts


def plot_marker_labels(ax, marker_data_list):
    """Adds marker labels to the matplotlib 3D plot."""
    texts = []
    for marker_data in marker_data_list:
        coords = marker_data['cam_coords']
        name = marker_data.get('name', str(marker_data.get('id', ''))) # Default to ID if name is missing
        # Add a small offset to marker labels to avoid overlap with marker point
        txt = ax.text(coords[0] + 15, coords[1] + 15, coords[2], name, # Offset can be adjusted
                      color='darkcyan', ha='left', va='bottom', fontsize=8, alpha=0.9)
        texts.append(txt)
    return texts

# ### NEW FUNCTION ###: To plot the floor plane
def plot_floor_plane(ax, floor_y_level, vertical_axis_idx, half_extent1, half_extent2, scene_center=None):
    """
    Plots a rectangular representation of the floor plane.
    Args:
        ax: The 3D matplotlib axes.
        floor_y_level (float): The coordinate of the floor along the vertical axis.
        vertical_axis_idx (int): Index of the world vertical axis (0=X, 1=Y, 2=Z).
        half_extent1 (float): Half-size of the floor rectangle along its first dimension.
        half_extent2 (float): Half-size of the floor rectangle along its second dimension.
        scene_center (np.array, optional): A 3D point around which to center the floor visualization.
                                           If None, defaults to world origin.
    """
    # Determine the plane's axes based on the vertical axis
    if vertical_axis_idx == 0: # X is up, floor is YZ plane
        x_coords = np.array([floor_y_level, floor_y_level]) # Constant X
        y_coords = np.array([-half_extent1, half_extent1]) # Extent along Y
        z_coords = np.array([-half_extent2, half_extent2]) # Extent along Z
        Y, Z = np.meshgrid(y_coords, z_coords)
        X = np.full_like(Y, floor_y_level)
        plane_axes_labels = ('Y', 'Z')
    elif vertical_axis_idx == 1: # Y is up, floor is XZ plane
        y_coords = np.array([floor_y_level, floor_y_level]) # Constant Y
        x_coords = np.array([-half_extent1, half_extent1]) # Extent along X
        z_coords = np.array([-half_extent2, half_extent2]) # Extent along Z
        X, Z = np.meshgrid(x_coords, z_coords)
        Y = np.full_like(X, floor_y_level)
        plane_axes_labels = ('X', 'Z')
    elif vertical_axis_idx == 2: # Z is up, floor is XY plane
        z_coords = np.array([floor_y_level, floor_y_level]) # Constant Z
        x_coords = np.array([-half_extent1, half_extent1]) # Extent along X
        y_coords = np.array([-half_extent2, half_extent2]) # Extent along Y
        X, Y = np.meshgrid(x_coords, y_coords)
        Z = np.full_like(X, floor_y_level)
        plane_axes_labels = ('X', 'Y')
    else:
        print(f"Error: Invalid vertical_axis_idx ({vertical_axis_idx}). Cannot plot floor.")
        return None

    # If a scene_center is provided, shift the floor plane to be centered there
    # (only shifting in the plane's dimensions, not along the normal/vertical axis)
    if scene_center is not None:
        if vertical_axis_idx == 0: # YZ plane
            Y += scene_center[1]
            Z += scene_center[2]
        elif vertical_axis_idx == 1: # XZ plane
            X += scene_center[0]
            Z += scene_center[2]
        elif vertical_axis_idx == 2: # XY plane
            X += scene_center[0]
            Y += scene_center[1]
            
    # Plot the surface
    floor_surface = ax.plot_surface(X, Y, Z, alpha=0.2, color='gray', rstride=1, cstride=1, linewidth=0, antialiased=True)
    # print(f"  Plotted floor at {('XYZ'[vertical_axis_idx])}={floor_y_level}, extents based on {plane_axes_labels}.")
    return floor_surface


# Global list to keep track of artists for clearing between animation frames
artists_collection = []

def update_plot(frame_num_str, ax, all_box_data, all_marker_data, title_text_obj, static_artists):
    """
    Update function for the animation.
    Clears previous dynamic artists and draws new ones for the current frame.
    """
    global artists_collection
    # Remove only dynamic artists added in previous calls to update_plot
    for artist_group in artists_collection:
        for artist in artist_group:
            # Check if artist is still part of the figure/axes before removing
            if artist and artist.axes:
                artist.remove()
    artists_collection = [] # Reset the list for current frame's artists

    current_artists_this_frame = [] # Artists specific to this frame update

    box_data_for_this_frame = all_box_data.get(frame_num_str)
    marker_data_for_this_frame = all_marker_data.get(frame_num_str, []) # Default to empty list

    plotted_something_this_frame = False

    # Plot markers if data exists for this frame
    if marker_data_for_this_frame:
        observed_markers_coords = np.array([m['cam_coords'] for m in marker_data_for_this_frame])
        if observed_markers_coords.size > 0:
            scatter_artist = ax.scatter(observed_markers_coords[:, 0], observed_markers_coords[:, 1],
                                        observed_markers_coords[:, 2], c='red', marker='o', s=30, label="Observed Markers" if not static_artists.get("markers_legend") else None)
            current_artists_this_frame.append(scatter_artist)
            if not static_artists.get("markers_legend"): static_artists["markers_legend"] = True # Mark legend as added

            marker_label_artists = plot_marker_labels(ax, marker_data_for_this_frame)
            current_artists_this_frame.extend(marker_label_artists)
            plotted_something_this_frame = True

    # Plot box if data exists for this frame
    if box_data_for_this_frame and 'corners' in box_data_for_this_frame:
        box_world_corners = box_data_for_this_frame['corners']
        # plot_box_wireframe_from_corners now uses BOX_EDGES_AS_CORNER_INDICES from config (implicitly)
        box_lines_artists = plot_box_wireframe_from_corners(ax, box_world_corners, 'green', "Estimated Box" if not static_artists.get("box_legend") else None)
        current_artists_this_frame.extend(box_lines_artists)
        if not static_artists.get("box_legend"): static_artists["box_legend"] = True # Mark legend as added

        # plot_face_labels uses FACE_DEFINITIONS from config (implicitly)
        face_label_artists = plot_face_labels(ax, box_world_corners, FACE_DEFINITIONS)
        current_artists_this_frame.extend(face_label_artists)
        plotted_something_this_frame = True

        # Print corner coordinates (optional, can be verbose for animation)
        # print(f"\n--- Frame {frame_num_str} (Time: {box_data_for_this_frame.get('Time', 'N/A')}) Box Corner Coordinates ---")
        # for c_idx, corner in enumerate(box_world_corners):
        #     print(f"  Corner {c_idx}: X={corner[0]:.2f}, Y={corner[1]:.2f}, Z={corner[2]:.2f}")
        # print("-------------------------------------------------")

    if not plotted_something_this_frame:
        # Display message if no data for this specific frame
        no_data_text = ax.text2D(0.5, 0.5, f"No data available for Frame {frame_num_str}",
                                 horizontalalignment='center', verticalalignment='center',
                                 transform=ax.transAxes, fontsize=12, color='grey')
        current_artists_this_frame.append(no_data_text)

    # Update title
    time_val = "N/A"
    if box_data_for_this_frame and 'Time' in box_data_for_this_frame:
        time_val = box_data_for_this_frame['Time']
    elif marker_data_for_this_frame and all_marker_data.get(frame_num_str): # Fallback to marker time if box time missing
        # This part assumes marker_data_for_this_frame is a list and needs a time source,
        # but load_marker_data_all_frames returns a dict keyed by frame_num_str whose value is the list.
        # A better way: if time is stored per frame in all_marker_data's structure.
        # For now, assuming time primarily comes from box_data.
        pass # Needs a clear source for time if box_data is missing for the frame.

    title_text_obj.set_text(f"Frame: {frame_num_str} (Time: {time_val})")
    
    artists_collection.append(current_artists_this_frame) # Add this frame's artists to global list for next clear

    # Return all artists that were modified or added in this frame
    # This includes the title and any new plot elements.
    # The floor is static so not returned here.
    all_updated_artists = current_artists_this_frame + [title_text_obj]
    return all_updated_artists


def main_animation(all_box_data, all_marker_data):
    """
    Main animation plotting function using Matplotlib.
    """
    if not all_box_data and not all_marker_data:
        print("No data available from either poses_csv or markers_csv. Cannot create animation.")
        return

    fig = plt.figure(figsize=(16, 12)) # Adjusted figure size
    ax = fig.add_subplot(111, projection='3d')

    # Determine common set of frame numbers for consistent animation
    available_frame_numbers = set()
    if all_box_data: available_frame_numbers.update(all_box_data.keys())
    if all_marker_data: available_frame_numbers.update(all_marker_data.keys())

    if not available_frame_numbers:
        print("No common frame numbers found in the loaded data. Cannot animate.")
        ax.text2D(0.5, 0.5, "No frame data loaded.", ha='center', va='center', transform=ax.transAxes)
        plt.show()
        return

    # Sort frame numbers: numerically if possible, otherwise as strings.
    try:
        # Convert to int for sorting, then back to str for dict keys
        sorted_frame_num_strs = sorted(list(available_frame_numbers), key=lambda x: int(x))
    except ValueError:
        print("Warning: FrameNumbers are not all numeric. Sorting as strings.")
        sorted_frame_num_strs = sorted(list(available_frame_numbers))

    ax.set_xlabel('X World Coordinate (mm)')
    ax.set_ylabel('Y World Coordinate (mm)')
    ax.set_zlabel('Z World Coordinate (mm)')

    # Calculate plot limits based on all data points across all frames
    all_points_for_limits = []
    for frame_key in sorted_frame_num_strs:
        if frame_key in all_marker_data:
            coords = np.array([m['cam_coords'] for m in all_marker_data[frame_key]])
            if coords.size > 0: all_points_for_limits.append(coords)
        if frame_key in all_box_data and 'corners' in all_box_data[frame_key]:
            all_points_for_limits.append(all_box_data[frame_key]['corners'])
    
    scene_center_for_floor = np.array([0,0,0]) # Default center for floor plot

    if all_points_for_limits:
        all_points_combined = np.vstack(all_points_for_limits)
        min_coords = all_points_combined.min(axis=0)
        max_coords = all_points_combined.max(axis=0)
        scene_center_for_floor = (max_coords + min_coords) / 2.0 # Center floor around data
        
        plot_range = np.max(max_coords - min_coords) * 0.75 # Make range slightly larger than data
        if plot_range == 0: plot_range = np.max(np.abs(scene_center_for_floor)) if np.max(np.abs(scene_center_for_floor)) > 0 else 1000.0
        
        ax.set_xlim(scene_center_for_floor[0] - plot_range, scene_center_for_floor[0] + plot_range)
        ax.set_ylim(scene_center_for_floor[1] - plot_range, scene_center_for_floor[1] + plot_range)
        ax.set_zlim(scene_center_for_floor[2] - plot_range, scene_center_for_floor[2] + plot_range)
    else:
        # Default limits if no data points found (e.g., only floor is plotted)
        ax.set_xlim(-1500, 1500); ax.set_ylim(-1500, 1500); ax.set_zlim(0, 2500)

    # Plot the floor plane once, statically.
    # Use scene_center_for_floor to approximately center the visualized floor area.
    # The floor itself is at FLOOR_LEVEL along the WORLD_VERTICAL_AXIS_INDEX.
    # We only shift the plotting center in the plane of the floor.
    floor_plot_center_in_plane = np.copy(scene_center_for_floor)
    floor_plot_center_in_plane[WORLD_VERTICAL_AXIS_INDEX] = FLOOR_LEVEL # Ensure this component is not used for plane centering

    plot_floor_plane(ax, FLOOR_LEVEL, WORLD_VERTICAL_AXIS_INDEX, 
                     PLOT_FLOOR_HALF_EXTENT_1, PLOT_FLOOR_HALF_EXTENT_2,
                     scene_center=floor_plot_center_in_plane)


    title_text_obj = ax.set_title("Frame: Initializing...") # Dynamic title object

    # Static legend: Create dummy artists, add to legend, then remove dummies.
    # This ensures legend items appear even if the corresponding data isn't in the first frame.
    static_artists_flags = {"markers_legend": False, "box_legend": False} # To track if legend items are added
    
    # Initial plot for the first frame to set up legend handles correctly if possible
    # Or, create dummy plots for legend items
    dummy_marker_scatter = ax.scatter([], [], [], c='red', marker='o', label='Observed Markers')
    dummy_box_line, = ax.plot([], [], [], color='green', label='Estimated Box')
    ax.legend(handles=[dummy_marker_scatter, dummy_box_line], loc='upper right')
    dummy_marker_scatter.remove() # Remove dummies after legend is created
    dummy_box_line.remove()


    # FuncAnimation call
    ani = FuncAnimation(fig, update_plot, frames=sorted_frame_num_strs,
                        fargs=(ax, all_box_data, all_marker_data, title_text_obj, static_artists_flags),
                        interval=10, blit=False, repeat=True) # blit=False often more robust with 3D text

    plt.tight_layout() # Adjust layout to prevent overlapping elements
    plt.show()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Plot box pose and/or markers as an animation using Matplotlib.")
    parser.add_argument('--poses_csv', type=str,
                        help="Path to the CSV file containing box pose sequence data (e.g., output of AlignBoxMain.py).")
    parser.add_argument('--markers_csv', type=str,
                        help="Path to the wide-formatted CSV file containing marker data (e.g., output of SmoothMarkerData.py).")

    args = parser.parse_args()

    if not args.poses_csv and not args.markers_csv:
        print("Error: At least one of --poses_csv or --markers_csv must be provided.")
        exit()

    all_box_data = {}
    if args.poses_csv:
        all_box_data = load_box_pose_data_all_frames(args.poses_csv)
        if not all_box_data and args.poses_csv: # Check if filepath was given but loading failed
            print(f"Warning: Could not load any box data from '{args.poses_csv}'.")

    all_marker_data = {}
    if args.markers_csv:
        all_marker_data = load_marker_data_all_frames(args.markers_csv)
        if not all_marker_data and args.markers_csv: # Check if filepath was given but loading failed
            print(f"Warning: Could not load any marker data from '{args.markers_csv}'.")

    if all_box_data or all_marker_data: # Proceed if at least one data source was successfully loaded
        main_animation(all_box_data, all_marker_data)
    else:
        print(f"No data could be loaded from the provided CSV files. Nothing to plot.")
