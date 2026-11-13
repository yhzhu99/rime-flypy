#!/usr/bin/env python3
"""Install configuration using system fonts; preview by default, never install applications."""
import argparse
import ctypes
import ctypes.util
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tempfile
import appearance

ROOT = Path(__file__).resolve().parent
RIME_FILES = (
    'default.custom.yaml', 'flypy.dict.yaml', 'flypy.schema.yaml',
    'flypydz.dict.yaml', 'flypydz.schema.yaml', 'weasel.custom.yaml',
    'ibus_rime.custom.yaml', 'squirrel.custom.yaml',
)


def host_platform():
    return {'Windows': 'windows', 'Linux': 'linux', 'Darwin': 'macos'}[platform.system()]


def default_paths(kind):
    home = Path.home()
    if kind == 'windows':
        return (Path(os.environ['APPDATA']) / 'Rime',
                Path(os.environ['LOCALAPPDATA']) / 'rime-flypy' / 'backups')
    if kind == 'macos':
        return home / 'Library/Rime', home / 'Library/Application Support/rime-flypy/backups'
    config = Path(os.environ.get('XDG_CONFIG_HOME', home / '.config'))
    state = Path(os.environ.get('XDG_STATE_HOME', home / '.local/state'))
    return config / 'ibus/rime', state / 'rime-flypy/backups'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def config_sources():
    files = [ROOT / name for name in RIME_FILES]
    files += list((ROOT / 'lua').rglob('*.lua'))
    files += list((ROOT / 'flypy').rglob('*.yaml'))
    for source in files:
        if not source.is_file() or not source.resolve().is_relative_to(ROOT.resolve()):
            raise RuntimeError(f'Missing configuration or source outside the repository: {source}')
    return sorted(files)


def configuration_plan(target, kind, config_only):
    if target.resolve() in (Path(target.anchor).resolve(), Path.home().resolve()):
        raise RuntimeError('Choose a dedicated Rime directory, not the home or filesystem root.')
    pairs = [(source, target / source.relative_to(ROOT), target, 'rime/' + source.relative_to(ROOT).as_posix())
             for source in config_sources()]
    if kind == 'macos' and not config_only:
        assets = Path.home() / '.config/karabiner/assets/complex_modifications'
        pairs.append((ROOT / 'platforms/macos/rime-flypy.json', assets / 'rime-flypy.json', assets, 'karabiner/rime-flypy.json'))
    changes = []
    for source, destination, allowed_root, backup_name in pairs:
        if not destination.resolve().is_relative_to(allowed_root.resolve()):
            raise RuntimeError(f'Refusing a destination outside the configuration directory: {destination}')
        if destination.is_symlink():
            raise RuntimeError(f'Refusing to replace a symlink: {destination}')
        if destination.exists() and not destination.is_file():
            raise RuntimeError(f'Destination is not a file: {destination}')
        after = digest(source)
        before = digest(destination) if destination.exists() else None
        if before != after:
            changes.append(dict(source=str(source), destination=str(destination.absolute()),
                                root=str(allowed_root.absolute()), backup=backup_name,
                                before=before, after=after))
    return changes


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf8')


def apply_configuration(changes, backup_root, kind):
    backup_root.mkdir(parents=True, exist_ok=True)
    backup = Path(tempfile.mkdtemp(prefix=datetime.now().strftime('%Y%m%d-%H%M%S-'), dir=backup_root))
    manifest = dict(version=1, platform=kind, status='prepared', files=changes)
    # Back up every replaced file before changing any destination.
    for change in changes:
        destination = Path(change['destination'])
        before = digest(destination) if destination.exists() else None
        if before != change['before']:
            raise RuntimeError(f'File changed after preview: {destination}')
        if before is not None:
            saved = backup / change['backup']
            saved.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(destination, saved)
    write_json(backup / 'manifest.json', manifest)
    try:
        for change in changes:
            destination = Path(change['destination'])
            destination.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(dir=destination.parent, delete=False) as stream:
                temporary = Path(stream.name)
            try:
                shutil.copy2(change['source'], temporary)
                os.replace(temporary, destination)
            finally:
                temporary.unlink(missing_ok=True)
        manifest['status'] = 'configuration-written'
    except Exception as error:
        manifest['status'] = 'failed'
        manifest['error'] = str(error)
        raise
    finally:
        write_json(backup / 'manifest.json', manifest)
    return backup


def restore_configuration(manifest_path):
    manifest_path = manifest_path.resolve()
    data = json.loads(manifest_path.read_text(encoding='utf8'))
    if data.get('version') != 1:
        raise RuntimeError('Unsupported backup manifest.')
    pending = []
    for item in data['files']:
        destination = Path(item['destination'])
        saved = manifest_path.parent / item['backup']
        if (destination.is_symlink() or
                not destination.resolve().is_relative_to(Path(item['root']).resolve()) or
                not saved.resolve().is_relative_to(manifest_path.parent)):
            raise RuntimeError('Backup contains a path outside its managed directory.')
        current = digest(destination) if destination.exists() else None
        if current == item['before']:
            continue  # Already restored, or an interrupted copy never reached this file.
        if current != item['after']:
            raise RuntimeError(f'File was edited after setup; refusing to overwrite: {destination}')
        if item['before'] is not None and (not saved.is_file() or digest(saved) != item['before']):
            raise RuntimeError(f'Backup is missing or altered: {saved}')
        pending.append((item, destination, saved))
    for item, destination, saved in pending:
        if item['before'] is None:
            destination.unlink()
        else:
            shutil.copy2(saved, destination)
    print('Configuration restored. Redeploy Rime. IBus preferences, system mappings, and enabled Karabiner rules have separate rollback steps in docs/.')


def run(command):
    subprocess.run([str(part) for part in command], check=True)


def windows_installation():
    import winreg
    for view in (winreg.KEY_WOW64_32KEY, winreg.KEY_WOW64_64KEY):
        try:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r'SOFTWARE\Rime\Weasel', 0, winreg.KEY_READ | view) as key:
                root = Path(winreg.QueryValueEx(key, 'WeaselRoot')[0])
                if (root / 'WeaselDeployer.exe').is_file():
                    return root
        except FileNotFoundError:
            pass
    raise RuntimeError('Install Weasel first; see docs/new-computer.md.')


def require_recent_engine(library):
    engine = ctypes.CDLL(str(library))
    # Public append-only RimeApi ABI: get_version follows 72 function pointers.
    # https://github.com/rime/librime/blob/1.17.0/src/rime_api.h
    class VersionAPI(ctypes.Structure):
        _fields_ = [('data_size', ctypes.c_int), ('prefix', ctypes.c_void_p * 72),
                    ('get_version', ctypes.c_void_p)]
    engine.rime_get_api.restype = ctypes.c_void_p
    address = engine.rime_get_api()
    if not address:
        raise RuntimeError('librime did not provide its API table.')
    size = ctypes.c_int.from_address(address).value + ctypes.sizeof(ctypes.c_int)
    if size < ctypes.sizeof(VersionAPI):
        raise RuntimeError('librime is too old to report its version.')
    api = VersionAPI.from_address(address)
    if not api.get_version:
        raise RuntimeError('librime has no version API.')
    version = ctypes.CFUNCTYPE(ctypes.c_char_p)(api.get_version)().decode('ascii')
    parts = version.split('.')
    if tuple(int(part) for part in parts[:2]) < (1, 17):
        raise RuntimeError(f'librime {version} is older than the tested baseline 1.17; upgrade before setup. See docs/new-computer.md.')
    print(f'librime version: {version}. The Lua plugin must also be installed.')


def preflight(kind):
    if kind == 'windows':
        if not ctypes.windll.shell32.IsUserAnAdmin():
            raise RuntimeError('Run --apply in an administrator terminal for this same Windows user.')
        installation = windows_installation()
        with os.add_dll_directory(str(installation)):
            require_recent_engine(installation / 'rime.dll')
        return installation
    if os.geteuid() == 0:
        raise RuntimeError('Run as your desktop user, not sudo/root; Linux setup invokes sudo only for keyd.')
    if kind == 'macos':
        for app in (Path('/Library/Input Methods/Squirrel.app'), Path('/Applications/Karabiner-Elements.app')):
            if not app.exists():
                raise RuntimeError(f'Install {app.name} first; see docs/new-computer.md.')
        return None
    for name in ('ibus', 'keyd', 'systemctl', 'sudo'):
        if not shutil.which(name):
            raise RuntimeError(f'Missing {name}; see docs/new-computer.md.')
    library = ctypes.util.find_library('rime')
    if not library:
        raise RuntimeError('librime was not found; install IBus-Rime and its Lua plugin first.')
    require_recent_engine(library)
    conflicts = [path for path in Path('/etc/keyd').glob('*.conf') if path.name != 'rime-flypy.conf']
    if conflicts:
        raise RuntimeError('Existing keyd configurations need a manual merge: ' + ', '.join(map(str, conflicts)))
    run(['keyd', 'check', ROOT / 'platforms/linux/rime-flypy.conf'])
    run(['sudo', '-v'])
    return None


def finish_platform(kind, backup, installation):
    if kind == 'windows':
        run([installation / 'WeaselDeployer.exe', '/deploy'])
        run(['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File',
             ROOT / 'platforms/windows/keyboard.ps1', '-Action', 'Apply',
             '-BackupPath', backup / 'keyboard-windows.json'])
        print('Select Weasel in Windows input sources, then restart Windows to activate the physical keyboard map.')
    elif kind == 'linux':
        destination = Path('/etc/keyd/rime-flypy.conf')
        if destination.exists():
            shutil.copy2(destination, backup / 'keyd-before.conf')
        write_json(backup / 'keyd-backup.json', {'existed': destination.exists(), 'path': str(destination)})
        run(['sudo', 'install', '-D', '-m', '644', ROOT / 'platforms/linux/rime-flypy.conf', destination])
        run(['sudo', 'systemctl', 'enable', '--now', 'keyd'])
        run(['sudo', 'keyd', 'reload'])
        print('Add Rime to the desktop IBus input sources. Then run: ibus restart; ibus engine rime. See docs/linux.md for first-login steps.')
    else:
        print('Configuration and Karabiner rule templates copied. Enable the three rime-flypy rules, grant required macOS permissions, select Squirrel, and redeploy from its menu. See docs/macos.md.')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--apply', action='store_true', help='Write configuration, desktop preferences, and the platform mapping.')
    mode.add_argument('--restore-config', type=Path, metavar='MANIFEST', help='Restore files only; system keyboard rollback is separate.')
    parser.add_argument('--config-only', action='store_true', help='Copy Rime files only; skip desktop settings, prerequisites, system mappings, and reload.')
    parser.add_argument('--rime-dir', type=Path, help='Override the Rime user directory.')
    parser.add_argument('--backup-dir', type=Path, help='Override the local backup parent directory.')
    args = parser.parse_args(argv)
    if args.restore_config:
        restore_configuration(args.restore_config)
        return
    kind = host_platform()
    default_target, default_backup = default_paths(kind)
    target = (args.rime_dir or default_target).expanduser().absolute()
    changes = configuration_plan(target, kind, args.config_only)
    print(f'Platform: {kind}\nRime directory: {target}\nFiles to write: {len(changes)}')
    if not args.apply:
        for change in changes:
            print(change['destination'])
        if not args.config_only:
            print('Use platform system fonts; no additional fonts are installed.')
            if kind == 'linux':
                print('Standard IBus panel: horizontal, Sans 16 pt with system Chinese fallback; global input engine.')
        print('Preview only. Install prerequisites from docs/new-computer.md, then pass --apply. --config-only excludes desktop settings and system mappings.')
        return
    installation = None if args.config_only else preflight(kind)
    prepared_appearance = None if args.config_only else appearance.prepare(kind)
    backup = apply_configuration(changes, (args.backup_dir or default_backup).expanduser(), kind)
    print(f'Configuration backup: {backup / "manifest.json"}')
    if not args.config_only:
        appearance.apply(prepared_appearance, backup)
        finish_platform(kind, backup, installation)
    else:
        print('Rime configuration copied only. Redeployment and keyboard mapping were intentionally skipped.')


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf8')
    sys.stderr.reconfigure(encoding='utf8')
    try:
        main()
    except (OSError, RuntimeError, ValueError, subprocess.CalledProcessError) as error:
        print(f'Setup stopped: {error}', file=sys.stderr)
        raise SystemExit(1)
