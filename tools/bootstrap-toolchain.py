#!/usr/bin/env python3
"""Build the pinned ARM toolchain, or verify and reuse an exact cached tree.

GPL-2.0-or-later. Python 3.6+; intended for the pinned ARM64 Linux container.
"""
import argparse
import hashlib
import importlib.util
import json
import os
import platform
import subprocess
import tarfile
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOCK = ROOT / 'toolchain-inputs.json'


def sha(path):
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def fetch(url, target, expected):
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.exists():
        pending = target.with_name(target.name + '.partial')
        try:
            with urllib.request.urlopen(url, timeout=120) as incoming, pending.open('wb') as outgoing:
                import shutil
                shutil.copyfileobj(incoming, outgoing)
            if sha(pending) != expected:
                raise ValueError('Download fingerprint mismatch: ' + target.name)
            pending.rename(target)
        finally:
            if pending.exists():
                pending.unlink()
    if sha(target) != expected:
        raise ValueError('Download fingerprint mismatch: ' + target.name)
    return target


def fingerprint():
    inputs = {name: sha(ROOT / name) for name in
              ('Dockerfile', 'toolchain-inputs.json', 'tools/bootstrap-toolchain.py')}
    inputs['architecture'] = platform.machine()
    return hashlib.sha256(json.dumps(inputs, sort_keys=True).encode()).hexdigest()


def tree_manifest(prefix):
    result = {}
    for path in sorted(prefix.rglob('*')):
        if path.name == 'toolchain-manifest.json':
            continue
        name = path.relative_to(prefix).as_posix()
        if path.is_symlink():
            result[name] = {'symlink': os.readlink(str(path))}
        elif path.is_file():
            result[name] = {'sha256': sha(path)}
        elif not path.is_dir():
            raise ValueError('Unexpected special file in toolchain')
    return result


def verify_cache(prefix, key):
    manifest = prefix / 'toolchain-manifest.json'
    if not manifest.exists():
        return False
    record = json.loads(manifest.read_text())
    if record['input_fingerprint'] != key or record['prefix'] != str(prefix):
        raise ValueError('Toolchain cache does not match pinned inputs/prefix')
    if record['files'] != tree_manifest(prefix):
        raise ValueError('Toolchain cache file verification failed')
    return True


def extract_source(archive, source, revision):
    source.mkdir()
    prefix = 'rockbox-' + revision
    with tarfile.open(str(archive)) as incoming:
        for member in incoming.getmembers():
            if member.name == prefix:
                continue
            if not member.name.startswith(prefix + '/'):
                raise ValueError('Unexpected upstream archive prefix')
            member.name = member.name[len(prefix) + 1:]
            parts = Path(member.name).parts
            if not parts or Path(member.name).is_absolute() or '..' in parts or member.islnk() or member.isdev():
                raise ValueError('Unsafe upstream archive member')
            if member.issym():
                target = (source / member.name).parent / member.linkname
                if Path(member.linkname).is_absolute() or source not in target.resolve().parents:
                    raise ValueError('Unsafe upstream archive symlink')
            incoming.extract(member, str(source))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prefix', type=Path, default=Path('/opt/toolchain'))
    parser.add_argument('--work', type=Path, default=Path('/opt/bootstrap'))
    parser.add_argument('--downloads', type=Path, default=Path('/opt/download'))
    args = parser.parse_args()
    if platform.system() != 'Linux' or platform.machine() not in ('aarch64', 'arm64'):
        raise SystemExit('Use the pinned ARM64 Linux container')
    lock = json.loads(LOCK.read_text())
    spec = importlib.util.spec_from_file_location('build', ROOT / 'tools/build.py')
    build = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(build)
    if lock['upstream_revision'] != build.REVISION or lock['source_archive_sha256'] != build.ARCHIVE_SHA:
        raise ValueError('Toolchain and firmware upstream inputs disagree')
    prefix = args.prefix.resolve()
    key = fingerprint()
    if verify_cache(prefix, key):
        print('Verified pinned toolchain cache')
        return
    prefix.mkdir(parents=True, exist_ok=True)
    if any(prefix.iterdir()):
        raise ValueError('Unverified toolchain directory is nonempty; choose a fresh prefix')
    work = args.work.resolve()
    work.mkdir(parents=True, exist_ok=True)
    source = work / 'source'
    builddir = work / 'toolchain-build'
    if source.exists() or builddir.exists():
        raise ValueError('Use a fresh bootstrap work directory')
    archive = fetch(lock['archive_url'], work / 'source.tar.gz', lock['source_archive_sha256'])
    for entry in lock['downloads']:
        fetch(entry['url'], args.downloads / entry['name'], entry['sha256'])
    extract_source(archive, source, lock['upstream_revision'])
    env = dict(os.environ)
    env.update(RBDEV_PREFIX=str(prefix), RBDEV_BUILD=str(builddir),
               RBDEV_DOWNLOAD=str(args.downloads.resolve()), GNU_MIRROR='https://ftp.gnu.org/gnu')
    # All six recipe downloads are already checksum-verified before extraction.
    subprocess.run(['bash', str(source / 'tools/rockboxdev.sh'), '--target=a'], env=env, check=True)
    compiler = str(prefix / 'bin/arm-elf-eabi-gcc')
    linker = str(prefix / 'bin/arm-elf-eabi-ld')
    gcc = subprocess.check_output([compiler, '--version'], universal_newlines=True).splitlines()[0]
    ld = subprocess.check_output([linker, '--version'], universal_newlines=True).splitlines()[0]
    if '4.9.4' not in gcc or '2.26.1' not in ld:
        raise ValueError('Unexpected compiler/binutils versions')
    manifest = {'input_fingerprint': key, 'prefix': str(prefix), 'gcc': gcc, 'binutils': ld,
                'inputs': lock, 'files': tree_manifest(prefix)}
    (prefix / 'toolchain-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print('Built and fingerprinted pinned toolchain')


if __name__ == '__main__':
    main()
