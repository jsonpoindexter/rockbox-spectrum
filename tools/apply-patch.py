#!/usr/bin/env python3
"""Apply the native-spectrum patch only to fingerprinted Rockbox 4.0 source."""
import argparse, hashlib, json, shutil, subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
REVISION='e094c599fa60236527f9e272e0b8309d7696e399'
def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('source',type=Path);args=parser.parse_args()
    source=args.source.resolve()
    for name,expected in json.loads((ROOT/'source-files.json').read_text()).items():
        p=source/name
        if not p.is_file() or hashlib.sha256(p.read_bytes()).hexdigest()!=expected:
            raise SystemExit(f'Refusing mismatched/already-patched source: {name}; expected {REVISION}')
    for p in (ROOT/'overlay').rglob('*'):
        if p.is_file() and (source/p.relative_to(ROOT/'overlay')).exists():
            raise SystemExit(f'Refusing existing overlay destination: {p.name}')
    patch=ROOT/'patches/0001-native-spectrum.patch'
    command=['patch','-d',str(source),'-p1','--batch']
    with patch.open('rb') as stream:subprocess.run(command+['--dry-run'],stdin=stream,check=True)
    with patch.open('rb') as stream:subprocess.run(command,stdin=stream,check=True)
    for p in (ROOT/'overlay').rglob('*'):
        if p.is_file():
            target=source/p.relative_to(ROOT/'overlay');target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,target)
    print(f'Applied spectrum patch to {source}; upstream revision {REVISION}')
if __name__=='__main__':main()
