#!/usr/bin/env python3
"""Check saved simulator pixels, independently of image-preview presentation.

The JSON manifest names a reference image, logical 320x240 regions, and
captures with a subset of regions to compare. ImageMagick is required. This
verifies persistent fixture text; it is not OCR or hardware acceptance.
"""
import argparse
import hashlib
import json
import shutil
import subprocess
from pathlib import Path


def pixels(path):
    convert = shutil.which('magick') or shutil.which('convert')
    if not convert:
        raise ValueError('ImageMagick magick/convert is required')
    identify = [convert, 'identify'] if Path(convert).name == 'magick' else [shutil.which('identify')]
    if not identify[0]:
        raise ValueError('ImageMagick identify is required')
    size = subprocess.check_output(identify + ['-format', '%w %h', str(path)]).decode().split()
    width, height = map(int, size)
    if (width, height) not in ((320, 240), (640, 480)):
        raise ValueError('Expected a 320x240 or 2x simulator capture: ' + str(path))
    data = subprocess.check_output([convert, str(path), '-filter', 'point',
                                   '-resize', '320x240!', '-depth', '8', 'RGB:-'])
    if len(data) != 320 * 240 * 3:
        raise ValueError('Unexpected image payload: ' + str(path))
    return data


def region(data, bounds):
    x0, y0, x1, y1 = bounds
    if not all(type(v) is int for v in bounds) or not (0 <= x0 < x1 <= 320 and 0 <= y0 < y1 <= 240):
        raise ValueError('Invalid region bounds')
    return b''.join(data[(y * 320 + x0) * 3:(y * 320 + x1) * 3] for y in range(y0, y1))


def nonblack(data, background=b'\0\0\0'):
    return sum(data[i:i + 3] != background for i in range(0, len(data), 3))


def verify(manifest_path):
    manifest_path = Path(manifest_path).resolve()
    spec = json.loads(manifest_path.read_text(encoding='utf-8'))
    background = spec.get('background_rgb', [0,0,0])
    if not isinstance(background, list) or len(background) != 3 or any(type(c) is not int or not 0 <= c <= 255 for c in background):
        raise ValueError('Invalid explicit background RGB')
    background_bytes = bytes(background)
    base = manifest_path.parent
    reference = pixels(base / spec['reference'])
    expected = {}
    for name, bounds in spec['regions'].items():
        data = region(reference, bounds)
        count = nonblack(data, background_bytes)
        if count < 32:
            raise ValueError('Reference region has insufficient text pixels: ' + name)
        expected[name] = data
    if not expected or not spec['captures']:
        raise ValueError('Reference regions and captures are required')
    results = []
    captured = {}
    checked_fields = set()
    for item in spec['captures']:
        name = item['file']
        data = pixels(base / name)
        captured[name] = data
        if nonblack(data, background_bytes) < 128:
            raise ValueError('Blank capture: ' + name)
        checks = {}
        for field in item['regions']:
            actual = region(data, spec['regions'][field])
            if actual != expected[field]:
                raise ValueError('Metadata differs: ' + name + ' / ' + field)
            checked_fields.add(field)
            checks[field] = {'nonbackground_pixels': nonblack(actual, background_bytes),
                             'rgb_sha256': hashlib.sha256(actual).hexdigest()}
        results.append({'file': name, 'state': item['state'], 'regions': checks,
                        'file_sha256': hashlib.sha256((base / name).read_bytes()).hexdigest()})
    if checked_fields != set(expected):
        raise ValueError('Some reference regions were never checked')
    animations = []
    for pair in spec.get('animation_pairs', []):
        a, b = [region(captured[name], pair['bounds']) for name in pair['files']]
        if a == b or not nonblack(a, background_bytes) or not nonblack(b, background_bytes):
            raise ValueError('Animation did not change: ' + repr(pair['files']))
        animations.append({'files': pair['files'], 'changed': True})
    for name in spec.get('blank_spectrum', []):
        if nonblack(region(captured[name], spec['spectrum_bounds']), background_bytes):
            raise ValueError('Suspended spectrum is not blank: ' + name)
    for name in spec.get('guided_silence', []):
        actual = region(captured[name], spec['spectrum_bounds'])
        x0, y0, x1, y1 = spec['spectrum_bounds']
        width, height = x1-x0, y1-y0
        expected_guides = bytearray(bytes(background)*width*height)
        bands = spec['guide_bands']
        if type(bands) is not int or bands not in (8,16,32) or width < 4*bands or height < 4:
            raise ValueError('Invalid guided-spectrum geometry')
        if spec.get('guide_pattern') in ('unfilled-bar-dots', 'thin-unfilled-bar-dots', 'single-separator-dots', 'uniform-dim-dots') and (height < 8 or width < 8*bands):
            raise ValueError('Unfilled-bar guides need three-pixel borders')
        pitch = 4 if spec.get('guide_pattern') == 'volume-dots' else 2
        for bar in range(bands):
            left = bar*width//bands; right = (bar+1)*width//bands-2
            for y in range(height):
                for x in range(left,right+1):
                    if spec.get('guide_pattern') == 'uniform-dim-dots':
                        dot = ((y == 0 or y == height-2) and (x-left) % 4 == 0) or \
                            (3 <= y < height-3 and bar > 0 and x == left and y % 4 == 0)
                        color = 191 if dot else None
                    elif spec.get('guide_pattern') == 'single-separator-dots':
                        dot = (y % 2 == 0 and (x-left) % 4 == y % 4) if y < 3 or y >= height-3 else \
                            (bar > 0 and x == left and y % 4 == 0)
                        color = 255 if dot else None
                    elif spec.get('guide_pattern') == 'thin-unfilled-bar-dots':
                        dot = (y % 2 == 0 and (x-left) % 4 == y % 4) if y < 3 or y >= height-3 else \
                            (x == left and y % 4 == 0) or (x == right and y % 4 == 2)
                        color = 255 if dot else None
                    elif spec.get('guide_pattern') == 'unfilled-bar-dots':
                        edge = x-left < 3 or right-x < 3 or y < 3 or y >= height-3
                        dot = y % 2 == 0 and (x-left) % 4 == y % 4
                        color = 255 if edge and dot else None
                    elif y in (0,height-1): color = 32 if (x-left)%pitch==0 else 0
                    elif x in (left,right): color = 32 if y%pitch==0 else 0
                    else: color = 72 if y==height-2 and (x-left-1)%pitch==0 else 0
                    offset=(y*width+x)*3
                    if color is not None:
                        expected_guides[offset:offset+3]=bytes([(color>>3)*255//31,(color>>2)*255//63,(color>>3)*255//31])
        if actual != bytes(expected_guides):
            raise ValueError('Paused area differs from independent lane/baseline mask: '+name)
    decay=[]
    for name in spec.get('pause_decay', []):
        data=region(captured[name],spec['spectrum_bounds'])
        # Data bars have a chromatic classic palette; guides are neutral gray.
        count=sum(max(data[i:i+3])-min(data[i:i+3])>64 for i in range(0,len(data),3))
        decay.append({'file':name,'colored_bar_pixels':count})
    if decay and (decay[0]['colored_bar_pixels']==0 or decay[-1]['colored_bar_pixels']!=0 or
                  any(b['colored_bar_pixels']>a['colored_bar_pixels'] for a,b in zip(decay,decay[1:])) or
                  len({d['colored_bar_pixels'] for d in decay})<3):
        raise ValueError('Pause sequence lacks monotonic intermediate bar decay')
    return {'pause_decay':decay,'result': 'passed', 'reference': spec['reference'], 'captures': results,
            'animation_pairs': animations, 'blank_spectrum': spec.get('blank_spectrum', []), 'guided_silence': spec.get('guided_silence', []),
            'method': 'Exact RGB bytes of fixture metadata, normalized with nearest-neighbor sampling; saved files, not image previews',
            'device_tests': 'not performed'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('manifest', type=Path)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    try:
        result = verify(args.manifest)
    except (ValueError, KeyError, subprocess.CalledProcessError) as error:
        parser.exit(1, str(error) + '\n')
    serialized = json.dumps(result, indent=2) + '\n'
    if args.output:
        args.output.write_text(serialized, encoding='utf-8')
    print(serialized)


if __name__ == '__main__':
    main()
