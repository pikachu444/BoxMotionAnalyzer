import pandas as pd
import numpy as np
from scipy.optimize import minimize
from scipy.spatial.transform import Rotation as R
from typing import Any
from src.config import config_analysis
from src.config.data_columns import PoseCols, RawMarkerCols, SourceCols, TimeCols

# [병렬 처리 참고]
# 이 함수들은 PoseOptimizer 클래스 외부에 정의되어야 합니다.
# multiprocessing의 Pool은 각 자식 프로세스에 작업을 전달할 때 'pickle'이라는 직렬화 과정을 사용하는데,
# 클래스 내부에 정의된 인스턴스 메서드는 직접적으로 pickle하기가 복잡하거나 불가능한 경우가 많습니다.
# 따라서, 병렬로 실행될 작업 함수와 그 함수가 사용하는 다른 함수들은 이처럼 최상위 레벨에 정의하는 것이 가장 안정적입니다.

def _distance_point_to_box_surface_overall(point_local, box_half_dims):
    """AABB(Axis-Aligned Bounding Box)의 전체 표면에 대한 점의 최단 거리를 계산합니다."""
    closest_p_on_box = np.clip(point_local, -box_half_dims, box_half_dims)
    return np.linalg.norm(point_local - closest_p_on_box)

def _distance_point_to_assigned_face_surface_and_bounds(point_local, face_key, box_dims_param, face_definitions):
    """마커에 할당된 특정 면에 대한 거리를, 해당 면의 경계를 고려하여 계산합니다."""
    if face_key not in face_definitions:
        return _distance_point_to_box_surface_overall(point_local, box_dims_param / 2.0)

    face_def = face_definitions[face_key]
    axis_idx = face_def['axis_idx']
    direction = face_def['direction']
    bound_axes_indices = face_def['bound_axes_indices']
    box_half_dims = box_dims_param / 2.0

    # 1. 면의 무한 평면까지의 수직 거리 계산
    d_plane = np.abs(point_local[axis_idx] - direction * box_half_dims[axis_idx])

    # 2. 면의 경계(테두리)까지의 거리 계산
    d_bound_1 = np.maximum(0, np.abs(point_local[bound_axes_indices[0]]) - box_half_dims[bound_axes_indices[0]])
    d_bound_2 = np.maximum(0, np.abs(point_local[bound_axes_indices[1]]) - box_half_dims[bound_axes_indices[1]])

    # 3. 최종 거리는 피타고라스 정리를 사용하여 계산
    return np.sqrt(d_plane**2 + d_bound_1**2 + d_bound_2**2)

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
    if np.linalg.det(R_kabsch) < 0: # 반사 행렬 방지
        Vt[-1, :] *= -1
        R_kabsch = Vt.T @ U.T
    try:
        return R.from_matrix(R_kabsch).as_rotvec()
    except ValueError:
        return None

def _objective_function(params: np.ndarray, frame_markers: list[dict[str, Any]], box_dims: np.ndarray, face_definitions: dict[str, Any]) -> float:
    """최적화를 위한 비용 함수. 모든 마커와 박스 표면 간의 거리 제곱의 합을 최소화하는 것을 목표로 합니다."""
    T_guess, rot_vec_guess = params[:3], params[3:]
    try:
        R_inv_guess = R.from_rotvec(rot_vec_guess).inv()
    except ValueError:
        return np.inf # 잘못된 회전 벡터 값에 대한 페널티

    total_sq_distance = 0.0
    for marker_info in frame_markers:
        # 월드 좌표계의 마커를 추정된 박스의 로컬 좌표계로 변환
        m_local_guess = R_inv_guess.apply(marker_info['cam_coords'] - T_guess)

        # 면 정보 유무에 따라 다른 거리 계산 함수 호출
        face_key = marker_info['face_key']
        if face_key is not None and face_key in face_definitions:
            dist = _distance_point_to_assigned_face_surface_and_bounds(m_local_guess, face_key, box_dims, face_definitions)
        else:
            dist = _distance_point_to_box_surface_overall(m_local_guess, box_dims / 2.0)

        total_sq_distance += dist ** 2
    return total_sq_distance

def _get_box_world_corners(pose_params, local_box_corners):
    """최적화된 Pose(위치/회전)를 사용하여 박스의 8개 꼭짓점의 월드 좌표를 계산합니다."""
    T, rot_vec = pose_params[:3], pose_params[3:]
    try:
        rot_obj = R.from_rotvec(rot_vec)
        # 로컬 좌표계의 꼭짓점들을 월드 좌표계로 변환
        return rot_obj.apply(local_box_corners) + T
    except ValueError:
        # 잘못된 회전 벡터의 경우 NaN으로 채워진 배열 반환
        return np.full((8, 3), np.nan)

class PoseOptimizer:
    """
    스무딩된 마커 데이터를 사용하여 각 프레임별로 박스의 최적 자세(위치/회전)를 순차적으로 계산합니다.
    """
    def __init__(self, box_dims: np.ndarray, face_definitions: dict[str, Any], local_box_corners: np.ndarray):
        self.box_dims = box_dims
        self.face_definitions = face_definitions
        self.local_box_corners = local_box_corners
        # 최적화 설정을 외부 config 파일에서 로드
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
            # 1. 현재 프레임의 유효한 마커 데이터 추출
            markers = []
            marker_ids = sorted(list(set([c.split('_')[0] for c in frame_row.index if c.endswith((RawMarkerCols.X_SUFFIX, RawMarkerCols.FACEINFO_SUFFIX))])))

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

            # 2. 최적화를 위한 초기값 설정
            observed_coords = np.array([m['cam_coords'] for m in markers])
            if previous_optimized_params is None: # 첫 프레임이거나 이전 프레임 최적화 실패 시
                initial_T = np.mean(observed_coords, axis=0) # 위치 초기값: 관측된 마커들의 중심

                # Kabsch 알고리즘으로 회전 초기값 계산
                local_pts, cam_pts = [], []
                for m in markers:
                    if m['face_key'] in self.face_definitions:
                        face_def = self.face_definitions[m['face_key']]
                        local_coord = np.zeros(3)
                        local_coord[face_def['axis_idx']] = face_def['direction'] * self.box_dims[face_def['axis_idx']] / 2.0
                        local_pts.append(local_coord)
                        cam_pts.append(m['cam_coords'])

                initial_rot_vec = _kabsch_align(np.array(local_pts), np.array(cam_pts))
                if initial_rot_vec is None: initial_rot_vec = np.array([0.0, 0.0, 0.0]) # Kabsch 실패 시 기본값
            else: # 이전 프레임의 결과를 초기값으로 사용
                initial_T, initial_rot_vec = previous_optimized_params[:3], previous_optimized_params[3:]

            initial_params = np.concatenate([initial_T, initial_rot_vec])

            # 3. SciPy를 사용한 최적화 실행
            result = minimize(
                _objective_function, initial_params,
                args=(markers, self.box_dims, self.face_definitions),
                method='Nelder-Mead',
                options=self.optimizer_options
            )

            # 4. 결과 저장 및 다음 프레임을 위한 값 업데이트
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

        # 5. 최종 결과를 원본 DataFrame에 통합
        pose_df = pd.DataFrame(results).set_index(TimeCols.TIME)
        final_df = df.copy()
        final_df.update(pose_df)
        # `update`는 기존에 없는 컬럼을 추가하지 않으므로, 수동으로 추가
        for col in pose_df.columns:
            if col not in final_df.columns:
                final_df[col] = pose_df[col]

        print(f"[PoseOptimizer INFO] Finished sequential processing for {len(df)} frames.")
        return final_df
