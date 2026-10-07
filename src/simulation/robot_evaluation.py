"""Evaluation-only continuity and coverage checks; never an analysis input."""
import numpy as np
from scipy.spatial.transform import Rotation
from src.utils.marker_profile_identity import validate_envelope, digest
from .robot_profiles import validate_plan


def _state_valid(state, errors):
    """Check actual snapshots, including independent freejoint/body consistency."""
    try:
        qpos=np.asarray(state['qpos'],dtype=float);qvel=np.asarray(state['qvel'],dtype=float)
        if (qpos.shape!=(14,) or qvel.shape!=(12,) or not np.isfinite(qpos).all()
                or not np.isfinite(qvel).all() or not np.isfinite(state['time_s']) or state['time_s']<0
                or len(state['active_constraints'])!=2 or any(type(v) is not int or v not in (0,1) for v in state['active_constraints'])):
            raise ValueError('Invalid freejoint state/clock/constraints.')
        for name,position,velocity in (('box',0,0),('gripper',7,6)):
            body=state[name];r=np.asarray(body['rotation'],dtype=float)
            vectors={key:np.asarray(body[key],dtype=float) for key in ('origin_mm','origin_velocity_world_mm_s',
                'angular_velocity_world_rad_s','angular_velocity_body_rad_s')}
            if (r.shape!=(3,3) or not np.isfinite(r).all() or not np.allclose(r.T@r,np.eye(3),atol=1e-10,rtol=0)
                    or abs(np.linalg.det(r)-1)>1e-10 or any(v.shape!=(3,) or not np.isfinite(v).all() for v in vectors.values())):
                raise ValueError('Invalid body transform/velocity.')
            quat=qpos[position+3:position+7]
            if abs(np.linalg.norm(quat)-1)>1e-10:raise ValueError('Invalid freejoint quaternion.')
            expected_r=Rotation.from_quat(quat[[1,2,3,0]]).as_matrix()
            if (not np.allclose(vectors['origin_mm'],qpos[position:position+3]*1000,atol=1e-10,rtol=0)
                    or not np.allclose(r,expected_r,atol=1e-12,rtol=0)
                    or not np.allclose(vectors['origin_velocity_world_mm_s'],qvel[velocity:velocity+3]*1000,atol=1e-10,rtol=0)
                    or not np.allclose(vectors['angular_velocity_body_rad_s'],qvel[velocity+3:velocity+6],atol=1e-12,rtol=0)
                    or not np.allclose(vectors['angular_velocity_world_rad_s'],r@qvel[velocity+3:velocity+6],atol=1e-12,rtol=0)):
                raise ValueError('Snapshot body pose/velocity differs from its freejoint state.')
        for key in ('floor','gripper'):
            if (type(state['contacts'][key+'_count']) is not int or state['contacts'][key+'_count']<0
                    or not np.isfinite(state['contacts'][key+'_force_n']) or state['contacts'][key+'_force_n']<0):
                raise ValueError('Invalid contact snapshot.')
        w=np.asarray(state['weld_data'],dtype=float)
        relative=state['relative_transform']
        if (w.shape!=(11,) or not np.isfinite(w).all()
                or np.asarray(relative['origin_mm']).shape!=(3,) or not np.isfinite(relative['origin_mm']).all()
                or np.asarray(relative['rotation']).shape!=(3,3) or not np.isfinite(relative['rotation']).all()):
            raise ValueError('Invalid attachment snapshot.')
        b,g=state['box'],state['gripper'];rb=np.asarray(b['rotation']);rg=np.asarray(g['rotation'])
        if (not np.allclose(relative['origin_mm'],rg.T@(np.asarray(b['origin_mm'])-g['origin_mm']),atol=1e-10,rtol=0)
                or not np.allclose(relative['rotation'],rg.T@rb,atol=1e-12,rtol=0)):
            raise ValueError('Snapshot relative transform differs from its actual body transforms.')
        return True
    except (KeyError,TypeError,ValueError,IndexError) as error:
        errors.append('Invalid sequence state: '+str(error));return False


def evaluate_sequence(evidence, plan, *, history=None, configuration_hash=None):
    if evidence is None: return dict(status='unavailable',reason='Sequence evidence is absent.')
    validate_envelope(evidence,'RobotSequenceEvidence');validate_plan(plan)
    errors=[]
    if configuration_hash is not None and evidence.get('configuration_hash')!=configuration_hash: errors.append('Stale sequence source identity.')
    if evidence.get('engine_builds')!=1: errors.append('Sequence requires exactly one engine build.')
    if evidence.get('world_frame')!='mujoco-z-up' or evidence.get('units')!=dict(position='mm',linear_velocity='mm/s',angular_velocity='rad/s',time='s'):
        errors.append('Sequence frame/units mismatch.')
    stages=evidence.get('stages',[])
    outcome=evidence.get('completion');complete=outcome=='completed'
    finished=outcome in ('completed','partial')
    interrupted=outcome in ('cancelled','time_limit','failure')
    if not finished and not interrupted:errors.append('Unsupported/nonterminal sequence completion status.')
    if len(stages)>len(plan['phases']) or not stages:errors.append('Invalid executed phase prefix.')
    if finished and (len(stages)!=len(plan['phases']) or evidence.get('unfinished_phase_ids')): errors.append('Premature whole-run completion.')
    if complete and plan['completion_policy']!='complete': errors.append('Partial plan cannot declare full completion.')
    if outcome=='partial' and plan['completion_policy']!='partial':errors.append('Complete plan cannot declare intentional partial completion.')
    if interrupted:
        if (not evidence.get('reason') or evidence.get('unfinished_phase_ids')!=[p['phase_id'] for p in plan['phases'][max(0,len(stages)-1):]]):
            errors.append('Interrupted sequence has inconsistent unfinished phase coverage.')
        _state_valid(evidence.get('terminal_state'),errors)
    previous=0.;previous_state=None
    for stage,phase in zip(stages,plan['phases']):
        validate_envelope(stage,'RobotPhaseExecution')
        if any(stage.get(key)!=phase[key] for key in ('phase_id','kind','step_id')): errors.append('Phase coverage identity differs.')
        start=stage.get('start_time_s');end=stage.get('end_time_s')
        if not isinstance(start,(int,float)) or not np.isfinite(start) or start!=previous: errors.append('Stage clock boundary discontinuity.')
        valid_start=_state_valid(stage.get('start_state'),errors)
        if valid_start and stage['start_state']['time_s']!=start:errors.append('Phase start clock differs from state.')
        if previous_state is not None and stage.get('start_state')!=previous_state:errors.append('Phase boundary state reset/discontinuity.')
        if end is not None:
            if stage.get('status')!='completed':errors.append('Finished phase has inconsistent status.')
            if not np.isfinite(end) or end<start: errors.append('Stage time regression.')
            if _state_valid(stage.get('end_state'),errors) and stage['end_state']['time_s']!=end:errors.append('Phase end clock differs from state.')
            previous_state=stage.get('end_state')
            previous=end
        elif (finished or stage is not stages[-1] or stage.get('status')!='running' or stage.get('end_state') is not None):
            errors.append('Sequence contains inconsistent unfinished phase.')
        elif interrupted and evidence['terminal_state']['time_s']<start:errors.append('Terminal clock precedes the interrupted phase.')
    if interrupted and stages and stages[-1].get('end_time_s') is not None:errors.append('Interrupted sequence has no interrupted phase.')
    toggles=evidence.get('toggles',[])
    transition_stages=[s for s in stages if s['kind'] in ('attach','pickup','release')]
    required=sum(s.get('status')=='completed' for s in transition_stages)
    if not required<=len(toggles)<=len(transition_stages):errors.append('Constraint transition coverage missing/duplicated.')
    for index,entry in enumerate(toggles):
        validate_envelope(entry,'RobotConstraintTransition')
        if index>=len(transition_stages) or any(entry.get(key)!=transition_stages[index][key] for key in ('phase_id','kind')):
            errors.append('Constraint transition differs from ordered phase coverage.')
        pre,post=entry['before'],entry['after']
        if not _state_valid(pre,errors) or not _state_valid(post,errors):continue
        if index<len(transition_stages):
            stage=transition_stages[index];boundary=stage.get('end_time_s')
            if boundary is None and interrupted:boundary=evidence['terminal_state']['time_s']
            if boundary is None or not stage['start_time_s']<=pre['time_s']<=boundary:errors.append('Constraint transition clock lies outside its phase.')
        for key in ('time_s','qpos','qvel'):
            if pre[key]!=post[key]: errors.append('Toggle reset '+key)
        constraint=entry['constraint_index'];before=pre['active_constraints'];after=post['active_constraints']
        if type(constraint) is not int or constraint!=1:
            errors.append('Incorrect attachment constraint identity.');continue
        expected_active=0 if entry['kind']=='release' else 1
        if (len(before)!=len(after) or before[constraint]==after[constraint] or after[constraint]!=expected_active
                or any(a!=b for i,(a,b) in enumerate(zip(before,after)) if i!=constraint)):
            errors.append('Incorrect active-constraint transition.')
        for name in ('box','gripper'):
            if pre[name]!=post[name]: errors.append('Toggle changed actual '+name+' pose/velocity.')
        if entry['kind'] in ('attach','pickup'):
            b,g=post['box'],post['gripper'];rb=np.array(b['rotation']);rg=np.array(g['rotation'])
            pb=np.array(b['origin_mm'])/1000;pg=np.array(g['origin_mm'])/1000;w=np.array(post['weld_data'])
            # Independent measured anchor closure, not a copied stored relative pose.
            distance=np.linalg.norm(pb+rb@w[:3]-pg-rg@w[3:6])
            relative_rotation=Rotation.from_quat(w[6:10][[1,2,3,0]]).as_matrix()
            angle=Rotation.from_matrix((rg@relative_rotation).T@rb).magnitude()
            if distance>1e-12 or angle>1e-12: errors.append('Incorrect measured attachment reference.')
            transform=post['relative_transform']
            if (not np.allclose(transform['origin_mm'],rg.T@(pb-pg)*1000,atol=1e-10,rtol=0)
                    or not np.allclose(transform['rotation'],rg.T@rb,atol=1e-12,rtol=0)):
                errors.append('Incorrect measured origin-relative transform.')
        next_step=entry.get('next_step')
        if next_step is None:
            if (not interrupted or index!=len(toggles)-1 or evidence.get('terminal_state')!=post
                    or entry.get('next_step_status')!='unavailable' or not entry.get('next_step_reason')):
                errors.append('Next-step reaction unavailable without a matching interrupted boundary.')
        else:
            if entry.get('next_step_status')!='recorded' or entry.get('next_step_reason') is not None:errors.append('Incorrect next-step availability declaration.')
            if _state_valid(next_step,errors):
                if abs(next_step['time_s']-post['time_s']-.002)>1e-9: errors.append('Next-step engine clock reset.')
                if next_step['active_constraints']!=post['active_constraints']:errors.append('Next-step attachment state changed unexpectedly.')
    if history is not None:
        times=np.array([h['time'] for h in history])
        if not len(times) or not np.isfinite(times).all() or times[0]!=0 or np.any(np.diff(times)<=0): errors.append('Recorded engine clock reset/nonfinite.')
        if finished and times[-1]!=previous: errors.append('Recording misses final sequence boundary.')
        if interrupted and times[-1]!=evidence['terminal_state']['time_s']:errors.append('Recording misses terminal sequence boundary.')
    return dict(status='failed' if errors else 'valid' if complete else 'partial',errors=errors,
        releases=sum(t['kind']=='release' for t in toggles),engine_builds=evidence.get('engine_builds'),
        evidence_hash=digest(evidence),physical_acceptance='not_evaluated')
