"""Explicit PUB07 execution plans; config-only PUB06 plans remain config-only."""
from copy import deepcopy
import numpy as np
from scipy.spatial.transform import Rotation
from src.utils.marker_profile_identity import envelope, digest, validate_envelope
from .mode_profiles import number, vector, _text

KINDS = ('approach', 'attach', 'lift', 'orient', 'hold', 'release', 'free_motion',
         'contact', 'settle', 'pickup', 'floor_move', 'flip')
NORMALS = {'+X': [1,0,0], '-X': [-1,0,0], '+Y': [0,1,0], '-Y': [0,-1,0],
           '+Z': [0,0,1], '-Z': [0,0,-1]}


def applicability(config):
    return digest(dict(size_mm=config['size_mm'], physics=config['physics_profile'],
        planned_steps=config['sequence_profile']['steps']))


def phase(kind, index, step_id=None, duration_s=.5, **settings):
    if 'target_origin_mm' in settings or 'target_xyz_deg' in settings:
        settings.setdefault('target_frame','mujoco-z-up-gripper-origin' if kind=='approach' else 'mujoco-z-up-box-origin')
    return dict(envelope('RobotSequencePhase', phase_id=f'phase-{index}',
        step_id=step_id, duration_s=duration_s, **settings), kind=kind)


def validate_plan(plan, config=None):
    validate_envelope(plan, 'RobotExecutionPlan')
    expected = {'schema_version','plan_spec','object_type','profile_id','source','applicability_hash',
        'test_type','type_source','handling_family','attachment_face','endpoint','physics',
        'transition','phases','completion_policy','selected_step_ids','omitted_step_ids'}
    if set(plan) != expected: raise ValueError('Unexpected robot execution plan fields.')
    _text(plan['profile_id'], 'Execution profile ID')
    if plan['source'] != dict(kind='public_synthetic_fixture', id='pub07-virtual-v1'):
        raise ValueError('Unsupported execution profile source; actual conditions require a new explicit profile.')
    if plan['test_type'] not in ('G','H','unknown') or plan['type_source'] != 'virtual-fixture-not-experimental':
        raise ValueError('Unsupported Type/source declaration.')
    if plan['handling_family'] not in ('airborne','floor_supported','held_only'):
        raise ValueError('Unsupported handling family.')
    if plan['test_type']=='H' and plan['handling_family']=='airborne':
        raise ValueError('Type H requires an explicit supported handling template.')
    if plan['attachment_face'] not in (*NORMALS, 'upward') or plan['endpoint']!='sphere-minus-local-z':
        raise ValueError('Unsupported attachment face/endpoint.')
    physics = plan['physics']
    if set(physics)!={'gripper_mass_kg','gripper_inertia_kg_m2','radius_mm','drive_timeconst_s','attach_timeconst_s','torque_scale_m','contact_margin_mm','solver_iterations'}:
        raise ValueError('Unexpected gripper physics fields.')
    for field in ('gripper_mass_kg','radius_mm','drive_timeconst_s','attach_timeconst_s','torque_scale_m'):
        number(physics[field], field, minimum=1e-4)
    number(physics['contact_margin_mm'],'Contact margin',minimum=0,maximum=5)
    vector(physics['gripper_inertia_kg_m2'],'Gripper inertia',minimum=1e-9)
    inertia=sorted(physics['gripper_inertia_kg_m2'])
    if inertia[2]>inertia[0]+inertia[1]:raise ValueError('Gripper inertia violates the triangle inequality.')
    if type(physics['solver_iterations']) is not int or not 10<=physics['solver_iterations']<=1000:
        raise ValueError('Invalid solver iteration budget.')
    limits = plan['transition']
    if set(limits)!={'distance_mm','normal_deg','relative_speed_mm_s','relative_spin_rad_s',
        'position_mm','attitude_deg','rest_speed_mm_s','rest_spin_rad_s','dwell_s','timeout_s','retries','penetration_mm'}:
        raise ValueError('Unexpected transition fields.')
    for key,value in limits.items():
        if key=='retries':
            if type(value) is not int or not 0<=value<=5: raise ValueError('Invalid attachment retries.')
        else: number(value,key,minimum=0)
    if not limits['timeout_s']>limits['dwell_s'] or limits['normal_deg']>90:
        raise ValueError('Invalid transition timeout/normal threshold.')
    if plan['completion_policy'] not in ('complete','partial'):
        raise ValueError('Invalid sequence completion policy.')
    for key in ('selected_step_ids','omitted_step_ids'):
        if not isinstance(plan[key],list) or len(set(plan[key]))!=len(plan[key]): raise ValueError('Invalid step coverage.')
        for value in plan[key]: _text(value,'Step ID')
    if set(plan['selected_step_ids']) & set(plan['omitted_step_ids']): raise ValueError('Conflicting step coverage.')
    phases=plan['phases']
    if not isinstance(phases,list) or not phases: raise ValueError('Execution phases are required.')
    attached=False; attached_step=None; released=set(); release_order=[]; ids=set()
    for item in phases:
        validate_envelope(item,'RobotSequencePhase')
        required={'schema_version','plan_spec','object_type','phase_id','kind','step_id','duration_s'}
        optional={'target_origin_mm','target_xyz_deg','target_frame','motion_fraction','support_pivot_local_mm'}
        if not required<=set(item) or set(item)-required-optional: raise ValueError('Unexpected phase fields.')
        if item['phase_id'] in ids: raise ValueError('Duplicate phase ID.')
        ids.add(item['phase_id']);_text(item['phase_id'],'Phase ID')
        kind=item['kind']
        if kind not in KINDS: raise ValueError('Unsupported robot phase.')
        number(item['duration_s'],'Phase duration',minimum=.002,maximum=60)
        if item['step_id'] is not None and item['step_id'] not in plan['selected_step_ids']:
            raise ValueError('Phase references an unselected drop.')
        for key in ('target_origin_mm','target_xyz_deg','support_pivot_local_mm'):
            if key in item: vector(item[key],key)
        if 'motion_fraction' in item: number(item['motion_fraction'],'Motion fraction',minimum=.01,maximum=1)
        targeted='target_origin_mm' in item or 'target_xyz_deg' in item
        if 'target_frame' in item and not targeted:
            raise ValueError('A target frame requires a motion target.')
        if 'motion_fraction' in item and (kind!='release' or not targeted):
            raise ValueError('Partial motion is supported only by a targeted release.')
        if 'support_pivot_local_mm' in item and (kind not in ('orient','flip','release') or not targeted):
            raise ValueError('A support pivot requires an explicit supported rotation target.')
        if targeted and item.get('target_frame')!=('mujoco-z-up-gripper-origin' if kind=='approach' else 'mujoco-z-up-box-origin'):
            raise ValueError('Unsupported phase target frame/units.')
        if (kind in ('attach','pickup','hold','free_motion','contact','settle') and set(item)&optional
                or kind in ('lift','orient','floor_move','flip') and not targeted):
            raise ValueError('Phase target is missing or inapplicable.')
        if kind in ('attach','pickup'):
            if attached: raise ValueError('Attachment requested while already attached.')
            attached=True; attached_step=item['step_id']
        if attached and item['step_id']!=attached_step:
            raise ValueError('Attached phases must retain their planned drop identity.')
        if kind in ('lift','orient','hold','floor_move','flip') and not attached:
            raise ValueError('Held motion requires attachment.')
        if kind=='release':
            if not attached or item['step_id'] is None: raise ValueError('Release requires attachment and planned drop ID.')
            if item['step_id'] in released: raise ValueError('A planned drop is released twice.')
            released.add(item['step_id']);release_order.append(item['step_id']);attached=False
        if kind in ('free_motion','contact','settle') and attached: raise ValueError('Released phase requested while attached.')
    if plan['completion_policy']=='complete' and released!=set(plan['selected_step_ids']):
        raise ValueError('Complete sequence is missing a planned release.')
    if plan['completion_policy']=='complete':
        if release_order!=plan['selected_step_ids']:
            raise ValueError('Release order differs from the selected planned drops.')
        for step_id in released:
            timeline=[p['kind'] for p in phases if p['step_id']==step_id]
            required_order=('orient','hold','release','free_motion','contact','settle')
            if not all(kind in timeline for kind in required_order):
                raise ValueError('Complete sequence is missing required phase coverage.')
            if [timeline.index(kind) for kind in required_order]!=sorted(timeline.index(kind) for kind in required_order):
                raise ValueError('Required phases must execute in order for each planned drop.')
        for previous,current in zip(release_order,release_order[1:]):
            settled=max(i for i,p in enumerate(phases) if p['step_id']==previous and p['kind']=='settle')
            pickup=next((i for i,p in enumerate(phases) if p['step_id']==current and p['kind']=='pickup'),None)
            if pickup is None or pickup<=settled:
                raise ValueError('Later drops require pickup after the previous settle.')
    if config is not None:
        if plan['applicability_hash']!=applicability(config): raise ValueError('Execution profile is stale; preview and explicit Apply are required.')
        all_ids={item['step_id'] for item in config['sequence_profile']['steps']}
        for item in config['sequence_profile']['steps']:
            if item['step_id'] in plan['selected_step_ids'] and plan['test_type']!='unknown':
                if ('Type '+plan['test_type']) not in item['category']:
                    raise ValueError('Declared virtual Type differs from the selected planned category.')
        if set(plan['selected_step_ids'])|set(plan['omitted_step_ids'])!=all_ids:
            raise ValueError('Execution selection must account for every planned drop.')
        half=np.array(config['size_mm'])/2
        for item in phases:
            if 'support_pivot_local_mm' in item:
                anchor=np.array(item['support_pivot_local_mm'])
                if np.any(np.abs(anchor)>half+1e-9) or np.count_nonzero(np.isclose(np.abs(anchor),half,atol=1e-9,rtol=0))<2:
                    raise ValueError('Support pivot must be an explicit box edge point.')
    return plan


def example_plan(config, *, family='airborne', selected_step_ids=None, attachment_face='upward'):
    """Build an explicitly virtual proposal, never an automatic experimental approval."""
    all_steps=config['sequence_profile']['steps'];selected_step_ids=selected_step_ids or [s['step_id'] for s in all_steps]
    steps=[s for s in all_steps if s['step_id'] in selected_step_ids]
    if not steps: raise ValueError('Select at least one planned drop.')
    phases=[]
    def add(kind, step, duration=.5, **settings):
        phases.append(phase(kind,len(phases)+1,step['step_id'],duration,**settings))
    for index,step in enumerate(steps):
        if '17_' in step['preset_id'] or 'hazard' in step['preset_id'].lower():
            raise ValueError('Hazard block is unavailable; explicitly omit that planned test.')
        add('approach' if index==0 else 'pickup',step,1.)
        if index==0: add('attach',step,.1)
        if family=='airborne':
            # Lift high enough to rotate any cuboid before lowering to release pose.
            high=np.linalg.norm(config['size_mm'])/2+step['clearance_mm']+30
            add('lift',step,1.,target_origin_mm=[0,0,float(high)])
            add('orient',step,1.,target_xyz_deg=step['fixed_xyz_deg'])
            corners=np.array([[x,y,z] for x in (-1,1) for y in (-1,1) for z in (-1,1)])*np.array(config['size_mm'])/2
            low=(corners@Rotation.from_euler('xyz',step['fixed_xyz_deg'],degrees=True).as_matrix().T)[:,2].min()
            add('lift',step,.8,target_origin_mm=[0,0,float(step['clearance_mm']-low)])
        elif family=='floor_supported':
            # Only an explicit small public y tilt. Never translate H preset labels
            # into invented apparatus motions or use their air-drop clearance.
            add('orient',step,1.,target_xyz_deg=[0,15,0],
                support_pivot_local_mm=[config['size_mm'][0]/2,0,-config['size_mm'][2]/2])
        elif family!='held_only': raise ValueError('Unsupported example family.')
        add('hold',step,.2)
        if family!='held_only':
            add('release',step,.002);add('free_motion',step,.008);add('contact',step,.1);add('settle',step,.3)
    result=envelope('RobotExecutionPlan',profile_id='public-'+family+'-v1',
        source=dict(kind='public_synthetic_fixture',id='pub07-virtual-v1'),applicability_hash=applicability(config),
        test_type='H' if family=='floor_supported' else 'G' if family=='airborne' else 'unknown',
        type_source='virtual-fixture-not-experimental',handling_family=family,
        attachment_face=attachment_face,endpoint='sphere-minus-local-z',
        physics=dict(gripper_mass_kg=max(1.,config['physics_profile']['mass_kg']),
            gripper_inertia_kg_m2=(max(1.,config['physics_profile']['mass_kg'])/12*
                (np.sum((np.array(config['size_mm'])/1000)**2)-(np.array(config['size_mm'])/1000)**2)).tolist(),radius_mm=5.,
            drive_timeconst_s=.01,attach_timeconst_s=.02,torque_scale_m=1.,contact_margin_mm=0.,solver_iterations=100),
        transition=dict(distance_mm=2.,normal_deg=5.,relative_speed_mm_s=30.,relative_spin_rad_s=.2,
            position_mm=5.,attitude_deg=3.,rest_speed_mm_s=15.,rest_spin_rad_s=.15,
            dwell_s=.15,timeout_s=3.,retries=1,penetration_mm=3.),phases=phases,
        completion_policy='partial' if family=='held_only' else 'complete',selected_step_ids=list(selected_step_ids),
        omitted_step_ids=[s['step_id'] for s in all_steps if s['step_id'] not in selected_step_ids])
    return validate_plan(result,config)


def with_example(config, **settings):
    result=deepcopy(config); result['sequence_profile']['execution_plan']=example_plan(result,**settings)
    return result
