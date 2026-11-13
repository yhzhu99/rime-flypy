"""Configure the standard IBus panel with system fonts; never install fonts."""
import argparse
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tempfile

LINUX_SETTINGS = {
    ('org.freedesktop.ibus.general', 'use-global-engine'): 'true',
    ('org.freedesktop.ibus.panel', 'lookup-table-orientation'): '0',
    ('org.freedesktop.ibus.panel', 'use-custom-font'): 'true',
    ('org.freedesktop.ibus.panel', 'custom-font'): "'Sans 16'",
}


def gsettings(*arguments):
    return subprocess.check_output(['gsettings', *arguments], text=True).strip()


def linux_settings_plan():
    if not shutil.which('gsettings'):
        raise RuntimeError('Install gsettings before applying Linux appearance.')
    schemas = set(gsettings('list-schemas').splitlines())
    changes = []
    for (schema, key), after in LINUX_SETTINGS.items():
        if schema not in schemas or key not in gsettings('list-keys', schema).splitlines():
            raise RuntimeError(f'Missing IBus setting: {schema}/{key}')
        if gsettings('writable', schema, key) != 'true':
            raise RuntimeError(f'IBus setting is locked: {schema}/{key}')
        before = gsettings('get', schema, key)
        if before != after:
            changes.append(dict(schema=schema, key=key, before=before, after=after))
    return changes


def prepare(kind):
    """Preflight desktop preferences; Windows/macOS use frontend font settings."""
    if kind != 'linux':
        return dict(platform=kind, settings=[])
    if os.geteuid() == 0:
        raise RuntimeError('Run appearance setup as your desktop user, not root.')
    return dict(platform=kind, settings=linux_settings_plan())


def apply(prepared, backup):
    if prepared['platform'] != 'linux':
        return
    backup.mkdir(parents=True, exist_ok=True)
    (backup / 'appearance.json').write_text(json.dumps(prepared, indent=2) + '\n', encoding='utf8')
    for item in prepared['settings']:
        if gsettings('get', item['schema'], item['key']) != item['before']:
            raise RuntimeError('IBus settings changed after preflight; stopped before changing settings.')
    for item in prepared['settings']:
        gsettings('set', item['schema'], item['key'], item['after'])
        if gsettings('get', item['schema'], item['key']) != item['after']:
            raise RuntimeError('IBus setting was not saved; run inside the logged-in desktop D-Bus session.')
    print('IBus panel: horizontal, Sans 16 with system Chinese fallback; shared input engine.')
    print('GNOME Shell/KDE panels can override fonts and colors; see docs/appearance.md.')


def restore_linux_settings(manifest):
    prepared = json.loads(manifest.read_text(encoding='utf8'))
    if prepared['platform'] != 'linux':
        raise RuntimeError('This restore action is only for IBus settings.')
    changes = []
    for item in prepared['settings']:
        pair = item['schema'], item['key']
        if pair not in LINUX_SETTINGS or item['after'] != LINUX_SETTINGS[pair]:
            raise RuntimeError('Unknown setting in the appearance backup.')
        current = gsettings('get', *pair)
        if current == item['before']:
            continue
        if current != item['after']:
            raise RuntimeError('IBus settings have later edits; refusing to overwrite.')
        changes.append(item)
    for item in changes:
        gsettings('set', item['schema'], item['key'], item['before'])
        if gsettings('get', item['schema'], item['key']) != item['before']:
            raise RuntimeError('IBus setting was not restored; check the desktop D-Bus session.')
    print('Previous effective IBus settings restored.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--apply', action='store_true')
    mode.add_argument('--restore-linux-settings', type=Path, metavar='APPEARANCE_JSON')
    args = parser.parse_args()
    if args.restore_linux_settings:
        restore_linux_settings(args.restore_linux_settings)
        return
    kind = {'Windows': 'windows', 'Darwin': 'macos', 'Linux': 'linux'}[platform.system()]
    if kind != 'linux':
        print('System fonts are selected by the Rime frontend configuration. No fonts or desktop settings were changed.')
        return
    if not args.apply:
        print('IBus settings:', LINUX_SETTINGS)
        print('Pass --apply to configure the desktop panel. No files were written; no fonts are installed.')
        return
    prepared = prepare(kind)
    state = Path(os.environ.get('XDG_STATE_HOME', Path.home() / '.local/state')) / 'rime-flypy'
    state.mkdir(parents=True, exist_ok=True)
    backup = Path(tempfile.mkdtemp(prefix='appearance-backup-', dir=state))
    apply(prepared, backup)
    print(f'Appearance record: {backup / "appearance.json"}')


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf8')
    try:
        main()
    except (OSError, RuntimeError, ValueError, subprocess.CalledProcessError) as error:
        print(f'Appearance setup stopped: {error}', file=sys.stderr)
        raise SystemExit(1)
