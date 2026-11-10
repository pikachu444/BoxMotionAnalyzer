"""Select Windows PR validation from the actual checked-out merge tree."""

import argparse
import os
from pathlib import Path
import re
import subprocess
import sys


PRESENTATION_PATHS = frozenset({
    'src/launcher.py',
    'src/utils/app_identity.py',
    'src/utils/plot_toolbar.py',
    'src/utils/ui_language.py',
    'src/utils/ui_text_ko.py',
})

PRESENTATION_TESTS = (
    'tests/test_launch_headless.py',
    'tests/test_ui_language.py',
    'tests/test_workflow_navigation.py',
    'tests/test_processing_window_layout.py',
    'tests/test_result_presentation.py',
    'tests/test_comparison_layout.py',
    'tests/test_marker_profile_gui.py',
    'tests/test_marker_review_layout.py',
    'tests/test_simulation_modes_gui.py',
    'tests/test_simulation_layout.py',
)


def choose_scope(event, base, head, cwd=None):
    if event != 'pull_request' or not all(re.fullmatch(r'[0-9a-f]{40}', ref) for ref in (base, head)):
        return 'full'
    try:
        parents = subprocess.check_output(
            ['git', 'rev-parse', 'HEAD^1', 'HEAD^2'], cwd=cwd, stderr=subprocess.DEVNULL,
        ).decode('ascii').splitlines()
        if parents != [base, head]:
            return 'full'
        changes = subprocess.check_output(
            ['git', 'diff', '--name-only', '--no-renames', '-z', base, 'HEAD', '--'],
            cwd=cwd, stderr=subprocess.DEVNULL,
        ).decode('utf-8').strip('\0').split('\0')
    except (OSError, subprocess.CalledProcessError, UnicodeDecodeError):
        return 'full'
    return 'presentation' if set(changes) <= PRESENTATION_PATHS else 'full'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('route', 'test-presentation'))
    args = parser.parse_args()
    if args.action == 'test-presentation':
        return subprocess.run([
            sys.executable, '-m', 'pytest', '-q', *PRESENTATION_TESTS,
            '--junitxml=tmp/ci-presentation.xml',
        ]).returncode

    scope = choose_scope(
        os.environ.get('GITHUB_EVENT_NAME', ''),
        os.environ.get('PR_BASE_SHA', ''),
        os.environ.get('PR_HEAD_SHA', ''),
    )
    print(f'Windows validation scope: {scope}')
    with Path(os.environ['GITHUB_OUTPUT']).open('a', encoding='utf-8') as output:
        output.write(f'scope={scope}\n')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
