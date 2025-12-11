import pyvista as pv
import numpy as np

# Simulate the fixed logic
def _adjust_camera_up_simulated(plotter, up_axis_idx=1):
    if up_axis_idx == 1: # Y-Up
        desired_up = np.array([0.0, 1.0, 0.0])
        secondary_up = np.array([0.0, 0.0, 1.0])
    else: # Z-Up
        desired_up = np.array([0.0, 0.0, 1.0])
        secondary_up = np.array([0.0, 1.0, 0.0])

    pos = np.array(plotter.camera.position)
    focal = np.array(plotter.camera.focal_point)
    view_vec = focal - pos
    norm = np.linalg.norm(view_vec)

    if norm > 0:
        view_vec = view_vec / norm
        dot_product = np.dot(view_vec, desired_up)

        print(f"View Vector: {view_vec}")
        print(f"Desired Up: {desired_up}")
        print(f"Dot Product: {dot_product}")

        if abs(dot_product) > 0.95:
            print(f"Parallel detected! Switching to Secondary Up: {secondary_up}")
            plotter.camera.up = tuple(secondary_up)
        else:
            print(f"Using Desired Up: {desired_up}")
            plotter.camera.up = tuple(desired_up)

def test_fix_iso():
    plotter = pv.Plotter(off_screen=True)
    plotter.add_mesh(pv.Cube(), color='blue')

    # 1. Set view to Isometric
    plotter.view_isometric()

    print("--- Testing Fix for Y-Up World in Isometric View ---")
    _adjust_camera_up_simulated(plotter, up_axis_idx=1)

    print(f"Final Camera Up: {plotter.camera.up}")

if __name__ == "__main__":
    test_fix_iso()
