#!/usr/bin/env python3
"""Build and verify all targets using fresh work directories. GPL-2.0-or-later."""
import argparse
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import time
from zipfile import ZipFile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work', type=Path, required=True)
    parser.add_argument('--reports', type=Path, required=True)
    parser.add_argument('--jobs', type=int, default=4)
    args = parser.parse_args()
    work = args.work.resolve()
    reports = args.reports.resolve()
    if work.exists():
        raise SystemExit('Use a fresh CI work directory')
    work.mkdir(parents=True)
    reports.mkdir(parents=True, exist_ok=True)
    results = []

    def run(name, command):
        print('Running ' + name, flush=True)
        started = time.monotonic()
        with (reports / (name + '.log')).open('w', encoding='utf-8') as log:
            with subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT) as result:
                while True:
                    try:
                        result.wait(timeout=60)
                        break
                    except subprocess.TimeoutExpired:
                        print('{} still running ({:.0f} minutes)'.format(name, (time.monotonic() - started) / 60), flush=True)
        results.append({'step': name, 'result': 'passed' if result.returncode == 0 else 'failed'})
        (reports / 'summary.json').write_text(json.dumps({'steps': results, 'device_tests': 'not performed'}, indent=2) + '\n')
        if result.returncode:
            print((reports / (name + '.log')).read_text(encoding='utf-8', errors='replace')[-12000:])
            raise subprocess.CalledProcessError(result.returncode, command)

    try:
        run('bootstrap', [sys.executable, str(ROOT / 'tools/bootstrap-toolchain.py')])
        shutil.copyfile('/opt/toolchain/toolchain-manifest.json', str(reports / 'toolchain-manifest.json'))
        os.environ['PATH'] = '/opt/toolchain/bin:' + os.environ['PATH']
        lock = json.loads((ROOT / 'toolchain-inputs.json').read_text())
        spec = importlib.util.spec_from_file_location('bootstrap', ROOT / 'tools/bootstrap-toolchain.py')
        bootstrap = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(bootstrap)
        reference = bootstrap.fetch(lock['official_reference']['url'], work / 'official-4.0.zip', lock['official_reference']['sha256'])
        for kind, baseline in [('firmware', True), ('firmware', False), ('simulator', False), ('checkwps', False)]:
            label = ('baseline-' if baseline else 'spectrum-') + kind
            command = [sys.executable, str(ROOT / 'tools/build.py'), '--work', str(work / label), '--kind', kind, '--jobs', str(args.jobs)]
            if baseline:
                command.append('--baseline')
            run(label, command)
        checker = work / 'spectrum-checkwps/spectrum-checkwps/checkwps.ipod6g'
        run('parser', [sys.executable, str(ROOT / 'tools/parser-tests.py'), str(checker), '--output', str(reports / 'parser.json')])
        for pack in sorted((ROOT / 'theme-packs').iterdir()):
            if not pack.is_dir(): continue
            meta = json.loads((pack / 'pack.json').read_text())
            output = work / 'theme-packs' / (meta['id'] + '-' + meta['version'] + '.zip')
            run('theme-pack-' + meta['id'], [sys.executable, str(ROOT / 'tools/theme-pack.py'),
                'build', str(pack), '--output', str(output), '--asset-cache', str(work / 'theme-assets')])
            asset_root = work / 'theme-runtime' / meta['id']
            if meta['schema'] == 3:
                # The builder verifies member paths and hashes before this extraction.
                with ZipFile(str(output)) as archive:
                    archive.extractall(str(asset_root))
            for skin in sorted((pack / '.rockbox').rglob('*')):
                if skin.suffix not in ('.wps', '.sbs'): continue
                command = [sys.executable, str(ROOT / 'tools/parse-theme.py'), str(checker),
                           str(skin), '--output', str(reports / ('theme-' + skin.name + '.json'))]
                if meta['schema'] == 3: command += ['--asset-root', str(asset_root)]
                run('theme-' + skin.name, command)
        run('package', [sys.executable, str(ROOT / 'tools/verify-package.py'),
                        str(work / 'spectrum-firmware/spectrum-firmware/rockbox.zip'), str(reference), '--output', str(reports / 'package.json')])
        print('All builds, parser and package checks passed')
    finally:
        for label in ('baseline-firmware', 'spectrum-firmware', 'spectrum-simulator', 'spectrum-checkwps'):
            build = work / label / label
            if build.exists():
                for pattern in ('*.log', 'build-manifest.json', 'rockbox-info.txt'):
                    for path in build.glob(pattern):
                        target = reports / label / path.name
                        target.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copyfile(str(path), str(target))


if __name__ == '__main__':
    main()
