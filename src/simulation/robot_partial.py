"""Explicitly retain an aborted immutable robot run beside the requested output."""
from pathlib import Path
from uuid import uuid4
from .data_exporter import DataExporter


def retain_partial(requested_path, engine):
    if engine.sequence_evidence['completion'] not in ('partial','cancelled','time_limit','failure'):
        raise ValueError('Only incomplete sequence captures can be retained as partial output.')
    if not engine.history: return None
    config=engine.config;observation=config['observation_profile']['corner']
    params=dict(duration=config['duration_s'],add_noise=observation['enabled'],noise_std=observation['std_mm'],
        noise_seed=observation['seed'],mode_config=config,run_id='partial-'+uuid4().hex)
    requested=Path(requested_path)
    target=requested.with_name(requested.stem+'.partial-'+uuid4().hex+requested.suffix)
    # A unique side path prevents partial publication from replacing an earlier
    # complete output. Its public status remains incomplete on loader/reopening.
    DataExporter.from_engine(engine.history,engine,params).export_proc_csv(target)
    return str(target)
