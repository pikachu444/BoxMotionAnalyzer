"""PUB06 source declarations. Analysis never reads full simulation truth.

The public projection carries settings and their identities, not sampled poses,
release velocities, injected fault windows, or phase/contact labels.
"""
from copy import deepcopy
import json
import math
import re

from src.utils.marker_profile_identity import envelope, validate_envelope, digest, canonical

FIELD = 'SimulationMetadataJson'
GENERATOR_VERSION = 'pub06-simulation-contract-v1'
ROBOT_GENERATOR_VERSION = 'pub07-dynamic-gripper-v1'
COORDINATE_POLICY = 'world-y-up-box-local-fixed-center-v1'
TRANSFORM = [[1.,0.,0.],[0.,0.,1.],[0.,-1.,0.]]
UNITS = dict(position='mm',time='s',rotation='rotation-matrix-local-to-world',
    linear_velocity='mm/s',angular_velocity='rad/s')


def _sealed(kind, **values):
    result=envelope(kind,**values);result['content_hash']=digest(result)
    return result


def _validate_seal(value,kind):
    validate_envelope(value,kind)
    if value.get('content_hash')!=digest({k:v for k,v in value.items() if k!='content_hash'}):
        raise ValueError('Stale simulation metadata identity.')


def _hash(value,label):
    if not isinstance(value,str) or re.fullmatch('[0-9a-f]{64}',value) is None:
        raise ValueError(f'{label} must be a SHA-256 identity.')


def _finite(value,label):
    if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value):
        raise ValueError(f'{label} must be finite.')


def public_configuration(config):
    """Declared inputs only. Corruption event times/axes are evaluation-only."""
    from src.simulation.mode_profiles import validate_config
    validate_config(config)
    sequence,physics,observation=(config[key] for key in
        ('sequence_profile','physics_profile','observation_profile'))
    marker=observation['marker']
    identity=marker['identity']
    return dict(size_mm=deepcopy(config['size_mm']),
        sequence_profile=deepcopy(sequence), physics_profile=deepcopy(physics),
        observation_profile=envelope('SimulationObservationDeclaration',profile_id=observation['profile_id'],model=observation['model'],
            units=observation['units'],source=deepcopy(observation['source']),
            corner=deepcopy(observation['corner']), marker=dict(profile_id=marker['profile']['profile_id'],
                profile_hash=identity['profile_hash'],geometry_hash=identity['geometry_hash'],
                semantic_hash=identity['semantic_hash'],observation_mapping_hash=identity['observation_mapping_hash'],
                settings_hash=digest(marker['faults']),seed=marker['seed'],corruption_details='evaluation-only')),
        requested_duration_s=config['duration_s'])


def build_metadata(config,engine,history,*,route,run_id):
    """Snapshot actual compiled engine settings once, outside the record loop."""
    import mujoco
    import numpy as np
    from src.simulation.mode_profiles import require_executable
    require_executable(config)
    if route not in ('direct_proc','marker_csv'):raise ValueError('Unsupported simulation output route.')
    if not isinstance(run_id,str) or not run_id.strip():raise ValueError('Simulation source run ID is required.')
    if not history:raise ValueError('Simulation history is empty.')
    times=np.asarray([row['time'] for row in history],dtype=float)
    if not np.isfinite(times).all() or np.any(np.diff(times)<=0):
        raise ValueError('Actual engine times must be finite and strictly increasing.')
    size=(np.asarray(engine.size_m)*2000).tolist()
    physics=config['physics_profile']
    if (not np.allclose(size,config['size_mm'],rtol=0,atol=1e-9) or engine.mass!=physics['mass_kg'] or engine.friction!=physics['friction']
            or engine.elasticity!=physics['contact_damping_control']
            or not np.allclose(np.asarray(engine.com_offset)*1000,physics['com_offset_mm'],rtol=0,atol=1e-12)):
        raise ValueError('Actual engine configuration does not match the captured source settings.')
    from scipy.spatial.transform import Rotation
    step=config['sequence_profile']['steps'][0]
    expected_rotation=Rotation.from_euler('xyz',step['fixed_xyz_deg'],degrees=True).as_matrix()
    quaternion=np.asarray(engine.init_quat,dtype=float)
    actual_rotation=Rotation.from_quat(quaternion[[1,2,3,0]]).as_matrix()
    corners=np.asarray([[-1,-1,-1],[1,-1,-1],[1,1,-1],[-1,1,-1],
        [-1,-1,1],[1,-1,1],[1,1,1],[-1,1,1]])*np.asarray(size)/2
    initial_position=[0.,0.,step['clearance_mm']-(corners@expected_rotation.T)[:,2].min()]
    if config['mode']=='single_drop' and (times[0]!=0 or not np.allclose(actual_rotation,expected_rotation,rtol=0,atol=1e-12)
            or not np.allclose(history[0]['RotationMatrix'],expected_rotation,rtol=0,atol=1e-12)
            or not np.allclose(history[0]['BodyOrigin'],initial_position,rtol=0,atol=1e-9)):
        raise ValueError('Initial recorded release differs from the captured drop settings.')
    robot=config['mode']=='robot_sequence'
    if robot:
        from src.simulation.robot_evaluation import evaluate_sequence
        if getattr(engine,'config',None)!=config:raise ValueError('Actual sequence source configuration differs.')
        if getattr(engine,'plan',None)!=config['sequence_profile']['execution_plan']:
            raise ValueError('Executed plan differs from the captured source configuration.')
        result=evaluate_sequence(engine.sequence_evidence,config['sequence_profile']['execution_plan'],
            history=history,configuration_hash=digest(config))
        if result['status']=='failed':raise ValueError('Sequence continuity/coverage failed: '+str(result['errors']))
    body=mujoco.mj_name2id(engine.model,mujoco.mjtObj.mjOBJ_BODY,'box')
    geometry=mujoco.mj_name2id(engine.model,mujoco.mjtObj.mjOBJ_GEOM,'box_geom')
    floor=mujoco.mj_name2id(engine.model,mujoco.mjtObj.mjOBJ_GEOM,'floor')
    configuration=public_configuration(config)
    clock=dict(field='Info/Time/Time' if route=='direct_proc' else 'Time',units='s',
        semantics='actual-engine-clock',frame_semantics='recorded-sample-index-not-seconds',
        samples=len(times),first_s=float(times[0]),last_s=float(times[-1]),
        interval_min_s=float(np.diff(times).min()) if len(times)>1 else None,
        interval_max_s=float(np.diff(times).max()) if len(times)>1 else None,
        interval_status='available' if len(times)>1 else 'unavailable-single-sample',
        recorded_time_hash=digest(times.tolist()))
    transforms=dict(coordinate_policy=COORDINATE_POLICY,engine_world='right-handed-z-up',
        output_world='right-handed-y-up',engine_to_output_world=deepcopy(TRANSFORM),
        rotation_policy='R_output=A@R_engine;local-basis-unchanged',
        body_origin_to_geocenter_mm=[0.,0.,0.],body_origin_to_com_mm=list(physics['com_offset_mm']),
        position_policy='p_geocenter=p_origin+R@offset; p_com=p_origin+R@com_offset',
        velocity_policy='v_point=v_origin+omega_world cross (R@offset)',units=deepcopy(UNITS),
        legacy_alias='Position/CoM is body-origin/geocenter; Simulation/InertialCOM is inertial COM')
    seed=config['observation_profile']['corner']['seed'] if route=='direct_proc' else config['observation_profile']['marker']['seed']
    public=_sealed('SimulationSourceMetadata',mode=config['mode'],source=dict(kind='mujoco_synthetic',run_id=run_id),
        generator=dict(name='mujoco',version=ROBOT_GENERATOR_VERSION if robot else GENERATOR_VERSION,engine_version=mujoco.__version__),
        route=route,seed=seed,configuration=configuration,configuration_hash=digest(configuration),
        clock=clock,transforms=transforms,release_state_status='evaluation-only',calibration_status='uncalibrated')
    if robot:
        public['execution_status']=engine.sequence_evidence['completion']
        public['content_hash']=digest({k:v for k,v in public.items() if k!='content_hash'})
    def contact(index):
        return dict(condim=int(engine.model.geom_condim[index]),friction=engine.model.geom_friction[index].tolist(),
            solref=engine.model.geom_solref[index].tolist(),solimp=engine.model.geom_solimp[index].tolist(),
            margin_m=float(engine.model.geom_margin[index]))
    # Initial release state is captured by the recorder before any integration;
    # it is never reconstructed from finite-interval derivative columns.
    initial=history[0]
    release=dict(status='recorded' if 'OriginLinearVelocityWorld' in initial else 'unavailable',
        reason=None if 'OriginLinearVelocityWorld' in initial else 'History has no instantaneous velocity snapshot.',
        engine_time_s=float(times[0]),body_origin_mm=np.asarray(initial['BodyOrigin']).tolist(),
        com_mm=np.asarray(initial['COM']).tolist(),rotation_matrix=np.asarray(initial['RotationMatrix']).tolist(),
        world_frame='mujoco-z-up',linear_velocity_units='mm/s',angular_velocity_units='rad/s',
        origin_linear_velocity_world=np.asarray(initial['OriginLinearVelocityWorld']).tolist() if 'OriginLinearVelocityWorld' in initial else None,
        angular_velocity_world=np.asarray(initial['AngularVelocityWorld']).tolist() if 'AngularVelocityWorld' in initial else None,
        angular_velocity_body=np.asarray(initial['AngularVelocityBody']).tolist() if 'AngularVelocityBody' in initial else None)
    if robot:
        release.update(status='unavailable',reason='Robot starts supported; actual releases are recorded in evaluation-only sequence_evidence.',
            origin_linear_velocity_world=None,angular_velocity_world=None,angular_velocity_body=None)
    full=_sealed('SimulationMetadata',public=public,source_configuration=deepcopy(config),
        source_configuration_hash=digest(config),compiled_physics=dict(timestep_s=float(engine.model.opt.timestep),
            gravity_m_s2=engine.model.opt.gravity.tolist(),mass_kg=float(engine.model.body_mass[body]),
            inertia_kg_m2=engine.model.body_inertia[body].tolist(),
            inertia_orientation_wxyz=engine.model.body_iquat[body].tolist(),box=contact(geometry),floor=contact(floor)),
        release_state=release,observation_config=deepcopy(config['observation_profile']),
        truth_access='direct simulation/evaluation only; never analysis input')
    if robot:
        full['sequence_evidence']=deepcopy(engine.sequence_evidence)
        grip=mujoco.mj_name2id(engine.model,mujoco.mjtObj.mjOBJ_BODY,'gripper')
        geom=mujoco.mj_name2id(engine.model,mujoco.mjtObj.mjOBJ_GEOM,'gripper_geom')
        drive=mujoco.mj_name2id(engine.model,mujoco.mjtObj.mjOBJ_EQUALITY,'drive')
        attach=mujoco.mj_name2id(engine.model,mujoco.mjtObj.mjOBJ_EQUALITY,'attachment')
        full['compiled_physics']['robot']=dict(gripper_mass_kg=float(engine.model.body_mass[grip]),
            gripper_inertia_kg_m2=engine.model.body_inertia[grip].tolist(),radius_mm=float(engine.model.geom_size[geom,0]*1000),
            drive_timeconst_s=float(engine.model.eq_solref[drive,0]),attach_timeconst_s=float(engine.model.eq_solref[attach,0]),
            torque_scale_m=float(engine.model.eq_data[attach,10]),contact_margin_mm=float(engine.model.geom_margin[geometry]*1000),
            solver_iterations=int(engine.model.opt.iterations))
        full['content_hash']=digest({k:v for k,v in full.items() if k!='content_hash'})
    validate_full(full)
    return full


def validate_public(value,artifact=None):
    if isinstance(value,str):value=json.loads(value)
    _validate_seal(value,'SimulationSourceMetadata')
    from src.simulation.mode_profiles import MODES,validate_step,number,vector,seed,_text,_profile
    expected={'schema_version','plan_spec','object_type','content_hash','mode','source','generator',
        'route','seed','configuration','configuration_hash','clock','transforms','release_state_status','calibration_status'}
    robot=value.get('mode')=='robot_sequence'
    if robot:expected.add('execution_status')
    if set(value)!=expected:raise ValueError('Unexpected simulation source fields; truth is not analysis metadata.')
    if value.get('mode') not in MODES:raise ValueError('Unsupported simulation metadata mode.')
    if robot and value.get('execution_status') not in ('completed','partial','cancelled','time_limit','failure'):
        raise ValueError('Invalid sequence execution status.')
    source=value.get('source')
    if (not isinstance(source,dict) or set(source)!={'kind','run_id'} or source.get('kind')!='mujoco_synthetic'
            or not isinstance(source.get('run_id'),str) or not source['run_id'].strip()):
        raise ValueError('Simulation source identity is required.')
    if value.get('route') not in ('direct_proc','marker_csv') or value.get('calibration_status')!='uncalibrated':
        raise ValueError('Unsupported simulation route/calibration declaration.')
    generator=value.get('generator')
    if (not isinstance(generator,dict) or set(generator)!={'name','version','engine_version'}
            or generator.get('name')!='mujoco' or generator.get('version')!=(ROBOT_GENERATOR_VERSION if robot else GENERATOR_VERSION)):
        raise ValueError('Unsupported simulation generator/version.')
    _text(generator.get('engine_version'),'Engine version')
    if type(value.get('seed')) is not int or not 0<=value['seed']<=2147483647:raise ValueError('Invalid simulation seed.')
    config=value.get('configuration')
    if not isinstance(config,dict) or value.get('configuration_hash')!=digest(config):
        raise ValueError('Stale simulation configuration identity.')
    vector(config.get('size_mm'),'Simulation dimensions',minimum=10,maximum=5000)
    if set(config)!={'size_mm','sequence_profile','physics_profile','observation_profile','requested_duration_s'}:
        raise ValueError('Unexpected simulation configuration declaration.')
    number(config.get('requested_duration_s'),'Duration',minimum=.5,maximum=60)
    sequence=config.get('sequence_profile');_profile(sequence,'SimulationSequenceProfile')
    if set(sequence)-({'execution_plan'} if robot else set())!={'schema_version','plan_spec','object_type','profile_id','source','mode','robot_model','steps'}:
        raise ValueError('Unexpected sequence declaration.')
    if sequence.get('mode')!=value['mode'] or sequence.get('robot_model')!=(None if value['mode']=='single_drop' else 'gripper_proxy'):
        raise ValueError('Simulation sequence/mode mismatch.')
    if (not isinstance(sequence.get('steps'),list) or not sequence['steps']
            or value['mode']=='single_drop' and len(sequence['steps'])!=1):raise ValueError('Planned drops are required for the declared mode.')
    for step in sequence['steps']:validate_step(step)
    if len({step['step_id'] for step in sequence['steps']})!=len(sequence['steps']):raise ValueError('Duplicate planned drop identity.')
    if robot:
        from src.simulation.robot_profiles import validate_plan
        validate_plan(sequence.get('execution_plan'),dict(size_mm=config['size_mm'],
            sequence_profile=sequence,physics_profile=config['physics_profile']))
    physics=config.get('physics_profile');_profile(physics,'SimulationPhysicsProfile')
    if set(physics)!={'schema_version','plan_spec','object_type','profile_id','source','units','model','mass_kg','friction','contact_damping_control','com_offset_mm'}:
        raise ValueError('Unexpected physics declaration.')
    if physics.get('units')!='kg-mm' or physics.get('model')!='legacy-cuboid-contact-v1':raise ValueError('Unsupported simulation physics.')
    number(physics.get('mass_kg'),'Mass',minimum=.1,maximum=10000)
    number(physics.get('friction'),'Friction',minimum=0,maximum=5)
    number(physics.get('contact_damping_control'),'Contact damping',minimum=0,maximum=1)
    vector(physics.get('com_offset_mm'),'COM offset',minimum=-2500,maximum=2500)
    observation=config.get('observation_profile')
    _profile(observation,'SimulationObservationDeclaration')
    if not isinstance(observation,dict) or observation.get('model')!='existing-corner-and-marker-v1' or observation.get('units')!='mm-s':
        raise ValueError('Unsupported simulation observation model/units.')
    if set(observation)!={'schema_version','plan_spec','object_type','profile_id','model','units','source','corner','marker'}:
        raise ValueError('Unexpected observation declaration; fault truth is evaluation-only.')
    corner=observation.get('corner')
    if not isinstance(corner,dict) or set(corner)!={'enabled','std_mm','seed'} or type(corner.get('enabled')) is not bool:
        raise ValueError('Invalid corner noise declaration.')
    number(corner.get('std_mm'),'Corner noise',minimum=.01,maximum=100);seed(corner.get('seed'))
    marker=observation.get('marker')
    if not isinstance(marker,dict) or marker.get('corruption_details')!='evaluation-only':raise ValueError('Simulation observation truth isolation is required.')
    if set(marker)!={'profile_id','profile_hash','geometry_hash','semantic_hash','observation_mapping_hash','settings_hash','seed','corruption_details'}:
        raise ValueError('Unexpected marker declaration; injected fault details are evaluation-only.')
    _text(marker.get('profile_id'),'Marker profile ID');seed(marker.get('seed'))
    if value['seed']!=(corner['seed'] if value['route']=='direct_proc' else marker['seed']):raise ValueError('Simulation output seed mismatch.')
    for key in ('profile_hash','geometry_hash','semantic_hash','observation_mapping_hash','settings_hash'):_hash(marker.get(key),'Marker '+key)
    transforms=value.get('transforms')
    if (not isinstance(transforms,dict) or set(transforms)!={'coordinate_policy','engine_world','output_world',
            'engine_to_output_world','rotation_policy','body_origin_to_geocenter_mm','body_origin_to_com_mm',
            'position_policy','velocity_policy','units','legacy_alias'} or transforms.get('coordinate_policy')!=COORDINATE_POLICY
            or transforms.get('engine_world')!='right-handed-z-up' or transforms.get('output_world')!='right-handed-y-up'
            or transforms.get('engine_to_output_world')!=TRANSFORM or transforms.get('units')!=UNITS
            or transforms.get('rotation_policy')!='R_output=A@R_engine;local-basis-unchanged'
            or transforms.get('body_origin_to_geocenter_mm')!=[0.,0.,0.]
            or transforms.get('body_origin_to_com_mm')!=physics['com_offset_mm']
            or transforms.get('position_policy')!='p_geocenter=p_origin+R@offset; p_com=p_origin+R@com_offset'
            or transforms.get('velocity_policy')!='v_point=v_origin+omega_world cross (R@offset)'
            or transforms.get('legacy_alias')!='Position/CoM is body-origin/geocenter; Simulation/InertialCOM is inertial COM'):
        raise ValueError('Unsupported simulation units/frame/origin transforms.')
    for row in transforms['engine_to_output_world']:vector(row,'World transform')
    vector(transforms['body_origin_to_geocenter_mm'],'Geocenter offset')
    clock=value.get('clock')
    if (not isinstance(clock,dict) or set(clock)!={'field','units','semantics','frame_semantics','samples','first_s',
            'last_s','interval_min_s','interval_max_s','interval_status','recorded_time_hash'}
            or clock.get('semantics')!='actual-engine-clock' or clock.get('units')!='s'
            or clock.get('frame_semantics')!='recorded-sample-index-not-seconds'
            or clock.get('field')!=('Time' if value['route']=='marker_csv' else 'Info/Time/Time')
            or type(clock.get('samples')) is not int or clock['samples']<1):
        raise ValueError('Unsupported simulation time/frame meaning.')
    _hash(clock.get('recorded_time_hash'),'Recorded time')
    for key in ('first_s','last_s'):_finite(clock.get(key),'Engine '+key)
    if clock['first_s']<0 or clock['last_s']<clock['first_s'] or (clock['samples']>1 and clock['last_s']==clock['first_s']):
        raise ValueError('Invalid simulation clock bounds.')
    if clock['samples']>1:
        for key in ('interval_min_s','interval_max_s'):
            number(clock.get(key),'Recording interval',minimum=0)
            if clock[key]<=0:raise ValueError('Recording interval must be positive.')
        if clock['interval_min_s']>clock['interval_max_s'] or clock['interval_status']!='available':raise ValueError('Invalid recording interval declaration.')
        span=clock['last_s']-clock['first_s'];intervals=clock['samples']-1
        slack=max(1e-12,abs(span)*1e-12)
        if not intervals*clock['interval_min_s']-slack<=span<=intervals*clock['interval_max_s']+slack:
            raise ValueError('Recording interval summary conflicts with span/sample count.')
    elif clock.get('interval_status')!='unavailable-single-sample' or clock.get('interval_min_s') is not None or clock.get('interval_max_s') is not None:
        raise ValueError('Single sample cannot declare an interval.')
    elif clock['first_s']!=clock['last_s']:raise ValueError('Single sample clock bounds must be equal.')
    if value.get('release_state_status')!='evaluation-only':raise ValueError('Release truth cannot enter analysis metadata.')
    if artifact is not None:
        if artifact.get('SourceKind')!=source['kind']:raise ValueError('Simulation/artifact source kind mismatch.')
        expected_units='bma-mm-s-rotvec-rad-summary-deg-v1' if value['route']=='marker_csv' else 'mm-s-rotvec-rad-global-angular-v1'
        if artifact.get('CoordinatePolicy')!=COORDINATE_POLICY or artifact.get('UnitsPolicy')!=expected_units:
            raise ValueError('Simulation/artifact coordinates/units policy mismatch.')
        dimensions=[artifact.get(key) for key in ('BoxLengthMm','BoxWidthMm','BoxHeightMm')]
        for dimension in dimensions:number(dimension,'Artifact dimension',minimum=10,maximum=5000)
        if any(abs(a-b)>1e-9 for a,b in zip(dimensions,config['size_mm'])):
            raise ValueError('Simulation/artifact geometry mismatch.')
        if value['route']=='marker_csv' and (artifact.get('MarkerLayoutId')!=marker.get('profile_id') or artifact.get('MarkerLayoutHash')!=marker['profile_hash']):
            raise ValueError('Simulation/artifact marker source mismatch.')
        if value['route']=='marker_csv':
            from src.utils.marker_profile_identity import artifact_identity
            identity=artifact_identity(artifact)
            if identity is None or any(identity[key]!=marker[key] for key in
                    ('profile_hash','geometry_hash','semantic_hash','observation_mapping_hash')):
                raise ValueError('Simulation/artifact marker interpretation identity mismatch.')
    return value


def validate_full(value):
    """Validate evaluation output without granting any analysis/trial approval."""
    import numpy as np
    from src.simulation.mode_profiles import require_executable,number,vector
    _validate_seal(value,'SimulationMetadata')
    public=validate_public(value.get('public'))
    config=value.get('source_configuration');require_executable(config)
    if config['mode']=='robot_sequence':
        from src.simulation.robot_evaluation import evaluate_sequence
        result=evaluate_sequence(value.get('sequence_evidence'),config['sequence_profile']['execution_plan'],configuration_hash=digest(config))
        if result['status'] in ('failed','unavailable'):raise ValueError('Invalid/missing sequence evidence.')
        if value['sequence_evidence']['completion']!=public['execution_status']:raise ValueError('Sequence status differs from public output status.')
    requested=value.get('requested_source_configuration')
    if requested is not None:
        require_executable(requested)
        effective=deepcopy(requested);effective['size_mm']=deepcopy(config['size_mm'])
        marker=requested['observation_profile']['marker']
        if (public['route']!='marker_csv' or effective!=config
                or config['size_mm']!=marker['profile']['box_dims_mm']
                or requested['size_mm']!=config['size_mm'] and not marker['use_layout_box']):
            raise ValueError('Requested/effective marker geometry lineage mismatch.')
    if value.get('source_configuration_hash')!=digest(config) or public_configuration(config)!=public['configuration'] or config['mode']!=public['mode']:
        raise ValueError('Simulation full/public source identity mismatch.')
    if value.get('observation_config')!=config['observation_profile'] or value.get('truth_access')!='direct simulation/evaluation only; never analysis input':
        raise ValueError('Simulation observation/truth access mismatch.')
    compiled=value.get('compiled_physics')
    if not isinstance(compiled,dict):raise ValueError('Compiled physics is required.')
    number(compiled.get('timestep_s'),'Engine timestep',minimum=0)
    if compiled['timestep_s']<=0:raise ValueError('Engine timestep must be positive.')
    number(compiled.get('mass_kg'),'Compiled mass',minimum=.1,maximum=10000)
    if compiled['mass_kg']!=config['physics_profile']['mass_kg']:raise ValueError('Compiled mass differs.')
    for field in ('gravity_m_s2','inertia_kg_m2'):vector(compiled.get(field),'Compiled '+field)
    if min(compiled['inertia_kg_m2'])<=0:raise ValueError('Compiled inertia must be positive.')
    if config['mode']=='robot_sequence':
        expected=config['sequence_profile']['execution_plan']['physics']
        actual=compiled.get('robot')
        if (not isinstance(actual,dict) or set(actual)!=set(expected)
                or any(not np.allclose(actual[key],expected[key],rtol=0,atol=1e-12) for key in expected)
                or compiled['timestep_s']!=.002 or compiled['gravity_m_s2']!=[0.,0.,-9.81]):
            raise ValueError('Compiled dynamic gripper physics differs from its execution profile.')
    quat=np.asarray(compiled.get('inertia_orientation_wxyz'),dtype=float)
    if quat.shape!=(4,) or not np.isfinite(quat).all() or abs(np.linalg.norm(quat)-1)>1e-10:raise ValueError('Invalid compiled inertia orientation.')
    for key in ('box','floor'):
        contact=compiled.get(key)
        if not isinstance(contact,dict) or contact.get('condim')!=4:raise ValueError('Unsupported compiled contact model.')
        for field,length in (('friction',3),('solref',2),('solimp',5)):
            array=np.asarray(contact.get(field),dtype=float)
            if array.shape!=(length,) or not np.isfinite(array).all():raise ValueError('Invalid compiled '+field)
        number(contact.get('margin_m'),'Contact margin',minimum=0)
    release=value.get('release_state')
    if (not isinstance(release,dict) or release.get('status') not in ('recorded','unavailable')
            or release.get('world_frame')!='mujoco-z-up' or release.get('linear_velocity_units')!='mm/s'
            or release.get('angular_velocity_units')!='rad/s' or release.get('engine_time_s')!=public['clock']['first_s']):
        raise ValueError('Unsupported release state frame/time/units.')
    for field in ('body_origin_mm','com_mm'):vector(release.get(field),'Release '+field)
    rotation=np.asarray(release.get('rotation_matrix'),dtype=float)
    if (rotation.shape!=(3,3) or not np.isfinite(rotation).all()
            or not np.allclose(rotation.T@rotation,np.eye(3),rtol=0,atol=1e-10)
            or abs(np.linalg.det(rotation)-1)>1e-10):raise ValueError('Release rotation must be proper.')
    expected=np.asarray(release['body_origin_mm'])+rotation@config['physics_profile']['com_offset_mm']
    if not np.allclose(release['com_mm'],expected,rtol=0,atol=1e-9):raise ValueError('Release origin/COM transform mismatch.')
    velocities=('origin_linear_velocity_world','angular_velocity_world','angular_velocity_body')
    if release['status']=='recorded':
        if release.get('reason') is not None:raise ValueError('Recorded release cannot have an unavailable reason.')
        for field in velocities:vector(release.get(field),'Release '+field)
        if not np.allclose(release['angular_velocity_world'],rotation@release['angular_velocity_body'],rtol=0,atol=1e-10):
            raise ValueError('Release world/body angular velocity mismatch.')
    elif not release.get('reason') or any(release.get(field) is not None for field in velocities):
        raise ValueError('Unavailable release velocities must remain unknown with a reason.')
    return value


def artifact_simulation(artifact):
    declaration=artifact.get(FIELD)
    return None if declaration is None or declaration=='' else validate_public(declaration,artifact)


def validate_recorded_times(declaration,times,*,complete=False):
    """Full records bind every timestamp; slices keep original source bounds."""
    import numpy as np
    values=np.asarray(times,dtype=float);clock=declaration['clock']
    if (values.ndim!=1 or not len(values) or not np.isfinite(values).all() or np.any(np.diff(values)<=0)
            or values[0]<clock['first_s']-1e-12 or values[-1]>clock['last_s']+1e-12):
        raise ValueError('Timestamps conflict with the declared simulation engine clock.')
    if complete or len(values)==clock['samples']:
        if (len(values)!=clock['samples'] or digest(values.tolist())!=clock['recorded_time_hash']
                or values[0]!=clock['first_s'] or values[-1]!=clock['last_s']):
            raise ValueError('Recorded timestamps differ from the declared simulation clock identity.')
        if len(values)>1 and (abs(float(np.diff(values).min())-clock['interval_min_s'])>1e-12
                or abs(float(np.diff(values).max())-clock['interval_max_s'])>1e-12):
            raise ValueError('Recorded timestamp intervals differ from the simulation clock.')


def validate_history_binding(metadata,history,*,times=None):
    """Opt-in metadata must describe actual history at the export boundary."""
    import numpy as np
    validate_full(metadata)
    if not history:raise ValueError('Simulation history is empty.')
    validate_recorded_times(metadata['public'],times if times is not None else [row['time'] for row in history],complete=True)
    release=metadata['release_state'];initial=history[0]
    from scipy.spatial.transform import Rotation
    quaternion=np.asarray(initial.get('QuaternionWXYZ'),dtype=float)
    if quaternion.shape!=(4,) or not np.isfinite(quaternion).all() or np.linalg.norm(quaternion)==0:
        raise ValueError('Export history release quaternion is invalid.')
    rotation=Rotation.from_quat(quaternion[[1,2,3,0]]).as_matrix()
    if not np.allclose(rotation,release['rotation_matrix'],rtol=0,atol=1e-12):
        raise ValueError('Export history release quaternion differs from metadata.')
    for field,key in (('body_origin_mm','BodyOrigin'),('com_mm','COM'),('rotation_matrix','RotationMatrix')):
        actual=np.asarray(initial.get(key),dtype=float);expected=np.asarray(release[field])
        if actual.shape!=expected.shape or not np.allclose(actual,expected,rtol=0,atol=1e-9):
            raise ValueError('Export history release snapshot differs from metadata.')
    if release['status']=='recorded':
        for field,key in (('origin_linear_velocity_world','OriginLinearVelocityWorld'),
                ('angular_velocity_world','AngularVelocityWorld'),('angular_velocity_body','AngularVelocityBody')):
            actual=np.asarray(initial.get(key),dtype=float)
            if actual.shape!=(3,) or not np.allclose(actual,release[field],rtol=0,atol=1e-12):
                raise ValueError('Export history release velocity differs from metadata.')


def compatibility_reasons(before,after):
    a,b=artifact_simulation(before),artifact_simulation(after)
    if a is None and b is None:return []  # Existing legacy eligibility is unchanged; mode stays unknown.
    if a is None or b is None:return ['Simulation mode/profile contract unavailable in one source; no inferred legacy equivalence']
    reasons=[]
    if a['mode']!=b['mode']:reasons.append('Simulation mode differs')
    for key in ('sequence_profile','physics_profile','observation_profile'):
        left,right=deepcopy(a['configuration'][key]),deepcopy(b['configuration'][key])
        # Seeds/run IDs/clock/generator builds identify evidence, not repeated settings.
        if key=='observation_profile':
            left['corner'].pop('seed',None);right['corner'].pop('seed',None)
            left['marker'].pop('seed',None);right['marker'].pop('seed',None)
            for value in (left,right):
                value['marker'].pop('profile_id',None);value['marker'].pop('profile_hash',None)
        if left!=right:reasons.append('Simulation '+key.replace('_',' ')+' differs')
    if a['transforms']!=b['transforms']:reasons.append('Simulation transforms differ')
    return reasons
