# =============================================
#   박스 & 마커 시계열 테스트 데이터 생성기
#   (PyVista 시각화 파이프라인 2단계)
# =============================================
# 1. config.py의 좌표계/인덱스/라벨/사이즈 등 기준 100% 준수
# 2. 3D rigid transformation: 각 프레임마다 박스가 x축을 기준으로 넘어지는 모션
#    (회전행렬 R, 병진벡터 t)
# 3. 마커는 각 면에 균등/예시로 배치 (면 중심 등)
# 4. wide-format csv로 저장, 컬럼명/라벨 config.py와 일치
# =============================================

import numpy as np
import pandas as pd
import config

def box_local_corners():
    # (minX, minY, minZ) ~ (maxX, maxY, maxZ)
    Lx, Ly, Lz = config.BOX_SIZE
    return np.array([
        [0,    0,    0   ], # 0
        [Lx,   0,    0   ], # 1
        [Lx,   Ly,   0   ], # 2
        [0,    Ly,   0   ], # 3
        [0,    0,    Lz  ], # 4
        [Lx,   0,    Lz  ], # 5
        [Lx,   Ly,   Lz  ], # 6
        [0,    Ly,   Lz  ], # 7
    ])

def generate_marker_local_positions():
    """
    Generates marker positions evenly distributed INSIDE each face of the box,
    avoiding the corners and edges.
    """
    corners = box_local_corners()
    all_marker_positions = []

    for face, n_markers in zip(config.BOX_FACES, config.MARKERS_PER_FACE):
        p0, p1, p2, p3 = corners[face["corner_indices"]]

        # Define local axes for the face
        u_vec = p1 - p0  # Width direction
        v_vec = p3 - p0  # Height direction

        face_positions = []

        if n_markers == 0:
            continue

        # Determine grid size (e.g., 8 markers -> 4x2 grid)
        # This is a simple heuristic to make the distribution reasonable
        if n_markers <= 3:
            grid_u, grid_v = n_markers, 1
        elif n_markers == 4:
            grid_u, grid_v = 2, 2
        elif n_markers <= 6:
            grid_u, grid_v = 3, 2
        elif n_markers <= 8:
            grid_u, grid_v = 4, 2
        else: # for n_markers > 8
            grid_u, grid_v = int(np.ceil(np.sqrt(n_markers))), int(np.round(np.sqrt(n_markers)))

        # Generate points on a normalized grid (0 to 1) and scale them
        # We add a margin (e.g., 0.2) to keep points away from the edges
        margin = 0.2
        u_steps = np.linspace(margin, 1.0 - margin, grid_u)
        v_steps = np.linspace(margin, 1.0 - margin, grid_v)

        for v in v_steps:
            for u in u_steps:
                if len(face_positions) < n_markers:
                    # Calculate point position using local axes and center it
                    point = p0 + u * u_vec + v * v_vec
                    face_positions.append(point)

        # Ensure the exact number of markers is added for this face
        while len(face_positions) < n_markers:
            # If grid logic is imperfect, fill with center point
            face_positions.append(p0 + 0.5 * u_vec + 0.5 * v_vec)

        all_marker_positions.extend(face_positions[:n_markers])

    return np.array(all_marker_positions)

def rotation_matrix_x(theta):
    # x축 회전
    c, s = np.cos(theta), np.sin(theta)
    return np.array([
        [1, 0,  0],
        [0, c, -s],
        [0, s,  c]
    ])

def main():
    corners_local = box_local_corners()
    markers_local = generate_marker_local_positions()

    N = config.N_FRAMES
    FPS = config.FPS
    dt = 1.0 / FPS
    theta_max = np.radians(60)
    z0 = 500

    # --- Create MultiIndex Columns ---
    k = config
    header_tuples = []
    # Level 0: data_type (pos/vel), Level 1: object_id, Level 2: axis (x/y/z)
    for data_type in [k.MH_VAL_POSITION, k.MH_VAL_VELOCITY]:
        for obj_label in k.BOX_CORNERS_LABELS + k.MARKER_LABELS:
            for axis in ['x', 'y', 'z']:
                header_tuples.append((data_type, obj_label, axis))

    columns = pd.MultiIndex.from_tuples(
        header_tuples,
        names=[k.MH_LEVEL_DATATYPE, k.MH_LEVEL_OBJECT_ID, k.MH_LEVEL_AXIS]
    )

    # --- Generate Frame Data ---
    all_frames_data = []
    prev_corners_world = None
    prev_markers_world = None

    for frame_idx in range(N):
        t = frame_idx * dt
        theta = theta_max * (frame_idx / (N - 1)) if N > 1 else 0
        R = rotation_matrix_x(theta)

        # Center the rotation
        box0_world = R @ corners_local[0] + np.array([0, 0, z0])
        dz = -box0_world[2]
        trans = np.array([0, 0, z0 + dz])

        # Apply transformation
        corners_world = (R @ corners_local.T).T + trans
        markers_world = (R @ markers_local.T).T + trans

        # Calculate velocity
        if prev_corners_world is not None:
            corners_vel = (corners_world - prev_corners_world) / dt
            markers_vel = (markers_world - prev_markers_world) / dt
        else:
            corners_vel = np.zeros_like(corners_world)
            markers_vel = np.zeros_like(markers_world)

        prev_corners_world = corners_world.copy()
        prev_markers_world = markers_world.copy()

        # Flatten all data for this frame into a single row
        frame_data = np.concatenate([
            corners_world.flatten(),
            markers_world.flatten(),
            corners_vel.flatten(),
            markers_vel.flatten()
        ])
        all_frames_data.append(frame_data)

    # --- Create and Save DataFrame ---
    df = pd.DataFrame(all_frames_data, columns=columns)

    # Add frame and time columns at the beginning
    df.insert(0, 'time', np.arange(N) * dt)
    df.insert(0, 'frame', np.arange(N))

    # Pandas automatically handles writing multi-level headers
    df.to_csv(config.TEST_CSV_PATH, index=False)
    print(f"✓ Multi-header test data generated: {config.TEST_CSV_PATH}")

if __name__ == '__main__':
    main()
