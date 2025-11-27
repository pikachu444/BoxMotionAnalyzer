import config  # config.py 파일이 같은 디렉토리에 있다고 가정합니다.
import pyvista as pv
import numpy as np
import glob
import os
# import threading # 현재 코드에서는 직접 사용되지 않음
# import time      # 현재 코드에서는 직접 사용되지 않음
# from pyvistaqt import BackgroundPlotter # 일반 Plotter 사용으로 변경

# =============================================
# config.py 예시 (실제 프로젝트에서는 별도 파일로 관리)
# class Config:
#     PVD_PATH = "data/animation.pvd"
#     DATA_DIR = "data"
#     FPS = 30
#     GROUND_CENTER = [0, 0, -1]
#     GROUND_SIZE = [10, 10]
#     GROUND_COLOR = "lightgreen"
#     BOX_CORNERS_LABELS = ["V1", "V2", "V3", "V4", "V5", "V6", "V7", "V8"]
#     MARKER_LABELS = ["M1", "M2", "M3", "M4", "M5", "M6", "M7", "M8"]
# config = Config()
# =============================================

def load_pvd_vtps():
    pvd_path = config.PVD_PATH
    print(f"[DEBUG] Checking PVD path: {pvd_path} (exists? {os.path.exists(pvd_path)})")
    box_vtps = []
    marker_vtps = []

    if os.path.exists(pvd_path):
        try:
            with open(pvd_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
            vtp_files = []
            pvd_dir = os.path.dirname(pvd_path)
            for line in lines:
                if ".vtp" in line or ".vtk" in line:
                    try:
                        vtp_file_relative = line.split('file="')[1].split('"')[0]
                        vtp_file_full_path = os.path.join(pvd_dir, vtp_file_relative)
                        if os.path.exists(vtp_file_full_path): # 파일 존재 유무 한 번 더 확인
                            vtp_files.append(vtp_file_full_path)
                        else:
                            print(f"[WARN] VTP file not found (referenced in PVD): {vtp_file_full_path}")
                    except IndexError:
                        print(f"[WARN] Malformed VTP entry in PVD file: {line.strip()}")

            for f_path in vtp_files: # 이미 valid_vtp_files로 필터링됨
                f_name = os.path.basename(f_path).lower()
                if "box" in f_name:
                    box_vtps.append(f_path)
                elif "marker" in f_name:
                    marker_vtps.append(f_path)
                else:
                    print(f"[WARN] Unknown VTP file type: {f_path}")
            box_vtps.sort()
            marker_vtps.sort()

            if not box_vtps or not marker_vtps:
                 print(f"[WARN] PVD parsed, but box_vtps ({len(box_vtps)}) or marker_vtps ({len(marker_vtps)}) is empty. Falling back to glob.")
                 box_vtps = sorted(glob.glob(os.path.join(config.DATA_DIR, "box_*.vtp")))
                 marker_vtps = sorted(glob.glob(os.path.join(config.DATA_DIR, "marker_*.vtp")))
        except Exception as e:
            print(f"[ERROR] Failed to parse PVD file {pvd_path}: {e}. Falling back to glob.")
            box_vtps = sorted(glob.glob(os.path.join(config.DATA_DIR, "box_*.vtp")))
            marker_vtps = sorted(glob.glob(os.path.join(config.DATA_DIR, "marker_*.vtp")))
    else:
        print(f"[INFO] PVD file not found: {pvd_path}. Searching in {config.DATA_DIR} using glob.")
        box_vtps = sorted(glob.glob(os.path.join(config.DATA_DIR, "box_*.vtp")))
        marker_vtps = sorted(glob.glob(os.path.join(config.DATA_DIR, "marker_*.vtp")))

    if not box_vtps and not marker_vtps: # 둘 다 비어있을 때만 에러 처리 (하나만 있을 수도 있으므로)
        print("[ERROR] No VTP files found for visualization. Check DATA_DIR and PVD_PATH.")
    elif not box_vtps:
        print("[WARN] No box VTP files found.")
    elif not marker_vtps:
        print("[WARN] No marker VTP files found.")

    print(f"[DEBUG] Found {len(box_vtps)} box VTPs, {len(marker_vtps)} marker VTPs.")
    return box_vtps, marker_vtps

def update_frame(idx, box_mesh_actor, marker_mesh_actor,
                 box_label_polydata, marker_label_polydata,
                 plotter, box_vtps, marker_vtps, n_frames):
    """
    애니메이션의 각 프레임마다 호출되어 메시와 라벨의 위치를 업데이트합니다.
    - 메시는 액터의 mapper.dataset을 직접 업데이트합니다.
    - 라벨은 연결된 PolyData의 points를 업데이트하여 위치를 갱신합니다.
    """
    try:
        # 1. 박스 메시 업데이트
        if idx < len(box_vtps):
            new_box_data = pv.read(box_vtps[idx])
            box_mesh_actor.mapper.dataset = new_box_data
            # 박스 라벨 PolyData 업데이트 (포인트 개수가 다를 수 있음에 유의)
            num_box_pts_for_labels = min(len(new_box_data.points), len(box_label_polydata.points))
            if num_box_pts_for_labels > 0 : # 업데이트 할 포인트가 있을 경우에만
                 box_label_polydata.points[:num_box_pts_for_labels] = new_box_data.points[:num_box_pts_for_labels]
                 # 만약 초기 라벨 포인트 수보다 현재 포인트 수가 적으면, 남는 라벨 포인트는 그대로 둠 (또는 특정 위치로 숨김 처리)
                 if len(new_box_data.points) < len(box_label_polydata.points):
                     # 예: 나머지 포인트들을 원점이나 매우 먼 곳으로 이동시켜 숨기는 효과
                     remaining_indices = range(len(new_box_data.points), len(box_label_polydata.points))
                     for i in remaining_indices:
                         box_label_polydata.points[i] = [0,0, -1e6] # 매우 먼 곳으로

            box_label_polydata.modified() # 변경 사항 알림
        else:
            print(f"[WARN] Box VTP index {idx} out of range.")

        # 2. 마커 메시 업데이트
        if idx < len(marker_vtps):
            new_marker_data = pv.read(marker_vtps[idx])
            marker_mesh_actor.mapper.dataset = new_marker_data
            # 마커 라벨 PolyData 업데이트
            num_marker_pts_for_labels = min(len(new_marker_data.points), len(marker_label_polydata.points))
            if num_marker_pts_for_labels > 0:
                marker_label_polydata.points[:num_marker_pts_for_labels] = new_marker_data.points[:num_marker_pts_for_labels]
                if len(new_marker_data.points) < len(marker_label_polydata.points):
                     remaining_indices = range(len(new_marker_data.points), len(marker_label_polydata.points))
                     for i in remaining_indices:
                         marker_label_polydata.points[i] = [0,0, -1e6]

            marker_label_polydata.modified() # 변경 사항 알림
        else:
            print(f"[WARN] Marker VTP index {idx} out of range.")

        plotter.title = f"Frame {idx + 1}/{n_frames}"
        plotter.render()

    except Exception as e:
        print(f"[ERROR] Failed to update frame {idx}: {e}")
        import traceback
        traceback.print_exc()

def next_frame(frame_idx, n_frames, update_frame_fn):
    if frame_idx[0] < n_frames - 1:
        frame_idx[0] += 1
        update_frame_fn(frame_idx[0])
    else:
        print("[INFO] Reached end of frames.")

def prev_frame(frame_idx, update_frame_fn):
    if frame_idx[0] > 0:
        frame_idx[0] -= 1
        update_frame_fn(frame_idx[0])
    else:
        print("[INFO] Reached start of frames.")

def main():
    box_vtps, marker_vtps = load_pvd_vtps()

    if not box_vtps and not marker_vtps: # 둘 다 파일이 없을 경우
        return

    # 사용 가능한 프레임 수는 box 또는 marker 중 하나라도 파일이 있는 경우를 고려
    n_frames_box = len(box_vtps)
    n_frames_marker = len(marker_vtps)

    if n_frames_box == 0 and n_frames_marker == 0:
        print("[ERROR] No VTP files loaded for box or markers. Exiting.")
        return

    # n_frames는 둘 중 최소값이 아니라, 각각의 VTP 리스트 길이를 사용하도록 update_frame에서 처리
    # 여기서는 UI 표시용으로 최대값을 사용할 수 있음
    n_frames_ui = max(n_frames_box, n_frames_marker)
    if n_frames_box != n_frames_marker:
        print(f"[WARN] Mismatch: {n_frames_box} box VTPs, {n_frames_marker} marker VTPs. Animation will run up to available frames for each.")

    plotter = pv.Plotter(notebook=False)
    plotter.set_background("white")

    # --- 초기 메시 및 라벨 PolyData 생성 ---
    # Box
    if n_frames_box > 0:
        initial_box_data = pv.read(box_vtps[0])
        box_mesh_actor = plotter.add_mesh(initial_box_data, color="lightblue", show_edges=True, opacity=0.5, name="box_actor")

        # 박스 라벨을 위한 PolyData (초기 포인트 수에 맞춰 생성)
        num_initial_box_labels = min(len(initial_box_data.points), len(config.BOX_CORNERS_LABELS))
        box_label_points = initial_box_data.points[:num_initial_box_labels] if num_initial_box_labels > 0 else np.empty((0,3))
        box_label_polydata = pv.PolyData(box_label_points)
        if num_initial_box_labels > 0:
            plotter.add_point_labels(box_label_polydata, config.BOX_CORNERS_LABELS[:num_initial_box_labels],
                                     point_size=0, font_size=12, text_color='navy', show_points=False, name="box_labels")
    else: # 박스 데이터가 없는 경우
        box_mesh_actor = None
        box_label_polydata = pv.PolyData(np.empty((0,3))) # 빈 PolyData

    # Marker
    if n_frames_marker > 0:
        initial_marker_data = pv.read(marker_vtps[0])
        marker_mesh_actor = plotter.add_mesh(initial_marker_data, color="red", render_points_as_spheres=True, point_size=16, name="marker_actor")

        num_initial_marker_labels = min(len(initial_marker_data.points), len(config.MARKER_LABELS))
        marker_label_points = initial_marker_data.points[:num_initial_marker_labels] if num_initial_marker_labels > 0 else np.empty((0,3))
        marker_label_polydata = pv.PolyData(marker_label_points)
        if num_initial_marker_labels > 0:
            plotter.add_point_labels(marker_label_polydata, config.MARKER_LABELS[:num_initial_marker_labels],
                                     point_size=0, font_size=10, text_color='maroon', show_points=False, name="marker_labels")
    else: # 마커 데이터가 없는 경우
        marker_mesh_actor = None
        marker_label_polydata = pv.PolyData(np.empty((0,3))) # 빈 PolyData

    # Ground
    ground = pv.Cube(center=config.GROUND_CENTER, x_length=config.GROUND_SIZE[0],
                     y_length=config.GROUND_SIZE[1], z_length=0.1)
    plotter.add_mesh(pv.PolyData(ground.points, faces=ground.faces), color=config.GROUND_COLOR, opacity=0.25, name='ground_mesh')
    ground_label_pos = [config.GROUND_CENTER[0], config.GROUND_CENTER[1], config.GROUND_CENTER[2] + 0.1]
    plotter.add_point_labels([ground_label_pos], ["GROUND"], point_size=0, font_size=16, text_color='gray', show_points=False, name='ground_label')

    frame_idx = [0]
    def update_callback(idx_val):
        # update_frame에 필요한 모든 액터와 PolyData 전달
        update_frame(idx_val, box_mesh_actor, marker_mesh_actor,
                     box_label_polydata, marker_label_polydata,
                     plotter, box_vtps, marker_vtps, n_frames_ui) # n_frames_ui는 제목 표시용

    plotter.add_key_event("1", lambda: plotter.view_xy())
    plotter.add_key_event("2", lambda: plotter.view_yz())
    plotter.add_key_event("3", lambda: plotter.view_zx())
    plotter.add_key_event("m", lambda: next_frame(frame_idx, n_frames_ui, update_callback)) # n_frames_ui 사용
    plotter.add_key_event("n", lambda: prev_frame(frame_idx, update_callback))
    plotter.add_key_event("q", plotter.close)

    if (n_frames_box > 0 and box_mesh_actor) or (n_frames_marker > 0 and marker_mesh_actor) : # 표시할 데이터가 있을 경우에만 초기 업데이트
        update_callback(0)
    else: # 표시할 데이터가 전혀 없을 경우
        plotter.title = "No data to display"
        plotter.render()

    print("[INFO] Starting PyVista Plotter. Press 'm'/'n' for frames, '1'/'2'/'3' for views, 'q' to quit.")
    plotter.show(title="Box+Marker Time Series Visualization (Label Update Test v2)", window_size=[1200, 900])

if __name__ == '__main__':
    if not hasattr(config, 'PVD_PATH'):
        print("[WARN] config.py not properly loaded or PVD_PATH not set. Using default dummy values.")
        class DummyConfig:
            PVD_PATH = "animation.pvd"
            DATA_DIR = "."
            FPS = 30
            GROUND_CENTER = [0, 0, -0.5]
            GROUND_SIZE = [15, 15]
            GROUND_COLOR = "lightgrey"
            BOX_CORNERS_LABELS = [f"Box{i+1}" for i in range(8)]
            MARKER_LABELS = [f"Mark{i+1}" for i in range(8)]
        config = DummyConfig()
        print(f"[INFO] Please ensure '{config.PVD_PATH}' exists or VTP files are in '{config.DATA_DIR}'.")
        # 간단한 더미 VTP 파일 생성 (테스트용, 실제 데이터로 대체 필요)
        if not os.path.exists(config.PVD_PATH) and not glob.glob(os.path.join(config.DATA_DIR,"box_*.vtp")):
            print("[INFO] Creating dummy VTP files for testing (box_0.vtp, marker_0.vtp).")
            sphere = pv.Sphere(center=(0,0,0))
            sphere.save(os.path.join(config.DATA_DIR,"box_0.vtp"))
            points = pv.PolyData(np.array([[0.5,0,0],[0,0.5,0]]))
            points.save(os.path.join(config.DATA_DIR,"marker_0.vtp"))
            # 더미 PVD 파일 생성
            pvd_content = f"""<?xml version="1.0"?>
<VTKFile type="Collection" version="0.1" byte_order="LittleEndian">
<Collection>
<DataSet timestep="0" group="" part="0" file="{os.path.join(config.DATA_DIR,'box_0.vtp')}"/>
<DataSet timestep="0" group="" part="0" file="{os.path.join(config.DATA_DIR,'marker_0.vtp')}"/>
</Collection>
</VTKFile>"""
            with open(config.PVD_PATH, "w") as f:
                f.write(pvd_content)
    main()
