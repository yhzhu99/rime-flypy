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
        for key, size in [('font_point', 16), ('label_font_point', 12), ('comment_font_point', 13)]:
            self.assertEqual(weasel['style'][key], size)
            self.assertEqual(squirrel['style/' + key], size)
        self.assertEqual(weasel['style']['font_face'], 'Noto Sans, LXGW WenKai')
        self.assertEqual(squirrel['style/font_face'], 'Noto Sans-Regular, LXGW WenKai-Regular')
        fonts = json.loads((ROOT / 'fonts.json').read_text(encoding='utf8'))
        self.assertEqual({font['family'] for font in fonts}, {'Noto Sans', 'LXGW WenKai'})

    def test_windows_highlight_stays_inside_rounded_frame(self):
        config = yaml.safe_load((ROOT / 'weasel.custom.yaml').read_text(encoding='utf8'))['patch']
        layout = config['style']['layout']
        self.assertEqual(layout['margin_x'], layout['margin_y'])
        # Weasel checks the inflated highlight against a frame deflated by 1 px.
        # Touching its rounded corner triggers automatic asymmetric rounding.
        for scale in (1, 1.25, 1.5, 1.75, 2, 3):
            with self.subTest(scale=scale):
                radius = int(layout['corner_radius'] * scale)
                padding = int(layout['hilite_padding'] * scale)
                gap_x = int(layout['margin_x'] * scale) - padding - 1
                gap_y = int(layout['margin_y'] * scale) - padding - 1
                self.assertGreater(gap_x, 0)
                self.assertGreater(gap_y, 0)
                # Reserve the same gap between padded candidate cells as at
                # the outer edge, including when the selected index changes.
                cell_gap = int(layout['candidate_spacing'] * scale) - 2 * padding
                outer_gap = int(layout['margin_x'] * scale) - padding
                self.assertLessEqual(abs(cell_gap - outer_gap), 1)
                self.assertGreater(cell_gap, 0)
                self.assertEqual(int(layout['hilite_spacing'] * scale), padding)
                dx = max(radius - gap_x, 0)
                dy = max(radius - gap_y, 0)
                self.assertLessEqual(dx * dx + dy * dy, radius * radius)

    def test_light_palette_parity_and_text_contrast(self):
        weasel = yaml.safe_load((ROOT / 'weasel.custom.yaml').read_text(encoding='utf8'))['patch']
        squirrel = yaml.safe_load((ROOT / 'squirrel.custom.yaml').read_text(encoding='utf8'))['patch']
        theme = weasel['style']['color_scheme']
        self.assertEqual(squirrel['style/color_scheme'], theme)
        self.assertEqual(squirrel['style/color_scheme_dark'], theme)
        windows_colors = weasel['preset_color_schemes'][theme]
        mac_colors = squirrel['preset_color_schemes/' + theme]
        for selected, normal in [
            ('hilited_back_color', 'back_color'),
            ('hilited_text_color', 'text_color'),
            ('hilited_candidate_text_color', 'candidate_text_color'),
            ('hilited_comment_text_color', 'comment_text_color'),
            ('hilited_label_color', 'label_color'),
        ]:
            self.assertEqual(windows_colors[selected], windows_colors[normal], selected)
        self.assertNotEqual(windows_colors['hilited_candidate_back_color'], windows_colors['back_color'])
        self.assertEqual(weasel['style']['layout']['round_corner'], 0)
        self.assertEqual(weasel['style']['layout']['shadow_radius'], 0)
        self.assertEqual(windows_colors['shadow_color'], 0)
        self.assertEqual(squirrel['style/hilited_corner_radius'], 0)
        for key, value in mac_colors.items():
            windows_key = 'hilited_label_color' if key == 'hilited_candidate_label_color' else key
            self.assertEqual(windows_colors[windows_key], value, key)

        def luminance(bgr):
            channels = [(bgr >> shift & 255) / 255 for shift in (0, 8, 16)]
            linear = [v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4 for v in channels]
            return sum(v * weight for v, weight in zip(linear, (0.2126, 0.7152, 0.0722)))

        self.assertGreater(luminance(windows_colors['back_color']), 0.9)
        self.assertGreaterEqual(
            (luminance(windows_colors['back_color']) + 0.05) /
            (luminance(windows_colors['hilited_candidate_back_color']) + 0.05),
            1.25,
        )
        for foreground, background in [
            ('text_color', 'back_color'),
            ('candidate_text_color', 'back_color'),
            ('comment_text_color', 'back_color'),
            ('label_color', 'back_color'),
            ('hilited_text_color', 'hilited_back_color'),
            ('hilited_candidate_text_color', 'hilited_candidate_back_color'),
            ('hilited_comment_text_color', 'hilited_candidate_back_color'),
            ('hilited_label_color', 'hilited_candidate_back_color'),
        ]:
            values = [luminance(windows_colors[key]) for key in (foreground, background)]
            contrast = (max(values) + 0.05) / (min(values) + 0.05)
            self.assertGreaterEqual(contrast, 4.5, foreground)


if __name__ == '__main__':
    unittest.main()
