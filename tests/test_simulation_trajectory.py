import sys
import numpy as np
import matplotlib.pyplot as plt
from src.simulation.engine.mujoco_engine import MuJoCoEngine
from src.simulation.scenarios import Scenarios
from pathlib import Path

def test_generate_trajectory_plot():
    # Set up engine (1m x 1m x 1m box, 100kg)
    engine = MuJoCoEngine(size=(1000, 1000, 1000), mass=100.0)

    # Run slightly longer to capture bouncing and rolling
    stop_time = 3.0

    # 1. Flat Drop (면 낙하) from 1m (1000mm)
    quat_flat = Scenarios.get_orientation("Flat_Bottom", (1000, 1000, 1000))
    engine.set_initial_state(1000, quat_flat)
    history_flat = engine.run_simulation(show_viewer=False, stop_condition_time=stop_time, velocity_threshold=0.005)

    # 2. Corner Drop (꼭짓점 낙하) from 1m (1000mm)
    # Re-instantiate engine to clear internal data states and prevent early stopping
    engine_corner = MuJoCoEngine(size=(1000, 1000, 1000), mass=100.0)
    quat_corner = Scenarios.get_orientation("Corner_Bottom_Front_Left", (1000, 1000, 1000))
    engine_corner.set_initial_state(1000, quat_corner)
    history_corner = engine_corner.run_simulation(show_viewer=False, stop_condition_time=stop_time, velocity_threshold=0.005)

    # Function to extract trajectory data
    def extract_metrics(history):
        times = [f['time'] for f in history]
        z_center = [f['Center'][2] for f in history]

        z_lowest = []
        z_highest = []

        for f in history:
            z_coords = [f[f'C{i}'][2] for i in range(1, 9)]
            z_lowest.append(np.min(z_coords))
            z_highest.append(np.max(z_coords))

        return times, z_center, z_lowest, z_highest

    times_f, z_center_f, z_lowest_f, z_highest_f = extract_metrics(history_flat)
    times_c, z_center_c, z_lowest_c, z_highest_c = extract_metrics(history_corner)

    # Plot
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 10), sharex=True)

    # Plot 1: Flat Drop
    ax1.plot(times_f, z_highest_f, label="Highest Corner Z", color='lightgrey')
    ax1.plot(times_f, z_center_f, label="Box Center Z", color='blue', linewidth=2)
    ax1.plot(times_f, z_lowest_f, label="Lowest Corner Z", color='red', linestyle='--')
    ax1.axhline(0, color='black', linewidth=1, linestyle='-', label="Ground")
    ax1.set_title("Flat Drop Trajectory (1000mm Height, 100kg Box)")
    ax1.set_ylabel("Height from Ground (mm)")
    ax1.grid(True)
    ax1.legend()

    # Plot 2: Corner Drop
    ax2.plot(times_c, z_highest_c, label="Highest Corner Z", color='lightgrey')
    ax2.plot(times_c, z_center_c, label="Box Center Z", color='blue', linewidth=2)
    ax2.plot(times_c, z_lowest_c, label="Lowest Corner Z", color='red', linestyle='--')
    ax2.axhline(0, color='black', linewidth=1, linestyle='-', label="Ground")
    ax2.set_title("Corner Drop Trajectory (1000mm Height, 100kg Box, ISTA-6A Tilt)")
    ax2.set_xlabel("Time (seconds)")
    ax2.set_ylabel("Height from Ground (mm)")
    ax2.grid(True)
    ax2.legend()

    plt.tight_layout()

    # Save Image
    output_path = Path("docs/proposal_simulation_trajectory.png")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()

    print(f"Plot saved to: {output_path.absolute()}")

if __name__ == "__main__":
    test_generate_trajectory_plot()
