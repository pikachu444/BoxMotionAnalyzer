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
    target = Path(destination).resolve()
    if target.exists():
        raise FileExistsError('Output already exists. Choose a new folder name.')
    if not target.parent.is_dir():
        raise ValueError('Choose an existing parent folder.')
    checkpoint()
    engine = MuJoCoEngine(size=profile['box_dims_mm'], mass=simulation['mass'],
        friction=simulation['friction'], elasticity=simulation['elasticity'], com_offset=simulation['com_offset'])
    engine.set_initial_state(simulation['height'], simulation['quat'])
    history = engine.run_simulation(show_viewer=False, stop_condition_time=simulation['duration'],
        cancelled=cancelled, progress=lambda t, stop: update(min(80, 80 * t / stop), 'Simulating'))
    checkpoint()
    trajectory = history_to_trajectory(history)
    spec = fault_spec(trajectory['time_s'], faults)
    update(85, 'Writing marker observations')
    # This temporary directory is newly owned by this export under the selected
    # parent. Neither cancellation nor cleanup touches an existing result.
    with tempfile.TemporaryDirectory(prefix='.bma-markers-', dir=target.parent) as staging:
        staged = write_observations(Path(staging) / 'capture', trajectory, profile, spec, seed, cancelled=cancelled)
        checkpoint()
        if target.exists():
            raise FileExistsError('Output already exists. Choose a new folder name.')
        staged.rename(target)
    update(100, 'Ready')
    return str(target / 'observed.csv')
