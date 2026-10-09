"""Select a virtual observation profile and export through the existing producer."""
import argparse
from copy import deepcopy
import json
from pathlib import Path

from .marker_export import generate_marker_capture
from .mode_profiles import read_profiles, require_executable, save_profiles
from .observation_profile import validate_observation_profile
from .scenarios import Scenarios


def export_settings(settings_path, profile_path, output, *, saved_settings=None):
    state = read_profiles(settings_path)
    config = deepcopy(state.configs[state.mode])
    marker = config['observation_profile']['marker']
    value = json.loads(Path(profile_path).read_text(encoding='utf-8-sig'))
    validate_observation_profile(value, marker['profile'])
    marker['observation_profile'] = value
    require_executable(config)
    state.set_config(config)
    if saved_settings is not None:
        save_profiles(saved_settings, state)
    physics = config['physics_profile']; step = config['sequence_profile']['steps'][0]
    quat = (config['initial_condition']['quaternion_wxyz'] if 'initial_condition' in config else
        Scenarios.get_orientation_from_euler(*step['fixed_xyz_deg']))
    simulation = dict(mode_config=config, mass=physics['mass_kg'], friction=physics['friction'],
        elasticity=physics['contact_damping_control'], com_offset=physics['com_offset_mm'],
        duration=config['duration_s'], height=step['clearance_mm'], quat=quat)
    return generate_marker_capture(output, marker['profile'], simulation, marker['faults'], marker['seed'])


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--settings', required=True, help='Existing SimulationProfilesDocument JSON; selects its active mode.')
    parser.add_argument('--profile', required=True, help='Sealed VirtualObservationProfile JSON; explicitly opts in.')
    parser.add_argument('--output', required=True, help='New capture folder; existing paths are refused.')
    parser.add_argument('--save-settings', help='Atomically save the selected profile in the existing settings format.')
    args = parser.parse_args(argv)
    try:
        path = export_settings(args.settings, args.profile, args.output, saved_settings=args.save_settings)
    except (ValueError, TypeError, KeyError, OSError) as error:
        parser.exit(2, f'Observation export failed: {error}\n')
    print(path)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
