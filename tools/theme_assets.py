"""Pinned, build-time theme assets. Downloaded binaries are never source files.

GPL-2.0-or-later. Sources and individual archive members are both fingerprinted.
"""
import hashlib
import io
import json
import subprocess
import tempfile
from pathlib import Path
from zipfile import ZipFile

MAX_SOURCE = 64 * 1024 * 1024


def sha(data):
    return hashlib.sha256(data).hexdigest()


def assemble(pack, cache):
    lock = json.loads((pack / 'assets.json').read_text())
    cache.mkdir(parents=True, exist_ok=True)
    files = {}
    for source in lock['sources']:
        fingerprint = source['sha256']
        if len(fingerprint) != 64 or any(c not in '0123456789abcdef' for c in fingerprint):
            raise ValueError('Invalid asset fingerprint')
        path = cache / fingerprint
        if not path.exists():
            with tempfile.TemporaryDirectory(dir=str(cache)) as temp:
                download = Path(temp) / 'download'
                subprocess.run(['curl', '--fail', '--location', '--proto', '=https',
                                '--proto-redir', '=https', '--max-time', '120',
                                '--max-filesize', str(MAX_SOURCE), '--retry', '2',
                                '--silent', '--show-error', '--output', str(download),
                                source['url']], check=True)
                if download.stat().st_size > MAX_SOURCE or sha(download.read_bytes()) != fingerprint:
                    raise ValueError('Downloaded theme asset fingerprint mismatch')
                download.replace(path)
        if path.is_symlink() or path.stat().st_size > MAX_SOURCE:
            raise ValueError('Unsafe theme asset cache')
        blob = path.read_bytes()
        if sha(blob) != fingerprint:
            raise ValueError('Cached theme asset fingerprint mismatch')
        if source['format'] not in ('raw', 'zip'):
            raise ValueError('Unknown asset source format')
        archive = ZipFile(io.BytesIO(blob)) if source['format'] == 'zip' else None
        try:
            for member in source['members']:
                target = member['target']
                if target in files:
                    raise ValueError('Duplicate assembled asset')
                if archive:
                    info = archive.getinfo(member['source'])
                    if info.file_size > MAX_SOURCE:
                        raise ValueError('Oversized source member')
                    data = archive.read(info)
                else:
                    data = blob
                if sha(data) != member['sha256']:
                    raise ValueError('Theme asset member fingerprint mismatch')
                files[target] = data
        finally:
            if archive:
                archive.close()
    return files
