"""Cancellable GUI orchestration of the same public marker export API."""
import copy
from pathlib import Path
import tempfile

import numpy as np

from .corruption_export import write_observations
from .engine import MuJoCoEngine
from .history_trajectory import history_to_trajectory
from .marker_fixtures import validate_profile


def fault_spec(times, settings):
    kind = settings.get('kind')
    if not kind:
        return dict(schema_version=1, events=[])
    start, end = float(settings['start']), float(settings['end'])
    times = np.asarray(times, dtype=float)
    if len(times) < 2:
        raise ValueError('Marker export needs at least two recorded samples.')
    stop = times[-1] + np.median(np.diff(times))
    if not np.isfinite([start, end]).all() or not times[0] <= start <= times[-1]:
        raise ValueError('Fault start is outside the recorded time range.')
    first = int(np.searchsorted(times, start))
    event = dict(kind=kind, channel=settings['channel'], start_index=first)
    if kind == 'flip_180_local_axis':
        event['axis'] = settings['axis']
    else:
        if not start < end <= stop + 1e-10:
            raise ValueError('Fault end must follow its start and stay within the recorded time range.')
        event['end_index_exclusive'] = int(np.searchsorted(times, end))
        if kind == 'gaussian_noise':
            event['std_mm'] = float(settings['std_mm'])
    return dict(schema_version=1, events=[event])


def generate_marker_capture(destination, profile, simulation, faults, seed, *, cancelled=None, progress=None):
    """Publish only a complete new directory; retain previous files on any failure."""
    def checkpoint():
        if cancelled is not None and cancelled():
            raise InterruptedError('Marker export cancelled.')

    def update(value, label):
        if progress is not None:
            progress(int(value), label)

    profile, simulation, faults = copy.deepcopy((profile, simulation, faults))
    validate_profile(profile)
    from .mode_profiles import require_executable,validate_config
    from src.utils.simulation_metadata import build_metadata
    from src.utils.marker_profile_identity import profile_identity
    from uuid import uuid4
    config=simulation.get('mode_config')
    if config is not None:
        require_executable(config)
        physics=config['physics_profile'];step=config['sequence_profile']['steps'][0]
        from .scenarios import Scenarios
        expected_quat=Scenarios.get_orientation_from_euler(*step['fixed_xyz_deg'])
        if 'initial_condition' in config:expected_quat=config['initial_condition']['quaternion_wxyz']
        if (simulation['mass']!=physics['mass_kg'] or simulation['friction']!=physics['friction']
                or simulation['elasticity']!=physics['contact_damping_control']
                or list(simulation['com_offset'])!=physics['com_offset_mm']
                or simulation['duration']!=config['duration_s'] or simulation['height']!=step['clearance_mm']
                or not np.allclose(simulation['quat'],expected_quat,rtol=0,atol=1e-14)):
            raise ValueError('Marker simulation settings differ from the captured configuration.')
        marker=config['observation_profile']['marker']
        if marker['profile']!=profile or marker['seed']!=seed or marker['faults']!=faults:
            raise ValueError('Marker observation settings differ from the captured configuration.')
        if list(profile['box_dims_mm'])!=config['size_mm'] and not marker['use_layout_box']:
            raise ValueError('Explicit layout dimensions are required for this marker capture.')
        # The existing marker path uses layout dimensions by explicit choice.
        # Preserve the requested snapshot separately; full metadata describes
        # the effective engine geometry rather than pretending it used UI size.
        requested=copy.deepcopy(config)
        if config['mode']=='robot_sequence' and config['size_mm']!=list(profile['box_dims_mm']):
            raise ValueError('Robot execution geometry must match the marker layout; explicitly preview/apply the effective dimensions.')
        config['size_mm']=list(profile['box_dims_mm']);validate_config(config)
    elif simulation.get('mode') not in (None,'single_drop'):
        raise ValueError('Explicit simulation mode requires its versioned configuration.')
    target = Path(destination).resolve()
    if target.exists():
        raise FileExistsError('Output already exists. Choose a new folder name.')
    if not target.parent.is_dir():
        raise ValueError('Choose an existing parent folder.')
    checkpoint()
    if config is not None and config['mode']=='robot_sequence':
        from .engine.robot_sequence import RobotSequenceEngine
        engine=RobotSequenceEngine(config)
    elif config is not None and ('initial_condition' in config or 'contact_profile' in config):
        from .initial_conditions import engine_from_config
        engine=engine_from_config(config)
    else:
        engine = MuJoCoEngine(size=profile['box_dims_mm'], mass=simulation['mass'],
            friction=simulation['friction'], elasticity=simulation['elasticity'], com_offset=simulation['com_offset'])
    if config is None or 'initial_condition' not in config:
        engine.set_initial_state(simulation['height'], simulation['quat'])
    def engine_progress(current,stop):
        phase=getattr(engine,'current_phase',None)
        label=(f"{phase['step_id']} — {phase['kind']} — {current:.3f} s" if phase else 'Simulating')
        update(min(80,80*current/stop),label)
    history = engine.run_simulation(show_viewer=False, stop_condition_time=simulation['duration'],
        cancelled=cancelled, progress=engine_progress)
    checkpoint()
    trajectory = history_to_trajectory(history)
    spec = fault_spec(trajectory['time_s'], faults)
    metadata=None if config is None else build_metadata(config,engine,history,
        route='marker_csv',run_id=simulation.get('run_id') or str(uuid4()))
    if metadata is not None:
        from src.utils.marker_profile_identity import digest
        metadata['requested_source_configuration']=requested
        metadata['content_hash']=digest({k:v for k,v in metadata.items() if k!='content_hash'})
    update(85, 'Writing marker observations')
    # This temporary directory is newly owned by this export under the selected
    # parent. Neither cancellation nor cleanup touches an existing result.
    with tempfile.TemporaryDirectory(prefix='.bma-markers-', dir=target.parent) as staging:
        staged = write_observations(Path(staging) / 'capture', trajectory, profile, spec, seed, cancelled=cancelled,
            simulation_metadata=metadata)
        checkpoint()
        if target.exists():
            raise FileExistsError('Output already exists. Choose a new folder name.')
        staged.rename(target)
    update(100, 'Ready')
    return str(target / 'observed.csv')
