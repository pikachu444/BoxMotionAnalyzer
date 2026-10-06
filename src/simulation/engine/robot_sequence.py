"""One MuJoCo clock/state with a dynamic gripper and runtime attachment weld."""
from copy import deepcopy
import time
import xml.etree.ElementTree as ET
import mujoco
import mujoco.viewer
import numpy as np
from scipy.spatial.transform import Rotation
from src.utils.marker_profile_identity import envelope, digest
from ..robot_profiles import validate_plan, NORMALS
from .mujoco_engine import MuJoCoEngine


class SequenceFailure(RuntimeError):
    def __init__(self, message, engine):
        super().__init__(message)
        self.history = engine.history
        self.evidence = engine.sequence_evidence


class SequenceCancelled(SequenceFailure, InterruptedError):
    """Preserve the existing producer cancellation exception contract."""


def quaternion(rotation):
    return Rotation.from_matrix(rotation).as_quat()[[3,0,1,2]]


class RobotSequenceEngine(MuJoCoEngine):
    def __init__(self, config):
        from ..mode_profiles import validate_config
        validate_config(config)
        if config['mode'] != 'robot_sequence': raise ValueError('Robot runner requires robot_sequence mode.')
        self.config=deepcopy(config)
        self.plan=deepcopy(validate_plan(config['sequence_profile'].get('execution_plan'),config))
        p=config['physics_profile']
        super().__init__(size=config['size_mm'],mass=p['mass_kg'],friction=p['friction'],
            elasticity=p['contact_damping_control'],com_offset=p['com_offset_mm'])
        self.init_pos=[0.,0.,self.size_m[2]+.001]
        self.history=[];self.relative=None;self.current_phase=None;self._retract=None
        self.sequence_evidence=envelope('RobotSequenceEvidence',configuration_hash=digest(config),
            engine_builds=0,world_frame='mujoco-z-up',units=dict(position='mm',linear_velocity='mm/s',angular_velocity='rad/s',time='s'),
            stages=[],toggles=[],attempts=[],completion='not_started',unfinished_phase_ids=[])

    def set_initial_state(self, *args):
        # Existing producers call this for single drop. A robot plan starts from
        # its declared supported initial state, never from the first release.
        if self.model is not None: raise ValueError('A running sequence cannot reset its initial state.')

    def _generate_xml(self):
        root=ET.fromstring(super()._generate_xml());root.insert(0,ET.Element('compiler',{'alignfree':'false'}))
        root.find('option').set('iterations',str(self.plan['physics']['solver_iterations']))
        world=root.find('worldbody');p=self.plan['physics'];radius=p['radius_mm']/1000
        position=[0,0,self.init_pos[2]+self.size_m[2]+radius+.1]
        attrs={'pos':' '.join(map(str,position)),'quat':'1 0 0 0'}
        target=ET.SubElement(world,'body',dict(name='robot_target',mocap='true',**attrs))
        ET.SubElement(target,'site',dict(name='target_visual',size='.004',rgba='0 1 0 .5'))
        gripper=ET.SubElement(world,'body',dict(name='gripper',**attrs));ET.SubElement(gripper,'freejoint',dict(name='gripper_joint'))
        ET.SubElement(gripper,'inertial',dict(pos='0 0 0',mass=str(p['gripper_mass_kg']),diaginertia=' '.join(map(str,p['gripper_inertia_kg_m2']))))
        ET.SubElement(gripper,'geom',dict(name='gripper_geom',type='sphere',size=str(radius),mass=str(p['gripper_mass_kg']),rgba='.2 .4 .8 1'))
        for geom in root.findall('.//geom'):
            if geom.get('name') in ('box_geom','floor','gripper_geom'): geom.set('margin',str(p['contact_margin_mm']/1000))
        eq=ET.SubElement(root,'equality')
        common={'torquescale':str(p['torque_scale_m']),'solimp':'.99 .999 .001 .5 2'}
        ET.SubElement(eq,'weld',dict(name='drive',body1='robot_target',body2='gripper',solref=f"{p['drive_timeconst_s']} 1",**common))
        ET.SubElement(eq,'weld',dict(name='attachment',body1='gripper',body2='box',active='false',solref=f"{p['attach_timeconst_s']} 1",**common))
        return ET.tostring(root,encoding='unicode')

    def build(self):
        if self.model is not None: raise ValueError('Sequence engine is built only once.')
        if (self.plan!=self.config['sequence_profile']['execution_plan']
                or digest(self.config)!=self.sequence_evidence['configuration_hash']):
            raise ValueError('Execution plan differs from the captured source configuration.')
        validate_plan(self.plan,self.config)
        super().build();self.sequence_evidence['engine_builds']+=1
        self.ids={name:mujoco.mj_name2id(self.model,mujoco.mjtObj.mjOBJ_BODY,name) for name in ('box','gripper')}
        self.geom_ids={name:mujoco.mj_name2id(self.model,mujoco.mjtObj.mjOBJ_GEOM,name) for name in ('floor','box_geom','gripper_geom')}
        self.attachment=mujoco.mj_name2id(self.model,mujoco.mjtObj.mjOBJ_EQUALITY,'attachment')
        self.corner_ids=[mujoco.mj_name2id(self.model,mujoco.mjtObj.mjOBJ_SITE,f'C{i}') for i in range(1,9)]

    def _record_frame(self, history, current_time=None):
        super()._record_frame(history,current_time)
        contacts=self.contacts();history[-1]['ContactCount']=contacts['floor_count']
        history[-1]['ContactNormalForceN']=contacts['floor_force_n']
        history[-1]['GripperContactCount']=contacts['gripper_count']
        history[-1]['GripperContactNormalForceN']=contacts['gripper_force_n']

    def body(self, name):
        index=self.ids[name];p=self.data.xpos[index].copy();r=self.data.xmat[index].reshape(3,3).copy()
        # Jacobians give world origin velocities without depending on freejoint
        # address/frame optimizations or confusing origin with inertial COM.
        jp=np.zeros((3,self.model.nv));jr=jp.copy()
        mujoco.mj_jacBody(self.model,self.data,jp,jr,index)
        return p,r,jp@self.data.qvel,jr@self.data.qvel

    def contacts(self):
        result=dict(floor_count=0,gripper_count=0,floor_force_n=0.,gripper_force_n=0.)
        floor={self.geom_ids['floor'],self.geom_ids['box_geom']}
        gripper={self.geom_ids['gripper_geom'],self.geom_ids['box_geom']}
        for i in range(self.data.ncon):
            item=self.data.contact[i];pair={int(item.geom1),int(item.geom2)}
            key='floor' if pair==floor else 'gripper' if pair==gripper else None
            if key is not None:
                force=np.zeros(6);mujoco.mj_contactForce(self.model,self.data,i,force)
                result[key+'_count']+=1;result[key+'_force_n']+=float(force[0])
        return result

    def snapshot(self):
        mujoco.mj_forward(self.model,self.data)
        result=dict(time_s=float(self.data.time),qpos=self.data.qpos.tolist(),qvel=self.data.qvel.tolist(),
            active_constraints=self.data.eq_active.astype(int).tolist(),contacts=self.contacts())
        for name in ('box','gripper'):
            p,r,v,w=self.body(name)
            result[name]=dict(origin_mm=(p*1000).tolist(),rotation=r.tolist(),origin_velocity_world_mm_s=(v*1000).tolist(),
                angular_velocity_world_rad_s=w.tolist(),angular_velocity_body_rad_s=(r.T@w).tolist())
        pb,rb,_,_=self.body('box');pg,rg,_,_=self.body('gripper')
        result['relative_transform']=dict(origin_mm=(rg.T@(pb-pg)*1000).tolist(),rotation=(rg.T@rb).tolist())
        result['weld_data']=self.model.eq_data[self.attachment].tolist()
        return result

    def toggle(self, enabled, *, anchor=None, kind):
        before=self.snapshot()
        if enabled:
            pb,rb,_,_=self.body('box');pg,rg,_,_=self.body('gripper')
            self.relative=(rg.T@(pb-pg),rg.T@rb)
            self.model.eq_data[self.attachment,:3]=anchor
            self.model.eq_data[self.attachment,3:6]=rg.T@(pb+rb@anchor-pg)
            self.model.eq_data[self.attachment,6:10]=quaternion(rg.T@rb)
        self.data.eq_active[self.attachment]=enabled
        after=self.snapshot()
        entry=dict(envelope('RobotConstraintTransition',phase_id=self.current_phase['phase_id'],
            constraint_index=int(self.attachment),before=before,after=after,next_step=None,
            next_step_status='pending',next_step_reason=None),kind=kind)
        self.sequence_evidence['toggles'].append(entry)
        return entry

    def attachment_target(self):
        pb,rb,vb,wb=self.body('box')
        face=self.plan['attachment_face']
        if face=='upward': face=max(NORMALS,key=lambda key:(rb@np.array(NORMALS[key]))[2])
        normal=np.array(NORMALS[face],dtype=float);anchor=normal*np.array(self.size_m)
        endpoint=np.array([0,0,-self.plan['physics']['radius_mm']/1000])
        rg=rb@Rotation.align_vectors([normal],[[0.,0.,1.]])[0].as_matrix()
        pg=pb+rb@anchor-rg@endpoint
        return pg,rg,anchor,normal,endpoint

    def can_attach(self, anchor, normal, endpoint):
        pb,rb,vb,wb=self.body('box');pg,rg,vg,wg=self.body('gripper')
        distance=np.linalg.norm(pb+rb@anchor-pg-rg@endpoint)*1000
        angle=np.degrees(np.arccos(np.clip(np.dot(rb@normal,rg[:,2]),-1,1)))
        speed=np.linalg.norm(vb+np.cross(wb,rb@anchor)-vg-np.cross(wg,rg@endpoint))*1000
        spin=np.linalg.norm(wb-wg);lim=self.plan['transition']
        return dict(distance_mm=float(distance),normal_deg=float(angle),relative_speed_mm_s=float(speed),relative_spin_rad_s=float(spin),
            eligible=bool(distance<=lim['distance_mm'] and angle<=lim['normal_deg'] and speed<=lim['relative_speed_mm_s'] and spin<=lim['relative_spin_rad_s']))

    def _step(self, cancelled, progress, limit, viewer):
        if (self.plan!=self.config['sequence_profile']['execution_plan']
                or digest(self.config)!=self.sequence_evidence['configuration_hash']):
            self._stop('failure','Execution source configuration changed during the run.')
        if cancelled is not None and cancelled(): self._stop('cancelled','Sequence cancelled.')
        if self.data.time>=limit-1e-12: self._stop('time_limit','Sequence time limit reached; unfinished phases remain.')
        if viewer is not None and not viewer.is_running(): self._stop('cancelled','Viewer closed; sequence cancelled.')
        if self._retract is not None:
            start,p,r=self._retract;u=min(1.,(self.data.time-start)/.3);s=10*u**3-15*u**4+6*u**5
            self._target(p+np.array([0,0,.1*s]),r)
            if u==1.:self._retract=None
        before=float(self.data.time);mujoco.mj_step(self.model,self.data);mujoco.mj_forward(self.model,self.data)
        if (not np.isfinite(self.data.qpos).all() or not np.isfinite(self.data.qvel).all()
                or abs(float(self.data.time)-before-self.model.opt.timestep)>1e-9):
            self._stop('failure','Engine state nonfinite or clock reset.')
        if any(item.number for item in self.data.warning): self._stop('failure','MuJoCo numerical warning; continuity is unavailable.')
        if self.current_phase is not None and ('support_pivot_local_mm' in self.current_phase or self.current_phase['kind']=='floor_move'):
            if min(self.data.site_xpos[i,2] for i in self.corner_ids)*1000 < -self.plan['transition']['penetration_mm']:
                self._stop('failure','Supported motion penetrated beyond the explicit synthetic transition limit.')
        for entry in self.sequence_evidence['toggles'][-1:]:
            if entry['next_step'] is None:
                entry.update(next_step=self.snapshot(),next_step_status='recorded',next_step_reason=None)
        if float(self.data.time)>=self._next_record-1e-12:
            self._record_frame(self.history);self._next_record+=self._sample_dt
        if progress is not None and (not self.history or len(self.history)!=self._last_progress):
            self._last_progress=len(self.history);progress(float(self.data.time),limit)
        if viewer is not None:
            viewer.sync();time.sleep(self.model.opt.timestep)

    def _stop(self, status, reason):
        self.sequence_evidence['completion']=status;self.sequence_evidence['reason']=reason
        for entry in self.sequence_evidence['toggles'][-1:]:
            if entry['next_step'] is None:
                entry.update(next_step_status='unavailable',next_step_reason=reason)
        if self.data is not None:
            self.sequence_evidence['terminal_state']=self.snapshot()
            self.sequence_evidence['terminal_target']=dict(origin_mm=(self.data.mocap_pos[0]*1000).tolist(),quaternion_wxyz=self.data.mocap_quat[0].tolist())
        if self.data is not None and (not self.history or self.history[-1]['time']!=self.data.time): self._record_frame(self.history)
        raise (SequenceCancelled if status=='cancelled' else SequenceFailure)(reason,self)

    def _target(self, p, r):
        self.data.mocap_pos[0]=p;self.data.mocap_quat[0]=quaternion(r)

    def _motion(self, p, r, duration, fraction, step, *, pivot=None):
        self._retract=None
        initial=self.data.mocap_pos[0].copy();initial_r=Rotation.from_quat(self.data.mocap_quat[0][[1,2,3,0]])
        delta=(initial_r.inv()*Rotation.from_matrix(r)).as_rotvec();start=float(self.data.time)
        while self.data.time-start<duration*fraction-1e-12:
            u=min(1.,(self.data.time-start+self.model.opt.timestep)/duration);s=10*u**3-15*u**4+6*u**5
            ri=(initial_r*Rotation.from_rotvec(s*delta)).as_matrix()
            pi=initial+s*(p-initial)
            if pivot is not None:
                anchor_world,anchor_local=self._pivot
                relative_p,relative_r=self.relative
                rb=ri@relative_r;pb=anchor_world-rb@anchor_local
                pi=pb-ri@relative_p
            self._target(pi,ri);step()

    def _follow_to_rest(self, p, r, step, *, supported=False):
        limits=self.plan['transition'];start=float(self.data.time);dwell=0.
        while self.data.time-start<limits['timeout_s']:
            pg,rg,vg,wg=self.body('gripper')
            err=np.degrees((Rotation.from_matrix(rg).inv()*Rotation.from_matrix(r)).magnitude())
            valid=(np.linalg.norm(pg-p)*1000<=limits['position_mm'] and err<=limits['attitude_deg']
                and np.linalg.norm(vg)*1000<=limits['rest_speed_mm_s'] and np.linalg.norm(wg)<=limits['rest_spin_rad_s'])
            if self.data.eq_active[self.attachment]:
                pb,rb,_,_=self.body('box');relative_p,relative_r=self.relative
                expected_p=p+r@relative_p;expected_r=r@relative_r
                box_angle=np.degrees(Rotation.from_matrix(expected_r.T@rb).magnitude())
                valid=valid and np.linalg.norm(pb-expected_p)*1000<=limits['position_mm'] and box_angle<=limits['attitude_deg']
            if supported: valid=valid and self.contacts()['floor_force_n']>1e-8
            dwell=dwell+self.model.opt.timestep if valid else 0.
            if dwell>=limits['dwell_s']: return
            step()
        self._stop('failure','Dynamic endpoint failed to reach its pose/rest/support transition condition.')

    def _attach(self, step, *, kind):
        limits=self.plan['transition']
        for attempt in range(limits['retries']+1):
            p,r,anchor,normal,endpoint=self.attachment_target()
            if p[2]-self.plan['physics']['radius_mm']/1000<0:
                self._stop('failure','Configured attachment endpoint intersects the floor and is not accessible.')
            self._motion(p,r,self.current_phase['duration_s'],1.,step)
            start=float(self.data.time)
            while self.data.time-start<limits['timeout_s']:
                metrics=self.can_attach(anchor,normal,endpoint)
                if metrics['eligible']:
                    self.sequence_evidence['attempts'].append(envelope('RobotAttachmentAttempt',phase_id=self.current_phase['phase_id'],
                        attempt=attempt,metrics=metrics,status='attached'))
                    self.toggle(True,anchor=anchor,kind=kind);step();return
                step()
            self.sequence_evidence['attempts'].append(envelope('RobotAttachmentAttempt',phase_id=self.current_phase['phase_id'],
                attempt=attempt,metrics=metrics,status='failed'))
        self._stop('failure','Attachment distance, normal or relative velocity failed after bounded retries.')

    def _phase(self, item, step):
        kind=item['kind'];duration=item['duration_s'];limits=self.plan['transition']
        if kind=='approach':
            p,r,_,_,_=self.attachment_target();p=p+r[:,2]*.02
            if 'target_origin_mm' in item:p=np.array(item['target_origin_mm'])/1000
            if 'target_xyz_deg' in item:r=Rotation.from_euler('xyz',item['target_xyz_deg'],degrees=True).as_matrix()
            self._motion(p,r,duration,1.,step);self._follow_to_rest(p,r,step);return
        if kind in ('attach','pickup'): self._attach(step,kind=kind);return
        if kind in ('lift','orient','floor_move','flip') or kind=='release' and ('target_origin_mm' in item or 'target_xyz_deg' in item):
            pb,rb,_,_=self.body('box');target_r=Rotation.from_euler('xyz',item.get('target_xyz_deg'),degrees=True).as_matrix() if 'target_xyz_deg' in item else rb
            target_p=np.array(item['target_origin_mm'])/1000 if 'target_origin_mm' in item else pb
            pivot=item.get('support_pivot_local_mm')
            if pivot is not None:
                local=np.array(pivot)/1000
                if abs((pb+rb@local)[2]*1000)>self.plan['transition']['penetration_mm']:
                    self._stop('failure','Configured support edge is not at the actual floor.')
                self._pivot=(pb+rb@local,local);target_p=self._pivot[0]-target_r@local
            relp,relr=self.relative;rg=target_r@relr.T;pg=target_p-rg@relp
            fraction=item.get('motion_fraction',1.)
            self._motion(pg,rg,duration,fraction,step,pivot=pivot)
            if fraction==1.: self._follow_to_rest(pg,rg,step,supported=pivot is not None or kind=='floor_move')
            if kind!='release': return
        if kind=='release':
            if self.plan['handling_family']=='airborne':
                self._record_frame([])  # refresh only; no state reset
                minimum=min(self.data.site_xpos[mujoco.mj_name2id(self.model,mujoco.mjtObj.mjOBJ_SITE,f'C{i}')][2] for i in range(1,9))
                if minimum<=0 or self.contacts()['floor_force_n']>1e-8: self._stop('failure','Airborne release requires actual floor clearance.')
            elif self.plan['handling_family']=='floor_supported' and self.contacts()['floor_force_n']<=1e-8:
                self._stop('failure','Supported release requires actual floor support.')
            self.toggle(False,kind='release');step()
            # Retract only the target after a physical release. The detached
            # dynamic gripper moves away instead of supporting the falling box.
            self._retract=(float(self.data.time),self.data.mocap_pos[0].copy(),Rotation.from_quat(self.data.mocap_quat[0][[1,2,3,0]]).as_matrix())
            return
        start=float(self.data.time);dwell=0.
        timeout=duration+limits['timeout_s'] if kind in ('contact','settle') else duration
        while self.data.time-start<timeout-1e-12:
            if kind=='contact' and self.contacts()['floor_force_n']>1e-8: return
            if kind=='settle':
                _,_,v,w=self.body('box')
                rest=(self.contacts()['floor_force_n']>1e-8 and np.linalg.norm(v)*1000<=limits['rest_speed_mm_s'] and np.linalg.norm(w)<=limits['rest_spin_rad_s'])
                dwell=dwell+self.model.opt.timestep if rest else 0.
                if self.data.time-start>=duration and dwell>=limits['dwell_s']: return
            step()
        if kind in ('contact','settle'): self._stop('failure',f'{kind} transition timed out.')
        if kind=='hold':
            self._follow_to_rest(self.data.mocap_pos[0].copy(),Rotation.from_quat(self.data.mocap_quat[0][[1,2,3,0]]).as_matrix(),step)

    def run_simulation(self, target_fps=120, stop_condition_time=None, show_viewer=False, *, cancelled=None, progress=None, **unused):
        if self.sequence_evidence['completion']!='not_started': raise ValueError('A sequence cannot be resumed/rebuilt implicitly.')
        if (self.plan!=self.config['sequence_profile']['execution_plan']
                or digest(self.config)!=self.sequence_evidence['configuration_hash']):
            raise ValueError('Execution plan differs from the captured source configuration.')
        validate_plan(self.plan,self.config)
        if not np.isfinite(target_fps) or target_fps<=0: raise ValueError('target_fps must be positive and finite.')
        limit=self.config['duration_s'] if stop_condition_time is None else stop_condition_time
        if limit!=self.config['duration_s']: raise ValueError('Sequence time limit differs from captured profile.')
        if self.model is None: self.build()
        self._sample_dt=max(1,int(1/target_fps/self.model.opt.timestep))*self.model.opt.timestep
        self._next_record=self._sample_dt;self._last_progress=-1;self._record_frame(self.history)
        self.sequence_evidence['completion']='running'
        phases=self.plan['phases']
        def execute(viewer):
            for index,item in enumerate(phases):
                self.current_phase=item;self.sequence_evidence['unfinished_phase_ids']=[p['phase_id'] for p in phases[index:]]
                stage=dict(envelope('RobotPhaseExecution',phase_id=item['phase_id'],step_id=item['step_id'],
                    start_time_s=float(self.data.time),end_time_s=None,start_state=self.snapshot(),end_state=None,status='running'),kind=item['kind'])
                self.sequence_evidence['stages'].append(stage)
                self._phase(item,lambda:self._step(cancelled,progress,limit,viewer))
                stage.update(end_time_s=float(self.data.time),end_state=self.snapshot(),status='completed')
            self.sequence_evidence['unfinished_phase_ids']=[]
            self.sequence_evidence['completion']='completed' if self.plan['completion_policy']=='complete' else 'partial'
            if self.history[-1]['time']!=self.data.time: self._record_frame(self.history)
            return self.history
        if show_viewer:
            with mujoco.viewer.launch_passive(self.model,self.data) as viewer: return execute(viewer)
        return execute(None)
