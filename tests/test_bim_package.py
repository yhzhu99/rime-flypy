"""Check BiM archive structure, dictionary parity, and touch layout."""
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from zipfile import ZipFile

import yaml

from platforms.ios import package


class BimPackageTests(unittest.TestCase):
    def test_importable_archives_keep_original_dictionary_bytes(self):
        with TemporaryDirectory() as directory:
            schema_path, theme_path = package.build_archives(Path(directory))
            with ZipFile(schema_path) as schema, ZipFile(theme_path) as theme:
                self.assertIsNone(schema.testzip())
                self.assertIsNone(theme.testzip())
                self.assertEqual({Path(name).parts[0] for name in schema.namelist()}, {'flypy'})
                self.assertEqual({Path(name).parts[0] for name in theme.namelist()}, {'flypy-ios'})
                self.assertIn('flypy-ios/theme.yaml', theme.namelist())
                for path in (*package.ROOT.glob('*.dict.yaml'), *package.ROOT.glob('flypy/*.dict.yaml')):
                    self.assertEqual(schema.read(f'flypy/{path.relative_to(package.ROOT).as_posix()}'), path.read_bytes())
                self.assertNotIn('flypy/lua/language_keys.lua', schema.namelist())
                info = yaml.safe_load(schema.read('flypy/info.yaml'))
                self.assertEqual(info['use_theme']['custom']['flypy'], 'themes/flypy-ios')
                for name in ('flypy', 'flypydz'):
                    desktop = yaml.safe_load((package.ROOT / f'{name}.schema.yaml').read_bytes())
                    desktop['engine']['processors'].remove('lua_processor@*language_keys')
                    self.assertEqual(yaml.safe_load(schema.read(f'flypy/{name}.schema.yaml')), desktop)
                for path in package.ROOT.glob('lua/*.lua'):
                    if path.name != 'language_keys.lua':
                        self.assertEqual(schema.read(f'flypy/lua/{path.name}'), path.read_bytes())

    def test_touch_layout_keeps_code_keys_and_both_language_pages(self):
        files = package.bundle_files()['flypy-ios']
        layout = yaml.safe_load(files['layout.yaml'])
        theme = yaml.safe_load(files['theme.yaml'])
        letters = [key for key in layout['letters'] if len(key.get('click', '')) == 1]
        self.assertEqual(''.join(key['click'] for key in letters), 'qwertyuiopasdfghjklzxcvbnm')
        self.assertEqual([key['swipe_up'] for key in letters[:10]], [f'commit_{digit}' for digit in '1234567890'])
        self.assertTrue(all(key['swipe_down'] for key in letters[:10]))
        self.assertEqual(theme['preset_keys']['flypy_semicolon']['send'], 'semicolon')
        self.assertEqual(theme['preset_keys']['flypy_reverse']['send'], 'grave')
        for page, mode, toggle in (('default', 0, 'eisu_toggle_ABC_english'), ('english', 1, 'eisu_toggle_中_default')):
            keyboard = theme['preset_keyboards'][page]
            self.assertEqual(keyboard['ascii_mode'], mode)
            self.assertEqual(keyboard['keys']['__include'], './layout:/letters')
            bottom = keyboard['keys/+']
            self.assertEqual(sum(key['width'] for key in bottom), 100)
            self.assertIn(toggle, [key['click'] for key in bottom])
            self.assertEqual(next(key for key in bottom if key['click'] == 'space')['swipe_up'], toggle)
