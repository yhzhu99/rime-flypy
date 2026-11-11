"""Install pinned user-local fonts and configure the standard IBus panel."""
import argparse
import ctypes
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tempfile
import urllib.request

ROOT = Path(__file__).resolve().parent
LINUX_SETTINGS = {
    ('org.freedesktop.ibus.general', 'use-global-engine'): 'true',
    ('org.freedesktop.ibus.panel', 'lookup-table-orientation'): '0',
    ('org.freedesktop.ibus.panel', 'use-custom-font'): 'true',
    ('org.freedesktop.ibus.panel', 'custom-font'): "'Noto Sans,LXGW WenKai 16'",
}


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def user_directories(kind):
    home = Path.home()
    if kind == 'windows':
        local = Path(os.environ['LOCALAPPDATA'])
        return local / 'Microsoft/Windows/Fonts', local / 'rime-flypy/font-cache'
    if kind == 'macos':
        return home / 'Library/Fonts', home / 'Library/Caches/rime-flypy/fonts'
    return (Path(os.environ.get('XDG_DATA_HOME', home / '.local/share')) / 'fonts/rime-flypy',
            Path(os.environ.get('XDG_CACHE_HOME', home / '.cache')) / 'rime-flypy/fonts')


def font_manifest():
    fonts = json.loads((ROOT / 'fonts.json').read_text(encoding='utf8'))
    for font in fonts:
        name = font['filename']
        if (not name.startswith('rime-flypy-') or Path(name).name != name or
                '/' in name or '\\' in name or not font['url'].startswith('https://') or
                len(font['sha256']) != 64 or any(c not in '0123456789abcdef' for c in font['sha256'])):
            raise RuntimeError('Invalid pinned font record.')
    return fonts


def download_font(font, cache):
    cache.mkdir(parents=True, exist_ok=True)
    path = cache / font['filename']
    if path.is_symlink():
        raise RuntimeError(f'Refusing a symlink in the font cache: {path}')
    if path.is_file() and sha256(path) == font['sha256']:
        return path
    request = urllib.request.Request(font['url'], headers={'User-Agent': 'rime-flypy-font-setup'})
    with tempfile.NamedTemporaryFile(dir=cache, delete=False) as stream:
        temporary = Path(stream.name)
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                shutil.copyfileobj(response, stream)
        except Exception:
            stream.close()
            temporary.unlink(missing_ok=True)
            raise
    try:
        if sha256(temporary) != font['sha256']:
            raise RuntimeError(f'Font checksum mismatch: {font["family"]}')
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)
    return path


def gsettings(*arguments):
    return subprocess.check_output(['gsettings', *arguments], text=True).strip()


def linux_settings_plan():
    for name in ('gsettings', 'fc-cache'):
        if not shutil.which(name):
            raise RuntimeError(f'Install {name} before applying Linux appearance.')
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
    """Preflight all destinations and download verified assets before deployment."""
    if kind != 'windows' and os.geteuid() == 0:
        raise RuntimeError('Run appearance setup as your desktop user, not root.')
    directory, cache = user_directories(kind)
    fonts = font_manifest()
    for font in fonts:
        destination = directory / font['filename']
        if destination.is_symlink() or (destination.exists() and
                (not destination.is_file() or sha256(destination) != font['sha256'])):
            raise RuntimeError(f'Refusing to overwrite an unrelated or modified font: {destination}')
    settings = linux_settings_plan() if kind == 'linux' else []
    for font in fonts:
        font['source'] = str(download_font(font, cache))
        font['destination'] = str(directory / font['filename'])
    return dict(platform=kind, fonts=fonts, settings=settings)


def register_windows_fonts(fonts):
    import winreg
    from ctypes import wintypes
    key_path = r'Software\Microsoft\Windows NT\CurrentVersion\Fonts'
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, key_path) as key:
        for font in fonts:
            name = font['family'] + ' (rime-flypy) (TrueType)'
            try:
                before = winreg.QueryValueEx(key, name)[0]
            except FileNotFoundError:
                before = font['destination']
            if before != font['destination']:
                raise RuntimeError(f'Font registration points to a different file: {name}')
        add_font = ctypes.windll.gdi32.AddFontResourceExW
        add_font.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, ctypes.c_void_p]
        add_font.restype = ctypes.c_int
        for font in fonts:
            if add_font(font['destination'], 0, None) == 0:
                raise RuntimeError(f'Windows could not load font: {font["family"]}')
            winreg.SetValueEx(key, font['family'] + ' (rime-flypy) (TrueType)', 0,
                             winreg.REG_SZ, font['destination'])
    send = ctypes.windll.user32.SendMessageTimeoutW
    send.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM,
                     wintypes.UINT, wintypes.UINT, ctypes.POINTER(ctypes.c_size_t)]
    send.restype = wintypes.LPARAM
    result = ctypes.c_size_t()
    send(0xffff, 0x001d, 0, 0, 2, 2000, ctypes.byref(result))  # WM_FONTCHANGE


def apply(prepared, backup):
    backup.mkdir(parents=True, exist_ok=True)
    (backup / 'appearance.json').write_text(json.dumps(prepared, indent=2) + '\n', encoding='utf8')
    for font in prepared['fonts']:
        source, destination = Path(font['source']), Path(font['destination'])
        if sha256(source) != font['sha256']:
            raise RuntimeError(f'Font cache changed after preflight: {source}')
        if destination.exists():
            if destination.is_symlink() or sha256(destination) != font['sha256']:
                raise RuntimeError(f'Font destination changed after preflight: {destination}')
            continue
        destination.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=destination.parent, delete=False) as stream:
            temporary = Path(stream.name)
        try:
            shutil.copy2(source, temporary)
            os.replace(temporary, destination)
        finally:
            temporary.unlink(missing_ok=True)
    if prepared['platform'] == 'windows':
        register_windows_fonts(prepared['fonts'])
    elif prepared['platform'] == 'linux':
        subprocess.run(['fc-cache', '-f', str(Path(prepared['fonts'][0]['destination']).parent)], check=True)
        for item in prepared['settings']:
            if gsettings('get', item['schema'], item['key']) != item['before']:
                raise RuntimeError('IBus settings changed after preflight; stopped before changing settings.')
        for item in prepared['settings']:
            gsettings('set', item['schema'], item['key'], item['after'])
            if gsettings('get', item['schema'], item['key']) != item['after']:
                raise RuntimeError('IBus setting was not saved; run inside the logged-in desktop D-Bus session.')
        print('IBus font preferences applied. GNOME Shell/KDE panels can override fonts and colors; see docs/appearance.md.')
    print('User-local fonts installed. Restart the input frontend if it cached the old font list.')


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
    print('Previous effective IBus settings restored. Installed fonts were kept.')


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
    directory, cache = user_directories(kind)
    if not args.apply:
        print(f'Preview: install verified fonts into {directory}')
        for font in font_manifest():
            print(f'{font["family"]}: {font["sha256"]}')
        if kind == 'linux':
            print('IBus settings:', LINUX_SETTINGS)
        print('Pass --apply to download and install fonts/settings. No files were written.')
        return
    prepared = prepare(kind)
    backup = Path(tempfile.mkdtemp(prefix='appearance-backup-', dir=cache))
    apply(prepared, backup)
    print(f'Appearance record: {backup / "appearance.json"}')


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf8')
    try:
        main()
    except (OSError, RuntimeError, ValueError, subprocess.CalledProcessError) as error:
        print(f'Appearance setup stopped: {error}', file=sys.stderr)
        raise SystemExit(1)
