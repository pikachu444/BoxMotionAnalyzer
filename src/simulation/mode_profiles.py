"""PUB06 settings-only mode profiles; robot execution belongs to PUB07.

No truth or observation data is stored in a settings document. Existing marker
documents and canonical author hashes are preserved, including pending edits.
"""
from copy import deepcopy
from datetime import datetime, timezone
import json
import math
from numbers import Real
import os
from pathlib import Path
import tempfile

from src.utils.marker_profile_identity import (envelope, validate_envelope,
    canonical, digest, profile_identity, validate_identity)
from .marker_fixtures import load_profile
from .profile_document import ProfileEditorState
from .scenarios import Scenarios

MODES = ('single_drop', 'robot_sequence')
BLOCKED_REASON = 'Robot sequence cannot run: attach, pickup and release engine requires #140.'
ATTITUDE_POLICY = 'mujoco-world-z-up-extrinsic-xyz-degrees'


def number(value, label, *, minimum=None, maximum=None):
    if isinstance(value, bool) or not isinstance(value, Real) or not math.isfinite(value):
        raise ValueError(f'{label} must be finite.')
    if minimum is not None and value < minimum or maximum is not None and value > maximum:
        raise ValueError(f'{label} is outside its supported range.')
    return value


def vector(value, label, *, minimum=None, maximum=None):
    if not isinstance(value, (list, tuple)) or len(value) != 3:
        raise ValueError(f'{label} must contain three values.')
    for component in value: number(component, label, minimum=minimum, maximum=maximum)


def seed(value):
    if type(value) is not int or not 0 <= value <= 2147483647:
        raise ValueError('Seed must be a nonnegative 32-bit integer.')


def _text(value, label):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f'{label} is required.')


def _profile(value, kind):
    validate_envelope(value, kind)
    _text(value.get('profile_id'), 'Profile ID')
    source = value.get('source')
    if not isinstance(source, dict) or set(source) != {'kind','id'} or source.get('kind') != 'synthetic_configuration':
        raise ValueError('A synthetic configuration source is required.')
    _text(source.get('id'), 'Profile source ID')


def profile(kind, profile_id, **settings):
    return envelope(kind, profile_id=profile_id,
        source=dict(kind='synthetic_configuration', id='public-default-v1'), **settings)


def drop_step(category, preset_id, clearance_mm, fixed_xyz_deg, *, step_id='drop-1'):
    return envelope('PlannedDrop', step_id=step_id, category=category,
        preset_id=preset_id, clearance_mm=clearance_mm, fixed_xyz_deg=list(fixed_xyz_deg),
        attitude_policy=ATTITUDE_POLICY)


def validate_step(step):
    validate_envelope(step, 'PlannedDrop')
    if set(step)!={'schema_version','plan_spec','object_type','step_id','category','preset_id','clearance_mm','fixed_xyz_deg','attitude_policy'}:
        raise ValueError('Unexpected planned drop fields.')
    _text(step.get('step_id'), 'Drop ID')
    if step.get('category') not in Scenarios.get_categories():
        raise ValueError('Unknown preset category.')
    if step.get('preset_id') not in {item.id for item in Scenarios.get_drop_sequence_specs(step['category'])}:
        raise ValueError('Unknown preset ID in selected category.')
    if step.get('attitude_policy') != ATTITUDE_POLICY:
        raise ValueError('Unsupported initial attitude frame or units.')
    number(step.get('clearance_mm'), 'Drop clearance', minimum=10, maximum=10000)
    vector(step.get('fixed_xyz_deg'), 'Fixed XYZ degrees', minimum=-180, maximum=180)


def validate_config(config):
    validate_envelope(config, 'SimulationModeConfiguration')
    if set(config)-{'initial_condition','contact_profile'}!={'schema_version','plan_spec','object_type','mode','size_mm','sequence_profile','physics_profile','observation_profile','duration_s','show_viewer'}:
        raise ValueError('Unexpected simulation configuration fields.')
    if 'initial_condition' in config or 'contact_profile' in config:
        from .initial_conditions import validate_seed, validate_profile
        if config['mode'] != 'single_drop': raise ValueError('PUB09 initial conditions/profiles are single-drop opt-ins.')
        if 'initial_condition' in config: validate_seed(config['initial_condition'])
        if 'contact_profile' in config:
            p = validate_profile(config['contact_profile'])
            legacy = config['physics_profile']
            if (p['mass_kg'] != legacy['mass_kg'] or p['friction'][0] != legacy['friction']
                    or p['com_offset_mm'] != legacy['com_offset_mm']):
                raise ValueError('Opt-in profile differs from captured legacy aliases.')
    mode = config.get('mode')
    if mode not in MODES:
        raise ValueError('Unsupported simulation mode.')
    vector(config.get('size_mm'), 'Box dimensions (mm)', minimum=10, maximum=5000)
    sequence, physics, observation = (config.get(field) for field in
        ('sequence_profile', 'physics_profile', 'observation_profile'))
    _profile(sequence, 'SimulationSequenceProfile')
    if set(sequence)-{'execution_plan'}!={'schema_version','plan_spec','object_type','profile_id','source','mode','robot_model','steps'}:
        raise ValueError('Unexpected sequence profile fields.')
    if sequence.get('mode') != mode or sequence.get('robot_model') != (None if mode == 'single_drop' else 'gripper_proxy'):
        raise ValueError('Sequence mode/robot model mismatch.')
    steps = sequence.get('steps')
    if not isinstance(steps, list) or not steps or mode == 'single_drop' and len(steps) != 1:
        raise ValueError('A single drop needs one entry; robot sequence needs planned drops.')
    for step in steps: validate_step(step)
    if len({step['step_id'] for step in steps}) != len(steps):
        raise ValueError('Planned drop IDs must be distinct.')
    if 'execution_plan' in sequence:
        if mode != 'robot_sequence': raise ValueError('Single drop cannot contain a robot execution plan.')
        from .robot_profiles import validate_plan
        validate_plan(sequence['execution_plan'])
    _profile(physics, 'SimulationPhysicsProfile')
    if set(physics)!={'schema_version','plan_spec','object_type','profile_id','source','units','model','mass_kg','friction','contact_damping_control','com_offset_mm'}:
        raise ValueError('Unexpected physics profile fields.')
    if physics.get('units') != 'kg-mm' or physics.get('model') != 'legacy-cuboid-contact-v1':
        raise ValueError('Unsupported physics units/model.')
    number(physics.get('mass_kg'), 'Mass', minimum=.1, maximum=10000)
    number(physics.get('friction'), 'Friction', minimum=0, maximum=5)
    number(physics.get('contact_damping_control'), 'Contact damping', minimum=0, maximum=1)
    vector(physics.get('com_offset_mm'), 'Local COM offset (mm)', minimum=-2500, maximum=2500)
    _profile(observation, 'SimulationObservationProfile')
    if set(observation)!={'schema_version','plan_spec','object_type','profile_id','source','units','model','corner','marker'}:
        raise ValueError('Unexpected observation profile fields.')
    if observation.get('units') != 'mm-s' or observation.get('model') != 'existing-corner-and-marker-v1':
        raise ValueError('Unsupported observation units/model.')
    corner, marker = observation.get('corner'), observation.get('marker')
    if not isinstance(corner, dict) or set(corner)!={'enabled','std_mm','seed'} or type(corner.get('enabled')) is not bool:
        raise ValueError('Corner noise enabled must be boolean.')
    number(corner.get('std_mm'), 'Corner noise standard deviation', minimum=.01, maximum=100)
    seed(corner.get('seed'))
    if (not isinstance(marker, dict) or set(marker)-{'observation_profile'}!={'profile','identity','document','seed','use_layout_box','faults'}
            or type(marker.get('use_layout_box')) is not bool):
        raise ValueError('Marker layout dimension choice must be boolean.')
    identity = profile_identity(marker.get('profile'))
    if 'observation_profile' in marker:
        from .observation_profile import validate_observation_profile
        observation_model = validate_observation_profile(marker['observation_profile'], marker['profile'])
        for item in observation_model['occlusions'] + observation_model['noise']:
            if not 0 <= item['start_s'] < item['end_s'] <= config['duration_s']:
                raise ValueError('Observation window must stay within captured simulation duration.')
    validate_identity(marker.get('identity'))
    if identity != marker['identity']:
        raise ValueError('Stale marker profile identity.')
    if marker.get('document') is not None:
        editor = ProfileEditorState.from_document(marker['document'])
        if editor.applied != marker['profile']:
            raise ValueError('Marker document applied profile differs from selected profile.')
    seed(marker.get('seed'))
    fault = marker.get('faults')
    if (not isinstance(fault, dict) or set(fault)!={'kind','channel','axis','start','end','std_mm'}
            or fault.get('kind') not in (None, 'missing', 'flip_180_local_axis', 'gaussian_noise')):
        raise ValueError('Unsupported marker fault kind.')
    if fault.get('channel') not in ('physical_markers', 'rigid_body_markers') or fault.get('axis') not in ('X', 'Y', 'Z'):
        raise ValueError('Unsupported marker channel/local axis.')
    if fault['kind'] == 'flip_180_local_axis' and fault['channel'] != 'rigid_body_markers':
        raise ValueError('Local half turns require solved rigid-body markers.')
    number(fault.get('start'), 'Fault start (s)', minimum=0)
    number(fault.get('end'), 'Fault end (s)', minimum=0)
    number(fault.get('std_mm'), 'Marker noise standard deviation', minimum=.001, maximum=100)
    number(config.get('duration_s'), 'Duration (s)', minimum=.5, maximum=3600 if mode=='robot_sequence' else 60)
    if fault['kind'] is not None:
        if fault['start'] > config['duration_s']:
            raise ValueError('Fault start is outside requested duration.')
        if fault['kind'] != 'flip_180_local_axis' and not fault['start'] < fault['end'] <= config['duration_s']:
            raise ValueError('Fault interval must increase within requested duration.')
    if type(config.get('show_viewer')) is not bool:
        raise ValueError('Viewer choice must be boolean.')
    return config


def default_config(mode='single_drop'):
    if mode not in MODES: raise ValueError('Unsupported simulation mode.')
    category = Scenarios.get_categories()[0]
    spec = Scenarios.get_drop_sequence_specs(category)[0]
    dimensions = [1578., 930., 142.]
    xyz = [round(float(value), 2) for value in Scenarios.get_euler_angles(spec, dimensions, category=category)]
    step = drop_step(category, spec.id, Scenarios.calculate_drop_height(category, spec, 25.), xyz)
    marker = load_profile(example='18')
    return validate_config(envelope('SimulationModeConfiguration', mode=mode, size_mm=dimensions,
        sequence_profile=profile('SimulationSequenceProfile', 'current-'+mode, mode=mode,
            robot_model=None if mode == 'single_drop' else 'gripper_proxy', steps=[step]),
        physics_profile=profile('SimulationPhysicsProfile', 'current-physics', units='kg-mm',
            model='legacy-cuboid-contact-v1', mass_kg=25., friction=.5,
            contact_damping_control=.15, com_offset_mm=[0., -200., 0.]),
        observation_profile=profile('SimulationObservationProfile', 'current-observations', units='mm-s',
            model='existing-corner-and-marker-v1', corner=dict(enabled=False, std_mm=1., seed=0),
            marker=dict(profile=marker, identity=profile_identity(marker), document=None,
                seed=74082, use_layout_box=False, faults=dict(kind=None, channel='rigid_body_markers',
                    axis='X', start=.24, end=.32, std_mm=.02))), duration_s=2., show_viewer=True))


def require_executable(config):
    validate_config(config)
    if config['mode'] != 'single_drop':
        if 'execution_plan' not in config['sequence_profile']: raise ValueError(BLOCKED_REASON)
        from .robot_profiles import validate_plan
        validate_plan(config['sequence_profile']['execution_plan'],config)


class ModeProfiles:
    """Two isolated configurations and source-bound settings change history."""
    def __init__(self):
        self.mode = 'single_drop'
        self.configs = {mode: default_config(mode) for mode in MODES}
        self.source_configs = deepcopy(self.configs)
        self.revision = 0
        self.history = []

    def set_config(self, config):
        validate_config(config)
        mode = config['mode']; previous = self.configs[mode]
        if previous == config: return
        self.revision += 1
        self.history.append(envelope('SimulationConfigurationEdit', serial=len(self.history)+1,
            utc=datetime.now(timezone.utc).isoformat(), mode=mode, revision=self.revision,
            before=deepcopy(previous), after=deepcopy(config)))
        self.configs[mode] = deepcopy(config)

    def switch(self, mode):
        if mode not in MODES: raise ValueError('Unsupported simulation mode.')
        self.mode = mode
        return deepcopy(self.configs[mode])

    def document(self):
        payload = envelope('SimulationProfilesDocument', selected_mode=self.mode,
            configs=deepcopy(self.configs), revision=self.revision, history=deepcopy(self.history),
            source_configs=deepcopy(self.source_configs), approval_status='not_evaluated')
        payload['content_hash'] = digest(payload)
        return payload

    @classmethod
    def from_document(cls, value):
        validate_envelope(value, 'SimulationProfilesDocument')
        body = {key:item for key,item in value.items() if key != 'content_hash'}
        if value.get('content_hash') != digest(body): raise ValueError('Stale simulation document identity.')
        if value.get('selected_mode') not in MODES or value.get('approval_status') != 'not_evaluated':
            raise ValueError('Unsupported simulation mode or approval status.')
        configs = value.get('configs')
        if not isinstance(configs, dict) or set(configs) != set(MODES):
            raise ValueError('Both mode configurations are required.')
        for mode, config in configs.items():
            validate_config(config)
            if mode != config['mode']: raise ValueError('Mode configuration key mismatch.')
        history = value.get('history'); revision = value.get('revision')
        if not isinstance(history, list) or type(revision) is not int or revision != len(history):
            raise ValueError('Invalid settings revision/history.')
        sources=value.get('source_configs')
        if not isinstance(sources,dict) or set(sources)!=set(MODES):raise ValueError('Settings source snapshots are required.')
        for mode,config in sources.items():
            validate_config(config)
            if config['mode']!=mode:raise ValueError('Source mode mismatch.')
        previous=deepcopy(sources)
        for index,event in enumerate(history,1):
            validate_envelope(event, 'SimulationConfigurationEdit')
            if event.get('serial') != index or event.get('revision') != index or event.get('mode') not in MODES:
                raise ValueError('Invalid settings history order/mode.')
            _text(event.get('utc'), 'Edit UTC')
            try:
                instant=datetime.fromisoformat(event['utc'])
                if instant.utcoffset() is None or instant.utcoffset().total_seconds()!=0:
                    raise ValueError('Settings edit time must be UTC.')
            except (ValueError,TypeError) as error:
                raise ValueError('Invalid settings edit UTC.') from error
            for field in ('before','after'):validate_config(event.get(field))
            mode=event['mode']
            if event['before'] != previous[mode] or event['after']['mode'] != mode:
                raise ValueError('Settings history source mismatch.')
            previous[mode]=event['after']
        if previous != configs:raise ValueError('Settings history/current configuration mismatch.')
        state=cls();state.mode=value['selected_mode'];state.configs=deepcopy(configs)
        state.source_configs=deepcopy(sources)
        state.revision=revision;state.history=deepcopy(history)
        return state


def save_profiles(path, state):
    payload=state.document();ModeProfiles.from_document(payload)
    target=Path(path); temporary=None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', newline='', dir=target.parent,
                prefix='.bma-modes-', suffix='.tmp', delete=False) as stream:
            temporary=Path(stream.name);stream.write(canonical(payload)+'\n');stream.flush();os.fsync(stream.fileno())
        os.replace(temporary,target)
    except BaseException as error:
        if temporary is not None:
            try:temporary.unlink(missing_ok=True)
            except OSError as cleanup_error:
                error.add_note(f'Could not remove temporary settings {temporary}: {cleanup_error}')
        raise


def read_profiles(path):
    return ModeProfiles.from_document(json.loads(Path(path).read_text(encoding='utf-8-sig')))
