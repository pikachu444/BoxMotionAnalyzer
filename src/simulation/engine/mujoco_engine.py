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
    def __init__(self, size=(1000, 1000, 1000), mass=100.0, friction=0.7, elasticity=0.2, com_offset=(0.0, 0.0, 0.0), *, contact_profile=None):
        from copy import deepcopy
        from ..initial_conditions import validate_profile
        self.contact_profile = deepcopy(validate_profile(contact_profile)) if contact_profile is not None else None
        self.initial_condition = None
        if self.contact_profile is not None:
            mass = self.contact_profile['mass_kg']
            friction = self.contact_profile['friction'][0]
            com_offset = self.contact_profile['com_offset_mm']
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
        self.contact_recorder = None

    def enable_contact_recording(self, source_identity):
        """Explicit evaluation sidecar; existing exports and defaults are intact."""
        if self.data is not None and self.data.time != 0:
            raise ValueError('Enable timestep contacts before physical execution.')
        from ..contact_recording import ContactRecorder
        self.contact_recorder = ContactRecorder(self, source_identity)

    def _capture_contacts(self):
        if self.contact_recorder is not None:
            self.contact_recorder.capture()

    def set_initial_state(self, height_mm, quat_wxyz):
        """
        Set initial drop height and orientation.
        Calculates the exact Z position so the lowest point of the box
        is exactly 'height_mm' above the floor, not the center.
        """
        if self.initial_condition is not None:
            raise ValueError('Choose either the explicit seed or legacy clearance setter.')
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

    def set_initial_condition(self, seed):
        """Apply an explicit seed only before build, never during a release."""
        from copy import deepcopy
        from ..initial_conditions import canonical_state, validate_seed
        if self.model is not None or hasattr(self, 'sequence_evidence'):
            raise ValueError('Initial conditions are pre-build single-drop inputs only.')
        self.initial_condition = deepcopy(validate_seed(seed))
        state = canonical_state(seed, np.asarray(self.com_offset) * 1000)
        self.init_pos = (state['origin_mm'] / 1000).tolist()
        self.init_quat = list(seed['quaternion_wxyz'])

    def _generate_xml(self):
        """
        Generates MuJoCo XML configuration dynamically.
        """
        # MuJoCo uses half-sizes for boxes
        sx, sy, sz = self.size_m

        # Diagonal moments of a homogeneous cuboid about its COM. A caller that
        # supplies an offset COM is explicitly assuming these same moments there.
        ixx = (1/12) * self.mass * ((2*sy)**2 + (2*sz)**2)
        iyy = (1/12) * self.mass * ((2*sx)**2 + (2*sz)**2)
        izz = (1/12) * self.mass * ((2*sx)**2 + (2*sy)**2)

        # Legacy 'elasticity' selects solref damping; it is not restitution.
        solref_timeconst = 0.02
        solref_dampratio = max(0.01, 1.0 - self.elasticity) # Lower damp ratio = more bouncy

        # condim=4 enables sliding and torsional friction, not rolling friction.
        # margin is contact activation distance; it does not round the box.

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
        if self.contact_profile is not None or self.initial_condition is not None:
            import xml.etree.ElementTree as ET
            from ..initial_conditions import moments, validate_profile
            root = ET.fromstring(xml)
            root.insert(0, ET.Element('compiler', {'alignfree': 'false'}))
            root.find('.//freejoint').set('align', 'false')
            if self.contact_profile is not None:
                p = validate_profile(self.contact_profile)
                option = root.find('option')
                option.attrib.update(timestep=str(p['solver']['timestep_s']),
                    integrator=p['solver']['integrator'], solver=p['solver']['algorithm'],
                    iterations=str(p['solver']['iterations']), tolerance=str(p['solver']['tolerance']))
                inertial = root.find('.//inertial')
                inertial.set('diaginertia', ' '.join(map(str, moments(p, np.asarray(self.size_m)*2000))))
                inertial.set('quat', ' '.join(map(str, p['inertia']['quaternion_wxyz'])))
                for geom in root.findall('.//geom'):
                    role = 'box' if geom.get('name') == 'box_geom' else 'floor'
                    geom.attrib.update(condim=str(p['condim']), friction=' '.join(map(str, p['friction'])),
                        solref=' '.join(map(str, p['solref'])), solimp=' '.join(map(str, p['solimp'])),
                        margin=str(p['margin_mm'][role]/1000), gap='0', priority='0', solmix='1')
            return ET.tostring(root, encoding='unicode')
        return xml

    def build(self):
        """
        Build MuJoCo model and data structures.
        """
        xml_string = self._generate_xml()
        self.model = mujoco.MjModel.from_xml_string(xml_string)
        self.data = mujoco.MjData(self.model)
        if self.initial_condition is not None:
            from ..initial_conditions import canonical_state
            state = canonical_state(self.initial_condition, np.asarray(self.com_offset)*1000)
            body = mujoco.mj_name2id(self.model, mujoco.mjtObj.mjOBJ_BODY, 'box')
            joint = self.model.body_jntadr[body]
            qa, va = self.model.jnt_qposadr[joint], self.model.jnt_dofadr[joint]
            self.data.qpos[qa:qa+3] = state['origin_mm']/1000
            self.data.qpos[qa+3:qa+7] = self.initial_condition['quaternion_wxyz']
            self.data.qvel[va:va+3] = state['origin_velocity_mm_s']/1000
            self.data.qvel[va+3:va+6] = state['angular_velocity_body']
        mujoco.mj_forward(self.model, self.data)
        if self.contact_profile is not None:
            from ..initial_conditions import validate_compiled
            validate_compiled(self)

    def run_simulation(self, target_fps=120, stop_condition_time=3.0, velocity_threshold=0.01, show_viewer=False,
                       *, cancelled=None, progress=None):
        """
        Runs the simulation and collects corner positions over time.
        Returns a list of dicts with time and corner positions (in mm).
        If show_viewer is True, displays the mujoco 3D viewer and keeps it open until closed by user.
        """
        if self.model is None or self.data is None:
            self.build()

        def checkpoint(current_time):
            if cancelled is not None and cancelled():
                raise InterruptedError('Simulation cancelled.')
            if progress is not None:
                progress(current_time, stop_condition_time)

        checkpoint(float(self.data.time))

        if not np.isfinite(target_fps) or target_fps <= 0:
            raise ValueError('target_fps must be positive and finite.')
        dt = 1.0 / target_fps
        sim_dt = self.model.opt.timestep
        steps_per_frame = max(1, int(dt / sim_dt))
        dt = steps_per_frame * sim_dt

        history = []

        current_time = float(self.data.time)
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
                    checkpoint(current_time)
                    step_start = time.time()

                    if simulation_active and current_time < stop_condition_time:
                        self._record_frame(history, current_time)

                        # Step simulation
                        for _ in range(steps_per_frame):
                            mujoco.mj_step(self.model, self.data)
                            self._capture_contacts()

                        current_time = float(self.data.time)

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
                checkpoint(current_time)
                self._record_frame(history, current_time)

                # Step simulation
                for _ in range(steps_per_frame):
                    mujoco.mj_step(self.model, self.data)
                    self._capture_contacts()

                current_time = float(self.data.time)

                if self._check_stop_condition(velocity_threshold, current_time):
                    consecutive_rest_frames += 1
                else:
                    consecutive_rest_frames = 0

                if consecutive_rest_frames > target_fps * 0.5:
                    break

        checkpoint(current_time)
        return history

    def record_samples(self, samples=100, substeps=4):
        """Record an exact sample count including the current state, without a viewer."""
        if not isinstance(samples, int) or samples < 1 or not isinstance(substeps, int) or substeps < 1:
            raise ValueError('samples and substeps must be positive integers.')
        if self.model is None or self.data is None:
            self.build()
        history = []
        for index in range(samples):
            if index:
                if self.contact_recorder is None:
                    mujoco.mj_step(self.model, self.data, nstep=substeps)
                else:
                    for _ in range(substeps):
                        mujoco.mj_step(self.model, self.data)
                        self._capture_contacts()
            self._record_frame(history)
        return history

    def _record_frame(self, history, current_time=None):
        # mj_step integrates state after calculating derived transforms. Refresh
        # kinematics so every recorded quantity refers to the same actual time.
        mujoco.mj_forward(self.model, self.data)
        self._capture_contacts()
        frame_data = {'time': float(self.data.time)}

        # Center remains the legacy body-origin alias. COM is explicitly separate.
        body_id = mujoco.mj_name2id(self.model, mujoco.mjtObj.mjOBJ_BODY, "box")
        body_pos = self.data.xpos[body_id] * 1000.0
        frame_data['Center'] = body_pos.copy()
        frame_data['BodyOrigin'] = body_pos.copy()
        frame_data['COM'] = (self.data.xipos[body_id] * 1000.0).copy()
        frame_data['RotationMatrix'] = self.data.xmat[body_id].reshape(3, 3).copy()
        if not history:
            # Free-joint translation is world-frame; rotation is body-frame.
            # Capture instantaneous release values once, never finite-difference
            # export aliases and never additional arrays in every sample.
            frame_data['OriginLinearVelocityWorld'] = self.data.qvel[:3].copy() * 1000.0
            frame_data['AngularVelocityBody'] = self.data.qvel[3:6].copy()
            frame_data['AngularVelocityWorld'] = frame_data['RotationMatrix'] @ frame_data['AngularVelocityBody']
        quaternion = self.data.xquat[body_id].copy()
        quaternion /= np.linalg.norm(quaternion)
        if history and np.dot(quaternion, history[-1]['QuaternionWXYZ']) < 0:
            quaternion *= -1
        frame_data['QuaternionWXYZ'] = quaternion
        frame_data['ContactCount'] = int(self.data.ncon)
        normal_force = 0.
        for contact_index in range(self.data.ncon):
            force = np.zeros(6)
            mujoco.mj_contactForce(self.model, self.data, contact_index, force)
            normal_force += float(force[0])
        frame_data['ContactNormalForceN'] = normal_force

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
