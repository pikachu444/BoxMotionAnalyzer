import pandas as pd
import numpy as np
from scipy.optimize import minimize
from scipy.spatial.transform import Rotation as R
from typing import Dict, Any, List, Tuple
from multiprocessing import Pool, cpu_count

# 클래스 외부로 objective_function을 빼내어 multiprocessing에서 pickle할 수 있도록 함
def _objective_function(params: np.ndarray, frame_markers: List[Dict[str, Any]], box_dims: np.ndarray) -> float:
    T_guess, rot_vec_guess = params[:3], params[3:]
    try:
        R_inv_guess = R.from_rotvec(rot_vec_guess).inv()
    except ValueError:
        return np.inf

    total_sq_distance = 0.0
    for marker_info in frame_markers:
        m_cam = marker_info['cam_coords']
        m_local_guess = R_inv_guess.apply(m_cam - T_guess)
        dist = np.linalg.norm(m_local_guess) # Placeholder
        total_sq_distance += dist ** 2
    return total_sq_distance

def _optimize_single_frame(args: Tuple) -> Dict[str, Any]:
    """단일 프레임에 대한 최적화를 수행하는 워커 함수."""
    frame_index, frame_row, prev_params, box_dims = args

    markers = []
    marker_ids = sorted(list(set([c.split('_')[0] for c in frame_row.index if c.endswith('_X')])))
    for mid in marker_ids:
        if f"{mid}_X" in frame_row and pd.notna(frame_row[f"{mid}_X"]):
            markers.append({
                'id': mid,
                'cam_coords': np.array([frame_row[f"{mid}_X"], frame_row[f"{mid}_Y"], frame_row[f"{mid}_Z"]])
            })

    if not markers:
        return {'Time': frame_index}

    if prev_params is None:
        initial_T = np.mean([m['cam_coords'] for m in markers], axis=0)
        initial_rot_vec = np.array([0.0, 0.0, 0.0])
    else:
        initial_T, initial_rot_vec = prev_params[:3], prev_params[3:]

    initial_params = np.concatenate([initial_T, initial_rot_vec])

    result = minimize(
        _objective_function,
        initial_params,
        args=(markers, box_dims),
        method='Nelder-Mead',
        options={'maxiter': 500, 'xatol': 1e-3, 'fatol': 1e-3}
    )

    optimized_params = result.x

    res_row = {'Time': frame_index}
    res_row['Box_Tx'], res_row['Box_Ty'], res_row['Box_Tz'] = optimized_params[:3]
    res_row['Box_Rx'], res_row['Box_Ry'], res_row['Box_Rz'] = optimized_params[3:]
    return res_row

class PoseOptimizer:
    def __init__(self, box_dims: np.ndarray, face_definitions: Dict[str, Any], local_box_corners: np.ndarray):
        self.box_dims = box_dims
        self.face_definitions = face_definitions
        self.local_box_corners = local_box_corners

    def process(self, df: pd.DataFrame) -> pd.DataFrame:
        if df.empty:
            return df

        tasks = []
        for index, row in df.iterrows():
            tasks.append((index, row, None, self.box_dims))

        num_processes = max(1, cpu_count() - 1)
        print(f"[PoseOptimizer INFO] Starting optimization with {num_processes} processes...")

        with Pool(processes=num_processes) as pool:
            pose_results = pool.starmap(_optimize_single_frame, tasks)

        pose_df = pd.DataFrame(pose_results).set_index('Time')

        final_df = df.join(pose_df)

        print(f"[PoseOptimizer INFO] Processed {len(df)} frames.")
        return final_df
