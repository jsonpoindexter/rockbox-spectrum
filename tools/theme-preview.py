#!/usr/bin/env python3
"""Capture real SDL simulator themes under Xvfb. Generated tones only; no device.

Run inside the pinned build container with its simulator and theme ZIPs.
GPL-2.0-or-later. Output must be a fresh directory; all player state is disposable.
"""
import argparse
import json
import math
import os
import shutil
import struct
import subprocess
import time
import wave
from pathlib import Path
from zipfile import ZipFile


def run(*args, **kwargs):
    return subprocess.check_output(list(args), **kwargs)


def fixture(path, scenario):
    rate = 44100
    frames = bytearray()
    frequencies = [75, 130, 220, 370, 620, 1050, 1760, 2960, 4970, 8350, 14000]
    for i in range(rate * 20):
        t = i / rate
        left = sum(math.sin(2 * math.pi * f * t) * (0.3 + 0.7 * math.sin(t * (1 + k * .17) + k) ** 2)
                   / (1 + k * .06) for k, f in enumerate(frequencies))
        beat = .35 + .65 * math.exp(-9 * (t % .5))
        sample = int(1700 * left * beat)
        frames.extend(struct.pack('<hh', sample, int(sample * .91)))
    with wave.open(str(path), 'wb') as out:
        out.setparams((2, 2, rate, 0, 'NONE', 'not compressed'))
        out.writeframes(frames)
    blob = path.read_bytes()
    tags = {'INAM': 'Midnight Circuit', 'IART': 'The Signal Room', 'IPRD': 'After Hours', 'ICRD': '2026'}
    if scenario == 'long-metadata':
        tags = {'INAM': 'Midnight Circuit — A Very Long Title for Scrolling Without Touching the Spectrum',
                'IART': 'The Signal Room with the After Hours Electronic Ensemble',
                'IPRD': 'A Long Album Name for a Small Screen', 'ICRD': '2026'}
    elif scenario == 'missing-metadata':
        tags = {}
    info = b'INFO'
    for key, value in tags.items():
        data = value.encode() + b'\0'
        info += key.encode() + struct.pack('<I', len(data)) + data + (b'\0' if len(data) % 2 else b'')
    blob += b'LIST' + struct.pack('<I', len(info)) + info
    path.write_bytes(blob[:4] + struct.pack('<I', len(blob)-8) + blob[8:])


def capture_theme(simulator, base, package, variant, output, tone, scenario):
    ident = package.name.rsplit('-', 1)[0]
    label = ident + '-' + variant
    folder = output / label
    folder.mkdir()
    root = folder / 'player'
    shutil.copytree(str(base), str(root))
    with ZipFile(str(package)) as archive:
        # Use the same validated archive reader as the installer before extraction.
        import importlib
        importlib.import_module('theme-pack').verify(package)
        archive.extractall(str(root))
    shutil.copyfile(str(tone), str(root / '00-Midnight-Circuit.wav'))
    if scenario == 'normal':
        run('convert', '-size', '116x116', 'xc:#123353', '-fill', '#3584e4',
            '-draw', 'rectangle 18,64 34,97 rectangle 50,26 66,97 rectangle 82,45 98,97',
            'BMP3:' + str(root / 'cover.bmp'))
    cfg = (root / '.rockbox/themes' / (label + '.cfg')).read_text()
    cfg += '\nstart in screen: files\nshow files: music\nbacklight timeout: on\nbacklight on button hold: on\nvolume: -30\nrepeat: all\nspectrum motion: smooth\nspectrum auto gain: on\nspectrum lane guides: on\n'
    (root / '.rockbox/config.cfg').write_text(cfg)
    if scenario == 'spectrum-off':
        with (root / '.rockbox/config.cfg').open('a') as cfgfile:
            cfgfile.write('spectrum enabled: off\n')
    log = (folder / 'simulator.log').open('w')
    runtime = folder / 'xdg'
    runtime.mkdir(mode=0o700)
    env = dict(os.environ, SDL_AUDIODRIVER='dummy', XDG_RUNTIME_DIR=str(runtime))
    process = subprocess.Popen([str(simulator), '--root', str(root), '--nobackground', '--zoom', '1'],
                               cwd=str(simulator.parent), env=env, stdout=log, stderr=subprocess.STDOUT)
    try:
        window = ''
        for attempt in range(100):
            if process.poll() is not None:
                raise RuntimeError('Simulator exited (%s): %s' % (process.returncode, folder / 'simulator.log'))
            result = subprocess.run(['xdotool', 'search', '--onlyvisible', '--pid', str(process.pid)], stdout=subprocess.PIPE)
            if result.returncode == 0 and result.stdout.strip():
                candidate = result.stdout.decode().splitlines()[-1]
                # SDL briefly creates a startup window before the LCD window.
                time.sleep(.3)
                focused = subprocess.run(['xdotool', 'windowfocus', candidate], stderr=subprocess.DEVNULL)
                if focused.returncode == 0:
                    window = candidate
                    break
            time.sleep(.1)
        if not window:
            raise RuntimeError('Simulator window not found')
        def key(name):
            run('xdotool', 'keydown', '--clearmodifiers', name)
            time.sleep(.12)
            run('xdotool', 'keyup', name)
            time.sleep(.12)
        def snap(name):
            path = folder / (name + '.png')
            run('import', '-window', window, str(path))
            size = run('identify', '-format', '%wx%h', str(path)).decode()
            if size != '320x240':
                raise RuntimeError('Unexpected capture size: ' + size)
            return path
        time.sleep(3)
        snap('browser')
        key('Return')
        time.sleep(3)
        snap('playing')
        if scenario != 'normal':
            time.sleep(3)
            snap('playing-later')
            return {'theme': label, 'scenario': scenario, 'result': 'captured',
                    'physical_device_tests': 'not performed'}
        frames = []
        for i in range(24):
            frames.append(snap('animation-%02d' % i))
            time.sleep(.06)
        run('convert', '-delay', '10', *[str(f) for f in frames], '-loop', '0', str(folder / 'playing.gif'))
        key('space')
        time.sleep(.1)
        snap('pause-tail')
        time.sleep(1)
        snap('paused')
        key('space')
        time.sleep(1)
        key('h')
        time.sleep(.7)
        snap('hold')
        key('h')
        time.sleep(.5)
        key('Escape')
        time.sleep(.5)
        snap('root-menu')
        # MENU opens the root menu; a second MENU resumes playback.
        key('Escape')
        time.sleep(.5)
        snap('resumed')
        print('Captured ' + label, flush=True)
    finally:
        process.terminate()
        try:
            process.wait(timeout=4)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
        log.close()
    return {'theme': label, 'result': 'captured', 'physical_device_tests': 'not performed'}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--simulator', type=Path, required=True)
    p.add_argument('--base', type=Path, required=True)
    p.add_argument('--packages', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--scenario', choices=['normal', 'long-metadata', 'missing-metadata', 'spectrum-off'], default='normal')
    p.add_argument('--theme', choices=['WinampSpectrum', 'StudioSpectrum', 'AdwaitaSpectrum'])
    a = p.parse_args()
    a.output = a.output.resolve()
    if a.output.exists():
        raise ValueError('Use a fresh preview output directory')
    a.output.mkdir(parents=True)
    tone = a.output / 'generated-tone.wav'
    fixture(tone, a.scenario)
    results = []
    for ident in ([a.theme] if a.theme else ['WinampSpectrum', 'StudioSpectrum', 'AdwaitaSpectrum']):
        for variant in ('Detail', 'Visualizer'):
            results.append(capture_theme(a.simulator.resolve(), a.base.resolve(),
                           a.packages.resolve() / (ident + '-1.0.zip'), variant, a.output, tone, a.scenario))
    (a.output / 'captures.json').write_text(json.dumps(results, indent=2) + '\n')


if __name__ == '__main__':
    main()
