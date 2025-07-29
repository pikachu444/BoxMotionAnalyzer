import pandas as pd
import numpy as np
from scipy.optimize import minimize
from scipy.spatial.transform import Rotation as R
from typing import Any
from src.config import config_analysis
from src.config.data_columns import PoseCols, RawMarkerCols, SourceCols, TimeCols

# Helper functions (remained the same)
def _distance_point_to_box_surface_overall(point_local, box_half_dims):
    closest_p_on_box = np.clip(point_local, -box_half_dims, box_half_dims)
    return np.linalg.norm(point_local - closest_p_on_box)

def _distance_point_to_assigned_face_surface_and_bounds(point_local, face_key, box_dims_param, face_definitions):
    if face_key not in face_definitions:
        return _distance_point_to_box_surface_overall(point_local, box_dims_param / 2.0)
    face_def = face_definitions[face_key]
    axis_idx, direction, bound_axes_indices = face_def['axis_idx'], face_def['direction'], face_def['bound_axes_indices']
    box_half_dims = box_dims_param / 2.0
    d_plane = np.abs(point_local[axis_idx] - direction * box_half_dims[axis_idx])
    d_bound_1 = np.maximum(0, np.abs(point_local[bound_axes_indices[0]]) - box_half_dims[bound_axes_indices[0]])
    d_bound_2 = np.maximum(0, np.abs(point_local[bound_axes_indices[1]]) - box_half_dims[bound_axes_indices[1]])
    return np.sqrt(d_plane**2 + d_bound_1**2 + d_bound_2**2)

def _kabsch_align(P, Q):
    if P.shape[0] < 3: return None
    centroid_P, centroid_Q = np.mean(P, axis=0), np.mean(Q, axis=0)
    P_centered, Q_centered = P - centroid_P, Q - centroid_Q
    H = P_centered.T @ Q_centered
    try:
        U, S, Vt = np.linalg.svd(H)
    except np.linalg.LinAlgError:
        return None
    R_kabsch = Vt.T @ U.T
    if np.linalg.det(R_kabsch) < 0:
        Vt[-1, :] *= -1
        R_kabsch = Vt.T @ U.T
    try:
        return R.from_matrix(R_kabsch).as_rotvec()
    except ValueError:
        return None

def _objective_function(params: np.ndarray, frame_markers: list[dict[str, Any]], box_dims: np.ndarray, face_definitions: dict[str, Any]) -> float:
    T_guess, rot_vec_guess = params[:3], params[3:]
    try:
        R_inv_guess = R.from_rotvec(rot_vec_guess).inv()
    except ValueError:
        return np.inf
    total_sq_distance = 0.0
    for marker_info in frame_markers:
        m_local_guess = R_inv_guess.apply(marker_info['cam_coords'] - T_guess)
        dist = _distance_point_to_assigned_face_surface_and_bounds(m_local_guess, marker_info['face_key'], box_dims, face_definitions)
        total_sq_distance += dist ** 2
    return total_sq_distance

def _get_box_world_corners(pose_params, local_box_corners):
    T, rot_vec = pose_params[:3], pose_params[3:]
    try:
        rot_obj = R.from_rotvec(rot_vec)
        return rot_obj.apply(local_box_corners) + T
    except ValueError:
        return np.full((8, 3), np.nan)

class PoseOptimizer:
    def __init__(self, box_dims: np.ndarray, face_definitions: dict[str, Any], local_box_corners: np.ndarray):
        self.box_dims = box_dims
        self.face_definitions = face_definitions
        self.local_box_corners = local_box_corners
        self.optimizer_options = {
            'maxiter': config_analysis.OPTIMIZER_MAX_ITERATIONS,
            'xatol': config_analysis.OPTIMIZER_XTOL,
            'fatol': config_analysis.OPTIMIZER_FATOL
        }

    def process(self, df: pd.DataFrame) -> pd.DataFrame:
        if df.empty:
            return df

        print(f"[PoseOptimizer INFO] Starting sequential optimization for {len(df)} frames...")
        results = []
        previous_optimized_params = None

        for frame_index, frame_row in df.iterrows():
            markers = []
            marker_ids = sorted(list(set([c.split('_')[0] for c in frame_row.index if c.endswith((RawMarkerCols.X_SUFFIX, RawMarkerCols.FACEINFO_SUFFIX))])))

            # This part is complex, ensuring we only consider valid markers for pose estimation
            valid_marker_ids = [mid for mid in marker_ids if f"{mid}{RawMarkerCols.X_SUFFIX}" in frame_row and pd.notna(frame_row[f"{mid}{RawMarkerCols.X_SUFFIX}"])]

            for mid in valid_marker_ids:
                face_key_val = frame_row.get(f"{mid}{RawMarkerCols.FACEINFO_SUFFIX}")
                face_key = str(face_key_val).strip().upper() if pd.notna(face_key_val) and str(face_key_val).strip().upper() not in ["", "NONE", "NULL", "ANY"] else None
                markers.append({
                    'id': mid,
                    'cam_coords': np.array([frame_row[f"{mid}{RawMarkerCols.X_SUFFIX}"], frame_row[f"{mid}{RawMarkerCols.Y_SUFFIX}"], frame_row[f"{mid}{RawMarkerCols.Z_SUFFIX}"]]),
                    'face_key': face_key
                })

            if not markers:
                results.append({TimeCols.TIME: frame_index})
                continue

            observed_coords = np.array([m['cam_coords'] for m in markers])
            if previous_optimized_params is None:
                initial_T = np.mean(observed_coords, axis=0)
                local_pts, cam_pts = [], []
                for m in markers:
                    if m['face_key'] in self.face_definitions:
                        face_def = self.face_definitions[m['face_key']]
                        local_coord = np.zeros(3)
                        local_coord[face_def['axis_idx']] = face_def['direction'] * self.box_dims[face_def['axis_idx']] / 2.0
                        local_pts.append(local_coord)
                        cam_pts.append(m['cam_coords'])

                initial_rot_vec = _kabsch_align(np.array(local_pts), np.array(cam_pts))
                if initial_rot_vec is None: initial_rot_vec = np.array([0.0, 0.0, 0.0])
            else:
                initial_T, initial_rot_vec = previous_optimized_params[:3], previous_optimized_params[3:]

            initial_params = np.concatenate([initial_T, initial_rot_vec])

            result = minimize(
                _objective_function, initial_params,
                args=(markers, self.box_dims, self.face_definitions),
                method='Nelder-Mead',
                options=self.optimizer_options
            )

            optimized_params = result.x
            world_corners = _get_box_world_corners(optimized_params, self.local_box_corners)

            res_row = {TimeCols.TIME: frame_index}
            res_row[PoseCols.POS_X], res_row[PoseCols.POS_Y], res_row[PoseCols.POS_Z] = optimized_params[:3]
            res_row[PoseCols.ROT_X], res_row[PoseCols.ROT_Y], res_row[PoseCols.ROT_Z] = optimized_params[3:]
            res_row[SourceCols.POSE] = "Optimized" if result.success else "OptimizationFailed"

            for i_corner, corner_coords in enumerate(world_corners):
                res_row[f'C{i_corner}_X'], res_row[f'C{i_corner}_Y'], res_row[f'C{i_corner}_Z'] = corner_coords

            results.append(res_row)
            previous_optimized_params = optimized_params if result.success else None

        if not results:
            return df

        pose_df = pd.DataFrame(results).set_index(TimeCols.TIME)
        final_df = df.copy()
        final_df.update(pose_df)
        for col in pose_df.columns:
            if col not in final_df.columns:
                final_df[col] = pose_df[col]

        print(f"[PoseOptimizer INFO] Finished sequential processing for {len(df)} frames.")
        return final_df
