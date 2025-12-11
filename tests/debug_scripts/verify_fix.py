import pyvista as pv
import numpy as np

# Simulate the fixed logic
def _adjust_camera_up_simulated(plotter, up_axis_idx=1):
    # 1. Determine Desired World Up Vector
    if up_axis_idx == 1: # Y-Up
        desired_up = np.array([0.0, 1.0, 0.0])
        secondary_up = np.array([0.0, 0.0, 1.0]) # Fallback (Z)
    else: # Z-Up (Default)
        desired_up = np.array([0.0, 0.0, 1.0])
        secondary_up = np.array([0.0, 1.0, 0.0]) # Fallback (Y)

    # 2. Check Parallelism with View Direction
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

        # If parallel (dot product close to 1 or -1), use secondary up
        if abs(dot_product) > 0.95:
            print(f"Parallel detected! Switching to Secondary Up: {secondary_up}")
            plotter.camera.up = tuple(secondary_up)
        else:
            print(f"Using Desired Up: {desired_up}")
            plotter.camera.up = tuple(desired_up)
    else:
        plotter.camera.up = tuple(desired_up)

def test_fix():
    plotter = pv.Plotter(off_screen=True)
    plotter.add_mesh(pv.Cube(), color='blue')

    # 1. Set view to XZ (PyVista default: look along -Y)
    plotter.view_xz()

    print("--- Testing Fix for Y-Up World in XZ View ---")
    # Simulate Y-Up World (up_axis_idx=1)
    _adjust_camera_up_simulated(plotter, up_axis_idx=1)

    print(f"Final Camera Up: {plotter.camera.up}")

    # Force Render to check for warnings (should be none)
    try:
        plotter.render()
        print("Render Success!")
    except Exception as e:
        print(f"Render Failed: {e}")

if __name__ == "__main__":
    test_fix()
