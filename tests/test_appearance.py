"""Verify font integrity and guarded desktop changes without installing anything."""
import contextlib
import hashlib
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
        self.font = dict(family='Test Sans', filename='rime-flypy-test.ttf',
                         url='https://example.invalid/test.ttf',
                         sha256=hashlib.sha256(b'verified font').hexdigest())

    def test_download_rejects_wrong_hash_and_preserves_cached_file(self):
        cache = self.root / 'cache'
        cache.mkdir()
        destination = cache / self.font['filename']
        destination.write_bytes(b'old cache')
        with patch.object(appearance.urllib.request, 'urlopen', return_value=io.BytesIO(b'bad download')):
            with self.assertRaisesRegex(RuntimeError, 'checksum mismatch'):
                appearance.download_font(self.font, cache)
        self.assertEqual(destination.read_bytes(), b'old cache')
        self.assertEqual(list(cache.iterdir()), [destination])

    def test_verified_cache_is_reused_without_network(self):
        cache = self.root / 'cache'
        with patch.object(appearance.urllib.request, 'urlopen', return_value=io.BytesIO(b'verified font')) as download:
            first = appearance.download_font(self.font, cache)
            second = appearance.download_font(self.font, cache)
        self.assertEqual(first, second)
        self.assertEqual(first.read_bytes(), b'verified font')
        self.assertEqual(download.call_count, 1)

    def test_preflight_rejects_modified_target_before_downloading(self):
        target = self.root / self.font['filename']
        target.write_bytes(b'personal modification')
        with patch.object(appearance, 'font_manifest', return_value=[self.font]), \
                patch.object(appearance, 'user_directories', return_value=(self.root, self.root / 'cache')), \
                patch.object(appearance, 'download_font') as download:
            with self.assertRaisesRegex(RuntimeError, 'Refusing to overwrite'):
                appearance.prepare('windows')
            download.assert_not_called()
        self.assertEqual(target.read_bytes(), b'personal modification')

    def test_copy_is_idempotent_and_checks_source_again(self):
        source = self.root / 'source.ttf'
        source.write_bytes(b'verified font')
        destination = self.root / 'fonts' / self.font['filename']
        record = dict(self.font, source=str(source), destination=str(destination))
        prepared = dict(platform='windows', fonts=[record], settings=[])
        with patch.object(appearance, 'register_windows_fonts') as register:
            appearance.apply(prepared, self.root / 'backup')
            before = destination.stat().st_mtime_ns
            appearance.apply(prepared, self.root / 'backup-2')
            self.assertEqual(destination.stat().st_mtime_ns, before)
            self.assertEqual(register.call_count, 2)
        self.assertEqual(destination.read_bytes(), b'verified font')
        source.write_bytes(b'tampered cache')
        with self.assertRaisesRegex(RuntimeError, 'cache changed'):
            appearance.apply(prepared, self.root / 'backup-3')
        self.assertEqual(destination.read_bytes(), b'verified font')

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
        source = self.root / 'source.ttf'
        source.write_bytes(b'verified font')
        record = dict(self.font, source=str(source), destination=str(self.root / 'fonts/test.ttf'))
        item = dict(schema='org.freedesktop.ibus.panel', key='use-custom-font', before='false', after='true')
        prepared = dict(platform='linux', fonts=[record], settings=[item])
        with patch.object(appearance.subprocess, 'run'), \
                patch.object(appearance, 'gsettings', return_value='false'):
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

    def test_preview_does_not_download_install_or_write(self):
        with patch('sys.argv', ['appearance.py']), \
                patch.object(appearance, 'prepare') as prepare, \
                patch.object(appearance, 'apply') as apply, \
                patch.object(appearance, 'user_directories', return_value=(self.root / 'fonts', self.root / 'cache')), \
                contextlib.redirect_stdout(io.StringIO()):
            appearance.main()
        prepare.assert_not_called()
        apply.assert_not_called()
        self.assertEqual(list(self.root.iterdir()), [])


if __name__ == '__main__':
    unittest.main()
