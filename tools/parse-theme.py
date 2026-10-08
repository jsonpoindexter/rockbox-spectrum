#!/usr/bin/env python3
"""Check theme syntax with packaged bitmaps or synthetic legacy dependencies.

GPL-2.0-or-later. Font metrics and visual appearance require simulator or device checks.
"""
import argparse
import hashlib
import json
import re
import shutil
import struct
import subprocess
import tempfile
from pathlib import Path


def bitmap(path, frames):
    width, height = 16, 16 * frames
    row = b'\x40\x80\xc0' * width
    pixels = row * height
    header = struct.pack('<2sIHHI', b'BM', 54 + len(pixels), 0, 0, 54)
    header += struct.pack('<IiiHHIIiiII', 40, width, height, 1, 24, 0, len(pixels), 0, 0, 0, 0)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(header + pixels)


def check(checkwps, theme, asset_root=None):
    original = theme.read_text(encoding='utf-8')
    images = {name: 1 for name in re.findall(r'(/\.rockbox/[^,()\s<>]+\.bmp)', original)}
    for body in re.findall(r'%xl\(([^)]+)\)', original):
        fields = [part.strip() for part in body.split(',')]
        if len(fields) >= 5 and fields[1] in images:
            frames = int(fields[4])
            if not 1 <= frames <= 256:
                raise ValueError('Unexpected sprite frame count')
            images[fields[1]] = max(images[fields[1]], frames)
    with tempfile.TemporaryDirectory(prefix='spectrum-theme-parse-') as temp:
        root = Path(temp)
        if asset_root is not None:
            shutil.copytree(str(asset_root / '.rockbox'), str(root / '.rockbox'))
        for name, frames in images.items():
            path = root / name.lstrip('/')
            if root not in path.resolve().parents:
                raise ValueError('Unsafe theme asset path')
            if asset_root is None:
                bitmap(path, frames)
            elif not path.is_file():
                raise ValueError('Missing real theme bitmap: ' + name)
        copy = root / theme.name
        copy.write_text(original.replace('/.rockbox/', str(root / '.rockbox') + '/'), encoding='utf-8')
        result = subprocess.run([str(checkwps.resolve()), str(copy)], stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, universal_newlines=True, encoding='utf-8', errors='replace')
        if result.returncode:
            raise ValueError(result.stdout)
    return {'result': 'passed', 'theme': theme.name,
            'original_wps_sha256': hashlib.sha256(theme.read_bytes()).hexdigest(),
            'synthetic_bitmap_count': len(images) if asset_root is None else 0,
            'original_assets': 'not loaded' if asset_root is None else 'packaged bitmaps loaded',
            'theme_appearance': 'not tested'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('checkwps', type=Path)
    parser.add_argument('theme', type=Path)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--asset-root', type=Path)
    args = parser.parse_args()
    result = check(args.checkwps, args.theme, args.asset_root)
    data = json.dumps(result, indent=2) + '\n'
    print(data, end='')
    if args.output:
        args.output.write_text(data)


if __name__ == '__main__':
    main()
