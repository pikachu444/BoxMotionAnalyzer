import config  # config.py 파일이 같은 디렉토리에 있다고 가정합니다.
import pyvista as pv
import numpy as np
import glob
import os
import sys # 프로그램 종료를 위해 추가
from collections.abc import Callable # Python 3.9+ 에서 Callable 임포트
# from typing import Any # Any는 더 이상 필요하지 않음 (Callable로 대체)

# =============================================
# config.py 예시 (실제 프로젝트에서는 별도 파일로 관리)
# class Config:
#     PVD_PATH: str = "data/animation.pvd"
#     DATA_DIR: str = "data"
#     FPS: int = 30
#     GROUND_CENTER: list[float] = [0, 0, -1]
#     GROUND_SIZE: list[float] = [10, 10]
#     GROUND_COLOR: str = "lightgreen"
#     BOX_CORNERS_LABELS: list[str] = ["V1", "V2", "V3", "V4", "V5", "V6", "V7", "V8"]
#     MARKER_LABELS: list[str] = ["M1", "M2", "M3", "M4", "M5", "M6", "M7", "M8"]
# config = Config()
# =============================================

def update_polydata_points(polydata_object: pv.PolyData, new_points_array: np.ndarray) -> None:
    """
    PolyData 객체의 점들을 안전하게 업데이트하고 Modified를 호출합니다.
    이 함수는 polydata_object의 기존 점 개수를 변경하지 않고, 좌표만 업데이트합니다.
    """
    if not isinstance(polydata_object, pv.PolyData):
        return
    if not isinstance(new_points_array, np.ndarray):
        if polydata_object.n_points > 0:
            for i in range(polydata_object.n_points):
                polydata_object.points[i, :] = [0.0, 0.0, -1.0e6]
            polydata_object.Modified()
        return

    num_target_points: int = polydata_object.n_points

    valid_source_points_array: np.ndarray
    if new_points_array.ndim == 2 and new_points_array.shape[1] == 3:
        valid_source_points_array = new_points_array
    elif new_points_array.size == 0:
        valid_source_points_array = np.empty((0,3), dtype=float)
    else:
        if num_target_points > 0:
            for i in range(num_target_points):
                polydata_object.points[i, :] = [0.0, 0.0, -1.0e6]
            polydata_object.Modified()
        return

    num_source_points: int = valid_source_points_array.shape[0]

    if num_target_points == 0:
        return

    points_to_copy: int = min(num_target_points, num_source_points)

    if points_to_copy > 0:
        polydata_object.points[:points_to_copy, :] = valid_source_points_array[:points_to_copy, :]

    if points_to_copy < num_target_points:
        for i in range(points_to_copy, num_target_points):
            polydata_object.points[i, :] = [0.0, 0.0, -1.0e6]

    if num_source_points == 0 and num_target_points > 0:
        for i in range(num_target_points):
            polydata_object.points[i, :] = [0.0, 0.0, -1.0e6]

    polydata_object.Modified()


def load_pvd_vtps() -> tuple[list[str], list[str]]:
    pvd_path: str = config.PVD_PATH
    box_vtps: list[str] = []
    marker_vtps: list[str] = []

    if os.path.exists(pvd_path):
        try:
            with open(pvd_path, "r", encoding="utf-8") as f:
                lines: list[str] = f.readlines()
            vtp_files: list[str] = []
            pvd_dir: str = os.path.dirname(pvd_path)
            for line in lines:
                if ".vtp" in line or ".vtk" in line:
                    try:
                        vtp_file_relative: str = line.split('file="')[1].split('"')[0]
                        vtp_file_full_path: str = os.path.normpath(os.path.join(pvd_dir, vtp_file_relative))
                        if os.path.exists(vtp_file_full_path):
                            vtp_files.append(vtp_file_full_path)
                        else:
                            print(f"[WARN] VTP file not found (referenced in PVD): {vtp_file_full_path}")
                    except IndexError:
                        print(f"[WARN] Malformed VTP entry in PVD file: {line.strip()}")

            for f_path in vtp_files:
                f_name: str = os.path.basename(f_path).lower()
                if "box" in f_name:
                    box_vtps.append(f_path)
                elif "marker" in f_name:
                    marker_vtps.append(f_path)
                else:
                    print(f"[WARN] Unknown VTP file type (expected 'box' or 'marker' in name): {f_path}")
            box_vtps.sort()
            marker_vtps.sort()

            if not box_vtps and not marker_vtps and vtp_files:
                 print(f"[WARN] PVD parsed, but no files were categorized as box or marker. Check VTP filenames in PVD.")
            if not box_vtps or not marker_vtps :
                 glob_box_vtps: list[str] = sorted(glob.glob(os.path.join(config.DATA_DIR, "box_*.vtp")))
                 glob_marker_vtps: list[str] = sorted(glob.glob(os.path.join(config.DATA_DIR, "marker_*.vtp")))
                 if glob_box_vtps and not box_vtps : box_vtps = glob_box_vtps
                 if glob_marker_vtps and not marker_vtps : marker_vtps = glob_marker_vtps
        except Exception as e:
            print(f"[ERROR] Failed to parse PVD file {pvd_path}: {e}. Falling back to glob.")
            box_vtps = sorted(glob.glob(os.path.join(config.DATA_DIR, "box_*.vtp")))
            marker_vtps = sorted(glob.glob(os.path.join(config.DATA_DIR, "marker_*.vtp")))
    else:
        print(f"[INFO] PVD file not found: {pvd_path}. Searching in {config.DATA_DIR} using glob.")
        box_vtps = sorted(glob.glob(os.path.join(config.DATA_DIR, "box_*.vtp")))
        marker_vtps = sorted(glob.glob(os.path.join(config.DATA_DIR, "marker_*.vtp")))

    if not box_vtps and not marker_vtps:
        print("[ERROR] No VTP files found for visualization. Check DATA_DIR and PVD_PATH.")
    elif not box_vtps:
        print("[WARN] No box VTP files found.")
    elif not marker_vtps:
        print("[WARN] No marker VTP files found.")

    return box_vtps, marker_vtps

def update_frame(idx: int, box_mesh_actor: pv.Actor | None, marker_mesh_actor: pv.Actor | None,
                 box_label_polydata: pv.PolyData | None, marker_label_polydata: pv.PolyData | None,
                 plotter: pv.Plotter, box_vtps: list[str], marker_vtps: list[str], n_frames: int) -> None:
    """
    애니메이션의 각 프레임마다 호출되어 메시와 라벨의 위치를 업데이트합니다.
    """
    try:
        if box_mesh_actor:
            if idx < len(box_vtps):
                new_box_data: pv.PolyData = pv.read(box_vtps[idx])
                box_mesh_actor.mapper.dataset = new_box_data
                if box_label_polydata is not None:
                    update_polydata_points(box_label_polydata, new_box_data.points)
            else:
                if box_label_polydata is not None:
                    update_polydata_points(box_label_polydata, np.empty((0,3)))

        if marker_mesh_actor:
            if idx < len(marker_vtps):
                new_marker_data: pv.PolyData = pv.read(marker_vtps[idx])
                marker_mesh_actor.mapper.dataset = new_marker_data
                if marker_label_polydata is not None:
                    update_polydata_points(marker_label_polydata, new_marker_data.points)
            else:
                if marker_label_polydata is not None:
                    update_polydata_points(marker_label_polydata, np.empty((0,3)))

        plotter.title = f"Frame {idx + 1}/{n_frames}"
        plotter.render()

    except Exception as e:
        print(f"[ERROR] Failed to update frame {idx}: {e}")
        import traceback
        traceback.print_exc()

def next_frame(frame_idx: list[int], n_frames: int, update_frame_fn: Callable[[int], None]) -> None:
    if frame_idx[0] < n_frames - 1:
        frame_idx[0] += 1
        update_frame_fn(frame_idx[0])
    else:
        print("[INFO] Reached end of frames.")

def prev_frame(frame_idx: list[int], update_frame_fn: Callable[[int], None]) -> None:
    if frame_idx[0] > 0:
        frame_idx[0] -= 1
        update_frame_fn(frame_idx[0])
    else:
        print("[INFO] Reached start of frames.")

def main() -> None:
    box_vtps: list[str]
    marker_vtps: list[str]
    box_vtps, marker_vtps = load_pvd_vtps()

    n_frames_box: int = len(box_vtps)
    n_frames_marker: int = len(marker_vtps)

    if n_frames_box == 0 and n_frames_marker == 0:
        print("[ERROR] No VTP files loaded. Exiting.")
        return

    n_frames_ui: int = max(n_frames_box, n_frames_marker)
    if n_frames_box != n_frames_marker:
        print(f"[WARN] Mismatch: {n_frames_box} box VTPs, {n_frames_marker} marker VTPs. Animation will use available frames for each.")

    plotter: pv.Plotter = pv.Plotter(notebook=False)
    plotter.set_background("white")

    box_mesh_actor: pv.Actor | None = None
    box_label_polydata: pv.PolyData | None = None
    marker_mesh_actor: pv.Actor | None = None
    marker_label_polydata: pv.PolyData | None = None

    num_box_labels_defined: int = len(config.BOX_CORNERS_LABELS)
    initial_box_label_coords = np.full((num_box_labels_defined, 3), [0.0, 0.0, -1.0e6])

    if n_frames_box > 0:
        initial_box_data: pv.PolyData = pv.read(box_vtps[0])
        box_mesh_actor = plotter.add_mesh(initial_box_data, color="lightblue", show_edges=True, opacity=0.5, name="box_actor")

        num_points_for_initial_box_labels: int = min(len(initial_box_data.points), num_box_labels_defined)
        if num_points_for_initial_box_labels > 0:
            initial_box_label_coords[:num_points_for_initial_box_labels] = initial_box_data.points[:num_points_for_initial_box_labels]

    box_label_polydata = pv.PolyData(initial_box_label_coords)
    if num_box_labels_defined > 0:
        plotter.add_point_labels(box_label_polydata, config.BOX_CORNERS_LABELS,
                                 point_size=0, font_size=12, text_color='navy',
                                 show_points=False, name="box_labels")

    num_marker_labels_defined: int = len(config.MARKER_LABELS)
    initial_marker_label_coords = np.full((num_marker_labels_defined, 3), [0.0, 0.0, -1.0e6])

    if n_frames_marker > 0:
        initial_marker_data: pv.PolyData = pv.read(marker_vtps[0])
        marker_mesh_actor = plotter.add_mesh(initial_marker_data, color="red", render_points_as_spheres=True, point_size=16, name="marker_actor")

        num_points_for_initial_marker_labels: int = min(len(initial_marker_data.points), num_marker_labels_defined)
        if num_points_for_initial_marker_labels > 0:
            initial_marker_label_coords[:num_points_for_initial_marker_labels] = initial_marker_data.points[:num_points_for_initial_marker_labels]

    marker_label_polydata = pv.PolyData(initial_marker_label_coords)
    if num_marker_labels_defined > 0:
        plotter.add_point_labels(marker_label_polydata, config.MARKER_LABELS,
                                 point_size=0, font_size=10, text_color='maroon',
                                 show_points=False, name="marker_labels")

    ground_center_coords: list[float] = config.GROUND_CENTER
    ground_size_dims: list[float] = config.GROUND_SIZE
    ground_color_str: str = config.GROUND_COLOR

    ground: pv.Cube = pv.Cube(center=ground_center_coords, x_length=ground_size_dims[0],
                               y_length=ground_size_dims[1], z_length=0.1)
    plotter.add_mesh(pv.PolyData(ground.points, faces=ground.faces), color=ground_color_str, opacity=0.25, name='ground_mesh')
    ground_label_pos: list[float] = [ground_center_coords[0], ground_center_coords[1], ground_center_coords[2] + 0.1]
    plotter.add_point_labels([ground_label_pos], ["GROUND"], point_size=0, font_size=16, text_color='gray', show_points=False, name='ground_label')

    frame_idx: list[int] = [0]
    def update_callback(idx_val: int) -> None:
        update_frame(idx_val, box_mesh_actor, marker_mesh_actor,
                     box_label_polydata, marker_label_polydata,
                     plotter, box_vtps, marker_vtps, n_frames_ui)

    plotter.add_key_event("1", lambda: plotter.view_xy())
    plotter.add_key_event("2", lambda: plotter.view_yz())
    plotter.add_key_event("3", lambda: plotter.view_zx())
    plotter.add_key_event("m", lambda: next_frame(frame_idx, n_frames_ui, update_callback))
    plotter.add_key_event("n", lambda: prev_frame(frame_idx, update_callback))

    # 'q' 키를 눌렀을 때 프로그램이 완전히 종료되도록 수정
    def exit_app():
        # plotter.close() # PyVista 창을 먼저 닫는 것이 좋을 수 있으나, sys.exit()가 강제 종료하므로 필수는 아님
        # print("[INFO] Exiting application...")
        sys.exit() # 프로그램 종료
    plotter.add_key_event("q", exit_app)


    if n_frames_ui > 0 :
        update_callback(0)
    else:
        plotter.title = "No data to display"
        plotter.render()

    print("[INFO] Starting PyVista Plotter. Press 'm'/'n' for frames, '1'/'2'/'3' for views, 'q' to quit.")
    plotter.show(title="Main Visualizer v1 (Final Touches)", window_size=[1200, 900])

if __name__ == '__main__':
    if not hasattr(config, 'PVD_PATH') or not hasattr(config, 'DATA_DIR'):
        print("[WARN] config.py not properly loaded or PVD_PATH/DATA_DIR not set. Using default dummy values.")
        class DummyConfig:
            PVD_PATH: str = "animation.pvd"
            DATA_DIR: str = "."
            FPS: int = 30
            GROUND_CENTER: list[float] = [0, 0, -0.5]
            GROUND_SIZE: list[float] = [15, 15]
            GROUND_COLOR: str = "lightgrey"
            BOX_CORNERS_LABELS: list[str] = [f"Box{i+1}" for i in range(2)]
            MARKER_LABELS: list[str] = [f"Mark{i+1}" for i in range(3)]
        config = DummyConfig() # type: ignore
        print(f"[INFO] Please ensure '{config.PVD_PATH}' exists or VTP files are in '{config.DATA_DIR}'.")

        os.makedirs(config.DATA_DIR, exist_ok=True)

        dummy_box_path = os.path.join(config.DATA_DIR,"box_0.vtp")
        dummy_marker_path = os.path.join(config.DATA_DIR,"marker_0.vtp")

        if not os.path.exists(config.PVD_PATH) and (not os.path.exists(dummy_box_path) or not os.path.exists(dummy_marker_path)):
            print(f"[INFO] Creating dummy VTP files in '{config.DATA_DIR}' for testing (box_0.vtp, marker_0.vtp).")

            box_coords = np.array([[0,1,0], [0.2,1,0]])
            sphere: pv.PolyData = pv.PolyData(box_coords)
            sphere.save(dummy_box_path)

            marker_coords: np.ndarray = np.array([[0.5,0,0],[0,0.5,0], [0.5,0.5,0]])
            markers: pv.PolyData = pv.PolyData(marker_coords)
            markers.save(dummy_marker_path)

            pvd_content: str = f"""<?xml version="1.0"?>
<VTKFile type="Collection" version="0.1" byte_order="LittleEndian">
<Collection>
<DataSet timestep="0" group="" part="0" file="{os.path.basename(dummy_box_path)}"/>
<DataSet timestep="0" group="" part="0" file="{os.path.basename(dummy_marker_path)}"/>
</Collection>
</VTKFile>"""
            with open(config.PVD_PATH, "w") as f:
                f.write(pvd_content)
            print(f"[INFO] Dummy PVD file '{config.PVD_PATH}' created. It references VTP files in '{config.DATA_DIR}'.")
    main()
