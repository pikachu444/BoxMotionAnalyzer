# --- START OF FILE PlotTransformedFrame.py ---
import argparse
import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
from mpl_toolkits.mplot3d import Axes3D # Required for 3D projection
# from mpl_toolkits.mplot3d.art3d import Poly3DCollection # For floor plane if using patch
from matplotlib.patches import FancyArrowPatch # For curved arrow for angular velocity
from mpl_toolkits.mplot3d import proj3d # For FancyArrowPatch in 3D

# --- Configuration Loading ---
# Attempt to load configurations from a central config.py file
import config
BOX_DIMS = config.BOX_DIMS
BOX_EDGES_AS_CORNER_INDICES = config.BOX_EDGES_AS_CORNER_INDICES
FACE_DEFINITIONS = config.FACE_DEFINITIONS # Used for face labels
PLOT_FLOOR_HALF_EXTENT_1 = config.PLOT_FLOOR_HALF_EXTENT_1
PLOT_FLOOR_HALF_EXTENT_2 = config.PLOT_FLOOR_HALF_EXTENT_2

# --- Helper class for 3D Arrow (e.g., for angular velocity arc) ---
class Arrow3D(FancyArrowPatch):
    def __init__(self, xs, ys, zs, *args, **kwargs):
        super().__init__((0, 0), (0, 0), *args, **kwargs)
        self._verts3d = xs, ys, zs

    def draw(self, renderer):
        xs3d, ys3d, zs3d = self._verts3d
        xs, ys, zs = proj3d.proj_transform(xs3d, ys3d, zs3d, self.axes.M)
        self.set_positions((xs[0], ys[0]), (xs[1], ys[1]))
        super().draw(renderer)

    # Compatibility for Matplotlib 3.5+
    def do_3d_projection(self, renderer=None):
        xs3d, ys3d, zs3d = self._verts3d
        xs, ys, zs = proj3d.proj_transform(xs3d, ys3d, zs3d, self.axes.M)
        self.set_positions((xs[0], ys[0]), (xs[1], ys[1]))
        return np.min(zs)

# --- Data Loading and Preparation Functions ---
def load_transformed_data_from_csv(csv_filepath):
    """
    Loads transformed data from the specified CSV file.
    Performs basic validation for the presence of expected column patterns.
    """
    try:
        df = pd.read_csv(csv_filepath)
        if df.empty:
            print(f"Warning: The CSV file '{csv_filepath}' is empty.")
            return None

        # Validate presence of some key column patterns to ensure it's likely the correct file type
        required_cols = ['FrameNumber', # Identifier
                         'Box_LC0_X_Ana', 'Box_LC0_Y_Ana', 'Box_LC0_Z_Ana', # Box Local Corners
                         'Floor_N_X_Ana', 'Floor_N_Y_Ana', 'Floor_N_Z_Ana', # Floor Normal
                         'Floor_P_X_Ana', 'Floor_P_Y_Ana', 'Floor_P_Z_Ana', # Floor Point
                         'CoM_Vx_Ana', 'CoM_Vy_Ana', 'CoM_Vz_Ana',          # CoM Velocity
                         'AngVel_Wx_Ana', 'AngVel_Wy_Ana', 'AngVel_Wz_Ana'  # Angular Velocity
                        ]
        missing_cols = [col for col in required_cols if col not in df.columns]
        
        if missing_cols:
            print(f"Warning: The CSV file '{csv_filepath}' is missing essential data columns: {', '.join(missing_cols)}")
            # Depending on strictness, could return None or allow proceeding with partial data.
            # For now, proceed with a warning. Plotting functions will need to handle missing data.
        return df
    except FileNotFoundError:
        print(f"Error: Transformed data file '{csv_filepath}' not found.")
        return None
    except Exception as e:
        print(f"Error reading transformed data CSV '{csv_filepath}': {e}")
        return None

def extract_data_for_plotting(data_row_series):
    """
    Extracts and structures data from a single row (Pandas Series) of the DataFrame
    into a dictionary suitable for plotting functions.
    Returns None if essential data is missing.
    """
    plot_data = {}
    try:
        plot_data['frame_number'] = data_row_series['FrameNumber']
        plot_data['time'] = data_row_series.get('Time', np.nan) # .get for optional 'Time'

        # Box corners in Analysis Frame (these are the local corners)
        box_corners_ana_list = []
        for i in range(8): # Assumes 8 corners
            box_corners_ana_list.append([
                data_row_series[f'Box_LC{i}_X_Ana'],
                data_row_series[f'Box_LC{i}_Y_Ana'],
                data_row_series[f'Box_LC{i}_Z_Ana']
            ])
        plot_data['box_corners_ana'] = np.array(box_corners_ana_list)

        # Floor parameters in Analysis Frame
        plot_data['n_floor_ana'] = data_row_series[['Floor_N_X_Ana', 'Floor_N_Y_Ana', 'Floor_N_Z_Ana']].values.astype(float)
        plot_data['p_floor_ana'] = data_row_series[['Floor_P_X_Ana', 'Floor_P_Y_Ana', 'Floor_P_Z_Ana']].values.astype(float)

        # Velocities in Analysis Frame
        plot_data['v_com_ana'] = data_row_series[['CoM_Vx_Ana', 'CoM_Vy_Ana', 'CoM_Vz_Ana']].values.astype(float)
        plot_data['omega_ana'] = data_row_series[['AngVel_Wx_Ana', 'AngVel_Wy_Ana', 'AngVel_Wz_Ana']].values.astype(float)
        
        return plot_data
    except KeyError as e:
        print(f"Error extracting data for frame {data_row_series.get('FrameNumber', 'Unknown')}: Missing column {e}. This frame will be skipped.")
        return None 
    except Exception as e_extract:
        print(f"Unexpected error extracting data for frame {data_row_series.get('FrameNumber', 'Unknown')}: {e_extract}. This frame will be skipped.")
        return None

# --- Plotting Utility Functions ---
def _plot_box_geometry(ax, box_corners_ana, hide_labels_flag, is_first_legend_pass_box):
    """Helper to plot box wireframe and face labels. Returns list of artists."""
    plotted_artists = []
    # Plot Box Wireframe
    for i_edge, (i, j) in enumerate(BOX_EDGES_AS_CORNER_INDICES):
        label_str = None
        if is_first_legend_pass_box and i_edge == 0 and not hide_labels_flag: # Label only first edge for legend
            label_str = 'Box (Analysis Frame)'
        line, = ax.plot([box_corners_ana[i,0], box_corners_ana[j,0]],
                        [box_corners_ana[i,1], box_corners_ana[j,1]],
                        [box_corners_ana[i,2], box_corners_ana[j,2]],
                        color='green', linewidth=1.0,
                        label=label_str)
        plotted_artists.append(line)
    
    # Plot Face Labels
    if not hide_labels_flag:
        for face_name, face_def in FACE_DEFINITIONS.items():
            face_corner_indices = face_def.get('corners')
            if face_corner_indices and len(face_corner_indices) == 4:
                if all(idx < len(box_corners_ana) for idx in face_corner_indices):
                    face_points = box_corners_ana[face_corner_indices]
                    face_center = np.mean(face_points, axis=0)
                    txt = ax.text(face_center[0], face_center[1], face_center[2], face_name,
                                  color='purple', ha='center', va='center', fontsize=7, alpha=0.7)
                    plotted_artists.append(txt)
    return plotted_artists

def _plot_transformed_floor_surface(ax, n_floor_ana, p_floor_ana):
    """Helper to plot the transformed floor plane. Returns list of artists."""
    if np.linalg.norm(n_floor_ana) < 1e-6: # Avoid division by zero if normal is zero vector
        print("Warning: Floor normal vector is close to zero. Cannot plot floor.")
        return []
    n_unit = n_floor_ana / np.linalg.norm(n_floor_ana)
    
    if abs(n_unit[0]) < 0.99: temp_vec = np.array([1.0, 0.0, 0.0])
    else: temp_vec = np.array([0.0, 1.0, 0.0])
    
    u1_vec = np.cross(n_unit, temp_vec)
    if np.linalg.norm(u1_vec) < 1e-6: # If n_unit was parallel to temp_vec
        # Try another temp_vec
        if abs(n_unit[1]) < 0.99: temp_vec = np.array([0.0, 1.0, 0.0])
        else: temp_vec = np.array([0.0, 0.0, 1.0])
        u1_vec = np.cross(n_unit, temp_vec)
        if np.linalg.norm(u1_vec) < 1e-6: # Still parallel, something is wrong (e.g. n_unit is zero, already checked)
            print("Warning: Could not find a vector orthogonal to floor normal. Floor not plotted.")
            return []
    u1_vec = u1_vec / np.linalg.norm(u1_vec)
    u2_vec = np.cross(n_unit, u1_vec) # u2_vec will be orthogonal and unit

    x_coords_plane = np.array([-PLOT_FLOOR_HALF_EXTENT_1, PLOT_FLOOR_HALF_EXTENT_1])
    y_coords_plane = np.array([-PLOT_FLOOR_HALF_EXTENT_2, PLOT_FLOOR_HALF_EXTENT_2])
    xx_plane, yy_plane = np.meshgrid(x_coords_plane, y_coords_plane)

    plane_points_x = p_floor_ana[0] + u1_vec[0] * xx_plane + u2_vec[0] * yy_plane
    plane_points_y = p_floor_ana[1] + u1_vec[1] * xx_plane + u2_vec[1] * yy_plane
    plane_points_z = p_floor_ana[2] + u1_vec[2] * xx_plane + u2_vec[2] * yy_plane
    
    floor_surface = ax.plot_surface(plane_points_x, plane_points_y, plane_points_z,
                                    color='dimgray', alpha=0.2, rstride=1, cstride=1,
                                    linewidth=0, antialiased=True)
    return [floor_surface]

def _plot_velocity_arrows(ax, v_com_ana, omega_ana, lin_vel_scale_factor, ang_vel_scale_factor, hide_labels_flag, is_first_legend_pass_vel):
    """Helper to plot translational and angular velocity vectors. Returns list of artists."""
    plotted_artists = []
    characteristic_length = np.max(BOX_DIMS) 
    
    norm_v_com = np.linalg.norm(v_com_ana)
    if norm_v_com > 1e-6:
        v_direction = v_com_ana / norm_v_com
        arrow_length_v = characteristic_length * lin_vel_scale_factor
        
        v_arrow = ax.quiver(0, 0, 0, v_direction[0], v_direction[1], v_direction[2],
                            length=arrow_length_v, color='blue', 
                            arrow_length_ratio=0.2, pivot='tail', linewidths=1.5,
                            label='v_CoM (analysis)' if not hide_labels_flag and is_first_legend_pass_vel else None)
        plotted_artists.append(v_arrow)
        if not hide_labels_flag:
            v_text_pos = v_direction * arrow_length_v * 1.15
            v_text = ax.text(v_text_pos[0], v_text_pos[1], v_text_pos[2],
                             f"v ({norm_v_com:.1f})", color='blue', fontsize=7, ha='center', va='bottom')
            plotted_artists.append(v_text)

    norm_omega = np.linalg.norm(omega_ana)
    if norm_omega > 1e-6:
        omega_direction = omega_ana / norm_omega
        arrow_length_omega_axis = characteristic_length * ang_vel_scale_factor

        omega_axis_arrow = ax.quiver(0, 0, 0, omega_direction[0], omega_direction[1], omega_direction[2],
                                     length=arrow_length_omega_axis, color='red',
                                     arrow_length_ratio=0.2, pivot='tail', linewidths=1.5,
                                     label='ω (axis, analysis)' if not hide_labels_flag and is_first_legend_pass_vel else None)
        plotted_artists.append(omega_axis_arrow)
        if not hide_labels_flag:
            omega_text_pos = omega_direction * arrow_length_omega_axis * 1.15
            omega_text = ax.text(omega_text_pos[0], omega_text_pos[1], omega_text_pos[2],
                                 f"ω ({norm_omega:.2f})", color='red', fontsize=7, ha='center', va='bottom')
            plotted_artists.append(omega_text)
        
        # Arc for angular velocity direction
        if abs(omega_direction[2]) < 0.99: temp_vec_arc = np.array([0, 0, 1.0])
        else: temp_vec_arc = np.array([1.0, 0.0, 0.0])
        
        u1_arc = np.cross(omega_direction, temp_vec_arc)
        if np.linalg.norm(u1_arc) < 1e-6: # omega_direction was parallel to temp_vec_arc
            if abs(omega_direction[1]) < 0.99: temp_vec_arc_alt = np.array([0,1,0])
            else: temp_vec_arc_alt = np.array([1,0,0]) # Should be different from first temp_vec_arc
            u1_arc = np.cross(omega_direction, temp_vec_arc_alt)

        if np.linalg.norm(u1_arc) > 1e-6: # Proceed if u1_arc is valid
            u1_arc = u1_arc / np.linalg.norm(u1_arc)
            u2_arc = np.cross(omega_direction, u1_arc) # Already unit if u1_arc and omega_direction are unit and perp

            arc_radius = arrow_length_omega_axis * 0.4 # Radius of the arc
            num_arc_points = 15
            theta_arc_pts = np.linspace(0, np.pi / 2.5, num_arc_points) # Arc angle (e.g. ~72 degrees)

            arc_pts_x = arc_radius * (np.cos(theta_arc_pts) * u1_arc[0] + np.sin(theta_arc_pts) * u2_arc[0])
            arc_pts_y = arc_radius * (np.cos(theta_arc_pts) * u1_arc[1] + np.sin(theta_arc_pts) * u2_arc[1])
            arc_pts_z = arc_radius * (np.cos(theta_arc_pts) * u1_arc[2] + np.sin(theta_arc_pts) * u2_arc[2])
            
            arc_line, = ax.plot(arc_pts_x, arc_pts_y, arc_pts_z, color='magenta', linestyle='-', linewidth=1.2)
            plotted_artists.append(arc_line)
            
            # Arrowhead for the arc
            theta_end = theta_arc_pts[-1]
            tangent_vec_x = arc_radius * (-np.sin(theta_end) * u1_arc[0] + np.cos(theta_end) * u2_arc[0])
            tangent_vec_y = arc_radius * (-np.sin(theta_end) * u1_arc[1] + np.cos(theta_end) * u2_arc[1])
            tangent_vec_z = arc_radius * (-np.sin(theta_end) * u1_arc[2] + np.cos(theta_end) * u2_arc[2])
            
            norm_tangent = np.linalg.norm([tangent_vec_x, tangent_vec_y, tangent_vec_z])
            if norm_tangent > 1e-6:
                tangent_dir = np.array([tangent_vec_x, tangent_vec_y, tangent_vec_z]) / norm_tangent
                # Use Arrow3D for a better 3D arrowhead if FancyArrowPatch is problematic for this
                # For now, using quiver for simplicity
                arc_arrowhead = ax.quiver(arc_pts_x[-1], arc_pts_y[-1], arc_pts_z[-1],
                                          tangent_dir[0], tangent_dir[1], tangent_dir[2],
                                          length=arc_radius * 0.35, # Length of the arrowhead itself
                                          color='magenta', normalize=True, arrow_length_ratio=0.6, pivot='tip', linewidths=1.0)
                plotted_artists.append(arc_arrowhead)
        else:
            print("Warning: Could not draw angular velocity arc due to u1_arc calculation issue.")
            
    return plotted_artists

def calculate_overall_plot_limits(all_frames_plot_data_list, args_for_scaling):
    """Calculates plot limits encompassing all objects across all provided frames."""
    if not all_frames_plot_data_list:
        return (-1500, 1500), (-1500, 1500), (-1000, 2000)

    global_min_coords = np.full(3, np.inf)
    global_max_coords = np.full(3, -np.inf)
    has_valid_data = False

    for frame_plot_data in all_frames_plot_data_list:
        if not frame_plot_data: continue
        has_valid_data = True
        
        # Box corners
        global_min_coords = np.minimum(global_min_coords, frame_plot_data['box_corners_ana'].min(axis=0))
        global_max_coords = np.maximum(global_max_coords, frame_plot_data['box_corners_ana'].max(axis=0))

        # Floor patch estimation
        n_f, p_f = frame_plot_data['n_floor_ana'], frame_plot_data['p_floor_ana']
        if np.linalg.norm(n_f) > 1e-6:
            n_f_unit = n_f / np.linalg.norm(n_f)
            if abs(n_f_unit[0]) < 0.99: temp_v = np.array([1.,0.,0.])
            else: temp_v = np.array([0.,1.,0.])
            u1_f = np.cross(n_f_unit, temp_v)
            if np.linalg.norm(u1_f) > 1e-6: u1_f /= np.linalg.norm(u1_f)
            else: u1_f = np.array([1.,0.,0.]) if abs(n_f_unit[1]) < 0.99 else np.array([0.,0.,1.]) # More robust fallback
            u2_f = np.cross(n_f_unit, u1_f)
            
            for x_s in [-1,1]:
                for y_s in [-1,1]:
                    corner_f = p_f + x_s*PLOT_FLOOR_HALF_EXTENT_1*u1_f + y_s*PLOT_FLOOR_HALF_EXTENT_2*u2_f
                    global_min_coords = np.minimum(global_min_coords, corner_f)
                    global_max_coords = np.maximum(global_max_coords, corner_f)
        
        # Velocity vector tips (rough estimation)
        char_len = np.max(BOX_DIMS)
        v_tip = (frame_plot_data['v_com_ana'] / (np.linalg.norm(frame_plot_data['v_com_ana'])+1e-9)) * char_len * args_for_scaling.lin_vel_scale
        o_tip = (frame_plot_data['omega_ana'] / (np.linalg.norm(frame_plot_data['omega_ana'])+1e-9)) * char_len * args_for_scaling.ang_vel_scale
        global_min_coords = np.minimum(global_min_coords, v_tip)
        global_max_coords = np.maximum(global_max_coords, v_tip)
        global_min_coords = np.minimum(global_min_coords, o_tip)
        global_max_coords = np.maximum(global_max_coords, o_tip)


    if not has_valid_data or np.any(np.isinf(global_min_coords)) or np.any(np.isinf(global_max_coords)):
        return (-1500, 1500), (-1500, 1500), (-1000, 2000)

    center = (global_max_coords + global_min_coords) / 2.0
    data_spans = global_max_coords - global_min_coords
    
    # Ensure a minimum visual span based on box dimensions, add padding
    min_span_needed = np.max(BOX_DIMS) * 0.5 
    padded_spans = np.maximum(data_spans, min_span_needed) * 1.5 # 50% padding on max span
    
    max_half_span = np.max(padded_spans) / 2.0
    if max_half_span < 10: max_half_span = 1000 # Absolute minimum if everything is zero

    xlim = (center[0] - max_half_span, center[0] + max_half_span)
    ylim = (center[1] - max_half_span, center[1] + max_half_span)
    zlim = (center[2] - max_half_span, center[2] + max_half_span)
    
    return xlim, ylim, zlim

# --- Main Function ---
def main():
    parser = argparse.ArgumentParser(
        description="Visualizes transformed frame data. Shows a single static frame or animates multiple frames."
    )
    parser.add_argument("--transformed_data_csv", type=str, required=True,
                        help="Path to the CSV file from AnalyzeTransformedFrame.py.")
    parser.add_argument("--animate", action="store_true",
                        help="Animate all frames in the CSV. If not set, shows static plot of --target_frame_number.")
    parser.add_argument("--target_frame_number", type=int, default=None,
                        help="FrameNumber to plot from the CSV (for static mode). If not provided and not animating, plots the first frame in the CSV.")
    parser.add_argument("--save_images", action="store_true",
                        help="Save the plot(s) as image(s).")
    parser.add_argument("--base_save_dir", type=str, default=".",
                        help="Base directory for saving images (under which PlotResults/subdir will be created). Default: current directory.")
    parser.add_argument("--hide_labels", action="store_true", help="Hide face and velocity labels.")
    parser.add_argument("--lin_vel_scale", type=float, default=0.2,
                        help="Scale factor for translational velocity arrow length (relative to max box dim).")
    parser.add_argument("--ang_vel_scale", type=float, default=0.2,
                        help="Scale factor for angular velocity axis arrow length (relative to max box dim).")
    parser.add_argument("--animation_interval", type=int, default=100,
                        help="Interval in ms between animation frames.")
    args = parser.parse_args()

    print(f"--- Plotting Transformed Frame(s) from: {args.transformed_data_csv} ---")

    df_all_loaded_frames = load_transformed_data_from_csv(args.transformed_data_csv)
    if df_all_loaded_frames is None or df_all_loaded_frames.empty:
        return

    # --- Determine which frames to render based on args ---
    frames_to_render_input_rows = pd.DataFrame() # DataFrame containing the rows to be rendered

    if args.animate:
        frames_to_render_input_rows = df_all_loaded_frames
        print(f"Mode: Animating {len(frames_to_render_input_rows)} frames.")
    else: # Static mode
        if args.target_frame_number is not None:
            # User specified a FrameNumber
            selected_rows_df = df_all_loaded_frames[df_all_loaded_frames['FrameNumber'] == args.target_frame_number]
            if selected_rows_df.empty:
                print(f"Error: Target FrameNumber {args.target_frame_number} not found in the CSV.")
                return
            frames_to_render_input_rows = selected_rows_df.head(1) # Take the first match if multiple
            print(f"Mode: Static plot for specified FrameNumber {args.target_frame_number}.")
        else:
            # Default to the first frame in the CSV if no FrameNumber is specified
            frames_to_render_input_rows = df_all_loaded_frames.head(1)
            print(f"Mode: Static plot for the first frame in the CSV (FrameNumber {frames_to_render_input_rows.iloc[0].get('FrameNumber', 'N/A')}).")

    if frames_to_render_input_rows.empty:
        print("No frames selected for plotting.")
        return
    
    # Extract plot data for all frames to be rendered (for limit calculation and animation)
    all_render_data_list = []
    for _, row in frames_to_render_input_rows.iterrows():
        data = extract_data_for_plotting(row)
        if data:
            all_render_data_list.append(data)
    
    if not all_render_data_list:
        print("No valid data could be extracted from selected frames.")
        return

    # --- Prepare save directory if saving images ---
    output_image_dir_full_path = None
    if args.save_images:
        input_filename_base = os.path.splitext(os.path.basename(args.transformed_data_csv))[0]
        specifier = ""
        if args.animate or len(all_render_data_list) > 1:
            specifier = "allframes"
        elif all_render_data_list: # Single frame
            specifier = f"frame{all_render_data_list[0]['frame_number']}"
        
        save_subdir_name = f"{input_filename_base}_{specifier}"
        output_image_dir_full_path = os.path.join(args.base_save_dir, "PlotResults", save_subdir_name)
        try:
            os.makedirs(output_image_dir_full_path, exist_ok=True)
            print(f"Images will be saved in: {output_image_dir_full_path}")
        except OSError as e_dir:
            print(f"Error creating output directory '{output_image_dir_full_path}': {e_dir}. Disabling image saving.")
            args.save_images = False

    # --- Setup Figure and Axes ---
    fig = plt.figure(figsize=(12, 10))
    ax = fig.add_subplot(111, projection='3d')

    # Set fixed plot limits and static elements (crucial for animation and consistent view)
    xlim_g, ylim_g, zlim_g = calculate_overall_plot_limits(all_render_data_list)
    ax.set_xlim(xlim_g)
    ax.set_ylim(ylim_g)
    ax.set_zlim(zlim_g)
    ax.set_xlabel("X_analysis (mm)")
    ax.set_ylabel("Y_analysis (mm)")
    ax.set_zlabel("Z_analysis (mm)")
    ax.set_box_aspect([1,1,1])

    # Title object for animation updates
    title_obj = ax.set_title("Initializing...", fontsize=10)
    
    # List to keep track of artists drawn in each frame for removal
    dynamic_artists_collection = []

    # --- Animation Update Function ---
    def update_animation_frame(frame_idx):
        nonlocal dynamic_artists_collection # Use nonlocal to modify list in outer scope
        
        # Remove artists from the previous frame
        for artist in dynamic_artists_collection:
            artist.remove()
        dynamic_artists_collection.clear()

        current_frame_plot_data = all_render_data_list[frame_idx]
        
        # Update title
        title_str = f"Analysis Frame: {current_frame_plot_data['frame_number']}"
        if not pd.isna(current_frame_plot_data['time']):
            title_str += f" (Time: {current_frame_plot_data['time']:.3f}s)"
        title_obj.set_text(title_str)
        # dynamic_artists_collection.append(title_obj) # Title is an updating artist

        # Plot dynamic elements for the current frame
        is_first_legend_pass = (frame_idx == 0) # For adding legend only once
        
        artists_box = _plot_box_geometry(ax, current_frame_plot_data['box_corners_ana'], args.hide_labels, is_first_legend_pass)
        dynamic_artists_collection.extend(artists_box)
        
        artists_floor = _plot_transformed_floor_surface(ax, current_frame_plot_data['n_floor_ana'], current_frame_plot_data['p_floor_ana'])
        dynamic_artists_collection.extend(artists_floor)
        
        artists_vel = _plot_velocity_arrows(ax, current_frame_plot_data['v_com_ana'], current_frame_plot_data['omega_ana'],
                                            args.lin_vel_scale, args.ang_vel_scale, args.hide_labels, is_first_legend_pass)
        dynamic_artists_collection.extend(artists_vel)
        
        # Legend should be created once if labels are present
        if is_first_legend_pass and not args.hide_labels:
            handles, labels = ax.get_legend_handles_labels()
            if handles: # Only create legend if there are labeled artists
                 # To avoid duplicate legend entries if update is called multiple times for static plot
                if not hasattr(ax, '_legend_drawn_flag') or not ax._legend_drawn_flag:
                    ax.legend(handles, labels, fontsize=8, loc='best')
                    ax._legend_drawn_flag = True


        return dynamic_artists_collection # Return list of artists to FuncAnimation

    # --- Execute Plotting ---
    if args.animate:
        if not all_render_data_list:
            print("No frames to animate.")
        else:
            print("Starting animation...")
            anim = FuncAnimation(fig, update_animation_frame, frames=len(all_render_data_list),
                                 interval=args.animation_interval, blit=False, repeat=True)
            
            if args.save_images: 
                print(f"Saving animation frames as images to {output_image_dir_full_path}...")
                # To save images from an animation, it's often better to iterate and save
                # rather than relying on FuncAnimation's save for image sequences if it's complex.
                # However, for simplicity, we'll re-draw each frame.
                # This means FuncAnimation above is just for display if not saving.
                # If saving images AND animating, the on-screen animation will run.
                # If ONLY saving images for an "animation sequence", don't call plt.show().
                
                # Re-loop for saving to ensure clean state for each image if FuncAnimation is problematic for saving
                # This is slightly inefficient as it re-extracts data, but ensures clean plots.
                # A better way would be to have FuncAnimation's update function also handle saving.
                # For now, let's assume if --animate and --save_images, we show animation AND save.
                # The save loop below is more for "save all frames as images" when not primarily animating on screen.

                # If the goal is to save all frames specified by `frames_to_render_list`
                # without necessarily running the interactive animation:
                if not plt.isinteractive(): # If not in interactive mode, plt.show() blocks.
                    plt.ioff() # Turn off interactive mode for saving loop

                for i, frame_data_to_save in enumerate(all_render_data_list):
                    # Effectively, we are re-doing the plot for each save.
                    # This is not ideal if FuncAnimation is also running for display.
                    # A better pattern for "save all frames" without animation display:
                    # if args.save_images and args.animate: # User wants to see anim AND save
                    #    print("Warning: Saving all frames while animating might be slow or have issues.")
                    #    # Here, one might try to hook into the animation's frame generation.
                    # else if args.save_images: # Just save, no interactive animation
                    
                    # Current logic: if --animate and --save_images, it will show animation.
                    # The saving loop below will then re-run the plotting for each frame.
                    # This is not optimal. Let's refine.

                    # If saving images for an "animation sequence", we don't need FuncAnimation for display.
                    # We just loop, plot, save.
                    if i > 0 : # For frames after the first, clear and redraw
                        for artist in dynamic_artists_collection: artist.remove()
                        dynamic_artists_collection.clear()
                        # Title is part of dynamic artists if we don't use title_obj.set_text()
                        # If title_obj is used, it's updated.
                    
                    # Call update_animation_frame to draw the content
                    update_animation_frame(i) # This will draw frame i

                    actual_frame_num = frame_data_to_save['frame_number']
                    save_path = os.path.join(output_image_dir_full_path, f"frame_{actual_frame_num}.png")
                    try:
                        fig.savefig(save_path, dpi=150)
                        print(f"  Saved {save_path}")
                    except Exception as e_sf:
                        print(f"  Error saving image {save_path}: {e_sf}")
                
                print("Finished saving animation frames.")
                if not (args.animate and plt.isinteractive()): # If not interactively animating, close.
                    plt.close(fig)
            
            if not args.save_images: # Only show if not saving (or if saving and interactive)
                 plt.tight_layout()
                 plt.show()

    else: # Static plot mode (single frame)
        if not all_render_data_list:
            print("No frame data selected for static plot.")
        else:
            print(f"Generating static plot for frame: {all_render_data_list[0]['frame_number']}")
            update_animation_frame(0) # Call update once for the single selected frame
            plt.tight_layout()
            if args.save_images:
                actual_frame_num = all_render_data_list[0]['frame_number']
                save_path = os.path.join(output_image_dir_full_path, f"frame_{actual_frame_num}.png")
                try:
                    fig.savefig(save_path, dpi=150)
                    print(f"Static plot saved to: {save_path}")
                except Exception as e_sf:
                    print(f"  Error saving static plot image {save_path}: {e_sf}")
                plt.close(fig) # Close after saving
            else: # Show static plot on screen
                plt.show()

    print(f"--- Plotting Script Finished ---")

if __name__ == '__main__':
    main()
# --- END OF FILE PlotTransformedFrame.py (Part 3/3) ---