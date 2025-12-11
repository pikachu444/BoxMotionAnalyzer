import pyvista as pv
import numpy as np

# Simulate the issue
def test_view_singularity():
    plotter = pv.Plotter(off_screen=True)
    plotter.add_mesh(pv.Cube(), color='blue')

    # Emulate 'view_xz_plane' which usually looks along Y axis (negative or positive)
    # If Y is UP in world, and we look ALONG Y, we have a singularity if we set UP=Y.

    # 1. Set view to XZ (PyVista default: look along -Y, up +Z)
    plotter.view_xz()
    print(f"Default view_xz() Camera Position: {plotter.camera.position}")
    print(f"Default view_xz() Camera ViewUp: {plotter.camera.up}")
    print(f"Default view_xz() Camera FocalPoint: {plotter.camera.focal_point}")

    # 2. Force Up to Y (The Bug)
    # This should fail if the camera is looking along Y.
    # We expect position.x ~ 0, position.z ~ 0, position.y != 0
    # And ViewUp = (0, 1, 0)

    try:
        plotter.camera.up = (0, 1, 0)
        print(f"Forced UP=(0,1,0) Camera ViewUp: {plotter.camera.up}")

        # Force a render to trigger the warning/error
        plotter.render()
        print("Render successful (unexpected if singularity exists)")
    except Exception as e:
        print(f"Render failed as expected: {e}")

    # Check for parallelism
    view_vec = np.array(plotter.camera.focal_point) - np.array(plotter.camera.position)
    view_vec = view_vec / np.linalg.norm(view_vec)
    up_vec = np.array(plotter.camera.up)

    dot_prod = np.dot(view_vec, up_vec)
    print(f"Dot product of View and Up: {dot_prod} (Close to 1 or -1 means parallel)")

if __name__ == "__main__":
    test_view_singularity()
