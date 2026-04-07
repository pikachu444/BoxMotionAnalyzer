import mujoco
import mujoco.viewer
import numpy as np
import time

class MuJoCoEngine:
    """
    Core MuJoCo simulation engine.
    Builds the model dynamically, runs the simulation, and extracts the 8 corner points.
    Supports interactive visualization using mujoco.viewer.
    """
    def __init__(self, size=(1000, 1000, 1000), mass=100.0, friction=0.7, elasticity=0.2, com_offset=(0.0, 0.0, 0.0)):
        # Convert dimensions from mm to meters for MuJoCo (half extents)
        self.size_m = [s / 2000.0 for s in size]
        self.mass = mass
        self.friction = friction
        self.elasticity = elasticity
        self.com_offset = [com / 1000.0 for com in com_offset] # Convert mm to m

        # Will be set in set_initial_state
        self.init_pos = [0, 0, 1.0] # 1.0m height default
        self.init_quat = [1, 0, 0, 0] # w, x, y, z

        self.model = None
        self.data = None

    def set_initial_state(self, height_mm, quat_wxyz):
        """
        Set initial drop height and orientation.
        Calculates the exact Z position so the lowest point of the box
        is exactly 'height_mm' above the floor, not the center.
        """
        self.init_quat = quat_wxyz

        # Scipy uses [x,y,z,w], but we stored [w,x,y,z] in scenarios.py
        # Convert to scipy format to calculate corner rotation
        scipy_quat = [quat_wxyz[1], quat_wxyz[2], quat_wxyz[3], quat_wxyz[0]]

        from scipy.spatial.transform import Rotation as R
        r = R.from_quat(scipy_quat)

        sx, sy, sz = self.size_m
        corners = np.array([
            [-sx, -sy, -sz],
            [ sx, -sy, -sz],
            [ sx,  sy, -sz],
            [-sx,  sy, -sz],
            [-sx, -sy,  sz],
            [ sx, -sy,  sz],
            [ sx,  sy,  sz],
            [-sx,  sy,  sz]
        ])

        rotated_corners = r.apply(corners)
        lowest_z_offset = np.min(rotated_corners[:, 2])

        # The center Z must be: desired_height - lowest_z_offset (which is negative)
        center_z = (height_mm / 1000.0) - lowest_z_offset
        self.init_pos = [0, 0, center_z]

    def _generate_xml(self):
        """
        Generates MuJoCo XML configuration dynamically.
        """
        # MuJoCo uses half-sizes for boxes
        sx, sy, sz = self.size_m

        # Box moment of inertia approximation
        ixx = (1/12) * self.mass * ((2*sy)**2 + (2*sz)**2)
        iyy = (1/12) * self.mass * ((2*sx)**2 + (2*sz)**2)
        izz = (1/12) * self.mass * ((2*sx)**2 + (2*sy)**2)

        # We increase solver impedance (solimp) slightly to make the box stiffer,
        # and adjust solref based on elasticity to control the bounce.
        solref_timeconst = 0.02
        solref_dampratio = max(0.01, 1.0 - self.elasticity) # Lower damp ratio = more bouncy

        # We increase solver impedance (solimp) slightly to make the box stiffer,
        # and adjust solref based on elasticity to control the bounce.
        solref_timeconst = 0.02
        solref_dampratio = max(0.01, 1.0 - self.elasticity) # Lower damp ratio = more bouncy

        # To simulate a box tumbling and rolling (instead of instantly stopping due to perfect face-to-face contact),
        # we activate condim="4" for torsional friction, and add small rolling/torsional friction values.
        # We also add a small margin to the box geometry so it acts slightly rounded, aiding tumbling.

        xml = f"""
        <mujoco>
            <option timestep="0.002" gravity="0 0 -9.81"/>
            <worldbody>
                <light pos="0 0 5" dir="0 0 -1" diffuse="1 1 1"/>
                <!-- solref is "timeconst dampratio" -->
                <geom name="floor" type="plane" size="5 5 0.1" rgba="0.8 0.9 0.8 1" condim="4"
                      friction="{self.friction} 0.01 0.005" solref="{solref_timeconst} {solref_dampratio}"/>

                <body name="box" pos="{self.init_pos[0]} {self.init_pos[1]} {self.init_pos[2]}" quat="{self.init_quat[0]} {self.init_quat[1]} {self.init_quat[2]} {self.init_quat[3]}">
                    <freejoint/>
                    <inertial pos="{self.com_offset[0]} {self.com_offset[1]} {self.com_offset[2]}" mass="{self.mass}" diaginertia="{ixx} {iyy} {izz}"/>
                    <geom name="box_geom" type="box" size="{sx} {sy} {sz}" rgba="0.8 0.6 0.4 1" margin="0.005"
                          condim="4" friction="{self.friction} 0.01 0.005"
                          solref="{solref_timeconst} {solref_dampratio}" solimp="0.9 0.95 0.001 0.5 2"/>
                    <!-- Define corners as sites for easy tracking -->
                    <site name="C1" pos="{-sx} {-sy} {-sz}" size="0.01" rgba="1 0 0 1"/>
                    <site name="C2" pos="{sx} {-sy} {-sz}" size="0.01" rgba="1 0 0 1"/>
                    <site name="C3" pos="{sx} {sy} {-sz}" size="0.01" rgba="1 0 0 1"/>
                    <site name="C4" pos="{-sx} {sy} {-sz}" size="0.01" rgba="1 0 0 1"/>
                    <site name="C5" pos="{-sx} {-sy} {sz}" size="0.01" rgba="1 0 0 1"/>
                    <site name="C6" pos="{sx} {-sy} {sz}" size="0.01" rgba="1 0 0 1"/>
                    <site name="C7" pos="{sx} {sy} {sz}" size="0.01" rgba="1 0 0 1"/>
                    <site name="C8" pos="{-sx} {sy} {sz}" size="0.01" rgba="1 0 0 1"/>
                </body>
            </worldbody>
        </mujoco>
        """
        return xml

    def build(self):
        """
        Build MuJoCo model and data structures.
        """
        xml_string = self._generate_xml()
        self.model = mujoco.MjModel.from_xml_string(xml_string)
        self.data = mujoco.MjData(self.model)
        mujoco.mj_forward(self.model, self.data)

    def run_simulation(self, target_fps=120, stop_condition_time=3.0, velocity_threshold=0.01, show_viewer=False):
        """
        Runs the simulation and collects corner positions over time.
        Returns a list of dicts with time and corner positions (in mm).
        If show_viewer is True, displays the mujoco 3D viewer and keeps it open until closed by user.
        """
        if self.model is None or self.data is None:
            self.build()

        dt = 1.0 / target_fps
        sim_dt = self.model.opt.timestep
        steps_per_frame = max(1, int(dt / sim_dt))

        history = []

        current_time = 0.0
        consecutive_rest_frames = 0
        simulation_active = True

        if show_viewer:
            # Run with viewer
            with mujoco.viewer.launch_passive(self.model, self.data) as viewer:
                viewer.cam.distance = 5.0
                viewer.cam.elevation = -20
                viewer.cam.azimuth = 90

                # Main viewer loop
                while viewer.is_running():
                    step_start = time.time()

                    if simulation_active and current_time < stop_condition_time:
                        self._record_frame(history, current_time)

                        # Step simulation
                        for _ in range(steps_per_frame):
                            mujoco.mj_step(self.model, self.data)

                        current_time += dt

                        if self._check_stop_condition(velocity_threshold, current_time):
                            consecutive_rest_frames += 1
                        else:
                            consecutive_rest_frames = 0

                        if consecutive_rest_frames > target_fps * 1.5: # Require 1.5s of rest to ensure it has fully settled
                            simulation_active = False

                    viewer.sync()

                    # Sync with real time for visualization
                    time_until_next_step = dt - (time.time() - step_start)
                    if time_until_next_step > 0:
                        time.sleep(time_until_next_step)
        else:
            # Run headless
            while current_time < stop_condition_time:
                self._record_frame(history, current_time)

                # Step simulation
                for _ in range(steps_per_frame):
                    mujoco.mj_step(self.model, self.data)

                current_time += dt

                if self._check_stop_condition(velocity_threshold, current_time):
                    consecutive_rest_frames += 1
                else:
                    consecutive_rest_frames = 0

                if consecutive_rest_frames > target_fps * 0.5:
                    break

        return history

    def _record_frame(self, history, current_time):
        frame_data = {'time': current_time}

        # Record Center of Mass (Body Position)
        body_id = mujoco.mj_name2id(self.model, mujoco.mjtObj.mjOBJ_BODY, "box")
        body_pos = self.data.xpos[body_id] * 1000.0
        frame_data['Center'] = body_pos.copy()

        for i in range(1, 9):
            site_id = mujoco.mj_name2id(self.model, mujoco.mjtObj.mjOBJ_SITE, f"C{i}")
            # Convert back to mm
            pos = self.data.site_xpos[site_id] * 1000.0
            frame_data[f'C{i}'] = pos.copy()
        history.append(frame_data)

    def _check_stop_condition(self, velocity_threshold, current_time):
        # Increased initial grace period to allow for falling
        if current_time < 0.5:
            return False
        vel = np.linalg.norm(self.data.qvel[:3]) # linear velocity
        ang_vel = np.linalg.norm(self.data.qvel[3:6]) # angular velocity
        return vel < velocity_threshold and ang_vel < velocity_threshold
