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
                theme_info = yaml.safe_load(theme.read('flypy-ios/info.yaml'))
                theme_config = yaml.safe_load(theme.read('flypy-ios/theme.yaml'))
                self.assertEqual(theme_info['version'], theme_config['config_version'])
                for path in (*package.ROOT.glob('*.dict.yaml'), *package.ROOT.glob('flypy/*.dict.yaml')):
                    self.assertEqual(schema.read(f'flypy/{path.relative_to(package.ROOT).as_posix()}'), path.read_bytes())
                self.assertNotIn('flypy/lua/language_keys.lua', schema.namelist())
                info = yaml.safe_load(schema.read('flypy/info.yaml'))
                self.assertEqual(info['use_theme']['custom']['flypy'], 'themes/flypy-ios')
                for name in ('flypy', 'flypydz'):
                    desktop = yaml.safe_load((package.ROOT / f'{name}.schema.yaml').read_bytes())
                    desktop['engine']['processors'].remove('lua_processor@*language_keys')
                    if name == 'flypy':
                        desktop['engine']['processors'].insert(0, 'lua_processor@*ios_ascii_tilde')
                        self.assertIn('flypy/lua/ios_ascii_tilde.lua', schema.namelist())
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
        index, underscore = next((index, key) for index, key in enumerate(layout['letters']) if key.get('click') == 'x')
        self.assertEqual(underscore['swipe_up'], 'commit_halfunderline')
        self.assertNotIn(f'keys/@{index}/swipe_up', theme['preset_keyboards']['english']['__patch'])
        self.assertEqual(theme['preset_keys']['flypy_semicolon']['send'], 'semicolon')
        for page, mode, target, current_label, target_label in (
            ('default', 0, 'english', '中', '英'),
            ('english', 1, 'default', '英', '中'),
        ):
            keyboard = theme['preset_keyboards'][page]
            self.assertEqual(keyboard['ascii_mode'], mode)
            self.assertEqual(keyboard['keys']['__include'], './layout:/letters')
            bottom = keyboard['keys/+']
            self.assertEqual(sum(key['width'] for key in bottom), 100)
            self.assertEqual([key['name'] for key in bottom], ['number', 'english', 'punctuation', 'space', 'secondary', 'return'])
            self.assertEqual(bottom[1]['label'], current_label)
            self.assertEqual(bottom[1]['long_click'], ['eisu_toggle_common_setting_board'])
            self.assertEqual(bottom[1]['click'], bottom[3]['swipe_up'])
            normal_action = bottom[1]['click'][0]['send'] if mode == 0 else bottom[1]['click']
            action = theme['preset_keys'][normal_action]
            self.assertEqual((action['select'], action['label']), (target, target_label))
            self.assertEqual(bottom[-1]['swipe_up'], 'next')
        self.assertEqual(theme['preset_fonts']['default']['key_upper_text_size'], 11)
        for page in ('number', 'symbols'):
            self.assertEqual(theme['preset_keyboards']['__patch'][f'{page}/keys/@last/swipe_up'], 'next')
        chinese = theme['preset_keyboards']['default']['keys/+']
        self.assertIs(chinese[2]['functional'], False)
        for gesture, symbol, event in (('click', '，', '{,}'), ('swipe_up', '。', '{.}')):
            self.assertEqual(theme['preset_keys'][chinese[2][gesture]], {
                'label': symbol, 'text': event, 'functional': False,
            })
        english = theme['preset_keyboards']['english']['keys/+']
        self.assertEqual((english[2]['click'], english[4]['click']), ('commit_half_comma', 'commit_half_dot'))
        self.assertTrue(all('swipe_up' not in english[index] for index in (2, 4)))

    def test_chinese_candidates_clear_with_shift_and_keep_reverse_lookup_on_semicolon(self):
        files = package.bundle_files()['flypy-ios']
        layout = yaml.safe_load(files['layout.yaml'])
        theme = yaml.safe_load(files['theme.yaml'])
        chinese = theme['preset_keyboards']['default']
        english = theme['preset_keyboards']['english']
        shift_index, shift = next((index, key) for index, key in enumerate(layout['letters']) if key.get('name') == 'shift')
        self.assertEqual(shift['click'], 'shift')
        self.assertNotIn('has_menu', shift)
        tap_path = f'keys/@{shift_index}/click'
        self.assertEqual(chinese['__patch'][tap_path], [
            {'when': 'normal', 'send': 'shift'},
            {'when': 'has_menu', 'send': 'flypy_cancel'},
            {'when': 'composing', 'send': 'flypy_cancel'},
        ])
        self.assertEqual(theme['preset_keys']['flypy_cancel'], {'label': '清码', 'text': '{Escape}'})
        self.assertNotIn(tap_path, english['__patch'])
        semicolon = next(key for key in chinese['keys/+'] if key['name'] == 'secondary')
        self.assertEqual(semicolon['click'], [
            {'when': 'normal', 'send': 'flypy_semicolon'},
            {'when': 'has_menu', 'send': 'select_second'},
        ])
        self.assertNotIn('has_menu', semicolon)
        self.assertNotIn('long_click', semicolon)
        self.assertIs(semicolon['functional'], False)
        normal = theme['preset_keys'][semicolon['click'][0]['send']]
        self.assertEqual(normal['label'], '；')
        self.assertIs(normal['functional'], False)
        reverse = theme['preset_keys'][semicolon['swipe_up']]
        self.assertEqual(reverse, {'label': '`', 'text': '{`}', 'functional': False})

    def test_switch_to_english_commits_literal_code_before_changing_keyboard(self):
        files = package.bundle_files()['flypy-ios']
        theme = yaml.safe_load(files['theme.yaml'])
        keys = {key['name']: key for key in theme['preset_keyboards']['default']['keys/+']}
        switch = keys['english']['click']
        self.assertEqual(switch, keys['space']['swipe_up'])
        choices = {entry['when']: entry['send'] for entry in switch}
        self.assertEqual(choices, {
            'normal': 'flypy_to_english',
            'has_menu': 'flypy_commit_code_to_english',
            'composing': 'flypy_commit_code_to_english',
        })
        action = theme['preset_keys'][choices['composing']]
        self.assertEqual(action, {'label': '英', 'text': '{Return}{flypy_to_english}'})

    def test_english_swipes_use_half_width_symbols(self):
        files = package.bundle_files()['flypy-ios']
        layout = yaml.safe_load(files['layout.yaml'])
        theme = yaml.safe_load(files['theme.yaml'])
        expected = {
            'v': ('commit_fullquestionmark', 'commit_half_questionmark'),
            'b': ('commit_fullexclamationpoint', 'flypy_ascii_exclamation'),
        }
        english = theme['preset_keyboards']['english']
        tilde_index, tilde_key = next((index, key) for index, key in enumerate(layout['letters']) if key.get('click') == 'a')
        self.assertEqual(tilde_key['swipe_up'], 'commit_fulltilde')
        tilde_path = f'keys/@{tilde_index}'
        tilde_action = english['__patch'][f'{tilde_path}/swipe_up']
        self.assertEqual(tilde_action, 'commit_half_tilde_no_functional')
        self.assertEqual(theme['preset_keys']['__patch'][tilde_action], {
            'label': '~\u2060', 'text': '{asciitilde}', 'functional': False,
        })
        self.assertIs(english['__patch'][f'{tilde_path}/functional'], False)
        self.assertEqual(english['__patch'][f'{tilde_path}/long_click'], [tilde_action])
        for index, key in enumerate(layout['letters']):
            if key.get('click') not in expected:
                continue
            full_width, action = expected[key['click']]
            for direction in ('swipe_up', 'swipe_down'):
                self.assertEqual(key[direction], full_width)
                self.assertEqual(english['__patch'][f'keys/@{index}/{direction}'], action)
        semicolon_index = next(index for index, key in enumerate(layout['letters']) if key.get('click') == 'f')
        self.assertEqual(english['__patch'][f'keys/@{semicolon_index}/swipe_up'], 'flypy_ascii_semicolon')
        for action, symbol in (('flypy_ascii_exclamation', '!'), ('flypy_ascii_semicolon', ';')):
            self.assertEqual(theme['preset_keys'][action]['commit'], symbol)

    def test_punctuation_legends_follow_the_current_page(self):
        files = package.bundle_files()['flypy-ios']
        letters = yaml.safe_load(files['layout.yaml'])['letters']
        theme = yaml.safe_load(files['theme.yaml'])
        overrides = theme['preset_keyboards']['english']['__patch']
        slash_index, slash = next((index, key) for index, key in enumerate(letters) if key.get('click') == 's')
        self.assertEqual(slash['swipe_up'], 'commit_halfslash')
        for page in ('default', 'english'):
            self.assertNotIn(f'keys/@{slash_index}/swipe_up', theme['preset_keyboards'][page]['__patch'])
        for letter, gesture, chinese, english in (
            ('d', 'swipe_up', 'commit_fullcolon', ':'),
            ('f', 'swipe_up', 'commit_fullsemicolon', 'flypy_ascii_semicolon'),
            ('k', 'swipe_up', 'flypy_double_quotes', '"'), ('l', 'swipe_up', 'flypy_single_quotes', "'"),
            ('p', 'swipe_down', 'flypy_yuan', '$'),
        ):
            index, key = next((index, key) for index, key in enumerate(letters) if key.get('click') == letter)
            self.assertEqual(key[gesture], chinese)
            self.assertEqual(overrides[f'keys/@{index}/{gesture}'], english)
        for name, pair in (('flypy_double_quotes', '“”'), ('flypy_single_quotes', '‘’')):
            action = theme['preset_keys'][name]
            self.assertEqual((action['label'], action['text']), (pair, pair + '{Left}'))
        for name, symbol in (('flypy_yuan', '￥'), ('flypy_percent', '%'),
                             ('flypy_asterisk', '*'), ('flypy_backslash', '\\')):
            action = theme['preset_keys'][name]
            self.assertEqual((action['label'], action['commit']), (symbol, symbol))
        for style in ('light_sm_md', 'dark_sm_md'):
            self.assertEqual(theme['preset_styles']['__patch'][f'{style}/keyboards'], ['default', 'english', 'number', 'symbols'])

    def test_nm_swipes_add_symbols_instead_of_repeating_punctuation(self):
        files = package.bundle_files()['flypy-ios']
        layout = yaml.safe_load(files['layout.yaml'])
        theme = yaml.safe_load(files['theme.yaml'])
        english = theme['preset_keyboards']['english']['__patch']
        expected = {'n': '=', 'm': '|'}
        indexed = {key.get('click'): (index, key) for index, key in enumerate(layout['letters'])}
        for letter, symbol in expected.items():
            index, key = indexed[letter]
            self.assertNotIn('swipe_down', key)
            self.assertNotIn(f'keys/@{index}/swipe_down', english)
            self.assertNotIn(f'keys/@{index}/swipe_up', english)
            preset = theme['preset_keys'][key['swipe_up']]
            self.assertEqual((preset['label'], preset['commit']), (symbol, symbol))

    def test_bracket_gestures_use_punctuation_for_the_current_language(self):
        files = package.bundle_files()['flypy-ios']
        layout = yaml.safe_load(files['layout.yaml'])
        theme = yaml.safe_load(files['theme.yaml'])
        english = theme['preset_keyboards']['english']['__patch']
        indexed = {key.get('click'): (index, key) for index, key in enumerate(layout['letters'])}
        for letter, chinese_pair, english_pair in (('g', '（）', '()'), ('h', '【】', '[]')):
            index, key = indexed[letter]
            for pair, swipe, long_click in (
                (chinese_pair, key['swipe_up'], key['long_click']),
                (english_pair, english[f'keys/@{index}/swipe_up'], english[f'keys/@{index}/long_click']),
            ):
                action = theme['preset_keys'][swipe]
                self.assertEqual((action['label'], action['text']), (pair, f'{pair}{{Left}}'))
                singles = [theme['preset_keys'][name] for name in long_click]
                self.assertEqual([(preset['label'], preset['commit']) for preset in singles], [(symbol, symbol) for symbol in pair])
