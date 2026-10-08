#!/usr/bin/env python3
"""Verify complete custom executables, theme separation, and old English IDs."""
import argparse, hashlib, json, struct
from firmware_version import firmware
from pathlib import Path
from zipfile import ZipFile
ROOT = Path(__file__).resolve().parents[1]
OFFICIAL_SHA = '974304b7d7fa9cd916ee15eaccb7e55707dc68c77aeb75286c4c1f62935c37ac'
def language(data):
    if data[:4] != bytes.fromhex('1a064700'):
        raise ValueError('Unexpected language target/format')
    count, size, offset = struct.unpack('>HHH', data[4:10])
    if offset != 10 or len(data) != offset + size:
        raise ValueError('Unexpected language section')
    entries = {}; pos = offset
    while pos < len(data):
        ident = struct.unpack('>H', data[pos:pos+2])[0]
        end = data.index(0, pos+2)
        if ident in entries: raise ValueError('Duplicate language ID')
        entries[ident] = data[pos+2:end]; pos = end+1
    if count != len(entries): raise ValueError('Language string count mismatch')
    return entries

def verify(package, official):
    if hashlib.sha256(official.read_bytes()).hexdigest() != OFFICIAL_SHA:
        raise ValueError('Expected verified official ipod6g 4.0 reference ZIP')
    with ZipFile(package) as custom, ZipFile(official) as stock:
        names = custom.namelist()
        if len(names) != len(set(names)) or custom.testzip():
            raise ValueError('Duplicate members or CRC failure')
        info = custom.read('.rockbox/rockbox-info.txt').decode('utf8')
        version = firmware(info)
        if custom.read('.rockbox/rockbox.ipod')[4:8] != b'ip6g':
            raise ValueError('Unexpected firmware binary target')
        if '.rockbox/rocks/demos/fft.rock' not in names:
            raise ValueError('Matching FFT plugin missing')
        plugin_api = version.plugin_api
        expected_extra = {884: b'Spectrum Visualizer'}
        if plugin_api >= 275:
            expected_extra.update({885: b'Spectrum Motion', 886: b'Fast3', 887: b'Smooth',
                888: b'Punchy', 889: b'Classic', 890: b'Spectrum Auto Gain', 891: b'Spectrum Lane Guides'})
        if plugin_api >= 276:
            expected_extra.update(dict(enumerate([b'Visualization Effect', b'Theme Default',
                b'Feedback Tunnel', b'Phosphor Orbit', b'Flowing Ribbons', b'Auto Cycle'],892)))
        plugins = codecs = 0
        for name in names:
            if name.endswith('.rock'):
                if struct.unpack('<IHH', custom.read(name)[:8]) != (0x526f634b, 71, plugin_api):
                    raise ValueError('Plugin target/API mismatch: '+name)
                plugins += 1
            elif name.endswith('.codec'):
                if struct.unpack('<IHH', custom.read(name)[:8]) not in ((0x52434f44, 71, 50), (0x52454e43, 71, 50)):
                    raise ValueError('Codec target/API mismatch: '+name)
                codecs += 1
        if plugins == 0 or codecs == 0: raise ValueError('Incomplete executables')
        # Custom themes/presets are independently packaged. Upstream default
        # themes are still shipped by Rockbox's standard make zip target.
        theme_files = {'.rockbox/' + p.relative_to(pack / '.rockbox').as_posix()
                       for pack in (ROOT / 'theme-packs').iterdir() if pack.is_dir()
                       for p in (pack / '.rockbox').rglob('*') if p.is_file()}
        if theme_files.intersection(names):
            raise ValueError('Custom theme/preset found in firmware package')
        old = language(stock.read('.rockbox/langs/english.lng'))
        new = language(custom.read('.rockbox/langs/english.lng'))
        if any(new.get(ident) != text for ident, text in old.items()):
            raise ValueError('Existing English ID/text changed; menu overlay unsafe')
        if old[21] != b'Database' or old[27] != b'Plugins' or set(new)-set(old) != set(expected_extra) or any(new.get(i) != value for i,value in expected_extra.items()):
            raise ValueError('Unexpected language extension/menu IDs')
    return {'result':'passed','package_sha256':hashlib.sha256(package.read_bytes()).hexdigest(),'firmware_release':None if version.release is None else '.'.join(map(str,version.release)), 'plugins_checked':plugins,'plugin_api':plugin_api,'codecs_checked':codecs,'codec_api':50,'unchanged_english_ids':len(old),'appended_english_ids':sorted(expected_extra),'custom_theme_files':0,'theme_packs_included':False,'device_tests':'not performed'}
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('package',type=Path);p.add_argument('official',type=Path);p.add_argument('--output',type=Path);a=p.parse_args()
    result=verify(a.package,a.official);text=json.dumps(result,indent=2)+'\n';print(text,end='')
    if a.output:a.output.write_text(text,encoding='utf8')
if __name__=='__main__':main()
