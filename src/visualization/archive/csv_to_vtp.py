# =============================================
#   CSV → VTK PolyData(.vtp) 변환기
#   (박스 + 마커, 시계열/프레임별 분리 저장)
# =============================================
# 1. config.py의 CSV_COLUMNS, LABEL, 경로 등 100% 참조
# 2. 입력 csv에서 박스 8점, 마커 28점, 각 3D 좌표 추출
# 3. 각 프레임별로 box_xxx.vtp, marker_xxx.vtp 저장
# =============================================

import numpy as np
import pandas as pd
import pyvista as pv
import config
import os

def main():
    # 입력 파일 및 저장 경로
    csv_path = config.TEST_CSV_PATH
    data = pd.read_csv(csv_path)
    n_frames = data.shape[0]

    # 박스/마커 info
    n_box = len(config.BOX_CORNERS_LABELS)
    n_marker = len(config.MARKER_LABELS)

    # 좌표 컬럼 인덱스 자동 추출
    box_xyz_cols = []
    for c in config.BOX_CORNERS_LABELS:
        box_xyz_cols += [f"{c}_x", f"{c}_y", f"{c}_z"]
    marker_xyz_cols = []
    for m in config.MARKER_LABELS:
        marker_xyz_cols += [f"{m}_x", f"{m}_y", f"{m}_z"]

    # 저장 디렉토리 생성
    os.makedirs(config.DATA_DIR, exist_ok=True)

    for i in range(n_frames):
        row = data.iloc[i]
        # 박스 8점 좌표 (8,3)
        box_pts = row[box_xyz_cols].values.reshape(n_box, 3)
        # 마커 28점 좌표 (28,3)
        marker_pts = row[marker_xyz_cols].values.reshape(n_marker, 3)

        # 박스 PolyData (면은 quad로, points+cells)
        # (면 인덱스는 config.BOX_FACES에서 읽음)
        faces = []
        for f in config.BOX_FACES:
            idx = f["corner_indices"]
            faces.append([4] + idx)  # quad (4점)
        faces = np.array(faces).flatten()
        box_poly = pv.PolyData(box_pts)
        box_poly.faces = faces
        # 라벨, 프레임 정보 추가 (옵션)
        box_poly["label"] = np.array(config.BOX_CORNERS_LABELS)
        box_poly["frame"] = np.full(n_box, i)

        # 마커 PolyData (points only)
        marker_poly = pv.PolyData(marker_pts)
        marker_poly["label"] = np.array(config.MARKER_LABELS)
        marker_poly["frame"] = np.full(n_marker, i)

        # 파일 저장
        box_path = config.VTP_BOX_PATH.format(i)
        marker_path = config.VTP_MARKER_PATH.format(i)
        box_poly.save(box_path)
        marker_poly.save(marker_path)

        print(f"✓ frame {i} → {box_path}, {marker_path}")

if __name__ == '__main__':
    main()
