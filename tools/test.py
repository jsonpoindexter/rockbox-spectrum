#!/usr/bin/env python3
"""Run the portable suite and collect reports; no device access. GPL-2.0-or-later."""
import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=Path('reports/portable'))
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    commands = [('core', [sys.executable, str(ROOT / 'tools/run-tests.py'), '--output', str(output / 'core.json')])]
    for name in ('visualizer', 'visualizer_service', 'service_render', 'cadence', 'pause_tail', 'wps_exit', 'simulator_captures', 'animation_captures'):
        commands.append((name, [sys.executable, str(ROOT / ('tests/test_' + name + '.py'))]))
    commands.append(('fixture_tests', [sys.executable, '-m', 'unittest', 'discover', '-s', str(ROOT / 'tests'), '-p', 'test*trial.py']))
    commands.append(('build_support', [sys.executable, str(ROOT / 'tests/test_build_support.py')]))
    results = []
    for name, command in commands:
        print('Running ' + name, flush=True)
        with (output / (name + '.log')).open('w', encoding='utf-8') as log:
            result = subprocess.run(command, cwd=str(ROOT), stdout=log, stderr=subprocess.STDOUT)
        results.append({'test': name, 'result': 'passed' if result.returncode == 0 else 'failed'})
        (output / 'summary.json').write_text(json.dumps({'tests': results, 'device_tests': 'not performed'}, indent=2) + '\n')
        if result.returncode:
            print((output / (name + '.log')).read_text(encoding='utf-8', errors='replace')[-12000:])
            raise SystemExit(result.returncode)
    print('All portable checks passed')


if __name__ == '__main__':
    main()
