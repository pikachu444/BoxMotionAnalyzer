# =============================================
#   박스 & 마커 시계열 테스트 데이터 생성기
#   (PyVista 시각화 파이프라인 2단계)
# =============================================
# 1. config.py의 좌표계/인덱스/라벨/사이즈 등 기준 100% 준수
# 2. 3D rigid transformation: 각 프레임마다 박스가 x축을 기준으로 넘어지는 모션
#    (회전행렬 R, 병진벡터 t)
# 3. Multi-Header CSV 생성 (HeaderL1, HeaderL2, HeaderL3 준수)
# =============================================

import numpy as np
import pandas as pd
import os
from src.config import config_visualization as config
from src.config.data_columns import HeaderL1, HeaderL2, HeaderL3

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
    Generates marker positions evenly distributed INSIDE each face of the box.
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

        if n_markers <= 3:
            grid_u, grid_v = n_markers, 1
        elif n_markers == 4:
            grid_u, grid_v = 2, 2
        elif n_markers <= 6:
            grid_u, grid_v = 3, 2
        elif n_markers <= 8:
            grid_u, grid_v = 4, 2
        else:
            grid_u, grid_v = int(np.ceil(np.sqrt(n_markers))), int(np.round(np.sqrt(n_markers)))

        margin = 0.2
        u_steps = np.linspace(margin, 1.0 - margin, grid_u)
        v_steps = np.linspace(margin, 1.0 - margin, grid_v)

        for v in v_steps:
            for u in u_steps:
                if len(face_positions) < n_markers:
                    point = p0 + u * u_vec + v * v_vec
                    face_positions.append(point)

        while len(face_positions) < n_markers:
            face_positions.append(p0 + 0.5 * u_vec + 0.5 * v_vec)

        all_marker_positions.extend(face_positions[:n_markers])

    return np.array(all_marker_positions)

def rotation_matrix_x(theta):
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
    # We need to construct a list of (Level1, Level2, Level3) tuples
    header_tuples = []

    # Define objects: Corners + Markers
    # Note: config.BOX_CORNERS_LABELS are "C1"..."C8"
    objects = config.BOX_CORNERS_LABELS + config.MARKER_LABELS

    # 1. Info Columns (Frame, Time)
    # These must be included in the MultiIndex to maintain structure
    # Frame -> (Info, Frame, Number)
    header_tuples.append((HeaderL1.INFO, HeaderL2.FRAME, HeaderL3.NUM))
    # Time -> (Info, Time, s) (Using 's' as per changeheader.txt/data_columns.py or 'Time'?)
    # data_columns.py: RESULT_TIME_COL = (HeaderL1.INFO, HeaderL2.TIME, HeaderL3.TIME)
    # But HeaderL3.TIME is "Time". HeaderL3.SEC is "s".
    # changeheader.txt says: `Time` -> ('Info', 'Time', 's')
    # Let's check src/config/data_columns.py again.
    # RESULT_TIME_COL = (HeaderL1.INFO, HeaderL2.TIME, HeaderL3.TIME) -> ('Info', 'Time', 'Time')
    # Wait, in data_columns.py: HeaderL3.TIME = "Time".
    # Let's stick to RESULT_TIME_COL constant if possible, but we are building the list manually.
    # I will use HeaderL3.TIME based on RESULT_TIME_COL definition in data_columns.py
    header_tuples.append((HeaderL1.INFO, HeaderL2.TIME, HeaderL3.TIME))

    # 2. Position & Velocity Columns for each object
    for obj_label in objects:
        # Position: PX, PY, PZ
        header_tuples.append((HeaderL1.POS, obj_label, HeaderL3.PX))
        header_tuples.append((HeaderL1.POS, obj_label, HeaderL3.PY))
        header_tuples.append((HeaderL1.POS, obj_label, HeaderL3.PZ))

        # Velocity: VX, VY, VZ
        header_tuples.append((HeaderL1.VEL, obj_label, HeaderL3.VX))
        header_tuples.append((HeaderL1.VEL, obj_label, HeaderL3.VY))
        header_tuples.append((HeaderL1.VEL, obj_label, HeaderL3.VZ))

    columns = pd.MultiIndex.from_tuples(
        header_tuples,
        names=[config.MH_LEVEL_DATATYPE, config.MH_LEVEL_OBJECT_ID, config.MH_LEVEL_AXIS]
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

        # Build row data in the exact order of header_tuples
        row_data = []

        # Info
        row_data.append(frame_idx) # Frame
        row_data.append(t)         # Time

        # Objects
        # corner indices: 0..7
        # marker indices: 0..M-1

        # We need to iterate objects in the same order as header loop
        # objects = corners + markers

        # Helper to get P and V for an object index
        # Corners first
        for i, _ in enumerate(config.BOX_CORNERS_LABELS):
            p = corners_world[i]
            v = corners_vel[i]
            row_data.extend([p[0], p[1], p[2]]) # PX, PY, PZ
            row_data.extend([v[0], v[1], v[2]]) # VX, VY, VZ

        # Markers next
        for i, _ in enumerate(config.MARKER_LABELS):
            p = markers_world[i]
            v = markers_vel[i]
            row_data.extend([p[0], p[1], p[2]]) # PX, PY, PZ
            row_data.extend([v[0], v[1], v[2]]) # VX, VY, VZ

        all_frames_data.append(row_data)

    # --- Create and Save DataFrame ---
    df = pd.DataFrame(all_frames_data, columns=columns)

    # Ensure output directory exists
    output_dir = os.path.dirname(config.TEST_CSV_PATH)
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    df.to_csv(config.TEST_CSV_PATH, index=False) # index=False because Frame/Time are columns
    print(f"✓ Multi-header test data generated: {config.TEST_CSV_PATH}")
    print(f"  Shape: {df.shape}")
    print(f"  Columns Levels: {df.columns.nlevels}")

if __name__ == '__main__':
    main()
