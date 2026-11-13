"""Exercise real file deployment/rollback in temporary directories, never OS settings."""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location('rime_setup', Path(__file__).resolve().parents[1] / 'setup.py')
setup = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(setup)


class SetupTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name)
        self.source = self.base / 'repository'
        self.target = self.base / 'Rime with spaces'
        self.backups = self.base / 'backups'
        self.source.mkdir()
        for name in setup.RIME_FILES:
            (self.source / name).write_text('new: 配置\n', encoding='utf8')
        for name in ('lua/key.lua', 'flypy/words.dict.yaml'):
            path = self.source / name
            path.parent.mkdir(exist_ok=True)
            path.write_text('repository data\n', encoding='utf8')
        # A checkout located in a live Rime directory may contain ignored state.
        (self.source / 'user.yaml').write_text('private source state', encoding='utf8')
        (self.source / 'installation.yaml').write_text('private installation ID', encoding='utf8')
        self.root_patch = patch.object(setup, 'ROOT', self.source)
        self.root_patch.start()
        self.addCleanup(self.root_patch.stop)

    def test_preview_has_no_filesystem_or_system_side_effects(self):
        with patch.object(setup, 'preflight') as preflight, patch.object(setup, 'finish_platform') as finish:
            with contextlib.redirect_stdout(io.StringIO()):
                setup.main(['--config-only', '--rime-dir', str(self.target), '--backup-dir', str(self.backups)])
            preflight.assert_not_called()
            finish.assert_not_called()
        self.assertFalse(self.target.exists())
        self.assertFalse(self.backups.exists())

    def test_copy_preserves_local_state_and_restore_is_guarded(self):
        self.target.mkdir()
        (self.target / 'default.custom.yaml').write_text('old: settings\n', encoding='utf8')
        (self.target / 'user.yaml').write_text('local user state', encoding='utf8')
        changes = setup.configuration_plan(self.target, 'linux', True)
        backup = setup.apply_configuration(changes, self.backups, 'linux')
        self.assertEqual((self.target / 'default.custom.yaml').read_text(encoding='utf8'), 'new: 配置\n')
        self.assertEqual((self.target / 'user.yaml').read_text(), 'local user state')
        self.assertFalse((self.target / 'installation.yaml').exists())
        self.assertEqual((backup / 'rime/default.custom.yaml').read_text(), 'old: settings\n')
        self.assertEqual(setup.configuration_plan(self.target, 'linux', True), [])
        # Subsequent personal edits must prevent the entire rollback before any deletion.
        (self.target / 'default.custom.yaml').write_text('later personal edit', encoding='utf8')
        with self.assertRaisesRegex(RuntimeError, 'edited after setup'):
            setup.restore_configuration(backup / 'manifest.json')
        self.assertTrue((self.target / 'lua/key.lua').exists())
        (self.target / 'default.custom.yaml').write_text('new: 配置\n', encoding='utf8')
        setup.restore_configuration(backup / 'manifest.json')
        self.assertEqual((self.target / 'default.custom.yaml').read_text(), 'old: settings\n')
        self.assertFalse((self.target / 'lua/key.lua').exists())
        self.assertEqual((self.target / 'user.yaml').read_text(), 'local user state')
        setup.restore_configuration(backup / 'manifest.json')  # Idempotent restoration.

    def test_preflight_failure_happens_before_copy(self):
        with patch.object(setup, 'host_platform', return_value='linux'), patch.object(setup, 'preflight', side_effect=RuntimeError('missing frontend')):
            with self.assertRaisesRegex(RuntimeError, 'missing frontend'):
                setup.main(['--apply', '--rime-dir', str(self.target)])
        self.assertFalse(self.target.exists())

    def test_config_only_apply_never_calls_platform_tools(self):
        with patch.object(setup, 'preflight') as preflight, patch.object(setup, 'finish_platform') as finish, \
                patch.object(setup.appearance, 'prepare') as desktop:
            with contextlib.redirect_stdout(io.StringIO()):
                setup.main(['--apply', '--config-only', '--rime-dir', str(self.target), '--backup-dir', str(self.backups)])
            preflight.assert_not_called()
            finish.assert_not_called()
            desktop.assert_not_called()
        self.assertTrue((self.target / 'lua/key.lua').is_file())
        self.assertFalse((self.target / 'user.yaml').exists())

    def test_rejects_directory_in_place_of_file(self):
        # Reject an existing directory where a managed file would be written.
        (self.target / 'default.custom.yaml').mkdir(parents=True)
        with self.assertRaisesRegex(RuntimeError, 'not a file'):
            setup.configuration_plan(self.target, 'linux', True)

    def test_changed_file_is_not_overwritten_after_preview(self):
        self.target.mkdir()
        plan = setup.configuration_plan(self.target, 'linux', True)
        path = self.target / 'default.custom.yaml'
        path.write_text('concurrent edit', encoding='utf8')
        with self.assertRaisesRegex(RuntimeError, 'changed after preview'):
            setup.apply_configuration(plan, self.backups, 'linux')
        self.assertEqual(path.read_text(), 'concurrent edit')

    def test_restore_rejects_path_traversal(self):
        backup = setup.apply_configuration(setup.configuration_plan(self.target, 'linux', True), self.backups, 'linux')
        path = backup / 'manifest.json'
        manifest = json.loads(path.read_text(encoding='utf8'))
        manifest['files'][0]['backup'] = '../outside'
        path.write_text(json.dumps(manifest), encoding='utf8')
        with self.assertRaisesRegex(RuntimeError, 'outside'):
            setup.restore_configuration(path)


if __name__ == '__main__':
    unittest.main()
