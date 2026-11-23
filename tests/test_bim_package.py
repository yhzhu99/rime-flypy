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
        for page, mode, toggle, target, label in (
            ('default', 0, 'eisu_toggle_ABC_english', 'english', '英'),
            ('english', 1, 'eisu_toggle_中_default', 'default', '中'),
        ):
            keyboard = theme['preset_keyboards'][page]
            self.assertEqual(keyboard['ascii_mode'], mode)
            self.assertEqual(keyboard['keys']['__include'], './layout:/letters')
            bottom = keyboard['keys/+']
            self.assertEqual(sum(key['width'] for key in bottom), 100)
            self.assertEqual([key['name'] for key in bottom], ['number', 'english', 'space', 'punctuation', 'secondary', 'return'])
            self.assertEqual(bottom[1]['click'], toggle)
            action = theme['preset_keys'][bottom[2]['swipe_up']]
            self.assertEqual((action['select'], action['label']), (target, label))
            self.assertEqual(bottom[-1]['swipe_up'], 'next')
        self.assertEqual(theme['preset_fonts']['default']['key_upper_text_size'], 11)
        for page in ('number', 'symbols'):
            self.assertEqual(theme['preset_keyboards']['__patch'][f'{page}/keys/@last/swipe_up'], 'next')
        chinese = theme['preset_keyboards']['default']['keys/+']
        self.assertEqual(chinese[3]['click'], 'text_halfcomma')
        self.assertEqual(chinese[3]['swipe_up'], 'flypy_period')
        self.assertEqual(chinese[4]['click'], 'flypy_semicolon')
        self.assertEqual(chinese[4]['has_menu'], 'select_second')
        self.assertEqual(chinese[4]['swipe_up'], 'flypy_reverse')

    def test_english_swipes_use_half_width_commit_actions(self):
        files = package.bundle_files()['flypy-ios']
        layout = yaml.safe_load(files['layout.yaml'])
        theme = yaml.safe_load(files['theme.yaml'])
        expected = {
            'v': ('？', 'commit_half_questionmark'), 'b': ('！', 'flypy_ascii_exclamation'),
            'n': ('，', 'commit_half_comma'), 'm': ('。', 'commit_half_dot'),
        }
        english = theme['preset_keyboards']['english']
        for index, key in enumerate(layout['letters']):
            if key.get('click') not in expected:
                continue
            full_width, action = expected[key['click']]
            self.assertIn(full_width, (key['swipe_up'], key['swipe_down']))
            for direction in ('swipe_up', 'swipe_down'):
                self.assertEqual(english['__patch'][f'keys/@{index}/{direction}'], action)
        for action, symbol in (('flypy_ascii_exclamation', '!'), ('flypy_ascii_semicolon', ';')):
            self.assertEqual(theme['preset_keys'][action]['commit'], symbol)
        comma = next(key for key in english['keys/+'] if key['click'] == 'commit_half_comma')
        self.assertEqual(comma['swipe_up'], 'commit_half_dot')
