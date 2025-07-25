import pandas as pd
import numpy as np
from scipy.optimize import minimize
from scipy.spatial.transform import Rotation as R
from typing import Dict, Any, List

class PoseOptimizer:
    """
    스무딩된 마커 데이터를 사용하여 각 프레임별로 박스의 최적 자세(위치/회전)를 계산합니다.
    """

    def __init__(self, box_dims: np.ndarray, face_definitions: Dict[str, Any], local_box_corners: np.ndarray):
        self.box_dims = box_dims
        self.face_definitions = face_definitions
        self.local_box_corners = local_box_corners
        self.box_half_dims = box_dims / 2.0

    def _objective_function(self, params: np.ndarray, frame_markers: List[Dict[str, Any]]) -> float:
        T_guess, rot_vec_guess = params[:3], params[3:]
        try:
            R_inv_guess = R.from_rotvec(rot_vec_guess).inv()
        except ValueError:
            return np.inf

        total_sq_distance = 0.0
        for marker_info in frame_markers:
            m_cam = marker_info['cam_coords']
            m_local_guess = R_inv_guess.apply(m_cam - T_guess)

            # Placeholder for distance calculation logic from AlignBoxMain.py
            # This needs to be replaced with the actual implementation
            dist = np.linalg.norm(m_local_guess)
            total_sq_distance += dist ** 2
        return total_sq_distance

    def _get_markers_for_frame(self, frame_row: pd.Series) -> List[Dict[str, Any]]:
        markers = []
        marker_ids = sorted(list(set([c.split('_')[0] for c in frame_row.index if c.endswith('_X')])))
        for mid in marker_ids:
            if f"{mid}_X" in frame_row and pd.notna(frame_row[f"{mid}_X"]):
                markers.append({
                    'id': mid,
                    'cam_coords': np.array([frame_row[f"{mid}_X"], frame_row[f"{mid}_Y"], frame_row[f"{mid}_Z"]])
                })
        return markers

    def process(self, df: pd.DataFrame) -> pd.DataFrame:
        if df.empty:
            return df

        pose_results = []
        prev_optimized_params = None

        for index, frame_row in df.iterrows():
            frame_markers = self._get_markers_for_frame(frame_row)
            if not frame_markers:
                pose_results.append({'Time': index})
                continue

            if prev_optimized_params is None:
                initial_T = np.mean([m['cam_coords'] for m in frame_markers], axis=0)
                initial_rot_vec = np.array([0.0, 0.0, 0.0])
            else:
                initial_T, initial_rot_vec = prev_optimized_params[:3], prev_optimized_params[3:]

            initial_params = np.concatenate([initial_T, initial_rot_vec])

            result = minimize(
                self._objective_function,
                initial_params,
                args=(frame_markers,),
                method='Nelder-Mead',
                options={'maxiter': 500, 'xatol': 1e-3, 'fatol': 1e-3}
            )

            optimized_params = result.x
            prev_optimized_params = optimized_params

            res_row = {'Time': index}
            res_row['Box_Tx'], res_row['Box_Ty'], res_row['Box_Tz'] = optimized_params[:3]
            res_row['Box_Rx'], res_row['Box_Ry'], res_row['Box_Rz'] = optimized_params[3:]
            pose_results.append(res_row)

        pose_df = pd.DataFrame(pose_results).set_index('Time')

        final_df = df.join(pose_df)

        print(f"[PoseOptimizer INFO] Processed {len(df)} frames.")
        return final_df
