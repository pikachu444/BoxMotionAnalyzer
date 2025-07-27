import pandas as pd
import numpy as np
from scipy.optimize import minimize
from scipy.spatial.transform import Rotation as R
from typing import Dict, Any, List, Tuple
from multiprocessing import Pool, cpu_count

# [병렬 처리 참고]
# 이 함수들은 PoseOptimizer 클래스 외부에 정의되어야 합니다.
# multiprocessing의 Pool은 각 자식 프로세스에 작업을 전달할 때 'pickle'이라는 직렬화 과정을 사용하는데,
# 클래스 내부에 정의된 인스턴스 메서드는 직접적으로 pickle하기가 복잡하거나 불가능한 경우가 많습니다.
# 따라서, 병렬로 실행될 작업 함수와 그 함수가 사용하는 다른 함수들은 이처럼 최상위 레벨에 정의하는 것이 가장 안정적입니다.

def _distance_point_to_box_surface_overall(point_local, box_half_dims):
    """AABB의 전체 표면에 대한 점의 최단 거리를 계산합니다."""
    closest_p_on_box = np.clip(point_local, -box_half_dims, box_half_dims)
    distance = np.linalg.norm(point_local - closest_p_on_box)
    return distance

def _distance_point_to_assigned_face_surface_and_bounds(point_local, face_key, box_dims_param, face_definitions):
    """할당된 면에 대한 점의 거리를 경계를 고려하여 계산합니다."""
    if face_key not in face_definitions:
        return _distance_point_to_box_surface_overall(point_local, box_dims_param / 2.0)

    face_def = face_definitions[face_key]
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

def _kabsch_align(P, Q):
    """Kabsch 알고리즘을 사용하여 점 집합 P를 Q에 정렬하는 최적의 회전 벡터를 계산합니다."""
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

def _objective_function(params: np.ndarray, frame_markers: List[Dict[str, Any]], box_dims: np.ndarray, face_definitions: Dict[str, Any]) -> float:
    """최적화를 위한 비용 함수 (단일 프레임용)."""
    T_guess, rot_vec_guess = params[:3], params[3:]
    try:
        R_inv_guess = R.from_rotvec(rot_vec_guess).inv()
    except ValueError:
        return np.inf

    total_sq_distance = 0.0
    box_half_dims_overall = box_dims / 2.0
    for marker_info in frame_markers:
        m_cam = marker_info['cam_coords']
        face_key = marker_info['face_key']
        m_local_guess = R_inv_guess.apply(m_cam - T_guess)

        if face_key is not None and face_key in face_definitions:
            dist = _distance_point_to_assigned_face_surface_and_bounds(m_local_guess, face_key, box_dims, face_definitions)
        else:
            dist = _distance_point_to_box_surface_overall(m_local_guess, box_half_dims_overall)
        total_sq_distance += dist ** 2
    return total_sq_distance


class PoseOptimizer:
    """
    스무딩된 마커 데이터를 사용하여 각 프레임별로 박스의 최적 자세(위치/회전)를 순차적으로 계산합니다.
    """
    def __init__(self, box_dims: np.ndarray, face_definitions: Dict[str, Any], local_box_corners: np.ndarray):
        self.box_dims = box_dims
        self.face_definitions = face_definitions
        self.local_box_corners = local_box_corners

    def process(self, df: pd.DataFrame) -> pd.DataFrame:
        if df.empty:
            return df

        print(f"[PoseOptimizer INFO] Starting sequential optimization for {len(df)} frames...")

        results = []
        previous_optimized_params = None

        for frame_index, frame_row in df.iterrows():
            # 1. 현재 프레임의 유효한 마커 데이터 추출
            markers = []
            marker_ids = sorted(list(set([c.split('_')[0] for c in frame_row.index if c.endswith(('_X', '_FaceInfo'))])))
            for mid in marker_ids:
                x_col, y_col, z_col = f"{mid}_X", f"{mid}_Y", f"{mid}_Z"
                face_col = f"{mid}_FaceInfo"
                if x_col in frame_row and pd.notna(frame_row[x_col]):
                    face_key_val = frame_row.get(face_col)
                    face_key = str(face_key_val).strip().upper() if pd.notna(face_key_val) and str(face_key_val).strip().upper() not in ["", "NONE", "NULL", "ANY"] else None
                    markers.append({
                        'id': mid,
                        'cam_coords': np.array([frame_row[x_col], frame_row[y_col], frame_row[z_col]]),
                        'face_key': face_key
                    })

            if not markers:
                results.append({'Time': frame_index})
                continue

            # 2. 최적화를 위한 초기값 설정
            observed_coords = np.array([m['cam_coords'] for m in markers])
            if previous_optimized_params is None: # 첫 프레임 또는 이전 프레임 실패 시
                initial_T = np.mean(observed_coords, axis=0)

                # Kabsch 알고리즘을 위한 포인트 준비
                local_pts, cam_pts = [], []
                for m in markers:
                    if m['face_key'] in self.face_definitions:
                        face_def = self.face_definitions[m['face_key']]
                        local_coord = np.zeros(3)
                        local_coord[face_def['axis_idx']] = face_def['direction'] * self.box_dims[face_def['axis_idx']] / 2.0
                        local_pts.append(local_coord)
                        cam_pts.append(m['cam_coords'])

                rot_vec_kabsch = _kabsch_align(np.array(local_pts), np.array(cam_pts))
                initial_rot_vec = rot_vec_kabsch if rot_vec_kabsch is not None else np.array([0.0, 0.0, 0.0])
            else:
                initial_T, initial_rot_vec = previous_optimized_params[:3], previous_optimized_params[3:]

            initial_params = np.concatenate([initial_T, initial_rot_vec])

            # 3. SciPy를 사용한 최적화 실행
            result = minimize(
                _objective_function, initial_params,
                args=(markers, self.box_dims, self.face_definitions),
                method='Nelder-Mead',
                options={'maxiter': 1500, 'xatol': 1e-4, 'fatol': 1e-4}
            )

            # 4. 결과 저장 및 다음 프레임을 위한 값 업데이트
            optimized_params = result.x
            res_row = {'Time': frame_index}
            res_row['Box_Tx'], res_row['Box_Ty'], res_row['Box_Tz'] = optimized_params[:3]
            res_row['Box_Rx'], res_row['Box_Ry'], res_row['Box_Rz'] = optimized_params[3:]
            res_row['Pose_Source'] = "Optimized" if result.success else "OptimizationFailed"
            results.append(res_row)

            previous_optimized_params = optimized_params if result.success else None

        # 5. 결과 취합
        if not results:
            return df

        pose_df = pd.DataFrame(results).set_index('Time')
        final_df = df.copy()
        final_df.update(pose_df)
        for col in pose_df.columns:
            if col not in final_df.columns:
                final_df[col] = pose_df[col]

        print(f"[PoseOptimizer INFO] Finished sequential processing for {len(df)} frames.")
        return final_df
