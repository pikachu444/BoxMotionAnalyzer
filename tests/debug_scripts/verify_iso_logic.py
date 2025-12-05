import pyvista as pv
import numpy as np

def test_iso_logic():
    print("--- Testing Manual Isometric Logic for Y-Up ---")
    plotter = pv.Plotter(off_screen=True)
    plotter.add_mesh(pv.Cube(), color='blue')

    # Initial state
    plotter.camera.position = (10, 10, 10)
    plotter.camera.focal_point = (0, 0, 0)
    plotter.camera.up = (0, 0, 1)

    # Logic copied from VistaWidget (Y-Up branch)
    focal = np.array(plotter.camera.focal_point)
    # Using a fixed distance for test stability
    distance = np.linalg.norm(np.array(plotter.camera.position) - focal)

    direction = np.array([1.0, 1.0, 1.0])
    direction = direction / np.linalg.norm(direction)
    new_pos = focal + direction * distance

    plotter.camera.position = tuple(new_pos)
    plotter.camera.up = (0.0, 1.0, 0.0) # Set Y-Up directly

    print(f"Final Position: {plotter.camera.position}")
    print(f"Final Up: {plotter.camera.up}")

    # Verification
    expected_dir = np.array([1.0, 1.0, 1.0]) / np.linalg.norm([1.0, 1.0, 1.0])
    actual_pos_vec = np.array(plotter.camera.position) - focal
    actual_dir = actual_pos_vec / np.linalg.norm(actual_pos_vec)

    print(f"Direction Match: {np.allclose(expected_dir, actual_dir)}")
    print(f"Up Vector Match: {np.allclose(plotter.camera.up, (0, 1, 0))}")

if __name__ == "__main__":
    test_iso_logic()
