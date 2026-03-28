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
    def __init__(self, size=(1000, 1000, 1000), mass=100.0, friction=0.7, elasticity=0.2):
        # Convert dimensions from mm to meters for MuJoCo (half extents)
        self.size_m = [s / 2000.0 for s in size]
        self.mass = mass
        self.friction = friction
        self.elasticity = elasticity

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

        xml = f"""
        <mujoco>
            <option timestep="0.002" gravity="0 0 -9.81"/>
            <worldbody>
                <light pos="0 0 5" dir="0 0 -1" diffuse="1 1 1"/>
                <geom name="floor" type="plane" size="5 5 0.1" rgba="0.8 0.9 0.8 1" condim="3" friction="{self.friction} 0.005 0.0001" solref="0.02 1"/>

                <body name="box" pos="{self.init_pos[0]} {self.init_pos[1]} {self.init_pos[2]}" quat="{self.init_quat[0]} {self.init_quat[1]} {self.init_quat[2]} {self.init_quat[3]}">
                    <freejoint/>
                    <geom name="box_geom" type="box" size="{sx} {sy} {sz}" mass="{self.mass}" rgba="0.8 0.6 0.4 1"
                          condim="3" friction="{self.friction} 0.005 0.0001" solref="0.02 1" solimp="0.9 0.95 0.001 0.5 2"/>
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
        If show_viewer is True, displays the mujoco 3D viewer.
        """
        if self.model is None or self.data is None:
            self.build()

        dt = 1.0 / target_fps
        sim_dt = self.model.opt.timestep
        steps_per_frame = max(1, int(dt / sim_dt))

        history = []

        current_time = 0.0
        consecutive_rest_frames = 0

        if show_viewer:
            # Run with viewer
            with mujoco.viewer.launch_passive(self.model, self.data) as viewer:
                viewer.cam.distance = 5.0
                viewer.cam.elevation = -20
                viewer.cam.azimuth = 90

                while current_time < stop_condition_time and viewer.is_running():
                    step_start = time.time()

                    self._record_frame(history, current_time)

                    # Step simulation
                    for _ in range(steps_per_frame):
                        mujoco.mj_step(self.model, self.data)

                    viewer.sync()
                    current_time += dt

                    # Sync with real time for visualization
                    time_until_next_step = dt - (time.time() - step_start)
                    if time_until_next_step > 0:
                        time.sleep(time_until_next_step)

                    if self._check_stop_condition(velocity_threshold, current_time):
                        consecutive_rest_frames += 1
                    else:
                        consecutive_rest_frames = 0

                    if consecutive_rest_frames > target_fps * 0.5:
                        # Hold viewer for a moment before closing
                        time.sleep(1.0)
                        break
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
        if current_time < 0.2:
            return False
        vel = np.linalg.norm(self.data.qvel[:3]) # linear velocity
        ang_vel = np.linalg.norm(self.data.qvel[3:6]) # angular velocity
        return vel < velocity_threshold and ang_vel < velocity_threshold
