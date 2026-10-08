#!/usr/bin/env python3
"""Sanitized native animation tests; no device performance claim."""
from pathlib import Path
import subprocess
import tempfile
ROOT = Path(__file__).resolve().parents[1]
CORE = ROOT / 'overlay/apps/gui/spectrum'
with tempfile.TemporaryDirectory(prefix='native-visualizer-') as folder:
    exe = Path(folder) / 'test'
    subprocess.run(['cc', '-std=c99', '-O1', '-Wall', '-Wextra', '-Werror',
                    '-fsanitize=address,undefined', '-fno-sanitize-recover=all', '-I', str(CORE),
                    str(ROOT / 'tests/test_visualizer.c'), str(CORE / 'visualizer.c'),
                    '-o', str(exe)], check=True)
    subprocess.run([str(exe)], check=True)
