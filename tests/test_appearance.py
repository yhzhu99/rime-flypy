"""Verify system-font setup and guarded desktop preferences without OS changes."""
import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import appearance


class AppearanceTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)

    def test_windows_and_macos_do_not_install_fonts_or_write_state(self):
        for kind in ('windows', 'macos'):
            with self.subTest(platform=kind), \
                    patch('urllib.request.urlopen') as network, \
                    patch.object(appearance, 'gsettings') as settings:
                prepared = appearance.prepare(kind)
                appearance.apply(prepared, self.root / 'backup')
                network.assert_not_called()
                settings.assert_not_called()
                self.assertEqual(list(self.root.iterdir()), [])

    def test_linux_preflight_rejects_locked_settings_before_writes(self):
        def settings_api(action, *args):
            if action == 'list-schemas':
                return '\n'.join({schema for schema, key in appearance.LINUX_SETTINGS})
            if action == 'list-keys':
                return '\n'.join(key for schema, key in appearance.LINUX_SETTINGS if schema == args[0])
            if action == 'writable':
                return 'false'
            self.fail('Locked settings must stop preflight before reading or writing values.')
        with patch.object(appearance.shutil, 'which', return_value='/usr/bin/gsettings'), \
                patch.object(appearance, 'gsettings', side_effect=settings_api):
            with self.assertRaisesRegex(RuntimeError, 'locked'):
                appearance.linux_settings_plan()
        self.assertEqual(list(self.root.iterdir()), [])

    def test_linux_apply_preserves_changes_made_after_preflight(self):
        settings = [dict(schema=s, key=k, before='previous', after=v)
                    for (s, k), v in appearance.LINUX_SETTINGS.items()]
        def settings_api(action, schema, key):
            self.assertEqual(action, 'get')
            return 'later edit' if key == settings[-1]['key'] else 'previous'
        with patch.object(appearance, 'gsettings', side_effect=settings_api):
            with self.assertRaisesRegex(RuntimeError, 'changed after preflight'):
                appearance.apply(dict(platform='linux', settings=settings), self.root / 'backup')
        self.assertTrue((self.root / 'backup/appearance.json').is_file())

    def test_linux_restore_preserves_later_edits_before_any_write(self):
        settings = [dict(schema=s, key=k, before='previous', after=v)
                    for (s, k), v in appearance.LINUX_SETTINGS.items()]
        manifest = self.root / 'appearance.json'
        manifest.write_text(json.dumps(dict(platform='linux', settings=settings)))
        calls = []
        def settings_api(action, schema, key, *values):
            calls.append((action, schema, key, *values))
            if key == settings[-1]['key']:
                return 'subsequent edit'
            return appearance.LINUX_SETTINGS[(schema, key)]
        with patch.object(appearance, 'gsettings', side_effect=settings_api):
            with self.assertRaisesRegex(RuntimeError, 'later edits'):
                appearance.restore_linux_settings(manifest)
        self.assertTrue(all(call[0] == 'get' for call in calls))

    def test_linux_apply_detects_a_setting_that_was_not_saved(self):
        item = dict(schema='org.freedesktop.ibus.panel', key='use-custom-font', before='false', after='true')
        prepared = dict(platform='linux', settings=[item])
        with patch.object(appearance, 'gsettings', return_value='false'):
            with self.assertRaisesRegex(RuntimeError, 'not saved'):
                appearance.apply(prepared, self.root / 'backup')
        self.assertTrue((self.root / 'backup/appearance.json').is_file())

    def test_linux_settings_rollback_restores_previous_effective_values(self):
        settings = [dict(schema=s, key=k, before='previous', after=v)
                    for (s, k), v in appearance.LINUX_SETTINGS.items()]
        manifest = self.root / 'appearance.json'
        manifest.write_text(json.dumps(dict(platform='linux', settings=settings)))
        state = {(item['schema'], item['key']): item['after'] for item in settings}
        def settings_api(action, schema, key, *values):
            if action == 'set':
                state[schema, key] = values[0]
            return state[schema, key]
        with patch.object(appearance, 'gsettings', side_effect=settings_api):
            appearance.restore_linux_settings(manifest)
            appearance.restore_linux_settings(manifest)
        self.assertTrue(all(value == 'previous' for value in state.values()))

    def test_preview_does_not_write_or_call_desktop_tools(self):
        for kind in ('Windows', 'Darwin', 'Linux'):
            with self.subTest(platform=kind), \
                    patch('sys.argv', ['appearance.py']), \
                    patch.object(appearance.platform, 'system', return_value=kind), \
                    patch.object(appearance, 'prepare') as prepare, \
                    patch.object(appearance, 'apply') as apply, \
                    patch.object(appearance, 'gsettings') as settings, \
                    patch.object(appearance.Path, 'home', return_value=self.root), \
                    contextlib.redirect_stdout(io.StringIO()):
                appearance.main()
            prepare.assert_not_called()
            apply.assert_not_called()
            settings.assert_not_called()
            self.assertEqual(list(self.root.iterdir()), [])

    def test_windows_and_macos_cli_apply_has_no_side_effects(self):
        for kind in ('Windows', 'Darwin'):
            with self.subTest(platform=kind), \
                    patch('sys.argv', ['appearance.py', '--apply']), \
                    patch.object(appearance.platform, 'system', return_value=kind), \
                    patch.object(appearance, 'prepare') as prepare, \
                    patch.object(appearance.Path, 'home', return_value=self.root), \
                    contextlib.redirect_stdout(io.StringIO()):
                appearance.main()
            prepare.assert_not_called()
            self.assertEqual(list(self.root.iterdir()), [])


if __name__ == '__main__':
    unittest.main()
