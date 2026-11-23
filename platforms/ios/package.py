"""Build separate BiM schema and theme archives without installing anything."""
import argparse
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

ROOT = Path(__file__).resolve().parents[2]
IOS = Path(__file__).resolve().parent
DESKTOP_PROCESSOR = b'    - lua_processor@*language_keys\n'


def bundle_files():
    schema = {'info.yaml': (IOS / 'schema/info.yaml').read_bytes(),
              'default.custom.yaml': (IOS / 'schema/default.custom.yaml').read_bytes()}
    for name in ('flypy', 'flypydz'):
        source = (ROOT / f'{name}.schema.yaml').read_bytes().replace(b'\r\n', b'\n')
        if source.count(DESKTOP_PROCESSOR) != 1:
            raise ValueError(f'Expected one desktop-only language processor in {name}')
        touch_processor = b'    - lua_processor@*ios_ascii_tilde\n' if name == 'flypy' else b''
        schema[f'{name}.schema.yaml'] = source.replace(DESKTOP_PROCESSOR, touch_processor)
        schema[f'{name}.dict.yaml'] = (ROOT / f'{name}.dict.yaml').read_bytes()
    for path in sorted((ROOT / 'flypy').glob('*.dict.yaml')):
        schema[f'flypy/{path.name}'] = path.read_bytes()
    for path in sorted((ROOT / 'lua').glob('*.lua')):
        if path.name != 'language_keys.lua':
            schema[f'lua/{path.name}'] = path.read_bytes()
    schema['lua/ios_ascii_tilde.lua'] = (IOS / 'schema/lua/ios_ascii_tilde.lua').read_bytes()
    theme = {path.name: path.read_bytes() for path in sorted((IOS / 'theme').glob('*.yaml'))}
    return {'flypy': schema, 'flypy-ios': theme}


def build_archives(output):
    output.mkdir(parents=True, exist_ok=True)
    for name, files in bundle_files().items():
        destination = output / f'{name}.zip'
        with ZipFile(destination, 'w', compression=ZIP_DEFLATED) as archive:
            for path, contents in sorted(files.items()):
                archive.writestr(f'{name}/{path}', contents)
        yield destination


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / '.local/bim')
    args = parser.parse_args()
    for archive in build_archives(args.output):
        print(archive)


if __name__ == '__main__':
    main()
