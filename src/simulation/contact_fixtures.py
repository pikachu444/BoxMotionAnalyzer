"""Hand-specified logic controls; not dynamically calibrated packaging trials."""
from copy import deepcopy

import numpy as np

from src.utils.marker_profile_identity import envelope, digest
from .contact_recording import CONTACT_CONTRACT
from .contact_policy import frozen_protocol


def public_case(case_id):
    """Expectations are in the protocol, never inferred by running the evaluator."""
    if case_id not in [c['case_id'] for c in frozen_protocol()['expectations']]:raise ValueError(case_id)
    local=np.array([[-100,-60,-40],[100,-60,-40],[100,60,-40],[-100,60,-40],[-100,-60,40],[100,-60,40],[100,60,40],[-100,60,40]],float)
    source=dict(kind='public_hand_specified_contact_control',case_id=case_id,version='pub08-controls-v1')
    samples=[]
    for k in range(201):
        t=k*.002; clearance=1. if k<50 or (case_id=='rebound' and 80<=k<130) else 0.
        p=np.array([0.,0.,40.+clearance]); ids=[]
        if k>=50:ids=[0,1,2,3] if case_id in ('face-single','rebound') else [0]
        if case_id=='rebound' and 80<=k<130:ids=[]
        if case_id in ('corner-edge','rocking','conflict','out-of-window') and k>=90:ids=[0,1]
        if case_id=='corner-face' and k>=90:ids=[0,1,2,3]
        if case_id=='chatter' and 80<=k<82:ids=[]
        if case_id=='gripper-only':ids=[]
        closing=200. if k in (49,89,129) else 0.
        if case_id=='rocking' and k==89:closing=5.
        if case_id=='conflict' and k==89:closing=-200.
        vel=np.array([0.,0.,-closing]);contacts=[]
        for j in ids:
            point=local[j]+p; distance=float(point[2]);basis=np.array([[0,0,1],[0,1,0],[-1,0,0]],float)
            contacts.append(dict(geom_ids=[0,1],geom_names=['floor','box_geom'],body_ids=[0,1],body_names=['world','box'],
                role='floor',box_side_sign=1,world_midpoint_mm=(point-np.array([0,0,distance/2])).tolist(),
                box_surface_world_mm=point.tolist(),box_surface_local_mm=local[j].tolist(),distance_mm=distance,
                inclusion_margin_mm=0.,frame_world_rows=basis.tolist(),wrench_contact_on_geom2=[5.,0.,0.,0.,0.,0.],
                force_world_on_box_n=[0.,0.,5.],torque_world_at_contact_on_box_nm=[0.,0.,0.],
                normal_force_n=5.,closing_speed_mm_s=closing,efc_address=j*4))
        if case_id=='gripper-only' and k>=50:
            point=local[4]+p
            contacts.append(dict(geom_ids=[2,1],geom_names=['gripper_geom','box_geom'],body_ids=[2,1],body_names=['gripper','box'],
                role='gripper',box_side_sign=1,world_midpoint_mm=point.tolist(),box_surface_world_mm=point.tolist(),
                box_surface_local_mm=local[4].tolist(),distance_mm=0.,inclusion_margin_mm=0.,
                frame_world_rows=[[0,0,-1],[0,1,0],[1,0,0]],wrench_contact_on_geom2=[5.,0.,0.,0.,0.,0.],
                force_world_on_box_n=[0.,0.,-5.],torque_world_at_contact_on_box_nm=[0.,0.,0.],
                normal_force_n=5.,closing_speed_mm_s=0.,efc_address=0))
        samples.append(dict(time_s=t,origin_mm=p.tolist(),rotation=np.eye(3).tolist(),com_mm=p.tolist(),
            origin_velocity_mm_s=vel.tolist(),angular_velocity_rad_s=[0.,0.,0.],corners_world_mm=(local+p).tolist(),
            corners_velocity_mm_s=np.tile(vel,(8,1)).tolist(),contacts=contacts,box_attached=False))
    return envelope('ContactRecording',contract=deepcopy(CONTACT_CONTRACT),source_identity=source,source_sha256=digest(source),
        model_xml_sha256=digest(dict(geometry='200/120/80 mm logic control')),mujoco_version='3.6.0',timestep_s=.002,
        box_half_extents_mm=[100.,60.,40.],origin_to_com_local_mm=[0.,0.,0.],completion='recorded',execution_status='bounded_capture',samples=samples)
