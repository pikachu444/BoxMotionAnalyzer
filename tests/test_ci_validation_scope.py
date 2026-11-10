import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from scripts.ci_validation_scope import choose_scope


class TestValidationScope(unittest.TestCase):
    def setUp(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.git('init', '-b', 'main')
        self.git('config', 'user.email', 'validation@example.invalid')
        self.git('config', 'user.name', 'CI validation test')
        self.git('config', 'commit.gpgsign', 'false')
        self.write('src/utils/ui_text_ko.py', 'original')
        self.write('tests/test_ui_language.py', 'def test_language(): pass\n')
        self.git('add', '.')
        self.git('commit', '-m', 'base')
        self.base = self.git('rev-parse', 'HEAD')
        self.git('switch', '-c', 'feature')

    def git(self, *args):
        return subprocess.check_output(
            ['git', *args], cwd=self.root, stderr=subprocess.DEVNULL, text=True,
        ).strip()

    def write(self, name, value):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(value, encoding='utf-8')

    def merge(self):
        self.git('add', '-A')
        self.git('commit', '-m', 'feature')
        head = self.git('rev-parse', 'HEAD')
        self.git('switch', 'main')
        self.git('merge', '--no-ff', 'feature', '-m', 'merge for validation')
        return head

    def test_known_presentation_changes_use_focused_windows_tests(self):
        self.write('src/utils/ui_text_ko.py', 'revised')
        self.write('src/launcher.py', 'revised')
        head = self.merge()
        self.assertEqual(choose_scope('pull_request', self.base, head, self.root), 'presentation')

    def test_merge_parents_are_available_in_the_workflow_shallow_checkout(self):
        self.write('src/utils/ui_text_ko.py', 'revised')
        head = self.merge()
        with TemporaryDirectory() as checkout:
            self.git('clone', '--no-local', '--depth', '2', '--branch', 'main', str(self.root), checkout)
            self.assertEqual(choose_scope('pull_request', self.base, head, checkout), 'presentation')

    def test_unknown_path_and_rename_use_full_validation(self):
        self.git('mv', 'src/utils/ui_text_ko.py', 'src/utils/shared_behavior.py')
        self.write('src/launcher.py', 'revised')
        head = self.merge()
        self.assertEqual(choose_scope('pull_request', self.base, head, self.root), 'full')

    def test_changes_to_presentation_tests_still_check_the_frozen_inventory(self):
        self.write('tests/test_ui_language.py', '')
        head = self.merge()
        self.assertEqual(choose_scope('pull_request', self.base, head, self.root), 'full')

    def test_non_pr_or_mismatched_checkout_uses_full_validation(self):
        self.write('src/utils/ui_text_ko.py', 'revised')
        head = self.merge()
        self.assertEqual(choose_scope('push', self.base, head, self.root), 'full')
        self.assertEqual(choose_scope('workflow_dispatch', self.base, head, self.root), 'full')
        self.assertEqual(choose_scope('pull_request', self.base, self.base, self.root), 'full')
        self.assertEqual(choose_scope('pull_request', '', head, self.root), 'full')
