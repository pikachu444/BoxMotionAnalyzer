import numpy as np
import matplotlib.pyplot as plt
from src.simulation.engine.mujoco_engine import MuJoCoEngine
from src.simulation.scenarios import Scenarios
from src.simulation.data_exporter import DataExporter

def plot_velocity_validation():
    print("Running Simulation for Velocity Validation (Edge Drop)...")
    # TV Size & Mass (Matching Legacy BOX_DIMS: X=Width, Y=Height, Z=Depth)
    size = (1578/2, 930/2, 142/2) # half-extents
    mass = 25.0
    com_offset = (0, -200, 0) # Offset along local Y (Height) to induce tumbling

    engine = MuJoCoEngine(size=size, mass=mass, friction=0.5, elasticity=0.15, com_offset=com_offset)

    # Run Edge Drop
    height = 500
    # Use Scenarios.get_orientation for Edge_3_4
    quat = Scenarios.get_orientation("Edge_3_4 (Bottom-Right)", size)
    engine.set_initial_state(height, quat)
    history = engine.run_simulation(show_viewer=False, stop_condition_time=1.5)

    # Calculate Velocity using DataExporter's logic
    exporter = DataExporter(history)
    exporter.calculate_derivatives()

    times = []
    com_vz = []
    c1_vz = []
    c2_vz = []
    c5_vz = []
    c6_vz = []

    for frame in exporter.history:
        times.append(frame['time'])
        com_vz.append(frame['Center_V'][2])
        # Bottom corners based on CORNER_NAME_MAP: C1(LBR), C2(RBR), C5(LBF), C6(RBF)
        c1_vz.append(frame['C1_V'][2])
        c2_vz.append(frame['C2_V'][2])
        c5_vz.append(frame['C5_V'][2])
        c6_vz.append(frame['C6_V'][2])

    plt.figure(figsize=(12, 6))
    plt.plot(times, com_vz, label='CoM (Center of Mass)', linewidth=3, color='black')
    plt.plot(times, c1_vz, label='C1 (Left-Bottom-Rear)', linestyle='--')
    plt.plot(times, c2_vz, label='C2 (Right-Bottom-Rear)', linestyle=':')
    plt.plot(times, c5_vz, label='C5 (Left-Bottom-Front)', linestyle='-.')
    plt.plot(times, c6_vz, label='C6 (Right-Bottom-Front)', linestyle=(0, (3, 1, 1, 1)))

    plt.axhline(0, color='black', linewidth=1)
    plt.title('Theoretical Validation: Vertical Velocities during 500mm Edge Drop (MuJoCo)')
    plt.xlabel('Time (s)')
    plt.ylabel('Vertical Velocity (mm/s)')
    plt.grid(True)
    plt.legend()

    plt.tight_layout()
    import os
    os.makedirs('docs/images', exist_ok=True)
    plt.savefig('docs/images/proposal_tv_velocity_corner.png', dpi=150)
    print("Saved velocity plot to docs/images/proposal_tv_velocity_corner.png")

if __name__ == "__main__":
    plot_velocity_validation()
