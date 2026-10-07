"""Opt-in, evaluation-only timestep contacts on a private MuJoCo data copy."""
from copy import deepcopy
import hashlib

import mujoco
import numpy as np

from src.utils.marker_profile_identity import envelope, digest


CONTACT_CONTRACT = dict(world_frame='mujoco-z-up', local_frame='box-body-origin',
    rotation='local-to-world', time='engine-seconds', sample_stage='post-integration-forward-copy',
    units=dict(position='mm', velocity='mm/s', angular_velocity='rad/s', force='N', torque='N*m', time='s'),
    contact_point='world midpoint; box surface = midpoint + box-side-sign * distance/2 * normal',
    contact_frame='rows world axes; x normal geom1-to-geom2',
    wrench='contact frame on geom2 at world midpoint; world on box uses transpose and box-side-sign',
    approach='positive closing speed; same-state rigid point Jacobians; not an impulse')


class ContactRecorder:
    """Never forwards or writes the live engine state; absent unless requested."""
    def __init__(self, engine, source_identity):
        if not isinstance(source_identity, dict) or not source_identity:
            raise ValueError('Contact recording requires an explicit source identity.')
        self.source = deepcopy(source_identity)
        self.source_hash = digest(self.source)
        self.samples = []
        self.data = None
        self.engine = engine

    def capture(self):
        e = self.engine
        if self.samples and self.samples[-1]['time_s'] == float(e.data.time):
            return
        if self.data is None:
            self.data = mujoco.MjData(e.model)
        d, m = self.data, e.model
        mujoco.mj_copyData(d, m, e.data)
        mujoco.mj_forward(m, d)
        bid = mujoco.mj_name2id(m, mujoco.mjtObj.mjOBJ_BODY, 'box')
        box = mujoco.mj_name2id(m, mujoco.mjtObj.mjOBJ_GEOM, 'box_geom')
        floor = mujoco.mj_name2id(m, mujoco.mjtObj.mjOBJ_GEOM, 'floor')
        grip = mujoco.mj_name2id(m, mujoco.mjtObj.mjOBJ_GEOM, 'gripper_geom')
        p = d.xpos[bid].copy()
        r = d.xmat[bid].reshape(3, 3).copy()

        def velocity(point, body):
            jp = np.zeros((3, m.nv)); jr = np.zeros_like(jp)
            mujoco.mj_jac(m, d, jp, jr, point, body)
            return jp @ d.qvel, jr @ d.qvel

        v, w = velocity(p, bid)
        corners = np.array([d.site_xpos[mujoco.mj_name2id(m, mujoco.mjtObj.mjOBJ_SITE, f'C{i}')] for i in range(1, 9)])
        corners_v = np.array([velocity(point, bid)[0] for point in corners])
        contacts = []
        for i in range(d.ncon):
            c = d.contact[i]; g1, g2 = int(c.geom1), int(c.geom2)
            pair = {g1, g2}
            role = 'floor' if pair == {box, floor} else 'gripper' if grip >= 0 and pair == {box, grip} else 'other'
            basis = c.frame.reshape(3, 3).copy()
            wrench = np.zeros(6); mujoco.mj_contactForce(m, d, i, wrench)
            side = 1 if g2 == box else -1 if g1 == box else 0
            surface = c.pos + side * c.dist / 2 * basis[0]
            b1, b2 = int(m.geom_bodyid[g1]), int(m.geom_bodyid[g2])
            v1, _ = velocity(c.pos, b1); v2, _ = velocity(c.pos, b2)
            local = r.T @ (surface - p)
            contacts.append(dict(geom_ids=[g1, g2], geom_names=[mujoco.mj_id2name(m, mujoco.mjtObj.mjOBJ_GEOM, g) for g in (g1, g2)],
                body_ids=[b1, b2], body_names=[mujoco.mj_id2name(m, mujoco.mjtObj.mjOBJ_BODY, b) for b in (b1, b2)],
                role=role, box_side_sign=side, world_midpoint_mm=(c.pos * 1000).tolist(),
                box_surface_world_mm=(surface * 1000).tolist(), box_surface_local_mm=(local * 1000).tolist(),
                distance_mm=float(c.dist * 1000), inclusion_margin_mm=float(c.includemargin * 1000), frame_world_rows=basis.tolist(), wrench_contact_on_geom2=wrench.tolist(),
                force_world_on_box_n=(side * basis.T @ wrench[:3]).tolist(),
                torque_world_at_contact_on_box_nm=(side * basis.T @ wrench[3:]).tolist(),
                normal_force_n=float(wrench[0]), closing_speed_mm_s=float(-basis[0] @ (v2-v1) * 1000),
                efc_address=int(c.efc_address)))
        self.samples.append(dict(time_s=float(d.time), origin_mm=(p * 1000).tolist(), rotation=r.tolist(),
            origin_velocity_mm_s=(v * 1000).tolist(), angular_velocity_rad_s=w.tolist(),
            com_mm=(d.xipos[bid] * 1000).tolist(), corners_world_mm=(corners * 1000).tolist(),
            corners_velocity_mm_s=(corners_v * 1000).tolist(), contacts=contacts,
            box_attached=bool(d.eq_active[e.attachment]) if hasattr(e, 'attachment') else False))

    def document(self):
        e = self.engine
        if e.model is None or not self.samples:
            raise ValueError('No actual timestep contact recording.')
        return envelope('ContactRecording', contract=deepcopy(CONTACT_CONTRACT), source_identity=deepcopy(self.source),
            source_sha256=self.source_hash, model_xml_sha256=hashlib.sha256(e._generate_xml().encode()).hexdigest(),
            mujoco_version=mujoco.__version__, timestep_s=float(e.model.opt.timestep),
            box_half_extents_mm=(np.array(e.size_m) * 1000).tolist(), completion='recorded',
            origin_to_com_local_mm=(np.array(e.com_offset)*1000).tolist(),
            execution_status=getattr(e, 'sequence_evidence', {}).get('completion', 'bounded_capture'),
            samples=deepcopy(self.samples))
