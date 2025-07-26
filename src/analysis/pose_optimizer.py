import pandas as pd
import numpy as np
from scipy.optimize import minimize
from scipy.spatial.transform import Rotation as R
from typing import Dict, Any, List, Tuple
from multiprocessing import Pool, cpu_count

# [병렬 처리 참고]
# 이 함수는 PoseOptimizer 클래스 외부에 정의되어야 합니다.
# multiprocessing의 Pool은 각 자식 프로세스에 작업을 전달할 때 'pickle'이라는 직렬화 과정을 사용하는데,
# 클래스 내부에 정의된 인스턴스 메서드는 직접적으로 pickle하기가 복잡하거나 불가능한 경우가 많습니다.
# 따라서, 병렬로 실행될 작업 함수는 이처럼 최상위 레벨에 정의하는 것이 가장 안정적입니다.
def _objective_function(params: np.ndarray, frame_markers: List[Dict[str, Any]], box_dims: np.ndarray) -> float:
    """최적화를 위한 비용 함수 (단일 프레임용)."""
    T_guess, rot_vec_guess = params[:3], params[3:]
    try:
        R_inv_guess = R.from_rotvec(rot_vec_guess).inv()
    except ValueError:
        return np.inf

    total_sq_distance = 0.0
    for marker_info in frame_markers:
        m_cam = marker_info['cam_coords']
        m_local_guess = R_inv_guess.apply(m_cam - T_guess)
        # TODO: AlignBoxMain.py의 실제 거리 계산 로직으로 교체 필요
        dist = np.linalg.norm(m_local_guess) # 현재는 임시 Placeholder
        total_sq_distance += dist ** 2
    return total_sq_distance

def _optimize_single_frame(args: Tuple) -> Dict[str, Any]:
    """
    단일 프레임에 대한 최적화를 수행하는 워커(worker) 함수입니다.
    multiprocessing.Pool에 의해 각기 다른 프로세스에서 병렬로 실행될 대상입니다.
    """
    frame_index, frame_row, prev_params, box_dims = args

    # 1. 현재 프레임의 유효한 마커 데이터만 추출
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

    # 2. 최적화를 위한 초기값 설정
    if prev_params is None:
        # 이전 프레임 정보가 없으면, 현재 프레임의 마커들의 평균 위치를 초기 이동값으로 사용
        initial_T = np.mean([m['cam_coords'] for m in markers], axis=0)
        initial_rot_vec = np.array([0.0, 0.0, 0.0]) # 회전은 0으로 시작
    else:
        # 이전 프레임의 최적화 결과를 초기값으로 사용 (현재는 비활성화)
        initial_T, initial_rot_vec = prev_params[:3], prev_params[3:]

    initial_params = np.concatenate([initial_T, initial_rot_vec])

    # 3. SciPy를 사용한 최적화 실행
    result = minimize(
        _objective_function,
        initial_params,
        args=(markers, box_dims),
        method='Nelder-Mead',
        options={'maxiter': 500, 'xatol': 1e-3, 'fatol': 1e-3} # 빠른 테스트를 위해 옵션 완화
    )

    optimized_params = result.x

    # 4. 최적화된 결과(자세 정보)를 딕셔너리 형태로 반환
    res_row = {'Time': frame_index}
    res_row['Box_Tx'], res_row['Box_Ty'], res_row['Box_Tz'] = optimized_params[:3]
    res_row['Box_Rx'], res_row['Box_Ry'], res_row['Box_Rz'] = optimized_params[3:]
    return res_row

class PoseOptimizer:
    """
    스무딩된 마커 데이터를 사용하여 각 프레임별로 박스의 최적 자세(위치/회전)를 계산합니다.
    내부적으로 multiprocessing을 사용하여 계산 속도를 향상시킵니다.
    """
    def __init__(self, box_dims: np.ndarray, face_definitions: Dict[str, Any], local_box_corners: np.ndarray):
        self.box_dims = box_dims
        self.face_definitions = face_definitions
        self.local_box_corners = local_box_corners

    def process(self, df: pd.DataFrame) -> pd.DataFrame:
        if df.empty:
            return df

        # 1. 병렬 처리를 위한 데이터 준비
        # 각 프레임은 독립적인 작업 단위로 처리됩니다.
        # _optimize_single_frame 함수에 전달될 인자들의 리스트를 생성합니다.
        # 각 리스트 요소는 (프레임 인덱스, 프레임 데이터, 이전 프레임 파라미터, 박스 크기) 형태의 튜플입니다.
        # 참고: 현재 구현에서는 모든 프레임을 독립적으로 처리하므로, prev_params는 None으로 전달합니다.
        tasks = []
        for index, row in df.iterrows():
            tasks.append((index, row, None, self.box_dims))

        # 2. 프로세스 풀(Pool) 생성 및 병렬 처리 실행
        # 사용할 CPU 코어 수를 결정합니다 (시스템의 최대 코어 수 - 1, 최소 1개).
        num_processes = max(1, cpu_count() - 1)
        print(f"[PoseOptimizer INFO] Starting optimization with {num_processes} processes...")

        # with 구문을 사용하여 프로세스 풀을 안전하게 생성하고, 작업이 끝나면 자동으로 종료합니다.
        with Pool(processes=num_processes) as pool:
            # pool.starmap: 'tasks' 리스트에 있는 각 튜플을 `_optimize_single_frame` 함수의 인자로 각각 전달하여 병렬로 실행합니다.
            # 'starmap'은 'map'과 달리, (arg1, arg2, ...) 형태의 튜플을 f(arg1, arg2, ...)처럼 자동으로 풀어주는 역할을 합니다.
            # 모든 작업이 완료될 때까지 기다린 후, 그 결과(각 프레임의 최적화 결과 딕셔너리 리스트)를 반환받습니다.
            pose_results = pool.starmap(_optimize_single_frame, tasks)

        # 3. 결과 취합
        # 병렬 처리된 결과(딕셔너리 리스트)를 하나의 DataFrame으로 변환합니다.
        pose_df = pd.DataFrame(pose_results).set_index('Time')

        # 원본 DataFrame에 새로 계산된 자세 정보 DataFrame을 합칩니다.
        final_df = df.join(pose_df)

        print(f"[PoseOptimizer INFO] Processed {len(df)} frames.")
        return final_df
