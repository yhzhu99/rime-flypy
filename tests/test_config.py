"""Check deployable configuration and consistent physical-key mappings."""
import json
from pathlib import Path
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[1]


class ConfigurationTests(unittest.TestCase):
    def test_yaml_and_references(self):
        configs = {}
        for path in ROOT.glob('*.yaml'):
            # Rime dictionary bodies are tab-delimited data, not YAML.
            header = path.read_text(encoding='utf-8-sig').split('\n...')[0]
            configs[path.name] = yaml.safe_load(header)
        for schema in (configs['flypy.schema.yaml'], configs['flypydz.schema.yaml']):
            for dependency in schema['schema'].get('dependencies', []):
                self.assertTrue((ROOT / f'{dependency}.schema.yaml').is_file())
            for table in configs[schema['translator']['dictionary'] + '.dict.yaml'].get('import_tables', []):
                self.assertTrue((ROOT / f'{table}.dict.yaml').is_file(), table)
            for components in schema['engine'].values():
                for component in components:
                    if component.startswith('lua_') and '@*' in component:
                        module = component.split('@*', 1)[1].split('@')[0]
                        self.assertTrue((ROOT / 'lua' / f'{module}.lua').is_file(), component)

    def test_fixed_language_keys_run_before_english_passthrough(self):
        default = yaml.safe_load((ROOT / 'default.custom.yaml').read_text(encoding='utf8'))['patch']
        switches = default['ascii_composer/switch_key']
        self.assertEqual(switches['Shift_L'], 'set_ascii_mode')
        for key in ('Shift_R', 'Alt_L', 'Alt_R', 'Control_L', 'Control_R', 'Caps_Lock'):
            self.assertEqual(switches[key], 'noop', key)
        for name in ('flypy', 'flypydz'):
            schema = yaml.safe_load((ROOT / f'{name}.schema.yaml').read_text(encoding='utf8'))
            processors = schema['engine']['processors']
            self.assertLess(processors.index('lua_processor@*language_keys'), processors.index('ascii_composer'))
            self.assertFalse(any(binding['accept'] == 'Shift_R' for binding in schema['key_binder'].get('bindings', [])))

    def test_linux_and_macos_physical_keys_agree(self):
        lines = (ROOT / 'platforms/linux/rime-flypy.conf').read_text().split('[main]', 1)[1].splitlines()
        linux = dict(line.strip().split(' = ', 1) for line in lines if line.strip() and not line.startswith('#'))
        self.assertEqual(linux, {
            'capslock': 'esc', 'esc': 'capslock',
            'leftcontrol': 'layer(alt)', 'leftalt': 'layer(control)', 'rightalt': 'f13',
        })
        macos = json.loads((ROOT / 'platforms/macos/rime-flypy.json').read_text())
        mappings = {}
        for rule in macos['rules']:
            for item in rule['manipulators']:
                self.assertEqual(item['type'], 'basic')
                self.assertEqual(item['from']['modifiers']['optional'], ['any'])
                source = item['from']['key_code']
                self.assertNotIn(source, mappings)
                mappings[source] = item['to'][0]['key_code']
        self.assertEqual(mappings, {
            'caps_lock': 'escape', 'escape': 'caps_lock',
            'left_control': 'left_option', 'left_option': 'left_control', 'right_option': 'f13',
        })

    def test_frontend_settings_are_separate(self):
        weasel = yaml.safe_load((ROOT / 'weasel.custom.yaml').read_text(encoding='utf8'))['patch']
        self.assertTrue(weasel['global_ascii'])
        for options in weasel['app_options'].values():
            self.assertNotIn('ascii_mode', options)
            self.assertNotIn('vim_mode', options)
        squirrel = yaml.safe_load((ROOT / 'squirrel.custom.yaml').read_text(encoding='utf8'))['patch']
        self.assertEqual(squirrel['style/candidate_list_layout'], 'linear')
        for options in squirrel['app_options'].values():
            self.assertNotIn('ascii_mode', options)
            self.assertNotIn('vim_mode', options)

    def test_readable_horizontal_frontends(self):
        weasel = yaml.safe_load((ROOT / 'weasel.custom.yaml').read_text(encoding='utf8'))['patch']
        squirrel = yaml.safe_load((ROOT / 'squirrel.custom.yaml').read_text(encoding='utf8'))['patch']
        ibus = yaml.safe_load((ROOT / 'ibus_rime.custom.yaml').read_text(encoding='utf8'))['patch']
        self.assertTrue(weasel['style']['horizontal'])
        self.assertFalse(weasel['style']['vertical_text'])
        self.assertEqual(squirrel['style/candidate_list_layout'], 'linear')
        self.assertEqual(squirrel['style/text_orientation'], 'horizontal')
        self.assertTrue(ibus['style/horizontal'])
        for key, size in [('font_point', 20), ('label_font_point', 14), ('comment_font_point', 16)]:
            self.assertEqual(weasel['style'][key], size)
            self.assertEqual(squirrel['style/' + key], size)
        self.assertEqual(weasel['style']['font_face'], 'Noto Sans, LXGW WenKai')
        self.assertEqual(squirrel['style/font_face'], 'NotoSans-Regular, LXGWWenKai-Regular')
        fonts = json.loads((ROOT / 'fonts.json').read_text(encoding='utf8'))
        self.assertEqual({font['family'] for font in fonts}, {'Noto Sans', 'LXGW WenKai'})


if __name__ == '__main__':
    unittest.main()
