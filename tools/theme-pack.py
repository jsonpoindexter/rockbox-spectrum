#!/usr/bin/env python3
"""Build, verify and independently install theme/preset packs. GPL-2.0-or-later.

Installation is dry-run by default. No executable, saved setting or music file
is a permitted payload. Applying a pack only copies files; selection is manual.
"""
import argparse
import hashlib
import io
import json
import re
import tempfile
from pathlib import Path, PurePosixPath
from zipfile import ZipFile, ZipInfo, ZIP_DEFLATED

from firmware_version import semver, theme_compatible

ROOT = Path(__file__).resolve().parents[1]


def digest(data):
    return hashlib.sha256(data).hexdigest()


def safe_path(name):
    parts = PurePosixPath(name).parts
    if not parts or name != PurePosixPath(name).as_posix() or '..' in parts or '\\' in name or name.startswith('/'):
        raise ValueError('Unsafe pack path: ' + name)
    return parts


def payload_path(name):
    parts = safe_path(name)
    if parts[0] != '.rockbox' or not (
        len(parts) == 3 and parts[1] in ('wps', 'themes') and
        name.endswith('.wps' if parts[1] == 'wps' else '.cfg') or
        len(parts) == 2 and re.fullmatch(r'(?:Motion-(?:Fast3|Smooth|Punchy|Classic)|VisualGain-(?:On|Off)|LaneGuides-(?:On|Off))\.cfg', parts[1])):
        raise ValueError('Pack payload must be theme text or a Spectrum preset: ' + name)


def metadata_valid(meta):
    if meta.get('schema') not in (1, 2) or meta.get('target') != 'ipod6g' or not re.fullmatch(r'[A-Za-z][A-Za-z0-9-]*', meta.get('id', '')) or not re.fullmatch(r'[0-9]+\.[0-9]+', meta.get('version', '')):
        raise ValueError('Invalid theme pack metadata')
    if meta['schema'] == 1:
        if type(meta.get('minimum_firmware_fast')) is not int or not 4 <= meta['minimum_firmware_fast'] <= 10:
            raise ValueError('Invalid legacy minimum firmware')
    else:
        if semver(meta.get('minimum_firmware_version')) < (1, 0, 0) or type(meta.get('required_skin_api')) is not int or meta['required_skin_api'] not in (1, 2):
            raise ValueError('Invalid minimum firmware/skin API')


def dependencies(files):
    refs = set()
    for data in files.values():
        text = data.decode('utf8')
        refs.update(re.findall(r'/\.rockbox/[A-Za-z0-9_./-]+\.(?:bmp|fnt|sbs|wps)', text))
        refs.update('/.rockbox/fonts/' + name for name in re.findall(r'%Fl\(\d+,([A-Za-z0-9_-]+\.fnt)\)', text))
    refs = sorted(name.lstrip('/') for name in refs if name.lstrip('/') not in files)
    for name in refs:
        if safe_path(name)[0] != '.rockbox':
            raise ValueError('Invalid asset dependency')
    return refs


def build(pack, output):
    if pack.is_symlink():
        raise ValueError('Pack source symlink refused')
    meta = json.loads((pack / 'pack.json').read_text())
    metadata_valid(meta)
    files = {}
    for path in sorted((pack / '.rockbox').rglob('*')):
        if path.is_symlink():
            raise ValueError('Pack source symlink refused')
        if path.is_file():
            name = path.relative_to(pack).as_posix()
            payload_path(name)
            files[name] = path.read_bytes()
    if not files:
        raise ValueError('Empty theme pack')
    meta['files'] = {name: digest(data) for name, data in files.items()}
    meta['dependencies'] = dependencies(files)
    files['theme-pack.json'] = (json.dumps(meta, indent=2, sort_keys=True) + '\n').encode()
    files['NOTICES.md'] = (ROOT / 'NOTICES.md').read_bytes()
    files['COPYING'] = (ROOT / 'COPYING').read_bytes()
    output.parent.mkdir(parents=True, exist_ok=True)
    # Fixed metadata produces reproducible theme ZIPs without a compiler.
    with output.open('xb') as stream, ZipFile(stream, 'w', compression=ZIP_DEFLATED) as archive:
        for name, data in sorted(files.items()):
            info = ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
            info.compress_type = ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, data)
    return verify(output)


def load_pack(package, expected=None):
    if package.stat().st_size > 2 * 1024 * 1024:
        raise ValueError('Oversized theme ZIP')
    blob = package.read_bytes()
    if expected is not None and digest(blob) != expected:
        raise ValueError('Theme package SHA-256 mismatch')
    with ZipFile(io.BytesIO(blob)) as archive:
        names = archive.namelist()
        if len(names) != len({name.casefold() for name in names}):
            raise ValueError('Duplicate member')
        if len(names) > 64 or sum(item.file_size for item in archive.infolist()) > 1024 * 1024:
            raise ValueError('Oversized theme pack')
        if archive.testzip():
            raise ValueError('CRC failure')
        for item in archive.infolist():
            safe_path(item.filename)
            if item.is_dir() or (item.external_attr >> 16) & 0o170000 == 0o120000:
                raise ValueError('Directories/symlinks are not pack payloads')
        meta = json.loads(archive.read('theme-pack.json'))
        metadata_valid(meta)
        if not meta.get('files') or set(names) != set(meta['files']) | {'theme-pack.json', 'NOTICES.md', 'COPYING'}:
            raise ValueError('Theme pack member mismatch')
        files = {}
        for name, checksum in meta['files'].items():
            payload_path(name)
            files[name] = archive.read(name)
            if digest(files[name]) != checksum:
                raise ValueError('Theme pack payload hash mismatch')
        if meta.get('dependencies') != dependencies(files):
            raise ValueError('Theme pack dependency mismatch')
    return ({'result': 'passed', 'package_sha256': digest(blob), 'metadata': meta,
             'device_tests': 'not performed'}, files)


def verify(package, expected=None):
    return load_pack(package, expected)[0]


def checked_path(volume, name):
    safe_path(name)
    path = volume / name
    for node in [path] + list(path.parents):
        if node.is_symlink():
            raise ValueError('Device path symlink refused: ' + str(node))
        if node == volume:
            break
    return path


def write_bytes(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    # Byte-only copy, no host xattrs/AppleDouble; replace one file atomically.
    with tempfile.NamedTemporaryFile(dir=str(path.parent), prefix='.theme-', delete=False) as stream:
        temp = Path(stream.name)
        stream.write(data)
    try:
        temp.replace(path)
    finally:
        if temp.exists():
            temp.unlink()


def check_current(volume, expected):
    for name, checksum in expected.items():
        path = checked_path(volume, name)
        actual = digest(path.read_bytes()) if path.exists() else None
        if actual != checksum:
            raise ValueError('Theme file changed since preview/staging: ' + name)


def write_files(volume, files):
    for name, data in files.items():
        path = checked_path(volume, name)
        if data is None:
            if path.exists():
                path.unlink()
        else:
            write_bytes(path, data)
            if path.read_bytes() != data:
                raise ValueError('Theme file readback mismatch: ' + name)


def apply_files(volume, files, expected):
    check_current(volume, expected)
    write_files(volume, files)


def install(args):
    report, files = load_pack(args.package, args.sha256)
    meta = report['metadata']
    volume = args.volume.absolute()
    info = checked_path(volume, '.rockbox/rockbox-info.txt').read_text()
    if not theme_compatible(info, meta):
        required = meta.get('minimum_firmware_version', 'compatible legacy build')
        raise ValueError('Theme needs ipod6g spectrum ' + required + ' and its required skin API')
    missing = [name for name in meta['dependencies'] if not checked_path(volume, name).is_file()]
    if missing:
        raise ValueError('Install original assets/fonts first: ' + ', '.join(missing))
    session = args.session.absolute()
    if session.resolve() == volume.resolve() or volume.resolve() in session.resolve().parents:
        raise ValueError('Session must be outside device volume')
    if session.exists():
        raise ValueError('Use a fresh theme session directory')
    previous = {name: checked_path(volume, name).read_bytes() if checked_path(volume, name).exists() else None for name in files}
    before = {name: digest(data) if data is not None else None for name, data in previous.items()}
    print(json.dumps({'action': 'install-theme', 'apply': args.apply, 'package': report,
                      'overwritten_files': [n for n, d in previous.items() if d is not None],
                      'settings_changed': False, 'firmware_changed': False}, indent=2))
    if not args.apply:
        return
    session.mkdir(parents=True)
    for name, data in previous.items():
        if data is not None:
            path = session / 'previous' / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
    state = {'volume': str(volume), 'before': before, 'after': meta['files'], 'package_sha256': report['package_sha256'], 'activation': 'pending'}
    (session / 'theme-trial.json').write_text(json.dumps(state, indent=2) + '\n')
    check_current(volume, before)
    try:
        write_files(volume, files)
    except BaseException:
        # Recover the exact affected files only; executables/settings are never touched.
        current = {name: digest(checked_path(volume, name).read_bytes()) if checked_path(volume, name).exists() else None for name in previous}
        apply_files(volume, previous, current)
        state['activation'] = 'failed; previous files restored'
        (session / 'theme-trial.json').write_text(json.dumps(state, indent=2) + '\n')
        raise
    state['activation'] = 'files verified; theme selection manual'
    (session / 'theme-trial.json').write_text(json.dumps(state, indent=2) + '\n')


def rollback(args):
    state = json.loads((args.session / 'theme-trial.json').read_text())
    volume = args.volume.absolute()
    if state['volume'] != str(volume) or state['activation'] != 'files verified; theme selection manual':
        raise ValueError('Session does not describe an installed pack on this volume')
    previous = {}
    for name, checksum in state['before'].items():
        payload_path(name)
        path = checked_path(args.session.absolute() / 'previous', name)
        previous[name] = path.read_bytes() if checksum is not None else None
        if checksum is not None and digest(previous[name]) != checksum:
            raise ValueError('Corrupt previous theme file')
    if set(previous) != set(state['after']):
        raise ValueError('Invalid session file set')
    print(json.dumps({'action': 'rollback-theme', 'apply': args.apply, 'files': sorted(previous)}, indent=2))
    # Validate even a dry run; refuse to overwrite later theme edits.
    for name, checksum in state['after'].items():
        if digest(checked_path(volume, name).read_bytes()) != checksum:
            raise ValueError('Installed theme changed; rollback refused')
    if args.apply:
        installed = {name: checked_path(volume, name).read_bytes() for name in previous}
        check_current(volume, state['after'])
        try:
            write_files(volume, previous)
        except BaseException:
            current = {name: digest(checked_path(volume, name).read_bytes()) if checked_path(volume, name).exists() else None for name in previous}
            apply_files(volume, installed, current)
            raise
        state['activation'] = 'rolled back'
        (args.session / 'theme-trial.json').write_text(json.dumps(state, indent=2) + '\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    subs = parser.add_subparsers(dest='action')
    p = subs.add_parser('build'); p.add_argument('pack', type=Path); p.add_argument('--output', type=Path, required=True)
    p = subs.add_parser('verify'); p.add_argument('package', type=Path); p.add_argument('--sha256')
    p = subs.add_parser('install'); p.add_argument('package', type=Path); p.add_argument('--sha256', required=True)
    for p in (p, subs.add_parser('rollback')):
        p.add_argument('--volume', type=Path, required=True); p.add_argument('--session', type=Path, required=True); p.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    if args.action == 'build': print(json.dumps(build(args.pack, args.output), indent=2))
    elif args.action == 'verify': print(json.dumps(verify(args.package, args.sha256), indent=2))
    elif args.action == 'install': install(args)
    elif args.action == 'rollback': rollback(args)
    else: parser.error('Choose build, verify, install or rollback')


if __name__ == '__main__':
    main()
